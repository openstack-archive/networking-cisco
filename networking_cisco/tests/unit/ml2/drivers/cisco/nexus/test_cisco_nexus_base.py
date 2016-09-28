# Copyright (c) 2015-2016 Cisco Systems, Inc.
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
Basic test Class and elements for testing Cisco Nexus platforms.
"""

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
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import driver_api as api
from neutron.tests.unit import testlib_api

# Static variables used in testing
NEXUS_IP_ADDRESS_1 = '1.1.1.1'
NEXUS_IP_ADDRESS_2 = '2.2.2.2'
NEXUS_IP_ADDRESS_3 = '3.3.3.3'
NEXUS_IP_ADDRESS_DUAL = '4.4.4.4'
NEXUS_IP_ADDRESS_DUAL2 = '5.5.5.5'
NEXUS_IP_ADDRESS_6 = '6.6.6.6'
NEXUS_IP_ADDRESS_7 = '7.7.7.7'
NEXUS_IP_ADDRESS_8 = '8.8.8.8'

HOST_NAME_1 = 'testhost1'
HOST_NAME_2 = 'testhost2'
HOST_NAME_PC = 'testpchost'
HOST_NAME_DUAL = 'testdualhost'
HOST_NAME_3 = 'testhost3'
HOST_NAME_4 = 'testhost4'
HOST_NAME_5 = 'testhost5'
HOST_NAME_6 = 'testhost6'
HOST_NAME_UNUSED = 'unused'

INSTANCE_1 = 'testvm1'
INSTANCE_2 = 'testvm2'
INSTANCE_PC = 'testpcvm'
INSTANCE_DUAL = 'testdualvm'

NEXUS_BAREMETAL_PORT_1 = 'Ethernet 1/10'
NEXUS_PORT_1 = 'ethernet:1/10'
NEXUS_PORT_2 = 'ethernet:1/20'
NEXUS_DUAL1 = 'ethernet:1/3'
NEXUS_DUAL2 = 'ethernet:1/2'
NEXUS_PORTCHANNELS = 'portchannel:2'
NEXUS_DUAL = 'ethernet:1/3,portchannel:2'
NEXUS_DUAL_2 = '1/2,1/3'

VLAN_ID_1 = 267
VLAN_ID_2 = 265
VLAN_ID_PC = 268
VLAN_ID_DUAL = 269

VXLAN_ID = 70000
NO_VXLAN_ID = 0

MCAST_GROUP = '255.1.1.1'

PHYSNET = 'physnet1'
NETID = 999
PORT_ID = 'fakePortID'

DEVICE_OWNER_BAREMETAL = 'baremetal:none'
DEVICE_OWNER_COMPUTE = 'compute:test'
DEVICE_OWNER_DHCP = n_const.DEVICE_OWNER_DHCP
DEVICE_OWNER_ROUTER_HA_INTF = n_const.DEVICE_OWNER_ROUTER_HA_INTF

NEXUS_SSH_PORT = '22'
PORT_STATE = n_const.PORT_STATUS_ACTIVE
NETWORK_TYPE = 'vlan'
VLAN_TYPE_TRUNK = 'trunk'
VLAN_TYPE_NATIVE = 'native'

NORMAL_VNIC = u'normal'
BAREMETAL_VNIC = u'baremetal'

CONNECT_ERROR = 'Unable to connect to Nexus'

## Test snippets used to verify nexus command output
RESULT_ADD_VLAN = """configure\>\s+\<vlan\>\s+\
<vlan-id-create-delete\>\s+\<__XML__PARAM_value\>{0}"""

RESULT_ADD_VLAN_VNI = """configure\>\s+\<vlan\>\s+\
<vlan-id-create-delete\>\s+\<__XML__PARAM_value\>{0}[\x20-\x7e]+\
\s+[\x20-\x7e]+\s+\<vn-segment\>\s+\<vlan-vnsegment\>{1}"""

RESULT_ADD_INTERFACE = """\<{0}\>\s+\<interface\>\
{1}\<\/interface\>\s+[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+\
\<allowed\>\s+\<vlan\>\s+\<add\>\s+\<vlan_id\>{2}"""

RESULT_ADD_NATIVE_INTERFACE = """\<{0}\>\s+\<interface\>\
{1}\<\/interface\>\s+[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+\
\<native\>\s+\<vlan\>\s+\<vlan_id\>{2}"""

RESULT_ADD_NVE_INTERFACE = """\<interface\>\s+\
\<nve\>nve{0}\<\/nve\>\s+[\x20-\x7e]+\s+\<member\>member vni {1} \
mcast-group {2}"""

RESULT_INTERFACE = """\<{0}\>\s+\<interface\>\
{1}\<\/interface\>\s+[\x20-\x7e]+\s+\<switchport\>\s+\<trunk\>\s+\
\<allowed\>\s+\<vlan\>\s+\<vlan_id\>{2}"""

RESULT_DEL_VLAN = """\
\<no\>\s+\<vlan\>\s+<vlan-id-create-delete\>\
\s+\<__XML__PARAM_value\>{0}"""

RESULT_DEL_INTERFACE = """\
\<{0}\>\s+\<interface\>{1}\<\/interface\>\s+\
[\x20-\x7e\s]+\<switchport\>\s+\<trunk\>\s+\
\<allowed\>\s+\<vlan\>\s+\<remove\>\s+\<vlan\>{2}"""

RESULT_DEL_NATIVE_INTERFACE = """\
\<{0}\>\s+\<interface\>{1}\<\/interface\>\s+\
[\x20-\x7e\s]+\<no\>\s+\<switchport\>\s+\<trunk\>\s+\
\<native\>"""

RESULT_DEL_NVE_INTERFACE = """\<interface\>\s+\
\<nve\>nve{0}\<\/nve\>\s+[\x20-\x7e]+\s+\<member\>no member vni {1}"""

NEXUS_DRIVER = ('networking_cisco.plugins.ml2.drivers.cisco.nexus.'
                'nexus_network_driver.CiscoNexusDriver')


class FakeNetworkContext(object):
    """Network context for testing purposes only."""

    def __init__(self, segment_id, nw_type, mcast_group='physnet1',
                 netid=None):

        if not netid:
            netid = NETID
        self._network_segments = {api.SEGMENTATION_ID: segment_id,
                                  api.ID: netid,
                                  api.NETWORK_TYPE: nw_type,
                                  const.PROVIDER_SEGMENT: False,
                                  api.PHYSICAL_NETWORK: mcast_group}

    @property
    def network_segments(self):
        return self._network_segments

    @property
    def current(self):
        return self._network_segments


class FakePortContext(object):

    """Port context for testing purposes only."""

    def __init__(self, device_id, host_name, device_owner,
                 network_context, bottom_segment=None,
                 profile=None, vnic_type=u'normal', netid=None):
        if profile is None:
            profile = []
        if not netid:
            netid = NETID
        self._set_port(device_id, host_name, device_owner,
                       profile, vnic_type, netid)
        self._port_orig = None
        self._network = network_context
        if network_context:
            self._segment = network_context.network_segments
            self.segments_to_bind = [network_context.network_segments]
        if bottom_segment is None:
            self._bottom_segment = None
        else:
            self._bottom_segment = bottom_segment.network_segments
        self._segments_to_bind = None

    def _set_port(self, device_id, host_name, device_owner,
                  profile=None, vnic_type=u'normal', netid=None):

        self._port = {
            'status': PORT_STATE,
            'device_id': device_id,
            'device_owner': device_owner,
            api.ID: PORT_ID,
            'network_id': netid,
            portbindings.HOST_ID: host_name,
            portbindings.VNIC_TYPE: vnic_type,
            portbindings.PROFILE: profile,
            portbindings.VIF_TYPE: portbindings.VIF_TYPE_OVS
        }

    def set_orig_port(self, device_id, host_name, device_owner,
                      profile=None, vnic_type=u'normal', netid=None):

        self._port_orig = {
            'status': PORT_STATE,
            'device_id': device_id,
            'device_owner': device_owner,
            api.ID: PORT_ID,
            'network_id': netid,
            portbindings.HOST_ID: host_name,
            portbindings.VNIC_TYPE: vnic_type,
            portbindings.PROFILE: profile,
            portbindings.VIF_TYPE: portbindings.VIF_TYPE_OVS
        }

    @property
    def current(self):
        return self._port

    @property
    def original(self):
        return self._port_orig

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

    def continue_binding(self, segment_id, next_segments_to_bind):
        pass

    def set_binding(self, segment_id, vif_type, vif_details,
                    status=None):
        pass

    def allocate_dynamic_segment(self, segment):
        pass

    def _prepare_to_bind(self, segments_to_bind):
        self._segments_to_bind = segments_to_bind
        self._new_bound_segment = None
        self._next_segments_to_bind = None


class FakeUnbindPortContext(FakePortContext):
    """Port context used during migration to unbind port."""
    @property
    def top_bound_segment(self):
        return None

    @property
    def bottom_bound_segment(self):
        return None

    @property
    def original_top_bound_segment(self):
        return self._segment

    @property
    def original_bottom_bound_segment(self):
        return self._bottom_segment


class TestCiscoNexusBase(testlib_api.SqlTestCase):
    """Feature Base Test Class for Cisco ML2 Nexus driver."""

    TestConfigObj = collections.namedtuple(
        'TestConfigObj',
        'nexus_ip_addr host_name nexus_port instance_id vlan_id vxlan_id '
        'mcast_group device_owner profile vnic_type')

    def _mock_init(self):
        # this is to prevent interface initialization from occurring
        # which adds unnecessary noise to the results.

        data_xml = {'connect.return_value.get.return_value.data_xml':
                    'switchport trunk allowed vlan none'}
        self.mock_ncclient.configure_mock(**data_xml)

    def _clear_port_dbs(self):
        nexus_db_v2.remove_all_nexusport_bindings()

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        super(TestCiscoNexusBase, self).setUp()

        cfg.CONF.import_opt('api_workers', 'neutron.service')
        cfg.CONF.set_default('api_workers', 0)
        cfg.CONF.import_opt('rpc_workers', 'neutron.service')
        cfg.CONF.set_default('rpc_workers', 0)

        # Use a mock netconf client
        self.mock_ncclient = mock.Mock()
        mock.patch.object(nexus_network_driver.CiscoNexusDriver,
                          '_import_ncclient',
                          return_value=self.mock_ncclient).start()

        self.mock_continue_binding = mock.patch.object(
            FakePortContext,
            'continue_binding').start()

        self._mock_init()

        def new_nexus_init(mech_instance):
            mech_instance.driver = importutils.import_object(NEXUS_DRIVER)
            mech_instance.monitor_timeout = (
                cfg.CONF.ml2_cisco.switch_heartbeat_time)
            mech_instance._ppid = os.getpid()

            mech_instance._switch_state = {}
            mech_instance._nexus_switches = collections.OrderedDict()
            for name, config in self.test_configs.items():
                ip_addr = config.nexus_ip_addr
                host_name = config.host_name
                nexus_port = config.nexus_port
                # baremetal config done differently
                if not ip_addr:
                    continue
                if host_name is not HOST_NAME_UNUSED:
                    if (ip_addr, host_name) in mech_instance._nexus_switches:
                        saved_port = (mech_instance._nexus_switches[
                            (ip_addr, host_name)])
                        if saved_port != nexus_port:
                            mech_instance._nexus_switches[
                                (ip_addr, host_name)] = (
                                    saved_port + ',' + nexus_port)
                    else:
                        mech_instance._nexus_switches[
                            (ip_addr, host_name)] = nexus_port
                mech_instance._nexus_switches[(ip_addr,
                                               'ssh_port')] = NEXUS_SSH_PORT
                mech_instance._nexus_switches[(ip_addr,
                                               constants.USERNAME)] = 'admin'
                mech_instance._nexus_switches[(ip_addr,
                                              constants.PASSWORD)] = 'password'
                mech_instance._nexus_switches[(ip_addr,
                                              'physnet')] = PHYSNET
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
        self.addCleanup(self._clear_port_dbs)

    def _generate_port_context(self, port_config,
                               override_host_name=None,
                               override_netid=None,
                               unbind_port=False):
        """Returns port context from port_config."""

        if override_host_name:
            host_name = override_host_name
        else:
            host_name = port_config.host_name
        instance_id = port_config.instance_id
        vlan_id = port_config.vlan_id
        vxlan_id = port_config.vxlan_id
        mcast_group = port_config.mcast_group
        device_owner = port_config.device_owner
        profile = port_config.profile
        vnic_type = port_config.vnic_type
        if override_netid:
            netid = override_netid
        else:
            netid = None

        network_context = FakeNetworkContext(vlan_id, NETWORK_TYPE, netid)
        if vxlan_id != NO_VXLAN_ID:
            vxlan_network_context = FakeNetworkContext(vxlan_id,
                const.TYPE_NEXUS_VXLAN, mcast_group, netid)
            if unbind_port:
                port_context = FakeUnbindPortContext(
                    instance_id, host_name, device_owner,
                    vxlan_network_context, network_context,
                    profile, vnic_type, netid)
            else:
                port_context = FakePortContext(
                    instance_id, host_name, device_owner,
                    vxlan_network_context, network_context,
                    profile, vnic_type, netid)
        else:
            if unbind_port:
                port_context = FakeUnbindPortContext(
                    instance_id, host_name, device_owner,
                    network_context, None,
                    profile, vnic_type, netid)
            else:
                port_context = FakePortContext(
                    instance_id, host_name, device_owner,
                    network_context, None,
                    profile, vnic_type, netid)

        return port_context

    def _bind_port(self, port_config, expect_success=True):
        """Tests creation of a virtual port."""

        port_context = self._generate_port_context(port_config)

        self.mock_set_binding = mock.patch.object(
            FakePortContext,
            'set_binding').start()

        port_context._prepare_to_bind(port_context)
        self._cisco_mech_driver.bind_port(port_context)

    def _create_port(self, port_config, override_netid=None):
        """Tests creation of a virtual port."""

        port_context = self._generate_port_context(
            port_config, override_netid=override_netid)

        self._cisco_mech_driver.create_port_postcommit(port_context)
        self._cisco_mech_driver.update_port_precommit(port_context)
        self._cisco_mech_driver.update_port_postcommit(port_context)

        if self._cisco_mech_driver._is_baremetal(port_context.current):
            connections = self._cisco_mech_driver._get_port_connections(
                port_context.current, '')
        else:
            connections = self._cisco_mech_driver._get_port_connections(
                port_context.current, port_config.host_name)

        # for port_id in port_config.nexus_port.split(','):
        for switch_ip, intf_type, port, is_p_vlan in connections:
            if switch_ip is not port_config.nexus_ip_addr:
                continue
            port_id = intf_type + ':' + port
            bindings = nexus_db_v2.get_nexusport_binding(
                           port_id,
                           port_config.vlan_id,
                           port_config.nexus_ip_addr,
                           port_config.instance_id)
            self.assertEqual(1, len(bindings))

    def _delete_port(self, port_config):
        """Tests deletion of a virtual port."""
        port_context = self._generate_port_context(port_config)

        self._cisco_mech_driver.delete_port_precommit(port_context)
        self._cisco_mech_driver.delete_port_postcommit(port_context)

        if self._cisco_mech_driver._is_baremetal(port_context.current):
            connections = self._cisco_mech_driver._get_port_connections(
                port_context.current, '')
        else:
            connections = self._cisco_mech_driver._get_port_connections(
                port_context.current, port_config.host_name)

        # for port_id in port_config.nexus_port.split(','):
        for switch_ip, intf_type, port, is_p_vlan in connections:
            if switch_ip is not port_config.nexus_ip_addr:
                continue
            port_id = intf_type + ':' + port
            with testtools.ExpectedException(
                    exceptions.NexusPortBindingNotFound):
                nexus_db_v2.get_nexusport_binding(
                    port_id,
                    port_config.vlan_id,
                    port_config.nexus_ip_addr,
                    port_config.instance_id)

    def _verify_results(self, driver_result):
        """Verifies correct entries sent to Nexus."""

        self.assertEqual(
            len(driver_result),
            self.mock_ncclient.connect.return_value.
            edit_config.call_count,
            "Unexpected driver count")

        for idx in range(0, len(driver_result)):
            self.assertIsNotNone(
                self.mock_ncclient.connect.
                return_value.edit_config.mock_calls[idx][2]['config'],
                "mock_data is None")
            # assign None to skip testing this one.
            if driver_result[idx]:
                self.assertIsNotNone(
                    re.search(driver_result[idx],
                        self.mock_ncclient.connect.return_value.
                        edit_config.mock_calls[idx][2]['config']),
                    "Expected result data not found")

    def _basic_create_verify_port_vlan(self, test_name, test_result,
                                       nbr_of_bindings=1,
                                       other_test=None):
        """Create port vlan and verify results."""

        if other_test is None:
            other_test = self.test_configs[test_name]

        # Configure port entry config which puts switch in inactive state
        self._create_port(other_test)

        # Verify it's in the port binding data base
        # Add one to count for the reserved switch state entry
        # if replay is enabled
        port_cfg = other_test
        if self._cisco_mech_driver.is_replay_enabled():
            nbr_of_bindings += 1
        try:
            port_bindings = nexus_db_v2.get_nexusport_switch_bindings(
                port_cfg.nexus_ip_addr)
        except exceptions.NexusPortBindingNotFound:
            port_bindings = []
        self.assertEqual(nbr_of_bindings, len(port_bindings))

        # Make sure there is only a single attempt to configure.
        self._verify_results(test_result)

        # Clean all the ncclient mock_calls to clear exception
        # and other mock_call history.
        self.mock_ncclient.reset_mock()

    def _basic_delete_verify_port_vlan(self, test_name, test_result,
                                       nbr_of_bindings=0,
                                       other_test=None):
        """Create port vlan and verify results."""

        if other_test is None:
            other_test = self.test_configs[test_name]

        self._delete_port(other_test)

        # Verify port binding has been removed
        # Verify failure stats is not reset and
        # verify no driver transactions have been sent
        port_cfg = other_test
        if self._cisco_mech_driver.is_replay_enabled():
            # Add one for the reserved switch state entry
            nbr_of_bindings += 1
        try:
            port_bindings = nexus_db_v2.get_nexusport_switch_bindings(
                port_cfg.nexus_ip_addr)
        except exceptions.NexusPortBindingNotFound:
            port_bindings = []
        self.assertEqual(nbr_of_bindings, len(port_bindings))

        # Make sure there is only a single attempt to configure.
        self._verify_results(test_result)

        # Clean all the ncclient mock_calls to clear exception
        # and other mock_call history.
        self.mock_ncclient.reset_mock()

    def _create_delete_port(self, test_name,
                            add_result, del_result):
        """Tests creation and deletion of a virtual port."""

        self._basic_create_verify_port_vlan(
            test_name,
            add_result)

        self._basic_delete_verify_port_vlan(
            test_name,
            del_result)

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

    def _set_nexus_type_failure(self):
        """Sets exception during ncclient get nexus type. """

        config = {'connect.return_value.get.side_effect':
            self._config_side_effects_on_count('show inventory',
            Exception(__name__))}
        self.mock_ncclient.configure_mock(**config)

    def _create_port_valid_exception(self, attr, match_str, test_case,
                                     which_exc):
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
        which_exc: Acceptable exception String to raise in exception.
        """

        # Set switch state to active
        switch_ip = self.test_configs[test_case].nexus_ip_addr
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            switch_ip, const.SWITCH_ACTIVE)

        # Clean all the ncclient mock_calls to clear exception
        # and other mock_call history.
        self.mock_ncclient.reset_mock()

        # Set up driver exception
        config = {attr:
            self._config_side_effects_on_count(match_str,
            Exception(which_exc))}
        self.mock_ncclient.configure_mock(**config)

        self._create_port(self.test_configs[test_case])

        # _create_port should complete with no switch state change.
        self.assertEqual(
            const.SWITCH_ACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(switch_ip))

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
        which_exc: Exception expecting to encounter
        """

        # Set switch state to active
        switch_ip = self.test_configs[test_case].nexus_ip_addr
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            switch_ip, const.SWITCH_ACTIVE)

        # Clean all the ncclient mock_calls to clear exception
        # and other mock_call history.
        self.mock_ncclient.reset_mock()

        # Set up driver exception
        config = {attr:
            self._config_side_effects_on_count(match_str,
            Exception(test_id))}
        self.mock_ncclient.configure_mock(**config)

        e = self.assertRaises(
                which_exc,
                self._create_port,
                self.test_configs[test_case])
        self.assertIn(test_id, six.u(str(e)))

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
        switch_ip = self.test_configs[test_case].nexus_ip_addr
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            switch_ip, const.SWITCH_ACTIVE)

        self._create_port(
            self.test_configs[test_case])

        # _create_port should complete successfully and no switch state change.
        self.assertEqual(
            const.SWITCH_ACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(switch_ip))

        # Clean all the ncclient mock_calls to clear exception
        # and other mock_call history.
        self.mock_ncclient.reset_mock()

        # Set up driver exception
        config = {attr:
            self._config_side_effects_on_count(match_str,
            Exception(test_id))}
        self.mock_ncclient.configure_mock(**config)

        self.assertRaises(
             exceptions.NexusConfigFailed,
             self._delete_port,
             self.test_configs[test_case])

        # Verify nothing in the port binding data base
        # except Reserved Port Binding if replay is enabled
        nbr_bindings = 1 if self._cisco_mech_driver.is_replay_enabled() else 0
        try:
            port_bindings = nexus_db_v2.get_nexusport_switch_bindings(
                switch_ip)
        except exceptions.NexusPortBindingNotFound:
            port_bindings = []

        self.assertEqual(nbr_bindings, len(port_bindings))

        # Verify nothing in the nve data base
        self.assertEqual(0,
            len(nexus_db_v2.get_nve_switch_bindings(switch_ip)))

        # _delete_port should complete with no switch state change.
        self.assertEqual(
            const.SWITCH_ACTIVE,
            self._cisco_mech_driver.get_switch_ip_and_active_state(switch_ip))


class TestCiscoNexusReplayBase(TestCiscoNexusBase):
    """Replay Base Test Class for Cisco ML2 Nexus driver."""

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('switch_heartbeat_time', 30, 'ml2_cisco')
        super(TestCiscoNexusReplayBase, self).setUp()

    def _process_replay(self, test1, test2,
                        if_init_result,
                        add_result1, add_result2,
                        replay_result,
                        del_result1, del_result2,
                        replay_init=None):
        """Tests create, replay, delete of two ports."""

        # Set all required connection state to True so
        # configurations will succeed
        port_cfg = self.test_configs[test1]
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)
        port_cfg = self.test_configs[test2]
        self._cisco_mech_driver.set_switch_ip_and_active_state(
            port_cfg.nexus_ip_addr, const.SWITCH_ACTIVE)

        self._basic_create_verify_port_vlan(
            test1, add_result1['driver_results'],
            add_result1['nbr_db_entries'])
        self._basic_create_verify_port_vlan(
            test2, add_result2['driver_results'],
            add_result2['nbr_db_entries'])

        # Set all connection state to False for
        # test case HOST_1, NEXUS_IP_ADDRESS_1
        cfg_type = ['test_replay_unique1',
                    'test_replay_duplvlan1',
                    'test_replay_duplport1']
        for which_cfg in cfg_type:
            if which_cfg in [test1, test2]:
                state = const.SWITCH_INACTIVE
                port_cfg = self.test_configs[which_cfg]
                self._cisco_mech_driver.set_switch_ip_and_active_state(
                    port_cfg.nexus_ip_addr, state)

        if replay_init:
            replay_init()
        # Since only this test case connection state is False,
        # it should be the only one replayed
        self._cfg_monitor.check_connections()
        if not replay_result:
            replay_result = (if_init_result +
                            add_result1['driver_results'] +
                            add_result2['driver_results'])
        self._verify_results(replay_result)

        # Clear mock_call history so we can evaluate
        # just the result of replay()
        self.mock_ncclient.reset_mock()

        self._basic_delete_verify_port_vlan(
                test2, del_result1['driver_results'],
                del_result1['nbr_db_entries'])
        self._basic_delete_verify_port_vlan(
                test1, del_result2['driver_results'],
                del_result2['nbr_db_entries'])


class TestContext(TestCiscoNexusBase):
    """Verify Context Blocks for Cisco ML2 Nexus driver."""

    # TODO(caboucha) Put VLAN_TYPE_TRUNK in switch_info for now.
    baremetal_profile = {
        "local_link_information": [
            {
                "switch_id": "10.86.1.129",
                "port_id": "portchannel:1",
                "switch_info": VLAN_TYPE_TRUNK,
            },
            {
                "switch_id": "10.86.1.128",
                "port_id": "portchannel:1",
                "switch_info": VLAN_TYPE_TRUNK,
            },
        ]
    }

    test_configs = {
        'test_vlan_unique1': TestCiscoNexusBase.TestConfigObj(
            NEXUS_IP_ADDRESS_1,
            HOST_NAME_1,
            NEXUS_PORT_1,
            INSTANCE_1,
            VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE,
            {},
            NORMAL_VNIC),
        'test_vxlan_unique1': TestCiscoNexusBase.TestConfigObj(
            NEXUS_IP_ADDRESS_1,
            HOST_NAME_1,
            NEXUS_PORT_1,
            INSTANCE_1,
            VLAN_ID_1,
            VXLAN_ID,
            '225.1.1.1',
            DEVICE_OWNER_COMPUTE,
            {},
            NORMAL_VNIC),
        'test_bm_vlan_unique1': TestCiscoNexusBase.TestConfigObj(
            NEXUS_IP_ADDRESS_1,
            HOST_NAME_1,
            NEXUS_PORT_1,
            INSTANCE_1,
            VLAN_ID_1,
            NO_VXLAN_ID,
            None,
            DEVICE_OWNER_COMPUTE,
            baremetal_profile,
            BAREMETAL_VNIC),
    }
    test_configs = collections.OrderedDict(sorted(test_configs.items()))

    def _verify_port_context(self, context, config):
        vlan_segment, vxlan_segment = (
            self._cisco_mech_driver._get_segments(
                context.top_bound_segment,
                context.bottom_bound_segment))
        port = context.current

        if port['device_id'] != config.instance_id:
            return 'device_id mismatch'
        if port[portbindings.HOST_ID] != config.host_name:
            return 'host_name mismatch'
        if vlan_segment[api.SEGMENTATION_ID] != config.vlan_id:
            return 'vlan_id mismatch'
        if vlan_segment[api.NETWORK_TYPE] != p_const.TYPE_VLAN:
            return 'network_type mismatch'
        if port['device_owner'] != config.device_owner:
            return 'device_owner mismatch'
        if vxlan_segment:
            if (vxlan_segment[api.PHYSICAL_NETWORK] !=
                config.mcast_group):
                return 'mcast_group mismatch'
            if (vxlan_segment[api.SEGMENTATION_ID] !=
                config.vxlan_id):
                return 'vxlan_id mismatch'

        if port[portbindings.VNIC_TYPE] != config.vnic_type:
            return 'vnic_type mismatch'

        if config.vnic_type == u'baremetal':
            profile = port[portbindings.PROFILE]['local_link_information']
            cfg_profile = config.profile['local_link_information']
            if (len(profile) != len(cfg_profile) or
                len(profile) == 0):
                return 'profile_len'

            mylen = len(profile)
            for i in range(mylen):
                if (profile[i]['switch_id'] !=
                   cfg_profile[i]['switch_id']):
                    return 'profile.switch_id mismatch'
                if (profile[i]['port_id'] !=
                    cfg_profile[i]['port_id']):
                    return 'profile.port_id mismatch'
                if (profile[i]['switch_info'] !=
                    cfg_profile[i]['switch_info']):
                    return 'profile_switch_info mismatch'
        elif config.vnic_type == u'normal':
            pass
        else:
            return 'vnic_type invalid'

    def test_normal_vlan_format(self):
        port_context = self._generate_port_context(
                self.test_configs['test_vlan_unique1'])

        self.assertIsNone(
            self._verify_port_context(
                port_context,
                self.test_configs['test_vlan_unique1']))

    def test_normal_vxlan_format(self):
        port_context = self._generate_port_context(
                self.test_configs['test_vxlan_unique1'])

        self.assertIsNone(
            self._verify_port_context(
                port_context,
                self.test_configs['test_vxlan_unique1']))

    def test_baremetal_format(self):
        port_context = self._generate_port_context(
                self.test_configs['test_bm_vlan_unique1'])

        self.assertIsNone(
            self._verify_port_context(
                port_context,
                self.test_configs['test_bm_vlan_unique1']))
