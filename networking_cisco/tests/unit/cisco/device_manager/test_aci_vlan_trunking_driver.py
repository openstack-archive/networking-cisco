# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
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
from oslo_log import log as logging
from oslo_utils import fileutils
from oslo_utils import uuidutils
import webob.exc

from neutron.common import constants as l3_constants
from neutron.common import test_lib
from neutron import context
from neutron.extensions import providernet as pr_net
from neutron import manager
from neutron.tests.unit.extensions import test_l3

from networking_cisco.plugins.cisco.device_manager.plugging_drivers import (
    aci_vlan_trunking_driver as aci_vlan)

from networking_cisco.plugins.cisco.extensions import routerrole
from networking_cisco.tests.unit.cisco.l3 import (
    test_l3_router_appliance_plugin)

_uuid = uuidutils.generate_uuid
LOG = logging.getLogger(__name__)

ROUTER_ROLE_ATTR = routerrole.ROUTER_ROLE_ATTR

DEVICE = 'mydev'
PORT_ID = 'myportid'
MAC_ADDRESS = '00:11:22:33:44:55'
APP_PROFILE = 'myAppProfile'
SEGMENT_ID = '11'
NETWORK_TYPE = 'opflex'
TENANT = 'mytenent'
HOST = 'ubuntu'
NETWORK_TENANT = 'net_tenant'
EPG_NAME = 'myEpg'
APIC_VLAN1 = 11
APIC_VLAN2 = 12


class FakePortDb(object):

    def __init__(self, id, network_id, device_owner, device_id):
        self.id = id
        self.network_id = network_id
        self.device_id = device_id
        self.device_owner = device_owner
        self.hosting_info = {}
        self.extra_subnets = []

    def get(self, name):
        return self[name]

    def __getitem__(self, key):
        if key == 'id':
            return self.id
        if key == 'network_id':
            return self.network_id
        if key == 'device_owner':
            return self.device_owner
        if key == 'device_id':
            return self.device_id
        if key == 'extra_subnets':
            return self.extra_subnets
        if key == 'hosting_info':
            return self.hosting_info


class TestAciVLANTrunkingPlugDriverBase(
    test_l3_router_appliance_plugin.L3RouterApplianceTestCaseBase,
    test_l3.L3NatTestCaseMixin):
    """Test class for Base ACI VLAN Trunking Plugging driver

    This class tests the functionality of the ACI VLAN Trunking Plugging
    driver, which is indpendent of the workflow used (GBP or Neutron)
    """

    # we use router types defined in .ini file.
    configure_routertypes = False
    router_type = 'ASR1k_Neutron_router'

    def setUp(self):
        super(TestAciVLANTrunkingPlugDriverBase, self).setUp(
            create_mgmt_nw=False)
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
        self.l3_plugin._core_plugin.mechanism_manager = mock.MagicMock()
        plug = aci_vlan.AciVLANTrunkingPlugDriver()
        plug._apic_driver = mock.Mock()
        self.plugging_driver = plug
        self.vlan_dict = {'net1': APIC_VLAN1, 'net2': APIC_VLAN2}

    def tearDown(self):
        if self._old_config_files is None:
            test_lib.test_config.pop('config_files', None)
        else:
            test_lib.test_config['config_files'] = self._old_config_files
        super(TestAciVLANTrunkingPlugDriverBase, self).tearDown()

    def test_create_hosting_device_resources(self):
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        mgmt_context = {'mgmt_nw_id': None}
        res = self.plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 2)
        self.assertIsNone(res['mgmt_port'])
        self.assertEqual(1, len(res))

    def test_create_hosting_device_resources_no_mgmt_context(self):
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        res = self.plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, None, 2)
        self.assertIsNone(res['mgmt_port'], res)
        self.assertEqual(1, len(res))

    def test_get_hosting_device_resources_by_complementary_id(self):
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        mgmt_context = {'mgmt_nw_id': None}
        res = self.plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 1)
        # ports that should not be returned
        with self.port(), self.port(device_id='uuid2'), self.port(
                tenant_id=tenant_id):
            res_get = self.plugging_driver.get_hosting_device_resources(
                ctx, '', 'some_id', tenant_id, None)
            self.assertIsNone(res_get['mgmt_port'])
            self.assertEqual(1, len(res))

    def test_get_hosting_device_resources_by_device_id(self):
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        mgmt_context = {'mgmt_nw_id': None}
        res = self.plugging_driver.create_hosting_device_resources(
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
            res_get = self.plugging_driver.get_hosting_device_resources(
                ctx, hd_uuid, 'some_id', tenant_id, None)
            self.assertIsNone(res_get['mgmt_port'])
            self.assertEqual(1, len(res))

    def test_delete_hosting_device_resources(self):
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        mgmt_context = {'mgmt_nw_id': None}
        res = self.plugging_driver.create_hosting_device_resources(
            ctx, "some_id", tenant_id, mgmt_context, 2)
        nets = self._list('networks')
        self.assertEqual(0, len(nets['networks']))
        subnets = self._list('subnets')
        self.assertEqual(0, len(subnets['subnets']))
        ports = self._list('ports')
        self.assertEqual(0, len(ports['ports']))
        # avoid passing the mgmt port twice in argument list
        mgmt_port = res['mgmt_port']
        del res['mgmt_port']
        self.plugging_driver.delete_hosting_device_resources(
            ctx, tenant_id, mgmt_port, **res)
        nets = self._list('networks')['networks']
        # no networks and subnets should remain
        self.assertEqual(0, len(nets))
        subnets = self._list('subnets')['subnets']
        self.assertEqual(0, len(subnets))
        ports = self._list('ports')
        self.assertEqual(0, len(ports['ports']))

    def test_transit_nets_cfg_invalid_file_format(self):
        self.plugging_driver._cfg_file = fileutils.write_to_tempfile(
            ("""{
                'EDGENAT': {
                    'gateway_ip': '1.109.100.254',
                    'cidr_exposed': '1.109.100.1/24',
                    'segmentation_id': 1066
                }
             }
             {
                'EDGENATBackup': {
                    'gateway_ip': '1.209.200.254',
                    'cidr_exposed': '1.209.200.1/24',
                    'segmentation_id': 1066
                }
             }""").encode('utf-8')
        )
        # TODO(thbachman): couldn't get assertRaises to work here,
        # so used this construct instead
        try:
            # just accessing the member should trigger the exception
            self.plugging_driver.transit_nets_cfg
            self.assertTrue(False)
        except aci_vlan.AciDriverConfigInvalidFileFormat:
            self.assertTrue(True)
        fileutils.delete_if_exists(self.plugging_driver._cfg_file)

    def test_config_sanity_check(self):
        test_config1 = {
            'Datacenter-Out': {
                'cidr_exposed': '1.103.2.0/24'
            }
        }
        test_config2 = {
            'Datacenter-Out': {
                'gateway_ip': '1.103.2.1',
            }
        }
        test_config3 = {
            'Datacenter-Out': {
                'gateway_ip': '1.103.2.254',
                'cidr_exposed': '1.103.2.1/24',
            }
        }
        self.assertRaises(aci_vlan.AciDriverConfigMissingGatewayIp,
                          self.plugging_driver._sanity_check_config,
                          test_config1)
        self.assertRaises(aci_vlan.AciDriverConfigMissingCidrExposed,
                          self.plugging_driver._sanity_check_config,
                          test_config2)
        self.assertTrue(
            test_config3,
            self.plugging_driver._sanity_check_config(test_config3))

    def test_no_driver(self):
        self.plugging_driver._apic_driver = None
        self.l3_plugin._core_plugin.mechanism_manager.mech_drivers = {}
        # TODO(thbachman): couldn't get assertRaises to work here,
        # so used this construct instead
        try:
            self.plugging_driver.apic_driver
            self.assertTrue(False)
        except aci_vlan.AciDriverNoAciDriverInstalledOrConfigured:
            self.assertTrue(True)


class TestAciVLANTrunkingPlugDriverGbp(
    test_l3_router_appliance_plugin.L3RouterApplianceTestCaseBase,
    test_l3.L3NatTestCaseMixin):
    """GBP-specific workflow testing of ACI VLAN driver

    This tests the GBP-specific workflow for the ACI VLAN Trunking
    Plugging driver.
    """

    # we use router types defined in .ini file.
    configure_routertypes = False
    router_type = 'ASR1k_Neutron_router'

    def setUp(self):
        super(TestAciVLANTrunkingPlugDriverGbp, self).setUp(
            create_mgmt_nw=False)
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
        self.mock_gbp_driver = mock.MagicMock()
        self.mock_gbp_plugin = mock.MagicMock()
        self.mock_gbp_plugin.policy_driver_manager.policy_drivers = {
            'apic': self.mock_gbp_driver}
        self._l3_plugins = manager.NeutronManager.get_service_plugins()
        self._l3_plugins['GROUP_POLICY'] = self.mock_gbp_plugin
        self._real_get_plugins = manager.NeutronManager.get_service_plugins
        manager.NeutronManager.get_service_plugins = mock.MagicMock(
            return_value=self._l3_plugins)
        plug = aci_vlan.AciVLANTrunkingPlugDriver()
        plug.apic_driver.gbp_plugin.get_l3p_id_from_router_id = mock.Mock(
            return_value='somerouterid')
        plug.apic_driver.l3out_vlan_alloc.get_vlan_allocated = self._stub_vlan
        self.plugging_driver = plug
        self.vlan_dict = {'net1': APIC_VLAN1,
                          'net2': APIC_VLAN2,
                          'Datacenter-Out': APIC_VLAN2}

    def tearDown(self):
        if self._old_config_files is None:
            test_lib.test_config.pop('config_files', None)
        else:
            test_lib.test_config['config_files'] = self._old_config_files

        manager.NeutronManager.get_service_plugins = self._real_get_plugins
        super(TestAciVLANTrunkingPlugDriverGbp, self).tearDown()

    def _stub_vlan(self, net, vrf, vrf_tenant):
        return self.vlan_dict.get(net)

    def _gen_ext_net_name(self, name):
        return aci_vlan.APIC_OWNED + _uuid() + "-" + name

    def _set_apic_driver_mocks(self, router):
        apic_driver = self.plugging_driver.apic_driver
        apic_driver.gbp_plugin.get_l3p_id_from_router_id = mock.Mock(
            return_value=router['id'])
        apic_driver.get_vrf_details = mock.Mock(
            return_value={'l3_policy_id': router['id']})

    def _verify_vrf(self, vrf_id, router):
        self.assertEqual(router['id'], vrf_id)

    def test_extend_hosting_port_info_adds_segmentation_id_internal(self):
        with self.network(name=self._gen_ext_net_name(
                'Datacenter-Out')) as ext_network:
            ext_net = ext_network['network']
            ext_net_id = ext_net['id']
            self._set_net_external(ext_net_id)
            with self.subnet() as subnet1:
                sn1 = subnet1['subnet']
                gw_info = {'network_id': ext_net_id}
                with self.router(external_gateway_info=gw_info,
                                 tenant_id=sn1['tenant_id']) as router1:
                    r1 = router1['router']
                    hosting_info = {}
                    fake_port_db_obj = FakePortDb('fakeuuid',
                        sn1['network_id'],
                        l3_constants.DEVICE_OWNER_ROUTER_INTF, r1['id'])
                    fake_port_db_obj.hosting_info['segmentation_id'] = 50
                    hosting_device = {'id':
                        '00000000-0000-0000-0000-000000000002'}
                    tenant_id = 'tenant_uuid1'
                    ctx = context.Context('', tenant_id, is_admin=True)
                    self._set_apic_driver_mocks(r1)
                    self.plugging_driver.extend_hosting_port_info(ctx,
                        fake_port_db_obj, hosting_device, hosting_info)
                    self.assertEqual('GigabitEthernet/1/0/1',
                                     hosting_info['physical_interface'])
                    self.assertEqual(50, hosting_info['segmentation_id'])
                    self.assertIsNone(hosting_info.get('vrf_id'))

    def test_extend_hosting_port_info_adds_segmentation_id_external(self):
        with self.network(name=self._gen_ext_net_name(
                'Datacenter-Out')) as ext_network:
            ext_net = ext_network['network']
            ext_net_id = ext_net['id']
            self._set_net_external(ext_net_id)
            with self.subnet(network=ext_network) as subnet1:
                sn1 = subnet1['subnet']
                hosting_info = {}
                gw_info = {'network_id': ext_net_id}
                with self.router(external_gateway_info=gw_info,
                                 tenant_id=sn1['tenant_id']) as router1:
                    r1 = router1['router']
                    fake_port_db_obj = FakePortDb('fakeuuid', ext_net_id,
                        l3_constants.DEVICE_OWNER_ROUTER_GW, r1['id'])
                    fake_port_db_obj.hosting_info['segmentation_id'] = 40
                    hosting_device = {'id':
                        '00000000-0000-0000-0000-000000000002'}
                    tenant_id = 'tenant_uuid1'
                    ctx = context.Context('', tenant_id, is_admin=True)
                    self._set_apic_driver_mocks(r1)
                    self.plugging_driver.extend_hosting_port_info(ctx,
                        fake_port_db_obj, hosting_device, hosting_info)
                    self.assertEqual('GigabitEthernet/2/0/1',
                                     hosting_info['physical_interface'])
                    self.assertEqual(40, hosting_info['segmentation_id'])
                    self._verify_vrf(hosting_info['vrf_id'], r1)

    # Had to create this b/c the helper won't let you set the name
    def _create_subnet_with_name(self, net_id, cidr, name):
        data = {'subnet': {'network_id': net_id,
                           'cidr': cidr,
                           'name': name,
                           'ip_version': 4,
                           'tenant_id': self._tenant_id}}
        subnet_req = self.new_create_request('subnets', data, self.fmt)
        subnet_res = subnet_req.get_response(self.api)
        # Things can go wrong - raise HTTP exc with res code only
        # so it can be caught by unit tests
        if subnet_res.status_int >= webob.exc.HTTPClientError.code:
            raise webob.exc.HTTPClientError(code=subnet_res.status_int)
        return self.deserialize(self.fmt, subnet_res)

    def test_extend_hosting_port_info_adds_snat_subnets(self):
        TEST_NET_NAME = 'Datacenter-Out'
        FAKE_IP = '1.1.1.2'
        FAKE_GW = '1.1.1.1'
        self.plugging_driver.apic_driver.get_snat_ip_for_vrf = mock.Mock(
            return_value={'external_segment_name': TEST_NET_NAME,
                'host_snat_ip': FAKE_IP,
                'gateway_ip': FAKE_GW,
                'prefixlen': 24})
        with self.network(name=self._gen_ext_net_name(
                TEST_NET_NAME)) as network:
            net = network['network']
            subnet = self._create_subnet_with_name(net['id'],
                                                   '10.0.0.0/24',
                                                   aci_vlan.APIC_SNAT_SUBNET)
            sn1 = subnet['subnet']
            ext_net_id = sn1['network_id']
            self._set_net_external(ext_net_id)
            gw_info = {'network_id': ext_net_id}
            with self.router(external_gateway_info=gw_info,
                             tenant_id=sn1['tenant_id']) as router1:
                r1 = router1['router']
                hosting_info = {}
                fake_port_db_obj = FakePortDb('fakeuuid', sn1['network_id'],
                    l3_constants.DEVICE_OWNER_ROUTER_GW, r1['id'])
                fake_port_db_obj.hosting_info['segmentation_id'] = 40
                hosting_device = {'id': '00000000-0000-0000-0000-000000000002'}
                tenant_id = 'tenant_uuid1'
                ctx = context.Context('', tenant_id, is_admin=True)
                self._set_apic_driver_mocks(r1)
                self.plugging_driver.extend_hosting_port_info(ctx,
                    fake_port_db_obj, hosting_device, hosting_info)
                self.assertEqual([{'id': r1['tenant_id'],
                                   'ip': FAKE_IP,
                                   'cidr': sn1['cidr']}],
                                 hosting_info['snat_subnets'])

    def test_extend_hosting_port_info_adds_interface_configuration(self):
        TEST_INFO_CONFIG_LIST = ['testinfo1', 'testinfo2', 'testinfo3']
        self.plugging_driver._default_ext_dict = {
            'gateway_ip': '1.103.2.1',
            'cidr_exposed': '1.103.2.0/24',
            'interface_config': TEST_INFO_CONFIG_LIST
        }
        with self.network(name=self._gen_ext_net_name(
                'Datacenter-Out')) as network1:
            with self.subnet(network=network1) as subnet1:
                sn1 = subnet1['subnet']
                ext_net_id = sn1['network_id']
                self._set_net_external(ext_net_id)
                gw_info = {'network_id': ext_net_id}
                with self.router(external_gateway_info=gw_info,
                                 tenant_id=sn1['tenant_id']) as router1:
                    r1 = router1['router']
                    hosting_info = {}
                    fake_port_db_obj = FakePortDb('fakeuuid',
                        sn1['network_id'],
                        l3_constants.DEVICE_OWNER_ROUTER_INTF,
                        r1['id'])
                    hosting_device = {'id':
                                      '00000000-0000-0000-0000-000000000002'}
                    tenant_id = 'tenant_uuid1'
                    ctx = context.Context('', tenant_id, is_admin=True)
                    self._set_apic_driver_mocks(r1)
                    self.plugging_driver.extend_hosting_port_info(ctx,
                        fake_port_db_obj, hosting_device, hosting_info)

                    self.assertIsNotNone(hosting_info.get('interface_config'))
                    for config in hosting_info['interface_config']:
                        self.assertIn(config, TEST_INFO_CONFIG_LIST)

    def test_extend_hosting_port_info_adds_global_configuration(self):
        TEST_INFO_CONFIG_LIST = ['testinfo1', 'testinfo2', 'testinfo3']
        self.plugging_driver._default_ext_dict = {
            'gateway_ip': '1.103.2.1',
            'cidr_exposed': '1.103.2.0/24',
            'global_config': TEST_INFO_CONFIG_LIST
        }
        dummy_router = {'id': 'someuuid',
                        'tenant_id': 'sometenantid',
                        ROUTER_ROLE_ATTR: None}
        self.plugging_driver.l3_plugin.get_router = mock.Mock(
            return_value=dummy_router)
        with self.network(name=self._gen_ext_net_name(
                'Datacenter-Out')) as network1:
            with self.subnet(network=network1) as subnet1:
                sn1 = subnet1['subnet']
                ext_net_id = sn1['network_id']
                self._set_net_external(ext_net_id)
                hosting_info = {}
                fake_port_db_obj = FakePortDb('fakeuuid',
                    sn1['network_id'],
                    l3_constants.DEVICE_OWNER_ROUTER_GW,
                    dummy_router['id'])
                hosting_device = {'id':
                                  '00000000-0000-0000-0000-000000000002'}
                tenant_id = 'tenant_uuid1'
                ctx = context.Context('', tenant_id, is_admin=True)
                self._set_apic_driver_mocks(dummy_router)
                self.plugging_driver.extend_hosting_port_info(ctx,
                    fake_port_db_obj, hosting_device, hosting_info)

                self.assertIsNotNone(hosting_info.get('global_config'))
                for config in hosting_info['global_config']:
                    self.assertIn(config, TEST_INFO_CONFIG_LIST)

    def _update_provider_net_info(self, res_list, fields):
        for res in res_list:
            pv_info = self._pv_info['vlan'].get(res['id'])
            if pv_info is None:
                pv_info = self._pv_info['vxlan'].get(res['id'])
                if pv_info is None:
                    nw_type = self._network_type
                    if not self._pv_info[nw_type]:
                        tag = {'vlan': 11, 'vxlan': 7000}[nw_type]
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
                for attr in list(res):
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
            self.assertEqual(port_db.id, binding_db.hosting_port_id)
            self.assertEqual(test_info['vlan_tags'][i],
                             binding_db.segmentation_id)
        with self.network(name=self._gen_ext_net_name(
                'Datacenter-Out')) as ext_network:
            ext_net = ext_network['network']
            ext_net_id = ext_net['id']
            self._set_net_external(ext_net_id)
            with self.subnet(network=ext_network) as subnet1:
                sn1 = subnet1['subnet']
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
                    self._set_apic_driver_mocks(r1)
                    with mock.patch.object(self.core_plugin,
                                           'get_network') as m1,\
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
                            test_info1, 0, hd, self.plugging_driver)
                        for i in range(1, len(test_info1['network_types'])):
                            cidr = '1.0.' + str(i) + '.0/24'
                            with self.subnet(cidr=cidr) as subnet2:
                                sn2 = subnet2['subnet']
                                itfc_info = self._router_interface_action(
                                    'add', r1['id'], sn2['id'], None)
                                self._network_type = test_info1[
                                    'network_types'][i]
                                port_db = self.core_plugin._get_port(
                                    u1_ctx, itfc_info['port_id'])
                                _validate_allocation(
                                    self.l3_plugin, u1_ctx, r1,
                                    port_db, test_info1,
                                    i, hd, self.plugging_driver)

    def test_allocate_hosting_port_vlan_network_all_unused(self):
        self._test_allocate_hosting_port({'network_types': ['vlan'],
                                          'vlan_tags': [APIC_VLAN1]})

    def test_allocate_hosting_port_vlan_network_vlan_already_allocated(self):
        self._test_allocate_hosting_port(
            {'network_types': ['vlan', 'vlan'],
             'vlan_tags': [APIC_VLAN1, APIC_VLAN2]})

    def test_allocate_hosting_port_vlan_network_not_found_failure(self):
        with self.network(name=self._gen_ext_net_name(
                'Datacenter-Out')) as ext_network:
            ext_net = ext_network['network']
            ext_net_id = ext_net['id']
            self._set_net_external(ext_net_id)
            with self.subnet() as subnet1:
                sn1 = subnet1['subnet']
                gw_info = {'network_id': ext_net_id}
                with self.router(external_gateway_info=gw_info,
                                 tenant_id=sn1['tenant_id']) as router1:
                    r1 = router1['router']
                    u_ctx = context.Context('', r1['tenant_id'], is_admin=True)
                    gw_port_db = self.core_plugin._get_ports_query(
                            u_ctx, filters={'network_id': [ext_net_id]}).one()
                    self._set_apic_driver_mocks(r1)
                    allocations = self.plugging_driver.allocate_hosting_port(
                        u_ctx, r1['id'], gw_port_db,
                        'vlan', 'non_existant_uuid')
                    self.assertIsNone(allocations)

    def test_allocate_hosting_port_info_adds_segment_id(self):
        self.plugging_driver._default_ext_dict = {
            'gateway_ip': '1.103.2.254',
            'cidr_exposed': '1.103.2.1/24',
            'interface_config': 'testinfo1',
            'segmentation_id': 3003
        }
        with self.network(name=self._gen_ext_net_name(
                'Datacenter-Out')) as network1:
            net1 = network1['network']
            self._set_net_external(net1['id'])
            net1['provider:network_type'] = 'opflex'

            def _return_mocked_net(self, args):
                return net1

            with self.subnet(network=network1) as subnet1:
                sn1 = subnet1['subnet']
                fake_port_db_obj = FakePortDb(
                    'some_dummy_id',
                    sn1['network_id'],
                    l3_constants.DEVICE_OWNER_ROUTER_GW,
                    'dummy_id'
                )
                hosting_device = {'id': '00000000-0000-0000-0000-000000000002'}
                tenant_id = 'tenant_uuid1'
                dummy_rid = 'dummy_router_id'
                ctx = context.Context('', tenant_id, is_admin=True)
                with mock.patch.object(self.core_plugin, 'get_network') as m1:
                    m1.side_effect = _return_mocked_net
                    allocations = self.plugging_driver.allocate_hosting_port(
                        ctx, dummy_rid, fake_port_db_obj,
                        'opflex', hosting_device['id'])
                    self.assertEqual(3003, allocations['allocated_vlan'])

    def test_allocate_hosting_port_info_exception(self):
        self.plugging_driver._default_ext_dict = {
            'gateway_ip': '1.103.2.254',
            'cidr_exposed': '1.103.2.1/24',
            'interface_config': 'testinfo1',
        }
        with self.network(name=self._gen_ext_net_name(
                'Datacenter-Out')) as network1:
            net1 = network1['network']
            self._set_net_external(net1['id'])
            net1['provider:network_type'] = 'opflex'

            def _return_mocked_net(self, args):
                return net1

            with self.subnet(network=network1) as subnet1:
                sn1 = subnet1['subnet']
                fake_port_db_obj = FakePortDb(
                    'some_dummy_id',
                    sn1['network_id'],
                    l3_constants.DEVICE_OWNER_ROUTER_GW,
                    'dummy_id'
                )
                hosting_device = {'id': '00000000-0000-0000-0000-000000000002'}
                tenant_id = 'tenant_uuid1'
                dummy_rid = 'dummy_router_id'
                ctx = context.Context('', tenant_id, is_admin=True)
                with mock.patch.object(self.core_plugin, 'get_network') as m1:
                    m1.side_effect = _return_mocked_net
                    self.assertRaises(
                        aci_vlan.AciDriverConfigMissingSegmentationId,
                        self.plugging_driver.allocate_hosting_port,
                        ctx, dummy_rid, fake_port_db_obj,
                        'opflex', hosting_device['id'])


class TestAciVLANTrunkingPlugDriverNeutron(TestAciVLANTrunkingPlugDriverGbp):
    """Neutron-specific workflow testing of ACI VLAN driver

    This tests the Neutron-specific workflow for the ACI VLAN Trunking
    Plugging driver.
    """

    # we use router types defined in .ini file.
    configure_routertypes = False
    router_type = 'ASR1k_Neutron_router'

    def setUp(self):
        super(TestAciVLANTrunkingPlugDriverGbp, self).setUp(
            create_mgmt_nw=False)
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
        self.l3_plugin._core_plugin.mechanism_manager = mock.MagicMock()
        plug = aci_vlan.AciVLANTrunkingPlugDriver()
        plug.apic_driver.l3out_vlan_alloc.get_vlan_allocated = self._stub_vlan
        plug.apic_driver.per_tenant_context = True
        self.plugging_driver = plug
        self.vlan_dict = {'net1': APIC_VLAN1,
                          'net2': APIC_VLAN2,
                          'Datacenter-Out': APIC_VLAN2}

    def tearDown(self):
        if self._old_config_files is None:
            test_lib.test_config.pop('config_files', None)
        else:
            test_lib.test_config['config_files'] = self._old_config_files

        super(TestAciVLANTrunkingPlugDriverGbp, self).tearDown()

    def _gen_ext_net_name(self, name):
        return name

    def _set_apic_driver_mocks(self, router):
        apic_driver = self.plugging_driver.apic_driver
        apic_driver.get_router_vrf_and_tenant = mock.Mock(
            return_value={'aci_name': router['id'],
                          'aci_tenant': router['tenant_id']})

    def _verify_vrf(self, vrf_id, router):
        if self.plugging_driver.apic_driver.per_tenant_context:
            self.assertEqual(router['tenant_id'], vrf_id)
        else:
            self.assertEqual(router['id'], vrf_id)

    def test_extend_hosting_port_info_adds_snat_subnets(self):
        TEST_NET_NAME = 'Datacenter-Out'
        FAKE_IP = '1.1.1.2'
        FAKE_GW = '1.1.1.1'
        self.plugging_driver.apic_driver.get_snat_ip_for_vrf = mock.Mock(
            return_value={'external_segment_name': TEST_NET_NAME,
                'host_snat_ip': FAKE_IP,
                'gateway_ip': FAKE_GW,
                'prefixlen': 24})
        with self.network(name=self._gen_ext_net_name(
                TEST_NET_NAME)) as network:
            ext_net = network['network']
            ext_net_id = ext_net['id']
            self._set_net_external(ext_net_id)
            with self.network(name=(aci_vlan.APIC_SNAT_NET + '-' +
                                    ext_net_id)) as snat_net:
                net = snat_net['network']
                subnet = self._create_subnet_with_name(
                    net['id'], '10.0.0.0/24', aci_vlan.APIC_SNAT_SUBNET)
                sn1 = subnet['subnet']
                gw_info = {'network_id': ext_net_id}
                with self.router(external_gateway_info=gw_info,
                                 tenant_id=sn1['tenant_id']) as router1:
                    r1 = router1['router']
                    hosting_info = {}
                    fake_port_db_obj = FakePortDb('fakeuuid', ext_net_id,
                        l3_constants.DEVICE_OWNER_ROUTER_GW, r1['id'])
                    fake_port_db_obj.hosting_info['segmentation_id'] = 40
                    hosting_device = {'id':
                                      '00000000-0000-0000-0000-000000000002'}
                    tenant_id = 'tenant_uuid1'
                    ctx = context.Context('', tenant_id, is_admin=True)
                    self._set_apic_driver_mocks(r1)
                    self.plugging_driver.extend_hosting_port_info(ctx,
                        fake_port_db_obj, hosting_device, hosting_info)
                    self.assertEqual([{'id': r1['tenant_id'],
                                       'ip': FAKE_IP,
                                       'cidr': sn1['cidr']}],
                                     hosting_info['snat_subnets'])

    def test_extend_hosting_port_info_no_snat_subnets_1(self):
        TEST_NET_NAME = 'Datacenter-Out'
        FAKE_IP = '1.1.1.2'
        FAKE_GW = '1.1.1.1'
        self.plugging_driver.apic_driver.get_snat_ip_for_vrf = mock.Mock(
            return_value={'external_segment_name': TEST_NET_NAME,
                'host_snat_ip': FAKE_IP,
                'gateway_ip': FAKE_GW,
                'prefixlen': 24})
        with self.network(name=self._gen_ext_net_name(
                TEST_NET_NAME)) as network:
            ext_net = network['network']
            ext_net_id = ext_net['id']
            self._set_net_external(ext_net_id)
            with self.network() as snat_net:
                net = snat_net['network']
                subnet = self._create_subnet_with_name(
                    net['id'], '10.0.0.0/24', aci_vlan.APIC_SNAT_SUBNET)
                sn1 = subnet['subnet']
                gw_info = {'network_id': ext_net_id}
                with self.router(external_gateway_info=gw_info,
                                 tenant_id=sn1['tenant_id']) as router1:
                    r1 = router1['router']
                    hosting_info = {}
                    fake_port_db_obj = FakePortDb('fakeuuid', ext_net_id,
                        l3_constants.DEVICE_OWNER_ROUTER_GW, r1['id'])
                    fake_port_db_obj.hosting_info['segmentation_id'] = 40
                    hosting_device = {'id':
                                      '00000000-0000-0000-0000-000000000002'}
                    tenant_id = 'tenant_uuid1'
                    ctx = context.Context('', tenant_id, is_admin=True)
                    self._set_apic_driver_mocks(r1)
                    self.plugging_driver.extend_hosting_port_info(ctx,
                        fake_port_db_obj, hosting_device, hosting_info)
                    self.assertEqual([], hosting_info['snat_subnets'])

    def test_extend_hosting_port_info_no_snat_subnets_2(self):
        TEST_NET_NAME = 'Datacenter-Out'
        FAKE_IP = '1.1.1.2'
        FAKE_GW = '1.1.1.1'
        self.plugging_driver.apic_driver.get_snat_ip_for_vrf = mock.Mock(
            return_value={'external_segment_name': TEST_NET_NAME,
                'host_snat_ip': FAKE_IP,
                'gateway_ip': FAKE_GW,
                'prefixlen': 24})
        with self.network(name=self._gen_ext_net_name(
                TEST_NET_NAME)) as ext_network:
            ext_net = ext_network['network']
            ext_net_id = ext_net['id']
            self._set_net_external(ext_net_id)
            with self.subnet(network=ext_network) as subnet1:
                sn1 = subnet1['subnet']
                gw_info = {'network_id': ext_net_id}
                with self.router(external_gateway_info=gw_info,
                                 tenant_id=sn1['tenant_id']) as router1:
                    r1 = router1['router']
                    hosting_info = {}
                    fake_port_db_obj = FakePortDb('fakeuuid', ext_net_id,
                        l3_constants.DEVICE_OWNER_ROUTER_GW, r1['id'])
                    fake_port_db_obj.hosting_info['segmentation_id'] = 40
                    hosting_device = {'id':
                        '00000000-0000-0000-0000-000000000002'}
                    tenant_id = 'tenant_uuid1'
                    ctx = context.Context('', tenant_id, is_admin=True)
                    self._set_apic_driver_mocks(r1)
                    self.plugging_driver.extend_hosting_port_info(ctx,
                        fake_port_db_obj, hosting_device, hosting_info)
                    self.assertIsNone(hosting_info.get('snat_subnets'))

    def test_extend_hosting_port_adds_segmentation_id_external_1_vrf(self):
        self.plugging_driver.apic_driver.per_tenant_context = False
        with self.network(name=self._gen_ext_net_name(
                'Datacenter-Out')) as ext_network:
            ext_net = ext_network['network']
            ext_net_id = ext_net['id']
            self._set_net_external(ext_net_id)
            with self.subnet(network=ext_network) as subnet1:
                sn1 = subnet1['subnet']
                hosting_info = {}
                gw_info = {'network_id': ext_net_id}
                with self.router(external_gateway_info=gw_info,
                                 tenant_id=sn1['tenant_id']) as router1:
                    r1 = router1['router']
                    fake_port_db_obj = FakePortDb('fakeuuid', ext_net_id,
                        l3_constants.DEVICE_OWNER_ROUTER_GW, r1['id'])
                    fake_port_db_obj.hosting_info['segmentation_id'] = 40
                    hosting_device = {'id':
                        '00000000-0000-0000-0000-000000000002'}
                    tenant_id = 'tenant_uuid1'
                    ctx = context.Context('', tenant_id, is_admin=True)
                    self._set_apic_driver_mocks(r1)
                    self.plugging_driver.extend_hosting_port_info(ctx,
                        fake_port_db_obj, hosting_device, hosting_info)
                    self.assertEqual('GigabitEthernet/2/0/1',
                                     hosting_info['physical_interface'])
                    self.assertEqual(40, hosting_info['segmentation_id'])
                    self._verify_vrf(hosting_info['vrf_id'], r1)

    def test_external_net_name(self):
        self.assertIsNotNone(self.plugging_driver.get_ext_net_name)

    def test_external_net_no_gw(self):
        class DummyPort(object):

            def __init__(self, router_id):
                self.device_id = router_id
                self.device_owner = None

        drv = self.plugging_driver
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        with self.router() as router1:
            r1 = router1['router']
            dummy_port = DummyPort(r1['id'])
            net_dict, net = drv._get_external_network_dict(ctx, dummy_port)
            self.assertIsNone(net)
            self.assertEqual({}, net_dict)

    def test_allocate_hosting_port_no_router(self):
        drv = self.plugging_driver
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        with self.port() as port1:
            p1 = port1['port']
            self.assertIsNone(drv.allocate_hosting_port(ctx,
                None, p1, None, None))

    def test_allocate_hosting_port_router_no_gw(self):
        drv = self.plugging_driver
        tenant_id = 'some_tenant_id'
        ctx = context.Context('', tenant_id, is_admin=True)
        with self.port() as port1:
            p1 = port1['port']
            with self.router() as router1:
                r1 = router1['router']
                p1['device_owner'] = l3_constants.DEVICE_OWNER_ROUTER_INTF
                self.assertIsNone(drv.allocate_hosting_port(ctx,
                    r1['id'], p1, None, None))
