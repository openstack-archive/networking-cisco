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

import unittest

from oslo_config import cfg
from oslo_utils import importutils

from neutron.api.rpc.agentnotifiers import dhcp_rpc_agent_api
from neutron.common import constants
from neutron.common import topics
from neutron.db import agentschedulers_db
from neutron.plugins.ml2 import rpc
from neutron.tests.unit.db import test_agentschedulers_db

from networking_cisco.plugins.cisco.common import cisco_constants as c_const
from networking_cisco.plugins.cisco.extensions import (
    ciscohostingdevicemanager as ciscodevmgr)
from networking_cisco.tests.unit.cisco.device_manager import (
    device_manager_test_support)
from networking_cisco.tests.unit.cisco.device_manager import (
    test_db_device_manager)
from networking_cisco.tests.unit.cisco.l3 import (
    test_l3_routertype_aware_schedulers)
from networking_cisco.tests.unit.cisco.l3 import l3_router_test_support
from networking_cisco.tests.unit.cisco.l3 import test_db_routertype


L3_HOSTA = test_agentschedulers_db.L3_HOSTA
L3_HOSTB = test_agentschedulers_db.L3_HOSTB

CORE_PLUGIN_KLASS = ('networking_cisco.tests.unit.cisco.l3'
                     '.test_agent_scheduler.TestAgentSchedCorePlugin')
L3_PLUGIN_KLASS = test_l3_routertype_aware_schedulers.L3_PLUGIN_KLASS


# A core plugin supporting Cisco device manager functionality
class TestAgentSchedCorePlugin(device_manager_test_support.TestCorePlugin,
                               agentschedulers_db.DhcpAgentSchedulerDbMixin):

    supported_extension_aliases = ["external-net", "agent",
                                   constants.DHCP_AGENT_SCHEDULER_EXT_ALIAS,
                                   ciscodevmgr.HOSTING_DEVICE_MANAGER_ALIAS]

    def __init__(self):
        self.network_scheduler = importutils.import_object(
            cfg.CONF.network_scheduler_driver)
        super(TestAgentSchedCorePlugin, self).__init__()
        self._start_rpc_notifiers()

    def _start_rpc_notifiers(self):
        """Initialize RPC notifiers for agents."""
        self.notifier = rpc.AgentNotifierApi(topics.AGENT)
        self.agent_notifiers[constants.AGENT_TYPE_DHCP] = (
            dhcp_rpc_agent_api.DhcpAgentNotifyAPI())


class L3RouterApplianceL3AgentSchedulerTestCase(
    test_agentschedulers_db.OvsAgentSchedulerTestCase,
    test_db_routertype.RoutertypeTestCaseMixin,
    test_db_device_manager.DeviceManagerTestCaseMixin,
    l3_router_test_support.L3RouterTestSupportMixin,
        device_manager_test_support.DeviceManagerTestSupportMixin):

    resource_prefix_map = (test_db_device_manager.TestDeviceManagerDBPlugin
                           .resource_prefix_map)

    def setup_coreplugin(self, core_plugin=None):
        # NOTE(bobmel): we override this function to make sure our core plugin,
        # which includes device manager functionality, is used for the tests
        cp_str = CORE_PLUGIN_KLASS if core_plugin == "ml2" else core_plugin
        super(L3RouterApplianceL3AgentSchedulerTestCase,
              self).setup_coreplugin(cp_str)

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        self.plugin_str = (CORE_PLUGIN_KLASS if core_plugin is None
                           else core_plugin)
        self.l3_plugin = (L3_PLUGIN_KLASS if l3_plugin is None
                          else l3_plugin)

        self._define_keystone_authtoken()
        cfg.CONF.set_override('api_extensions_path',
                              l3_router_test_support.extensions_path)
        cfg.CONF.set_override('default_router_type',
                              c_const.NAMESPACE_ROUTER_TYPE, group='routing')

        super(L3RouterApplianceL3AgentSchedulerTestCase, self).setUp()

        self._mock_l3_admin_tenant()
        templates = self._test_create_hosting_device_templates()
        self._test_create_routertypes(templates.values())
        # mock the periodic router backlog processing in the tests
        self._mock_backlog_processing(self.l3plugin)

    def tearDown(self):
        self._test_remove_routertypes()
        self._test_remove_hosting_device_templates()
        super(L3RouterApplianceL3AgentSchedulerTestCase, self).tearDown()

    @unittest.skip("DVR not supported")
    def test_dvr_router_scheduling_to_only_dvr_snat_agent(self):
        pass

    @unittest.skip("DVR not supported")
    def test_dvr_router_csnat_rescheduling(self):
        pass

    @unittest.skip("DVR not supported")
    def test_dvr_router_manual_rescheduling(self):
        pass

    @unittest.skip("DVR not supported")
    def test_sync_dvr_router(self):
        pass


class L3RouterApplianceL3AgentNotifierTestCase(
    test_agentschedulers_db.OvsL3AgentNotifierTestCase,
    test_db_routertype.RoutertypeTestCaseMixin,
    test_db_device_manager.DeviceManagerTestCaseMixin,
    l3_router_test_support.L3RouterTestSupportMixin,
        device_manager_test_support.DeviceManagerTestSupportMixin):

    resource_prefix_map = (test_db_device_manager.TestDeviceManagerDBPlugin
                           .resource_prefix_map)

    def setup_coreplugin(self, core_plugin=None):
        # NOTE(bobmel): we override this function to make sure our core plugin,
        # which includes device manager functionality, is used for the tests
        cp_str = CORE_PLUGIN_KLASS if core_plugin == "ml2" else core_plugin
        super(L3RouterApplianceL3AgentNotifierTestCase, self).setup_coreplugin(
            cp_str)

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        self.plugin_str = (CORE_PLUGIN_KLASS if core_plugin is None
                           else core_plugin)
        self.l3_plugin = (L3_PLUGIN_KLASS if l3_plugin is None
                          else l3_plugin)

        self._define_keystone_authtoken()
        cfg.CONF.set_override('api_extensions_path',
                              l3_router_test_support.extensions_path)
        cfg.CONF.set_override('default_router_type',
                              c_const.NAMESPACE_ROUTER_TYPE, group='routing')

        super(L3RouterApplianceL3AgentNotifierTestCase, self).setUp()

        self._mock_l3_admin_tenant()
        templates = self._test_create_hosting_device_templates()
        self._test_create_routertypes(templates.values())

    def tearDown(self):
        self._test_remove_routertypes()
        self._test_remove_hosting_device_templates()
        super(L3RouterApplianceL3AgentNotifierTestCase, self).tearDown()
