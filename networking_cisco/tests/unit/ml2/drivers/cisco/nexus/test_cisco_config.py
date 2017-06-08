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

import mock
from oslo_config import cfg

from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    config as cisco_config)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_helpers as nexus_help)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import nexus_db_v2

from neutron.tests.unit import testlib_api


class TestCiscoNexusPluginConfig(testlib_api.SqlTestCase):

    def setUp(self):
        self.config_parse()
        super(TestCiscoNexusPluginConfig, self).setUp()

    def test_config_parse_error(self):
        """Check that config error is raised upon config parser failure."""
        with mock.patch.object(cfg, 'MultiConfigParser') as parser:
            parser.return_value.read.return_value = []
            self.assertRaises(cfg.Error, cisco_config.ML2MechCiscoConfig)

    def test_create_device_dictionary(self):
        """Test creation of the device dictionary based on nexus config."""
        test_config = {
            'ml2_mech_cisco_nexus:1.1.1.1': {
                'username': ['admin'],
                'password': ['mySecretPassword'],
                'ssh_port': [22],
                'compute1': ['1/1'],
                'compute2': ['1/2'],
                'compute5': ['1/3,1/4']
            },
            'ml2_mech_cisco_nexus:2.2.2.2': {
                'username': ['admin'],
                'password': ['mySecretPassword'],
                'ssh_port': [22],
                'compute3': ['1/1'],
                'compute4': ['1/2'],
                'compute5': ['portchannel:20,portchannel:30']
            },
        }
        expected_dev_dict = {
            ('1.1.1.1', 'username'): 'admin',
            ('1.1.1.1', 'password'): 'mySecretPassword',
            ('1.1.1.1', 'ssh_port'): 22,
            ('2.2.2.2', 'username'): 'admin',
            ('2.2.2.2', 'password'): 'mySecretPassword',
            ('2.2.2.2', 'ssh_port'): 22,
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

        with mock.patch.object(cfg, 'MultiConfigParser') as parser:
            parser.return_value.read.return_value = cfg.CONF.config_file
            parser.return_value.parsed = [test_config]
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
