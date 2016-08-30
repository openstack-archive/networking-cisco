# Copyright 2014 Cisco Systems, Inc.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import loopingcall
from oslo_utils import importutils

from neutron.common import rpc as n_rpc
from neutron import manager

import networking_cisco.plugins
from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)
from networking_cisco.plugins.cisco.db.device_manager import (
    hosting_device_manager_db as dev_mgr_db)
from networking_cisco.plugins.cisco.db.scheduler import (
    cfg_agentschedulers_db as agt_sched_db)
from networking_cisco.plugins.cisco.device_manager.rpc import (
    devices_cfgagent_rpc_cb as devices_rpc)
from networking_cisco.plugins.cisco.device_manager.rpc import (
    devmgr_rpc_cfgagent_api)
from networking_cisco.plugins.cisco.extensions import ciscocfgagentscheduler
from networking_cisco.plugins.cisco.extensions import ciscohostingdevicemanager

LOG = logging.getLogger(__name__)


class CiscoDeviceManagerPlugin(dev_mgr_db.HostingDeviceManagerMixin,
                               agt_sched_db.CfgAgentSchedulerDbMixin):
    """Implementation of Cisco Device Manager Service Plugin for Neutron.

    This class implements a (hosting) device manager service plugin that
    provides hosting device template and hosting device resources. As such
    it manages associated REST API processing. All DB functionality is
    implemented in class hosting_device_manager_db.HostingDeviceManagerMixin.
    """
    supported_extension_aliases = [
        ciscohostingdevicemanager.HOSTING_DEVICE_MANAGER_ALIAS,
        ciscocfgagentscheduler.CFG_AGENT_SCHEDULER_ALIAS]
    path_prefix = ciscocfgagentscheduler.PATH_PREFIX

    def __init__(self):
        self.setup_rpc()
        basepath = networking_cisco.plugins.__path__[0]
        ext_paths = [basepath + '/cisco/extensions']
        cp = cfg.CONF.api_extensions_path
        to_add = ""
        for ext_path in ext_paths:
            if cp.find(ext_path) == -1:
                to_add += ':' + ext_path
        if to_add != "":
            cfg.CONF.set_override('api_extensions_path', cp + to_add)
        self.cfg_agent_scheduler = importutils.import_object(
            cfg.CONF.general.configuration_agent_scheduler_driver)
        self._setup_cfg_agent_monitoring()

    def setup_rpc(self):
        # RPC support
        self.topic = c_constants.DEVICE_MANAGER_PLUGIN
        self.conn = n_rpc.create_connection()
        self.agent_notifiers[c_constants.AGENT_TYPE_CFG] = (
            devmgr_rpc_cfgagent_api.DeviceMgrCfgAgentNotifyAPI(self))
        self.endpoints = [devices_rpc.DeviceMgrCfgRpcCallback(self)]
        self.conn.create_consumer(self.topic, self.endpoints, fanout=False)
        self.conn.consume_in_threads()

    def _setup_cfg_agent_monitoring(self):
        LOG.debug('Activating periodic config agent monitor')
        self._heartbeat = loopingcall.FixedIntervalLoopingCall(
            self._check_config_agents)
        self._heartbeat.start(
            interval=cfg.CONF.general.cfg_agent_monitoring_interval)

    @property
    def _core_plugin(self):
        try:
            return self._plugin
        except AttributeError:
            self._plugin = manager.NeutronManager.get_plugin()
            return self._plugin
