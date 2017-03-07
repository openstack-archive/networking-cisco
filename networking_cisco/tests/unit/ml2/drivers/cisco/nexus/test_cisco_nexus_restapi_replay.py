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


from oslo_config import cfg

from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_restapi_snippets as snipp)
from networking_cisco.tests.unit.ml2.drivers.cisco.nexus import (
    test_cisco_nexus_base as base)
from networking_cisco.tests.unit.ml2.drivers.cisco.nexus import (
    test_cisco_nexus_replay)


class TestCiscoNexusRestReplayResults(base.TestCiscoNexusBaseResults):

    """Unit tests driver results for Cisco ML2 Nexus."""

    test_results = {

        'driver_result_unique_init': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '')),
             base.POST],
        ],

        'driver_result_unique_add1': [
            [snipp.PATH_VLAN_ALL,
             None,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             None,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST]
        ],

        'driver_result_unique_add2': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+265')),
             base.POST]
        ],

        'driver_result_unique_del1': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_del2': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             None,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             None,
             '',
             base.DELETE]
        ],

        'driver_result_unique_2vlan_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+265,267')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                  snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]
        ],

        'dupl_vlan_result1_add': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST]
        ],

        'dupl_vlan_result2_add': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST]
        ],

        'dupl_vlan_result2_del': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-267')),
             base.POST]
        ],

        'dupl_vlan_result_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
        ],

        'dupl_port_result_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_3,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_3,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
        ],

        'switch_up_result_add': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_VLAN_ADD % 269),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+269')),
             base.POST]
        ],

        'switch_up_result_del': [
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-269')),
             base.POST],
            [(snipp.PATH_VLAN % '269'),
             base.NEXUS_IP_ADDRESS_DUAL,
             '',
             base.DELETE]
        ],

        'switch_restore_result_add': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_VLAN_ADD % 269),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+269')),
             base.POST]
        ],

        'switch_restore_result_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/2]'),
             base.NEXUS_IP_ADDRESS_DUAL2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+269')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_DUAL2,
             (snipp.BODY_VLAN_ADD % 269),
             base.POST]
        ],

        'switch_restore_result_del': [
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-269')),
             base.POST],
            [(snipp.PATH_VLAN % '269'),
             base.NEXUS_IP_ADDRESS_DUAL,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'phys-[eth1/2]'),
             base.NEXUS_IP_ADDRESS_DUAL2,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-269')),
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

        cfg.CONF.set_override('nexus_driver', 'restapi', 'ml2_cisco')
        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusRestReplay, self).setUp()
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
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '')),
             base.POST],
        ],

        'driver_result_unique_eth_add1': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST]
        ],

        'driver_result_unique_eth_add2': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+265')),
             base.POST]
        ],

        'driver_result_unique_eth_del1': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_eth_del2': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_vPC_init': [
            [(snipp.PATH_IF % 'aggr--[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '')),
             base.POST],
        ],

        'driver_result_unique_vPC_add1': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '+267')),
             base.POST]
        ],

        'driver_result_unique_vPC_add2': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '+265')),
             base.POST]
        ],

        'driver_result_unique_vPC_del1': [
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_vPC_del2': [
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_native_port_ethernet_add': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '+265', 'vlan-265')),
             base.POST]
        ],

        'driver_result_unique_native_port_ethernet_del': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '-265', '')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_2vlan_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+265,267')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                 snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]
        ],

        'driver_result_unique_2vlan_vpc_replay': [
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '+265,267')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                 snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]
        ],

        'driver_result_unique_vPC470_del1': [
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_vPC470_del2': [
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_vPC470_2vlan_replay': [
            [(snipp.PATH_IF % 'aggr-[po470]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '+265,267')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                  snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]
        ],

        'driver_result_unique_2vlan_vpc_enchg_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+265,267')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                  snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]
        ],

        'driver_result_unique_native_2vlan_replay': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '+265', 'vlan-265')),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+265,267')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD_START % 265) + (
                  snipp.BODY_VLAN_ADD_NEXT % 267) + snipp.BODY_VLAN_ALL_END,
             base.POST]
        ]

    }


GET_PORT_CH_RESPONSE = {
    "totalCount": "3",
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

    def _init_port_channel(self, ch_grp):

        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.

        GET_PORT_CH_RESPONSE['imdata'][1]['pcRsMbrIfs'][
            'attributes']['parentSKey'] = ('po' + str(ch_grp))
        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect}
        self.mock_ncclient.configure_mock(**data_json)

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('nexus_driver', 'restapi', 'ml2_cisco')
        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusRestBaremetalReplay, self).setUp()
        self.results = TestCiscoNexusRestBaremetalReplayResults()

    def test_replay_unique_ethernet_ports(self):
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_ethernet_ports())

    def test_replay_unique_vPC_ports(self):
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_vPC_ports())

    def test_replay_unique_vPC_ports_chg_vPC_nbr(self):
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_vPC_ports_chg_vPC_nbr())

    def test_replay_unique_vPC_ports_chg_to_enet(self):
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_vPC_ports_chg_to_enet())

    def test_replay_unique_native_nonnative_ethernet_ports(self):
        (super(TestCiscoNexusRestBaremetalReplay, self).
            test_replay_unique_native_nonnative_ethernet_ports())


#The tests in class below is reproduced this is does not apply to restapis.
#class TestCiscoNexusNonCachedSshReplay(
#    test_cisco_nexus_base.TestCiscoNexusReplayBase):
