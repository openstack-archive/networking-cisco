# Copyright 2014 Cisco Systems, Inc.  All rights reserved.
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

import copy

import mock
import unittest

from oslo_config import cfg
from oslo_db import exception as db_exc
from oslo_utils import importutils
from oslo_utils import uuidutils
from sqlalchemy import exc as inner_db_exc
from webob import exc

from neutron.api.rpc.agentnotifiers import l3_rpc_agent_api
from neutron.common import constants
from neutron.common import test_lib
from neutron import context as n_context
from neutron.extensions import agent
from neutron.extensions import l3
from neutron import manager
from neutron.plugins.common import constants as plugin_consts
from neutron.tests import fake_notifier
from neutron.tests.unit.db import test_agentschedulers_db
from neutron.tests.unit.extensions import test_l3
from neutron.tests.unit.scheduler import test_l3_agent_scheduler
from neutron_lib import constants as lib_constants

from networking_cisco.plugins.cisco.common import cisco_constants as c_const
from networking_cisco.plugins.cisco.db.l3 import ha_db
from networking_cisco.plugins.cisco.db.scheduler import (
    l3_routertype_aware_schedulers_db as router_sch_db)
from networking_cisco.plugins.cisco.extensions import ciscohostingdevicemanager
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routerhostingdevice
from networking_cisco.plugins.cisco.extensions import routertype
from networking_cisco.plugins.cisco.extensions import routertypeawarescheduler
from networking_cisco.plugins.cisco.l3.rpc import l3_router_rpc_cfg_agent_api
from networking_cisco.plugins.cisco.l3.schedulers import (
    l3_router_hosting_device_scheduler as scheduler)
from networking_cisco.tests.unit.cisco.device_manager import (
    device_manager_test_support)
from networking_cisco.tests.unit.cisco.device_manager import (
    test_db_device_manager)
from networking_cisco.tests.unit.cisco.l3 import (
    test_l3_router_appliance_plugin)
from networking_cisco.tests.unit.cisco.l3 import l3_router_test_support
from networking_cisco.tests.unit.cisco.l3 import test_db_routertype


CORE_PLUGIN_KLASS = device_manager_test_support.CORE_PLUGIN_KLASS
L3_PLUGIN_KLASS = (
    'networking_cisco.tests.unit.cisco.l3.test_l3_routertype_aware_schedulers.'
    'TestSchedulingCapableL3RouterServicePlugin')
HA_L3_PLUGIN_KLASS = ('networking_cisco.tests.unit.cisco.l3.'
                      'test_l3_routertype_aware_schedulers.'
                      'TestSchedulingHACapableL3RouterServicePlugin')

_uuid = uuidutils.generate_uuid
HOSTING_DEVICE_ATTR = routerhostingdevice.HOSTING_DEVICE_ATTR
HARDWARE_CATEGORY = ciscohostingdevicemanager.HARDWARE_CATEGORY
AGENT_TYPE_L3_CFG = c_const.AGENT_TYPE_L3_CFG


class TestSchedulingL3RouterApplianceExtensionManager(
        test_db_routertype.L3TestRoutertypeExtensionManager):

    def get_resources(self):
        # first, add auto_schedule and share_hosting_device attributes to
        # router resource
        l3.RESOURCE_ATTRIBUTE_MAP['routers'].update(
            routertypeawarescheduler.EXTENDED_ATTRIBUTES_2_0['routers'])
        # most of the resources are added in our super class
        res = super(TestSchedulingL3RouterApplianceExtensionManager,
                    self).get_resources()
        # add the router to hosting device scheduler resources
        ext_mgr = routertypeawarescheduler.Routertypeawarescheduler()
        for item in ext_mgr.get_resources():
            res.append(item)
        return res


# A scheduler-enabled routertype capable L3 routing service plugin class
class TestSchedulingCapableL3RouterServicePlugin(
    l3_router_test_support.TestL3RouterServicePlugin,
        router_sch_db.L3RouterTypeAwareSchedulerDbMixin):

    supported_extension_aliases = (
        l3_router_test_support.TestL3RouterServicePlugin.
        supported_extension_aliases +
        [routertypeawarescheduler.ROUTERTYPE_AWARE_SCHEDULER_ALIAS,
         constants.L3_AGENT_SCHEDULER_EXT_ALIAS])

    def __init__(self):
        self.agent_notifiers.update(
            {lib_constants.AGENT_TYPE_L3: l3_rpc_agent_api.L3AgentNotifyAPI(),
             c_const.AGENT_TYPE_L3_CFG:
             l3_router_rpc_cfg_agent_api.L3RouterCfgAgentNotifyAPI(self)})
        self.router_scheduler = importutils.import_object(
            cfg.CONF.routing.router_type_aware_scheduler_driver)
        self.l3agent_scheduler = importutils.import_object(
            cfg.CONF.router_scheduler_driver)

    def cleanup_after_test(self):
        """Reset all class variables to their default values.
        This is needed to avoid tests to pollute subsequent tests.
        """
        TestSchedulingCapableL3RouterServicePlugin._router_schedulers = {}
        TestSchedulingCapableL3RouterServicePlugin._router_drivers = {}
        (TestSchedulingCapableL3RouterServicePlugin.
         _namespace_router_type_id) = None
        TestSchedulingCapableL3RouterServicePlugin._backlogged_routers = set()
        (TestSchedulingCapableL3RouterServicePlugin.
         _refresh_router_backlog) = True


class L3RoutertypeAwareL3AgentSchedulerTestCase(
    test_l3_agent_scheduler.L3SchedulerTestCaseMixin,
    test_db_routertype.RoutertypeTestCaseMixin,
    test_db_device_manager.DeviceManagerTestCaseMixin,
    l3_router_test_support.L3RouterTestSupportMixin,
        device_manager_test_support.DeviceManagerTestSupportMixin):

    resource_prefix_map = (test_db_device_manager.TestDeviceManagerDBPlugin
                           .resource_prefix_map)

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        if not core_plugin:
            core_plugin = CORE_PLUGIN_KLASS
        if l3_plugin is None:
            l3_plugin = L3_PLUGIN_KLASS
        service_plugins = {'l3_plugin_name': l3_plugin}

        cfg.CONF.set_override('api_extensions_path',
                              l3_router_test_support.extensions_path)
        if ext_mgr is None:
            ext_mgr = TestSchedulingL3RouterApplianceExtensionManager()

        # call grandparent's setUp() to avoid that wrong plugin and
        # extensions are used.
        super(test_l3_agent_scheduler.L3SchedulerTestCaseMixin, self).setUp(
            plugin=core_plugin, service_plugins=service_plugins,
            ext_mgr=ext_mgr)

        self._define_keystone_authtoken()
        cfg.CONF.set_override('default_router_type',
                              c_const.NAMESPACE_ROUTER_TYPE, group='routing')

        self.adminContext = n_context.get_admin_context()
        self.plugin = manager.NeutronManager.get_plugin()
        self.l3_plugin = manager.NeutronManager.get_service_plugins().get(
            plugin_consts.L3_ROUTER_NAT)
        # work-around to make some tests in super class, which assumes core
        # plugin does the l3 routing, run correctly
        self.plugin.router_scheduler = (
            self.l3_plugin.l3agent_scheduler)
        self._register_l3_agents()
        self._mock_l3_admin_tenant()
        templates = self._test_create_hosting_device_templates()
        self._test_create_routertypes(templates.values())
        # mock the periodic router backlog processing in the tests
        self._mock_backlog_processing(self.l3_plugin)

    def tearDown(self):
        self._test_remove_routertypes()
        self._test_remove_hosting_device_templates()
        self.l3_plugin.cleanup_after_test()
        self.plugin.cleanup_after_test()
        super(L3RoutertypeAwareL3AgentSchedulerTestCase, self).tearDown()

    def _test_add_router_to_l3_agent(self,
                                     distributed=False,
                                     already_scheduled=False,
                                     external_gw=None):
        # Parent test class run tests that use this function with L3 agent
        # notifier set to None so we do the same.
        self.l3_plugin.agent_notifiers[lib_constants.AGENT_TYPE_L3] = None
        super(L3RoutertypeAwareL3AgentSchedulerTestCase,
              self)._test_add_router_to_l3_agent()

    def test_add_router_to_l3_agent_dvr_to_snat(self):
        # Parent test class run tests that use this function with L3 agent
        # notifier set to None so we do the same.
        self.l3_plugin.agent_notifiers[lib_constants.AGENT_TYPE_L3] = None
        super(L3RoutertypeAwareL3AgentSchedulerTestCase,
              self).test_add_router_to_l3_agent_dvr_to_snat()

    def test_get_unscheduled_routers_only_returns_namespace_routers(self):
        self._create_mgmt_nw_for_tests(self.fmt)
        arg_list = (routertype.TYPE_ATTR, )
        kwargs = {routertype.TYPE_ATTR: test_db_routertype.HW_ROUTERTYPE_NAME}
        # router 1
        self._make_router(self.fmt, _uuid(), 'router1', arg_list=arg_list,
                          **kwargs)['router']
        # namespace-based routers
        with self.router(name='router2') as router2, self.router(
                name='router3') as router3:
            r2 = router2['router']
            r3 = router3['router']
            # router 4
            self._make_router(self.fmt, _uuid(), 'router2', arg_list=arg_list,
                              **kwargs)['router']
            routers = self.l3_plugin.router_scheduler._get_unscheduled_routers(
                self.adminContext, self.l3_plugin)
            r_ids = set(r['id'] for r in routers)
            self.assertEqual(2, len(r_ids))
            for r in [r2, r3]:
                self.assertIn(r['id'], r_ids)
        self._remove_mgmt_nw_for_tests()

    def test_only_namespace_routers_scheduled_by_l3agent_scheduler(self):
        self._create_mgmt_nw_for_tests(self.fmt)
        arg_list = (routertype.TYPE_ATTR, )
        kwargs = {routertype.TYPE_ATTR: test_db_routertype.HW_ROUTERTYPE_NAME}
        r1 = self._make_router(self.fmt, _uuid(), 'router1',
                               arg_list=arg_list, **kwargs)['router']
        # namespace-based routers
        with self.router(name='router2') as router2,\
                self.router(name='router3') as router3,\
                mock.patch.object(self.l3_plugin.l3agent_scheduler,
                                  'schedule') as scheduler_mock,\
                mock.patch('neutron.scheduler.l3_agent_scheduler.L3Scheduler.'
                           '_get_routers_can_schedule') as auto_scheduler_mock:
            r2 = router2['router']
            r3 = router3['router']
            r4 = self._make_router(self.fmt, _uuid(), 'router4',
                                   arg_list=arg_list, **kwargs)['router']
            r_list = [r1, r2, r3, r4]
            # first test schedule function
            self.l3_plugin.schedule_routers(self.adminContext, r_list)
            scheduler_mock.assert_has_calls(
                [mock.call(mock.ANY, self.adminContext, r2['id'], None),
                 mock.call(mock.ANY, self.adminContext, r3['id'], None)])
            r_ids = [r['id'] for r in r_list]
            # then test auto_schedule function
            self.l3_plugin.auto_schedule_routers(self.adminContext, 'host_1',
                                                 r_ids)
            r_ids_scheduled = set([r['id'] for r in
                                   auto_scheduler_mock.call_args[0][2]])
            self.assertEqual(2, len(r_ids_scheduled))
            for r in [r2, r3]:
                self.assertIn(r['id'], r_ids_scheduled)
        self._remove_mgmt_nw_for_tests()

    def test_rpc_sync_routers_gets_only_namespace_routers(self):
        self._create_mgmt_nw_for_tests(self.fmt)
        arg_list = (routertype.TYPE_ATTR, )
        kwargs = {routertype.TYPE_ATTR: test_db_routertype.HW_ROUTERTYPE_NAME}
        # router 1
        self._make_router(self.fmt, _uuid(), 'router1', arg_list=arg_list,
                          **kwargs)['router']
        # namespace-based routers
        with self.router(name='router2') as router2, self.router(
                name='router3') as router3:
            r2 = router2['router']
            r3 = router3['router']
            # router 4
            self._make_router(self.fmt, _uuid(), 'router2', arg_list=arg_list,
                              **kwargs)['router']
            routers = self.l3_plugin.get_sync_data(self.adminContext)
            r_ids = set(r['id'] for r in routers)
            self.assertEqual(2, len(r_ids))
            for r in [r2, r3]:
                self.assertIn(r['id'], r_ids)
        self._remove_mgmt_nw_for_tests()

    def test_check_ports_exist_on_l3agent_with_dhcp_enabled_subnets(self):
        # overload to disable this test that fails as as it pertains to DVR
        # which we don't support
        pass


class L3RoutertypeAwareChanceL3AgentSchedulerTestCase(
    test_l3_agent_scheduler.L3AgentChanceSchedulerTestCase,
        L3RoutertypeAwareL3AgentSchedulerTestCase):

    def setUp(self):
        cfg.CONF.set_override('router_scheduler_driver',
                              'neutron.scheduler.l3_agent_scheduler.'
                              'ChanceScheduler')
        # call grandparent's setUp() to avoid that wrong scheduler is used
        super(test_l3_agent_scheduler.L3AgentChanceSchedulerTestCase,
              self).setUp()
        # Some UTs in parent class expects self.plugin to refer to l3 plugin
        self.plugin = self.l3_plugin

    def test_scheduler_auto_schedule_when_agent_added(self):
        # in our test setup the auto_schedule_routers function is provided by
        # the separate l3 service plugin, not the core plugin
        self.l3_plugin.auto_schedule_routers = (
            self.l3_plugin.auto_schedule_routers)
        super(L3RoutertypeAwareChanceL3AgentSchedulerTestCase,
              self).test_scheduler_auto_schedule_when_agent_added()

    @unittest.skip("DVR not supported")
    def test_get_l3_agent_candidates_dvr_ha_snat_no_vms(self):
        pass

    @unittest.skip("DVR not supported")
    def test_get_l3_agent_candidates_dvr_no_vms(self):
        pass

    @unittest.skip("DVR not supported")
    def test_add_router_to_l3_agent_dvr_to_snat(self):
        pass

    @unittest.skip("DVR not supported")
    def test_remove_router_from_l3_agent_in_dvr_snat_mode(self):
        pass

    @unittest.skip("DVR not supported")
    def test_add_router_to_l3_agent_mismatch_error_dvr_to_legacy(self):
        pass


class L3RoutertypeAwareLeastRoutersL3AgentSchedulerTestCase(
    test_l3_agent_scheduler.L3AgentLeastRoutersSchedulerTestCase,
        L3RoutertypeAwareL3AgentSchedulerTestCase):

    def setUp(self):
        cfg.CONF.set_override('router_scheduler_driver',
                              'neutron.scheduler.l3_agent_scheduler.'
                              'LeastRoutersScheduler')
        # call grandparent's setUp() to avoid that wrong scheduler is used
        super(test_l3_agent_scheduler.L3AgentLeastRoutersSchedulerTestCase,
              self).setUp()
        # Some UTs in parent class expects self.plugin to refer to l3 plugin
        self.plugin = self.l3_plugin

    @unittest.skip("DVR not supported")
    def test_add_router_to_l3_agent_mismatch_error_dvr_to_legacy(self):
        pass

    @unittest.skip("DVR not supported")
    def test_remove_router_from_l3_agent_in_dvr_mode(self):
        pass

    @unittest.skip("DVR not supported")
    def test_add_router_to_l3_agent_mismatch_error_legacy_to_dvr(self):
        pass

    @unittest.skip("DVR not supported")
    def test_add_router_to_l3_agent_dvr_to_snat(self):
        pass

    @unittest.skip("DVR not supported")
    def test_remove_router_from_l3_agent_in_dvr_snat_mode(self):
        pass

    @unittest.skip("DVR not supported")
    def test_get_l3_agent_candidates_dvr_snat(self):
        pass


#TODO(bobmel): Activate unit tests for DVR when we support DVR

class RouterHostingDeviceSchedulerTestMixIn(
        test_agentschedulers_db.AgentSchedulerTestMixIn):

    def _list_routers_hosted_by_hosting_device(self, hosting_device_id,
                                               expected_code=exc.HTTPOk.code,
                                               admin_context=True):
        path = "/dev_mgr/hosting_devices/%s/%s.%s" % (
            hosting_device_id, routertypeawarescheduler.DEVICE_L3_ROUTERS,
            self.fmt)
        return self._request_list(path, expected_code=expected_code,
                                  admin_context=admin_context)

    def _list_hosting_devices_hosting_router(self, router_id,
                                             expected_code=exc.HTTPOk.code,
                                             admin_context=True):
        path = "/routers/%s/%s.%s" % (
            router_id, routertypeawarescheduler.L3_ROUTER_DEVICES, self.fmt)
        return self._request_list(path, expected_code=expected_code,
                                  admin_context=admin_context)

    def _add_router_to_hosting_device(self, hosting_device_id, router_id,
                                      expected_code=exc.HTTPCreated.code,
                                      admin_context=True):
        path = "/dev_mgr/hosting_devices/%s/%s.%s" % (
            hosting_device_id, routertypeawarescheduler.DEVICE_L3_ROUTERS,
            self.fmt)
        req = self._path_create_request(path,
                                        {'router_id': router_id},
                                        admin_context=admin_context)
        res = req.get_response(self.ext_api)
        self.assertEqual(expected_code, res.status_int)

    def _remove_router_from_hosting_device(
            self, hosting_device_id, router_id,
            expected_code=exc.HTTPNoContent.code, admin_context=True):
        path = "/dev_mgr/hosting_devices/%s/%s/%s.%s" % (
            hosting_device_id, routertypeawarescheduler.DEVICE_L3_ROUTERS,
            router_id, self.fmt)
        req = self._path_delete_request(path, admin_context=admin_context)
        res = req.get_response(self.ext_api)
        self.assertEqual(expected_code, res.status_int)


class L3RoutertypeAwareHostingDeviceSchedulerTestCaseBase(
    test_l3.L3NatTestCaseMixin,
    RouterHostingDeviceSchedulerTestMixIn,
        test_l3_router_appliance_plugin.L3RouterApplianceTestCaseBase):

    router_type = 'ASR1k_Neutron_router'
    configure_routertypes = False

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None, use_ini_files=True):
        # save possible test_lib.test_config 'config_files' dict entry so we
        # can restore it after tests since we will change its value
        self._old_config_files = copy.copy(test_lib.test_config.get(
            'config_files'))
        if l3_plugin is None:
            l3_plugin = L3_PLUGIN_KLASS
        if ext_mgr is None:
            ext_mgr = TestSchedulingL3RouterApplianceExtensionManager()
        super(L3RoutertypeAwareHostingDeviceSchedulerTestCaseBase, self).setUp(
            core_plugin, l3_plugin, dm_plugin, ext_mgr)
        if use_ini_files is True:
            # include config files for device manager service plugin and router
            # service plugin since we define a number of hosting device
            # templates, hosting devices and routertypes there
            self._add_device_manager_plugin_ini_file()
            self._add_router_plugin_ini_file()
        #TODO(bobmel): Fix bug in test_extensions.py and we can remove the
        # below call to setup_config()
        self.setup_config()
        # do pool management in same green thread during tests
        self._mock_eventlet_greenpool_spawn_n()
        self.adminContext = n_context.get_admin_context()
        # tests need a predictable random.choice so we always return first
        # item in the argument sequence
        self.random_patch = mock.patch('random.choice')
        random_mock = self.random_patch.start()

        random_mock.side_effect = lambda seq: sorted(seq)[0]

    def tearDown(self):
        self.random_patch.stop()
        if self._old_config_files is None:
            test_lib.test_config.pop('config_files', None)
        else:
            test_lib.test_config['config_files'] = self._old_config_files
        self._test_remove_all_hosting_devices()
        super(L3RoutertypeAwareHostingDeviceSchedulerTestCaseBase,
              self).tearDown()


class L3RoutertypeAwareHostingDeviceSchedulerBaseTestCase(
        L3RoutertypeAwareHostingDeviceSchedulerTestCaseBase):

    def test_new_router_backlogged_and_remains_backlogged_if_no_hosting_device(
            self):
        with mock.patch.object(self.l3_plugin, '_backlogged_routers') as m1,\
                mock.patch.object(self.l3_plugin, '_refresh_router_backlog',
                                  False):
            back_log = set()
            m1.__iter__ = lambda obj: iter(copy.deepcopy(back_log))
            m1.__contains__ = lambda obj, r_id: r_id in back_log
            m1.add.side_effect = lambda r_id: back_log.add(r_id)
            m1.discard.side_effect = lambda r_id: back_log.discard(r_id)
            arg_list = (routertype.TYPE_ATTR, )
            kwargs = {
                routertype.TYPE_ATTR: '00000000-0000-0000-0000-000000000007'}
            router = self._make_router(self.fmt, _uuid(), 'router1',
                                       arg_list=arg_list, **kwargs)
            r = router['router']
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            # verify that the new router is backlogged
            m1.add.assert_called_once_with(r['id'])
            self.assertIn(r['id'], back_log)
            self.l3_plugin._process_backlogged_routers()
            # verify that the router remains backlogged since not hosting
            # device exists for the router type
            self.assertIn(r['id'], back_log)

    def test_backlogged_router_is_scheduled_if_hosting_device_exists(self):
        with mock.patch.object(self.l3_plugin, '_backlogged_routers') as m1,\
                mock.patch.object(self.l3_plugin, '_refresh_router_backlog',
                                  False):
            back_log = set()
            # o'boy, this __iter__ mock took me so long to figure out....
            m1.__iter__ = lambda obj: iter(copy.deepcopy(back_log))
            m1.__contains__ = lambda obj, r_id: r_id in back_log
            m1.add.side_effect = lambda r_id: back_log.add(r_id)
            m1.discard.side_effect = lambda r_id: back_log.discard(r_id)
            arg_list = (routertype.TYPE_ATTR, )
            kwargs = {
                routertype.TYPE_ATTR: '00000000-0000-0000-0000-000000000006'}
            router = self._make_router(self.fmt, _uuid(), 'router1',
                                       arg_list=arg_list, **kwargs)
            r = router['router']
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            m1.add.assert_called_once_with(r['id'])
            self.l3_plugin._process_backlogged_routers()
            self.assertNotIn(r['id'], back_log)

    def test_already_backlogged_router_not_backlogged(self):
        with mock.patch.object(self.l3_plugin, '_backlogged_routers') as m:
            back_log = set()
            m.__contains__.side_effect = lambda r_id: r_id in back_log
            m.add.side_effect = lambda r_id: back_log.add(r_id)
            with self.router() as router:
                r = router['router']
                self.assertIsNone(r[HOSTING_DEVICE_ATTR])
                m.add.assert_called_once_with(r['id'])
                r_after = self._update(
                    'routers', r['id'],
                    {'router': {'name': 'routerA'}})['router']
                self.assertEqual('routerA', r_after['name'])
                self.assertIsNone(
                    r_after[HOSTING_DEVICE_ATTR])
                # router should be back-logged only once for later
                # scheduling attempts
                m.add.assert_called_once_with(r['id'])
                m.__contains__.assert_has_calls([mock.call(r['id']),
                                                 mock.call(r['id'])])

    def test_namespace_router_not_backlogged(self):
        with mock.patch.object(self.l3_plugin, '_backlogged_routers') as m:
            back_log = set()
            m.__contains__.side_effect = lambda r_id: r_id in back_log
            m.add.side_effect = lambda r_id: back_log.add(r_id)
            arg_list = (routertype.TYPE_ATTR, )
            kwargs = {
                routertype.TYPE_ATTR: '00000000-0000-0000-0000-000000000001'}
            router = self._make_router(self.fmt, _uuid(), 'router1',
                                       arg_list=arg_list, **kwargs)
            r = router['router']
            self.assertFalse(m.add.called)
            self.assertFalse(m.__contains__.called)
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            r_after = self._update('routers', r['id'],
                                   {'router': {'name': 'routerA'}})['router']
            self.assertEqual('routerA', r_after['name'])
            self.assertIsNone(
                r_after[HOSTING_DEVICE_ATTR])
            # router should be back-logged only once for later
            # scheduling attempts
            self.assertFalse(m.add.called)
            self.assertFalse(m.__contains__.called)

    def test_router_without_auto_schedule_not_backlogged(self):
        with mock.patch.object(self.l3_plugin, '_backlog_router') as (
                mock_b_lg):
            arg_list = (routertypeawarescheduler.AUTO_SCHEDULE_ATTR, )
            kwargs = {
                routertypeawarescheduler.AUTO_SCHEDULE_ATTR: False}
            router = self._make_router(self.fmt, _uuid(), 'router1',
                                       arg_list=arg_list, **kwargs)
            r = router['router']
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            mock_b_lg.assert_has_calls([])
            r_after = self._update('routers', r['id'],
                                   {'router': {'name': 'routerA'}})['router']
            self.assertIsNone(r_after[HOSTING_DEVICE_ATTR])
            mock_b_lg.assert_has_calls([])
            self.l3_plugin._sync_router_backlog()
            self.assertEqual(0, len(self.l3_plugin._backlogged_routers))

    def test_rpc_sync_routers_ext_gets_no_namespace_routers(self):
        arg_list = (routertype.TYPE_ATTR, )
        kwargs = {routertype.TYPE_ATTR: test_db_routertype.NS_ROUTERTYPE_NAME}
        # namespace-based routers
        self._make_router(self.fmt, _uuid(), 'router1', arg_list=arg_list,
                          **kwargs)
        # hw routers
        with self.router(name='router2') as r2, self.router(
                name='router3') as r3:
            # router 4
            self._make_router(self.fmt, _uuid(), 'router4', arg_list=arg_list,
                              **kwargs)
            routers = self.l3_plugin.get_sync_data_ext(self.adminContext)
            r_ids = set(r['id'] for r in routers)
            self.assertEqual(2, len(r_ids))
            for r in [r2['router'], r3['router']]:
                self.assertIn(r['id'], r_ids)

    def test_router_scheduling_aborts_if_other_process_scheduled_router(self):

        def fake_allocator(context, binding_info_db, target_hosting_device_id,
                           slot_need, synchronized):
            # here we mimic that another process has concurrently already
            # completed the scheduling of the router so that the attempt here
            # fails and raises an IntegrityError
            res = orig_func(context, binding_info_db, selected_hd_id,
                            slot_need, synchronized)
            self.assertTrue(res)
            self.assertEqual(0, len(self.l3_plugin._backlogged_routers))
            # The call to orig_func removed the router from the one and only
            # backlog we have in the test when it bound the router to the
            # hosting device.
            # However, in the real, non-simulated case each process would have
            # its own backlog. We therefore put the router back in the backlog
            # to mimic this.
            self.l3_plugin._backlogged_routers.add(binding_info_db.router_id)
            # kaboom!
            raise db_exc.DBDuplicateEntry(
                inner_exception=inner_db_exc.IntegrityError(
                    "Invalid insert", params="", orig=None))

        selected_hd_id = '00000000-0000-0000-0000-000000000002'
        with self.router() as router:
            r = router['router']
            self.assertIn(r['id'], self.l3_plugin._backlogged_routers)
            orig_func = self.l3_plugin._try_allocate_slots_and_bind_to_host
            with mock.patch.object(
                    self.l3_plugin,
                    '_try_allocate_slots_and_bind_to_host') as m:
                m.side_effect = fake_allocator
                self.l3_plugin._process_backlogged_routers()
            self.assertEqual(1, len(self.l3_plugin._backlogged_routers))
            r_after = self._show('routers', r['id'])['router']
            self.assertEqual(selected_hd_id, r_after[HOSTING_DEVICE_ATTR])

    def test_router_deleted_by_other_process_removed_from_backlog(self):
        r_id = 'non_existant_router_id'
        self.l3_plugin._backlogged_routers.add(r_id)
        self.l3_plugin._refresh_router_backlog = False
        self.assertEqual(1, len(self.l3_plugin._backlogged_routers))
        self.l3_plugin._process_backlogged_routers()
        self.assertEqual(0, len(self.l3_plugin._backlogged_routers))


class L3RoutertypeAwareHostingDeviceSchedulerTestCase(
        L3RoutertypeAwareHostingDeviceSchedulerTestCaseBase):

    def test_router_add_to_hosting_device(self):
        with self.router() as router:
            r = router['router']
            rt_id = '00000000-0000-0000-0000-000000000005'
            self.assertEqual(rt_id, r[routertype.TYPE_ATTR])
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            self._add_router_to_hosting_device(
                '00000000-0000-0000-0000-000000000001', r['id'])
            r_after = self._show('routers', r['id'])['router']
            self.assertEqual(rt_id, r_after[routertype.TYPE_ATTR])
            self.assertEqual('00000000-0000-0000-0000-000000000001',
                             r_after[HOSTING_DEVICE_ATTR])

    def test_hosted_router_add_to_hosting_device(self):
        with self.router() as router:
            # trigger scheduling of router
            self.l3_plugin._process_backlogged_routers()
            r = self._show('routers', router['router']['id'])['router']
            rt_id = '00000000-0000-0000-0000-000000000005'
            self.assertEqual(rt_id, r[routertype.TYPE_ATTR])
            self.assertIsNotNone(r[HOSTING_DEVICE_ATTR])
            self._add_router_to_hosting_device(
                '00000000-0000-0000-0000-000000000002', r['id'],
                exc.HTTPConflict.code)
            r_after = self._show('routers', r['id'])['router']
            self.assertEqual(rt_id, r_after[routertype.TYPE_ATTR])
            self.assertEqual(r[HOSTING_DEVICE_ATTR],
                             r_after[HOSTING_DEVICE_ATTR])

    def test_hosted_router_add_to_different_type_hosting_device(self):
        with self.router() as router:
            r = router['router']
            rt_id = '00000000-0000-0000-0000-000000000005'
            self.assertEqual(rt_id, r[routertype.TYPE_ATTR])
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            hd_id = '00000000-0000-0000-0000-000000000004'
            self._add_router_to_hosting_device(hd_id, r['id'])
            r_after = self._show('routers', r['id'])['router']
            self.assertEqual(hd_id, r_after[HOSTING_DEVICE_ATTR])
            temp_rt_id = '00000000-0000-0000-0000-000000000006'
            routertype_id = "%s (normal: %s)" % (temp_rt_id, rt_id)
            self.assertEqual(routertype_id, r_after[routertype.TYPE_ATTR])

    def test_router_add_to_hosting_device_insufficient_slots(self):
        with mock.patch.object(
                self.core_plugin,
                'acquire_hosting_device_slots') as acquire_mock,\
                self.router() as router:
            acquire_mock.return_value = False
            r = router['router']
            rt_id = '00000000-0000-0000-0000-000000000005'
            self.assertEqual(rt_id, r[routertype.TYPE_ATTR])
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            hd_id = '00000000-0000-0000-0000-000000000004'
            self._add_router_to_hosting_device(hd_id, r['id'],
                                               exc.HTTPConflict.code)
            r_after = self._show('routers', r['id'])['router']
            self.assertIsNone(r_after[HOSTING_DEVICE_ATTR])
            self.assertEqual(rt_id, r_after[routertype.TYPE_ATTR])

    def test_router_add_to_hosting_device_insufficient_slots_no_auto(self):
        with mock.patch.object(
                self.core_plugin,
                'acquire_hosting_device_slots') as acquire_mock,\
                mock.patch.object(self.l3_plugin,
                                  '_backlog_router') as mock_b_lg:
            acquire_mock.return_value = False
            arg_list = (routertypeawarescheduler.AUTO_SCHEDULE_ATTR, )
            kwargs = {
                routertypeawarescheduler.AUTO_SCHEDULE_ATTR: False}
            router = self._make_router(self.fmt, _uuid(), 'router1',
                                       arg_list=arg_list, **kwargs)
            r = router['router']
            rt_id = '00000000-0000-0000-0000-000000000005'
            self.assertEqual(rt_id, r[routertype.TYPE_ATTR])
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            mock_b_lg.assert_has_calls([])
            hd_id = '00000000-0000-0000-0000-000000000004'
            self._add_router_to_hosting_device(hd_id, r['id'],
                                               exc.HTTPConflict.code)
            r_after = self._show('routers', r['id'])['router']
            self.assertIsNone(r_after[HOSTING_DEVICE_ATTR])
            self.assertEqual(rt_id, r_after[routertype.TYPE_ATTR])
            mock_b_lg.assert_has_calls([])

    def test_router_add_to_hosting_device_with_admin_state_down(self):
        with self.router() as router:
            r = router['router']
            rt_id = '00000000-0000-0000-0000-000000000005'
            self.assertEqual(rt_id, r[routertype.TYPE_ATTR])
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            id_hd_disabled = '00000000-0000-0000-0000-000000000001'
            self._update('hosting_devices', id_hd_disabled,
                         {'hosting_device': {'admin_state_up': False}})
            self._add_router_to_hosting_device(id_hd_disabled, r['id'],
                                               exc.HTTPNotFound.code)
            r_after = self._show('routers', r['id'])['router']
            self.assertEqual(rt_id, r_after[routertype.TYPE_ATTR])
            self.assertIsNone(r_after[HOSTING_DEVICE_ATTR])

    def test_router_add_to_hosting_device_two_times(self):
        with self.router() as router:
            r = router['router']
            rt_id = '00000000-0000-0000-0000-000000000005'
            self.assertEqual(rt_id, r[routertype.TYPE_ATTR])
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            self._add_router_to_hosting_device(
                '00000000-0000-0000-0000-000000000001', r['id'])
            r_after = self._show('routers', r['id'])['router']
            self.assertEqual(rt_id, r_after[routertype.TYPE_ATTR])
            self.assertEqual('00000000-0000-0000-0000-000000000001',
                             r_after[HOSTING_DEVICE_ATTR])
            self._add_router_to_hosting_device(
                '00000000-0000-0000-0000-000000000001', r['id'])
            r_final = self._show('routers', r['id'])['router']
            self.assertEqual(rt_id, r_final[routertype.TYPE_ATTR])
            self.assertEqual('00000000-0000-0000-0000-000000000001',
                             r_final[HOSTING_DEVICE_ATTR])

    def test_router_remove_from_hosting_device(self):
        with self.router() as router:
            # trigger scheduling of router
            self.l3_plugin._process_backlogged_routers()
            r = self._show('routers', router['router']['id'])['router']
            rt_id = '00000000-0000-0000-0000-000000000005'
            self.assertEqual(rt_id, r[routertype.TYPE_ATTR])
            self.assertIsNotNone(r[HOSTING_DEVICE_ATTR])
            self._remove_router_from_hosting_device(
                '00000000-0000-0000-0000-000000000001', r['id'])
            r_after = self._show('routers', r['id'])['router']
            self.assertEqual(rt_id, r_after[routertype.TYPE_ATTR])
            self.assertIsNone(r_after[HOSTING_DEVICE_ATTR])

    def test_router_remove_from_wrong_hosting_device(self):
        with self.router() as router:
            # trigger scheduling of router
            self.l3_plugin._process_backlogged_routers()
            r = self._show('routers', router['router']['id'])['router']
            rt_id = '00000000-0000-0000-0000-000000000005'
            self.assertEqual(rt_id, r[routertype.TYPE_ATTR])
            self.assertIsNotNone(r[HOSTING_DEVICE_ATTR])
            self._remove_router_from_hosting_device(
                '00000000-0000-0000-0000-000000000002', r['id'],
                exc.HTTPConflict.code)
            r_after = self._show('routers', r['id'])['router']
            self.assertEqual(rt_id, r_after[routertype.TYPE_ATTR])
            self.assertEqual(r[HOSTING_DEVICE_ATTR],
                             r_after[HOSTING_DEVICE_ATTR])

    def test_unhosted_router_remove_from_hosting_device(self):
        with self.router() as router:
            r = router['router']
            rt_id = '00000000-0000-0000-0000-000000000005'
            self.assertEqual(rt_id, r[routertype.TYPE_ATTR])
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            self._remove_router_from_hosting_device(
                '00000000-0000-0000-0000-000000000001', r['id'],
                exc.HTTPConflict.code)
            r_after = self._show('routers', r['id'])['router']
            self.assertEqual(rt_id, r_after[routertype.TYPE_ATTR])
            self.assertIsNone(r_after[HOSTING_DEVICE_ATTR])

    def test_router_scheduling_policy(self):
        with self.router() as router1, self.router() as router2:
            r1 = router1['router']
            r2 = router2['router']
            hd_id = '00000000-0000-0000-0000-000000000001'
            self._add_router_to_hosting_device(hd_id, r1['id'])
            self._list_routers_hosted_by_hosting_device(hd_id)
            self._list_routers_hosted_by_hosting_device(
                hd_id, expected_code=exc.HTTPForbidden.code,
                admin_context=False)
            self._add_router_to_hosting_device(
                hd_id, r2['id'], expected_code=exc.HTTPForbidden.code,
                admin_context=False)
            self._remove_router_from_hosting_device(
                hd_id, r1['id'], expected_code=exc.HTTPForbidden.code,
                admin_context=False)
            self._remove_router_from_hosting_device(hd_id, r1['id'])
            self._list_hosting_devices_hosting_router(r1['id'])
            self._list_hosting_devices_hosting_router(
                r1['id'], expected_code=exc.HTTPForbidden.code,
                admin_context=False)

    def test_hosting_device_keep_services_off(self):
        #TODO(bobmel): Implement this unit test
        # Introduce new option: keep_services_on_agents_with_admin_state_down
        # Here set to keep_services_on_agents_with_admin_state_down = False
        # routers on hosting device that is set to admin down should be removed
        #  from that hosting device
        pass

    def test_hosting_device_keep_services_on(self):
        #TODO(bobmel): Implement this unit test
        # Introduce new option: keep_services_on_agents_with_admin_state_down
        # Here set to keep_services_on_agents_with_admin_state_down = False
        # routers on hosting device that set to admin down should stay on that
        # hosting device
        pass

    def test_list_routers_by_hosting_device(self):
        with self.router() as router1, self.router() as router2,\
                self.router() as router3:
            r1 = router1['router']
            r2 = router2['router']
            r3 = router3['router']
            hd1_id = '00000000-0000-0000-0000-000000000001'
            self._add_router_to_hosting_device(hd1_id, r1['id'])
            self._add_router_to_hosting_device(hd1_id, r2['id'])
            hd2_id = '00000000-0000-0000-0000-000000000002'
            self._add_router_to_hosting_device(hd2_id, r3['id'])
            r_list1 = self._list_routers_hosted_by_hosting_device(hd1_id)
            self.assertEqual(2, len(r_list1['routers']))
            r1_set = {r1['id'], r2['id']}
            for r in r_list1['routers']:
                self.assertTrue(r1_set)
            r_list2 = self._list_routers_hosted_by_hosting_device(hd2_id)
            self.assertEqual(1, len(r_list2['routers']))
            self.assertEqual(r3['id'], r_list2['routers'][0]['id'])

    def test_list_routers_by_hosting_device_with_non_existing_hosting_device(
            self):
        with self.router() as router:
            r = router['router']
            hd_id = '00000000-0000-0000-0000-000000000001'
            missing_hd_id = '00000000-0000-0000-0000-000000000099'
            self._add_router_to_hosting_device(hd_id, r['id'])
            r_list = self._list_routers_hosted_by_hosting_device(missing_hd_id)
            self.assertEqual(0, len(r_list['routers']))

    def test_list_hosting_devices_hosting_router(self):
        with self.router() as router:
            r = router['router']
            hd_id = '00000000-0000-0000-0000-000000000001'
            self._add_router_to_hosting_device(hd_id, r['id'])
            h_list = self._list_hosting_devices_hosting_router(r['id'])
            self.assertEqual(1, len(h_list['hosting_devices']))
            self.assertEqual(hd_id, h_list['hosting_devices'][0]['id'])

    def test_list_hosting_devices_hosting_unhosted_router(self):
        with self.router() as router:
            r = router['router']
            h_list = self._list_hosting_devices_hosting_router(r['id'])
            self.assertEqual(0, len(h_list['hosting_devices']))

    def test_list_hosting_devices_hosting_non_existent_router(self):
        with self.router() as router:
            r = router['router']
            r_id_non_exist = r['id'][:-1]
            h_list = self._list_hosting_devices_hosting_router(r_id_non_exist)
            self.assertEqual(0, len(h_list['hosting_devices']))

    def _test_list_active_sync_routers_on_hosting_devices(self, func):
        with self.router(name='router1') as router1,\
                self.router(name='router2') as router2,\
                self.router(name='router3') as router3:
            r1 = router1['router']
            r2 = router2['router']
            r3 = router3['router']
            hd1_id = '00000000-0000-0000-0000-000000000001'
            self._add_router_to_hosting_device(hd1_id, r1['id'])
            self._add_router_to_hosting_device(hd1_id, r2['id'])
            hd2_id = '00000000-0000-0000-0000-000000000002'
            self._add_router_to_hosting_device(hd2_id, r3['id'])
            # when cfg agent on host_a registers itself, hosting devices with
            # uuid hd1_id and hd2_id will be assigned to that cfg agent
            self._register_cfg_agent_states()
            template_id = '00000000-0000-0000-0000-000000000005'
            with self.hosting_device(template_id, no_delete=True) as h_d3,\
                    self.router(name='router4') as router4,\
                    self.router(name='router5') as router5:
                # hd3 should not yet have been assigned to a cfg agent
                hd3 = h_d3['hosting_device']
                r4 = router4['router']
                r5 = router5['router']
                self._add_router_to_hosting_device(hd3['id'], r4['id'])
                self._add_router_to_hosting_device(hd3['id'], r5['id'])
                # when cfg agent on host_b registers itself, hosting
                # device hd3 will be assigned to that cfg agent
                self._register_cfg_agent_states(host_a_active=False,
                                                host_b_active=True)
                agents = self._list(
                    'agents',
                    query_params='agent_type=%s' % c_const.AGENT_TYPE_CFG)
                agent_dict = {agt['host']: agt for agt in agents['agents']}
                if func:
                    func(r1, r2, r3, r4, r5, hd1_id, hd2_id, hd3,
                         template_id, agent_dict)

    def _verify_hosting(self, agent_dict, r_set, host, router_ids=None,
                        hosting_device_ids=None):
        r_l = self.l3_plugin.list_active_sync_routers_on_hosting_devices(
            self.adminContext, host, router_ids, hosting_device_ids)
        self.assertEqual(len(r_set), len(r_l))
        hds = {}
        agent_id = agent_dict[host]['id']
        for r in r_l:
            self.assertTrue(r['id'] in r_set)
            router_host = r[HOSTING_DEVICE_ATTR]
            if router_host not in hds:
                hd = self._show('hosting_devices', router_host)
                hds[router_host] = hd['hosting_device']
            self.assertEqual(agent_id, hds[router_host]['cfg_agent_id'])

    def test_list_active_sync_all_routers_on_all_hosting_devices(self):

        def assert_function(r1, r2, r3, r4, r5, hd1_id, hd2_id,
                            hd3, template_id, agent_dict):
            r_set = {r1['id'], r2['id'], r3['id']}
            self._verify_hosting(agent_dict, r_set,
                                 device_manager_test_support.L3_CFG_HOST_A)
            r_set = {r4['id'], r5['id']}
            self._verify_hosting(agent_dict, r_set,
                                 device_manager_test_support.L3_CFG_HOST_B)

        self._test_list_active_sync_routers_on_hosting_devices(assert_function)

    def test_list_active_sync_some_routers_on_all_hosting_devices(self):

        def assert_function(r1, r2, r3, r4, r5, hd1_id, hd2_id,
                            hd3, template_id, agent_dict):
            router_ids = [r1['id'], r3['id']]
            r_set = set(router_ids)
            self._verify_hosting(agent_dict, r_set,
                                 device_manager_test_support.L3_CFG_HOST_A,
                                 router_ids)

        self._test_list_active_sync_routers_on_hosting_devices(assert_function)

    def test_list_active_sync_all_routers_on_some_hosting_devices(self):
        def assert_function(r1, r2, r3, r4, r5, hd1_id, hd2_id,
                            hd3, template_id, agent_dict):
            r_set = {r3['id']}
            self._verify_hosting(agent_dict, r_set,
                                 device_manager_test_support.L3_CFG_HOST_A,
                                 hosting_device_ids=[hd2_id])

        self._test_list_active_sync_routers_on_hosting_devices(assert_function)

    def test_list_active_sync_some_routers_on_some_hosting_devices(self):
        def assert_function(r1, r2, r3, r4, r5, hd1_id, hd2_id,
                            hd3, template_id, agent_dict):
            router_ids = [r1['id'], r3['id']]
            r_set = {r1['id']}
            self._verify_hosting(agent_dict, r_set,
                                 device_manager_test_support.L3_CFG_HOST_A,
                                 router_ids, hosting_device_ids=[hd1_id])

        self._test_list_active_sync_routers_on_hosting_devices(assert_function)

    def test_list_active_sync_routers_on_hosting_devices_cfg_agent_admin_down(
            self):

        def assert_function(r1, r2, r3, r4, r5, hd1_id, hd2_id,
                            hd3, template_id, agent_dict):
            agent_id = agent_dict[device_manager_test_support.L3_CFG_HOST_A][
                'id']
            self._update('agents', agent_id,
                         {'agent': {'admin_state_up': False}})
            r_set = {}
            self._verify_hosting(agent_dict, r_set,
                                 device_manager_test_support.L3_CFG_HOST_A)
            r_set = {r4['id'], r5['id']}
            self._verify_hosting(agent_dict, r_set,
                                 device_manager_test_support.L3_CFG_HOST_B)

        self._test_list_active_sync_routers_on_hosting_devices(assert_function)

    def test_list_active_sync_routers_on_hosting_devices_idle_cfg_agent(
            self):

        def assert_function(r1, r2, r3, r4, r5, hd1_id, hd2_id,
                            hd3, template_id, agent_dict):
            # there should be no hosting devices left that can be assigned
            # to cfg agent on host_c
            self._register_cfg_agent_states(host_a_active=False,
                                            host_b_active=False,
                                            host_c_active=True)
            r_set = {}
            agents = self._list(
                'agents',
                query_params='agent_type=%s' % c_const.AGENT_TYPE_CFG)
            agent_dict = {agt['host']: agt for agt in agents['agents']}
            self._verify_hosting(agent_dict, r_set,
                                 device_manager_test_support.L3_CFG_HOST_C)
            r_set = {r1['id'], r2['id'], r3['id']}
            self._verify_hosting(agent_dict, r_set,
                                 device_manager_test_support.L3_CFG_HOST_A)
            r_set = {r4['id'], r5['id']}
            self._verify_hosting(agent_dict, r_set,
                                 device_manager_test_support.L3_CFG_HOST_B)

        self._test_list_active_sync_routers_on_hosting_devices(assert_function)

    def test_list_active_sync_routers_on_hosting_devices_no_cfg_agent_on_host(
            self):
        self.assertRaises(
            agent.AgentNotFoundByTypeHost,
            self.l3_plugin.list_active_sync_routers_on_hosting_devices,
            self.adminContext, 'bogus_host')

    def test_list_all_routers_on_hosting_devices(self):
        with self.router(name='router1') as router1,\
                self.router(name='router2'),\
                self.router(name='router3') as router3:
            r1 = router1['router']
            r3 = router3['router']
            hd1_id = '00000000-0000-0000-0000-000000000001'
            self._add_router_to_hosting_device(hd1_id, r1['id'])
            hd2_id = '00000000-0000-0000-0000-000000000002'
            self._add_router_to_hosting_device(hd2_id, r3['id'])
            template_id = '00000000-0000-0000-0000-000000000005'
            with self.hosting_device(template_id, no_delete=True) as h_d3,\
                    self.router(name='router4') as router4,\
                    self.router(name='router5') as router5:
                hd3 = h_d3['hosting_device']
                r4 = router4['router']
                r5 = router5['router']
                self._add_router_to_hosting_device(hd3['id'], r4['id'])
                self._add_router_to_hosting_device(hd3['id'], r5['id'])
                r_l = self.l3_plugin.list_all_routers_on_hosting_devices(
                    self.adminContext)
                r_set = {r1['id'], r3['id'], r4['id'], r5['id']}
                self.assertEqual(len(r_set), len(r_l))
                hds = {}
                for r in r_l:
                    self.assertTrue(r['id'] in r_set)
                    router_host = r[HOSTING_DEVICE_ATTR]
                    self.assertIsNotNone(router_host)
                    # assert that router's hosting device exists
                    if router_host not in hds:
                        hd = self._show('hosting_devices', router_host)
                        hds[router_host] = hd['hosting_device']

    def test_router_reschedule_from_dead_hosting_device(self):
        with mock.patch.object(self.l3_plugin, '_backlogged_routers') as m1,\
                mock.patch.object(self.l3_plugin, '_refresh_router_backlog',
                                  False):
            back_log = set()
            m1.__iter__ = lambda obj: iter(copy.deepcopy(back_log))
            m1.__contains__ = lambda obj, r_id: r_id in back_log
            m1.add.side_effect = lambda r_id: back_log.add(r_id)
            m1.discard.side_effect = lambda r_id: back_log.discard(r_id)
            with self.router(name='router1') as router1,\
                    self.router(name='router2') as router2,\
                    self.router(name='router3') as router3:
                rs_initial = [r['router'] for r in [router1, router2, router3]]
                # all routers initially un-hosted
                for r in rs_initial:
                    self.assertIsNone(r[HOSTING_DEVICE_ATTR])
                hosting_device_id1 = '00000000-0000-0000-0000-000000000001'
                hosting_device_id2 = '00000000-0000-0000-0000-000000000002'
                r_ids = [r['id'] for r in [rs_initial[0], rs_initial[2]]]
                for r_id in r_ids:
                    self._add_router_to_hosting_device(hosting_device_id1,
                                                       r_id)
                self._add_router_to_hosting_device(hosting_device_id2,
                                                   rs_initial[1]['id'])
                rs_after = [self._show('routers', r['id'])['router']
                            for r in rs_initial]
                # r1 and r3 on hosting device 1, r2 on hosting device 2
                for r in [rs_after[0], rs_after[2]]:
                    self.assertEqual(hosting_device_id1,
                                     r[HOSTING_DEVICE_ATTR])
                self.assertEqual(hosting_device_id2,
                                 rs_after[1][HOSTING_DEVICE_ATTR])
                # no routers should be back-logged now
                self.assertEqual(0, len(back_log))
                hosting_device_1 = self._show(
                    'hosting_devices', hosting_device_id1)['hosting_device']
                affected_resources = {}
                notifier_mock = mock.MagicMock()
                with mock.patch.dict(self.l3_plugin.agent_notifiers,
                                     {AGENT_TYPE_L3_CFG: notifier_mock}):
                    # now report hosting device 1 as dead
                    self.l3_plugin.handle_non_responding_hosting_devices(
                        self.adminContext, [hosting_device_1],
                        affected_resources)
                # only routers 1 and 3 should be affected
                affected_rs = affected_resources[hosting_device_id1]['routers']
                self.assertEqual(2, len(affected_rs))
                ntfy_method = notifier_mock.routers_removed_from_hosting_device
                ntfy_method.assert_called_with(mock.ANY, affected_rs,
                                               hosting_device_1)
                # affected routers should be back-logged
                for r_id in r_ids:
                    self.assertIn(r_id, affected_rs)
                    self.assertIn(r_id, back_log)
                rs_final = [self._show('routers', r['id'])['router']
                            for r in rs_initial]
                # routers 1 and 3 should be un-hosted
                for r in [rs_final[0], rs_final[2]]:
                    self.assertIsNone(r[HOSTING_DEVICE_ATTR])
                # router 2 was unaffected and should remain hosted
                self.assertEqual(hosting_device_id2,
                                 rs_final[1][HOSTING_DEVICE_ATTR])

    def test_router_without_auto_schedule_not_unscheduled_from_dead_hd(self):
        with mock.patch.object(
                self.l3_plugin, 'unschedule_router_from_hosting_device') as (
                    mock_unsched):
            arg_list = (routertypeawarescheduler.AUTO_SCHEDULE_ATTR, )
            kwargs = {
                routertypeawarescheduler.AUTO_SCHEDULE_ATTR: False}
            router = self._make_router(self.fmt, _uuid(), 'router1',
                                       arg_list=arg_list, **kwargs)
            r = router['router']
            r_id = r['id']
            self.assertIsNone(r[HOSTING_DEVICE_ATTR])
            hosting_device_id = '00000000-0000-0000-0000-000000000001'
            self._add_router_to_hosting_device(hosting_device_id, r_id)
            r_after = self._show('routers', r['id'])['router']
            self.assertEqual(hosting_device_id, r_after[HOSTING_DEVICE_ATTR])
            affected_resources = {}
            # now report hosting device 1 as dead
            self.l3_plugin.handle_non_responding_hosting_devices(
                self.adminContext, [{'id': hosting_device_id}],
                affected_resources)
            self.assertEqual(0, mock_unsched.call_count)
            r_final = self._show('routers', r['id'])['router']
            self.assertEqual(hosting_device_id, r_final[HOSTING_DEVICE_ATTR])


class HostingDeviceRouterL3CfgAgentNotifierTestCase(
        L3RoutertypeAwareHostingDeviceSchedulerTestCaseBase):

    mock_cfg_agent_notifiers = False

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        super(HostingDeviceRouterL3CfgAgentNotifierTestCase, self).setUp(
            core_plugin, l3_plugin, dm_plugin, ext_mgr)
        fake_notifier.reset()

    def test_router_add_to_hosting_device_notification(self):
        l3_notifier = self.l3_plugin.agent_notifiers[c_const.AGENT_TYPE_L3_CFG]
        with mock.patch.object(
                l3_notifier.client, 'prepare',
                return_value=l3_notifier.client) as mock_prepare,\
                mock.patch.object(l3_notifier.client, 'cast') as mock_cast,\
                self.router() as router:
            r = router['router']
            # when cfg agent on host_a registers itself, hosting
            # device with uuid hd_id will be assigned to that cfg agent
            self._register_cfg_agent_states()
            self._add_router_to_hosting_device(
                '00000000-0000-0000-0000-000000000001', r['id'])
            mock_prepare.assert_called_with(
                server=device_manager_test_support.L3_CFG_HOST_A)
            mock_cast.assert_called_with(
                mock.ANY, 'router_added_to_hosting_device',
                routers=[r['id']])
            notifications = fake_notifier.NOTIFICATIONS
            expected_event_type = 'hosting_device.router.add'
            self._assert_notify(notifications, expected_event_type)

    def test_router_remove_from_hosting_device_notification(self):
        l3_notifier = self.l3_plugin.agent_notifiers[c_const.AGENT_TYPE_L3_CFG]
        with mock.patch.object(
                l3_notifier.client, 'prepare',
                return_value=l3_notifier.client) as mock_prepare,\
                mock.patch.object(l3_notifier.client, 'cast') as mock_cast,\
                self.router() as router:
            r = router['router']
            # when cfg agent on host_a registers itself, hosting
            # device with uuid hd_id will be assigned to that cfg agent
            self._register_cfg_agent_states()
            self._add_router_to_hosting_device(
                '00000000-0000-0000-0000-000000000001', r['id'])
            self._remove_router_from_hosting_device(
                '00000000-0000-0000-0000-000000000001', r['id'])
            mock_prepare.assert_called_with(
                server=device_manager_test_support.L3_CFG_HOST_A)
            mock_cast.assert_called_with(
                mock.ANY, 'router_removed_from_hosting_device',
                routers=[r['id']])
            notifications = fake_notifier.NOTIFICATIONS
            expected_event_type = 'hosting_device.router.remove'
            self._assert_notify(notifications, expected_event_type)

    def test_backlogged_routers_scheduled_routers_updated_notification(self):
        l3_notifier = self.l3_plugin.agent_notifiers[c_const.AGENT_TYPE_L3_CFG]
        with mock.patch.object(
                l3_notifier.client, 'prepare',
                return_value=l3_notifier.client) as mock_prepare,\
                mock.patch.object(l3_notifier.client, 'cast') as mock_cast,\
                mock.patch.object(self.l3_plugin,
                                  '_backlogged_routers') as mock_b_lg,\
                mock.patch.object(self.l3_plugin, '_refresh_router_backlog',
                                  False):
            back_log = set()
            mock_b_lg.__iter__ = lambda obj: iter(copy.deepcopy(back_log))
            mock_b_lg.__contains__ = lambda obj, r_id: r_id in back_log
            mock_b_lg.add.side_effect = lambda r_id: back_log.add(r_id)
            mock_b_lg.discard.side_effect = lambda r_id: back_log.discard(r_id)
            arg_list = (routertype.TYPE_ATTR, )
            # namespace-based router
            kwargs = {
                routertype.TYPE_ATTR: '00000000-0000-0000-0000-000000000001'}
            self._make_router(self.fmt, _uuid(), 'router1', arg_list=arg_list,
                              **kwargs)
            # router that should be successfully hosted
            kwargs = {
                routertype.TYPE_ATTR: '00000000-0000-0000-0000-000000000006'}
            r2 = self._make_router(self.fmt, _uuid(), 'router2',
                                   arg_list=arg_list, **kwargs)['router']
            # routertype for which no hosting devices exists
            kwargs = {
                routertype.TYPE_ATTR: '00000000-0000-0000-0000-000000000007'}
            r3 = self._make_router(self.fmt, _uuid(), 'router3',
                                   arg_list=arg_list, **kwargs)['router']
            # routers that should be successfully hosted
            with self.router(name='router4') as router4, self.router(
                    name='router5') as router5:
                # when cfg agent on host_a registers itself, hosting
                # devices will be assigned to that cfg agent
                self._register_cfg_agent_states()
                r4 = router4['router']
                r5 = router5['router']
                self.assertEqual(4, len(back_log))
                for r_id in [r2['id'], r3['id'], r4['id'], r5['id']]:
                    self.assertIn(r_id, back_log)
                self.l3_plugin._process_backlogged_routers()
                mock_prepare.assert_called_with(
                    server=device_manager_test_support.L3_CFG_HOST_A)
                calls = [
                    mock.call(mock.ANY, 'routers_updated', routers=[r2['id']]),
                    mock.call(mock.ANY, 'routers_updated', routers=[r4['id']]),
                    mock.call(mock.ANY, 'routers_updated', routers=[r5['id']])]
                mock_cast.assert_has_calls(calls, any_order=True)
                self.assertEqual(1, len(back_log))
                self.assertIn(r3['id'], back_log)


class TestHASchedulingL3RouterApplianceExtensionManager(
        TestSchedulingL3RouterApplianceExtensionManager):

    def get_resources(self):
        # add ha attributes to router resource
        l3.RESOURCE_ATTRIBUTE_MAP['routers'].update(
            ha.EXTENDED_ATTRIBUTES_2_0['routers'])
        # let our super class do the rest
        return super(TestHASchedulingL3RouterApplianceExtensionManager,
                     self).get_resources()


# A scheduler-enabled routertype capable L3 routing service plugin class
class TestSchedulingHACapableL3RouterServicePlugin(
        ha_db.HA_db_mixin, TestSchedulingCapableL3RouterServicePlugin):

    supported_extension_aliases = (
        TestSchedulingCapableL3RouterServicePlugin.
        supported_extension_aliases +
        [routertypeawarescheduler.ROUTERTYPE_AWARE_SCHEDULER_ALIAS,
         constants.L3_AGENT_SCHEDULER_EXT_ALIAS,
         ha.HA_ALIAS])

    def cleanup_after_test(self):
        """Reset all class variables to their default values.
        This is needed to avoid tests to pollute subsequent tests.
        """
        TestSchedulingHACapableL3RouterServicePlugin._router_schedulers = {}
        TestSchedulingHACapableL3RouterServicePlugin._router_drivers = {}
        (TestSchedulingHACapableL3RouterServicePlugin.
         _namespace_router_type_id) = None
        (TestSchedulingHACapableL3RouterServicePlugin.
         _backlogged_routers) = set()
        (TestSchedulingHACapableL3RouterServicePlugin.
         _refresh_router_backlog) = True


class L3RouterHostingDeviceHARandomSchedulerTestCase(
        L3RoutertypeAwareHostingDeviceSchedulerTestCaseBase):

    _is_ha_tests = True

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        if l3_plugin is None:
            l3_plugin = HA_L3_PLUGIN_KLASS
        if ext_mgr is None:
            ext_mgr = TestHASchedulingL3RouterApplianceExtensionManager()
        cfg.CONF.set_override('default_ha_redundancy_level', 2, group='ha')
        super(L3RouterHostingDeviceHARandomSchedulerTestCase, self).setUp(
            l3_plugin=l3_plugin, ext_mgr=ext_mgr)

    def test_ha_routers_hosted_on_different_hosting_devices(self):
        with self.subnet() as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(external_gateway_info={
                    'network_id': s['subnet']['network_id']}) as router:
                r = router['router']
                self.l3_plugin._process_backlogged_routers()
                r_after = self._show('routers', r['id'])['router']
                self.assertIsNotNone(
                    r_after[routerhostingdevice.HOSTING_DEVICE_ATTR])
                hd_ids = {r_after[routerhostingdevice.HOSTING_DEVICE_ATTR]}
                r_rs_after = [self._show('routers', rr['id'])['router']
                              for rr in r[ha.DETAILS][ha.REDUNDANCY_ROUTERS]]
                for rr in r_rs_after:
                    hd_id = rr[routerhostingdevice.HOSTING_DEVICE_ATTR]
                    self.assertIsNotNone(hd_id)
                    self.assertNotIn(hd_id, hd_ids)
                    hd_ids.add(hd_id)


class L3RouterHostingDeviceBaseSchedulerTestCase(
        L3RoutertypeAwareHostingDeviceSchedulerTestCaseBase):

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):

        super(L3RouterHostingDeviceBaseSchedulerTestCase, self).setUp(
            use_ini_files=False)

    def _update_hosting_device_statuses(self, hosting_devices, statuses):
        adm_ctxt = n_context.get_admin_context()
        core_plugin = manager.NeutronManager.get_plugin()
        for (hosting_device, status) in zip(hosting_devices, statuses):
            hd = hosting_device['hosting_device']
            core_plugin.update_hosting_device(
                adm_ctxt, hd['id'], {'hosting_device': {'status': status}})

    def _test_get_candidates(self, templates_id, slot_capacity=5,
                             share_hosting_device=True,
                             slot_need=2, expected_candidates=None):
        r_hd_b_db = mock.MagicMock()
        r_hd_b_db.__getitem__ = lambda obj, name: fake_attrs[name]
        r_hd_b_db.share_hosting_device = share_hosting_device
        r_hd_b_db.router = mock.MagicMock()
        fake_attrs = {'template_id': templates_id,
                      'tenant_id': 'some_tenant'}
        r_hd_b_db.router.__getitem__ = lambda obj, name: fake_attrs[name]
        r_hd_b_db.router_type = mock.MagicMock()
        r_hd_b_db.router_type.slot_need = slot_need
        r_hd_b_db.router_type.__getitem__ = lambda obj, name: fake_attrs[name]
        r_hd_b_db.router_type.template = mock.MagicMock()
        r_hd_b_db.router_type.template.slot_capacity = slot_capacity
        adm_ctx = n_context.get_admin_context()
        sched_obj = scheduler.L3RouterHostingDeviceLongestRunningScheduler()
        candidates = sched_obj.get_candidates(None, adm_ctx, r_hd_b_db)
        expected_candidates = expected_candidates or []
        self.assertEqual(len(expected_candidates), len(candidates))
        # candidates must be in correct order
        for i in range(len(candidates)):
            self.assertEqual(expected_candidates[i], candidates[i][0])

    def test_get_candidates_excludes_non_active(self):
        with self.hosting_device_template(
                host_category=HARDWARE_CATEGORY) as hdt:
            template_id = hdt['hosting_device_template']['id']
            credentials = device_manager_test_support._uuid()
            with self.hosting_device(template_id=template_id,
                                     credentials_id=credentials) as hd1,\
                    self.hosting_device(template_id=template_id,
                                        credentials_id=credentials) as hd2,\
                    self.hosting_device(template_id=template_id,
                                        credentials_id=credentials) as hd3,\
                    self.hosting_device(template_id=template_id,
                                        credentials_id=credentials) as hd4,\
                    self.hosting_device(template_id=template_id,
                                        credentials_id=credentials) as hd5,\
                    self.hosting_device(template_id=template_id,
                                        credentials_id=credentials) as hd6:
                self._update_hosting_device_statuses(
                    [hd2, hd4, hd5],
                    [c_const.HD_DEAD, c_const.HD_ERROR,
                     c_const.HD_NOT_RESPONDING])
                expected = [hd1['hosting_device']['id'],
                            hd3['hosting_device']['id'],
                            hd6['hosting_device']['id']]
                self._test_get_candidates(template_id,
                                          expected_candidates=expected)

    def test_get_candidates_excludes_admin_down(self):
        with self.hosting_device_template(
                host_category=HARDWARE_CATEGORY) as hdt:
            template_id = hdt['hosting_device_template']['id']
            credentials = device_manager_test_support._uuid()
            with self.hosting_device(template_id=template_id,
                                     credentials_id=credentials) as hd1,\
                    self.hosting_device(template_id=template_id,
                                        credentials_id=credentials,
                                        admin_state_up=False),\
                    self.hosting_device(template_id=template_id,
                                        credentials_id=credentials,
                                        admin_state_up=False),\
                    self.hosting_device(template_id=template_id,
                                        credentials_id=credentials) as hd4:
                expected = [hd1['hosting_device']['id'],
                            hd4['hosting_device']['id']]
                self._test_get_candidates(template_id,
                                          expected_candidates=expected)
