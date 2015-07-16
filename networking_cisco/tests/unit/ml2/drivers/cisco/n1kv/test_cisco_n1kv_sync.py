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

import hashlib
import mock
import six

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_client)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_sync)
from networking_cisco.tests.unit.ml2.drivers.cisco.n1kv.test_cisco_n1kv_mech import TestN1KVMechanismDriver  # noqa


class TestN1kvSyncDriver(TestN1KVMechanismDriver):
    """Test N1kv md5 based sync between neutron and VSM."""

    TEST_VSM_NETWORK_PROFILES = ['test_network_profile1', ]
    TEST_VSM_NETWORKS = ['test_network1',
                         'test_network2', ]
    TEST_VSM_SUBNETS = ['test_subnet1', ]
    TEST_VSM_PORTS = ['test_port1', 'test_port2', ]

    TEST_NEUTRON_NETWORK_PROFILES = TEST_VSM_NETWORK_PROFILES[:]
    TEST_NEUTRON_NETWORKS = TEST_VSM_NETWORKS[:]
    TEST_NEUTRON_SUBNETS = TEST_VSM_SUBNETS[:]
    TEST_NEUTRON_PORTS = TEST_VSM_PORTS[:]

    def setUp(self):
        super(TestN1kvSyncDriver, self).setUp()

        # fake n1kv_client.Client.list_md5_hashes() for getting VSM MD5
        # hashes
        list_md5_patcher = mock.patch(n1kv_client.__name__ +
                                      ".Client.list_md5_hashes")
        fake_list_md5 = list_md5_patcher.start()
        fake_list_md5.return_value = self._fake_get_vsm_md5_hashes()

        # fake SyncDriver._get_neutron_resource() for getting resources on
        # Neutron
        self.sync_driver = n1kv_sync.N1kvSyncDriver(None)
        self.sync_driver._get_neutron_resource = mock.MagicMock(
            side_effect=self._fake_get_neutron_res)

    def _fake_get_neutron_res(self, res):
        """
        Mock function replacing SyncDriver._get_neutron_resource().

        It would be called from SyncDriver._md5_hash_comparison() function.

        :param res: network_profiles, networks, subnets or ports
        :return: list of objects or dictionaries for all entries belonging
                 to res
        """
        res_list = getattr(self, 'TEST_NEUTRON_' + res.upper())
        return [{'id': x} for x in res_list]

    def _fake_get_vsm_md5_hashes(self):
        """
        Mock function replacing n1kv_client.Client.list_md5_hashes().

        It would be eventually called from SyncDriver._md5_hash_comparison()
        function.

        :return: Dictionary with all VSM md5 hashes (including consolidated
                 md5) as would have been returned by VSM REST APIs
        """
        def calc_md5(resource):
            md5 = hashlib.md5()
            res_name = 'TEST_VSM_' + resource.split('_md5')[0].upper() + 'S'
            for uuid in sorted(getattr(self, res_name)):
                md5.update(six.b(uuid))
            return md5.hexdigest()

        res_order = [n1kv_const.NETWORK_PROFILE_MD5, n1kv_const.SUBNET_MD5,
                     n1kv_const.NETWORK_MD5, n1kv_const.PORT_MD5]
        res_md5 = {res: calc_md5(res) for res in res_order}
        consolidated_md5 = hashlib.md5()
        for res in res_order:
            consolidated_md5.update(six.b(res_md5[res]))
        res_md5[n1kv_const.CONSOLIDATED_MD5] = consolidated_md5.hexdigest()
        vsm_md5_hashes = {
            'md5_hashes': {
                'properties': res_md5
            }
        }
        return vsm_md5_hashes

    def test_md5_hash_comparison_all(self):
        """Compare Neutron-VSM MD5 hashes with identical configurations."""
        self.sync_driver._md5_hash_comparison(None)
        self.assertFalse(any(self.sync_driver.sync_resource.values()))

    def test_md5_hash_comparison_networks(self):
        """
        Compare Neutron-VSM MD5 hashes for Networks.

        Test whether or not Neutron-VSM sync would be triggered for three test
        cases:
        1. when neutron-VSM have identical networks
        2. when VSM has a missing network
        3. when VSM has an extra network
        """
        # case 1.
        self.sync_driver._md5_hash_comparison(None)
        self.assertFalse(self.sync_driver.sync_resource[n1kv_const.NETWORKS])

        # case 2.
        self.TEST_NEUTRON_NETWORKS.append('test_extra_neutron_network')
        self.sync_driver._md5_hash_comparison(None)
        self.assertTrue(self.sync_driver.sync_resource[n1kv_const.NETWORKS])
        self.TEST_NEUTRON_NETWORKS.pop()

        # case 3.
        network = self.TEST_NEUTRON_NETWORKS.pop()
        self.sync_driver._md5_hash_comparison(None)
        self.assertTrue(self.sync_driver.sync_resource[n1kv_const.NETWORKS])
        self.TEST_NEUTRON_NETWORKS.append(network)

    def test_md5_hash_comparison_ports(self):
        """
        Compare Neutron-VSM MD5 hashes for Ports.

        Test whether or not Neutron-VSM sync would be triggered for three test
        cases:
        1. when neutron-VSM have identical ports
        2. when VSM has a missing port
        3. when VSM has an extra port
        """
        # case 1.
        self.sync_driver._md5_hash_comparison(None)
        self.assertFalse(self.sync_driver.sync_resource[n1kv_const.PORTS])

        # case 2.
        self.TEST_NEUTRON_PORTS.append('test_extra_neutron_port')
        self.sync_driver._md5_hash_comparison(None)
        self.assertTrue(self.sync_driver.sync_resource[n1kv_const.PORTS])
        self.TEST_NEUTRON_PORTS.pop()

        # case 3.
        port = self.TEST_NEUTRON_PORTS.pop()
        self.sync_driver._md5_hash_comparison(None)
        self.assertTrue(self.sync_driver.sync_resource[n1kv_const.PORTS])
        self.TEST_NEUTRON_PORTS.append(port)

    def test_bd_sync_triggered_on_neutron_restart(self):
        """
        Test whether bridge-domain sync flags are set to True on Neutron
        restarts, for all VSMs.
        """
        self.assertTrue(all(self.sync_driver.sync_bds.values()))
