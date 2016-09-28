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

import mock
from oslo_config import cfg

import networking_cisco.plugins
# we must import service_vm_lib to get a config option defined there
from networking_cisco.plugins.cisco.device_manager import service_vm_lib  # NOQA
from networking_cisco.plugins.cisco.device_manager.hosting_device_drivers\
    .csr1kv_hd_driver import CSR1kvHostingDeviceDriver

from neutron.tests import base


templates_path = (networking_cisco.plugins.__path__[0] +
                  '/cisco/device_manager/configdrive_templates')


class TestCSR1kvHostingDeviceDriver(base.BaseTestCase):

    def setUp(self):
        super(TestCSR1kvHostingDeviceDriver, self).setUp()

    def test_get_hosting_device_name(self):
        driver = CSR1kvHostingDeviceDriver()
        self.assertEqual(driver.hosting_device_name(), 'CSR1kv')

    def test_create_config(self):
        cfg.CONF.set_override('templates_path', templates_path, 'general')
        credentials_info = {'user_name': 'bob', 'password': 'tooEasy'}
        fake_mgmt_port = {'fixed_ips': [{'ip_address': '10.0.0.55'}]}
        connectivity_info = {'mgmt_port': fake_mgmt_port,
                             'netmask': '255.255.255.0',
                             'gateway_ip': '10.0.0.1',
                             'name_server_1': '8.8.8.8',
                             'name_server_2': '8.8.4.4'}
        driver = CSR1kvHostingDeviceDriver()
        context_mock = mock.MagicMock()
        res = driver.create_config(context_mock, credentials_info,
                                   connectivity_info)
        self.assertEqual(len(res), 1)
        self.assertIn('iosxe_config.txt', res)
        line_set = {item for item in res['iosxe_config.txt'].split('\n')}
        self.assertIn('username bob priv 15 secret tooEasy', line_set)
        self.assertIn(' ip address 10.0.0.55 255.255.255.0', line_set)
        self.assertIn('ip route 0.0.0.0 0.0.0.0 GigabitEthernet1 10.0.0.1',
                      line_set)
        self.assertIn('ip name-server 8.8.8.8', line_set)

    def test_create_config_template_not_found(self):
        cfg.CONF.set_override('templates_path', templates_path, 'general')
        cfg.CONF.set_override('csr1kv_configdrive_template', 'wrong_name.cfg',
                              'hosting_devices')
        credentials_info = {'user_name': 'bob', 'password': 'tooEasy'}
        fake_mgmt_port = {'fixed_ips': [{'ip_address': '10.0.0.55'}]}
        connectivity_info = {'mgmt_port': fake_mgmt_port,
                             'netmask': '255.255.255.0',
                             'gateway_ip': '10.0.0.1',
                             'name_server_1': '8.8.8.8',
                             'name_server_2': '8.8.4.4'}
        driver = CSR1kvHostingDeviceDriver()
        context_mock = mock.MagicMock()
        self.assertRaises(IOError, driver.create_config, context_mock,
                          credentials_info, connectivity_info)
