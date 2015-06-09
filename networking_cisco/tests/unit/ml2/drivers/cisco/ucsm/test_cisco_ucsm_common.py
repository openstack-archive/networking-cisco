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

from neutron.common import config as neutron_config
from neutron.plugins.ml2 import config as ml2_config
from neutron.tests import base

from networking_cisco.plugins.ml2.drivers.cisco.ucsm import config

UCSM_IP_ADDRESS = '1.1.1.1'
UCSM_USERNAME = 'username'
UCSM_PASSWORD = 'password'
UCSM_PHY_NETS = ['test_physnet']
HOST_CONFIG1 = ['Hostname1:Service_profile1']


class ConfigMixin(object):

    """Mock config for UCSM driver."""

    mocked_parser = None

    def set_up_mocks(self):
        # Mock the configuration file

        args = ['--config-file', base.etcdir('neutron.conf')]
        neutron_config.init(args=args)

        # Configure the ML2 mechanism drivers and network types
        ml2_opts = {
            'mechanism_drivers': ['cisco_ucsm'],
            'tenant_network_types': ['vlan'],
        }
        for opt, val in ml2_opts.items():
            ml2_config.cfg.CONF.set_override(opt, val, 'ml2')

        # Configure the Cisco UCS Manager mechanism driver
        ucsm_test_config = {
            'ucsm_ip': UCSM_IP_ADDRESS,
            'ucsm_username': UCSM_USERNAME,
            'ucsm_password': UCSM_PASSWORD,
            'ucsm_host_list': HOST_CONFIG1,
        }

        for opt, val in ucsm_test_config.items():
            config.cfg.CONF.set_override(opt, val, 'ml2_cisco_ucsm')
