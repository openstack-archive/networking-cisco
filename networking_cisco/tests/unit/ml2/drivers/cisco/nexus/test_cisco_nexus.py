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

import collections
import mock
import os
from oslo_utils import importutils
import re
import testtools

from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    config as cisco_config)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    constants as const)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_network_driver)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import constants
from networking_cisco.plugins.ml2.drivers.cisco.nexus import exceptions
from networking_cisco.plugins.ml2.drivers.cisco.nexus import mech_cisco_nexus
from networking_cisco.plugins.ml2.drivers.cisco.nexus import nexus_db_v2

from neutron.common import constants as n_const
from neutron.extensions import portbindings
from neutron.plugins.ml2 import driver_api as api
from neutron.tests.unit import testlib_api


CONNECT_ERROR = 'Unable to connect to Nexus'

NEXUS_IP_ADDRESS = '1.1.1.1'
NEXUS_IP_ADDRESS_PC = '2.2.2.2'
NEXUS_IP_ADDRESS_DUAL = '3.3.3.3'
HOST_NAME_1 = 'testhost1'
HOST_NAME_2 = 'testhost2'
HOST_NAME_PC = 'testpchost'
HOST_NAME_DUAL = 'testdualhost'
INSTANCE_1 = 'testvm1'
INSTANCE_2 = 'testvm2'
INSTANCE_PC = 'testpcvm'
INSTANCE_DUAL = 'testdualvm'
NEXUS_PORT_1 = 'ethernet:1/10'
NEXUS_PORT_2 = 'ethernet:1/20'
NEXUS_PORTCHANNELS = 'portchannel:2'
NEXUS_DUAL = 'ethernet:1/3,portchannel:2'
VLAN_ID_1 = 267
VLAN_ID_2 = 265
VLAN_ID_PC = 268
VLAN_ID_DUAL = 269
VXLAN_ID = 70000
NO_VXLAN_ID = 0
MCAST_GROUP = '255.1.1.1'
DEVICE_OWNER_COMPUTE = 'compute:test'
DEVICE_OWNER_DHCP = n_const.DEVICE_OWNER_DHCP
NEXUS_SSH_PORT = '22'
PORT_STATE = n_const.PORT_STATUS_ACTIVE
NETWORK_TYPE = 'vlan'
NEXUS_VXLAN_NETWORK_TYPE = 'nexus_vxlan'
NEXUS_DRIVER = ('networking_cisco.plugins.ml2.drivers.cisco.nexus.'
                'nexus_network_driver.CiscoNexusDriver')


class FakeNetworkContext(object):

    """Network context for testing purposes only."""

    def __init__(self, segment_id, nw_type, mcast_group='physnet1'):

        self._network_segments = {api.SEGMENTATION_ID: segment_id,
                                  api.NETWORK_TYPE: nw_type,
                                  const.PROVIDER_SEGMENT: False,
                                  api.PHYSICAL_NETWORK: mcast_group}

    @property
    def network_segments(self):
        return self._network_segments


class FakePortContext(object):

    """Port context for testing purposes only."""

    def __init__(self, device_id, host_name, device_owner,
                 network_context, bottom_segment=None):
        self._port = {
            'status': PORT_STATE,
            'device_id': device_id,
            'device_owner': device_owner,
            portbindings.HOST_ID: host_name,
            portbindings.VIF_TYPE: portbindings.VIF_TYPE_OVS
        }
        self._network = network_context
        self._segment = network_context.network_segments
        if bottom_segment is None:
            self._bottom_segment = None
        else:
            self._bottom_segment = bottom_segment.network_segments

    @property
    def current(self):
        return self._port

    @property
    def network(self):
        return self._network

    @property
    def top_bound_segment(self):
        return self._segment

    @property
    def bottom_bound_segment(self):
        return self._bottom_segment

    @property
    def original_top_bound_segment(self):
        return None

    @property
    def original_bottom_bound_segment(self):
        return None


class TestCiscoNexusDevice(testlib_api.SqlTestCase):

    """Unit tests for Cisco ML2 Nexus device driver."""

    TestConfigObj = collections.namedtuple(
        'TestConfigObj',
        'nexus_ip_addr host_name nexus_port instance_id vlan_id vxlan_id '
        'mcast_group device_owner')

    test_configs = {
        'test_config1': TestConfigObj(
            NEXUS_IP_ADDRESS,
            HOST_NAME_1,
            NEXUS_PORT_1,
            INSTANCE_1,
            VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_config2': TestConfigObj(
            NEXUS_IP_ADDRESS,
            HOST_NAME_2,
            NEXUS_PORT_2,
            INSTANCE_2,
            VLAN_ID_2,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_config3': TestConfigObj(
            NEXUS_IP_ADDRESS,
            HOST_NAME_1,
            NEXUS_PORT_1,
            INSTANCE_2,
            VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_config_portchannel': TestConfigObj(
            NEXUS_IP_ADDRESS_PC,
            HOST_NAME_PC,
            NEXUS_PORTCHANNELS,
            INSTANCE_PC,
            VLAN_ID_PC,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_config_dual': TestConfigObj(
            NEXUS_IP_ADDRESS_DUAL,
            HOST_NAME_DUAL,
            NEXUS_DUAL,
            INSTANCE_DUAL,
            VLAN_ID_DUAL,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_config_dhcp': TestConfigObj(
            NEXUS_IP_ADDRESS,
            HOST_NAME_1,
            NEXUS_PORT_1,
            INSTANCE_1,
            VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_DHCP),
        'test_vxlan_config1': TestConfigObj(
            NEXUS_IP_ADDRESS,
            HOST_NAME_1,
            NEXUS_PORT_1,
            INSTANCE_1,
            VLAN_ID_1,
            VXLAN_ID,
            '225.1.1.1',
            DEVICE_OWNER_COMPUTE),
    }

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""
        super(TestCiscoNexusDevice, self).setUp()

        cisco_config.cfg.CONF.set_default('api_workers', 0)
        cisco_config.cfg.CONF.set_default('rpc_workers', 0)

        # Use a mock netconf client
        self.mock_ncclient = mock.Mock()
        mock.patch.object(nexus_network_driver.CiscoNexusDriver,
                          '_import_ncclient',
                          return_value=self.mock_ncclient).start()
        data_xml = {'connect.return_value.get.return_value.data_xml': ''}
        self.mock_ncclient.configure_mock(**data_xml)

        def new_nexus_init(mech_instance):
            mech_instance.driver = importutils.import_object(NEXUS_DRIVER)
            mech_instance.monitor_timeout = (
                cisco_config.cfg.CONF.ml2_cisco.switch_heartbeat_time)
            mech_instance._ppid = os.getpid()

            mech_instance._nexus_switches = {}
            for name, config in TestCiscoNexusDevice.test_configs.items():
                ip_addr = config.nexus_ip_addr
                host_name = config.host_name
                nexus_port = config.nexus_port
                mech_instance._nexus_switches[(ip_addr,
                                               host_name)] = nexus_port
                mech_instance._nexus_switches[(ip_addr,
                                               'ssh_port')] = NEXUS_SSH_PORT
                mech_instance._nexus_switches[(ip_addr,
                                               constants.USERNAME)] = 'admin'
                mech_instance._nexus_switches[(ip_addr,
                                              constants.PASSWORD)] = 'password'
            mech_instance.driver.nexus_switches = (
                mech_instance._nexus_switches)

        mock.patch.object(mech_cisco_nexus.CiscoNexusMechanismDriver,
                          '__init__', new=new_nexus_init).start()
        self._cisco_mech_driver = (mech_cisco_nexus.
                                   CiscoNexusMechanismDriver())

    def _verify_results(self, driver_result):
        """Verifies correct entries sent to Nexus."""

        self.assertEqual(self.mock_ncclient.connect.return_value.
            edit_config.call_count,
            len(driver_result),
            "Unexpected driver count")

        for idx in range(0, len(driver_result)):
            self.assertNotEqual(self.mock_ncclient.connect.
                return_value.edit_config.mock_calls[idx][2]['config'],
                None, "mock_data is None")
            self.assertNotEqual(
                re.search(driver_result[idx],
                    self.mock_ncclient.connect.return_value.
                    edit_config.mock_calls[idx][2]['config']),
                None, "Expected result data not found")

    def _create_port(self, port_config):
        """Tests creation and deletion of a virtual port."""
        nexus_ip_addr = port_config.nexus_ip_addr
        host_name = port_config.host_name
        nexus_port = port_config.nexus_port
        instance_id = port_config.instance_id
        vlan_id = port_config.vlan_id
        vxlan_id = port_config.vxlan_id
        mcast_group = port_config.mcast_group
        device_owner = port_config.device_owner

        network_context = FakeNetworkContext(vlan_id, NETWORK_TYPE)
        if vxlan_id != NO_VXLAN_ID:
            bottom_context = network_context
            network_context = FakeNetworkContext(vxlan_id,
                NEXUS_VXLAN_NETWORK_TYPE, mcast_group)
        else:
            bottom_context = None

        port_context = FakePortContext(instance_id, host_name,
            device_owner, network_context, bottom_context)

        self._cisco_mech_driver.update_port_precommit(port_context)
        self._cisco_mech_driver.update_port_postcommit(port_context)
        for port_id in nexus_port.split(','):
            bindings = nexus_db_v2.get_nexusport_binding(port_id,
                                                         vlan_id,
                                                         nexus_ip_addr,
                                                         instance_id)
            self.assertEqual(len(bindings), 1)

    def _delete_port(self, port_config):
        """Tests creation and deletion of a virtual port."""
        nexus_ip_addr = port_config.nexus_ip_addr
        host_name = port_config.host_name
        nexus_port = port_config.nexus_port
        instance_id = port_config.instance_id
        vlan_id = port_config.vlan_id
        vxlan_id = port_config.vxlan_id
        mcast_group = port_config.mcast_group
        device_owner = port_config.device_owner

        network_context = FakeNetworkContext(vlan_id, NETWORK_TYPE)
        if vxlan_id != NO_VXLAN_ID:
            bottom_context = network_context
            network_context = FakeNetworkContext(vxlan_id,
                NEXUS_VXLAN_NETWORK_TYPE, mcast_group)
        else:
            bottom_context = None

        port_context = FakePortContext(instance_id, host_name,
            device_owner, network_context, bottom_context)

        self._cisco_mech_driver.delete_port_precommit(port_context)
        self._cisco_mech_driver.delete_port_postcommit(port_context)
        for port_id in nexus_port.split(','):
            with testtools.ExpectedException(
                    exceptions.NexusPortBindingNotFound):
                nexus_db_v2.get_nexusport_binding(port_id,
                                                  vlan_id,
                                                  nexus_ip_addr,
                                                  instance_id)

    def _create_delete_port(self, port_config):
        """Tests creation and deletion of a virtual port."""
        self._create_port(port_config)
        self._delete_port(port_config)

    def _config_side_effects(self, match_config, exc):
        """Generates config-dependent side effect for ncclient.

        This method was written to configure side_effects for both
        ncclient edit_config and get_config drivers.  In the case
        of edit_config, the arguments target and config are passed
        into _side_effect_method.  In the case of get, the argument
        filter is passed into _side_effect_method.  For the sake of
        simplicity, the _side_effect_method was written to handle
        either case.
        """
        keywords = match_config.split()

        def _side_effect_method(target=None, config=None, filter=None):
            if config is None:
                config = filter[1]
            if all(word in config for word in keywords):
                raise exc
        return _side_effect_method

    def _create_port_failure(self, attr, match_str, test_case, test_id):
        """Verifies exception handling during initial create object.

        This method is a shared method to initiate an exception
        at various point of object creation.  The points of failure
        are identified by the caller which can be get operations or
        edit operations.  When local replay mechanism is not configured,
        the exception should bubble up.

        attr:      Which mock attribute to contain side_effect exception
        match_str: String for side_effect method to match for exception
        test_case: which configuration test case to run thru test
        test_id:   String to put in the exception and verify contained
                   in exception string.  This indicates it was indeed
                   our exception which was executed indicating test
                   indeed is complete
        """

        config = {attr:
            self._config_side_effects(match_str,
            Exception(test_id))}
        self.mock_ncclient.configure_mock(**config)
        e = self.assertRaises(
                exceptions.NexusConfigFailed,
                self._create_port,
                TestCiscoNexusDevice.test_configs[test_case])
        self.assertIn(test_id, unicode(e))

    def _delete_port_failure(self, attr, match_str, test_case, test_id):
        """Verifies exception handling during object deletion.

        This method is a shared method to initiate an exception
        at various point of object deletion.  The points of failure
        are identified by the caller which can be get operations or
        edit operations. When local replay mechanism is not configured,
        the exception should bubble up.

        attr:      Which mock attribute to contain side_effect exception
        match_str: String for side_effect method to match for exception
        test_case: which configuration test case to run thru test
        test_id:   String to put in the exception and verify contained
                   in exception string.  This indicates it was indeed
                   our exception which was executed indicating test
                   indeed is complete
        """

        self._create_port(
            TestCiscoNexusDevice.test_configs[test_case])
        config = {attr:
            self._config_side_effects(match_str,
            Exception(test_id))}
        self.mock_ncclient.configure_mock(**config)
        e = self.assertRaises(
                exceptions.NexusConfigFailed,
                self._delete_port,
                TestCiscoNexusDevice.test_configs[test_case])
        self.assertIn(test_id, unicode(e))

    def test_create_delete_ports(self):
        """Tests creation and deletion of two new virtual Ports."""
        self._create_delete_port(
            TestCiscoNexusDevice.test_configs['test_config1'])

        self._create_delete_port(
            TestCiscoNexusDevice.test_configs['test_config2'])

    def test_create_delete_duplicate_ports(self):
        """Tests creation and deletion of two new virtual Ports."""
        duplicate_add_port_driver_result = [
            '\<vlan\-name\>q\-267\<\/vlan\-name>',
            '\<vstate\>active\<\/vstate>',
            '\<no\>\s+\<shutdown\/\>\s+\<\/no\>',
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<vlan_id\>267',
        ]
        duplicate_delete_port_driver_result = [
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e\s]+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<remove\>\s+\<vlan\>267',
            '\<no\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
            '\s+\<__XML__PARAM_value\>267',
        ]

        self._create_port(
            TestCiscoNexusDevice.test_configs['test_config1'])
        # verify first config was indeed configured
        self._verify_results(duplicate_add_port_driver_result)

        self._create_port(
            TestCiscoNexusDevice.test_configs['test_config3'])
        # verify only the first config was applied
        self._verify_results(duplicate_add_port_driver_result)

        # Verify there are 2 port configs
        bindings = nexus_db_v2.get_nexusvlan_binding(VLAN_ID_1,
                                                     NEXUS_IP_ADDRESS)
        self.assertEqual(len(bindings), 2)

        # Clean all the ncclient mock_calls so we can evaluate
        # results of delete operations.
        self.mock_ncclient.reset_mock()

        self._delete_port(
            TestCiscoNexusDevice.test_configs['test_config1'])
        # Using empty list verify no nexus action on first port removal
        self._verify_results([])

        self._delete_port(
            TestCiscoNexusDevice.test_configs['test_config3'])
        # verify port removed on 2nd port delete
        self._verify_results(duplicate_delete_port_driver_result)

    def test_create_delete_portchannel(self):
        """Tests creation of a port over a portchannel."""
        self._create_delete_port(
            TestCiscoNexusDevice.test_configs['test_config_portchannel'])

    def test_create_delete_dual(self):
        """Tests creation and deletion of dual ports for single server"""
        self._create_delete_port(
            TestCiscoNexusDevice.test_configs['test_config_dual'])

    def test_create_delete_dhcp(self):
        """Tests creation and deletion of ports with device_owner of dhcp."""
        self._create_delete_port(
            TestCiscoNexusDevice.test_configs['test_config_dhcp'])

    def test_connect_failure(self):
        """Verifies exception handling during ncclient connect. """

        config = {'connect.side_effect': Exception(CONNECT_ERROR)}
        self.mock_ncclient.configure_mock(**config)

        e = self.assertRaises(exceptions.NexusConfigFailed,
                              self._create_port,
                              TestCiscoNexusDevice.test_configs[
                                  'test_config1'])
        self.assertIn(CONNECT_ERROR, unicode(e))

    def test_get_interface_failure(self):
        """Verifies exception during ncclient get interface. """

        self._create_port_failure(
            'connect.return_value.get.side_effect',
            'show running-config interface ethernet',
            'test_config1',
            __name__)

    def test_enable_vxlan_feature_failure(self):
        """Verifies exception during enable VXLAN driver. """

        # Set configuration variable to add/delete the VXLAN global nexus
        # switch values.
        cisco_config.cfg.CONF.set_override('vxlan_global_config', True,
                                           'ml2_cisco')
        self._create_port_failure(
            'connect.return_value.edit_config.side_effect',
            'feature nv overlay vn-segment-vlan-based',
            'test_vxlan_config1',
            __name__)

    def test_disable_vxlan_feature_failure(self):
        """Verifies exception during disable VXLAN driver. """

        # Set configuration variable to add/delete the VXLAN global nexus
        # switch values.
        cisco_config.cfg.CONF.set_override('vxlan_global_config', True,
                                           'ml2_cisco')
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
            'vlan-id-create-delete vlan-name',
            'test_config1',
            __name__)

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


RP_NEXUS_IP_ADDRESS_1 = '1.1.1.1'
RP_NEXUS_IP_ADDRESS_2 = '2.2.2.2'
RP_NEXUS_IP_ADDRESS_3 = '3.3.3.3'
RP_HOST_NAME_1 = 'UniquePort'
RP_HOST_NAME_2 = 'DuplicateVlan'
RP_HOST_NAME_3 = 'DuplicatePort'
RP_INSTANCE_1 = 'testvm1'
RP_INSTANCE_2 = 'testvm2'
RP_NEXUS_PORT_1 = 'ethernet:1/10'
RP_NEXUS_PORT_2 = 'ethernet:1/20'
RP_VLAN_ID_1 = 267
RP_VLAN_ID_2 = 265


class TestCiscoNexusReplay(testlib_api.SqlTestCase):
    """Unit tests for Replay of Cisco ML2 Nexus data."""

    TestConfigObj = collections.namedtuple(
        'TestConfigObj',
        'nexus_ip_addr host_name nexus_port instance_id vlan_id vxlan_id '
        'mcast_group device_owner')

    test_configs = {
        'test_replay_unique1': TestConfigObj(
            RP_NEXUS_IP_ADDRESS_1,
            RP_HOST_NAME_1,
            RP_NEXUS_PORT_1,
            RP_INSTANCE_1,
            RP_VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_replay_unique2': TestConfigObj(
            RP_NEXUS_IP_ADDRESS_1,
            RP_HOST_NAME_1,
            RP_NEXUS_PORT_1,
            RP_INSTANCE_2,
            RP_VLAN_ID_2,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_replay_duplvlan1': TestConfigObj(
            RP_NEXUS_IP_ADDRESS_2,
            RP_HOST_NAME_2,
            RP_NEXUS_PORT_1,
            RP_INSTANCE_1,
            RP_VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_replay_duplvlan2': TestConfigObj(
            RP_NEXUS_IP_ADDRESS_2,
            RP_HOST_NAME_2,
            RP_NEXUS_PORT_2,
            RP_INSTANCE_2,
            RP_VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_replay_duplport1': TestConfigObj(
            RP_NEXUS_IP_ADDRESS_3,
            RP_HOST_NAME_3,
            RP_NEXUS_PORT_1,
            RP_INSTANCE_1,
            RP_VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_replay_duplport2': TestConfigObj(
            RP_NEXUS_IP_ADDRESS_3,
            RP_HOST_NAME_3,
            RP_NEXUS_PORT_1,
            RP_INSTANCE_2,
            RP_VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_replay_vxlan_unique1': TestConfigObj(
            RP_NEXUS_IP_ADDRESS_1,
            RP_HOST_NAME_1,
            RP_NEXUS_PORT_1,
            RP_INSTANCE_1,
            RP_VLAN_ID_1,
            VXLAN_ID,
            '225.1.1.1',
            DEVICE_OWNER_COMPUTE),
    }

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""
        super(TestCiscoNexusReplay, self).setUp()

        cisco_config.cfg.CONF.set_default('api_workers', 0)
        cisco_config.cfg.CONF.set_default('rpc_workers', 0)

        # Use a mock netconf client
        self.mock_ncclient = mock.Mock()
        mock.patch.object(nexus_network_driver.CiscoNexusDriver,
                          '_import_ncclient',
                          return_value=self.mock_ncclient).start()
        data_xml = {'connect.return_value.get.return_value.data_xml': ''}
        self.mock_ncclient.configure_mock(**data_xml)

        cisco_config.cfg.CONF.set_override('switch_heartbeat_time',
            30, 'ml2_cisco')

        def new_nexus_init(mech_instance):
            mech_instance.driver = importutils.import_object(NEXUS_DRIVER)
            mech_instance.monitor_timeout = (
                cisco_config.cfg.CONF.ml2_cisco.switch_heartbeat_time)
            mech_instance._ppid = os.getpid()

            mech_instance._switch_state = {}
            mech_instance._nexus_switches = {}
            for name, config in TestCiscoNexusReplay.test_configs.items():
                ip_addr = config.nexus_ip_addr
                host_name = config.host_name
                nexus_port = config.nexus_port
                if (ip_addr, host_name) in mech_instance._nexus_switches:
                    saved_port = (
                        mech_instance._nexus_switches[(ip_addr, host_name)])
                    if saved_port != nexus_port:
                        mech_instance._nexus_switches[(ip_addr, host_name)] = (
                            saved_port + ',' + nexus_port)
                else:
                    mech_instance._nexus_switches[(ip_addr,
                                                   host_name)] = nexus_port
                mech_instance._nexus_switches[(ip_addr,
                                               'ssh_port')] = NEXUS_SSH_PORT
                mech_instance._nexus_switches[(ip_addr,
                                               constants.USERNAME)] = 'admin'
                mech_instance._nexus_switches[(ip_addr,
                                              constants.PASSWORD)] = 'password'
            mech_instance.driver.nexus_switches = (
                mech_instance._nexus_switches)

        mock.patch.object(mech_cisco_nexus.CiscoNexusMechanismDriver,
                          '__init__', new=new_nexus_init).start()
        self._cisco_mech_driver = (mech_cisco_nexus.
                                   CiscoNexusMechanismDriver())
        self._cfg_monitor = (mech_cisco_nexus.
                             CiscoNexusCfgMonitor(
                                 self._cisco_mech_driver.driver,
                                 self._cisco_mech_driver))

    def _create_port(self, port_config):
        """Tests creation of a virtual port."""
        nexus_ip_addr = port_config.nexus_ip_addr
        host_name = port_config.host_name
        nexus_port = port_config.nexus_port
        instance_id = port_config.instance_id
        vlan_id = port_config.vlan_id
        vxlan_id = port_config.vxlan_id
        mcast_group = port_config.mcast_group
        device_owner = port_config.device_owner

        network_context = FakeNetworkContext(vlan_id, NETWORK_TYPE)
        if vxlan_id != NO_VXLAN_ID:
            vxlan_network_context = FakeNetworkContext(vlan_id,
                NEXUS_VXLAN_NETWORK_TYPE, mcast_group)
            port_context = FakePortContext(instance_id, host_name,
                device_owner, vxlan_network_context, network_context)
        else:
            port_context = FakePortContext(instance_id, host_name,
                device_owner, network_context)

        self._cisco_mech_driver.update_port_precommit(port_context)
        self._cisco_mech_driver.update_port_postcommit(port_context)
        for port_id in nexus_port.split(','):
            bindings = nexus_db_v2.get_nexusport_binding(port_id,
                                                         vlan_id,
                                                         nexus_ip_addr,
                                                         instance_id)
            self.assertEqual(len(bindings), 1)

    def _delete_port(self, port_config):
        """Tests deletion of a virtual port."""
        nexus_ip_addr = port_config.nexus_ip_addr
        host_name = port_config.host_name
        nexus_port = port_config.nexus_port
        instance_id = port_config.instance_id
        vlan_id = port_config.vlan_id
        vxlan_id = port_config.vxlan_id
        mcast_group = port_config.mcast_group
        device_owner = port_config.device_owner

        network_context = FakeNetworkContext(vlan_id, NETWORK_TYPE)
        if vxlan_id != NO_VXLAN_ID:
            vxlan_network_context = FakeNetworkContext(vlan_id,
                NEXUS_VXLAN_NETWORK_TYPE, mcast_group)
            port_context = FakePortContext(instance_id, host_name,
                device_owner, vxlan_network_context, network_context)
        else:
            port_context = FakePortContext(instance_id, host_name,
                device_owner, network_context)

        self._cisco_mech_driver.delete_port_precommit(port_context)
        self._cisco_mech_driver.delete_port_postcommit(port_context)
        for port_id in nexus_port.split(','):
            with testtools.ExpectedException(
                    exceptions.NexusPortBindingNotFound):
                nexus_db_v2.get_nexusport_binding(port_id,
                                                  vlan_id,
                                                  nexus_ip_addr,
                                                  instance_id)

    def _verify_replay_results(self, driver_result):
        """Verifies correct entries sent to Nexus."""

        self.assertEqual(self.mock_ncclient.connect.return_value.
            edit_config.call_count,
            len(driver_result),
            "Unexpected driver count")

        for idx in range(0, len(driver_result)):
            self.assertNotEqual(self.mock_ncclient.connect.
                return_value.edit_config.mock_calls[idx][2]['config'],
                None, "mock_data is None")
            self.assertNotEqual(
                re.search(driver_result[idx],
                    self.mock_ncclient.connect.return_value.
                    edit_config.mock_calls[idx][2]['config']),
                None, "Expected result data not found")

    def _process_replay(self, test1, test2, driver_results):
        """Tests create, replay, delete of two ports."""

        # Set all connection state to True except for
        # test case HOST_1, RP_NEXUS_IP_ADDRESS_1
        cfg_type = ['test_replay_unique1',
                    'test_replay_duplvlan1',
                    'test_replay_duplport1']
        for which_cfg in cfg_type:
            if which_cfg in [test1, test2]:
                state = False
            else:
                state = True
            port_cfg = TestCiscoNexusReplay.test_configs[which_cfg]
            self._cisco_mech_driver.set_switch_ip_and_active_state(
                port_cfg.nexus_ip_addr, state)

        self._create_port(
            TestCiscoNexusReplay.test_configs[test1])
        self._create_port(
            TestCiscoNexusReplay.test_configs[test2])

        # Clean all the ncclient mock_calls so we can evaluate
        # content as a result of replay()
        self.mock_ncclient.reset_mock()

        # Since only this test case connection state is False,
        # it should be the only one replayed
        self._cfg_monitor.check_connections()
        self._verify_replay_results(driver_results)

        self._delete_port(
            TestCiscoNexusReplay.test_configs[test1])

        self._delete_port(
            TestCiscoNexusReplay.test_configs[test2])

    def _config_side_effects(self, match_config, exc):
        """Generates config-dependent side effect for ncclient.

        This method was written to configure side_effects for both
        ncclient edit_config and get_config drivers.  In the case
        of edit_config, the arguments target and config are passed
        into _side_effect_method.  In the case of get, the argument
        filter is passed into _side_effect_method.  For the sake of
        simplicity, the _side_effect_method was written to handle
        either case.
        """
        keywords = match_config.split()

        def _side_effect_method(target=None, config=None, filter=None):
            if config is None:
                config = filter[1]
            if all(word in config for word in keywords):
                raise exc
        return _side_effect_method

    def _create_port_failure(self, attr, match_str, test_case, test_id):
        """Verifies exception handling during initial create object.

        This method is a shared method to initiate an exception
        at various point of object creation.  The points of failure
        are identified by the caller which can be get operations or
        edit operations.  When the mechanism replay is functioning,
        the exception should be suppressed and the switch is marked
        as inactive.

        attr:      Which mock attribute to contain side_effect exception
        match_str: String for side_effect method to match for exception
        test_case: which configuration test case to run thru test
        test_id:   String to put in the exception.
        """

        # Set switch state to active
        switch_ip = TestCiscoNexusReplay.test_configs[test_case].nexus_ip_addr
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            switch_ip, True)

        # Set up driver exception
        config = {attr:
            self._config_side_effects(match_str,
            Exception(test_id))}
        self.mock_ncclient.configure_mock(**config)

        self._create_port(TestCiscoNexusReplay.test_configs[test_case])

        # _create_port should complete successfully but switch state changed
        # to inactive.
        self.assertFalse(
            self._cisco_mech_driver.get_switch_ip_and_active_state(switch_ip))

    def _delete_port_failure(self, attr, match_str, test_case, test_id):
        """Verifies exception handling during object deletion.

        This method is a shared method to initiate an exception
        at various point of object deletion.  The points of failure
        are identified by the caller which can be get operations or
        edit operations.  When the mechanism replay is functioning,
        the exception should be suppressed and the switch is marked
        as inactive.

        attr:      Which mock attribute to contain side_effect exception
        match_str: String for side_effect method to match for exception
        test_case: which configuration test case to run thru test
        test_id:   String to put in the exception.
        """

        # Set switch state to active
        switch_ip = TestCiscoNexusReplay.test_configs[test_case].nexus_ip_addr
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            switch_ip, True)

        self._create_port(
            TestCiscoNexusReplay.test_configs[test_case])

        # _create_port should complete successfully and no switch state change.
        self.assertTrue(
            self._cisco_mech_driver.get_switch_ip_and_active_state(switch_ip))

        # Set up driver exception
        config = {attr:
            self._config_side_effects(match_str,
            Exception(test_id))}
        self.mock_ncclient.configure_mock(**config)

        self._delete_port(TestCiscoNexusReplay.test_configs[test_case])

        # _delete_port should complete successfully but switch state changed
        # to inactive.
        self.assertFalse(
            self._cisco_mech_driver.get_switch_ip_and_active_state(switch_ip))

    def test_replay_unique_ports(self):
        """Provides replay data and result data for unique ports. """
        unique_driver_result = [
            '\<vlan\-name\>q\-265\<\/vlan\-name>',
            '\<vstate\>active\<\/vstate>',
            '\<no\>\s+\<shutdown\/\>\s+\<\/no\>',
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<vlan_id\>265',

            '\<vlan\-name\>q\-267\<\/vlan\-name>',
            '\<vstate\>active\<\/vstate>',
            '\<no\>\s+\<shutdown\/\>\s+\<\/no\>',
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<vlan_id\>267',
        ]

        self._process_replay('test_replay_unique1',
                             'test_replay_unique2',
                             unique_driver_result)

    def test_replay_duplicate_vlan(self):
        """Provides replay data and result data for duplicate vlans. """
        duplicate_vlan_result = [
            '\<vlan\-name\>q\-267\<\/vlan\-name>',
            '\<vstate\>active\<\/vstate>',
            '\<no\>\s+\<shutdown\/\>\s+\<\/no\>',
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<vlan_id\>267',

            '\<interface\>1\/20\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<vlan_id\>267',
        ]

        self._process_replay('test_replay_duplvlan1',
                             'test_replay_duplvlan2',
                             duplicate_vlan_result)

    def test_replay_duplicate_ports(self):
        """Provides replay data and result data for duplicate ports. """
        duplicate_port_result = [
            '\<vlan\-name\>q\-267\<\/vlan\-name>',
            '\<vstate\>active\<\/vstate>',
            '\<no\>\s+\<shutdown\/\>\s+\<\/no\>',
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<vlan_id\>267',
        ]

        self._process_replay('test_replay_duplport1',
                             'test_replay_duplport2',
                             duplicate_port_result)

    def test_replay_get_interface_failure(self):
        """Verifies exception during ncclient get interface. """

        self._create_port_failure(
            'connect.return_value.get.side_effect',
            'show running-config interface ethernet',
            'test_replay_unique1',
            __name__)

    def test_replay_enable_vxlan_feature_failure(self):
        """Verifies exception during enable VXLAN feature driver. """

        # Set configuration variable to add/delete the VXLAN global nexus
        # switch values.
        cisco_config.cfg.CONF.set_override('vxlan_global_config', True,
                                           'ml2_cisco')
        self._create_port_failure(
            'connect.return_value.edit_config.side_effect',
            'feature nv overlay vn-segment-vlan-based',
            'test_replay_vxlan_unique1',
            __name__)

    def test_replay_disable_vxlan_feature_failure(self):
        """Verifies exception during disable VXLAN feature driver. """

        # Set configuration variable to add/delete the VXLAN global nexus
        # switch values.
        cisco_config.cfg.CONF.set_override('vxlan_global_config', True,
                                           'ml2_cisco')
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
            'vlan-id-create-delete vlan-name',
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

    def test_replay_get_nexus_type_failure(self):
        """Verifies exception during get nexus_type while replaying. """

        #Set-up failed config which puts switch in inactive state
        self.test_replay_create_vlan_failure()

        # Clean all the ncclient mock_calls so we can evaluate
        # content as a result of replay()
        self.mock_ncclient.reset_mock()

        # Set-up so get_nexus_type driver fails
        config = {'connect.return_value.get.side_effect':
            self._config_side_effects('show inventory',
            Exception(__name__))}
        self.mock_ncclient.configure_mock(**config)

        # Perform replay which should not send back exception
        # but merely quit
        self._cfg_monitor.check_connections()

        # Since get of nexus_type failed, there should be
        # no attempt to configure anything.
        self._verify_replay_results([])

    def test_replay_retry_handling(self):
        """Verifies a series of events to check retry_count operations.

        1) Verify retry count is incremented upon failure during replay.
        2) Verify further attempts to configure replay data stops.
        3) Verify upon receipt of new transaction that retry count
        is reset to 0 so replay attempts will restart.
        4) Verify retry count is reset when replay is successful.
        """

        unique_driver_result1 = [
            '\<vlan\-name\>q\-267\<\/vlan\-name>',
        ]
        unique_driver_result2 = [
            '\<vlan\-name\>q\-267\<\/vlan\-name>',
            '\<vlan\-name\>q\-267\<\/vlan\-name>',
            '\<vlan\-name\>q\-267\<\/vlan\-name>',
            '\<vlan\-name\>q\-267\<\/vlan\-name>',
        ]
        config_replay = cisco_config.cfg.CONF.ml2_cisco.switch_replay_count

        #Set-up failed config which puts switch in inactive state
        self.test_replay_create_vlan_failure()
        # Make sure there is only a single attempt to configure.
        self._verify_replay_results(unique_driver_result1)

        # Don't reset_mock so create_vlan continues failing

        # Perform replay 4 times to exceed retry count of 3.
        # This should not roll-up an exception but merely quit
        for i in range(config_replay + 1):
            self._cfg_monitor.check_connections()

        # Verify switch retry count reached configured max and
        # verify only 4 attempts to send create_vlan.
        # first is from test_replay_create_vlan_failure()
        # and only 3 from check_connections()
        assert(self._cisco_mech_driver.get_switch_retry_count(
               RP_NEXUS_IP_ADDRESS_1) == (config_replay + 1))
        self._verify_replay_results(unique_driver_result2)

        # Clean all the ncclient mock_calls to clear exception
        # and other mock_call history.
        self.mock_ncclient.reset_mock()

        # Verify there exists a single port binding
        assert(len(nexus_db_v2.get_nexusport_switch_bindings(
               RP_NEXUS_IP_ADDRESS_1)) == 1)

        # Sent another config which should reset retry count
        # Verify replay results again
        self._delete_port(
            TestCiscoNexusReplay.test_configs['test_replay_unique1'])

        # Verify port binding has been removed
        # Verify switch retry count reset to 0 and
        # verify no driver transactions have been sent
        self.assertRaises(exceptions.NexusPortBindingNotFound,
                     nexus_db_v2.get_nexusport_switch_bindings,
                     RP_NEXUS_IP_ADDRESS_1)
        assert(self._cisco_mech_driver.get_switch_retry_count(
               RP_NEXUS_IP_ADDRESS_1) == 0)
        self._verify_replay_results([])

        # Replay Retry test 4)
        # Set-up failed config which puts switch in inactive state
        self.test_replay_create_vlan_failure()
        # Make sure there is only a single attempt to configure.
        self._verify_replay_results(unique_driver_result1)

        # Perform replay once to increment retry count to 1.
        # Verify retry count is 1.
        self._cfg_monitor.check_connections()
        assert(self._cisco_mech_driver.get_switch_retry_count(
               RP_NEXUS_IP_ADDRESS_1) == 1)

        # Clean all the ncclient mock_calls to clear
        # mock_call history.
        self.mock_ncclient.reset_mock()

        # Clear the driver exception.
        config = {'connect.return_value.edit_config.side_effect':
                  None}
        self.mock_ncclient.configure_mock(**config)

        # Perform replay once which will be successful causing
        # retry count to be reset to 0.
        # Then verify retry count is indeed 0.
        self._cfg_monitor.check_connections()
        assert(self._cisco_mech_driver.get_switch_retry_count(
               RP_NEXUS_IP_ADDRESS_1) == 0)
