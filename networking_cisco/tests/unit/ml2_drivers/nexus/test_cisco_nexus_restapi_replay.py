# Copyright (c) 2017 Cisco Systems, Inc.
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

"""
Replay Test Classes using RESTAPI Driver to test Cisco Nexus platforms.

These Classes are based on the original ssh event driver so same
tests occur with same configuration.  What's different between
the tests is the resulting driver output which is what
the tests in this class presents to its parent class.

You will notice in this file there are test methods which
are skipped by using 'pass'.  This is because these tests
apply to ssh only OR because rerunning the test would be
redundant.
"""

import mock
from oslo_config import cfg

from networking_cisco.ml2_drivers.nexus import (
    constants as const)
from networking_cisco.ml2_drivers.nexus import (
    nexus_db_v2 as nxos_db)
from networking_cisco.ml2_drivers.nexus import (
    nexus_restapi_snippets as snipp)
from networking_cisco.tests.unit.ml2_drivers.nexus import (
    test_cisco_nexus_base as base)
from networking_cisco.tests.unit.ml2_drivers.nexus import (
    test_cisco_nexus_replay)


class TestCiscoNexusRestReplayResults(base.TestCiscoNexusBaseResults):

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


class TestCiscoNexusRestReplay(test_cisco_nexus_replay.TestCiscoNexusReplay):
    """Unit tests for Replay of Cisco ML2 Nexus data."""

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        # Call Grandfather's setUp(); otherwise parent will set driver to
        # 'ncclient' instead of 'restapi'.
        super(test_cisco_nexus_replay.TestCiscoNexusReplay, self).setUp()
        self.results = TestCiscoNexusRestReplayResults()

    def test_replay_unique_ports(self):
        super(TestCiscoNexusRestReplay, self).test_replay_unique_ports()

    def test_replay_duplicate_vlan(self):
        super(TestCiscoNexusRestReplay, self).test_replay_duplicate_vlan()

    def test_replay_duplicate_ports(self):
        super(TestCiscoNexusRestReplay, self).test_replay_duplicate_ports()

    def test_replay_enable_vxlan_feature_failure(self):
        pass

    def test_replay_disable_vxlan_feature_failure(self):
        pass

    def test_replay_create_nve_member_failure(self):
        pass

    def test_replay_delete_nve_member_failure(self):
        pass

    def test_replay_create_vlan_failure(self):
        pass

    def test_replay_delete_vlan_failure(self):
        pass

    def test_replay_create_trunk_failure(self):
        pass

    def test_replay_delete_trunk_failure(self):
        pass

    def test_replay_new_port_success_if_one_switch_up(self):
        (super(TestCiscoNexusRestReplay, self).
            test_replay_new_port_success_if_one_switch_up())

    def test_replay_port_success_if_one_switch_restored(self):
        (super(TestCiscoNexusRestReplay, self).
            test_replay_port_success_if_one_switch_restored())

    def test_replay_create_fails_if_single_switch_down(self):
        (super(TestCiscoNexusRestReplay, self).
            test_replay_create_fails_if_single_switch_down())

    def test_replay_update_fails_if_single_switch_down(self):
        (super(TestCiscoNexusRestReplay, self).
            test_replay_update_fails_if_single_switch_down())

    def test_replay_delete_success_if_switch_down(self):
        (super(TestCiscoNexusRestReplay, self).
            test_replay_delete_success_if_switch_down())

    def test_replay_get_nexus_type_failure_two_switches(self):
        pass

    def test_replay_get_nexus_type_failure(self):
        pass

    def test_replay_create_vlan_failure_during_replay(self):
        pass

    def test_replay_vlan_batch_failure_during_replay(self):
        pass

    def test_replay_no_retry_failure_handling(self):
        pass


class TestCiscoNexusRestBaremetalReplayResults(base.TestCiscoNexusBaseResults):

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
             base.POST],
        ],

        'driver_result_unique_eth_add1': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'l1PhysIf', '', '+267', 'vlan-267')),
             base.POST]
        ],

        'driver_result_unique_eth_add2': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'l1PhysIf', '', '+265', 'vlan-265')),
             base.POST]
        ],

        'driver_result_unique_eth_del1': [
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '', '-265', '')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_eth_del2': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

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
             base.POST]
        ],

        'driver_result_unique_eth_add_vm': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+265')),
             base.POST]
        ],

        'driver_result_unique_eth_del_vm': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

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
             base.POST]
        ],
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
             base.POST]
        ],

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
             base.DELETE]
        ],

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
             base.POST]
        ],

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
             base.POST],
        ],

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
             base.POST]
        ],

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
             base.DELETE],
        ],

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
             base.DELETE],
        ],

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
             base.POST]
        ],

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
             base.POST]
        ],

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
             base.POST]
        ],

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
             base.DELETE]
        ],
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
             base.POST]
        ],
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
             base.POST]
        ],

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
             base.POST]
        ],
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
             base.POST],
        ],
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
             base.POST]
        ],

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

GET_INTERFACE_PCHAN_NO_TRUNK_RESPONSE = {
    "totalCount": "1",
    "imdata": [
        {
            "pcAggrIf": {
                "attributes": {
                    "trunkVlans": "1-4094"
                }
            }
        }
    ]
}


class TestCiscoNexusRestBaremetalReplay(
    test_cisco_nexus_replay.TestCiscoNexusBaremetalReplay):

    def get_init_side_effect(
        self, action, ipaddr=None, body=None, headers=None):

        eth_path = 'api/mo/sys/intf/phys-'
        port_chan_path = 'api/mo/sys/intf/aggr-'

        if action == snipp.PATH_GET_NEXUS_TYPE:
            return base.GET_NEXUS_TYPE_RESPONSE
        elif action in snipp.PATH_GET_PC_MEMBERS:
            return GET_PORT_CH_RESPONSE
        elif eth_path in action:
            return base.GET_INTERFACE_RESPONSE
        elif port_chan_path in action:
            return base.GET_INTERFACE_PCHAN_RESPONSE

        return {}

    def get_init_side_effect2(
        self, action, ipaddr=None, body=None, headers=None):

        eth_path = 'api/mo/sys/intf/phys-'
        port_chan_path = 'api/mo/sys/intf/aggr-'

        if action == snipp.PATH_GET_NEXUS_TYPE:
            return base.GET_NEXUS_TYPE_RESPONSE
        elif action in snipp.PATH_GET_PC_MEMBERS:
            return base.GET_NO_PORT_CH_RESPONSE
        elif eth_path in action:
            return base.GET_INTERFACE_RESPONSE
        elif port_chan_path in action:
            return GET_INTERFACE_PCHAN_NO_TRUNK_RESPONSE

        return {}

    def _init_port_channel(self, ch_grp, which=1):

        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.

        GET_PORT_CH_RESPONSE['imdata'][which]['pcRsMbrIfs'][
            'attributes']['parentSKey'] = ('po' + str(ch_grp))
        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect}
        self.mock_ncclient.configure_mock(**data_json)

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""
        original_intersect = nxos_db._get_free_vpcids_on_switches

        def new_get_free_vpcids_on_switches(nexus_ips):
            intersect = list(original_intersect(nexus_ips))
            intersect.sort()
            return intersect

        mock.patch.object(nxos_db,
                         '_get_free_vpcids_on_switches',
                         new=new_get_free_vpcids_on_switches).start()
        # Call Grandfather's setUp(); otherwise parent will set driver to
        # 'ncclient' instead of 'restapi'.
        super(test_cisco_nexus_replay.TestCiscoNexusBaremetalReplay,
              self).setUp()
        self.results = TestCiscoNexusRestBaremetalReplayResults()

    def test_replay_unique_ethernet_ports(self):
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_ethernet_ports())

    def test_replay_unique_ethernet_port_and_vm(self):
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_ethernet_port_and_vm())

    def test_replay_unique_vPC_ports(self):
        self._init_port_channel(469, 3)
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_vPC_ports())
        self._init_port_channel(470, 3)

    def test_replay_unique_vPC_ports_and_vm(self):
        self._init_port_channel(470, 3)
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_vPC_ports_and_vm())

    def test_replay_unique_vPC_ports_chg_vPC_nbr(self):
        self._init_port_channel(469, 3)
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_vPC_ports_chg_vPC_nbr())
        self._init_port_channel(470, 3)

    def test_replay_unique_vPC_ports_chg_to_enet(self):
        self._init_port_channel(469, 3)
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_vPC_ports_chg_to_enet())
        self._init_port_channel(470, 3)

    def test_replay_automated_port_channel_w_user_cfg(self):
        """Basic replay of auto-port-channel creation with user config."""

        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect2}
        self.mock_ncclient.configure_mock(**data_json)

        switch_list = ['1.1.1.1', '2.2.2.2']

        for switch_ip in switch_list:
            cfg.CONF.set_override(
                const.VPCPOOL, ('1001-1025'),
                cfg.CONF.ml2_cisco.nexus_switches.get(switch_ip)._group)
        self._cisco_mech_driver._initialize_vpc_alloc_pools()

        self._cfg_vPC_user_commands(
            switch_list, "spanning-tree port type edge trunk;no lacp "
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

        for switch_ip in switch_list:
            self.assertEqual(
                25, len(nxos_db.get_free_switch_vpc_allocs(switch_ip)))

    def test_replay_automated_vPC_ports_and_vm(self):
        """Provides replay data and result data for unique ports. """

        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect2}
        self.mock_ncclient.configure_mock(**data_json)

        switch_list = ['1.1.1.1', '2.2.2.2']

        for switch_ip in switch_list:
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

        for switch_ip in switch_list:
            self.assertEqual(
                25, len(nxos_db.get_free_switch_vpc_allocs(switch_ip)))


#The tests in class below is reproduced this is does not apply to restapis.
#class TestCiscoNexusNonCachedSshReplay(
#    test_cisco_nexus_base.TestCiscoNexusReplayBase):
