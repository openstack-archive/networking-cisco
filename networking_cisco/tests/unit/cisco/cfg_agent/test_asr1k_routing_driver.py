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

import sys

import mock
import netaddr
from oslo_config import cfg
from oslo_utils import uuidutils

from neutron.tests import base

from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_routing_driver as driver)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_snippets as snippets)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.iosxe import (
    cisco_iosxe_snippets as iosxe_snippets)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.iosxe import (
    iosxe_routing_driver as iosxe_driver)
from networking_cisco.plugins.cisco.cfg_agent.service_helpers import (
    routing_svc_helper)
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routerrole
from networking_cisco.tests.unit.cisco.cfg_agent import cfg_agent_test_support

sys.modules['ncclient'] = mock.MagicMock()

_uuid = uuidutils.generate_uuid
DEV_NAME_LEN = iosxe_driver.IosXeRoutingDriver.DEV_NAME_LEN
HA_INFO = 'ha_info'
ROUTER_ROLE_ATTR = routerrole.ROUTER_ROLE_ATTR
ROUTER_ROLE_HA_REDUNDANCY = cisco_constants.ROUTER_ROLE_HA_REDUNDANCY


class ASR1kRoutingDriver(base.BaseTestCase,
                         cfg_agent_test_support.CfgAgentTestSupportMixin):

    def setUp(self):
        super(ASR1kRoutingDriver, self).setUp()

        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

        device_params = self.prepare_hosting_device_params()
        self.driver = driver.ASR1kRoutingDriver(**device_params)
        self.driver._ncc_connection = mock.MagicMock()
        self.driver._check_response = mock.MagicMock(return_value=True)
        self.driver._check_acl = mock.MagicMock(return_value=False)

    def tearDown(self):
        super(ASR1kRoutingDriver, self).tearDown()
        self.driver._ncc_connection.reset_mock()

    def _create_test_routers(self, is_user_visible=True):
        self.router, ports = self.prepare_router_data(
            is_user_visible=is_user_visible)
        self.ri = routing_svc_helper.RouterInfo(self.router['id'],
                                                self.router)
        self.ha_priority = self.router[ha.DETAILS][ha.PRIORITY]
        self.vrf = ('nrouter-' + self.router['id'])[:DEV_NAME_LEN]

        # router port on external network, i.e., gateway port
        self.ext_gw_port = self.router['gw_port']
        self.ext_gw_port['ip_info'] = {
            'subnet_id': self.ext_gw_port['subnets'][0]['id'],
            'is_primary': True,
            'ip_cidr': self.ext_gw_port['subnets'][0]['cidr']
        }
        self.ext_phy_infc = (
            self.ext_gw_port['hosting_info']['physical_interface'])
        self.vlan_ext = self.ext_gw_port['hosting_info']['segmentation_id']
        self.ext_gw_upstream_ip = self.ext_gw_port['subnets'][0]['gateway_ip']
        self.ext_gw_ip = self.ext_gw_port['fixed_ips'][0]['ip_address']
        self.ext_gw_ip_cidr = self.ext_gw_port['subnets'][0]['cidr']
        self.ext_gw_ip_mask = str(
            netaddr.IPNetwork(self.ext_gw_ip_cidr).netmask)
        port_ha_info = self.ext_gw_port['ha_info']
        self.ext_gw_ha_group = port_ha_info['group']

        # router port on internal network
        self.int_port = ports[0]
        self.int_port['ip_info'] = {
            'subnet_id': self.int_port['subnets'][0]['id'],
            'is_primary': True,
            'ip_cidr': self.int_port['subnets'][0]['cidr']
        }
        self.int_port['change_details'] = {
            'new_ports': [self.int_port],
            'current_ports': [self.int_port],
            'old_ports': [],
            'former_ports': []
        }
        self.int_phy_infc = self.int_port['hosting_info']['physical_interface']
        self.vlan_int = self.int_port['hosting_info']['segmentation_id']
        self.int_gw_ip = self.int_port['fixed_ips'][0]['ip_address']
        self.int_gw_ip_cidr = self.int_port['subnets'][0]['cidr']
        self.int_gw_ip_mask = str(
            netaddr.IPNetwork(self.int_gw_ip_cidr).netmask)
        port_ha_info = self.int_port['ha_info']
        self.int_gw_ip_vip = (
            port_ha_info['ha_port']['fixed_ips'][0]['ip_address'])
        self.int_gw_ha_group = port_ha_info['group']
        self.floating_ip = '19.4.0.6'
        self.fixed_ip = '35.4.0.20'

    def _create_test_global_routers(self, num_ext_subnets=1, subnet_index=0):
        # global router and its ports
        self.global_router, gl_ports = self.prepare_router_data(
            is_global=True, num_ext_subnets=num_ext_subnets)
        self.ha_priority = self.global_router[ha.DETAILS][ha.PRIORITY]
        self.ri_global = routing_svc_helper.RouterInfo(
            self.global_router['id'], self.global_router)
        self.gl_port = gl_ports[0]
        self.gl_port['ip_info'] = {
            'subnet_id': self.gl_port['subnets'][0]['id'],
            'is_primary': True,
            'ip_cidr': self.gl_port['subnets'][0]['cidr']
        }
        self.ext_phy_infc = self.gl_port['hosting_info']['physical_interface']
        self.vlan_ext = self.gl_port['hosting_info']['segmentation_id']
        self.gl_port_ip = self.gl_port['fixed_ips'][subnet_index]['ip_address']
        self.gl_port_ip_cidr = self.gl_port['subnets'][subnet_index]['cidr']
        self.gl_port_ip_mask = str(
            netaddr.IPNetwork(self.gl_port_ip_cidr).netmask)
        port_ha_info = self.gl_port['ha_info']
        self.gl_port_vip = (
            port_ha_info['ha_port']['fixed_ips'][subnet_index]['ip_address'])
        self.gl_port_ha_group = port_ha_info['group']

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
        self._create_test_routers()
        self.driver.internal_network_added(self.ri, self.int_port)

        sub_interface = self.int_phy_infc + '.' + str(self.vlan_int)
        cfg_args_sub = (sub_interface, self.vlan_int, self.vrf, self.int_gw_ip,
                        self.int_gw_ip_mask)
        self.assert_edit_run_cfg(
            snippets.CREATE_SUBINTERFACE_WITH_ID, cfg_args_sub)

        cfg_args_hsrp = self._generate_hsrp_cfg_args(
            sub_interface, self.int_gw_ha_group, self.ha_priority,
            self.int_gw_ip_vip, self.vlan_int)
        self.assert_edit_run_cfg(
            snippets.SET_INTC_ASR_HSRP_EXTERNAL, cfg_args_hsrp)

    def test_internal_network_added_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        self._create_test_routers()
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)

        region_id = cfg.CONF.multi_region.region_id

        vrf = self.vrf + "-" + region_id

        self.driver.internal_network_added(self.ri, self.int_port)

        sub_interface = self.int_phy_infc + '.' + str(self.vlan_int)
        cfg_args_sub = (sub_interface, region_id, self.vlan_int, vrf,
                        self.int_gw_ip, self.int_gw_ip_mask)
        self.assert_edit_run_cfg(
            snippets.CREATE_SUBINTERFACE_REGION_ID_WITH_ID, cfg_args_sub)

        cfg_args_hsrp = self._generate_hsrp_cfg_args(
            sub_interface, self.int_gw_ha_group, self.ha_priority,
            self.int_gw_ip_vip, self.vlan_int)
        self.assert_edit_run_cfg(
            snippets.SET_INTC_ASR_HSRP_EXTERNAL, cfg_args_hsrp)

    def test_internal_network_added_global_router(self):
        self._create_test_global_routers()
        self.driver.internal_network_added(self.ri_global, self.gl_port)
        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        cfg_args_sub = (sub_interface, self.vlan_ext,
                        self.gl_port_ip, self.gl_port_ip_mask)
        self.assert_edit_run_cfg(
            snippets.CREATE_SUBINTERFACE_EXTERNAL_WITH_ID, cfg_args_sub)

        cfg_args_hsrp = self._generate_hsrp_cfg_args(
            sub_interface, self.gl_port_ha_group, self.ha_priority,
            self.gl_port_vip, self.vlan_ext)
        self.assert_edit_run_cfg(
            snippets.SET_INTC_ASR_HSRP_EXTERNAL, cfg_args_hsrp)

    def test_internal_network_added_global_router_secondary_subnet(self):
        self._create_test_global_routers(num_ext_subnets=2, subnet_index=1)
        self.gl_port['ip_info']['subnet_id'] = self.gl_port['subnets'][1]['id']
        self.gl_port['ip_info']['ip_cidr'] = self.gl_port['subnets'][1]['cidr']
        self.gl_port['ip_info']['is_primary'] = False

        self.driver.internal_network_added(self.ri_global, self.gl_port)
        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        cfg_args_sub = (sub_interface, self.gl_port_ip, self.gl_port_ip_mask)
        self.assert_edit_run_cfg(
            snippets.SET_INTERFACE_SECONDARY_IP, cfg_args_sub)

        cfg_args_hsrp = (sub_interface, self.gl_port_ha_group,
                         self.gl_port_vip)
        self.assert_edit_run_cfg(
            snippets.SET_INTC_ASR_SECONDARY_HSRP_EXTERNAL, cfg_args_hsrp)

    def test_internal_network_added_global_router_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        self._create_test_global_routers()
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id

        self.driver.internal_network_added(self.ri_global, self.gl_port)
        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        cfg_args_sub = (sub_interface, region_id, self.vlan_ext,
                        self.gl_port_ip, self.gl_port_ip_mask)
        self.assert_edit_run_cfg(
            snippets.CREATE_SUBINTERFACE_EXT_REGION_ID_WITH_ID, cfg_args_sub)

        cfg_args_hsrp = self._generate_hsrp_cfg_args(
            sub_interface, self.gl_port_ha_group, self.ha_priority,
            self.gl_port_vip, self.vlan_ext)
        self.assert_edit_run_cfg(
            snippets.SET_INTC_ASR_HSRP_EXTERNAL, cfg_args_hsrp)

    def test_internal_network_added_global_router_with_multi_region_sec_sn(
            self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        self._create_test_global_routers(num_ext_subnets=2, subnet_index=1)
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)

        self.gl_port['ip_info']['subnet_id'] = self.gl_port['subnets'][1]['id']
        self.gl_port['ip_info']['ip_cidr'] = self.gl_port['subnets'][1]['cidr']
        self.gl_port['ip_info']['is_primary'] = False
        self.driver.internal_network_added(self.ri_global, self.gl_port)
        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        cfg_args_sub = (sub_interface, self.gl_port_ip, self.gl_port_ip_mask)
        self.assert_edit_run_cfg(
            snippets.SET_INTERFACE_SECONDARY_IP, cfg_args_sub)

        cfg_args_hsrp = (sub_interface, self.gl_port_ha_group,
                         self.gl_port_vip)
        self.assert_edit_run_cfg(
            snippets.SET_INTC_ASR_SECONDARY_HSRP_EXTERNAL, cfg_args_hsrp)

    def _make_test_router_non_ha(self):
        self._create_test_routers()
        self.ri.router[ha.ENABLED] = False
        del self.ri.router[ha.DETAILS]
        del self.ext_gw_port[HA_INFO]
        del self.int_port[HA_INFO]

    def test_external_network_added_non_ha(self):
        self._make_test_router_non_ha()
        self.driver.external_gateway_added(self.ri, self.ext_gw_port)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(iosxe_snippets.ENABLE_INTF, sub_interface)

        cfg_params_nat = (self.vrf + '_nat_pool', self.ext_gw_ip,
                          self.ext_gw_ip, self.ext_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.CREATE_NAT_POOL, cfg_params_nat)

    def test_external_network_added_user_visible_router(self):
        self._create_test_routers()
        self.driver.external_gateway_added(self.ri, self.ext_gw_port)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(iosxe_snippets.ENABLE_INTF, sub_interface)

        cfg_params_nat = (self.vrf + '_nat_pool', self.ext_gw_ip,
                          self.ext_gw_ip, self.ext_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.CREATE_NAT_POOL, cfg_params_nat)

    def test_external_network_added_redundancy_router(self):
        self._create_test_routers(is_user_visible=False)
        self.driver.external_gateway_added(self.ri, self.ext_gw_port)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(iosxe_snippets.ENABLE_INTF, sub_interface)

        cfg_params_nat = (self.vrf + '_nat_pool', self.ext_gw_ip,
                          self.ext_gw_ip, self.ext_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.CREATE_NAT_POOL, cfg_params_nat)

    def test_external_network_added_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        self._create_test_routers()
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.external_gateway_added(self.ri, self.ext_gw_port)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(iosxe_snippets.ENABLE_INTF, sub_interface)

        cfg_params_nat = (vrf + '_nat_pool', self.ext_gw_ip,
                          self.ext_gw_ip, self.ext_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.CREATE_NAT_POOL, cfg_params_nat)

    def test_external_gateway_removed_non_ha(self):
        self._make_test_router_non_ha()
        self.driver.external_gateway_removed(self.ri, self.ext_gw_port)

        cfg_params_nat = (self.vrf + '_nat_pool', self.ext_gw_ip,
                          self.ext_gw_ip, self.ext_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.DELETE_NAT_POOL, cfg_params_nat)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        cfg_params_remove_route = (self.vrf,
                                   sub_interface, self.ext_gw_upstream_ip)
        self.assert_edit_run_cfg(snippets.REMOVE_DEFAULT_ROUTE_WITH_INTF,
                                 cfg_params_remove_route)

    def test_external_gateway_removed_user_visible_router(self):
        self._create_test_routers()
        self.driver.external_gateway_removed(self.ri, self.ext_gw_port)

        cfg_params_nat = (self.vrf + '_nat_pool', self.ext_gw_ip,
                          self.ext_gw_ip, self.ext_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.DELETE_NAT_POOL, cfg_params_nat)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        cfg_params_remove_route = (self.vrf,
                                   sub_interface, self.ext_gw_upstream_ip)
        self.assert_edit_run_cfg(snippets.REMOVE_DEFAULT_ROUTE_WITH_INTF,
                                 cfg_params_remove_route)

    def test_external_gateway_removed_redundancy_router(self):
        self._create_test_routers(is_user_visible=False)
        self.driver.external_gateway_removed(self.ri, self.ext_gw_port)

        cfg_params_nat = (self.vrf + '_nat_pool', self.ext_gw_ip,
                          self.ext_gw_ip, self.ext_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.DELETE_NAT_POOL, cfg_params_nat)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        cfg_params_remove_route = (self.vrf,
                                   sub_interface, self.ext_gw_upstream_ip)
        self.assert_edit_run_cfg(snippets.REMOVE_DEFAULT_ROUTE_WITH_INTF,
                                 cfg_params_remove_route)

    def test_external_gateway_removed_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        self._create_test_routers()
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.external_gateway_removed(self.ri, self.ext_gw_port)

        cfg_params_nat = (vrf + '_nat_pool', self.ext_gw_ip,
                          self.ext_gw_ip, self.ext_gw_ip_mask)
        self.assert_edit_run_cfg(snippets.DELETE_NAT_POOL, cfg_params_nat)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        cfg_params_remove_route = (vrf,
                                   sub_interface, self.ext_gw_upstream_ip)
        self.assert_edit_run_cfg(snippets.REMOVE_DEFAULT_ROUTE_WITH_INTF,
                                 cfg_params_remove_route)

    def test_external_gateway_removed_global_router(self):
        self._create_test_global_routers()
        self.driver._interface_exists = mock.MagicMock(return_value=True)

        self.driver.external_gateway_removed(self.ri_global, self.gl_port)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(
            iosxe_snippets.REMOVE_SUBINTERFACE, sub_interface)

    def test_floating_ip_added(self):
        self._create_test_routers()
        self.driver.floating_ip_added(self.ri, self.ext_gw_port,
                                      self.floating_ip, self.fixed_ip)

        self._assert_number_of_edit_run_cfg_calls(1)
        cfg_params_floating = (self.fixed_ip, self.floating_ip, self.vrf,
                               self.ext_gw_ha_group, self.vlan_ext)
        self.assert_edit_run_cfg(snippets.SET_STATIC_SRC_TRL_NO_VRF_MATCH,
                                 cfg_params_floating)

    def test_floating_ip_added_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        self._create_test_routers()
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.floating_ip_added(self.ri, self.ext_gw_port,
                                      self.floating_ip, self.fixed_ip)

        self._assert_number_of_edit_run_cfg_calls(1)
        cfg_params_floating = (self.fixed_ip, self.floating_ip, vrf,
                               self.ext_gw_ha_group, self.vlan_ext)
        self.assert_edit_run_cfg(snippets.SET_STATIC_SRC_TRL_NO_VRF_MATCH,
                                 cfg_params_floating)

    def test_floating_ip_removed(self):
        self._create_test_routers()
        self.driver.floating_ip_removed(self.ri, self.ext_gw_port,
                                        self.floating_ip, self.fixed_ip)

        self._assert_number_of_edit_run_cfg_calls(1)
        cfg_params_floating = (self.fixed_ip, self.floating_ip, self.vrf,
                               self.ext_gw_ha_group, self.vlan_ext)
        self.assert_edit_run_cfg(snippets.REMOVE_STATIC_SRC_TRL_NO_VRF_MATCH,
                                 cfg_params_floating)

    def test_floating_ip_removed_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        self._create_test_routers()
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.floating_ip_removed(self.ri, self.ext_gw_port,
                                      self.floating_ip, self.fixed_ip)

        self._assert_number_of_edit_run_cfg_calls(1)
        cfg_params_floating = (self.fixed_ip, self.floating_ip, vrf,
                               self.ext_gw_ha_group, self.vlan_ext)
        self.assert_edit_run_cfg(snippets.REMOVE_STATIC_SRC_TRL_NO_VRF_MATCH,
                                 cfg_params_floating)

    def test_driver_enable_internal_network_NAT(self):
        self._create_test_routers()
        self.driver.enable_internal_network_NAT(self.ri, self.int_port,
                                                self.ext_gw_port)

        self._assert_number_of_edit_run_cfg_calls(4)

        acl_name = '%(acl_prefix)s_%(vlan)s_%(port)s' % {
                   'acl_prefix': 'neutron_acl',
                   'vlan': self.vlan_int,
                   'port': self.int_port['id'][:8]}
        net = netaddr.IPNetwork(self.int_gw_ip_cidr).network
        net_mask = netaddr.IPNetwork(self.int_gw_ip_cidr).hostmask
        cfg_params_create_acl = (acl_name, net, net_mask)
        self.assert_edit_run_cfg(
            iosxe_snippets.CREATE_ACL, cfg_params_create_acl)

        pool_name = "%s_nat_pool" % self.vrf
        cfg_params_dyn_trans = (acl_name, pool_name, self.vrf)
        self.assert_edit_run_cfg(
            snippets.SET_DYN_SRC_TRL_POOL, cfg_params_dyn_trans)

        sub_interface_int = self.int_phy_infc + '.' + str(self.vlan_int)
        sub_interface_ext = self.int_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(iosxe_snippets.SET_NAT,
                                 (sub_interface_int, 'inside'))
        self.assert_edit_run_cfg(iosxe_snippets.SET_NAT,
                                 (sub_interface_ext, 'outside'))

    def test_driver_enable_internal_network_NAT_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        self._create_test_routers()
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.enable_internal_network_NAT(self.ri, self.int_port,
                                                self.ext_gw_port)

        self._assert_number_of_edit_run_cfg_calls(4)

        acl_name = '%(acl_prefix)s_%(region_id)s_%(vlan)s_%(port)s' % {
                   'acl_prefix': 'neutron_acl',
                   'region_id': region_id,
                   'vlan': self.vlan_int,
                   'port': self.int_port['id'][:8]}

        net = netaddr.IPNetwork(self.int_gw_ip_cidr).network
        net_mask = netaddr.IPNetwork(self.int_gw_ip_cidr).hostmask
        cfg_params_create_acl = (acl_name, net, net_mask)
        self.assert_edit_run_cfg(
            iosxe_snippets.CREATE_ACL, cfg_params_create_acl)

        pool_name = "%s_nat_pool" % vrf
        cfg_params_dyn_trans = (acl_name, pool_name, vrf)
        self.assert_edit_run_cfg(
            snippets.SET_DYN_SRC_TRL_POOL, cfg_params_dyn_trans)

        sub_interface_int = self.int_phy_infc + '.' + str(self.vlan_int)
        sub_interface_ext = self.int_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(iosxe_snippets.SET_NAT,
                                 (sub_interface_int, 'inside'))
        self.assert_edit_run_cfg(iosxe_snippets.SET_NAT,
                                 (sub_interface_ext, 'outside'))

    def test_driver_disable_internal_network_NAT(self):
        self._create_test_routers()
        self.driver.disable_internal_network_NAT(self.ri, self.int_port,
                                                 self.ext_gw_port)

        self._assert_number_of_edit_run_cfg_calls(3)

        acl_name = '%(acl_prefix)s_%(vlan)s_%(port)s' % {
                   'acl_prefix': 'neutron_acl',
                   'vlan': self.vlan_int,
                   'port': self.int_port['id'][:8]}
        pool_name = "%s_nat_pool" % self.vrf

        cfg_params_dyn_trans = (acl_name, pool_name, self.vrf)
        self.assert_edit_run_cfg(
            snippets.REMOVE_DYN_SRC_TRL_POOL, cfg_params_dyn_trans)

        self.assert_edit_run_cfg(iosxe_snippets.REMOVE_ACL, acl_name)

    def test_driver_disable_internal_network_NAT_with_multi_region(self):
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        self._create_test_routers()
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        self.assertEqual(True, is_multi_region_enabled)
        region_id = cfg.CONF.multi_region.region_id
        vrf = self.vrf + "-" + region_id

        self.driver.disable_internal_network_NAT(self.ri, self.int_port,
                                                 self.ext_gw_port)

        self._assert_number_of_edit_run_cfg_calls(3)

        acl_name = '%(acl_prefix)s_%(region_id)s_%(vlan)s_%(port)s' % {
                   'acl_prefix': 'neutron_acl',
                   'region_id': region_id,
                   'vlan': self.vlan_int,
                   'port': self.int_port['id'][:8]}

        pool_name = "%s_nat_pool" % vrf

        cfg_params_dyn_trans = (acl_name, pool_name, vrf)
        self.assert_edit_run_cfg(
            snippets.REMOVE_DYN_SRC_TRL_POOL, cfg_params_dyn_trans)

        self.assert_edit_run_cfg(iosxe_snippets.REMOVE_ACL, acl_name)

    def test_enable_interface_user_visible_router(self):
        self._create_test_routers()
        self.driver.enable_router_interface(self.ri, self.ext_gw_port)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(iosxe_snippets.ENABLE_INTF, sub_interface)

    def test_enable_interface_redundancy_router(self):
        self._create_test_routers(is_user_visible=False)
        self.driver.enable_router_interface(self.ri, self.ext_gw_port)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(iosxe_snippets.ENABLE_INTF, sub_interface)

    def test_disable_interface_user_visible_router(self):
        self._create_test_routers()
        self.driver.disable_router_interface(self.ri, self.ext_gw_port)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(iosxe_snippets.DISABLE_INTF, sub_interface)

    def test_disable_interface_redundancy_router(self):
        self._create_test_routers(is_user_visible=False)
        self.driver.disable_router_interface(self.ri, self.ext_gw_port)

        sub_interface = self.ext_phy_infc + '.' + str(self.vlan_ext)
        self.assert_edit_run_cfg(iosxe_snippets.DISABLE_INTF, sub_interface)

    def test_get_configuration(self):
        self._create_test_routers()
        self.driver._get_running_config = mock.MagicMock()
        self.driver.get_configuration()
        self.driver._get_running_config.assert_called_once_with(split=False)
