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
from neutron.tests.unit.extensions import test_l3

from neutron_lib import constants as l3_constants

from networking_cisco.plugins.cisco.device_manager.plugging_drivers.\
    hw_vlan_trunking_driver import HwVLANTrunkingPlugDriver
from networking_cisco.tests.unit.cisco.l3 import (
    test_l3_router_appliance_plugin)


class TestHwVLANTrunkingPlugDriver(
    test_l3_router_appliance_plugin.L3RouterApplianceTestCaseBase,
    test_l3.L3NatTestCaseMixin):

    # we use router types defined in .ini file.
    configure_routertypes = False
    router_type = 'ASR1k_Neutron_router'

    def setUp(self):
        super(TestHwVLANTrunkingPlugDriver, self).setUp(create_mgmt_nw=False)
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

    def tearDown(self):
        if self._old_config_files is None:
            test_lib.test_config.pop('config_files', None)
        else:
            test_lib.test_config['config_files'] = self._old_config_files
        super(TestHwVLANTrunkingPlugDriver, self).tearDown()

    def test_create_hosting_device_resources(self):
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = HwVLANTrunkingPlugDriver()
        mgmt_context = {'mgmt_nw_id': None}
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 2)
        self.assertIsNone(res['mgmt_port'])
        self.assertEqual(len(res), 1)

    def test_create_hosting_device_resources_no_mgmt_context(self):
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = HwVLANTrunkingPlugDriver()
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, None, 2)
        self.assertIsNone(res['mgmt_port'], res)
        self.assertEqual(len(res), 1)

    def test_get_hosting_device_resources_by_complementary_id(self):
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = HwVLANTrunkingPlugDriver()
        mgmt_context = {'mgmt_nw_id': None}
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 1)
        # ports that should not be returned
        with self.port(), self.port(device_id='uuid2'), self.port(
                tenant_id=tenant_id):
            res_get = plugging_driver.get_hosting_device_resources(
                ctx, '', 'some_id', tenant_id, None)
            self.assertIsNone(res_get['mgmt_port'])
            self.assertEqual(len(res), 1)

    def test_get_hosting_device_resources_by_device_id(self):
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = HwVLANTrunkingPlugDriver()
        mgmt_context = {'mgmt_nw_id': None}
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
                ctx, hd_uuid, 'some_id', tenant_id, None)
            self.assertIsNone(res_get['mgmt_port'])
            self.assertEqual(len(res), 1)

    def test_delete_hosting_device_resources(self):
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        mgmt_context = {'mgmt_nw_id': None}
        plugging_driver = HwVLANTrunkingPlugDriver()
        res = plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 2)
        nets = self._list('networks')
        self.assertEqual(len(nets['networks']), 0)
        subnets = self._list('subnets')
        self.assertEqual(len(subnets['subnets']), 0)
        ports = self._list('ports')
        self.assertEqual(len(ports['ports']), 0)
        # avoid passing the mgmt port twice in argument list
        mgmt_port = res['mgmt_port']
        del res['mgmt_port']
        plugging_driver.delete_hosting_device_resources(
            ctx, tenant_id, mgmt_port, **res)
        nets = self._list('networks')['networks']
        # no networks and subnets should remain
        self.assertEqual(len(nets), 0)
        subnets = self._list('subnets')['subnets']
        self.assertEqual(len(subnets), 0)
        ports = self._list('ports')
        self.assertEqual(len(ports['ports']), 0)

    def test_extend_hosting_port_info_adds_segmentation_id_internal(self):
        hosting_info = {}
        fake_port_db_obj = mock.MagicMock()
        fake_port_db_obj.hosting_info = mock.MagicMock()
        fake_port_db_obj.hosting_info.segmentation_id = 50
        fake_port_db_obj.device_owner = l3_constants.DEVICE_OWNER_ROUTER_INTF
        hosting_device = {'id': '00000000-0000-0000-0000-000000000002'}
        tenant_id = 'tenant_uuid1'
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = HwVLANTrunkingPlugDriver()
        plugging_driver.extend_hosting_port_info(ctx, fake_port_db_obj,
                                                 hosting_device, hosting_info)
        self.assertEqual(hosting_info['physical_interface'],
                         'GigabitEthernet/1/0/1')
        self.assertEqual(hosting_info['segmentation_id'], 50)

    def test_extend_hosting_port_info_adds_segmentation_id_external(self):
        hosting_info = {}
        fake_port_db_obj = mock.MagicMock()
        fake_port_db_obj.hosting_info = mock.MagicMock()
        fake_port_db_obj.hosting_info.segmentation_id = 40
        fake_port_db_obj.device_owner = l3_constants.DEVICE_OWNER_ROUTER_GW
        hosting_device = {'id': '00000000-0000-0000-0000-000000000002'}
        tenant_id = 'tenant_uuid1'
        ctx = context.Context('', tenant_id, is_admin=True)
        plugging_driver = HwVLANTrunkingPlugDriver()
        plugging_driver.extend_hosting_port_info(ctx, fake_port_db_obj,
                                                 hosting_device, hosting_info)
        self.assertEqual(hosting_info['physical_interface'],
                         'GigabitEthernet/2/0/1')
        self.assertEqual(hosting_info['segmentation_id'], 40)

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

    def _test_allocate_hosting_port(self, test_info1):

        def _validate_allocation(plugin, ctx, r, port_db, test_info,
                                 i, hd, plugging_driver):
            binding_db = plugin._allocate_hosting_port(
                ctx, r['id'], port_db, hd['id'], plugging_driver)
            self.assertIsNotNone(binding_db.hosting_port_id)
            self.assertEqual(binding_db.hosting_port_id,
                             port_db.id)
            self.assertEqual(binding_db.segmentation_id,
                             test_info['vlan_tags'][i])

        plugging_driver = HwVLANTrunkingPlugDriver()
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
                        test_info1, 0, hd, plugging_driver)
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
                                test_info1, i, hd, plugging_driver)

    def test_allocate_hosting_port_vlan_network_all_unused(self):
        self._test_allocate_hosting_port({'network_types': ['vlan'],
                                          'vlan_tags': [50]})

    def test_allocate_hosting_port_vlan_network_vlan_already_allocated(self):
        self._test_allocate_hosting_port({'network_types': ['vlan', 'vlan'],
                                          'vlan_tags': [50, 51]})

    def test_allocate_hosting_port_vlan_network_not_found_failure(self):
        with self.subnet() as subnet1:
            sn1 = subnet1['subnet']
            ext_net_id = sn1['network_id']
            self._set_net_external(ext_net_id)
            gw_info = {'network_id': ext_net_id}
            with self.router(external_gateway_info=gw_info,
                             tenant_id=sn1['tenant_id']) as router1:
                r1 = router1['router']
                plugging_driver = HwVLANTrunkingPlugDriver()
                u_ctx = context.Context('', r1['tenant_id'], is_admin=True)
                gw_port_db = self.core_plugin._get_ports_query(
                        u_ctx, filters={'network_id': [ext_net_id]}).one()
                allocations = plugging_driver.allocate_hosting_port(
                    u_ctx, r1['id'], gw_port_db, 'vlan', 'non_existant_uuid')
                self.assertIsNone(allocations)
