# Copyright (c) 2014-2016 Cisco Systems, Inc.
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo_config import cfg
import six

from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    config as cisco_config)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_helpers as nexus_help)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import nexus_db_v2

from neutron.tests.unit import testlib_api

from networking_cisco.tests import base as nc_base

test_config_file = """
[ml2_mech_cisco_nexus:1.1.1.1]
username=admin
password=mySecretPassword
ssh_port=22
nve_src_intf=2
physnet=physnet1
vpc_pool=5,10
intfcfg_portchannel=user cmd1;user cmd2
https_verify=True
https_local_certificate=/path/to/your/local-certificate-file.crt
compute1=1/1
compute2=1/2
compute5=1/3,1/4

[ml2_mech_cisco_nexus:2.2.2.2]
username=admin
password=mySecretPassword
ssh_port=22
compute3=1/1
compute4=1/2
compute5=portchannel:20,portchannel:30
"""

# Make sure intfcfg.portchannel still works
test_deprecate_config_file = """
[ml2_mech_cisco_nexus:1.1.1.1]
username=admin
password=mySecretPassword
ssh_port=22
nve_src_intf=2
physnet=physnet1
vpc_pool=5,10
intfcfg.portchannel=user cmd1;user cmd2
https_verify=True
https_local_certificate=/path/to/your/local-certificate-file.crt
compute1=1/1
compute2=1/2
compute5=1/3,1/4
"""

# Assign non-integer to ssh_port for error
test_error_config_file = """
[ml2_mech_cisco_nexus:1.1.1.1]
username=admin
password=mySecretPassword
ssh_port='abc'
nve_src_intf=2
physnet=physnet1
compute1=1/1
"""


class TestCiscoNexusPluginConfig(testlib_api.SqlTestCase):

    def setUp(self):
        super(TestCiscoNexusPluginConfig, self).setUp()
        nc_base.load_config_file(test_config_file)

    def test_create_device_dictionary(self):
        """Test creation of the device dictionary based on nexus config."""
        expected_dev_dict = {
            ('1.1.1.1', 'username'): 'admin',
            ('1.1.1.1', 'password'): 'mySecretPassword',
            ('1.1.1.1', 'ssh_port'): 22,
            ('1.1.1.1', 'nve_src_intf'): '2',
            ('1.1.1.1', 'physnet'): 'physnet1',
            ('1.1.1.1', 'vpc_pool'): '5,10',
            ('1.1.1.1', 'intfcfg_portchannel'): 'user cmd1 ;user cmd2',
            ('1.1.1.1', 'https_verify'): True,
            ('1.1.1.1', 'https_local_certificate'): (
                '/path/to/your/local-certificate-file.crt'),
            ('2.2.2.2', 'username'): 'admin',
            ('2.2.2.2', 'password'): 'mySecretPassword',
            ('2.2.2.2', 'ssh_port'): 22,
            ('2.2.2.2', 'https_verify'): False,
        }
        host_map_data = [
            ('compute1', '1.1.1.1', '1/1'),
            ('compute2', '1.1.1.1', '1/2'),
            ('compute3', '2.2.2.2', '1/1'),
            ('compute4', '2.2.2.2', '1/2'),
            ('compute5', '1.1.1.1', '1/3'),
            ('compute5', '1.1.1.1', '1/4'),
            ('compute5', '2.2.2.2', 'portchannel:20'),
            ('compute5', '2.2.2.2', 'portchannel:30')
        ]

        cisco_config.ML2MechCiscoConfig()
        self.assertEqual(expected_dev_dict,
                         cisco_config.ML2MechCiscoConfig.nexus_dict)

        mappings = nexus_db_v2.get_all_host_mappings()
        idx = 0
        maps_sorted = []
        for map in mappings:
            maps_sorted.append([map.host_id, map.switch_ip,
                                map.if_id, map.ch_grp, map.is_static])
        maps_sorted.sort()
        for map in maps_sorted:
            self.assertEqual(map[0], host_map_data[idx][0])
            self.assertEqual(map[1], host_map_data[idx][1])
            if_type, port = nexus_help.split_interface_name(
                host_map_data[idx][2])
            eth_name = nexus_help.format_interface_name(if_type, port)
            self.assertEqual(map[2], eth_name)
            self.assertEqual(map[3], 0)
            self.assertTrue(map[4])
            idx += 1

    def test_config_using_subsection_option(self):
        expected = {
            '1.1.1.1': {
                'username': 'admin',
                'password': 'mySecretPassword',
                'ssh_port': 22,
                'nve_src_intf': '2',
                'physnet': 'physnet1',
                'vpc_pool': '5,10',
                'intfcfg_portchannel': 'user cmd1;user cmd2',
                'https_verify': True,
                'https_local_certificate': (
                    '/path/to/your/local-certificate-file.crt'),
                'host_port_mapping': {
                    'compute1': '1/1',
                    'compute2': '1/2',
                    'compute5': '1/3,1/4'
                }
            }, '2.2.2.2': {
                'username': 'admin',
                'password': 'mySecretPassword',
                'ssh_port': 22,
                'physnet': None,
                'nve_src_intf': None,
                'vpc_pool': None,
                'intfcfg_portchannel': None,
                'https_verify': False,
                'https_local_certificate': None,
                'host_port_mapping': {
                    'compute3': '1/1',
                    'compute4': '1/2',
                    'compute5': 'portchannel:20,portchannel:30'
                }
            }
        }

        for switch_ip, options in expected.items():
            for opt_name, option in options.items():
                self.assertEqual(
                    option, cfg.CONF.ml2_cisco.nexus_switches.get(
                        switch_ip).get(opt_name))


class TestCiscoNexusPluginDeprecatedConfig(testlib_api.SqlTestCase):

    def setUp(self):
        super(TestCiscoNexusPluginDeprecatedConfig, self).setUp()
        nc_base.load_config_file(test_deprecate_config_file)

    def test_deprecated_intfcfg_portchannel(self):
        """Test creation deprecated intfcfg_portchannel works."""
        expected_dev_dict = {
            ('1.1.1.1', 'username'): 'admin',
            ('1.1.1.1', 'password'): 'mySecretPassword',
            ('1.1.1.1', 'ssh_port'): 22,
            ('1.1.1.1', 'nve_src_intf'): '2',
            ('1.1.1.1', 'physnet'): 'physnet1',
            ('1.1.1.1', 'vpc_pool'): '5,10',
            ('1.1.1.1', 'intfcfg_portchannel'): 'user cmd1 ;user cmd2',
            ('1.1.1.1', 'https_verify'): True,
            ('1.1.1.1', 'https_local_certificate'): (
                '/path/to/your/local-certificate-file.crt'),
        }

        cisco_config.ML2MechCiscoConfig()
        self.assertEqual(expected_dev_dict,
                         cisco_config.ML2MechCiscoConfig.nexus_dict)


class TestCiscoNexusPluginConfigError(testlib_api.SqlTestCase):

    def setUp(self):
        super(TestCiscoNexusPluginConfigError, self).setUp()
        nc_base.load_config_file(test_error_config_file)

    def test_create_device_error(self):
        """Test error during create of the Nexus device dictionary."""

        e = self.assertRaises(cfg.ConfigFileValueError,
                              cisco_config.ML2MechCiscoConfig)
        x = six.u(str(e))
        self.assertIn("Value for option ssh_port is not valid: "
                      "invalid literal for int() with base 10: "
                      "'abc'", x)
