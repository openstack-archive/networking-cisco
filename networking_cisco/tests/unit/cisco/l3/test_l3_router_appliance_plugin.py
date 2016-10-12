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

import contextlib
import os


import mock
from oslo_config import cfg
from oslo_db import exception as db_exc
from oslo_utils import uuidutils
import six
from sqlalchemy import exc as inner_db_exc
import unittest

from neutron.api.v2 import attributes
from neutron.callbacks import registry
from neutron.common import constants as l3_constants
from neutron import context as n_context
from neutron.db import agents_db
from neutron.extensions import external_net as external_net
from neutron.extensions import extraroute
from neutron.extensions import l3
from neutron.extensions import providernet as pnet
from neutron import manager
from neutron.plugins.common import constants as service_constants
from neutron.tests.unit.db import test_db_base_plugin_v2
from neutron.tests.unit.extensions import test_extraroute
from neutron.tests.unit.extensions import test_l3

from networking_cisco._i18n import _
from networking_cisco import backwards_compatibility as bc
import networking_cisco.plugins
from networking_cisco.plugins.cisco.common import cisco_constants as c_const
from networking_cisco.plugins.cisco.db.l3 import l3_router_appliance_db
from networking_cisco.plugins.cisco.device_manager import service_vm_lib
from networking_cisco.plugins.cisco.extensions import ciscohostingdevicemanager
from networking_cisco.plugins.cisco.extensions import routertype
from networking_cisco.tests.unit.cisco.device_manager import (
    device_manager_test_support)
from networking_cisco.tests.unit.cisco.device_manager import (
    test_db_device_manager)
from networking_cisco.tests.unit.cisco.l3 import l3_router_test_support
from networking_cisco.tests.unit.cisco.l3 import test_db_routertype

_uuid = uuidutils.generate_uuid


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

    def cleanup_after_test(self):
        """Reset all class variables to their default values.
        This is needed to avoid tests to pollute subsequent tests.
        """
        TestApplianceL3RouterServicePlugin._router_schedulers = {}
        TestApplianceL3RouterServicePlugin._router_drivers = {}
        TestApplianceL3RouterServicePlugin._namespace_router_type_id = None
        TestApplianceL3RouterServicePlugin._backlogged_routers = set()
        TestApplianceL3RouterServicePlugin._refresh_router_backlog = True


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
        self.l3_plugin = manager.NeutronManager.get_service_plugins().get(
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
            self._mock_cfg_agent_notifier(self.l3_plugin)
        # mock the periodic router backlog processing in the tests
        self._mock_backlog_processing(self.l3_plugin)

    def restore_attribute_map(self):
        # Restore the original RESOURCE_ATTRIBUTE_MAP
        attributes.RESOURCE_ATTRIBUTE_MAP = self.saved_attr_map

    def tearDown(self):
        if self.configure_routertypes is True:
            self._test_remove_routertypes()
            self._test_remove_hosting_device_templates()
        if self._created_mgmt_nw is True:
            self._remove_mgmt_nw_for_tests()
        self.l3_plugin.cleanup_after_test()
        self.core_plugin.cleanup_after_test()
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
        # Remove any dict extend functions that our plugin does not support
        _dict_extend_functions = l3_router_appliance_db.DICT_EXTEND_FUNCTIONS
        _dict_extend_functions.append('_extend_router_dict_extraroute')
        for func in self.plugin._dict_extend_functions[l3.ROUTERS][:]:
            if func in l3_router_appliance_db.DICT_EXTEND_FUNCTIONS:
                continue
            self.plugin._dict_extend_functions[l3.ROUTERS].remove(func)

    def test_schedule_router_pre_and_post_commit(self):
        hdts = self._list(
            'hosting_device_templates',
            query_params='name=%s' % test_db_device_manager.HW_TEMPLATE_NAME)
        hdt_id = hdts['hosting_device_templates'][0]['id']
        with mock.patch.object(
                self.l3_plugin, '_refresh_router_backlog', False),\
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
                self.l3_plugin._process_backlogged_routers()
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
                mock.patch.object(self.l3_plugin, '_get_effective_slot_need',
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
                self.l3_plugin.unschedule_router_from_hosting_device(
                    n_context.get_admin_context(), binding_mock)
            pre_mock.assert_has_calls([mock.call(mock.ANY, mock.ANY)])
            post_mock.assert_has_calls([mock.call(mock.ANY, mock.ANY)])

    def test_create_router_pre_and_post(self):
        driver = mock.Mock()
        self.l3_plugin._get_router_type_driver = mock.Mock(
            return_value=driver)
        router = {'router': {'tenant_id': 'foo',
                             'admin_state_up': True,
                             'name': 'bar'}}
        ctx = n_context.get_admin_context()
        self.l3_plugin.create_router(ctx, router)
        driver.create_router_precommit.assert_called_once_with(
            ctx, mock.ANY)
        driver.create_router_postcommit.assert_called_once_with(
            ctx, mock.ANY)

    def test_update_router_pre_and_post(self):
        driver = mock.Mock()
        self.l3_plugin._get_router_type_driver = mock.Mock(
            return_value=driver)
        with self.router() as router:
            r = router['router']
            ctx = n_context.get_admin_context()
            self.l3_plugin.update_router(ctx, r['id'], router)
            driver.update_router_precommit.assert_called_once_with(
                ctx, mock.ANY)
            driver.update_router_postcommit.assert_called_once_with(
                ctx, mock.ANY)

    def test_delete_router_pre_and_post(self):
        driver = mock.Mock()
        self.l3_plugin._get_router_type_driver = mock.Mock(
            return_value=driver)
        with self.router() as router:
            r = router['router']
            ctx = n_context.get_admin_context()
            self.l3_plugin.delete_router(ctx, r['id'])
            driver.delete_router_precommit.assert_called_once_with(
                ctx, mock.ANY)
            driver.delete_router_postcommit.assert_called_once_with(
                ctx, mock.ANY)

    def test_add_router_interface_pre_and_post_subnet(self):
        driver = mock.Mock()
        self.l3_plugin._get_router_type_driver = mock.Mock(
            return_value=driver)
        with self.router() as router, self.subnet(cidr='10.0.1.0/24') as sub:
            r = router['router']
            s1 = sub['subnet']
            ctx = n_context.get_admin_context()
            info = {'subnet_id': s1['id']}
            self.l3_plugin.add_router_interface(ctx, r['id'], info)
            driver.add_router_interface_precommit.assert_called_once_with(
                ctx, mock.ANY)
            driver.add_router_interface_postcommit.assert_called_once_with(
                ctx, mock.ANY)

    def test_add_router_interface_pre_and_post_port(self):
        driver = mock.Mock()
        self.l3_plugin._get_router_type_driver = mock.Mock(
            return_value=driver)
        with self.router() as router, self.port(cidr='10.0.1.0/24') as port:
            r = router['router']
            p1 = port['port']
            ctx = n_context.get_admin_context()
            info = {'port_id': p1['id']}
            self.l3_plugin.add_router_interface(ctx, r['id'], info)
            driver.add_router_interface_precommit.assert_called_once_with(
                ctx, mock.ANY)
            driver.add_router_interface_postcommit.assert_called_once_with(
                ctx, mock.ANY)

    def test_remove_router_interface_pre_and_post_subnet(self):
        driver = mock.Mock()
        self.l3_plugin._get_router_type_driver = mock.Mock(
            return_value=driver)
        with self.router() as router, self.subnet(cidr='10.0.1.0/24') as sub:
            r = router['router']
            s1 = sub['subnet']
            ctx = n_context.get_admin_context()
            info = {'subnet_id': s1['id']}
            self.l3_plugin.add_router_interface(ctx, r['id'], info)
            self.l3_plugin.remove_router_interface(ctx, r['id'], info)
            driver.remove_router_interface_precommit.assert_called_once_with(
                ctx, mock.ANY)
            driver.remove_router_interface_postcommit.assert_called_once_with(
                ctx, mock.ANY)

    def test_remove_router_interface_pre_and_post_port(self):
        driver = mock.Mock()
        self.l3_plugin._get_router_type_driver = mock.Mock(
            return_value=driver)
        with self.router() as router, self.port(cidr='10.0.1.0/24') as port:
            r = router['router']
            p1 = port['port']
            ctx = n_context.get_admin_context()
            info = {'port_id': p1['id']}
            self.l3_plugin.add_router_interface(ctx, r['id'], info)
            self.l3_plugin.remove_router_interface(ctx, r['id'], info)
            driver.remove_router_interface_precommit.assert_called_once_with(
                ctx, mock.ANY)
            driver.remove_router_interface_postcommit.assert_called_once_with(
                ctx, mock.ANY)

    def test_create_floating_ip_post(self):
        driver = mock.Mock()
        self.l3_plugin._get_router_type_driver = mock.Mock(
            return_value=driver)
        with self.subnet() as ext_s, self.subnet(cidr='10.0.1.0/24') as s:
            s1 = ext_s['subnet']
            ext_net_id = s1['network_id']
            self._set_net_external(ext_net_id)
            with self.router(
                    external_gateway_info={'network_id': ext_net_id}) as r,\
                    self.port(s) as p:
                self._router_interface_action('add', r['router']['id'], None,
                                              p['port']['id'])
                p1 = p['port']
                fip = {'floatingip': {'floating_network_id': ext_net_id,
                                      'port_id': p1['id'],
                                      'tenant_id': s1['tenant_id']}}
                ctx = n_context.get_admin_context()
                self.l3_plugin.create_floatingip(ctx, fip)
                driver.create_floatingip_postcommit.assert_called_once_with(
                    ctx, mock.ANY)

    def test_update_floating_ip_pre_and_post(self):
        driver = mock.Mock()
        self.l3_plugin._get_router_type_driver = mock.Mock(
            return_value=driver)
        with self.subnet() as ext_s, self.subnet(cidr='10.0.1.0/24') as s:
            s1 = ext_s['subnet']
            ext_net_id = s1['network_id']
            self._set_net_external(ext_net_id)
            with self.router(
                    external_gateway_info={'network_id': ext_net_id}) as r,\
                    self.port(s) as p:
                self._router_interface_action('add', r['router']['id'], None,
                                              p['port']['id'])
                p1 = p['port']
                fip = {'floatingip': {'floating_network_id': ext_net_id,
                                      'port_id': p1['id'],
                                      'tenant_id': s1['tenant_id']}}
                ctx = n_context.get_admin_context()
                floating_ip = self.l3_plugin.create_floatingip(ctx, fip)
                fip = {'floatingip': {'port_id': None}}
                self.l3_plugin.update_floatingip(ctx, floating_ip['id'], fip)
                driver.update_floatingip_precommit.assert_called_once_with(
                    ctx, mock.ANY)
                fip = {'floatingip': {'floating_network_id': ext_net_id,
                                      'port_id': p1['id'],
                                      'tenant_id': s1['tenant_id']}}
                self.l3_plugin.update_floatingip(ctx, floating_ip['id'], fip)
                driver.update_floatingip_postcommit.assert_called_once_with(
                    ctx, mock.ANY)

    def test_delete_floating_ip_pre_and_post(self):
        driver = mock.Mock()
        self.l3_plugin._get_router_type_driver = mock.Mock(
            return_value=driver)
        with self.subnet() as ext_s, self.subnet(cidr='10.0.1.0/24') as s:
            s1 = ext_s['subnet']
            ext_net_id = s1['network_id']
            self._set_net_external(ext_net_id)
            with self.router(
                    external_gateway_info={'network_id': ext_net_id}) as r,\
                    self.port(s) as p:
                self._router_interface_action('add', r['router']['id'], None,
                                              p['port']['id'])
                p1 = p['port']
                fip = {'floatingip': {'floating_network_id': ext_net_id,
                                      'port_id': p1['id'],
                                      'tenant_id': s1['tenant_id']}}
                ctx = n_context.get_admin_context()
                floating_ip = self.l3_plugin.create_floatingip(ctx, fip)
                self.l3_plugin.delete_floatingip(ctx, floating_ip['id'])
                driver.delete_floatingip_precommit.assert_called_once_with(
                    ctx, mock.ANY)
                driver.delete_floatingip_postcommit.assert_called_once_with(
                    ctx, mock.ANY)


class L3RouterApplianceNamespaceTestCase(
    test_l3.L3NatTestCaseBase, test_extraroute.ExtraRouteDBTestCaseBase,
        L3RouterApplianceTestCaseBase):

    router_type = c_const.NAMESPACE_ROUTER_TYPE

    def test_floatingip_with_assoc_fails(self):
        self._test_floatingip_with_assoc_fails(
            'neutron.db.l3_db.L3_NAT_dbonly_mixin._check_and_get_fip_assoc')

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

    @unittest.skipIf(bc.NEUTRON_VERSION < bc.NEUTRON_NEWTON_VERSION,
                     "Test not applicable prior to Newton")
    def test_create_router_gateway_fails_nested_delete_router_failed(self):
        (super(L3RouterApplianceNamespaceTestCase, self).
         test_create_router_gateway_fails_nested_delete_router_failed())
        # must disable the UT patches so that our router type cleanup,
        # which deletes any remaining routers, can proceed
        mock.patch.stopall()


class L3AgentRouterApplianceTestCase(L3RouterApplianceTestCaseBase,
                                     test_l3.L3AgentDbTestCaseBase):

    router_type = c_const.NAMESPACE_ROUTER_TYPE

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        super(L3AgentRouterApplianceTestCase, self).setUp(
            core_plugin=core_plugin, l3_plugin=l3_plugin, dm_plugin=dm_plugin,
            ext_mgr=ext_mgr)
        # UTs in parent class expects self.plugin to refer to l3 plugin
        self.plugin = self.l3_plugin

    # Overloaded test function that needs to be modified to run
    @unittest.skipIf(bc.NEUTRON_VERSION < bc.NEUTRON_NEWTON_VERSION,
                     "Test not applicable prior to Newton")
    def test_router_delete_event_exception_preserved(self):
        super(L3AgentRouterApplianceTestCase,
              self).test_router_delete_event_exception_preserved()
        registry.clear()

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
        self.orig_get_sync_data = self.l3_plugin.get_sync_data
        self.l3_plugin.get_sync_data = self.l3_plugin.get_sync_data_ext
        self._mock_get_routertype_scheduler_always_none()
        # Some UTs in parent class expects self.plugin to refer to l3 plugin
        self.plugin = self.l3_plugin

    def tearDown(self):
        self.l3_plugin.get_sync_data = self.orig_get_sync_data
        super(L3CfgAgentRouterApplianceTestCase, self).tearDown()

    # Overloaded test function that needs to be modified to run
    @unittest.skipIf(bc.NEUTRON_VERSION < bc.NEUTRON_NEWTON_VERSION,
                     "Test not applicable prior to Newton")
    def test_router_delete_event_exception_preserved(self):
        super(L3CfgAgentRouterApplianceTestCase,
              self).test_router_delete_event_exception_preserved()
        registry.clear()

    def _test_notify_op_agent(self, target_func, *args):
        kargs = [item for item in args]
        kargs.append(self._l3_cfg_agent_mock)
        target_func(*kargs)

    def test_failed_add_gw_hosting_port_info_changes_router_status(self,
                                                                   num=1):
        with self.subnet() as ext_s, self.subnet(cidr='10.0.1.0/24') as s:
            ext_net_id = ext_s['subnet']['network_id']
            self._set_net_external(ext_net_id)
            with self.router(
                    external_gateway_info={'network_id': ext_net_id}) as r,\
                    self.port(s) as p:
                self._router_interface_action('add', r['router']['id'], None,
                                              p['port']['id'])
                with mock.patch.object(
                        self.l3_plugin,
                        'add_type_and_hosting_device_info') as m1,\
                        mock.patch.object(
                            self.l3_plugin,
                            '_populate_hosting_info_for_port') as m2,\
                        mock.patch.object(
                            self._core_plugin,
                            'get_hosting_device_plugging_driver'):
                    m1.side_effect = lambda ctx, r, bi=None, sch=None: (
                        r.update({'hosting_device': {'id': 'fake_id'}}))
                    m2.return_value = None
                    routers = self.l3_plugin.get_sync_data(
                        n_context.get_admin_context(), None)
                    self.assertEqual(num, len(routers))
                    self.assertEqual(c_const.ROUTER_INFO_INCOMPLETE,
                                     routers[0]['status'])
                    self.assertEqual(num, m2.call_count)

    def test_failed_add_hosting_port_info_changes_router_status(self, num=1):
        with self.router() as r, self.subnet(cidr='10.0.1.0/24') as s2:
            with self.port() as p1, self.port(s2) as p2:
                r_id = r['router']['id']
                self._router_interface_action('add', r_id, None,
                                              p1['port']['id'])
                self._router_interface_action('add', r_id, None,
                                              p2['port']['id'])
                with mock.patch.object(
                        self.l3_plugin,
                        'add_type_and_hosting_device_info') as m1,\
                        mock.patch.object(
                            self.l3_plugin,
                            '_populate_hosting_info_for_port') as m2,\
                        mock.patch.object(
                            self._core_plugin,
                            'get_hosting_device_plugging_driver'):
                    m1.side_effect = lambda ctx, r, bi=None, sch=None: (
                        r.update({'hosting_device': {'id': 'fake_id'}}))
                    m2.return_value = None
                    routers = self.l3_plugin.get_sync_data(
                        n_context.get_admin_context(), None)
                    self.assertEqual(num, len(routers))
                    self.assertEqual(c_const.ROUTER_INFO_INCOMPLETE,
                                     routers[0]['status'])
                    self.assertEqual(num, m2.call_count)

    def test__allocate_hosting_port_returns_none_if_binding_fails(self):
        with self.router() as r, self.port() as p1:
            r_id = r['router']['id']
            p1_id = p1['port']['id']
            self._router_interface_action('add', r_id, None, p1_id)
            plugging_drv_mock = mock.MagicMock()
            plugging_drv_mock.allocate_hosting_port.return_value = {
                'allocated_port_id': p1_id, 'allocated_vlan': 10}
            adm_ctx = n_context.get_admin_context()
            p1_db = self._core_plugin._get_port(adm_ctx, p1_id)
            ctx_mock = mock.MagicMock()
            ctx_mock.session = mock.MagicMock()
            ctx_mock.session.begin = adm_ctx.session.begin
            ctx_mock.session.add = mock.MagicMock()
            ctx_mock.session.add.side_effect = db_exc.DBReferenceError(
                'cisco_port_mappings', 'foreign key constraint', p1_id,
                'ports', inner_exception=inner_db_exc.IntegrityError(
                    "Invalid insert", params="", orig=None))
            res = self.l3_plugin._allocate_hosting_port(
                ctx_mock, r_id, p1_db, 'fake_hd_id', plugging_drv_mock)
            self.assertIsNone(res)


class L3RouterApplianceGbpTestCase(test_l3.L3NatTestCaseMixin,
                                   L3RouterApplianceTestCaseBase):

    router_type = "ASR1k_Neutron_router"

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        super(L3RouterApplianceGbpTestCase, self).setUp(
            core_plugin=core_plugin, l3_plugin=l3_plugin, dm_plugin=dm_plugin,
            ext_mgr=ext_mgr)
        self._created_mgmt_nw = False

    @contextlib.contextmanager
    def _mock_neutron_service_plugins(self):
        """Context manager for mocking get_service_plugins

        This is required to mock and unmock the function as close to where its
        being used as possible.
        """
        with mock.patch.object(manager.NeutronManager,
                               'get_service_plugins') as get_svc_plugin:
            get_svc_plugin.return_value = {
                'GROUP_POLICY': object(),
                service_constants.L3_ROUTER_NAT: self}
            yield get_svc_plugin

    def test_is_gbp_workflow(self):
        with self._mock_neutron_service_plugins():
            self.assertTrue(self.l3_plugin.is_gbp_workflow)

    def test_create_floatingip_gbp(self):
        kwargs = {'arg_list': (external_net.EXTERNAL,),
                  external_net.EXTERNAL: True}
        self.l3_plugin._update_fip_assoc = mock.Mock()
        with self.network(**kwargs) as net:
            with self.subnet(network=net, cidr='200.0.0.0/22') as sub:
                subnet = sub['subnet']
                # dummy func is used to verify that our stub was called
                dummy_func = mock.Mock()

                def _stub_modify_context(context, fip_context):
                    context.nat_pool_list = [{'subnet_id': subnet['id']}]
                    dummy_func(context)

                mock_drvr = mock.Mock()
                mock_drvr.create_floatingip_precommit = _stub_modify_context
                self.l3_plugin._get_router_type_driver = mock.Mock(
                    return_value=mock_drvr
                )
                network = net['network']
                floating_ip = {
                    'floatingip': {'floating_network_id': network['id'],
                                   'tenant_id': net['network']['tenant_id']}
                }
                ctx = n_context.get_admin_context()
                with self._mock_neutron_service_plugins():
                    self.l3_plugin.create_floatingip(ctx, floating_ip)
                dummy_func.assert_called_once_with(ctx)
                mock_drvr.create_floatingip_postcommit.assert_called_once_with(
                    ctx, mock.ANY)
                self.l3_plugin._update_fip_assoc.assert_called_once_with(ctx,
                    mock.ANY, mock.ANY, mock.ANY)

    def test_update_floatingip_gbp(self):
        self.l3_plugin._do_update_floatingip = mock.Mock()
        ctx = n_context.get_admin_context()
        TEST_FIP_UUID = _uuid()
        floating_ip = {
            'floatingip': {'floating_network_id': _uuid()}
        }
        with self._mock_neutron_service_plugins():
            self.l3_plugin.update_floatingip(ctx, TEST_FIP_UUID, floating_ip)
        self.l3_plugin._do_update_floatingip.assert_called_once_with(ctx,
            TEST_FIP_UUID, floating_ip, add_fip=True)


class L3RouterApplianceNoGbpTestCase(test_l3.L3NatTestCaseMixin,
                                     L3RouterApplianceTestCaseBase):
    router_type = "ASR1k_Neutron_router"

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        super(L3RouterApplianceNoGbpTestCase, self).setUp(
            core_plugin=core_plugin, l3_plugin=l3_plugin, dm_plugin=dm_plugin,
            ext_mgr=ext_mgr)
        self._created_mgmt_nw = False

    def test_is_not_gbp_workflow(self):
        self.assertFalse(self.l3_plugin.is_gbp_workflow)

    def test_create_floatingip_gbp(self):
        self.l3_plugin._update_fip_assoc = mock.Mock()
        self.l3_plugin._create_floatingip_neutron = mock.Mock()
        self.l3_plugin._create_floatingip_gbp = mock.Mock()
        ctx = n_context.get_admin_context()
        floating_ip = {
            'floatingip': {'floating_network_id': _uuid()}
        }
        self.l3_plugin.create_floatingip(ctx, floating_ip)
        self.l3_plugin._create_floatingip_gbp.assert_not_called()
        self.l3_plugin._create_floatingip_neutron.assert_called_once_with(ctx,
            floating_ip, initial_status=l3_constants.FLOATINGIP_STATUS_ACTIVE)

    def test_update_floatingip_no_gbp(self):
        self.l3_plugin._do_update_floatingip = mock.Mock()
        ctx = n_context.get_admin_context()
        TEST_FIP_UUID = _uuid()
        floating_ip = {
            'floatingip': {'floating_network_id': _uuid()}
        }
        self.l3_plugin.update_floatingip(ctx, TEST_FIP_UUID, floating_ip)
        self.l3_plugin._do_update_floatingip.assert_called_once_with(ctx,
            TEST_FIP_UUID, floating_ip)
