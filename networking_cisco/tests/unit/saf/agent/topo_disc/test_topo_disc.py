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

from networking_cisco.apps.saf.agent.topo_disc import (
    topo_disc_constants as topo_constants)
from networking_cisco.apps.saf.agent.topo_disc import topo_disc

try:
    OrderedDict = collections.OrderedDict
except AttributeError:
    import ordereddict
    OrderedDict = ordereddict.OrderedDict


class TopoDiscTest(base.BaseTestCase):
    """A test suite to exercise the TopoDisc Class. """

    def setUp(self):
        """Setup Routine. """
        super(TopoDiscTest, self).setUp()
        self.root_helper = 'sudo'
        self.intf_list = ['eth1', 'eth2']
        self.updated_intf_list = ['eth1', 'eth2', 'LLDPLeth2']
        self.protocol_interface = 'LLDPLeth2'
        self.phy_interface = 'eth2'
        period_fn = mock.patch(
            'networking_cisco.apps.saf.common.utils.PeriodicTask').start()
        self.get_run_phy_intf = mock.patch(
            'networking_cisco.apps.saf.common.dfa_sys_lib.'
            'get_all_run_phy_intf', return_value=self.intf_list).start()
        self.enable_lldp = mock.patch(
            'networking_cisco.apps.saf.agent.topo_disc.'
            'pub_lldp_api.LldpApi.enable_lldp').start()
        period_obj = period_fn.return_value
        parent = mock.MagicMock()
        parent.attach_mock(period_obj.run, 'run')
        expected_calls = [mock.call.run()]
        self.topo_disc = topo_disc.TopoDisc(None, self.root_helper)
        period_fn.assert_any_call(topo_constants.PERIODIC_TASK_INTERVAL,
                                  self.topo_disc.periodic_discovery_task)
        parent.assert_has_calls(expected_calls)

    def test_init_cfg_interfaces(self):
        """Test the _init_cfg_interfaces function. """
        with mock.patch('networking_cisco.apps.saf.agent.topo_disc.'
                        'topo_disc.TopoDisc.'
                        'cfg_lldp_interface_list') as topo_intf_fn:
            self.topo_disc._init_cfg_interfaces("")
        topo_intf_fn.assert_any_call(self.intf_list)
        self.assertEqual(self.topo_disc.intf_list, self.intf_list)

    def test_cfg_intf(self):
        """Test the cfg_intf function. """
        with mock.patch.object(self.topo_disc,
                               'cfg_lldp_interface') as cfg_lldp_intf_fn:
            self.topo_disc.cfg_intf(self.protocol_interface,
                                    self.phy_interface)
        cfg_lldp_intf_fn.assert_any_call(self.protocol_interface,
                                         self.phy_interface)
        self.assertEqual(self.updated_intf_list, self.topo_disc.intf_list)

    def test_cfg_lldp_interface_list(self):
        """Test the cfg_lldp_interface_list function. """
        with mock.patch.object(self.topo_disc,
                               'cfg_lldp_interface') as cfg_lldp_intf_fn:
            self.topo_disc.cfg_lldp_interface_list(self.intf_list)
        for intf in self.intf_list:
            cfg_lldp_intf_fn.assert_any_call(intf)

    def test_cfg_lldp_interface(self):
        """Test the test_cfg_lldp_interface function. """
        self.enable_lldp.return_value = True
        self.topo_disc.cfg_lldp_interface(self.protocol_interface,
                                          self.phy_interface)
        self.enable_lldp.assert_called_with(self.protocol_interface)
        self.assertTrue(
            self.topo_disc.get_attr_obj(
                self.protocol_interface).get_lldp_status())

    def test_cfg_lldp_interface_error(self):
        """Test the test_cfg_lldp_interface function when it returns False. """
        self.enable_lldp.return_value = False
        self.topo_disc.cfg_lldp_interface(self.protocol_interface,
                                          self.phy_interface)
        self.enable_lldp.assert_called_with(self.protocol_interface)
        self.assertFalse(
            self.topo_disc.get_attr_obj(
                self.protocol_interface).get_lldp_status())

    def _set_tlv_params_attr_obj(self, attr_obj, val):
        attr_obj.return_value.remote_evb_mode_uneq_store.return_value = val
        attr_obj.return_value.remote_evb_cfgd_uneq_store.return_value = val
        attr_obj.return_value.remote_mgmt_addr_uneq_store.return_value = val
        attr_obj.return_value.remote_sys_desc_uneq_store.return_value = val
        attr_obj.return_value.remote_sys_name_uneq_store.return_value = val
        attr_obj.return_value.remote_port_uneq_store.return_value = val
        attr_obj.return_value.remote_chassis_id_mac_uneq_store.return_value = (
            val)
        attr_obj.return_value.remote_port_id_mac_uneq_store.return_value = val

    def test_cmp_store_tlv_params_all_false(self):
        """Test the test_cmp_store_tlv_params for all false case.

        This test the case when all TLV compare functions returns False.
        """
        with mock.patch.object(self.topo_disc, 'get_attr_obj') as attr_obj,\
            mock.patch('networking_cisco.apps.saf.agent.topo_disc.'
                       'pub_lldp_api.LldpApi.get_remote_evb_mode'):
            self._set_tlv_params_attr_obj(attr_obj, False)
            ret = self.topo_disc.cmp_store_tlv_params(self.protocol_interface,
                                                      'Some TLV Data')
        self.assertFalse(ret)

    def test_cmp_store_tlv_params_all_true(self):
        """Test the test_cmp_store_tlv_params for all True case.

        This test the case when all TLV compare functions returns True.
        """
        with mock.patch.object(self.topo_disc, 'get_attr_obj') as attr_obj,\
            mock.patch('networking_cisco.apps.saf.agent.topo_disc.'
                       'pub_lldp_api.LldpApi.get_remote_evb_mode'):
            self._set_tlv_params_attr_obj(attr_obj, True)
            ret = self.topo_disc.cmp_store_tlv_params(self.protocol_interface,
                                                      'Some TLV Data')
        self.assertTrue(ret)

    def test_cmp_store_tlv_params_one_true(self):
        """Test the test_cmp_store_tlv_params for one True case.

        This test the case when all TLV compare functions returns True.
        """
        with mock.patch.object(self.topo_disc, 'get_attr_obj') as attr_obj,\
            mock.patch('networking_cisco.apps.saf.agent.topo_disc.'
                       'pub_lldp_api.LldpApi.get_remote_evb_mode'):
            self._set_tlv_params_attr_obj(attr_obj, False)
            attr_obj.return_value.remote_port_uneq_store.return_value = True
            ret = self.topo_disc.cmp_store_tlv_params(self.protocol_interface,
                                                      'Some TLV Data')
        self.assertTrue(ret)

    def _test_uneq_store_fn(self, fn_ext, new_value, stored_value,
                            member_name, fn_ret):
        """Generic function to test all variants of uneq_store functions. """
        attr_obj = self.topo_disc.get_attr_obj(self.phy_interface)
        fn_name = getattr(attr_obj, fn_ext)
        setattr(attr_obj, member_name, stored_value)
        ret = fn_name(new_value)
        self.assertEqual(fn_ret, ret)
        self.assertEqual(new_value, getattr(attr_obj, member_name))

    def test_remote_evb_mode_uneq_store_equal(self):
        """Test remote_evb_mode_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        evb_mode = 'bridge'
        self._test_uneq_store_fn(
            'remote_evb_mode_uneq_store', evb_mode, evb_mode,
            'remote_evb_mode', False)

    def test_remote_evb_mode_uneq_store_unequal(self):
        """Test remote_evb_mode_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        evb_mode = 'bridge'
        old_evb_mode = ''
        self._test_uneq_store_fn(
            'remote_evb_mode_uneq_store', evb_mode, old_evb_mode,
            'remote_evb_mode', True)

    def test_remote_evb_cfgd_uneq_store_equal(self):
        """Test remote_evb_cfgd_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        evb_cfgd = True
        self._test_uneq_store_fn(
            'remote_evb_cfgd_uneq_store', evb_cfgd, evb_cfgd,
            'remote_evb_cfgd', False)

    def test_remote_evb_cfgd_uneq_store_unequal(self):
        """Test remote_evb_cfgd_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        evb_cfgd = True
        old_evb_cfgd = False
        self._test_uneq_store_fn(
            'remote_evb_cfgd_uneq_store', evb_cfgd, old_evb_cfgd,
            'remote_evb_cfgd', True)

    def test_remote_mgmt_addr_uneq_store_equal(self):
        """Test remote_mgmt_addr_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        mgmt_addr = '10.2.2.4'
        self._test_uneq_store_fn(
            'remote_mgmt_addr_uneq_store', mgmt_addr, mgmt_addr,
            'remote_mgmt_addr', False)

    def test_remote_mgmt_addr_uneq_store_unequal(self):
        """Test remote_mgmt_addr_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        mgmt_addr = '10.2.2.4'
        old_mgmt_addr = '1.2.5.4'
        self._test_uneq_store_fn(
            'remote_mgmt_addr_uneq_store', mgmt_addr, old_mgmt_addr,
            'remote_mgmt_addr', True)

    def test_remote_system_desc_uneq_store_equal(self):
        """Test remote_system_desc_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        system_desc = "Cisco NXOS"
        self._test_uneq_store_fn(
            'remote_sys_desc_uneq_store', system_desc, system_desc,
            'remote_system_desc', False)

    def test_remote_system_desc_uneq_store_unequal(self):
        """Test remote_system_desc_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        system_desc = "Cisco NXOS"
        old_system_desc = "Cisco Non-NXOS"
        self._test_uneq_store_fn(
            'remote_sys_desc_uneq_store', system_desc, old_system_desc,
            'remote_system_desc', True)

    def test_remote_system_name_uneq_store_equal(self):
        """Test remote_system_name_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        system_name = 'N6K-50'
        self._test_uneq_store_fn(
            'remote_sys_name_uneq_store', system_name, system_name,
            'remote_system_name', False)

    def test_remote_system_name_uneq_store_unequal(self):
        """Test remote_system_name_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        system_name = 'N6K-50'
        old_system_name = 'N6K-51'
        self._test_uneq_store_fn(
            'remote_sys_name_uneq_store', system_name, old_system_name,
            'remote_system_name', True)

    def test_remote_port_uneq_store_equal(self):
        """Test remote_port_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        port = 'G1/1'
        self._test_uneq_store_fn(
            'remote_port_uneq_store', port, port, 'remote_port', False)

    def test_remote_port_uneq_store_unequal(self):
        """Test remote_port_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        port = 'G1/1'
        old_port = 'G1/2'
        self._test_uneq_store_fn(
            'remote_port_uneq_store', port, old_port, 'remote_port', True)

    def test_remote_chassis_id_mac_uneq_store_equal(self):
        """Test remote_chassis_id_mac_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        chassis_id_mac = '00:11:22:33:44:55'
        self._test_uneq_store_fn(
            'remote_chassis_id_mac_uneq_store', chassis_id_mac, chassis_id_mac,
            'remote_chassis_id_mac', False)

    def test_remote_chassis_id_mac_uneq_store_unequal(self):
        """Test remote_chassis_id_mac_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        chassis_id_mac = '00:11:22:33:44:55'
        old_chassis_id_mac = '00:22:33:44:55:66'
        self._test_uneq_store_fn(
            'remote_chassis_id_mac_uneq_store', chassis_id_mac,
            old_chassis_id_mac, 'remote_chassis_id_mac', True)

    def test_remote_port_id_mac_uneq_store_equal(self):
        """Test remote_port_id_mac_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        port_id_mac = '00:aa:bb:cc:dd:ee'
        self._test_uneq_store_fn(
            'remote_port_id_mac_uneq_store', port_id_mac, port_id_mac,
            'remote_port_id_mac', False)

    def test_remote_port_id_mac_uneq_store_unequal(self):
        """Test remote_port_id_mac_uneq_store for same value case.

        This tests the case when the value stored is the same as the value
        passed.
        """
        port_id_mac = '00:aa:bb:cc:dd:ee'
        old_port_id_mac = '00:bb:cc:dd:ee:ff'
        self._test_uneq_store_fn(
            'remote_port_id_mac_uneq_store', port_id_mac, old_port_id_mac,
            'remote_port_id_mac', True)

    def _test_period_task_reset_general(self, cb_ret,
                                        bond_interface_change_ret=False,
                                        cmp_store_tlv_ret=False,
                                        get_db_retry_status=False,
                                        topo_disc_send_cnt=1,
                                        update_lldp_status=True):
        """Internal helper function for all period_tast_reset functions. """
        with mock.patch('networking_cisco.apps.saf.agent.topo_disc.'
                        'pub_lldp_api.LldpApi.get_lldp_tlv'),\
            mock.patch.object(
                self.topo_disc, '_check_bond_interface_change',
                return_value=bond_interface_change_ret),\
            mock.patch.object(self.topo_disc, 'cmp_store_tlv_params',
                              return_value=cmp_store_tlv_ret):
            self.topo_disc.cb = mock.MagicMock()
            self.topo_disc.cb.return_value = cb_ret
            self.topo_disc.intf_list = [self.phy_interface]
            attr_obj = self.topo_disc.get_attr_obj(self.phy_interface)
            attr_obj.update_lldp_status(update_lldp_status)
            attr_obj.store_db_retry_status(get_db_retry_status)
            attr_obj.topo_send_cnt = topo_disc_send_cnt
            self.topo_disc.periodic_discovery_task()
        self.assertEqual(0, attr_obj.topo_send_cnt)
        self.assertEqual(not cb_ret, attr_obj.get_db_retry_status())
        self.topo_disc.cb.assert_called_with(
            self.phy_interface,
            self.topo_disc.get_attr_obj(self.phy_interface))

    def test_period_task_reset_case_cmp_true(self):
        """Test the periodic task when cmp_store_tlv_params returns True.

        Also, the callback invoked case is verified for a return value of True.
        """
        cb_ret = True
        self._test_period_task_reset_general(cb_ret, cmp_store_tlv_ret=True)

    def test_period_task_reset_case_get_db_retry_true(self):
        """Test the periodic task when get_db_retry_status returns True.

        Also, the callback invoked case is verified for a return value of
        False.
        """
        cb_ret = False
        self._test_period_task_reset_general(cb_ret, get_db_retry_status=True)

    def test_period_task_reset_case_bond_intf_change_true(self):
        """Test the periodic task when bond_intf_change returns True.

        Also, the callback invoked case is verified for a return value of
        False.
        """
        cb_ret = False
        self._test_period_task_reset_general(
            cb_ret, bond_interface_change_ret=True)

    def test_period_task_reset_case_topo_disc_cnt_exceed_threshold(self):
        """Test the periodic task when send failure cnt exceeds threshold.

        Also, the callback invoked case is verified for a return value of
        True.
        """
        cb_ret = True
        self._test_period_task_reset_general(
            cb_ret,
            topo_disc_send_cnt=topo_constants.TOPO_DISC_SEND_THRESHOLD + 1)

    def test_period_task_reset_case_all_false(self):
        """Test the periodic task when callback is not invoked.

        When all conditions for calling callback returns False.
        """
        topo_send_cnt = 1
        with mock.patch('networking_cisco.apps.saf.agent.topo_disc.'
                        'pub_lldp_api.LldpApi.get_lldp_tlv'),\
            mock.patch.object(
                self.topo_disc, '_check_bond_interface_change',
                return_value=False),\
            mock.patch.object(self.topo_disc, 'cmp_store_tlv_params',
                              return_value=False):
            self.topo_disc.cb = mock.MagicMock()
            self.topo_disc.cb.return_value = False
            self.topo_disc.intf_list = [self.phy_interface]
            attr_obj = self.topo_disc.get_attr_obj(self.phy_interface)
            attr_obj.update_lldp_status(True)
            attr_obj.store_db_retry_status(False)
            attr_obj.topo_send_cnt = topo_send_cnt
            self.topo_disc.periodic_discovery_task()
        self.assertEqual(topo_send_cnt + 1, attr_obj.topo_send_cnt)
        self.topo_disc.cb.assert_not_called()

    def test_period_task_reset_case_lldp_status_false(self):
        """Test the periodic task when LLDP status is False. """
        topo_send_cnt = 1
        with mock.patch('networking_cisco.apps.saf.agent.topo_disc.'
                        'pub_lldp_api.LldpApi.get_lldp_tlv'),\
            mock.patch.object(
                self.topo_disc, '_check_bond_interface_change',
                return_value=False),\
            mock.patch.object(self.topo_disc, 'cmp_store_tlv_params',
                              return_value=False):
            self.topo_disc.cb = mock.MagicMock()
            self.topo_disc.cb.return_value = False
            self.topo_disc.intf_list = [self.phy_interface]
            attr_obj = self.topo_disc.get_attr_obj(self.phy_interface)
            attr_obj.update_lldp_status(False)
            attr_obj.store_db_retry_status(False)
            attr_obj.topo_send_cnt = topo_send_cnt
            self.enable_lldp.return_value = True
            self.topo_disc.periodic_discovery_task()
        self.assertEqual(topo_send_cnt, attr_obj.topo_send_cnt)
        self.topo_disc.cb.assert_not_called()
        self.enable_lldp.assert_called_with(self.phy_interface)
        self.assertTrue(
            self.topo_disc.get_attr_obj(self.phy_interface).get_lldp_status())
