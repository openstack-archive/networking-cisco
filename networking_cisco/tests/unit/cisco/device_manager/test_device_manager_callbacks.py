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

import mock
import six

from networking_cisco.plugins.cisco.common import cisco_constants as const
from networking_cisco.plugins.cisco.device_manager.rpc import (
    devices_cfgagent_rpc_cb)
from neutron.tests import base


class TestCfgAgentDeviceManagerCallbacks(base.BaseTestCase):

    def setUp(self):
        super(TestCfgAgentDeviceManagerCallbacks, self).setUp()

    def test_report_non_responding_hosting_devices(self):
        dm_plugin = mock.MagicMock()
        cb = devices_cfgagent_rpc_cb.DeviceMgrCfgRpcCallback(dm_plugin)
        ctx = mock.MagicMock()
        host = 'some_host'
        hd_ids = ['hd_id1', 'hd_id2']
        update_status_mock = mock.MagicMock()
        cb.update_hosting_device_status = update_status_mock
        cb.report_non_responding_hosting_devices(ctx, host, hd_ids)
        update_status_mock.assert_called_once_with(
            ctx, host, {const.HD_DEAD: hd_ids})

    def test_report_for_duty_triggers_scheduling(self):
        dm_plugin = mock.MagicMock()
        cb = devices_cfgagent_rpc_cb.DeviceMgrCfgRpcCallback(dm_plugin)
        ctx = mock.MagicMock()
        host = 'some_host'
        cb.register_for_duty(ctx, host)
        dm_plugin.auto_schedule_hosting_devices.assert_called_once_with(ctx,
                                                                        host)

    def _test_update_hosting_device_status(self, status_info):
        dm_plugin = mock.MagicMock()
        cb = devices_cfgagent_rpc_cb.DeviceMgrCfgRpcCallback(dm_plugin)
        ctx = mock.MagicMock()
        host = 'some_host'
        cb.update_hosting_device_status(ctx, host, status_info)
        non_resp_calls = []
        for status, hd_ids in six.iteritems(status_info):
            hd_spec = {'hosting_device': {'status': status}}
            update_calls = [mock.call(ctx, hd_id, hd_spec)
                            for hd_id in hd_ids]
            dm_plugin.update_hosting_device.assert_has_calls(update_calls,
                                                             any_order=True)

            if status == const.HD_DEAD or status == const.HD_ERROR:
                non_resp_calls.append(mock.call(ctx, host, hd_ids))
        dm_plugin.handle_non_responding_hosting_devices.has_calls(
            non_resp_calls, any_order=True)
        self.assertEqual(
            len(non_resp_calls),
            dm_plugin.handle_non_responding_hosting_devices.call_count)

    def test_update_hosting_device_status_to_dead(self):
        self._test_update_hosting_device_status(
            {const.HD_DEAD: ['hd_id1', 'hd_id2']})

    def test_update_hosting_device_status_to_active(self):
        self._test_update_hosting_device_status(
            {const.HD_ACTIVE: ['hd_id1', 'hd_id2']})

    def test_update_hosting_device_status_to_error(self):
        self._test_update_hosting_device_status(
            {const.HD_ERROR: ['hd_id1', 'hd_id2']})

    def test_update_hosting_device_status_to_not_responding(self):
        self._test_update_hosting_device_status(
            {const.HD_NOT_RESPONDING: ['hd_id1', 'hd_id2']})

    def test_update_hosting_device_status_multiple(self):
        self._test_update_hosting_device_status(
            {const.HD_ACTIVE: ['hd_id1', 'hd_id2'],
             const.HD_NOT_RESPONDING: ['hd_id3', 'hd_id4']})

    def test_update_hosting_device_status_all(self):
        self._test_update_hosting_device_status(
            {const.HD_ACTIVE: ['hd_id1', 'hd_id2'],
             const.HD_NOT_RESPONDING: ['hd_id3', 'hd_id4', 'hd_id5'],
             const.HD_DEAD: ['hd_id6'],
             const.HD_ERROR: ['hd_id7', 'hd_id8']})
