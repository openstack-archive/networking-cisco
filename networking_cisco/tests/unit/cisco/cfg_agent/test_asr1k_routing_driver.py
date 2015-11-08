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
import sys

import mock
import netaddr
from oslo_config import cfg
from oslo_utils import uuidutils

from neutron.common import constants as l3_constants
from neutron.tests import base

from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_routing_driver as driver)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_snippets as snippets)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.csr1kv import (
    cisco_csr1kv_snippets as csr_snippets)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.csr1kv import (
    iosxe_routing_driver as iosxe_driver)
from networking_cisco.plugins.cisco.cfg_agent.service_helpers import (
    routing_svc_helper)
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.extensions import routerrole

sys.modules['ncclient'] = mock.MagicMock()
sys.modules['ciscoconfparse'] = mock.MagicMock()

_uuid = uuidutils.generate_uuid
FAKE_ID = _uuid()
PORT_ID = _uuid()


class ASR1kRoutingDriver(base.BaseTestCase):
    def setUp(self):
        super(ASR1kRoutingDriver, self).setUp()

        device_params = {'management_ip_address': 'fake_ip',
                         'protocol_port': 22,
                         'credentials': {"user_name": "stack",
                                         "password": "cisco"},
                         'timeout': None,
                         'id': '0000-1',
                         'device_id': 'ASR-1'
                         }
        self.driver = driver.ASR1kRoutingDriver(**device_params)
        self.driver._ncc_connection = mock.MagicMock()
        self.driver._check_response = mock.MagicMock(return_value=True)

        self.vrf = ('nrouter-' + FAKE_ID)[:iosxe_driver.IosXeRoutingDriver.
                                          DEV_NAME_LEN]
        self.driver._get_vrfs = mock.Mock(return_value=[self.vrf])
        self.ex_gw_ip_vip = '20.0.0.31'
        self.ex_gw_ip = '20.0.0.33'
        self.ex_gw_prefixlen = 24
        self.ex_gw_cidr = '20.0.0.30/24'
        self.ex_gw_ip_mask = '255.255.255.0'
        self.ex_gw_vlan = 1000
        self.ex_gw_gateway_ip = '20.0.0.1'
        self.phy_infc = 'GigabitEthernet0/0/0'
        self.vlan_ext = 317
        self.vlan_int = 314
        self.hosting_info = {'physical_interface': self.phy_infc,
                             'segmentation_id': 317}
        self.gw_ip_cidr = '10.0.3.0/24'
        self.gw_ip = '10.0.3.3'
        self.gw_ip_vip = '10.0.3.1'
        self.gw_ip_mask = '255.255.255.0'
        self.ha_group = 1621
        self.ha_info = {'group': self.ha_group,
                        'ha_port':
                            {'fixed_ips': [{'ip_address': self.gw_ip_vip}]}
                        }
        self.port = {'id': PORT_ID,
                     'ip_cidr': self.gw_ip_cidr,
                     'fixed_ips': [{'ip_address': self.gw_ip}],
                     'subnets': [{'cidr': self.gw_ip_cidr,
                                  'gateway_ip': self.gw_ip}],
                     'hosting_info': {
                         'physical_interface': self.phy_infc,
                         'segmentation_id': self.vlan_int},
                     'ha_info': self.ha_info
                     }
        int_ports = [self.port]
        self.ex_gw_port = {'id': _uuid(),
                           'network_id': _uuid(),
                           'fixed_ips': [{'ip_address': self.ex_gw_ip,
                                          'prefixlen': self.ex_gw_prefixlen,
                                          'subnet_id': _uuid()}],
                           'subnets': [{'cidr': self.ex_gw_cidr,
                                        'gateway_ip': self.ex_gw_gateway_ip}],
                           'device_owner': l3_constants.DEVICE_OWNER_ROUTER_GW,
                           'mac_address': 'ca:fe:de:ad:be:ef',
                           'hosting_info':
                               {'physical_interface': self.phy_infc,
                                'segmentation_id': self.vlan_ext},
                           'ha_info': self.ha_info}
        self.floating_ip = '20.0.0.35'
        self.fixed_ip = '10.0.3.5'
        self.ha_priority = 10
        self.cisco_ha_details = {'priority': self.ha_priority,
                                 'redundancy_level': 1,
                                 'redundancy_routers': [
                                     {'id': _uuid(),
                                      'priority': 20,
                                      'state': 'STANDBY'}],
                                 'state': 'ACTIVE',
                                 'type': 'HSRP'}
        self.router = {
            'id': FAKE_ID,
            l3_constants.INTERFACE_KEY: int_ports,
            'enable_snat': True,
            'routes': [],
            routerrole.ROUTER_ROLE_ATTR: 'Logical',
            'cisco_ha:details': self.cisco_ha_details,
            'gw_port': self.ex_gw_port}

        self.ri = routing_svc_helper.RouterInfo(FAKE_ID, self.router)
        self.ri.internal_ports = int_ports
        # Global router
        self.global_router = copy.deepcopy(self.router)
        self.global_router[routerrole.ROUTER_ROLE_ATTR] = (
            cisco_constants.ROUTER_ROLE_GLOBAL)
        self.global_router['gw_port']['ha_info']['ha_port']['fixed_ips'][0][
            'ip_address'] = self.ex_gw_ip_vip
        self.ri_global = routing_svc_helper.RouterInfo(
            FAKE_ID, self.global_router)
        self.ri_global.internal_ports = int_ports

    def tearDown(self):
        super(ASR1kRoutingDriver, self).tearDown()
        self.driver._ncc_connection.reset_mock()

    def assert_edit_run_cfg(self, snippet_name, args):
        if args:
            confstr = snippet_name % args
        else:
            confstr = snippet_name
        self.driver._ncc_connection.edit_config.assert_any_call(
            target='running', config=confstr)

    def _assert_number_of_edit_run_cfg_calls(self, num):
        self.assertEqual(num,
                         self.driver._ncc_connection.edit_config.call_count)

    def _generate_hsrp_cfg_args(self, subintfc, group, priority, vip, vlan):
        return (subintfc,
                group, priority,
                group, vip,
                group,
                group, group, vlan)

    def test_internal_network_added(self):
        self.driver.internal_network_added(self.ri, self.port)

        sub_interface = self.phy_infc + '.' + str(self.vlan_int)
        cfg_args_sub = (sub_interface, self.vlan_int, self.vrf,
                        self.gw_ip, self.gw_ip_mask)
        self.assert_edit_run_cfg(
            snippets.CREATE_SUBINTERFACE_WITH_ID, cfg_args_sub)

        cfg_args_hsrp = self._generate_hsrp_cfg_args(
            sub_interface, self.ha_group, self.ha_priority, self.gw_ip_vip,
            self.vlan_int)
        self.assert_edit_run_cfg(
            snippets.SET_INTC_ASR_HSRP_EXTERNAL, cfg_args_hsrp)

    def test_internal_network_added_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)

        region_id = cfg.CONF.multi_region.region_id

        vrf = self.vrf + "-" + region_id

        self.driver.internal_network_added(self.ri, self.port)

        sub_interface = self.phy_infc + '.' + str(self.vlan_int)
        cfg_args_sub = (sub_interface, region_id, self.vlan_int, vrf,
                        self.gw_ip, self.gw_ip_mask)
        self.assert_edit_run_cfg(
            snippets.CREATE_SUBINTERFACE_REGION_ID_WITH_ID, cfg_args_sub)

        cfg_args_hsrp = self._generate_hsrp_cfg_args(
            sub_interface, self.ha_group, self.ha_priority, self.gw_ip_vip,
            self.vlan_int)
        self.assert_edit_run_cfg(
            snippets.SET_INTC_ASR_HSRP_EXTERNAL, cfg_args_hsrp)

        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

    def test_internal_network_added_global_router(self):
        self.driver.internal_network_added(self.ri_global, self.port)
        sub_interface = self.phy_infc + '.' + str(self.vlan_int)
        cfg_args_sub = (sub_interface, self.vlan_int,
                        self.gw_ip, self.gw_ip_mask)
        self.assert_edit_run_cfg(
            snippets.CREATE_SUBINTERFACE_EXTERNAL_WITH_ID, cfg_args_sub)

        cfg_args_hsrp = self._generate_hsrp_cfg_args(
            sub_interface, self.ha_group, self.ha_priority, self.gw_ip_vip,
            self.vlan_int)
        self.assert_edit_run_cfg(
            snippets.SET_INTC_ASR_HSRP_EXTERNAL, cfg_args_hsrp)

    def test_internal_network_added_global_router_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id

        self.driver.internal_network_added(self.ri_global, self.port)
        sub_interface = self.phy_infc + '.' + str(self.vlan_int)
        cfg_args_sub = (sub_interface, region_id, self.vlan_int,
                        self.gw_ip, self.gw_ip_mask)
        self.assert_edit_run_cfg(
            snippets.CREATE_SUBINTERFACE_EXT_REGION_ID_WITH_ID, cfg_args_sub)

        cfg_args_hsrp = self._generate_hsrp_cfg_args(
            sub_interface, self.ha_group, self.ha_priority, self.gw_ip_vip,
            self.vlan_int)
        self.assert_edit_run_cfg(
            snippets.SET_INTC_ASR_HSRP_EXTERNAL, cfg_args_hsrp)
        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

    def test_external_network_added(self):
        self.driver.external_gateway_added(self.ri, self.ex_gw_port)

        sub_interface = self.phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(csr_snippets.ENABLE_INTF, sub_interface)

        cfg_params_nat = (self.vrf + '_nat_pool', self.ex_gw_ip,
                          self.ex_gw_ip, self.ex_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.CREATE_NAT_POOL, cfg_params_nat)

    def test_external_network_added_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.external_gateway_added(self.ri, self.ex_gw_port)

        sub_interface = self.phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(csr_snippets.ENABLE_INTF, sub_interface)

        cfg_params_nat = (vrf + '_nat_pool', self.ex_gw_ip,
                          self.ex_gw_ip, self.ex_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.CREATE_NAT_POOL, cfg_params_nat)
        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

    def test_external_gateway_removed(self):
        self.driver.external_gateway_removed(self.ri, self.ex_gw_port)

        cfg_params_nat = (self.vrf + '_nat_pool', self.ex_gw_ip,
                          self.ex_gw_ip, self.ex_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.DELETE_NAT_POOL, cfg_params_nat)

        sub_interface = self.phy_infc + '.' + str(self.vlan_ext)
        cfg_params_remove_route = (self.vrf,
                                   sub_interface, self.ex_gw_gateway_ip)
        self.assert_edit_run_cfg(snippets.REMOVE_DEFAULT_ROUTE_WITH_INTF,
                                 cfg_params_remove_route)

    def test_external_gateway_removed_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.external_gateway_removed(self.ri, self.ex_gw_port)

        cfg_params_nat = (vrf + '_nat_pool', self.ex_gw_ip,
                          self.ex_gw_ip, self.ex_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.DELETE_NAT_POOL, cfg_params_nat)

        sub_interface = self.phy_infc + '.' + str(self.vlan_ext)
        cfg_params_remove_route = (vrf,
                                   sub_interface, self.ex_gw_gateway_ip)
        self.assert_edit_run_cfg(snippets.REMOVE_DEFAULT_ROUTE_WITH_INTF,
                                 cfg_params_remove_route)
        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

    def test_external_gateway_removed_global_router(self):
        self.driver._interface_exists = mock.MagicMock(return_value=True)

        self.driver.external_gateway_removed(self.ri_global, self.ex_gw_port)

        sub_interface = self.phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(
            csr_snippets.REMOVE_SUBINTERFACE, sub_interface)

    def test_floating_ip_added(self):
        self.driver.floating_ip_added(self.ri, self.ex_gw_port,
                                      self.floating_ip, self.fixed_ip)

        self._assert_number_of_edit_run_cfg_calls(1)
        cfg_params_floating = (self.fixed_ip, self.floating_ip, self.vrf,
                               self.ha_group, self.vlan_ext)
        self.assert_edit_run_cfg(snippets.SET_STATIC_SRC_TRL_NO_VRF_MATCH,
                                 cfg_params_floating)

    def test_floating_ip_added_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.floating_ip_added(self.ri, self.ex_gw_port,
                                      self.floating_ip, self.fixed_ip)

        self._assert_number_of_edit_run_cfg_calls(1)
        cfg_params_floating = (self.fixed_ip, self.floating_ip, vrf,
                               self.ha_group, self.vlan_ext)
        self.assert_edit_run_cfg(snippets.SET_STATIC_SRC_TRL_NO_VRF_MATCH,
                                 cfg_params_floating)
        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

    def test_floating_ip_removed(self):
        self.driver.floating_ip_removed(self.ri, self.ex_gw_port,
                                      self.floating_ip, self.fixed_ip)

        self._assert_number_of_edit_run_cfg_calls(1)
        cfg_params_floating = (self.fixed_ip, self.floating_ip, self.vrf,
                               self.ha_group, self.vlan_ext)
        self.assert_edit_run_cfg(snippets.REMOVE_STATIC_SRC_TRL_NO_VRF_MATCH,
                                 cfg_params_floating)

    def test_floating_ip_removed_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.floating_ip_removed(self.ri, self.ex_gw_port,
                                      self.floating_ip, self.fixed_ip)

        self._assert_number_of_edit_run_cfg_calls(1)
        cfg_params_floating = (self.fixed_ip, self.floating_ip, vrf,
                               self.ha_group, self.vlan_ext)
        self.assert_edit_run_cfg(snippets.REMOVE_STATIC_SRC_TRL_NO_VRF_MATCH,
                                 cfg_params_floating)
        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

    def test_driver_enable_internal_network_NAT(self):
        self.driver.enable_internal_network_NAT(self.ri,
                                                self.port, self.ex_gw_port)

        self._assert_number_of_edit_run_cfg_calls(4)

        acl_name = '%s_%s' % ('neutron_acl', str(self.vlan_int))
        net = netaddr.IPNetwork(self.gw_ip_cidr).network
        net_mask = netaddr.IPNetwork(self.gw_ip_cidr).hostmask
        cfg_params_create_acl = (acl_name, net, net_mask)
        self.assert_edit_run_cfg(
            csr_snippets.CREATE_ACL, cfg_params_create_acl)

        pool_name = "%s_nat_pool" % self.vrf
        cfg_params_dyn_trans = (acl_name, pool_name, self.vrf)
        self.assert_edit_run_cfg(
            snippets.SET_DYN_SRC_TRL_POOL, cfg_params_dyn_trans)

        sub_interface_int = self.phy_infc + '.' + str(self.vlan_int)
        sub_interface_ext = self.phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(csr_snippets.SET_NAT,
                                 (sub_interface_int, 'inside'))
        self.assert_edit_run_cfg(csr_snippets.SET_NAT,
                                 (sub_interface_ext, 'outside'))

    def test_driver_enable_internal_network_NAT_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.enable_internal_network_NAT(self.ri,
                                                self.port, self.ex_gw_port)

        self._assert_number_of_edit_run_cfg_calls(4)

        acl_name = '%s_%s_%s' % ('neutron_acl', region_id, str(self.vlan_int))
        net = netaddr.IPNetwork(self.gw_ip_cidr).network
        net_mask = netaddr.IPNetwork(self.gw_ip_cidr).hostmask
        cfg_params_create_acl = (acl_name, net, net_mask)
        self.assert_edit_run_cfg(
            csr_snippets.CREATE_ACL, cfg_params_create_acl)

        pool_name = "%s_nat_pool" % vrf
        cfg_params_dyn_trans = (acl_name, pool_name, vrf)
        self.assert_edit_run_cfg(
            snippets.SET_DYN_SRC_TRL_POOL, cfg_params_dyn_trans)

        sub_interface_int = self.phy_infc + '.' + str(self.vlan_int)
        sub_interface_ext = self.phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(csr_snippets.SET_NAT,
                                 (sub_interface_int, 'inside'))
        self.assert_edit_run_cfg(csr_snippets.SET_NAT,
                                 (sub_interface_ext, 'outside'))
        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

    def test_driver_disable_internal_network_NAT(self):
        self.driver.disable_internal_network_NAT(self.ri,
                                                 self.port, self.ex_gw_port)

        self._assert_number_of_edit_run_cfg_calls(3)

        acl_name = '%s_%s' % ('neutron_acl', str(self.vlan_int))
        pool_name = "%s_nat_pool" % self.vrf

        cfg_params_dyn_trans = (acl_name, pool_name, self.vrf)
        self.assert_edit_run_cfg(
            snippets.REMOVE_DYN_SRC_TRL_POOL, cfg_params_dyn_trans)

        self.assert_edit_run_cfg(csr_snippets.REMOVE_ACL, acl_name)

    def test_driver_disable_internal_network_NAT_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.disable_internal_network_NAT(self.ri,
                                                 self.port, self.ex_gw_port)

        self._assert_number_of_edit_run_cfg_calls(3)

        acl_name = '%s_%s_%s' % ('neutron_acl', region_id, str(self.vlan_int))
        pool_name = "%s_nat_pool" % vrf

        cfg_params_dyn_trans = (acl_name, pool_name, vrf)
        self.assert_edit_run_cfg(
            snippets.REMOVE_DYN_SRC_TRL_POOL, cfg_params_dyn_trans)

        self.assert_edit_run_cfg(csr_snippets.REMOVE_ACL, acl_name)
        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

    def test_get_configuration(self):
        self.driver._get_running_config = mock.MagicMock()
        self.driver.get_configuration()
        self.driver._get_running_config.assert_called_once_with(split=False)
