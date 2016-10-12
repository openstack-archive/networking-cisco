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

import copy
import mock

from oslo_config import cfg
from oslo_utils import uuidutils
from sqlalchemy.orm import exc
import unittest
import webob.exc

from neutron.callbacks import events
from neutron.callbacks import registry
from neutron.callbacks import resources
from neutron import context
from neutron.db import l3_db
from neutron.extensions import extraroute
from neutron.extensions import l3
from neutron import manager
from neutron.plugins.common import constants as service_constants
from neutron.tests import fake_notifier

from neutron_lib import constants as l3_constants

from networking_cisco import backwards_compatibility as bc
import networking_cisco.plugins
from networking_cisco.plugins.cisco.common import (
    cisco_constants as cisco_const)
from networking_cisco.plugins.cisco.db.l3 import ha_db
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.tests.unit.cisco.device_manager import (
    device_manager_test_support)
from networking_cisco.tests.unit.cisco.l3 import (
    test_l3_router_appliance_plugin)
from networking_cisco.tests.unit.cisco.l3 import test_db_routertype


_uuid = uuidutils.generate_uuid

EXTERNAL_GW_INFO = l3.EXTERNAL_GW_INFO

CORE_PLUGIN_KLASS = device_manager_test_support.CORE_PLUGIN_KLASS
DEFAULT_PRIORITY = ha_db.DEFAULT_MASTER_PRIORITY
L3_PLUGIN_KLASS = (
    "networking_cisco.tests.unit.cisco.l3.test_ha_l3_router_appliance_plugin."
    "TestApplianceHAL3RouterServicePlugin")
extensions_path = networking_cisco.plugins.__path__[0] + '/cisco/extensions'

DEVICE_OWNER_ROUTER_INTF = l3_constants.DEVICE_OWNER_ROUTER_INTF


def _sort_routes(routes):
    return sorted(routes, key=lambda route: route['destination'])


class TestHAL3RouterApplianceExtensionManager(
        test_db_routertype.L3TestRoutertypeExtensionManager):

    def get_resources(self):
        l3.RESOURCE_ATTRIBUTE_MAP['routers'].update(
            extraroute.EXTENDED_ATTRIBUTES_2_0['routers'])
        l3.RESOURCE_ATTRIBUTE_MAP['routers'].update(
            ha.EXTENDED_ATTRIBUTES_2_0['routers'])
        return super(TestHAL3RouterApplianceExtensionManager,
                     self).get_resources()


# A set routes and HA capable L3 routing service plugin class
# supporting appliances
class TestApplianceHAL3RouterServicePlugin(
    ha_db.HA_db_mixin,
        test_l3_router_appliance_plugin.TestApplianceL3RouterServicePlugin):

    supported_extension_aliases = (
        test_l3_router_appliance_plugin.TestApplianceL3RouterServicePlugin.
        supported_extension_aliases + [ha.HA_ALIAS])

    def cleanup_after_test(self):
        """Reset all class variables to their default values.
        This is needed to avoid tests to pollute subsequent tests.
        """
        TestApplianceHAL3RouterServicePlugin._router_schedulers = {}
        TestApplianceHAL3RouterServicePlugin._router_drivers = {}
        TestApplianceHAL3RouterServicePlugin._namespace_router_type_id = None
        TestApplianceHAL3RouterServicePlugin._backlogged_routers = set()
        TestApplianceHAL3RouterServicePlugin._refresh_router_backlog = True


# TODO(bobmel): Add tests that ensures that Cisco HA is not applied on
# Namespace-based routers
class HAL3RouterApplianceNamespaceTestCase(
        test_l3_router_appliance_plugin.L3RouterApplianceNamespaceTestCase):

    _is_ha_tests = True

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        if l3_plugin is None:
            l3_plugin = L3_PLUGIN_KLASS
        if ext_mgr is None:
            ext_mgr = TestHAL3RouterApplianceExtensionManager()
        super(HAL3RouterApplianceNamespaceTestCase, self).setUp(
            l3_plugin=l3_plugin, ext_mgr=ext_mgr)


class HAL3RouterTestsMixin(object):

    def _get_ha_defaults(self, ha_enabled=None, ha_type=None,
                         redundancy_level=None, priority=DEFAULT_PRIORITY,
                         state=ha.HA_ACTIVE, probing_enabled=None,
                         probe_target=None, probe_interval=None):

        if ha_enabled is None:
            ha_enabled = self._is_ha_tests
        if not ha_enabled:
            return {ha.ENABLED: False}
        ha_details = {
            ha.TYPE: ha_type or cfg.CONF.ha.default_ha_mechanism,
            ha.PRIORITY: priority,
            ha.STATE: state,
            ha.REDUNDANCY_LEVEL: (redundancy_level or
                                  cfg.CONF.ha.default_ha_redundancy_level),
            ha.PROBE_CONNECTIVITY: (
                probing_enabled if probing_enabled is not None else
                cfg.CONF.ha.connectivity_probing_enabled_by_default)}
        if probing_enabled:
            ha_details.update({
                ha.PROBE_TARGET: (probe_target or
                                  cfg.CONF.ha.default_ping_target),
                ha.PROBE_INTERVAL: (probe_interval or
                                    cfg.CONF.ha.default_ping_interval)})
        return {ha.ENABLED: ha_enabled, ha.DETAILS: ha_details}

    def _verify_ha_settings(self, router, expected_ha):
            self.assertEqual(router[ha.ENABLED], expected_ha[ha.ENABLED])
            if expected_ha[ha.ENABLED]:
                if ha.DETAILS in expected_ha:
                    ha_details = copy.deepcopy(router[ha.DETAILS])
                    redundancy_routers = ha_details.pop(ha.REDUNDANCY_ROUTERS)
                    self.assertDictEqual(ha_details,
                                         expected_ha[ha.DETAILS])
                    self.assertEqual(
                        len(redundancy_routers),
                        expected_ha[ha.DETAILS][ha.REDUNDANCY_LEVEL])
                else:
                    self.assertTrue(ha.DETAILS not in router)
            else:
                self.assertIsNone(router.get(ha.DETAILS))

    def _verify_router_gw_port(self, router_id, external_net_id,
                               external_subnet_id):
        body = self._list('ports',
                          query_params='device_id=%s' % router_id)
        ports = body['ports']
        self.assertEqual(len(ports), 1)
        p_e = ports[0]
        self.assertEqual(p_e['network_id'], external_net_id)
        self.assertEqual(p_e['fixed_ips'][0]['subnet_id'], external_subnet_id)
        self.assertEqual(p_e['device_owner'],
                         l3_constants.DEVICE_OWNER_ROUTER_GW)


class HAL3RouterApplianceVMTestCase(
    HAL3RouterTestsMixin,
        test_l3_router_appliance_plugin.L3RouterApplianceVMTestCase):

    _is_ha_tests = True

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        if l3_plugin is None:
            l3_plugin = L3_PLUGIN_KLASS
        if ext_mgr is None:
            ext_mgr = TestHAL3RouterApplianceExtensionManager()
        cfg.CONF.set_override('default_ha_redundancy_level', 2, group='ha')
        super(HAL3RouterApplianceVMTestCase, self).setUp(
            l3_plugin=l3_plugin, ext_mgr=ext_mgr)

    def test_router_add_interface_port(self):
        orig_update_port = self.core_plugin.update_port
        with self.router() as router, (
            self.port()) as port, (
                mock.patch.object(self.core_plugin,
                                  'update_port')) as update_port:
            update_port.side_effect = orig_update_port
            r = router['router']
            p = port['port']
            body = self._router_interface_action('add', r['id'], None, p['id'])
            self.assertIn('port_id', body)
            self.assertEqual(p['id'], body['port_id'])
            r_ids = [rr['id']
                     for rr in [r] + r[ha.DETAILS][ha.REDUNDANCY_ROUTERS]]
            # get ports for the user visible router and its two redundancy
            # routers for which device_id attribute should have been updated
            params = "&".join(["device_id=%s" % r_id for r_id in r_ids])
            router_ports = self._list('ports', query_params=params)['ports']
            self.assertEqual(len(router_ports), 3)
            expected_calls = []
            for port in router_ports:
                expected_port_update = {
                    'port': {'device_owner': DEVICE_OWNER_ROUTER_INTF,
                             'device_id': port['device_id']}}
                expected_calls.append(
                    mock.call(mock.ANY, port['id'], expected_port_update))
            update_port.assert_has_calls(expected_calls, any_order=True)
            r_port_ids = {r_p['id'] for r_p in router_ports}
            # get the extra port for the user visible router
            other_router_ports = [r_p for r_p in self._list('ports')['ports']
                                  if r_p['id'] not in r_port_ids]
            # clean-up
            self._router_interface_action('remove', r['id'], None, p['id'])

            # should only be one since we've created one router port
            self.assertEqual(1, len(other_router_ports))
            self.assertEqual(DEVICE_OWNER_ROUTER_INTF,
                             other_router_ports[0]['device_owner'])

    def test_hidden_port_creation_includes_dns_attribute(self):
        with mock.patch('networking_cisco.plugins.cisco.db.l3.ha_db.'
                        'utils.is_extension_supported',
                        return_value=True) as extension_support,\
                mock.patch.object(self.core_plugin, 'create_port') as c_p_mock:
                    # Verify the function is called with extension dns enabled
                    expected_calls = [
                        mock.call(self.core_plugin, 'dns-integration')]
                    self.l3_plugin._create_hidden_port(
                        'fake_ctx', 'some_network_id', 'some_device_id', [])
                    extension_support.assert_has_calls(expected_calls,
                                                       any_order=True)
                    c_p_mock.assert_called_once_with('fake_ctx', mock.ANY)
                    self.assertEqual(
                        '', c_p_mock.call_args[0][1]['port']['dns_name'])

    def _test_create_ha_router(self, router, subnet, ha_settings=None):
        if ha_settings is None:
            ha_settings = self._get_ha_defaults()
        self._verify_ha_settings(router, ha_settings)
        if subnet is not None:
            self.assertEqual(subnet['network_id'],
                             router['external_gateway_info']['network_id'])
            self._verify_router_gw_port(router['id'], subnet['network_id'],
                                        subnet['id'])
        ha_disabled_settings = self._get_ha_defaults(ha_enabled=False)
        # verify redundancy routers
        for rr_info in router[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
            rr = self._show('routers', rr_info['id'])
            # check that redundancy router is hidden
            self.assertEqual(rr['router']['tenant_id'], '')
            # redundancy router should have ha disabled
            self._verify_ha_settings(rr['router'], ha_disabled_settings)
            if subnet is not None:
                # check that redundancy router has all ports
                self._verify_router_gw_port(rr['router']['id'],
                                            subnet['network_id'], subnet['id'])

    def test_create_ha_router_with_defaults(self):
        with self.subnet() as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(external_gateway_info={
                    'network_id': s['subnet']['network_id']}) as r:
                self._test_create_ha_router(r['router'], s['subnet'])

    def test_create_non_gw_ha_router_with_defaults(self):
        with self.router() as r:
            self._test_create_ha_router(r['router'], None)

    def test_create_ha_router_with_defaults_non_admin_succeeds(self):
        tenant_id = _uuid()
        with self.network(tenant_id=tenant_id) as n_external:
            res = self._create_subnet(self.fmt, n_external['network']['id'],
                                      cidr='10.0.1.0/24', tenant_id=tenant_id)
            s = self.deserialize(self.fmt, res)
            self._set_net_external(s['subnet']['network_id'])
            with self.router(
                    tenant_id=tenant_id,
                    external_gateway_info={
                        'network_id': s['subnet']['network_id']},
                    set_context=True) as r:
                self.assertEqual(
                    s['subnet']['network_id'],
                    r['router']['external_gateway_info']['network_id'])
                self.assertTrue(r['router'][ha.ENABLED])
                # non-admin users should not see ha detail
                self.assertIsNone(r['router'].get(ha.DETAILS))

    def test_create_non_gw_ha_router_with_defaults_non_admin_succeeds(self):
        tenant_id = _uuid()
        with self.router(tenant_id=tenant_id, set_context=True) as r:
            self.assertTrue(r['router'][ha.ENABLED])
            # non-admin users should not see ha detail
            self.assertIsNone(r['router'].get(ha.DETAILS))

    def test_create_ha_router_with_ha_specification(self):
        with self.subnet() as s:
            self._set_net_external(s['subnet']['network_id'])
            ha_settings = self._get_ha_defaults(
                ha_type=ha.HA_GLBP, priority=DEFAULT_PRIORITY,
                probing_enabled=True,
                probe_interval=3, probe_target='10.5.5.2')
            kwargs = {ha.DETAILS: ha_settings[ha.DETAILS],
                      l3.EXTERNAL_GW_INFO: {'network_id':
                                            s['subnet']['network_id']}}
            with self.router(arg_list=(ha.DETAILS,), **kwargs) as r:
                self._test_create_ha_router(r['router'], s['subnet'],
                                            ha_settings)

    def test_create_non_gw_ha_router_with_ha_specification(self):
        ha_settings = self._get_ha_defaults(
            ha_type=ha.HA_GLBP, priority=DEFAULT_PRIORITY,
            probing_enabled=True,
            probe_interval=3, probe_target='10.5.5.2')
        kwargs = {ha.DETAILS: ha_settings[ha.DETAILS]}
        with self.router(arg_list=(ha.DETAILS,), **kwargs) as r:
            self._test_create_ha_router(r['router'], None, ha_settings)

    def test_create_ha_router_with_ha_specification_validation_fails(self):
        with self.subnet() as s:
            self._set_net_external(s['subnet']['network_id'])
            ha_settings = self._get_ha_defaults(redundancy_level=5,
                ha_type=ha.HA_GLBP, priority=15, probing_enabled=True,
                probe_interval=3, probe_target='10.5.5.2')
            kwargs = {ha.ENABLED: True,
                      ha.DETAILS: ha_settings[ha.DETAILS],
                      l3.EXTERNAL_GW_INFO: {'network_id':
                                            s['subnet']['network_id']}}
            res = self._create_router(self.fmt, _uuid(), 'ha_router1',
                                      arg_list=(ha.ENABLED,
                                                ha.DETAILS,
                                                l3.EXTERNAL_GW_INFO),
                                      **kwargs)
            self.assertEqual(res.status_int, webob.exc.HTTPBadRequest.code)

    def test_create_non_gw_ha_router_with_ha_specification_validation_fails(
            self):
        ha_settings = self._get_ha_defaults(redundancy_level=5,
            ha_type=ha.HA_GLBP, priority=15, probing_enabled=True,
            probe_interval=3, probe_target='10.5.5.2')
        kwargs = {ha.ENABLED: True, ha.DETAILS: ha_settings[ha.DETAILS]}
        res = self._create_router(self.fmt, _uuid(), 'ha_router1',
                                  arg_list=(ha.ENABLED, ha.DETAILS), **kwargs)
        self.assertEqual(res.status_int, webob.exc.HTTPBadRequest.code)

    def test_create_ha_router_with_ha_specification_invalid_HA_type_fails(
            self):
        with self.subnet() as s:
            self._set_net_external(s['subnet']['network_id'])
            ha_settings = self._get_ha_defaults(redundancy_level=3,
                ha_type="UNKNOWN", priority=15, probing_enabled=True,
                probe_interval=3, probe_target='10.5.5.2')
            kwargs = {ha.ENABLED: True,
                      ha.DETAILS: ha_settings[ha.DETAILS],
                      l3.EXTERNAL_GW_INFO: {'network_id':
                                            s['subnet']['network_id']}}
            res = self._create_router(self.fmt, _uuid(), 'ha_router1',
                                      arg_list=(ha.ENABLED,
                                                ha.DETAILS,
                                                l3.EXTERNAL_GW_INFO),
                                      **kwargs)
            self.assertEqual(res.status_int, webob.exc.HTTPBadRequest.code)

    def test_create_non_gw_ha_router_with_ha_spec_invalid_HA_type_fails(self):
        ha_settings = self._get_ha_defaults(
            redundancy_level=3, ha_type="UNKNOWN", priority=15,
            probing_enabled=True, probe_interval=3, probe_target='10.5.5.2')
        kwargs = {ha.ENABLED: True, ha.DETAILS: ha_settings[ha.DETAILS]}
        res = self._create_router(self.fmt, _uuid(), 'ha_router1',
                                  arg_list=(ha.ENABLED, ha.DETAILS), **kwargs)
        self.assertEqual(res.status_int, webob.exc.HTTPBadRequest.code)

    def test_create_ha_router_with_ha_specification_non_admin_fails(self):
        with self.subnet() as s:
            self._set_net_external(s['subnet']['network_id'])
            kwargs = {
                ha.ENABLED: True,
                ha.DETAILS: {ha.TYPE: ha.HA_VRRP},
                l3.EXTERNAL_GW_INFO: {'network_id': s['subnet']['network_id']}}
            res = self._create_router(
                self.fmt, _uuid(), 'ha_router1', set_context=True,
                arg_list=(ha.ENABLED, ha.DETAILS, l3.EXTERNAL_GW_INFO),
                **kwargs)
            self.assertEqual(res.status_int, webob.exc.HTTPForbidden.code)

    def test_create_non_gw_ha_router_with_ha_spec_non_admin_fails(self):
        kwargs = {ha.ENABLED: True, ha.DETAILS: {ha.TYPE: ha.HA_VRRP}}
        res = self._create_router(
            self.fmt, _uuid(), 'ha_router1', set_context=True,
            arg_list=(ha.ENABLED, ha.DETAILS), **kwargs)
        self.assertEqual(res.status_int, webob.exc.HTTPForbidden.code)

    def test_create_ha_router_with_disabled_ha_type_fails(self):
        cfg.CONF.set_override('disabled_ha_mechanisms', [ha.HA_VRRP],
                              group='ha')
        with self.subnet() as s:
            self._set_net_external(s['subnet']['network_id'])
            kwargs = {
                ha.ENABLED: True,
                ha.DETAILS: {ha.TYPE: ha.HA_VRRP},
                l3.EXTERNAL_GW_INFO: {'network_id': s['subnet']['network_id']}}
            res = self._create_router(
                self.fmt, _uuid(), 'ha_router1',
                arg_list=(ha.ENABLED, ha.DETAILS, l3.EXTERNAL_GW_INFO),
                **kwargs)
            self.assertEqual(res.status_int, webob.exc.HTTPConflict.code)

    def test_create_non_gw_ha_router_with_disabled_ha_type_fails(self):
        cfg.CONF.set_override('disabled_ha_mechanisms', [ha.HA_VRRP],
                              group='ha')
        kwargs = {ha.ENABLED: True, ha.DETAILS: {ha.TYPE: ha.HA_VRRP}}
        res = self._create_router(
            self.fmt, _uuid(), 'ha_router1', set_context=True,
            arg_list=(ha.ENABLED, ha.DETAILS), **kwargs)
        self.assertEqual(res.status_int, webob.exc.HTTPForbidden.code)

    def test_create_ha_router_when_ha_support_disabled_fails(self):
        cfg.CONF.set_override('ha_support_enabled', False, group='ha')
        with self.subnet() as s:
            self._set_net_external(s['subnet']['network_id'])
            kwargs = {
                ha.ENABLED: True,
                l3.EXTERNAL_GW_INFO: {'network_id': s['subnet']['network_id']}}
            res = self._create_router(
                self.fmt, _uuid(), 'ha_router1',
                arg_list=(ha.ENABLED,), **kwargs)
            self.assertEqual(res.status_int, webob.exc.HTTPConflict.code)

    def test_create_non_gw_ha_router_when_ha_support_disabled_fails(self):
        cfg.CONF.set_override('ha_support_enabled', False, group='ha')
        kwargs = {ha.ENABLED: True}
        res = self._create_router(
            self.fmt, _uuid(), 'ha_router1', arg_list=(ha.ENABLED,),
            **kwargs)
        self.assertEqual(res.status_int, webob.exc.HTTPConflict.code)

    def test_show_ha_router_non_admin(self):
        tenant_id = _uuid()
        with self.network(tenant_id=tenant_id) as n_external:
            res = self._create_subnet(self.fmt, n_external['network']['id'],
                                      cidr='10.0.1.0/24', tenant_id=tenant_id)
            s = self.deserialize(self.fmt, res)
            self._set_net_external(s['subnet']['network_id'])
            with self.router(tenant_id=tenant_id,
                             external_gateway_info={
                                 'network_id': s['subnet']['network_id']},
                             set_context=True) as r:
                self.assertEqual(
                    s['subnet']['network_id'],
                    r['router']['external_gateway_info']['network_id'])
                self.assertTrue(r['router'][ha.ENABLED])
                # ensure that no ha details are included
                self.assertNotIn(ha.DETAILS, r['router'])
                r_s = self._show('routers', r['router']['id'],
                                 neutron_context=context.Context('',
                                                                 tenant_id))
                self.assertTrue(r_s['router'][ha.ENABLED])
                # ensure that no ha details are included
                self.assertNotIn(ha.DETAILS, r_s['router'])

    def test_show_non_gw_ha_router_non_admin(self):
        tenant_id = _uuid()
        with self.router(tenant_id=tenant_id, set_context=True) as r:
            self.assertIsNone(r['router']['external_gateway_info'])
            self.assertTrue(r['router'][ha.ENABLED])
            # ensure that no ha details are included
            self.assertNotIn(ha.DETAILS, r['router'])
            r_s = self._show('routers', r['router']['id'],
                             neutron_context=context.Context('', tenant_id))
            self.assertTrue(r_s['router'][ha.ENABLED])
            # ensure that no ha details are included
            self.assertNotIn(ha.DETAILS, r_s['router'])

    def _verify_router_ports(self, router_id, external_net_id=None,
                             external_subnet_id=None, internal_net_id=None,
                             internal_subnet_id=None):
        body = self._list('ports',
                          query_params='device_id=%s' % router_id)
        ports = body['ports']
        if external_net_id:
            p_e = ports[0]
            num_ports = 1
        else:
            num_ports = 0
        if internal_net_id:
            p_i = ports[0]
            num_ports += 1
        self.assertEqual(len(ports), num_ports)
        if num_ports == 2:
            if ports[0]['network_id'] == external_net_id:
                p_e = ports[0]
                p_i = ports[1]
            else:
                p_e = ports[1]
                p_i = ports[0]
        if external_net_id:
            self.assertEqual(p_e['fixed_ips'][0]['subnet_id'],
                             external_subnet_id)
            self.assertEqual(p_e['device_owner'],
                             l3_constants.DEVICE_OWNER_ROUTER_GW)
        if internal_net_id:
            self.assertEqual(p_i['network_id'], internal_net_id)
            self.assertEqual(p_i['fixed_ips'][0]['subnet_id'],
                             internal_subnet_id)
            self.assertEqual(p_i['device_owner'],
                             l3_constants.DEVICE_OWNER_ROUTER_INTF)

    def _ha_router_port_test(self, subnet, router, port, ha_spec=None,
                             additional_tests_function=None):
        body = self._router_interface_action('add', router['id'], None,
                                             port['id'])
        self.assertIn('port_id', body)
        self.assertEqual(body['port_id'], port['id'])
        if ha_spec is None:
            ha_spec = self._get_ha_defaults()
        # verify router visible to user
        self._verify_ha_settings(router, ha_spec)
        self._verify_router_ports(router['id'], subnet['network_id'],
                                  subnet['id'], port['network_id'],
                                  port['fixed_ips'][0]['subnet_id'])
        ha_disabled_settings = self._get_ha_defaults(ha_enabled=False)
        redundancy_routers = []
        # verify redundancy routers
        for rr_info in router[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
            rr = self._show('routers', rr_info['id'])
            redundancy_routers.append(rr['router'])
            # check that redundancy router is hidden
            self.assertEqual(rr['router']['tenant_id'], '')
            # redundancy router should have ha disabled
            self._verify_ha_settings(rr['router'], ha_disabled_settings)
            # check that redundancy router has all ports
            self._verify_router_ports(rr['router']['id'], subnet['network_id'],
                                      subnet['id'], port['network_id'],
                                      port['fixed_ips'][0]['subnet_id'])
        if additional_tests_function is not None:
            additional_tests_function(redundancy_routers)
        # clean-up
        self._router_interface_action('remove', router['id'], None, port['id'])

    def test_ha_router_add_and_remove_interface_port(self):
        with self.subnet(cidr='10.0.1.0/24') as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(external_gateway_info={
                    'network_id': s['subnet']['network_id']}) as r:
                with self.port() as p:
                    self._ha_router_port_test(s['subnet'], r['router'],
                                              p['port'])

    def test_non_gw_ha_router_add_and_remove_interface_port(self):
        with self.router() as r, self.port() as p:
            no_subnet = {'id': None, 'network_id': None}
            self._ha_router_port_test(no_subnet, r['router'], p['port'])

    def test_ha_router_disable_ha_succeeds(self):
        def _disable_ha_tests(redundancy_routers):
            body = {'router': {ha.ENABLED: False}}
            updated_router = self._update('routers', r['router']['id'], body)
            self._verify_ha_settings(updated_router['router'],
                                     self._get_ha_defaults(ha_enabled=False))
            # verify that the redundancy routers are indeed gone
            params = "&".join(["id=%s" % rr['id'] for rr in
                               redundancy_routers])
            redundancy_routers = self._list('routers', query_params=params)
            self.assertEqual(len(redundancy_routers['routers']), 0)

        with self.subnet(cidr='10.0.1.0/24') as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(external_gateway_info={
                    'network_id': s['subnet']['network_id']}) as r:
                with self.port() as p:
                    self._ha_router_port_test(s['subnet'], r['router'],
                                              p['port'], None,
                                              _disable_ha_tests)

    def test_non_gw_ha_router_disable_ha_succeeds(self):
        def _disable_ha_tests(redundancy_routers):
            body = {'router': {ha.ENABLED: False}}
            updated_router = self._update('routers', r['router']['id'], body)
            self._verify_ha_settings(updated_router['router'],
                                     self._get_ha_defaults(ha_enabled=False))
            # verify that the redundancy routers are indeed gone
            params = "&".join(["id=%s" % rr['id'] for rr in
                               redundancy_routers])
            redundancy_routers = self._list('routers', query_params=params)
            self.assertEqual(len(redundancy_routers['routers']), 0)

        with self.router() as r, self.port() as p:
            no_subnet = {'id': None, 'network_id': None}
            self._ha_router_port_test(no_subnet, r['router'], p['port'],
                                      None, _disable_ha_tests)

    def test_ha_router_disable_ha_non_admin_succeeds(self):
        def _disable_ha_tests(redundancy_routers):
            body = {'router': {ha.ENABLED: False}}
            updated_router = self._update(
                'routers', r['router']['id'], body,
                neutron_context=context.Context('', tenant_id))
            self._verify_ha_settings(updated_router['router'],
                                     self._get_ha_defaults(ha_enabled=False))
            # verify that the redundancy routers are indeed gone
            params = "&".join(["id=%s" % rr['id'] for rr in
                               redundancy_routers])
            redundancy_routers = self._list('routers', query_params=params)
            self.assertEqual(len(redundancy_routers['routers']), 0)

        tenant_id = _uuid()
        with self.network(tenant_id=tenant_id) as n_external:
            res = self._create_subnet(self.fmt, n_external['network']['id'],
                                      cidr='10.0.1.0/24', tenant_id=tenant_id)
            s = self.deserialize(self.fmt, res)
            self._set_net_external(s['subnet']['network_id'])
            with self.router(
                    external_gateway_info={
                        'network_id': s['subnet']['network_id']},
                    tenant_id=tenant_id) as r:
                with self.port(tenant_id=tenant_id) as p:
                    self._ha_router_port_test(s['subnet'], r['router'],
                                              p['port'], None,
                                              _disable_ha_tests)

    def test_non_gw_ha_router_disable_ha_non_admin_succeeds(self):
        def _disable_ha_tests(redundancy_routers):
            body = {'router': {ha.ENABLED: False}}
            updated_router = self._update(
                'routers', r['router']['id'], body,
                neutron_context=context.Context('', tenant_id))
            self._verify_ha_settings(updated_router['router'],
                                     self._get_ha_defaults(ha_enabled=False))
            # verify that the redundancy routers are indeed gone
            params = "&".join(["id=%s" % rr['id'] for rr in
                               redundancy_routers])
            redundancy_routers = self._list('routers', query_params=params)
            self.assertEqual(len(redundancy_routers['routers']), 0)

        tenant_id = _uuid()
        with self.router(tenant_id=tenant_id) as r:
            with self.port(tenant_id=tenant_id) as p:
                no_subnet = {'id': None, 'network_id': None}
                self._ha_router_port_test(no_subnet, r['router'], p['port'],
                                          None, _disable_ha_tests)

    def test_ha_router_remove_gateway_succeeds(self):
        with self.subnet(cidr='10.0.1.0/24') as s:
            subnet = s['subnet']
            self._set_net_external(subnet['network_id'])
            with self.router(external_gateway_info={
                    'network_id': subnet['network_id']}) as r:
                router = r['router']
                # verify router visible to user
                ha_spec = self._get_ha_defaults()
                self._verify_ha_settings(router, ha_spec)
                self._verify_router_ports(router['id'], subnet['network_id'],
                                          subnet['id'])
                # verify redundancy router ports
                for rr_info in router[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                    self._verify_router_ports(
                        rr_info['id'], subnet['network_id'], subnet['id'])
                body = {'router': {'external_gateway_info': None}}
                r_after = self._update('routers', router['id'], body)
                self._verify_ha_settings(r_after['router'], ha_spec)
                self._verify_router_ports(router['id'])
                # verify redundancy router ports
                for rr_info in router[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                    self._verify_router_ports(rr_info['id'])

    def test_ha_non_gw_router_add_gateway_succeeds(self):
        with self.router() as r:
            router = r['router']
            # verify router visible to user
            ha_spec = self._get_ha_defaults()
            self._verify_ha_settings(router, ha_spec)
            self._verify_router_ports(router['id'])
            # verify redundancy router ports
            for rr_info in router[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                self._verify_router_ports(rr_info['id'])
            with self.subnet(cidr='10.0.1.0/24') as s:
                subnet = s['subnet']
                self._set_net_external(subnet['network_id'])
                body = {'router': {'external_gateway_info': {
                    'network_id': subnet['network_id']}}}
                r_after = self._update('routers', router['id'], body)
                self._verify_ha_settings(r_after['router'], ha_spec)
                self._verify_router_ports(router['id'], subnet['network_id'],
                                          subnet['id'])
                # verify redundancy router ports
                for rr_info in router[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                    self._verify_router_ports(
                        rr_info['id'], subnet['network_id'], subnet['id'])

    def test_ha_update_admin_state_up(self):
        with self.router() as r:
            router = r['router']
            # verify router visible to user
            ha_spec = self._get_ha_defaults()
            self._verify_ha_settings(router, ha_spec)
            # verify initial state of admin_state_up is True
            self.assertEqual(True, router['admin_state_up'])
            for rr_info in router[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                rr = self._show('routers', rr_info['id'])
                self.assertEqual(True, rr['router']['admin_state_up'])

            # update admin_state_up to False
            body = {'router': {'admin_state_up': False}}
            r_after = self._update('routers', router['id'], body)

            # verify update to router visible to user and the backup routers
            self.assertEqual(False, r_after['router']['admin_state_up'])
            for rr_info in (
                r_after['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS]):
                rr = self._show('routers', rr_info['id'])
                self.assertEqual(False, rr['router']['admin_state_up'])

    def _test_enable_ha(self, subnet, router, port, set_ha_details=True,
                        neutron_context=None):
        if port['network_id']:
            body = self._router_interface_action('add', router['id'], None,
                                                 port['id'])
            self.assertIn('port_id', body)
            self.assertEqual(body['port_id'], port['id'])
        # verify router visible to user
        ha_disabled_settings = self._get_ha_defaults(
            ha_enabled=False)
        self._verify_ha_settings(router, ha_disabled_settings)
        self._verify_router_ports(router['id'], subnet['network_id'],
                                  subnet['id'], port['network_id'],
                                  port['fixed_ips'][0]['subnet_id'])
        body = {'router': {ha.ENABLED: True}}
        if set_ha_details is True:
            body['router'][ha.DETAILS] = {ha.TYPE: ha.HA_VRRP}
        ha_type = body['router'].get(ha.DETAILS, {}).get(ha.TYPE)
        if neutron_context:
            updated_router = self._update('routers', router['id'], body,
                                          neutron_context=neutron_context)
            self._verify_ha_settings(updated_router['router'],
                                     {ha.ENABLED: True})
        else:
            updated_router = self._update('routers', router['id'], body)
            self._verify_ha_settings(updated_router['router'],
                                     self._get_ha_defaults(ha_type=ha_type))
            ha_d = updated_router['router'][ha.DETAILS]
            redundancy_routers = self._list(
                'routers',
                query_params="&".join(["id=%s" % rr['id'] for rr in
                                       ha_d[ha.REDUNDANCY_ROUTERS]]))
            for rr in redundancy_routers['routers']:
                # redundancy router should have ha disabled
                self._verify_ha_settings(rr, ha_disabled_settings)
                # check that redundancy routers have all ports
                self._verify_router_ports(rr['id'], subnet['network_id'],
                                          subnet['id'], port['network_id'],
                                          port['fixed_ips'][0]['subnet_id'])
        if port['network_id']:
            # clean-up
            self._router_interface_action('remove', router['id'], None,
                                          port['id'])

    def test_enable_ha_on_router_succeeds(self):
        with self.subnet(cidr='10.0.1.0/24') as s:
            self._set_net_external(s['subnet']['network_id'])
            kwargs = {ha.ENABLED: False,
                      l3.EXTERNAL_GW_INFO: {'network_id':
                                            s['subnet']['network_id']}}
            with self.router(arg_list=(ha.ENABLED,), **kwargs) as r,\
                    self.port() as p:
                self._test_enable_ha(s['subnet'], r['router'], p['port'])

    def test_enable_ha_on_non_gw_router_succeeds(self):
        kwargs = {ha.ENABLED: False}
        with self.router(arg_list=(ha.ENABLED,), **kwargs) as r,\
                self.port() as p:
            no_subnet = {'id': None, 'network_id': None}
            self._test_enable_ha(no_subnet, r['router'], p['port'])

    def test_enable_ha_on_router_no_itfcs_succeeds_succeeds(self):
        with self.subnet(cidr='10.0.1.0/24') as s:
            self._set_net_external(s['subnet']['network_id'])
            kwargs = {ha.ENABLED: False,
                      l3.EXTERNAL_GW_INFO: {'network_id':
                                            s['subnet']['network_id']}}
            with self.router(arg_list=(ha.ENABLED,), **kwargs) as r:
                no_port = {'id': None, 'network_id': None,
                           'fixed_ips': [{'subnet_id': None}]}
                self._test_enable_ha(s['subnet'], r['router'], no_port)

    def test_enable_ha_on_non_gw_router_no_itfcs_succeeds(self):
        kwargs = {ha.ENABLED: False}
        with self.router(arg_list=(ha.ENABLED,), **kwargs) as r:
            no_subnet = {'id': None, 'network_id': None}
            no_port = {'id': None, 'network_id': None,
                       'fixed_ips': [{'subnet_id': None}]}
            self._test_enable_ha(no_subnet, r['router'], no_port)

    def test_enable_ha_on_router_succeeds_no_ha_spec(self):
        with self.subnet(cidr='10.0.1.0/24') as s:
            self._set_net_external(s['subnet']['network_id'])
            kwargs = {ha.ENABLED: False,
                      l3.EXTERNAL_GW_INFO: {'network_id':
                                            s['subnet']['network_id']}}
            with self.router(arg_list=(ha.ENABLED,), **kwargs) as r:
                with self.port() as p:
                    self._test_enable_ha(s['subnet'], r['router'], p['port'],
                                         set_ha_details=False)

    def test_enable_ha_on_non_gw_router_succeeds_no_ha_spec(self):
        kwargs = {ha.ENABLED: False}
        with self.router(arg_list=(ha.ENABLED,), **kwargs) as r,\
                self.port() as p:
            no_subnet = {'id': None, 'network_id': None}
            self._test_enable_ha(no_subnet, r['router'], p['port'],
                                 set_ha_details=False)

    def test_enable_ha_on_router_non_admin_succeeds(self):
        tenant_id = _uuid()
        with self.network(tenant_id=tenant_id) as n_external:
            res = self._create_subnet(self.fmt, n_external['network']['id'],
                                      cidr='10.0.1.0/24', tenant_id=tenant_id)
            s = self.deserialize(self.fmt, res)
            self._set_net_external(s['subnet']['network_id'])
            kwargs = {ha.ENABLED: False,
                      l3.EXTERNAL_GW_INFO: {'network_id':
                                            s['subnet']['network_id']}}
            with self.router(tenant_id=tenant_id, arg_list=(ha.ENABLED,),
                             **kwargs) as r:
                with self.port(tenant_id=tenant_id) as p:
                    self._test_enable_ha(
                        s['subnet'], r['router'], p['port'], False,
                        neutron_context=context.Context('', tenant_id))

    def test_enable_ha_on_non_gw_router_non_admin_succeeds(self):
        tenant_id = _uuid()
        kwargs = {ha.ENABLED: False}
        with self.router(tenant_id=tenant_id, arg_list=(ha.ENABLED,),
                         **kwargs) as r, self.port(tenant_id=tenant_id) as p:
            no_subnet = {'id': None, 'network_id': None}
            self._test_enable_ha(no_subnet, r['router'], p['port'])

    def test_update_router_ha_settings(self):
        with self.subnet(cidr='10.0.1.0/24') as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(external_gateway_info={
                    'network_id': s['subnet']['network_id']}) as r:
                self._verify_ha_settings(r['router'], self._get_ha_defaults())
                ha_settings = self._get_ha_defaults(
                    priority=15, probing_enabled=True, probe_interval=3,
                    probe_target='10.5.5.2')
                ha_spec = copy.deepcopy(ha_settings[ha.DETAILS])
                del ha_spec[ha.TYPE]
                del ha_spec[ha.REDUNDANCY_LEVEL]
                body = {'router': {ha.DETAILS: ha_spec}}
                r_after = self._update('routers', r['router']['id'], body)
                self._verify_ha_settings(r_after['router'], ha_settings)
                r_show = self._show('routers', r['router']['id'])
                self._verify_ha_settings(r_show['router'], ha_settings)

    def test_update_non_gw_router_ha_settings(self):
        with self.router() as r:
            self._verify_ha_settings(r['router'], self._get_ha_defaults())
            ha_settings = self._get_ha_defaults(
                priority=15, probing_enabled=True, probe_interval=3,
                probe_target='10.5.5.2')
            ha_spec = copy.deepcopy(ha_settings[ha.DETAILS])
            del ha_spec[ha.TYPE]
            del ha_spec[ha.REDUNDANCY_LEVEL]
            body = {'router': {ha.DETAILS: ha_spec}}
            r_after = self._update('routers', r['router']['id'], body)
            self._verify_ha_settings(r_after['router'], ha_settings)
            r_show = self._show('routers', r['router']['id'])
            self._verify_ha_settings(r_show['router'], ha_settings)

    def test_update_router_ha_settings_non_admin_fails(self):
        tenant_id = _uuid()
        with self.network(tenant_id=tenant_id) as n_external:
            res = self._create_subnet(self.fmt, n_external['network']['id'],
                                      cidr='10.0.1.0/24', tenant_id=tenant_id)
            s = self.deserialize(self.fmt, res)
            self._set_net_external(s['subnet']['network_id'])
            with self.router(
                    external_gateway_info={
                        'network_id': s['subnet']['network_id']},
                    tenant_id=tenant_id) as r:
                ha_settings = self._get_ha_defaults()
                self._verify_ha_settings(r['router'], ha_settings)
                body = {'router': {ha.DETAILS: {ha.PRIORITY: 15,
                                                ha.PROBE_CONNECTIVITY: True,
                                                ha.PROBE_TARGET: '10.5.5.2',
                                                ha.PROBE_INTERVAL: 3}}}
                self._update('routers', r['router']['id'], body,
                             expected_code=webob.exc.HTTPForbidden.code,
                             neutron_context=context.Context('', tenant_id))
                r_show = self._show('routers', r['router']['id'])
                self._verify_ha_settings(r_show['router'], ha_settings)

    def test_update_non_gw_router_ha_settings_non_admin_fails(self):
        tenant_id = _uuid()
        with self.router(tenant_id=tenant_id) as r:
            ha_settings = self._get_ha_defaults()
            self._verify_ha_settings(r['router'], ha_settings)
            body = {'router': {ha.DETAILS: {ha.PRIORITY: 15,
                                            ha.PROBE_CONNECTIVITY: True,
                                            ha.PROBE_TARGET: '10.5.5.2',
                                            ha.PROBE_INTERVAL: 3}}}
            self._update('routers', r['router']['id'], body,
                         expected_code=webob.exc.HTTPForbidden.code,
                         neutron_context=context.Context('', tenant_id))
            r_show = self._show('routers', r['router']['id'])
            self._verify_ha_settings(r_show['router'], ha_settings)

    def test_update_ha_type_on_router_with_ha_enabled_fails(self):
        with self.subnet(cidr='10.0.1.0/24') as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(external_gateway_info={
                    'network_id': s['subnet']['network_id']}) as r:
                ha_settings = self._get_ha_defaults()
                self._verify_ha_settings(r['router'], ha_settings)
                body = {'router': {ha.DETAILS: {ha.TYPE: ha.HA_GLBP}}}
                self._update('routers', r['router']['id'], body,
                             expected_code=webob.exc.HTTPConflict.code)
                r_after = self._show('routers', r['router']['id'])
                self._verify_ha_settings(r_after['router'], ha_settings)

    def test_update_ha_type_on_non_gw_router_with_ha_enabled_fails(self):
        with self.router() as r:
            ha_settings = self._get_ha_defaults()
            self._verify_ha_settings(r['router'], ha_settings)
            body = {'router': {ha.DETAILS: {ha.TYPE: ha.HA_GLBP}}}
            self._update('routers', r['router']['id'], body,
                         expected_code=webob.exc.HTTPConflict.code)
            r_after = self._show('routers', r['router']['id'])
            self._verify_ha_settings(r_after['router'], ha_settings)

    def _test_ha_disabled_cases(self):
        with self.subnet(cidr='10.0.1.0/24') as s:
            self._set_net_external(s['subnet']['network_id'])
            kwargs = {ha.ENABLED: False,
                      l3.EXTERNAL_GW_INFO: {'network_id':
                                            s['subnet']['network_id']}}
            with self.router(arg_list=(ha.ENABLED,), **kwargs) as r:
                ha_disabled_settings = self._get_ha_defaults(ha_enabled=False)
                self._verify_ha_settings(r['router'], ha_disabled_settings)
                body = {'router': {ha.ENABLED: True,
                                   ha.DETAILS: {ha.TYPE: ha.HA_VRRP}}}
                self._update('routers', r['router']['id'], body,
                             expected_code=webob.exc.HTTPConflict.code)
                r_after = self._show('routers', r['router']['id'])
                self._verify_ha_settings(r_after['router'],
                                         ha_disabled_settings)

    def test_enable_ha_when_ha_support_disabled_fails(self):
        cfg.CONF.set_override('ha_support_enabled', False, group='ha')
        self._test_ha_disabled_cases()

    def test_enable_ha_with_disabled_ha_type_fails(self):
        cfg.CONF.set_override('disabled_ha_mechanisms', [ha.HA_VRRP],
                              group='ha')
        self._test_ha_disabled_cases()

    def _test_ha_disabled_non_gw_cases(self):
        kwargs = {ha.ENABLED: False}
        with self.router(arg_list=(ha.ENABLED,), **kwargs) as r:
            ha_disabled_settings = self._get_ha_defaults(ha_enabled=False)
            self._verify_ha_settings(r['router'], ha_disabled_settings)
            body = {'router': {ha.ENABLED: True,
                               ha.DETAILS: {ha.TYPE: ha.HA_VRRP}}}
            self._update('routers', r['router']['id'], body,
                         expected_code=webob.exc.HTTPConflict.code)
            r_after = self._show('routers', r['router']['id'])
            self._verify_ha_settings(r_after['router'],
                                     ha_disabled_settings)

    def test_enable_ha_when_ha_support_disabled_fails_non_gw(self):
        cfg.CONF.set_override('ha_support_enabled', False, group='ha')
        self._test_ha_disabled_non_gw_cases()

    def test_enable_ha_with_disabled_ha_type_fails_non_gw(self):
        cfg.CONF.set_override('disabled_ha_mechanisms', [ha.HA_VRRP],
                              group='ha')
        self._test_ha_disabled_non_gw_cases()

    def _test_change_ha_router_redundancy_level(self, new_level=1,
                                                gateway=True):

        def _change_redundancy_tests(redundancy_routers):
            new_ha_settings = self._get_ha_defaults(redundancy_level=new_level,
                                                    ha_type=ha.HA_HSRP,
                                                    probing_enabled=False)
            ha_spec = copy.deepcopy(new_ha_settings)
            del ha_spec[ha.DETAILS][ha.PRIORITY]
            updated_router = self._update('routers', r['router']['id'],
                                          {'router': ha_spec})
            # verify router visible to user
            self._verify_ha_settings(updated_router['router'], new_ha_settings)
            self._verify_router_ports(updated_router['router']['id'],
                                      subnet['network_id'], subnet['id'],
                                      port['network_id'],
                                      port['fixed_ips'][0]['subnet_id'])
            ha_d = updated_router['router'][ha.DETAILS]
            params = "&".join(["id=%s" % rr['id'] for rr in
                               ha_d[ha.REDUNDANCY_ROUTERS]])
            res = self._list('routers', query_params=params)
            new_redundancy_routers = res['routers']
            self.assertEqual(len(new_redundancy_routers), new_level)
            ha_disabled_settings = self._get_ha_defaults(ha_enabled=False)
            for rr in new_redundancy_routers:
                # redundancy router should have ha disabled
                self._verify_ha_settings(rr, ha_disabled_settings)
                # check that redundancy router have all ports
                self._verify_router_ports(
                    rr['id'], subnet['network_id'], subnet['id'],
                    port['network_id'], port['fixed_ips'][0]['subnet_id'])
            # verify that non-deleted redundancy routers are the same
            old_rr_ids = set(rr['id'] for rr in redundancy_routers)
            new_rr_ids = set(rr['id'] for rr in new_redundancy_routers)
            if len(old_rr_ids) < len(new_rr_ids):
                self.assertTrue(old_rr_ids.issubset(new_rr_ids))
            else:
                self.assertTrue(new_rr_ids.issubset(old_rr_ids))

        with self.port() as p:
            port = p['port']
            if gateway is True:
                with self.subnet(cidr='10.0.1.0/24') as s:
                    subnet = s['subnet']
                    self._set_net_external(subnet['network_id'])
                    with self.router(external_gateway_info={
                            'network_id': subnet['network_id']}) as r:
                        self._ha_router_port_test(subnet, r['router'], port,
                                                  None,
                                                  _change_redundancy_tests)
            else:
                with self.router() as r:
                    subnet = {'id': None, 'network_id': None}
                    self._ha_router_port_test(subnet, r['router'], port, None,
                                              _change_redundancy_tests)

    def test_decrease_ha_router_redundancy_level(self):
        self._test_change_ha_router_redundancy_level()

    def test_decrease_non_gw_ha_router_redundancy_level(self):
        self._test_change_ha_router_redundancy_level(gateway=False)

    def test_increase_ha_router_redundancy_level(self):
        self._test_change_ha_router_redundancy_level(new_level=3)

    def test_increase_non_gw_ha_router_redundancy_level(self):
        self._test_change_ha_router_redundancy_level(new_level=3,
                                                     gateway=False)

    # Overloaded test function that needs to be modified to run
    def _test_router_add_interface_subnet(self, router, subnet, msg=None):
        exp_notifications = ['router.create.start',
                             'router.create.end',
                             'network.create.start',
                             'network.create.end',
                             'subnet.create.start',
                             'subnet.create.end',
                             'router.interface.create',
                             'router.interface.delete']
        body = self._router_interface_action('add',
                                             router['router']['id'],
                                             subnet['subnet']['id'],
                                             None)
        self.assertIn('port_id', body, msg)

        # fetch port and confirm device_id
        r_port_id = body['port_id']
        port = self._show('ports', r_port_id)
        self.assertEqual(port['port']['device_id'],
                         router['router']['id'], msg)

        self._router_interface_action('remove',
                                      router['router']['id'],
                                      subnet['subnet']['id'],
                                      None)
        self._show('ports', r_port_id,
                   expected_code=webob.exc.HTTPNotFound.code)

        self.assertEqual(
            set(exp_notifications),
            set(n['event_type'] for n in fake_notifier.NOTIFICATIONS), msg)

        # include redundancy routers ids in allowed ids
        r_ids = {router['router']['id'],
                 router['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS][0]['id'],
                 router['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS][1]['id']}
        for n in fake_notifier.NOTIFICATIONS:
            if n['event_type'].startswith('router.interface.'):
                payload = n['payload']['router_interface']
                self.assertIn('id', payload)
                # assert by set inclusion
                self.assertIn(payload['id'], r_ids)
                self.assertIn('tenant_id', payload)
                stid = subnet['subnet']['tenant_id']
                # tolerate subnet tenant deliberately set to '' in the
                # nsx metadata access case
                self.assertIn(payload['tenant_id'], [stid, ''], msg)

    # Overloaded test function that needs to be modified to run
    def test_router_list(self):
        with self.router() as v1, self.router() as v2, self.router() as v3:
            routers = [v1, v2, v3]
            for r in routers[:]:
                for rr in r['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                    routers.append({'router': {'id': rr['id']}})
            self._test_list_resources('router', routers)

    def test_router_list_with_sort(self):
        with self.router(name='router1') as router1,\
                self.router(name='router2') as router2,\
                self.router(name='router3') as router3:
            routers = []
            for r in (router3, router2, router1):
                rr_info = r['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS][0]
                rr1 = self._show('routers', rr_info['id'])
                rr_info = r['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS][1]
                rr2 = self._show('routers', rr_info['id'])
                if rr1['router']['name'] < rr2['router']['name']:
                    routers.append(rr2)
                    routers.append(rr1)
                else:
                    routers.append(rr1)
                    routers.append(rr2)
                routers.append(r)
            self._test_list_with_sort('router', routers, [('name', 'desc')])

    # Overloaded test function that needs to be modified to run
    def test_router_list_with_pagination(self):
        with self.router(name='router1') as router1,\
                self.router(name='router2') as router2,\
                self.router(name='router3') as router3:
            routers = []
            for r in (router1, router2, router3):
                rr_info = r['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS][0]
                rr1 = self._show('routers', rr_info['id'])
                rr_info = r['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS][1]
                rr2 = self._show('routers', rr_info['id'])
                routers.append(r)
                if rr1['router']['name'] > rr2['router']['name']:
                    routers.append(rr2)
                    routers.append(rr1)
                else:
                    routers.append(rr1)
                    routers.append(rr2)
            self._test_list_with_pagination('router', routers, ('name', 'asc'),
                                            3, 4)

    # Overloaded test function that needs to be modified to run
    def test_router_list_with_pagination_reverse(self):
        with self.router(name='router1') as router1,\
                self.router(name='router2') as router2,\
                self.router(name='router3') as router3:
            routers = []
            for r in (router1, router2, router3):
                rr_info = r['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS][0]
                rr1 = self._show('routers', rr_info['id'])
                rr_info = r['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS][1]
                rr2 = self._show('routers', rr_info['id'])
                routers.append(r)
                if rr1['router']['name'] > rr2['router']['name']:
                    routers.append(rr2)
                    routers.append(rr1)
                else:
                    routers.append(rr1)
                    routers.append(rr2)
            self._test_list_with_pagination_reverse('router', routers,
                                                    ('name', 'asc'), 4, 3)

    # Overloaded test function that needs to be modified to run
    def test_floatingip_multi_external_one_internal(self):
        with self.subnet(cidr="10.0.0.0/24") as exs1,\
                self.subnet(cidr="11.0.0.0/24") as exs2,\
                self.subnet(cidr="12.0.0.0/24") as ins1:
            network_ex_id1 = exs1['subnet']['network_id']
            network_ex_id2 = exs2['subnet']['network_id']
            self._set_net_external(network_ex_id1)
            self._set_net_external(network_ex_id2)

            r2i_fixed_ips = [{'ip_address': '12.0.0.2'}]
            with self.router() as r1,\
                    self.router() as r2,\
                    self.port(subnet=ins1,
                              fixed_ips=r2i_fixed_ips) as r2i_port:
                self._add_external_gateway_to_router(
                    r1['router']['id'],
                    network_ex_id1)
                self._router_interface_action('add', r1['router']['id'],
                                              ins1['subnet']['id'],
                                              None)
                self._add_external_gateway_to_router(
                    r2['router']['id'],
                    network_ex_id2)
                self._router_interface_action('add', r2['router']['id'],
                                              None,
                                              r2i_port['port']['id'])

                with self.port(subnet=ins1,
                    # Use 12.0.0.199 instead of 12.0.0.3 so that the IP
                    # address we're requesting is definitely available
                               fixed_ips=[{'ip_address': '12.0.0.199'}]
                               ) as private_port:
                    # Use 10.0.0.199 instead of 10.0.0.3 so that the IP
                    # address we're requesting is definitely available
                    fp1 = self._make_floatingip(self.fmt, network_ex_id1,
                                                private_port['port']['id'],
                                                floating_ip='10.0.0.199')
                    # Use 11.0.0.199 instead of 11.0.0.3 so that the IP
                    # address we're requesting is definitely available
                    fp2 = self._make_floatingip(self.fmt, network_ex_id2,
                                                private_port['port']['id'],
                                                floating_ip='11.0.0.199')
                    self.assertEqual(fp1['floatingip']['router_id'],
                                     r1['router']['id'])
                    self.assertEqual(fp2['floatingip']['router_id'],
                                     r2['router']['id'])

    # Overloaded test function that needs to be modified to run
    def test_router_update_on_external_port(self):
        with self.router() as r:
            with self.subnet(cidr='10.0.1.0/24') as s:
                self._set_net_external(s['subnet']['network_id'])
                self._add_external_gateway_to_router(
                    r['router']['id'],
                    s['subnet']['network_id'])
                body = self._show('routers', r['router']['id'])
                net_id = body['router']['external_gateway_info']['network_id']
                self.assertEqual(net_id, s['subnet']['network_id'])
                port_res = self._list_ports(
                    'json',
                    200,
                    s['subnet']['network_id'],
                    tenant_id=r['router']['tenant_id'],
                    device_owner=l3_constants.DEVICE_OWNER_ROUTER_GW)
                port_list = self.deserialize('json', port_res)
                # Need to change to 3 as there are two ports for the
                # redundancy routers
                self.assertEqual(len(port_list['ports']), 3)

                routes = [{'destination': '135.207.0.0/16',
                           'nexthop': '10.0.1.199'}]

                body = self._update('routers', r['router']['id'],
                                    {'router': {'routes':
                                                routes}})

                body = self._show('routers', r['router']['id'])
                self.assertEqual(body['router']['routes'],
                                 routes)

                # Need to assert that the routes for the redundancy routers
                # have also been updated
                for rr_info in r['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                    body = self._show('routers', rr_info['id'])
                    self.assertEqual(body['router']['routes'],
                                     routes)

                self._remove_external_gateway_from_router(
                    r['router']['id'],
                    s['subnet']['network_id'])
                body = self._show('routers', r['router']['id'])
                r_after = body['router']
                gw_info = r_after['external_gateway_info']
                self.assertIsNone(gw_info)
                # Need to assert that the gateways in the redundancy
                # routers have also been updated
                for rr_info in r_after[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                    body = self._show('routers', rr_info['id'])
                    gw_info = body['router']['external_gateway_info']
                    self.assertIsNone(gw_info)

    # Overloaded test function that needs to be modified to run
    def test_floatingip_same_external_and_internal(self):
        # Select router with subnet's gateway_ip for floatingip when
        # routers connected to same subnet and external network.
        with self.subnet(cidr="10.0.0.0/24") as exs, \
                self.subnet(cidr="12.0.0.0/24", gateway_ip="12.0.0.50") as ins:
            network_ex_id = exs['subnet']['network_id']
            self._set_net_external(network_ex_id)

            r2i_fixed_ips = [{'ip_address': '12.0.0.2'}]
            with self.router() as r1, \
                    self.router() as r2, \
                    self.port(subnet=ins,
                              fixed_ips=r2i_fixed_ips) as r2i_port:
                self._add_external_gateway_to_router(
                    r1['router']['id'],
                    network_ex_id)
                self._router_interface_action('add', r2['router']['id'],
                                              None,
                                              r2i_port['port']['id'])
                self._router_interface_action('add', r1['router']['id'],
                                              ins['subnet']['id'],
                                              None)
                self._add_external_gateway_to_router(
                    r2['router']['id'],
                    network_ex_id)
                # Use 12.0.0.199 instead of 12.0.0.14 so that the IP
                # address we're requesting is definitely available
                with self.port(subnet=ins,
                               fixed_ips=[{'ip_address': '12.0.0.199'}]
                               ) as private_port:
                    fp = self._make_floatingip(self.fmt, network_ex_id,
                                               private_port['port']['id'])
                    self.assertEqual(r1['router']['id'],
                                     fp['floatingip']['router_id'])

    def test_router_update_change_external_gateway_and_routes(self):
        with self.router() as router:
            r = router['router']
            with self.subnet(cidr='12.0.1.0/24') as s_priv,\
                    self.subnet(cidr='10.0.1.0/24') as s_ext_1:
                self._set_net_external(s_ext_1['subnet']['network_id'])
                self._add_external_gateway_to_router(r['id'],
                    s_ext_1['subnet']['network_id'])
                body = self._show('routers', r['id'])
                net_id = body['router']['external_gateway_info']['network_id']
                self.assertEqual(net_id, s_ext_1['subnet']['network_id'])
                self._router_interface_action('add', r['id'],
                                              s_priv['subnet']['id'], None)
                port_res = self._list_ports(
                    'json',
                    200,
                    s_ext_1['subnet']['network_id'],
                    tenant_id=r['tenant_id'],
                    device_owner=l3_constants.DEVICE_OWNER_ROUTER_GW)
                gw_port_list = self.deserialize('json', port_res)
                # There are one gw port on the user visible router and two gw
                # ports on the redundancy routers
                self.assertEqual(len(gw_port_list['ports']), 3)
                port_res = self._list_ports(
                    'json',
                    200,
                    s_priv['subnet']['network_id'],
                    tenant_id=r['tenant_id'],
                    device_owner=l3_constants.DEVICE_OWNER_ROUTER_INTF)
                port_list = self.deserialize('json', port_res)
                # There are one interface VIP port and one extra port (for
                # interface ip) on the user visible router and two ports on
                # the redundancy routers (for their interface ips)
                self.assertEqual(len(port_list['ports']), 4)
                with self.subnet(cidr='11.0.1.0/24') as s_ext_2:
                    self._set_net_external(s_ext_2['subnet']['network_id'])
                    new_ext_gw = {
                        'network_id': s_ext_2['subnet']['network_id']}
                    routes = [{'destination': '135.207.0.0/16',
                               'nexthop': '12.0.1.55'}]
                    # change gateway and a route using that gateway
                    body = self._update('routers', r['id'],
                                        {'router': {
                                            EXTERNAL_GW_INFO: new_ext_gw,
                                            'routes': routes}})
                    body = self._show('routers', r['id'])
                    self.assertEqual(body['router']['routes'],
                                     routes)

                    # Need to assert that the routes for the redundancy routers
                    # have also been updated
                    self.assertEqual(
                        len(r[ha.DETAILS][ha.REDUNDANCY_ROUTERS]), 2)
                    for rr_info in r[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                        body = self._show('routers', rr_info['id'])
                        self.assertEqual(body['router']['routes'],
                                         routes)

                    self._remove_external_gateway_from_router(
                        r['id'], s_ext_2['subnet']['network_id'])
                    body = self._show('routers', r['id'])
                    r_after = body['router']
                    gw_info = r_after['external_gateway_info']
                    self.assertIsNone(gw_info)
                    # Need to assert that the gateways in the redundancy
                    # routers have also been updated
                    for rr_info in r_after[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                        body = self._show('routers', rr_info['id'])
                        gw_info = body['router']['external_gateway_info']
                        self.assertIsNone(gw_info)
                    routes = []
                    # Remove the route
                    body = self._update('routers', r['id'],
                                        {'router': {'routes': routes}})
                    body = self._show('routers', r['id'])
                    self.assertEqual(body['router']['routes'],
                                     routes)

                    # Need to assert that the routes for the redundancy routers
                    # have also been updated
                    self.assertEqual(
                        len(r[ha.DETAILS][ha.REDUNDANCY_ROUTERS]), 2)
                    for rr_info in r[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                        body = self._show('routers', rr_info['id'])
                        self.assertEqual(body['router']['routes'],
                                         routes)

                    self._router_interface_action('remove', r['id'],
                                                  s_priv['subnet']['id'], None)

    def test_redundancy_router_routes_is_from_user_visible_router(self):

        routes = [{'destination': '135.207.0.0/16', 'nexthop': '10.0.1.199'},
                  {'destination': '12.0.0.0/8', 'nexthop': '10.0.1.200'},
                  {'destination': '141.212.0.0/16', 'nexthop': '10.0.1.201'}]
        with self.router() as router,\
                self.subnet(cidr='10.0.1.0/24') as subnet,\
                self.port(subnet=subnet) as port:
            r = router['router']
            p = port['port']
            updated_r = self._routes_update_prepare(r['id'], None, p['id'],
                                                    routes)['router']
            params = "&".join(["id=%s" % rr['id'] for rr in
                               r[ha.DETAILS][ha.REDUNDANCY_ROUTERS]])
            routers = self._list('routers', query_params=params)['routers']
            routers.append(updated_r)
            correct_routes = _sort_routes(routes)
            for router in routers:
                self.assertEqual(_sort_routes(router['routes']),
                                 correct_routes)
            self._routes_update_cleanup(p['id'], None, r['id'], [])

    def _rr_routes_update_prepare(self, router_id, subnet_id, port_id,
                                  routes_router_id, routes, skip_add=False):
        if not skip_add:
            self._router_interface_action('add', router_id, subnet_id, port_id)
        self._update('routers', routes_router_id, {'router': {
            'routes': routes}})
        return self._show('routers', routes_router_id)

    def _rr_routes_update_cleanup(self, port_id, subnet_id, router_id,
                                  routes_router_id, routes):
        self._update('routers', routes_router_id, {'router': {
            'routes': routes}})
        self._router_interface_action('remove', router_id, subnet_id, port_id)

    def test_redundancy_router_routes_includes_user_visible_router(self):
        routes1 = [{'destination': '135.207.0.0/16', 'nexthop': '10.0.1.199'},
                   {'destination': '12.0.0.0/8', 'nexthop': '10.0.1.200'},
                   {'destination': '141.212.0.0/16', 'nexthop': '10.0.1.201'}]
        routes2 = [{'destination': '155.210.0.0/28', 'nexthop': '11.0.1.199'},
                   {'destination': '130.238.5.0/24', 'nexthop': '11.0.1.199'}]
        with self.router() as router,\
                self.subnet(cidr='10.0.1.0/24') as subnet1,\
                self.subnet(cidr='11.0.1.0/24') as subnet2,\
                self.port(subnet=subnet1) as port1,\
                self.port(subnet=subnet2) as port2:
            r = router['router']
            p1 = port1['port']
            p2 = port2['port']
            updated_r = self._routes_update_prepare(r['id'], None, p1['id'],
                                                    routes1)['router']
            rr1_id = r[ha.DETAILS][ha.REDUNDANCY_ROUTERS][0]['id']
            updated_rr1 = self._rr_routes_update_prepare(
                r['id'], None, p2['id'], rr1_id, routes2)['router']
            params = "id=%s" % r[ha.DETAILS][ha.REDUNDANCY_ROUTERS][1]['id']
            routers = self._list('routers', query_params=params)['routers']
            routers.append(updated_r)
            correct_routes1 = _sort_routes(routes1)
            for router in routers:
                self.assertEqual(_sort_routes(router['routes']),
                                 correct_routes1)
            routes1.extend(routes2)
            self.assertEqual(_sort_routes(updated_rr1['routes']),
                             _sort_routes(routes1))
            self._rr_routes_update_cleanup(p2['id'], None, r['id'], rr1_id, [])
            self._routes_update_cleanup(p1['id'], None, r['id'], [])

    def test__notify_subnetpool_address_scope_update(self):
        l3_plugin = manager.NeutronManager.get_service_plugins()[
            service_constants.L3_ROUTER_NAT]

        tenant_id = _uuid()
        with mock.patch.object(
                l3_plugin, 'notify_routers_updated') as chk_method, \
                self.subnetpool(prefixes=['10.0.0.0/24'],
                                admin=True, name='sp',
                                tenant_id=tenant_id) as subnetpool, \
                self.router(tenant_id=tenant_id) as router, \
                self.network(tenant_id=tenant_id) as network:
            subnetpool_id = subnetpool['subnetpool']['id']
            data = {'subnet': {
                    'network_id': network['network']['id'],
                    'subnetpool_id': subnetpool_id,
                    'prefixlen': 24,
                    'ip_version': 4,
                    'tenant_id': tenant_id}}
            req = self.new_create_request('subnets', data)
            subnet = self.deserialize(self.fmt, req.get_response(self.api))

            admin_ctx = context.get_admin_context()
            l3_plugin.add_router_interface(
                admin_ctx,
                router['router']['id'], {'subnet_id': subnet['subnet']['id']})
            l3_db._notify_subnetpool_address_scope_update(
                mock.ANY, mock.ANY, mock.ANY,
                context=admin_ctx, subnetpool_id=subnetpool_id)
            args, kwargs = chk_method.call_args
            self.assertEqual(admin_ctx, args[0])
            self.assertIn(router['router']['id'], args[1])


class L3AgentHARouterApplianceTestCase(
        test_l3_router_appliance_plugin.L3AgentRouterApplianceTestCase):

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        if l3_plugin is None:
            l3_plugin = L3_PLUGIN_KLASS
        if ext_mgr is None:
            ext_mgr = TestHAL3RouterApplianceExtensionManager()
        super(L3AgentHARouterApplianceTestCase, self).setUp(
            l3_plugin=l3_plugin, ext_mgr=ext_mgr)


class L3CfgAgentHARouterApplianceTestCase(
    HAL3RouterTestsMixin,
        test_l3_router_appliance_plugin.L3CfgAgentRouterApplianceTestCase):

    _is_ha_tests = True

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        if l3_plugin is None:
            l3_plugin = L3_PLUGIN_KLASS
        if ext_mgr is None:
            ext_mgr = TestHAL3RouterApplianceExtensionManager()
        cfg.CONF.set_override('default_ha_redundancy_level', 2, group='ha')

        super(L3CfgAgentHARouterApplianceTestCase, self).setUp(
            l3_plugin=l3_plugin, ext_mgr=ext_mgr)
        self.orig_get_sync_data = self.l3_plugin.get_sync_data
        self.l3_plugin.get_sync_data = self.l3_plugin.get_sync_data_ext

    def tearDown(self):
        self.l3_plugin.get_sync_data = self.orig_get_sync_data
        super(L3CfgAgentHARouterApplianceTestCase, self).tearDown()

    # Overloaded test function that needs to be modified to run
    def test_l3_agent_routers_query_interfaces(self):
        with self.router() as r:
            with self.port() as p:
                self._router_interface_action('add',
                                              r['router']['id'],
                                              None,
                                              p['port']['id'])

                routers = self.l3_plugin.get_sync_data(
                    context.get_admin_context(), None)
                self.assertEqual(3, len(routers))
                for router in routers:
                    interfaces = router[l3_constants.INTERFACE_KEY]
                    self.assertEqual(1, len(interfaces))
                    subnets = interfaces[0]['subnets']
                    self.assertEqual(1, len(subnets))
                    subnet_id = subnets[0]['id']
                    wanted_subnetid = p['port']['fixed_ips'][0]['subnet_id']
                    self.assertEqual(wanted_subnetid, subnet_id)

    # Overloaded test function that needs to be modified to run
    def test_l3_agent_routers_query_ignore_interfaces_with_moreThanOneIp(self):
        with self.router() as r:
            with self.subnet(cidr='9.0.1.0/24') as subnet:
                with self.port(subnet=subnet,
                               fixed_ips=[{'ip_address': '9.0.1.3'}]) as p:
                    self._router_interface_action('add',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])
                    # IP addresses 9.0.1.4 and 9.0.1.5 are consumed by the
                    # redundancy routers to we need to use other addresses.
                    port = {'port': {'fixed_ips':
                                     [{'ip_address': '9.0.1.199',
                                       'subnet_id': subnet['subnet']['id']},
                                      {'ip_address': '9.0.1.200',
                                       'subnet_id': subnet['subnet']['id']}]}}
                    ctx = context.get_admin_context()
                    self.core_plugin.update_port(ctx, p['port']['id'], port)
                    routers = self.l3_plugin.get_sync_data(ctx, None)
                    # One user visible router and two redundancy routers
                    self.assertEqual(3, len(routers))
                    # One interface for the user visible router and one each
                    # for the two redundancy routers
                    for r in routers:
                        interfaces = r.get(l3_constants.INTERFACE_KEY, [])
                        self.assertEqual(1, len(interfaces))

    # Overloaded test function that needs to be modified to run
    @unittest.skipIf(bc.NEUTRON_VERSION < bc.NEUTRON_NEWTON_VERSION,
                     "Test not applicable prior to Newton")
    def test_router_delete_precommit_event(self):
        deleted = set()
        auditor = lambda *a, **k: deleted.add(k['router_id'])
        registry.subscribe(auditor, resources.ROUTER, events.PRECOMMIT_DELETE)
        with self.router() as r:
            self._delete('routers', r['router']['id'])
        r_ids = {rr['id'] for rr in
                 r['router'][ha.DETAILS][ha.REDUNDANCY_ROUTERS]}
        r_ids.add(r['router']['id'])
        self.assertEqual(r_ids, deleted)

    def _test_notify_op_agent(self, target_func, *args):
        kargs = [item for item in args]
        kargs.append(self._l3_cfg_agent_mock)
        target_func(*kargs)

    def _routes_update_prepare(self, router_id, subnet_id, port_id,
                               routes_router_id, routes, skip_add=False):
        if not skip_add:
            self._router_interface_action('add', router_id, subnet_id, port_id)
        self._update('routers', routes_router_id, {'router': {
            'routes': routes}})
        return self._show('routers', routes_router_id)

    def _routes_update_cleanup(self, port_id, subnet_id, router_id,
                               routes_router_id, routes):
        self._update('routers', routes_router_id, {'router': {
            'routes': routes}})
        self._router_interface_action('remove', router_id, subnet_id, port_id)

    def test_l3_cfg_agent_query_ha_rdcy_router_routes_is_from_user_vsbl_router(
            self):
        routes = [{'destination': '135.207.0.0/16', 'nexthop': '10.0.1.199'},
                  {'destination': '12.0.0.0/8', 'nexthop': '10.0.1.200'},
                  {'destination': '141.212.0.0/16', 'nexthop': '10.0.1.201'}]
        with self.router() as router,\
                self.subnet(cidr='10.0.1.0/24') as subnet,\
                self.port(subnet=subnet) as port:
            r = router['router']
            p = port['port']
            self._routes_update_prepare(r['id'], None, p['id'], r['id'],
                                        routes)
            router_ids = [rr['id']
                          for rr in r[ha.DETAILS][ha.REDUNDANCY_ROUTERS]]
            router_ids.append(r['id'])
            e_context = context.get_admin_context()
            routers = self.l3_plugin.get_sync_data_ext(e_context, router_ids)
            self.assertEqual(len(router_ids), len(routers))
            correct_routes = _sort_routes(routes)
            for router in routers:
                self.assertEqual(_sort_routes(router['routes']),
                                 correct_routes)
            self._routes_update_cleanup(p['id'], None, r['id'], r['id'], [])

    def test_l3_cfg_agent_query_ha_rdcy_router_routes_include_user_vsbl_router(
            self):
        routes1 = [{'destination': '135.207.0.0/16', 'nexthop': '10.0.1.199'},
                   {'destination': '12.0.0.0/8', 'nexthop': '10.0.1.200'},
                   {'destination': '141.212.0.0/16', 'nexthop': '10.0.1.201'}]
        routes2 = [{'destination': '155.210.0.0/28', 'nexthop': '11.0.1.202'},
                   {'destination': '130.238.5.0/24', 'nexthop': '11.0.1.202'}]
        with self.router() as router,\
                self.subnet(cidr='10.0.1.0/24') as subnet1,\
                self.subnet(cidr='11.0.1.0/24') as subnet2,\
                self.port(subnet=subnet1) as port1,\
                self.port(subnet=subnet2) as port2:
            r = router['router']
            p1 = port1['port']
            p2 = port2['port']
            self._routes_update_prepare(r['id'], None, p1['id'], r['id'],
                                        routes1)
            rr1_id = r[ha.DETAILS][ha.REDUNDANCY_ROUTERS][0]['id']
            self._routes_update_prepare(r['id'], None, p2['id'], rr1_id,
                                        routes2)
            router_ids = [r['id'],
                          r[ha.DETAILS][ha.REDUNDANCY_ROUTERS][1]['id']]
            e_context = context.get_admin_context()
            routers = self.l3_plugin.get_sync_data_ext(e_context, router_ids)
            self.assertEqual(len(router_ids), len(routers))
            correct_routes1 = _sort_routes(routes1)
            for router in routers:
                self.assertEqual(_sort_routes(router['routes']),
                                 correct_routes1)
            routers = self.l3_plugin.get_sync_data_ext(e_context, [rr1_id])
            routes1.extend(routes2)
            self.assertEqual(_sort_routes(routers[0]['routes']),
                             _sort_routes(routes1))
            self._routes_update_cleanup(p2['id'], None, r['id'], rr1_id, [])
            self._routes_update_cleanup(p1['id'], None, r['id'], r['id'], [])

    def test_l3_cfg_agent_query_ha_router_with_fips(self):
        with self.subnet(cidr='10.0.1.0/24') as s_ext,\
                self.subnet(cidr='10.0.2.0/24') as s1,\
                self.subnet(cidr='10.0.3.0/24') as s2:
            self._set_net_external(s_ext['subnet']['network_id'])
            with self.router(external_gateway_info={
                    'network_id': s_ext['subnet']['network_id'],
                    'external_fixed_ips': [{'ip_address': '10.0.1.2'}]}) as r:
                ipspec1 = [{'subnet_id': s1['subnet']['id'],
                            'ip_address': s1['subnet']['gateway_ip']}]
                ipspec2 = [{'subnet_id': s2['subnet']['id'],
                            'ip_address': s2['subnet']['gateway_ip']}]
                with self.port(subnet=s1, fixed_ips=ipspec1) as p1,\
                        self.port(subnet=s1) as private_p1,\
                        self.port(subnet=s2, fixed_ips=ipspec2) as p2,\
                        self.port(subnet=s2) as private_p2:
                    self._router_interface_action(
                        'add', r['router']['id'], None, p1['port']['id'])
                    self._router_interface_action(
                        'add', r['router']['id'], None, p2['port']['id'])
                    fip1 = self._make_floatingip(
                        self.fmt,
                        s_ext['subnet']['network_id'],
                        port_id=private_p1['port']['id'])
                    fip1['floatingip']['fixed_ip_address_scope'] = None
                    fip2 = self._make_floatingip(
                        self.fmt,
                        s_ext['subnet']['network_id'],
                        port_id=private_p2['port']['id'])
                    fip2['floatingip']['fixed_ip_address_scope'] = None
                    fips_dict = {fip1['floatingip']['id']: fip1['floatingip'],
                                 fip2['floatingip']['id']: fip2['floatingip']}

                    e_context = context.get_admin_context()
                    query_params = """fixed_ips=ip_address%%3D%s""".strip() % (
                                   '10.0.1.2')
                    gw_port = self._list('ports',
                                         query_params=query_params)['ports'][0]
                    ports = {gw_port['id']: gw_port,
                             p1['port']['id']: p1['port'],
                             p2['port']['id']: p2['port']}
                    ha_groups_dict = {}
                    ha_settings = self._get_ha_defaults()
                    routers = self._validate_router_sync_data(
                        e_context, [r['router']['id']], s_ext, ports,
                        ha_settings, ha_groups_dict, fips_dict)
                    rr_ids = [rr['id'] for rr in routers[0][ha.DETAILS][
                        ha.REDUNDANCY_ROUTERS]]
                    del fip1['floatingip']['fixed_ip_address_scope']
                    del fip2['floatingip']['fixed_ip_address_scope']
                    # redundancy routers should here have same ha settings
                    # as the user visible routers since the l3 cfg agent
                    # needs that information to configure the redundancy
                    # router
                    self._validate_router_sync_data(
                        e_context, rr_ids, s_ext, ports, ha_settings,
                        ha_groups_dict, fips_dict)
                    # clean-up
                    self._delete('floatingips', fip2['floatingip']['id'])
                    self._delete('floatingips', fip1['floatingip']['id'])
                    self._router_interface_action('remove', r['router']['id'],
                                                  None, p2['port']['id'])
                    self._router_interface_action('remove', r['router']['id'],
                                                  None, p1['port']['id'])

    def _validate_router_sync_data(self, context, router_ids, external_subnet,
                                   ports, ha_settings, ha_groups_dict,
                                   fips_dict):
            routers = self.l3_plugin.get_sync_data_ext(context, router_ids)
            self.assertEqual(len(router_ids), len(routers))
            for r in routers:
                self.assertEqual(external_subnet['subnet']['id'],
                                 r['gw_port']['subnets'][0]['id'])
                # redundancy routers should here have same ha settings
                # as the user visible routers since the l3 cfg agent
                # needs that information to configure the redundancy
                # router
                self._verify_ha_settings(r, ha_settings)
                # the id of this redundancy router should be in the
                # list of redundancy routers
                rr_ids = [rr['id'] for rr in r[ha.DETAILS][
                    ha.REDUNDANCY_ROUTERS]]
                r_fips = r.get(l3_constants.FLOATINGIP_KEY, [])
                self.assertEqual(len(r_fips), len(fips_dict))
                for r_fip in r_fips:
                    self.assertEqual(r_fip, fips_dict[r_fip['id']])
                if ha_groups_dict:
                    # the id of a redundancy router should be in the
                    # list of redundancy routers
                    self.assertIn(r['id'], rr_ids)
                else:
                    # but not the id of a user visible router
                    self.assertNotIn(r['id'], rr_ids)
                # adding the router gw port to the list of internal router port
                # since we want to run the identical tests for all of them
                r[l3_constants.INTERFACE_KEY].append(r['gw_port'])
                self._validate_router_interface_ha_info(
                    ports, r[l3_constants.INTERFACE_KEY],
                    ha_groups_dict)
            return routers

    def _validate_router_interface_ha_info(self, ports_dict, interfaces,
                                           ha_groups_dict):
        self.assertEqual(len(ports_dict), len(interfaces))
        assemble_groups = len(ha_groups_dict) == 0
        for i in interfaces:
            ha_info = i[ha.HA_INFO]
            self.assertIsNotNone(ha_info)
            if assemble_groups:
                ha_groups_dict[ha_info[ha_db.HA_PORT]['id']] = ha_info[
                    ha_db.HA_GROUP]
            else:
                ha_port_id = ha_info[ha_db.HA_PORT]['id']
                self.assertIsNotNone(ports_dict.get(ha_port_id))
                self.assertEqual(ha_info[ha_db.HA_GROUP],
                                 ha_groups_dict[ha_port_id])

    def _test_router_gateway_op_agent(self, notifyApi):
        with self.router() as r:
            with self.subnet() as s:
                self._set_net_external(s['subnet']['network_id'])
                self._add_external_gateway_to_router(
                    r['router']['id'],
                    s['subnet']['network_id'])
                self._remove_external_gateway_from_router(
                    r['router']['id'],
                    s['subnet']['network_id'])
                # one user visible router and two redundancy routers (for
                # which a single update contains both redundancy routers), so
                # 1 + 1 add gateway + 1 + 1 remove gateway = 4 uodates
                self.assertEqual(
                    4, notifyApi.routers_updated.call_count)

    def _test_interfaces_op_agent(self, r, notifyApi):
        with self.port() as p:
            self._router_interface_action('add',
                                          r['router']['id'],
                                          None,
                                          p['port']['id'])
            # clean-up
            self._router_interface_action('remove',
                                          r['router']['id'],
                                          None,
                                          p['port']['id'])
        # one user visible router and two redundancy routers, so
        # 3 x add interface + 3 x remove interface
        self.assertEqual(6, notifyApi.routers_updated.call_count)

    def _test_floatingips_op_agent(self, notifyApi):
        with self.floatingip_with_assoc():
            pass
        # 2 x add gateway (one for user visible router), one for redundancy
        # routers
        # 3 x add interface (one for each router),
        # 1 x creation of floatingip (with 3 routers included),
        # 1 x deletion of floatingip (with 3 routers included)
        self.assertEqual(7, notifyApi.routers_updated.call_count)

    def _validate_ha_fip_ops(self, notifyApi, routers, first_operation):
        # 2 x add gateway (one for user visible router), one for redundancy
        # routers
        # 3 x add interface (one for each router),
        # 1 x update of floatingip (with 3 routers included),
        # 1 x deletion of floatingip (with 3 routers included)
        notify_call_1 = notifyApi.routers_updated.mock_calls[5]
        self.assertEqual(notify_call_1[1][2], first_operation)
        r_ids = {r['id'] for r in notify_call_1[1][1]}
        for r in routers:
            self.assertIn(r['id'], r_ids)
            r_ids.remove(r['id'])
        self.assertEqual(len(r_ids), 0)
        delete_call = notifyApi.routers_updated.mock_calls[6]
        self.assertEqual(delete_call[1][2], 'delete_floatingip')
        r_ids = {r['id'] for r in delete_call[1][1]}
        for r in routers:
            self.assertIn(r['id'], r_ids)
            r_ids.remove(r['id'])
        self.assertEqual(len(r_ids), 0)
        self.assertEqual(7, notifyApi.routers_updated.call_count)

    def _test_ha_floatingips_op_cfg_agent(self, notifyApi):
        with self.floatingip_with_assoc():
            routers = self._list('routers')['routers']
        self._validate_ha_fip_ops(notifyApi, routers, 'create_floatingip')

    def test_ha_floatingips_op_cfg_agent(self):
        self._test_notify_op_agent(self._test_ha_floatingips_op_cfg_agent)

    def _test_ha_floatingip_update_cfg_agent(self, notifyApi):
        with self.subnet() as private_sub:
            with self.port(private_sub) as p_port:
                private_port = p_port['port']
                with self.floatingip_no_assoc(private_sub) as fl_ip:
                    fip = fl_ip['floatingip']
                    routers = self._list('routers')['routers']
                    fip_spec = {'floatingip': {'port_id': private_port['id']}}
                    self._update('floatingips', fip['id'], fip_spec)
        self._validate_ha_fip_ops(notifyApi, routers, 'update_floatingip')

    def test_ha_floatingip_update_cfg_agent(self):
        self._test_notify_op_agent(self._test_ha_floatingip_update_cfg_agent)

    def test_populate_port_ha_information_no_port(self):

        with self.router(arg_list=(ha.ENABLED,)) as router:
            r = router['router']
            with self.port() as port:
                p = port['port']
                body = self._router_interface_action('add', r['id'], None,
                                                     p['id'])
                self.assertIn('port_id', body)
                self.assertEqual(body['port_id'], p['id'])
                adm_ctx = context.get_admin_context()
                with mock.patch(
                    'networking_cisco.plugins.cisco.db.l3.ha_db.HA_db_mixin.'
                    '_populate_port_ha_information') as mock_port_ha:
                    mock_port_ha.return_value = None
                    routers = self.l3_plugin.get_sync_data_ext(adm_ctx,
                                                               [r['id']])
                    for router in routers:
                        self.assertEqual(cisco_const.ROUTER_INFO_INCOMPLETE,
                            router['status'])

    def test_populate_port_ha_information_red_router_no_port(self):

        with self.router(arg_list=(ha.ENABLED,)) as router:
            r = router['router']
            with self.port() as port:
                p = port['port']
                body = self._router_interface_action('add', r['id'], None,
                                                     p['id'])
                self.assertIn('port_id', body)
                self.assertEqual(body['port_id'], p['id'])
                adm_ctx = context.get_admin_context()
                with mock.patch(
                    'networking_cisco.plugins.cisco.db.l3.ha_db.HA_db_mixin.'
                    '_populate_port_ha_information') as mock_port_ha:
                    mock_port_ha.return_value = None
                    rr_ids = [rr['id'] for rr in r[ha.DETAILS][
                        ha.REDUNDANCY_ROUTERS]]
                    routers = self.l3_plugin.get_sync_data_ext(adm_ctx, rr_ids)
                    for router in routers:
                        self.assertEqual(cisco_const.ROUTER_INFO_INCOMPLETE,
                            router['status'])

    def test_populate_port_ha_information_no_port_gw_port(self):

        with self.router(arg_list=(ha.ENABLED,)) as router:
            r = router['router']
            with self.subnet() as s:
                self._set_net_external(s['subnet']['network_id'])
                self._add_external_gateway_to_router(
                    r['id'],
                    s['subnet']['network_id'])
                adm_ctx = context.get_admin_context()
                with mock.patch(
                    'networking_cisco.plugins.cisco.db.l3.ha_db.HA_db_mixin.'
                    '_populate_port_ha_information') as mock_port_ha:
                    mock_port_ha.return_value = None
                    routers = self.l3_plugin.get_sync_data_ext(adm_ctx,
                                                               [r['id']])
                    for router in routers:
                        body = self._show('routers', r['id'])
                        r_after = body['router']
                        gw_info = r_after['external_gateway_info']
                        self.assertIsNotNone(gw_info)
                        self.assertEqual(cisco_const.ROUTER_INFO_INCOMPLETE,
                            router['status'])

    def test_populate_port_ha_information_red_router_no_port_gw_port(self):

        with self.router(arg_list=(ha.ENABLED,)) as router:
            r = router['router']
            with self.subnet() as s:
                self._set_net_external(s['subnet']['network_id'])
                self._add_external_gateway_to_router(
                    r['id'],
                    s['subnet']['network_id'])
                adm_ctx = context.get_admin_context()
                with mock.patch(
                    'networking_cisco.plugins.cisco.db.l3.ha_db.HA_db_mixin.'
                    '_populate_port_ha_information') as mock_port_ha:
                    mock_port_ha.return_value = None
                    rr_ids = [rr['id'] for rr in r[ha.DETAILS][
                        ha.REDUNDANCY_ROUTERS]]
                    routers = self.l3_plugin.get_sync_data_ext(adm_ctx, rr_ids)
                    for router in routers:
                        body = self._show('routers', router['id'])
                        r_after = body['router']
                        gw_info = r_after['external_gateway_info']
                        self.assertIsNotNone(gw_info)
                        self.assertEqual(cisco_const.ROUTER_INFO_INCOMPLETE,
                            router['status'])

    def test_populate_port_ha_information_retries_succeed(self):

        def fake_one():
            if m.call_count == 3:
                return hag
            elif m.call_count == 4:
                return extra_port
            else:
                raise exc.NoResultFound

        with self.router(arg_list=(ha.ENABLED,)) as router:
            r = router['router']
            with self.port() as port:
                p = port['port']
                body = self._router_interface_action('add', r['id'], None,
                                                     p['id'])
                self.assertIn('port_id', body)
                self.assertEqual(body['port_id'], p['id'])
                adm_ctx = context.get_admin_context()
                hags = {}
                mod_itfcs = []
                hag = self.l3_plugin._get_ha_group_for_subnet_id(
                    adm_ctx, r['id'], p['fixed_ips'][0]['subnet_id'])
                extra_port = self._show('ports', hag.extra_port_id)['port']
                with mock.patch('sqlalchemy.orm.query.Query.one') as m:
                    m.side_effect = fake_one
                    pop_p = self.l3_plugin._populate_port_ha_information(
                        adm_ctx, p, r['id'], hags, r['id'], mod_itfcs)
                    self.assertEqual(m.call_count, 4)
                    self.assertIn(ha.HA_INFO, pop_p)
                    self.assertIsNotNone(pop_p[ha.HA_INFO]['group'])

    def test_populate_port_ha_information_all_retries_fail(self):
        with self.router(arg_list=(ha.ENABLED,)) as router:
            r = router['router']
            with self.port() as port:
                p = port['port']
                body = self._router_interface_action('add', r['id'], None,
                                                     p['id'])
                self.assertIn('port_id', body)
                self.assertEqual(body['port_id'], p['id'])
                adm_ctx = context.get_admin_context()
                hags = {}
                mod_itfcs = []
                with mock.patch('sqlalchemy.orm.query.Query.one') as m:
                    m.side_effect = exc.NoResultFound
                    pop_p = self.l3_plugin._populate_port_ha_information(
                        adm_ctx, p, r['id'], hags, r['id'], mod_itfcs)
                    self.assertIsNone(pop_p)
                    self.assertEqual(len(mod_itfcs), 0)
                    self.assertEqual(m.call_count, ha_db.LOOKUP_RETRIES)

    def test_failed_add_gw_hosting_port_info_changes_router_status(self,
                                                                   num=1):
        (super(L3CfgAgentHARouterApplianceTestCase, self).
         test_failed_add_gw_hosting_port_info_changes_router_status(3))

    def test_failed_add_hosting_port_info_changes_router_status(self, num=1):
        (super(L3CfgAgentHARouterApplianceTestCase, self).
         test_failed_add_hosting_port_info_changes_router_status(3))
