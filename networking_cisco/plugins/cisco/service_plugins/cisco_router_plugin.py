# Copyright 2015 Cisco Systems, Inc.  All rights reserved.
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

from oslo_config import cfg
from oslo_utils import importutils

from neutron.api.rpc.agentnotifiers import l3_rpc_agent_api
from neutron.api.rpc.handlers import l3_rpc
from neutron.common import constants as neutron_constants
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron.db import common_db_mixin
#from neutron.db import l3_gwmode_db
from neutron import manager
from neutron.plugins.common import constants

import networking_cisco.plugins
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.db.l3 import ha_db
from networking_cisco.plugins.cisco.db.l3 import l3_router_appliance_db
from networking_cisco.plugins.cisco.db.l3 import routertype_db
from networking_cisco.plugins.cisco.db.scheduler import (
    l3_routertype_aware_schedulers_db as router_sch_db)
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routerhostingdevice
from networking_cisco.plugins.cisco.extensions import routerrole
from networking_cisco.plugins.cisco.extensions import routertype
from networking_cisco.plugins.cisco.extensions import routertypeawarescheduler
from networking_cisco.plugins.cisco.l3.rpc import (
    l3_router_cfg_agent_rpc_cb as l3cfg_rpc)
from networking_cisco.plugins.cisco.l3.rpc import l3_router_rpc_cfg_agent_api


class CiscoRouterPlugin(common_db_mixin.CommonDbMixin,
                        routertype_db.RoutertypeDbMixin,
                        ha_db.HA_db_mixin,
                        l3_router_appliance_db.L3RouterApplianceDBMixin,
                        #l3_gwmode_db.L3_NAT_db_mixin,
                        router_sch_db.L3RouterTypeAwareSchedulerDbMixin):

    """Implementation of Cisco L3 Router Service Plugin for Neutron.

    This class implements a L3 service plugin that provides
    router and floatingip resources and manages associated
    request/response.
    All DB functionality is implemented in class
    l3_router_appliance_db.L3RouterApplianceDBMixin.
    """
    supported_extension_aliases = [
        "router",  # "ext-gw-mode",
        "standard-attr-description",
        "extraroute", "l3_agent_scheduler",
        routerhostingdevice.ROUTERHOSTINGDEVICE_ALIAS,
        routerrole.ROUTERROLE_ALIAS,
        routertype.ROUTERTYPE_ALIAS,
        routertypeawarescheduler.ROUTERTYPE_AWARE_SCHEDULER_ALIAS,
        ha.HA_ALIAS]

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
        self.router_scheduler = importutils.import_object(
            cfg.CONF.routing.router_type_aware_scheduler_driver)
        self.l3agent_scheduler = importutils.import_object(
            cfg.CONF.router_scheduler_driver)

    def setup_rpc(self):
        # RPC support
        self.topic = topics.L3PLUGIN
        self.conn = n_rpc.create_connection()
        self.agent_notifiers[neutron_constants.AGENT_TYPE_L3] = (
            l3_rpc_agent_api.L3AgentNotifyAPI())
        self.agent_notifiers[cisco_constants.AGENT_TYPE_L3_CFG] = (
            l3_router_rpc_cfg_agent_api.L3RouterCfgAgentNotifyAPI(self))
        self.endpoints = [l3_rpc.L3RpcCallback(),
                          l3cfg_rpc.L3RouterCfgRpcCallback(self)]
        self.conn.create_consumer(self.topic, self.endpoints,
                                  fanout=False)
        # Consume from all consumers in threads
        self.conn.consume_in_threads()

    def get_plugin_type(self):
        return constants.L3_ROUTER_NAT

    def get_plugin_description(self):
        return ("Cisco Router Service Plugin for basic L3 forwarding"
                " between (L2) Neutron networks and access to external"
                " networks via a NAT gateway.")

    def create_floatingip(self, context, floatingip):
        """Create floating IP.

        :param context: Neutron request context
        :param floatingip: data for the floating IP being created
        :returns: A floating IP object on success

        As the l3 router plugin asynchronously creates floating IPs
        leveraging the l3 agent and l3 cfg agent, the initial status for the
        floating IP object will be DOWN.
        """
        return super(CiscoRouterPlugin, self).create_floatingip(
            context, floatingip,
            initial_status=neutron_constants.FLOATINGIP_STATUS_DOWN)

    @property
    def _core_plugin(self):
        try:
            return self._plugin
        except AttributeError:
            self._plugin = manager.NeutronManager.get_plugin()
            return self._plugin
