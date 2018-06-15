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

from networking_cisco.ml2_drivers.nexus import (
    constants as const)
from networking_cisco.ml2_drivers.nexus import (
    nexus_restapi_snippets as snipp)
from networking_cisco.ml2_drivers.nexus import exceptions
from networking_cisco.ml2_drivers.nexus import nexus_db_v2
from networking_cisco.tests.unit.ml2_drivers.nexus import (
    test_cisco_nexus_base as base)

RP_HOST_NAME_1 = 'UniquePort'
RP_HOST_NAME_2 = 'DuplicateVlan'
RP_HOST_NAME_3 = 'DuplicatePort'
RP_HOST_NAME_DUAL = 'testdualhost'
MAX_REPLAY_COUNT = 4


class TestCiscoNexusReplayResults(
    base.TestCiscoNexusBaseResults):

    """Unit tests driver results for Cisco ML2 Nexus."""

    test_results = {

        'driver_result_unique_init': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '')),
             base.POST],
        ],

        'driver_result_unique_add1': [
            [snipp.PATH_ALL,
             None,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             None,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],

        'driver_result_unique_add2': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+265')),
             base.POST]
        ],

        'driver_result_unique_del1': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_del2': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             None,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             None,
             '',
             base.DELETE]
        ],

        'driver_result_unique_2vlan_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+265,267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                  snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]
        ],

        'dupl_vlan_result1_add': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],

        'dupl_vlan_result2_add': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],

        'dupl_vlan_result2_del': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST]
        ],

        'dupl_vlan_result_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
        ],

        'dupl_port_result_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_3,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_3,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
        ],

        'switch_up_result_add': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_VLAN_ADD % 269),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+269')),
             base.POST]
        ],

        'switch_up_result_del': [
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-269')),
             base.POST],
            [(snipp.PATH_VLAN % '269'),
             base.NEXUS_IP_ADDRESS_DUAL,
             '',
             base.DELETE]
        ],

        'switch_restore_result_add': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_VLAN_ADD % 269),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+269')),
             base.POST]
        ],

        'switch_restore_result_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/2]'),
             base.NEXUS_IP_ADDRESS_DUAL2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+269')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_DUAL2,
             (snipp.BODY_VLAN_ADD % 269),
             base.POST]
        ],

        'switch_restore_result_del': [
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-269')),
             base.POST],
            [(snipp.PATH_VLAN % '269'),
             base.NEXUS_IP_ADDRESS_DUAL,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'phys-[eth1/2]'),
             base.NEXUS_IP_ADDRESS_DUAL2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-269')),
             base.POST],
            [(snipp.PATH_VLAN % '269'),
             base.NEXUS_IP_ADDRESS_DUAL2,
             '',
             base.DELETE]
        ],

    }


class TestCiscoNexusReplay(base.TestCiscoNexusReplayBase):
    """Unit tests for Replay of Cisco ML2 Nexus data."""
    test_configs = {
        'test_replay_unique1':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                RP_HOST_NAME_1,
                base.NEXUS_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_replay_unique2':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                RP_HOST_NAME_1,
                base.NEXUS_PORT_1,
                base.INSTANCE_2,
                base.VLAN_ID_2,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_replay_duplvlan1':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_2,
                RP_HOST_NAME_2,
                base.NEXUS_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_replay_duplvlan2':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_2,
                RP_HOST_NAME_2,
                base.NEXUS_PORT_2,
                base.INSTANCE_2,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_replay_duplport1':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_3,
                RP_HOST_NAME_3,
                base.NEXUS_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_replay_duplport2':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_3,
                RP_HOST_NAME_3,
                base.NEXUS_PORT_1,
                base.INSTANCE_2,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_replay_dual':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_DUAL,
                RP_HOST_NAME_DUAL,
                base.NEXUS_DUAL1,
                base.INSTANCE_DUAL,
                base.VLAN_ID_DUAL,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_replay_dual2':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_DUAL2,
                RP_HOST_NAME_DUAL,
                base.NEXUS_DUAL2,
                base.INSTANCE_DUAL,
                base.VLAN_ID_DUAL,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_replay_vxlan_unique1':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                RP_HOST_NAME_1,
                base.NEXUS_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.VXLAN_ID,
                base.MCAST_GROUP,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
    }
    test_configs = collections.OrderedDict(sorted(test_configs.items()))

    def setUp(self):
        """Sets up mock driver, and switch and credentials dictionaries."""

        super(TestCiscoNexusReplay, self).setUp()
        self.results = TestCiscoNexusReplayResults()

    def test_replay_unique_ports(self):
        """Provides replay data and result data for unique ports. """

        first_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_add1'),
            'nbr_db_entries': 1}
        second_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_add2'),
            'nbr_db_entries': 2}
        first_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_del1'),
            'nbr_db_entries': 1}
        second_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_del2'),
            'nbr_db_entries': 0}

        self._process_replay(
            'test_replay_unique1',
            'test_replay_unique2',
            self.results.get_test_results(
                'driver_result_unique_init'),
            first_add,
            second_add,
            self.results.get_test_results(
                'driver_result_unique_2vlan_replay'),
            first_del,
            second_del)

    def test_replay_duplicate_vlan(self):
        """Provides replay data and result data for duplicate vlans. """

        first_add = {
            'driver_results': self.results.get_test_results(
                'dupl_vlan_result1_add'),
            'nbr_db_entries': 2}

        # TODO(caboucha)
        # 'driver_result': [], until the correct fix for
        # the following issue is resolved.
        # https://review.openstack.org/#/c/241216/
        second_add = {
            'driver_results': self.results.get_test_results(
                'dupl_vlan_result2_add'),
            'nbr_db_entries': 4}

        first_del = {'driver_results': [],
                     'nbr_db_entries': 2}

        second_del = {
            'driver_results': self.results.get_test_results(
                'dupl_vlan_result2_del'),
            'nbr_db_entries': 0}

        self._process_replay('test_replay_duplvlan1',
                             'test_replay_duplvlan2',
                             [],
                             first_add, second_add,
                             self.results.get_test_results(
                                 'dupl_vlan_result_replay'),
                             first_del, second_del)

    def test_replay_duplicate_ports(self):
        """Provides replay data and result data for duplicate ports. """

        first_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_add1'),
            'nbr_db_entries': 1}

        # TODO(caboucha)
        # 'driver_result': [], until the correct fix for
        # the following issue is resolved.
        # https://review.openstack.org/#/c/241216/
        second_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_add1'),
            'nbr_db_entries': 2}
        first_del = {'driver_results': [],
                     'nbr_db_entries': 1}

        second_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_del2'),
            'nbr_db_entries': 0}

        self._process_replay('test_replay_duplport1',
                             'test_replay_duplport2',
                             [],
                             first_add, second_add,
                             self.results.get_test_results(
                                 'dupl_port_result_replay'),
                             first_del, second_del)

    def test_replay_new_port_success_if_one_switch_up(self):
        """Verifies create port successful if one multi-switch up."""

        # Make sure port is not rejected when there are multiple
        # switches and only one is active.
        port_cfg1 = self.test_configs['test_replay_dual']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg1.nexus_ip_addr, const.SWITCH_ACTIVE)
        port_cfg2 = self.test_configs['test_replay_dual2']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg2.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_dual',
            self.results.get_test_results(
                'switch_up_result_add'),
            nbr_of_bindings=1)

        # Even though 2nd entry is inactive, there should be
        # a data base entry configured for it.
        # 2 = One entry for port the other for reserved binding
        self.assertEqual(
            2, len(nexus_db_v2.get_nexusport_switch_bindings(
                   port_cfg2.nexus_ip_addr)))

        # Clean-up the port entry
        self._basic_delete_verify_port_vlan('test_replay_dual',
            self.results.get_test_results(
                'switch_up_result_del'),
            nbr_of_bindings=0)

    def test_replay_port_success_if_one_switch_restored(self):
        """Verifies port restored after one of multi-switch restored."""

        # Make sure port is not rejected when there are multiple
        # switches and one is active.  Then proceed to bring-up
        # the other switch and it gets configured successfully.
        # Then remove all.
        port_cfg1 = self.test_configs['test_replay_dual']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg1.nexus_ip_addr, const.SWITCH_ACTIVE)
        port_cfg2 = self.test_configs['test_replay_dual2']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg2.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_dual',
            self.results.get_test_results(
                'switch_restore_result_add'),
            nbr_of_bindings=1)

        # Even though 2nd entry is inactive, there should be
        # a data base entry configured for it.
        # 2 = One entry for port the other for reserved binding
        self.assertEqual(
            2, len(nexus_db_v2.get_nexusport_switch_bindings(
                   port_cfg2.nexus_ip_addr)))

        # Restore port data for that switch
        self._cfg_monitor.check_connections()
        self._verify_results(
            self.results.get_test_results(
                'switch_restore_result_replay'))

        # Clear mock_call history.
        self.mock_driver.reset_mock()

        # Clean-up the port entries
        self._basic_delete_verify_port_vlan('test_replay_dual',
            self.results.get_test_results(
                'switch_restore_result_del'),
            nbr_of_bindings=0)

    def test_replay_create_fails_if_single_switch_down(self):
        """Verifies port create fails if switch down."""

        # Make sure create ethernet config fails when the
        # switch state is inactive.
        port_cfg = self.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        port_context = self._generate_port_context(port_cfg)
        self.assertRaises(
                exceptions.NexusConnectFailed,
                self._cisco_mech_driver.create_port_postcommit,
                port_context)

    def test_replay_update_fails_if_single_switch_down(self):
        """Verifies port update fails if switch down."""

        # Make sure update ethernet config fails when the
        # switch state is inactive.
        port_cfg = self.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        port_context = self._generate_port_context(port_cfg)
        self.assertRaises(
                exceptions.NexusConnectFailed,
                self._cisco_mech_driver.update_port_postcommit,
                port_context)

    def test_replay_delete_success_if_switch_down(self):
        """Verifies port delete success if switch down."""

        # Make sure delete config successful even when the
        # switch state is inactive.
        port_cfg = self.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        self._basic_create_verify_port_vlan('test_replay_unique1',
            self.results.get_test_results(
                'driver_result_unique_add1'))

        # Make switch inactive before delete
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Clean-up the port entry
        self._basic_delete_verify_port_vlan('test_replay_unique1',
            [], nbr_of_bindings=0)

    def test_replay_get_nexus_type_failure_two_switches(self):
        """Verifies exception during driver get nexus type. """

        # There are two switches, one active and the other inactive.
        # Make sure 'get_nexus_type' fails so create_port_postcommit()
        # will return an exception.  'get_nexus_type' is used as
        # as ping so even if the switch is marked active then double
        # check it is indeed still active.  If not and thre are no
        # other active switches, then raise exception.
        port_cfg1 = self.test_configs['test_replay_dual']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg1.nexus_ip_addr, const.SWITCH_ACTIVE)
        port_cfg2 = self.test_configs['test_replay_dual2']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg2.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Set-up so get_nexus_type driver fails on active switch
        self._set_nexus_type_failure()

        port_context = self._generate_port_context(port_cfg1)
        self.assertRaises(
                exceptions.NexusConnectFailed,
                self._cisco_mech_driver.create_port_postcommit,
                port_context)

    def test_replay_get_nexus_type_failure(self):
        """Verifies exception during get nexus_type while replaying. """

        # Set switch state to False so replay config will start.
        # This should not affect user configuration.
        port_cfg = self.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_unique1',
            self.results.get_test_results(
                'driver_result_unique_add1'))

        # Set-up so get_nexus_type driver fails
        self._set_nexus_type_failure()

        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Perform replay which should not send back exception
        # but merely quit
        self._cfg_monitor.check_connections()

        # Since get of nexus_type failed, there should be
        # no attempt to configure anything.
        self._verify_results([])

        # Clean-up the port entry
        self._basic_delete_verify_port_vlan('test_replay_unique1',
            [])

    def test_replay_create_vlan_failure_during_replay(self):
        """Verifies exception during create vlan while replaying. """

        # Set switch state to False so replay config will start.
        # This should not affect user configuration.
        port_cfg = self.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_unique1',
            self.results.get_test_results(
                'driver_result_unique_add1'))

        # Set-up exception during create_vlan
        config = {'rest_post.side_effect':
                  self._config_restapi_side_effects(
                      '"fabEncap": "vlan-267"',
                      exceptions.NexusConnectFailed,
                      (__name__ + '1'))}
        self.mock_driver.configure_mock(**config)

        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Perform replay which should not send back exception
        # but merely quit
        self._cfg_monitor.check_connections()

        # Verify that switch is put back into INACTIVE state
        self.assertEqual(
            const.SWITCH_INACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                port_cfg.nexus_ip_addr))

        # The edit of create_vlan failed, but there will
        # be 2 create vlan attempts in mock call history.
        result_replay = [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
            base.NEXUS_IP_ADDRESS_1,
            (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
            base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST]
        ]

        self._verify_results(result_replay)

        # Clear the edit driver exception for next test.
        config = {'rest_post.side_effect':
                  None}
        self.mock_driver.configure_mock(**config)

        # Perform replay which should not send back exception
        # but merely quit
        self._cfg_monitor.check_connections()

        # Verify that switch is in ACTIVE state
        self.assertEqual(
            const.SWITCH_ACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                port_cfg.nexus_ip_addr))

        # Clear mock_call history.
        self.mock_driver.reset_mock()

        # Clean-up the port entry
        self._basic_delete_verify_port_vlan('test_replay_unique1',
            self.results.get_test_results(
                'driver_result_unique_del2'))

    def test_replay_vlan_batch_failure_during_replay(self):
        """Verifies handling of batch vlan during replay."""

        tmp_cfg = self.TestConfigObj(
            base.NEXUS_IP_ADDRESS_1,
            RP_HOST_NAME_1,
            base.NEXUS_PORT_1,
            base.INSTANCE_1,
            base.VLAN_ID_1,
            base.NO_VXLAN_ID,
            None,
            base.DEVICE_OWNER_COMPUTE,
            {},
            None,
            base.NORMAL_VNIC)
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            tmp_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Create a batch of port entries with unique vlans
        num_vlans = const.CREATE_VLAN_BATCH + 10
        for x in range(num_vlans):
            instance_id = base.INSTANCE_1 + '-' + str(x)
            new_cfg = tmp_cfg._replace(
                          vlan_id=base.VLAN_ID_1 + x,
                          instance_id=instance_id)
            self._create_port(new_cfg)

        # Put it back to inactive state
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            tmp_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        self._cfg_monitor.check_connections()

        # Verify the switch is in restore stage 2 state
        self.assertEqual(
            const.SWITCH_RESTORE_S2,
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                tmp_cfg.nexus_ip_addr))

        config = {'rest_post.side_effect':
                  self._config_restapi_side_effects(
                      '"fabEncap": "vlan-',
                      exceptions.NexusConnectFailed,
                      (__name__ + '1'))}
        self.mock_driver.configure_mock(**config)

        # Call check_connections() again  to attempt to send
        # last batch of 10 which should fail
        self._cfg_monitor.check_connections()
        # Verify the switch is back in INACTIVE state
        self.assertEqual(
            const.SWITCH_INACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                tmp_cfg.nexus_ip_addr))

        # Clear mock_call history.
        self.mock_driver.reset_mock()

        # Clear the edit driver exception for next test.
        config = {'rest_post.side_effect':
                  None}
        self.mock_driver.configure_mock(**config)

        # Call check_connections() again  to restart restore
        self._cfg_monitor.check_connections()

        # Verify the switch is in restore stage 2 state
        self.assertEqual(
            const.SWITCH_RESTORE_S2,
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                tmp_cfg.nexus_ip_addr))

        # Call check_connections() to successfully send
        # last batch of 10 which should fail
        self._cfg_monitor.check_connections()

        # Verify the switch is in restore stage 2 state
        self.assertEqual(
            const.SWITCH_ACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                tmp_cfg.nexus_ip_addr))

    def test_replay_no_retry_failure_handling(self):
        """Tests to check replay 'no retry' failure handling.

        1) Verify config_failure is incremented upon failure during
        replay config and verify create_vlan transactions are seen.
        2) Verify contact_failure is incremented upon failure during
        get_nexus_type transaction.
        3) Verify receipt of new transaction does not reset
        failure statistics.
        4) Verify config&contact_failure is reset when replay is
        successful.
        """

        driver_result2 = ([
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
            base.NEXUS_IP_ADDRESS_1,
            (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
            base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST]]) * 4

        config_replay = MAX_REPLAY_COUNT
        port_cfg = self.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan(
            'test_replay_unique1',
            self.results.get_test_results(
                'driver_result_unique_add1'))

        # Test 1:
        # Set the edit create vlan driver exception
        # Perform replay MAX_REPLAY_COUNT times
        # This should not roll-up an exception but merely quit
        # and increment FAIL_CONFIG statistics
        config = {'rest_post.side_effect':
                  self._config_restapi_side_effects(
                      '"fabEncap": "vlan-267"',
                      exceptions.NexusConnectFailed,
                      (__name__ + '1'))}
        self.mock_driver.configure_mock(**config)

        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)
        for i in range(config_replay):
            self._cfg_monitor.check_connections()

        # Verify FAIL_CONFIG reached(MAX_REPLAY_COUNT) and there
        # were only MAX_REPLAY_COUNT+1 attempts to send create_vlan.
        # first is from test_replay_create_vlan_failure()
        # and MAX_REPLAY_COUNT from check_connections()
        self.assertEqual(
            config_replay,
            self._cisco_mech_driver.get_switch_replay_failure(
                const.FAIL_CONFIG,
                base.NEXUS_IP_ADDRESS_1))
        self._verify_results(driver_result2)

        # Verify there exists a single port binding
        # plus 1 for reserved switch entry
        self.assertEqual(
            2, len(nexus_db_v2.get_nexusport_switch_bindings(
                   base.NEXUS_IP_ADDRESS_1)))

        # Clear mock_call history.
        self.mock_driver.reset_mock()

        # Clear the edit driver exception for next test.
        config = {'rest_post.side_effect':
                  None}
        self.mock_driver.configure_mock(**config)

        # Test 2)
        # Set it up so get nexus type returns exception.
        # FAIL_CONTACT should increment.
        self._set_nexus_type_failure()

        # Perform replay MAX_REPLAY_COUNT times
        # This should not roll-up an exception but merely quit
        for i in range(config_replay):
            self._cfg_monitor.check_connections()

        # Verify switch FAIL_CONTACT reached (MAX_REPLAY_COUNT)
        # and there were no attempts to send create_vlan.
        self.assertEqual(
            config_replay,
            self._cisco_mech_driver.get_switch_replay_failure(
                const.FAIL_CONFIG,
                base.NEXUS_IP_ADDRESS_1))
        self.assertEqual(
            config_replay,
            self._cisco_mech_driver.get_switch_replay_failure(
                const.FAIL_CONTACT,
                base.NEXUS_IP_ADDRESS_1))
        self._verify_results([])

        # Test 3)
        # Verify delete transaction doesn't affect failure stats.
        self._basic_delete_verify_port_vlan('test_replay_unique1',
            [])

        # Verify failure stats is not reset
        self.assertEqual(
            config_replay,
            self._cisco_mech_driver.get_switch_replay_failure(
                const.FAIL_CONFIG,
                base.NEXUS_IP_ADDRESS_1))
        self.assertEqual(
            config_replay,
            self._cisco_mech_driver.get_switch_replay_failure(
                const.FAIL_CONTACT,
                base.NEXUS_IP_ADDRESS_1))

        # Clear the get nexus type driver exception.
        config = {'rest_get.side_effect':
                  self.get_init_side_effect}
        self.mock_driver.configure_mock(**config)

        # Test 4)
        # Verify config&contact_failure is reset when replay is
        # successful.

        # Perform replay once which will be successful causing
        # failure stats to be reset to 0.
        # Then verify these stats are indeed 0.
        self._cfg_monitor.check_connections()
        self.assertEqual(
            0,
            self._cisco_mech_driver.get_switch_replay_failure(
                const.FAIL_CONFIG,
                base.NEXUS_IP_ADDRESS_1))
        self.assertEqual(
            0,
            self._cisco_mech_driver.get_switch_replay_failure(
                const.FAIL_CONTACT,
                base.NEXUS_IP_ADDRESS_1))

        # Verify switch state is now active following successful replay.
        self.assertEqual(
            const.SWITCH_ACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                base.NEXUS_IP_ADDRESS_1))


class TestCiscoNexusBaremetalReplayResults(
    base.TestCiscoNexusBaseResults):
    """Unit tests driver results for Cisco ML2 Nexus."""

    test_results = {

        'driver_result_unique_init': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '')),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '')),
             base.POST]],

        'driver_result_unique_eth_add1': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'l1PhysIf', '', '+267', 'vlan-267')),
             base.POST]],

        'driver_result_unique_eth_add2': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'l1PhysIf', '', '+265', 'vlan-265')),
             base.POST]],

        'driver_result_unique_eth_del1': [
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '', '-265', '')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]],

        'driver_result_unique_eth_del2': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]],

        'driver_result_unique_2if_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'l1PhysIf', '', '+267', 'vlan-267')),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'l1PhysIf', '', '+265', 'vlan-265')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                 snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]],

        'driver_result_unique_eth_add_vm': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+265')),
             base.POST]],

        'driver_result_unique_eth_del_vm': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]],

        'driver_result_unique_2vlan_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'l1PhysIf', '', '+267', 'vlan-267')),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+265,267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                 snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]],

        'driver_result_unique_vPC_2switch_add1': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST]],

        'driver_result_unique_vPC_2switch_del1': [
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE]],

        'driver_result_unique_vPC_2if_replay': [
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST]],

        'driver_result_unique_vPC470_add1': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST]],

        'driver_result_unique_vPC470_add2': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+265')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+265')),
             base.POST]],

        'driver_result_unique_vPC470_del1': [
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE]],

        'driver_result_unique_vPC470_del2': [
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('pcAggrIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('pcAggrIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE]],

        'driver_result_unique_vPC470_2vlan_replay': [
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+265,267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                  snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+265,267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                  snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]],

        'driver_result_unique_auto_vPC_2vlan_replay': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_ADD_PORT_CH % (1001, 1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_ADD_PORT_CH_P2 % (1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_ADD_CH_GRP % (1001, 1001, 'phys-[eth1/10]')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % (
                 'pcAggrIf', snipp.BODY_PORT_CH_MODE, '')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+265,267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                  snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_ADD_PORT_CH % (1001, 1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_ADD_PORT_CH_P2 % (1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_ADD_CH_GRP % (1001, 1001, 'phys-[eth1/20]')),
            base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % (
                 'pcAggrIf', snipp.BODY_PORT_CH_MODE, '')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+265,267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                  snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]],

        'driver_result_unique_auto_vPC_vm_add1': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+265')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+265')),
             base.POST]],

        'driver_result_unique_auto_vPC_vm_del1': [
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
            base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE]],

        'driver_result_unique_auto_vPC_add1': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_ADD_PORT_CH % (1001, 1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_ADD_PORT_CH_P2 % (1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_ADD_CH_GRP % (1001, 1001, 'phys-[eth1/10]')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % (
                 'pcAggrIf', snipp.BODY_PORT_CH_MODE, '')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_ADD_PORT_CH % (1001, 1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_ADD_PORT_CH_P2 % (1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_ADD_CH_GRP % (1001, 1001, 'phys-[eth1/20]')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % (
                 'pcAggrIf', snipp.BODY_PORT_CH_MODE, '')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST]],

        'driver_result_unique_auto_vPC_del1': [
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('pcAggrIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_DEL_CH_GRP % ('1001', 'phys-[eth1/10]')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_DEL_PORT_CH % ('1001')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('pcAggrIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_DEL_CH_GRP % ('1001', 'phys-[eth1/20]')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_DEL_PORT_CH % ('1001')),
             base.POST]],

        'driver_result_unique_auto_vPC_add1_w_user_cfg': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_ADD_PORT_CH % (1001, 1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_ADD_CH_GRP % (1001, 1001, 'phys-[eth1/10]')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % (
                 'pcAggrIf', snipp.BODY_PORT_CH_MODE, '')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_ADD_PORT_CH % (1001, 1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_ADD_CH_GRP % (1001, 1001, 'phys-[eth1/20]')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % (
                 'pcAggrIf', snipp.BODY_PORT_CH_MODE, '')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST]],

        'driver_result_unique_auto_vPC_add_usr_cmd_nxapi_cli': [
            [snipp.PATH_USER_CMDS,
             base.NEXUS_IP_ADDRESS_1,
             "int port-channel 1001 ;spanning-tree port type edge trunk "
             ";no lacp suspend-individual",
             base.POST],
            [snipp.PATH_USER_CMDS,
             base.NEXUS_IP_ADDRESS_2,
             "int port-channel 1001 ;spanning-tree port type edge trunk "
             ";no lacp suspend-individual",
             base.POST]],

        'driver_result_unique_auto_vPC_add1_w_user_cfg_replay': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_ADD_PORT_CH % (1001, 1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_ADD_CH_GRP % (1001, 1001, 'phys-[eth1/10]')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % (
                 'pcAggrIf', snipp.BODY_PORT_CH_MODE, '')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_ADD_PORT_CH % (1001, 1001, 1001)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_ADD_CH_GRP % (1001, 1001, 'phys-[eth1/20]')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % (
                 'pcAggrIf', snipp.BODY_PORT_CH_MODE, '')),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po1001]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'pcAggrIf', '', '+267', 'vlan-267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST]],

    }

GET_PORT_CH_RESPONSE = {
    "totalCount": "4",
    "imdata": [
        {
            "pcRsMbrIfs": {
                "attributes": {
                    "parentSKey": "po1",
                    "tSKey": "eth1/11",
                }
            }
        },
        {
            "pcRsMbrIfs": {
                "attributes": {
                    "parentSKey": "po469",
                    "tSKey": "eth1/10",
                }
            }
        },
        {
            "pcRsMbrIfs": {
                "attributes": {
                    "parentSKey": "po2",
                    "tSKey": "eth1/12",
                }
            }
        },
        {
            "pcRsMbrIfs": {
                "attributes": {
                    "parentSKey": "po469",
                    "tSKey": "eth1/20",
                }
            }
        }
    ]
}


class TestCiscoNexusBaremetalReplay(
    base.TestCiscoNexusReplayBase):

    """Unit tests for Replay of Cisco ML2 Nexus data."""

    baremetal_profile = {
        "local_link_information": [
            {
                "port_id": base.NEXUS_BAREMETAL_PORT_1,
                "switch_info": {
                    "switch_ip": base.NEXUS_IP_ADDRESS_1,
                },
            },
        ]
    }

    baremetal_profile2 = {
        "local_link_information": [
            {
                "port_id": base.NEXUS_BAREMETAL_PORT_2,
                "switch_info": {
                    "switch_ip": base.NEXUS_IP_ADDRESS_1,
                },
            },
        ]
    }

    baremetal_profile_vPC = {
        "local_link_information": [
            {
                "port_id": base.NEXUS_BAREMETAL_PORT_1,
                "switch_info": {
                    "switch_ip": base.NEXUS_IP_ADDRESS_1,
                },
            },
            {
                "port_id": base.NEXUS_BAREMETAL_PORT_2,
                "switch_info": {
                    "switch_ip": base.NEXUS_IP_ADDRESS_2,
                },
            },
        ]
    }

    test_configs = {
        'test_replay_unique1':
            base.TestCiscoNexusBase.TestConfigObj(
                None,
                base.HOST_NAME_UNUSED,
                base.NEXUS_BAREMETAL_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_BAREMETAL,
                baremetal_profile,
                base.HOST_NAME_Baremetal + '1',
                base.BAREMETAL_VNIC),
        'test_replay_unique2':
            base.TestCiscoNexusBase.TestConfigObj(
                None,
                base.HOST_NAME_UNUSED,
                base.NEXUS_BAREMETAL_PORT_2,
                base.INSTANCE_2,
                base.VLAN_ID_2,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_BAREMETAL,
                baremetal_profile2,
                base.HOST_NAME_Baremetal + '1',
                base.BAREMETAL_VNIC),
        'test_replay_unique_vPC':
            base.TestCiscoNexusBase.TestConfigObj(
                None,
                base.HOST_NAME_UNUSED,
                base.NEXUS_BAREMETAL_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_BAREMETAL,
                baremetal_profile_vPC,
                base.HOST_NAME_Baremetal + '1',
                base.BAREMETAL_VNIC),
        'test_config_vm':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                base.HOST_NAME_Baremetal + '1',
                base.NEXUS_BAREMETAL_PORT_1,
                base.INSTANCE_2,
                base.VLAN_ID_2,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
    }

    test_configs = collections.OrderedDict(sorted(test_configs.items()))

    def setUp(self):
        """Sets up mock driver, and switch and credentials dictionaries."""
        original_intersect = nexus_db_v2._get_free_vpcids_on_switches

        def new_get_free_vpcids_on_switches(nexus_ips):
            intersect = list(original_intersect(nexus_ips))
            intersect.sort()
            return intersect

        mock.patch.object(nexus_db_v2,
                         '_get_free_vpcids_on_switches',
                         new=new_get_free_vpcids_on_switches).start()

        super(TestCiscoNexusBaremetalReplay, self).setUp()
        self.results = TestCiscoNexusBaremetalReplayResults()

    def get_init_side_effect(
        self, action, ipaddr=None, body=None, headers=None):

        if action == snipp.PATH_GET_NEXUS_TYPE:
            return base.GET_NEXUS_TYPE_RESPONSE
        elif action in snipp.PATH_GET_PC_MEMBERS:
            return GET_PORT_CH_RESPONSE
        elif base.ETH_PATH in action:
            return base.GET_INTERFACE_RESPONSE
        elif base.PORT_CHAN_PATH in action:
            return base.GET_INTERFACE_PCHAN_RESPONSE

        return {}

    def get_init_side_effect2(
        self, action, ipaddr=None, body=None, headers=None):

        if action == snipp.PATH_GET_NEXUS_TYPE:
            return base.GET_NEXUS_TYPE_RESPONSE
        elif action in snipp.PATH_GET_PC_MEMBERS:
            return base.GET_NO_PORT_CH_RESPONSE
        elif base.ETH_PATH in action:
            return base.GET_INTERFACE_RESPONSE
        elif base.PORT_CHAN_PATH in action:
            return base.GET_INTERFACE_PCHAN_NO_TRUNK_RESPONSE

        return {}

    def _init_port_channel(self, ch_grp, which=1):

        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.

        GET_PORT_CH_RESPONSE['imdata'][which]['pcRsMbrIfs'][
            'attributes']['parentSKey'] = ('po' + str(ch_grp))
        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect}
        self.mock_driver.configure_mock(**data_json)

    def test_replay_unique_ethernet_ports(self):
        """Provides replay data and result data for unique ports. """

        first_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_eth_add1'),
            'nbr_db_entries': 1}
        second_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_eth_add2'),
            'nbr_db_entries': 2}
        first_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_eth_del1'),
            'nbr_db_entries': 1,
            'nbr_db_mappings': 0}
        second_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_eth_del2'),
            'nbr_db_entries': 0}

        self._process_replay(
            'test_replay_unique1',
            'test_replay_unique2',
            self.results.get_test_results(
                'driver_result_unique_eth_init'),
            first_add,
            second_add,
            self.results.get_test_results(
                'driver_result_unique_2if_replay'),
            first_del,
            second_del)

    def test_replay_unique_ethernet_port_and_vm(self):
        """Provides replay data and result data for unique ports. """

        first_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_eth_add1'),
            'nbr_db_entries': 1}
        second_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_eth_add_vm'),
            'nbr_db_entries': 2}
        first_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_eth_del_vm'),
            'nbr_db_entries': 1}
        second_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_eth_del2'),
            'nbr_db_entries': 0}

        self._process_replay(
            'test_replay_unique1',
            'test_config_vm',
            self.results.get_test_results(
                'driver_result_unique_eth_init'),
            first_add,
            second_add,
            self.results.get_test_results(
                'driver_result_unique_2vlan_replay'),
            first_del,
            second_del)

    def test_replay_unique_vPC_ports(self):
        """Provides replay data and result data for unique ports. """

        first_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_vPC_2switch_add1'),
            'nbr_db_entries': 2}
        second_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_vPC_2switch_del1'),
            'nbr_db_entries': 0}

        self._init_port_channel(469)
        self._init_port_channel(469, 3)

        self._process_replay(
            'test_replay_unique_vPC',
            None,
            [],
            first_add,
            None,
            self.results.get_test_results(
                'driver_result_unique_vPC_2if_replay'),
            None,
            second_del)

    def test_replay_unique_vPC_ports_and_vm(self):
        """Provides replay data and result data for unique ports. """

        first_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_vPC470_add1'),
            'nbr_db_entries': 2}
        second_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_vPC470_add2'),
            'nbr_db_entries': 4}
        first_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_vPC470_del1'),
            'nbr_db_entries': 2}
        second_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_vPC470_del2'),
            'nbr_db_entries': 0}

        self._init_port_channel(470)
        self._init_port_channel(470, 3)

        self._process_replay(
            'test_replay_unique_vPC',
            'test_config_vm',
            [],
            first_add,
            second_add,
            self.results.get_test_results(
                'driver_result_unique_vPC470_2vlan_replay'),
            first_del,
            second_del)
        self._init_port_channel(469)
        self._init_port_channel(469, 3)

    def test_replay_unique_vPC_ports_chg_vPC_nbr(self):
        """Persist with learned channel group even if it changed."""

        def replay_init():
            # This causes port-channel 469 will persist instead.
            # We will not relearn
            self._init_port_channel(470)

        first_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_vPC_2switch_add1'),
            'nbr_db_entries': 2}
        second_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_vPC_2switch_del1'),
            'nbr_db_entries': 0}

        self._init_port_channel(469)

        self._process_replay(
            'test_replay_unique_vPC',
            None,
            [],
            first_add,
            None,
            self.results.get_test_results(
                'driver_result_unique_vPC_2if_replay'),
            None,
            second_del,
            replay_init)
        self._init_port_channel(469)

    def test_replay_unique_vPC_ports_chg_to_enet(self):
        """Persist with learned channel group even if it was removed."""

        def replay_init():
            # This causes port-channel to get replaced with enet
            # by eliminating channel-group config from enet config.
            self.restapi_mock_init()

        first_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_vPC_2switch_add1'),
            'nbr_db_entries': 2}
        second_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_vPC_2switch_del1'),
            'nbr_db_entries': 0}

        self._init_port_channel(469)
        self._init_port_channel(469, 3)

        self._process_replay(
            'test_replay_unique_vPC',
            None,
            [],
            first_add,
            None,
            self.results.get_test_results(
                'driver_result_unique_vPC_2if_replay'),
            None,
            second_del,
            replay_init)

    def test_replay_automated_port_channel_w_user_cfg(self):
        """Basic replay of auto-port-channel creation with user config."""

        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect2}
        self.mock_driver.configure_mock(**data_json)

        for switch_ip in base.SWITCH_LIST:
            cfg.CONF.set_override(
                const.VPCPOOL, ('1001-1025'),
                cfg.CONF.ml2_cisco.nexus_switches.get(switch_ip)._group)
        self._cisco_mech_driver._initialize_vpc_alloc_pools()

        self._cfg_vPC_user_commands(
            base.SWITCH_LIST,
            "spanning-tree port type edge trunk;no lacp "
            "suspend-individual")

        # _init_port_channel is not called so the vpc nbr gets created.

        def replay_complete():
            # Add same together cause this  accounts for the initial add
            # as well as add during replay.
            myresults = (self.results.get_test_results(
                'driver_result_unique_auto_vPC_add_usr_cmd_nxapi_cli') +
                self.results.get_test_results(
                    'driver_result_unique_auto_vPC_add_usr_cmd_nxapi_cli'))
            self._verify_nxapi_results(myresults)

        first_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_auto_vPC_add1_w_user_cfg'),
            'nbr_db_entries': 2}
        second_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_auto_vPC_del1'),
            'nbr_db_entries': 0}

        self._process_replay(
            'test_replay_unique_vPC',
            None,
            [],
            first_add,
            None,
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_add1_w_user_cfg_replay'),
            None,
            second_del,
            replay_complete=replay_complete)

        for switch_ip in base.SWITCH_LIST:
            self.assertEqual(
                25, len(nexus_db_v2.get_free_switch_vpc_allocs(
                        switch_ip)))

    def test_replay_automated_vPC_ports_and_vm(self):
        """Provides replay data and result data for unique ports. """

        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect2}
        self.mock_driver.configure_mock(**data_json)

        for switch_ip in base.SWITCH_LIST:
            cfg.CONF.set_override(
                const.VPCPOOL, ('1001-1025'),
                cfg.CONF.ml2_cisco.nexus_switches.get(switch_ip)._group)
        self._cisco_mech_driver._initialize_vpc_alloc_pools()

        # _init_port_channel is not called so the vpc nbr is created

        first_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_auto_vPC_add1'),
            'nbr_db_entries': 2}
        second_add = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_auto_vPC_vm_add1'),
            'nbr_db_entries': 4}
        first_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_auto_vPC_vm_del1'),
            'nbr_db_entries': 2}
        second_del = {
            'driver_results': self.results.get_test_results(
                'driver_result_unique_auto_vPC_del1'),
            'nbr_db_entries': 0}

        self._process_replay(
            'test_replay_unique_vPC',
            'test_config_vm',
            [],
            first_add,
            second_add,
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_2vlan_replay'),
            first_del,
            second_del)

        for switch_ip in base.SWITCH_LIST:
            self.assertEqual(
                25, len(nexus_db_v2.get_free_switch_vpc_allocs(
                        switch_ip)))
