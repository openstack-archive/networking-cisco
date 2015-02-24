# Copyright (c) 2014 OpenStack Foundation
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

from neutron.extensions import portbindings
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import config as ml2_config
from neutron.plugins.ml2.drivers import type_vlan as vlan_config
from neutron.plugins.ml2.drivers import type_vxlan as vxlan_config
from neutron.tests.unit.ml2 import test_type_vlan
from neutron.tests.unit.ml2 import test_type_vxlan
from neutron.tests.unit import test_db_plugin

ML2_PLUGIN = 'neutron.plugins.ml2.plugin.Ml2Plugin'
SERVICE_PLUGIN = ('networking_cisco.plugins.ml2.drivers.cisco.n1kv.'
                  'policy_profile_service.PolicyProfilePlugin')
PHYS_NET = 'some-phys-net'
VLAN_MIN = 100
VLAN_MAX = 500
VXLAN_MIN = 5000
VXLAN_MAX = 6000


class FakeResponse(object):
    """This obj is returned by mocked requests lib instead of normal response.

    Initialize it with the status code, header and buffer contents you wish to
    return.

    """
    def __init__(self, status, response_text, headers):
        self.buffer = response_text
        self.status_code = status
        self.headers = headers

    def json(self, *args, **kwargs):
        return self.buffer


# Mock for policy profile polling method- only does single call to populate
def _fake_poll_policy_profiles(self):
    self._populate_policy_profiles()


class TestN1KVMechanismDriver(test_db_plugin.NeutronDbPluginV2TestCase):
    """Test Cisco Nexus1000V mechanism driver."""

    tenant_id = "some_tenant"

    DEFAULT_RESP_BODY = ""
    DEFAULT_RESP_CODE = 200
    DEFAULT_CONTENT_TYPE = ""
    fmt = "json"

    def setUp(self):

        ml2_opts = {
            'mechanism_drivers': ['cisco_n1kv'],
            'extension_drivers': ['cisco_n1kv_ext'],
            'type_drivers': ['vlan', 'vxlan'],
            'tenant_network_types': ['vlan', 'vxlan']}
        ml2_cisco_opts = {
            'n1kv_vsm_ips': ['127.0.0.1'],
            'username': ['admin'],
            'password': ['Sfish123']
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

        if not self.DEFAULT_RESP_BODY:
            self.DEFAULT_RESP_BODY = {
                "icehouse-pp": {
                    "properties": {
                        "name": "icehouse-pp",
                        "id": "00000000-0000-0000-0000-000000000000"}},
                "default-pp": {
                    "properties": {
                        "name": "default-pp",
                        "id": "00000000-0000-0000-0000-000000000001"}},
                "dhcp_pp": {
                    "properties": {
                        "name": "dhcp_pp",
                        "id": "00000000-0000-0000-0000-000000000002"}},
            }

        # Creating a mock HTTP connection object for requests lib. The N1KV
        # client interacts with the VSM via HTTP. Since we don't have a VSM
        # running in the unit tests, we need to 'fake' it by patching the HTTP
        # library itself. We install a patch for a fake HTTP connection class.
        # Using __name__ to avoid having to enter the full module path.
        http_patcher = mock.patch(n1kv_client.requests.__name__ + ".request")
        FakeHttpConnection = http_patcher.start()
        # Now define the return values for a few functions that may be called
        # on any instance of the fake HTTP connection class.
        self.resp_headers = {"content-type": "application/json"}
        FakeHttpConnection.return_value = (FakeResponse(
                                           self.DEFAULT_RESP_CODE,
                                           self.DEFAULT_RESP_BODY,
                                           self.resp_headers))
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


class TestN1KVMechDriverBasicGet(test_db_plugin.TestBasicGet,
                                 TestN1KVMechanismDriver):

    pass


class TestN1KVMechDriverHTTPResponse(test_db_plugin.TestV2HTTPResponse,
                                     TestN1KVMechanismDriver):

    pass


class TestN1KVMechDriverNetworksV2(test_db_plugin.TestNetworksV2,
                                   TestN1KVMechanismDriver):

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


class TestN1KVMechDriverPortsV2(test_db_plugin.TestPortsV2,
                                TestN1KVMechanismDriver):

    VIF_TYPE = portbindings.VIF_TYPE_OVS
    HAS_PORT_FILTER = True

    def test_create_port_with_default_n1kv_policy_profile_id(self):
        """Test port create without passing policy profile id."""
        with self.port() as port:
            pp = n1kv_db.get_policy_profile_by_name('default-pp')
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


class TestN1KVMechDriverSubnetsV2(test_db_plugin.TestSubnetsV2,
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
