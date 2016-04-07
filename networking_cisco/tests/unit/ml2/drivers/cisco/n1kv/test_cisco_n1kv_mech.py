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
    n1kv_client)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_sync)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    policy_profile_service)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv.extensions import (
    network_profile as network_profile_module)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv.extensions import (
    policy_profile as policy_profile_module)
from networking_cisco.tests.unit.ml2.drivers.cisco.n1kv import (
    fake_client)

from neutron import context
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
service_plugins = {
            "CISCO_N1KV_POLICY_PROFILE_PLUGIN": POLICY_PROFILE_PLUGIN,
            "CISCO_N1KV_NETWORK_PROFILE_PLUGIN": NETWORK_PROFILE_PLUGIN}

PHYS_NET = 'some-phys-net'
VLAN_MIN = 100
VLAN_MAX = 500
VXLAN_MIN = 5000
VXLAN_MAX = 6000
# Set to this based on fake_client, change there before changing here
DEFAULT_PP = 'pp-1'
TEST_PP = 'pp-2'


# Mock for policy profile polling method- only does single call to populate
def _fake_poll_policy_profiles(self):
    self._populate_policy_profiles()


class TestN1KVMechanismDriver(
        test_db_base_plugin_v2.NeutronDbPluginV2TestCase):
    """Test Cisco Nexus1000V mechanism driver."""

    tenant_id = "some_tenant"
    admin_tenant = "admin_tenant"

    DEFAULT_RESP_BODY = ""
    DEFAULT_RESP_CODE = 200
    DEFAULT_CONTENT_TYPE = ""
    fmt = "json"
    shared = False
    upd_shared = False
    vsm_retry = False
    load_network_profile_extension = False
    load_policy_profile_extension = False

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
        (policy_profile_service.PolicyProfilePlugin.
         _poll_policy_profiles) = _fake_poll_policy_profiles
        # Setup the policy profile service plugin in order to load policy
        # profiles for testing
        if self.load_network_profile_extension:
            super(TestN1KVMechanismDriver,
                  self).setUp(plugin=ML2_PLUGIN,
                              service_plugins=service_plugins,
                              ext_mgr=network_profile_module.Network_profile())
        elif self.load_policy_profile_extension:
            super(TestN1KVMechanismDriver,
                  self).setUp(plugin=ML2_PLUGIN,
                              service_plugins=service_plugins,
                              ext_mgr=policy_profile_module.Policy_profile())
        else:
            super(TestN1KVMechanismDriver,
                  self).setUp(plugin=ML2_PLUGIN,
                              service_plugins=service_plugins)
        self.port_create_status = 'DOWN'

    def create_resource(self, resource, data, tenant_id,
                        expected_status, is_admin=False, api=None):
        api = api or self.ext_api
        create_req = self.new_create_request(resource, data, self.fmt)
        create_req.environ['neutron.context'] = context.Context(
            '',
            tenant_id,
            is_admin=is_admin)
        create_res = create_req.get_response(api)
        res_dict = None
        response_status = create_res.status_int
        self.assertEqual(expected_status, response_status)
        if response_status < webob.exc.HTTPClientError.code:
            res_dict = self.deserialize(self.fmt, create_res)
        return res_dict

    def list_resource(self, resource, tenant_id):
        list_req = self.new_list_request(resource)
        list_req.environ['neutron.context'] = context.Context('', tenant_id)
        list_res = list_req.get_response(self.ext_api)
        if list_res.status_int < webob.exc.HTTPClientError.code:
            return self.deserialize(self.fmt, list_res)

    def get_test_network_profile_dict(self, segment_type,
                                      multicast_ip_range=None,
                                      sub_type=None,
                                      name='test-net-profile',
                                      tenant_id='admin',
                                      **kwargs):
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
        for arg, val in kwargs.items():
            net_prof['network_profile'][arg] = val
        return net_prof

    def assert_profile_binding_exists(self, binding, tenant_id, profile_id):
        """
        Assert that binding for a given tenant-profile pair exists

        :param binding: type of profile binding (network/policy)
        :param tenant_id: UUID of the tenant
        :param profile_id: UUID of the network/policy profile
        """
        prof_bindings = self.list_resource(
            resource=binding,
            tenant_id=tenant_id
        )
        self.assertIn(
            needle=tenant_id,
            haystack=[d["tenant_id"] for d in prof_bindings[
                      binding] if d["profile_id"] == profile_id])

    def assert_profile_binding_absent(self, binding, tenant_id, profile_id):
        """
        Assert that binding for a given tenant-profile pair does NOT exist

        :param binding: type of profile binding (network/policy)
        :param tenant_id: UUID of the tenant
        :param profile_id: UUID of the network/policy profile
        """
        prof_bindings = self.list_resource(
            resource=binding,
            tenant_id=tenant_id
        )
        self.assertNotIn(
            needle=tenant_id,
            haystack=[d["tenant_id"] for d in prof_bindings[
                      binding] if d["profile_id"] == profile_id])

    def create_assert_network_profile_success(
            self, data, tenant_id=None, is_admin=True,
            expected_status=webob.exc.HTTPCreated.code):
        """
        Create a network profile and assert that a binding for the
        profile exists with the tenant who created it.

        """
        tenant_id = tenant_id or self.admin_tenant
        net_profile = self.create_resource(
            resource='network_profiles',
            data=data,
            tenant_id=tenant_id,
            is_admin=is_admin,
            expected_status=expected_status)
        # assert that binding is created
        self.assert_profile_binding_exists(
            binding='network_profile_bindings',
            tenant_id=tenant_id,
            profile_id=net_profile['network_profile']['id'])
        return net_profile

    def create_assert_network_profile_failure(
            self, data, tenant_id=None, is_admin=True,
            expected_status=webob.exc.HTTPBadRequest.code):
        """
        Create a network profile with erroneous arguments and assert that
        the profile creation fails.

        """
        tenant_id = tenant_id or self.admin_tenant
        net_profile = self.create_resource(
            resource='network_profiles',
            data=data,
            tenant_id=tenant_id,
            is_admin=is_admin,
            expected_status=expected_status)
        # assert that network profile was not created
        self.assertIsNone(net_profile)

    def update_assert_profile(self, profile_type, profile_id,
                              add_tenants=None, remove_tenants=None,
                              fmt=None):
        """
        Update a network/policy profile by adding new tenant associations
        and/or removing existing ones. Also, assert that only expected
        tenant-profile bindings exist after the update is complete.

        """
        add_tenants = add_tenants or []
        remove_tenants = remove_tenants or []
        fmt = fmt or self.fmt
        profile = profile_type + '_profiles'
        binding_type = profile_type + '_profile_bindings'
        data = {
            profile_type + "_profile": {
                'add_tenant': add_tenants,
                'remove_tenant': remove_tenants
            }
        }
        update_req = self.new_update_request(
            resource=profile,
            data=data,
            id=profile_id,
            fmt=fmt)
        update_res = update_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPOk.code, update_res.status_int)

        for added_tenant in add_tenants:
            self.assert_profile_binding_exists(binding_type, added_tenant,
                                               profile_id)
        for removed_tenant in remove_tenants:
            self.assert_profile_binding_absent(binding_type, removed_tenant,
                                               profile_id)


class TestN1KVMechDriverBasicGet(test_db_base_plugin_v2.TestBasicGet,
                                 TestN1KVMechanismDriver):

    pass


class TestN1KVMechDriverHTTPResponse(test_db_base_plugin_v2.TestV2HTTPResponse,
                                     TestN1KVMechanismDriver):

    pass


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
