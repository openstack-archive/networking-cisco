# Copyrigh 2015 Cisco Systems.
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

from networking_cisco.apps.saf.agent.vdp import (
    lldpad_constants as vdp_const)
from networking_cisco.apps.saf.agent.vdp import lldpad
from networking_cisco.apps.saf.common import dfa_sys_lib as utils

try:
    OrderedDict = collections.OrderedDict
except AttributeError:
    import ordereddict
    OrderedDict = ordereddict.OrderedDict


class LldpadDriverTest(base.BaseTestCase):
    """A test suite to exercise the Lldpad Driver.  """

    def setUp(self):
        '''Setup for the test scripts '''
        super(LldpadDriverTest, self).setUp()
        self.root_helper = 'sudo'
        self.port_name = "loc_veth"
        self.uplink = "eth2"
        self.port_str = "loc_veth_eth2"
        self.execute = mock.patch.object(
            utils, "execute", spec=utils.execute).start()
        self.fill_default_vsi_params()
        self._test_lldp_init()

    def _test_lldp_init(self):
        '''Tests the initialization '''
        with mock.patch('networking_cisco.apps.saf.common.'
                        'utils.PeriodicTask') as period_fn:
            period_obj = period_fn.return_value
            parent = mock.MagicMock()
            parent.attach_mock(period_obj.run, 'run')
            self.lldpad = lldpad.LldpadDriver(self.port_str, self.uplink,
                                              self.root_helper)
        expected_calls = [mock.call.run()]
        parent.assert_has_calls(expected_calls)

    def test_init(self):
        '''Place hlder for init '''
        pass

    def _test_enable_lldp(self, is_ncb=True):
        '''Tests the routine the enables EVB cfg '''
        self.lldpad.enable_lldp()
        if is_ncb is True:
            self.execute.assert_called_with(
                ["lldptool", "-L", "-i", self.port_str, "-g", "ncb",
                 "adminStatus=rxtx"], root_helper=self.root_helper)

    def test_enable_lldp(self):
        '''Tests the routine the enables LLDP cfg '''
        self._test_enable_lldp(is_ncb=True)

    def test_enable_evb(self):
        '''Top level routine for EVB cfg test '''
        parent = mock.MagicMock()
        parent.attach_mock(self.execute, 'execute')
        self.lldpad.enable_evb()
        expected_calls = [mock.call.execute(["lldptool", "-T", "-i",
                                             self.port_str, "-g", "ncb", "-V",
                                             "evb", "enableTx=yes"],
                                            root_helper=self.root_helper),
                          mock.call.execute(["lldptool", "-T", "-i",
                                             self.port_str, "-g", "ncb", "-V",
                                             "evb", "-c", "evbgpid=yes"],
                                            root_helper=self.root_helper)]
        parent.assert_has_calls(expected_calls)

    def fill_default_vsi_params(self):
        '''Mock VSI Params '''
        self.uuid = "00000000-1111-2222-3333-444455556666"
        self.vsiid = self.uuid
        self.mgrid = 0
        self.typeid = 0
        self.typeidver = 0
        self.gid = 20000
        self.mac = "00:11:22:33:44:55"
        self.vlan = 0

        self.mgrid_str = "mgrid2=0"
        self.typeid_str = "typeid=0"
        self.typeidver_str = "typeidver=0"
        self.vsiid_str = "uuid=00000000-1111-2222-3333-444455556666"
        self.filter_str = "filter=0-00:11:22:33:44:55-20000"
        self.mode_str = "mode=assoc"

    def _test_vnic_assert(self, test_vlan, vlan_ret, filter_str, new_nwk,
                          parent, is_rest=0):
        '''assert tests called by other test functions '''
        if new_nwk:
            if is_rest == 1:
                expected_calls = [mock.call.execute(["vdptool", "-t", "-i",
                                                     self.port_str, "-R",
                                                     "-V", "assoc", "-c",
                                                     self.mode_str, "-c",
                                                     self.mgrid_str, "-c",
                                                     self.typeid_str, "-c",
                                                     self.typeidver_str, "-c",
                                                     self.vsiid_str],
                                                    root_helper=(
                    self.root_helper))]
            else:
                expected_calls = [mock.call.execute(["vdptool", "-T", "-i",
                                                     self.port_str, "-W",
                                                     "-V", "assoc", "-c",
                                                     self.mode_str, "-c",
                                                     self.mgrid_str, "-c",
                                                     self.typeid_str, "-c",
                                                     self.typeidver_str, "-c",
                                                     self.vsiid_str, "-c",
                                                     "hints=none", "-c",
                                                     filter_str],
                                                    root_helper=(
                    self.root_helper))]
            self.assertEqual(vlan_ret, test_vlan)
            self.assertEqual(test_vlan,
                             self.lldpad.vdp_vif_map[self.uuid].
                             get('vdp_vlan'))
        else:
            expected_calls = [mock.call.execute(["vdptool", "-T", "-i",
                                                 self.port_str, "-V", "assoc",
                                                 "-c", self.mode_str,
                                                 "-c", self.mgrid_str, "-c",
                                                 self.typeid_str, "-c",
                                                 self.typeidver_str, "-c",
                                                 self.vsiid_str, "-c",
                                                 "hints=none", "-c",
                                                 filter_str],
                                                root_helper=self.root_helper)]
        parent.assert_has_calls(expected_calls)
        self.assertEqual(self.mgrid,
                         self.lldpad.vdp_vif_map[self.uuid].get('mgrid'))
        self.assertEqual(self.typeid,
                         self.lldpad.vdp_vif_map[self.uuid].get('typeid'))
        self.assertEqual(self.typeidver,
                         self.lldpad.vdp_vif_map[self.uuid].get('typeid_ver'))
        self.assertEqual(self.vsiid,
                         self.lldpad.vdp_vif_map[self.uuid].get('vsiid'))
        self.assertEqual(vdp_const.VDP_FILTER_GIDMACVID,
                         self.lldpad.vdp_vif_map[self.uuid].get('filter_frmt'))
        self.assertEqual(self.gid,
                         self.lldpad.vdp_vif_map[self.uuid].get('gid'))
        self.assertEqual(self.mac,
                         self.lldpad.vdp_vif_map[self.uuid].get('mac'))

    def test_vdp_port_up_new_nwk(self):
        '''Tests the case when a VM comes for a new network '''
        expected_vlan = 3003
        parent = mock.MagicMock()
        parent.attach_mock(self.execute, 'execute')
        self.execute.return_value = ("Response from VDP\n\tmode = assoc\n\t"
                                     "mgrid2 = 0\n\ttypeid = 0\n\t"
                                     "typeidver = 0\n\tuuid = 00000000-1111-"
                                     "2222-3333-444455556666\n\t"
                                     "filter = 3003-00:11:22:33:44:55-0\n")
        self.lldpad.send_vdp_query_msg = mock.Mock()
        vlan_ret = self.lldpad.send_vdp_vnic_up(port_uuid=self.uuid,
                                                vsiid=self.vsiid,
                                                mgrid=self.mgrid,
                                                typeid=self.typeid,
                                                typeid_ver=self.typeidver,
                                                gid=self.gid,
                                                mac=self.mac,
                                                new_network=True)
        self._test_vnic_assert(expected_vlan, vlan_ret[0], self.filter_str,
                               True, parent)

    def test_vdp_port_up_new_nwk_after_restart(self):
        '''Tests the case when a VM comes for a new network after restart '''
        expected_vlan = 3003
        parent = mock.MagicMock()
        parent.attach_mock(self.execute, 'execute')
        self.execute.return_value = ("M000080c4C3010000001509LLDPLeth5"
                                     "020000000304mode0005assoc06mgrid2"
                                     "0001006typeid0001009typeidver0001004"
                                     "uuid002400000000-1111-2222-3333-44445555"
                                     "6666\nR00C3010000001509LLDPLeth500000003"
                                     "010504mode0005assoc06mgrid20001006typeid"
                                     "0001009typeidver0001004uuid00000000-1111"
                                     "-2222-3333-44445555666605hints0001006"
                                     "filter001c3003-00:11:22:33:44:55-2000003"
                                     "oui006105cisco07vm_name000bFW_SRVC_RTR07"
                                     "vm_uuid002467f338a6-0925-42aa-b2df-e8114"
                                     "e9fd0da09ipv4_addr00020l\n")
        vlan_ret = self.lldpad.send_vdp_vnic_up(port_uuid=self.uuid,
                                                vsiid=self.vsiid,
                                                mgrid=self.mgrid,
                                                typeid=self.typeid,
                                                typeid_ver=self.typeidver,
                                                gid=self.gid,
                                                mac=self.mac,
                                                new_network=True)
        self._test_vnic_assert(expected_vlan, vlan_ret[0], self.filter_str,
                               True, parent, is_rest=1)

    def test_vdp_refresh_handler(self):
        """Test for VDP refresh handler, with one VDI. """
        vlan_vif = 3003
        self.lldpad.vdp_vif_map = {
            '00000000-1111-2222-3333-444455556666':
            {'vsw_cb_data': None, 'vsw_cb_fn': None, 'vsiid_frmt': 5,
             'typeid_ver': 0, 'mac': '00:11:22:33:44:55',
             'vsiid': '00000000-1111-2222-3333-444455556666',
             'vdp_vlan': vlan_vif, 'callback_count': 0, 'typeid': 0,
             'fail_reason': None, 'gid': 20000, 'filter_frmt': 4, 'mgrid': 0}}
        port_vif_map = self.lldpad.vdp_vif_map.get(
            '00000000-1111-2222-3333-444455556666')
        with mock.patch.object(self.lldpad, 'send_vdp_assoc',
                               return_value=[vlan_vif, None]) as vdp_assoc:
            self.lldpad._vdp_refrsh_hndlr()
        vdp_assoc.assert_called_with(
            vsiid=port_vif_map.get('vsiid'), mgrid=0, typeid=0, typeid_ver=0,
            vsiid_frmt=port_vif_map.get('vsiid_frmt'),
            filter_frmt=port_vif_map.get('filter_frmt'),
            gid=port_vif_map.get('gid'), mac=port_vif_map.get('mac'),
            vlan=0, oui_id='', oui_data='', sw_resp=True)
        self.assertEqual(1, port_vif_map.get('callback_count'))

    def test_vdp_refresh_handler_modf_vlan(self):
        """Test for VDP refresh handler, when VLAN from VDP is changed. """
        vlan_vif = 3003
        vdp_vlan = 3004
        self.lldpad.vdp_vif_map = {
            '00000000-1111-2222-3333-444455556666':
            {'vsw_cb_data': 'dummy_data', 'vsw_cb_fn': None, 'vsiid_frmt': 5,
             'typeid_ver': 0, 'mac': '00:11:22:33:44:55',
             'vsiid': '00000000-1111-2222-3333-444455556666',
             'vdp_vlan': vlan_vif, 'callback_count': 0, 'typeid': 0,
             'fail_reason': None, 'gid': 20000, 'filter_frmt': 4, 'mgrid': 0}}
        port_vif_map = self.lldpad.vdp_vif_map.get(
            '00000000-1111-2222-3333-444455556666')
        with mock.patch.object(self.lldpad, 'send_vdp_assoc',
                               return_value=[vdp_vlan, None]) as vdp_assoc:
            port_vif_map['vsw_cb_fn'] = mock.MagicMock()
            self.lldpad._vdp_refrsh_hndlr()
        vdp_assoc.assert_called_with(
            vsiid=port_vif_map.get('vsiid'), mgrid=0, typeid=0, typeid_ver=0,
            vsiid_frmt=port_vif_map.get('vsiid_frmt'),
            filter_frmt=port_vif_map.get('filter_frmt'),
            gid=port_vif_map.get('gid'), mac=port_vif_map.get('mac'),
            vlan=0, oui_id='', oui_data='', sw_resp=True)
        self.assertEqual(0, port_vif_map.get('callback_count'))
        port_vif_map['vsw_cb_fn'].assert_called_with('dummy_data', vdp_vlan,
                                                     None)

    def test_vdp_refresh_handler_modf_reason(self):
        """Test for VDP refresh handler, when fail reason is changed. """
        vlan_vif = 0
        self.lldpad.vdp_vif_map = {
            '00000000-1111-2222-3333-444455556666':
            {'vsw_cb_data': 'dummy_data', 'vsw_cb_fn': None, 'vsiid_frmt': 5,
             'typeid_ver': 0, 'mac': '00:11:22:33:44:55',
             'vsiid': '00000000-1111-2222-3333-444455556666',
             'vdp_vlan': vlan_vif, 'callback_count': 0, 'typeid': 0,
             'fail_reason': "some reason", 'gid': 20000, 'filter_frmt': 4,
             'mgrid': 0}}
        port_vif_map = self.lldpad.vdp_vif_map.get(
            '00000000-1111-2222-3333-444455556666')
        with mock.patch.object(self.lldpad, 'send_vdp_assoc',
                               return_value=[vlan_vif,
                                             "any reason"]) as vdp_assoc:
            port_vif_map['vsw_cb_fn'] = mock.MagicMock()
            self.lldpad._vdp_refrsh_hndlr()
        vdp_assoc.assert_called_with(
            vsiid=port_vif_map.get('vsiid'), mgrid=0, typeid=0, typeid_ver=0,
            vsiid_frmt=port_vif_map.get('vsiid_frmt'),
            filter_frmt=port_vif_map.get('filter_frmt'),
            gid=port_vif_map.get('gid'), mac=port_vif_map.get('mac'),
            vlan=0, oui_id='', oui_data='', sw_resp=True)
        self.assertEqual(0, port_vif_map.get('callback_count'))
        port_vif_map['vsw_cb_fn'].assert_called_with(
            'dummy_data', 0, "any reason")

    def test_vdp_refresh_handler_cb_thresh_exceed(self):
        """Test for refresh handler, when callback threshold has exceeded. """
        vlan_vif = 3003
        self.lldpad.vdp_vif_map = {
            '00000000-1111-2222-3333-444455556666':
            {'vsw_cb_data': 'dummy_data', 'vsw_cb_fn': None, 'vsiid_frmt': 5,
             'typeid_ver': 0, 'mac': '00:11:22:33:44:55',
             'vsiid': '00000000-1111-2222-3333-444455556666',
             'vdp_vlan': vlan_vif, 'callback_count': 7, 'typeid': 0,
             'fail_reason': None, 'gid': 20000, 'filter_frmt': 4, 'mgrid': 0}}
        port_vif_map = self.lldpad.vdp_vif_map.get(
            '00000000-1111-2222-3333-444455556666')
        with mock.patch.object(self.lldpad, 'send_vdp_assoc',
                               return_value=[vlan_vif, None]) as vdp_assoc:
            port_vif_map['vsw_cb_fn'] = mock.MagicMock()
            self.lldpad._vdp_refrsh_hndlr()
        vdp_assoc.assert_called_with(
            vsiid=port_vif_map.get('vsiid'), mgrid=0, typeid=0, typeid_ver=0,
            vsiid_frmt=port_vif_map.get('vsiid_frmt'),
            filter_frmt=port_vif_map.get('filter_frmt'),
            gid=port_vif_map.get('gid'), mac=port_vif_map.get('mac'),
            vlan=0, oui_id='', oui_data='', sw_resp=True)
        self.assertEqual(0, port_vif_map.get('callback_count'))
        port_vif_map['vsw_cb_fn'].assert_called_with(
            'dummy_data', vlan_vif, None)

    def test_vdp_failure_reason_valid(self):
        """Test for case that parses the failure reason for valid case. """
        reply = ("Response from VDP\n\tmode = deassoc\n\tmgrid2 = 0\n\t"
                 "typeid = 0\n\ttypeidver = 0\n\t"
                 "uuid = 7af441dd-253b-4772-8cf1-a4cfef18efe5\n\t"
                 "Error returned by Bridge: Other Failures\n\t"
                 "filter = 0-fa:16:3e:af:43:d9-0\n")
        reason = self.lldpad.get_vdp_failure_reason(reply)
        self.assertEqual("Error returned by Bridge: Other Failures", reason)

    def test_vdp_failure_reason_invalid(self):
        """Test for case that parses the failure reason for invalid case. """
        reply = "\nReturn from vsievt -11"
        expected_reason = vdp_const.retrieve_failure_reason % (reply)
        reason = self.lldpad.get_vdp_failure_reason(reply)
        self.assertEqual(expected_reason, reason)

    def test_vdp_failure_reason_invalid_null(self):
        """Test for case that parses the failure reason for null case. """
        reply = ""
        expected_reason = vdp_const.retrieve_failure_reason % (reply)
        reason = self.lldpad.get_vdp_failure_reason(reply)
        self.assertEqual(expected_reason, reason)

    def test_filter_query_validity_incorrect_filter(self):
        """Test for filter query, when there's no filter. """
        reply = "\nReturn from vsievt -11"
        expected_reason = vdp_const.filter_failure_reason % (reply)
        result, reason = self.lldpad.check_filter_validity(reply, "filter")
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_filter_reply_validity_incorrect_filter(self):
        """Test for filter reply, when there's no filter. """
        reply = "\nReturn from vsievt -11"
        expected_reason = vdp_const.filter_failure_reason % (reply)
        result, reason = self.lldpad.check_filter_validity(reply, "filter = ")
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_filter_query_validity_multiple_filter(self):
        """Test for filter query, when there are multiple filters. """
        reply = ("M000080c4C3010000001509LLDPLeth5"
                 "020000000304mode0005assoc06mgrid2"
                 "0001006typeid0001009typeidver0001004"
                 "uuid002400000000-1111-2222-3333-44445555"
                 "6666\nR00C3010000001509LLDPLeth500000003"
                 "010504mode0005assoc06mgrid20001006typeid"
                 "0001009typeidver0001004uuid00000000-1111"
                 "-2222-3333-44445555666605hints0001006"
                 "filter001c3003-00:11:22:33:44:55-2000003"
                 "filter001c3003-00:aa:22:33:44:55-2000003"
                 "oui006105cisco07vm_name000bFW_SRVC_RTR07"
                 "vm_uuid002467f338a6-0925-42aa-b2df-e8114"
                 "e9fd0da09ipv4_addr00020l\n")
        expected_reason = vdp_const.multiple_filter_failure_reason % (reply)
        result, reason = self.lldpad.check_filter_validity(reply, "filter")
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_filter_reply_validity_multiple_filter(self):
        """Test for filter reply, when there are multiple filters. """

        reply = ("Response from VDP\n\tmode = assoc\n\t"
                 "mgrid2 = 0\n\ttypeid = 0\n\t"
                 "typeidver = 0\n\tuuid = 00000000-1111-"
                 "2222-3333-444455556666\n\t"
                 "filter = 3003-00:11:22:33:44:55-0\n"
                 "filter = 3003-00:AA:22:33:44:55-0\n")
        expected_reason = vdp_const.multiple_filter_failure_reason % (reply)
        result, reason = self.lldpad.check_filter_validity(reply, "filter = ")
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_filter_query_validity(self):
        """Test for filter query validity. Positive case. """
        reply = ("M000080c4C3010000001509LLDPLeth5"
                 "020000000304mode0005assoc06mgrid2"
                 "0001006typeid0001009typeidver0001004"
                 "uuid002400000000-1111-2222-3333-44445555"
                 "6666\nR00C3010000001509LLDPLeth500000003"
                 "010504mode0005assoc06mgrid20001006typeid"
                 "0001009typeidver0001004uuid00000000-1111"
                 "-2222-3333-44445555666605hints0001006"
                 "filter001c3003-00:11:22:33:44:55-2000003"
                 "oui006105cisco07vm_name000bFW_SRVC_RTR07"
                 "vm_uuid002467f338a6-0925-42aa-b2df-e8114"
                 "e9fd0da09ipv4_addr00020l\n")
        expected_reason = None
        result, reason = self.lldpad.check_filter_validity(reply, "filter")
        self.assertTrue(result)
        self.assertEqual(expected_reason, reason)

    def test_filter_reply_validity(self):
        """Test for filter reply validity. Positive case. """
        reply = ("Response from VDP\n\tmode = assoc\n\t"
                 "mgrid2 = 0\n\ttypeid = 0\n\t"
                 "typeidver = 0\n\tuuid = 00000000-1111-"
                 "2222-3333-444455556666\n\t"
                 "filter = 3003-00:11:22:33:44:55-0\n")
        expected_reason = None
        result, reason = self.lldpad.check_filter_validity(reply, "filter = ")
        self.assertTrue(result)
        self.assertEqual(expected_reason, reason)

    def test_mode_reply_invalid(self):
        """Test for mode reply validity. Invalid case. """
        reply = ("Response from VDP\n\t"
                 "mgrid2 = 0\n\ttypeid = 0\n\t"
                 "typeidver = 0\n\tuuid = 00000000-1111-"
                 "2222-3333-444455556666\n\t"
                 "filter = 3003-00:11:22:33:44:55-0\n")
        expected_reason = vdp_const.mode_failure_reason % (reply)
        vlan, reason = self.lldpad.get_vlan_from_associate_reply(
            reply, "00000000-1111-2222-3333-444455556666", "00:11:22:33:44:55")
        self.assertEqual(-1, vlan)
        self.assertEqual(expected_reason, reason)

    def test_mode_reply_deassoc(self):
        """Test for mode reply when deassoc is sent. """
        reply = ("Response from VDP\n\tmode = deassoc\n\tmgrid2 = 0\n\t"
                 "typeid = 0\n\ttypeidver = 0\n\t"
                 "uuid = 7af441dd-253b-4772-8cf1-a4cfef18efe5\n\t"
                 "Error returned by Bridge: Other Failures\n\t"
                 "filter = 0-fa:16:3e:af:43:d9-0\n")
        expected_reason = "Error returned by Bridge: Other Failures"
        vlan, reason = self.lldpad.get_vlan_from_associate_reply(
            reply, "7af441dd-253b-4772-8cf1-a4cfef18efe5", "fa:16:3e:af:43:d9")
        self.assertEqual(-1, vlan)
        self.assertEqual(expected_reason, reason)

    def test_vlan_reply_invalid(self):
        """Test for invalid vlan reply. """
        reply = ("Response from VDP\n\tmode = assoc\n\tmgrid2 = 0\n\t"
                 "typeid = 0\n\ttypeidver = 0\n\t"
                 "uuid = 7af441dd-253b-4772-8cf1-a4cfef18efe5\n\t"
                 "filter = pat-fa:16:3e:af:43:d9-0\n")
        expected_reason = vdp_const.format_failure_reason % (reply)
        vlan, reason = self.lldpad.get_vlan_from_associate_reply(
            reply, "7af441dd-253b-4772-8cf1-a4cfef18efe5", "fa:16:3e:af:43:d9")
        self.assertEqual(-1, vlan)
        self.assertEqual(expected_reason, reason)

    # Have another case, where reply is there, but no hints
    def test_incorrect_hints(self):
        """Test for case when there's no hints in reply. """
        reply = "\nReturn from vsievt -11"
        expected_reason = vdp_const.hints_failure_reason % (reply)
        result, reason = self.lldpad.check_hints(reply)
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_multiple_hints(self):
        """Test for case, when there are multiple hints in query response. """
        reply = ("M000080c4C3010000001509LLDPLeth5"
                 "020000000304mode0005assoc06mgrid2"
                 "0001006typeid0001009typeidver0001004"
                 "uuid002400000000-1111-2222-3333-44445555"
                 "6666\nR00C3010000001509LLDPLeth500000003"
                 "010504mode0005assoc06mgrid20001006typeid"
                 "0001009typeidver0001004uuid00000000-1111"
                 "-2222-3333-44445555666605hints0001006"
                 "05hints0001007filter001c3003-00:11:22:33:44:55-2000003"
                 "oui006105cisco07vm_name000bFW_SRVC_RTR07"
                 "vm_uuid002467f338a6-0925-42aa-b2df-e8114"
                 "e9fd0da09ipv4_addr00020l\n")
        expected_reason = vdp_const.multiple_hints_failure_reason % (reply)
        result, reason = self.lldpad.check_hints(reply)
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_nonzero_hints(self):
        """Test for non-zero hints. """
        reply = ("M000080c4C3010000001509LLDPLeth5"
                 "020000000304mode0005assoc06mgrid2"
                 "0001006typeid0001009typeidver0001004"
                 "uuid002400000000-1111-2222-3333-44445555"
                 "6666\nR00C3010000001509LLDPLeth500000003"
                 "010504mode0005assoc06mgrid20001006typeid"
                 "0001009typeidver0001004uuid00000000-1111"
                 "-2222-3333-44445555666605hints0001806"
                 "filter001c3003-00:11:22:33:44:55-2000003"
                 "oui006105cisco07vm_name000bFW_SRVC_RTR07"
                 "vm_uuid002467f338a6-0925-42aa-b2df-e8114"
                 "e9fd0da09ipv4_addr00020l\n")
        expected_reason = vdp_const.nonzero_hints_failure % 8
        result, reason = self.lldpad.check_hints(reply)
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_hints_exception(self):
        """Test for incorrectly formatted hints. """
        reply = ("M000080c4C3010000001509LLDPLeth5"
                 "020000000304mode0005assoc06mgrid2"
                 "0001006typeid0001009typeidver0001004"
                 "uuid002400000000-1111-2222-3333-44445555"
                 "6666\nR00C3010000001509LLDPLeth500000003"
                 "010504mode0005assoc06mgrid20001006typeid"
                 "0001009typeidver0001004uuid00000000-1111"
                 "-2222-3333-44445555666605hints00ef806"
                 "filter001c3003-00:11:22:33:44:55-2000003"
                 "oui006105cisco07vm_name000bFW_SRVC_RTR07"
                 "vm_uuid002467f338a6-0925-42aa-b2df-e8114"
                 "e9fd0da09ipv4_addr00020l\n")
        expected_reason = vdp_const.format_failure_reason % (reply)
        result, reason = self.lldpad.check_hints(reply)
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_valid_hints(self):
        """Test for valid hints case. """
        reply = ("M000080c4C3010000001509LLDPLeth5"
                 "020000000304mode0005assoc06mgrid2"
                 "0001006typeid0001009typeidver0001004"
                 "uuid002400000000-1111-2222-3333-44445555"
                 "6666\nR00C3010000001509LLDPLeth500000003"
                 "010504mode0005assoc06mgrid20001006typeid"
                 "0001009typeidver0001004uuid00000000-1111"
                 "-2222-3333-44445555666605hints0001006"
                 "filter001c3003-00:11:22:33:44:55-2000003"
                 "oui006105cisco07vm_name000bFW_SRVC_RTR07"
                 "vm_uuid002467f338a6-0925-42aa-b2df-e8114"
                 "e9fd0da09ipv4_addr00020l\n")
        result, reason = self.lldpad.check_hints(reply)
        self.assertTrue(result)
        self.assertIsNone(reason)

    def test_vlan_query_incorrect_filter(self):
        """Test for incorrect filter in vlan query function. """
        reply = "Mock reply"
        with mock.patch.object(self.lldpad, 'check_hints',
                               return_value=[True, None]),\
            mock.patch.object(self.lldpad, 'check_filter_validity',
                              return_value=[False, 'Some failure']):
            result, reason = self.lldpad.get_vlan_from_query_reply(
                reply, "00000000-1111-2222-3333-444455556666",
                "00:11:22:33:44:55")
        self.assertEqual(-1, result)

    def test_vlan_query_vsiid_fail(self):
        """Test for incorrect vsiid in vlan query function. """
        reply = "Mock reply"
        with mock.patch.object(self.lldpad, 'check_hints',
                               return_value=[True, None]),\
            mock.patch.object(self.lldpad, 'check_filter_validity',
                              return_value=[True, None]),\
            mock.patch.object(self.lldpad, 'crosscheck_query_vsiid_mac',
                              return_value=[False, None]):
            result, reason = self.lldpad.get_vlan_from_query_reply(
                reply, "00000000-1111-2222-3333-444455556666",
                "00:11:22:33:44:55")
        self.assertEqual(-1, result)

    def test_vlan_query_exception(self):
        """Test for incorrectly formatted reply in vlan query function. """
        reply = ("M000080c4C3010000001509LLDPLeth5"
                 "020000000304mode0005assoc06mgrid2"
                 "0001006typeid0001009typeidver0001004"
                 "uuid002400000000-1111-2222-3333-44445555"
                 "6666\nR00C3010000001509LLDPLeth500000003"
                 "010504mode0005assoc06mgrid20001006typeid"
                 "0001009typeidver0001004uuid00000000-1111"
                 "-2222-3333-44445555666605hints0001006"
                 "filter001ca003-00:11:22:33:44:55-2000003"
                 "oui006105cisco07vm_name000bFW_SRVC_RTR07"
                 "vm_uuid002467f338a6-0925-42aa-b2df-e8114"
                 "e9fd0da09ipv4_addr00020l\n")
        expected_reason = vdp_const.format_failure_reason % (reply)
        with mock.patch.object(self.lldpad, 'check_hints',
                               return_value=[True, None]),\
            mock.patch.object(self.lldpad, 'check_filter_validity',
                              return_value=[True, None]),\
            mock.patch.object(self.lldpad, 'crosscheck_query_vsiid_mac',
                              return_value=[True, None]):
            result, reason = self.lldpad.get_vlan_from_query_reply(
                reply, "00000000-1111-2222-3333-444455556666",
                "00:11:22:33:44:55")
        self.assertEqual(-1, result)
        self.assertEqual(expected_reason, reason)

    def test_crosscheck_query_mismatch_vsiid(self):
        """Test VSI ID mismatch in reply. """
        reply = ("M000080c4C3010000001509LLDPLeth5"
                 "020000000304mode0005assoc06mgrid2"
                 "0001006typeid0001009typeidver0001004"
                 "uuid002400000000-1111-2222-3333-44445555"
                 "6666\nR00C3010000001509LLDPLeth500000003"
                 "010504mode0005assoc06mgrid20001006typeid"
                 "0001009typeidver0001004uuid00000000-1111"
                 "-2222-3333-44445555666605hints0001006"
                 "filter001ca003-00:11:22:33:44:55-2000003"
                 "oui006105cisco07vm_name000bFW_SRVC_RTR07"
                 "vm_uuid002467f338a6-0925-42aa-b2df-e8114"
                 "e9fd0da09ipv4_addr00020l\n")
        expected_reason = vdp_const.vsi_mismatch_failure_reason % (
            "000000ff-1111-2222-3333-444455556666",
            "00000000-1111-2222-3333-444455556666")
        result, reason = self.lldpad.crosscheck_query_vsiid_mac(
            reply, "000000ff-1111-2222-3333-444455556666", "00:11:22:33:44:55")
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_crosscheck_reply_mismatch_vsiid(self):
        """Test VSI ID mismatch in reply. """
        reply = ("Response from VDP\n\tmode = assoc\n\t"
                 "mgrid2 = 0\n\ttypeid = 0\n\t"
                 "typeidver = 0\n\tuuid = 00000000-1111-"
                 "2222-3333-444455556666\n\t"
                 "filter = 3003-00:12:22:33:44:55-0\n")
        expected_reason = vdp_const.vsi_mismatch_failure_reason % (
            "000000ff-1111-2222-3333-444455556666",
            "00000000-1111-2222-3333-444455556666")
        result, reason = self.lldpad.crosscheck_reply_vsiid_mac(
            reply, "000000ff-1111-2222-3333-444455556666", "00:11:22:33:44:55")
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_crosscheck_query_mismatch_mac(self):
        """Test MAC mismatch in query. """
        reply = ("M000080c4C3010000001509LLDPLeth5"
                 "020000000304mode0005assoc06mgrid2"
                 "0001006typeid0001009typeidver0001004"
                 "uuid002400000000-1111-2222-3333-44445555"
                 "6666\nR00C3010000001509LLDPLeth500000003"
                 "010504mode0005assoc06mgrid20001006typeid"
                 "0001009typeidver0001004uuid00000000-1111"
                 "-2222-3333-44445555666605hints0001006"
                 "filter001ca003-00:11:22:33:44:55-2000003"
                 "oui006105cisco07vm_name000bFW_SRVC_RTR07"
                 "vm_uuid002467f338a6-0925-42aa-b2df-e8114"
                 "e9fd0da09ipv4_addr00020l\n")
        expected_reason = vdp_const.mac_mismatch_failure_reason % (
            "00:ff:22:33:44:55", "00:11:22:33:44:55")
        result, reason = self.lldpad.crosscheck_query_vsiid_mac(
            reply, "00000000-1111-2222-3333-444455556666", "00:ff:22:33:44:55")
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_crosscheck_reply_mismatch_mac(self):
        """Test MAC mismatch in reply. """
        reply = ("Response from VDP\n\tmode = assoc\n\t"
                 "mgrid2 = 0\n\ttypeid = 0\n\t"
                 "typeidver = 0\n\tuuid = 00000000-1111-"
                 "2222-3333-444455556666\n\t"
                 "filter = 3003-00:11:22:33:44:55-0\n")
        expected_reason = vdp_const.mac_mismatch_failure_reason % (
            "00:ff:22:33:44:55", "00:11:22:33:44:55")
        result, reason = self.lldpad.crosscheck_reply_vsiid_mac(
            reply, "00000000-1111-2222-3333-444455556666", "00:ff:22:33:44:55")
        self.assertFalse(result)
        self.assertEqual(expected_reason, reason)

    def test_vdp_port_up_new_nwk_invalid_vlan(self):
        '''
        Tests the case when an invalid VLAN is rteturned for a VM that comes
        up for a new network
        '''
        expected_vlan = -1
        parent = mock.MagicMock()
        parent.attach_mock(self.execute, 'execute')
        self.execute.return_value = "\nReturn from vsievt -11"
        vlan_ret = self.lldpad.send_vdp_vnic_up(port_uuid=self.uuid,
                                                vsiid=self.vsiid,
                                                mgrid=self.mgrid,
                                                typeid=self.typeid,
                                                typeid_ver=self.typeidver,
                                                gid=self.gid,
                                                mac=self.mac,
                                                new_network=True)
        self._test_vnic_assert(expected_vlan, vlan_ret[0], self.filter_str,
                               True, parent)

    def test_vdp_port_up_old_nwk(self):
        '''Tests the case when a VM comes for an existing network '''
        parent = mock.MagicMock()
        parent.attach_mock(self.execute, 'execute')
        self.execute.return_value = ("Response from VDP\n\tmode = assoc\n\t"
                                     "mgrid2 = 0\n\ttypeid = 0\n\t"
                                     "typeidver = 0\n\tuuid = 00000000-1111-"
                                     "2222-3333-444455556666\n\t"
                                     "filter = 3003-00:12:22:33:44:55-0\n")
        filter_str = "filter=0-00:11:22:33:44:55-20000"
        stored_vlan = 3003
        self.lldpad.send_vdp_vnic_up(port_uuid=self.uuid, vsiid=self.vsiid,
                                     mgrid=self.mgrid,
                                     typeid=self.typeid,
                                     typeid_ver=self.typeidver,
                                     gid=self.gid,
                                     mac=self.mac, vlan=0,
                                     new_network=False)
        self._test_vnic_assert(stored_vlan,
                               self.lldpad.vdp_vif_map[self.uuid].
                               get('vdp_vlan'), filter_str, False, parent)

    def test_vdp_port_down(self):
        '''Tests the case when a VM goes down '''
        parent = mock.MagicMock()
        parent.attach_mock(self.execute, 'execute')
        filter_str = "filter=100-00:11:22:33:44:55-20000"
        stored_vlan = 100
        mode_str = "mode=deassoc"
        self.lldpad.send_vdp_vnic_down(port_uuid=self.uuid, vsiid=self.vsiid,
                                       mgrid=self.mgrid,
                                       typeid=self.typeid,
                                       typeid_ver=self.typeidver,
                                       gid=self.gid,
                                       mac=self.mac, vlan=stored_vlan)
        self.execute.assert_called_with(
            ["vdptool", "-T", "-i", self.port_str,
             "-V", "deassoc", "-c", mode_str, "-c", self.mgrid_str,
             "-c", self.typeid_str, "-c", self.typeidver_str,
             "-c", self.vsiid_str, "-c", "hints=none",
             "-c", filter_str], root_helper=self.root_helper)
        self.assertNotIn(self.uuid, self.lldpad.vdp_vif_map)
