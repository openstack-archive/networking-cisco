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

import mock

from neutron.tests import base

from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.db import dfa_db_models as dbm
from networking_cisco.apps.saf.server.services.firewall.native.drivers import (
    dev_mgr)
from networking_cisco.apps.saf.server.services.firewall.native import fw_mgr


TENANT_NAME = 'TenantA'
TENANT_ID = '0000-1111-2222-5555'
FW_ID = '0000-aaaa-bbbb-ccce'
FW_NAME = 'FwA'
POLCY_ID = '0000-aaaa-bbbb-cccc'
FW_TYPE = 'TE'
ROUTER_ID = '0000-aaaa-bbbb-5555'
RULE_ID = '0000-aaaa-bbbb-cccd'
PROTOCOL = 'tcp'
SRC_IP = '1.1.1.1'
DST_IP = '2.2.2.2'
SRC_PORT = 34
DST_PORT = 43
RULE_NAME = 'RuleA'


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


class FwMgrTest(base.BaseTestCase):
    """A test suite to exercise the FW Mgr. """

    def setUp(self):
        """Setup for the test scripts. """
        super(FwMgrTest, self).setUp()
        self._init_values()
        config = self._fill_cfg()
        self.cfg = config.CiscoDFAConfig().cfg

        fw_mgr.FwMgr.__bases__ = (FakeClass.imitate(dev_mgr.DeviceMgr,
                                                    dbm.DfaDBMixin),)
        FakeClass.set_return(dbm.DfaDBMixin, 'get_all_fw_db', dict())
        mock.patch('networking_cisco.apps.saf.server.services.firewall.'
                   'native.fabric_setup_base.FabricBase').start()
        mock.patch('networking_cisco.apps.saf.server.dfa_openstack_helper.'
                   'DfaNeutronHelper').start()
        fw_mgr.FwMgr.events = mock.Mock()
        self.fw_mgr = fw_mgr.FwMgr(self.cfg)
        self.update_fw_db_mock = mock.patch.object(
            self.fw_mgr, 'update_fw_db_final_result').start()
        self.create_fw_dev_mock = mock.patch.object(
            self.fw_mgr, 'create_fw_device').start()
        self.update_fw_dev_mock = mock.patch.object(
            self.fw_mgr, 'update_fw_db_dev_status').start()

    def _init_values(self):
        self.tenant_name = TENANT_NAME
        self.tenant_id = TENANT_ID
        self.fw_id = FW_ID
        self.fw_name = FW_NAME
        self.policy_id = POLCY_ID
        self.fw_type = FW_TYPE
        self.router_id = ROUTER_ID
        self.rule_id = RULE_ID
        self.rule_dict = {'protocol': PROTOCOL, 'name': RULE_NAME,
                          'enabled': True, 'source_ip_address': SRC_IP,
                          'destination_ip_address': DST_IP,
                          'source_port': SRC_PORT,
                          'destination_port': DST_PORT, 'action': 'allow'}

    def _fill_cfg(self):
        config.default_firewall_opts['firewall'] = {
            'device': 'phy_asa', 'fw_mgmt_ip': '1.1.1.1',
            'fw_username': 'user', 'fw_passport': 'user',
            'fw_interface_in': 'e1/1', 'fw_interface_out': 'e1/1'}
        return config

    def test_fw_mgr_init(self):
        """Wrapper for the init. """
        pass

    def _fill_rule_data(self):
        fw_rule_dict = {'firewall_rule': {'tenant_id': self.tenant_id}}
        sub_rule_dict = fw_rule_dict['firewall_rule']
        sub_rule_dict.update({
            'firewall_policy_id': self.policy_id,
            'id': self.rule_id,
            'protocol': self.rule_dict['protocol'],
            'source_ip_address': self.rule_dict['source_ip_address'],
            'destination_ip_address': self.rule_dict['destination_ip_address'],
            'source_port': self.rule_dict['source_port'],
            'destination_port': self.rule_dict['destination_port'],
            'action': self.rule_dict['action'],
            'enabled': True, 'name': RULE_NAME})
        return fw_rule_dict

    def _test_fw_rule_create(self):
        with mock.patch.object(self.fw_mgr.fabric,
                               'prepare_fabric_fw') as prep_fab:
            fw_rule_data = self._fill_rule_data()
            self.fw_mgr.fw_rule_create(fw_rule_data, None)
            parent = mock.MagicMock()
            parent.attach_mock(prep_fab, 'prepare_fabric_fw')
            parent.attach_mock(self.create_fw_dev_mock, 'create_fw_device')
            parent.attach_mock(self.update_fw_db_mock,
                               'update_fw_db_final_result')
            parent.attach_mock(self.update_fw_dev_mock,
                               'update_fw_db_dev_status')
            prep_fab.assert_not_called()
            self.update_fw_db_mock.assert_not_called()
            self.create_fw_dev_mock.assert_not_called()
            self.update_fw_dev_mock.assert_not_called()

    def test_fw_rule_create(self):
        """Test FW rule create. """
        self._test_fw_rule_create()

    def _fill_policy_data(self, rule_dict):
        fw_policy_dict = {'firewall_policy': {
            'tenant_id': self.tenant_id, 'id': self.policy_id,
            'name': 'PolicyA', 'firewall_rules': rule_dict}}
        # Fill the above with Policy rules by calling the fill rule fn
        return fw_policy_dict

    def _test_fw_policy_create(self, with_rule=False):
        with mock.patch.object(self.fw_mgr.fabric,
                               'prepare_fabric_fw') as prep_fab:
            fw_rule_data = dict()
            if with_rule:
                fw_rule_data = []
                fw_rule_data.append(self.rule_id)
                fw_policy_data = self._fill_policy_data(fw_rule_data)
                self.fw_mgr.fw_policy_create(fw_policy_data, None)
                parent = mock.MagicMock()
                parent.attach_mock(prep_fab, 'prepare_fabric_fw')
                parent.attach_mock(self.create_fw_dev_mock, 'create_fw_device')
                parent.attach_mock(self.update_fw_db_mock,
                                   'update_fw_db_final_result')
                parent.attach_mock(self.update_fw_dev_mock,
                                   'update_fw_db_dev_status')
                prep_fab.assert_not_called()
                self.update_fw_db_mock.assert_not_called()
                self.create_fw_dev_mock.assert_not_called()
                self.update_fw_dev_mock.assert_not_called()

    def test_fw_policy_create(self):
        """Test FW policy create. """
        self._test_fw_policy_create()

    def _fill_fw_data(self, rule_dict):
        return {'firewall': {'tenant_id': self.tenant_id,
                             'id': self.fw_id,
                             'firewall_policy_id': self.policy_id,
                             'admin_state_up': True, 'name': self.fw_name,
                             'firewall_rules': rule_dict,
                             'router_ids': [self.router_id]}}

    def _fill_fw_delete_data(self):
        fw_dict = {}
        fw_dict['firewall_id'] = self.fw_id
        return fw_dict

    def _prepare_result_fw_dict(self):
        return {'rules': {self.rule_id: self.rule_dict},
                'tenant_name': self.tenant_name,
                'tenant_id': self.tenant_id, 'fw_id': self.fw_id,
                'fw_name': self.fw_name,
                'firewall_policy_id': self.policy_id,
                'fw_type': self.fw_type, 'router_id': self.router_id}

    def _test_fw_create(self, with_rule=True):
        res_fw_dict = self._prepare_result_fw_dict()
        with mock.patch('networking_cisco.apps.saf.server.'
                        'dfa_openstack_helper.DfaNeutronHelper'),\
            mock.patch.object(self.fw_mgr.fabric,
                              'prepare_fabric_fw') as prep_fab,\
            mock.patch('networking_cisco.apps.saf.db.dfa_db_models.'
                       'DfaDBMixin.get_project_name',
                       return_value=self.tenant_name):
            FakeClass.set_return(dev_mgr.DeviceMgr,
                                 'is_device_virtual', False)
            self.fw_mgr.os_helper.get_rtr_name.return_value = (
                'Cisco_TenantEdge_TenantA')
            fw_rule_data = dict()
            if with_rule:
                fw_rule_data = self._fill_rule_data()
            fw_data = self._fill_fw_data(fw_rule_data)
            self._test_fw_rule_create()
            self._test_fw_policy_create(with_rule=True)
            parent = mock.MagicMock()
            parent.attach_mock(prep_fab, 'prepare_fabric_fw')
            parent.attach_mock(self.create_fw_dev_mock, 'create_fw_device')
            parent.attach_mock(self.update_fw_db_mock,
                               'update_fw_db_final_result')
            parent.attach_mock(self.update_fw_dev_mock,
                               'update_fw_db_dev_status')
            self.fw_mgr.fw_create(fw_data, None)
        expected_calls = [
            mock.call.prepare_fabric_fw(self.tenant_id, res_fw_dict, False,
                                        'FAB_CREATE_PEND'),
            mock.call.update_fw_db_final_result(res_fw_dict.get('fw_id'),
                                                'FAB_CREATE_DONE'),
            mock.call.create_fw_device(self.tenant_id,
                                       res_fw_dict.get('fw_id'), res_fw_dict),
            mock.call.update_fw_db_dev_status(res_fw_dict.get('fw_id'),
                                              'SUCCESS')]
        parent.assert_has_calls(expected_calls, any_order=True)
        # any_order should be False,in which case it didn't work TODO(padkrish)

    def test_fw_create(self):
        """Test FW create. """
        self._test_fw_create()

    def _test_fw_create_fabric_error(self, with_rule=True):
        """Internal function to test the error case for fabric create.

        The fabric module is mocked to return an error for prepare fabric.
        """
        res_fw_dict = self._prepare_result_fw_dict()
        with mock.patch('networking_cisco.apps.saf.server.'
                        'dfa_openstack_helper.DfaNeutronHelper'),\
            mock.patch('networking_cisco.apps.saf.db.dfa_db_models.'
                       'DfaDBMixin.get_project_name',
                       return_value=self.tenant_name),\
            mock.patch.object(self.fw_mgr.fabric, 'prepare_fabric_fw',
                              return_value=False) as prep_fab:
            FakeClass.set_return(dev_mgr.DeviceMgr, 'is_device_virtual', False)
            self.fw_mgr.os_helper.get_rtr_name.return_value = (
                'Cisco_TenantEdge_TenantA')
            fw_rule_data = dict()
            if with_rule:
                fw_rule_data = self._fill_rule_data()
            fw_data = self._fill_fw_data(fw_rule_data)
            self._test_fw_rule_create()
            self._test_fw_policy_create(with_rule=True)
            parent = mock.MagicMock()
            parent.attach_mock(prep_fab, 'prepare_fabric_fw')
            parent.attach_mock(self.create_fw_dev_mock, 'create_fw_device')
            parent.attach_mock(self.update_fw_db_mock,
                               'update_fw_db_final_result')
            parent.attach_mock(self.update_fw_dev_mock,
                               'update_fw_db_dev_status')
            self.fw_mgr.fw_create(fw_data, None)
        expected_calls = [mock.call.prepare_fabric_fw(self.tenant_id,
                                                      res_fw_dict, False,
                                                      'FAB_CREATE_PEND')]
        parent.assert_has_calls(expected_calls, any_order=True)
        self.update_fw_db_mock.assert_not_called()
        self.create_fw_dev_mock.assert_not_called()
        self.update_fw_dev_mock.assert_not_called()

    def test_fw_create_fabric_error(self):
        """Test FW create. """
        self._test_fw_create_fabric_error()

    def _test_fw_create_device_error(self, with_rule=True):
        """Internal function to test the error case for device setup.

        The device driver module is mocked to return an error for device
        configuration.
        """
        res_fw_dict = self._prepare_result_fw_dict()
        with mock.patch('networking_cisco.apps.saf.server.'
                        'dfa_openstack_helper.DfaNeutronHelper'),\
            mock.patch('networking_cisco.apps.saf.db.dfa_db_models.'
                       'DfaDBMixin.get_project_name',
                       return_value=self.tenant_name),\
            mock.patch.object(self.fw_mgr.fabric,
                              'prepare_fabric_fw') as prep_fab,\
            mock.patch.object(self.fw_mgr, 'create_fw_device',
                              return_value=False) as create_fw_dev:
            FakeClass.set_return(dev_mgr.DeviceMgr, 'is_device_virtual', False)
            self.fw_mgr.os_helper.get_rtr_name.return_value = (
                'Cisco_TenantEdge_TenantA')
            fw_rule_data = dict()
            if with_rule:
                fw_rule_data = self._fill_rule_data()
            fw_data = self._fill_fw_data(fw_rule_data)
            self._test_fw_rule_create()
            self._test_fw_policy_create(with_rule=True)
            parent = mock.MagicMock()
            parent.attach_mock(prep_fab, 'prepare_fabric_fw')
            parent.attach_mock(create_fw_dev, 'create_fw_device')
            parent.attach_mock(self.update_fw_db_mock,
                               'update_fw_db_final_result')
            parent.attach_mock(self.update_fw_dev_mock,
                               'update_fw_db_dev_status')
            self.fw_mgr.fw_create(fw_data, None)
        expected_calls = [
            mock.call.prepare_fabric_fw(self.tenant_id, res_fw_dict, False,
                                        'FAB_CREATE_PEND'),
            mock.call.update_fw_db_final_result(res_fw_dict.get('fw_id'),
                                                'FAB_CREATE_DONE'),
            mock.call.create_fw_device(self.tenant_id,
                                       res_fw_dict.get('fw_id'), res_fw_dict)]
        parent.assert_has_calls(expected_calls, any_order=True)
        self.update_fw_dev_mock.assert_not_called()

    def test_fw_create_device_error(self):
        """Test FW create. """
        self._test_fw_create_device_error()

    def _test_fw_delete(self, with_rule=True):
        res_fw_dict = self._prepare_result_fw_dict()
        with mock.patch('networking_cisco.apps.saf.server.'
                        'dfa_openstack_helper.DfaNeutronHelper'),\
            mock.patch.object(self.fw_mgr,
                              'delete_fw_device') as delete_fw_dev,\
            mock.patch.object(self.fw_mgr.fabric,
                              'delete_fabric_fw') as del_fab,\
            mock.patch.object(self.fw_mgr, 'delete_fw') as del_fw,\
            mock.patch('networking_cisco.apps.saf.db.dfa_db_models.'
                       'DfaDBMixin.get_project_name',
                       return_value=self.tenant_name):
            FakeClass.set_return(dev_mgr.DeviceMgr, 'is_device_virtual',
                                 False)
            self.fw_mgr.os_helper.get_rtr_name.return_value = (
                'Cisco_TenantEdge_TenantA')
            fw_rule_data = dict()
            if with_rule:
                fw_rule_data = self._fill_rule_data()
            fw_data = self._fill_fw_data(fw_rule_data)
            self._test_fw_rule_create()
            self._test_fw_policy_create(with_rule=True)
            self._test_fw_create(with_rule=True)
            parent = mock.MagicMock()
            parent.attach_mock(del_fab, 'delete_fabric_fw')
            parent.attach_mock(delete_fw_dev, 'delete_fw_device')
            parent.attach_mock(self.update_fw_db_mock,
                               'update_fw_db_final_result')
            parent.attach_mock(self.update_fw_dev_mock,
                               'update_fw_db_dev_status')
            parent.attach_mock(del_fw, 'delete_fw')
            fw_data = self._fill_fw_delete_data()
            self.fw_mgr.fw_delete(fw_data, None)
        expected_calls = [
            mock.call.update_fw_db_final_result(res_fw_dict.get('fw_id'),
                                                'FAB_DELETE_PEND'),
            mock.call.delete_fw_device(self.tenant_id,
                                       res_fw_dict.get('fw_id'), res_fw_dict),
            mock.call.update_fw_db_dev_status(res_fw_dict.get('fw_id'), ''),
            mock.call.delete_fabric_fw(self.tenant_id, res_fw_dict, False,
                                       'FAB_DELETE_PEND'),
            mock.call.update_fw_db_final_result(res_fw_dict.get('fw_id'),
                                                'FAB_DELETE_DONE'),
            mock.call.delete_fw(res_fw_dict.get('fw_id'))]
        parent.assert_has_calls(expected_calls, any_order=True)

    def test_fw_delete(self):
        """Test FW delete. """
        self._test_fw_delete()

    def _test_fw_delete_dev_error(self, with_rule=True):
        """Internal function to test the error case for device cleanup.

        The device driver module is mocked to return an error for device
        configuration cleanup.
        """
        res_fw_dict = self._prepare_result_fw_dict()
        with mock.patch('networking_cisco.apps.saf.server.'
                        'dfa_openstack_helper.DfaNeutronHelper'),\
            mock.patch.object(self.fw_mgr, 'delete_fw_device',
                              return_value=False) as delete_fw_dev,\
            mock.patch.object(self.fw_mgr.fabric,
                              'delete_fabric_fw') as del_fab,\
            mock.patch.object(self.fw_mgr, 'delete_fw') as del_fw,\
            mock.patch('networking_cisco.apps.saf.db.dfa_db_models.'
                       'DfaDBMixin.get_project_name',
                       return_value=self.tenant_name):
            FakeClass.set_return(dev_mgr.DeviceMgr, 'is_device_virtual', False)
            self.fw_mgr.os_helper.get_rtr_name.return_value = (
                'Cisco_TenantEdge_TenantA')
            fw_rule_data = dict()
            if with_rule:
                fw_rule_data = self._fill_rule_data()
            fw_data = self._fill_fw_data(fw_rule_data)
            self._test_fw_rule_create()
            self._test_fw_policy_create(with_rule=True)
            self._test_fw_create(with_rule=True)
            parent = mock.MagicMock()
            parent.attach_mock(del_fab, 'delete_fabric_fw')
            parent.attach_mock(delete_fw_dev, 'delete_fw_device')
            parent.attach_mock(self.update_fw_db_mock,
                               'update_fw_db_final_result')
            parent.attach_mock(self.update_fw_dev_mock,
                               'update_fw_db_dev_status')
            parent.attach_mock(del_fw, 'delete_fw')
            fw_data = self._fill_fw_delete_data()
            self.fw_mgr.fw_delete(fw_data, None)
        expected_calls = [
            mock.call.update_fw_db_final_result(res_fw_dict.get('fw_id'),
                                                'FAB_DELETE_PEND'),
            mock.call.delete_fw_device(self.tenant_id,
                                       res_fw_dict.get('fw_id'), res_fw_dict)]
        parent.assert_has_calls(expected_calls, any_order=True)
        del_fab.assert_not_called()
        del_fw.assert_not_called()

    def test_fw_delete_dev_error(self):
        """Test FW delete. """
        self._test_fw_delete_dev_error()

    def _test_fw_delete_fab_error(self, with_rule=True):
        """Internal function to test the error case for fabric cleanup.

        The fabric module is mocked to return an error for delete the fabric
        configuration.
        """
        res_fw_dict = self._prepare_result_fw_dict()
        with mock.patch('networking_cisco.apps.saf.server.'
                        'dfa_openstack_helper.DfaNeutronHelper'),\
            mock.patch.object(self.fw_mgr,
                              'delete_fw_device') as delete_fw_dev,\
            mock.patch.object(self.fw_mgr.fabric, 'delete_fabric_fw',
                              return_value=False) as del_fab,\
            mock.patch.object(self.fw_mgr, 'delete_fw') as del_fw,\
            mock.patch('networking_cisco.apps.saf.db.dfa_db_models.'
                       'DfaDBMixin.get_project_name',
                       return_value=self.tenant_name):
            FakeClass.set_return(dev_mgr.DeviceMgr, 'is_device_virtual', False)
            self.fw_mgr.os_helper.get_rtr_name.return_value = (
                'Cisco_TenantEdge_TenantA')
            fw_rule_data = dict()
            if with_rule:
                fw_rule_data = self._fill_rule_data()
            fw_data = self._fill_fw_data(fw_rule_data)
            self._test_fw_rule_create()
            self._test_fw_policy_create(with_rule=True)
            self._test_fw_create(with_rule=True)
            parent = mock.MagicMock()
            parent.attach_mock(del_fab, 'delete_fabric_fw')
            parent.attach_mock(delete_fw_dev, 'delete_fw_device')
            parent.attach_mock(self.update_fw_db_mock,
                               'update_fw_db_final_result')
            parent.attach_mock(self.update_fw_dev_mock,
                               'update_fw_db_dev_status')
            parent.attach_mock(del_fw, 'delete_fw')
            fw_data = self._fill_fw_delete_data()
            self.fw_mgr.fw_delete(fw_data, None)
        expected_calls = [
            mock.call.update_fw_db_final_result(res_fw_dict.get('fw_id'),
                                                'FAB_DELETE_PEND'),
            mock.call.delete_fw_device(self.tenant_id,
                                       res_fw_dict.get('fw_id'), res_fw_dict),
            mock.call.update_fw_db_dev_status(res_fw_dict.get('fw_id'), ''),
            mock.call.delete_fabric_fw(self.tenant_id, res_fw_dict, False,
                                       'FAB_DELETE_PEND')]
        parent.assert_has_calls(expected_calls, any_order=True)
        del_fw.assert_not_called()

    def test_fw_delete_fab_error(self):
        """Test FW delete. """
        self._test_fw_delete_fab_error()
