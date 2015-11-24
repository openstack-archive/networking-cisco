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
from oslo_config import cfg
from oslo_utils import importutils
import re
import six
import testtools

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
DEVICE_OWNER_ROUTER_HA_INTF = n_const.DEVICE_OWNER_ROUTER_HA_INTF
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
        'test_config_router_ha_intf': TestConfigObj(
            NEXUS_IP_ADDRESS,
            HOST_NAME_1,
            NEXUS_PORT_1,
            INSTANCE_1,
            VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_ROUTER_HA_INTF),
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

        cfg.CONF.import_opt('api_workers', 'neutron.service')
        cfg.CONF.set_default('api_workers', 0)
        cfg.CONF.import_opt('rpc_workers', 'neutron.service')
        cfg.CONF.set_default('rpc_workers', 0)

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
                cfg.CONF.ml2_cisco.switch_heartbeat_time)
            mech_instance._ppid = os.getpid()

            mech_instance._nexus_switches = collections.OrderedDict()
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

        self._cisco_mech_driver.create_port_postcommit(port_context)
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

    def _config_side_effects_on_count(self, match_config, exc,
                                      match_range=None):
        """Generates config-dependent side effect for ncclient.

        This method was written to configure side_effects for both
        ncclient edit_config and get_config drivers.  In the case
        of edit_config, the arguments target and config are passed
        into _side_effect_method.  In the case of get, the argument
        filter is passed into _side_effect_method.  For the sake of
        simplicity, the _side_effect_method was written to handle
        either case.

        Additionally, arguments start and count were passed in to
        handle the number of times to raise exception for a given
        match.  Also match_config if passed in as an empty string,
        is interpreted as match not desired.

        Usage Examples:

        First 2 times for the given mock side-effect, throw an exception.
        _config_side_effects_on_count('', Exception(test_id), range(0,2))

        Two times after 4th attempt for the given mock side-effect,
        throw an exception.
        _config_side_effects_on_count('', Exception(test_id), range(4,6))

        First 2 time, for the given mock side-effect which the call
        matches 'match string', throw an exception.
        _config_side_effects_on_count('match string',
                                      Exception(test_id), range(0,2))

        do 'no range check' and for the given mock side-effect which the call
        matches 'match string', throw an exception.
        _config_side_effects_on_count('match string',
                                      Exception(test_id))
        """
        keywords = match_config.split()

        def _side_effect_method(target=None, config=None, filter=None):
            if not hasattr(self, "position"):
                self.position = 0

            if config is None:
                config = filter[1]
            match = True if not keywords else all(
                word in config for word in keywords)

            # If there is a match, check count in range; otherwise
            # mark as unmatch
            if match and match_range is not None:
                match = self.position in match_range
                self.position += 1

            if match:
                raise exc
            else:
                return mock.DEFAULT

        return _side_effect_method

    def _create_port_failure(self, attr, match_str, test_case, test_id,
            which_exc=exceptions.NexusConfigFailed):
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
            self._config_side_effects_on_count(match_str,
            Exception(test_id))}
        self.mock_ncclient.configure_mock(**config)
        e = self.assertRaises(
                which_exc,
                self._create_port,
                TestCiscoNexusDevice.test_configs[test_case])
        self.assertIn(test_id, six.u(str(e)))

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
            self._config_side_effects_on_count(match_str,
            Exception(test_id))}
        self.mock_ncclient.configure_mock(**config)
        e = self.assertRaises(
                exceptions.NexusConfigFailed,
                self._delete_port,
                TestCiscoNexusDevice.test_configs[test_case])
        self.assertIn(test_id, six.u(str(e)))

    def test_create_delete_ports(self):
        """Tests creation and deletion of two new virtual Ports."""

        self._create_delete_port(
            TestCiscoNexusDevice.test_configs['test_config1'])

        self._create_delete_port(
            TestCiscoNexusDevice.test_configs['test_config2'])

        # Verify we attempt to connect once with no reconnect
        self.assertEqual(self.mock_ncclient.connect.call_count, 1)

    def test_create_delete_duplicate_ports(self):
        """Tests creation and deletion of two new virtual Ports."""

        duplicate_add_port_driver_result = [
            'configure\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
            '\s+\<__XML__PARAM_value\>267',
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>267',
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
        # TODO(caboucha)
        # Commented out until the correct fix for
        # the following issue is resolved.
        # https://review.openstack.org/#/c/241216/
        #
        # verify first config was indeed configured
        # Original code was as follows:
        # self._verify_results(duplicate_add_port_driver_result)

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

    def test_create_delete_router_ha_intf(self):
        """Tests creation and deletion of ports with device_owner
        of router_ha_interface.
        """
        self._create_delete_port(
            TestCiscoNexusDevice.test_configs['test_config_router_ha_intf'])

    def test_connect_failure(self):
        """Verifies exception handling during ncclient connect. """

        config = {'connect.side_effect': Exception(CONNECT_ERROR)}
        self.mock_ncclient.configure_mock(**config)

        e = self.assertRaises(exceptions.NexusConnectFailed,
                              self._create_port,
                              TestCiscoNexusDevice.test_configs[
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

        config = {'connect.return_value.edit_config.side_effect':
                  self._config_side_effects_on_count(
                      'vlan vlan-id-create-delete 267',
                      Exception(__name__), range(1))}

        self.mock_ncclient.configure_mock(**config)
        self._create_delete_port(
            TestCiscoNexusDevice.test_configs['test_config1'])

        # Verify we connected twice. Connect attempt 1 occurs on
        # any first driver call.  Then create-vlan fails first
        # time resulting close of stale handle. Driver
        # loops around to try and reopen and create-vlan should
        # then be successful on the 2nd pass.
        self.assertEqual(self.mock_ncclient.connect.call_count, 2)

RP_NEXUS_IP_ADDRESS_1 = '1.1.1.1'
RP_NEXUS_IP_ADDRESS_2 = '2.2.2.2'
RP_NEXUS_IP_ADDRESS_3 = '3.3.3.3'
RP_NEXUS_IP_ADDRESS_DUAL = '4.4.4.4'
RP_NEXUS_IP_ADDRESS_DUAL2 = '5.5.5.5'
RP_HOST_NAME_1 = 'UniquePort'
RP_HOST_NAME_2 = 'DuplicateVlan'
RP_HOST_NAME_3 = 'DuplicatePort'
RP_HOST_NAME_DUAL = 'testdualhost'
RP_INSTANCE_1 = 'testvm1'
RP_INSTANCE_2 = 'testvm2'
RP_INSTANCE_DUAL = 'testdualvm'
RP_NEXUS_PORT_1 = 'ethernet:1/10'
RP_NEXUS_PORT_2 = 'ethernet:1/20'
RP_NEXUS_DUAL1 = 'ethernet:1/3'
RP_NEXUS_DUAL2 = 'ethernet:1/2'
RP_VLAN_ID_1 = 267
RP_VLAN_ID_2 = 265
RP_VLAN_ID_DUAL = 269
MAX_REPLAY_COUNT = 4


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
        'test_replay_dual': TestConfigObj(
            RP_NEXUS_IP_ADDRESS_DUAL,
            RP_HOST_NAME_DUAL,
            RP_NEXUS_DUAL1,
            RP_INSTANCE_DUAL,
            RP_VLAN_ID_DUAL,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE),
        'test_replay_dual2': TestConfigObj(
            RP_NEXUS_IP_ADDRESS_DUAL2,
            RP_HOST_NAME_DUAL,
            RP_NEXUS_DUAL2,
            RP_INSTANCE_DUAL,
            RP_VLAN_ID_DUAL,
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
    driver_result_unique_init = [
        '\<interface\>1\/10\<\/interface\>\s+'
        '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
        '\<allowed\>\s+\<vlan\>\s+\<vlan_id\>None',
    ]
    driver_result_unique_add1 = [
        'configure\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
        '\s+\<__XML__PARAM_value\>267',
        '\<interface\>1\/10\<\/interface\>\s+'
        '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
        '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>267',
    ]
    driver_result_unique_add2 = [
        'configure\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
        '\s+\<__XML__PARAM_value\>265',
        '\<interface\>1\/10\<\/interface\>\s+'
        '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
        '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>265',
    ]
    driver_result_unique_2vlan_replay = [
        '\<interface\>1\/10\<\/interface\>\s+'
        '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
        '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>265,267',
        'configure\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
        '\s+\<__XML__PARAM_value\>265,267',
    ]
    driver_result_unique_del1 = [
        '\<interface\>1\/10\<\/interface\>\s+'
        '[\x20-\x7e\s]+\<switchport\>\s+\<trunk\>\s+'
        '\<allowed\>\s+\<vlan\>\s+\<remove\>\s+\<vlan\>265',
        '\<no\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
        '\s+\<__XML__PARAM_value\>265',
    ]
    driver_result_unique_del2 = [
        '\<interface\>1\/10\<\/interface\>\s+'
        '[\x20-\x7e\s]+\<switchport\>\s+\<trunk\>\s+'
        '\<allowed\>\s+\<vlan\>\s+\<remove\>\s+\<vlan\>267',
        '\<no\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
        '\s+\<__XML__PARAM_value\>267',
    ]
    driver_result_dual_add_if1 = [
        '\<ethernet\>\s+\<interface\>1\/3\<\/interface\>\s+'
        '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
        '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>269',
    ]
    driver_result_dual_add_vlan = [
        'configure\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
        '\s+\<__XML__PARAM_value\>269',
    ]
    driver_result_dual_add_if2 = [
        '\<ethernet\>\s+\<interface\>1\/2\<\/interface\>\s+'
        '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
        '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>269',
    ]
    driver_result_dual_del1 = [
        '\<ethernet\>\s+\<interface\>1\/3\<\/interface\>\s+'
        '[\x20-\x7e\s]+\<switchport\>\s+\<trunk\>\s+'
        '\<allowed\>\s+\<vlan\>\s+\<remove\>\s+\<vlan\>269',
        '\<no\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
        '\s+\<__XML__PARAM_value\>269',
    ]
    driver_result_dual_del2 = [
        '\<ethernet\>\s+\<interface\>1\/2\<\/interface\>\s+'
        '[\x20-\x7e\s]+\<switchport\>\s+\<trunk\>\s+'
        '\<allowed\>\s+\<vlan\>\s+\<remove\>\s+\<vlan\>269',
        '\<no\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
        '\s+\<__XML__PARAM_value\>269',
    ]
    test_configs = collections.OrderedDict(sorted(test_configs.items()))

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""
        super(TestCiscoNexusReplay, self).setUp()

        cfg.CONF.import_opt('api_workers', 'neutron.service')
        cfg.CONF.set_default('api_workers', 0)
        cfg.CONF.import_opt('rpc_workers', 'neutron.service')
        cfg.CONF.set_default('rpc_workers', 0)

        # Use a mock netconf client
        self.mock_ncclient = mock.Mock()
        mock.patch.object(nexus_network_driver.CiscoNexusDriver,
                          '_import_ncclient',
                          return_value=self.mock_ncclient).start()
        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.
        data_xml = {'connect.return_value.get.return_value.data_xml':
                    'switchport trunk allowed vlan none'}
        self.mock_ncclient.configure_mock(**data_xml)

        cfg.CONF.set_override('switch_heartbeat_time', 30, 'ml2_cisco')

        def new_nexus_init(mech_instance):
            mech_instance.driver = importutils.import_object(NEXUS_DRIVER)
            mech_instance.monitor_timeout = (
                cfg.CONF.ml2_cisco.switch_heartbeat_time)
            mech_instance._ppid = os.getpid()

            mech_instance._switch_state = {}
            mech_instance._nexus_switches = collections.OrderedDict()
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

    def _generate_port_context(self, port_config):
        """Returns port context from port_config."""

        host_name = port_config.host_name
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

        return port_context

    def _create_port(self, port_config):
        """Tests creation of a virtual port."""

        port_context = self._generate_port_context(port_config)

        self._cisco_mech_driver.create_port_postcommit(port_context)
        self._cisco_mech_driver.update_port_precommit(port_context)
        self._cisco_mech_driver.update_port_postcommit(port_context)
        for port_id in port_config.nexus_port.split(','):
            bindings = nexus_db_v2.get_nexusport_binding(
                           port_id,
                           port_config.vlan_id,
                           port_config.nexus_ip_addr,
                           port_config.instance_id)
            self.assertEqual(len(bindings), 1)

    def _delete_port(self, port_config):
        """Tests deletion of a virtual port."""
        port_context = self._generate_port_context(port_config)

        self._cisco_mech_driver.delete_port_precommit(port_context)
        self._cisco_mech_driver.delete_port_postcommit(port_context)
        for port_id in port_config.nexus_port.split(','):
            with testtools.ExpectedException(
                    exceptions.NexusPortBindingNotFound):
                nexus_db_v2.get_nexusport_binding(
                    port_id,
                    port_config.vlan_id,
                    port_config.nexus_ip_addr,
                    port_config.instance_id)

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

    def _basic_create_verify_port_vlan(self, test_name, test_result,
                                       nbr_of_bindings=1):
        """Create port vlan and verify results."""

        # Configure port entry config which puts switch in inactive state
        self._create_port(
            TestCiscoNexusReplay.test_configs[test_name])

        # Verify it's in the port binding data base
        # Add one to count for the reserved switch state entry
        port_cfg = TestCiscoNexusReplay.test_configs[test_name]
        assert(len(nexus_db_v2.get_nexusport_switch_bindings(
               port_cfg.nexus_ip_addr)) == nbr_of_bindings + 1)

        # Make sure there is only a single attempt to configure.
        self._verify_replay_results(test_result)

        # Clean all the ncclient mock_calls to clear exception
        # and other mock_call history.
        self.mock_ncclient.reset_mock()

    def _basic_delete_verify_port_vlan(self, test_name, test_result,
                                       nbr_of_bindings=0):
        """Create port vlan and verify results."""

        self._delete_port(
            TestCiscoNexusReplay.test_configs[test_name])

        # Verify port binding has been removed
        # Verify failure stats is not reset and
        # verify no driver transactions have been sent
        port_cfg = TestCiscoNexusReplay.test_configs[test_name]
        if nbr_of_bindings == 0:
            # Verify only the reserved switch state entry exists
            assert(len(nexus_db_v2.get_nexusport_switch_bindings(
                   port_cfg.nexus_ip_addr)) == 1)
        else:
            # Verify it's in the port binding data base
            # Add one to count for the reserved switch state entry
            assert(len(nexus_db_v2.get_nexusport_switch_bindings(
                   port_cfg.nexus_ip_addr)) == nbr_of_bindings + 1)

        # Make sure there is only a single attempt to configure.
        self._verify_replay_results(test_result)

        # Clean all the ncclient mock_calls to clear exception
        # and other mock_call history.
        self.mock_ncclient.reset_mock()

    def _process_replay(self, test1, test2,
                        if_init_result,
                        add_result1, add_result2,
                        replay_result,
                        del_result1, del_result2):
        """Tests create, replay, delete of two ports."""

        # Set all required connection state to True so
        # configurations will succeed
        port_cfg = TestCiscoNexusReplay.test_configs[test1]
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)
        port_cfg = TestCiscoNexusReplay.test_configs[test2]
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        self._basic_create_verify_port_vlan(
            test1, add_result1['driver_results'],
            add_result1['nbr_db_entries'])
        self._basic_create_verify_port_vlan(
            test2, add_result2['driver_results'],
            add_result2['nbr_db_entries'])

        # Set all connection state to False for
        # test case HOST_1, RP_NEXUS_IP_ADDRESS_1
        cfg_type = ['test_replay_unique1',
                    'test_replay_duplvlan1',
                    'test_replay_duplport1']
        for which_cfg in cfg_type:
            if which_cfg in [test1, test2]:
                state = const.SWITCH_INACTIVE
                port_cfg = TestCiscoNexusReplay.test_configs[which_cfg]
                self._cisco_mech_driver.set_switch_ip_and_active_state(
                    port_cfg.nexus_ip_addr, state)

        # Since only this test case connection state is False,
        # it should be the only one replayed
        self._cfg_monitor.check_connections()
        if not replay_result:
            replay_result = (if_init_result +
                            add_result1['driver_results'] +
                            add_result2['driver_results'])
        self._verify_replay_results(replay_result)

        # Clear mock_call history so we can evaluate
        # just the result of replay()
        self.mock_ncclient.reset_mock()

        self._basic_delete_verify_port_vlan(
                test2, del_result1['driver_results'],
                del_result1['nbr_db_entries'])
        self._basic_delete_verify_port_vlan(
                test1, del_result2['driver_results'],
                del_result2['nbr_db_entries'])

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
            else:
                return mock.DEFAULT
        return _side_effect_method

    def _set_nexus_type_failure(self):
        """Sets exception during ncclient get nexus type. """

        config = {'connect.return_value.get.side_effect':
            self._config_side_effects('show inventory',
            Exception(__name__))}
        self.mock_ncclient.configure_mock(**config)

    def _create_port_failure(self, attr, match_str, test_case, test_id,
                             which_exc=exceptions.NexusConfigFailed):
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
            switch_ip, const.SWITCH_ACTIVE)

        # Set up driver exception
        config = {attr:
            self._config_side_effects(match_str,
            Exception(test_id))}
        self.mock_ncclient.configure_mock(**config)

        self.assertRaises(
                exceptions.NexusConfigFailed,
                self._create_port,
                TestCiscoNexusReplay.test_configs[test_case])

        # _create_port should complete with no switch state change.
        self.assertEqual(
            self._cisco_mech_driver.get_switch_ip_and_active_state(switch_ip),
            const.SWITCH_ACTIVE)

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
            switch_ip, const.SWITCH_ACTIVE)

        self._create_port(
            TestCiscoNexusReplay.test_configs[test_case])

        # _create_port should complete successfully and no switch state change.
        self.assertEqual(
            self._cisco_mech_driver.get_switch_ip_and_active_state(switch_ip),
            const.SWITCH_ACTIVE)

        # Set up driver exception
        config = {attr:
            self._config_side_effects(match_str,
            Exception(test_id))}
        self.mock_ncclient.configure_mock(**config)

        self.assertRaises(
                exceptions.NexusConfigFailed,
                self._delete_port,
                TestCiscoNexusReplay.test_configs[test_case])

        # Verify nothing in the port binding data base
        # except Reserved Port Binding
        assert(len(nexus_db_v2.get_nexusport_switch_bindings(
               switch_ip)) == 1)

        # Verify nothing in the nve data base
        assert(len(nexus_db_v2.get_nve_switch_bindings(
               switch_ip)) == 0)

        # _delete_port should complete with no switch state change.
        self.assertEqual(
            self._cisco_mech_driver.get_switch_ip_and_active_state(switch_ip),
            const.SWITCH_ACTIVE)

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

        self._process_replay(
            'test_replay_unique1',
            'test_replay_unique2',
            self.driver_result_unique_init,
            first_add,
            second_add,
            self.driver_result_unique_2vlan_replay,
            first_del,
            second_del)

    def test_replay_duplicate_vlan(self):
        """Provides replay data and result data for duplicate vlans. """

        driver_result_duplvlan_add_vlan = [
            'configure\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
            '\s+\<__XML__PARAM_value\>267',
        ]
        driver_result_duplvlan_add1 = [
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>267',
        ]
        driver_result_duplvlan_add2 = [
            '\<interface\>1\/20\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>267',
        ]
        driver_result_duplvlan_del1 = [
            '\<interface\>1\/20\<\/interface\>\s+'
            '[\x20-\x7e\s]+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<remove\>\s+\<vlan\>267',
        ]
        driver_result_duplvlan_del2 = [
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e\s]+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<remove\>\s+\<vlan\>267',
            '\<no\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
            '\s+\<__XML__PARAM_value\>267',
        ]
        first_add = {'driver_results': (
                     driver_result_duplvlan_add_vlan +
                     driver_result_duplvlan_add1 +
                     driver_result_duplvlan_add_vlan +
                     driver_result_duplvlan_add2),
                     'nbr_db_entries': 2}
        # TODO(caboucha)
        # 'driver_result': [], until the correct fix for
        # the following issue is resolved.
        # https://review.openstack.org/#/c/241216/
        second_add = {'driver_results': (
                      driver_result_duplvlan_add_vlan +
                      driver_result_duplvlan_add1 +
                      driver_result_duplvlan_add2),
                      'nbr_db_entries': 4}
        first_del = {'driver_results': [],
                     'nbr_db_entries': 2}
        second_del = {'driver_results': (
                      driver_result_duplvlan_del2 +
                      driver_result_duplvlan_del1),
                      'nbr_db_entries': 0}

        self._process_replay('test_replay_duplvlan1',
                             'test_replay_duplvlan2',
                             [],
                             first_add, second_add,
                             (driver_result_duplvlan_add1 +
                              driver_result_duplvlan_add2 +
                              driver_result_duplvlan_add_vlan),
                             first_del, second_del)

    def test_replay_duplicate_ports(self):
        """Provides replay data and result data for duplicate ports. """

        driver_result_duplport_add_vlan = [
            'configure\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
            '\s+\<__XML__PARAM_value\>267',
        ]
        driver_result_duplport_add_if = [
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>267',
        ]
        driver_result_duplport_del1 = [
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e\s]+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<remove\>\s+\<vlan\>267',
            '\<no\>\s+\<vlan\>\s+<vlan-id-create-delete\>'
            '\s+\<__XML__PARAM_value\>267',
        ]
        first_add = {'driver_results':
                     (driver_result_duplport_add_vlan +
                     driver_result_duplport_add_if),
                     'nbr_db_entries': 1}
        # TODO(caboucha)
        # 'driver_result': [], until the correct fix for
        # the following issue is resolved.
        # https://review.openstack.org/#/c/241216/
        second_add = {'driver_results':
                      (driver_result_duplport_add_vlan +
                      driver_result_duplport_add_if),
                      'nbr_db_entries': 2}
        first_del = {'driver_results': [],
                     'nbr_db_entries': 1}
        second_del = {'driver_results':
                      driver_result_duplport_del1,
                      'nbr_db_entries': 0}

        self._process_replay('test_replay_duplport1',
                             'test_replay_duplport2',
                             [],
                             first_add, second_add,
                             (driver_result_duplport_add_if +
                             driver_result_duplport_add_vlan),
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
        port_cfg1 = TestCiscoNexusReplay.test_configs['test_replay_dual']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg1.nexus_ip_addr, const.SWITCH_ACTIVE)
        port_cfg2 = TestCiscoNexusReplay.test_configs['test_replay_dual2']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg2.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_dual',
            (self.driver_result_dual_add_vlan +
             self.driver_result_dual_add_if1),
            nbr_of_bindings=1)

        # Even though 2nd entry is inactive, there should be
        # a data base entry configured for it.
        # 2 = One entry for port the other for reserved binding
        assert(len(nexus_db_v2.get_nexusport_switch_bindings(
               port_cfg2.nexus_ip_addr)) == 2)

        # Clean-up the port entry
        self._basic_delete_verify_port_vlan('test_replay_dual',
            self.driver_result_dual_del1 + self.driver_result_dual_del2,
            nbr_of_bindings=0)

    def test_replay_port_success_if_one_switch_restored(self):
        """Verifies port restored after one of multi-switch restored."""

        # Make sure port is not rejected when there are multiple
        # switches and one is active.  Then proceed to bring-up
        # the other switch and it gets configured successfully.
        # Then remove all.
        port_cfg1 = TestCiscoNexusReplay.test_configs['test_replay_dual']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg1.nexus_ip_addr, const.SWITCH_ACTIVE)
        port_cfg2 = TestCiscoNexusReplay.test_configs['test_replay_dual2']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg2.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_dual',
            (self.driver_result_dual_add_vlan +
            self.driver_result_dual_add_if1),
            nbr_of_bindings=1)

        # Even though 2nd entry is inactive, there should be
        # a data base entry configured for it.
        # 2 = One entry for port the other for reserved binding
        assert(len(nexus_db_v2.get_nexusport_switch_bindings(
               port_cfg2.nexus_ip_addr)) == 2)

        # Restore port data for that switch
        self._cfg_monitor.check_connections()
        self._verify_replay_results(
            self.driver_result_dual_add_if2 +
            self.driver_result_dual_add_vlan)

        # Clear mock_call history.
        self.mock_ncclient.reset_mock()

        # Clean-up the port entries
        self._basic_delete_verify_port_vlan('test_replay_dual',
            self.driver_result_dual_del1 + self.driver_result_dual_del2,
            nbr_of_bindings=0)

    def test_replay_create_fails_if_single_switch_down(self):
        """Verifies port create fails if switch down."""

        # Make sure create ethernet config fails when the
        # switch state is inactive.
        port_cfg = TestCiscoNexusReplay.test_configs['test_replay_unique1']
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
        port_cfg = TestCiscoNexusReplay.test_configs['test_replay_unique1']
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
        port_cfg = TestCiscoNexusReplay.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_unique1',
            self.driver_result_unique_add1)

        # Make switch inactive before delete
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Clean-up the port entry
        self._basic_delete_verify_port_vlan('test_replay_unique1',
            self.driver_result_unique_del2, nbr_of_bindings=0)

    def test_replay_get_nexus_type_failure_two_switches(self):
        """Verifies exception during ncclient get inventory. """

        # There are two switches, one active and the other inactive.
        # Make sure 'get_nexus_type' fails so create_port_postcommit()
        # will return an exception.  'get_nexus_type' is used as
        # as ping so even if the switch is marked active then double
        # check it is indeed still active.  If not and thre are no
        # other active switches, then raise exception.
        port_cfg1 = TestCiscoNexusReplay.test_configs['test_replay_dual']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg1.nexus_ip_addr, const.SWITCH_ACTIVE)
        port_cfg2 = TestCiscoNexusReplay.test_configs['test_replay_dual2']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg2.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Set-up so get_nexus_type driver fails on active switch
        config = {'connect.return_value.get.side_effect':
            self._config_side_effects('show inventory',
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
        port_cfg = TestCiscoNexusReplay.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_unique1',
            self.driver_result_unique_add1)

        # Set-up so get_nexus_type driver fails
        config = {'connect.return_value.get.side_effect':
            self._config_side_effects('show inventory',
            Exception(__name__))}
        self.mock_ncclient.configure_mock(**config)

        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Perform replay which should not send back exception
        # but merely quit
        self._cfg_monitor.check_connections()

        # Since get of nexus_type failed, there should be
        # no attempt to configure anything.
        self._verify_replay_results([])

        # Clean-up the port entry
        self._basic_delete_verify_port_vlan('test_replay_unique1',
            self.driver_result_unique_del2)

    def test_replay_create_vlan_failure_during_replay(self):
        """Verifies exception during create vlan while replaying. """

        driver_result_unique_add_if1 = [
            '\<interface\>1\/10\<\/interface\>\s+'
            '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+'
            '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>267',
        ]
        vlan267 = '<vlan-id-create-delete\>\s+\<__XML__PARAM_value\>267'
        driver_result1 = [vlan267] * 2

        # Set switch state to False so replay config will start.
        # This should not affect user configuration.
        port_cfg = TestCiscoNexusReplay.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Set-up successful creation of port vlan config
        self._basic_create_verify_port_vlan('test_replay_unique1',
            self.driver_result_unique_add1)

        # set-up exception during create_vlan
        config = {'connect.return_value.edit_config.side_effect':
                  self._config_side_effects(
                      'vlan-id-create-delete',
                      Exception(__name__ + '1'))}
        self.mock_ncclient.configure_mock(**config)

        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        # Perform replay which should not send back exception
        # but merely quit
        self._cfg_monitor.check_connections()

        # Verify that switch is put back into INACTIVE state
        assert(self._cisco_mech_driver.get_switch_ip_and_active_state(
               port_cfg.nexus_ip_addr) ==
               const.SWITCH_INACTIVE)

        # The edit of create_vlan failed, but there will
        # be 2 create vlan attempts in mock call history.
        self._verify_replay_results(
            driver_result_unique_add_if1 + driver_result1)

        # Clear the edit driver exception for next test.
        config = {'connect.return_value.edit_config.side_effect':
                  None}
        self.mock_ncclient.configure_mock(**config)

        # Perform replay which should not send back exception
        # but merely quit
        self._cfg_monitor.check_connections()

        # Verify that switch is in ACTIVE state
        assert(self._cisco_mech_driver.get_switch_ip_and_active_state(
               port_cfg.nexus_ip_addr) ==
               const.SWITCH_ACTIVE)

        # Clear mock_call history.
        self.mock_ncclient.reset_mock()

        # Clean-up the port entry
        self._basic_delete_verify_port_vlan('test_replay_unique1',
            self.driver_result_unique_del2)

    def test_replay_vlan_batch_failure_during_replay(self):
        """Verifies handling of batch vlan during replay."""

        tmp_cfg = self.TestConfigObj(
            RP_NEXUS_IP_ADDRESS_1,
            RP_HOST_NAME_1,
            RP_NEXUS_PORT_1,
            RP_INSTANCE_1,
            RP_VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE)
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            tmp_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        # Create a batch of port entries with unique vlans
        num_vlans = const.CREATE_VLAN_BATCH + 10
        for x in range(num_vlans):
            new_cfg = tmp_cfg._replace(
                          vlan_id=RP_VLAN_ID_1 + x,
                          instance_id=RP_INSTANCE_1 + '-' + str(x))
            self._create_port(new_cfg)

        # Verify it goes back to inactive state
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            tmp_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)

        self._cfg_monitor.check_connections()

        # Verify the switch is in restore stage 2 state
        assert(self._cisco_mech_driver.get_switch_ip_and_active_state(
               tmp_cfg.nexus_ip_addr) ==
               const.SWITCH_RESTORE_S2)

        config = {'connect.return_value.edit_config.side_effect':
                  self._config_side_effects(
                      'vlan-id-create-delete',
                      Exception(__name__ + '1'))}
        self.mock_ncclient.configure_mock(**config)

        # Call check_connections() again  to attempt to send
        # last batch of 10 which should fail
        self._cfg_monitor.check_connections()
        # Verify the switch is back in INACTIVE state
        assert(self._cisco_mech_driver.get_switch_ip_and_active_state(
               tmp_cfg.nexus_ip_addr) ==
               const.SWITCH_INACTIVE)

        # Verify stored list of vlans is released

        # Clear mock_call history.
        self.mock_ncclient.reset_mock()

        # Clear the edit driver exception for next test.
        config = {'connect.return_value.edit_config.side_effect':
                  None}
        self.mock_ncclient.configure_mock(**config)

        # Call check_connections() again  to restart restore
        self._cfg_monitor.check_connections()

        # Verify the switch is in restore stage 2 state
        assert(self._cisco_mech_driver.get_switch_ip_and_active_state(
               tmp_cfg.nexus_ip_addr) ==
               const.SWITCH_RESTORE_S2)

        # Call check_connections() to successfully send
        # last batch of 10 which should fail
        self._cfg_monitor.check_connections()

        # Verify the switch is in restore stage 2 state
        assert(self._cisco_mech_driver.get_switch_ip_and_active_state(
               tmp_cfg.nexus_ip_addr) ==
               const.SWITCH_ACTIVE)

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
        addif = '\<interface\>1\/10\<\/interface\>\s+' \
                '[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+' \
                '\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>267'
        vlan267 = '<vlan-id-create-delete\>\s+\<__XML__PARAM_value\>267'
        driver_result2 = ([addif] + [vlan267] * 2) * 4

        config_replay = MAX_REPLAY_COUNT
        port_cfg = TestCiscoNexusReplay.test_configs['test_replay_unique1']
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
                  self._config_side_effects(
                      'vlan-id-create-delete',
                      Exception(__name__ + '1'))}
        self.mock_ncclient.configure_mock(**config)

        port_cfg = TestCiscoNexusReplay.test_configs['test_replay_unique1']
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_INACTIVE)
        for i in range(config_replay):
            self._cfg_monitor.check_connections()

        # Verify FAIL_CONFIG reached(MAX_REPLAY_COUNT) and there
        # were only MAX_REPLAY_COUNT+1 attempts to send create_vlan.
        # first is from test_replay_create_vlan_failure()
        # and MAX_REPLAY_COUNT from check_connections()
        assert(self._cisco_mech_driver.get_switch_replay_failure(
               const.FAIL_CONFIG,
               RP_NEXUS_IP_ADDRESS_1) ==
               config_replay)
        self._verify_replay_results(driver_result2)

        # Verify there exists a single port binding
        # plus 1 for reserved switch entry
        assert(len(nexus_db_v2.get_nexusport_switch_bindings(
               RP_NEXUS_IP_ADDRESS_1)) == 2)

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
        assert(self._cisco_mech_driver.get_switch_replay_failure(
               const.FAIL_CONFIG, RP_NEXUS_IP_ADDRESS_1) ==
               config_replay)
        assert(self._cisco_mech_driver.get_switch_replay_failure(
               const.FAIL_CONTACT, RP_NEXUS_IP_ADDRESS_1) ==
               config_replay)
        self._verify_replay_results([])

        # Test 3)
        # Verify delete transaction doesn't affect failure stats.
        self._basic_delete_verify_port_vlan('test_replay_unique1',
            self.driver_result_unique_del2)

        # Verify failure stats is not reset
        assert(self._cisco_mech_driver.get_switch_replay_failure(
               const.FAIL_CONFIG,
               RP_NEXUS_IP_ADDRESS_1) == config_replay)
        assert(self._cisco_mech_driver.get_switch_replay_failure(
               const.FAIL_CONTACT,
               RP_NEXUS_IP_ADDRESS_1) == config_replay)

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
        assert(self._cisco_mech_driver.get_switch_replay_failure(
               const.FAIL_CONFIG,
               RP_NEXUS_IP_ADDRESS_1) == 0)
        assert(self._cisco_mech_driver.get_switch_replay_failure(
               const.FAIL_CONTACT,
               RP_NEXUS_IP_ADDRESS_1) == 0)

        # Verify switch state is now active following successful replay.
        self.assertEqual(
            self._cisco_mech_driver.get_switch_ip_and_active_state(
                RP_NEXUS_IP_ADDRESS_1),
            const.SWITCH_ACTIVE)
