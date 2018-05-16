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

from neutron.tests.unit import testlib_api

from networking_cisco.tests import base as nc_base

from networking_cisco.ml2_drivers.nexus import config  # noqa

cfg.CONF.import_group("ml2_cisco", "networking_cisco.ml2_drivers.nexus.config")

test_config_file = """
[ml2_mech_cisco_nexus:1.1.1.1]
username=admin
password=mySecretPassword
nve_src_intf=2
physnet=physnet1
vpc_pool=5,10
intfcfg_portchannel=user cmd1;user cmd2
https_local_certificate=/path/to/your/local-certificate-file.crt
host_ports_mapping=compute1:[1/1],
                   compute2:[1/2],
                   compute5:[1/3, 1/4]


[ml2_mech_cisco_nexus:2.2.2.2]
username=admin
password=mySecretPassword
https_verify=False
host_ports_mapping=compute3:[1/1],
                   compute4:[1/2],
                   compute5:[port-channel:20,port-channel:30]
"""

# Assign non-boolean to https_verify for error test
test_error_config_file = """
[ml2_mech_cisco_nexus:1.1.1.1]
username=admin
password=mySecretPassword
nve_src_intf=2
physnet=physnet1
https_verify='abc'
compute1=1/1
"""

dict_mapping_config_file = """
[ml2_mech_cisco_nexus:1.1.1.1]
username=admin
password=mySecretPassword
nve_src_intf=2
physnet=physnet1
host_ports_mapping=compute1:[1/1],
                   compute2:[1/2],
                   compute3:[1/3, port-channel30]
"""


class TestCiscoNexusPluginConfigBase(testlib_api.SqlTestCase):

    def setUp(self):
        super(TestCiscoNexusPluginConfigBase, self).setUp()
        cfg.CONF.clear()


class TestCiscoNexusPluginConfig(TestCiscoNexusPluginConfigBase):

    def test_config_using_subsection_option(self):
        nc_base.load_config_file(test_config_file)
        expected = {
            '1.1.1.1': {
                'username': 'admin',
                'password': 'mySecretPassword',
                'nve_src_intf': '2',
                'physnet': 'physnet1',
                'vpc_pool': '5,10',
                'intfcfg_portchannel': 'user cmd1;user cmd2',
                'https_verify': True,
                'https_local_certificate': (
                    '/path/to/your/local-certificate-file.crt'),
                'host_ports_mapping': {
                    'compute1': ['1/1'],
                    'compute2': ['1/2'],
                    'compute5': ['1/3', '1/4']
                }
            }, '2.2.2.2': {
                'username': 'admin',
                'password': 'mySecretPassword',
                'physnet': None,
                'nve_src_intf': None,
                'vpc_pool': None,
                'intfcfg_portchannel': None,
                'https_verify': False,
                'https_local_certificate': None,
                'host_ports_mapping': {
                    'compute3': ['1/1'],
                    'compute4': ['1/2'],
                    'compute5': ['port-channel:20', 'port-channel:30']
                }
            }
        }

        for switch_ip, options in expected.items():
            for opt_name, option in options.items():
                self.assertEqual(
                    option, cfg.CONF.ml2_cisco.nexus_switches.get(
                        switch_ip).get(opt_name))

    def test_create_device_error(self):
        """Test error during create of the Nexus device dictionary."""
        nc_base.load_config_file(test_error_config_file)

        e = self.assertRaises(cfg.ConfigFileValueError,
            cfg.CONF.ml2_cisco.nexus_switches.get('1.1.1.1').get,
            "https_verify")
        x = six.u(str(e))
        self.assertIn("Value for option https_verify is not valid: "
                      "Unexpected boolean value 'abc'", x)

    def test_dict_host_port_mapping(self):
        nc_base.load_config_file(dict_mapping_config_file)
        """Test host_ports_mapping dictionary works."""
        expected = {
            '1.1.1.1': {
                'username': 'admin',
                'password': 'mySecretPassword',
                'host_ports_mapping': {
                    'compute1': ['1/1'],
                    'compute2': ['1/2'],
                    'compute3': ['1/3', 'port-channel30']
                }
            }
        }

        for switch_ip, options in expected.items():
            for opt_name, option in options.items():
                self.assertEqual(
                    option, cfg.CONF.ml2_cisco.nexus_switches.get(
                        switch_ip).get(opt_name))
