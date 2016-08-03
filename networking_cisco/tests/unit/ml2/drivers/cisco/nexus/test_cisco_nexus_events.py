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

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusDevice, self).setUp()

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
        self.assertEqual(2, self.mock_ncclient.connect.call_count)
        self.assertEqual(1,
            self.mock_ncclient.connect.return_value.
            close_session.call_count)


class TestCiscoNexusNonCacheSshDevice(
    test_cisco_nexus_base.TestCiscoNexusBase):

    """Unit tests for Cisco ML2 Nexus device driver in non-cache ssh mode."""

    # Testing new default of True for config var 'never_cache_ssh_connection'

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
    }

    simple_add_port_ethernet_driver_result = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 267)])

    simple_delete_port_ethernet_driver_result = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 267),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(267)])

    def test_create_delete_basic(self):
        """Basic creation and deletion test of 1 ethernet port."""

        # Clean all the ncclient mock_calls so we can evaluate
        # results of add operation.
        self.mock_ncclient.reset_mock()

        # Call _create_port directly without verification
        # We know at this point that this works.
        self._create_port(self.test_configs['test_config1'])

        # The objective is to verify call count when caching disabled
        self.assertEqual(2, self.mock_ncclient.connect.call_count)
        self.assertEqual(2,
            self.mock_ncclient.connect.return_value.
            close_session.call_count)

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        # nbr_of_bindings includes reserved port binding
        self._delete_port(self.test_configs['test_config1'])

        self.assertEqual(2, self.mock_ncclient.connect.call_count)
        self.assertEqual(2,
            self.mock_ncclient.connect.return_value.
            close_session.call_count)

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

        # With ssh handle not patched, there will be 3 connects
        # and 3 closes.
        # 1) Full connect during create_port get nexus type call
        #    and close after this call.
        # 2) Full connect during update_port on first failed
        #    create_vlan, then close on error. Driver then
        #    loops back and performs a full reconnect on
        #    successful send of create_vlan.
        #    The close operation is skipped following this.
        # 3) When interface configuration is sent, a close
        #    is then perform to complete this transaction set.
        self.assertEqual(3, self.mock_ncclient.connect.call_count)
        self.assertEqual(3,
            self.mock_ncclient.connect.return_value.
            close_session.call_count)
