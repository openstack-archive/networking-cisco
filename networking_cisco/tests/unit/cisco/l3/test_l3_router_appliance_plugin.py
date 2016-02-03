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

import os

import mock
from oslo_config import cfg
from oslo_log import log as logging
import six

from neutron.api.v2 import attributes
from neutron import context as q_context
from neutron.db import agents_db
from neutron.extensions import extraroute
from neutron.extensions import l3
from neutron.extensions import providernet as pnet
from neutron import manager
from neutron.plugins.common import constants as service_constants
from neutron.tests.unit.db import test_db_base_plugin_v2
from neutron.tests.unit.extensions import test_extraroute
from neutron.tests.unit.extensions import test_l3

from networking_cisco._i18n import _
import networking_cisco.plugins
from networking_cisco.plugins.cisco.common import cisco_constants as c_const
from networking_cisco.plugins.cisco.device_manager import service_vm_lib
from networking_cisco.plugins.cisco.extensions import ciscohostingdevicemanager
from networking_cisco.plugins.cisco.extensions import routertype
from networking_cisco.tests.unit.cisco.device_manager import (
    device_manager_test_support)
from networking_cisco.tests.unit.cisco.device_manager import (
    test_db_device_manager)
from networking_cisco.tests.unit.cisco.l3 import l3_router_test_support
from networking_cisco.tests.unit.cisco.l3 import test_db_routertype

LOG = logging.getLogger(__name__)


CORE_PLUGIN_KLASS = device_manager_test_support.CORE_PLUGIN_KLASS
L3_PLUGIN_KLASS = (
    'networking_cisco.tests.unit.cisco.l3.test_l3_router_appliance_plugin.'
    'TestApplianceL3RouterServicePlugin')
extensions_path = networking_cisco.plugins.__path__[0] + '/cisco/extensions'
policy_path = (os.path.abspath(networking_cisco.__path__[0]) +
               '/../etc/policy.json')


class TestL3RouterApplianceExtensionManager(
        test_db_routertype.L3TestRoutertypeExtensionManager):

    def get_resources(self):
        l3.RESOURCE_ATTRIBUTE_MAP['routers'].update(
            extraroute.EXTENDED_ATTRIBUTES_2_0['routers'])
        return super(TestL3RouterApplianceExtensionManager,
                     self).get_resources()


class TestNoL3NatPlugin(test_l3.TestNoL3NatPlugin,
                        agents_db.AgentDbMixin):

    # There is no need to expose agent REST API
    supported_extension_aliases = ["external-net", "provider"]
    NET_TYPE = 'vlan'

    def __init__(self):
        self.tags = {}
        self.tag = 1
        super(TestNoL3NatPlugin, self).__init__()

    def _make_network_dict(self, network, fields=None,
                           process_extensions=True):
        res = {'id': network['id'],
               'name': network['name'],
               'tenant_id': network['tenant_id'],
               'admin_state_up': network['admin_state_up'],
               'status': network['status'],
               'shared': network['shared'],
               'subnets': [subnet['id']
                           for subnet in network['subnets']]}
        try:
            tag = self.tags[network['id']]
        except KeyError:
            self.tag += 1
            tag = self.tag
            self.tags[network['id']] = tag
        res.update({pnet.PHYSICAL_NETWORK: 'phy',
                    pnet.NETWORK_TYPE: self.NET_TYPE,
                    pnet.SEGMENTATION_ID: tag})
        # Call auxiliary extend functions, if any
        if process_extensions:
            self._apply_dict_extend_functions(
                attributes.NETWORKS, res, network)
        return self._fields(res, fields)

    def get_network_profiles(self, context, filters=None, fields=None):
        return [{'id': "1234"}]

    def get_policy_profiles(self, context, filters=None, fields=None):
        return [{'id': "4321"}]


# A set routes capable L3 routing service plugin class supporting appliances
class TestApplianceL3RouterServicePlugin(
        l3_router_test_support.TestL3RouterServicePlugin):

    supported_extension_aliases = (
        l3_router_test_support.TestL3RouterServicePlugin.
        supported_extension_aliases + ["extraroute"])


class L3RouterApplianceTestCaseBase(
    test_db_base_plugin_v2.NeutronDbPluginV2TestCase,
    test_db_routertype.RoutertypeTestCaseMixin,
    test_db_device_manager.DeviceManagerTestCaseMixin,
    l3_router_test_support.L3RouterTestSupportMixin,
        device_manager_test_support.DeviceManagerTestSupportMixin):

    resource_prefix_map = (test_db_device_manager.TestDeviceManagerDBPlugin
                           .resource_prefix_map)
    router_type = None
    configure_routertypes = True
    mock_cfg_agent_notifiers = True

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None, create_mgmt_nw=True, service_plugins=None):
        # Save the global RESOURCE_ATTRIBUTE_MAP
        self.saved_attr_map = {}
        for resource, attrs in six.iteritems(
                attributes.RESOURCE_ATTRIBUTE_MAP):
            self.saved_attr_map[resource] = attrs.copy()
        if not core_plugin:
            core_plugin = CORE_PLUGIN_KLASS
        if l3_plugin is None:
            l3_plugin = L3_PLUGIN_KLASS
        if not service_plugins:
            service_plugins = {'l3_plugin_name': l3_plugin}
        cfg.CONF.set_override('api_extensions_path',
                              l3_router_test_support.extensions_path)

        # for these tests we need to enable overlapping ips
        cfg.CONF.set_default('allow_overlapping_ips', True)
        cfg.CONF.set_default('max_routes', 3)
        if ext_mgr is None:
            ext_mgr = TestL3RouterApplianceExtensionManager()

        super(L3RouterApplianceTestCaseBase, self).setUp(
            plugin=core_plugin, service_plugins=service_plugins,
            ext_mgr=ext_mgr)

        # Ensure we use policy definitions from our repo
        cfg.CONF.set_override('policy_file', policy_path, 'oslo_policy')

        self.core_plugin = manager.NeutronManager.get_plugin()
        self.plugin = manager.NeutronManager.get_service_plugins().get(
            service_constants.L3_ROUTER_NAT)

        self.setup_notification_driver()

        cfg.CONF.set_override('allow_sorting', True)
        self._define_keystone_authtoken()

        cfg.CONF.register_opt(
            cfg.BoolOpt('router_auto_schedule', default=True,
                        help=_('Allow auto scheduling of routers to '
                               'L3 agent.')))
        if self.router_type is not None:
            cfg.CONF.set_override('default_router_type', self.router_type,
                                  group='routing')

        self._mock_l3_admin_tenant()
        self._created_mgmt_nw = create_mgmt_nw
        if create_mgmt_nw is True:
            self._create_mgmt_nw_for_tests(self.fmt)
        if self.configure_routertypes is True:
            templates = self._test_create_hosting_device_templates()
            self._test_create_routertypes(templates.values())
        # in unit tests we don't use keystone so we mock that session
        self.core_plugin._svc_vm_mgr_obj = service_vm_lib.ServiceVMManager(
            True, None, None, None, '', keystone_session=mock.MagicMock())
        self._mock_svc_vm_create_delete(self.core_plugin)
        self._mock_io_file_ops()
        if self.mock_cfg_agent_notifiers is True:
            self._mock_cfg_agent_notifier(self.plugin)
        # mock the periodic router backlog processing in the tests
        self._mock_backlog_processing(self.plugin)

    def restore_attribute_map(self):
        # Restore the original RESOURCE_ATTRIBUTE_MAP
        attributes.RESOURCE_ATTRIBUTE_MAP = self.saved_attr_map

    def tearDown(self):
        if self.configure_routertypes is True:
            self._test_remove_routertypes()
            self._test_remove_hosting_device_templates()
        if self._created_mgmt_nw is True:
            self._remove_mgmt_nw_for_tests()
        TestApplianceL3RouterServicePlugin._router_schedulers = {}
        TestApplianceL3RouterServicePlugin._router_drivers = {}
        TestApplianceL3RouterServicePlugin._namespace_router_type_id = None
        TestApplianceL3RouterServicePlugin._backlogged_routers = set()
        TestApplianceL3RouterServicePlugin._refresh_router_backlog = True
        device_manager_test_support.TestCorePlugin._l3_tenant_uuid = None
        device_manager_test_support.TestCorePlugin._mgmt_nw_uuid = None
        device_manager_test_support.TestCorePlugin._mgmt_subnet_uuid = None
        device_manager_test_support.TestCorePlugin._mgmt_sec_grp_id = None
        device_manager_test_support.TestCorePlugin._credentials = {}
        device_manager_test_support.TestCorePlugin._plugging_drivers = {}
        device_manager_test_support.TestCorePlugin._hosting_device_drivers = {}
        device_manager_test_support.TestCorePlugin._hosting_device_locks = {}
        device_manager_test_support.TestCorePlugin._cfgagent_scheduler = None
        device_manager_test_support.TestCorePlugin._cfg_agent_statuses = {}
        device_manager_test_support.TestCorePlugin._svc_vm_mgr_obj = None
        device_manager_test_support.TestCorePlugin._nova_running = False

        self.restore_attribute_map()
        super(L3RouterApplianceTestCaseBase, self).tearDown()


class L3RouterApplianceRouterTypeDriverTestCase(test_l3.L3NatTestCaseMixin,
                                                L3RouterApplianceTestCaseBase):
    #TODO(bobmel): Add unit tests for the other driver methods when those are
    # actually called

    #NOTE(bobmel): Work-around to make these unit tests to work since we
    # let the core plugin implement the device manager service.
    # The device manager service should map to hosting device extension
    service_constants.EXT_TO_SERVICE_MAPPING[
        ciscohostingdevicemanager.HOSTING_DEVICE_MANAGER_ALIAS] = (
        c_const.DEVICE_MANAGER)
    routertype = test_db_routertype.HW_ROUTERTYPE_NAME

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        super(L3RouterApplianceRouterTypeDriverTestCase, self).setUp(
            core_plugin, l3_plugin, dm_plugin, ext_mgr)

    def test_schedule_router_pre_and_post_commit(self):
        hdts = self._list(
            'hosting_device_templates',
            query_params='name=%s' % test_db_device_manager.HW_TEMPLATE_NAME)
        hdt_id = hdts['hosting_device_templates'][0]['id']
        with mock.patch.object(
                self.plugin, '_refresh_router_backlog', False),\
                mock.patch('networking_cisco.plugins.cisco.l3.drivers.'
                           'noop_routertype_driver.NoopL3RouterDriver.'
                           'schedule_router_precommit') as pre_mock,\
                mock.patch('networking_cisco.plugins.cisco.l3.drivers.'
                       'noop_routertype_driver.NoopL3RouterDriver.'
                       'schedule_router_postcommit') as post_mock,\
                mock.patch('networking_cisco.plugins.cisco.db.l3.'
                           'l3_router_appliance_db.L3RouterApplianceDBMixin.'
                           '_get_router_type_scheduler') as scheduler_mock,\
                mock.patch.object(
                    self.core_plugin,
                    'acquire_hosting_device_slots') as acquire_mock,\
                self.hosting_device(hdt_id) as hosting_device:
            hd = hosting_device['hosting_device']
            scheduler_mock.return_value.schedule_router.return_value = (
                [hd['id']])
            acquire_mock.return_value = True
            with self.router():
                self.plugin._process_backlogged_routers()
                pre_mock.assert_has_calls([mock.call(mock.ANY, mock.ANY)])
                post_mock.assert_has_calls([mock.call(mock.ANY, mock.ANY)])

    def test_unschedule_router_pre_and_post_commit(self):
        with mock.patch('networking_cisco.plugins.cisco.l3.drivers.'
                        'noop_routertype_driver.NoopL3RouterDriver.'
                        'unschedule_router_precommit') as pre_mock,\
                mock.patch('networking_cisco.plugins.cisco.l3.drivers.'
                           'noop_routertype_driver.NoopL3RouterDriver.'
                           'unschedule_router_postcommit') as post_mock,\
                mock.patch('networking_cisco.plugins.cisco.db.l3.'
                           'l3_router_appliance_db.L3RouterApplianceDBMixin.'
                           '_get_router_type_scheduler') as scheduler_mock,\
                mock.patch.object(self.plugin, '_get_effective_slot_need',
                                  return_value=5),\
                mock.patch.object(self.core_plugin,
                                  'release_hosting_device_slots') as (
                    release_mock):
            scheduler_mock.return_value.unschedule_router.return_value = True
            release_mock.return_value = True
            with self.router() as router,\
                    mock.patch('networking_cisco.plugins.cisco.db.l3.'
                               'l3_router_appliance_db.'
                               'L3RouterApplianceDBMixin.'
                               '_extend_router_dict_routerrole'),\
                    mock.patch('networking_cisco.plugins.cisco.db.l3.'
                               'l3_router_appliance_db.'
                               'L3RouterApplianceDBMixin.'
                               '_extend_router_dict_routertype'),\
                    mock.patch('networking_cisco.plugins.cisco.db.l3.'
                               'l3_router_appliance_db.'
                               'L3RouterApplianceDBMixin.'
                               '_extend_router_dict_routerhostingdevice'),\
                    mock.patch('networking_cisco.plugins.cisco.db.scheduler'
                               '.l3_routertype_aware_schedulers_db.'
                               'L3RouterTypeAwareSchedulerDbMixin.'
                               '_extend_router_dict_scheduling_info'):
                r = router['router']
                binding_mock = mock.MagicMock()
                binding_mock.router_id = r['id']
                binding_mock.router_type_id = r[routertype.TYPE_ATTR]
                r['gw_port_id'] = None
                r['route_list'] = []
                binding_mock.router = r
                self.plugin.unschedule_router_from_hosting_device(
                    q_context.get_admin_context(), binding_mock)
            pre_mock.assert_has_calls([mock.call(mock.ANY, mock.ANY)])
            post_mock.assert_has_calls([mock.call(mock.ANY, mock.ANY)])


class L3RouterApplianceNamespaceTestCase(
    test_l3.L3NatTestCaseBase, test_extraroute.ExtraRouteDBTestCaseBase,
        L3RouterApplianceTestCaseBase):

    router_type = c_const.NAMESPACE_ROUTER_TYPE

    def test_floatingip_with_assoc_fails(self):
        self._test_floatingip_with_assoc_fails(
            'neutron.db.l3_db.L3_NAT_dbonly_mixin._check_and_get_fip_assoc')

    def test_router_add_interface_port(self):
        # workaround for this particular test, since in our class self.plugin
        # is the L3 router service plugin and not the core plugin
        plugin = self.plugin
        self.plugin = self.core_plugin
        super(L3RouterApplianceNamespaceTestCase,
              self).test_router_add_interface_port()
        # restore the order
        self.plugin = plugin

    def _check_driver_calls(self, func_name, num_teardown, num_setup):
        with mock.patch.object(self.core_plugin,
                               'get_hosting_device_plugging_driver') as m:
            func = getattr(super(L3RouterApplianceNamespaceTestCase, self),
                           func_name, None)
            # call test case function
            func()
            drv = m.return_value
            teardown_mock = drv.teardown_logical_port_connectivity
            setup_mock = drv.setup_logical_port_connectivity
            self.assertEqual(teardown_mock.call_count, num_teardown)
            self.assertEqual(setup_mock.call_count, num_setup)

    def test_router_update_gateway_with_external_ip_used_by_gw(self):
        self._check_driver_calls(
            'test_router_update_gateway_with_external_ip_used_by_gw', 0, 0)

    def test_router_update_gateway_with_invalid_external_ip(self):
        self._check_driver_calls(
            'test_router_update_gateway_with_invalid_external_ip', 0, 0)

    def test_router_update_gateway_with_invalid_external_subnet(self):
        self._check_driver_calls(
            'test_router_update_gateway_with_invalid_external_subnet', 0, 0)

    def test_router_update_gateway_with_existed_floatingip(self):
        self._check_driver_calls(
            'test_router_update_gateway_with_existed_floatingip', 1, 1)

    def test_router_update_gateway_to_empty_with_existed_floatingip(self):
        self._check_driver_calls(
            'test_router_update_gateway_to_empty_with_existed_floatingip', 1,
            1)


class L3RouterApplianceVMTestCase(L3RouterApplianceNamespaceTestCase):

    router_type = c_const.CSR1KV_ROUTER_TYPE

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        super(L3RouterApplianceVMTestCase, self).setUp(
            core_plugin=core_plugin, l3_plugin=l3_plugin, dm_plugin=dm_plugin,
            ext_mgr=ext_mgr)

        self._mock_get_routertype_scheduler_always_none()


class L3AgentRouterApplianceTestCase(L3RouterApplianceTestCaseBase,
                                     test_l3.L3AgentDbTestCaseBase):

    router_type = c_const.NAMESPACE_ROUTER_TYPE

    def _test_notify_op_agent(self, target_func, *args):
        kargs = [item for item in args]
        kargs.append(self._l3_agent_mock)
        target_func(*kargs)


class L3CfgAgentRouterApplianceTestCase(L3RouterApplianceTestCaseBase,
                                        test_l3.L3AgentDbTestCaseBase):

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        super(L3CfgAgentRouterApplianceTestCase, self).setUp(
            core_plugin=core_plugin, l3_plugin=l3_plugin, dm_plugin=dm_plugin,
            ext_mgr=ext_mgr)

        self.orig_get_sync_data = self.plugin.get_sync_data
        self.plugin.get_sync_data = self.plugin.get_sync_data_ext

        self._mock_get_routertype_scheduler_always_none()

    def tearDown(self):
        self.plugin.get_sync_data = self.orig_get_sync_data
        super(L3CfgAgentRouterApplianceTestCase, self).tearDown()

    def _test_notify_op_agent(self, target_func, *args):
        kargs = [item for item in args]
        kargs.append(self._l3_cfg_agent_mock)
        target_func(*kargs)
