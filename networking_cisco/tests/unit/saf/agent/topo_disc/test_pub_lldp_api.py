# Copyright 2017 Cisco Systems.
# All Rights Reserved.
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

import collections

import mock

from neutron.tests import base

from networking_cisco.apps.saf.agent.topo_disc import pub_lldp_api as pub_lldp
from networking_cisco.apps.saf.common import dfa_sys_lib as sys_utils

try:
    OrderedDict = collections.OrderedDict
except AttributeError:
    import ordereddict
    OrderedDict = ordereddict.OrderedDict


class LldpApiTest(base.BaseTestCase):
    """A test suite to exercise the public LldpApi class. """

    def setUp(self):
        """Setup for LldpApiTest. """
        super(LldpApiTest, self).setUp()
        self.root_helper = 'sudo'
        self.port_name = 'eth2'
        self.chassis_id_tlv = (
            "Chassis ID TLV\n\n\tMAC: e0:0e:da:cc:ac:1d\n\n")
        self.portid_tlv = (
            "Port ID TLV\n\n\tIfname: Ethernet1/2\n\t"
            "MAC: e0:0e:da:cc:ac:1e\n\tLocal: eth2\n")
        self.ttl_tlv = "Time to Live TLV\n\n\t120\n\n"
        self.port_descr_tlv = "Port Description TLV\n\tEthernet1/2\n"
        self.system_name_tlv = "System Name TLV\n\tN9k-L4\n"
        self.system_desc_tlv = (
            "System Description TLV\n\tCisco Nexus Operating System (NX-OS) "
            "Software 7.0(3)I5(2)TAC support: http://www.cisco.com/tac "
            "Copyright (c) 2002-2016, Cisco Systems, Inc. All rights "
            "reserved.\n")
        self.system_capab_tlv = (
            "System Capabilities TLV\n\t"
            "System capabilities:  Bridge, Router\n\t"
            "Enabled capabilities: Bridge, Router\n\t")
        self.management_address_tlv = (
            "Management Address TLV\n\tIPv4: 11.0.100.74\n\t"
            "Ifindex: 83886080\n\t")
        self.cisco_power_tlv = (
            "Cisco 4-wire Power-via-MDI TLV\n\t4-Pair PoE supported\n\t"
            "Spare pair Detection/Classification not required\n\t"
            "PD Spare pair Desired State: Disabled\n\t"
            "PSE Spare pair Operational State: Disabled\n")
        self.port_vlan_id_tlv = "Port VLAN ID TLV\n\tPVID: 1\n"
        self.mgmt_address_tlv = (
            "Management Address TLV\n\tIPv6: 2002:11:0:100::74\n\t"
            "Ifindex: 83886080\n")
        self.evb_cfg_tlv = (
            "EVB Configuration TLV\n\tbridge:bgid(0x4)\n\tstation:(00)\n\t"
            "retries:3 rte:14\n\tmode:bridge r/l:0 rwd:20\n\tr/l:0 rka:22\n\t")
        self.end_tlv = "End of LLDPDU TLV"
        self.lldp_tlv_correct_out = ''.join(
            (self.chassis_id_tlv, self.portid_tlv, self.ttl_tlv,
             self.port_descr_tlv, self.system_name_tlv, self.system_desc_tlv,
             self.system_capab_tlv, self.management_address_tlv,
             self.cisco_power_tlv, self.port_vlan_id_tlv,
             self.mgmt_address_tlv, self.evb_cfg_tlv, self.end_tlv))
        self.execute = mock.patch.object(
            sys_utils, "execute", spec=sys_utils.execute).start()
        self.pub_lldp = pub_lldp.LldpApi(self.root_helper)

    def test_enable_lldp_ncb_correct_reply(self):
        """Test for enable_lldp function for correct return value. """
        self.execute.return_value = "adminstatus=rxtx"
        ret = self.pub_lldp.enable_lldp(self.port_name)
        self.execute.assert_called_with(
            ["lldptool", "-L", "-i", self.port_name, "-g", "ncb",
             "adminStatus=rxtx"], root_helper=self.root_helper)
        self.assertTrue(ret)

    def test_enable_lldp_ncb_incorrect_reply(self):
        """Test for enable_lldp function for incorrect return value. """
        self.execute.return_value = ""
        ret = self.pub_lldp.enable_lldp(self.port_name)
        self.execute.assert_called_with(
            ["lldptool", "-L", "-i", self.port_name, "-g", "ncb",
             "adminStatus=rxtx"], root_helper=self.root_helper)
        self.assertFalse(ret)

    def test_enable_lldp_nb(self):
        """Test for enable_lldp function for NB DMAC case. """
        self.execute.return_value = "adminstatus=rxtx"
        ret = self.pub_lldp.enable_lldp(self.port_name,
                                        is_ncb=False, is_nb=True)
        self.execute.assert_called_with(
            ["lldptool", "-L", "-i", self.port_name, "-g", "nb",
             "adminStatus=rxtx"], root_helper=self.root_helper)
        self.assertTrue(ret)

    def test_enable_lldp_invalid_case(self):
        """Test for enable_lldp function for neither NCB or NB DMAC case. """
        self.execute.return_value = "adminstatus=rxtx"
        ret = self.pub_lldp.enable_lldp(self.port_name, is_ncb=False)
        self.execute.assert_not_called()
        self.assertFalse(ret)

    def test_get_lldp_tlv_ncb(self):
        """Test for get_lldp_tlv for ncb DMAC case. """
        self.execute.return_value = 'some TLV'
        ret = self.pub_lldp.get_lldp_tlv(self.port_name, is_ncb=True)
        self.execute.assert_called_with(
            ["lldptool", "get-tlv", "-n", "-i", self.port_name, "-g",
             "ncb"], root_helper=self.root_helper)
        self.assertEqual(self.execute.return_value, ret)

    def test_get_lldp_tlv_nb(self):
        """Test for get_lldp_tlv for nb DMAC case. """
        self.execute.return_value = 'some TLV'
        ret = self.pub_lldp.get_lldp_tlv(self.port_name, is_ncb=False,
                                         is_nb=True)
        self.execute.assert_called_with(
            ["lldptool", "get-tlv", "-n", "-i", self.port_name, "-g",
             "nb"], root_helper=self.root_helper)
        self.assertEqual(self.execute.return_value, ret)

    def test_common_tlv_format_none_case(self):
        """Test _check_common_tlv_format when TLV data is None. """
        ret, tlv_parsed = self.pub_lldp._check_common_tlv_format(
            None, None, None)
        self.assertFalse(ret)
        self.assertIsNone(tlv_parsed)

    def test_common_tlv_format_no_tlv_case(self):
        """Test _check_common_tlv_format when specific TLV is not present. """
        invalid_tlv = self.lldp_tlv_correct_out.replace(self.evb_cfg_tlv, '')
        ret, tlv_parsed = self.pub_lldp._check_common_tlv_format(
            invalid_tlv, "mode:", "EVB Configuration TLV")
        self.assertFalse(ret)
        self.assertIsNone(tlv_parsed)

    def test_common_tlv_format_no_tlv_data_case(self):
        """Test _check_common_tlv_format when TLV data is not present. """
        invalid_tlv = self.lldp_tlv_correct_out.replace(self.evb_cfg_tlv, '')
        invalid_tlv = invalid_tlv + "EVB Configuration TLV\n\t"
        ret, tlv_parsed = self.pub_lldp._check_common_tlv_format(
            invalid_tlv, "mode:", "EVB Configuration TLV")
        self.assertFalse(ret)
        self.assertIsNone(tlv_parsed)

    def test_common_tlv_format_no_tlv_data_pattern_case(self):
        """Test _check_common_tlv_format when TLV pattern is not present. """
        invalid_tlv = self.lldp_tlv_correct_out.replace(
            "mode:bridge r/l:0 rwd:20", '')
        ret, tlv_parsed = self.pub_lldp._check_common_tlv_format(
            invalid_tlv, "mode:", "EVB Configuration TLV")
        self.assertFalse(ret)
        self.assertIsNone(tlv_parsed)

    def test_remote_evb_cfgd(self):
        """Test the case when remove EVB TLV is present.

        False case is tested in the test_common.. cases.
        """
        ret = self.pub_lldp.get_remote_evb_cfgd(self.lldp_tlv_correct_out)
        self.assertTrue(ret)

    def test_remote_evb_mode(self):
        """Test the get_remote_evb_mode function. """
        ret = self.pub_lldp.get_remote_evb_mode(self.lldp_tlv_correct_out)
        self.assertEqual('bridge', ret)

    def test_remote_evb_mode_incorrect(self):
        """Test the get_remote_evb_mode function for incorrect TLV. """
        invalid_tlv = self.lldp_tlv_correct_out.replace(
            "mode:bridge r/l:0 rwd:20", '')
        ret = self.pub_lldp.get_remote_evb_mode(invalid_tlv)
        self.assertIsNone(ret)

    def test_remote_mgmt_addr(self):
        """Test the get_remote_mgmt_addr function. """
        ret = self.pub_lldp.get_remote_mgmt_addr(self.lldp_tlv_correct_out)
        self.assertEqual('IPv4:11.0.100.74', ret)

    def test_remote_system_desc(self):
        """Test the get_remote_system_desc function. """
        ret = self.pub_lldp.get_remote_sys_desc(self.lldp_tlv_correct_out)
        match_string = self.system_desc_tlv.replace(
            "System Description TLV", '').replace('\n', '').replace('\t', '')
        self.assertEqual(match_string, ret)

    def test_remote_system_name(self):
        """Test the get_remote_system_name function. """
        ret = self.pub_lldp.get_remote_sys_name(self.lldp_tlv_correct_out)
        self.assertEqual('N9k-L4', ret)

    def test_remote_port(self):
        """Test the get_remote_port function. """
        ret = self.pub_lldp.get_remote_port(self.lldp_tlv_correct_out)
        self.assertEqual('Ethernet1/2', ret)

    def test_remote_chassis_id_mac(self):
        """Test the get_remote_chassis_id_mac function. """
        ret = self.pub_lldp.get_remote_chassis_id_mac(
            self.lldp_tlv_correct_out)
        self.assertEqual('e0:0e:da:cc:ac:1d', ret)

    def test_remote_port_id_mac(self):
        """Test the get_remote_port_id_mac function. """
        ret = self.pub_lldp.get_remote_port_id_mac(self.lldp_tlv_correct_out)
        self.assertEqual('e0:0e:da:cc:ac:1e', ret)

    def test_remote_port_id_local(self):
        """Test the get_remote_port_id_local function. """
        ret = self.pub_lldp.get_remote_port_id_local(self.lldp_tlv_correct_out)
        self.assertEqual('eth2', ret)
