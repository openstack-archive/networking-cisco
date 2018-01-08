#Copyright (c) 2017 Cisco Systems, Inc.
# All Rights Reserved.
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

"""
VXLAN Test Class using RESTAPI Driver to test Cisco Nexus platforms.

These Classes are based on the original ssh VXLAN event driver
so same tests occur with same configuration.  What's different
between the tests is the resulting driver output which is what
the tests in this class presents to its parent class.

You will notice in this file there are test methods which
are skipped by using 'pass'.  This is because these tests
apply to ssh only OR because rerunning the test would be
redundant.
"""


from oslo_config import cfg


from networking_cisco.ml2_drivers.nexus import (
    nexus_restapi_snippets as snipp)
from networking_cisco.tests.unit.ml2_drivers.nexus import (
    test_cisco_nexus_base as base)
from networking_cisco.tests.unit.ml2_drivers.nexus import (
    test_cisco_nexus_events_vxlan)


class TestCiscoNexusRestVxlanResults(base.TestCiscoNexusBaseResults):

    """Unit tests driver results for Cisco ML2 Nexus."""

    test_results = {

        # The following contains desired Nexus output for
        # some basic vxlan config.
        'add_port_driver_result': [
            [(snipp.PATH_VNI_UPDATE % ('1', '70000')),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VNI_UPDATE % (
                 '70000', '70000', '70000',
                 base.MCAST_GROUP)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VXLAN_ADD % (267, 70000)),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],

        'delete_port_driver_result': [
            [(snipp.PATH_VNI_UPDATE % ('1', '70000')),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_1,
             '',
             base.DELETE]
        ],


        'add_port2_driver_result': [
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_VXLAN_ADD % (267, 70000)),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],

        'delete_port2_driver_result': [
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_1,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST],
        ],

        'add_port_driver_result3': [
            [(snipp.PATH_VNI_UPDATE % ('1', '70000')),
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_VNI_UPDATE % (
                 '70000', '70000', '70000',
                 base.MCAST_GROUP)),
             base.POST],
            [(snipp.PATH_VNI_UPDATE % ('1', '70000')),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_VNI_UPDATE % (
                 '70000', '70000', '70000',
                 base.MCAST_GROUP)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_VXLAN_ADD % (267, 70000)),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_VXLAN_ADD % (267, 70000)),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/2]'),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_VXLAN_ADD % (267, 70000)),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],

        'delete_port_driver_result3': [
            [(snipp.PATH_VNI_UPDATE % ('1', '70000')),
             base.NEXUS_IP_ADDRESS_6,
             '',
             base.DELETE],
            [(snipp.PATH_VNI_UPDATE % ('1', '70000')),
             base.NEXUS_IP_ADDRESS_7,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_6,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_6,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'phys-[eth1/2]'),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_7,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'phys-[eth1/3]'),
             base.NEXUS_IP_ADDRESS_7,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST],
        ],

        'add_port_driver_result2': [
            [(snipp.PATH_VNI_UPDATE % ('1', '70001')),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_VNI_UPDATE % (
                 '70001', '70001', '70001',
                 base.MCAST_GROUP)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_VXLAN_ADD % (265, 70001)),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+265')),
             base.POST]
        ],

        'delete_port_driver_result2': [
            [(snipp.PATH_VNI_UPDATE % ('1', '70001')),
             base.NEXUS_IP_ADDRESS_8,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'phys-[eth1/20]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-265')),
             base.POST],
            [(snipp.PATH_VLAN % '265'),
             base.NEXUS_IP_ADDRESS_8,
             '',
             base.DELETE]
        ],
        'add_port_driver_result4': [
            [(snipp.PATH_VNI_UPDATE % ('1', '70000')),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_VNI_UPDATE % (
                 '70000', '70000', '70000',
                 base.MCAST_GROUP)),
             base.POST],
            [snipp.PATH_ALL,
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_VXLAN_ADD % (267, 70000)),
             base.POST],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '+267')),
             base.POST]
        ],

        'delete_port_driver_result4': [
            [(snipp.PATH_VNI_UPDATE % ('1', '70000')),
             base.NEXUS_IP_ADDRESS_8,
             '',
             base.DELETE],
            [(snipp.PATH_IF % 'phys-[eth1/10]'),
             base.NEXUS_IP_ADDRESS_8,
             (snipp.BODY_TRUNKVLAN % ('l1PhysIf', '', '-267')),
             base.POST],
            [(snipp.PATH_VLAN % '267'),
             base.NEXUS_IP_ADDRESS_8,
             '',
             base.DELETE]
        ],


    }


class TestCiscoNexusRestVxlanDevice(
    test_cisco_nexus_events_vxlan.TestCiscoNexusVxlanDevice):

    """Unit tests for Cisco ML2 VXLAN Nexus device driver."""

    def setUp(self):
        """Sets up mock ncclient, and switch and credentials dictionaries."""

        cfg.CONF.set_override('switch_heartbeat_time', 0, 'ml2_cisco')

        # Call Grandfather's setUp(); otherwise parent will set driver to
        # 'ncclient' instead of 'restapi'.
        super(test_cisco_nexus_events_vxlan.TestCiscoNexusVxlanDevice,
              self).setUp()
        self.mock_ncclient.reset_mock()
        self.addCleanup(self._clear_nve_db)
        self.results = TestCiscoNexusRestVxlanResults()

    def test_enable_vxlan_feature_failure(self):
        pass

    def test_disable_vxlan_feature_failure(self):
        pass

    def test_create_nve_member_failure(self):
        pass

    def test_delete_nve_member_failure(self):
        pass

    def test_nexus_vxlan_one_network_two_hosts(self):
        (super(TestCiscoNexusRestVxlanDevice, self).
            test_nexus_vxlan_one_network_two_hosts())

    def test_nexus_missing_vxlan_fields(self):
        pass

    def test_nexus_vxlan_bind_port(self):
        pass

    def test_nexus_vxlan_bind_port_no_physnet(self):
        pass

    def test_nexus_vxlan_bind_port_no_dynamic_segment(self):
        pass

    def test_nexus_vxlan_one_network(self):
        (super(TestCiscoNexusRestVxlanDevice, self).
            test_nexus_vxlan_one_network())

    def test_nexus_vxlan_two_network(self):
        (super(TestCiscoNexusRestVxlanDevice, self).
            test_nexus_vxlan_two_network())
