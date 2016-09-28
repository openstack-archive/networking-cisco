# Copyright (c) 2013-2016 Cisco Systems, Inc.
# All Rights Reserved.
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

import collections
import mock
from oslo_config import cfg
import six

from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_network_driver)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import exceptions
from networking_cisco.plugins.ml2.drivers.cisco.nexus import nexus_db_v2

from networking_cisco.tests.unit.ml2.drivers.cisco.nexus import (
    test_cisco_nexus_base)

from neutron.plugins.common import constants as p_const

CONNECT_ERROR = 'Unable to connect to Nexus'


class TestCiscoNexusDeviceConfig(object):

    """Unit tests for Cisco ML2 Nexus device driver."""

    test_configs = {
        'test_config1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_1,
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
                test_cisco_nexus_base.HOST_NAME_2,
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
                test_cisco_nexus_base.HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_2,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config4':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_8,
                test_cisco_nexus_base.HOST_NAME_4,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config5':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_8,
                test_cisco_nexus_base.HOST_NAME_5,
                test_cisco_nexus_base.NEXUS_PORT_2,
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
                test_cisco_nexus_base.HOST_NAME_PC,
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
                test_cisco_nexus_base.HOST_NAME_DUAL,
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
                test_cisco_nexus_base.HOST_NAME_1,
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
                test_cisco_nexus_base.HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_ROUTER_HA_INTF,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config_portchannel2':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_6,
                test_cisco_nexus_base.HOST_NAME_3,
                test_cisco_nexus_base.NEXUS_PORTCHANNELS,
                test_cisco_nexus_base.INSTANCE_PC,
                test_cisco_nexus_base.VLAN_ID_PC,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config_portchannel3':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_7,
                test_cisco_nexus_base.HOST_NAME_3,
                test_cisco_nexus_base.NEXUS_PORTCHANNELS,
                test_cisco_nexus_base.INSTANCE_PC,
                test_cisco_nexus_base.VLAN_ID_PC,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_config_migrate':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_6,
                test_cisco_nexus_base.NEXUS_PORT_2,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
    }

    test_configs = collections.OrderedDict(sorted(test_configs.items()))

    # The following contains desired Nexus output for some basic config above.
    duplicate_add_port_driver_result = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 267)])

    duplicate_delete_port_driver_result = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 267),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(267)])


class TestCiscoNexusDevice(test_cisco_nexus_base.TestCiscoNexusBase,
                           TestCiscoNexusDeviceConfig):

    """Unit tests for Cisco ML2 Nexus device driver."""

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusDevice, self).setUp()
        self.mock_ncclient.reset_mock()

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
        self.assertEqual(2, len(bindings))

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

    def test_create_delete_duplicate_port_transaction(self):
        """Tests creation and deletion same port transaction."""

        self._basic_create_verify_port_vlan(
            'test_config1',
            self.duplicate_add_port_driver_result)

        self.assertEqual(
            1, len(nexus_db_v2.get_nexusport_switch_bindings(
                   test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)))

        self._create_port(
            self.test_configs['test_config1'])
        self._verify_results(self.duplicate_add_port_driver_result)

        self.assertEqual(
            1, len(nexus_db_v2.get_nexusport_switch_bindings(
                   test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)))

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_config1',
            self.duplicate_delete_port_driver_result,
            nbr_of_bindings=0)

        self._basic_delete_verify_port_vlan(
            'test_config1',
            self.duplicate_delete_port_driver_result)

    def test_create_delete_same_switch_diff_hosts_diff_vlan(self):
        """Test create/delete two Ports, same switch/diff host & vlan."""

        add_port2_driver_result = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN.format(265),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/20', 265)])
        delete_port2_driver_result = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/20', 265),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(265)])

        self._basic_create_verify_port_vlan(
            'test_config1',
            self.duplicate_add_port_driver_result)

        self._create_port(
            self.test_configs['test_config2'])
        self._verify_results(add_port2_driver_result)

        # Verify there are 2 port configs
        bindings = nexus_db_v2.get_nexusport_switch_bindings(
                       test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)
        self.assertEqual(2, len(bindings))

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_config2',
            delete_port2_driver_result,
            nbr_of_bindings=1)

        self._basic_delete_verify_port_vlan(
            'test_config1',
            self.duplicate_delete_port_driver_result)

    def test_create_delete_same_switch_diff_hosts_same_vlan(self):
        """Test create/delete two Ports, same switch & vlan/diff host."""

        add_port2_driver_result = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/20', 267)])
        delete_port2_driver_result = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/20', 267)])

        self._basic_create_verify_port_vlan(
            'test_config4',
            self.duplicate_add_port_driver_result)

        self._create_port(
            self.test_configs['test_config5'])
        self._verify_results(add_port2_driver_result)

        # Verify there are 2 port configs
        bindings = nexus_db_v2.get_nexusport_switch_bindings(
                       test_cisco_nexus_base.NEXUS_IP_ADDRESS_8)
        self.assertEqual(2, len(bindings))

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_config5',
            delete_port2_driver_result,
            nbr_of_bindings=1)

        self._basic_delete_verify_port_vlan(
            'test_config4',
            self.duplicate_delete_port_driver_result)

    def test_create_delete_diff_switch_same_host(self):
        """Test create/delete of two Ports, diff switch/same host."""

        add_port2_driver_result = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN.format(268),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('portchannel', '2', 268),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format(268),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('portchannel', '2', 268)])
        delete_port2_driver_result = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('portchannel', '2', 268),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(268),
            test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('portchannel', '2', 268),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(268)])

        self._basic_create_verify_port_vlan(
            'test_config_portchannel2',
            add_port2_driver_result)

        # Verify there are 2 port configs. One per switch.
        bindings = nexus_db_v2.get_nexusport_switch_bindings(
                       test_cisco_nexus_base.NEXUS_IP_ADDRESS_6)
        self.assertEqual(1, len(bindings))
        bindings = nexus_db_v2.get_nexusport_switch_bindings(
                       test_cisco_nexus_base.NEXUS_IP_ADDRESS_7)
        self.assertEqual(1, len(bindings))

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        # For results, pass empty list to verify no nexus action on
        # first port removal.
        self._basic_delete_verify_port_vlan(
            'test_config_portchannel2',
            delete_port2_driver_result)

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
        self.assertEqual(1, self.mock_ncclient.connect.call_count)

    def test_ncclient_fail_on_connect_other_exceptions(self):
        """Test that other errors during connect() sequences are still handled.

        If the old ncclient is installed, we expect to get a TypeError first,
        but should still handle other errors in the usual way, whether they
        appear on the first or second call to connect().
        """

        # Clear connect_call_count
        self.mock_ncclient.reset_mock()

        err_strings = ['This is TypeError',
                       'This is IOError',
                       'This is AttributeError']
        except_errors = [TypeError(err_strings[0]),
                        IOError(err_strings[1]),
                        AttributeError(err_strings[2])]
        call_count = 0
        for errors in except_errors:
            config = {'connect.side_effect': errors}
            self.mock_ncclient.configure_mock(**config)
            port_context = self._generate_port_context(
                self.test_configs['test_config1'])

            e = self.assertRaises(
                exceptions.NexusConnectFailed,
                self._cisco_mech_driver.create_port_postcommit,
                port_context)
            self.assertIn(
                "Create Failed: Port event can not "
                "be processed at this time.", six.u(str(e)))

            self._cisco_mech_driver.update_port_precommit(port_context)
            e = self.assertRaises(
                exceptions.NexusConnectFailed,
                self._cisco_mech_driver.update_port_postcommit,
                port_context)
            self.assertIn(err_strings[call_count], six.u(str(e)))

            self._cisco_mech_driver.delete_port_precommit(port_context)
            e = self.assertRaises(
                exceptions.NexusConnectFailed,
                self._cisco_mech_driver.delete_port_postcommit,
                port_context)
            self.assertIn(err_strings[call_count], six.u(str(e)))

            call_count += 1
            self.assertEqual(
                call_count * 3,
                self.mock_ncclient.connect.call_count)

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
        self.assertEqual(1, self.mock_ncclient.connect.call_count)

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
        self.assertEqual(2, self.mock_ncclient.connect.call_count)

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

    def test_nexus_host_not_configured(self):
        """Test handling of a host not found in our configuration.

        If a host is not found in the cisco configuration the driver
        should silently ignore (unknown host name is logged) and no database
        or switch configuration is performed. Exercise against all APIs.
        """

        test_func_list = [
            self._cisco_mech_driver.create_port_postcommit,
            self._cisco_mech_driver.update_port_precommit,
            self._cisco_mech_driver.update_port_postcommit,
            self._cisco_mech_driver.delete_port_precommit,
            self._cisco_mech_driver.delete_port_postcommit,
        ]

        self.mock_ncclient.reset_mock()
        port_context = self._generate_port_context(
            self.test_configs['test_config1'],
            override_host_name='no_host')

        for test_func in test_func_list:
            test_func(port_context)
            self.assertRaises(
                 exceptions.NexusPortBindingNotFound,
                 nexus_db_v2.get_nexusport_switch_bindings,
                 test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)
            assert not self.mock_ncclient.connect.called

    def test_nexus_invalid_segment(self):
        """Test handling of a non VLAN segment.

        Pass a FLAT segment type into the driver. Verify that no
        exceptions are raised (non-VLAN segments are logged only) and
        that no database or switch configuration is performed.
        """

        test_func_list = [
            self._cisco_mech_driver.create_port_postcommit,
            self._cisco_mech_driver.update_port_precommit,
            self._cisco_mech_driver.update_port_postcommit,
        ]

        network_context = test_cisco_nexus_base.FakeNetworkContext(
            0, p_const.TYPE_FLAT)
        port_config = self.test_configs['test_config1']
        port_context = test_cisco_nexus_base.FakePortContext(
            port_config.instance_id,
            port_config.host_name,
            port_config.device_owner,
            network_context, None,
            port_config.profile,
            port_config.vnic_type
        )

        # Clear out call_count changes during initialization activity
        self.mock_ncclient.reset_mock()
        for test_func in test_func_list:
            test_func(port_context)
            self.assertRaises(
                 exceptions.NexusPortBindingNotFound,
                 nexus_db_v2.get_nexusport_switch_bindings,
                 test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)
            assert not self.mock_ncclient.connect.called

    def test_nexus_missing_fields(self):
        """Test handling of a NexusMissingRequiredFields exception.

        Test the Cisco NexusMissingRequiredFields exception by using
        empty device_id value during port creation.
        """

        local_test_configs = {
            'test_config1':
                test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                    test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                    test_cisco_nexus_base.HOST_NAME_1,
                    test_cisco_nexus_base.NEXUS_PORT_1,
                    '',
                    test_cisco_nexus_base.VLAN_ID_1,
                    test_cisco_nexus_base.NO_VXLAN_ID,
                    None,
                    test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                    {},
                    test_cisco_nexus_base.NORMAL_VNIC),
        }

        # Clear out call_count changes during initialization activity
        self.mock_ncclient.reset_mock()
        self.assertRaises(
            exceptions.NexusMissingRequiredFields,
            self._create_port,
            local_test_configs['test_config1'])

    def test_nexus_segment_none(self):
        """Test handling of segment is None.

        Verify that None segments do not throw an exception in
        _port_action_xxx. None segments passed to the event handlers are
        logged and are not processed.
        """

        network_context = test_cisco_nexus_base.FakeNetworkContext(
            0, p_const.TYPE_VLAN)
        network_context._network_segments = None
        port_config = self.test_configs['test_config1']
        port_context = test_cisco_nexus_base.FakePortContext(
            port_config.instance_id,
            port_config.host_name,
            port_config.device_owner,
            network_context, None,
            port_config.profile,
            port_config.vnic_type
        )
        test_func_list = [
            self._cisco_mech_driver.update_port_precommit,
            self._cisco_mech_driver.update_port_postcommit,
        ]

        # Clear out call_count changes during initialization activity
        self.mock_ncclient.reset_mock()
        for test_func in test_func_list:
            test_func(port_context)
            self.assertRaises(
                 exceptions.NexusPortBindingNotFound,
                 nexus_db_v2.get_nexusport_switch_bindings,
                 test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)
            assert not self.mock_ncclient.connect.called

    def test_nexus_ncclient_disconnect(self):
        """Test handling of closing ncclient sessions.

        When multi neutron-server processes are used verify that ncclient
        close_session method is called.
        """

        # Mock to keep track of number of close_session calls.
        ncclient_close = mock.patch.object(
            nexus_network_driver.CiscoNexusDriver,
            '_close_session').start()

        # Clear out call_count changes during initialization activity
        self.mock_ncclient.reset_mock()

        # Verify that ncclient is not closed by default.
        self._basic_create_verify_port_vlan(
            'test_config1',
            self.duplicate_add_port_driver_result)
        assert not ncclient_close.called

        self._basic_delete_verify_port_vlan(
            'test_config1',
            self.duplicate_delete_port_driver_result)

        # Patch to close ncclient session.
        mock.patch.object(nexus_network_driver.CiscoNexusDriver,
                          '_get_close_ssh_session',
                          return_value=True).start()

        # Verify that ncclient close is called twice. Once for
        # get_nexus_type during create_port_postcommit(). Then
        # It is suppressed for successful create VLAN but called
        # after trunk interface calls.
        self._basic_create_verify_port_vlan(
            'test_config1',
            self.duplicate_add_port_driver_result)
        self.assertEqual(2, ncclient_close.call_count)

    def test_nexus_extended_vlan_range_failure(self):
        """Test that extended VLAN range config errors are ignored.

        Some versions of Nexus switch do not allow state changes for
        the extended VLAN range (1006-4094), but these errors can be
        ignored (default values are appropriate). Test that such errors
        are ignored by the Nexus plugin.
        """

        self._create_port_valid_exception(
            'connect.return_value.edit_config.side_effect',
            'vlan vlan-id-create-delete 267',
            'test_config1',
            "Can't modify state for extended")

        # No reconnect attempted...call_count will be one
        self.assertEqual(1, self.mock_ncclient.connect.call_count)

        self._create_port_valid_exception(
            'connect.return_value.edit_config.side_effect',
            'vlan vlan-id-create-delete 265',
            'test_config2',
            "Command is only allowed on VLAN")

        # No reconnect attempted...call_count will be 0 since reset_mock
        # is called in _create_port_valid_exception and caching enabled
        self.assertEqual(0, self.mock_ncclient.connect.call_count)

    def test_nexus_vm_migration(self):
        """Verify VM (live) migration.

        Simulate the following:
        Nova informs neutron of live-migration with port-update(new host).
        This should trigger two update_port_pre/postcommit() calls.

        The first one should only change the current host_id and remove the
        binding resulting in the mechanism drivers receiving:
          PortContext.original['binding:host_id']: previous value
          PortContext.original_top_bound_segment: previous value
          PortContext.current['binding:host_id']: current (new) value
          PortContext.top_bound_segment: None

        The second one binds the new host resulting in the mechanism
        drivers receiving:
          PortContext.original['binding:host_id']: previous value
          PortContext.original_top_bound_segment: None
          PortContext.current['binding:host_id']: previous value
          PortContext.top_bound_segment: new value
        """
        migrate_add_host2_driver_result = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/20', 267)])

        self._basic_create_verify_port_vlan(
            'test_config1',
            self.duplicate_add_port_driver_result)
        binding = nexus_db_v2.get_nexusvm_bindings(
            test_cisco_nexus_base.VLAN_ID_1,
            test_cisco_nexus_base.INSTANCE_1)[0]
        self.assertEqual(
            test_cisco_nexus_base.NEXUS_PORT_1,
            binding.port_id)

        port_context = self._generate_port_context(
            self.test_configs['test_config_migrate'],
            unbind_port=True)
        port_cfg = self.test_configs['test_config1']
        port_context.set_orig_port(
            port_cfg.instance_id,
            port_cfg.host_name,
            port_cfg.device_owner,
            port_cfg.profile,
            port_cfg.vnic_type,
            test_cisco_nexus_base.NETID)

        self._cisco_mech_driver.create_port_postcommit(port_context)
        self._cisco_mech_driver.update_port_precommit(port_context)
        self._cisco_mech_driver.update_port_postcommit(port_context)

        # Verify that port entry has been deleted.
        self.assertRaises(
            exceptions.NexusPortBindingNotFound,
            nexus_db_v2.get_nexusvm_bindings,
            test_cisco_nexus_base.VLAN_ID_1,
            test_cisco_nexus_base.INSTANCE_1)

        # Clean all the ncclient mock_calls to clear exception
        # and other mock_call history.
        self.mock_ncclient.reset_mock()

        self._basic_create_verify_port_vlan(
            'test_config_migrate',
            migrate_add_host2_driver_result)

        # Verify that port entry has been added using new host name.
        # Use port_id to verify that 2nd host name was used.
        binding = nexus_db_v2.get_nexusvm_bindings(
            test_cisco_nexus_base.VLAN_ID_1,
            test_cisco_nexus_base.INSTANCE_1)[0]
        self.assertEqual(
            test_cisco_nexus_base.NEXUS_PORT_2,
            binding.port_id)


class TestCiscoNexusDeviceInit(test_cisco_nexus_base.TestCiscoNexusBase,
                               TestCiscoNexusDeviceConfig):
    """Verifies interface vlan allowed none is set when missing."""

    def _mock_init(self):
        # Prevent default which returns
        # 'switchport trunk allowed vlan none'
        # in get interface calls so Nexus driver
        # initialization will send it to Nexus device.
        data_xml = {'connect.return_value.get.return_value.data_xml':
                    ''}
        self.mock_ncclient.configure_mock(**data_xml)

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusDeviceInit, self).setUp()

    def test_verify_initialization(self):

        # set 1 - switch 1.1.1.1 sets eth 1/10 & 1/20 to None
        # set 2 - switch 8.8.8.8 sets eth 1/10 & 1/20 to None
        # set 3 - switch 4.4.4.4 sets eth 1/3 & portchannel 2 to None
        # set 4 - switch 2.2.2.2 sets portchannel 2 to None
        # set 5 - switch 6.6.6.6 sets portchannel 2 to None
        # set 6 - switch 7.7.7.7 sets portchannel 2 to None
        duplicate_init_port_driver_result1 = (
            [test_cisco_nexus_base.RESULT_INTERFACE.
                format('ethernet', '1\/10', 'None'),
            test_cisco_nexus_base.RESULT_INTERFACE.
                format('ethernet', '1\/10', 'None'),
            test_cisco_nexus_base.RESULT_INTERFACE.
                format('ethernet', '1\/3', 'None'),
            test_cisco_nexus_base.RESULT_INTERFACE.
                format('portchannel', '2', 'None'),
            test_cisco_nexus_base.RESULT_INTERFACE.
                format('portchannel', '2', 'None'),
            test_cisco_nexus_base.RESULT_INTERFACE.
                format('portchannel', '2', 'None')])

        # Only one entry to match for last 3 so make None
        # so count matches in _verify_results
        duplicate_init_port_driver_result2 = (
            [test_cisco_nexus_base.RESULT_INTERFACE.
                format('ethernet', '1\/20', 'None'),
            test_cisco_nexus_base.RESULT_INTERFACE.
                format('ethernet', '1\/20', 'None'),
            test_cisco_nexus_base.RESULT_INTERFACE.
                format('portchannel', '2', 'None'),
            None,
            None,
            None])

        self._verify_results(duplicate_init_port_driver_result1)
        self._verify_results(duplicate_init_port_driver_result2)


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

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusBaremetalDevice, self).setUp()

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


class TestCiscoNexusNonCacheSshDevice(
    test_cisco_nexus_base.TestCiscoNexusBase):

    """Unit tests for Cisco ML2 Nexus device driver in non-cache ssh mode."""

    # Testing new default of True for config var 'never_cache_ssh_connection'

    test_configs = {
        'test_config1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_1,
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
