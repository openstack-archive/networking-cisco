# Copyright 2015 Cisco Systems.
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

from networking_cisco.apps.saf.agent.vdp import dfa_vdp_mgr
from networking_cisco.apps.saf.agent.vdp import ovs_vdp
from networking_cisco.apps.saf.common import constants
from networking_cisco.apps.saf.common import dfa_sys_lib as utils

try:
    OrderedDict = collections.OrderedDict
except AttributeError:
    import ordereddict
    OrderedDict = ordereddict.OrderedDict


class DfaVdpMgrTest(base.BaseTestCase):
    """A test suite to exercise the DfaVdpMgr Class.  """

    def setUp(self):
        '''Setup routine '''
        super(DfaVdpMgrTest, self).setUp()
        self.root_helper = 'sudo'
        self.port_name = "loc_veth"
        self.uplink = "eth2"
        self.port_str = "loc_veth_eth2"
        self.br_integ = 'br-int1'
        self.br_ex = 'br-ethd1'
        self.rpc_client = mock.Mock()
        self.host = 'hostabc'
        self.config_dict = {'integration_bridge': self.br_integ,
                            'external_bridge': self.br_ex,
                            'root_helper': self.root_helper,
                            'node_list': 'hostabc',
                            'node_uplink_list': self.uplink}
        self.execute = mock.patch.object(
            utils, "execute", spec=utils.execute).start()
        self._test_dfa_mgr_init()

    def _test_dfa_mgr_init(self):
        '''Test routine for init '''
        with mock.patch('networking_cisco.apps.saf.common.utils.'
                        'EventProcessingThread') as event_fn,\
                mock.patch('networking_cisco.apps.saf.common.'
                           'utils.PeriodicTask') as period_fn:
            event_obj = event_fn.return_value
            period_obj = period_fn.return_value
            parent = mock.MagicMock()
            parent.attach_mock(event_obj.start, 'start')
            parent.attach_mock(period_obj.run, 'run')
            self.dfa_vdp_mgr = dfa_vdp_mgr.VdpMgr(self.config_dict,
                                                  self.rpc_client,
                                                  self.host)
        event_fn.assert_called_with("VDP_Mgr", self.dfa_vdp_mgr,
                                    'process_queue')
        period_fn.assert_any_call(constants.ERR_PROC_INTERVAL,
                                  self.dfa_vdp_mgr.process_err_queue)
        period_fn.assert_any_call(constants.UPLINK_DET_INTERVAL,
                                  self.dfa_vdp_mgr.vdp_uplink_proc_top)
        expected_calls = [mock.call.start(), mock.call.run(), mock.call.run()]
        parent.assert_has_calls(expected_calls)

    def _setup_uplink_msg(self, status):
        '''construct the uplink message '''
        msg = dfa_vdp_mgr.VdpQueMsg(constants.UPLINK_MSG_TYPE, status=status,
                                    phy_uplink=self.uplink,
                                    br_int=self.br_integ,
                                    br_ex=self.br_ex,
                                    root_helper=self.root_helper)
        return msg

    def _setup_vm_msg(self, status):
        '''construct the VM message '''
        msg = dfa_vdp_mgr.VdpQueMsg(constants.VM_MSG_TYPE,
                                    port_uuid='0000-1111-2222-3333',
                                    vm_mac='00:00:fa:11:22:33',
                                    net_uuid='0000-aaaa-bbbb-cccc',
                                    segmentation_id=10001, status='up',
                                    oui=None, phy_uplink=self.uplink)
        return msg

    def _test_process_up_uplink_event(self):
        '''Test routine when a uplink is detected '''
        msg = self._setup_uplink_msg('up')
        self.dfa_vdp_mgr.phy_uplink = self.uplink
        with mock.patch('networking_cisco.apps.saf.agent.'
                        'vdp.ovs_vdp.OVSNeutronVdp') as ovs_vdp_fn, \
            mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as (
                save_uplink_fn):
            self.dfa_vdp_mgr.process_uplink_event(msg, self.uplink)
        ovs_vdp_obj = ovs_vdp_fn.return_value
        ovs_vdp_fn.assert_called_with(self.uplink, self.br_integ, self.br_ex,
                                      self.root_helper)
        save_uplink_fn.assert_called_with(
            uplink=self.uplink, veth_intf=ovs_vdp_obj.get_lldp_bridge_port())

    def _test_process_down_uplink_event(self):
        '''Test routine when a uplink goes down '''
        msg = self._setup_uplink_msg('down')
        self.dfa_vdp_mgr.phy_uplink = self.uplink
        del_flow = mock.patch.object(
            ovs_vdp, "delete_uplink_and_flows",
            spec=ovs_vdp.delete_uplink_and_flows).start()
        with mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as sav_fn:
            parent = mock.MagicMock()
            parent.attach_mock(del_flow, 'delete_uplink_and_flows')
            self.dfa_vdp_mgr.process_uplink_event(msg, self.uplink)
        expected_call = [mock.call.delete_uplink_and_flows(self.root_helper,
                                                           self.br_ex,
                                                           self.uplink)]
        parent.assert_has_calls(expected_call)
        sav_fn.assert_called_with()

    def _test_process_down_uplink_event_clear(self):
        '''Test routine when a uplink goes down and flow is cleared '''
        msg = self._setup_uplink_msg('down')
        self.dfa_vdp_mgr.phy_uplink = self.uplink
        self.dfa_vdp_mgr.ovs_vdp_obj_dict = {}
        self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink] = mock.Mock()
        with mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                               'clear_obj_params') as neut_vdp_clear_fn, \
                mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as sav_fn:
            self.dfa_vdp_mgr.process_uplink_event(msg, self.uplink)
        neut_vdp_clear_fn.assert_called_with()
        sav_fn.assert_called_with()

    def _test_process_vm_event_succ(self):
        '''Test routine for VM event process is successful '''
        msg = self._setup_vm_msg('up')
        self.dfa_vdp_mgr.uplink_det_compl = True
        self.dfa_vdp_mgr.ovs_vdp_obj_dict = {}
        self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink] = mock.Mock()
        with mock.patch.object(self.dfa_vdp_mgr, 'update_vm_result') as \
                save_vmres_fn:
            self.dfa_vdp_mgr.process_vm_event(msg, self.uplink)
        save_vmres_fn.assert_called_with('0000-1111-2222-3333', 'SUCCESS')

    def _test_process_vm_event_fail(self):
        '''Test routine for VM event process has failed '''
        msg = self._setup_vm_msg('up')
        self.dfa_vdp_mgr.uplink_det_compl = True
        with mock.patch.object(self.dfa_vdp_mgr, 'update_vm_result') as \
                save_vmres_fn:
            self.dfa_vdp_mgr.process_vm_event(msg, self.uplink)
        save_vmres_fn.assert_called_with('0000-1111-2222-3333', 'CREATE:FAIL')

    def test_process_uplink_event_case1(self):
        '''Top routine that calls the uplink down case '''
        self._test_process_down_uplink_event()

    def test_process_uplink_event_case2(self):
        '''Top routine that calls the uplink detect case '''
        self._test_process_up_uplink_event()
        self._test_process_down_uplink_event_clear()

    def test_process_vm_event_succ(self):
        '''Top routine that calls process VM event success case '''
        self._test_process_vm_event_succ()

    def test_process_vm_event_fail(self):
        '''Top routine that calls process VM event fail case '''
        self._test_process_vm_event_fail()

    def test_process_static_uplink_new(self):
        """Test routine for static uplink, first time call."""
        ret = self.dfa_vdp_mgr.static_uplink_detect(None)
        self.assertEqual(ret, self.uplink)

    def test_process_static_uplink_normal(self):
        """Test routine for static uplink, normal case."""
        ret = self.dfa_vdp_mgr.static_uplink_detect('veth_temp')
        self.assertEqual(ret, 'normal')

    def test_process_static_uplink_down(self):
        """Test routine for static uplink, down case."""
        self.dfa_vdp_mgr.phy_uplink = 'eth3'
        ret = self.dfa_vdp_mgr.static_uplink_detect(None)
        self.assertEqual(ret, 'down')
