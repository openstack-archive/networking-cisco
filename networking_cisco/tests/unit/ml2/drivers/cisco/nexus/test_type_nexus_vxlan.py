# Copyright (c) 2014-2016 Cisco Systems, Inc.
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

from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    constants as const)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import type_nexus_vxlan

import neutron.db.api as db
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import driver_api as api

from neutron.tests.unit import testlib_api

VNI_RANGES = [(100, 102), (200, 202)]
VNI_RANGE_LOW_INVALID = [str(type_nexus_vxlan.MIN_NEXUS_VNI - 1) + ':' +
                         str(p_const.MAX_VXLAN_VNI)]
VNI_RANGE_HIGH_INVALID = [str(type_nexus_vxlan.MIN_NEXUS_VNI) + ':' +
                          str(p_const.MAX_VXLAN_VNI + 1)]
MCAST_GROUP_RANGES = ['224.0.0.1:224.0.0.2', '224.0.1.1:224.0.1.2']


class NexusVxlanTypeTest(testlib_api.SqlTestCase):

    def setUp(self):
        super(NexusVxlanTypeTest, self).setUp()
        self.driver = type_nexus_vxlan.NexusVxlanTypeDriver()
        self.driver.conf_mcast_ranges = MCAST_GROUP_RANGES
        self.driver.tunnel_ranges = VNI_RANGES
        self.driver.sync_allocations()
        self.session = db.get_session()

    def vni_in_range(self, vni):
        # SegmentTypeDriver.allocate_partially_specified_segment allocates
        # a random VNI from the range
        return any(lower <= vni <= upper for (lower, upper) in VNI_RANGES)

    def test_allocate_tenant_segment(self):
        segment = self.driver.allocate_tenant_segment(self.session)
        self.assertEqual(segment[api.NETWORK_TYPE], const.TYPE_NEXUS_VXLAN)
        self.assertEqual(segment[api.PHYSICAL_NETWORK], '224.0.0.1')
        self.assertTrue(self.vni_in_range(segment[api.SEGMENTATION_ID]))

    def test_allocate_shared_mcast_group(self):
        segments = []
        for i in range(0, 6):
            segments.append(self.driver.allocate_tenant_segment(self.session))
        self.assertEqual(segments[0][api.NETWORK_TYPE],
                         const.TYPE_NEXUS_VXLAN)
        self.assertEqual(segments[0][api.PHYSICAL_NETWORK], '224.0.0.1')
        self.assertTrue(self.vni_in_range(segments[0][api.SEGMENTATION_ID]))
        self.assertEqual(segments[-1][api.NETWORK_TYPE],
                         const.TYPE_NEXUS_VXLAN)
        self.assertEqual(segments[-1][api.PHYSICAL_NETWORK], '224.0.0.1')
        self.assertTrue(self.vni_in_range(segments[-1][api.SEGMENTATION_ID]))
        self.assertNotEqual(segments[0], segments[-1])

    def test_reserve_provider_segment_full_specs(self):
        segment = {api.NETWORK_TYPE: const.TYPE_NEXUS_VXLAN,
                   api.PHYSICAL_NETWORK: '224.0.0.1',
                   api.SEGMENTATION_ID: '5000'}
        result = self.driver.reserve_provider_segment(self.session, segment)
        alloc = self.driver.get_allocation(self.session,
                                           result[api.SEGMENTATION_ID])
        mcast_group = self.driver._get_mcast_group_for_vni(self.session,
                                                           alloc.vxlan_vni)
        self.assertTrue(alloc.allocated)
        self.assertEqual(alloc.vxlan_vni, 5000)
        self.assertEqual(mcast_group, '224.0.0.1')

    def test_reserve_provider_segment_partial_specs(self):
        segment = {api.NETWORK_TYPE: const.TYPE_NEXUS_VXLAN,
                   api.PHYSICAL_NETWORK: '224.0.0.1'}

        result = self.driver.reserve_provider_segment(self.session, segment)
        alloc = self.driver.get_allocation(self.session,
                                           result[api.SEGMENTATION_ID])
        mcast_group = self.driver._get_mcast_group_for_vni(self.session,
                                                           alloc.vxlan_vni)
        self.assertTrue(alloc.allocated)
        self.assertTrue(self.vni_in_range(alloc.vxlan_vni))
        self.assertEqual(mcast_group, '224.0.0.1')

    def test_invalid_vni_ranges(self):
        for invalid_vni_range in [VNI_RANGE_LOW_INVALID,
                                  VNI_RANGE_HIGH_INVALID]:
            type_nexus_vxlan.cfg.CONF.set_override('vni_ranges',
                                                   invalid_vni_range,
                                                   'ml2_type_nexus_vxlan')
            self.assertRaises(SystemExit, self.driver._verify_vni_ranges)
