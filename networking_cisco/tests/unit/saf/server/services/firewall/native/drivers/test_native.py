# Copyrigh 2016 Cisco Systems.
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
import copy

import mock

from neutron.tests import base as base_test

from networking_cisco.apps.saf.server.services.firewall.native import (
    fabric_setup_base as FP)
from networking_cisco.apps.saf.server.services.firewall.native.drivers import (
    base)
from networking_cisco.apps.saf.server.services.firewall.native.drivers import (
    native)
import networking_cisco.apps.saf.server.services.firewall.native.fw_constants \
    as fw_const


TIME = 'Thu Aug 11 19:11:30 2000'
TENANT_NAME = 'TenantA'
TENANT_ID = '0000-1111-2222-5555'
FW_ID = '0000-aaaa-bbbb-ccce'
FW_NAME = 'FwA'
POLCY_ID = '0000-aaaa-bbbb-cccc'
FW_TYPE = 'TE'
ROUTER_ID = '0000-aaaa-bbbb-5555'
RULE_ID = '0000-aaaa-bbbb-cccd'
NET_ID = '0000-aaa1-bbbb-cccd'
OUT_NET_ID = '0000-aab1-bbbb-cccd'
RTR_ID = '0000-aaa2-bbbb-cccd'
SUBNET_ID = '0000-aaa3-bbbb-cccd'
OUT_SUBNET_ID = '0000-aaa4-bbbb-cccd'
PROTOCOL = 'tcp'
MGMT_IP = '3.3.3.3'
SRC_IP = '1.1.1.1'
DST_IP = '2.2.2.2'
NEW_CIDR = '10.11.12.0/24'
SRC_PORT = 34
DST_PORT = 43
RULE_NAME = 'RuleA'
IN_SUBNET = '100.100.11.0'
IN_MASK = '255.255.255.0'
IN_SUBNET_AND_MASK = '100.100.11.0/24'
IN_START = '100.100.11.3'
IN_SEC_GW = '100.100.11.254'
IN_GW = '100.100.11.2'
IN_FABRIC_GW = '100.100.11.1'
IN_END = '100.100.11.254'
SEGMENTATION_ID = 87999
OUT_SEGMENTATION_ID = 88000
VLAN_ID = 770
OUT_VLAN_ID = 771
OUT_SUBNET = '200.200.11.0'
OUT_MASK = '255.255.255.0'
OUT_SUBNET_AND_MASK = '200.200.11.0/24'
RTR_SUBNET_AND_MASK = '9.9.9.0/24'
OUT_START = '200.200.11.3'
OUT_SEC_GW = '200.200.11.254'
OUT_GW = '200.200.11.2'
OUT_FABRIC_GW = '200.200.11.1'
OUT_END = '200.200.11.254'
INTF_IN = 'e1/1'
INTF_OUT = 'e1/2'
HOST_NAME = 'Host1'
VM_MAC = '00:00:00:11:22:33'
VM_IP = '2.3.5.4'
PORT_ID = '0000-aab3-bbbb-cccd'
STATIC_SUB = '2.3.5.0'
NEW_STATIC_SUB = '10.11.12.0'

try:
    OrderedDict = collections.OrderedDict
except AttributeError:
    import ordereddict
    OrderedDict = ordereddict.OrderedDict


class FakeClass(object):
    """Fake class"""
    @classmethod
    def imitate(cls, *others):
        for other in others:
            for name in other.__dict__:
                try:
                    setattr(cls, name, mock.Mock())
                except (TypeError, AttributeError):
                    pass
        return cls

    @classmethod
    def set_return(cls, class_name, fn_name, return_val):
        getattr(cls, fn_name).return_value = return_val


class NativeFirewallTest(base_test.BaseTestCase):
    """A test suite to exercise the Native Firewall Driver.  """

    def setUp(self):
        '''Setup for the test scripts '''
        super(NativeFirewallTest, self).setUp()
        self._init_values()
        self.cfg_dict = self._fill_cfg()

        native.NativeFirewall.__bases__ = (FakeClass.imitate(base.BaseDriver,
                                                             FP.FabricApi),)
        mock.patch('networking_cisco.apps.saf.server.'
                   'dfa_openstack_helper.DfaNeutronHelper').start()
        mock.patch('time.sleep').start()
        mock.patch('time.ctime', return_value=TIME).start()
        self.native_fw = native.NativeFirewall()
        self.native_fw.initialize(self.cfg_dict)
        self.native_fw.populate_dcnm_obj(mock.MagicMock())
        self.native_fw.populate_event_que(mock.MagicMock())

    def _init_values(self):
        self.tenant_name = TENANT_NAME
        self.tenant_id = TENANT_ID
        self.rule_id = RULE_ID
        self.in_subnet = IN_SUBNET
        self.in_subnet_and_mask = IN_SUBNET_AND_MASK
        self.in_gw = IN_GW
        self.in_start = IN_START
        self.in_sec_gw = IN_SEC_GW
        self.in_end = IN_END
        self.out_subnet = OUT_SUBNET
        self.out_subnet_and_mask = OUT_SUBNET_AND_MASK
        self.out_gw = OUT_GW
        self.out_sec_gw = OUT_SEC_GW
        self.out_start = OUT_START
        self.out_end = OUT_END
        self.in_fabric_gw = IN_FABRIC_GW
        self.out_fabric_gw = OUT_FABRIC_GW
        self.segmentation_id = SEGMENTATION_ID
        self.out_segmentation_id = OUT_SEGMENTATION_ID
        self.vlan_id = VLAN_ID
        self.out_vlan_id = OUT_VLAN_ID
        self.net_id = NET_ID
        self.out_net_id = OUT_NET_ID
        self.rtr_id = RTR_ID
        self.subnet_id = SUBNET_ID
        self.out_subnet_id = OUT_SUBNET_ID
        self.fw_data = {'tenant_name': self.tenant_name,
                        'router_id': self.rtr_id}

    def _fill_cfg(self):
        config = {'mgmt_ip_addr': MGMT_IP, 'user': 'user',
                  'pwd': 'user', 'interface_in': INTF_IN,
                  'interface_out': INTF_OUT}
        return config

    def test_native_fw_init(self):
        '''Wrapper for the init'''
        pass

    def _get_modified_fw_data(self):
        new_fw_data = copy.deepcopy(self.fw_data)
        new_fw_data.get('rules').get(self.rule_id)['action'] = 'deny'
        return new_fw_data

    def _get_port_data(self):
        port_data = {'binding:host_id': HOST_NAME, 'mac_address': VM_MAC,
                     'id': PORT_ID, 'fixed_ips': [{'ip_address': VM_IP}]}
        return port_data

    def _get_vm_vdp_data(self, status, net_id, segid, oper, event):
        vm_name = 'FW_SRVC_RTR_' + self.tenant_name + '_' + oper
        vm_vdp_data = {'status': status, 'vm_name': vm_name,
                       'network_id': net_id, 'gw_mac': None, 'host': HOST_NAME,
                       'segid': segid, 'mac': VM_MAC, 'vm_uuid': self.rtr_id,
                       'vm_ip': VM_IP, 'port_id': PORT_ID,
                       'fwd_mod': 'anycast_gateway'}
        payload = {'service': vm_vdp_data}
        data = (event, payload)
        return data

    def _test_send_in_router_port_msg(self, status):
        """Test for the 'in' service vNic create message. """
        port_data = self._get_port_data()
        if status == 'up':
            msg = 'service.vnic.create'
        else:
            msg = 'service.vnic.delete'
        vm_vdp_data_in = self._get_vm_vdp_data(status, self.net_id,
                                               self.segmentation_id,
                                               'in', msg)
        with mock.patch.object(self.native_fw.que_obj, 'put') as que_put,\
            mock.patch.object(self.native_fw.os_helper,
                              'get_router_port_subnet',
                              return_value=port_data):
            FakeClass.set_return(FP.FabricApi, 'get_in_subnet_id',
                                 self.subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_subnet_id',
                                 self.out_subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_in_net_id', self.net_id)
            parent = mock.MagicMock()
            parent.attach_mock(que_put, 'put')
            arg_dict = self.native_fw._create_arg_dict(self.tenant_id,
                                                       self.fw_data,
                                                       self.subnet_id,
                                                       self.out_subnet_id)
            self.native_fw.tenant_dict[self.tenant_id] = (
                {'host': None, 'router_id': self.rtr_id})
            self.native_fw.send_in_router_port_msg(self.tenant_id, arg_dict,
                                                   status)
        expected_calls = [mock.call.put((34, TIME, vm_vdp_data_in))]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_send_in_router_port_msg_up(self):
        self._test_send_in_router_port_msg('up')

    def test_send_in_router_port_msg_down(self):
        self._test_send_in_router_port_msg('down')

    def _test_send_in_router_port_msg_fail(self, status):
        """Test for the 'in' service vNic create message fail. """
        subnet_lst = set()
        subnet_lst.add(self.subnet_id)
        subnet_lst.add(self.out_subnet_id)
        with mock.patch.object(self.native_fw.que_obj, 'put') as que_put,\
            mock.patch.object(self.native_fw.os_helper,
                              'get_router_port_subnet',
                              return_value=None),\
            mock.patch.object(self.native_fw.os_helper,
                              'delete_intf_router',
                              return_value=True) as del_intf_rtr:
            FakeClass.set_return(FP.FabricApi, 'get_in_subnet_id',
                                 self.subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_subnet_id',
                                 self.out_subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_in_net_id', self.net_id)
            parent = mock.MagicMock()
            parent.attach_mock(que_put, 'put')
            if status == 'up':
                parent.attach_mock(del_intf_rtr, 'delete_intf_router')
            arg_dict = self.native_fw._create_arg_dict(self.tenant_id,
                                                       self.fw_data,
                                                       self.subnet_id,
                                                       self.out_subnet_id)
            self.native_fw.tenant_dict[self.tenant_id] = (
                {'host': None, 'router_id': self.rtr_id})
            self.native_fw.send_in_router_port_msg(self.tenant_id, arg_dict,
                                                   status)
        expected_calls = []
        if status == 'up':
            expected_calls.append(mock.call.delete_intf_router(
                self.tenant_name, self.tenant_id, self.rtr_id, subnet_lst))
        parent.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(que_put.called, False)

    def test_send_in_router_port_msg_fail_up(self):
        self._test_send_in_router_port_msg_fail('up')

    def test_send_in_router_port_msg_fail_down(self):
        self._test_send_in_router_port_msg_fail('down')

    def _test_send_out_router_port_msg(self, status):
        """Test for the 'out' service vNic create message. """
        port_data = self._get_port_data()
        if status == 'up':
            msg = 'service.vnic.create'
        else:
            msg = 'service.vnic.delete'
        vm_vdp_data_out = self._get_vm_vdp_data(status, self.out_net_id,
                                                self.out_segmentation_id,
                                                'out', msg)
        with mock.patch.object(self.native_fw.que_obj, 'put') as que_put,\
            mock.patch.object(self.native_fw.os_helper,
                              'get_router_port_subnet',
                              return_value=port_data):
            FakeClass.set_return(FP.FabricApi, 'get_in_subnet_id',
                                 self.subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_subnet_id',
                                 self.out_subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_net_id',
                                 self.out_net_id)
            parent = mock.MagicMock()
            parent.attach_mock(que_put, 'put')
            arg_dict = self.native_fw._create_arg_dict(self.tenant_id,
                                                       self.fw_data,
                                                       self.subnet_id,
                                                       self.out_subnet_id)
            self.native_fw.tenant_dict[self.tenant_id] = (
                {'host': None, 'router_id': self.rtr_id})
            self.native_fw.send_out_router_port_msg(self.tenant_id, arg_dict,
                                                    status)
        expected_calls = [mock.call.put((34, TIME, vm_vdp_data_out))]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_send_out_router_port_msg_up(self):
        self._test_send_out_router_port_msg('up')

    def test_send_out_router_port_msg_down(self):
        self._test_send_out_router_port_msg('down')

    def _test_send_out_router_port_msg_fail(self, status):
        """Test for the 'out' service vNic create message fail. """
        subnet_lst = set()
        subnet_lst.add(self.subnet_id)
        subnet_lst.add(self.out_subnet_id)
        with mock.patch.object(self.native_fw.que_obj, 'put') as que_put,\
            mock.patch.object(self.native_fw.os_helper,
                              'get_router_port_subnet',
                              return_value=None),\
            mock.patch.object(self.native_fw.os_helper,
                              'delete_intf_router',
                              return_value=True) as del_intf_rtr:
            FakeClass.set_return(FP.FabricApi, 'get_in_subnet_id',
                                 self.subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_subnet_id',
                                 self.out_subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_net_id', self.net_id)
            parent = mock.MagicMock()
            parent.attach_mock(que_put, 'put')
            if status == 'up':
                parent.attach_mock(del_intf_rtr, 'delete_intf_router')
            arg_dict = self.native_fw._create_arg_dict(self.tenant_id,
                                                       self.fw_data,
                                                       self.subnet_id,
                                                       self.out_subnet_id)
            self.native_fw.tenant_dict[self.tenant_id] = (
                {'host': None, 'router_id': self.rtr_id})
            self.native_fw.send_out_router_port_msg(self.tenant_id, arg_dict,
                                                    status)
        expected_calls = []
        if status == 'up':
            expected_calls.append(mock.call.delete_intf_router(
                self.tenant_name, self.tenant_id, self.rtr_id, subnet_lst))
        parent.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(que_put.called, False)

    def test_send_out_router_port_msg_fail_up(self):
        self._test_send_out_router_port_msg_fail('up')

    def test_send_out_router_port_msg_fail_down(self):
        self._test_send_out_router_port_msg_fail('down')

    def test_program_next_hop(self):
        """Test for programming the next hop for out network. """
        with mock.patch.object(self.native_fw.os_helper,
                               'program_rtr_all_nwk_next_hop',
                               return_value=True) as prog_rtr_all_nwk:
            FakeClass.set_return(FP.FabricApi, 'get_in_ip_addr',
                                 {'subnet': self.in_subnet,
                                  'start': self.in_start,
                                  'sec_gateway': self.in_sec_gw,
                                  'gateway': self.in_fabric_gw,
                                  'end': self.in_end})
            FakeClass.set_return(FP.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_fabric_gw,
                                  'end': self.out_end})
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            parent = mock.MagicMock()
            parent.attach_mock(prog_rtr_all_nwk,
                               'program_rtr_all_nwk_next_hop')
            arg_dict = self.native_fw._create_arg_dict(self.tenant_id,
                                                       self.fw_data,
                                                       self.subnet_id,
                                                       self.out_subnet_id)
            self.native_fw.program_next_hop(self.tenant_id, arg_dict)
        expected_calls = [
            mock.call.program_rtr_all_nwk_next_hop(
                self.tenant_id, self.rtr_id, self.in_fabric_gw,
                [self.in_subnet, self.out_subnet])]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_program_next_hop_fail(self):
        """Test for programming the next hop for out network, failure case. """
        subnet_lst = set()
        subnet_lst.add(self.subnet_id)
        subnet_lst.add(self.out_subnet_id)
        with mock.patch.object(self.native_fw.os_helper,
                               'program_rtr_all_nwk_next_hop',
                               return_value=False) as prog_rtr_all_nwk,\
            mock.patch.object(self.native_fw.os_helper,
                              'delete_intf_router',
                              return_value=True) as del_intf_rtr:
            FakeClass.set_return(FP.FabricApi, 'get_in_ip_addr',
                                 {'subnet': self.in_subnet,
                                  'start': self.in_start,
                                  'sec_gateway': self.in_sec_gw,
                                  'gateway': self.in_fabric_gw,
                                  'end': self.in_end})
            FakeClass.set_return(FP.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_fabric_gw,
                                  'end': self.out_end})
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_in_subnet_id',
                                 self.subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_subnet_id',
                                 self.out_subnet_id)
            parent = mock.MagicMock()
            parent.attach_mock(prog_rtr_all_nwk,
                               'program_rtr_all_nwk_next_hop')
            parent.attach_mock(del_intf_rtr, 'delete_intf_router')
            self.native_fw.tenant_dict[self.tenant_id] = (
                {'host': None, 'router_id': self.rtr_id})
            arg_dict = self.native_fw._create_arg_dict(self.tenant_id,
                                                       self.fw_data,
                                                       self.subnet_id,
                                                       self.out_subnet_id)
            self.native_fw.program_next_hop(self.tenant_id, arg_dict)
        expected_calls = [
            mock.call.program_rtr_all_nwk_next_hop(
                self.tenant_id, self.rtr_id, self.in_fabric_gw,
                [self.in_subnet, self.out_subnet]),
            mock.call.delete_intf_router(self.tenant_name,
                                         self.tenant_id,
                                         self.rtr_id,
                                         subnet_lst)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_program_default_gw(self):
        """Test for programming the default GW. """
        with mock.patch.object(self.native_fw.os_helper,
                               'program_rtr_default_gw',
                               return_value=True) as prog_def_gw:
            FakeClass.set_return(FP.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_fabric_gw,
                                  'end': self.out_end})
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            parent = mock.MagicMock()
            parent.attach_mock(prog_def_gw, 'program_rtr_default_gw')
            arg_dict = self.native_fw._create_arg_dict(self.tenant_id,
                                                       self.fw_data,
                                                       self.subnet_id,
                                                       self.out_subnet_id)
            self.native_fw.program_default_gw(self.tenant_id, arg_dict)
        expected_calls = [
            mock.call.program_rtr_default_gw(
                self.tenant_id, self.rtr_id, self.out_fabric_gw)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_program_default_gw_fail(self):
        """Test for programming the default gw, failure case. """
        subnet_lst = set()
        subnet_lst.add(self.subnet_id)
        subnet_lst.add(self.out_subnet_id)
        with mock.patch.object(self.native_fw.os_helper,
                               'program_rtr_default_gw',
                               return_value=False) as prog_def_gw,\
            mock.patch.object(self.native_fw.os_helper,
                              'delete_intf_router',
                              return_value=True) as del_intf_rtr:
            FakeClass.set_return(FP.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_fabric_gw,
                                  'end': self.out_end})
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_in_subnet_id',
                                 self.subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_subnet_id',
                                 self.out_subnet_id)
            parent = mock.MagicMock()
            parent.attach_mock(prog_def_gw, 'program_rtr_default_gw')
            parent.attach_mock(del_intf_rtr, 'delete_intf_router')
            self.native_fw.tenant_dict[self.tenant_id] = (
                {'host': None, 'router_id': self.rtr_id})
            arg_dict = self.native_fw._create_arg_dict(self.tenant_id,
                                                       self.fw_data,
                                                       self.subnet_id,
                                                       self.out_subnet_id)
            self.native_fw.program_default_gw(self.tenant_id, arg_dict)
        expected_calls = [
            mock.call.program_rtr_default_gw(
                self.tenant_id, self.rtr_id, self.out_fabric_gw),
            mock.call.delete_intf_router(self.tenant_name,
                                         self.tenant_id,
                                         self.rtr_id,
                                         subnet_lst)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_update_dcnm_part_static_route(self):
        """Test for updating the DCNM partition's static route. """
        with mock.patch.object(self.native_fw.os_helper,
                               'get_subnet_nwk_excl',
                               return_value=[STATIC_SUB]),\
            mock.patch.object(self.native_fw.dcnm_obj,
                              'update_partition_static_route',
                              return_value=True) as upd_part:
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_srvc_node_ip_addr',
                                 self.out_gw)
            parent = mock.MagicMock()
            parent.attach_mock(upd_part, 'update_partition_static_route')
            arg_dict = self.native_fw._create_arg_dict(self.tenant_id,
                                                       self.fw_data,
                                                       self.subnet_id,
                                                       self.out_subnet_id)
            self.native_fw.update_dcnm_partition_static_route(
                self.tenant_id, arg_dict)
        expected_calls = [
            mock.call.update_partition_static_route(
                self.tenant_name, fw_const.SERV_PART_NAME, [STATIC_SUB],
                vrf_prof=(
                    self.native_fw.cfg.firewall.fw_service_part_vrf_profile),
                service_node_ip=self.out_gw)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_update_dcnm_part_static_route_fail(self):
        """Test for updating the DCNM partition's static route. """
        subnet_lst = set()
        subnet_lst.add(self.subnet_id)
        subnet_lst.add(self.out_subnet_id)
        with mock.patch.object(self.native_fw.os_helper,
                               'get_subnet_nwk_excl',
                               return_value=[STATIC_SUB]),\
            mock.patch.object(self.native_fw.dcnm_obj,
                              'update_partition_static_route',
                              return_value=False) as upd_part,\
            mock.patch.object(self.native_fw.os_helper,
                              'delete_intf_router',
                              return_value=True) as del_intf_rtr:
            FakeClass.set_return(FP.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_fabric_gw,
                                  'end': self.out_end})
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_in_subnet_id',
                                 self.subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_subnet_id',
                                 self.out_subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_srvc_node_ip_addr',
                                 self.out_gw)
            parent = mock.MagicMock()
            parent.attach_mock(upd_part, 'update_partition_static_route')
            parent.attach_mock(del_intf_rtr, 'delete_intf_router')
            self.native_fw.tenant_dict[self.tenant_id] = (
                {'host': None, 'router_id': self.rtr_id})
            arg_dict = self.native_fw._create_arg_dict(self.tenant_id,
                                                       self.fw_data,
                                                       self.subnet_id,
                                                       self.out_subnet_id)
            self.native_fw.update_dcnm_partition_static_route(
                self.tenant_id, arg_dict)
        expected_calls = [
            mock.call.update_partition_static_route(
                self.tenant_name, fw_const.SERV_PART_NAME, [STATIC_SUB],
                vrf_prof=(
                    self.native_fw.cfg.firewall.fw_service_part_vrf_profile),
                service_node_ip=self.out_gw),
            mock.call.delete_intf_router(self.tenant_name,
                                         self.tenant_id,
                                         self.rtr_id,
                                         subnet_lst)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def _test_create_fw(self):
        port_data = self._get_port_data()
        subnet_lst = set()
        subnet_lst.add(self.subnet_id)
        subnet_lst.add(self.out_subnet_id)
        vm_vdp_data_in = self._get_vm_vdp_data('up', self.net_id,
                                               self.segmentation_id,
                                               'in', 'service.vnic.create')
        vm_vdp_data_out = self._get_vm_vdp_data('up', self.out_net_id,
                                                self.out_segmentation_id,
                                                'out', 'service.vnic.create')
        with mock.patch.object(self.native_fw.os_helper, 'add_intf_router',
                               return_value=True) as add_intf_rtr,\
                mock.patch.object(self.native_fw.os_helper,
                                  'get_subnet_nwk_excl',
                                  return_value=[STATIC_SUB]),\
                mock.patch.object(self.native_fw.dcnm_obj,
                                  'update_partition_static_route',
                                  return_value=True) as upd_part,\
                mock.patch.object(self.native_fw.os_helper,
                                  'program_rtr_default_gw',
                                  return_value=True) as prog_def_gw,\
                mock.patch.object(self.native_fw.os_helper,
                                  'program_rtr_all_nwk_next_hop',
                                  return_value=True) as prog_rtr_all_nwk,\
                mock.patch.object(self.native_fw.os_helper,
                                  'get_router_port_subnet',
                                  return_value=port_data),\
                mock.patch.object(self.native_fw.que_obj, 'put') as que_put:
            FakeClass.set_return(FP.FabricApi, 'get_in_ip_addr',
                                 {'subnet': self.in_subnet,
                                  'start': self.in_start,
                                  'sec_gateway': self.in_sec_gw,
                                  'gateway': self.in_fabric_gw,
                                  'end': self.in_end})
            FakeClass.set_return(FP.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_fabric_gw,
                                  'end': self.out_end})
            FakeClass.set_return(FP.FabricApi, 'get_in_srvc_node_ip_addr',
                                 self.in_gw)
            FakeClass.set_return(FP.FabricApi, 'get_out_srvc_node_ip_addr',
                                 self.out_gw)
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_in_net_id', self.net_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_net_id',
                                 self.out_net_id)
            FakeClass.set_return(FP.FabricApi, 'get_in_subnet_id',
                                 self.subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_subnet_id',
                                 self.out_subnet_id)
            parent = mock.MagicMock()
            parent.attach_mock(add_intf_rtr, 'add_intf_router')
            parent.attach_mock(upd_part, 'update_partition_static_route')
            parent.attach_mock(prog_def_gw, 'program_rtr_default_gw')
            parent.attach_mock(prog_rtr_all_nwk,
                               'program_rtr_all_nwk_next_hop')
            parent.attach_mock(que_put, 'put')
            self.native_fw.create_fw(self.tenant_id, self.fw_data)
        expected_calls = [
            mock.call.add_intf_router(self.rtr_id, self.tenant_id, subnet_lst),
            mock.call.update_partition_static_route(
                self.tenant_name, fw_const.SERV_PART_NAME, [STATIC_SUB],
                vrf_prof=(
                    self.native_fw.cfg.firewall.fw_service_part_vrf_profile),
                service_node_ip=self.out_gw),
            mock.call.program_rtr_default_gw(self.tenant_id, self.rtr_id,
                                             self.out_fabric_gw),
            mock.call.program_rtr_all_nwk_next_hop(
                self.tenant_id, self.rtr_id, self.in_fabric_gw,
                [self.in_subnet, self.out_subnet]),
            mock.call.put((34, TIME, vm_vdp_data_in)),
            mock.call.put((34, TIME, vm_vdp_data_out))]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_create_fw(self):
        """Create FW Test """
        self._test_create_fw()

    def _test_delete_fw(self):
        port_data = self._get_port_data()
        subnet_lst = set()
        subnet_lst.add(self.subnet_id)
        subnet_lst.add(self.out_subnet_id)
        vm_vdp_data_in = self._get_vm_vdp_data('down', self.net_id,
                                               self.segmentation_id,
                                               'in', 'service.vnic.delete')
        vm_vdp_data_out = self._get_vm_vdp_data('down', self.out_net_id,
                                                self.out_segmentation_id,
                                                'out', 'service.vnic.delete')
        with mock.patch.object(self.native_fw.os_helper,
                               'delete_intf_router',
                               return_value=True) as del_intf_rtr,\
                mock.patch.object(self.native_fw.os_helper,
                                  'get_router_port_subnet',
                                  return_value=port_data),\
                mock.patch.object(self.native_fw.que_obj, 'put') as que_put:

            FakeClass.set_return(
                FP.FabricApi, 'get_in_ip_addr',
                {'subnet': self.in_subnet, 'start': self.in_start,
                 'sec_gateway': self.in_sec_gw, 'gateway': self.in_fabric_gw,
                 'end': self.in_end})
            FakeClass.set_return(FP.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_fabric_gw,
                                  'end': self.out_end})
            FakeClass.set_return(FP.FabricApi, 'get_in_seg_vlan',
                                 [self.segmentation_id, self.vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_out_seg_vlan',
                                 [self.out_segmentation_id, self.out_vlan_id])
            FakeClass.set_return(FP.FabricApi, 'get_in_net_id', self.net_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_net_id',
                                 self.out_net_id)
            FakeClass.set_return(FP.FabricApi, 'get_in_subnet_id',
                                 self.subnet_id)
            FakeClass.set_return(FP.FabricApi, 'get_out_subnet_id',
                                 self.out_subnet_id)
            parent = mock.MagicMock()
            parent.attach_mock(que_put, 'put')
            parent.attach_mock(del_intf_rtr, 'delete_intf_router')
            self.native_fw.delete_fw(self.tenant_id, self.fw_data)
        expected_calls = [
            mock.call.put((34, TIME, vm_vdp_data_in)),
            mock.call.put((34, TIME, vm_vdp_data_out)),
            mock.call.delete_intf_router(self.tenant_name, self.tenant_id,
                                         self.rtr_id, subnet_lst)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_delete_fw(self):
        """Delete FW Test """
        self._test_delete_fw()

    def _test_nwk_create_notif(self):
        subnet_lst = set()
        subnet_lst.add(self.subnet_id)
        subnet_lst.add(self.out_subnet_id)
        with mock.patch.object(self.native_fw.os_helper, 'get_subnet_nwk_excl',
                               return_value=[NEW_STATIC_SUB]),\
            mock.patch.object(self.native_fw.os_helper, 'get_rtr_by_name',
                              return_value=[{'id': self.rtr_id}]),\
            mock.patch.object(self.native_fw.dcnm_obj,
                              'update_partition_static_route',
                              return_value=True) as upd_part,\
            mock.patch.object(self.native_fw.os_helper,
                              'program_rtr_nwk_next_hop',
                              return_value=True) as prog_rtr_nwk:
            FakeClass.set_return(FP.FabricApi, 'get_in_ip_addr',
                                 {'subnet': self.in_subnet,
                                  'start': self.in_start,
                                  'sec_gateway': self.in_sec_gw,
                                  'gateway': self.in_fabric_gw,
                                  'end': self.in_end})
            FakeClass.set_return(FP.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_fabric_gw,
                                  'end': self.out_end})
            FakeClass.set_return(FP.FabricApi, 'get_out_srvc_node_ip_addr',
                                 self.out_gw)
            parent = mock.MagicMock()
            parent.attach_mock(upd_part, 'update_partition_static_route')
            parent.attach_mock(prog_rtr_nwk, 'program_rtr_nwk_next_hop')
            self.native_fw.network_create_notif(self.tenant_id,
                                                self.tenant_name, NEW_CIDR)
        expected_calls = [
            mock.call.update_partition_static_route(
                self.tenant_name, fw_const.SERV_PART_NAME, [NEW_STATIC_SUB],
                vrf_prof=(
                    self.native_fw.cfg.firewall.fw_service_part_vrf_profile),
                service_node_ip=self.out_gw),
            mock.call.program_rtr_nwk_next_hop(self.rtr_id, self.in_fabric_gw,
                                               NEW_CIDR)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_nwk_create_notif(self):
        """Nwk Create Notif """
        self._test_nwk_create_notif()

    def _test_nwk_delete_notif(self):
        excl_lst = []
        excl_lst.append(self.in_subnet)
        excl_lst.append(self.out_subnet)
        with mock.patch.object(self.native_fw.os_helper, 'get_subnet_nwk_excl',
                               return_value=[NEW_STATIC_SUB]),\
            mock.patch.object(self.native_fw.os_helper, 'get_rtr_by_name',
                              return_value=[{'id': self.rtr_id}]),\
            mock.patch.object(self.native_fw.dcnm_obj,
                              'update_partition_static_route',
                              return_value=True) as upd_part,\
            mock.patch.object(self.native_fw.os_helper,
                              'remove_rtr_nwk_next_hop',
                              return_value=True) as prog_rtr_nwk:
            FakeClass.set_return(FP.FabricApi, 'get_in_ip_addr',
                                 {'subnet': self.in_subnet,
                                  'start': self.in_start,
                                  'sec_gateway': self.in_sec_gw,
                                  'gateway': self.in_fabric_gw,
                                  'end': self.in_end})
            FakeClass.set_return(FP.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_fabric_gw,
                                  'end': self.out_end})
            FakeClass.set_return(FP.FabricApi, 'get_out_srvc_node_ip_addr',
                                 self.out_gw)
            parent = mock.MagicMock()
            parent.attach_mock(upd_part, 'update_partition_static_route')
            parent.attach_mock(prog_rtr_nwk, 'remove_rtr_nwk_next_hop')
            self.native_fw.network_delete_notif(self.tenant_id,
                                                self.tenant_name, NEW_CIDR)
        expected_calls = [
            mock.call.update_partition_static_route(
                self.tenant_name, fw_const.SERV_PART_NAME, [NEW_STATIC_SUB],
                vrf_prof=(
                    self.native_fw.cfg.firewall.fw_service_part_vrf_profile),
                service_node_ip=self.out_gw),
            mock.call.remove_rtr_nwk_next_hop(self.rtr_id, self.in_fabric_gw,
                                              [NEW_STATIC_SUB], excl_lst)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_nwk_delete_notif(self):
        """Create Notif """
        self._test_nwk_delete_notif()
