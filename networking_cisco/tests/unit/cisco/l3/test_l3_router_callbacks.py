# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
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

import mock
import six

from oslo_db import exception as db_exc

from neutron.extensions import l3
from neutron.tests import base
from neutron_lib import constants

from networking_cisco.plugins.cisco.l3.rpc import l3_router_cfg_agent_rpc_cb


# NOTE(bobmel): The scheduling functions called by some of the callback
# functions are tested in test_l3_routertype_aware_schedulers.py and in
# test_l3_router_appliance_plugin.py (specifically the class
# L3CfgAgentRouterApplianceTestCase).
class TestCfgAgentL3RouterCallbacks(base.BaseTestCase):

    def setUp(self):
        self.l3_plugin = mock.MagicMock()
        self.cb = l3_router_cfg_agent_rpc_cb.L3RouterCfgRpcCallback(
            self.l3_plugin)
        self.contextMock = mock.MagicMock()
        super(TestCfgAgentL3RouterCallbacks, self).setUp()

    def test_cfg_sync_routers_retries_on_db_errors(self):
        router_ids = ['some_router_id_1', 'some_router_id_2']
        routers = [{'id': router_ids[0]}, {'id': router_ids[1]}]
        host = 'some_host'
        hosting_device_ids = [host]
        self.l3_plugin.list_active_sync_routers_on_hosting_devices = (
            mock.MagicMock(side_effect=[db_exc.DBDeadlock, db_exc.DBDeadlock,
                                        routers]))
        result = self.cb.cfg_sync_routers(self.contextMock, host,
                                          router_ids, hosting_device_ids)
        calls = [mock.call(mock.ANY, host, router_ids, hosting_device_ids)
                 for call in [1, 2, 3]]
        (self.l3_plugin.list_active_sync_routers_on_hosting_devices
         .assert_has_calls(calls))
        self.assertEqual(
            3,
            self.l3_plugin.list_active_sync_routers_on_hosting_devices.
            call_count)
        self.assertEqual(routers, result)

    def test_cfg_sync_routers_missing_scheduling_fcn(self):
        self.l3_plugin.list_active_sync_routers_on_hosting_devices = (
            mock.MagicMock(side_effect=AttributeError))
        result = self.cb.cfg_sync_routers(self.contextMock, 'some_host')
        self.assertEqual([], result)

    def test_cfg_sync_all_hosted_routers_retries_on_db_errors(self):
        routers = [{'id': 'some_router_id_1'}, {'id': 'some_router_id_2'}]
        self.l3_plugin.list_all_routers_on_hosting_devices = mock.MagicMock(
            side_effect=[db_exc.DBDeadlock, db_exc.DBDeadlock, routers])
        result = self.cb.cfg_sync_all_hosted_routers(self.contextMock,
                                                     'some_host')
        self.assertEqual(
            3, self.l3_plugin.list_all_routers_on_hosting_devices.call_count)
        self.assertEqual(routers, result)

    def test_cfg_sync_all_hosted_routers_missing_scheduling_fcn(self):
        self.l3_plugin.list_all_routers_on_hosting_devices = mock.MagicMock(
            side_effect=AttributeError)
        result = self.cb.cfg_sync_all_hosted_routers(self.contextMock,
                                                     'some_host')
        self.assertEqual([], result)

    def test_update_floatingip_statuses_cfg_retries_on_db_errors(self):
        fip_statuses = {'fip_id_1': 'ACTIVE'}
        self.l3_plugin.update_floatingip_status = mock.MagicMock(
            side_effect=[db_exc.DBDeadlock, None])
        self.cb.update_floatingip_statuses_cfg(
            self.contextMock, 'some_router_id', fip_statuses)
        calls = [mock.call(self.contextMock, fip_id, status)
                 for fip_id, status in six.iteritems(fip_statuses)]
        self.l3_plugin.update_floatingip_status.assert_has_calls(calls)
        self.assertEqual(2, self.l3_plugin.update_floatingip_status.call_count)

    def test_update_floatingip_statuses_cfg_ignores_missing_fip(self):
        bad_fip_id = 'id_non_existent_fip'
        fip_statuses = {bad_fip_id: 'ACTIVE'}
        self.l3_plugin.update_floatingip_status = mock.MagicMock(
            side_effect=[l3.FloatingIPNotFound(floatingip_id=bad_fip_id)])
        self.l3_plugin.get_floatingips = mock.MagicMock(return_value=[])
        with mock.patch('networking_cisco.plugins.cisco.l3.rpc'
                        '.l3_router_cfg_agent_rpc_cb.LOG.debug') as log_mock:
            self.cb.update_floatingip_statuses_cfg(
                self.contextMock, 'some_router_id', fip_statuses)
        calls = [mock.call("Floating IP: %s no longer present.", bad_fip_id)]
        log_mock.assert_has_calls(calls, any_order=True)
        self.assertEqual(1, self.l3_plugin.update_floatingip_status.call_count)

    def test_update_floatingip_statuses_cfg_sets_status_down_if_no_router(
            self):
        fip_id = 'fip_id_1'
        status = 'ACTIVE'
        fip_statuses = {fip_id: status}
        self.l3_plugin.update_floatingip_status = mock.MagicMock()
        self.l3_plugin.get_floatingips = mock.MagicMock(return_value=[{
            'id': fip_id, 'router_id': None}])
        self.cb.update_floatingip_statuses_cfg(
            self.contextMock, 'some_router_id', fip_statuses)
        calls = [mock.call(self.contextMock, fip_id, status),
                 mock.call(self.contextMock, fip_id,
                           constants.FLOATINGIP_STATUS_DOWN)]
        self.l3_plugin.update_floatingip_status.assert_has_calls(calls)
        self.assertEqual(2, self.l3_plugin.update_floatingip_status.call_count)

    def test_update_port_statuses_cfg_retries_on_db_errors(self):
        port_ids = ['some_port_id_1', 'some_port_id_2']
        status = 'ACTIVE'
        self.l3_plugin.update_router_port_statuses = mock.MagicMock(
            side_effect=[db_exc.DBDeadlock, db_exc.DBDeadlock, port_ids])
        self.cb.update_port_statuses_cfg(self.contextMock, port_ids, status)
        calls = [mock.call(self.contextMock, port_ids, status)
                 for call in [1, 2, 3]]
        self.assertEqual(3,
                         self.l3_plugin.update_router_port_statuses.call_count)
        self.l3_plugin.update_router_port_statuses.assert_has_calls(calls)
