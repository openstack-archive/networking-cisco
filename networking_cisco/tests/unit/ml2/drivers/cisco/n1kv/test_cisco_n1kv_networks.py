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
    config as ml2_n1kv_config)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_db)
from networking_cisco.tests.unit.ml2.drivers.cisco.n1kv import (
    test_cisco_n1kv_mech)

from neutron.plugins.ml2 import config as ml2_config
from neutron.tests.unit.db import test_db_base_plugin_v2


class TestN1KVMechDriverNetworksV2(
    test_db_base_plugin_v2.TestNetworksV2,
    test_cisco_n1kv_mech.TestN1KVMechanismDriver):

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
        self.load_network_profile_extension = True
        super(TestN1KVMechDriverNetworksV2, self).setUp()

    def test_create_network_with_default_n1kv_vlan_network_profile_id(
            self, restrict_network_profiles=False):
        """Test VLAN network create without passing network profile id."""
        ml2_n1kv_config.cfg.CONF.set_override(
            'restrict_network_profiles',
            restrict_network_profiles,
            'ml2_cisco_n1kv')
        np = n1kv_db.get_network_profile_by_name(
                n1kv_const.DEFAULT_VLAN_NETWORK_PROFILE_NAME)

        # assert that DB binding for the tenant and default VLAN network
        # profile is absent
        self.assertRaises(n1kv_exc.ProfileTenantBindingNotFound,
                          n1kv_db.get_profile_binding,
                          self._tenant_id,
                          np.id)

        # test network creation with non-admin tenant
        with self.network() as network:
            self.assertEqual(n1kv_const.DEFAULT_VLAN_NETWORK_PROFILE_NAME,
                             np["name"])
            net_np = n1kv_db.get_network_binding(network['network']['id'])
            self.assertEqual(network['network']['id'], net_np['network_id'])
            self.assertEqual(np['id'], net_np['profile_id'])
            network_tenant_id = network['network']['tenant_id']
            self.assertEqual(self._tenant_id, network_tenant_id)

            # assert that API bindings have tenant association
            # with the profile
            self.assert_profile_binding_exists(
                binding='network_profile_bindings',
                tenant_id=network_tenant_id,
                profile_id=np.id
            )

    def test_create_network_with_default_n1kv_vxlan_network_profile_id(
            self, restrict_network_profiles=False):
        """Test VxLAN network create without passing network profile id."""
        ml2_config.cfg.CONF.set_override('tenant_network_types',
                                         ['vxlan', 'vlan'], 'ml2')
        ml2_n1kv_config.cfg.CONF.set_override(
            'restrict_network_profiles',
            restrict_network_profiles,
            'ml2_cisco_n1kv')
        np = n1kv_db.get_network_profile_by_name(
                n1kv_const.DEFAULT_VXLAN_NETWORK_PROFILE_NAME)

        # assert that DB binding for the tenant and default VxLAN network
        # profile is absent
        self.assertRaises(n1kv_exc.ProfileTenantBindingNotFound,
                          n1kv_db.get_profile_binding,
                          self._tenant_id,
                          np.id)

        # test network create with non-admin tenant
        with self.network() as network:
            self.assertEqual(n1kv_const.DEFAULT_VXLAN_NETWORK_PROFILE_NAME,
                             np["name"])
            net_np = n1kv_db.get_network_binding(network['network']['id'])
            self.assertEqual(network['network']['id'], net_np['network_id'])
            self.assertEqual(np['id'], net_np['profile_id'])
            network_tenant_id = network['network']['tenant_id']
            self.assertEqual(self._tenant_id, network_tenant_id)

            # assert that API bindings also have tenant association
            # with the profile
            self.assert_profile_binding_exists(
                binding='network_profile_bindings',
                tenant_id=network_tenant_id,
                profile_id=np.id
            )

    def test_create_network_with_default_n1kv_vlan_net_profile_id_restricted(
            self):
        self.test_create_network_with_default_n1kv_vlan_network_profile_id(
            restrict_network_profiles=True)

    def test_create_network_with_default_n1kv_vxlan_net_profile_id_restricted(
            self):
        self.test_create_network_with_default_n1kv_vxlan_network_profile_id(
            restrict_network_profiles=True
        )

    def test_delete_network_with_default_n1kv_network_profile_id(self):
        """Test network delete without passing network profile id."""
        res = self._create_network(self.fmt, name='net', admin_state_up=True)
        network = self.deserialize(self.fmt, res)
        req = self.new_delete_request('networks', network['network']['id'])
        req.get_response(self.api)
        self.assertRaises(n1kv_exc.NetworkBindingNotFound,
                          n1kv_db.get_network_binding,
                          network['network']['id'])

    def test_create_net_admin_defined_vlan_net_profile_name_unrestricted(self):
        """
        Test network create with admin created VLAN network profile name with
        unrestricted access to network profiles for tenants.

        """
        ml2_n1kv_config.cfg.CONF.set_override(
            'restrict_network_profiles',
            False,
            'ml2_cisco_n1kv')
        data = self.get_test_network_profile_dict(segment_type='vlan')
        net_profile = self.create_assert_network_profile_success(data)
        net_prof_name = net_profile['network_profile']['name']
        net_prof_id = net_profile['network_profile']['id']
        # test net-create with non-admin and admin tenants
        tenant_id_list = ['non-admin-tenant', self.admin_tenant]
        for tenant_id in tenant_id_list:
            # assert that binding of this net-profile with ANY tenant
            # exists in unrestricted mode
            self.assert_profile_binding_exists(
                binding='network_profile_bindings',
                tenant_id=tenant_id,
                profile_id=net_prof_id
            )
            res = self._create_network(self.fmt,
                                       name='vlan-net',
                                       admin_state_up=True,
                                       arg_list=('n1kv:profile', 'tenant_id'),
                                       set_context=True,
                                       **{n1kv_const.N1KV_PROFILE:
                                            net_prof_name,
                                          'tenant_id': tenant_id})
            self.assertEqual(webob.exc.HTTPCreated.code, res.status_int)
            network = self.deserialize(self.fmt, res)
            net_np = n1kv_db.get_network_binding(network['network']['id'])
            self.assertEqual(net_prof_id, network['network'][
                n1kv_const.N1KV_PROFILE])
            self.assertEqual(net_np['network_id'], network['network']['id'])
            self.assertEqual(net_prof_id, net_np['profile_id'])
            self.assertEqual(tenant_id, network['network']['tenant_id'])

    def test_create_net_admin_defined_vlan_net_profile_name_restricted(self):
        """
        Test network create with admin created VLAN network profile name with
        restricted access to network profiles for tenants.

        """
        ml2_n1kv_config.cfg.CONF.set_override(
            'restrict_network_profiles',
            True,
            'ml2_cisco_n1kv')
        data = self.get_test_network_profile_dict(segment_type='vlan')
        net_profile = self.create_assert_network_profile_success(data)
        net_prof_name = net_profile['network_profile']['name']
        net_prof_id = net_profile['network_profile']['id']

        # test net-create with non-admin tenant
        tenant_id = 'unauthorized_tenant'
        # assert that the API binding for the unauthorized tenant is not
        # present for this profile
        self.assert_profile_binding_absent(
            binding='network_profile_bindings',
            tenant_id=tenant_id,
            profile_id=net_prof_id
        )
        res = self._create_network(self.fmt, name='vlan-net',
                                   admin_state_up=False,
                                   arg_list=('n1kv:profile', 'tenant_id'),
                                   set_context=True,
                                   **{n1kv_const.N1KV_PROFILE: net_prof_name,
                                      'tenant_id': tenant_id})
        self.assertEqual(webob.exc.HTTPBadRequest.code, res.status_int)

        # test net-create with admin tenant
        # assert that the binding for admin tenant is present
        self.assert_profile_binding_exists(
            binding='network_profile_bindings',
            tenant_id=self.admin_tenant,
            profile_id=net_prof_id
        )
        res = self._create_network(self.fmt, name='vlan-net',
                                   admin_state_up=True,
                                   arg_list=('n1kv:profile', 'tenant_id'),
                                   set_context=True,
                                   **{n1kv_const.N1KV_PROFILE:
                                      net_prof_name,
                                      'tenant_id': self.admin_tenant})
        self.assertEqual(webob.exc.HTTPCreated.code, res.status_int)

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
        net_profile = self.create_assert_network_profile_success(data)
        net_prof_name = net_profile['network_profile']['name']
        net_prof_id = net_profile['network_profile']['id']

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
        net_profile = self.create_assert_network_profile_success(data)
        net_prof_id = net_profile['network_profile']['id']
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
        net_profile = self.create_assert_network_profile_success(data)
        net_prof_name = net_profile['network_profile']['name']
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
        net_profile = self.create_assert_network_profile_success(data)
        net_prof_name = net_profile['network_profile']['name']
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
