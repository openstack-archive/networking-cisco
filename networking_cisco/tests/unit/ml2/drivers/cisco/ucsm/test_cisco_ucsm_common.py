# Copyright 2015 Cisco Systems, Inc.
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_config import cfg

from networking_cisco.backwards_compatibility import ml2_config  # noqa
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import (config as
    ucsm_config)
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import constants as const
from networking_cisco.tests import base as nc_base

from neutron.common import config as neutron_config

from neutron.tests import base


UCSM_IP_ADDRESS_1 = '1.1.1.1'
UCSM_USERNAME_1 = 'username1'
UCSM_PASSWORD_1 = 'password1'
UCSM_VIRTIO_ETH_PORTS_1 = ['eth0, eth1']
UCSM_HOST_LIST_1 = ['UCS-1:UCS-1-SP, UCS-2:org-root/test/ls-UCS-2-SP']

UCSM_IP_ADDRESS_2 = '2.2.2.2'
UCSM_USERNAME_2 = 'username2'
UCSM_PASSWORD_2 = 'password2'
UCSM_VIRTIO_ETH_PORTS_2 = ['eth2, eth3']

UCSM_PHY_NETS = ['test_physnet']


ucsm_test_config_file = """
[ml2_cisco_ucsm_ip:1.1.1.1]
ucsm_username=username1
ucsm_password=password1
ucsm_host_list=UCS-1:UCS-1-SP, UCS-2:org-root/test/ls-UCS-2-SP
ucsm_virtio_eth_ports=eth0, eth1
vnic_template_list=test-physnet:org-root:Test-VNIC,vnic2
sriov_qos_policy=Test

[ml2_cisco_ucsm_ip:2.2.2.2]
ucsm_username=username2
ucsm_password=password2
ucsm_virtio_eth_ports=eth2, eth3
vnic_template_list=physnet2:org-root/org-Test-Sub:Test

[sriov_multivlan_trunk]
test_network1=5, 7-9
test_network2=500-509, 700
"""

CONF = cfg.CONF


class ConfigMixin(object):

    """Mock config for UCSM driver."""

    mocked_parser = None

    def set_up_mocks(self):
        # Mock the configuration file
        CONF.reset()

        args = ['--config-file', base.etcdir('neutron.conf')]
        neutron_config.init(args=args)

        nc_base.load_config_file(ucsm_test_config_file)

        # Configure the ML2 mechanism drivers and network types
        ml2_opts = {
            'mechanism_drivers': ['cisco_ucsm'],
            'tenant_network_types': ['vlan'],
        }
        for opt, val in ml2_opts.items():
            ml2_config.cfg.CONF.set_override(opt, val, 'ml2')

        # Configure and test the Cisco UCS Manager mechanism driver
        config = ucsm_config.UcsmConfig()

        self.assertEqual(CONF.ml2_cisco_ucsm.ucsms['1.1.1.1'].ucsm_username,
                         UCSM_USERNAME_1)
        self.assertEqual(CONF.ml2_cisco_ucsm.ucsms['1.1.1.1'].ucsm_password,
                         UCSM_PASSWORD_1)

        self.assertEqual(CONF.ml2_cisco_ucsm.ucsms['2.2.2.2'].ucsm_username,
                         UCSM_USERNAME_2)
        self.assertEqual(CONF.ml2_cisco_ucsm.ucsms['2.2.2.2'].ucsm_password,
                         UCSM_PASSWORD_2)

        expected_sp_dict = {
            ('1.1.1.1', 'UCS-1'): ('org-root/ls-UCS-1-SP'),
            ('1.1.1.1', 'UCS-2'): ('org-root/test/ls-UCS-2-SP'),
        }
        self.assertEqual(expected_sp_dict, config.ucsm_sp_dict)

        self.assertEqual(config.get_vnic_template_for_ucsm_ip("1.1.1.1"),
                         [('org-root', 'Test-VNIC,vnic2')])

        self.assertEqual(
            config.get_vnic_template_for_physnet("1.1.1.1", "test-physnet"),
            ('org-root', 'Test-VNIC,vnic2'))

        self.assertEqual(
            config.get_vnic_template_for_physnet("2.2.2.2", "physnet2"),
            ('org-root/org-Test-Sub', 'Test'))

        self.assertTrue(config.is_vnic_template_configured())

        self.assertEqual(config.get_ucsm_eth_port_list('1.1.1.1'),
                         [const.ETH_PREFIX + 'eth0',
                          const.ETH_PREFIX + 'eth1'])

        self.assertEqual(config.get_ucsm_eth_port_list('2.2.2.2'),
                         [const.ETH_PREFIX + 'eth2',
                          const.ETH_PREFIX + 'eth3'])

        self.assertEqual(config.get_sriov_qos_policy('1.1.1.1'),
                         'Test')

        self.assertEqual(
            config.get_sriov_multivlan_trunk_config("test_network1"),
            [5, 7, 8, 9])

        self.assertEqual(
            config.get_sriov_multivlan_trunk_config("test_network2"),
            [500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 700])
