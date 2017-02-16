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

from oslo_serialization import jsonutils

import mock

from neutron.tests import base

from networking_cisco.apps.saf.agent.vdp import dfa_vdp_mgr
from networking_cisco.apps.saf.agent.vdp import ovs_vdp
from networking_cisco.apps.saf.common import constants
from networking_cisco.apps.saf.common import dfa_sys_lib as utils
from networking_cisco.apps.saf.common import utils as common_utils

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
        mock.patch('time.sleep').start()
        self.topo_disc = mock.patch(
            'networking_cisco.apps.saf.agent.topo_disc.topo_disc.'
            'TopoDisc').start()
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
                                    segmentation_id=10001, status=status,
                                    oui=None, phy_uplink=self.uplink)
        return msg

    def _setup_bulk_vm_msg(self, status):
        """construct the Bulk VM message. """
        vm_dict = self._construct_vm_dict(status)
        msg = dfa_vdp_mgr.VdpQueMsg(constants.VM_BULK_SYNC_MSG_TYPE,
                                    vm_bulk_list=[vm_dict],
                                    phy_uplink=self.uplink)
        return msg

    def _construct_vm_dict(self, status):
        """Construct a sample VM dict. """
        vm_dict = {'status': status, 'port_uuid': '0000-1111-2222-3333',
                   'vm_mac': '00:00:fa:11:22:33',
                   'net_uuid': '0000-aaaa-bbbb-cccc', 'vdp_vlan': 3005,
                   'segmentation_id': 10001, 'oui': None, 'local_vlan': 10,
                   'phy_uplink': self.uplink}
        return vm_dict

    def _test_process_up_uplink_event(self):
        '''Test routine when a uplink is detected '''
        msg = self._setup_uplink_msg('up')
        self.dfa_vdp_mgr.phy_uplink = self.uplink
        with mock.patch('networking_cisco.apps.saf.agent.'
                        'vdp.ovs_vdp.OVSNeutronVdp') as ovs_vdp_fn, \
            mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as (
                save_uplink_fn), \
            mock.patch.object(
                self.dfa_vdp_mgr.topo_disc, 'uncfg_intf') as uncfg_intf_fn, \
            mock.patch.object(
                self.dfa_vdp_mgr.topo_disc, 'cfg_intf') as cfg_intf_fn:
            self.dfa_vdp_mgr.process_uplink_event(msg, self.uplink)
        veth_val = self.dfa_vdp_mgr.ovs_vdp_obj_dict[
            self.uplink].get_lldp_local_bridge_port()
        ovs_vdp_fn.assert_called_with(self.uplink, self.br_integ, self.br_ex,
                                      self.root_helper,
                                      self.dfa_vdp_mgr.vdp_vlan_change_cb)
        save_uplink_fn.assert_called_with(
            uplink=self.uplink, veth_intf=veth_val)
        uncfg_intf_fn.assert_called_with(self.uplink)
        cfg_intf_fn.assert_called_with(
            self.dfa_vdp_mgr.ovs_vdp_obj_dict[
                self.uplink].get_lldp_local_bridge_port(),
            phy_interface=self.uplink)

    def test_process_up_uplink_event_lldp_fail(self):
        """Test routine when a uplink is detected and lldp is down. """
        msg = self._setup_uplink_msg('up')
        self.dfa_vdp_mgr.phy_uplink = self.uplink
        with mock.patch('networking_cisco.apps.saf.agent.'
                        'vdp.ovs_vdp.OVSNeutronVdp') as ovs_vdp_fn, \
            mock.patch.object(self.dfa_vdp_mgr.err_que, 'enqueue') as enq, \
            mock.patch.object(
                self.dfa_vdp_mgr, 'save_uplink') as save_uplink_fn:
            ovs_vdp_fn.return_value.is_lldpad_setup_done.return_value = False
            ovs_vdp_fn.return_value.get_uplink_fail_reason.return_value = (
                'Some Reason')
            self.dfa_vdp_mgr.process_uplink_event(msg, self.uplink)
        ovs_vdp_fn.assert_called_with(self.uplink, self.br_integ, self.br_ex,
                                      self.root_helper,
                                      self.dfa_vdp_mgr.vdp_vlan_change_cb)
        save_uplink_fn.assert_called_with(
            uplink=self.uplink, fail_reason='Some Reason')
        enq.assert_called_with(constants.Q_UPL_PRIO, msg)

    def _test_process_down_uplink_event(self):
        '''Test routine when a uplink goes down '''
        msg = self._setup_uplink_msg('down')
        self.dfa_vdp_mgr.phy_uplink = self.uplink
        del_flow = mock.patch.object(
            ovs_vdp, "delete_uplink_and_flows",
            spec=ovs_vdp.delete_uplink_and_flows).start()
        with mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as sav_fn, \
            mock.patch.object(
                self.dfa_vdp_mgr.topo_disc, 'uncfg_intf') as uncfg_intf_fn, \
            mock.patch.object(
                self.dfa_vdp_mgr.topo_disc, 'cfg_intf') as cfg_intf_fn:
            parent = mock.MagicMock()
            parent.attach_mock(del_flow, 'delete_uplink_and_flows')
            parent.attach_mock(uncfg_intf_fn, 'uncfg_intf')
            parent.attach_mock(cfg_intf_fn, 'cfg_intf')
            self.dfa_vdp_mgr.process_uplink_event(msg, self.uplink)
        expected_call = [mock.call.delete_uplink_and_flows(self.root_helper,
                                                           self.br_ex,
                                                           self.uplink),
                         mock.call.uncfg_intf(None),
                         mock.call.cfg_intf(self.uplink)]
        parent.assert_has_calls(expected_call)
        sav_fn.assert_called_with()

    def _test_process_down_uplink_event_clear(self):
        '''Test routine when a uplink goes down and flow is cleared '''
        msg = self._setup_uplink_msg('down')
        self.dfa_vdp_mgr.phy_uplink = self.uplink
        self.dfa_vdp_mgr.ovs_vdp_obj_dict = {}
        self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink] = mock.Mock()
        with mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                               'clear_obj_params') as vdp_clear_fn, \
            mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as sav_fn, \
            mock.patch.object(
                self.dfa_vdp_mgr.topo_disc, 'uncfg_intf') as uncfg_intf_fn, \
            mock.patch.object(
                self.dfa_vdp_mgr.topo_disc, 'cfg_intf') as cfg_intf_fn:
            self.dfa_vdp_mgr.process_uplink_event(msg, self.uplink)
        vdp_clear_fn.assert_called_with()
        sav_fn.assert_called_with()
        uncfg_intf_fn.assert_called_with(None)
        cfg_intf_fn.assert_called_with(self.uplink)

    def _test_process_vm_event_succ(self):
        '''Test routine for VM event process is successful '''
        msg = self._setup_vm_msg('up')
        lvid = 10
        vdp_vlan = 3000
        self.dfa_vdp_mgr.uplink_det_compl = True
        port_reply = {'result': True, 'fail_reason': None}
        self.dfa_vdp_mgr.ovs_vdp_obj_dict = {self.uplink: mock.Mock()}
        with mock.patch.object(
            self.dfa_vdp_mgr, 'update_vm_result') as save_vmres_fn, \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'send_vdp_port_event',
                              return_value=port_reply), \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'get_lvid_vdp_vlan',
                              return_value=[lvid, vdp_vlan]):
            self.dfa_vdp_mgr.process_vm_event(msg, self.uplink)
        save_vmres_fn.assert_called_with('0000-1111-2222-3333', 'SUCCESS',
                                         fail_reason=None, lvid=lvid,
                                         vdp_vlan=vdp_vlan)

    def _test_process_vm_event_fail(self):
        '''Test routine for VM event process has failed '''
        msg = self._setup_vm_msg('up')
        self.dfa_vdp_mgr.uplink_det_compl = True
        self.dfa_vdp_mgr.ovs_vdp_obj_dict = {self.uplink: mock.Mock()}
        port_reply = {'result': False, 'fail_reason': 'some reason'}
        with mock.patch.object(
            self.dfa_vdp_mgr, 'update_vm_result') as save_vmres_fn, \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'send_vdp_port_event',
                              return_value=port_reply):
            self.dfa_vdp_mgr.process_vm_event(msg, self.uplink)
        save_vmres_fn.assert_called_with('0000-1111-2222-3333', 'CREATE:FAIL',
                                         fail_reason='some reason')

    def test_process_vm_event_uplink_not_rcvd(self):
        """Test for VM event process, when uplink event is not received. """
        msg = self._setup_vm_msg('up')
        self.dfa_vdp_mgr.uplink_det_compl = True
        with mock.patch.object(self.dfa_vdp_mgr, 'update_vm_result') as \
                save_vmres_fn:
            self.dfa_vdp_mgr.process_vm_event(msg, self.uplink)
        save_vmres_fn.assert_called_with('0000-1111-2222-3333', 'CREATE:FAIL')

    def test_process_vm_down_event_uplink_not_rcvd(self):
        """Test for VM down event, when uplink event is not received. """
        msg = self._setup_vm_msg('down')
        self.dfa_vdp_mgr.uplink_det_compl = True
        with mock.patch.object(self.dfa_vdp_mgr, 'update_vm_result') as \
                save_vmres_fn:
            self.dfa_vdp_mgr.process_vm_event(msg, self.uplink)
        save_vmres_fn.assert_called_with('0000-1111-2222-3333', 'DELETE:FAIL')

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

    def test_vdp_vlan_change_cb(self):
        """Function to test the VDP VLAN change Callback. """
        port_uuid = '0000-1111-2222-3333'
        lvid = 10
        vdp_vlan = 3000
        with mock.patch.object(self.dfa_vdp_mgr, 'update_vm_result') as \
                save_vmres_fn:
            self.dfa_vdp_mgr.vdp_vlan_change_cb(port_uuid, lvid, vdp_vlan,
                                                'some reason')
        save_vmres_fn.assert_called_with('0000-1111-2222-3333', 'SUCCESS',
                                         lvid=lvid, vdp_vlan=vdp_vlan,
                                         fail_reason='some reason')

    def _test_setup_uplink_params_steady(self):
        """Internal function to setup the DFA VDP Mgr parameters. """
        self.dfa_vdp_mgr.is_os_run = True
        self.dfa_vdp_mgr.restart_uplink_called = True
        self.dfa_vdp_mgr.process_uplink_ongoing = False
        self.dfa_vdp_mgr.uplink_det_compl = False
        self.dfa_vdp_mgr.static_uplink = False
        self.dfa_vdp_mgr.phy_uplink = self.uplink
        self.dfa_vdp_mgr.ovs_vdp_obj_dict = {self.uplink: mock.Mock()}

    def test_vdp_uplink_proc_down_threshold_exceed(self):
        """Test VDP uplink proc for down case, when threshold exceed. """
        self._test_setup_uplink_params_steady()
        self.dfa_vdp_mgr.uplink_down_cnt = 3
        with mock.patch('networking_cisco.apps.saf.agent.detect_uplink.'
                        'detect_uplink', return_value='down'), \
            mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                       'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch.object(self.dfa_vdp_mgr.que, 'enqueue') as enq, \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'get_lldp_local_bridge_port',
                              return_value='veth_eth1'):
            self.dfa_vdp_mgr.vdp_uplink_proc()
        vdp_que.assert_called_with(
            constants.UPLINK_MSG_TYPE, status='down',
            phy_uplink=self.uplink, br_int=self.dfa_vdp_mgr.br_integ,
            br_ex=self.dfa_vdp_mgr.br_ex,
            root_helper=self.dfa_vdp_mgr.root_helper)
        enq.assert_called_with(constants.Q_UPL_PRIO, 'some obj')

    def test_vdp_uplink_proc_down_threshold_not_exceed(self):
        """Test VDP uplink proc for down case, when threshold not exceed. """
        self._test_setup_uplink_params_steady()
        self.dfa_vdp_mgr.uplink_down_cnt = 1
        with mock.patch('networking_cisco.apps.saf.agent.detect_uplink.'
                        'detect_uplink', return_value='down'), \
            mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                       'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch.object(self.dfa_vdp_mgr.que, 'enqueue') as enq, \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'get_lldp_local_bridge_port',
                              return_value='veth_eth1'):
            self.dfa_vdp_mgr.vdp_uplink_proc()
        vdp_que.assert_not_called()
        enq.assert_not_called()

    def test_vdp_uplink_proc_none(self):
        """Test VDP uplink proc for none case. """
        self._test_setup_uplink_params_steady()
        with mock.patch('networking_cisco.apps.saf.agent.detect_uplink.'
                        'detect_uplink', return_value=None), \
            mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                       'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'get_lldp_local_bridge_port',
                              return_value=None), \
            mock.patch.object(self.dfa_vdp_mgr.que, 'enqueue') as enq, \
            mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as (
                save_uplink_fn):
            self.dfa_vdp_mgr.vdp_uplink_proc()
        vdp_que.assert_not_called()
        enq.assert_not_called()
        save_uplink_fn.assert_called_with(
            fail_reason=constants.uplink_undiscovered_reason)

    def test_vdp_uplink_proc_normal(self):
        """Test VDP uplink proc for normal case. """
        self._test_setup_uplink_params_steady()
        with mock.patch('networking_cisco.apps.saf.agent.detect_uplink.'
                        'detect_uplink', return_value='normal'), \
            mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                       'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch('networking_cisco.apps.saf.common.dfa_sys_lib.'
                       'get_bond_intf', return_value=None), \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'get_lldp_local_bridge_port',
                              return_value='veth_eth1'), \
            mock.patch.object(self.dfa_vdp_mgr.que, 'enqueue') as enq, \
            mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as (
                save_uplink_fn):
            self.dfa_vdp_mgr.vdp_uplink_proc()
        vdp_que.assert_called_with(
            constants.UPLINK_MSG_TYPE, status='up',
            phy_uplink=self.uplink, br_int=self.dfa_vdp_mgr.br_integ,
            br_ex=self.dfa_vdp_mgr.br_ex,
            root_helper=self.dfa_vdp_mgr.root_helper)
        enq.assert_called_with(constants.Q_UPL_PRIO, 'some obj')
        save_uplink_fn.assert_not_called()

    def test_vdp_uplink_proc_normal_static(self):
        """Test VDP uplink proc for normal case for static uplink. """
        self._test_setup_uplink_params_steady()
        self.dfa_vdp_mgr.static_uplink = True
        with mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                        'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch('networking_cisco.apps.saf.common.dfa_sys_lib.'
                       'get_bond_intf', return_value=None), \
            mock.patch.object(self.dfa_vdp_mgr, 'static_uplink_detect',
                              return_value='normal'), \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'get_lldp_local_bridge_port',
                              return_value='veth_eth1'), \
            mock.patch.object(self.dfa_vdp_mgr.que, 'enqueue') as enq, \
            mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as (
                save_uplink_fn):
            self.dfa_vdp_mgr.vdp_uplink_proc()
        vdp_que.assert_called_with(
            constants.UPLINK_MSG_TYPE, status='up',
            phy_uplink=self.uplink, br_int=self.dfa_vdp_mgr.br_integ,
            br_ex=self.dfa_vdp_mgr.br_ex,
            root_helper=self.dfa_vdp_mgr.root_helper)
        enq.assert_called_with(constants.Q_UPL_PRIO, 'some obj')
        save_uplink_fn.assert_not_called()

    def test_vdp_uplink_proc_normal_bulk_vm_not_rcvd(self):
        """Test VDP uplink proc for normal case, for bulk VM.

        This is for the case when bulk VM notificationis not received.
        """
        self._test_setup_uplink_params_steady()
        self.dfa_vdp_mgr.bulk_vm_rcvd_flag = False
        self.dfa_vdp_mgr.bulk_vm_check_cnt = 2
        with mock.patch('networking_cisco.apps.saf.agent.detect_uplink.'
                        'detect_uplink', return_value='normal'), \
            mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                       'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch('networking_cisco.apps.saf.common.dfa_sys_lib.'
                       'get_bond_intf', return_value=None), \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'get_lldp_local_bridge_port',
                              return_value='veth_eth1'), \
            mock.patch.object(self.dfa_vdp_mgr.que, 'enqueue') as enq, \
            mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as (
                save_uplink_fn):
            self.dfa_vdp_mgr.vdp_uplink_proc()
        vdp_que.assert_called_with(
            constants.UPLINK_MSG_TYPE, status='up',
            phy_uplink=self.uplink, br_int=self.dfa_vdp_mgr.br_integ,
            br_ex=self.dfa_vdp_mgr.br_ex,
            root_helper=self.dfa_vdp_mgr.root_helper)
        enq.assert_called_with(constants.Q_UPL_PRIO, 'some obj')
        save_uplink_fn.assert_called_with(uplink=self.uplink,
                                          veth_intf='veth_eth1')

    def test_vdp_uplink_proc_normal_bond_intf(self):
        """Test VDP uplink proc for normal case, for bond interface. """
        self._test_setup_uplink_params_steady()
        with mock.patch('networking_cisco.apps.saf.agent.detect_uplink.'
                        'detect_uplink', return_value='normal'), \
            mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                       'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch('networking_cisco.apps.saf.common.dfa_sys_lib.'
                       'get_bond_intf', return_value='bond0'), \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'get_lldp_local_bridge_port',
                              return_value='veth_eth1'), \
            mock.patch.object(self.dfa_vdp_mgr.que, 'enqueue') as enq, \
            mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as (
                save_uplink_fn):
            parent = mock.MagicMock()
            parent.attach_mock(save_uplink_fn, 'save_uplink')
            parent.attach_mock(vdp_que, 'VdpQueMsg')
            parent.attach_mock(enq, 'enqueue')
            self.dfa_vdp_mgr.vdp_uplink_proc()
        expected_calls = [
            mock.call.save_uplink(
                fail_reason=constants.port_transition_bond_down_reason),
            mock.call.VdpQueMsg(
                constants.UPLINK_MSG_TYPE, status='down',
                phy_uplink=self.uplink, br_int=self.dfa_vdp_mgr.br_integ,
                br_ex=self.dfa_vdp_mgr.br_ex,
                root_helper=self.dfa_vdp_mgr.root_helper),
            mock.call.enqueue(1, 'some obj'),
            mock.call.save_uplink(
                fail_reason=constants.port_transition_bond_up_reason,
                uplink='bond0'),
            mock.call.VdpQueMsg(
                constants.UPLINK_MSG_TYPE, status='up',
                phy_uplink='bond0', br_int=self.dfa_vdp_mgr.br_integ,
                br_ex=self.dfa_vdp_mgr.br_ex,
                root_helper=self.dfa_vdp_mgr.root_helper),
            mock.call.enqueue(1, 'some obj')]
        parent.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual('bond0', self.dfa_vdp_mgr.phy_uplink)
        self.assertTrue(self.dfa_vdp_mgr.process_uplink_ongoing)
        self.assertFalse(self.dfa_vdp_mgr.uplink_det_compl)

    def test_vdp_uplink_proc_new_uplink(self):
        """Test VDP uplink proc for a new uplink case. """
        self._test_setup_uplink_params_steady()
        with mock.patch('networking_cisco.apps.saf.agent.detect_uplink.'
                        'detect_uplink', return_value='eth4'), \
            mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                       'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'get_lldp_local_bridge_port',
                              return_value='veth_eth1'), \
            mock.patch.object(self.dfa_vdp_mgr.que, 'enqueue') as enq, \
            mock.patch.object(self.dfa_vdp_mgr, 'save_uplink') as (
                save_uplink_fn):
            self.dfa_vdp_mgr.vdp_uplink_proc()
        vdp_que.assert_called_with(
            constants.UPLINK_MSG_TYPE, status='up',
            phy_uplink='eth4', br_int=self.dfa_vdp_mgr.br_integ,
            br_ex=self.dfa_vdp_mgr.br_ex,
            root_helper=self.dfa_vdp_mgr.root_helper)
        enq.assert_called_with(constants.Q_UPL_PRIO, 'some obj')
        save_uplink_fn.assert_called_with(uplink='eth4', veth_intf='veth_eth1')
        self.assertTrue(self.dfa_vdp_mgr.process_uplink_ongoing)
        self.assertEqual('eth4', self.dfa_vdp_mgr.phy_uplink)

    def test_process_bulk_vm_event_up(self):
        "Test Bulk Process event for up status. """
        msg = self._setup_bulk_vm_msg('up')
        self.dfa_vdp_mgr.ovs_vdp_obj_dict = {}
        self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink] = mock.Mock()
        with mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                        'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch.object(self.dfa_vdp_mgr,
                              'process_vm_event') as process_vm_event:
            self.dfa_vdp_mgr.uplink_det_compl = True
            self.dfa_vdp_mgr.process_bulk_vm_event(msg, self.uplink)
        vm_dict = self._construct_vm_dict('up')
        vdp_que.assert_called_with(
            constants.VM_MSG_TYPE, port_uuid=vm_dict['port_uuid'],
            vm_mac=vm_dict['vm_mac'], net_uuid=vm_dict['net_uuid'],
            segmentation_id=vm_dict['segmentation_id'],
            status=vm_dict['status'], oui=vm_dict['oui'],
            phy_uplink=self.uplink)
        process_vm_event.assert_called_with('some obj', self.uplink)

    def test_process_bulk_vm_event_down(self):
        "Test Bulk Process event for down status. """
        msg = self._setup_bulk_vm_msg('down')
        self.dfa_vdp_mgr.ovs_vdp_obj_dict = {}
        self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink] = mock.Mock()
        with mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                        'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch.object(self.dfa_vdp_mgr.ovs_vdp_obj_dict[self.uplink],
                              'pop_local_cache') as pop_ovs_cache, \
            mock.patch.object(self.dfa_vdp_mgr,
                              'process_vm_event') as process_vm_event:
            self.dfa_vdp_mgr.uplink_det_compl = True
            self.dfa_vdp_mgr.process_bulk_vm_event(msg, self.uplink)
        vm_dict = self._construct_vm_dict('down')
        pop_ovs_cache.assert_called_with(
            vm_dict['port_uuid'], vm_dict['vm_mac'], vm_dict['net_uuid'],
            vm_dict['local_vlan'], vm_dict['vdp_vlan'],
            vm_dict['segmentation_id'])
        vdp_que.assert_called_with(
            constants.VM_MSG_TYPE, port_uuid=vm_dict['port_uuid'],
            vm_mac=vm_dict['vm_mac'], net_uuid=vm_dict['net_uuid'],
            segmentation_id=vm_dict['segmentation_id'],
            status=vm_dict['status'], oui=vm_dict['oui'],
            phy_uplink=self.uplink)
        process_vm_event.assert_called_with('some obj', self.uplink)

    def test_vdp_vm_event_dict(self):
        """Test for VM event, when input is a VM dict. """
        vm_dict = self._construct_vm_dict('up')
        self.dfa_vdp_mgr.phy_uplink = self.uplink
        with mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                        'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch.object(self.dfa_vdp_mgr.que, 'enqueue') as enq, \
            mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                       'VdpQueMsg', return_value='some obj') as vdp_que:
            self.dfa_vdp_mgr.vdp_vm_event(vm_dict)
        vdp_que.assert_called_with(
            constants.VM_MSG_TYPE, port_uuid=vm_dict['port_uuid'],
            vm_mac=vm_dict['vm_mac'], net_uuid=vm_dict['net_uuid'],
            segmentation_id=vm_dict['segmentation_id'],
            status=vm_dict['status'], oui=vm_dict['oui'],
            phy_uplink=self.uplink)
        enq.assert_called_with(constants.Q_VM_PRIO, 'some obj')

    def test_vdp_vm_event_list(self):
        """Test for VM event, when input is a VM dict list. """
        vm_dict = self._construct_vm_dict('up')
        self.dfa_vdp_mgr.phy_uplink = self.uplink
        with mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                        'VdpQueMsg', return_value='some obj') as vdp_que, \
            mock.patch.object(self.dfa_vdp_mgr.que, 'enqueue') as enq, \
            mock.patch('networking_cisco.apps.saf.agent.vdp.dfa_vdp_mgr.'
                       'VdpQueMsg', return_value='some obj') as vdp_que:
            self.dfa_vdp_mgr.vdp_vm_event([vm_dict])
        vdp_que.assert_called_with(
            constants.VM_BULK_SYNC_MSG_TYPE,
            vm_bulk_list=[vm_dict], phy_uplink=self.uplink)
        enq.assert_called_with(constants.Q_VM_PRIO, 'some obj')
        self.assertTrue(self.dfa_vdp_mgr.bulk_vm_rcvd_flag)

    def test_dfa_uplink_restart_no_uplink(self):
        """Test for DFA uplink restart case with no uplink. """
        uplink_dict = {}
        with mock.patch('networking_cisco.apps.saf.agent.vdp.ovs_vdp.'
                        'delete_uplink_and_flows') as ovs_del_flow:
            self.dfa_vdp_mgr.dfa_uplink_restart(uplink_dict)
        self.assertTrue(self.dfa_vdp_mgr.restart_uplink_called)
        ovs_del_flow.assert_not_called()

    def test_dfa_uplink_restart_valid_uplink_veth(self):
        """Test for DFA uplink restart case with valid uplink/veth. """
        uplink_dict = {'uplink': self.uplink, 'veth_intf': 'veth_eth1'}
        with mock.patch('networking_cisco.apps.saf.agent.vdp.ovs_vdp.'
                        'delete_uplink_and_flows') as ovs_del_flow:
            self.dfa_vdp_mgr.dfa_uplink_restart(uplink_dict)
        self.assertTrue(self.dfa_vdp_mgr.restart_uplink_called)
        self.assertEqual(self.uplink, self.dfa_vdp_mgr.phy_uplink)
        self.assertEqual('veth_eth1', self.dfa_vdp_mgr.veth_intf)
        ovs_del_flow.assert_not_called()

    def test_dfa_uplink_restart_invalid_veth(self):
        """Test for DFA uplink restart case with invalid veth. """
        uplink_dict = {'uplink': self.uplink}
        with mock.patch('networking_cisco.apps.saf.agent.vdp.ovs_vdp.'
                        'delete_uplink_and_flows') as ovs_del_flow:
            self.dfa_vdp_mgr.dfa_uplink_restart(uplink_dict)
        self.assertTrue(self.dfa_vdp_mgr.restart_uplink_called)
        ovs_del_flow.assert_called_with(
            self.dfa_vdp_mgr.root_helper, self.dfa_vdp_mgr.br_ex, self.uplink)

    def _get_topo_disc_arg(self):
        """Fill the argument to topology discovery. """
        return {'phy_interface': self.uplink, 'remote_evb_cfgd': True,
                'remote_evb_mode': 'bridge', 'remote_mgmt_addr': '10.1.1.1',
                'remote_system_desc': 'Cisco Test Os',
                'remote_system_name': 'N6K-1', 'remote_port': 'e2/1',
                'remote_chassis_id_mac': '00:11:22:33:44:55',
                'remote_port_id_mac': '00:22:33:44:55:66'}

    def _get_topo_dict_final(self):
        """Fill the argument to topology discovery for final check. """
        return {'host': None, 'protocol_interface': self.uplink,
                'heartbeat': 'Jan 1',
                'phy_interface': self.uplink, 'remote_evb_cfgd': True,
                'remote_evb_mode': 'bridge',
                'remote_mgmt_addr': '10.1.1.1',
                'remote_system_desc': 'Cisco Test Os',
                'remote_system_name': 'N6K-1', 'remote_port': 'e2/1',
                'remote_chassis_id_mac': '00:11:22:33:44:55',
                'remote_port_id_mac': '00:22:33:44:55:66',
                'configurations': jsonutils.dumps({})}

    def test_topo_disc_cb(self):
        """Test the topology discovery CB function. """
        topo_dict = self._get_topo_disc_arg()
        topo_dict_final = self._get_topo_dict_final()
        topo_obj = common_utils.Dict2Obj(topo_dict)
        with mock.patch('time.ctime') as ctime_fn:
            ctime_fn.return_value = 'Jan 1'
            self.dfa_vdp_mgr.topo_disc_cb(self.uplink, topo_obj)
        self.rpc_client.make_msg.assert_called_with(
            'save_topo_disc_params', {}, msg=jsonutils.dumps(topo_dict_final))
