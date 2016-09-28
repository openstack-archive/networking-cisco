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
from oslo_config import cfg

from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    constants as const)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import exceptions
from networking_cisco.plugins.ml2.drivers.cisco.nexus import nexus_db_v2
from networking_cisco.tests.unit.ml2.drivers.cisco.nexus import (
    test_cisco_nexus_base)

RP_HOST_NAME_1 = 'UniquePort'
RP_HOST_NAME_2 = 'DuplicateVlan'
RP_HOST_NAME_3 = 'DuplicatePort'
RP_HOST_NAME_DUAL = 'testdualhost'
MAX_REPLAY_COUNT = 4


class TestCiscoNexusReplay(test_cisco_nexus_base.TestCiscoNexusReplayBase):
    """Unit tests for Replay of Cisco ML2 Nexus data."""
    test_configs = {
        'test_replay_unique1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                RP_HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_replay_unique2':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                RP_HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_2,
                test_cisco_nexus_base.VLAN_ID_2,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_replay_duplvlan1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_2,
                RP_HOST_NAME_2,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_replay_duplvlan2':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_2,
                RP_HOST_NAME_2,
                test_cisco_nexus_base.NEXUS_PORT_2,
                test_cisco_nexus_base.INSTANCE_2,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_replay_duplport1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_3,
                RP_HOST_NAME_3,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_replay_duplport2':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_3,
                RP_HOST_NAME_3,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_2,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_replay_dual':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_DUAL,
                RP_HOST_NAME_DUAL,
                test_cisco_nexus_base.NEXUS_DUAL1,
                test_cisco_nexus_base.INSTANCE_DUAL,
                test_cisco_nexus_base.VLAN_ID_DUAL,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_replay_dual2':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_DUAL2,
                RP_HOST_NAME_DUAL,
                test_cisco_nexus_base.NEXUS_DUAL2,
                test_cisco_nexus_base.INSTANCE_DUAL,
                test_cisco_nexus_base.VLAN_ID_DUAL,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
        'test_replay_vxlan_unique1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                RP_HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.VXLAN_ID,
                test_cisco_nexus_base.MCAST_GROUP,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
    }
    driver_result_unique_init = (
        [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 'None')])

    driver_result_unique_add1 = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 267)])

    driver_result_unique_add2 = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(265),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 265)])

    driver_result_unique_del1 = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 265),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(265)])

    driver_result_unique_del2 = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 267),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(267)])

    test_configs = collections.OrderedDict(sorted(test_configs.items()))

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusReplay, self).setUp()

    def test_replay_unique_ports(self):
        """Provides replay data and result data for unique ports. """

        first_add = {'driver_results': self.
                     driver_result_unique_add1,
                     'nbr_db_entries': 1}
        second_add = {'driver_results': self.
                      driver_result_unique_add2,
                      'nbr_db_entries': 2}
        first_del = {'driver_results': self.
                     driver_result_unique_del1,
                     'nbr_db_entries': 1}
        second_del = {'driver_results': self.
                      driver_result_unique_del2,
                      'nbr_db_entries': 0}
        driver_result_unique_2vlan_replay = (
            [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/10', '265,267'),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format('265,267')])

        self._process_replay(
            'test_replay_unique1',
            'test_replay_unique2',
            self.driver_result_unique_init,
            first_add,
            second_add,
            driver_result_unique_2vlan_replay,
            first_del,
            second_del)

    def test_replay_duplicate_vlan(self):
        """Provides replay data and result data for duplicate vlans. """

        result1_add = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/10', 267),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/20', 267)])
        first_add = {'driver_results': result1_add,
                     'nbr_db_entries': 2}

        result2_add = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/10', 267),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/20', 267)])
        # TODO(caboucha)
        # 'driver_result': [], until the correct fix for
        # the following issue is resolved.
        # https://review.openstack.org/#/c/241216/
        second_add = {'driver_results': result2_add,
                      'nbr_db_entries': 4}

        first_del = {'driver_results': [],
                     'nbr_db_entries': 2}

        result2_del = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/10', 267),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(267),
            test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/20', 267)])
        second_del = {'driver_results': result2_del,
                      'nbr_db_entries': 0}

        result_replay = (
            [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/10', 267),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/20', 267),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format(267)])

        self._process_replay('test_replay_duplvlan1',
                             'test_replay_duplvlan2',
                             [],
                             first_add, second_add,
                             result_replay,
                             first_del, second_del)

    def test_replay_duplicate_ports(self):
        """Provides replay data and result data for duplicate ports. """

        first_add = {'driver_results': self.driver_result_unique_add1,
                     'nbr_db_entries': 1}

        # TODO(caboucha)
        # 'driver_result': [], until the correct fix for
        # the following issue is resolved.
        # https://review.openstack.org/#/c/241216/
        second_add = {'driver_results': self.driver_result_unique_add1,
                      'nbr_db_entries': 2}
        first_del = {'driver_results': [],
                     'nbr_db_entries': 1}

        second_del = {'driver_results': self.driver_result_unique_del2,
                      'nbr_db_entries': 0}

        result_replay = (
            [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/10', 267),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format(267)])

        self._process_replay('test_replay_duplport1',
                             'test_replay_duplport2',
                             [],
                             first_add, second_add,
                             result_replay,
                             first_del, second_del)

    def test_replay_enable_vxlan_feature_failure(self):
        """Verifies exception during enable VXLAN feature driver. """

        # Set configuration variable to add/delete the VXLAN global nexus
        # switch values.
        cfg.CONF.set_override('vxlan_global_config', True, 'ml2_cisco')
        self._create_port_failure(
            'connect.return_value.edit_config.side_effect',
            'feature nv overlay vn-segment-vlan-based',
            'test_replay_vxlan_unique1',
            __name__)

    def test_replay_disable_vxlan_feature_failure(self):
        """Verifies exception during disable VXLAN feature driver. """

        # Set configuration variable to add/delete the VXLAN global nexus
        # switch values.
        cfg.CONF.set_override('vxlan_global_config', True, 'ml2_cisco')
        self._delete_port_failure(
            'connect.return_value.edit_config.side_effect',
            'no feature nv overlay vn-segment-vlan-based',
            'test_replay_vxlan_unique1',
            __name__)

    def test_replay_create_nve_member_failure(self):
        """Verifies exception during create nve member driver. """

        self._create_port_failure(
            'connect.return_value.edit_config.side_effect',
            'member vni mcast-group',
            'test_replay_vxlan_unique1',
            __name__)

    def test_replay_delete_nve_member_failure(self):
        """Verifies exception during delete nve member driver. """

        self._delete_port_failure(
            'connect.return_value.edit_config.side_effect',
            'no member vni',
            'test_replay_vxlan_unique1',
            __name__)

    def test_replay_create_vlan_failure(self):
        """Verifies exception during edit vlan create driver. """

        self._create_port_failure(
            'connect.return_value.edit_config.side_effect',
            'vlan-id-create-delete',
            'test_replay_unique1',
            __name__)

    def test_replay_delete_vlan_failure(self):
        """Verifies exception during edit vlan delete driver. """

        self._delete_port_failure(
            'connect.return_value.edit_config.side_effect',
            'vlan-id-create-delete no vlan 267',
            'test_replay_unique1',
            __name__)

    def test_replay_create_trunk_failure(self):
        """Verifies exception during create trunk interface driver. """

        self._create_port_failure(
            'connect.return_value.edit_config.side_effect',
            'switchport trunk allowed vlan_id 267',
            'test_replay_unique1',
            __name__)

    def test_replay_delete_trunk_failure(self):
        """Verifies exception during delete trunk interface driver. """

        self._delete_port_failure(
            'connect.return_value.edit_config.side_effect',
            'switchport trunk allowed remove vlan 267',
            'test_replay_unique1',
            __name__)

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
        result_add = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN.format(269),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/3', 269)])
        self._basic_create_verify_port_vlan('test_replay_dual',
            result_add,
            nbr_of_bindings=1)

        # Even though 2nd entry is inactive, there should be
        # a data base entry configured for it.
        # 2 = One entry for port the other for reserved binding
        self.assertEqual(
            2, len(nexus_db_v2.get_nexusport_switch_bindings(
                   port_cfg2.nexus_ip_addr)))

        # Clean-up the port entry
        result_del = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/3', 269),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(269)])
        self._basic_delete_verify_port_vlan('test_replay_dual',
            result_del,
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
        result_add = (
            [test_cisco_nexus_base.RESULT_ADD_VLAN.format(269),
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/3', 269)])
        self._basic_create_verify_port_vlan('test_replay_dual',
            result_add,
            nbr_of_bindings=1)

        # Even though 2nd entry is inactive, there should be
        # a data base entry configured for it.
        # 2 = One entry for port the other for reserved binding
        self.assertEqual(
            2, len(nexus_db_v2.get_nexusport_switch_bindings(
                   port_cfg2.nexus_ip_addr)))

        # Restore port data for that switch
        self._cfg_monitor.check_connections()
        result_replay = (
            [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/2', 269),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format(269)])
        self._verify_results(result_replay)

        # Clear mock_call history.
        self.mock_ncclient.reset_mock()

        # Clean-up the port entries
        result_del = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/3', 269),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(269),
            test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('ethernet', '1\/2', 269),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(269)])
        self._basic_delete_verify_port_vlan('test_replay_dual',
            result_del,
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
            self.driver_result_unique_add1)

        # Make switch inactive before delete
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Clean-up the port entry
        self._basic_delete_verify_port_vlan('test_replay_unique1',
            [], nbr_of_bindings=0)

    def test_replay_get_nexus_type_failure_two_switches(self):
        """Verifies exception during ncclient get inventory. """

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
        config = {'connect.return_value.get.side_effect':
            self._config_side_effects_on_count('show inventory',
            Exception(__name__))}
        self.mock_ncclient.configure_mock(**config)

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
            self.driver_result_unique_add1)

        # Set-up so get_nexus_type driver fails
        config = {'connect.return_value.get.side_effect':
            self._config_side_effects_on_count('show inventory',
            Exception(__name__))}
        self.mock_ncclient.configure_mock(**config)

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

        vlan267 = test_cisco_nexus_base.RESULT_ADD_VLAN.format(267)
        driver_result1 = [vlan267] * 2

        # Set switch state to False so replay config will start.
        # This should not affect user configuration.
        port_cfg = self.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_unique1',
            self.driver_result_unique_add1)

        # Set-up exception during create_vlan
        config = {'connect.return_value.edit_config.side_effect':
                  self._config_side_effects_on_count(
                      'vlan-id-create-delete',
                      Exception(__name__ + '1'))}
        self.mock_ncclient.configure_mock(**config)

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
        result_replay = (
            [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/10', 267)] + driver_result1)
        self._verify_results(result_replay)

        # Clear the edit driver exception for next test.
        config = {'connect.return_value.edit_config.side_effect':
                  None}
        self.mock_ncclient.configure_mock(**config)

        # Perform replay which should not send back exception
        # but merely quit
        self._cfg_monitor.check_connections()

        # Verify that switch is in ACTIVE state
        self.assertEqual(
            const.SWITCH_ACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                port_cfg.nexus_ip_addr))

        # Clear mock_call history.
        self.mock_ncclient.reset_mock()

        # Clean-up the port entry
        self._basic_delete_verify_port_vlan('test_replay_unique1',
            self.driver_result_unique_del2)

    def test_replay_vlan_batch_failure_during_replay(self):
        """Verifies handling of batch vlan during replay."""

        tmp_cfg = self.TestConfigObj(
            test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
            RP_HOST_NAME_1,
            test_cisco_nexus_base.NEXUS_PORT_1,
            test_cisco_nexus_base.INSTANCE_1,
            test_cisco_nexus_base.VLAN_ID_1,
            test_cisco_nexus_base.NO_VXLAN_ID,
            None,
            test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
            {},
            test_cisco_nexus_base.NORMAL_VNIC)
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            tmp_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Create a batch of port entries with unique vlans
        num_vlans = const.CREATE_VLAN_BATCH + 10
        for x in range(num_vlans):
            instance_id = test_cisco_nexus_base.INSTANCE_1 + '-' + str(x)
            new_cfg = tmp_cfg._replace(
                          vlan_id=test_cisco_nexus_base.VLAN_ID_1 + x,
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

        config = {'connect.return_value.edit_config.side_effect':
                  self._config_side_effects_on_count(
                      'vlan-id-create-delete',
                      Exception(__name__ + '1'))}
        self.mock_ncclient.configure_mock(**config)

        # Call check_connections() again  to attempt to send
        # last batch of 10 which should fail
        self._cfg_monitor.check_connections()
        # Verify the switch is back in INACTIVE state
        self.assertEqual(
            const.SWITCH_INACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                tmp_cfg.nexus_ip_addr))

        # Clear mock_call history.
        self.mock_ncclient.reset_mock()

        # Clear the edit driver exception for next test.
        config = {'connect.return_value.edit_config.side_effect':
                  None}
        self.mock_ncclient.configure_mock(**config)

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

        # Due to 2 retries in driver to deal with stale ncclient
        # handle, the results are doubled.
        vlan267 = '<vlan-id-create-delete\>\s+\<__XML__PARAM_value\>267'
        driver_result2 = ([test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 267)] + [vlan267] * 2) * 4

        config_replay = MAX_REPLAY_COUNT
        port_cfg = self.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_unique1',
            self.driver_result_unique_add1)

        # Test 1:
        # Set the edit create vlan driver exception
        # Perform replay MAX_REPLAY_COUNT times
        # This should not roll-up an exception but merely quit
        # and increment FAIL_CONFIG statistics

        config = {'connect.return_value.edit_config.side_effect':
                  self._config_side_effects_on_count(
                      'vlan-id-create-delete',
                      Exception(__name__ + '1'))}
        self.mock_ncclient.configure_mock(**config)

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
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1))
        self._verify_results(driver_result2)

        # Verify there exists a single port binding
        # plus 1 for reserved switch entry
        self.assertEqual(
            2, len(nexus_db_v2.get_nexusport_switch_bindings(
                   test_cisco_nexus_base.NEXUS_IP_ADDRESS_1)))

        # Clear mock_call history.
        self.mock_ncclient.reset_mock()

        # Clear the edit driver exception for next test.
        config = {'connect.return_value.edit_config.side_effect':
                  None}
        self.mock_ncclient.configure_mock(**config)

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
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1))
        self.assertEqual(
            config_replay,
            self._cisco_mech_driver.get_switch_replay_failure(
                const.FAIL_CONTACT,
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1))
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
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1))
        self.assertEqual(
            config_replay,
            self._cisco_mech_driver.get_switch_replay_failure(
                const.FAIL_CONTACT,
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1))

        # Clear the get nexus type driver exception.
        config = {'connect.return_value.get.side_effect':
                  None}
        self.mock_ncclient.configure_mock(**config)

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
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1))
        self.assertEqual(
            0,
            self._cisco_mech_driver.get_switch_replay_failure(
                const.FAIL_CONTACT,
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1))

        # Verify switch state is now active following successful replay.
        self.assertEqual(
            const.SWITCH_ACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1))


class TestCiscoNexusBaremetalReplay(
    test_cisco_nexus_base.TestCiscoNexusReplayBase):
    """Unit tests for Replay of Cisco ML2 Nexus data."""
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

    test_configs = {
        'test_replay_unique1':
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
        'test_replay_unique2':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_UNUSED,
                test_cisco_nexus_base.NEXUS_BAREMETAL_PORT_1,
                test_cisco_nexus_base.INSTANCE_2,
                test_cisco_nexus_base.VLAN_ID_2,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_BAREMETAL,
                baremetal_profile,
                test_cisco_nexus_base.BAREMETAL_VNIC),
        'test_replay_unique_native1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                test_cisco_nexus_base.HOST_NAME_UNUSED,
                test_cisco_nexus_base.NEXUS_BAREMETAL_PORT_1,
                test_cisco_nexus_base.INSTANCE_2,
                test_cisco_nexus_base.VLAN_ID_2,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_BAREMETAL,
                baremetal_profile_is_native,
                test_cisco_nexus_base.BAREMETAL_VNIC),
    }

    driver_result_unique_eth_init = (
        [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 'None')])

    driver_result_unique_eth_add1 = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 267)])

    driver_result_unique_eth_add2 = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(265),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 265)])

    driver_result_unique_eth_del1 = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 265),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(265)])

    driver_result_unique_eth_del2 = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 267),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(267)])

    driver_result_unique_vPC_init = (
        [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('port-channel', '469', 'None')])

    driver_result_unique_vPC_add1 = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(267),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('port-channel', '469', 267)])

    driver_result_unique_vPC_add2 = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(265),
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('port-channel', '469', 265)])

    driver_result_unique_vPC_del1 = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('port-channel', '469', 265),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(265)])

    driver_result_unique_vPC_del2 = (
        [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('port-channel', '469', 267),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(267)])

    driver_result_unique_native_port_ethernet_add = (
        [test_cisco_nexus_base.RESULT_ADD_VLAN.format(265),
        (test_cisco_nexus_base.RESULT_ADD_NATIVE_INTERFACE.
            format('ethernet', '1\/10', 265) +
        '[\x00-\x7f]+' +
        test_cisco_nexus_base.RESULT_ADD_INTERFACE.
            format('ethernet', '1\/10', 265))])

    driver_result_unique_native_port_ethernet_del = (
        [(test_cisco_nexus_base.RESULT_DEL_NATIVE_INTERFACE.
            format('ethernet', '1\/10') +
        '[\x00-\x7f]+' +
        test_cisco_nexus_base.RESULT_DEL_INTERFACE.
            format('ethernet', '1\/10', 265)),
        test_cisco_nexus_base.RESULT_DEL_VLAN.format(265)])

    test_configs = collections.OrderedDict(sorted(test_configs.items()))

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('never_cache_ssh_connection', False, 'ml2_cisco')
        super(TestCiscoNexusBaremetalReplay, self).setUp()

    def test_replay_unique_ethernet_ports(self):
        """Provides replay data and result data for unique ports. """

        first_add = {'driver_results': self.
                     driver_result_unique_eth_add1,
                     'nbr_db_entries': 2}
        second_add = {'driver_results': self.
                      driver_result_unique_eth_add2,
                      'nbr_db_entries': 3}
        first_del = {'driver_results': self.
                     driver_result_unique_eth_del1,
                     'nbr_db_entries': 2}
        second_del = {'driver_results': self.
                      driver_result_unique_eth_del2,
                      'nbr_db_entries': 1}
        driver_result_unique_2vlan_replay = (
            [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/10', '265,267'),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format('265,267')])

        self._process_replay(
            'test_replay_unique1',
            'test_replay_unique2',
            self.driver_result_unique_eth_init,
            first_add,
            second_add,
            driver_result_unique_2vlan_replay,
            first_del,
            second_del)

    def test_replay_unique_vPC_ports(self):
        """Provides replay data and result data for unique ports. """

        first_add = {'driver_results': self.
                     driver_result_unique_vPC_add1,
                     'nbr_db_entries': 2}
        second_add = {'driver_results': self.
                      driver_result_unique_vPC_add2,
                      'nbr_db_entries': 3}
        first_del = {'driver_results': self.
                     driver_result_unique_vPC_del1,
                     'nbr_db_entries': 2}
        second_del = {'driver_results': self.
                      driver_result_unique_vPC_del2,
                      'nbr_db_entries': 1}
        driver_result_unique_2vlan_replay = (
            [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('port-channel', '469', '265,267'),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format('265,267')])

        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.
        data_xml = {'connect.return_value.get.return_value.data_xml':
                    'switchport trunk allowed vlan none\n'
                    'channel-group 469 mode active'}
        self.mock_ncclient.configure_mock(**data_xml)

        self._process_replay(
            'test_replay_unique1',
            'test_replay_unique2',
            self.driver_result_unique_vPC_init,
            first_add,
            second_add,
            driver_result_unique_2vlan_replay,
            first_del,
            second_del)

    def test_replay_unique_vPC_ports_chg_vPC_nbr(self):
        """Provides replay data and result data for unique ports. """

        def replay_init():
            # This is to cause port-channel to get configured to 470
            data_xml = {'connect.return_value.get.return_value.data_xml':
                        'switchport trunk allowed vlan none\n'
                        'channel-group 470 mode active'}
            self.mock_ncclient.configure_mock(**data_xml)

        driver_result_unique_vPC470_del1 = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('port-channel', '470', 265),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(265)])

        driver_result_unique_vPC470_del2 = (
            [test_cisco_nexus_base.RESULT_DEL_INTERFACE.
                format('port-channel', '470', 267),
            test_cisco_nexus_base.RESULT_DEL_VLAN.format(267)])

        first_add = {'driver_results': self.
                     driver_result_unique_vPC_add1,
                     'nbr_db_entries': 2}
        second_add = {'driver_results': self.
                      driver_result_unique_vPC_add2,
                      'nbr_db_entries': 3}
        first_del = {'driver_results':
                     driver_result_unique_vPC470_del1,
                     'nbr_db_entries': 2}
        second_del = {'driver_results':
                      driver_result_unique_vPC470_del2,
                      'nbr_db_entries': 1}
        driver_result_unique_vPC470_2vlan_replay = (
            [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('port-channel', '470', '265,267'),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format('265,267')])

        # This is to cause port-channel 469 to get configured
        data_xml = {'connect.return_value.get.return_value.data_xml':
                    'switchport trunk allowed vlan none\n'
                    'channel-group 469 mode active'}
        self.mock_ncclient.configure_mock(**data_xml)

        # Providing replay_init to change channel-group
        self._process_replay(
            'test_replay_unique1',
            'test_replay_unique2',
            self.driver_result_unique_vPC_init,
            first_add,
            second_add,
            driver_result_unique_vPC470_2vlan_replay,
            first_del,
            second_del,
            replay_init)

    def test_replay_unique_vPC_ports_chg_to_enet(self):
        """Provides replay data and result data for unique ports. """

        def replay_init():
            # This is to cause port-channel to get replaced with enet
            data_xml = {'connect.return_value.get.return_value.data_xml':
                        'switchport trunk allowed vlan none\n'}
            self.mock_ncclient.configure_mock(**data_xml)

        first_add = {'driver_results': self.
                     driver_result_unique_vPC_add1,
                     'nbr_db_entries': 2}
        second_add = {'driver_results': self.
                      driver_result_unique_vPC_add2,
                      'nbr_db_entries': 3}
        first_del = {'driver_results': self.
                     driver_result_unique_eth_del1,
                     'nbr_db_entries': 2}
        second_del = {'driver_results': self.
                      driver_result_unique_eth_del2,
                      'nbr_db_entries': 1}
        driver_result_unique_2vlan_replay = (
            [test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/10', '265,267'),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format('265,267')])

        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.
        data_xml = {'connect.return_value.get.return_value.data_xml':
                    'switchport trunk allowed vlan none\n'
                    'channel-group 469 mode active'}
        self.mock_ncclient.configure_mock(**data_xml)

        # Providing replay_init to remove port-channel
        self._process_replay(
            'test_replay_unique1',
            'test_replay_unique2',
            self.driver_result_unique_vPC_init,
            first_add,
            second_add,
            driver_result_unique_2vlan_replay,
            first_del,
            second_del,
            replay_init)

    def test_replay_unique_native_nonnative_ethernet_ports(self):
        """Test replay with native and nonnative ethernet ports. """

        first_add = {'driver_results': self.
                     driver_result_unique_native_port_ethernet_add,
                     'nbr_db_entries': 2}
        second_add = {'driver_results': self.
                      driver_result_unique_eth_add1,
                      'nbr_db_entries': 3}
        first_del = {'driver_results': self.
                     driver_result_unique_eth_del2,
                     'nbr_db_entries': 2}
        second_del = {'driver_results': self.
                     driver_result_unique_native_port_ethernet_del,
                      'nbr_db_entries': 1}
        driver_result_unique_native_2vlan_replay = (
            [(test_cisco_nexus_base.RESULT_ADD_NATIVE_INTERFACE.
            format('ethernet', '1\/10', 265) +
            '[\x00-\x7f]+' +
            test_cisco_nexus_base.RESULT_ADD_INTERFACE.
                format('ethernet', '1\/10', '265,267')),
            test_cisco_nexus_base.RESULT_ADD_VLAN.format('265,267')])

        self._process_replay(
            'test_replay_unique_native1',
            'test_replay_unique1',
            self.driver_result_unique_eth_init,
            first_add,
            second_add,
            driver_result_unique_native_2vlan_replay,
            first_del,
            second_del)


class TestCiscoNexusNonCachedSshReplay(
    test_cisco_nexus_base.TestCiscoNexusReplayBase):
    """Unit tests for Replay of Cisco ML2 Nexus data."""

    # Testing new default of True for config var 'never_cache_ssh_connection'

    test_configs = {
        'test_replay_unique1':
            test_cisco_nexus_base.TestCiscoNexusBase.TestConfigObj(
                test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
                RP_HOST_NAME_1,
                test_cisco_nexus_base.NEXUS_PORT_1,
                test_cisco_nexus_base.INSTANCE_1,
                test_cisco_nexus_base.VLAN_ID_1,
                test_cisco_nexus_base.NO_VXLAN_ID,
                None,
                test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
                {},
                test_cisco_nexus_base.NORMAL_VNIC),
    }

    def test_basic_replay_NonCacheSsh(self):
        """Basic none cached ssh replay test."""

        tmp_cfg = self.TestConfigObj(
            test_cisco_nexus_base.NEXUS_IP_ADDRESS_1,
            RP_HOST_NAME_1,
            test_cisco_nexus_base.NEXUS_PORT_1,
            test_cisco_nexus_base.INSTANCE_1,
            test_cisco_nexus_base.VLAN_ID_1,
            test_cisco_nexus_base.NO_VXLAN_ID,
            None,
            test_cisco_nexus_base.DEVICE_OWNER_COMPUTE,
            {},
            test_cisco_nexus_base.NORMAL_VNIC)

        self._cisco_mech_driver.set_switch_ip_and_active_state(
            tmp_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        self.mock_ncclient.reset_mock()

        # Create a batch of port entries with unique vlans
        num_vlans = 10
        for x in range(num_vlans):
            instance_id = test_cisco_nexus_base.INSTANCE_1 + '-' + str(x)
            new_cfg = tmp_cfg._replace(
                          vlan_id=test_cisco_nexus_base.VLAN_ID_1 + x,
                          instance_id=instance_id)
            self._create_port(new_cfg)

        self.assertEqual(20, self.mock_ncclient.connect.call_count)
        self.assertEqual(20,
            self.mock_ncclient.connect.return_value.
            close_session.call_count)

        self.mock_ncclient.reset_mock()

        # Put it back to inactive state
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            tmp_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        self._cfg_monitor.check_connections()

        self.assertEqual(2, self.mock_ncclient.connect.call_count)
        self.assertEqual(2,
            self.mock_ncclient.connect.return_value.
            close_session.call_count)
