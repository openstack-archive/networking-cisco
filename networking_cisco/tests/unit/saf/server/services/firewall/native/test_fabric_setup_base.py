# Copyright 2016 Cisco Systems.
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

from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.common import utils
from networking_cisco.apps.saf.db import dfa_db_models as dbm
from networking_cisco.apps.saf.server.services.firewall.native import (
    fabric_setup_base as fsb)
import networking_cisco.apps.saf.server.services.firewall.native.fw_constants \
    as fw_const

TENANT_NAME = 'TenantA'
TENANT_ID = '0000-1111-2222-5555'
FW_ID = '0000-aaaa-bbbb-ccce'
NET_ID = '0000-1111-bbbb-ccce'
OUT_NET_ID = '0000-1112-bbbb-ccce'
RTR_NET_ID = '0000-1113-bbbb-ccce'
SUBNET_ID = '0000-2222-bbbb-ccce'
OUT_SUBNET_ID = '0000-2222-bbbc-ccce'
RTR_SUBNET_ID = '0000-2222-bbbd-ccce'
FW_NAME = 'FwA'
POLCY_ID = '0000-aaaa-bbbb-cccc'
FW_TYPE = 'TE'
ROUTER_ID = '0000-aaaa-bbbb-5555'
IN_SUBNET = '100.100.11.0'
IN_SUBNET_AND_MASK = '100.100.11.0/24'
IN_START = '100.100.11.3'
IN_SEC_GW = '100.100.11.254'
IN_GW = '100.100.11.2'
IN_DCNM_GW = '100.100.11.1'
IN_END = '100.100.11.254'
SEGMENTATION_ID = 87999
OUT_SUBNET = '200.200.11.0'
OUT_SUBNET_AND_MASK = '200.200.11.0/24'
RTR_SUBNET_AND_MASK = '9.9.9.0/24'
OUT_START = '200.200.11.3'
OUT_SEC_GW = '200.200.11.254'
OUT_GW = '200.200.11.2'
OUT_DCNM_GW = '200.200.11.1'
OUT_END = '200.200.11.254'
OUT_SEGMENTATION_ID = 88000
EXT_PART = 34500

VLAN_ID = 0


try:
    OrderedDict = collections.OrderedDict
except AttributeError:
    import ordereddict
    OrderedDict = ordereddict.OrderedDict


class FakeClass(object):
    """Fake class. """
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


class FabricBaseTest(base.BaseTestCase):
    """A test suite to exercise the Fabric setup Base. """

    def setUp(self):
        '''Setup for the test scripts '''
        super(FabricBaseTest, self).setUp()
        self._init_values()
        config = self._fill_cfg()
        self.cfg = config
        self.cfg = config.CiscoDFAConfig().cfg

        fsb.FabricBase.__bases__ = (FakeClass.imitate(dbm.DfaDBMixin,
                                                      fsb.FabricApi),)
        FakeClass.set_return(dbm.DfaDBMixin, 'get_all_fw_db', dict())
        mock.patch('networking_cisco.apps.saf.db.dfa_db_models.'
                   'DfaSegmentTypeDriver').start()
        mock.patch('networking_cisco.apps.saf.db.dfa_db_models.'
                   'DfasubnetDriver').start()
        mock.patch('networking_cisco.apps.saf.server.'
                   'dfa_openstack_helper.DfaNeutronHelper').start()
        mock.patch('networking_cisco.apps.saf.db.dfa_db_models.'
                   'DfaDBMixin.update_fw_db').start()
        self.upd_fw_db_res_mock = mock.patch(
            'networking_cisco.apps.saf.db.dfa_db_models.DfaDBMixin.'
            'update_fw_db_result').start()
        self.app_state_final_res_mock = mock.patch(
            'networking_cisco.apps.saf.db.dfa_db_models.DfaDBMixin.'
            'append_state_final_result').start()
        self.fabric_base = fsb.FabricBase()
        self.add_nwk_db_mock = mock.patch.object(self.fabric_base,
                                                 'add_network_db').start()
        self.fabric_base.store_dcnm(mock.MagicMock())

    def _init_values(self):
        self.tenant_name = TENANT_NAME
        self.tenant_id = TENANT_ID
        self.net_id = NET_ID
        self.out_net_id = OUT_NET_ID
        self.rtr_net_id = RTR_NET_ID
        self.subnet_id = SUBNET_ID
        self.out_subnet_id = OUT_SUBNET_ID
        self.rtr_subnet_id = RTR_SUBNET_ID
        self.fw_id = FW_ID
        self.fw_name = FW_NAME
        self.policy_id = POLCY_ID
        self.fw_type = FW_TYPE
        self.router_id = ROUTER_ID
        self.in_subnet = IN_SUBNET
        self.in_subnet_and_mask = IN_SUBNET_AND_MASK
        self.in_gw = IN_GW
        self.in_dcnm_gw = IN_DCNM_GW
        self.in_sec_gw = IN_SEC_GW
        self.in_start = IN_START
        self.in_end = IN_END
        self.segmentation_id = SEGMENTATION_ID
        self.in_srvc_nwk_name = self.fw_id[0:4] + fw_const.IN_SERVICE_NWK + (
            self.fw_id[len(self.fw_id) - 4:])
        self.out_subnet = OUT_SUBNET
        self.out_subnet_and_mask = OUT_SUBNET_AND_MASK
        self.out_gw = OUT_GW
        self.out_dcnm_gw = OUT_DCNM_GW
        self.out_sec_gw = OUT_SEC_GW
        self.out_start = OUT_START
        self.out_end = OUT_END
        self.out_segmentation_id = OUT_SEGMENTATION_ID
        self.out_srvc_nwk_name = self.fw_id[0:4] + fw_const.OUT_SERVICE_NWK + (
            self.fw_id[len(self.fw_id) - 4:])
        self.mock_fw_dict = self._prepare_fw_dict()
        self.net_dict = self._prepare_net_dict("in")
        self.out_net_dict = self._prepare_net_dict("out")
        self.rtr_net_dict = self._prepare_rtr_net_dict()
        self.rtr_subnet_and_mask = RTR_SUBNET_AND_MASK
        self.ext_part = EXT_PART

    def _fill_cfg(self):
        config.default_firewall_opts['firewall'][
            'fw_auto_serv_nwk_create'] = True
        config.default_firewall_opts['firewall'][
            'fw_service_host_profile'] = fw_const.HOST_PROF
        config.default_firewall_opts['firewall'][
            'fw_service_host_fwd_mode'] = fw_const.HOST_FWD_MODE
        config.default_firewall_opts['firewall'][
            'fw_service_ext_profile'] = fw_const.EXT_PROF
        config.default_firewall_opts['firewall'][
            'fw_service_ext_fwd_mode'] = fw_const.EXT_FWD_MODE
        config.default_firewall_opts['firewall'][
            'fw_service_part_vrf_profile'] = fw_const.PART_PROF
        config.default_firewall_opts['firewall']['fw_mgmt_ip'] = '1.1.1.1'
        config.default_dcnm_opts['dcnm']['vlan_id_min'] = 2
        config.default_dcnm_opts['dcnm']['vlan_id_max'] = 200
        config.default_dcnm_opts['dcnm']['segmentation_id_min'] = 20000
        config.default_dcnm_opts['dcnm']['segmentation_id_max'] = 30000
        config.default_dcnm_opts['dcnm']['segmentation_reuse_timeout'] = 20
        return config

    def test_fabric_base_init(self):
        '''Wrapper for the init'''
        pass

    def _prepare_fw_dict(self):
        mock_fw_dict = {'rules': {}, 'tenant_name': self.tenant_name,
                        'tenant_id': self.tenant_id, 'fw_id': self.fw_id,
                        'fw_name': self.fw_name,
                        'firewall_policy_id': self.policy_id,
                        'fw_type': self.fw_type, 'router_id': self.router_id}
        return mock_fw_dict

    def _prepare_net_dict(self, direc):
        if direc == 'in':
            srvc_name = self.in_srvc_nwk_name
            srvc_seg = SEGMENTATION_ID
            srvc_prof = config.default_firewall_opts[
                'firewall']['fw_service_host_profile']
            srvc_fwd_mode = config.default_firewall_opts[
                'firewall']['fw_service_host_fwd_mode']
        else:
            srvc_name = self.out_srvc_nwk_name
            srvc_seg = OUT_SEGMENTATION_ID
            srvc_prof = config.default_firewall_opts[
                'firewall']['fw_service_ext_profile']
            srvc_fwd_mode = config.default_firewall_opts[
                'firewall']['fw_service_ext_fwd_mode']
        network_dict = {'tenant_id': self.tenant_id, 'name': srvc_name,
                        'segmentation_id': srvc_seg, 'vlan': VLAN_ID,
                        'config_profile': srvc_prof, 'fwd_mode': srvc_fwd_mode}
        return network_dict

    def _prepare_rtr_net_dict(self):
        rtr_nwk = self.fw_id[0:4] + fw_const.DUMMY_SERVICE_NWK + (
            self.fw_id[len(self.fw_id) - 4:])
        return {'tenant_id': self.tenant_id, 'name': rtr_nwk,
                'segmentation_id': None, 'vlan': None,
                'config_profile': None, 'fwd_mode': None}

    def _fill_fw_net_dict(self):
        return {'fw_id': self.fw_id, 'tenant_id': self.tenant_id,
                'name': self.fw_name, 'in_service_ip': self.in_start,
                'in_network_id': self.net_id}

    def _fill_fw_net_res_dict(self):
        fw_net_dict2 = self._fill_fw_net_dict()
        fw_net_dict2['os_status'] = fw_const.OS_IN_NETWORK_CREATE_SUCCESS
        return fw_net_dict2

    def _fill_fw_out_net_dict(self):
        return {'fw_id': self.fw_id, 'tenant_id': self.tenant_id,
                'name': self.fw_name, 'out_service_ip': self.out_start,
                'out_network_id': self.out_net_id}

    def _fill_fw_rtr_net_dict(self):
        return {'router_id': self.router_id, 'name': self.fw_name,
                'router_net_id': self.rtr_net_id,
                'tenant_id': self.tenant_id,
                'fw_id': self.fw_id,
                'router_subnet_id': self.rtr_subnet_id,
                'os_status': fw_const.OS_DUMMY_RTR_CREATE_SUCCESS}

    def _fill_fw_rtr_net_dict_virt(self):
        return {'router_id': self.router_id, 'name': self.fw_name,
                'router_net_id': None,
                'tenant_id': self.tenant_id,
                'fw_id': self.fw_id, 'router_subnet_id': None,
                'os_status': fw_const.OS_DUMMY_RTR_CREATE_SUCCESS}

    def _fill_fw_out_net_res_dict(self):
        fw_net_dict2 = self._fill_fw_out_net_dict()
        fw_net_dict2['os_status'] = fw_const.OS_OUT_NETWORK_CREATE_SUCCESS
        return fw_net_dict2

    def _fill_fw_dcnm_rest_net_dict(self):
        return {
            'status': 'ACTIVE', 'admin_state_up': True,
            'tenant_id': self.tenant_id, 'provider:network_type': 'local',
            'vlan_id': VLAN_ID, 'segmentation_id': self.segmentation_id,
            'mob_domain': False, 'mob_domain_name': None,
            'name': self.in_srvc_nwk_name, 'part_name': None,
            'config_profile': config.default_firewall_opts[
                'firewall']['fw_service_host_profile'],
            'fwd_mode': config.default_firewall_opts[
                'firewall']['fw_service_host_fwd_mode']}

    def _fill_fw_dcnm_rest_subnet_dict(self):
        name = self.fw_id[0:4] + fw_const.IN_SERVICE_SUBNET + (
            self.fw_id[len(self.fw_id) - 4:])
        alloc_pool_dict = {}
        alloc_pool_dict['start'] = self.in_start
        alloc_pool_dict['end'] = self.in_end
        fw_subnet_dict = {'name': name,
                          'enable_dhcp': False,
                          'tenant_id': self.tenant_id,
                          'cidr': self.in_subnet_and_mask,
                          'gateway_ip': self.in_dcnm_gw,
                          'secondary_gw': self.in_sec_gw,
                          'ip_version': 4}
        fw_subnet_dict['allocation_pools'] = []
        fw_subnet_dict['allocation_pools'].append(alloc_pool_dict)
        return fw_subnet_dict

    def _fill_fw_dcnm_rest_out_net_dict(self):
        return {
            'status': 'ACTIVE', 'admin_state_up': True,
            'tenant_id': self.tenant_id, 'provider:network_type': 'local',
            'vlan_id': VLAN_ID, 'segmentation_id': self.out_segmentation_id,
            'mob_domain': False, 'mob_domain_name': None,
            'name': self.out_srvc_nwk_name,
            'part_name': fw_const.SERV_PART_NAME,
            'config_profile': config.default_firewall_opts[
                'firewall']['fw_service_ext_profile'],
            'fwd_mode': config.default_firewall_opts[
                'firewall']['fw_service_ext_fwd_mode']}

    def _fill_fw_dcnm_rest_out_subnet_dict(self):
        name = self.fw_id[0:4] + fw_const.OUT_SERVICE_SUBNET + (
            self.fw_id[len(self.fw_id) - 4:])
        alloc_pool_dict = {}
        alloc_pool_dict['start'] = self.out_start
        alloc_pool_dict['end'] = self.out_end
        fw_subnet_dict = {'name': name,
                          'enable_dhcp': False,
                          'tenant_id': self.tenant_id,
                          'cidr': self.out_subnet_and_mask,
                          'gateway_ip': self.out_dcnm_gw,
                          'secondary_gw': self.out_sec_gw,
                          'ip_version': 4}
        fw_subnet_dict['allocation_pools'] = []
        fw_subnet_dict['allocation_pools'].append(alloc_pool_dict)
        return fw_subnet_dict

    def _fill_fw_dcnm_net_dict(self):
        return {'router_id': self.router_id,
                'out_network_id': self.out_net_id,
                'name': self.fw_name,
                'router_net_id': self.rtr_net_id,
                'tenant_id': self.tenant_id,
                'fw_id': self.fw_id,
                'dcnm_status': fw_const.DCNM_IN_NETWORK_CREATE_SUCCESS,
                'in_network_id': self.net_id,
                'out_service_ip': None,
                'os_status': fw_const.OS_DUMMY_RTR_CREATE_SUCCESS,
                'router_subnet_id': self.rtr_subnet_id,
                'in_service_ip': None}

    def _fill_fw_dcnm_out_net_dict(self):
        return {'router_id': self.router_id,
                'out_network_id': self.out_net_id,
                'name': self.fw_name,
                'router_net_id': self.rtr_net_id,
                'tenant_id': self.tenant_id,
                'fw_id': self.fw_id,
                'dcnm_status': fw_const.DCNM_OUT_NETWORK_CREATE_SUCCESS,
                'in_network_id': self.net_id,
                'out_network_id': self.out_net_id,
                'out_service_ip': None,
                'os_status': fw_const.OS_DUMMY_RTR_CREATE_SUCCESS,
                'router_subnet_id': self.rtr_subnet_id,
                'in_service_ip': None,
                'out_service_ip': None}

    def _fill_fw_dcnm_part_upd_dict(self, direc):
        dcnm_status = fw_const.DCNM_IN_PART_UPDATE_SUCCESS \
            if direc == "in" else fw_const.DCNM_OUT_PART_UPDATE_SUCCESS
        fw_part_dict = {'tenant_id': self.tenant_id,
                        'fw_id': self.fw_id,
                        'dcnm_status': dcnm_status,
                        'name': self.fw_name}
        return fw_part_dict

    def _fill_fw_dcnm_part_create_dict(self):
        return {'tenant_id': self.tenant_id,
                'fw_id': self.fw_id,
                'dcnm_status': fw_const.DCNM_OUT_PART_CREATE_SUCCESS,
                'name': self.fw_name}

    def _fill_fw_del_net_dict(self):
        return {'router_id': self.router_id, 'name': self.fw_name,
                'router_net_id': self.rtr_net_id,
                'tenant_id': self.tenant_id,
                'fw_id': self.fw_id, 'out_network_id': self.out_net_id,
                'in_network_id': self.net_id, 'in_service_ip': None,
                'out_service_ip': None,
                'router_subnet_id': self.rtr_subnet_id}

    def _fill_fw_db_data(self, state):
        fw_data = dict()
        compl_result = fw_const.RESULT_FW_CREATE_INIT + '(' + str(state) + ')'
        fw_data[self.fw_id] = {
            'tenant_id': self.tenant_id, 'name': self.fw_name,
            'in_network_id': self.net_id, 'out_network_id': self.out_net_id,
            'os_status': fw_const.OS_DUMMY_RTR_CREATE_SUCCESS,
            'result': compl_result, 'router_id': self.router_id,
            'router_net_id': self.rtr_net_id,
            'router_subnet_id': self.rtr_subnet_id}
        return fw_data

    def test_create_in_nwk(self):
        """Create IN Network. """
        id_list = []
        id_list.append(self.net_id)
        id_list.append(self.subnet_id)
        fw_net_dict2 = self._fill_fw_net_res_dict()
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.OS_IN_NETWORK_STATE),\
            mock.patch.object(self.fabric_base.os_helper, 'create_network',
                              return_value=id_list) as create_nwk:
            FakeClass.set_return(fsb.FabricApi, 'get_in_ip_addr',
                                 {'subnet': self.in_subnet,
                                  'start': self.in_start,
                                  'sec_gateway': self.in_sec_gw,
                                  'gateway': self.in_gw,
                                  'end': self.in_end})
            self.fabric_base.service_segs.allocate_segmentation_id.\
                return_value = self.segmentation_id
            self.fabric_base.fabric_fsm[fw_const.OS_OUT_NETWORK_STATE][0] = \
                mock.MagicMock()
            self.fabric_base.fabric_fsm[fw_const.OS_OUT_NETWORK_STATE][0].\
                return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            parent = mock.MagicMock()
            parent.attach_mock(create_nwk, 'create_network')
            parent.attach_mock(self.add_nwk_db_mock, 'add_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, True,
                                               fw_const.RESULT_FW_CREATE_INIT)
        expected_calls = [mock.call.create_network(self.in_srvc_nwk_name,
                                                   self.tenant_id,
                                                   self.in_subnet_and_mask,
                                                   gw=self.in_gw),
                          mock.call.add_network_db(self.net_id, self.net_dict,
                                                   fw_const.FW_CONST,
                                                   'SUCCESS'),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'), fw_net_dict2),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.OS_OUT_NETWORK_STATE),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.OS_OUT_NETWORK_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_create_in_nwk_fail(self):
        """Create IN Network Fail.

        The Openstack create network helper function is mocked to return a
        failure.
        """
        id_list = []
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.OS_IN_NETWORK_STATE),\
            mock.patch.object(self.fabric_base.os_helper, 'create_network',
                              return_value=id_list) as create_nwk:
            FakeClass.set_return(fsb.FabricApi, 'get_in_ip_addr',
                                 {'subnet': self.in_subnet,
                                  'start': self.in_start,
                                  'sec_gateway': self.in_sec_gw,
                                  'gateway': self.in_gw,
                                  'end': self.in_end})
            self.fabric_base.service_segs.allocate_segmentation_id.\
                return_value = self.segmentation_id
            self.fabric_base.fabric_fsm[fw_const.OS_OUT_NETWORK_STATE][0] = \
                mock.MagicMock()
            self.fabric_base.fabric_fsm[fw_const.OS_OUT_NETWORK_STATE][0].\
                return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            parent = mock.MagicMock()
            parent.attach_mock(create_nwk, 'create_network')
            parent.attach_mock(self.add_nwk_db_mock, 'add_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, True,
                                               fw_const.RESULT_FW_CREATE_INIT)
        expected_calls = [mock.call.create_network(self.in_srvc_nwk_name,
                                                   self.tenant_id,
                                                   self.in_subnet_and_mask,
                                                   gw=self.in_gw),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.OS_IN_NETWORK_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)
        self.add_nwk_db_mock.assert_not_called()
        self.upd_fw_db_res_mock.assert_not_called()

    def test_create_out_nwk(self):
        """Create Out Network Test. """
        id_list = []
        id_list.append(self.out_net_id)
        id_list.append(self.out_subnet_id)
        fw_net_dict2 = self._fill_fw_out_net_res_dict()
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.OS_OUT_NETWORK_STATE),\
            mock.patch.object(self.fabric_base.os_helper, 'create_network',
                              return_value=id_list) as create_nwk:
            FakeClass.set_return(fsb.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_gw,
                                  'end': self.out_end})
            self.fabric_base.service_segs.allocate_segmentation_id.\
                return_value = self.out_segmentation_id
            self.fabric_base.fabric_fsm[fw_const.OS_DUMMY_RTR_STATE][0] = \
                mock.MagicMock()
            self.fabric_base.fabric_fsm[fw_const.OS_DUMMY_RTR_STATE][0].\
                return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            parent = mock.MagicMock()
            parent.attach_mock(create_nwk, 'create_network')
            parent.attach_mock(self.add_nwk_db_mock, 'add_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, True,
                                               fw_const.RESULT_FW_CREATE_INIT)
        expected_calls = [mock.call.create_network(self.out_srvc_nwk_name,
                                                   self.tenant_id,
                                                   self.out_subnet_and_mask,
                                                   gw=self.out_gw),
                          mock.call.add_network_db(self.out_net_id,
                                                   self.out_net_dict,
                                                   fw_const.FW_CONST,
                                                   'SUCCESS'),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'), fw_net_dict2),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.OS_DUMMY_RTR_STATE),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.OS_DUMMY_RTR_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_create_out_nwk_fail(self):
        """Create OUT Network Fail.

        The Openstack create network helper function is mocked to return a
        failure.
        """
        id_list = [None, None]
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.OS_OUT_NETWORK_STATE),\
            mock.patch.object(self.fabric_base.os_helper, 'create_network',
                              return_value=id_list) as create_nwk:
            FakeClass.set_return(fsb.FabricApi, 'get_out_ip_addr',
                                 {'subnet': self.out_subnet,
                                  'start': self.out_start,
                                  'sec_gateway': self.out_sec_gw,
                                  'gateway': self.out_gw,
                                  'end': self.out_end})
            self.fabric_base.service_segs.allocate_segmentation_id.\
                return_value = self.out_segmentation_id
            self.fabric_base.fabric_fsm[fw_const.OS_DUMMY_RTR_STATE][0] = \
                mock.MagicMock()
            self.fabric_base.fabric_fsm[fw_const.OS_DUMMY_RTR_STATE][0].\
                return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            parent = mock.MagicMock()
            parent.attach_mock(create_nwk, 'create_network')
            parent.attach_mock(self.add_nwk_db_mock, 'add_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, True,
                                               fw_const.RESULT_FW_CREATE_INIT)
        expected_calls = [mock.call.create_network(self.out_srvc_nwk_name,
                                                   self.tenant_id,
                                                   self.out_subnet_and_mask,
                                                   gw=self.out_gw),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.OS_OUT_NETWORK_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)
        self.add_nwk_db_mock.assert_not_called()
        self.upd_fw_db_res_mock.assert_not_called()

    def test_create_os_dummy_rtr(self):
        """Create Dummy Router Test. """
        id_list = []
        id_list.append(self.rtr_net_id)
        id_list.append(self.rtr_subnet_id)
        rtr_net_list = set()
        rtr_net_list.add(self.rtr_subnet_id)
        rtr_net_dict = self._fill_fw_rtr_net_dict()
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.OS_DUMMY_RTR_STATE),\
            mock.patch.object(self.fabric_base.os_helper, 'create_network',
                              return_value=id_list) as create_nwk,\
            mock.patch.object(self.fabric_base.os_helper, 'add_intf_router',
                              return_value=True) as add_intf_rtr:
            self.fabric_base.fabric_fsm[fw_const.DCNM_IN_NETWORK_STATE][0] = \
                mock.MagicMock()
            self.fabric_base.fabric_fsm[fw_const.DCNM_IN_NETWORK_STATE][0].\
                return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            parent = mock.MagicMock()
            parent.attach_mock(create_nwk, 'create_network')
            parent.attach_mock(add_intf_rtr, 'add_intf_router')
            parent.attach_mock(self.add_nwk_db_mock, 'add_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, False,
                                               fw_const.RESULT_FW_CREATE_INIT)
        rtr_nwk_name = self.fw_id[0:4] + fw_const.DUMMY_SERVICE_NWK + (
            self.fw_id[len(self.fw_id) - 4:])
        expected_calls = [mock.call.create_network(rtr_nwk_name,
                                                   self.tenant_id,
                                                   self.rtr_subnet_and_mask),
                          mock.call.add_network_db(self.rtr_net_id,
                                                   self.rtr_net_dict,
                                                   fw_const.FW_CONST,
                                                   'SUCCESS'),
                          mock.call.add_intf_router(self.router_id,
                                                    self.tenant_id,
                                                    rtr_net_list),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'), rtr_net_dict),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.DCNM_IN_NETWORK_STATE),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.DCNM_IN_NETWORK_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_create_os_dummy_rtr_fail(self):
        """Create Dummy Router Fail Test.

        The Openstack add interface to router helper function is mocked to
        return a failure.
        """
        id_list = []
        id_list.append(self.rtr_net_id)
        id_list.append(self.rtr_subnet_id)
        rtr_net_list = set()
        rtr_net_list.add(self.rtr_subnet_id)
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.OS_DUMMY_RTR_STATE),\
            mock.patch.object(self.fabric_base.os_helper, 'create_network',
                              return_value=id_list) as create_nwk,\
            mock.patch.object(self.fabric_base.os_helper, 'add_intf_router',
                              return_value=False) as add_intf_rtr,\
            mock.patch.object(self.fabric_base.os_helper, 'delete_network',
                              return_value=id_list):
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            parent = mock.MagicMock()
            parent.attach_mock(create_nwk, 'create_network')
            parent.attach_mock(add_intf_rtr, 'add_intf_router')
            parent.attach_mock(self.add_nwk_db_mock, 'add_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, False,
                                               fw_const.RESULT_FW_CREATE_INIT)
        rtr_nwk_name = self.fw_id[0:4] + fw_const.DUMMY_SERVICE_NWK + (
            self.fw_id[len(self.fw_id) - 4:])
        expected_calls = [mock.call.create_network(rtr_nwk_name,
                                                   self.tenant_id,
                                                   self.rtr_subnet_and_mask),
                          mock.call.add_network_db(self.rtr_net_id,
                                                   self.rtr_net_dict,
                                                   fw_const.FW_CONST,
                                                   'SUCCESS'),
                          mock.call.add_intf_router(self.router_id,
                                                    self.tenant_id,
                                                    rtr_net_list),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.OS_DUMMY_RTR_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)
        self.upd_fw_db_res_mock.assert_not_called()

    def test_create_os_dummy_rtr_virt(self):
        """Create Dummy Router Virt Test. """
        id_list = []
        id_list.append(self.rtr_net_id)
        id_list.append(self.rtr_subnet_id)
        rtr_net_list = set()
        rtr_net_list.add(self.rtr_subnet_id)
        rtr_net_dict = self._fill_fw_rtr_net_dict_virt()
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.OS_DUMMY_RTR_STATE),\
            mock.patch.object(self.fabric_base.os_helper, 'create_network',
                              return_value=id_list) as create_nwk,\
            mock.patch.object(self.fabric_base.os_helper, 'add_intf_router',
                              return_value=True) as add_intf_rtr:
            self.fabric_base.fabric_fsm[fw_const.DCNM_IN_NETWORK_STATE][0] = \
                mock.MagicMock()
            self.fabric_base.fabric_fsm[fw_const.DCNM_IN_NETWORK_STATE][0].\
                return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            parent = mock.MagicMock()
            parent.attach_mock(create_nwk, 'create_network')
            parent.attach_mock(add_intf_rtr, 'add_intf_router')
            parent.attach_mock(self.add_nwk_db_mock, 'add_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, True,
                                               fw_const.RESULT_FW_CREATE_INIT)
        expected_calls = [
            mock.call.update_fw_db_result(self.mock_fw_dict.get('fw_id'),
                                          rtr_net_dict),
            mock.call.append_state_final_result(
                self.mock_fw_dict.get('fw_id'), fw_const.RESULT_FW_CREATE_INIT,
                fw_const.DCNM_IN_NETWORK_STATE),
            mock.call.append_state_final_result(
                self.mock_fw_dict.get('fw_id'), fw_const.RESULT_FW_CREATE_INIT,
                fw_const.DCNM_IN_NETWORK_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)
        create_nwk.assert_not_called()
        self.add_nwk_db_mock.assert_not_called()
        add_intf_rtr.assert_not_called()

    def test_create_dcnm_in_nwk(self):
        """Create IN Network Test.

        This function relies on the state information filled by previous
        functions. So, rather than starting fresh, we shall populate the
        FW DB. This is equivalent to restarting the enabler server and it
        reading the DB and populating the local cache
        """
        fw_dcnm_net_dict = self._fill_fw_dcnm_net_dict()
        fw_dcnm_rest_net_dict = self._fill_fw_dcnm_rest_net_dict()
        fw_dcnm_rest_subnet_dict = self._fill_fw_dcnm_rest_subnet_dict()
        fake_db_net = {'segmentation_id': self.segmentation_id,
                       'vlan': VLAN_ID}
        fake_net_obj = utils.Dict2Obj(fake_db_net)
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.DCNM_IN_NETWORK_STATE),\
            mock.patch('networking_cisco.apps.saf.common.utils.'
                       'Dict2Obj') as dict_obj,\
            mock.patch.object(self.fabric_base.dcnm_obj,
                              'create_service_network') as create_nwk:
            self.fabric_base.fabric_fsm[
                fw_const.DCNM_IN_PART_UPDATE_STATE][0] = mock.MagicMock()
            self.fabric_base.fabric_fsm[
                fw_const.DCNM_IN_PART_UPDATE_STATE][0].return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(
                dbm.DfaDBMixin, 'get_all_fw_db',
                self._fill_fw_db_data(fw_const.DCNM_IN_NETWORK_STATE))
            FakeClass.set_return(dbm.DfaDBMixin, 'get_network', fake_net_obj)
            self.fabric_base.service_in_ip.get_subnet_by_netid.\
                return_value = self.in_subnet
            self.fabric_base.populate_local_cache()
            parent = mock.MagicMock()
            parent.attach_mock(dict_obj, 'Dict2Obj')
            parent.attach_mock(dict_obj, 'Dict2Obj')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, True,
                                               fw_const.RESULT_FW_CREATE_INIT)
        expected_calls = [mock.call.Dict2Obj(fw_dcnm_rest_net_dict),
                          mock.call.Dict2Obj(fw_dcnm_rest_subnet_dict),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_dcnm_net_dict),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.DCNM_IN_PART_UPDATE_STATE),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.DCNM_IN_PART_UPDATE_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(create_nwk.called, True)

    def test_create_dcnm_in_part_update(self):
        """DCNM Update IN Partition Test. """
        fw_dcnm_part_dict = self._fill_fw_dcnm_part_upd_dict("in")
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.DCNM_IN_PART_UPDATE_STATE),\
            mock.patch.object(self.fabric_base.dcnm_obj,
                              'update_project') as update_proj:
            self.fabric_base.fabric_fsm[fw_const.DCNM_OUT_PART_STATE][0] = \
                mock.MagicMock()
            self.fabric_base.fabric_fsm[fw_const.DCNM_OUT_PART_STATE][0].\
                return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(fsb.FabricApi, 'get_in_ip_addr',
                                 {'subnet': self.in_subnet,
                                  'start': self.in_start,
                                  'sec_gateway': self.in_sec_gw,
                                  'gateway': self.in_gw,
                                  'end': self.in_end})
            parent = mock.MagicMock()
            parent.attach_mock(update_proj, 'update_project')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, True,
                                               fw_const.RESULT_FW_CREATE_INIT)
        expected_calls = [mock.call.update_project(self.tenant_name, None,
                                                   desc='Service Partition',
                                                   service_node_ip=self.in_gw,
                                                   vrf_prof=None),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_dcnm_part_dict),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.DCNM_OUT_PART_STATE),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.DCNM_OUT_PART_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_create_dcnm_out_part(self):
        """DCNM Out Part Create Test. """
        fw_dcnm_part_dict = self._fill_fw_dcnm_part_create_dict()
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.DCNM_OUT_PART_STATE),\
            mock.patch.object(self.fabric_base.dcnm_obj,
                              'create_partition') as create_part:
            self.fabric_base.fabric_fsm[fw_const.DCNM_OUT_NETWORK_STATE][0] = \
                mock.MagicMock()
            self.fabric_base.fabric_fsm[fw_const.DCNM_OUT_NETWORK_STATE][0].\
                return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            parent = mock.MagicMock()
            parent.attach_mock(create_part, 'create_partition')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, True,
                                               fw_const.RESULT_FW_CREATE_INIT)
        expected_calls = [
            mock.call.create_partition(
                self.tenant_name, fw_const.SERV_PART_NAME, None,
                config.default_firewall_opts[
                    'firewall']['fw_service_part_vrf_profile'],
                desc='Service Partition'),
            mock.call.update_fw_db_result(self.mock_fw_dict.get('fw_id'),
                                          fw_dcnm_part_dict),
            mock.call.append_state_final_result(
                self.mock_fw_dict.get('fw_id'), fw_const.RESULT_FW_CREATE_INIT,
                fw_const.DCNM_OUT_NETWORK_STATE),
            mock.call.append_state_final_result(
                self.mock_fw_dict.get('fw_id'),
                fw_const.RESULT_FW_CREATE_INIT,
                fw_const.DCNM_OUT_NETWORK_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_create_dcnm_out_nwk(self):
        """Create OUT Network Test.

        This function relies on the state information filled by previous
        functions. So, rather than starting fresh, we shall populate the
        FW DB. This is equivalent to restarting the enabler server and it
        reading the DB and populating the local cache.
        """
        fw_dcnm_out_net_dict = self._fill_fw_dcnm_out_net_dict()
        fw_dcnm_rest_out_net_dict = self._fill_fw_dcnm_rest_out_net_dict()
        fw_dcnm_rest_out_subnet_dict = (
            self._fill_fw_dcnm_rest_out_subnet_dict())
        fake_db_net = {'segmentation_id': self.out_segmentation_id,
                       'vlan': VLAN_ID}
        fake_net_obj = utils.Dict2Obj(fake_db_net)
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.DCNM_OUT_NETWORK_STATE),\
            mock.patch('networking_cisco.apps.saf.common.utils.'
                       'Dict2Obj') as dict_obj,\
            mock.patch.object(self.fabric_base.dcnm_obj,
                              'create_service_network') as create_nwk:
            self.fabric_base.fabric_fsm[
                fw_const.DCNM_OUT_PART_UPDATE_STATE][0] = mock.MagicMock()
            self.fabric_base.fabric_fsm[
                fw_const.DCNM_OUT_PART_UPDATE_STATE][0].return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(
                dbm.DfaDBMixin, 'get_all_fw_db',
                self._fill_fw_db_data(fw_const.DCNM_OUT_NETWORK_STATE))
            FakeClass.set_return(dbm.DfaDBMixin, 'get_network', fake_net_obj)
            self.fabric_base.service_out_ip.get_subnet_by_netid.\
                return_value = self.out_subnet
            self.fabric_base.populate_local_cache()
            parent = mock.MagicMock()
            parent.attach_mock(dict_obj, 'Dict2Obj')
            parent.attach_mock(dict_obj, 'Dict2Obj')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, True,
                                               fw_const.RESULT_FW_CREATE_INIT)
        expected_calls = [mock.call.Dict2Obj(fw_dcnm_rest_out_net_dict),
                          mock.call.Dict2Obj(fw_dcnm_rest_out_subnet_dict),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_dcnm_out_net_dict),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.DCNM_OUT_PART_UPDATE_STATE),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_CREATE_INIT,
                              fw_const.DCNM_OUT_PART_UPDATE_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(create_nwk.called, True)

    def test_create_dcnm_out_part_update(self):
        """DCNM Update OUT Partition Test. """
        fw_dcnm_part_dict = self._fill_fw_dcnm_part_upd_dict("out")
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.DCNM_OUT_PART_UPDATE_STATE),\
            mock.patch.object(self.fabric_base.dcnm_obj,
                              'get_partition_segmentId',
                              return_value=self.ext_part),\
            mock.patch.object(self.fabric_base.dcnm_obj,
                              'update_project') as update_proj:
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            parent = mock.MagicMock()
            parent.attach_mock(update_proj, 'update_project')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.prepare_fabric_fw(self.tenant_id,
                                               self.mock_fw_dict, True,
                                               fw_const.RESULT_FW_CREATE_INIT)
        expected_calls = [
            mock.call.update_project(
                self.tenant_name, fw_const.SERV_PART_NAME,
                dci_id=self.ext_part,
                vrf_prof=config.default_firewall_opts[
                    'firewall']['fw_service_part_vrf_profile']),
            mock.call.update_fw_db_result(self.mock_fw_dict.get('fw_id'),
                                          fw_dcnm_part_dict),
            mock.call.append_state_final_result(
                self.mock_fw_dict.get('fw_id'), fw_const.RESULT_FW_CREATE_INIT,
                fw_const.FABRIC_PREPARE_DONE_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def _test_delete_nwk(self, state, direc):
        fw_net_dict2 = self._fill_fw_del_net_dict()
        if direc == "in":
            net_id = self.net_id
            segmentation_id = self.segmentation_id
            subnet = self.in_subnet
            net_id = self.net_id
            fw_net_dict2['os_status'] = fw_const.OS_IN_NETWORK_DEL_SUCCESS
        else:
            net_id = self.out_net_id
            segmentation_id = self.out_segmentation_id
            subnet = self.out_subnet
            net_id = self.out_net_id
            fw_net_dict2['os_status'] = fw_const.OS_OUT_NETWORK_DEL_SUCCESS
        fw_db_data = self._fill_fw_db_data(state)
        fake_fw_obj = utils.Dict2Obj(fw_db_data.get(self.fw_id))
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state', return_value=state),\
            mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                       'native.fabric_setup_base.ServiceIpSegTenantMap.'
                       'fixup_state', return_value=state),\
            mock.patch.object(self.fabric_base.os_helper,
                              'delete_network_all_subnets',
                              return_value=True) as delete_nwk,\
            mock.patch.object(
                self.fabric_base.service_segs,
                'release_segmentation_id') as rel_seg, \
            mock.patch.object(
                self.fabric_base.service_in_ip, 'release_subnet') as rel_sub, \
            mock.patch.object(self.fabric_base,
                              'delete_network_db') as del_nwk_db:

            if direc == "in":
                FakeClass.set_return(fsb.FabricApi, 'get_in_ip_addr',
                                     {'subnet': self.in_subnet,
                                      'start': self.in_start,
                                      'sec_gateway': self.in_sec_gw,
                                      'gateway': self.in_gw,
                                      'end': self.in_end})
                self.fabric_base.fabric_fsm[fw_const.INIT_STATE][1] = \
                    mock.MagicMock()
                self.fabric_base.fabric_fsm[fw_const.INIT_STATE][1].\
                    return_value = False
            else:
                FakeClass.set_return(fsb.FabricApi, 'get_out_ip_addr',
                                     {'subnet': self.out_subnet,
                                      'start': self.out_start,
                                      'sec_gateway': self.out_sec_gw,
                                      'gateway': self.out_gw,
                                      'end': self.out_end})
                self.fabric_base.fabric_fsm[fw_const.OS_IN_NETWORK_STATE][1] = \
                    mock.MagicMock()
                self.fabric_base.fabric_fsm[fw_const.OS_IN_NETWORK_STATE][1].\
                    return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(dbm.DfaDBMixin, 'get_all_fw_db', fw_db_data)
            FakeClass.set_return(dbm.DfaDBMixin, 'get_fw', [fake_fw_obj, None])
            if direc == "in":
                FakeClass.set_return(fsb.FabricApi, 'get_in_seg_vlan',
                                     [self.segmentation_id, VLAN_ID])
                self.fabric_base.service_in_ip.get_subnet_by_netid.\
                    return_value = self.in_subnet
                prev_state = fw_const.INIT_STATE
            else:
                FakeClass.set_return(fsb.FabricApi, 'get_out_seg_vlan',
                                     [self.out_segmentation_id, VLAN_ID])
                self.fabric_base.service_out_ip.get_subnet_by_netid.\
                    return_value = self.out_subnet
                prev_state = fw_const.OS_IN_NETWORK_STATE
            self.fabric_base.populate_local_cache()
            parent = mock.MagicMock()
            parent.attach_mock(delete_nwk, 'delete_network_all_subnets')
            parent.attach_mock(del_nwk_db, 'delete_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(rel_seg, 'release_segmentation_id')
            parent.attach_mock(rel_sub, 'release_subnet')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.delete_fabric_fw(self.tenant_id,
                                              self.mock_fw_dict, True,
                                              fw_const.RESULT_FW_DELETE_INIT)
        expected_calls = [mock.call.delete_network_all_subnets(net_id),
                          mock.call.release_segmentation_id(segmentation_id),
                          mock.call.release_subnet(subnet),
                          mock.call.delete_network_db(net_id),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'), fw_net_dict2),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT, prev_state)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_delete_in_nwk(self):
        """Delete IN Network Test. """
        self._test_delete_nwk(fw_const.OS_IN_NETWORK_STATE, "in")

    def _test_delete_nwk_fail(self, direc):
        """Internal function for delete network failure case.

        The Openstack delete network helper function is mocked to
        return a failure.
        """
        fw_net_dict2 = self._fill_fw_del_net_dict()
        if direc == "in":
            fw_net_dict2['os_status'] = fw_const.OS_IN_NETWORK_DEL_FAIL
            state = fw_const.OS_IN_NETWORK_STATE
            net_id = self.net_id
        else:
            fw_net_dict2['os_status'] = fw_const.OS_OUT_NETWORK_DEL_FAIL
            state = fw_const.OS_OUT_NETWORK_STATE
            net_id = self.out_net_id
        fw_db_data = self._fill_fw_db_data(state)
        fake_fw_obj = utils.Dict2Obj(fw_db_data.get(self.fw_id))
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state', return_value=state),\
            mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                       'native.fabric_setup_base.ServiceIpSegTenantMap.'
                       'fixup_state', return_value=state),\
            mock.patch.object(self.fabric_base.os_helper,
                              'delete_network_all_subnets',
                              return_value=False) as delete_nwk,\
            mock.patch.object(
                self.fabric_base.service_segs,
                'release_segmentation_id') as rel_seg, \
            mock.patch.object(
                self.fabric_base.service_in_ip, 'release_subnet') as rel_sub, \
            mock.patch.object(self.fabric_base,
                              'delete_network_db') as del_nwk_db:
            if direc == "in":
                FakeClass.set_return(fsb.FabricApi, 'get_in_ip_addr',
                                     {'subnet': self.in_subnet,
                                      'start': self.in_start,
                                      'sec_gateway': self.in_sec_gw,
                                      'gateway': self.in_gw,
                                      'end': self.in_end})
                self.fabric_base.fabric_fsm[fw_const.INIT_STATE][0] = \
                    mock.MagicMock()
                self.fabric_base.fabric_fsm[fw_const.INIT_STATE][0].\
                    return_value = False
                FakeClass.set_return(fsb.FabricApi, 'get_in_seg_vlan',
                                     [self.segmentation_id, VLAN_ID])
                self.fabric_base.service_in_ip.get_subnet_by_netid.\
                    return_value = self.in_subnet
            else:
                FakeClass.set_return(fsb.FabricApi, 'get_out_ip_addr',
                                     {'subnet': self.out_subnet,
                                      'start': self.out_start,
                                      'sec_gateway': self.out_sec_gw,
                                      'gateway': self.out_gw,
                                      'end': self.out_end})
                self.fabric_base.fabric_fsm[
                    fw_const.OS_IN_NETWORK_STATE][0] = mock.MagicMock()
                self.fabric_base.fabric_fsm[fw_const.OS_IN_NETWORK_STATE][0].\
                    return_value = False
                FakeClass.set_return(fsb.FabricApi, 'get_out_seg_vlan',
                                     [self.out_segmentation_id, VLAN_ID])
                self.fabric_base.service_out_ip.get_subnet_by_netid.\
                    return_value = self.out_subnet
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(dbm.DfaDBMixin, 'get_all_fw_db', fw_db_data)
            FakeClass.set_return(dbm.DfaDBMixin, 'get_fw', [fake_fw_obj, None])
            self.fabric_base.populate_local_cache()
            parent = mock.MagicMock()
            parent.attach_mock(delete_nwk, 'delete_network_all_subnets')
            parent.attach_mock(del_nwk_db, 'delete_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(rel_seg, 'release_segmentation_id')
            parent.attach_mock(rel_sub, 'release_subnet')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.delete_fabric_fw(self.tenant_id,
                                              self.mock_fw_dict, True,
                                              fw_const.RESULT_FW_DELETE_INIT)
        expected_calls = [mock.call.delete_network_all_subnets(net_id),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'), fw_net_dict2),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT, state)]
        parent.assert_has_calls(expected_calls, any_order=False)
        rel_seg.assert_not_called()
        rel_sub.assert_not_called()
        del_nwk_db.assert_not_called()

    def test_delete_in_nwk_fail(self):
        """Delete IN Network Failure Test. """
        self._test_delete_nwk_fail("in")

    def test_delete_out_nwk(self):
        """Delete OUT Network Test. """
        self._test_delete_nwk(fw_const.OS_OUT_NETWORK_STATE, "out")

    def test_delete_out_nwk_fail(self):
        """Delete OUT Network Failure Test. """
        self._test_delete_nwk_fail("out")

    def test_delete_os_dummy_rtr(self):
        """Delete Dummy Router Test. """
        fw_net_dict2 = self._fill_fw_del_net_dict()
        fw_net_dict2['os_status'] = fw_const.OS_DUMMY_RTR_DEL_SUCCESS
        subnet_lst = set()
        subnet_lst.add(self.rtr_subnet_id)
        net_id = self.rtr_net_id

        fw_db_data = self._fill_fw_db_data(fw_const.OS_DUMMY_RTR_STATE)
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.OS_DUMMY_RTR_STATE),\
            mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                       'native.fabric_setup_base.ServiceIpSegTenantMap.'
                       'fixup_state',
                       return_value=fw_const.OS_DUMMY_RTR_STATE),\
            mock.patch.object(self.fabric_base.os_helper,
                              'delete_intf_router',
                              return_value=True) as delete_intf_rtr,\
            mock.patch.object(self.fabric_base.os_helper,
                              'delete_network_all_subnets',
                              return_value=True) as delete_all_subnets,\
            mock.patch.object(self.fabric_base,
                              'delete_network_db') as del_nwk_db:
            self.fabric_base.fabric_fsm[fw_const.OS_OUT_NETWORK_STATE][1] = \
                mock.MagicMock()
            self.fabric_base.fabric_fsm[fw_const.OS_OUT_NETWORK_STATE][1].\
                return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(dbm.DfaDBMixin, 'get_all_fw_db', fw_db_data)
            self.fabric_base.service_in_ip.get_subnet_by_netid.\
                return_value = self.in_subnet
            self.fabric_base.populate_local_cache()

            parent = mock.MagicMock()
            parent.attach_mock(delete_intf_rtr, 'delete_intf_router')
            parent.attach_mock(delete_all_subnets,
                               'delete_network_all_subnets')
            parent.attach_mock(del_nwk_db, 'delete_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.delete_fabric_fw(self.tenant_id,
                                              self.mock_fw_dict, False,
                                              fw_const.RESULT_FW_DELETE_INIT)
        expected_calls = [mock.call.delete_intf_router(None, None,
                                                       self.router_id,
                                                       subnet_lst),
                          mock.call.delete_network_all_subnets(net_id),
                          mock.call.delete_network_db(net_id),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'), fw_net_dict2),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT,
                              fw_const.OS_OUT_NETWORK_STATE),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT,
                              fw_const.OS_OUT_NETWORK_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_delete_os_dummy_rtr_fail(self):
        """Delete Dummy Router Fail Test.

        The Openstack delete interface to router helper function is mocked to
        return a failure.
        """
        fw_net_dict2 = self._fill_fw_del_net_dict()
        fw_net_dict2['os_status'] = fw_const.OS_DUMMY_RTR_DEL_FAIL
        subnet_lst = set()
        subnet_lst.add(self.rtr_subnet_id)
        net_id = self.rtr_net_id

        fw_db_data = self._fill_fw_db_data(fw_const.OS_DUMMY_RTR_STATE)
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.OS_DUMMY_RTR_STATE),\
            mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                       'native.fabric_setup_base.ServiceIpSegTenantMap.'
                       'fixup_state',
                       return_value=fw_const.OS_DUMMY_RTR_STATE),\
            mock.patch.object(self.fabric_base.os_helper,
                              'delete_intf_router',
                              return_value=False) as delete_intf_rtr,\
            mock.patch.object(self.fabric_base.os_helper,
                              'delete_network_all_subnets',
                              return_value=True) as delete_all_subnets,\
            mock.patch.object(self.fabric_base,
                              'delete_network_db') as del_nwk_db:
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(dbm.DfaDBMixin, 'get_all_fw_db', fw_db_data)
            self.fabric_base.service_in_ip.get_subnet_by_netid.\
                return_value = self.in_subnet
            self.fabric_base.populate_local_cache()

            parent = mock.MagicMock()
            parent.attach_mock(delete_intf_rtr, 'delete_intf_router')
            parent.attach_mock(delete_all_subnets,
                               'delete_network_all_subnets')
            parent.attach_mock(del_nwk_db, 'delete_network_db')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.delete_fabric_fw(self.tenant_id,
                                              self.mock_fw_dict, False,
                                              fw_const.RESULT_FW_DELETE_INIT)
        expected_calls = [mock.call.delete_intf_router(None, None,
                                                       self.router_id,
                                                       subnet_lst),
                          mock.call.delete_network_db(net_id),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'), fw_net_dict2),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT,
                              fw_const.OS_DUMMY_RTR_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)
        delete_all_subnets.assert_not_called()

    def _test_delete_dcnm_nwk(self, direc):
        fw_net_dict2 = self._fill_fw_del_net_dict()
        if direc == "in":
            fw_net_dict2['dcnm_status'] = fw_const.DCNM_IN_NETWORK_DEL_SUCCESS
            state = fw_const.DCNM_IN_NETWORK_STATE
            prev_state = fw_const.OS_DUMMY_RTR_STATE
            part = None
        else:
            fw_net_dict2['dcnm_status'] = fw_const.DCNM_OUT_NETWORK_DEL_SUCCESS
            state = fw_const.DCNM_OUT_NETWORK_STATE
            prev_state = fw_const.DCNM_OUT_PART_STATE
            part = fw_const.SERV_PART_NAME
        fw_net_dict2['os_status'] = fw_const.OS_DUMMY_RTR_CREATE_SUCCESS

        fw_db_data = self._fill_fw_db_data(state)
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state', return_value=state),\
            mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                       'native.fabric_setup_base.ServiceIpSegTenantMap.'
                       'fixup_state', return_value=state),\
            mock.patch('networking_cisco.apps.saf.common.utils.'
                       'Dict2Obj') as dict_obj,\
            mock.patch.object(self.fabric_base.dcnm_obj,
                              'delete_service_network') as delete_nwk:
            self.fabric_base.fabric_fsm[prev_state][1] = mock.MagicMock()
            self.fabric_base.fabric_fsm[prev_state][1].return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(dbm.DfaDBMixin, 'get_all_fw_db', fw_db_data)
            if direc == "in":
                FakeClass.set_return(fsb.FabricApi, 'get_in_seg_vlan',
                                     [self.segmentation_id, VLAN_ID])
                fake_db_net = {'part_name': None,
                               'segmentation_id': self.segmentation_id,
                               'vlan': VLAN_ID}
                self.fabric_base.service_in_ip.get_subnet_by_netid.\
                    return_value = self.in_subnet
            else:
                FakeClass.set_return(fsb.FabricApi, 'get_out_seg_vlan',
                                     [self.out_segmentation_id, VLAN_ID])
                fake_db_net = {'part_name': part,
                               'segmentation_id': self.out_segmentation_id,
                               'vlan': VLAN_ID}
                self.fabric_base.service_out_ip.get_subnet_by_netid.\
                    return_value = self.out_subnet
            self.fabric_base.populate_local_cache()

            parent = mock.MagicMock()
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            parent.attach_mock(dict_obj, 'Dict2Obj')
            self.fabric_base.delete_fabric_fw(self.tenant_id,
                                              self.mock_fw_dict, False,
                                              fw_const.RESULT_FW_DELETE_INIT)
        expected_calls = [mock.call.Dict2Obj(fake_db_net),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'), fw_net_dict2),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT, prev_state),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT, prev_state)]
        parent.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(delete_nwk.called, True)

    def test_delete_dcnm_in_nwk(self):
        """Delete DCNM In Network Test. """
        self._test_delete_dcnm_nwk("in")

    def test_clear_dcnm_in_part(self):
        """Clear DCNM IN partition service node address Test. """
        fw_net_dict2 = self._fill_fw_del_net_dict()
        fw_net_dict2['dcnm_status'] = fw_const.DCNM_IN_PART_UPDDEL_SUCCESS
        fw_net_dict2['os_status'] = fw_const.OS_DUMMY_RTR_CREATE_SUCCESS

        fw_db_data = self._fill_fw_db_data(fw_const.DCNM_IN_PART_UPDATE_STATE)
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.DCNM_IN_PART_UPDATE_STATE),\
            mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                       'native.fabric_setup_base.ServiceIpSegTenantMap.'
                       'fixup_state',
                       return_value=fw_const.DCNM_IN_PART_UPDATE_STATE),\
            mock.patch.object(self.fabric_base.dcnm_obj,
                              'update_project') as update_project:
            self.fabric_base.fabric_fsm[
                fw_const.DCNM_IN_NETWORK_STATE][1] = mock.MagicMock()
            self.fabric_base.fabric_fsm[
                fw_const.DCNM_IN_NETWORK_STATE][1].return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(dbm.DfaDBMixin, 'get_all_fw_db', fw_db_data)
            FakeClass.set_return(fsb.FabricApi, 'get_in_ip_addr',
                                 {'subnet': self.in_subnet,
                                  'start': self.in_start,
                                  'sec_gateway': self.in_sec_gw,
                                  'gateway': self.in_gw,
                                  'end': self.in_end})
            self.fabric_base.service_in_ip.get_subnet_by_netid.\
                return_value = self.in_subnet
            self.fabric_base.populate_local_cache()

            parent = mock.MagicMock()
            parent.attach_mock(update_project, 'update_project')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.delete_fabric_fw(self.tenant_id,
                                              self.mock_fw_dict, False,
                                              fw_const.RESULT_FW_DELETE_INIT)
        expected_calls = [mock.call.update_project(self.tenant_name, None,
                                                   service_node_ip=None,
                                                   vrf_prof=None,
                                                   desc="Service Partition"),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'), fw_net_dict2),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT,
                              fw_const.DCNM_IN_NETWORK_STATE),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT,
                              fw_const.DCNM_IN_NETWORK_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_delete_dcnm_out_part(self):
        """Delete DCNM OUT partition address Test. """
        fw_net_dict2 = self._fill_fw_del_net_dict()
        fw_net_dict2['dcnm_status'] = fw_const.DCNM_OUT_PART_DEL_SUCCESS
        fw_net_dict2['os_status'] = fw_const.OS_DUMMY_RTR_CREATE_SUCCESS

        fw_db_data = self._fill_fw_db_data(fw_const.DCNM_OUT_PART_STATE)
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.DCNM_OUT_PART_STATE),\
            mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                       'native.fabric_setup_base.ServiceIpSegTenantMap.'
                       'fixup_state',
                       return_value=fw_const.DCNM_OUT_PART_STATE),\
            mock.patch.object(self.fabric_base.dcnm_obj,
                              'delete_partition') as delete_partition:
            self.fabric_base.fabric_fsm[
                fw_const.DCNM_IN_PART_UPDATE_STATE][1] = mock.MagicMock()
            self.fabric_base.fabric_fsm[
                fw_const.DCNM_IN_PART_UPDATE_STATE][1].return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(dbm.DfaDBMixin, 'get_all_fw_db', fw_db_data)
            self.fabric_base.service_in_ip.get_subnet_by_netid.\
                return_value = self.in_subnet
            self.fabric_base.populate_local_cache()

            parent = mock.MagicMock()
            parent.attach_mock(delete_partition, 'delete_partition')
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.delete_fabric_fw(self.tenant_id,
                                              self.mock_fw_dict, False,
                                              fw_const.RESULT_FW_DELETE_INIT)
        expected_calls = [mock.call.delete_partition(self.tenant_name,
                                                     fw_const.SERV_PART_NAME),
                          mock.call.update_fw_db_result(
                              self.mock_fw_dict.get('fw_id'), fw_net_dict2),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT,
                              fw_const.DCNM_IN_PART_UPDATE_STATE),
                          mock.call.append_state_final_result(
                              self.mock_fw_dict.get('fw_id'),
                              fw_const.RESULT_FW_DELETE_INIT,
                              fw_const.DCNM_IN_PART_UPDATE_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)

    def test_delete_dcnm_out_nwk(self):
        """Delete DCNM Out Network Test. """
        self._test_delete_dcnm_nwk("out")

    def test_clear_dcnm_out_part(self):
        """Clear DCNM OUT partition service node address Test. """
        fw_net_dict2 = self._fill_fw_del_net_dict()
        fw_net_dict2['dcnm_status'] = fw_const.DCNM_OUT_PART_UPDDEL_SUCCESS
        fw_net_dict2['os_status'] = fw_const.OS_DUMMY_RTR_CREATE_SUCCESS

        fw_db_data = self._fill_fw_db_data(fw_const.DCNM_OUT_PART_UPDATE_STATE)
        with mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                        'native.fabric_setup_base.ServiceIpSegTenantMap.'
                        'get_state',
                        return_value=fw_const.DCNM_OUT_PART_UPDATE_STATE),\
            mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                       'native.fabric_setup_base.ServiceIpSegTenantMap.'
                       'fixup_state',
                       return_value=fw_const.DCNM_OUT_PART_UPDATE_STATE):
            self.fabric_base.fabric_fsm[
                fw_const.DCNM_OUT_NETWORK_STATE][1] = mock.MagicMock()
            self.fabric_base.fabric_fsm[
                fw_const.DCNM_OUT_NETWORK_STATE][1].return_value = False
            # update_fw_db is removed from here. Because both this and
            # update_fw_db_result uses the same fw_dict and fw_dict
            # is updated with result before calling update_fw_db_result. But,
            # mock records the updated fw_dict as a result of which argument
            # check fails.
            FakeClass.set_return(dbm.DfaDBMixin, 'get_all_fw_db', fw_db_data)
            self.fabric_base.service_in_ip.get_subnet_by_netid.\
                return_value = self.in_subnet
            self.fabric_base.populate_local_cache()

            parent = mock.MagicMock()
            parent.attach_mock(self.upd_fw_db_res_mock, 'update_fw_db_result')
            parent.attach_mock(self.app_state_final_res_mock,
                               'append_state_final_result')
            self.fabric_base.delete_fabric_fw(self.tenant_id,
                                              self.mock_fw_dict, False,
                                              fw_const.RESULT_FW_DELETE_INIT)
        expected_calls = [
            mock.call.update_fw_db_result(self.mock_fw_dict.get('fw_id'),
                                          fw_net_dict2),
            mock.call.append_state_final_result(
                self.mock_fw_dict.get('fw_id'), fw_const.RESULT_FW_DELETE_INIT,
                fw_const.DCNM_OUT_NETWORK_STATE),
            mock.call.append_state_final_result(
                self.mock_fw_dict.get('fw_id'), fw_const.RESULT_FW_DELETE_INIT,
                fw_const.DCNM_OUT_NETWORK_STATE)]
        parent.assert_has_calls(expected_calls, any_order=False)
