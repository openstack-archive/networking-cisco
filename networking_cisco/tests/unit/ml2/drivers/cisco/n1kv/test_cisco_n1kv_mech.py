# Copyright (c) 2015 Cisco Systems, Inc.
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

import mock
import webob.exc

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    mech_cisco_n1kv)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_client)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_db)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_sync)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    policy_profile_service)
from networking_cisco.tests.unit.ml2.drivers.cisco.n1kv import (
    fake_client)

from neutron.extensions import portbindings
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import config as ml2_config
from neutron.plugins.ml2.drivers import type_vlan as vlan_config
from neutron.plugins.ml2.drivers import type_vxlan as vxlan_config
from neutron.tests.unit.db import test_db_base_plugin_v2
from neutron.tests.unit.plugins.ml2.drivers import test_type_vlan
from neutron.tests.unit.plugins.ml2.drivers import test_type_vxlan

ML2_PLUGIN = 'neutron.plugins.ml2.plugin.Ml2Plugin'
SERVICE_PLUGIN = ('networking_cisco.plugins.ml2.drivers.cisco.n1kv.'
                  'policy_profile_service.PolicyProfilePlugin')
PHYS_NET = 'some-phys-net'
VLAN_MIN = 100
VLAN_MAX = 500
VXLAN_MIN = 5000
VXLAN_MAX = 6000
# Set to this based on fake_client, change there before changing here
DEFAULT_PP = 'pp-1'


# Mock for policy profile polling method- only does single call to populate
def _fake_poll_policy_profiles(self):
    self._populate_policy_profiles()


class TestN1KVMechanismDriver(
        test_db_base_plugin_v2.NeutronDbPluginV2TestCase):
    """Test Cisco Nexus1000V mechanism driver."""

    tenant_id = "some_tenant"

    DEFAULT_RESP_BODY = ""
    DEFAULT_RESP_CODE = 200
    DEFAULT_CONTENT_TYPE = ""
    fmt = "json"
    shared = False
    upd_shared = False

    def setUp(self):

        ml2_opts = {
            'mechanism_drivers': ['cisco_n1kv'],
            'extension_drivers': ['cisco_n1kv_ext'],
            'type_drivers': ['vlan', 'vxlan'],
            'tenant_network_types': ['vlan', 'vxlan']}
        ml2_cisco_opts = {
            'n1kv_vsm_ips': ['127.0.0.1'],
            'username': ['admin'],
            'password': ['Sfish123'],
            'default_policy_profile': DEFAULT_PP
        }
        for opt, val in ml2_opts.items():
            ml2_config.cfg.CONF.set_override(opt, val, 'ml2')

        for opt, val in ml2_cisco_opts.items():
            ml2_config.cfg.CONF.set_override(opt, val, 'ml2_cisco_n1kv')

        # Configure the ML2 VLAN parameters
        phys_vrange = ':'.join([PHYS_NET, str(VLAN_MIN), str(VLAN_MAX)])
        vlan_config.cfg.CONF.set_override('network_vlan_ranges',
                                          [phys_vrange],
                                          'ml2_type_vlan')
        # Configure the ML2 VXLAN parameters
        vxrange = ':'.join([str(VXLAN_MIN), str(VXLAN_MAX)])
        vxlan_config.cfg.CONF.set_override('vni_ranges',
                                           [vxrange],
                                           'ml2_type_vxlan')

        # Create a mock for all client operations. The N1KV client interacts
        # with the VSM via HTTP. Since we don't have a VSM running in the unit
        # tests, we need to 'fake' it by patching the client library itself.
        # We install a patch with a class that overrides the _do_request
        # function with something that verifies the values passed in and
        # returning the results of that verification. Using __name__ to
        # avoid having to enter the full module path.

        # For shared networks we need to use a different mock so that we
        # can check that the tenant_id override works correctly.
        if self.shared:
            client_patch = mock.patch(n1kv_client.__name__ + ".Client",
                                      new=fake_client.TestClientSharedNetwork)
            client_patch.start()
        # For tests that update the network to be shared, we need to have a
        # separate mock that initially checks the network create as normal
        # then verifies the tenant_id is set to 0 as expected on update.
        elif self.upd_shared:
            client_patch = mock.patch(n1kv_client.__name__ + ".Client",
                new=fake_client.TestClientUpdateSharedNetwork)
            client_patch.start()
        # Normal mock for most test cases- verifies request parameters.
        else:
            client_patch = mock.patch(n1kv_client.__name__ + ".Client",
                                      new=fake_client.TestClient)
            client_patch.start()
        # Create a mock for FullSync since there is no VSM at the time of UT.
        sync_patcher = mock.patch(n1kv_sync.
                                  __name__ + ".N1kvSyncDriver.do_sync")
        FakeSync = sync_patcher.start()
        # Return None for Full Sync for No Op
        FakeSync.return_value = None
        # Mock the policy profile polling method with a single call to populate
        (policy_profile_service.
         _poll_policy_profiles) = _fake_poll_policy_profiles
        # Setup the policy profile service plugin in order to load policy
        # profiles for testing
        service_plugins = {"CISCO_N1KV": SERVICE_PLUGIN}
        super(TestN1KVMechanismDriver,
              self).setUp(plugin=ML2_PLUGIN,
                          service_plugins=service_plugins)
        self.port_create_status = 'DOWN'


class TestN1KVMechDriverNetworkProfiles(TestN1KVMechanismDriver):

    def test_ensure_network_profiles_created(self):
        # Ensure that both network profiles are created
        profile = n1kv_db.get_network_profile_by_type(p_const.TYPE_VLAN)
        self.assertEqual(p_const.TYPE_VLAN, profile.segment_type)
        profile = n1kv_db.get_network_profile_by_type(p_const.TYPE_VXLAN)
        self.assertEqual(p_const.TYPE_VXLAN, profile.segment_type)
        # Ensure no additional profiles are created (get by type returns one())
        mech = mech_cisco_n1kv.N1KVMechanismDriver()
        mech._ensure_network_profiles_created_on_vsm()
        profile = n1kv_db.get_network_profile_by_type(p_const.TYPE_VLAN)
        self.assertEqual(p_const.TYPE_VLAN, profile.segment_type)
        profile = n1kv_db.get_network_profile_by_type(p_const.TYPE_VXLAN)
        self.assertEqual(p_const.TYPE_VXLAN, profile.segment_type)


class TestN1KVMechDriverBasicGet(test_db_base_plugin_v2.TestBasicGet,
                                 TestN1KVMechanismDriver):

    pass


class TestN1KVMechDriverHTTPResponse(test_db_base_plugin_v2.TestV2HTTPResponse,
                                     TestN1KVMechanismDriver):

    pass


class TestN1KVMechDriverNetworksV2(test_db_base_plugin_v2.TestNetworksV2,
                                   TestN1KVMechanismDriver):

    _shared_network_test_cases = (
        'test_create_public_network',
        'test_create_public_network_no_admin_tenant')
    _update_shared_network_test_cases = (
        'test_update_shared_network_noadmin_returns_403',
        'test_update_network_set_shared',
        'test_update_network_set_shared_owner_returns_403',
        'test_update_network_with_subnet_set_shared')

    def setUp(self):
        if self._testMethodName in self._shared_network_test_cases:
            self.shared = True
        elif self._testMethodName in self._update_shared_network_test_cases:
            self.upd_shared = True
        super(TestN1KVMechDriverNetworksV2, self).setUp()

    def test_create_network_with_default_n1kv_network_profile_id(self):
        """Test network create without passing network profile id."""
        with self.network() as network:
            np = n1kv_db.get_network_profile_by_type(p_const.TYPE_VLAN)
            net_np = n1kv_db.get_network_binding(network['network']['id'])
            self.assertEqual(network['network']['id'], net_np['network_id'])
            self.assertEqual(net_np['profile_id'], np['id'])

    def test_delete_network_with_default_n1kv_network_profile_id(self):
        """Test network delete without passing network profile id."""
        res = self._create_network(self.fmt, name='net', admin_state_up=True)
        network = self.deserialize(self.fmt, res)
        req = self.new_delete_request('networks', network['network']['id'])
        req.get_response(self.api)
        self.assertRaises(n1kv_exc.NetworkBindingNotFound,
                          n1kv_db.get_network_binding,
                          network['network']['id'])


class TestN1KVMechDriverPortsV2(test_db_base_plugin_v2.TestPortsV2,
                                TestN1KVMechanismDriver):

    VIF_TYPE = portbindings.VIF_TYPE_OVS
    HAS_PORT_FILTER = True

    def test_create_port_with_default_n1kv_policy_profile_id(self):
        """Test port create without passing policy profile id."""
        with self.port() as port:
            pp = n1kv_db.get_policy_profile_by_name(DEFAULT_PP)
            profile_binding = n1kv_db.get_policy_binding(port['port']['id'])
            self.assertEqual(profile_binding.profile_id, pp['id'])

    def test_delete_port_with_default_n1kv_policy_profile_id(self):
        """Test port delete without passing policy profile id."""
        with self.network() as network:
            res = self._create_port(self.fmt, network['network']['id'],
                                    webob.exc.HTTPCreated.code,
                                    tenant_id=network['network']['tenant_id'],
                                    set_context=True)
            port = self.deserialize(self.fmt, res)
            req = self.new_delete_request('ports', port['port']['id'])
            req.get_response(self.api)
            self.assertRaises(n1kv_exc.PortBindingNotFound,
                              n1kv_db.get_policy_binding,
                              port['port']['id'])


class TestN1KVMechDriverSubnetsV2(test_db_base_plugin_v2.TestSubnetsV2,
                                  TestN1KVMechanismDriver):

    pass


class TestN1KVMechDriverVlan(test_type_vlan.VlanTypeTest,
                             TestN1KVMechanismDriver):

    pass


class TestN1KVMechDriverVxlan(test_type_vxlan.VxlanTypeTest,
                              TestN1KVMechanismDriver):

    pass


class TestN1KVMechDriverVxlanMultiRange(
                                test_type_vxlan.VxlanTypeMultiRangeTest,
                                TestN1KVMechanismDriver):

    pass
