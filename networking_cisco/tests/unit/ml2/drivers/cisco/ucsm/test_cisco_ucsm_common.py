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
[ml2_cisco_ucsm]
supported_pci_devs=thing1:thing2, thing1:thing3
ucsm_https_verify=False

ucsm_ip=3.3.3.3
ucsm_username=username3
ucsm_password=password3
ucsm_host_list=UCS-3:UCS-3-SP

sriov_qos_policy=Global

[ml2_cisco_ucsm_ip:1.1.1.1]
ucsm_username=username1
ucsm_password=password1
ucsm_host_list=UCS-1:UCS-1-SP, UCS-2:org-root/test/ls-UCS-2-SP
ucsm_virtio_eth_ports=eth4, eth5
vnic_template_list=test-physnet:org-root:Test-VNIC,vnic2
sriov_qos_policy=Test

[ml2_cisco_ucsm_ip:2.2.2.2]
ucsm_username=username2
ucsm_password=password2
ucsm_virtio_eth_ports=eth2, eth3
vnic_template_list=physnet2:org-root/org-Test-Sub:Test
sp_template_list=SP_Template1_path:SP_Template1:S1,S2 \
                 SP_Template2_path:SP_Template2:S3,S4
sriov_qos_policy=

[ml2_cisco_ucsm_ip:4.4.4.4]
ucsm_username=username4
ucsm_password=password4

[sriov_multivlan_trunk]
test_network1=5, 7-9
test_network2=500-509, 700
"""

ucsm_config_bad_pci_devs = """
[ml2_cisco_ucsm]
supported_pci_devs=thing:thing, thing2, thing3:thing4
"""

CONF = cfg.CONF


class UCSMConfigTestCase(nc_base.TestCase):

    def setUp(self):
        super(UCSMConfigTestCase, self).setUp()
        CONF.reset()
        nc_base.load_config_file(ucsm_test_config_file)
        self.config = ucsm_config.UcsmConfig()

    def test_oslo_config_configuration_loading(self):
        expected_config_data = {
            "ucsm_https_verify": False,
            "ucsm_ip": "3.3.3.3",
            "ucsm_username": "username3",
            "ucsm_password": "password3",
            "supported_pci_devs": ["thing1:thing2", "thing1:thing3"],
            "ucsm_host_list": {"UCS-3": "UCS-3-SP"},
            "ucsm_virtio_eth_ports": [const.ETH_PREFIX + const.ETH0,
                                      const.ETH_PREFIX + const.ETH1],
            "sriov_qos_policy": 'Global',
            "vnic_template_list": {},
            "sp_template_list": {},
            "ucsms": {
                "1.1.1.1": {
                    "ucsm_username": "username1",
                    "ucsm_password": "password1",
                    "ucsm_virtio_eth_ports": [const.ETH_PREFIX + "eth4",
                                              const.ETH_PREFIX + "eth5"],
                    "ucsm_host_list": {"UCS-1": "UCS-1-SP",
                                       "UCS-2": "org-root/test/ls-UCS-2-SP"},
                    "sriov_qos_policy": "Test",
                    "vnic_template_list": {
                        "test-physnet": ucsm_config.UCSTemplate(
                            "org-root", "Test-VNIC,vnic2")},
                    "sp_template_list": {},
                },
                "2.2.2.2": {
                    "ucsm_username": "username2",
                    "ucsm_password": "password2",
                    "ucsm_virtio_eth_ports": [const.ETH_PREFIX + "eth2",
                                              const.ETH_PREFIX + "eth3"],
                    "ucsm_host_list": None,
                    "sriov_qos_policy": '',
                    "vnic_template_list": {
                        "physnet2": ucsm_config.UCSTemplate(
                            "org-root/org-Test-Sub", "Test")},
                    "sp_template_list": {
                        "S1": ucsm_config.UCSTemplate("SP_Template1_path",
                                                      "SP_Template1"),
                        "S2": ucsm_config.UCSTemplate("SP_Template1_path",
                                                      "SP_Template1"),
                        "S3": ucsm_config.UCSTemplate("SP_Template2_path",
                                                      "SP_Template2"),
                        "S4": ucsm_config.UCSTemplate("SP_Template2_path",
                                                      "SP_Template2"),
                    },
                },
                "3.3.3.3": {
                    "ucsm_username": "username3",
                    "ucsm_password": "password3",
                    "ucsm_virtio_eth_ports": [const.ETH_PREFIX + "eth0",
                                              const.ETH_PREFIX + "eth1"],
                    "ucsm_host_list": {"UCS-3": "UCS-3-SP"},
                    "sriov_qos_policy": 'Global',
                    "vnic_template_list": {},
                    "sp_template_list": {},
                },
                # 4.4.4.4 Test's if we've inherited sriov_qos_policy from the
                # main group
                "4.4.4.4": {
                    "ucsm_username": "username4",
                    "ucsm_password": "password4",
                    "ucsm_virtio_eth_ports": [const.ETH_PREFIX + "eth0",
                                              const.ETH_PREFIX + "eth1"],
                    "ucsm_host_list": None,
                    "sriov_qos_policy": 'Global',
                    "vnic_template_list": {},
                    "sp_template_list": {},
                }
            }
        }

        expected_sriov_multivlan = {
            "test_network1": [5, 7, 8, 9],
            "test_network2": [500, 501, 502, 503, 504, 505, 506, 507,
                              508, 509, 700]
        }

        # Convert nested oslo.config GroupAttrs to dict for comparision
        loaded_config = dict(CONF.ml2_cisco_ucsm)
        for ip, data in CONF.ml2_cisco_ucsm.ucsms.items():
            loaded_config['ucsms'][ip] = dict(data)

        # Test the ml2_cisco_ucsm group is what we expect
        self.assertEqual(expected_config_data, loaded_config)

        # Test the sriov multivlan group is what we expect
        self.assertEqual(expected_sriov_multivlan,
                         dict(CONF.sriov_multivlan_trunk.network_vlans))

    def test_sp_dict_configured_as_expected(self):
        expected_sp_dict = {
            ('1.1.1.1', 'UCS-1'): ('org-root/ls-UCS-1-SP'),
            ('1.1.1.1', 'UCS-2'): ('org-root/test/ls-UCS-2-SP'),
            ('3.3.3.3', 'UCS-3'): ('org-root/ls-UCS-3-SP'),
        }
        self.assertEqual(expected_sp_dict, self.config.ucsm_sp_dict)

    def _assert_sp_templates_in_start_state(self):
        self.assertEqual(
            CONF.ml2_cisco_ucsm.ucsms['1.1.1.1'].sp_template_list, {})
        self.assertEqual(
            CONF.ml2_cisco_ucsm.ucsms['2.2.2.2'].sp_template_list,
            {"S1": ucsm_config.UCSTemplate("SP_Template1_path",
                                           "SP_Template1"),
             "S2": ucsm_config.UCSTemplate("SP_Template1_path",
                                           "SP_Template1"),
             "S3": ucsm_config.UCSTemplate("SP_Template2_path",
                                           "SP_Template2"),
             "S4": ucsm_config.UCSTemplate("SP_Template2_path",
                                           "SP_Template2")})

    def _assert_sp_templates_in_end_state(self):
        self.assertEqual(
            CONF.ml2_cisco_ucsm.ucsms['1.1.1.1'].sp_template_list,
            {"S1": ucsm_config.UCSTemplate("SP_Template1_path",
                                          "SP_Template1")})
        self.assertEqual(
            CONF.ml2_cisco_ucsm.ucsms['2.2.2.2'].sp_template_list,
            {"S2": ucsm_config.UCSTemplate("SP_Template1_path",
                                           "SP_Template1"),
             "S3": ucsm_config.UCSTemplate("SP_Template2_path",
                                           "SP_Template2"),
             "S4": ucsm_config.UCSTemplate("SP_Template2_path",
                                           "SP_Template2")})

    def test_add_sp_template_config_for_host(self):
        self._assert_sp_templates_in_start_state()
        self.config.add_sp_template_config_for_host(
            'S1', '1.1.1.1', 'SP_Template1_path', 'SP_Template1')
        self._assert_sp_templates_in_end_state()

    def test_update_sp_template_config(self):
        self._assert_sp_templates_in_start_state()
        self.config.update_sp_template_config(
            'S1', '1.1.1.1', 'SP_Template1_path/SP_Template1')
        self._assert_sp_templates_in_end_state()

    def test_support_pci_devices_bad_format(self):
        CONF.reset()
        nc_base.load_config_file(ucsm_config_bad_pci_devs)
        self.assertRaises(ValueError, CONF.ml2_cisco_ucsm.get,
                          "supported_pci_devs")


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
        ucsm_config.UcsmConfig()
