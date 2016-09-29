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
from oslo_config import cfg
from oslo_utils import uuidutils

from neutron.common import constants as l3_constants
from neutron.tests import base

from networking_cisco import backwards_compatibility as bc_attr
from networking_cisco.plugins.cisco.cfg_agent import cfg_agent
from networking_cisco.plugins.cisco.cfg_agent.service_helpers import (
    routing_svc_helper as svc_helper)
from networking_cisco.plugins.cisco.cfg_agent.service_helpers import (
    routing_svc_helper_aci as aci_svc_helper)
from networking_cisco.tests.unit.cisco.cfg_agent import (
    test_routing_svc_helper as helper)

_uuid = uuidutils.generate_uuid

TEST_PHYS_IF = 'GigabitEthernet0/1/0'
TEST_VLAN = '3333'
TEST_GW_IP = '4.3.2.1'
TEST_CIDR = '4.3.2.0/24'
TEST_NET1 = 'mynewnet'
TEST_VLAN2 = '4444'
TEST_GW_IP2 = '5.4.3.1'
TEST_CIDR2 = '5.4.3.0/24'
TEST_NET2 = 'myothernet'


def create_hosting_info(vrf=None, net_name=TEST_NET1,
                        vlan=TEST_VLAN, gw_ip=TEST_GW_IP,
                        cidr=TEST_CIDR, if_config=None,
                        global_config=None, snat_subnets=None):
    if vrf is None:
        vrf = _uuid()
    hosting_info = {
        'vrf_id': vrf,
        'physical_interface': TEST_PHYS_IF,
        'network_name': net_name,
        'segmentation_id': vlan,
        'segmentation_id': vlan,
        'gateway_ip': gw_ip,
        'cidr_exposed': cidr,
    }
    if if_config:
        hosting_info['interface_config'] = if_config
    if global_config:
        hosting_info['global_config'] = global_config
    if snat_subnets:
        hosting_info['snat_subnets'] = snat_subnets
    return hosting_info


class TestBasicRoutingOperationsAci(helper.TestBasicRoutingOperations):

    def setUp(self):
        super(TestBasicRoutingOperationsAci, self).setUp()
        self.routing_helper = aci_svc_helper.RoutingServiceHelperAci(
            helper.HOST, self.conf, self.agent)
        self.routing_helper._internal_network_added = mock.Mock()
        self.routing_helper._external_gateway_added = mock.Mock()
        self.routing_helper._internal_network_removed = mock.Mock()
        self.routing_helper._external_gateway_removed = mock.Mock()
        self.routing_helper._enable_router_interface = mock.Mock()
        self.routing_helper._disable_router_interface = mock.Mock()
        self.driver = self._mock_driver_and_hosting_device(
            self.routing_helper)

    def test_process_router(self):
        super(TestBasicRoutingOperationsAci,
              self).test_process_router(test_admin_state=False)

    def test_process_router_2_rids_1_vrf(self):
        driver = self._mock_driver_and_hosting_device(self.routing_helper)
        router1, ports = helper.prepare_router_data()
        ri1 = svc_helper.RouterInfo(router1['id'], router=router1)

        # Router #2 is like #1, except with some different IDs
        router2 = copy.deepcopy(router1)
        router2['id'] = _uuid()
        ri2 = svc_helper.RouterInfo(router2['id'], router=router2)
        h_info1 = create_hosting_info()
        h_info2 = copy.deepcopy(h_info1)
        ri1.router['hosting_info'] = h_info1
        ri2.router['hosting_info'] = h_info2

        driver._get_vrf_name = mock.Mock(
            return_value=ri1.router['hosting_info']['vrf_id'])
        self.routing_helper._process_router(ri1)

        vrf = ri1.router['hosting_info']['vrf_id']
        driver._get_vrf_name.assert_called_with(ri1)
        driver._do_create_vrf.assert_called_with(vrf)
        self.assertEqual(1, len(self.routing_helper._router_ids_by_vrf))
        self.assertEqual(1, len(self.routing_helper._router_ids_by_vrf[vrf]))

        driver._get_vrf_name.reset_mock()
        driver._do_create_vrf.reset_mock()

        self.routing_helper._process_router(ri2)

        driver._get_vrf_name.assert_called_with(ri2)
        driver._do_create_vrf.assert_not_called()
        self.assertEqual(1, len(self.routing_helper._router_ids_by_vrf))
        self.assertEqual(2, len(self.routing_helper._router_ids_by_vrf[vrf]))

        del ri1.router['gw_port']
        driver._get_vrf_name.reset_mock()

        self.routing_helper._process_router(ri1)
        driver._get_vrf_name.assert_called_with(ri1)
        driver._remove_vrf.assert_not_called()
        self.assertEqual(1, len(self.routing_helper._router_ids_by_vrf))
        self.assertEqual(1, len(self.routing_helper._router_ids_by_vrf[vrf]))

        del ri2.router['gw_port']
        driver._get_vrf_name.reset_mock()
        driver._remove_vrf.reset_mock()
        self.routing_helper._process_router(ri2)
        driver._get_vrf_name.assert_called_with(ri2)
        driver._remove_vrf.assert_called_with(ri2)
        self.assertEqual({}, self.routing_helper._router_ids_by_vrf)


def _mock_driver_and_hosting_device(svc_helper):
    svc_helper._dev_status.is_hosting_device_reachable = mock.MagicMock(
        return_value=True)
    driver = mock.MagicMock()
    svc_helper._drivermgr.get_driver = mock.Mock(return_value=driver)
    svc_helper._drivermgr.set_driver = mock.Mock(return_value=driver)
    return driver


class TestNetworkRoutingOperationsAci(base.BaseTestCase):

    def setUp(self):
        super(TestNetworkRoutingOperationsAci, self).setUp()
        self.agent = mock.Mock()
        self.conf = cfg.ConfigOpts()
        self.conf.register_opts(bc_attr.core_opts)
        self.conf.register_opts(cfg_agent.OPTS, "cfg_agent")
        self.l3pluginApi_cls_p = mock.patch(
            'networking_cisco.plugins.cisco.cfg_agent.service_helpers.'
            'routing_svc_helper.CiscoRoutingPluginApi')
        l3plugin_api_cls = self.l3pluginApi_cls_p.start()
        self.plugin_api = mock.Mock()
        l3plugin_api_cls.return_value = self.plugin_api
        self.plugin_api.get_routers = mock.MagicMock()
        self.looping_call_p = mock.patch(
            'oslo_service.loopingcall.FixedIntervalLoopingCall')
        self.looping_call_p.start()
        mock.patch('neutron.common.rpc.create_connection').start()
        self.routing_helper = aci_svc_helper.RoutingServiceHelperAci(
            helper.HOST, self.conf, self.agent)
        self.routing_helper._external_gateway_added = mock.Mock()
        self.routing_helper._external_gateway_removed = mock.Mock()

    def _set_driver_port_mocks(self, driver):
        driver.internal_network_added = mock.Mock()
        driver.internal_network_removed = mock.Mock()
        driver.enable_internal_network_NAT = mock.Mock()
        driver.disable_internal_network_NAT = mock.Mock()

    def test_process_router_2_rids_1_vrf_1_network(self):
        driver = _mock_driver_and_hosting_device(self.routing_helper)
        self._set_driver_port_mocks(driver)

        router1, ports = helper.prepare_router_data()
        ri1 = svc_helper.RouterInfo(router1['id'], router=router1)

        # Router #2 is like #1, except with some different IDs
        router2 = copy.deepcopy(router1)
        router2['id'] = _uuid()
        ri2 = svc_helper.RouterInfo(router2['id'], router=router2)
        h_info1 = create_hosting_info()
        h_info2 = copy.deepcopy(h_info1)
        ri1.router['hosting_info'] = h_info1
        ri2.router['hosting_info'] = h_info2

        ex_gw_port1 = ri1.router.get('gw_port')
        ex_gw_port2 = ri2.router.get('gw_port')
        ex_gw_port1['hosting_info'] = h_info1
        ex_gw_port2['hosting_info'] = h_info2
        vrf = ri1.router['hosting_info']['vrf_id']
        driver._get_vrf_name = mock.Mock(return_value=vrf)
        self.routing_helper._process_router(ri1)

        driver.internal_network_added.assert_called_with(
            ri1, ports[0])
        driver.enable_internal_network_NAT.assert_called_with(
            ri1, ports[0], ex_gw_port1)

        v_n_r_dict = self.routing_helper._router_ids_by_vrf_and_ext_net
        network_name = h_info1['network_name']
        self.assertEqual(1, len(v_n_r_dict))
        self.assertEqual(1, len(v_n_r_dict[vrf]))
        self.assertEqual(1, len(v_n_r_dict[vrf][network_name]))

        driver.internal_network_added.reset_mock()
        driver.enable_internal_network_NAT.reset_mock()

        self.routing_helper._process_router(ri2)
        driver.internal_network_added.assert_called_with(
            ri2, ports[0])
        driver.enable_internal_network_NAT.assert_called_with(
            ri2, ports[0], ex_gw_port2)
        network_name = h_info1['network_name']
        self.assertEqual(1, len(v_n_r_dict))
        self.assertEqual(1, len(v_n_r_dict[vrf]))
        self.assertEqual(2, len(v_n_r_dict[vrf][network_name]))

        del ri1.router[l3_constants.INTERFACE_KEY]
        self.routing_helper._process_router(ri1)

        driver.internal_network_removed.assert_called_with(
            ri1, ports[0], itfc_deleted=False)
        driver.disable_internal_network_NAT.assert_called_with(
            ri1, ports[0], ex_gw_port1, itfc_deleted=False)
        self.assertEqual(1, len(v_n_r_dict))
        self.assertEqual(1, len(v_n_r_dict[vrf]))
        self.assertEqual(1, len(v_n_r_dict[vrf][network_name]))

        driver.internal_network_removed.reset_mock()
        driver.disable_internal_network_NAT.reset_mock()

        del ri2.router[l3_constants.INTERFACE_KEY]
        self.routing_helper._process_router(ri2)

        driver.internal_network_removed.assert_called_with(
            ri2, ports[0], itfc_deleted=True)
        driver.disable_internal_network_NAT.assert_called_with(
            ri2, ports[0], ex_gw_port2, itfc_deleted=True)
        self.assertEqual({}, v_n_r_dict)

    def test_process_router_2_rids_2_vrfs_1_network(self):
        driver = _mock_driver_and_hosting_device(self.routing_helper)
        self._set_driver_port_mocks(driver)

        router1, ports = helper.prepare_router_data()
        ri1 = svc_helper.RouterInfo(router1['id'], router=router1)

        # Router #2 is like #1, except with some different IDs
        router2 = copy.deepcopy(router1)
        router2['id'] = _uuid()
        ri2 = svc_helper.RouterInfo(router2['id'], router=router2)
        h_info1 = create_hosting_info()
        h_info2 = copy.deepcopy(h_info1)
        h_info2['vrf_id'] = _uuid()
        ri1.router['hosting_info'] = h_info1
        ri2.router['hosting_info'] = h_info2

        ex_gw_port1 = ri1.router.get('gw_port')
        ex_gw_port2 = ri2.router.get('gw_port')
        ex_gw_port1['hosting_info'] = h_info1
        ex_gw_port2['hosting_info'] = h_info2
        vrf1 = ri1.router['hosting_info']['vrf_id']
        vrf2 = ri2.router['hosting_info']['vrf_id']
        driver._get_vrf_name = mock.Mock(return_value=vrf1)
        self.routing_helper._process_router(ri1)

        driver.internal_network_added.assert_called_with(
            ri1, ports[0])
        driver.enable_internal_network_NAT.assert_called_with(
            ri1, ports[0], ex_gw_port1)

        v_n_r_dict = self.routing_helper._router_ids_by_vrf_and_ext_net
        network_name = h_info1['network_name']
        self.assertEqual(1, len(v_n_r_dict))
        self.assertEqual(1, len(v_n_r_dict[vrf1]))
        self.assertEqual(1, len(v_n_r_dict[vrf1][network_name]))

        driver.internal_network_added.reset_mock()
        driver.enable_internal_network_NAT.reset_mock()

        driver._get_vrf_name = mock.Mock(return_value=vrf2)
        self.routing_helper._process_router(ri2)
        driver.internal_network_added.assert_called_with(
            ri2, ports[0])
        driver.enable_internal_network_NAT.assert_called_with(
            ri2, ports[0], ex_gw_port2)
        network_name = h_info1['network_name']
        self.assertEqual(2, len(v_n_r_dict))
        self.assertEqual(1, len(v_n_r_dict[vrf1]))
        self.assertEqual(1, len(v_n_r_dict[vrf2]))
        self.assertEqual(1, len(v_n_r_dict[vrf1][network_name]))
        self.assertEqual(1, len(v_n_r_dict[vrf2][network_name]))

        del ri1.router[l3_constants.INTERFACE_KEY]
        driver._get_vrf_name = mock.Mock(return_value=vrf1)
        self.routing_helper._process_router(ri1)

        driver.internal_network_removed.assert_called_with(
            ri1, ports[0], itfc_deleted=True)
        driver.disable_internal_network_NAT.assert_called_with(
            ri1, ports[0], ex_gw_port1, itfc_deleted=True)
        self.assertEqual(1, len(v_n_r_dict))
        self.assertFalse(v_n_r_dict.get(vrf1))
        self.assertEqual(1, len(v_n_r_dict[vrf2]))
        self.assertEqual(1, len(v_n_r_dict[vrf2][network_name]))

        driver.internal_network_removed.reset_mock()
        driver.disable_internal_network_NAT.reset_mock()

        del ri2.router[l3_constants.INTERFACE_KEY]
        driver._get_vrf_name = mock.Mock(return_value=vrf2)
        self.routing_helper._process_router(ri2)

        driver.internal_network_removed.assert_called_with(
            ri2, ports[0], itfc_deleted=True)
        driver.disable_internal_network_NAT.assert_called_with(
            ri2, ports[0], ex_gw_port2, itfc_deleted=True)
        self.assertEqual({}, v_n_r_dict)

    def test_process_router_2_rids_1_vrf_2_networks(self):
        driver = _mock_driver_and_hosting_device(self.routing_helper)
        self._set_driver_port_mocks(driver)

        router1, ports = helper.prepare_router_data()
        ri1 = svc_helper.RouterInfo(router1['id'], router=router1)

        # Router #2 is like #1, except with different IDs and host info
        router2 = copy.deepcopy(router1)
        router2['id'] = _uuid()
        ri2 = svc_helper.RouterInfo(router2['id'], router=router2)
        h_info1 = create_hosting_info()
        h_info2 = create_hosting_info(vrf=h_info1['vrf_id'],
            net_name=TEST_NET2, vlan=TEST_VLAN2, gw_ip=TEST_GW_IP2,
            cidr=TEST_CIDR2)
        ri1.router['hosting_info'] = h_info1
        ri2.router['hosting_info'] = h_info2

        ex_gw_port1 = ri1.router.get('gw_port')
        ex_gw_port2 = ri2.router.get('gw_port')
        ex_gw_port1['hosting_info'] = h_info1
        ex_gw_port2['hosting_info'] = h_info2
        network_name1 = h_info1['network_name']
        network_name2 = h_info2['network_name']
        vrf = ri1.router['hosting_info']['vrf_id']
        driver._get_vrf_name = mock.Mock(return_value=vrf)
        self.routing_helper._process_router(ri1)

        driver.internal_network_added.assert_called_with(
            ri1, ports[0])
        driver.enable_internal_network_NAT.assert_called_with(
            ri1, ports[0], ex_gw_port1)

        v_n_r_dict = self.routing_helper._router_ids_by_vrf_and_ext_net
        self.assertEqual(1, len(v_n_r_dict))
        self.assertEqual(1, len(v_n_r_dict[vrf]))
        self.assertEqual(1, len(v_n_r_dict[vrf][network_name1]))

        driver.internal_network_added.reset_mock()
        driver.enable_internal_network_NAT.reset_mock()

        self.routing_helper._process_router(ri2)
        driver.internal_network_added.assert_called_with(
            ri2, ports[0])
        driver.enable_internal_network_NAT.assert_called_with(
            ri2, ports[0], ex_gw_port2)
        self.assertEqual(1, len(v_n_r_dict))
        self.assertEqual(2, len(v_n_r_dict[vrf]))
        self.assertEqual(1, len(v_n_r_dict[vrf][network_name1]))
        self.assertEqual(1, len(v_n_r_dict[vrf][network_name2]))

        del ri1.router[l3_constants.INTERFACE_KEY]
        self.routing_helper._process_router(ri1)

        driver.internal_network_removed.assert_called_with(
            ri1, ports[0], itfc_deleted=True)
        driver.disable_internal_network_NAT.assert_called_with(
            ri1, ports[0], ex_gw_port1, itfc_deleted=True)
        self.assertEqual(1, len(v_n_r_dict))
        self.assertEqual(1, len(v_n_r_dict[vrf]))
        self.assertFalse(v_n_r_dict[vrf].get(network_name1))
        self.assertEqual(1, len(v_n_r_dict[vrf][network_name2]))

        driver.internal_network_removed.reset_mock()
        driver.disable_internal_network_NAT.reset_mock()

        del ri2.router[l3_constants.INTERFACE_KEY]
        self.routing_helper._process_router(ri2)

        driver.internal_network_removed.assert_called_with(
            ri2, ports[0], itfc_deleted=True)
        driver.disable_internal_network_NAT.assert_called_with(
            ri2, ports[0], ex_gw_port2, itfc_deleted=True)
        self.assertEqual({}, v_n_r_dict)

    def test_process_router_2_rids_2_vrfs_2_networks(self):
        driver = _mock_driver_and_hosting_device(self.routing_helper)
        self._set_driver_port_mocks(driver)

        router1, ports = helper.prepare_router_data()
        ri1 = svc_helper.RouterInfo(router1['id'], router=router1)

        # Router #2 is like #1, except with different IDs and host info
        router2 = copy.deepcopy(router1)
        router2['id'] = _uuid()
        ri2 = svc_helper.RouterInfo(router2['id'], router=router2)
        h_info1 = create_hosting_info()
        h_info2 = create_hosting_info(net_name=TEST_NET2,
            vlan=TEST_VLAN2, gw_ip=TEST_GW_IP2, cidr=TEST_CIDR2)
        ri1.router['hosting_info'] = h_info1
        ri2.router['hosting_info'] = h_info2

        ex_gw_port1 = ri1.router.get('gw_port')
        ex_gw_port2 = ri2.router.get('gw_port')
        ex_gw_port1['hosting_info'] = h_info1
        ex_gw_port2['hosting_info'] = h_info2
        vrf1 = ri1.router['hosting_info']['vrf_id']
        vrf2 = ri2.router['hosting_info']['vrf_id']
        network_name1 = h_info1['network_name']
        network_name2 = h_info2['network_name']
        driver._get_vrf_name = mock.Mock(return_value=vrf1)
        self.routing_helper._process_router(ri1)

        driver.internal_network_added.assert_called_with(
            ri1, ports[0])
        driver.enable_internal_network_NAT.assert_called_with(
            ri1, ports[0], ex_gw_port1)

        v_n_r_dict = self.routing_helper._router_ids_by_vrf_and_ext_net
        self.assertEqual(1, len(v_n_r_dict))
        self.assertEqual(1, len(v_n_r_dict[vrf1]))
        self.assertEqual(1, len(v_n_r_dict[vrf1][network_name1]))

        driver.internal_network_added.reset_mock()
        driver.enable_internal_network_NAT.reset_mock()
        driver._get_vrf_name = mock.Mock(return_value=vrf2)

        self.routing_helper._process_router(ri2)
        driver.internal_network_added.assert_called_with(
            ri2, ports[0])
        driver.enable_internal_network_NAT.assert_called_with(
            ri2, ports[0], ex_gw_port2)
        self.assertEqual(2, len(v_n_r_dict))
        self.assertEqual(1, len(v_n_r_dict[vrf1]))
        self.assertEqual(1, len(v_n_r_dict[vrf2]))
        self.assertEqual(1, len(v_n_r_dict[vrf1][network_name1]))
        self.assertEqual(1, len(v_n_r_dict[vrf2][network_name2]))

        del ri1.router[l3_constants.INTERFACE_KEY]
        driver._get_vrf_name = mock.Mock(return_value=vrf1)
        self.routing_helper._process_router(ri1)

        driver.internal_network_removed.assert_called_with(
            ri1, ports[0], itfc_deleted=True)
        driver.disable_internal_network_NAT.assert_called_with(
            ri1, ports[0], ex_gw_port1, itfc_deleted=True)
        self.assertEqual(1, len(v_n_r_dict))
        self.assertEqual(1, len(v_n_r_dict[vrf2]))
        self.assertFalse(v_n_r_dict.get(vrf1))
        self.assertEqual(1, len(v_n_r_dict[vrf2][network_name2]))

        driver.internal_network_removed.reset_mock()
        driver.disable_internal_network_NAT.reset_mock()

        del ri2.router[l3_constants.INTERFACE_KEY]
        driver._get_vrf_name = mock.Mock(return_value=vrf2)
        self.routing_helper._process_router(ri2)

        driver.internal_network_removed.assert_called_with(
            ri2, ports[0], itfc_deleted=True)
        driver.disable_internal_network_NAT.assert_called_with(
            ri2, ports[0], ex_gw_port2, itfc_deleted=True)
        self.assertEqual({}, v_n_r_dict)
