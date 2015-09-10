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
    config as ml2_n1kv_config)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
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
from networking_cisco.plugins.ml2.drivers.cisco.n1kv.extensions import (
    network_profile as network_profile_module)
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
POLICY_PROFILE_PLUGIN = ('networking_cisco.plugins.ml2.drivers.cisco.n1kv.'
                  'policy_profile_service.PolicyProfilePlugin')
NETWORK_PROFILE_PLUGIN = ('networking_cisco.plugins.ml2.drivers.cisco.n1kv.'
                  'network_profile_service.NetworkProfilePlugin')

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
    vsm_retry = False

    def setUp(self):

        ml2_opts = {
            'mechanism_drivers': ['cisco_n1kv'],
            'extension_drivers': ['cisco_n1kv_ext'],
            'type_drivers': ['vlan', 'vxlan'],
            'tenant_network_types': ['vlan', 'vxlan']}
        ml2_cisco_opts = {
            'n1kv_vsm_ips': ['127.0.0.1'],
            'username': 'admin',
            'password': 'Sfish123',
            'default_policy_profile': DEFAULT_PP
        }
        for opt, val in ml2_opts.items():
            ml2_config.cfg.CONF.set_override(opt, val, 'ml2')

        for opt, val in ml2_cisco_opts.items():
            ml2_n1kv_config.cfg.CONF.set_override(opt, val, 'ml2_cisco_n1kv')

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
        # For tests that update the network to be shared, we need to have a
        # separate mock that initially checks the network create as normal
        # then verifies the tenant_id is set to 0 as expected on update.
        elif self.upd_shared:
            client_patch = mock.patch(n1kv_client.__name__ + ".Client",
                new=fake_client.TestClientUpdateSharedNetwork)
        elif self.vsm_retry:
            client_patch = mock.patch(n1kv_client.__name__ + ".Client",
                new=fake_client.TestClientVSMRetry)
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
        service_plugins = {
            "CISCO_N1KV_POLICY_PROFILE_PLUGIN": POLICY_PROFILE_PLUGIN,
            "CISCO_N1KV_NETWORK_PROFILE_PLUGIN": NETWORK_PROFILE_PLUGIN}
        super(TestN1KVMechanismDriver,
              self).setUp(plugin=ML2_PLUGIN,
                          service_plugins=service_plugins,
                          ext_mgr=network_profile_module.Network_profile())
        self.port_create_status = 'DOWN'

    def network_profile(self, data):
        net_prof_req = self.new_create_request('network_profiles', data)
        res = net_prof_req.get_response(self.ext_api)
        if res.status_int < webob.exc.HTTPClientError.code:
            return self.deserialize(self.fmt, res)

    def get_test_network_profile_dict(self, segment_type,
                                      multicast_ip_range=None,
                                      sub_type=None,
                                      name='test-net-profile',
                                      tenant_id='admin'):
        net_prof = {"network_profile": {
            "name": name,
            "segment_type": segment_type,
            "tenant_id": tenant_id}
        }
        valid_subtypes = [n1kv_const.CLI_VXLAN_MODE_ENHANCED,
                          n1kv_const.CLI_VXLAN_MODE_NATIVE]
        if segment_type == p_const.TYPE_VLAN:
            net_prof["network_profile"]["physical_network"] = "physnet"
        elif segment_type == p_const.TYPE_VXLAN:
            self.assertIn(needle=sub_type, haystack=valid_subtypes)
            net_prof["network_profile"]["sub_type"] = sub_type
            if multicast_ip_range:
                net_prof["network_profile"]["multicast_ip_range"] = (
                    multicast_ip_range)
        return net_prof


class TestN1KVMechDriverNetworkProfiles(TestN1KVMechanismDriver):

    def test_ensure_network_profiles_created(self):
        # Ensure that both network profiles are created
        profile = n1kv_db.get_network_profile_by_type(p_const.TYPE_VLAN)
        self.assertEqual(p_const.TYPE_VLAN, profile.segment_type)
        profile = n1kv_db.get_network_profile_by_type(p_const.TYPE_VXLAN)
        self.assertEqual(p_const.TYPE_VXLAN, profile.segment_type)
        # Ensure no additional profiles are created (get by type returns one())
        mech = mech_cisco_n1kv.N1KVMechanismDriver()
        mech.initialize()
        mech._ensure_network_profiles_created_on_vsm()
        profile = n1kv_db.get_network_profile_by_type(p_const.TYPE_VLAN)
        self.assertEqual(p_const.TYPE_VLAN, profile.segment_type)
        profile = n1kv_db.get_network_profile_by_type(p_const.TYPE_VXLAN)
        self.assertEqual(p_const.TYPE_VXLAN, profile.segment_type)

    def test_create_network_profile_vlan(self):
        """Test a VLAN network profile creation."""
        data = self.get_test_network_profile_dict(segment_type='vlan')
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPCreated.code, res.status_int)

    def test_create_network_profile_overlay_native(self):
        """Test a native VxLAN network profile creation."""
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            multicast_ip_range="224.1.1.1-224.1.1.10",
            sub_type='native')
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPCreated.code, res.status_int)

    def test_create_network_profile_overlay_native_invalid_mcast(self):
        """
        Test a native VxLAN network profile creation with invalid
        multi-cast address.

        """

        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            multicast_ip_range="3.1.1.1-2.1.1.10",
            sub_type='native')
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPBadRequest.code, res.status_int)

    def test_create_network_profile_overlay_native_reserved_mcast(self):
        """
        Test a native VxLAN network profile creation with reserved
        multi-cast address.

        """
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            multicast_ip_range="224.0.0.100-224.0.1.100",
            sub_type='native')
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPBadRequest.code, res.status_int)

    def test_create_network_profile_overlay_native_global(self):
        """Test a global native VxLAN network profile creation."""
        ml2_config.cfg.CONF.set_override('vxlan_group',
                                         '239.1.1.1',
                                         'ml2_type_vxlan')
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            sub_type='native')
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPCreated.code, res.status_int)

    def test_create_network_profile_overlay_native_no_multicast(self):
        """
        Test a shared native VxLAN network profile creation with no
        multi-cast address.

        """
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            sub_type='native')
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPBadRequest.code, res.status_int)

    def test_create_network_profile_overlay_enhanced(self):
        """Test a enhanced VxLAN network profile creation."""
        data = self.get_test_network_profile_dict(segment_type='vxlan',
                                                  sub_type='enhanced')
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPCreated.code, res.status_int)

    def test_create_network_profile_with_default_network_profile_names(self):
        # test for default VLAN network profile
        data = self.get_test_network_profile_dict(
            segment_type='vlan',
            name=n1kv_const.DEFAULT_VLAN_NETWORK_PROFILE_NAME)
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPBadRequest.code, res.status_int)
        # test for default VxLAN network profile
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            name=n1kv_const.DEFAULT_VXLAN_NETWORK_PROFILE_NAME,
            sub_type='enhanced')
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPBadRequest.code, res.status_int)

    def test_create_network_profile_invalid_segment_type(self):
        """Test a network profile create with invalid segment type."""
        data = self.get_test_network_profile_dict(
            segment_type='unknown_segment_type')
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPBadRequest.code, res.status_int)

    def test_create_network_profile_overlay_missing_subtype(self):
        """Test a VxLAN network profile creation with missing sub-type."""
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            multicast_ip_range="224.1.1.1-224.1.1.10",
            sub_type='native')
        data['network_profile'].pop('sub_type')
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPBadRequest.code, res.status_int)

    def test_create_network_profile_overlay_unknown_subtype(self):
        """Test a VxLAN network profile creation with unknown sub-type."""
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            multicast_ip_range="224.1.1.1-224.1.1.10",
            sub_type='native')
        data['network_profile']['sub_type'] = 'unknown-sub-type'
        network_req = self.new_create_request('network_profiles', data)
        res = network_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPBadRequest.code, res.status_int)

    def test_network_profile_create_on_vsm_error(self):
        """Test a network profile creation when the operation fails on VSM."""
        data = self.get_test_network_profile_dict(segment_type='vxlan',
                                                  sub_type='enhanced')
        new_net_prof_name = data["network_profile"]["name"]
        mocked_ex = mock.MagicMock(side_effect=n1kv_exc.VSMError(
            reason='Internal VSM error'))
        with mock.patch(n1kv_client.__name__ +
                        ".Client.create_network_segment_pool", mocked_ex):
            network_req = self.new_create_request('network_profiles', data)
            res = network_req.get_response(self.ext_api)
            self.assertEqual(webob.exc.HTTPInternalServerError.code,
                             res.status_int)
        # list all network profiles
        list_req = self.new_list_request('network_profiles')
        list_res = list_req.get_response(self.ext_api)
        netprofs = self.deserialize(self.fmt, list_res)
        # assert that the network profile created is cleaned up on neutron
        # when creation on VSM fails
        self.assertNotIn(
            needle=new_net_prof_name,
            haystack=[d["name"] for d in netprofs["network_profiles"]])

    def test_network_profile_create_on_vsm_connection_failed(self):
        """Test a network profile creation when the operation fails on VSM."""
        data = self.get_test_network_profile_dict(segment_type='vxlan',
                                                  sub_type='enhanced')
        new_net_prof_name = data["network_profile"]["name"]
        mocked_ex = mock.MagicMock(side_effect=n1kv_exc.VSMConnectionFailed(
            reason='Connection to VSM lost'))
        with mock.patch(n1kv_client.__name__ +
                        ".Client.create_network_segment_pool", mocked_ex):
            network_req = self.new_create_request('network_profiles', data)
            res = network_req.get_response(self.ext_api)
            self.assertEqual(webob.exc.HTTPServiceUnavailable.code,
                             res.status_int)
        # list all network profiles
        list_req = self.new_list_request('network_profiles')
        list_res = list_req.get_response(self.ext_api)
        netprofs = self.deserialize(self.fmt, list_res)
        # assert that the network profile created is cleaned up on neutron
        # when creation on VSM fails
        self.assertNotIn(
            needle=new_net_prof_name,
            haystack=[d["name"] for d in netprofs["network_profiles"]])

    def test_delete_network_profile_by_id(self):
        """Test a network profile delete by its ID."""
        data = self.get_test_network_profile_dict(segment_type='vlan')
        net_prof = self.network_profile(data)
        req = self.new_delete_request('network_profiles', net_prof[
            'network_profile']['id'])
        res = req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPNoContent.code, res.status_int)

    def test_delete_default_network_profile(self):
        """Test the deletion of default network profiles."""
        list_req = self.new_list_request('network_profiles')
        list_res = list_req.get_response(self.ext_api)
        default_netprofs = self.deserialize(self.fmt, list_res)
        for default_netprof in default_netprofs["network_profiles"]:
            default_netprof_id = default_netprof["id"]
            del_req = self.new_delete_request(
                'network_profiles',
                default_netprof_id)
            del_res = del_req.get_response(self.ext_api)
            self.assertEqual(webob.exc.HTTPInternalServerError.code,
                             del_res.status_int)

    def test_delete_network_profile_with_network(self):
        """Test a network profile delete when its network is around."""
        data = self.get_test_network_profile_dict(segment_type='vlan')
        net_prof = self.network_profile(data)
        net_prof_id = net_prof['network_profile']['id']
        net_res = self._create_network(
            self.fmt,
            name='vlan-net',
            admin_state_up=True,
            arg_list=('n1kv:profile',),
            **{n1kv_const.N1KV_PROFILE: net_prof_id})
        self.assertEqual(webob.exc.HTTPCreated.code, net_res.status_int)
        net_prof_req = self.new_delete_request('network_profiles', net_prof[
            'network_profile']['id'])
        net_prof_res = net_prof_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPConflict.code, net_prof_res.status_int)


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

    def test_create_network_with_default_n1kv_vlan_network_profile_id(self):
        """Test VLAN network create without passing network profile id."""
        with self.network() as network:
            np = n1kv_db.get_network_profile_by_name(
                n1kv_const.DEFAULT_VLAN_NETWORK_PROFILE_NAME)
            self.assertEqual(n1kv_const.DEFAULT_VLAN_NETWORK_PROFILE_NAME,
                             np["name"])
            net_np = n1kv_db.get_network_binding(network['network']['id'])
            self.assertEqual(network['network']['id'], net_np['network_id'])
            self.assertEqual(net_np['profile_id'], np['id'])

    def test_create_network_with_default_n1kv_vxlan_network_profile_id(self):
        """Test VxLAN network create without passing network profile id."""
        ml2_config.cfg.CONF.set_override('tenant_network_types',
                                         ['vxlan', 'vlan'], 'ml2')
        with self.network() as network:
            np = n1kv_db.get_network_profile_by_name(
                n1kv_const.DEFAULT_VXLAN_NETWORK_PROFILE_NAME)
            self.assertEqual(n1kv_const.DEFAULT_VXLAN_NETWORK_PROFILE_NAME,
                             np["name"])
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

    def test_create_network_with_admin_defined_vlan_network_profile_name(self):
        """Test network create with admin created VLAN network profile name."""
        data = self.get_test_network_profile_dict(segment_type='vlan')
        net_prof = self.network_profile(data)
        net_prof_name = net_prof['network_profile']['name']
        net_prof_id = net_prof['network_profile']['id']
        res = self._create_network(self.fmt, name='vlan-net',
                                   admin_state_up=True,
                                   arg_list=('n1kv:profile',),
                                   **{n1kv_const.N1KV_PROFILE: net_prof_name})
        self.assertEqual(webob.exc.HTTPCreated.code, res.status_int)
        network = self.deserialize(self.fmt, res)
        net_np = n1kv_db.get_network_binding(network['network']['id'])
        self.assertEqual(net_prof_id, network['network'][
            n1kv_const.N1KV_PROFILE])
        self.assertEqual(net_np['network_id'], network['network']['id'])
        self.assertEqual(net_np['profile_id'], net_prof_id)

    def test_create_network_with_admin_defined_overlay_network_profile_name(
            self):
        """
        Test network create with admin defined VxLAN network profile
        name.

        """
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            sub_type='enhanced',
            multicast_ip_range="224.1.1.1-224.1.1.10")
        net_prof = self.network_profile(data)
        net_prof_name = net_prof['network_profile']['name']
        net_prof_id = net_prof['network_profile']['id']
        res = self._create_network(self.fmt, name='vxlan-net',
                                   admin_state_up=True,
                                   arg_list=('n1kv:profile',),
                                   **{n1kv_const.N1KV_PROFILE: net_prof_name})
        self.assertEqual(webob.exc.HTTPCreated.code, res.status_int)
        network = self.deserialize(self.fmt, res)
        net_np = n1kv_db.get_network_binding(network['network']['id'])
        self.assertEqual(net_prof_id, network['network'][
            n1kv_const.N1KV_PROFILE])
        self.assertEqual(net_np['network_id'], network['network']['id'])
        self.assertEqual(net_np['profile_id'], net_prof_id)

    def test_create_network_with_admin_defined_vlan_network_profile_id(self):
        """Test network create with admin defined VLAN network profile ID."""
        data = self.get_test_network_profile_dict(segment_type='vlan')
        net_prof = self.network_profile(data)
        net_prof_id = net_prof['network_profile']['id']
        res = self._create_network(self.fmt, name='vlan-net',
                                   admin_state_up=True,
                                   arg_list=('n1kv:profile',),
                                   **{n1kv_const.N1KV_PROFILE: net_prof_id})
        self.assertEqual(webob.exc.HTTPCreated.code, res.status_int)
        network = self.deserialize(self.fmt, res)
        net_np = n1kv_db.get_network_binding(network['network']['id'])
        self.assertEqual(net_prof_id, network['network'][
            n1kv_const.N1KV_PROFILE])
        self.assertEqual(net_np['network_id'], network['network']['id'])
        self.assertEqual(net_np['profile_id'], net_prof_id)

    def test_delete_vlan_network_with_admin_defined_n1kv_network_profile(self):
        """
        Test network delete for a network created using admin defined
        VLAN network profile name.

        """
        data = self.get_test_network_profile_dict(segment_type='vlan')
        net_prof = self.network_profile(data)
        net_prof_name = net_prof['network_profile']['name']
        res = self._create_network(self.fmt, name='vlan-net',
                                   admin_state_up=True,
                                   arg_list=('n1kv:profile',),
                                   **{n1kv_const.N1KV_PROFILE: net_prof_name})
        network = self.deserialize(self.fmt, res)
        req = self.new_delete_request('networks', network['network']['id'])
        req.get_response(self.api)
        self.assertRaises(n1kv_exc.NetworkBindingNotFound,
                          n1kv_db.get_network_binding,
                          network['network']['id'])

    def test_delete_vxlan_network_with_admin_defined_n1kv_network_profile(
            self):
        """
        Test network delete for a network created using admin defined
        VxLAN network profile name.

        """
        data = self.get_test_network_profile_dict(segment_type='vxlan',
                                                  sub_type='enhanced')
        net_prof = self.network_profile(data)
        net_prof_name = net_prof['network_profile']['name']
        res = self._create_network(self.fmt, name='vxlan-net',
                                   admin_state_up=True,
                                   arg_list=('n1kv:profile',),
                                   **{n1kv_const.N1KV_PROFILE: net_prof_name})
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


class TestN1KVCLientVSMRetry(TestN1KVMechanismDriver):

    def setUp(self):
        self.vsm_retry = True
        super(TestN1KVCLientVSMRetry, self).setUp()

    def test_vsm_retry(self):
        """Test retry count for VSM REST API."""
        max_retries = 3
        ml2_config.cfg.CONF.set_override('max_vsm_retries', max_retries,
                                         'ml2_cisco_n1kv')
        with mock.patch.object(fake_client.TestClientVSMRetry,
                               '_fake_pool_spawn') as mock_method:
            # Mock the fake HTTP conn method to generate timeouts
            mock_method.side_effect = Exception("Conn timeout")
            # Create client instance
            client = n1kv_client.Client()
            # Test that the GET API for profiles is retried
            self.assertRaises(n1kv_exc.VSMConnectionFailed,
                              client.list_port_profiles)
            # Verify that number of attempts = 1 + max_retries
            self.assertEqual(1 + max_retries, mock_method.call_count)
