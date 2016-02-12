# Copyright (c) 2013 OpenStack Foundation.
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

from networking_cisco.plugins.ml2.drivers.cisco.nexus import exceptions
from networking_cisco.plugins.ml2.drivers.cisco.nexus import nexus_db_v2

from networking_cisco.tests.unit.ml2.drivers.cisco.nexus import (
    test_cisco_nexus_base)

CONNECT_ERROR = 'Unable to connect to Nexus'

HOST_NAME_1 = 'testhost1'
HOST_NAME_2 = 'testhost2'
HOST_NAME_PC = 'testpchost'
HOST_NAME_DUAL = 'testdualhost'


class TestCiscoNexusDevice(test_cisco_nexus_base.TestCiscoNexusBase):

    """Unit tests for Cisco ML2 Nexus device driver."""

    test_configs = {
        'test_config1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config2':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                HOST_NAME_2,
                test_cisco_nexus_base.NEXUS_PORT_2,
                test_cisco_nexus_base.INSTANCE_2,
                test_cisco_nexus_base.VLAN_ID_2,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config3':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_2,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config_portchannel':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_2,
                HOST_NAME_PC,
                test_cisco_nexus_base.NEXUS_PORTCHANNELS,
                test_cisco_nexus_base.INSTANCE_PC,
                test_cisco_nexus_base.VLAN_ID_PC,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config_dual':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_DUAL,
                HOST_NAME_DUAL,
                test_cisco_nexus_base.NEXUS_DUAL,
                test_cisco_nexus_base.INSTANCE_DUAL,
                test_cisco_nexus_base.VLAN_ID_DUAL,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config_dhcp':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_DHCP,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config_router_ha_intf':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_ROUTER_HA_INTF,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_vxlan_config1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.VXLAN_ID,
                test_cisco_nexus_base.MCAST_GROUP,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
    }

    duplicate_add_port_driver_result = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 267)])

    duplicate_delete_port_driver_result = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 267),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(267)])

    def test_create_delete_duplicate_ports(self):
        """Tests creation and deletion of two new virtual Ports."""

        self._basic_create_verify_port_vlan(
            'test_config1',
            self.duplicate_add_port_driver_result)

        self._create_port(
            self.test_configs['test_config3'])
        # TODO(caboucha)
        # Commented out until the correct fix for
        # the following issue is resolved.
        # https://review.openstack.org/#/c/241216/
        #
        # verify first config was indeed configured
        # Original code was as follows:
        # self._verify_results(duplicate_add_port_driver_result)

        # Verify there are 2 port configs
        bindings = nexus_db_v2.get_nexusvlan_binding(
                       test_cisco_nexus_base.VLAN_ID_1,
                       test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)
        self.assertEqual(len(bindings), 2)

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        # For results, pass empty list to verify no nexus action on
        # first port removal.
        self._basic_delete_verify_port_vlan(
            'test_config1',
            [], nbr_of_bindings=1)

        self._basic_delete_verify_port_vlan(
            'test_config3',
            self.duplicate_delete_port_driver_result)

    def test_create_delete_portchannel(self):
        """Tests creation of a port over a portchannel."""

        duplicate_add_port_driver_result = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN.format(268),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('portchannel', '2', 268)])

        duplicate_delete_port_driver_result = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('portchannel', '2', 268),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(268)])

        self._create_delete_port(
            'test_config_portchannel',
            duplicate_add_port_driver_result,
            duplicate_delete_port_driver_result)

    def test_create_delete_dual(self):
        """Tests creation and deletion of dual ports for single server"""

        duplicate_add_port_driver_result = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN.format(269),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/3', 269),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format(269),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('portchannel', '2', 269)])

        duplicate_delete_port_driver_result = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/3', 269),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(269),
            test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('portchannel', '2', 269)])

        self._basic_create_verify_port_vlan(
            'test_config_dual',
            duplicate_add_port_driver_result,
            nbr_of_bindings=2)

        self._basic_delete_verify_port_vlan(
            'test_config_dual',
            duplicate_delete_port_driver_result)

    def test_create_delete_dhcp(self):
        """Tests creation and deletion of ports with device_owner of dhcp."""

        self._create_delete_port(
            'test_config_dhcp',
            self.duplicate_add_port_driver_result,
            self.duplicate_delete_port_driver_result)

    def test_create_delete_router_ha_intf(self):
        """Tests creation and deletion of ports with device_owner
        of router_ha_interface.
        """

        self._create_delete_port(
            'test_config_router_ha_intf',
            self.duplicate_add_port_driver_result,
            self.duplicate_delete_port_driver_result)

    def test_connect_failure(self):
        """Verifies exception handling during ncclient connect. """

        # Clean all the ncclient mock_calls to clear exception
        # and other mock_call history.
        self.mock_ncclient.reset_mock()

        config = {'connect.side_effect': Exception(CONNECT_ERROR)}
        self.mock_ncclient.configure_mock(**config)

        e = self.assertRaises(exceptions.NexusConnectFailed,
                              self._create_port,
                              self.test_configs[
                                  'test_config1'])
        self.assertIn(CONNECT_ERROR, six.u(str(e)))
        self.assertEqual(self.mock_ncclient.connect.call_count, 1)

    def test_get_nexus_type_failure(self):
        """Verifies exception during ncclient get inventory. """

        self._create_port_failure(
            'connect.return_value.get.side_effect',
            'show inventory',
            'test_config1',
            'Create Failed:',
            which_exc=exceptions.NexusConnectFailed)

        # Verify we attempt to connect once. get_nexus_type is a
        # special case since replay code will retry
        self.assertEqual(self.mock_ncclient.connect.call_count, 1)

    def test_enable_vxlan_feature_failure(self):
        """Verifies exception during enable VXLAN driver. """

        # Set configuration variable to add/delete the VXLAN global nexus
        # switch values.
        cfg.CONF.set_override('vxlan_global_config', True, 'ml2_cisco')
        self._create_port_failure(
            'connect.return_value.edit_config.side_effect',
            'feature nv overlay vn-segment-vlan-based',
            'test_vxlan_config1',
            __name__)

    def test_disable_vxlan_feature_failure(self):
        """Verifies exception during disable VXLAN driver. """

        # Set configuration variable to add/delete the VXLAN global nexus
        # switch values.
        cfg.CONF.set_override('vxlan_global_config', True, 'ml2_cisco')
        self._delete_port_failure(
            'connect.return_value.edit_config.side_effect',
            'no feature nv overlay vn-segment-vlan-based',
            'test_vxlan_config1',
            __name__)

    def test_create_nve_member_failure(self):
        """Verifies exception during create nve member driver. """

        self._create_port_failure(
            'connect.return_value.edit_config.side_effect',
            'member vni mcast-group',
            'test_vxlan_config1',
            __name__)

    def test_delete_nve_member_failure(self):
        """Verifies exception during delete nve member driver. """

        self._delete_port_failure(
            'connect.return_value.edit_config.side_effect',
            'no member vni',
            'test_vxlan_config1',
            __name__)

    def test_create_vlan_failure(self):
        """Verifies exception during edit vlan create driver. """

        self._create_port_failure(
            'connect.return_value.edit_config.side_effect',
            'vlan vlan-id-create-delete 267',
            'test_config1',
            __name__)

        # Verify we attempt to connect twice. First when first
        # create_vlan fails then _edit_config loops to attempt
        # it again and it fails again.
        self.assertEqual(self.mock_ncclient.connect.call_count, 2)

    def test_delete_vlan_failure(self):
        """Verifies exception during edit vlan delete driver. """

        self._delete_port_failure(
            'connect.return_value.edit_config.side_effect',
            'vlan-id-create-delete no vlan 267',
            'test_config1',
            __name__)

    def test_create_trunk_failure(self):
        """Verifies exception during create trunk interface driver. """

        self._create_port_failure(
            'connect.return_value.edit_config.side_effect',
            'switchport trunk allowed vlan_id 267',
            'test_config1',
            __name__)

    def test_delete_trunk_failure(self):
        """Verifies exception during delete trunk interface driver. """

        self._delete_port_failure(
            'connect.return_value.edit_config.side_effect',
            'switchport trunk allowed remove vlan 267',
            'test_config1',
            __name__)

    def test_edit_fail_on_try_1(self):
        """Verifies reconnect during ncclient edit. """

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        config = {'connect.return_value.edit_config.side_effect':
                  self._config_side_effects_on_count(
                      'vlan vlan-id-create-delete 267',
                      Exception(__name__), range(1))}
        self.mock_ncclient.configure_mock(**config)

        self._create_port(self.test_configs['test_config1'])

        # Verify we connected twice. Connect attempt 1 occurs on
        # any first driver call.  Then create-vlan fails first
        # time resulting close of stale handle. Driver
        # loops around to try and reopen and create-vlan should
        # then be successful on the 2nd pass.
        self.assertEqual(self.mock_ncclient.connect.call_count, 2)


class TestCiscoNexusBaremetalDevice(test_cisco_nexus_base.TestCiscoNexusBase):

    """Unit tests for Cisco ML2 Nexus baremetal device driver."""

    baremetal_profile = {
        "local_link_information": [
            {
                "port_id": test_cisco_nexus_base.NEXUS_BAREMETAL_PORT_1,
                "switch_info": {
                    "is_native": False,
                    "switch_ip": test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                },
            },
        ]
    }

    baremetal_profile_is_native = {
        "local_link_information": [
            {
                "port_id": test_cisco_nexus_base.NEXUS_BAREMETAL_PORT_1,
                "switch_info": {
                    "is_native": True,
                    "switch_ip": test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                },
            },
        ]
    }

    # The IP Address and Nexus Port information is duplicated in case
    # of baremetal.  The core code uses content of baremetal_profile
    # While test code continues to use values in test_config
    # for verification. This keeps test code simpler.
    test_configs = {
        'test_config1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_UNUSED,
                test_cisco_nexus_base.NEXUS_BAREMETAL_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_BAREMETAL,
                baremetal_profile,
                test_cisco_nexus_base.BAREMETAL_VNIC),
        'test_config_native':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_UNUSED,
                test_cisco_nexus_base.NEXUS_BAREMETAL_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_2,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_BAREMETAL,
                baremetal_profile_is_native,
                test_cisco_nexus_base.BAREMETAL_VNIC),
    }

    simple_add_port_ethernet_driver_result = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 267)])

    simple_delete_port_ethernet_driver_result = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 267),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(267)])

    simple_add_port_channel_driver_result = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('port-channel', '469', 267)])

    simple_delete_port_channel_driver_result = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('port-channel', '469', 267),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(267)])

    simple_add_port_ethernet_native_driver_result = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(265),
        (test_cisco_nexus_base.RESULT_ADD_NATIVE_INTERFACE.
            format('ethernet', '1\/10', 265) +
        '[\x00-\x7f]+' +
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 265))])

    simple_delete_port_ethernet_native_driver_result = (
        [(test_cisco_nexus_base.RESULT_DEL_NATIVE_INTERFACE.
            format('ethernet', '1\/10') +
        '[\x00-\x7f]+' +
        test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 265)),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(265)])

    def test_create_delete_basic_ethernet_port(self):
        """Basic creation and deletion test of 1 ethernet port."""

        # nbr_of_bindings includes reserved port binding
        self._basic_create_verify_port_vlan(
            'test_config1',
            self.simple_add_port_ethernet_driver_result, 2)

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        # nbr_of_bindings includes reserved port binding
        self._basic_delete_verify_port_vlan(
            'test_config1',
            self.simple_delete_port_ethernet_driver_result,
            nbr_of_bindings=1)

    def test_create_delete_basic_port_channel(self):
        """Basic creation and deletion test of 1 port-channel."""

        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.
        data_xml = {'connect.return_value.get.return_value.data_xml':
                    'switchport trunk allowed vlan none\n'
                    'channel-group 469 mode active'}
        self.mock_ncclient.configure_mock(**data_xml)

        # nbr_of_bindings includes reserved port binding
        self._basic_create_verify_port_vlan(
            'test_config1',
            self.simple_add_port_channel_driver_result, 2)

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        # nbr_of_bindings includes reserved port binding
        self._basic_delete_verify_port_vlan(
            'test_config1',
            self.simple_delete_port_channel_driver_result,
            nbr_of_bindings=1)

    def test_create_delete_basic_eth_port_is_native(self):
        """Basic creation and deletion test of 1 ethernet port."""

        # nbr_of_bindings includes reserved port binding
        self._basic_create_verify_port_vlan(
            'test_config_native',
            self.simple_add_port_ethernet_native_driver_result, 2)

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        # nbr_of_bindings includes reserved port binding
        self._basic_delete_verify_port_vlan(
            'test_config_native',
            self.simple_delete_port_ethernet_native_driver_result,
            nbr_of_bindings=1)

    def test_create_delete_switch_ip_not_defined(self):
        """Create/delete of 1 ethernet port switchinfo is string."""

        baremetal_profile_no_switch_ip = {
            "local_link_information": [
                # This IP is configured at init time
                {
                    "port_id": test_cisco_nexus_base.NEXUS_BAREMETAL_PORT_1,
                    "switch_info": {
                        "is_native": False,
                        "switch_ip": "1.1.1.1",
                    },
                },
                # This IP not configured at init time
                {
                    "port_id": test_cisco_nexus_base.NEXUS_BAREMETAL_PORT_1,
                    "switch_info": {
                        "is_native": False,
                        "switch_ip": "6.6.6.6",
                    },
                },
            ]
        }

        local_test_configs = {
            'test_config1':
                test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                    test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                    test_cisco_nexus_base.HOST_NAME_UNUSED,
                    test_cisco_nexus_base.NEXUS_BAREMETAL_PORT_1,
                    test_cisco_nexus_base.INSTANCE_1,
                    test_cisco_nexus_base.VLAN_ID_1,
                    test_cisco_nexus_base.NO_VXLAN_ID,
                    None,
                    test_cisco_nexus_base.DEVICE_OWNER_BAREMETAL,
                    baremetal_profile_no_switch_ip,
                    test_cisco_nexus_base.BAREMETAL_VNIC),
        }

        # nbr_of_bindings includes reserved port binding
        self._basic_create_verify_port_vlan(
            '',
            self.simple_add_port_ethernet_driver_result, 2,
            other_test=local_test_configs['test_config1'])

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        # nbr_of_bindings includes reserved port binding
        self._basic_delete_verify_port_vlan(
            '',
            self.simple_delete_port_ethernet_driver_result,
            nbr_of_bindings=1,
            other_test=local_test_configs['test_config1'])
