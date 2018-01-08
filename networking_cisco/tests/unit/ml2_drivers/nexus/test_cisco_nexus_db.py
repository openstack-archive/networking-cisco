# Copyright (c) 2013-2016 Cisco Systems, Inc.
# All Rights Reserved.
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

import collections
import mock
import testtools

from networking_cisco.ml2_drivers.nexus import exceptions
from networking_cisco.ml2_drivers.nexus import nexus_db_v2
from oslo_db import exception as db_exc

from neutron.tests.unit import testlib_api


class TestCiscoNexusDb(testlib_api.SqlTestCase):

    """Unit tests for Cisco mechanism driver's Nexus port binding database."""

    NpbObj = collections.namedtuple('NpbObj', 'port vlan vni switch instance '
                 'channel_group is_native_vlan')

    def _npb_test_obj(self, pnum, vnum, vni=0, switch='10.9.8.7',
                      instance=None, channel_group=0, is_native_vlan=False):
        """Creates a Nexus port binding test object from a pair of numbers."""
        if pnum is 'router':
            port = pnum
        else:
            port = '1/%s' % pnum
        if instance is None:
            instance = 'instance_%s_%s' % (pnum, vnum)
        return self.NpbObj(port, vnum, vni, switch, instance,
                           channel_group, is_native_vlan=False)

    def _assert_bindings_match(self, npb, npb_obj):
        """Asserts that a port binding matches a port binding test obj."""
        self.assertEqual(npb.port_id, npb_obj.port)
        self.assertEqual(npb.vlan_id, npb_obj.vlan)
        self.assertEqual(npb.switch_ip, npb_obj.switch)
        self.assertEqual(npb.instance_id, npb_obj.instance)

    def _add_binding_to_db(self, npb):
        """Adds a port binding to the Nexus database."""
        return nexus_db_v2.add_nexusport_binding(
            npb.port, npb.vlan, npb.vni, npb.switch, npb.instance,
            npb.channel_group, npb.is_native_vlan)

    def _add_bindings_to_db(self, npbs):
        """Adds a list of port bindings to the Nexus database."""
        for npb in npbs:
            nexus_db_v2.add_nexusport_binding(
                npb.port, npb.vlan, npb.vni, npb.switch, npb.instance,
                npb.channel_group, npb.is_native_vlan)

    def _remove_binding_from_db(self, npb):
        """Removes a port binding from the Nexus database."""
        return nexus_db_v2.remove_nexusport_binding(
            npb.port, npb.vlan, npb.vni, npb.switch, npb.instance)

    def _get_nexusport_binding(self, npb):
        """Gets a port binding based on port, vlan, switch, and instance."""
        return nexus_db_v2.get_nexusport_binding(
            npb.port, npb.vlan, npb.switch, npb.instance)

    def _get_nexusvlan_binding(self, npb):
        """Gets port bindings based on vlan and switch."""
        return nexus_db_v2.get_nexusvlan_binding(npb.vlan, npb.switch)

    def _get_nexusvm_binding(self, npb):
        """Gets port binding based on vlan and instance."""
        return nexus_db_v2.get_nexusvm_bindings(npb.vlan, npb.instance)[0]

    def _get_port_vlan_switch_binding(self, npb):
        """Gets port bindings based on port, vlan, and switch."""
        return nexus_db_v2.get_port_vlan_switch_binding(
            npb.port, npb.vlan, npb.switch)

    def _get_port_switch_bindings(self, npb):
        """Get port bindings based on port and switch."""
        return nexus_db_v2.get_port_switch_bindings(npb.port, npb.switch)

    def test_nexusportbinding_add_remove(self):
        """Tests add and removal of port bindings from the Nexus database."""
        npb11 = self._npb_test_obj(10, 100)
        npb = self._add_binding_to_db(npb11)
        self._assert_bindings_match(npb, npb11)
        npb = self._remove_binding_from_db(npb11)
        self.assertEqual(len(npb), 1)
        self._assert_bindings_match(npb[0], npb11)
        with testtools.ExpectedException(exceptions.NexusPortBindingNotFound):
            self._remove_binding_from_db(npb11)

    def test_nexusportbinding_get(self):
        """Tests get of specific port bindings from the database."""
        npb11 = self._npb_test_obj(10, 100)
        npb21 = self._npb_test_obj(20, 100)
        npb22 = self._npb_test_obj(20, 200)
        self._add_bindings_to_db([npb11, npb21, npb22])

        npb = self._get_nexusport_binding(npb11)
        self.assertEqual(len(npb), 1)
        self._assert_bindings_match(npb[0], npb11)
        npb = self._get_nexusport_binding(npb21)
        self.assertEqual(len(npb), 1)
        self._assert_bindings_match(npb[0], npb21)
        npb = self._get_nexusport_binding(npb22)
        self.assertEqual(len(npb), 1)
        self._assert_bindings_match(npb[0], npb22)

        with testtools.ExpectedException(exceptions.NexusPortBindingNotFound):
            nexus_db_v2.get_nexusport_binding(
                npb21.port, npb21.vlan, npb21.switch, "dummyInstance")

    def test_nexusvlanbinding_get(self):
        """Test get of port bindings based on vlan and switch."""
        npb11 = self._npb_test_obj(10, 100)
        npb21 = self._npb_test_obj(20, 100)
        npb22 = self._npb_test_obj(20, 200)
        self._add_bindings_to_db([npb11, npb21, npb22])

        npb_all_v100 = self._get_nexusvlan_binding(npb11)
        self.assertEqual(len(npb_all_v100), 2)
        npb_v200 = self._get_nexusvlan_binding(npb22)
        self.assertEqual(len(npb_v200), 1)
        self._assert_bindings_match(npb_v200[0], npb22)

        with testtools.ExpectedException(exceptions.NexusPortBindingNotFound):
            nexus_db_v2.get_nexusvlan_binding(npb21.vlan, "dummySwitch")

    def test_nexusvmbinding_get(self):
        """Test get of port bindings based on vlan and instance."""
        npb11 = self._npb_test_obj(10, 100)
        npb21 = self._npb_test_obj(20, 100)
        npb22 = self._npb_test_obj(20, 200)
        self._add_bindings_to_db([npb11, npb21, npb22])

        npb = self._get_nexusvm_binding(npb21)
        self._assert_bindings_match(npb, npb21)
        npb = self._get_nexusvm_binding(npb22)
        self._assert_bindings_match(npb, npb22)

        with testtools.ExpectedException(exceptions.NexusPortBindingNotFound):
            nexus_db_v2.get_nexusvm_bindings(npb21.vlan, "dummyInstance")[0]

    def test_nexusportvlanswitchbinding_get(self):
        """Tests get of port bindings based on port, vlan, and switch."""
        npb11 = self._npb_test_obj(10, 100)
        npb21 = self._npb_test_obj(20, 100)
        self._add_bindings_to_db([npb11, npb21])

        npb = self._get_port_vlan_switch_binding(npb11)
        self.assertEqual(len(npb), 1)
        self._assert_bindings_match(npb[0], npb11)

        with testtools.ExpectedException(exceptions.NexusPortBindingNotFound):
            nexus_db_v2.get_port_vlan_switch_binding(
                npb21.port, npb21.vlan, "dummySwitch")

    def test_nexusportswitchbinding_get(self):
        """Tests get of port bindings based on port and switch."""
        npb11 = self._npb_test_obj(10, 100)
        npb21 = self._npb_test_obj(20, 100, switch='2.2.2.2')
        npb22 = self._npb_test_obj(20, 200, switch='2.2.2.2')
        self._add_bindings_to_db([npb11, npb21, npb22])

        npb = self._get_port_switch_bindings(npb11)
        self.assertEqual(len(npb), 1)
        self._assert_bindings_match(npb[0], npb11)
        npb_all_p20 = self._get_port_switch_bindings(npb21)
        self.assertEqual(len(npb_all_p20), 2)

        npb = nexus_db_v2.get_port_switch_bindings(npb21.port, "dummySwitch")
        self.assertIsNone(npb)

    def test_nexusbinding_update(self):
        """Tests update of vlan IDs for port bindings."""
        npb11 = self._npb_test_obj(10, 100, switch='1.1.1.1', instance='test')
        npb21 = self._npb_test_obj(20, 100, switch='1.1.1.1', instance='test')
        self._add_bindings_to_db([npb11, npb21])

        npb_all_v100 = nexus_db_v2.get_nexusvlan_binding(100, '1.1.1.1')
        self.assertEqual(len(npb_all_v100), 2)

        npb22 = self._npb_test_obj(20, 200, switch='1.1.1.1', instance='test')
        npb = nexus_db_v2.update_nexusport_binding(npb21.port, 200)
        self._assert_bindings_match(npb, npb22)

        npb_all_v100 = nexus_db_v2.get_nexusvlan_binding(100, '1.1.1.1')
        self.assertEqual(len(npb_all_v100), 1)
        self._assert_bindings_match(npb_all_v100[0], npb11)

        npb = nexus_db_v2.update_nexusport_binding(npb21.port, 0)
        self.assertIsNone(npb)

        npb33 = self._npb_test_obj(30, 300, switch='1.1.1.1', instance='test')
        with testtools.ExpectedException(exceptions.NexusPortBindingNotFound):
            nexus_db_v2.update_nexusport_binding(npb33.port, 200)


class TestCiscoNexusVpcAllocDbTest(testlib_api.SqlTestCase):

    """Unit tests for Cisco mechanism driver's Nexus vpc alloc database."""

    def _make_vpc_list(self, from_in, to_in):

        new_list = []
        for x in range(from_in, (to_in + 1)):
            new_list.append(x)
        return new_list

    def setUp(self):
        original_intersect = nexus_db_v2._get_free_vpcids_on_switches

        def new_get_free_vpcids_on_switches(nexus_ips):
            intersect = list(original_intersect(nexus_ips))
            intersect.sort()
            return intersect

        mock.patch.object(nexus_db_v2,
                         '_get_free_vpcids_on_switches',
                         new=new_get_free_vpcids_on_switches).start()

        super(TestCiscoNexusVpcAllocDbTest, self).setUp()

    def test_vpcalloc_init(self):

        nexus_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3']

        for this_ip in nexus_ips:
            nexus_db_v2.init_vpc_entries(
                this_ip, self._make_vpc_list(1001, 1025))
            allocs = nexus_db_v2.get_free_switch_vpc_allocs(this_ip)
            self.assertEqual(len(allocs), 25)

        nexus_db_v2.update_vpc_entry(['1.1.1.1'], 1001, False, True)
        nexus_db_v2.update_vpc_entry(['2.2.2.2'], 1002, False, True)
        nexus_db_v2.update_vpc_entry(['3.3.3.3'], 1003, False, True)

        # Verify this update fails since entry already active
        self.assertRaises(
            exceptions.NexusVPCAllocNotFound,
            nexus_db_v2.update_vpc_entry,
            ['3.3.3.3'], 1003, False, True)

        new_vpcid = nexus_db_v2.alloc_vpcid(nexus_ips)
        self.assertEqual(new_vpcid, 1004)

        nexus_db_v2.free_vpcid_for_switch(1002, '2.2.2.2')
        nexus_db_v2.free_vpcid_for_switch_list(1004, nexus_ips)

        # verify vpc 1002 can now be reused
        new_vpcid = nexus_db_v2.alloc_vpcid(nexus_ips)
        self.assertEqual(new_vpcid, 1002)

    def test_vpcalloc_rollback(self):

        nexus_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3']

        for this_ip in nexus_ips:
            nexus_db_v2.init_vpc_entries(
                this_ip, self._make_vpc_list(1001, 1025))

        nexus_db_v2.update_vpc_entry(
            nexus_ips, 1001, False, True)
        allocs = nexus_db_v2.get_free_switch_vpc_allocs('1.1.1.1')
        self.assertEqual(len(allocs), 24)
        allocs = nexus_db_v2.get_free_switch_vpc_allocs('2.2.2.2')
        self.assertEqual(len(allocs), 24)
        allocs = nexus_db_v2.get_free_switch_vpc_allocs('3.3.3.3')
        self.assertEqual(len(allocs), 24)

        nexus_db_v2.update_vpc_entry(
            nexus_ips, 1001, False, False)
        allocs = nexus_db_v2.get_free_switch_vpc_allocs('1.1.1.1')
        self.assertEqual(len(allocs), 25)
        allocs = nexus_db_v2.get_free_switch_vpc_allocs('2.2.2.2')
        self.assertEqual(len(allocs), 25)
        allocs = nexus_db_v2.get_free_switch_vpc_allocs('3.3.3.3')
        self.assertEqual(len(allocs), 25)

        nexus_db_v2.update_vpc_entry(['3.3.3.3'], 1001, False, True)
        try:
            nexus_db_v2.update_vpc_entry(
                nexus_ips, 1001, False, True)
        except exceptions.NexusVPCAllocNotFound:
            allocs = nexus_db_v2.get_free_switch_vpc_allocs('1.1.1.1')
            self.assertEqual(len(allocs), 25)
            allocs = nexus_db_v2.get_free_switch_vpc_allocs('2.2.2.2')
            self.assertEqual(len(allocs), 25)
            allocs = nexus_db_v2.get_free_switch_vpc_allocs('3.3.3.3')
            self.assertEqual(len(allocs), 24)

    def test_vpcalloc_test_alloc_collision(self):

        def new_get_free_vpcids_on_switches(nexus_ips):
            results = nexus_db_v2.get_free_switch_vpc_allocs('4.4.4.4')
            return results

        nexus_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3']

        for this_ip in nexus_ips:
            nexus_db_v2.init_vpc_entries(
                this_ip, self._make_vpc_list(1001, 1025))
        # IP 4.4.4.4 is added only to return a list of vpc ids
        # in same format as sql will return.
        nexus_db_v2.init_vpc_entries(
                '4.4.4.4', self._make_vpc_list(1001, 1003))
        mock.patch.object(nexus_db_v2,
                         '_get_free_vpcids_on_switches',
                          new=new_get_free_vpcids_on_switches).start()

        # configure '3.3.3.3', vpcid 1001 so alloc_vpcid will fail
        # on 1001 after updating 1.1.1.1 and 2.2.2.2 and rollback
        # occurs.  Then moves onto successfully allocating 1002.
        nexus_db_v2.update_vpc_entry(['3.3.3.3'], 1001, False, True)
        vpc_id = nexus_db_v2.alloc_vpcid(nexus_ips)
        self.assertEqual(vpc_id, 1002)
        allocs = nexus_db_v2.get_free_switch_vpc_allocs('1.1.1.1')
        self.assertEqual(len(allocs), 24)
        allocs = nexus_db_v2.get_free_switch_vpc_allocs('2.2.2.2')
        self.assertEqual(len(allocs), 24)
        allocs = nexus_db_v2.get_free_switch_vpc_allocs('3.3.3.3')
        self.assertEqual(len(allocs), 23)

    def test_vpcalloc_min_max(self):

        # Initialize 3 switch vpc entries
        nexus_db_v2.init_vpc_entries(
            '1.1.1.1', self._make_vpc_list(1001, 2000))
        nexus_db_v2.init_vpc_entries(
            '2.2.2.2', self._make_vpc_list(2001, 3000))
        nexus_db_v2.init_vpc_entries(
            '3.3.3.3', self._make_vpc_list(3001, 4000))

        # Verify get_switch_vpc_count_min_max() returns correct
        # count, min, max values for all 3 switches.
        count, min, max = nexus_db_v2.get_switch_vpc_count_min_max(
            '1.1.1.1')
        self.assertEqual(count, 1000)
        self.assertEqual(min, 1001)
        self.assertEqual(max, 2000)

        count, min, max = nexus_db_v2.get_switch_vpc_count_min_max(
            '2.2.2.2')
        self.assertEqual(count, 1000)
        self.assertEqual(min, 2001)
        self.assertEqual(max, 3000)

        count, min, max = nexus_db_v2.get_switch_vpc_count_min_max(
            '3.3.3.3')
        self.assertEqual(count, 1000)
        self.assertEqual(min, 3001)
        self.assertEqual(max, 4000)


class TestCiscoNexusHostMappingDbTest(testlib_api.SqlTestCase):

    """Tests for Nexus Mechanism driver Host Mapping database."""

    def test_enet_host_mapping_db(self):

        nexus_db_v2.add_host_mapping(
            "host-1", "110.1.1.1", "ethernet:1/1", 0, False)
        nexus_db_v2.add_host_mapping(
            "host-1", "112.2.2.2", "ethernet:1/1", 0, False)
        nexus_db_v2.add_host_mapping(
            "host-2", "110.1.1.1", "ethernet:2/2", 0, False)
        nexus_db_v2.add_host_mapping(
            "host-3", "113.3.3.3", "ethernet:3/3", 0, True)
        nexus_db_v2.add_host_mapping(
            "host-4", "114.4.4.4", "ethernet:4/4", 0, True)

        # Do a get 110.1.1.1 and verify  only host-1 is returned
        mappings = nexus_db_v2.get_switch_if_host_mappings(
            "110.1.1.1", "ethernet:1/1")
        self.assertEqual(
            len(mappings),
            1,
            "Unexpected number of switch interface mappings")
        for map in mappings:
            self.assertEqual(
                map.host_id,
                "host-1",
                "Expecting host-1 returned from "
                "get_switch_if_host_mappings")

        # Do a get on host-1 and verify 2 entries returned
        mappings = nexus_db_v2.get_host_mappings("host-1")
        self.assertEqual(
            len(mappings),
            2,
            "Unexpected number of host mappings")
        for map in mappings:
            self.assertEqual(
                map.host_id,
                "host-1",
                "Expecting host-1 returned from "
                "get_host_mappings")
            self.assertEqual(
                map.if_id,
                "ethernet:1/1",
                "Expecting interface returned from "
                "get_host_mappings")

        # Do a get on switch 110.1.1.1 and verify 2 entries returned
        mappings = nexus_db_v2.get_switch_host_mappings("110.1.1.1")
        self.assertEqual(
            len(mappings),
            2,
            "Unexpected number of switch mappings")
        for map in mappings:
            self.assertEqual(
                map.switch_ip,
                "110.1.1.1",
                "Expecting switch_ip returned from "
                "get_switch_host_mappings")

        # Update host mapping by changing the ch_grp
        nexus_db_v2.update_host_mapping(
            "host-2",
            "ethernet:2/2",
            "110.1.1.1",
            2)
        mappings = nexus_db_v2.get_host_mappings("host-2")
        self.assertEqual(
            len(mappings),
            1,
            "Unexpected number of host mappings aft update")
        for map in mappings:
            self.assertEqual(
                map.host_id,
                "host-2",
                "Expecting host-2 returned from "
                "get_host_mappings")
            self.assertEqual(
                map.ch_grp,
                2,
                "Expecting ch_grp 2 returned from "
                "get_host_mappings for host 2")

        # remove 1 host mapping
        nexus_db_v2.remove_host_mapping(
            "ethernet:2/2", "110.1.1.1")
        # Verify it is gone
        self.assertRaises(
            exceptions.NexusHostMappingNotFound,
            nexus_db_v2.get_host_mappings,
            "host-2")

        # remove all static host mapping
        nexus_db_v2.remove_all_static_host_mappings()
        # Verify it is gone
        mappings = nexus_db_v2.get_all_host_mappings()
        self.assertEqual(
            len(mappings),
            2,
            "Unexpected number of non-static entries")
        for map in mappings:
            self.assertFalse(
                map.is_static,
                "Expecting remaining hosts from"
                "get_all_host_mappings to be dynamic")

        # remove host mappings
        nexus_db_v2.remove_host_mapping(
            "ethernet:1/1", "112.2.2.2")
        nexus_db_v2.remove_host_mapping(
            "ethernet:1/1", "110.1.1.1")
        # Verify it is gone
        self.assertRaises(
            exceptions.NexusHostMappingNotFound,
            nexus_db_v2.get_host_mappings,
            "host-1")

    def test_portchannel_host_mapping_db(self):

        nexus_db_v2.add_host_mapping(
            "host-1", "110.1.1.1", "port-channel:100", 0, True)
        nexus_db_v2.add_host_mapping(
            "host-1", "112.2.2.2", "port-channel:100", 0, True)
        nexus_db_v2.add_host_mapping(
            "host-2", "110.1.1.1", "port-channel:100", 0, True)
        nexus_db_v2.add_host_mapping(
            "host-3", "110.1.1.1", "port-channel:100", 0, False)

        # Non-static config should raise DBDuplicateEntry when
        # it already exists.
        self.assertRaises(
            db_exc.DBDuplicateEntry,
            nexus_db_v2.add_host_mapping,
            "host-3", "110.1.1.1", "port-channel:100", 0, False)

        # Static config should NOT raise DBDuplicateEntry when
        # it already exists.
        nexus_db_v2.add_host_mapping(
            "host-2", "110.1.1.1", "port-channel:100", 0, True)

        # Do a get 110.1.1.1 and verify  correct host ids returned
        mappings = nexus_db_v2.get_switch_if_host_mappings(
            "110.1.1.1", "port-channel:100")
        self.assertEqual(
            len(mappings),
            3,
            "Expected 3 switch interface mappings for 110.1.1.1")

        test_host_id = ["host-1", "host-2", "host-3"]
        for map in mappings:
            if map.host_id not in test_host_id:
                raise Exception("Unexpected host from "
                                "get_switch_if_host_mappings")

        # Do a get on host-1 and verify 2 entries returned
        mappings = nexus_db_v2.get_host_mappings("host-1")
        self.assertEqual(
            len(mappings),
            2,
            "Unexpected number of host mappings")
        for map in mappings:
            self.assertEqual(
                map.host_id,
                "host-1",
                "Expecting host-1 returned from "
                "get_host_mappings")
            self.assertEqual(
                map.if_id,
                "port-channel:100",
                "Expecting interface returned from "
                "get_host_mappings")

        # Do a get on switch 110.1.1.1 and verify 2 entries returned
        mappings = nexus_db_v2.get_switch_host_mappings("110.1.1.1")
        self.assertEqual(
            len(mappings),
            3,
            "Expected 3 switch mappings")
        for map in mappings:
            self.assertEqual(
                map.switch_ip,
                "110.1.1.1",
                "Expecting switch_ip returned from "
                "get_switch_host_mappings")

        # Update host mapping by changing the ch_grp
        nexus_db_v2.update_host_mapping(
            "host-2",
            "port-channel:100",
            "110.1.1.1",
            2)
        mappings = nexus_db_v2.get_host_mappings("host-2")
        self.assertEqual(
            len(mappings),
            1,
            "Unexpected number of host mappings aft update")
        for map in mappings:
            self.assertEqual(
                map.host_id,
                "host-2",
                "Expecting host-2 returned from "
                "get_host_mappings")
            self.assertEqual(
                map.ch_grp,
                2,
                "Expecting ch_grp 2 returned from "
                "get_host_mappings for host 2")

        # Not testing remove_host_mapping like above
        # since this is used for baremeatl only in which
        # it only removes ethernet interfaces.

        # remove all static host mapping
        nexus_db_v2.remove_all_static_host_mappings()
        # Verify it is gone
        mappings = nexus_db_v2.get_all_host_mappings()
        self.assertEqual(
            len(mappings),
            1,
            "Unexpected number of non-static entries")
        for map in mappings:
            self.assertFalse(
                map.is_static,
                "Expecting remaining hosts from"
                "get_all_host_mappings to be dynamic")

        # remove host mappings
        nexus_db_v2.remove_host_mapping(
            "port-channel:100", "112.2.2.2")
        # Verify it is gone
        self.assertRaises(
            exceptions.NexusHostMappingNotFound,
            nexus_db_v2.get_host_mappings,
            "host-1")
