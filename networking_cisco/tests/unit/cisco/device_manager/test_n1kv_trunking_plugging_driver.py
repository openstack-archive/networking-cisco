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

import copy

import mock

from neutron.common import test_lib
from neutron import context
from neutron.extensions import providernet as pr_net
from neutron import manager
from neutron.plugins.common import constants as service_constants
from neutron.tests.unit.extensions import test_l3

from networking_cisco.plugins.cisco.device_manager.plugging_drivers.\
    n1kv_ml2_trunking_driver import N1kvML2TrunkingPlugDriver
from networking_cisco.plugins.cisco.device_manager.plugging_drivers.\
    n1kv_ml2_trunking_driver import MIN_LL_VLAN_TAG
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    config as ml2_n1kv_config)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import constants
from networking_cisco.tests.unit.cisco.l3 import (
    test_l3_router_appliance_plugin)

L3_PLUGIN_KLASS = (
    'networking_cisco.tests.unit.cisco.l3.test_l3_router_appliance_plugin.'
    'TestApplianceL3RouterServicePlugin')
POLICY_PROFILE_PLUGIN = ('networking_cisco.plugins.ml2.drivers.cisco.n1kv.'
                  'policy_profile_service.PolicyProfilePlugin')
NETWORK_PROFILE_PLUGIN = ('networking_cisco.plugins.ml2.drivers.cisco.n1kv.'
                  'network_profile_service.NetworkProfilePlugin')
DEFAULT_PP = 'm1'


class TestN1kvTrunkingPluggingDriver(
    test_l3_router_appliance_plugin.L3RouterApplianceTestCaseBase,
        test_l3.L3NatTestCaseMixin):

    # we use router types defined in .ini file.
    configure_routertypes = False
    router_type = 'CSR1kv_Neutron_router'

    test_driver = N1kvML2TrunkingPlugDriver

    def setUp(self, service_plugins=None):
        service_plugins = {
            constants.CISCO_N1KV: POLICY_PROFILE_PLUGIN,
            constants.CISCO_N1KV_NET_PROFILE: NETWORK_PROFILE_PLUGIN,
            service_constants.L3_ROUTER_NAT: L3_PLUGIN_KLASS}

        ml2_cisco_opts = {
            'n1kv_vsm_ips': ['127.0.0.1'],
            'username': 'admin',
            'password': 'Sfish123',
            'default_policy_profile': DEFAULT_PP
        }

        for opt, val in ml2_cisco_opts.items():
            ml2_n1kv_config.cfg.CONF.set_override(opt, val, 'ml2_cisco_n1kv')

        super(TestN1kvTrunkingPluggingDriver, self).setUp(
            service_plugins=service_plugins)
        # save possible test_lib.test_config 'config_files' dict entry so we
        # can restore it after tests since we will change its value
        self._old_config_files = copy.copy(test_lib.test_config.get(
            'config_files'))
        # include config files for device manager service plugin and router
        # service plugin since we define a number of hosting device templates,
        # hosting devices and routertypes there
        self._add_device_manager_plugin_ini_file()
        self._add_router_plugin_ini_file()
        #TODO(bobmel): Fix bug in test_extensions.py and we can remove the
        # below call to setup_config()
        self.setup_config()
        self.net_plugin = manager.NeutronManager.get_service_plugins().get(
            constants.CISCO_N1KV_NET_PROFILE)
        self.policy_plugin = manager.NeutronManager.get_service_plugins().get(
            constants.CISCO_N1KV)

    def tearDown(self):
        if self._old_config_files is None:
            test_lib.test_config.pop('config_files', None)
        else:
            test_lib.test_config['config_files'] = self._old_config_files
        super(TestN1kvTrunkingPluggingDriver, self).tearDown()

    def test__get_profile_id(self):
        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'}])
        self.policy_plugin.get_policy_profiles = m1
        plugging_driver = self.test_driver()
        p_id = plugging_driver._get_profile_id('port_profile', 'N1kv port '
                                               'profile', 'the_profile')
        self.assertEqual(p_id, 'profile_uuid1')

    def test__get_profile_id_multiple_match(self):
        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'},
                                          {'id': 'profile_uuid2'}])
        self.policy_plugin.get_policy_profiles = m1
        plugging_driver = self.test_driver()
        p_id = plugging_driver._get_profile_id('port_profile', 'N1kv port '
                                               'profile', 'the_profile')
        self.assertEqual(p_id, None)

    def test__get_profile_id_no_match(self):
        m1 = mock.MagicMock(return_value=[])
        self.policy_plugin.get_policy_profiles = m1
        plugging_driver = self.test_driver()
        p_id = plugging_driver._get_profile_id('port_profile', 'N1kv port '
                                               'profile', 'the_profile')
        self.assertEqual(p_id, None)

    def test__get_network_profile_id(self):
        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'}])
        self.net_plugin.get_network_profiles = m1
        plugging_driver = self.test_driver()
        p_id = plugging_driver._get_profile_id('net_profile', 'net profile',
                                               'the_profile')
        self.assertEqual(p_id, 'profile_uuid1')

    def test__get_network_profile_id_multiple_match(self):
        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'},
                                          {'id': 'profile_uuid2'}])
        self.net_plugin.get_network_profiles = m1
        plugging_driver = self.test_driver()
        p_id = plugging_driver._get_profile_id('net_profile', 'net profile',
                                               'the_profile')
        self.assertEqual(p_id, None)

    def test__get_network_profile_id_no_match(self):
        m1 = mock.MagicMock(return_value=[])
        self.net_plugin.get_network_profiles = m1
        plugging_driver = self.test_driver()
        p_id = plugging_driver._get_profile_id('net_profile', 'net profile',
                                               'the_profile')
        self.assertEqual(p_id, None)

    def test_create_hosting_device_resources(self):

        def _verify_resource_name(res_list, resource_prefix, num):
            valid_names = set()
            for i in range(num):
                index = str(i + 1)
                valid_names.add('t1_' + resource_prefix + index)
                valid_names.add('t2_' + resource_prefix + index)
            for r in res_list:
                # assert by trying to remove item
                valid_names.remove(r['name'])
            self.assertEqual(len(valid_names), 0)

        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'}])
        self.policy_plugin.get_policy_profiles = m1
        m2 = mock.MagicMock(return_value=[{'id': 'profile_uuid2'}])
        self.net_plugin.get_network_profiles = m2
        osn_subnet = self._list('subnets')['subnets'][0]
        tenant_id = osn_subnet['tenant_id']
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = self.test_driver()
        mgmt_context = {'mgmt_nw_id': osn_subnet['network_id']}
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 2)
        self.assertIsNotNone(plugging_driver._t1_net_id)
        self.assertIsNotNone(plugging_driver._t2_net_id)
        self.assertIsNotNone(res['mgmt_port'])
        self.assertEqual(len(res), 2)
        self.assertEqual(len(res['ports']), 4)
        _verify_resource_name(res['ports'], 'p:', 2)

    def test_create_hosting_device_resources_no_mgmt_context(self):
        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'}])
        self.policy_plugin.get_policy_profiles = m1
        m2 = mock.MagicMock(return_value=[{'id': 'profile_uuid2'}])
        self.net_plugin.get_network_profiles = m2
        osn_subnet = self._list('subnets')['subnets'][0]
        tenant_id = osn_subnet['tenant_id']
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = self.test_driver()
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, None, 2)
        self.assertIsNone(plugging_driver._t1_net_id)
        self.assertIsNone(plugging_driver._t2_net_id)
        self.assertIsNone(res['mgmt_port'], res)
        self.assertEqual(len(res), 2)
        self.assertEqual(len(res['ports']), 0)

    def test_get_hosting_device_resources_by_complementary_id(self):
        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'}])
        self.policy_plugin.get_policy_profiles = m1
        m2 = mock.MagicMock(return_value=[{'id': 'profile_uuid2'}])
        self.net_plugin.get_network_profiles = m2
        osn_subnet = self._list('subnets')['subnets'][0]
        tenant_id = osn_subnet['tenant_id']
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = self.test_driver()
        mgmt_context = {'mgmt_nw_id': osn_subnet['network_id']}
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 1)
        # ports that should not be returned
        with self.port(), self.port(device_id='uuid2'), self.port(
                tenant_id=tenant_id):
            res_get = plugging_driver.get_hosting_device_resources(
                ctx, '', 'some_id', tenant_id, osn_subnet['network_id'])
            self.assertEqual(res_get['mgmt_port']['id'],
                             res['mgmt_port']['id'])
            self.assertEqual({i['id'] for i in res['ports']},
                             {i['id'] for i in res_get['ports']})

    def test_get_hosting_device_resources_by_device_id(self):
        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'}])
        self.policy_plugin.get_policy_profiles = m1
        m2 = mock.MagicMock(return_value=[{'id': 'profile_uuid2'}])
        self.net_plugin.get_network_profiles = m2
        osn_subnet = self._list('subnets')['subnets'][0]
        tenant_id = osn_subnet['tenant_id']
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = self.test_driver()
        mgmt_context = {'mgmt_nw_id': osn_subnet['network_id']}
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 1)
        # update attributes of created ports to fake what Nova updates
        hd_uuid = 'hd_uuid1'
        update_spec = {'port': {'device_id': hd_uuid,
                                'device_owner': 'nova'}}
        for hd_port in self._list('ports')['ports']:
            self._update('ports', hd_port['id'], update_spec)
        # ports that should not be returned
        with self.port(), self.port(device_id='uuid2'), self.port(
                tenant_id=tenant_id), self.port(tenant_id=tenant_id,
                                                device_owner='other_uuid'):
            res_get = plugging_driver.get_hosting_device_resources(
                ctx, hd_uuid, 'some_id', tenant_id, osn_subnet['network_id'])
            self.assertEqual(res_get['mgmt_port']['id'],
                             res['mgmt_port']['id'])
            self.assertEqual({i['id'] for i in res['ports']},
                             {i['id'] for i in res_get['ports']})

    def test_delete_hosting_device_resources(self):
        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'}])
        self.policy_plugin.get_policy_profiles = m1
        m2 = mock.MagicMock(return_value=[{'id': 'profile_uuid2'}])
        self.net_plugin.get_network_profiles = m2
        osn_subnet = self._list('subnets')['subnets'][0]
        tenant_id = osn_subnet['tenant_id']
        ctx = context.Context('', tenant_id, is_admin=True)
        mgmt_context = {'mgmt_nw_id': osn_subnet['network_id']}
        plugging_driver = self.test_driver()
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 2)
        nets = self._list('networks')
        self.assertEqual(len(nets['networks']), 3)
        subnets = self._list('subnets')
        self.assertEqual(len(subnets['subnets']), 3)
        ports = self._list('ports')
        self.assertEqual(len(ports['ports']), 5)
        # avoid passing the mgmt port twice in argument list
        mgmt_port = res['mgmt_port']
        del res['mgmt_port']
        plugging_driver.delete_hosting_device_resources(
            ctx, tenant_id, mgmt_port, **res)
        nets = self._list('networks')['networks']
        # mgmt network and subnet should remain
        self.assertEqual(len(nets), 1)
        self.assertEqual(nets[0]['id'], osn_subnet['network_id'])
        subnets = self._list('subnets')['subnets']
        self.assertEqual(len(subnets), 1)
        self.assertEqual(subnets[0]['id'], osn_subnet['id'])
        ports = self._list('ports')
        self.assertEqual(len(ports['ports']), 0)

    def test_delete_hosting_device_resources_retry_success(self):

        def _fake_delete_resources(context, name, deleter,
                                   exception_type, resource_ids):
            if counters['attempts'] < counters['max_attempts']:
                if name == "trunk port":
                    counters['attempts'] += 1
                return
            real_delete_resources(context, name, deleter,
                                  exception_type, resource_ids)

        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'}])
        self.policy_plugin.get_policy_profiles = m1
        m2 = mock.MagicMock(return_value=[{'id': 'profile_uuid2'}])
        self.net_plugin.get_network_profiles = m2
        osn_subnet = self._list('subnets')['subnets'][0]
        tenant_id = osn_subnet['tenant_id']
        ctx = context.Context('', tenant_id, is_admin=True)
        mgmt_context = {'mgmt_nw_id': osn_subnet['network_id']}
        plugging_driver = self.test_driver()
        real_delete_resources = plugging_driver._delete_resources
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 2)
        nets = self._list('networks')
        self.assertEqual(len(nets['networks']), 3)
        subnets = self._list('subnets')
        self.assertEqual(len(subnets['subnets']), 3)
        ports = self._list('ports')
        self.assertEqual(len(ports['ports']), 5)
        # avoid passing the mgmt port twice in argument list
        mgmt_port = res['mgmt_port']
        del res['mgmt_port']
        with mock.patch.object(plugging_driver, '_delete_resources') as (
                delete_mock):
            with mock.patch(
                    'networking_cisco.plugins.cisco.device_manager.'
                    'plugging_drivers.n1kv_ml2_trunking_driver.'
                    'eventlet.sleep'):
                delete_mock.side_effect = _fake_delete_resources
                counters = {'attempts': 0, 'max_attempts': 2}
                plugging_driver.delete_hosting_device_resources(
                    ctx, tenant_id, mgmt_port, **res)
                # three retry iterations with two calls per iteration
                self.assertEqual(delete_mock.call_count, 6)
                nets = self._list('networks')['networks']
                self.assertEqual(len(nets), 1)
                subnets = self._list('subnets')['subnets']
                self.assertEqual(len(subnets), 1)
                ports = self._list('ports')
                self.assertEqual(len(ports['ports']), 0)

    def test_delete_hosting_device_resources_finite_attempts(self):
        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'}])
        self.policy_plugin.get_policy_profiles = m1
        m2 = mock.MagicMock(return_value=[{'id': 'profile_uuid2'}])
        self.net_plugin.get_network_profiles = m2
        osn_subnet = self._list('subnets')['subnets'][0]
        tenant_id = osn_subnet['tenant_id']
        ctx = context.Context('', tenant_id, is_admin=True)
        mgmt_context = {'mgmt_nw_id': osn_subnet['network_id']}
        plugging_driver = self.test_driver()
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 2)
        nets = self._list('networks')
        self.assertEqual(len(nets['networks']), 3)
        subnets = self._list('subnets')
        self.assertEqual(len(subnets['subnets']), 3)
        ports = self._list('ports')
        self.assertEqual(len(ports['ports']), 5)
        # avoid passing the mgmt port twice in argument list
        mgmt_port = res['mgmt_port']
        del res['mgmt_port']
        with mock.patch.object(plugging_driver, '_delete_resources') as (
                delete_mock):
            with mock.patch(
                    'networking_cisco.plugins.cisco.device_manager.'
                    'plugging_drivers.n1kv_ml2_trunking_driver.eventlet'
                    '.sleep'):
                plugging_driver.delete_hosting_device_resources(
                    ctx, tenant_id, mgmt_port, **res)
                # four retry iterations with two calls per iteration
                self.assertEqual(delete_mock.call_count, 8)
                nets = self._list('networks')['networks']
                self.assertEqual(len(nets), 3)
                subnets = self._list('subnets')['subnets']
                self.assertEqual(len(subnets), 3)
                ports = self._list('ports')
                self.assertEqual(len(ports['ports']), 5)

    def test_extend_hosting_port_info_adds_segmentation_id(self):
        hosting_info = {}
        fake_port_db_obj = mock.MagicMock()
        fake_port_db_obj.hosting_info = mock.MagicMock()
        fake_port_db_obj.hosting_info.segmentation_id = 50
        hosting_device = mock.MagicMock()
        tenant_id = 'tenant_uuid1'
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = self.test_driver()
        plugging_driver.extend_hosting_port_info(ctx, fake_port_db_obj,
                                                 hosting_device, hosting_info)
        self.assertEqual(hosting_info['segmentation_id'], 50)

    def _update_provider_net_info(self, res_list, fields):
        for res in res_list:
            pv_info = self._pv_info['vlan'].get(res['id'])
            if pv_info is None:
                pv_info = self._pv_info['vxlan'].get(res['id'])
                if pv_info is None:
                    nw_type = self._network_type
                    if not self._pv_info[nw_type]:
                        tag = {'vlan': 50, 'vxlan': 7000}[nw_type]
                        pv_info = {'nw_type': nw_type, 'tag': tag}
                        self._pv_info[nw_type][res['id']] = pv_info
            if pv_info is None:
                tag = max([i['tag']
                           for i in self._pv_info[nw_type].values()]) + 1
                pv_info = {'nw_type': nw_type, 'tag': tag}
                self._pv_info[nw_type][res['id']] = pv_info
            res[pr_net.NETWORK_TYPE] = pv_info['nw_type']
            res[pr_net.SEGMENTATION_ID] = pv_info['tag']
            if fields is not None:
                for attr in list(res.keys()):
                    if attr not in fields:
                        del res[attr]

    def _mocked_get_network(self, context, id, fields=None):
        res = self.real_get_network(context, id)
        self._update_provider_net_info([res], fields)
        return res

    def _mocked_get_networks(self, *args, **kwargs):
        if len(args) >= 3:
            fields = args[2]
            list_args = [i for i in args]
            list_args[2] = None
            args = list_args
        else:
            fields = kwargs.pop('fields', None)
        res_list = self.real_get_networks(*args, **kwargs)
        self._update_provider_net_info(res_list, fields)
        return res_list

    def _test_allocate_hosting_port(self, test_info1, test_info2):

        def _validate_allocation(plugin, ctx, r, port_db, test_info,
                                 i, hd, trunk_ports, plugging_driver):
            binding_db = plugin._allocate_hosting_port(
                ctx, r['id'], port_db, hd['id'], plugging_driver)
            selected_port = trunk_ports.get(binding_db.hosting_port_id)
            self.assertIsNotNone(selected_port)
            self.assertEqual(selected_port['name'],
                             test_info['port_names'][i])
            self.assertEqual(binding_db.segmentation_id,
                             test_info['vlan_tags'][i])

        m1 = mock.MagicMock(return_value=[{'id': 'profile_uuid1'}])
        self.policy_plugin.get_policy_profiles = m1
        m2 = mock.MagicMock(return_value=[{'id': 'profile_uuid2'}])
        self.net_plugin.get_network_profiles = m2
        osn_subnet = self._list('subnets')['subnets'][0]
        tenant_id = osn_subnet['tenant_id']
        ctx = context.Context('', tenant_id, is_admin=True)
        mgmt_context = {'mgmt_nw_id': osn_subnet['network_id']}
        plugging_driver = self.test_driver()
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 2)
        plugging_driver.setup_logical_port_connectivity = mock.MagicMock()
        plugging_driver.teardown_logical_port_connectivity = mock.MagicMock()
        with self.subnet() as subnet1:
            sn1 = subnet1['subnet']
            ext_net_id = sn1['network_id']
            self._set_net_external(ext_net_id)
            gw_info = {'network_id': ext_net_id}
            with self.router(external_gateway_info=gw_info,
                             tenant_id=sn1['tenant_id']) as router1:
                r1 = router1['router']
                hds = self._list('hosting_devices')['hosting_devices']
                hd = hds[0]
                # update attributes of created ports to fake what Nova updates
                hd_uuid = hd['id']
                update_spec = {'port': {'device_id': hd_uuid,
                                        'device_owner': 'nova'}}
                self._update('ports', res['mgmt_port']['id'], update_spec)
                trunk_ports = {}
                for hd_port in res['ports']:
                    self._update('ports', hd_port['id'], update_spec)
                    trunk_ports[hd_port['id']] = hd_port

                self._pv_info = {'vlan': {}, 'vxlan': {}}
                self._network_type = test_info1['network_types'][0]
                self.real_get_network = self.core_plugin.get_network
                self.real_get_networks = self.core_plugin.get_networks
                with mock.patch.object(self.core_plugin, 'get_network') as m1,\
                        mock.patch.object(self.core_plugin,
                                          'get_networks') as m2:
                    m1.side_effect = self._mocked_get_network
                    m2.side_effect = self._mocked_get_networks
                    u1_ctx = context.Context('', r1['tenant_id'],
                                             is_admin=True)
                    gw_port_db = self.core_plugin._get_ports_query(
                        u1_ctx, filters={'network_id': [ext_net_id]}).one()
                    _validate_allocation(
                        self.l3_plugin, u1_ctx, r1, gw_port_db,
                        test_info1, 0, hd, trunk_ports, plugging_driver)
                    for i in range(1, len(test_info1['network_types'])):
                        cidr = '1.0.' + str(i) + '.0/24'
                        with self.subnet(cidr=cidr) as subnet2:
                            sn2 = subnet2['subnet']
                            itfc_info = self._router_interface_action(
                                'add', r1['id'], sn2['id'], None)
                            self._network_type = test_info1['network_types'][i]
                            port_db = self.core_plugin._get_port(
                                u1_ctx, itfc_info['port_id'])
                            _validate_allocation(
                                self.l3_plugin, u1_ctx, r1, port_db,
                                test_info1,
                                i, hd, trunk_ports, plugging_driver)
                    self._network_type = test_info2['network_types'][0]
                    with self.router(external_gateway_info=gw_info,
                                     tenant_id=sn1['tenant_id']) as router2:
                        r2 = router2['router']
                        u2_ctx = context.Context('', r2['tenant_id'],
                                                 is_admin=True)
                        gw_port_db = self.core_plugin._get_ports_query(
                            u2_ctx, filters={'network_id': [ext_net_id],
                                             'device_id': [r2['id']]}).one()
                        _validate_allocation(
                            self.l3_plugin, u2_ctx, r2, gw_port_db,
                            test_info2, 0, hd, trunk_ports, plugging_driver)
                        for i in range(1, len(test_info2['network_types'])):
                            cidr = '2.0.' + str(i) + '.0/24'
                            with self.subnet(cidr=cidr) as subnet3:
                                sn3 = subnet3['subnet']
                                itfc_info = self._router_interface_action(
                                    'add', r2['id'], sn3['id'], None)
                                self._network_type = test_info2[
                                    'network_types'][i]
                                port_db = self.core_plugin._get_port(
                                    u2_ctx, itfc_info['port_id'])
                                _validate_allocation(
                                    self.l3_plugin, u2_ctx, r2,
                                    port_db, test_info2, i, hd, trunk_ports,
                                    plugging_driver)

    def test_allocate_hosting_port_vlan_network_all_unused(self):
        self._test_allocate_hosting_port({'network_types': ['vlan'],
                                          'port_names': ['t2_p:1'],
                                          'vlan_tags': [50]},
                                         {'network_types': ['vlan'],
                                          'port_names': ['t2_p:2'],
                                          'vlan_tags': [50]})

    def test_allocate_hosting_port_vlan_network_vlan_already_allocated(self):
        self._test_allocate_hosting_port({'network_types': ['vlan', 'vlan'],
                                          'port_names': ['t2_p:1', 't2_p:1'],
                                          'vlan_tags': [50, 51]},
                                         {'network_types': ['vlan', 'vlan'],
                                          'port_names': ['t2_p:2', 't2_p:2'],
                                          'vlan_tags': [50, 52]})

    def test_allocate_hosting_port_vlan_network_vxlan_already_allocated(self):
        self._test_allocate_hosting_port({'network_types': ['vxlan', 'vlan'],
                                          'port_names': ['t1_p:1', 't2_p:1'],
                                          'vlan_tags': [MIN_LL_VLAN_TAG, 50]},
                                         {'network_types': ['vxlan', 'vlan'],
                                          'port_names': ['t1_p:2', 't2_p:2'],
                                          'vlan_tags': [MIN_LL_VLAN_TAG, 51]})

    def test_allocate_hosting_port_vxlan_network_all_unused(self):
        self._test_allocate_hosting_port({'network_types': ['vxlan'],
                                          'port_names': ['t1_p:1'],
                                          'vlan_tags': [MIN_LL_VLAN_TAG]},
                                         {'network_types': ['vxlan'],
                                          'port_names': ['t1_p:2'],
                                          'vlan_tags': [MIN_LL_VLAN_TAG]})

    def test_allocate_hosting_port_vxlan_network_vlan_already_allocated(self):
        self._test_allocate_hosting_port({'network_types': ['vlan', 'vxlan'],
                                          'port_names': ['t2_p:1', 't1_p:1'],
                                          'vlan_tags': [50, MIN_LL_VLAN_TAG]},
                                         {'network_types': ['vlan', 'vxlan'],
                                          'port_names': ['t2_p:2', 't1_p:2'],
                                          'vlan_tags': [50,
                                                        MIN_LL_VLAN_TAG]})

    def test_allocate_hosting_port_vxlan_network_vxlan_already_allocated(self):
        self._test_allocate_hosting_port({'network_types': ['vxlan', 'vxlan'],
                                          'port_names': ['t1_p:1', 't1_p:1'],
                                          'vlan_tags': [10, 11]},
                                         {'network_types': ['vxlan', 'vxlan'],
                                          'port_names': ['t1_p:2', 't1_p:2'],
                                          'vlan_tags': [10, 11]})

    def _test_allocate_hosting_port_no_port_found_failure(self, nw_type):
        with self.subnet() as subnet1:
            sn1 = subnet1['subnet']
            ext_net_id = sn1['network_id']
            self._set_net_external(ext_net_id)
            gw_info = {'network_id': ext_net_id}
            with self.router(external_gateway_info=gw_info,
                             tenant_id=sn1['tenant_id']) as router1:
                r1 = router1['router']
                plugging_driver = self.test_driver()
                u_ctx = context.Context('', r1['tenant_id'], is_admin=True)
                gw_port_db = self.core_plugin._get_ports_query(
                        u_ctx, filters={'network_id': [ext_net_id]}).one()
                with mock.patch(
                    'networking_cisco.plugins.cisco.device_manager.'
                    'plugging_drivers.n1kv_ml2_trunking_driver.eventlet.'
                        'sleep') as m1:
                    allocations = plugging_driver.allocate_hosting_port(
                        u_ctx, r1['id'], gw_port_db, nw_type,
                        'non_existant_uuid')
                    self.assertIsNone(allocations)
                    self.assertEqual(10, m1.call_count)

    def test_allocate_hosting_port_vlan_network_no_port_found_failure(self):
        self._test_allocate_hosting_port_no_port_found_failure('vlan')

    def test_allocate_hosting_port_vxlan_network_no_port_found_failure(self):
        self._test_allocate_hosting_port_no_port_found_failure('vxlan')
