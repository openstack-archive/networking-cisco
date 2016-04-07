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


from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_client)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_db)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    policy_profile_service)
from networking_cisco.tests.unit.ml2.drivers.cisco.n1kv.test_cisco_n1kv_mech\
    import TestN1KVMechanismDriver, TEST_PP  # noqa
from networking_cisco.tests.unit.ml2.drivers.cisco.n1kv import test_n1kv_db

import neutron.db.api as db
from neutron.plugins.ml2 import config as ml2_config


TEST_STALE_POLICY_PROFILE = {'id': '5a417990-76fb-11e2-bcfd-0800200c9a66',
                       'name': 'test_stale_policy_profile',
                       'vsm_ip': '127.0.0.2'}


class TestPolicyProfilePlugin(TestN1KVMechanismDriver):
    """Test Policy Profile Plugin."""

    def setUp(self):
        self.load_policy_profile_extension = True
        super(TestPolicyProfilePlugin, self).setUp()
        self.session = db.get_session()
        pp = policy_profile_service.PolicyProfilePlugin()
        pp._populate_policy_profiles()

    def test_sanitize_policy_profile_table(self):
        profile = test_n1kv_db._create_test_policy_profile_if_not_there(
                                    self.session, TEST_STALE_POLICY_PROFILE)
        pp = policy_profile_service.PolicyProfilePlugin()
        pp.sanitize_policy_profile_table()
        self.assertRaises(n1kv_exc.PolicyProfileNotFound,
                          n1kv_db.get_policy_profile_by_uuid, self.session,
                          profile['name'])

    def test_update_policy_profile(self):
        """
        Test policy profile updation including both adding new tenants,
        and removing existing ones from a policy profile.

        """
        ml2_config.cfg.CONF.set_override(
            'restrict_policy_profiles',
            True,
            'ml2_cisco_n1kv')
        port_profiles = n1kv_client.Client().list_port_profiles()
        test_port_profile = port_profiles[TEST_PP][
            'properties']
        tenant_ids = ['tenant1', 'tenant2']
        # test pp update with new tenant additions
        self.update_assert_profile(profile_type='policy',
                                   profile_id=test_port_profile['id'],
                                   add_tenants=tenant_ids)
        # test pp update with existing tenant deletions
        self.update_assert_profile(profile_type='policy',
                                   profile_id=test_port_profile['id'],
                                   remove_tenants=tenant_ids)
