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
        self._test_ovs_vdp_init()

    def _test_ovs_vdp_init(self):
        '''Test the init routine '''
        lldp_ovs_portnum = 14
        phy_port_num = 14
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.delete_flows') as (ovs_br_del),\
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.get_bridges') as (get_br), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.is_patch') as (is_patch), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.get_peer') as (get_peer), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.add_flow') as (ovs_br_add), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.add_port',
                       return_value=str(lldp_ovs_portnum)), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.get_port_ofport',
                       return_value=str(phy_port_num)), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.'
                       'get_port_name_list') as port_name_list, \
            mock.patch('neutron.agent.linux.ip_lib.'
                       'device_exists') as dev_exist, \
            mock.patch('neutron.agent.linux.ip_lib.'
                       'IPWrapper.add_veth') as add_veth, \
                mock.patch('networking_cisco.apps.saf.'
                           'agent.vdp.lldpad.LldpadDriver') as lldpad:
            lldp_inst = lldpad.return_value
            get_br.return_value = self.integ_br + ' ' + self.ext_br
            port_name_list.return_value = 'port_int1'
            is_patch.return_value = True
            get_peer.return_value = 'port_int1'
            dev_exist.return_value = False
            add_veth.return_value = mock.Mock(), mock.Mock()

            parent = mock.MagicMock()
            parent.attach_mock(ovs_br_del, 'delete_flows')
            parent.attach_mock(ovs_br_add, 'add_flow')
            parent.attach_mock(lldp_inst.enable_evb, 'enable_evb')
            self.ovs_vdp = ovs_vdp.OVSNeutronVdp(self.uplink, self.integ_br,
                                                 self.ext_br,
                                                 self.root_helper)
        veth_str = vconstants.LLDPAD_LOC_VETH_PORT + self.uplink
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

    def test_process_init(self):
        '''Wrapper for the init routine test '''
        pass

    def _test_vdp_port_event_new(self):
        '''Test the case for a new vnic port for a network '''
        port_uuid = '0000-1111-2222-3333'
        mac = '00:00:fa:11:22:33'
        net_uuid = '0000-aaaa-bbbb-cccc'
        segmentation_id = 10001
        status = 'up'
        oui = None
        with mock.patch('networking_cisco.apps.saf.common.'
                        'dfa_sys_lib.OVSBridge.add_flow') as (ovs_br_add), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.get_ofport_name',
                       return_value='test_port'), \
            mock.patch('networking_cisco.apps.saf.common.'
                       'dfa_sys_lib.OVSBridge.get_port_vlan_tag',
                       return_value=10), \
            mock.patch.object(self.ovs_vdp.lldpad_info, 'send_vdp_vnic_up',
                              return_value=500):
            parent = mock.MagicMock()
            parent.attach_mock(ovs_br_add, 'add_flow')
            phy_port_num = 5
            int_peer_port_num = 6
            self.ovs_vdp.phy_peer_port_num = phy_port_num
            self.ovs_vdp.int_peer_port_num = int_peer_port_num
            self.ovs_vdp.send_vdp_port_event(port_uuid, mac, net_uuid,
                                             segmentation_id, status, oui)
        expected_calls = [
            mock.call.add_flow(priority=4, in_port=phy_port_num,
                               dl_vlan=10,
                               actions="mod_vlan_vid:%s,normal" % 500),
            mock.call.add_flow(priority=3, in_port=int_peer_port_num,
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
            phy_port_num = 5
            int_peer_port_num = 6
            self.ovs_vdp.phy_peer_port_num = phy_port_num
            self.ovs_vdp.int_peer_port_num = int_peer_port_num
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
                          mock.call.delete_flows(in_port=phy_port_num,
                                                 dl_vlan=10),
                          mock.call.delete_flows(in_port=int_peer_port_num,
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
