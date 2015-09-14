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

import webob.exc

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_client)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_db)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    policy_profile_service)
from networking_cisco.tests.unit.ml2.drivers.cisco.n1kv import (
    test_cisco_n1kv_mech)

from neutron.extensions import portbindings
from neutron.plugins.ml2 import config as ml2_config
from neutron.tests.unit.db import test_db_base_plugin_v2


class TestN1KVMechDriverPortsV2(test_db_base_plugin_v2.TestPortsV2,
                                test_cisco_n1kv_mech.TestN1KVMechanismDriver):

    VIF_TYPE = portbindings.VIF_TYPE_OVS
    HAS_PORT_FILTER = True

    def setUp(self):
        self.load_policy_profile_extension = True
        super(TestN1KVMechDriverPortsV2, self).setUp()
        pp = policy_profile_service.PolicyProfilePlugin()
        pp._populate_policy_profiles()

    def test_create_port_with_default_n1kv_policy_profile_id(
            self, restrict_policy_profiles=False):
        """Test port create without passing policy profile id."""
        ml2_config.cfg.CONF.set_override(
            'restrict_policy_profiles',
            restrict_policy_profiles,
            'ml2_cisco_n1kv')
        with self.port() as port:
            pp = n1kv_db.get_policy_profile_by_name(
                test_cisco_n1kv_mech.DEFAULT_PP)
            profile_binding = n1kv_db.get_policy_binding(port['port']['id'])
            self.assertEqual(profile_binding.profile_id, pp['id'])
            # assert that binding for default port-profile exists
            port_tenant = port['port']['tenant_id']
            self.assert_profile_binding_exists(
                binding='policy_profile_bindings',
                tenant_id=port_tenant,
                profile_id=pp['id']
            )

    def test_create_port_with_default_n1kv_policy_profile_id_restricted(self):
        """
        Test port creation with default policy profile, with restricted access
        to policy profiles.

        """
        self.test_create_port_with_default_n1kv_policy_profile_id(
            restrict_policy_profiles=True)

    def test_create_port_non_default_profile_restricted(self):
        """
        Test port creation with a test policy profile, and restricted
        access to policy profiles.

        """
        port_profiles = n1kv_client.Client().list_port_profiles()
        test_port_profile = port_profiles[test_cisco_n1kv_mech.TEST_PP][
            'properties']
        ml2_config.cfg.CONF.set_override(
            'restrict_policy_profiles',
            True,
            'ml2_cisco_n1kv')
        with self.network() as network:
            # test port-create with non-admin tenant
            self._create_port(
                self.fmt,
                network['network']['id'],
                expected_res_status=webob.exc.HTTPBadRequest.code,
                tenant_id=network['network']['tenant_id'],
                set_context=True,
                arg_list=('n1kv:profile',),
                **{n1kv_const.N1KV_PROFILE: test_cisco_n1kv_mech.TEST_PP})
            self.assert_profile_binding_absent(
                binding='policy_profile_bindings',
                tenant_id=network['network']['tenant_id'],
                profile_id=test_port_profile['id'])
            # test port-create with admin tenant
            port_data = {
                'port': {'network_id': network['network']['id'],
                         'tenant_id': self.admin_tenant,
                         n1kv_const.N1KV_PROFILE:
                             test_cisco_n1kv_mech.TEST_PP}}
            self.create_resource(
                resource='ports',
                data=port_data,
                tenant_id=self.admin_tenant,
                is_admin=True,
                expected_status=webob.exc.HTTPCreated.code,
                api=self.api)
            self.assert_profile_binding_exists(
                binding='policy_profile_bindings',
                tenant_id=self.admin_tenant,
                profile_id=test_port_profile['id'])

    def test_create_port_non_default_profile_unrestricted(self):
        """
        Test port creation with a test policy profile, and unrestricted
        access to policy profiles.

        """
        port_profiles = n1kv_client.Client().list_port_profiles()
        test_port_profile = port_profiles[test_cisco_n1kv_mech.TEST_PP][
            'properties']
        ml2_config.cfg.CONF.set_override(
            'restrict_policy_profiles',
            False,
            'ml2_cisco_n1kv')
        with self.network() as network:
            res = self._create_port(
                self.fmt,
                network['network']['id'],
                expected_res_status=webob.exc.HTTPCreated.code,
                tenant_id=network['network']['tenant_id'],
                set_context=True,
                arg_list=('n1kv:profile',),
                **{n1kv_const.N1KV_PROFILE: test_cisco_n1kv_mech.TEST_PP})
            port = self.deserialize(self.fmt, res)
            # assert that binding for port-profile exists
            port_tenant = port['port']['tenant_id']
            self.assert_profile_binding_exists(
                binding='policy_profile_bindings',
                tenant_id=port_tenant,
                profile_id=test_port_profile['id']
            )

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
