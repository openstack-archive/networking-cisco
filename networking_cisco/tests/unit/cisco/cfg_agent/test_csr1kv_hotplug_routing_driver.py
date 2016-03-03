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

import mock
import netaddr
import sys

from oslo_utils import uuidutils

from networking_cisco.plugins.cisco.cfg_agent.device_drivers.csr1kv import (
    cisco_csr1kv_snippets as snippets)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.csr1kv import (
    csr1kv_hotplug_routing_driver as csr_driver)

from networking_cisco.tests.unit.cisco.cfg_agent import (
    test_csr1kv_routing_driver)

sys.modules['ncclient'] = mock.MagicMock()

_uuid = uuidutils.generate_uuid
FAKE_ID = _uuid()
PORT_ID = _uuid()


class TestCSR1kvHotplug(test_csr1kv_routing_driver.TestCSR1kvRouting):
    def setUp(self):
        super(TestCSR1kvHotplug, self).setUp()

        device_params = {'management_ip_address': 'fake_ip',
                         'protocol_port': 22,
                         'credentials': {"user_name": "stack",
                                         "password": "cisco"},
                         'timeout': None
                         }

        # set to the hotplug driver
        self.driver = csr_driver.CSR1kvHotPlugRoutingDriver(
            **device_params)
        self.driver._csr_conn = self.mock_conn
        self.driver._check_response = mock.MagicMock(return_value=True)
        self.driver._get_vrfs = mock.Mock(return_value=[self.vrf])

        # add and update some variables for the hotplug driver
        self.interface = 'GigabitEthernet0'
        self.mac = 'be:ef:de:ad:be:ef'
        self.ex_gw_mac = 'ca:fe:de:ad:be:ef'
        self.ex_gw_int = 'GigabitEthernet1'
        self.hosting_port_name = 'hostingport_12345'
        self.port['mac_address'] = self.mac
        self.port['hosting_info']['hosting_mac'] = self.mac
        self.port['hosting_info']['hosting_port_name'] = self.hosting_port_name
        self.ex_gw_netmask = netaddr.IPNetwork(self.ex_gw_cidr).netmask
        self.ex_gw_port['hosting_info']['hosting_mac'] = self.ex_gw_mac
        ret_VNIC = {netaddr.EUI(self.mac): self.interface,
                    netaddr.EUI(self.ex_gw_mac): self.ex_gw_int}
        self.driver._get_VNIC_mapping = mock.MagicMock(return_value=ret_VNIC)

    def test_internal_network_added(self):
        self.driver._configure_interface_mac = mock.MagicMock()
        self.driver._configure_interface = mock.MagicMock()

        self.driver.internal_network_added(self.ri, self.port)

        self.driver._configure_interface_mac.assert_called_with(self.interface,
                                                                self.mac)
        self.driver._configure_interface.assert_called_with(self.interface,
            self.vrf, self.gw_ip, netaddr.IPNetwork(self.gw_ip_cidr).netmask)

    def test_internal_network_removed(self):
        self.driver._csr_deconfigure_interface = mock.MagicMock()

        self.driver.internal_network_removed(self.ri, self.port)

        self.driver._csr_deconfigure_interface.called_with(self.interface)

    def test_external_gateway_added(self):
        self.driver._configure_interface_mac = mock.MagicMock()
        self.driver._configure_interface = mock.MagicMock()
        self.driver._add_default_static_route = mock.MagicMock()

        self.driver.external_gateway_added(self.ri, self.ex_gw_port)

        self.driver._configure_interface_mac.assert_called_with(self.ex_gw_int,
                                                                self.ex_gw_mac)
        self.driver._configure_interface.assert_called_with(self.ex_gw_int,
                                                            self.vrf,
                                                            self.ex_gw_ip,
                                                            self.ex_gw_netmask)
        self.driver._add_default_static_route.assert_called_once_with(
            self.ex_gw_gateway_ip, self.vrf)

    def test_external_gateway_removed(self):
        self.driver._csr_deconfigure_interface = mock.MagicMock()
        self.driver._remove_default_static_route = mock.MagicMock()

        self.driver.external_gateway_removed(self.ri, self.ex_gw_port)

        self.driver._remove_default_static_route.assert_called_once_with(
            self.ex_gw_gateway_ip, self.vrf)
        self.driver._csr_deconfigure_interface.called_with(self.interface)

    def test_enable_internal_network_NAT(self):
        self.driver._nat_rules_for_internet_access = mock.MagicMock()
        int_interface = 'GigabitEthernet0'
        ext_interface = 'GigabitEthernet1'
        args = (('acl_' + self.hosting_port_name.lstrip("hostingport_")),
                netaddr.IPNetwork(self.gw_ip_cidr).network,
                netaddr.IPNetwork(self.gw_ip_cidr).hostmask,
                int_interface,
                ext_interface,
                self.vrf,
                self.ex_gw_ip)

        self.driver.enable_internal_network_NAT(self.ri, self.port,
                                                self.ex_gw_port)

        self.driver._nat_rules_for_internet_access.assert_called_once_with(
            *args)

    def test_enable_internal_network_NAT_with_confstring(self):
        self.driver._csr_conn.reset_mock()
        self.driver._check_acl = mock.Mock(return_value=False)
        int_interface = 'GigabitEthernet0'
        ext_interface = 'GigabitEthernet1'
        acl_no = ('acl_' + self.hosting_port_name.lstrip("hostingport_"))
        pool_name = ('pool_' + self.hosting_port_name.lstrip("hostingport_"))
        int_network = netaddr.IPNetwork(self.gw_ip_cidr).network
        int_net_mask = netaddr.IPNetwork(self.gw_ip_cidr).hostmask

        self.driver.enable_internal_network_NAT(self.ri, self.port,
                                                self.ex_gw_port)

        self.assert_edit_running_config(
            snippets.CREATE_ACL, (acl_no, int_network, int_net_mask))
        self.assert_edit_running_config(
            snippets.SET_DYN_SRC_TRL_POOL, (acl_no, pool_name, self.vrf))
        self.assert_edit_running_config(
            snippets.SET_NAT, (int_interface, 'inside'))
        self.assert_edit_running_config(
            snippets.SET_NAT, (ext_interface, 'outside'))

    def test_disable_internal_network_NAT(self):
        self.driver._remove_interface_nat = mock.MagicMock()
        self.driver._remove_dyn_nat_translations = mock.MagicMock()
        self.driver._remove_dyn_nat_rule = mock.MagicMock()
        int_interface = 'GigabitEthernet0'
        ext_interface = 'GigabitEthernet1'
        self.driver.disable_internal_network_NAT(self.ri, self.port,
                                                 self.ex_gw_port)
        args = (('acl_' + self.hosting_port_name.lstrip("hostingport_")),
               ext_interface, self.vrf)

        self.driver._remove_interface_nat.assert_called_once_with(
            int_interface, 'inside')
        self.driver._remove_dyn_nat_translations.assert_called_once_with()
        self.driver._remove_dyn_nat_rule.assert_called_once_with(*args)

    def test_disable_internal_network_NAT_with_confstring(self):
        self.driver._cfg_exists = mock.Mock(return_value=True)
        int_interface = 'GigabitEthernet0'
        acl_no = 'acl_' + self.hosting_port_name.lstrip("hostingport_")
        pool_name = 'pool_' + self.hosting_port_name.lstrip("hostingport_")
        self.driver.disable_internal_network_NAT(self.ri, self.port,
                                                 self.ex_gw_port)

        self.assert_edit_running_config(
            snippets.REMOVE_NAT, (int_interface, 'inside'))
        self.assert_edit_running_config(snippets.CLEAR_DYN_NAT_TRANS, None)
        self.assert_edit_running_config(
            snippets.REMOVE_DYN_SRC_TRL_POOL, (acl_no, pool_name,
                                               self.vrf))
        self.assert_edit_running_config(snippets.REMOVE_ACL, acl_no)

    def test_floatingip(self):
        floating_ip = '15.1.2.3'
        fixed_ip = '10.0.0.3'

        self.driver._add_floating_ip = mock.MagicMock()
        self.driver._remove_floating_ip = mock.MagicMock()
        self.driver._add_interface_nat = mock.MagicMock()
        self.driver._remove_dyn_nat_translations = mock.MagicMock()
        self.driver._remove_interface_nat = mock.MagicMock()

        self.driver.floating_ip_added(self.ri, self.ex_gw_port,
                                      floating_ip, fixed_ip)
        self.driver._add_floating_ip.assert_called_once_with(
            floating_ip, fixed_ip, self.vrf)

        self.driver.floating_ip_removed(self.ri, self.ex_gw_port,
                                        floating_ip, fixed_ip)

        self.driver._remove_interface_nat.assert_called_once_with(
            'GigabitEthernet1', 'outside')
        self.driver._remove_dyn_nat_translations.assert_called_once_with()
        self.driver._remove_floating_ip.assert_called_once_with(
            floating_ip, fixed_ip, self.vrf)
        self.driver._add_interface_nat.assert_called_once_with(
            'GigabitEthernet1', 'outside')
