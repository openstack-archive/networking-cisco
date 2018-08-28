# Copyright 2018 Cisco Systems, Inc.  All rights reserved.
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

from oslo_config import cfg

from neutron.tests.unit import testlib_api

from networking_cisco.plugins.cisco.device_manager import config
from networking_cisco.tests import base as nc_base


test_config_file = """
[cisco_hosting_device_template:1]
name = NetworkNode
enabled = True
host_category = Network_Node
service_types = router:FW:VPN
image =
flavor =
default_credentials_id = 1
configuration_mechanism =
protocol_port = 22
booting_time = 360
slot_capacity = 2000
desired_slots_free = 0
tenant_bound =
device_driver = networking_cisco.plugins.cisco.device_manager.hosting_device_drivers.noop_hd_driver.NoopHostingDeviceDriver
plugging_driver = networking_cisco.plugins.cisco.device_manager.plugging_drivers.noop_plugging_driver.NoopPluggingDriver

[cisco_hosting_device_template:3]
name = ASR1k
enabled = True
host_category = Hardware
service_types = router:FW:VPN
image =
flavor =
default_credentials_id = 1
configuration_mechanism =
protocol_port = 22
booting_time = 360
slot_capacity = 2000
desired_slots_free = 0
tenant_bound =
device_driver = networking_cisco.plugins.cisco.device_manager.hosting_device_drivers.noop_hd_driver.NoopHostingDeviceDriver
plugging_driver = networking_cisco.plugins.cisco.device_manager.plugging_drivers.hw_vlan_trunking_driver.HwVLANTrunkingPlugDriver

[cisco_router_type:1]
name = Namespace_Neutron_router
description = Neutron
template_id = 1
ha_enabled_by_default = False
shared = True
slot_need = 0
scheduler =
driver =
cfg_agent_service_helper =
cfg_agent_driver =

[cisco_router_type:3]
name = ASR1k_router
description = Neutron
template_id = 3
ha_enabled_by_default = True
shared = True
slot_need = 2
scheduler = networking_cisco.plugins.cisco.l3.schedulers.l3_router_hosting_device_scheduler.L3RouterHostingDeviceHARandomScheduler
driver = networking_cisco.plugins.cisco.l3.drivers.asr1k.asr1k_routertype_driver.ASR1kL3RouterDriver
cfg_agent_service_helper = networking_cisco.plugins.cisco.cfg_agent.service_helpers.routing_svc_helper.RoutingServiceHelper
cfg_agent_driver = networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k.asr1k_routing_driver.ASR1kRoutingDriver

[cisco_hosting_device_credential:1]
name = Universal
description = Credential1
user_name = admin
password = password1
type =

[cisco_hosting_device_credential:2]
name = Universal
description = Credential2
user_name = admin
password = password2
type =

[cisco_hosting_device:1]
template_id = 3
credentials_id = 1
device_id = SN:abcd1234efgh
admin_state_up = True
management_ip_address = 192.133.149.10
protocol_port = 22
tenant_bound =
auto_delete = False

[cisco_hosting_device:2]
template_id = 3
credentials_id = 2
device_id = SN:abcd1234efgh
admin_state_up = True
management_ip_address = 192.133.149.11
protocol_port = 22
tenant_bound =
auto_delete = False

[HwVLANTrunkingPlugDriver:1]
external_net_interface_1 = *:te0/1/0
internal_net_interface_1 = *:te0/1/0

[HwVLANTrunkingPlugDriver:2]
external_net_interface_1 = *:te0/1/0
internal_net_interface_1 = *:te0/1/0
"""  # noqa


class TestDeviceManagerConfig(testlib_api.SqlTestCase):

    def setUp(self):
        super(TestDeviceManagerConfig, self).setUp()
        cfg.CONF.clear()

    def test_obtain_hosting_device_credentials_from_config(self):
        nc_base.load_config_file(test_config_file)
        creds_dict = config.obtain_hosting_device_credentials_from_config()

        expected_config = {
            '00000000-0000-0000-0000-000000000001': {
                'name': 'Universal',
                'user_name': 'admin',
                'password': 'password1',
                'description': 'Credential1',
                'type': ''
            },
            '00000000-0000-0000-0000-000000000002': {
                'name': 'Universal',
                'user_name': 'admin',
                'password': 'password2',
                'description': 'Credential2',
                'type': ''
            }
        }

        self.assertEqual(expected_config, creds_dict)

    def test_cisco_hosting_devices(self):
        nc_base.load_config_file(test_config_file)
        devices = config.get_specific_config('cisco_hosting_device')

        expected_config = {
            '1': {
                'name': None,
                'description': None,
                'template_id': '3',
                'credentials_id': '1',
                'device_id': 'SN:abcd1234efgh',
                'admin_state_up': True,
                'management_ip_address': '192.133.149.10',
                'protocol_port': 22,
                'tenant_bound': '',
                'auto_delete': False,
            },
            '2': {
                'name': None,
                'description': None,
                'template_id': '3',
                'credentials_id': '2',
                'device_id': 'SN:abcd1234efgh',
                'admin_state_up': True,
                'management_ip_address': '192.133.149.11',
                'protocol_port': 22,
                'tenant_bound': '',
                'auto_delete': False,
            },
        }

        self.assertEqual(expected_config, devices)
