# Copyright 2014 Cisco Systems, Inc.
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

from sqlalchemy.orm import exc as s_exc

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    config as ml2_n1kv_config)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as c_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_db)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_models)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    policy_profile_service)

import neutron.db.api as db
from neutron.plugins.common import constants as p_const
from neutron.tests.unit.db import test_db_base_plugin_v2
from neutron.tests.unit import testlib_api


TEST_NETWORK_ID = 'abcdefghijklmnopqrstuvwxyz'
TEST_NETWORK_ID2 = 'abcdefghijklmnopqrstuvwxy2'
TEST_NETWORK_PROFILE = {'name': 'test_profile',
                        'segment_type': 'vlan'}
TEST_NETWORK_PROFILE_VXLAN = {'name': 'test_profile2',
                              'segment_type': 'vxlan'}
TEST_POLICY_PROFILE = {'id': '4a417990-76fb-11e2-bcfd-0800200c9a66',
                       'name': 'test_policy_profile',
                       'vsm_ip': '127.0.0.1'}
TEST_PPROFILES = [TEST_POLICY_PROFILE]
TEST_VSM_HOSTS = ['127.0.0.1']
TEST_MULTI_VSM_HOSTS = ['127.0.0.1', '127.0.0.2']
pprofile_mixin = policy_profile_service.PolicyProfile_db_mixin()


def _create_test_vxlan_network_profile_if_not_there(session,
                                           profile=TEST_NETWORK_PROFILE_VXLAN):
    try:
        _profile = session.query(n1kv_models.NetworkProfile).filter_by(
            name=profile['name']).one()
    except s_exc.NoResultFound:
        _profile = n1kv_db.add_network_profile(profile['name'],
                                          profile['segment_type'])
    return _profile


def _create_test_network_profile_if_not_there(session,
                                              profile=TEST_NETWORK_PROFILE):
    try:
        _profile = session.query(n1kv_models.NetworkProfile).filter_by(
            name=profile['name']).one()
    except s_exc.NoResultFound:
        _profile = n1kv_db.add_network_profile(profile['name'],
                                          profile['segment_type'])
    return _profile


def _create_test_policy_profile_if_not_there(session,
                                             profile=TEST_POLICY_PROFILE):
    try:
        _profile = session.query(n1kv_models.PolicyProfile).filter_by(
            name=profile['name']).one()
    except s_exc.NoResultFound:
        _profile = pprofile_mixin._create_policy_profile(
            profile['id'],
            profile['name'],
            profile['vsm_ip'])
    return _profile


class NetworkProfileTests(testlib_api.SqlTestCase):

    def setUp(self):
        super(NetworkProfileTests, self).setUp()
        self.session = db.get_session()

    def test_create_network_profile(self):
        _db_profile = n1kv_db.add_network_profile(TEST_NETWORK_PROFILE['name'],
                                             p_const.TYPE_VLAN)
        self.assertIsNotNone(_db_profile)
        db_profile = (self.session.query(n1kv_models.NetworkProfile).
                      filter_by(name=TEST_NETWORK_PROFILE['name']).one())
        self.assertIsNotNone(db_profile)
        self.assertEqual(_db_profile.id, db_profile.id)
        self.assertEqual(_db_profile.name, db_profile.name)
        self.assertEqual(_db_profile.segment_type, db_profile.segment_type)

    def test_get_network_profiles_by_type(self):
        test_profiles = [{'name': 'test_profile1',
                          'segment_type': p_const.TYPE_VLAN},
                         {'name': 'test_profile2',
                          'segment_type': p_const.TYPE_VXLAN}]
        for p in test_profiles:
            n1kv_db.add_network_profile(p['name'], p['segment_type'])
        profile = n1kv_db.get_network_profile_by_type(p_const.TYPE_VLAN)
        self.assertEqual(test_profiles[0]['name'], profile['name'])
        self.assertEqual(test_profiles[0]['segment_type'],
                         profile['segment_type'])

    def test_remove_network_profile(self):
        _db_profile = n1kv_db.add_network_profile(TEST_NETWORK_PROFILE['name'],
                                             p_const.TYPE_VLAN)
        db_profile = n1kv_db.get_network_profile_by_type(
                                            p_const.TYPE_VLAN)
        self.assertIsNotNone(db_profile)
        self.assertEqual(_db_profile.id, db_profile.id)
        n1kv_db.remove_network_profile(_db_profile.id)
        self.assertRaises(c_exc.NetworkProfileNotFound,
                          n1kv_db.get_network_profile_by_type,
                          p_const.TYPE_VLAN)


class PolicyProfileTests(testlib_api.SqlTestCase):

    def setUp(self):
        super(PolicyProfileTests, self).setUp()
        self.session = db.get_session()

    def test_create_policy_profile(self):
        _db_profile = pprofile_mixin._create_policy_profile(
            TEST_POLICY_PROFILE['id'],
            TEST_POLICY_PROFILE['name'],
            TEST_POLICY_PROFILE['vsm_ip'])
        self.assertIsNotNone(_db_profile)
        db_profile = (self.session.query(n1kv_models.PolicyProfile).
                      filter_by(name=TEST_POLICY_PROFILE['name']).one)()
        self.assertIsNotNone(db_profile)
        self.assertEqual(_db_profile.id, db_profile.id)
        self.assertEqual(_db_profile.name, db_profile.name)

    def test_delete_policy_profile(self):
        profile = _create_test_policy_profile_if_not_there(self.session)
        pprofile_mixin._remove_policy_profile(profile.id, profile.vsm_ip)
        try:
            self.session.query(n1kv_models.PolicyProfile).filter_by(
                name=TEST_POLICY_PROFILE['name']).one()
        except s_exc.NoResultFound:
            pass
        else:
            self.fail("Policy Profile (%s) was not deleted" %
                      TEST_POLICY_PROFILE['name'])

    def test_get_policy_profile_by_name(self):
        ml2_n1kv_config.cfg.CONF.set_override('n1kv_vsm_ips', TEST_VSM_HOSTS,
                                            'ml2_cisco_n1kv')
        profile = _create_test_policy_profile_if_not_there(self.session)
        got_profile = n1kv_db.get_policy_profile_by_name(
                                            TEST_POLICY_PROFILE['name'])
        self.assertEqual(profile.id, got_profile.id)
        self.assertEqual(profile.name, got_profile.name)

    def test_get_policy_profile_by_uuid(self):
        ml2_n1kv_config.cfg.CONF.set_override('n1kv_vsm_ips', TEST_VSM_HOSTS,
                                            'ml2_cisco_n1kv')
        profile = _create_test_policy_profile_if_not_there(self.session)
        got_profile = n1kv_db.get_policy_profile_by_uuid(self.session,
                                            TEST_POLICY_PROFILE['id'])
        self.assertEqual(profile.id, got_profile.id)
        self.assertEqual(profile.name, got_profile.name)
        ml2_n1kv_config.cfg.CONF.set_override('n1kv_vsm_ips',
                                TEST_MULTI_VSM_HOSTS, 'ml2_cisco_n1kv')
        self.assertRaises(c_exc.PolicyProfileNotFound,
                          n1kv_db.get_policy_profile_by_uuid,
                          self.session, TEST_POLICY_PROFILE['id'])

    def test_check_policy_profile_exists_on_all_vsm(self):
        _create_test_policy_profile_if_not_there(self.session)
        self.assertTrue(n1kv_db.check_policy_profile_exists_on_all_vsm(
                                            TEST_PPROFILES, TEST_VSM_HOSTS))


class NetworkBindingsTest(test_db_base_plugin_v2.NeutronDbPluginV2TestCase):

    def setUp(self):
        super(NetworkBindingsTest, self).setUp()
        self.session = db.get_session()

    def test_add_and_get_network_binding(self):
        with self.network() as network:
            TEST_NETWORK_ID = network['network']['id']
            self.assertRaises(c_exc.NetworkBindingNotFound,
                              n1kv_db.get_network_binding,
                              TEST_NETWORK_ID)

            p = _create_test_network_profile_if_not_there(self.session)
            n1kv_db.add_network_binding(TEST_NETWORK_ID,
                                        p_const.TYPE_VLAN,
                                        1234, p.id)
            binding = n1kv_db.get_network_binding(TEST_NETWORK_ID)
            self.assertIsNotNone(binding)
            self.assertEqual(TEST_NETWORK_ID, binding.network_id)
            self.assertEqual(p_const.TYPE_VLAN, binding.network_type)
            self.assertEqual(1234, binding.segmentation_id)

    def test_add_and_get_multiple_network_bindings(self):
        with self.network() as network1:
            with self.network() as network2:
                TEST_NETWORK_ID1 = network1['network']['id']
                TEST_NETWORK_ID2 = network2['network']['id']
                self.assertRaises(c_exc.NetworkBindingNotFound,
                                  n1kv_db.get_network_binding,
                                  TEST_NETWORK_ID1)
                self.assertRaises(c_exc.NetworkBindingNotFound,
                                  n1kv_db.get_network_binding,
                                  TEST_NETWORK_ID2)
                p = _create_test_network_profile_if_not_there(self.session)
                n1kv_db.add_network_binding(
                    TEST_NETWORK_ID1, p_const.TYPE_VLAN,
                    1234, p.id)
                binding = n1kv_db.get_network_binding(TEST_NETWORK_ID1)
                self.assertIsNotNone(binding)
                self.assertEqual(TEST_NETWORK_ID1, binding.network_id)
                self.assertEqual(p_const.TYPE_VLAN,
                                 binding.network_type)
                n1kv_db.add_network_binding(
                    TEST_NETWORK_ID2, p_const.TYPE_VLAN,
                    1235, p.id)
                binding = n1kv_db.get_network_binding(TEST_NETWORK_ID2)
                self.assertIsNotNone(binding)
                self.assertEqual(TEST_NETWORK_ID2, binding.network_id)
                self.assertEqual(p_const.TYPE_VLAN,
                                 binding.network_type)
                self.assertEqual(1235, binding.segmentation_id)

    def test_add_and_get_network_binding_vxlan(self):
        with self.network() as network:
            TEST_NETWORK_ID = network['network']['id']
            self.assertRaises(c_exc.NetworkBindingNotFound,
                              n1kv_db.get_network_binding,
                              TEST_NETWORK_ID)

            p = _create_test_vxlan_network_profile_if_not_there(self.session)
            n1kv_db.add_network_binding(
                TEST_NETWORK_ID, p_const.TYPE_VXLAN,
                1234, p.id)
            binding = n1kv_db.get_network_binding(TEST_NETWORK_ID)
            self.assertIsNotNone(binding)
            self.assertEqual(TEST_NETWORK_ID, binding.network_id)
            self.assertEqual(p_const.TYPE_VXLAN, binding.network_type)
            self.assertEqual(1234, binding.segmentation_id)

    def test_add_and_get_multiple_network_bindings_vxlan(self):
        with self.network() as network1:
            with self.network() as network2:
                TEST_NETWORK_ID1 = network1['network']['id']
                TEST_NETWORK_ID2 = network2['network']['id']
                self.assertRaises(c_exc.NetworkBindingNotFound,
                                  n1kv_db.get_network_binding,
                                  TEST_NETWORK_ID1)
                self.assertRaises(c_exc.NetworkBindingNotFound,
                                  n1kv_db.get_network_binding,
                                  TEST_NETWORK_ID2)
                p = _create_test_vxlan_network_profile_if_not_there(
                    self.session)
                n1kv_db.add_network_binding(
                    TEST_NETWORK_ID1, p_const.TYPE_VXLAN,
                    1234, p.id)
                binding = n1kv_db.get_network_binding(TEST_NETWORK_ID1)
                self.assertIsNotNone(binding)
                self.assertEqual(TEST_NETWORK_ID1, binding.network_id)
                self.assertEqual(p_const.TYPE_VXLAN,
                                 binding.network_type)
                n1kv_db.add_network_binding(
                    TEST_NETWORK_ID2, p_const.TYPE_VXLAN,
                    1235, p.id)
                binding = n1kv_db.get_network_binding(TEST_NETWORK_ID2)
                self.assertIsNotNone(binding)
                self.assertEqual(TEST_NETWORK_ID2, binding.network_id)
                self.assertEqual(p_const.TYPE_VXLAN,
                                 binding.network_type)
                self.assertEqual(1235, binding.segmentation_id)

    def test_add_and_get_multiple_network_bindings_mix(self):
        with self.network() as network1:
            with self.network() as network2:
                TEST_NETWORK_ID1 = network1['network']['id']
                TEST_NETWORK_ID2 = network2['network']['id']
                self.assertRaises(c_exc.NetworkBindingNotFound,
                                  n1kv_db.get_network_binding,
                                  TEST_NETWORK_ID1)
                self.assertRaises(c_exc.NetworkBindingNotFound,
                                  n1kv_db.get_network_binding,
                                  TEST_NETWORK_ID2)
                p = _create_test_network_profile_if_not_there(self.session)
                p2 = _create_test_vxlan_network_profile_if_not_there(
                    self.session)
                n1kv_db.add_network_binding(
                    TEST_NETWORK_ID1, p_const.TYPE_VXLAN,
                    1234, p2.id)
                binding = n1kv_db.get_network_binding(TEST_NETWORK_ID1)
                self.assertIsNotNone(binding)
                self.assertEqual(binding.network_id, TEST_NETWORK_ID1)
                self.assertEqual(binding.network_type,
                                 p_const.TYPE_VXLAN)
                n1kv_db.add_network_binding(
                    TEST_NETWORK_ID2, p_const.TYPE_VLAN,
                    1235, p.id)
                binding = n1kv_db.get_network_binding(TEST_NETWORK_ID2)
                self.assertIsNotNone(binding)
                self.assertEqual(TEST_NETWORK_ID2, binding.network_id)
                self.assertEqual(p_const.TYPE_VLAN,
                                 binding.network_type)
                self.assertEqual(1235, binding.segmentation_id)


class ProfileBindingsTest(test_db_base_plugin_v2.NeutronDbPluginV2TestCase):

    def setUp(self):
        super(ProfileBindingsTest, self).setUp()
        self.session = db.get_session()

    def test_add_and_get_profile_binding(self):
        with self.port() as port:
            TEST_PORT_ID = port['port']['id']
            self.assertRaises(c_exc.PortBindingNotFound,
                              n1kv_db.get_policy_binding,
                              TEST_PORT_ID)

            p = _create_test_policy_profile_if_not_there(self.session)
            n1kv_db.add_policy_binding(TEST_PORT_ID, p.id)
            binding = n1kv_db.get_policy_binding(TEST_PORT_ID)
            self.assertIsNotNone(binding)
            self.assertEqual(TEST_PORT_ID, binding.port_id)
            self.assertEqual(p.id, binding.profile_id)

    def test_add_and_get_multiple_profile_bindings(self):
        with self.subnet() as subnet:
            with self.port(subnet=subnet) as port1:
                with self.port(subnet=subnet) as port2:
                    TEST_PORT_ID1 = port1['port']['id']
                    TEST_PORT_ID2 = port2['port']['id']
                    self.assertRaises(c_exc.PortBindingNotFound,
                                      n1kv_db.get_policy_binding,
                                      TEST_PORT_ID1)
                    self.assertRaises(c_exc.PortBindingNotFound,
                                      n1kv_db.get_policy_binding,
                                      TEST_PORT_ID2)

                    p = _create_test_policy_profile_if_not_there(self.session)
                    n1kv_db.add_policy_binding(TEST_PORT_ID1, p.id)
                    binding = n1kv_db.get_policy_binding(TEST_PORT_ID1)
                    self.assertIsNotNone(binding)
                    self.assertEqual(TEST_PORT_ID1, binding.port_id)
                    self.assertEqual(p.id, binding.profile_id)
                    n1kv_db.add_policy_binding(TEST_PORT_ID2, p.id)
                    binding = n1kv_db.get_policy_binding(TEST_PORT_ID2)
                    self.assertIsNotNone(binding)
                    self.assertEqual(TEST_PORT_ID2, binding.port_id)
                    self.assertEqual(p.id, binding.profile_id)
