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

from networking_cisco.backwards_compatibility import constants as cb_constants
from networking_cisco.ml2_drivers.nexus import (
    constants as const)
from networking_cisco.ml2_drivers.nexus import (
    nexus_db_v2 as nxos_db)
from networking_cisco.ml2_drivers.nexus import (
    nexus_restapi_snippets as snipp)
from networking_cisco.ml2_drivers.nexus import exceptions

from networking_cisco.tests.unit.ml2_drivers.nexus import (
    test_cisco_nexus_base as base)

CONNECT_ERROR = 'Unable to connect to Nexus'


class TestCiscoNexusDeviceConfig(object):

    """Unit tests Config for Cisco ML2 Nexus device driver."""

    test_configs = {
        'test_config1':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                base.HOST_NAME_1,
                base.NEXUS_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config2':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                base.HOST_NAME_2,
                base.NEXUS_PORT_2,
                base.INSTANCE_2,
                base.VLAN_ID_2,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config3':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                base.HOST_NAME_1,
                base.NEXUS_PORT_1,
                base.INSTANCE_2,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config4':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_8,
                base.HOST_NAME_4,
                base.NEXUS_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config5':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_8,
                base.HOST_NAME_5,
                base.NEXUS_PORT_2,
                base.INSTANCE_2,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config_portchannel':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_2,
                base.HOST_NAME_PC,
                base.NEXUS_PORTCHANNELS,
                base.INSTANCE_PC,
                base.VLAN_ID_PC,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config_dual':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_DUAL,
                base.HOST_NAME_DUAL,
                base.NEXUS_DUAL,
                base.INSTANCE_DUAL,
                base.VLAN_ID_DUAL,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config_dhcp':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                base.HOST_NAME_1,
                base.NEXUS_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_DHCP,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config_router_ha_intf':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                base.HOST_NAME_1,
                base.NEXUS_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_ROUTER_HA_INTF,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config_router_intf':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                base.HOST_NAME_1,
                base.NEXUS_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_ROUTER_INTF,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config_router_gw':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                base.HOST_NAME_1,
                base.NEXUS_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_ROUTER_GW,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config_portchannel2':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_6,
                base.HOST_NAME_3,
                base.NEXUS_PORTCHANNELS,
                base.INSTANCE_PC,
                base.VLAN_ID_PC,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config_portchannel3':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_7,
                base.HOST_NAME_3,
                base.NEXUS_PORTCHANNELS,
                base.INSTANCE_PC,
                base.VLAN_ID_PC,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
        'test_config_migrate':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_3,
                base.HOST_NAME_6,
                base.NEXUS_PORT_2,
                base.INSTANCE_1,
                base.VLAN_ID_1,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_COMPUTE,
                {},
                None,
                base.NORMAL_VNIC),
    }

    test_configs = collections.OrderedDict(sorted(test_configs.items()))


class TestCiscoNexusDeviceResults(
    base.TestCiscoNexusBaseResults):

    """Unit tests driver results for Cisco ML2 Nexus."""

    test_results = {

        'duplicate_add_port_driver_result': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],
        'duplicate_del_port_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],
        'add_port2_driver_result': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+265')),
             base.POST]
        ],

        'delete_port2_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],
        'add_port2_driver_result2': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],
        'delete_port2_driver_result2': [
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST]
        ],
        'add_port2_driver_result3': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_VLAN_ADD % 268),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+268')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_VLAN_ADD % 268),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+268')),
             base.POST]
        ],

        'delete_port2_driver_result3': [
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-268')),
             base.POST],
            [(snipp.PATH_VLAN % '268'),
             base.NEXUS_IP_ADDRESS_6,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-268')),
             base.POST],
            [(snipp.PATH_VLAN % '268'),
             base.NEXUS_IP_ADDRESS_7,
             '',
             base.DELETE]
        ],
        'add_port_channel_driver_result': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 268),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+268')),
             base.POST]
        ],
        'delete_port_channel_driver_result': [
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-268')),
             base.POST],
            [(snipp.PATH_VLAN % '268'),
             base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE]
        ],
        'dual_add_port_driver_result': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_VLAN_ADD % 269),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+269')),
            base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_VLAN_ADD % 269),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+269')),
             base.POST]
        ],
        'dual_delete_port_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-269')),
             base.POST],
            [(snipp.PATH_VLAN % '269'),
             base.NEXUS_IP_ADDRESS_DUAL,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-269')),
             base.POST],
        ],
        'add_port_driver_result': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],
        'del_port_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_8,
             '',
             base.DELETE]
        ],
        'migrate_add_host2_driver_result': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_3,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_3,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],
    }


class TestCiscoNexusDevice(base.TestCiscoNexusBase,
                           TestCiscoNexusDeviceConfig,
                           TestCiscoNexusDeviceResults):

    """Unit tests for Cisco ML2 Nexus device driver."""

    def setUp(self):
        """Sets up mock driver, and switch and credentials dictionaries."""

        cfg.CONF.set_override('switch_heartbeat_time', 0, 'ml2_cisco')
        super(TestCiscoNexusDevice, self).setUp()
        self.mock_driver.reset_mock()
        self.results = TestCiscoNexusDeviceResults()

    def test_create_delete_duplicate_ports(self):
        """Tests creation and deletion of two new virtual Ports."""

        self._basic_create_verify_port_vlan(
            'test_config1',
            self.results.get_test_results('duplicate_add_port_driver_result')
        )

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
        bindings = nxos_db.get_nexusvlan_binding(
                       base.VLAN_ID_1,
                       base.NEXUS_IP_ADDRESS_1)
        self.assertEqual(2, len(bindings))

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        # For results, pass empty list to verify no nexus action on
        # first port removal.
        self._basic_delete_verify_port_vlan(
            'test_config1',
            [], nbr_of_bindings=1)

        self._basic_delete_verify_port_vlan(
            'test_config3',
            self.results.get_test_results('duplicate_del_port_driver_result'))

    def test_create_delete_duplicate_port_transaction(self):
        """Tests creation and deletion same port transaction."""

        self._basic_create_verify_port_vlan(
            'test_config1',
            self.results.get_test_results('duplicate_add_port_driver_result')
        )

        self.assertEqual(
            1, len(nxos_db.get_nexusport_switch_bindings(
                   base.NEXUS_IP_ADDRESS_1)))

        self._create_port(
            self.test_configs['test_config1'])
        self._verify_results(
            self.results.get_test_results('duplicate_add_port_driver_result')
        )

        self.assertEqual(
            1, len(nxos_db.get_nexusport_switch_bindings(
                   base.NEXUS_IP_ADDRESS_1)))

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_config1',
            self.results.get_test_results('duplicate_del_port_driver_result'),
            nbr_of_bindings=0)

        self._basic_delete_verify_port_vlan(
            'test_config1',
            self.results.get_test_results('duplicate_del_port_driver_result'))

    def test_create_delete_same_switch_diff_hosts_diff_vlan(self):
        """Test create/delete two Ports, same switch/diff host & vlan."""

        self._basic_create_verify_port_vlan(
            'test_config1',
            self.results.get_test_results('duplicate_add_port_driver_result'))

        self._create_port(
            self.test_configs['test_config2'])
        self._verify_results(
            self.results.get_test_results('add_port2_driver_result'))

        # Verify there are 2 port configs
        bindings = nxos_db.get_nexusport_switch_bindings(
                       base.NEXUS_IP_ADDRESS_1)
        self.assertEqual(2, len(bindings))

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_config2',
            self.results.get_test_results('delete_port2_driver_result'),
            nbr_of_bindings=1)

        self._basic_delete_verify_port_vlan(
            'test_config1',
            self.results.get_test_results('duplicate_del_port_driver_result'))

    def test_create_delete_same_switch_diff_hosts_same_vlan(self):
        """Test create/delete two Ports, same switch & vlan/diff host."""

        self._basic_create_verify_port_vlan(
            'test_config4',
            self.results.get_test_results('add_port_driver_result'))

        self._create_port(
            self.test_configs['test_config5'])
        self._verify_results(
            self.results.get_test_results('add_port2_driver_result2'))

        # Verify there are 2 port configs
        bindings = nxos_db.get_nexusport_switch_bindings(
                       base.NEXUS_IP_ADDRESS_8)
        self.assertEqual(2, len(bindings))

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_config5',
            self.results.get_test_results('delete_port2_driver_result2'),
            nbr_of_bindings=1)

        self._basic_delete_verify_port_vlan(
            'test_config4',
            self.results.get_test_results('del_port_driver_result'))

    def test_create_delete_diff_switch_same_host(self):
        """Test create/delete of two Ports, diff switch/same host."""

        self._basic_create_verify_port_vlan(
            'test_config_portchannel2',
            self.results.get_test_results('add_port2_driver_result3'))

        # Verify there are 2 port configs. One per switch.
        bindings = nxos_db.get_nexusport_switch_bindings(
                       base.NEXUS_IP_ADDRESS_6)
        self.assertEqual(1, len(bindings))
        bindings = nxos_db.get_nexusport_switch_bindings(
                       base.NEXUS_IP_ADDRESS_7)
        self.assertEqual(1, len(bindings))

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        # For results, pass empty list to verify no nexus action on
        # first port removal.
        self._basic_delete_verify_port_vlan(
            'test_config_portchannel2',
            self.results.get_test_results('delete_port2_driver_result3'))

    def test_create_delete_portchannel(self):
        """Tests creation of a port over a portchannel."""

        self._create_delete_port(
            'test_config_portchannel',
            self.results.get_test_results('add_port_channel_driver_result'),
            self.results.get_test_results('delete_port_channel_driver_result'))

    def test_create_delete_dual(self):
        """Tests creation and deletion of dual ports for single server"""

        self._basic_create_verify_port_vlan(
            'test_config_dual',
            self.results.get_test_results('dual_add_port_driver_result'),
            nbr_of_bindings=2)

        self._basic_delete_verify_port_vlan(
            'test_config_dual',
            self.results.get_test_results('dual_delete_port_driver_result'))

    def test_create_delete_dhcp(self):
        """Tests creation and deletion of ports with device_owner of dhcp."""

        self._create_delete_port(
            'test_config_dhcp',
            self.results.get_test_results('duplicate_add_port_driver_result'),
            self.results.get_test_results('duplicate_del_port_driver_result'))

    def test_create_delete_router_ha_intf(self):
        """Tests creation and deletion of ports with device_owner
        of router_ha_interface.
        """

        self._create_delete_port(
            'test_config_router_ha_intf',
            self.results.get_test_results('duplicate_add_port_driver_result'),
            self.results.get_test_results('duplicate_del_port_driver_result'))

    def test_create_delete_router_intf(self):
        """Tests creation and deletion of ports with device_owner
        of router_interface.
        """

        self._create_delete_port(
            'test_config_router_intf',
            self.results.get_test_results('duplicate_add_port_driver_result'),
            self.results.get_test_results('duplicate_del_port_driver_result'))

    def test_create_delete_router_gateway(self):
        """Tests creation and deletion of ports with device_owner
        of router_gateway.
        """

        self._create_delete_port(
            'test_config_router_gw',
            self.results.get_test_results('duplicate_add_port_driver_result'),
            self.results.get_test_results('duplicate_del_port_driver_result'))

    def test_nexus_vm_migration(self):
        """Verify VM (live) migration.

        Simulate the following:
        Nova informs neutron of live-migration with port-update(new host).
        This should trigger two update_port_pre/postcommit() calls.

        The first one should only change the current host_id and remove the
        binding resulting in the mechanism drivers receiving:

        * PortContext.original['binding:host_id']: previous value
        * PortContext.original_top_bound_segment: previous value
        * PortContext.current['binding:host_id']: current (new) value
        * PortContext.top_bound_segment: None

        The second one binds the new host resulting in the mechanism
        drivers receiving:

        * PortContext.original['binding:host_id']: previous value
        * PortContext.original_top_bound_segment: None
        * PortContext.current['binding:host_id']: previous value
        * PortContext.top_bound_segment: new value
        """

        self._basic_create_verify_port_vlan(
            'test_config1',
            self.results.get_test_results('duplicate_add_port_driver_result'))
        binding = nxos_db.get_nexusvm_bindings(
            base.VLAN_ID_1,
            base.INSTANCE_1)[0]
        self.assertEqual(
            base.NEXUS_PORT_1,
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
            base.NETID)

        self._cisco_mech_driver.create_port_postcommit(port_context)
        self._cisco_mech_driver.update_port_precommit(port_context)
        self._cisco_mech_driver.update_port_postcommit(port_context)

        # Verify that port entry has been deleted.
        self.assertRaises(
            exceptions.NexusPortBindingNotFound,
            nxos_db.get_nexusvm_bindings,
            base.VLAN_ID_1,
            base.INSTANCE_1)

        # Clean all the driver mock_calls to clear exception
        # and other mock_call history.
        self.mock_driver.reset_mock()

        self._basic_create_verify_port_vlan(
            'test_config_migrate',
            self.results.get_test_results('migrate_add_host2_driver_result'))

        # Verify that port entry has been added using new host name.
        # Use port_id to verify that 2nd host name was used.
        binding = nxos_db.get_nexusvm_bindings(
            base.VLAN_ID_1,
            base.INSTANCE_1)[0]
        self.assertEqual(
            base.NEXUS_PORT_2,
            binding.port_id)

    def test_update_postcommit_port_not_found(self):

        port_config = self.test_configs['test_config2']
        port_context = self._generate_port_context(
            port_config, override_netid=None)

        # An exception should not be raised during update.
        self._cisco_mech_driver.update_port_postcommit(port_context)

        # Nothing should have been sent
        self._verify_results([])

        # No port bindings should exist
        self.assertRaises(exceptions.NexusPortBindingNotFound,
            nxos_db.get_nexusport_switch_bindings,
                base.NEXUS_IP_ADDRESS_1)


class TestCiscoNexusDeviceFailure(base.TestCiscoNexusBase,
                           TestCiscoNexusDeviceConfig,
                           TestCiscoNexusDeviceResults):

    """Negative Unit tests for Cisco ML2 Nexus device driver."""

    def setUp(self):
        """Sets up mock driver, and switch and credentials dictionaries."""

        cfg.CONF.set_override('switch_heartbeat_time', 0, 'ml2_cisco')
        super(TestCiscoNexusDeviceFailure, self).setUp()
        self.mock_driver.reset_mock()
        self.results = TestCiscoNexusDeviceResults()

    def test_connect_failure(self):
        """Verifies exception handling during driver connect. """

        # Clean all the driver mock_calls to clear exception
        # and other mock_call history.
        self.mock_driver.reset_mock()

        data_json = {'rest_get.side_effect':
                    exceptions.NexusConnectFailed(
                        nexus_host=base.NEXUS_IP_ADDRESS_1,
                        exc='error')}
        self.mock_driver.configure_mock(**data_json)

        e = self.assertRaises(exceptions.NexusConnectFailed,
                              self._create_port,
                              self.test_configs[
                                  'test_config1'])
        self.assertIn(CONNECT_ERROR, six.u(str(e)))
        self.assertEqual(1, self.mock_driver.rest_get.call_count)

    def test_fail_on_connect_other_exceptions(self):
        """Test other errors during connect() sequences are still handled."""

        # Clear connect_call_count
        self.mock_driver.reset_mock()

        err_strings = ['This is TypeError',
                       'This is IOError',
                       'This is AttributeError']
        except_errors = [TypeError(err_strings[0]),
                        IOError(err_strings[1]),
                        AttributeError(err_strings[2])]
        call_count = 0
        for errors in except_errors:
            config = {'rest_get.side_effect':
                     exceptions.NexusConnectFailed(
                         nexus_host=base.NEXUS_IP_ADDRESS_1,
                         exc=errors)}
            self.mock_driver.configure_mock(**config)
            port_context = self._generate_port_context(
                self.test_configs['test_config1'])

            e = self.assertRaises(
                exceptions.NexusConnectFailed,
                self._cisco_mech_driver.create_port_postcommit,
                port_context)
            self.assertIn(
                "Create Failed: Port event can not "
                "be processed at this time.", six.u(str(e)))

            config = {'rest_post.side_effect':
                     exceptions.NexusConnectFailed(
                         nexus_host=base.NEXUS_IP_ADDRESS_1,
                         exc=errors)}
            self.mock_driver.configure_mock(**config)
            self._cisco_mech_driver.update_port_precommit(port_context)
            e = self.assertRaises(
                exceptions.NexusConnectFailed,
                self._cisco_mech_driver.update_port_postcommit,
                port_context)
            self.assertIn(err_strings[call_count], six.u(str(e)))

            config = {'rest_delete.side_effect':
                     exceptions.NexusConnectFailed(
                         nexus_host=base.NEXUS_IP_ADDRESS_1,
                         exc=errors)}
            self.mock_driver.configure_mock(**config)
            self._cisco_mech_driver.delete_port_precommit(port_context)
            e = self.assertRaises(
                exceptions.NexusConnectFailed,
                self._cisco_mech_driver.delete_port_postcommit,
                port_context)
            self.assertIn(err_strings[call_count], six.u(str(e)))

            call_count += 1
            self.assertEqual(
                call_count * 3,
                (self.mock_driver.rest_post.call_count +
                self.mock_driver.rest_get.call_count +
                self.mock_driver.rest_delete.call_count))

    def test_get_nexus_type_failure(self):
        """Verifies exception during get nexus type. """

        self._create_port_failure(
            'rest_get.side_effect',
            snipp.PATH_GET_NEXUS_TYPE,
            'test_config1',
            'Create Failed:',
            which_exc=exceptions.NexusConnectFailed)

        # Verify we attempt to connect once. get_nexus_type is a
        # special case since replay code will retry
        self.assertEqual(1, self.mock_driver.rest_get.call_count)

    def test_create_vlan_failure(self):
        """Verifies exception during edit vlan create driver. """

        self._create_port_failure(
            'rest_post.side_effect',
            '"fabEncap": "vlan-267"',
            'test_config1',
            __name__,
            which_exc=exceptions.NexusConnectFailed)

        self.assertEqual(1, self.mock_driver.rest_post.call_count)

    def test_delete_vlan_failure(self):
        """Verifies exception during edit vlan delete driver. """

        self._delete_port_failure(
            'rest_delete.side_effect',
            'api/mo/sys/bd/bd-[vlan-267].json',
            'test_config1',
            __name__)

    def test_create_trunk_failure(self):
        """Verifies exception during create trunk interface driver. """

        self._create_port_failure(
            'rest_post.side_effect',
            '{"l1PhysIf": {"attributes": { "trunkVlans": "+267"}}}',
            'test_config1',
            __name__)

    def test_delete_trunk_failure(self):
        """Verifies exception during delete trunk interface driver. """

        self._delete_port_failure(
            'rest_post.side_effect',
            '{"l1PhysIf": {"attributes": { "trunkVlans": "-267"}}}',
            'test_config1',
            __name__)

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

        self.mock_driver.reset_mock()
        port_context = self._generate_port_context(
            self.test_configs['test_config1'],
            override_host_name='no_host')

        for test_func in test_func_list:
            test_func(port_context)
            self.assertRaises(
                 exceptions.NexusPortBindingNotFound,
                 nxos_db.get_nexusport_switch_bindings,
                 base.NEXUS_IP_ADDRESS_1)
            assert not self.mock_driver.connect.called

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

        network_context = base.FakeNetworkContext(
            0, cb_constants.TYPE_FLAT)
        port_config = self.test_configs['test_config1']
        port_context = base.FakePortContext(
            port_config.instance_id,
            port_config.host_name,
            port_config.device_owner,
            network_context, None,
            port_config.profile,
            port_config.vnic_type
        )

        # Clear out call_count changes during initialization activity
        self.mock_driver.reset_mock()
        for test_func in test_func_list:
            test_func(port_context)
            self.assertRaises(
                 exceptions.NexusPortBindingNotFound,
                 nxos_db.get_nexusport_switch_bindings,
                 base.NEXUS_IP_ADDRESS_1)
            assert not self.mock_driver.connect.called

    def test_nexus_missing_fields(self):
        """Test handling of a NexusMissingRequiredFields exception.

        Test the Cisco NexusMissingRequiredFields exception by using
        empty device_id value during port creation.
        """

        local_test_configs = {
            'test_config1':
                base.TestCiscoNexusBase.TestConfigObj(
                    base.NEXUS_IP_ADDRESS_1,
                    base.HOST_NAME_1,
                    base.NEXUS_PORT_1,
                    '',
                    base.VLAN_ID_1,
                    base.NO_VXLAN_ID,
                    None,
                    base.DEVICE_OWNER_COMPUTE,
                    {},
                    None,
                    base.NORMAL_VNIC),
        }

        # Clear out call_count changes during initialization activity
        self.mock_driver.reset_mock()
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

        network_context = base.FakeNetworkContext(
            0, cb_constants.TYPE_VLAN)
        network_context._network_segments = None
        port_config = self.test_configs['test_config1']
        port_context = base.FakePortContext(
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
        self.mock_driver.reset_mock()
        for test_func in test_func_list:
            test_func(port_context)
            self.assertRaises(
                 exceptions.NexusPortBindingNotFound,
                 nxos_db.get_nexusport_switch_bindings,
                 base.NEXUS_IP_ADDRESS_1)
            assert not self.mock_driver.connect.called


class TestCiscoNexusInitResults(
    base.TestCiscoNexusBaseResults):

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
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf',
                 snipp.BODY_PORT_CH_MODE, '')),
             base.POST],

            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf',
                 snipp.BODY_PORT_CH_MODE, '')),
             base.POST],

            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf',
                 snipp.BODY_PORT_CH_MODE, '')),
             base.POST],

            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_3,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf',
                 snipp.BODY_PORT_CH_MODE, '')),
             base.POST],

            [(snipp.PATH_IF % 'phys-[eth1/3]'),
            base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf',
                 snipp.BODY_PORT_CH_MODE, '')),
             base.POST],

            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_DUAL,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf',
                 snipp.BODY_PORT_CH_MODE, '')),
             base.POST],

            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf',
                 snipp.BODY_PORT_CH_MODE, '')),
             base.POST],

            [(snipp.PATH_IF % 'aggr-[po2]'),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf',
                 snipp.BODY_PORT_CH_MODE, '')),
             base.POST],

            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf',
                 snipp.BODY_PORT_CH_MODE, '')),
             base.POST],

            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf',
                 snipp.BODY_PORT_CH_MODE, '')),
             base.POST],

        ],
    }


class TestCiscoNexusDeviceInit(base.TestCiscoNexusBase,
                               TestCiscoNexusDeviceConfig):
    """Verifies interface vlan allowed none is set when missing."""

    def restapi_mock_init(self):

        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.

        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect}
        self.mock_driver.configure_mock(**data_json)

    def setUp(self):
        """Sets up mock driver, and switch and credentials dictionaries."""

        cfg.CONF.set_override('switch_heartbeat_time', 0, 'ml2_cisco')
        super(TestCiscoNexusDeviceInit, self).setUp()
        self.results = TestCiscoNexusInitResults()

    def test_verify_initialization(self):

        self._verify_results(
            self.results.get_test_results(
                'duplicate_init_port_driver_result1'))


class TestCiscoNexusBaremetalResults(
    base.TestCiscoNexusBaseResults):

    """Unit tests driver results for Cisco ML2 Nexus."""

    test_results = {

        'add_port_ethernet_driver_result': [
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

        'delete_port_ethernet_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'add_vm_port_ethernet_driver_result': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+265')),
             base.POST]
        ],

        'delete_vm_port_ethernet_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'add_port_channel_driver_result': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 267),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+267')),
             base.POST]
        ],

        'delete_port_channel_driver_result': [
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'add_port_ethernet_native_driver_result': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % (
                 'l1PhysIf', '', '+265', 'vlan-265')),
             base.POST]
        ],

        'delete_port_ethernet_native_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('l1PhysIf', '', '-265', '')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],

        'driver_result_unique_vPC_add1': [
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

        'driver_result_unique_vPC_del1': [
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('pcAggrIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_NATIVE_TRUNKVLAN % ('pcAggrIf', '', '-267', '')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE]
        ],


        'driver_result_unique_vPC_add1_vm': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+265')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_VLAN_ADD % 265),
             base.POST],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '+265')),
             base.POST]
        ],

        'driver_result_unique_vPC_del1_vm': [
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'aggr-[po469]'),
             base.NEXUS_IP_ADDRESS_2,
             (snipp.BODY_TRUNKVLAN % ('pcAggrIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_2,
             '',
             base.DELETE]
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

        'driver_result_unique_auto_vPC_inconsistency_failure': [
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
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_DEL_CH_GRP % ('1001', 'phys-[eth1/10]')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_DEL_PORT_CH % ('1001')),
             base.POST]
        ],

        'driver_result_unique_auto_vPC_add_usr_cmd_rest': [
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
             base.POST],
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
                    "parentSKey": "po470",
                    "tSKey": "eth1/20",
                }
            }
        }
    ]
}


class TestCiscoNexusBaremetalDevice(base.TestCiscoNexusBase):

    """Unit tests for Cisco ML2 Nexus baremetal device driver."""

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

    baremetal_profile_is_native = {
        "local_link_information": [
            {
                "port_id": base.NEXUS_BAREMETAL_PORT_1,
                "switch_info": {
                    "switch_ip": base.NEXUS_IP_ADDRESS_1,
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
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
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
        'test_config_vPC':
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
        'test_config_native':
            base.TestCiscoNexusBase.TestConfigObj(
                base.NEXUS_IP_ADDRESS_1,
                base.HOST_NAME_UNUSED,
                base.NEXUS_BAREMETAL_PORT_1,
                base.INSTANCE_1,
                base.VLAN_ID_2,
                base.NO_VXLAN_ID,
                None,
                base.DEVICE_OWNER_BAREMETAL,
                baremetal_profile_is_native,
                None,
                base.BAREMETAL_VNIC),
    }

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

    def _init_port_channel(self, which=1):

        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.

        GET_PORT_CH_RESPONSE['imdata'][which]['pcRsMbrIfs'][
            'attributes']['parentSKey'] = 'po469'
        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect}
        self.mock_driver.configure_mock(**data_json)

    def setUp(self):
        """Sets up mock driver, and switch and credentials dictionaries."""

        original_intersect = nxos_db._get_free_vpcids_on_switches

        def new_get_free_vpcids_on_switches(nexus_ips):
            intersect = list(original_intersect(nexus_ips))
            intersect.sort()
            return intersect

        mock.patch.object(nxos_db,
                         '_get_free_vpcids_on_switches',
                         new=new_get_free_vpcids_on_switches).start()

        cfg.CONF.set_override('switch_heartbeat_time', 0, 'ml2_cisco')
        super(TestCiscoNexusBaremetalDevice, self).setUp()
        self.results = TestCiscoNexusBaremetalResults()

    def test_create_delete_basic_bm_ethernet_port_and_vm(self):
        """Basic creation and deletion test of 1 ethernet port."""

        self._basic_create_verify_port_vlan(
            'test_config1',
            self.results.get_test_results(
                'add_port_ethernet_driver_result'))

        # Clean all driver mock_calls so we can evaluate next
        # set of results.
        self.mock_driver.reset_mock()

        self._basic_create_verify_port_vlan(
            'test_config_vm',
            self.results.get_test_results(
                'add_vm_port_ethernet_driver_result'),
            nbr_of_bindings=2)

        self._basic_delete_verify_port_vlan(
            'test_config_vm',
            self.results.get_test_results(
                'delete_vm_port_ethernet_driver_result'),
            nbr_of_bindings=1)

        self._basic_delete_verify_port_vlan(
            'test_config1',
            self.results.get_test_results(
                'delete_port_ethernet_driver_result'))

    def test_create_delete_basic_port_channel(self):
        """Basic creation and deletion test of 1 port-channel."""

        self._init_port_channel(3)
        self._basic_create_verify_port_vlan(
            'test_config_vPC',
            self.results.get_test_results(
                'driver_result_unique_vPC_add1'),
            nbr_of_bindings=2)

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_config_vPC',
            self.results.get_test_results(
                'driver_result_unique_vPC_del1'))

    def test_create_delete_learn_vpc_and_vm(self):
        """Basic creation and deletion test of 2 learn port-channel and vm."""

        self._init_port_channel(3)

        for switch_ip in base.SWITCH_LIST:
            cfg.CONF.set_override(
                const.VPCPOOL, ('451-475'),
                cfg.CONF.ml2_cisco.nexus_switches.get(switch_ip)._group)
        self._cisco_mech_driver._initialize_vpc_alloc_pools()

        self._basic_create_verify_port_vlan(
            'test_config_vPC',
            self.results.get_test_results(
                'driver_result_unique_vPC_add1'),
            nbr_of_bindings=2)

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        self._basic_create_verify_port_vlan(
            'test_config_vm',
            self.results.get_test_results(
                'driver_result_unique_vPC_add1_vm'),
            nbr_of_bindings=4)

        self._basic_delete_verify_port_vlan(
            'test_config_vm',
            self.results.get_test_results(
                'driver_result_unique_vPC_del1_vm'),
            nbr_of_bindings=2)

        self._basic_delete_verify_port_vlan(
            'test_config_vPC',
            self.results.get_test_results(
                'driver_result_unique_vPC_del1'))

        for switch_ip in base.SWITCH_LIST:
            self.assertEqual(
                25, len(nxos_db.get_free_switch_vpc_allocs(switch_ip)))

    def test_create_delete_basic_eth_port_is_native(self):
        """Basic creation and deletion test of 1 ethernet port."""

        self._basic_create_verify_port_vlan(
            'test_config_native',
            self.results.get_test_results(
                'add_port_ethernet_native_driver_result'))

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_config_native',
            self.results.get_test_results(
                'delete_port_ethernet_native_driver_result'))

    def test_create_delete_switch_ip_not_defined(self):
        """Create/delete of 1 ethernet port switchinfo is string."""

        baremetal_profile_no_switch_ip = {
            "local_link_information": [
                # This IP is configured at init time
                {
                    "port_id": base.NEXUS_BAREMETAL_PORT_1,
                    "switch_info": {
                        "switch_ip": "1.1.1.1",
                    },
                },
                # This IP not configured at init time
                {
                    "port_id": base.NEXUS_BAREMETAL_PORT_1,
                    "switch_info": {
                        "switch_ip": "6.6.6.6",
                    },
                },
            ]
        }

        local_test_configs = {
            'test_config1':
                base.TestCiscoNexusBase.TestConfigObj(
                    base.NEXUS_IP_ADDRESS_1,
                    base.HOST_NAME_UNUSED,
                    base.NEXUS_BAREMETAL_PORT_1,
                    base.INSTANCE_1,
                    base.VLAN_ID_1,
                    base.NO_VXLAN_ID,
                    None,
                    base.DEVICE_OWNER_BAREMETAL,
                    baremetal_profile_no_switch_ip,
                    base.HOST_NAME_Baremetal + '3',
                    base.BAREMETAL_VNIC),
        }

        self._basic_create_verify_port_vlan(
            '',
            self.results.get_test_results(
                'add_port_ethernet_driver_result'), 1,
            other_test=local_test_configs['test_config1'])

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        self._basic_delete_verify_port_vlan(
            '',
            self.results.get_test_results(
                'delete_port_ethernet_driver_result'),
            nbr_of_bindings=0,
            other_test=local_test_configs['test_config1'])

    def test_automated_port_channel_creation_deletion(self):
        """Basic creation and deletion test of 1 auto port-channel."""

        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect2}
        self.mock_driver.configure_mock(**data_json)

        for switch_ip in base.SWITCH_LIST:
            cfg.CONF.set_override(
                const.VPCPOOL, ('1001-1025, 1030'),
                cfg.CONF.ml2_cisco.nexus_switches.get(switch_ip)._group)
        self._cisco_mech_driver._initialize_vpc_alloc_pools()

        self._basic_create_verify_port_vlan(
            'test_config_vPC',
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_add1'),
            nbr_of_bindings=2)

        for switch_ip in base.SWITCH_LIST:
            self.assertEqual(
                25, len(nxos_db.get_free_switch_vpc_allocs(switch_ip)))

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_config_vPC',
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_del1'))

        for switch_ip in base.SWITCH_LIST:
            self.assertEqual(
                26, len(nxos_db.get_free_switch_vpc_allocs(switch_ip)))

    def test_create_delete_automated_vpc_and_vm(self):
        """Basic creation and deletion test of 2 auto port-channel and vm."""

        data_json = {'rest_get.side_effect':
                    self.get_init_side_effect2}
        self.mock_driver.configure_mock(**data_json)

        for switch_ip in base.SWITCH_LIST:
            cfg.CONF.set_override(
                const.VPCPOOL, ('1001-1025, 1030'),
                cfg.CONF.ml2_cisco.nexus_switches.get(switch_ip)._group)
        self._cisco_mech_driver._initialize_vpc_alloc_pools()

        self._basic_create_verify_port_vlan(
            'test_config_vPC',
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_add1'),
            nbr_of_bindings=2)

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        self._basic_create_verify_port_vlan(
            'test_config_vm',
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_vm_add1'),
            nbr_of_bindings=4)

        for switch_ip in base.SWITCH_LIST:
            self.assertEqual(
                25, len(nxos_db.get_free_switch_vpc_allocs(switch_ip)))

        self._basic_delete_verify_port_vlan(
            'test_config_vm',
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_vm_del1'),
            nbr_of_bindings=2)

        self._basic_delete_verify_port_vlan(
            'test_config_vPC',
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_del1'))

        for switch_ip in base.SWITCH_LIST:
            self.assertEqual(
                26, len(nxos_db.get_free_switch_vpc_allocs(switch_ip)))

    def test_automated_port_channel_w_user_cfg(self):
        """Basic creation and deletion test of 1 auto port-channel."""

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
            "spanning-tree port type edge trunk ;no lacp "
            "suspend-individual")

        self._basic_create_verify_port_vlan(
            'test_config_vPC',
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_add_usr_cmd_rest'),
            nbr_of_bindings=2)

        self._verify_nxapi_results(
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_add_usr_cmd_nxapi_cli'))

        # Clean all the driver mock_calls so we can evaluate
        # results of delete operations.
        self.mock_driver.reset_mock()

        self._basic_delete_verify_port_vlan(
            'test_config_vPC',
            self.results.get_test_results(
                'driver_result_unique_auto_vPC_del1'))

        for switch_ip in base.SWITCH_LIST:
            self.assertEqual(
                25, len(nxos_db.get_free_switch_vpc_allocs(switch_ip)))

    def test_failure_inconsistent_learned_chgrp(self):
        """Learning chgrp but different on both eth interfaces."""

        # Clean all the driver mock_calls to clear exception
        # and other mock_call history.
        self.mock_driver.reset_mock()

        LOCAL_GET_PORT_CH_RESPONSE = {
            "totalCount": "2",
            "imdata": [
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
                            "parentSKey": "po470",
                            "tSKey": "eth1/20",
                        }
                    }
                }
            ]
        }

        def local_get_init_side_effect(
            action, ipaddr=None, body=None, headers=None):

            if action == snipp.PATH_GET_NEXUS_TYPE:
                return base.GET_NEXUS_TYPE_RESPONSE
            elif action in snipp.PATH_GET_PC_MEMBERS:
                return LOCAL_GET_PORT_CH_RESPONSE
            elif base.ETH_PATH in action:
                return base.GET_INTERFACE_RESPONSE
            elif base.PORT_CHAN_PATH in action:
                return base.GET_INTERFACE_PCHAN_NO_TRUNK_RESPONSE

            return {}

        # Substitute init_port_channel() with the following
        # since this is a one time test scenario.
        data_json = {'rest_get.side_effect':
                    local_get_init_side_effect}
        self.mock_driver.configure_mock(**data_json)

        e = self.assertRaises(exceptions.NexusVPCLearnedNotConsistent,
                              self._create_port,
                              self.test_configs[
                                  'test_config_vPC'])
        x = six.u(str(e))
        self.assertIn("first interface 1.1.1.1, ethernet:1/10, vpc=469", x)
        self.assertIn("second interface 2.2.2.2, ethernet:1/20, vpc=470", x)

    def test_failure_inconsistent_new_chgrp(self):
        """Started as newly created chgrp but one if had chgrp configured."""

        # First interface Nexus returns there's no ch_grp
        # so treat as port-channel create.
        # Second interface Nexus returns ch_grp so so process
        # reset procedure which checks that .....
        #   - port-channel deleted from Nexus for first interface
        #   - ch_grp removed from Nexus on first interface
        #   - free-up vpcid allocated on first interface
        #   - raised cexc.NexusVPCExpectedNoChgrp

        LOCAL_GET_PORT_CH_RESPONSE = {
            "totalCount": "1",
            "imdata": [
                {
                    "pcRsMbrIfs": {
                        "attributes": {
                            "parentSKey": "po470",
                            "tSKey": "eth1/20",
                        }
                    }
                }
            ]
        }

        def local_get_init_side_effect(
            action, ipaddr=None, body=None, headers=None):

            if action == snipp.PATH_GET_NEXUS_TYPE:
                return base.GET_NEXUS_TYPE_RESPONSE
            elif action in snipp.PATH_GET_PC_MEMBERS:
                return LOCAL_GET_PORT_CH_RESPONSE
            elif base.ETH_PATH in action:
                return base.GET_INTERFACE_RESPONSE
            elif base.PORT_CHAN_PATH in action:
                return base.GET_INTERFACE_PCHAN_NO_TRUNK_RESPONSE

            return {}

        # Substitute init_port_channel() with the following
        # since this is a one time test scenario.
        data_json = {'rest_get.side_effect':
                    local_get_init_side_effect}
        self.mock_driver.configure_mock(**data_json)

        for switch_ip in base.SWITCH_LIST:
            nxos_db.init_vpc_entries(switch_ip,
                self._make_vpc_list(1001, 1025))
            allocs = nxos_db.get_free_switch_vpc_allocs(switch_ip)
            self.assertEqual(len(allocs), 25)

        e = self.assertRaises(exceptions.NexusVPCExpectedNoChgrp,
                              self._create_port,
                              self.test_configs[
                                  'test_config_vPC'])
        # Check that appropriate string in exception string
        x = six.u(str(e))
        self.assertIn("first interface 1.1.1.1, ethernet:1/10, vpc=None", x)
        self.assertIn("second interface 2.2.2.2, ethernet:1/20, vpc=470", x)

        # Verify vpcid initially allocated is now free
        for switch_ip in base.SWITCH_LIST:
            allocs = nxos_db.get_free_switch_vpc_allocs(switch_ip)
            self.assertEqual(len(allocs), 25)

        # Verify no attempt to create port-channels
        self._verify_results([])

    def test_vpcids_depleted_failure(self):
        """Verifies exception when failed to get vpcid."""

        # Clean all the driver mock_calls to clear exception
        # and other mock_call history.
        self.mock_driver.reset_mock()

        def new_alloc_vpcid(nexus_ip_list):
            return 0

        mock.patch.object(nxos_db,
                         'alloc_vpcid',
                          new=new_alloc_vpcid).start()
        e = self.assertRaises(exceptions.NexusVPCAllocFailure,
                              self._create_port,
                              self.test_configs[
                                  'test_config_vPC'])
        x = six.u(str(e))
        self.assertIn("switches=1.1.1.1,2.2.2.2", x)

        # Clean all the driver mock_calls to clear exception
        # and other mock_call history.
        self.mock_driver.reset_mock()


class TestCiscoNexusBaremetalVPCConfig(base.TestCiscoNexusBase,
                                       TestCiscoNexusDeviceConfig,
                                       TestCiscoNexusDeviceResults):

    """Unit tests for Cisco ML2 Nexus baremetal VPC Config.

    The purpose of this test case is to validate vpc pool initialization.
    If vpc-pool is configured, it will be compared with what currently
    exists in the vpc pool data base. Adds and removals of the data base
    will occur.  Removal will not occur if the entry is active.
    """

    def setUp(self):
        super(TestCiscoNexusBaremetalVPCConfig, self).setUp()
        self.mock_driver.reset_mock()

    def _run_vpc_config_test(self, switch_ip, config, count_in,
                             min_in, max_in):
        """Config vpc-pool config with garbage. log & no db entries."""

        cfg.CONF.set_override(
            const.VPCPOOL, config,
            cfg.CONF.ml2_cisco.nexus_switches.get(switch_ip)._group)

        self._cisco_mech_driver._initialize_vpc_alloc_pools()

        # Verify get_switch_vpc_count_min_max() returns correct
        # count, min, max values for switches.
        count, min, max = nxos_db.get_switch_vpc_count_min_max(
            switch_ip)
        self.assertEqual(count, count_in)
        self.assertEqual(min, min_in)
        self.assertEqual(max, max_in)

    def test_vpc_config_db_results_bad_config1(self):
        """Config vpc-pool config with garbage. log & no db entries."""

        self._run_vpc_config_test('1.1.1.1', 'blahblahblah', 0, None, None)

    def test_vpc_config_db_results_bad_config2(self):
        """Config vpc-pool config with bad range. log & no db entries."""

        self._run_vpc_config_test('1.1.1.1', '5-7-9,1', 0, None, None)

    def test_vpc_config_db_results_bad_config3(self):
        """Config vpc-pool config with bad digits. log & no db entries."""
        self._run_vpc_config_test('1.1.1.1', '5-abc,1', 0, None, None)

    def test_vpc_config_db_results_bad_vpc_range(self):
        """Config vpc-pool config with bad min/max values."""

        # bad_min = 0-5
        bad_min = str(const.MINVPC - 1) + '-5'
        self._run_vpc_config_test('1.1.1.1', bad_min, 0, None, None)

        # bad_max = 4096-4097
        bad_max = str(const.MAXVPC) + '-' + str(const.MAXVPC + 1)
        self._run_vpc_config_test('1.1.1.1', bad_max, 0, None, None)

    def test_vpc_config_db_results_bad_config_keep_old(self):
        """Verify on config error, existing db entries stay intact."""

        old_list = [1, 6, 8, 11]

        # Pretend these already existed and make 8 active
        nxos_db.init_vpc_entries('1.1.1.1', old_list)
        nxos_db.update_vpc_entry(['1.1.1.1'], 8, True, True)

        # valid port-channel values are 1-4096 on Nexus 9K

        # ERROR: range starts with 0
        bad_min = str(const.MINVPC - 1) + '-1001, 1002'
        self._run_vpc_config_test('1.1.1.1', bad_min, 4, 1, 11)

    def test_vpc_config_db_results_removal(self):
        """Allow user to remove config but only non-active."""

        # 1 no add, already exists
        # 6 remove not active
        # 8 no remove, ACTIVE
        # 11 no add, already exists
        old_list = [1, 6, 8, 11]

        # Pretend these already existed and make 8 active
        nxos_db.init_vpc_entries('1.1.1.1', old_list)
        nxos_db.update_vpc_entry(['1.1.1.1'], 8, True, True)

        self._run_vpc_config_test('1.1.1.1', '', 1, 8, 8)

        # Make 8 inactive and try again.
        nxos_db.update_vpc_entry(['1.1.1.1'], 8, False, False)
        self._run_vpc_config_test('1.1.1.1', '', 0, None, None)

    def test_vpc_config_db_results_good_config_not_range(self):
        """Config valid vpc-pool not range config. """

        self._run_vpc_config_test('1.1.1.1', '1,3,5', 3, 1, 5)

    def test_vpc_config_db_results_good_config_range(self):
        """Config valid vpc-pool range config. """

        self._run_vpc_config_test('1.1.1.1', '1-5', 5, 1, 5)

    def test_vpc_config_db_results_good_config_all(self):
        """Config valid vpc-pool range config. Test Min/Max vpc value."""

        # test_range_limits = 1-5,4096
        test_range_limits = str(const.MINVPC) + '-5,' + str(const.MAXVPC)
        self._run_vpc_config_test('1.1.1.1', test_range_limits,
                                  6, const.MINVPC, const.MAXVPC)

    def test_vpc_config_db_results_with_old_config1(self):
        """Config valid vpc-pool compare with pre-existing entries."""

        # 1 will be removed,
        # 3 no add, already exists
        # 4 no add, already exists
        # 11 will not be removed since active
        old_list = [1, 3, 4, 11]

        # Pretend these already existed and make 11 active
        nxos_db.init_vpc_entries('1.1.1.1', old_list)
        nxos_db.update_vpc_entry(['1.1.1.1'], 11, True, True)

        self._run_vpc_config_test('1.1.1.1', '2-5, 8', 6, 2, 11)

    def test_vpc_config_db_results_with_old_config2(self):
        """Config valid vpc-pool compare with pre-existing entries."""

        # 1 no add, already exists
        # 6 remove not active
        # 8 no remove, ACTIVE
        # 11 no add, already exists
        old_list = [1, 6, 8, 11]

        # Pretend these already existed and make 8 active
        nxos_db.init_vpc_entries('1.1.1.1', old_list)
        nxos_db.update_vpc_entry(['1.1.1.1'], 8, True, True)

        self._run_vpc_config_test('1.1.1.1', '1-4, 9, 11', 7, 1, 11)

    def test_vpc_config_db_results_with_old_config3(self):
        """Config valid vpc-pool compare with pre-existing entries."""

        # 1 no add, already exists
        # 11 no add, already exists
        old_list = [1, 6, 8, 11]

        # Pretend these already existed and make 8 active
        nxos_db.init_vpc_entries('1.1.1.1', old_list)

        self._run_vpc_config_test('1.1.1.1', '1-4, 6-9, 11', 9, 1, 11)
