# Copyright (c) 2017 Cisco Systems, Inc.
# All rights reserved.
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

"""
Basic Test Classes using RESTAPI Driver to test Cisco Nexus platforms.

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
    test_cisco_nexus_events)


class TestCiscoNexusRestDeviceResults(base.TestCiscoNexusBaseResults):

    """Unit tests driver results for Cisco ML2 Nexus."""

    test_results = {
        'duplicate_add_port_driver_result': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST]
        ],
        'duplicate_del_port_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],
        'add_port2_driver_result': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+265')),
             base.POST]
        ],
        'delete_port2_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],
        'add_port2_driver_result2': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST]
        ],
        'delete_port2_driver_result2': [
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-267')),
             base.POST]
        ],
        'add_port2_driver_result3': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_VLAN_ADD % 268),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '+268')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_VLAN_ADD % 268),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '+268')),
             base.POST]
        ],
        'delete_port2_driver_result3': [
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '-268')),
             base.POST],
            [(snipp.PATH_VLAN % '268'),
             base.NEXUS_IP_ADDRESS_6,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '-268')),
             base.POST],
            [(snipp.PATH_VLAN % '268'),
             base.NEXUS_IP_ADDRESS_7,
             '',
             base.DELETE]
        ],
        'add_port_channel_driver_result': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 268),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '+268')),
             base.POST]
        ],
        'delete_port_channel_driver_result': [
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '-268')),
             base.POST],
            [(snipp.PATH_VLAN % '268'),
             base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE]
        ],
        'dual_add_port_driver_result': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_VLAN_ADD % 269),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+269')),
             base.POST],
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_VLAN_ADD % 269),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '+269')),
             base.POST]
        ],
        'dual_delete_port_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-269')),
             base.POST],
            [(snipp.PATH_VLAN % '269'),
             base.NEXUS_IP_ADDRESS_DUAL,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '-269')),
             base.POST],
        ],
        'add_port_driver_result': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST]
        ],
        'del_port_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_8,
             '',
             base.DELETE]
        ],
        'migrate_add_host2_driver_result': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST]
        ],
    }


class TestCiscoNexusRestDevice(test_cisco_nexus_events.TestCiscoNexusDevice):

    """Unit tests for Cisco ML2 Nexus restapi device driver"""

    def setUp(self):
        cfg.CONF.set_override('nexus_driver', 'restapi', 'ml2_cisco')
        super(TestCiscoNexusRestDevice, self).setUp()
        self.results = TestCiscoNexusRestDeviceResults()

    def test_create_delete_duplicate_ports(self):
        (super(TestCiscoNexusRestDevice, self).
            test_create_delete_duplicate_ports())

    def test_create_delete_duplicate_port_transaction(self):
        (super(TestCiscoNexusRestDevice, self).
            test_create_delete_duplicate_port_transaction())

    def test_create_delete_same_switch_diff_hosts_diff_vlan(self):
        (super(TestCiscoNexusRestDevice, self).
            test_create_delete_same_switch_diff_hosts_diff_vlan())

    def test_create_delete_same_switch_diff_hosts_same_vlan(self):
        (super(TestCiscoNexusRestDevice, self).
            test_create_delete_same_switch_diff_hosts_same_vlan())

    def test_create_delete_diff_switch_same_host(self):
        (super(TestCiscoNexusRestDevice, self).
            test_create_delete_diff_switch_same_host())

    def test_create_delete_portchannel(self):
        super(TestCiscoNexusRestDevice, self).test_create_delete_portchannel()

    def test_create_delete_dual(self):
        super(TestCiscoNexusRestDevice, self).test_create_delete_dual()

    def test_create_delete_dhcp(self):
        super(TestCiscoNexusRestDevice, self).test_create_delete_dhcp()

    def test_create_delete_router_ha_intf(self):
        (super(TestCiscoNexusRestDevice, self).
            test_create_delete_router_ha_intf())

    def test_nexus_vm_migration(self):
        super(TestCiscoNexusRestDevice, self).test_nexus_vm_migration()


class TestCiscoNexusRestInitResults(base.TestCiscoNexusBaseResults):

    """Unit tests driver results for Cisco ML2 Nexus."""

    test_results = {
        # set 1 - switch 1.1.1.1 sets eth 1/10 & 1/20 to None
        # set 2 - switch 8.8.8.8 sets eth 1/10 & 1/20 to None
        # set 3 - switch 4.4.4.4 sets eth 1/3 & portchannel 2 to None
        # set 4 - switch 2.2.2.2 sets portchannel 2 to None
        # set 5 - switch 6.6.6.6 sets portchannel 2 to None
        # set 6 - switch 7.7.7.7 sets portchannel 2 to None
        'duplicate_init_port_driver_result1': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '')),
             base.POST],

            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '')),
             base.POST],

            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '')),
             base.POST],

            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '')),
             base.POST],

            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '')),
             base.POST],

            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '')),
             base.POST],

            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '')),
             base.POST],

            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '')),
             base.POST],

            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '')),
             base.POST],

            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '')),
             base.POST],

        ],

    }

GET_INTERFACE_NO_TRUNK_RESPONSE = {
    "totalCount": "1",
    "imdata": [
        {
            "l1PhysIf": {
                "attributes": {
                    "trunkVlans": "1-4094"
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


# Skipped inheriting event class TestCiscoNexusDeviceFailure
# since some tests are generic and need not be executed twice
# and some apply only to SSH driver.

class TestCiscoNexusRestDeviceInit(
    test_cisco_nexus_events.TestCiscoNexusDeviceInit):
    """Verifies interface vlan allowed none is set when missing."""

    def get_init_side_effect(
        self, action, ipaddr=None, body=None, headers=None):

        eth_path = 'api/mo/sys/intf/phys-'
        port_chan_path = 'api/mo/sys/intf/aggr-'

        if action == snipp.PATH_GET_NEXUS_TYPE:
            return base.GET_NEXUS_TYPE_RESPONSE
        elif action in snipp.PATH_GET_PC_MEMBERS:
            return base.GET_NO_PORT_CH_RESPONSE
        elif eth_path in action:
            return GET_INTERFACE_NO_TRUNK_RESPONSE
        elif port_chan_path in action:
            return GET_INTERFACE_PCHAN_NO_TRUNK_RESPONSE

        return {}

    def restapi_mock_init(self):

        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.

        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect}
        self.mock_ncclient.configure_mock(**data_json)

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('nexus_driver', 'restapi', 'ml2_cisco')
        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusRestDeviceInit, self).setUp()
        self.results = TestCiscoNexusRestInitResults()

    def test_verify_initialization(self):
        self._verify_results(
            self.results.get_test_results(
                'duplicate_init_port_driver_result1'))


class TestCiscoNexusRestBaremetalResults(base.TestCiscoNexusBaseResults):

    """Unit tests driver results for Cisco ML2 Nexus."""

    test_results = {

        'add_port_ethernet_driver_result': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '+267')),
             base.POST]
        ],

        'delete_port_ethernet_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'add_port_channel_driver_result': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '+267')),
             base.POST]
        ],

        'delete_port_channel_driver_result': [
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'add_port_ethernet_native_driver_result': [
            [snipp.PATH_VLAN_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '+265', 'vlan-265')),
             base.POST]
        ],

        'delete_port_ethernet_native_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '-265', '')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

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


class TestCiscoNexusRestBaremetalDevice(
    test_cisco_nexus_events.TestCiscoNexusBaremetalDevice):

    """Tests for Cisco ML2 Nexus baremetal RESTAPI device driver."""

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

    def _init_port_channel(self):

        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.

        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect}
        self.mock_ncclient.configure_mock(**data_json)

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('nexus_driver', 'restapi', 'ml2_cisco')
        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusRestBaremetalDevice, self).setUp()
        self.results = TestCiscoNexusRestBaremetalResults()

    def test_create_delete_basic_ethernet_port(self):
        (super(TestCiscoNexusRestBaremetalDevice, self).
            test_create_delete_basic_ethernet_port())

    def test_create_delete_basic_port_channel(self):
        (super(TestCiscoNexusRestBaremetalDevice, self).
            test_create_delete_basic_port_channel())

    def test_create_delete_basic_eth_port_is_native(self):
        (super(TestCiscoNexusRestBaremetalDevice, self).
            test_create_delete_basic_eth_port_is_native())

    def test_create_delete_switch_ip_not_defined(self):
        (super(TestCiscoNexusRestBaremetalDevice, self).
            test_create_delete_switch_ip_not_defined())


# Skipped inheriting event class TestCiscoNexusNonCacheSshDevice
# since it does not apply to REST API
