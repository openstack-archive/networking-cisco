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
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    mech_cisco_n1kv)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_client)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_db)
from networking_cisco.tests.unit.ml2.drivers.cisco.n1kv import (
    test_cisco_n1kv_mech)

from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import config as ml2_config


class TestN1KVMechDriverNetworkProfiles(
    test_cisco_n1kv_mech.TestN1KVMechanismDriver):

    def setUp(self):
        self.load_network_profile_extension = True
        super(TestN1KVMechDriverNetworkProfiles, self).setUp()

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
        self.create_assert_network_profile_success(data)

    def test_create_network_profile_overlay_native(self):
        """Test a native VxLAN network profile creation."""
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            multicast_ip_range="224.1.1.1-224.1.1.10",
            sub_type='native')
        self.create_assert_network_profile_success(data)

    def test_create_network_profile_overlay_native_invalid_mcast(self):
        """
        Test a native VxLAN network profile creation with invalid
        multi-cast address.

        """
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            multicast_ip_range="3.1.1.1-2.1.1.10",
            sub_type='native')
        self.create_assert_network_profile_failure(data)

    def test_create_network_profile_overlay_native_reserved_mcast(self):
        """
        Test a native VxLAN network profile creation with reserved
        multi-cast address.

        """
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            multicast_ip_range="224.0.0.100-224.0.1.100",
            sub_type='native')
        self.create_assert_network_profile_failure(data)

    def test_create_network_profile_overlay_native_global(self):
        """Test a global native VxLAN network profile creation."""
        ml2_config.cfg.CONF.set_override('vxlan_group',
                                         '239.1.1.1',
                                         'ml2_type_vxlan')
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            sub_type='native')
        self.create_assert_network_profile_success(data)

    def test_create_network_profile_overlay_native_no_multicast(self):
        """
        Test a shared native VxLAN network profile creation with no
        multi-cast address.

        """
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            sub_type='native')
        self.create_assert_network_profile_failure(data)

    def test_create_network_profile_overlay_enhanced(self):
        """Test a enhanced VxLAN network profile creation."""
        data = self.get_test_network_profile_dict(segment_type='vxlan',
                                                  sub_type='enhanced')
        self.create_assert_network_profile_success(data)

    def test_create_network_profile_vlan_non_admin_tenant(self):
        """Test a VLAN network profile creation using a non-admin tenant."""
        data = self.get_test_network_profile_dict(segment_type='vlan')
        tenant_id = 'unauthorized_tenant'
        self.create_assert_network_profile_failure(data=data,
                                                   tenant_id=tenant_id,
                                                   is_admin=False)

    def test_create_network_profile_overlay_enhanced_non_admin_tenant(self):
        """Test a VxLAN network profile creation using a non-admin tenant."""
        data = self.get_test_network_profile_dict(segment_type='vxlan',
                                                  sub_type='enhanced')
        tenant_id = 'unauthorized_tenant'
        self.create_assert_network_profile_failure(data=data,
                                                   tenant_id=tenant_id,
                                                   is_admin=False)

    def test_create_network_profile_with_default_network_profile_names(self):
        """
        Test network profile creation with the same name as a default
        network profile.

        """
        # test for default VLAN network profile
        data = self.get_test_network_profile_dict(
            segment_type='vlan',
            name=n1kv_const.DEFAULT_VLAN_NETWORK_PROFILE_NAME)
        self.create_assert_network_profile_failure(data=data)

        # test for default VxLAN network profile
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            name=n1kv_const.DEFAULT_VXLAN_NETWORK_PROFILE_NAME,
            sub_type='enhanced')
        self.create_assert_network_profile_failure(data)

    def test_create_network_profile_invalid_segment_type(self):
        """Test a network profile create with invalid segment type."""
        data = self.get_test_network_profile_dict(
            segment_type='unknown_segment_type')
        self.create_assert_network_profile_failure(data)

    def test_create_network_profile_overlay_missing_subtype(self):
        """Test a VxLAN network profile creation with missing sub-type."""
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            multicast_ip_range="224.1.1.1-224.1.1.10",
            sub_type='native')
        data['network_profile'].pop('sub_type')
        self.create_assert_network_profile_failure(data)

    def test_create_network_profile_overlay_unknown_subtype(self):
        """Test a VxLAN network profile creation with unknown sub-type."""
        data = self.get_test_network_profile_dict(
            segment_type='vxlan',
            multicast_ip_range="224.1.1.1-224.1.1.10",
            sub_type='native')
        data['network_profile']['sub_type'] = 'unknown-sub-type'
        self.create_assert_network_profile_failure(data)

    def test_create_network_profile_on_vsm_error(self):
        """Test a network profile creation when the operation fails on VSM."""
        data = self.get_test_network_profile_dict(segment_type='vxlan',
                                                  sub_type='enhanced')
        new_net_prof_name = data["network_profile"]["name"]
        mocked_ex = mock.MagicMock(side_effect=n1kv_exc.VSMError(
            reason='Internal VSM error'))
        with mock.patch(n1kv_client.__name__ +
                        ".Client.create_network_segment_pool", mocked_ex):
            self.create_assert_network_profile_failure(
                data=data,
                expected_status=webob.exc.HTTPInternalServerError.code)
        # list all network profiles
        netprofs = self.list_resource(
            resource='network_profiles',
            tenant_id=self.admin_tenant
        )
        # assert that the network profile created is cleaned up on neutron
        # when creation on VSM fails
        self.assertNotIn(
            needle=new_net_prof_name,
            haystack=[d["name"] for d in netprofs["network_profiles"]])

    def test_create_network_profile_on_vsm_connection_failed(self):
        """
        Test a network profile creation when the connection to VSM is lost.

        """
        data = self.get_test_network_profile_dict(segment_type='vxlan',
                                                  sub_type='enhanced')
        new_net_prof_name = data["network_profile"]["name"]
        mocked_ex = mock.MagicMock(side_effect=n1kv_exc.VSMConnectionFailed(
            reason='Connection to VSM lost'))
        with mock.patch(n1kv_client.__name__ +
                        ".Client.create_network_segment_pool", mocked_ex):
            self.create_assert_network_profile_failure(
                data=data,
                expected_status=webob.exc.HTTPServiceUnavailable.code)
        # list all network profiles
        netprofs = self.list_resource(
            resource='network_profiles',
            tenant_id=self.admin_tenant
        )
        # assert that the network profile created is cleaned up on neutron
        # when creation on VSM fails
        self.assertNotIn(
            needle=new_net_prof_name,
            haystack=[d["name"] for d in netprofs["network_profiles"]])

    def test_create_network_profile_with_add_tenants_parameter(self):
        """Test a network profile creation while adding more tenants to it."""
        tenant_ids = ['another-tenant-1', 'another-tenant-2']
        data = self.get_test_network_profile_dict(segment_type='vxlan',
                                                  sub_type='enhanced',
                                                  **{n1kv_const.ADD_TENANTS:
                                                  tenant_ids})
        net_profile = self.create_assert_network_profile_success(data)
        # assert that the bindings are created for all tenants
        for tenant_id in tenant_ids:
            self.assert_profile_binding_exists(
                binding='network_profile_bindings',
                tenant_id=tenant_id,
                profile_id=net_profile['network_profile']['id']
            )

    def test_delete_network_profile_by_id(self):
        """Test a network profile delete by its ID."""
        data = self.get_test_network_profile_dict(segment_type='vlan')
        net_profile = self.create_assert_network_profile_success(data)

        req = self.new_delete_request('network_profiles', net_profile[
            'network_profile']['id'])
        res = req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPNoContent.code, res.status_int)

        # assert that the binding is also gone
        self.assert_profile_binding_absent(
            binding='network_profile_bindings',
            tenant_id=self.admin_tenant,
            profile_id=net_profile['network_profile']['id']
        )

    def test_delete_network_profile_with_add_tenants_parameter(self):
        """Test deletion for a network profile owned by multiple tenants."""
        tenant_ids = ['another-tenant-1', 'another-tenant-2']
        data = self.get_test_network_profile_dict(segment_type='vxlan',
                                                  sub_type='enhanced',
                                                  **{n1kv_const.ADD_TENANTS:
                                                  tenant_ids})
        net_profile = self.create_assert_network_profile_success(data)
        net_profile_id = net_profile['network_profile']['id']
        del_req = self.new_delete_request('network_profiles', net_profile_id)
        del_res = del_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPNoContent.code, del_res.status_int)

        # assert that bindings for all tenants are gone
        for tenant_id in tenant_ids:
            self.assert_profile_binding_absent(
                binding='network_profile_bindings',
                tenant_id=tenant_id,
                profile_id=net_profile_id
            )

    def test_delete_default_network_profile(self):
        """Test the deletion of default network profiles."""
        default_netprofs = self.list_resource(
            resource='network_profiles',
            tenant_id=self.admin_tenant
        )
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
        net_profile = self.create_assert_network_profile_success(data)
        net_prof_id = net_profile['network_profile']['id']
        net_res = self._create_network(
            self.fmt,
            name='vlan-net',
            admin_state_up=True,
            arg_list=('n1kv:profile',),
            set_context=True,
            **{n1kv_const.N1KV_PROFILE: net_prof_id})
        self.assertEqual(webob.exc.HTTPCreated.code, net_res.status_int)
        net_prof_req = self.new_delete_request('network_profiles', net_profile[
            'network_profile']['id'])
        net_prof_res = net_prof_req.get_response(self.ext_api)
        self.assertEqual(webob.exc.HTTPConflict.code, net_prof_res.status_int)
