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

from oslotest import base

from networking_cisco.apps.saf.agent.vdp import ovs_vdp
from networking_cisco.apps.saf.agent.vdp import vdp_constants as vconstants
from networking_cisco.apps.saf.common import dfa_sys_lib as utils

try:
    OrderedDict = collections.OrderedDict
except AttributeError:
    import ordereddict
    OrderedDict = ordereddict.OrderedDict


class OvsVdpTest(base.BaseTestCase):
    """A test suite to exercise the OvsVdp Class.  """

    def setUp(self):
        '''Setup routine '''
        super(OvsVdpTest, self).setUp()
        self.root_helper = 'sudo'
        self.uplink = "eth2"
        self.integ_br = 'br-int1'
        self.ext_br = 'br-ethd1'

        self.port_name = "loc_veth"
        self.port_str = "loc_veth_eth2"
        self.rpc_client = mock.Mock()
        self.execute = mock.patch.object(
            utils, "execute", spec=utils.execute).start()
        self.addCleanup(mock.patch.stopall)
        self._test_ovs_vdp_init()
        phy_port_num = 5
        int_peer_port_num = 6
        self.port_uuid = '0000-1111-2222-3334'
        self.port_uuid_1 = '0000-1111-2222-3335'
        self.mac = '00:00:fa:11:22:34'
        self.net_uuid = '0000-aaaa-bbbb-cccc'
        self.segmentation_id = 10001
        self.lvid = 10
        self.exist_vdp_vlan = 3000
        self.oui = None
        self.ovs_vdp.phy_peer_port_num = phy_port_num
        self.ovs_vdp.int_peer_port_num = int_peer_port_num

    def _test_ovs_vdp_init(self):
        '''Test the init routine '''
        lldp_ovs_portnum = 14
        phy_port_num = 14
        get_br = mock.patch('networking_cisco.apps.saf.common.'
                            'dfa_sys_lib.get_bridges').start()
        is_patch = mock.patch('networking_cisco.apps.saf.common.'
                              'dfa_sys_lib.is_patch').start()
        get_peer = mock.patch('networking_cisco.apps.saf.common.'
                              'dfa_sys_lib.get_peer').start()
        self.ovs_br_add = mock.patch('networking_cisco.apps.saf.common.'
                                     'dfa_sys_lib.OVSBridge.add_flow').start()
        mock.patch('networking_cisco.apps.saf.common.'
                   'dfa_sys_lib.OVSBridge.add_port',
                   return_value=str(lldp_ovs_portnum)).start()
        mock.patch('networking_cisco.apps.saf.common.'
                   'dfa_sys_lib.OVSBridge.get_port_ofport',
                   return_value=str(phy_port_num)).start()
        port_name_list = mock.patch('networking_cisco.apps.saf.common.'
                                    'dfa_sys_lib.OVSBridge.'
                                    'get_port_name_list').start()
        dev_exist = mock.patch('neutron.agent.linux.ip_lib.'
                               'device_exists').start()
        add_veth = mock.patch('neutron.agent.linux.ip_lib.'
                              'IPWrapper.add_veth').start()
        mock.patch('networking_cisco.apps.saf.'
                   'agent.vdp.lldpad.LldpadDriver').start()
        mock.patch('networking_cisco.apps.saf.common.'
                   'utils.PeriodicTask').start()
        get_br.return_value = self.integ_br + ' ' + self.ext_br
        port_name_list.return_value = 'port_int1'
        is_patch.return_value = True
        get_peer.return_value = 'port_int1'
        dev_exist.return_value = False
        add_veth.return_value = mock.Mock(), mock.Mock()
        self.vdp_cb = mock.MagicMock()
        self.ovs_vdp = ovs_vdp.OVSNeutronVdp(self.uplink, self.integ_br,
                                             self.ext_br,
                                             self.root_helper, self.vdp_cb)
        self.ovs_br_add.reset_mock()

    def test_process_init(self):
        '''Wrapper for the init routine test '''
        pass

    def test_setup_lldpad_ports(self):
        """Test for setup lldpad ports. """
        lldp_ovs_portnum = 14
        phy_port_num = 14
        veth_str = vconstants.LLDPAD_LOC_VETH_PORT + self.uplink
        with mock.patch('networking_cisco.apps.saf.'
                        'agent.vdp.lldpad.LldpadDriver') as lldpad, \
            mock.patch('networking_cisco.apps.saf.common.dfa_sys_lib.'
                       'OVSBridge.delete_flows') as ovs_br_del:
            lldp_inst = lldpad.return_value
            parent = mock.MagicMock()
            parent.attach_mock(ovs_br_del, 'delete_flows')
            parent.attach_mock(self.ovs_br_add, 'add_flow')
            parent.attach_mock(lldp_inst.enable_evb, 'enable_evb')
            self.ovs_vdp.setup_lldpad_ports()
        expected_calls = [
            mock.call.delete_flows(dl_dst=vconstants.NCB_DMAC,
                                   dl_type=vconstants.LLDP_ETYPE),
            mock.call.delete_flows(dl_dst=vconstants.NCB_DMAC,
                                   dl_type=vconstants.VDP22_ETYPE),
            mock.call.add_flow(priority=vconstants.VDP_FLOW_PRIO,
                               in_port=str(lldp_ovs_portnum),
                               dl_dst=vconstants.NCB_DMAC,
                               dl_type=vconstants.LLDP_ETYPE,
                               actions="output:%s" % phy_port_num),
            mock.call.add_flow(priority=vconstants.VDP_FLOW_PRIO,
                               in_port=str(phy_port_num),
                               dl_dst=vconstants.NCB_DMAC,
                               dl_type=vconstants.LLDP_ETYPE,
                               actions="output:%s" % lldp_ovs_portnum),
            mock.call.add_flow(priority=vconstants.VDP_FLOW_PRIO,
                               in_port=str(lldp_ovs_portnum),
                               dl_dst=vconstants.NCB_DMAC,
                               dl_type=vconstants.VDP22_ETYPE,
                               actions="output:%s" % phy_port_num),
            mock.call.add_flow(priority=vconstants.VDP_FLOW_PRIO,
                               in_port=str(phy_port_num),
                               dl_dst=vconstants.NCB_DMAC,
                               dl_type=vconstants.VDP22_ETYPE,
                               actions="output:%s" % lldp_ovs_portnum),
            mock.call.enable_evb()]
        parent.assert_has_calls(expected_calls, any_order=False)
        lldpad.assert_called_with(veth_str, self.uplink, self.root_helper)

    def _test_vdp_port_event_new(self):
        '''Test the case for a new vnic port for a network '''
        port_uuid = '0000-1111-2222-3333'
        mac = '00:00:fa:11:22:33'
        net_uuid = '0000-aaaa-bbbb-cccc'
        segmentation_id = 10001
        status = 'up'
        oui = None
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.get_ofport_name',
                        return_value='test_port'), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.get_port_vlan_tag',
                       return_value=10), \
            mock.patch.object(self.ovs_vdp.lldpad_info, 'send_vdp_vnic_up',
                              return_value=[500, None]):
            parent = mock.MagicMock()
            parent.attach_mock(self.ovs_br_add, 'add_flow')
            self.ovs_vdp.send_vdp_port_event(port_uuid, mac, net_uuid,
                                             segmentation_id, status, oui)
        expected_calls = [
            mock.call.add_flow(priority=4,
                               in_port=self.ovs_vdp.phy_peer_port_num,
                               dl_vlan=10,
                               actions="mod_vlan_vid:%s,normal" % 500),
            mock.call.add_flow(priority=3,
                               in_port=self.ovs_vdp.int_peer_port_num,
                               dl_vlan=500,
                               actions="mod_vlan_vid:%s,normal" % 10)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def _test_vdp_port_event_exist(self):
        '''Test the case for a exist vnic port for a network '''
        port_uuid = '0000-1111-2222-3334'
        mac = '00:00:fa:11:22:34'
        net_uuid = '0000-aaaa-bbbb-cccc'
        segmentation_id = 10001
        status = 'up'
        oui = None
        ovs_cb_data = {'obj': self.ovs_vdp, 'mac': mac,
                       'port_uuid': port_uuid, 'net_uuid': net_uuid}
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.get_ofport_name',
                        return_value='test_port'), \
                mock.patch.object(self.ovs_vdp.lldpad_info,
                                  'send_vdp_vnic_up') as vnic_up:
            parent = mock.MagicMock()
            parent.attach_mock(vnic_up, 'send_vdp_vnic_up')
            self.ovs_vdp.send_vdp_port_event(port_uuid, mac, net_uuid,
                                             segmentation_id, status, oui)
        expected_calls = [
            mock.call.send_vdp_vnic_up(port_uuid=port_uuid,
                                       vsiid=port_uuid,
                                       gid=segmentation_id,
                                       mac=mac, vlan=500,
                                       oui=oui,
                                       vsw_cb_fn=self.ovs_vdp.vdp_vlan_change,
                                       vsw_cb_data=ovs_cb_data)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def _test_vdp_port_event_down(self):
        '''Test the case for a vnic port down for a network '''
        port_uuid = '0000-1111-2222-3334'
        mac = '00:00:fa:11:22:34'
        net_uuid = '0000-aaaa-bbbb-cccc'
        segmentation_id = 10001
        status = 'down'
        oui = None
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.delete_flows') as (del_flow), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.get_ofport_name',
                       return_value='test_port'), \
            mock.patch.object(self.ovs_vdp.lldpad_info,
                              'send_vdp_vnic_down') as vnic_down:
            self.ovs_vdp.local_vlan_map[net_uuid] = ovs_vdp.LocalVlan(10, (
                segmentation_id))
            lvm = self.ovs_vdp.local_vlan_map[net_uuid]
            lvm.lvid = 10
            lvm.port_uuid_list[port_uuid] = port_uuid
            self.ovs_vdp.local_vlan_map[net_uuid].late_binding_vlan = 500
            parent = mock.MagicMock()
            parent.attach_mock(vnic_down, 'send_vdp_vnic_down')
            parent.attach_mock(del_flow, 'delete_flows')
            self.ovs_vdp.send_vdp_port_event(port_uuid, mac, net_uuid,
                                             segmentation_id, status, oui)
        expected_calls = [mock.call.send_vdp_vnic_down(port_uuid=port_uuid,
                                                       vsiid=port_uuid,
                                                       gid=segmentation_id,
                                                       mac=mac, vlan=500,
                                                       oui=oui),
                          mock.call.delete_flows(
                              in_port=self.ovs_vdp.phy_peer_port_num,
                              dl_vlan=10),
                          mock.call.delete_flows(
                              in_port=self.ovs_vdp.int_peer_port_num,
                              dl_vlan=500)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_vdp_port_event(self):
        '''
        Routine the calls the other new port and existing port test routines
        '''
        self._test_vdp_port_event_new()
        self._test_vdp_port_event_exist()

    def test_vdp_port_event_down(self):
        '''Routine the calls the port down test '''
        self._test_vdp_port_event_down()

    def test_vdp_port_event_down_valid_vlan(self):
        """Test the case for a vnic port down for a network.

        This is to test the case when there are more than one vNic for a
        network with a valid VLAN. Flows should not be removed.
        """
        status = 'down'
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.delete_flows') as (del_flow), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.get_ofport_name',
                       return_value='test_port'), \
            mock.patch.object(self.ovs_vdp.lldpad_info,
                              'send_vdp_vnic_down') as vnic_down:
            self.ovs_vdp.local_vlan_map[self.net_uuid] = ovs_vdp.LocalVlan(
                self.lvid, self.segmentation_id)
            lvm = self.ovs_vdp.local_vlan_map[self.net_uuid]
            lvm.lvid = self.lvid
            lvm.set_port_uuid(self.port_uuid, self.exist_vdp_vlan, None)
            lvm.set_port_uuid(self.port_uuid_1, self.exist_vdp_vlan, None)
            self.ovs_vdp.local_vlan_map[
                self.net_uuid].late_binding_vlan = self.exist_vdp_vlan
            parent = mock.MagicMock()
            parent.attach_mock(vnic_down, 'send_vdp_vnic_down')
            parent.attach_mock(del_flow, 'delete_flows')
            self.ovs_vdp.send_vdp_port_event(
                self.port_uuid, self.mac, self.net_uuid,
                self.segmentation_id, status, self.oui)
        expected_calls = [mock.call.send_vdp_vnic_down(
            port_uuid=self.port_uuid, vsiid=self.port_uuid,
            gid=self.segmentation_id, mac=self.mac, vlan=self.exist_vdp_vlan,
            oui=self.oui)]
        parent.assert_has_calls(expected_calls, any_order=False)
        del_flow.assert_not_called()

    def test_vdp_port_event_down_no_valid_vlan(self):
        """Test the case for a vnic port down for a network with no valid vlan.

       This is to test the case when there are more than one vNic for a
        network with no valid VLAN. Flows should be removed.
        """
        status = 'down'
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.delete_flows') as (del_flow), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.get_ofport_name',
                       return_value='test_port'), \
            mock.patch.object(self.ovs_vdp.lldpad_info,
                              'send_vdp_vnic_down') as vnic_down:
            self.ovs_vdp.local_vlan_map[self.net_uuid] = ovs_vdp.LocalVlan(
                self.lvid, self.segmentation_id)
            lvm = self.ovs_vdp.local_vlan_map[self.net_uuid]
            lvm.lvid = self.lvid
            lvm.set_port_uuid(self.port_uuid, self.exist_vdp_vlan, None)
            lvm.set_port_uuid(self.port_uuid_1, 0, None)
            self.ovs_vdp.local_vlan_map[
                self.net_uuid].late_binding_vlan = self.exist_vdp_vlan
            parent = mock.MagicMock()
            parent.attach_mock(vnic_down, 'send_vdp_vnic_down')
            parent.attach_mock(del_flow, 'delete_flows')
            self.ovs_vdp.send_vdp_port_event(
                self.port_uuid, self.mac, self.net_uuid,
                self.segmentation_id, status, self.oui)
        expected_calls = [
            mock.call.send_vdp_vnic_down(
                port_uuid=self.port_uuid, vsiid=self.port_uuid,
                gid=self.segmentation_id, mac=self.mac,
                vlan=self.exist_vdp_vlan, oui=self.oui),
            mock.call.delete_flows(in_port=self.ovs_vdp.phy_peer_port_num,
                                   dl_vlan=self.lvid),
            mock.call.delete_flows(in_port=self.ovs_vdp.int_peer_port_num,
                                   dl_vlan=self.exist_vdp_vlan)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_vdp_port_event_down_mismatched_vlans(self):
        """Test the case for a vnic port down for a network with mismatch vlan.

        This is to test the case when there are more than one vNic for a
        network with mismatched VLAN's. Stale Flows should be removed and new
        flows should be added.
        """
        old_vdp_vlan = 3001
        status = 'down'
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.delete_flows') as (del_flow), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.add_flow') as (add_flow), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.get_ofport_name',
                       return_value='test_port'), \
            mock.patch.object(self.ovs_vdp.lldpad_info,
                              'send_vdp_vnic_down') as vnic_down:
            self.ovs_vdp.local_vlan_map[self.net_uuid] = ovs_vdp.LocalVlan(
                self.lvid, self.segmentation_id)
            lvm = self.ovs_vdp.local_vlan_map[self.net_uuid]
            lvm.lvid = self.lvid
            lvm.set_port_uuid(self.port_uuid, self.exist_vdp_vlan, None)
            lvm.set_port_uuid(self.port_uuid_1, old_vdp_vlan, None)
            self.ovs_vdp.local_vlan_map[
                self.net_uuid].late_binding_vlan = self.exist_vdp_vlan
            parent = mock.MagicMock()
            parent.attach_mock(vnic_down, 'send_vdp_vnic_down')
            parent.attach_mock(del_flow, 'delete_flows')
            parent.attach_mock(add_flow, 'add_flow')
            self.ovs_vdp.send_vdp_port_event(
                self.port_uuid, self.mac, self.net_uuid,
                self.segmentation_id, status, self.oui)
        expected_calls = [
            mock.call.send_vdp_vnic_down(
                port_uuid=self.port_uuid, vsiid=self.port_uuid,
                gid=self.segmentation_id, mac=self.mac,
                vlan=self.exist_vdp_vlan, oui=self.oui),
            mock.call.delete_flows(in_port=self.ovs_vdp.phy_peer_port_num,
                                   dl_vlan=self.lvid),
            mock.call.delete_flows(in_port=self.ovs_vdp.int_peer_port_num,
                                   dl_vlan=self.exist_vdp_vlan),
            mock.call.add_flow(
                priority=4, in_port=self.ovs_vdp.phy_peer_port_num,
                dl_vlan=self.lvid,
                actions="mod_vlan_vid:%s,normal" % old_vdp_vlan),
            mock.call.add_flow(
                priority=3, in_port=self.ovs_vdp.int_peer_port_num,
                dl_vlan=old_vdp_vlan,
                actions="mod_vlan_vid:%s,normal" % self.lvid)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_vdp_vlan_change_rem_add(self):
        """Testing the VDP VLAN change for a remove/add flow case. """
        new_vdp_vlan = 3006
        ovs_cb_data = {'port_uuid': self.port_uuid, 'net_uuid': self.net_uuid}
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.delete_flows') as (ovs_br_del):
            parent = mock.MagicMock()
            parent.attach_mock(ovs_br_del, 'delete_flows')
            parent.attach_mock(self.ovs_br_add, 'add_flow')
            self.ovs_vdp.local_vlan_map[
                self.net_uuid] = ovs_vdp.LocalVlan(self.lvid,
                                                   self.segmentation_id)
            lvm = self.ovs_vdp.local_vlan_map[self.net_uuid]
            lvm.late_binding_vlan = self.exist_vdp_vlan
            lvm.set_port_uuid(self.port_uuid, self.exist_vdp_vlan, None)
            self.ovs_vdp.vdp_vlan_change(ovs_cb_data, new_vdp_vlan, None)
        expected_calls = [
            mock.call.delete_flows(
                in_port=self.ovs_vdp.phy_peer_port_num, dl_vlan=self.lvid),
            mock.call.delete_flows(
                in_port=self.ovs_vdp.int_peer_port_num,
                dl_vlan=self.exist_vdp_vlan),
            mock.call.add_flow(
                priority=4, in_port=self.ovs_vdp.phy_peer_port_num,
                dl_vlan=self.lvid,
                actions="mod_vlan_vid:%s,normal" % new_vdp_vlan),
            mock.call.add_flow(
                priority=3, in_port=self.ovs_vdp.int_peer_port_num,
                dl_vlan=new_vdp_vlan,
                actions="mod_vlan_vid:%s,normal" % self.lvid)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_vdp_vlan_change_rem(self):
        """Testing the VDP VLAN change for a remove flow case. """
        new_vdp_vlan = 0
        ovs_cb_data = {'port_uuid': self.port_uuid, 'net_uuid': self.net_uuid}
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.delete_flows') as (ovs_br_del):
            parent = mock.MagicMock()
            parent.reset_mock(self.ovs_br_add)
            parent.attach_mock(ovs_br_del, 'delete_flows')
            self.ovs_vdp.local_vlan_map[
                self.net_uuid] = ovs_vdp.LocalVlan(self.lvid,
                                                   self.segmentation_id)
            lvm = self.ovs_vdp.local_vlan_map[self.net_uuid]
            lvm.late_binding_vlan = self.exist_vdp_vlan
            lvm.set_port_uuid(self.port_uuid, self.exist_vdp_vlan, None)
            self.ovs_vdp.vdp_vlan_change(ovs_cb_data, new_vdp_vlan, None)
        expected_calls = [
            mock.call.delete_flows(
                in_port=self.ovs_vdp.phy_peer_port_num, dl_vlan=self.lvid),
            mock.call.delete_flows(
                in_port=self.ovs_vdp.int_peer_port_num,
                dl_vlan=self.exist_vdp_vlan)]
        parent.assert_has_calls(expected_calls, any_order=False)
        self.ovs_br_add.assert_not_called()

    def test_vdp_vlan_change_multiple_vnics_norem(self):
        """Testing the VDP VLAN change for multiple vnic's.

        This is for the case when there are multiple vNics for the same
        network and for one vNic a VDP VLAN of 0, is returned. So flow
        should not be deleted.
        """
        new_vdp_vlan = 0
        ovs_cb_data = {'port_uuid': self.port_uuid, 'net_uuid': self.net_uuid}
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.add_flow') as (ovs_br_add), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.delete_flows') as (ovs_br_del):
            parent = mock.MagicMock()
            parent.attach_mock(ovs_br_del, 'delete_flows')
            parent.attach_mock(ovs_br_add, 'add_flow')
            self.ovs_vdp.local_vlan_map[
                self.net_uuid] = ovs_vdp.LocalVlan(self.lvid,
                                                   self.segmentation_id)
            lvm = self.ovs_vdp.local_vlan_map[self.net_uuid]
            lvm.late_binding_vlan = self.exist_vdp_vlan
            lvm.set_port_uuid(self.port_uuid, self.exist_vdp_vlan, None)
            lvm.set_port_uuid(self.port_uuid_1, self.exist_vdp_vlan, None)
            self.ovs_vdp.vdp_vlan_change(ovs_cb_data, new_vdp_vlan, None)
        ovs_br_add.assert_not_called()
        ovs_br_del.assert_not_called()

    def test_flow_check_handler_ext_flows_missing(self):
        """Testing the flow check handler for external bridge.

        Flow is missing for external bridge.
        """
        integ_flow = "NXST_FLOW reply (xid=0x4):\n" \
                     "cookie=0x0, duration=460654.804s, table=0, "\
                     "n_packets=3885, n_bytes=248632, idle_age=71, "\
                     "hard_age=65534, priority=3,in_port=1,dl_vlan=10 "\
                     "actions=mod_vlan_vid:3005,NORMAL\n" \
                     "cookie=0x9feb720beeec4ab9, duration=777857.315s, "\
                     "table=0, n_packets=32387, n_bytes=2186200, idle_age=4,"\
                     " hard_age=65534, priority=2,in_port=1 actions=drop"
        ext_flow = "NXST_FLOW reply (xid=0x4):"
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.add_flow') as (ovs_br_add), \
            mock.patch.object(self.ovs_vdp.integ_br_obj, 'dump_flows_for',
                              return_value=integ_flow), \
            mock.patch.object(self.ovs_vdp.ext_br_obj, 'dump_flows_for',
                              return_value=ext_flow):
            parent = mock.MagicMock()
            parent.attach_mock(ovs_br_add, 'add_flow')
            self.ovs_vdp.local_vlan_map[
                self.net_uuid] = ovs_vdp.LocalVlan(self.lvid,
                                                   self.segmentation_id)
            lvm = self.ovs_vdp.local_vlan_map[self.net_uuid]
            lvm.late_binding_vlan = self.exist_vdp_vlan
            lvm.lvid = self.lvid
            lvm.set_port_uuid(self.port_uuid, self.exist_vdp_vlan, None)
            self.ovs_vdp._flow_check_handler()
        expected_calls = [
            mock.call.add_flow(
                priority=4, in_port=self.ovs_vdp.phy_peer_port_num,
                dl_vlan=self.lvid,
                actions="mod_vlan_vid:%s,normal" % self.exist_vdp_vlan),
            mock.call.add_flow(
                priority=3, in_port=self.ovs_vdp.int_peer_port_num,
                dl_vlan=self.exist_vdp_vlan,
                actions="mod_vlan_vid:%s,normal" % self.lvid)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_flow_check_handler_integ_flows_missing(self):
        """Testing the flow check handler for integ bridge.

        Flow is missing for integration bridge.
        """
        ext_flow = "NXST_FLOW reply (xid=0x4):\n" \
                   "cookie=0x0, duration=460654.804s, table=0, "\
                   "n_packets=3885, n_bytes=248632, idle_age=71, "\
                   "hard_age=65534, priority=3,in_port=1,dl_vlan=3005 "\
                   "actions=mod_vlan_vid:10,NORMAL\n" \
                   "cookie=0x9feb720beeec4ab9, duration=777857.315s, "\
                   "table=0, n_packets=32387, n_bytes=2186200, idle_age=4,"\
                   " hard_age=65534, priority=2,in_port=1 actions=drop"
        integ_flow = "NXST_FLOW reply (xid=0x4):"
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.add_flow') as (ovs_br_add), \
            mock.patch.object(self.ovs_vdp.integ_br_obj, 'dump_flows_for',
                              return_value=integ_flow), \
            mock.patch.object(self.ovs_vdp.ext_br_obj, 'dump_flows_for',
                              return_value=ext_flow):
            parent = mock.MagicMock()
            parent.attach_mock(ovs_br_add, 'add_flow')
            self.ovs_vdp.local_vlan_map[
                self.net_uuid] = ovs_vdp.LocalVlan(self.lvid,
                                                   self.segmentation_id)
            lvm = self.ovs_vdp.local_vlan_map[self.net_uuid]
            lvm.late_binding_vlan = self.exist_vdp_vlan
            lvm.lvid = self.lvid
            lvm.set_port_uuid(self.port_uuid, self.exist_vdp_vlan, None)
            self.ovs_vdp._flow_check_handler()
        expected_calls = [
            mock.call.add_flow(
                priority=4, in_port=self.ovs_vdp.phy_peer_port_num,
                dl_vlan=self.lvid,
                actions="mod_vlan_vid:%s,normal" % self.exist_vdp_vlan),
            mock.call.add_flow(
                priority=3, in_port=self.ovs_vdp.int_peer_port_num,
                dl_vlan=self.exist_vdp_vlan,
                actions="mod_vlan_vid:%s,normal" % self.lvid)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_flow_check_handler_both_flows_missing(self):
        """Testing the flow check handler for both bridges.

        Flow is missing for both bridges.
        """
        ext_flow = "NXST_FLOW reply (xid=0x4):"
        integ_flow = "NXST_FLOW reply (xid=0x4):"
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.add_flow') as (ovs_br_add), \
            mock.patch.object(self.ovs_vdp.integ_br_obj, 'dump_flows_for',
                              return_value=integ_flow), \
            mock.patch.object(self.ovs_vdp.ext_br_obj, 'dump_flows_for',
                              return_value=ext_flow):
            parent = mock.MagicMock()
            parent.attach_mock(ovs_br_add, 'add_flow')
            self.ovs_vdp.local_vlan_map[
                self.net_uuid] = ovs_vdp.LocalVlan(self.lvid,
                                                   self.segmentation_id)
            lvm = self.ovs_vdp.local_vlan_map[self.net_uuid]
            lvm.late_binding_vlan = self.exist_vdp_vlan
            lvm.lvid = self.lvid
            lvm.set_port_uuid(self.port_uuid, self.exist_vdp_vlan, None)
            self.ovs_vdp._flow_check_handler()
        expected_calls = [
            mock.call.add_flow(
                priority=4, in_port=self.ovs_vdp.phy_peer_port_num,
                dl_vlan=self.lvid,
                actions="mod_vlan_vid:%s,normal" % self.exist_vdp_vlan),
            mock.call.add_flow(
                priority=3, in_port=self.ovs_vdp.int_peer_port_num,
                dl_vlan=self.exist_vdp_vlan,
                actions="mod_vlan_vid:%s,normal" % self.lvid)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_flow_check_handler_no_flows_missing(self):
        """Testing the flow check handler for both bridges.

        No flows are missing in both the bridges.
        """
        new_vdp_vlan = 3005
        ext_flow = "NXST_FLOW reply (xid=0x4):\n" \
                   "cookie=0x0, duration=460654.804s, table=0, "\
                   "n_packets=3885, n_bytes=248632, idle_age=71, "\
                   "hard_age=65534, priority=3,in_port=1,dl_vlan=10 "\
                   "actions=mod_vlan_vid:3005,NORMAL\n" \
                   "cookie=0x9feb720beeec4ab9, duration=777857.315s, "\
                   "table=0, n_packets=32387, n_bytes=2186200, idle_age=4,"\
                   " hard_age=65534, priority=2,in_port=1 actions=drop"
        integ_flow = "NXST_FLOW reply (xid=0x4):\n" \
                     "cookie=0x0, duration=460654.804s, table=0, "\
                     "n_packets=3885, n_bytes=248632, idle_age=71, "\
                     "hard_age=65534, priority=3,in_port=1,dl_vlan=3005 "\
                     "actions=mod_vlan_vid:10,NORMAL\n" \
                     "cookie=0x9feb720beeec4ab9, duration=777857.315s, "\
                     "table=0, n_packets=32387, n_bytes=2186200, idle_age=4,"\
                     " hard_age=65534, priority=2,in_port=1 actions=drop"
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.add_flow') as (ovs_br_add), \
            mock.patch.object(self.ovs_vdp.integ_br_obj, 'dump_flows_for',
                              return_value=integ_flow), \
            mock.patch.object(self.ovs_vdp.ext_br_obj, 'dump_flows_for',
                              return_value=ext_flow):
            parent = mock.MagicMock()
            parent.attach_mock(ovs_br_add, 'add_flow')
            self.ovs_vdp.local_vlan_map[
                self.net_uuid] = ovs_vdp.LocalVlan(self.lvid,
                                                   self.segmentation_id)
            lvm = self.ovs_vdp.local_vlan_map[self.net_uuid]
            lvm.late_binding_vlan = new_vdp_vlan
            lvm.lvid = self.lvid
            lvm.set_port_uuid(self.port_uuid, new_vdp_vlan, None)
            self.ovs_vdp._flow_check_handler()
        ovs_br_add.assert_not_called()

    def test_populate_cache(self):
        """Test the populate cache function. """
        self.ovs_vdp.pop_local_cache(
            self.port_uuid, self.mac, self.net_uuid, self.lvid,
            self.exist_vdp_vlan, self.segmentation_id)
        rvlan = self.ovs_vdp.local_vlan_map[self.net_uuid].get_portid_vlan(
            self.port_uuid)
        fail_reason = self.ovs_vdp.local_vlan_map[
            self.net_uuid].get_portid_fail_reason(self.port_uuid)
        valid_vlan = self.ovs_vdp.local_vlan_map[
            self.net_uuid].any_valid_vlan()
        self.assertEqual(
            self.lvid, self.ovs_vdp.local_vlan_map[self.net_uuid].lvid)
        self.assertEqual(
            self.exist_vdp_vlan,
            self.ovs_vdp.local_vlan_map[self.net_uuid].late_binding_vlan)
        self.assertEqual(
            False, self.ovs_vdp.local_vlan_map[self.net_uuid].vdp_nego_req)
        self.assertEqual(self.exist_vdp_vlan, rvlan)
        self.assertIsNone(fail_reason)
        self.assertTrue(valid_vlan)
