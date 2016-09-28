# Copyright (c) 2016 Cisco Systems, Inc.
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

from networking_cisco.plugins.ml2.drivers.cisco.nexus import exceptions
from networking_cisco.plugins.ml2.drivers.cisco.nexus import nexus_db_v2

from networking_cisco.tests.unit.ml2.drivers.cisco.nexus import (
    test_cisco_nexus_base)

from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import db as ml2_db
from neutron.plugins.ml2 import driver_api as api


class TestCiscoNexusVxlanDeviceConfig(object):
    """Config Data for Cisco ML2 VXLAN Nexus device driver."""

    test_configs = {
        'test_vxlan_config1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.VXLAN_ID,
                test_cisco_nexus_base.MCAST_GROUP,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_vxlan_config2':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_2,
                test_cisco_nexus_base.NEXUS_PORT_2,
                test_cisco_nexus_base.INSTANCE_2,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.VXLAN_ID,
                test_cisco_nexus_base.MCAST_GROUP,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_vxlan_config3':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_3,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.VXLAN_ID,
                test_cisco_nexus_base.MCAST_GROUP,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_vxlan_config4':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_2,
                test_cisco_nexus_base.HOST_NAME_3,
                test_cisco_nexus_base.NEXUS_DUAL_2,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.VXLAN_ID,
                test_cisco_nexus_base.MCAST_GROUP,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_vxlan_config5':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_4,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.VXLAN_ID,
                test_cisco_nexus_base.MCAST_GROUP,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_vxlan_config6':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_5,
                test_cisco_nexus_base.NEXUS_PORT_2,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_2,
                test_cisco_nexus_base.VXLAN_ID + 1,
                test_cisco_nexus_base.MCAST_GROUP,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
    }

    test_configs = collections.OrderedDict(sorted(test_configs.items()))

    # The following contains desired Nexus output for some basic config above.
    add_port_driver_result = (
        [test_cisco_nexus_base.RESULT_ADD_NVE_INTERFACE.
            format(1, 70000, '255.1.1.1'),
        test_cisco_nexus_base.RESULT_ADD_VLAN_VNI.
            format(267, 70000),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 267)])

    delete_port_driver_result = (
        [test_cisco_nexus_base.RESULT_DEL_NVE_INTERFACE.
            format(1, 70000, 267),
        test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 267),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(267)])


class TestCiscoNexusVxlanDevice(test_cisco_nexus_base.TestCiscoNexusBase,
                           TestCiscoNexusVxlanDeviceConfig):

    """Unit tests for Cisco ML2 VXLAN Nexus device driver."""

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusVxlanDevice, self).setUp()
        self.mock_ncclient.reset_mock()
        self.addCleanup(self._clear_nve_db)

    def _clear_nve_db(self):
        nexus_db_v2.remove_all_nexusnve_bindings()

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

    def test_nexus_vxlan_one_network_two_hosts(self):
        """Tests creation and deletion of two new virtual Ports."""

        add_port2_driver_result = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN_VNI.
                format(267, 70000),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/20', 267)])

        delete_port2_driver_result = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/20', 267)])

        self._basic_create_verify_port_vlan(
            'test_vxlan_config1',
            self.add_port_driver_result)

        self._create_port(
            self.test_configs['test_vxlan_config2'])
        self._verify_results(add_port2_driver_result)

        bindings = nexus_db_v2.get_nexusvlan_binding(
                       test_cisco_nexus_base.VLAN_ID_1,
                       test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)
        self.assertEqual(2, len(bindings))

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_vxlan_config2',
            delete_port2_driver_result, nbr_of_bindings=1)

        self._basic_delete_verify_port_vlan(
            'test_vxlan_config1',
            self.delete_port_driver_result)

    def test_nexus_missing_vxlan_fields(self):
        """Test handling of a VXLAN NexusMissingRequiredFields exception.

        Test the Cisco NexusMissingRequiredFields exception by using
        empty VNI and mcast address values during port update event.
        """
        local_test_configs = {
            'test_vxlan_config_no_vni':
                test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                    test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                    test_cisco_nexus_base.HOST_NAME_1,
                    test_cisco_nexus_base.NEXUS_PORT_1,
                    test_cisco_nexus_base.INSTANCE_1,
                    test_cisco_nexus_base.VLAN_ID_1,
                    None,
                    test_cisco_nexus_base.MCAST_GROUP,
                    test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                    {},
                    test_cisco_nexus_base.NORMAL_VNIC),
            'test_vxlan_config_no_mcast':
                test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                    test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                    test_cisco_nexus_base.HOST_NAME_1,
                    test_cisco_nexus_base.NEXUS_PORT_1,
                    test_cisco_nexus_base.INSTANCE_1,
                    test_cisco_nexus_base.VLAN_ID_1,
                    test_cisco_nexus_base.VXLAN_ID,
                    None,
                    test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                    {},
                    test_cisco_nexus_base.NORMAL_VNIC),
        }
        test_list = ('test_vxlan_config_no_vni',
                     'test_vxlan_config_no_mcast')
        for test_name in test_list:
            self.assertRaises(
                exceptions.NexusMissingRequiredFields,
                self._create_port,
                local_test_configs[test_name])

    def test_nexus_vxlan_bind_port(self):
        """Test VXLAN bind_port method processing.

        Verify the bind_port method allocates the VLAN segment correctly.
        """
        #TODO(rpothier) Add back in provider segment support.
        expected_dynamic_segment = {
            api.SEGMENTATION_ID: mock.ANY,
            #const.PROVIDER_SEGMENT: False,
            api.PHYSICAL_NETWORK: test_cisco_nexus_base.PHYSNET,
            api.ID: mock.ANY,
            api.NETWORK_TYPE: p_const.TYPE_VLAN}

        mock_get_dynamic_segment = mock.patch.object(ml2_db,
                                                'get_dynamic_segment').start()
        mock_get_dynamic_segment.return_value = expected_dynamic_segment

        self._bind_port(self.test_configs['test_vxlan_config1'])
        self.mock_continue_binding.assert_called_once_with(
            test_cisco_nexus_base.NETID,
            [expected_dynamic_segment])

    def test_nexus_vxlan_bind_port_no_physnet(self):
        """Test VXLAN bind_port error processing.

        Verify that continue_binding() method is not called when no 'physnet'
        key is present in the nexus switch dictionary.
        """

        self._cisco_mech_driver._nexus_switches.pop(
            (test_cisco_nexus_base.NEXUS_IP_ADDRESS_1, 'physnet'))

        try:
            self._bind_port(self.test_configs['test_vxlan_config1'])
        except exceptions.PhysnetNotConfigured:
            assert not self.mock_continue_binding.called

    def test_nexus_vxlan_bind_port_no_dynamic_segment(self):
        """Test VXLAN bind_port processing.

        Verify that the continue_binding() method is not called when the vlan
        dynamic segment wasn't allocated.
        """

        mock_get_dynamic_segment = mock.patch.object(ml2_db,
                                                'get_dynamic_segment').start()
        mock_get_dynamic_segment.return_value = None

        try:
            self._bind_port(self.test_configs['test_vxlan_config1'])
        except exceptions.NoDynamicSegmentAllocated:
            assert not self.mock_continue_binding.called

    def test_nexus_vxlan_one_network(self):
        """Test processing for creating one VXLAN segment."""

        add_port_driver_result3 = (
            [test_cisco_nexus_base.RESULT_ADD_NVE_INTERFACE.
                format(1, 70000, '255.1.1.1'),
            test_cisco_nexus_base.RESULT_ADD_NVE_INTERFACE.
                format(1, 70000, '255.1.1.1'),
            test_cisco_nexus_base.RESULT_ADD_VLAN_VNI.
                format(267, 70000),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/10', 267),
            test_cisco_nexus_base.RESULT_ADD_VLAN_VNI.
                format(267, 70000),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/2', 267),
            test_cisco_nexus_base.RESULT_ADD_VLAN_VNI.
                format(267, 70000),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/3', 267)])

        delete_port_driver_result3 = (
            [test_cisco_nexus_base.RESULT_DEL_NVE_INTERFACE.
                format(1, 70000, 267),
             test_cisco_nexus_base.RESULT_DEL_NVE_INTERFACE.
                format(1, 70000, 267),
            test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/10', 267),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(267),
            test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/2', 267),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(267),
            test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/3', 267)])

        # Since test_vxlan_config3 & test_vxlan_config4 share
        # the same host name they both get processed in the
        # next call.
        self._basic_create_verify_port_vlan(
            'test_vxlan_config3',
            add_port_driver_result3)

        for switch_ip, nbr_bind in [
            (test_cisco_nexus_base.NEXUS_IP_ADDRESS_1, 1),
            (test_cisco_nexus_base.NEXUS_IP_ADDRESS_2, 2)]:
            bindings = nexus_db_v2.get_nexusvlan_binding(
                           test_cisco_nexus_base.VLAN_ID_1,
                           switch_ip)
            self.assertEqual(nbr_bind, len(bindings))
            binding = nexus_db_v2.get_nve_switch_bindings(switch_ip)
            self.assertEqual(1, len(binding))

        # Since test_vxlan_config3 & test_vxlan_config4 share
        # the same host name they both get processed in the
        # next call.
        self._basic_delete_verify_port_vlan(
            'test_vxlan_config3',
            delete_port_driver_result3)

        for switch_ip in [
            test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
            test_cisco_nexus_base.NEXUS_IP_ADDRESS_2]:
            try:
                bindings = nexus_db_v2.get_nexusvlan_binding(
                               test_cisco_nexus_base.VLAN_ID_1,
                               switch_ip)
            except exceptions.NexusPortBindingNotFound:
                bindings = []
            self.assertEqual(0, len(bindings))
            try:
                binding = nexus_db_v2.get_nve_switch_bindings(switch_ip)
            except exceptions.NexusPortBindingNotFound:
                binding = []
            self.assertEqual(0, len(binding))

    def test_nexus_vxlan_two_network(self):
        """Test processing for creating one VXLAN segment."""

        add_port_driver_result2 = (
            [test_cisco_nexus_base.RESULT_ADD_NVE_INTERFACE.
                format(1, 70001, '255.1.1.1'),
            test_cisco_nexus_base.RESULT_ADD_VLAN_VNI.
                format(265, 70001),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/20', 265)])

        delete_port_driver_result2 = (
            [test_cisco_nexus_base.RESULT_DEL_NVE_INTERFACE.
                format(1, 70001, 265),
            test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/20', 265),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(265)])

        self._basic_create_verify_port_vlan(
            'test_vxlan_config5',
            self.add_port_driver_result)

        self._create_port(
            self.test_configs['test_vxlan_config6'],
            override_netid=888)
        self._verify_results(add_port_driver_result2)

        binding = nexus_db_v2.get_nve_switch_bindings(
            test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)
        self.assertEqual(2, len(binding))

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_vxlan_config6',
            delete_port_driver_result2, nbr_of_bindings=1)

        self._basic_delete_verify_port_vlan(
            'test_vxlan_config5',
            self.delete_port_driver_result)

        try:
            binding = nexus_db_v2.get_nve_switch_bindings(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)
        except exceptions.NexusPortBindingNotFound:
            binding = []
        self.assertEqual(0, len(binding))
