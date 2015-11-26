# Copyright 2015 Cisco Systems, Inc.  All rights reserved.
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

import os

import mock
from oslo_config import cfg
import six
from webob import exc

from neutron.api.v2 import attributes
from neutron import context as n_context
from neutron import manager
from neutron.plugins.common import constants as svc_constants
from neutron.tests import fake_notifier
from neutron.tests.unit.db import test_agentschedulers_db
from neutron.tests.unit.db import test_db_base_plugin_v2

import networking_cisco
from networking_cisco.plugins.cisco.common import cisco_constants as c_const
from networking_cisco.plugins.cisco.device_manager import service_vm_lib
from networking_cisco.plugins.cisco.extensions import ciscocfgagentscheduler
from networking_cisco.plugins.cisco.extensions import ciscohostingdevicemanager
from networking_cisco.tests.unit.cisco.device_manager import (
    device_manager_test_support as dev_mgr_test_support)
from networking_cisco.tests.unit.cisco.device_manager import (
    test_db_device_manager)


policy_path = (os.path.abspath(networking_cisco.__path__[0]) +
               '/../etc/policy.json')

CORE_PLUGIN_KLASS = dev_mgr_test_support.CORE_PLUGIN_KLASS
HW_CATEGORY = ciscohostingdevicemanager.HARDWARE_CATEGORY
L3_CFG_HOST_A = dev_mgr_test_support.L3_CFG_HOST_A
L3_CFG_HOST_B = dev_mgr_test_support.L3_CFG_HOST_B
L3_CFG_HOST_C = dev_mgr_test_support.L3_CFG_HOST_C


class HostingDeviceCfgAgentSchedulerTestMixIn(
        test_agentschedulers_db.AgentSchedulerTestMixIn):

    def _list_hosting_devices_handled_by_cfg_agent(
            self, cfg_agent_id, expected_code=exc.HTTPOk.code,
            admin_context=True):
        path = "/agents/%s/%s.%s" % (
            cfg_agent_id, ciscocfgagentscheduler.CFG_AGENT_HOSTING_DEVICES,
            self.fmt)
        return self._request_list(path, expected_code=expected_code,
                                  admin_context=admin_context)

    def _list_cfg_agents_handling_hosting_device(
            self, hosting_device_id, expected_code=exc.HTTPOk.code,
            admin_context=True):
        path = "/dev_mgr/hosting_devices/%s/%s.%s" % (
            hosting_device_id,
            ciscocfgagentscheduler.HOSTING_DEVICE_CFG_AGENTS, self.fmt)
        return self._request_list(path, expected_code=expected_code,
                                  admin_context=admin_context)

    def _assign_hosting_device_to_cfg_agent(
            self, cfg_agent_id, hosting_device_id,
            expected_code=exc.HTTPCreated.code, admin_context=True):
        path = "/agents/%s/%s.%s" % (
            cfg_agent_id, ciscocfgagentscheduler.CFG_AGENT_HOSTING_DEVICES,
            self.fmt)
        req = self._path_create_request(
            path, {'hosting_device_id': hosting_device_id},
            admin_context=admin_context)
        res = req.get_response(self.ext_api)
        self.assertEqual(expected_code, res.status_int)

    def _unassign_hosting_device_from_cfg_agent(
            self, cfg_agent_id, hosting_device_id,
            expected_code=exc.HTTPNoContent.code, admin_context=True):
        path = "/agents/%s/%s/%s.%s" % (
            cfg_agent_id, ciscocfgagentscheduler.CFG_AGENT_HOSTING_DEVICES,
            hosting_device_id, self.fmt)
        req = self._path_delete_request(path, admin_context=admin_context)
        res = req.get_response(self.ext_api)
        self.assertEqual(expected_code, res.status_int)


class HostingDeviceConfigAgentSchedulerTestCaseBase(
    test_db_base_plugin_v2.NeutronDbPluginV2TestCase,
    test_db_device_manager.DeviceManagerTestCaseMixin,
    dev_mgr_test_support.DeviceManagerTestSupportMixin,
        HostingDeviceCfgAgentSchedulerTestMixIn):

    #NOTE(bobmel): Work-around to make these unit tests to work since we
    # let the core plugin implement the device manager service.
    # The device manager service should map to hosting device extension
    svc_constants.EXT_TO_SERVICE_MAPPING[
        ciscohostingdevicemanager.HOSTING_DEVICE_MANAGER_ALIAS] = (
        c_const.DEVICE_MANAGER)
    resource_prefix_map = (test_db_device_manager.TestDeviceManagerDBPlugin
                           .resource_prefix_map)
    mock_cfg_agent_notifiers = True
    host_category = HW_CATEGORY

    def setUp(self, core_plugin=None, dm_plugin=None, ext_mgr=None):
        # Save the global RESOURCE_ATTRIBUTE_MAP
        self.saved_attr_map = {}
        for resource, attrs in six.iteritems(
                attributes.RESOURCE_ATTRIBUTE_MAP):
            self.saved_attr_map[resource] = attrs.copy()
        if not core_plugin:
            core_plugin = CORE_PLUGIN_KLASS
        service_plugins = {}
        cfg.CONF.set_override('api_extensions_path',
                              dev_mgr_test_support.extensions_path)
        if ext_mgr is None:
            ext_mgr = dev_mgr_test_support.TestDeviceManagerExtensionManager()

        super(HostingDeviceConfigAgentSchedulerTestCaseBase, self).setUp(
            plugin=core_plugin, service_plugins=service_plugins,
            ext_mgr=ext_mgr)

        # Ensure we use policy definitions from our repo
        cfg.CONF.set_override('policy_file', policy_path, 'oslo_policy')
        self.core_plugin = manager.NeutronManager.get_plugin()
        self.plugin = self.core_plugin
        self.setup_notification_driver()

        cfg.CONF.set_override('allow_sorting', True)
        self._define_keystone_authtoken()

        self._mock_l3_admin_tenant()
        self._create_mgmt_nw_for_tests(self.fmt)
        # in unit tests we don't use keystone so we mock that session
        self.core_plugin._svc_vm_mgr_obj = service_vm_lib.ServiceVMManager(
            True, None, None, None, '', keystone_session=mock.MagicMock())
        self._mock_svc_vm_create_delete(self.core_plugin)
        self._mock_io_file_ops()
        if self.mock_cfg_agent_notifiers is True:
            self._mock_cfg_agent_notifier(self.plugin)
        self._other_tenant_id = dev_mgr_test_support._uuid()
        self.adminContext = n_context.get_admin_context()

    def _setup_cfg_agents(self, host_a_active=True, host_b_active=False,
                          host_c_active=False):
        self._register_cfg_agent_states(host_a_active, host_b_active,
                                        host_c_active)
        agents = self._list(
            'agents', query_params='agent_type=%s' % c_const.AGENT_TYPE_CFG)
        self._agent_dict = {agt['host']: agt for agt in agents['agents']}


class HostingDeviceConfigAgentSchedulerTestCase(
        HostingDeviceConfigAgentSchedulerTestCaseBase):

    def _test_assign_hosting_device_to_cfg_agent(self, hosting_device,
                                                 cfg_agent_id,
                                                 id_bound_agent=None):
        hd = hosting_device['hosting_device']
        self.assertEqual(id_bound_agent, hd['cfg_agent_id'])
        self._assign_hosting_device_to_cfg_agent(cfg_agent_id, hd['id'])
        hosting_device_after = self._show('hosting_devices', hd['id'])
        hd_after = hosting_device_after['hosting_device']
        self.assertEqual(cfg_agent_id, hd_after['cfg_agent_id'])
        return hosting_device_after

    def test_hosting_device_assign_to_cfg_agent(self):
        self._setup_cfg_agents()
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._test_assign_hosting_device_to_cfg_agent(hosting_device,
                                                              cfg_agent_id)

    def test_assigned_hosting_device_assign_to_cfg_agent(self):
        self._setup_cfg_agents(True, True)
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                cfg_agent_id1 = self._agent_dict[L3_CFG_HOST_A]['id']
                self._test_assign_hosting_device_to_cfg_agent(hosting_device,
                                                              cfg_agent_id1)
                hd = hosting_device['hosting_device']
                cfg_agent_id2 = self._agent_dict[L3_CFG_HOST_B]['id']
                self._assign_hosting_device_to_cfg_agent(
                    cfg_agent_id2, hd['id'], exc.HTTPConflict.code)
                hd_after = self._show('hosting_devices', hd['id'])[
                    'hosting_device']
                self.assertEqual(cfg_agent_id1, hd_after['cfg_agent_id'])

    def test_hosting_device_assign_to_cfg_agent_with_admin_state_down(self):
        self._setup_cfg_agents()
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                self.assertIsNone(hd['cfg_agent_id'])
                id_cfg_agent_disabled = self._agent_dict[L3_CFG_HOST_A]['id']
                self._update('agents', id_cfg_agent_disabled,
                             {'agent': {'admin_state_up': False}})
                self._assign_hosting_device_to_cfg_agent(
                    id_cfg_agent_disabled, hd['id'], exc.HTTPNotFound.code)
                hd_after = self._show('hosting_devices',
                                      hd['id'])['hosting_device']
                self.assertIsNone(hd_after['cfg_agent_id'])

    def test_hosting_device_assign_to_cfg_agent_two_times(self):
        self._setup_cfg_agents()
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                hd_after = self._test_assign_hosting_device_to_cfg_agent(
                    hosting_device, cfg_agent_id)
                self._test_assign_hosting_device_to_cfg_agent(hd_after,
                                                              cfg_agent_id,
                                                              cfg_agent_id)

    def test_hosting_device_assign_to_non_existing_cfg_agent(self):
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                no_cfg_agent_id = '00000000-0000-0000-0000-000000000099'
                self._assign_hosting_device_to_cfg_agent(
                    no_cfg_agent_id, hd['id'], exc.HTTPNotFound.code)
                hd_after = self._show('hosting_devices', hd['id'])[
                    'hosting_device']
                self.assertIsNone(hd_after['cfg_agent_id'])

    def test_hosting_device_assign_to_non_existing_hosting_device(self):
        self._setup_cfg_agents()
        no_hd_id = '00000000-0000-0000-0000-000000000099'
        cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
        self._assign_hosting_device_to_cfg_agent(cfg_agent_id, no_hd_id,
                                                 exc.HTTPNotFound.code)

    def test_hosting_device_unassign_from_hosting_device(self):
        self._setup_cfg_agents()
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._test_assign_hosting_device_to_cfg_agent(hosting_device,
                                                              cfg_agent_id)
                hd = hosting_device['hosting_device']
                self._unassign_hosting_device_from_cfg_agent(cfg_agent_id,
                                                             hd['id'])
                hd_final = self._show('hosting_devices',
                                      hd['id'])['hosting_device']
                self.assertIsNone(hd_final['cfg_agent_id'])

    def test_hosting_device_unassign_from_non_existing_cfg_agent(self):
        self._setup_cfg_agents()
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._test_assign_hosting_device_to_cfg_agent(hosting_device,
                                                              cfg_agent_id)
                hd = hosting_device['hosting_device']
                no_cfg_agent_id = '00000000-0000-0000-0000-000000000099'
                self._unassign_hosting_device_from_cfg_agent(
                    no_cfg_agent_id, hd['id'], exc.HTTPNotFound.code)
                hd_after = self._show('hosting_devices',
                                      hd['id'])['hosting_device']
                self.assertEqual(cfg_agent_id, hd_after['cfg_agent_id'])

    def test_hosting_device_unassign_from_non_existing_hosting_device(self):
        self._setup_cfg_agents()
        no_hd_id = '00000000-0000-0000-0000-000000000099'
        cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
        self._unassign_hosting_device_from_cfg_agent(cfg_agent_id, no_hd_id,
                                                     exc.HTTPNotFound.code)

    def test_unassigned_hosting_device_unassign_from_hosting_device(self):
        self._setup_cfg_agents()
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                self.assertIsNone(hd['cfg_agent_id'])
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._unassign_hosting_device_from_cfg_agent(
                    cfg_agent_id, hd['id'], exc.HTTPNotFound.code)
                hd_after = self._show('hosting_devices',
                                      hd['id'])['hosting_device']
                self.assertIsNone(hd_after['cfg_agent_id'])

    def test_hosting_device_scheduling_policy(self):
        self._setup_cfg_agents()
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as (
                    hosting_device1),\
                    self.hosting_device(template_id=hdt['id']) as (
                        hosting_device2):
                hd1 = hosting_device1['hosting_device']
                hd2 = hosting_device2['hosting_device']
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._assign_hosting_device_to_cfg_agent(cfg_agent_id,
                                                         hd1['id'])
                self._list_hosting_devices_handled_by_cfg_agent(cfg_agent_id)
                self._list_hosting_devices_handled_by_cfg_agent(
                    cfg_agent_id, expected_code=exc.HTTPForbidden.code,
                    admin_context=False)
                self._assign_hosting_device_to_cfg_agent(
                    cfg_agent_id, hd2['id'],
                    expected_code=exc.HTTPForbidden.code, admin_context=False)
                self._unassign_hosting_device_from_cfg_agent(
                    cfg_agent_id, hd1['id'],
                    expected_code=exc.HTTPForbidden.code, admin_context=False)
                self._unassign_hosting_device_from_cfg_agent(cfg_agent_id,
                                                             hd1['id'])
                self._list_cfg_agents_handling_hosting_device(hd1['id'])
                self._list_cfg_agents_handling_hosting_device(
                    hd1['id'], expected_code=exc.HTTPForbidden.code,
                    admin_context=False)

    def test_list_hosting_devices_by_cfg_agent(self):
        self._setup_cfg_agents(True, True)
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as (
                    hosting_device1),\
                    self.hosting_device(template_id=hdt['id']) as (
                        hosting_device2),\
                    self.hosting_device(template_id=hdt['id']) as (
                        hosting_device3):
                hd1 = hosting_device1['hosting_device']
                hd2 = hosting_device2['hosting_device']
                hd3 = hosting_device3['hosting_device']
                cfg_agent1_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._assign_hosting_device_to_cfg_agent(cfg_agent1_id,
                                                         hd1['id'])
                self._assign_hosting_device_to_cfg_agent(cfg_agent1_id,
                                                         hd2['id'])
                cfg_agent2_id = self._agent_dict[L3_CFG_HOST_B]['id']
                self._assign_hosting_device_to_cfg_agent(cfg_agent2_id,
                                                         hd3['id'])
                hd_list1 = self._list_hosting_devices_handled_by_cfg_agent(
                    cfg_agent1_id)
                self.assertEqual(2, len(hd_list1['hosting_devices']))
                hd1_set = {hd1['id'], hd2['id']}
                for hd in hd_list1['hosting_devices']:
                    self.assertTrue(hd['id'] in hd1_set)
                hd_list2 = self._list_hosting_devices_handled_by_cfg_agent(
                    cfg_agent2_id)
                self.assertEqual(1, len(hd_list2['hosting_devices']))
                self.assertEqual(hd3['id'],
                                 hd_list2['hosting_devices'][0]['id'])

    def test_list_hosting_devices_by_cfg_agent_with_non_existing_cfg_agent(
            self):
        self._setup_cfg_agents()
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                missing_cfg_agent_id = '00000000-0000-0000-0000-000000000099'
                self._assign_hosting_device_to_cfg_agent(cfg_agent_id,
                                                         hd['id'])
                hd_list = self._list_hosting_devices_handled_by_cfg_agent(
                    missing_cfg_agent_id)
                self.assertEqual(0, len(hd_list['hosting_devices']))

    def test_list_cfg_agents_handling_hosting_device(self):
        self._setup_cfg_agents(True, True)
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._assign_hosting_device_to_cfg_agent(cfg_agent_id,
                                                         hd['id'])
                a_list = self._list_cfg_agents_handling_hosting_device(
                    hd['id'])
                self.assertEqual(1, len(a_list['agents']))
                self.assertEqual(cfg_agent_id, a_list['agents'][0]['id'])

    def test_list_cfg_agents_handling_unassigned_hosting_device(self):
        self._setup_cfg_agents(True, True)
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                a_list = self._list_cfg_agents_handling_hosting_device(
                    hd['id'])
                self.assertEqual(0, len(a_list['agents']))

    def test_list_cfg_agents_handling_non_existent_hosting_device(self):
        self._setup_cfg_agents()
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                hd_id_non_exist = hd['id'][:-1]
                self._list_cfg_agents_handling_hosting_device(
                    hd_id_non_exist, exc.HTTPNotFound.code)

    def test_get_cfg_agents(self):
        self._setup_cfg_agents(True, True)
        agents = self.plugin.get_cfg_agents(self.adminContext)
        self.assertEqual(len(self._agent_dict), len(agents))
        for agent in agents:
            self.assertIn(agent.host, self._agent_dict)
        id_cfg_agent_disabled = self._agent_dict[L3_CFG_HOST_A]['id']
        # admin down cfg agent should not be returned
        self._update('agents', id_cfg_agent_disabled,
                     {'agent': {'admin_state_up': False}})
        active_agents = self.plugin.get_cfg_agents(self.adminContext,
                                                   active=True)
        self.assertEqual(1, len(active_agents))
        self.assertEqual(L3_CFG_HOST_B, active_agents[0].host)
        self._update('agents', id_cfg_agent_disabled,
                     {'agent': {'admin_state_up': True}})
        # cfg agent with too old time report should not be returned
        with mock.patch(
                'networking_cisco.plugins.cisco.db.scheduler.'
                'cfg_agentschedulers_db.timeutils.'
                'is_older_than') as is_older_mock:
            is_older_mock.side_effect = [False, True]
            alive_agents = self.plugin.get_cfg_agents(self.adminContext,
                                                      active=True)
            self.assertEqual(1, len(alive_agents))
            self.assertEqual(L3_CFG_HOST_A, alive_agents[0].host)

    def test_get_cfg_agents_filtered(self):
        self._setup_cfg_agents(True, True, True)
        hosts = [L3_CFG_HOST_B, L3_CFG_HOST_C]
        agents = self.plugin.get_cfg_agents(self.adminContext,
                                            filters={'host': hosts})
        self.assertEqual(2, len(agents))
        for agent in agents:
            self.assertIn(agent.host, hosts)
        id_cfg_agent_disabled = self._agent_dict[L3_CFG_HOST_B]['id']
        # admin down agent should not be returned
        self._update('agents', id_cfg_agent_disabled,
                     {'agent': {'admin_state_up': False}})
        active_agents = self.plugin.get_cfg_agents(
            self.adminContext, active=True, filters={'host': hosts})
        self.assertEqual(1, len(active_agents))
        self.assertEqual(L3_CFG_HOST_C, active_agents[0].host)
        self._update('agents', id_cfg_agent_disabled,
                     {'agent': {'admin_state_up': True}})
        # cfg agent with too old time report should not be returned
        with mock.patch(
                'networking_cisco.plugins.cisco.db.scheduler.'
                'cfg_agentschedulers_db.timeutils.'
                'is_older_than') as is_older_mock:
            is_older_mock.side_effect = [False, True]
            alive_agents = self.plugin.get_cfg_agents(
                self.adminContext, active=True, filters={'host': hosts})
            self.assertEqual(1, len(alive_agents))
            self.assertEqual(L3_CFG_HOST_B, alive_agents[0].host)

    def _test_get_cfg_agents_for_hosting_devices(self, assignable_agents,
                                                 schedule=False,
                                                 id_disable_cfg_agent=None):
        def faked_choice(seq):
            res = seq[self._current_index]
            self._current_index += 1
            return res

        if id_disable_cfg_agent is not None:
            self._update('agents', id_disable_cfg_agent,
                         {'agent': {'admin_state_up': False}})
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as (
                    hosting_device1),\
                    self.hosting_device(template_id=hdt['id']) as (
                        hosting_device2),\
                    self.hosting_device(template_id=hdt['id']) as (
                        hosting_device3):
                hds = [hd['hosting_device'] for hd in (
                    hosting_device1, hosting_device2, hosting_device3)]
                hd_ids = [hd['id'] for hd in hds]
                # hosting devices initially not assigned to any cfg agent
                for hd in hds:
                    self.assertIsNone(hd['cfg_agent_id'])
                # hosting device with index 1 is to be left unassigned
                ids_hd_to_assign = [hds[0]['id'], hds[2]['id']]
                self._current_index = 0
                with mock.patch(
                    'networking_cisco.plugins.cisco.device_manager.scheduler'
                    '.hosting_device_cfg_agent_scheduler'
                        '.random.choice') as random_mock:
                    random_mock.side_effect = faked_choice
                    agents = self.plugin.get_cfg_agents_for_hosting_devices(
                        self.adminContext, ids_hd_to_assign, schedule=schedule)
                    self .assertEqual(len(assignable_agents), len(agents))
                    for agent in agents:
                        self.assertIn(agent['id'], assignable_agents)
                    hds_after_dict = {hd['id']: hd for hd in self._list(
                        'hosting_devices')['hosting_devices']}
                    hds_after = [hds_after_dict[i] for i in hd_ids]
                    if len(assignable_agents) == 0:
                        # with no assignable cfg agents none of the hosting
                        # devices should have been assigned a cfg agent
                        for hd_after in hds_after:
                            self.assertIsNone(hd_after['cfg_agent_id'])
                    else:
                        # hosting devices with index 0 and 2 should have been
                        # assigned a config agent (each one different)
                        self.assertIn(hds_after[0]['cfg_agent_id'],
                                      assignable_agents)
                        # remove agent from set to ensure the next assert
                        # can only match the other agent
                        assignable_agents.discard(hds_after[0]['cfg_agent_id'])
                        self.assertIn(hds_after[2]['cfg_agent_id'],
                                      assignable_agents)
                        # hosting device with index should still not have a
                        # cfg agent assigned
                        self.assertIsNone(hds_after[1]['cfg_agent_id'])

    def test_get_cfg_agents_for_hosting_devices(self):
        self._setup_cfg_agents(True, True, True)
        # the cfg agents that the hosting devices will be assigned to
        assignable_agents = {self._agent_dict[L3_CFG_HOST_A]['id'],
                             self._agent_dict[L3_CFG_HOST_B]['id']}
        self._test_get_cfg_agents_for_hosting_devices(assignable_agents, True)

    def test_get_cfg_agents_for_hosting_devices_no_schedule(self):
        self._setup_cfg_agents(True, True, True)
        # the hosting devices should not be assigned to any cfg agent
        assignable_agents = set()
        self._test_get_cfg_agents_for_hosting_devices(assignable_agents)

    def test_get_cfg_agents_for_hosting_devices_cfg_agent_admin_down(self):
        self._setup_cfg_agents(True, True, True)
        # the cfg agents that the hosting devices will be assigned to
        assignable_agents = {self._agent_dict[L3_CFG_HOST_A]['id'],
                             self._agent_dict[L3_CFG_HOST_C]['id']}
        # disable cfg agent on host_b
        id_disable_cfg_agent = self._agent_dict[L3_CFG_HOST_B]['id']
        self._test_get_cfg_agents_for_hosting_devices(assignable_agents, True,
                                                      id_disable_cfg_agent)

    def test_get_cfg_agents_for_hosting_devices_cfg_agent_admin_down_no_sched(
           self):
        self._setup_cfg_agents(True, True, True)
        # the hosting devices should not be assigned to any cfg agent
        assignable_agents = set()
        # disable cfg agent on host_b
        id_disable_cfg_agent = self._agent_dict[L3_CFG_HOST_B]['id']
        self._test_get_cfg_agents_for_hosting_devices(assignable_agents, False,
                                                      id_disable_cfg_agent)

    def test_get_cfg_agents_for_hosting_devices_reschedules_from_dead(self):
        self._setup_cfg_agents(True, True)
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._test_assign_hosting_device_to_cfg_agent(hosting_device,
                                                              cfg_agent_id)
                # cfg agent with too old time report should not be returned
                with mock.patch(
                    'networking_cisco.plugins.cisco.db.scheduler.'
                    'cfg_agentschedulers_db.timeutils.is_older_than') as (
                        is_older_mock):
                    # the cfg agents on host_a and host_b are dead and
                    # alive, respectively
                    is_older_mock.side_effect = [True, True, False]
                    agents = self.plugin.get_cfg_agents_for_hosting_devices(
                        self.adminContext, [hd['id']], schedule=True)
                    cfg_agent_id_after = self._agent_dict[L3_CFG_HOST_B]['id']
                    # the hosting device should now be rescheduled and thereby
                    # be bound to the cfg agent on host_b
                    self.assertEqual(1, len(agents))
                    self.assertEqual(cfg_agent_id_after, agents[0]['id'])
                    hosting_device_after = self._show('hosting_devices',
                                                      hd['id'])
                    hd_after = hosting_device_after['hosting_device']
                    self.assertEqual(cfg_agent_id_after,
                                     hd_after['cfg_agent_id'])

    def test__check_config_agents_auto_adds_new_cfg_agents(self):
        self._setup_cfg_agents()
        with mock.patch(
            'networking_cisco.plugins.cisco.db.scheduler.'
            'cfg_agentschedulers_db.timeutils.'
            'is_older_than') as is_older_mock:
            # make the cfg agent appear to have recent timestamps
            is_older_mock.side_effect = [False, False]
            self.plugin._check_config_agents()
            self.assertEqual(len(self._agent_dict),
                             len(self.plugin._cfg_agent_statuses))
            agent_ids = {attrs['id'] for attrs in self._agent_dict.values()}
            for agent_id, info in six.iteritems(
                    self.plugin._cfg_agent_statuses):
                self.assertIn(agent_id, agent_ids)

    def test__check_config_agents_stops_monitoring_non_existent_cfg_agents(
            self):
        self.plugin._cfg_agent_statuses['non_existent_agent_id'] = {
            'timestamp': 'faketime'}
        with mock.patch(
            'networking_cisco.plugins.cisco.db.scheduler.'
            'cfg_agentschedulers_db.timeutils.is_older_than') as is_older_mock:
            # The non-existent cfg agent should have a too old time stamp
            is_older_mock.side_effect = [True]
            self.plugin._check_config_agents()
            # verify that the non-existent cfg agent is no longer monitored
            self.assertEqual(0, len(self.plugin._cfg_agent_statuses))

    def test__check_config_agents_dead_cfg_agent_triggers_hd_rescheduling(
            self):
        self._setup_cfg_agents()
        with mock.patch(
            'networking_cisco.plugins.cisco.db.scheduler.'
            'cfg_agentschedulers_db.timeutils.is_older_than') as is_older_mock:
            # make the cfg agent appear to have recent timestamps
            is_older_mock.side_effect = [False, True, True, True]
            with mock.patch('networking_cisco.plugins.cisco.db.scheduler.'
                            'cfg_agentschedulers_db.CfgAgentSchedulerDbMixin.'
                            '_reschedule_hosting_devices') as resched_mock:
                self.plugin._check_config_agents()
                self.assertEqual(1, len(self.plugin._cfg_agent_statuses))
                agent_id = list(self._agent_dict.values())[0]['id']
                self.assertEqual(
                    list(self.plugin._cfg_agent_statuses.keys())[0], agent_id)
                resched_mock.assert_called_once_with(mock.ANY, agent_id)

    def test__reschedule_hosting_devices_no_other_cfg_agent(self):
        self._setup_cfg_agents(True)
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._test_assign_hosting_device_to_cfg_agent(hosting_device,
                                                              cfg_agent_id)
                hd_after = self._show('hosting_devices',
                                      hd['id'])['hosting_device']
                self.assertEqual(cfg_agent_id, hd_after['cfg_agent_id'])
                notify_mock = mock.MagicMock()
                self.plugin.agent_notifiers[c_const.AGENT_TYPE_CFG] = (
                    notify_mock)
                e_context = n_context.get_admin_context()
                with mock.patch(
                        'networking_cisco.plugins.cisco.db.scheduler.'
                        'cfg_agentschedulers_db.timeutils.is_older_than') as (
                        is_older_mock):
                    # make the cfg agent appear to have outdated timestamps
                    is_older_mock.side_effect = [True]
                    self.plugin._reschedule_hosting_devices(e_context,
                                                            cfg_agent_id)
                    hd_final = self._show('hosting_devices',
                                          hd['id'])['hosting_device']
                    self.assertIsNone(hd_final['cfg_agent_id'])
                    self.assertEqual(0, notify_mock.call_count)

    def test__reschedule_hosting_devices_to_other_cfg_agent(self):
        random_patch = mock.patch('random.choice')
        random_mock = random_patch.start()

        def side_effect(seq):
            return seq[0]

        random_mock.side_effect = side_effect
        self._setup_cfg_agents(True, True)
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(
                    template_id=hdt['id']) as hosting_device_1,\
                    self.hosting_device(
                        template_id=hdt['id']) as hosting_device_2:
                cfg_agent_id1 = self._agent_dict[L3_CFG_HOST_A]['id']
                self._test_assign_hosting_device_to_cfg_agent(hosting_device_1,
                                                              cfg_agent_id1)
                self._test_assign_hosting_device_to_cfg_agent(hosting_device_2,
                                                              cfg_agent_id1)
                hds_after = self._list('hosting_devices')['hosting_devices']
                for hd_after in hds_after:
                    self.assertEqual(cfg_agent_id1, hd_after['cfg_agent_id'])
                notify_mock = mock.MagicMock()
                self.plugin.agent_notifiers[c_const.AGENT_TYPE_CFG] = (
                    notify_mock)
                e_context = n_context.get_admin_context()
                with mock.patch(
                        'networking_cisco.plugins.cisco.db.scheduler.'
                        'cfg_agentschedulers_db.timeutils.is_older_than') as (
                        is_older_mock):
                    # make the cfg agent appear to have outdated timestamps
                    is_older_mock.side_effect = [True, False, True, False]
                    self.plugin._reschedule_hosting_devices(e_context,
                                                            cfg_agent_id1)
                    cfg_agent_id2 = self._agent_dict[L3_CFG_HOST_B]['id']
                    hds_final = self._list(
                        'hosting_devices')['hosting_devices']
                    for hd_final in hds_final:
                        self.assertEqual(cfg_agent_id2,
                                         hd_final['cfg_agent_id'])
        assign_notify_mock = notify_mock.hosting_devices_assigned_to_cfg_agent
        hd_ids = [hd['id'] for hd in hds_final]
        assign_notify_mock.assert_called_once_with(
            mock.ANY, hd_ids, self._agent_dict[L3_CFG_HOST_B]['host'])
        random_patch.stop()


class HostingDeviceConfigAgentNotifierTestCase(
        HostingDeviceConfigAgentSchedulerTestCaseBase):

    mock_cfg_agent_notifiers = False

    def setUp(self, core_plugin=None, dm_plugin=None, ext_mgr=None):
        super(HostingDeviceConfigAgentNotifierTestCase, self).setUp(
            core_plugin, dm_plugin, ext_mgr)
        fake_notifier.reset()

    def test_hosting_device_assign_to_cfg_agent_notification(self):
        cfg_notifier = self.plugin.agent_notifiers[c_const.AGENT_TYPE_CFG]
        with mock.patch.object(cfg_notifier.client, 'prepare',
                               return_value=cfg_notifier.client) as (
            mock_prepare),\
            mock.patch.object(cfg_notifier.client, 'cast') as mock_cast,\
            self.hosting_device_template(host_category=self.host_category) as (
                hosting_device_template):
            hdt = hosting_device_template['hosting_device_template']
            self._setup_cfg_agents()
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._assign_hosting_device_to_cfg_agent(cfg_agent_id,
                                                         hd['id'])
                mock_prepare.assert_called_with(
                    server=L3_CFG_HOST_A)
                mock_cast.assert_called_with(
                    mock.ANY, 'hosting_devices_assigned_to_cfg_agent',
                    payload={'hosting_device_ids': [hd['id']]})
                notifications = fake_notifier.NOTIFICATIONS
                expected_event_type = 'agent.hosting_device.add'
                self._assert_notify(notifications, expected_event_type)

    def test_hosting_device_unassign_from_cfg_agent_notification(self):
        cfg_notifier = self.plugin.agent_notifiers[c_const.AGENT_TYPE_CFG]
        with mock.patch.object(cfg_notifier.client, 'prepare',
                               return_value=cfg_notifier.client) as (
                mock_prepare),\
                mock.patch.object(cfg_notifier.client, 'cast') as mock_cast,\
                self.hosting_device_template(
                    host_category=self.host_category) as (
                        hosting_device_template):
            hdt = hosting_device_template['hosting_device_template']
            self._setup_cfg_agents()
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                cfg_agent_id = self._agent_dict[L3_CFG_HOST_A]['id']
                self._assign_hosting_device_to_cfg_agent(cfg_agent_id,
                                                         hd['id'])
                self._unassign_hosting_device_from_cfg_agent(cfg_agent_id,
                                                             hd['id'])
                mock_prepare.assert_called_with(
                    server=L3_CFG_HOST_A)
                mock_cast.assert_called_with(
                    mock.ANY, 'hosting_devices_unassigned_from_cfg_agent',
                    payload={'hosting_device_ids': [hd['id']]})
                notifications = fake_notifier.NOTIFICATIONS
                expected_event_type = 'agent.hosting_device.remove'
                self._assert_notify(notifications, expected_event_type)

    def test_hosting_device_assign_from_cfg_agent_notification_when_schedule(
            self):
        cfg_notifier = self.plugin.agent_notifiers[c_const.AGENT_TYPE_CFG]
        with mock.patch.object(
                cfg_notifier.client, 'prepare',
                return_value=cfg_notifier.client) as mock_prepare,\
                mock.patch.object(cfg_notifier.client, 'cast') as mock_cast,\
                self.hosting_device_template(
                    host_category=self.host_category) as (
                        hosting_device_template):
            hdt = hosting_device_template['hosting_device_template']
            self._setup_cfg_agents()
            with self.hosting_device(template_id=hdt['id']) as hosting_device:
                hd = hosting_device['hosting_device']
                self.plugin.get_cfg_agents_for_hosting_devices(
                        self.adminContext, [hd['id']], schedule=True)
                mock_prepare.assert_called_with(
                    server=L3_CFG_HOST_A)
                mock_cast.assert_called_with(
                    mock.ANY, 'hosting_devices_assigned_to_cfg_agent',
                    payload={'hosting_device_ids': [hd['id']]})


class HostingDeviceToCfgAgentRandomSchedulerTestCase(
        HostingDeviceConfigAgentSchedulerTestCaseBase):

    def test_random_scheduling(self):
        random_patch = mock.patch('random.choice')
        random_mock = random_patch.start()

        def side_effect(seq):
            return seq[0]
        random_mock.side_effect = side_effect

        self._setup_cfg_agents(True, True)
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as (
                    hosting_device_1):
                hd1 = hosting_device_1['hosting_device']
                agents = self.plugin.get_cfg_agents_for_hosting_devices(
                    self.adminContext, [hd1['id']], schedule=True)
                self.assertEqual(1, len(agents))
                self.assertEqual(1, random_mock.call_count)
                with self.hosting_device(template_id=hdt['id']) as (
                        hosting_device_2):
                    hd2 = hosting_device_2['hosting_device']
                    self.plugin.get_cfg_agents_for_hosting_devices(
                        self.adminContext, [hd2['id']], schedule=True)
                    self.assertEqual(2, random_mock.call_count)


class HostingDeviceToCfgAgentStingySchedulerTestCase(
        HostingDeviceConfigAgentSchedulerTestCaseBase):

    def setUp(self, core_plugin=None, dm_plugin=None, ext_mgr=None):
        cfg.CONF.set_override('configuration_agent_scheduler_driver',
                              'networking_cisco.plugins.cisco.device_manager.'
                              'scheduler.hosting_device_cfg_agent_scheduler.'
                              'StingyHostingDeviceCfgAgentScheduler',
                              'general')
        super(HostingDeviceToCfgAgentStingySchedulerTestCase, self).setUp(
            core_plugin=core_plugin, dm_plugin=dm_plugin, ext_mgr=ext_mgr)

    def test_stingy_scheduling(self):
        self._setup_cfg_agents(True, True, True)
        with self.hosting_device_template(
                host_category=self.host_category) as hosting_device_template:
            hdt = hosting_device_template['hosting_device_template']
            with self.hosting_device(template_id=hdt['id']) as (
                    hosting_device_1),\
                    self.hosting_device(template_id=hdt['id']) as (
                        hosting_device_2),\
                    self.hosting_device(template_id=hdt['id']) as (
                        hosting_device_3):
                hd1 = hosting_device_1['hosting_device']
                hd2 = hosting_device_2['hosting_device']
                hd3 = hosting_device_3['hosting_device']
                hd_ids = [hd1['id'], hd2['id'], hd3['id']]
                agents = self.plugin.get_cfg_agents_for_hosting_devices(
                    self.adminContext, hd_ids, schedule=True)
                self.assertEqual(3, len(agents))
                self.assertNotEqual(agents[0]['id'], agents[1]['id'])
                self.assertNotEqual(agents[0]['id'], agents[2]['id'])
                self.assertNotEqual(agents[1]['id'], agents[2]['id'])
