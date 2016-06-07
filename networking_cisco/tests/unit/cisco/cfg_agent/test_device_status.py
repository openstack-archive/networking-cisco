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
import sys

import datetime
import mock
from oslo_utils import uuidutils

sys.modules['ncclient'] = mock.MagicMock()
from networking_cisco.plugins.cisco.cfg_agent import device_status
from neutron.tests import base

import networking_cisco.plugins.cisco.common.cisco_constants as cc
_uuid = uuidutils.generate_uuid

TYPE_STRING = 'string'
TYPE_DATETIME = 'datetime'
NOW = 0
BOOT_TIME = 420
DEAD_TIME = 300
BELOW_BOOT_TIME = 100


def create_timestamp(seconds_from_now, type=TYPE_STRING):
    timedelta = datetime.timedelta(seconds=seconds_from_now)
    past_time = datetime.datetime.utcnow() - timedelta
    if type is TYPE_STRING:
        return past_time.strftime("%Y-%m-%dT%H:%M:%S.%f")
    if type is TYPE_DATETIME:
        return past_time


class TestHostingDevice(base.BaseTestCase):

    def setUp(self):
        super(TestHostingDevice, self).setUp()
        self.status = device_status.DeviceStatus()
        device_status._is_pingable = mock.MagicMock(return_value=True)

        self.hosting_device = {'id': 123,
                               'host_type': 'CSR1kv',
                               'management_ip_address': '10.0.0.1',
                               'port': '22',
                               'booting_time': 420}
        self.created_at_str = datetime.datetime.utcnow().strftime(
            "%Y-%m-%d %H:%M:%S")
        self.hosting_device['created_at'] = self.created_at_str

        # if is_pingable, then hd_state is 'Active'
        self.hosting_device['hd_state'] = cc.HD_ACTIVE
        self.router_id = _uuid()
        self.router = {id: self.router_id,
                       'hosting_device': self.hosting_device}

    def test_hosting_devices_object(self):
        self.assertEqual({}, self.status.backlog_hosting_devices)

    def test_is_hosting_device_reachable_positive(self):
        self.assertTrue(self.status.is_hosting_device_reachable(
            self.hosting_device))

    def test_is_hosting_device_reachable_positive_heartbeat_disabled(self):
        self.status.enable_heartbeat = False
        self.assertTrue(self.status.is_hosting_device_reachable(
            self.hosting_device))
        self.assertEqual(0, len(self.status.get_backlogged_hosting_devices()))

    def test_is_hosting_device_reachable_positive_heartbeat_enabled(self):
        self.status.enable_heartbeat = True
        self.assertTrue(self.status.is_hosting_device_reachable(
            self.hosting_device))
        self.assertEqual(1, len(self.status.get_backlogged_hosting_devices()))
        self.assertTrue(123 in self.status.get_backlogged_hosting_devices())
        self.assertEqual(self.status.backlog_hosting_devices[123]['hd'],
                         self.hosting_device)

    def test_is_hosting_device_reachable_negative(self):
        self.assertEqual(0, len(self.status.backlog_hosting_devices))
        self.hosting_device['created_at'] = self.created_at_str  # Back to str
        device_status._is_pingable.return_value = False
        self.hosting_device['hd_state'] = cc.HD_NOT_RESPONDING

        self.assertFalse(device_status._is_pingable('1.2.3.4'))
        self.assertFalse(self.status.is_hosting_device_reachable(
            self.hosting_device))
        self.assertEqual(1, len(self.status.get_backlogged_hosting_devices()))
        self.assertTrue(123 in self.status.get_backlogged_hosting_devices())
        self.assertEqual(self.status.backlog_hosting_devices[123]['hd'],
                         self.hosting_device)

    def test_is_hosting_device_reachable_negative_heartbeat_disabled(self):
        """
        Even if heartbeat is disabled, unreachable hosting device should
        still be backlogged
        """
        self.status.enable_heartbeat = False

        self.assertEqual(0, len(self.status.backlog_hosting_devices))
        self.hosting_device['created_at'] = self.created_at_str  # Back to str
        device_status._is_pingable.return_value = False
        self.hosting_device['hd_state'] = cc.HD_NOT_RESPONDING

        self.assertFalse(device_status._is_pingable('1.2.3.4'))
        self.assertFalse(self.status.is_hosting_device_reachable(
            self.hosting_device))
        self.assertEqual(1, len(self.status.get_backlogged_hosting_devices()))
        self.assertTrue(123 in self.status.get_backlogged_hosting_devices())
        self.assertEqual(self.status.backlog_hosting_devices[123]['hd'],
                         self.hosting_device)

    def test_test_is_hosting_device_reachable_negative_exisiting_hd(self):
        self.status.backlog_hosting_devices.clear()
        self.status.backlog_hosting_devices[123] = {'hd': self.hosting_device}

        self.assertEqual(1, len(self.status.backlog_hosting_devices))
        self.assertEqual(True, self.status.is_hosting_device_reachable(
            self.hosting_device))
        self.assertEqual(1, len(self.status.get_backlogged_hosting_devices()))
        self.assertTrue(123 in self.status.backlog_hosting_devices.keys())
        self.assertEqual(self.status.backlog_hosting_devices[123]['hd'],
                         self.hosting_device)

    def test_is_hosting_device_reachable_negative_dead_hd(self):
        self.status.backlog_hosting_devices.clear()
        self.hosting_device['hd_state'] = cc.HD_DEAD
        self.status.backlog_hosting_devices = {
            self.hosting_device['id']: {'hd': self.hosting_device}
        }
        self.assertEqual(False, self.status.is_hosting_device_reachable(
                self.hosting_device))
        self.hosting_device['hd_state'] = cc.HD_ACTIVE
        self.status.backlog_hosting_devices.clear()


class TestBacklogHostingDevice(base.BaseTestCase):
    """
    This test class covers test cases pertaining to hosting device backlog
    handling in the DeviceStatus class.  The "backlog" represents a set
    of hosting-devices that should be monitored for liveness and is used
    to retry router update scenarios and for heartbeat / device syncing.
    """

    def setUp(self):
        super(TestBacklogHostingDevice, self).setUp()

        self.status = device_status.DeviceStatus()
        device_status._is_pingable = mock.MagicMock(return_value=True)

        self.hosting_device = {'id': 123,
                               'host_type': 'CSR1kv',
                               'management_ip_address': '10.0.0.1',
                               'port': '22',
                               'booting_time': 420}
        self.created_at_str = datetime.datetime.utcnow().strftime(
            "%Y-%m-%d %H:%M:%S")
        self.hosting_device['created_at'] = self.created_at_str

        # if is_pingable, then hd_state is 'Active'
        self.hosting_device['hd_state'] = cc.HD_ACTIVE
        self.router_id = _uuid()
        self.router = {id: self.router_id,
                       'hosting_device': self.hosting_device}

        # mock out drv_mgr
        self.drv_mgr = mock.MagicMock()
        self.drv_mock = mock.MagicMock()
        self.drv_mock.send_empty_cfg = mock.MagicMock()
        self.drv_mgr.get_driver_for_hosting_device.return_value = self.drv_mock

    def test_check_backlog_empty(self):

        expected = {'reachable': [],
                    'revived': [],
                    'dead': []}
        self.assertEqual(expected,
                         self.status.check_backlogged_hosting_devices(
                                                                 self.drv_mgr))
        self.assertEqual(0, self.drv_mock.send_empty_cfg.call_count)

    def test_check_backlog_below_booting_time(self):
        expected = {'reachable': [],
                    'revived': [],
                    'dead': []}

        self.hosting_device['created_at'] = create_timestamp(NOW)
        hd = self.hosting_device
        hd_id = hd['id']
        hd['hd_state'] = cc.HD_NOT_RESPONDING
        self.status.backlog_hosting_devices[hd_id] = {
            'hd': hd,
            'routers': [self.router_id]}
        self.assertEqual(expected,
                    self.status.check_backlogged_hosting_devices(self.drv_mgr))
        self.assertEqual(0, self.drv_mock.send_empty_cfg.call_count)

        #Simulate 20 seconds before boot time finishes
        self.hosting_device['created_at'] = create_timestamp(BOOT_TIME - 20)
        self.assertEqual(expected,
                    self.status.check_backlogged_hosting_devices(self.drv_mgr))
        self.assertEqual(0, self.drv_mock.send_empty_cfg.call_count)

        #Simulate 1 second before boot time
        self.hosting_device['created_at'] = create_timestamp(BOOT_TIME - 1)
        self.assertEqual(expected,
                    self.status.check_backlogged_hosting_devices(self.drv_mgr))

    def test_check_backlog_above_booting_time_pingable(self):
        """Test for backlog processing after booting.

        Simulates a hosting device which has passed the created time.
        The device should now be pingable.
        """
        self.hosting_device['created_at'] = create_timestamp(BOOT_TIME + 10)
        hd = self.hosting_device
        hd_id = hd['id']
        device_status._is_pingable.return_value = True
        # assumption in this scenario was that reachability to the
        # hosting-device was unknown
        hd['hd_state'] = cc.HD_NOT_RESPONDING
        self.status.backlog_hosting_devices[hd_id] = {
            'hd': hd,
            'routers': [self.router_id]}
        expected = {'reachable': [hd_id],
                    'revived': [],
                    'dead': []}
        self.assertEqual(expected,
                    self.status.check_backlogged_hosting_devices(self.drv_mgr))
        self.assertEqual(0, self.drv_mgr.call_count)

    def test_check_backlog_above_BT_not_pingable_below_deadtime(self):
        """Test for backlog processing in dead time interval.

        This test simulates a hosting device which has passed the created
        time but less than the 'declared dead' time.
        Hosting device is still not pingable.
        """
        hd = self.hosting_device
        hd['created_at'] = create_timestamp(BOOT_TIME + 10)
        #Inserted in backlog now
        hd['backlog_insertion_ts'] = create_timestamp(NOW, type=TYPE_DATETIME)
        hd_id = hd['id']
        device_status._is_pingable.return_value = False
        hd['hd_state'] = cc.HD_NOT_RESPONDING
        self.status.backlog_hosting_devices[hd_id] = {
            'hd': hd,
            'routers': [self.router_id]}
        expected = {'reachable': [],
                    'revived': [],
                    'dead': []}
        self.assertEqual(expected,
                    self.status.check_backlogged_hosting_devices(self.drv_mgr))
        self.assertEqual(0, self.drv_mock.send_empty_cfg.call_count)

    def test_check_backlog_above_BT_not_pingable_aboveDeadTime(self):
        """Test for backlog processing after dead time interval.

        This test simulates a hosting device which has passed the
        created time but greater than the 'declared dead' time.
        Hosting device is still not pingable.
        """
        hd = self.hosting_device
        hd['created_at'] = create_timestamp(BOOT_TIME + DEAD_TIME + 10)
        #Inserted in backlog 5 seconds after booting time
        hd['backlog_insertion_ts'] = create_timestamp(BOOT_TIME + 5,
                                                      type=TYPE_DATETIME)

        hd_id = hd['id']
        device_status._is_pingable.return_value = False
        hd['hd_state'] = cc.HD_NOT_RESPONDING
        self.status.backlog_hosting_devices[hd_id] = {
            'hd': hd,
            'routers': [self.router_id]}
        expected = {'reachable': [],
                    'revived': [],
                    'dead': [hd_id]}
        self.assertEqual(expected,
                    self.status.check_backlogged_hosting_devices(self.drv_mgr))
        self.assertEqual(0, self.drv_mock.send_empty_cfg.call_count)
        post_hd_state = (
            self.status.backlog_hosting_devices[hd_id]['hd']['hd_state'])
        self.assertEqual(cc.HD_DEAD, post_hd_state)

    def test_check_backlog_above_BT_revived_hosting_device(self):
        """
        Test reviving a hosting device after it's been deemed dead

        This test simulates a hosting device which has died is now
        reachable again.
        """
        hd = self.hosting_device
        hd['created_at'] = create_timestamp(BOOT_TIME + DEAD_TIME + 10)
        hd['backlog_insertion_ts'] = create_timestamp(BOOT_TIME + 5,
                                                      type=TYPE_DATETIME)
        hd_id = hd['id']
        device_status._is_pingable.return_value = False
        hd['hd_state'] = cc.HD_NOT_RESPONDING
        self.status.backlog_hosting_devices[hd_id] = {
            'hd': hd,
            'routers': [self.router_id]}
        expected = {'reachable': [],
                    'revived': [],
                    'dead': [hd_id]}
        self.assertEqual(expected,
                    self.status.check_backlogged_hosting_devices(self.drv_mgr))
        self.assertEqual(0, self.drv_mock.send_empty_cfg.call_count)

        post_hd_state = (
            self.status.backlog_hosting_devices[hd_id]['hd']['hd_state'])
        self.assertEqual(cc.HD_DEAD, post_hd_state)

        # now simulate that the hosting device is resurrected
        self.assertEqual(1, len(self.status.get_backlogged_hosting_devices()))
        device_status._is_pingable.return_value = True

        expected = {'reachable': [],
                    'revived': [hd_id],
                    'dead': []}
        self.assertEqual(expected,
                    self.status.check_backlogged_hosting_devices(self.drv_mgr))
        self.assertEqual(1, self.drv_mock.send_empty_cfg.call_count)

        post_hd_state = (
            self.status.backlog_hosting_devices[hd_id]['hd']['hd_state'])
        self.assertEqual(cc.HD_ACTIVE, post_hd_state)

    def test_check_backlog_above_BT_reachable_hosting_device(self):
        """
        Test reviving a hosting device after it's been deemed
        unresponsive and then becomes pingable before it's deemed
        dead.
        """
        hd = self.hosting_device
        hd['created_at'] = create_timestamp(BOOT_TIME + DEAD_TIME + 10)
        hd['backlog_insertion_ts'] = create_timestamp(BOOT_TIME + 5,
                                                      type=TYPE_DATETIME)
        hd_id = hd['id']
        device_status._is_pingable.return_value = True
        hd['hd_state'] = cc.HD_NOT_RESPONDING
        self.status.backlog_hosting_devices[hd_id] = {
            'hd': hd,
            'routers': [self.router_id]}

        expected = {'reachable': [hd_id],
                    'revived': [],
                    'dead': []}
        self.assertEqual(expected,
                    self.status.check_backlogged_hosting_devices(self.drv_mgr))
        self.assertEqual(0, self.drv_mock.send_empty_cfg.call_count)

        post_hd_state = (
            self.status.backlog_hosting_devices[hd_id]['hd']['hd_state'])
        self.assertEqual(cc.HD_ACTIVE, post_hd_state)
