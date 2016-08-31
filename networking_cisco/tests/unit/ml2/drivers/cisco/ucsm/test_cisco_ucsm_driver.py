# Copyright 2015 Cisco Systems, Inc.
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import mock
from oslo_config import cfg

from neutron.db import api as db_api
from neutron.extensions import portbindings
from neutron.plugins.ml2 import driver_api as api
from neutron.tests.unit import testlib_api

from neutron_lib import constants as n_const

from networking_cisco.plugins.ml2.drivers.cisco.ucsm import (
    mech_cisco_ucsm as md)
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import config as conf
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import constants as const
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import exceptions
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import ucsm_db
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import ucsm_network_driver
from networking_cisco.tests.unit.ml2.drivers.cisco.ucsm import (
    test_cisco_ucsm_common as mocked)


UCSM_IP_ADDRESS_1 = '1.1.1.1'
UCSM_IP_ADDRESS_2 = '2.2.2.2'

VNIC_NORMAL = 'normal'
VNIC_DIRECT = 'direct'
VNIC_MACVTAP = 'macvtap'
VNIC_TYPES = [VNIC_NORMAL, VNIC_DIRECT, VNIC_MACVTAP]
SRIOV_VNIC_TYPES = [VNIC_DIRECT, VNIC_MACVTAP]

SUPPORTED_PCI_DEVS = ["1137:0071", "8086:10c9"]

NETWORK_ID_1 = 1001
NETWORK_NAME = 'test-network'
VLAN_ID_1 = 100
VLAN_ID_2 = 101
PORT_STATE_ACTIVE = n_const.PORT_STATUS_ACTIVE
NETWORK_TYPE = 'vlan'
NETWORK_ID = 'test-network'
PORT_NAME = 'port1'
PORT_NAME2 = 'port2'
PORT_ID = '100001'
PORT_ID2 = '100002'
HOST1 = 'Hostname1'
HOST2 = 'Hostname2'

PCI_INFO_BAD_NIC = '1111:2222'
PCI_INFO_INVALID = '1111'

UCSM_DRIVER = ('neutron.plugins.ml2.drivers.cisco.ucsm.'
               'ucsm_network_driver.CiscoUcsmDriver')

VLAN_SEGMENT = {api.ID: 'vlan_segment_id',
                api.NETWORK_TYPE: 'vlan',
                api.PHYSICAL_NETWORK: 'test_physnet',
                api.SEGMENTATION_ID: VLAN_ID_1}

VXLAN_SEGMENT = {api.ID: 'vlan_segment_id',
                 api.NETWORK_TYPE: 'vxlan',
                 api.PHYSICAL_NETWORK: 'test_physnet',
                 api.SEGMENTATION_ID: VLAN_ID_1}

VLAN_SEGMENTS_BAD = {api.ID: 'vlan_segment_id',
                     api.NETWORK_TYPE: 'vlan',
                     api.PHYSICAL_NETWORK: 'fake_physnet',
                     api.SEGMENTATION_ID: VLAN_ID_2}

VLAN_SEGMENTS_GOOD = [{api.ID: 'vlan_segment_id',
                       api.NETWORK_TYPE: 'vlan',
                       api.PHYSICAL_NETWORK: 'test_physnet',
                       api.SEGMENTATION_ID: VLAN_ID_2}]

UCSM_HOST_DICT = {HOST1: UCSM_IP_ADDRESS_1,
                  HOST2: UCSM_IP_ADDRESS_2}

vnic_template_dict = {
    ('1.1.1.1', 'test-physnet'): ('org-root', 'Test-VNIC'),
    ('2.2.2.2', 'physnet2'): ('org-root/org-Test-Sub', 'Test'),
}


class FakeNetworkContext(api.NetworkContext):

    """Network context for testing purposes only."""

    def __init__(self, segments):

        self._network_segments = segments

    @property
    def current(self):
        return {'id': NETWORK_ID_1,
                'name': NETWORK_NAME}

    @property
    def original(self):
        return None

    @property
    def network_segments(self):
        return self._network_segments


class FakePortContext(object):

    """Port context for testing purposes only."""

    def __init__(self, name, port_id, vnic_type, profile,
                 network_context):
        self._port = {
            'status': None,
            'id': port_id,
            'name': name,
            # set for _is_supported_deviceowner() to return True
            'device_owner': n_const.DEVICE_OWNER_DHCP,
            portbindings.HOST_ID: HOST1,
            portbindings.VNIC_TYPE: vnic_type,
            portbindings.PROFILE: profile
        }
        self._network = network_context
        self._segment = network_context.network_segments[0]
        self.session = db_api.get_session()

    @property
    def current(self):
        return self._port

    @property
    def original(self):
        return None

    @property
    def network(self):
        return self._network

    @property
    def segment(self):
        return self._segment

    @property
    def bottom_bound_segment(self):
        return self._segment

    def set_binding(self, segment_id, vif_type, vif_details,
                    status=None):
        self._bound_segment_id = segment_id
        self._bound_vif_type = vif_type
        self._bound_vif_details = vif_details
        self._port['status'] = status


class TestCiscoUcsmMechDriver(testlib_api.SqlTestCase,
                              mocked.ConfigMixin):

    """Unit tests for Cisco ML2 UCS Manager MD."""

    def setUp(self):
        """Sets up mock Ucs Sdk."""
        super(TestCiscoUcsmMechDriver, self).setUp()
        self.set_up_mocks()

        def new_ucsm_driver_init(mech_instance):
            mech_instance.ucsmsdk = None
            mech_instance.handles = {}
            mech_instance.supported_sriov_vnic_types = SRIOV_VNIC_TYPES
            mech_instance.supported_pci_devs = SUPPORTED_PCI_DEVS
            mech_instance.ucsm_host_dict = UCSM_HOST_DICT

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          '__init__',
                          new=new_ucsm_driver_init).start()

        self.mech_driver = md.CiscoUcsmMechanismDriver()
        self.mech_driver.initialize()
        self.vif_type = const.VIF_TYPE_802_QBH
        self.db = ucsm_db.UcsmDbModel()
        self.ucsm_driver = ucsm_network_driver.CiscoUcsmDriver()
        self.ucsm_config = conf.UcsmConfig()

    def _create_network_context(self):
        segment = {api.SEGMENTATION_ID: "",
                   api.NETWORK_TYPE: "",
                   }
        segment[api.SEGMENTATION_ID] = VLAN_ID_1
        segment[api.NETWORK_TYPE] = 'vlan'

        network_context = FakeNetworkContext([VLAN_SEGMENT])
        return network_context

    def _create_port_context_vmfex(self):
        """Creates port context with valid VM-FEX vendor info."""
        name = PORT_NAME
        port_id = PORT_ID
        vnic_type = VNIC_DIRECT
        profile = {'pci_vendor_info': const.PCI_INFO_CISCO_VIC_1240}
        network_context = FakeNetworkContext([VLAN_SEGMENT])
        port_context = FakePortContext(name, port_id, vnic_type,
                                       profile, network_context)
        return port_context

    def _create_port_context_bad(self):
        """Creates port context with badly formed vendor info."""
        name = PORT_NAME
        port_id = PORT_ID
        vnic_type = VNIC_DIRECT
        profile = {'pci_vendor_info': PCI_INFO_BAD_NIC}
        network_context = FakeNetworkContext([VLAN_SEGMENT])
        port_context = FakePortContext(name, port_id, vnic_type,
                                       profile, network_context)
        return port_context

    def _create_port_context_sriov(self):
        """Creates port context with valid SR-IOV vendor info."""
        name = PORT_NAME
        port_id = PORT_ID
        vnic_type = VNIC_MACVTAP
        profile = {'pci_vendor_info': const.PCI_INFO_INTEL_82599}
        network_context = FakeNetworkContext([VLAN_SEGMENT])
        port_context = FakePortContext(name, port_id, vnic_type,
                                       profile, network_context)
        return port_context

    def _create_port_context_normal(self):
        """Creates port context with Normal vnic type."""
        name = PORT_NAME
        port_id = PORT_ID
        vnic_type = VNIC_NORMAL
        profile = {'pci_vendor_info': const.PCI_INFO_CISCO_VIC_1240}
        network_context = FakeNetworkContext([VLAN_SEGMENT])
        port_context = FakePortContext(name, port_id, vnic_type,
                                       profile, network_context)
        return port_context

    def test_parse_pci_vendor_config(self):
        """Verifies parsing of both good and bad pci vendor config."""
        vendor1 = PCI_INFO_INVALID
        vendor2 = const.PCI_INFO_INTEL_82599
        self.assertNotIn(vendor1, self.ucsm_driver.supported_pci_devs)
        self.assertIn(vendor2, self.ucsm_driver.supported_pci_devs)

    def test_port_supported_deviceowner(self):
        """Verifies detection of supported set of device owners for ports."""
        port_context = self._create_port_context_normal()
        port = port_context._port
        supported_owners = [n_const.DEVICE_OWNER_ROUTER_HA_INTF,
                            n_const.DEVICE_OWNER_DHCP,
                            'compute:nova']
        for owner in supported_owners:
            port['device_owner'] = owner
            self.assertTrue(self.mech_driver._is_supported_deviceowner(port))

    def test_port_unsupported_deviceowner(self):
        """Verifies detection of unsupported device owners for ports."""
        port_context = self._create_port_context_normal()
        port = port_context._port
        unsupported_owners = [n_const.DEVICE_OWNER_ROUTER_INTF,
                              n_const.DEVICE_OWNER_ROUTER_GW,
                              n_const.DEVICE_OWNER_FLOATINGIP,
                              n_const.DEVICE_OWNER_ROUTER_SNAT,
                              n_const.DEVICE_OWNER_LOADBALANCER,
                              n_const.DEVICE_OWNER_LOADBALANCERV2,
                              'controller:foobar']
        for owner in unsupported_owners:
            port['device_owner'] = owner
            self.assertFalse(self.mech_driver._is_supported_deviceowner(port))

    def test_port_supported_status(self):
        """Verifies detection of supported status values for ports."""
        port_context = self._create_port_context_normal()
        port = port_context._port
        port['status'] = n_const.PORT_STATUS_ACTIVE
        self.assertTrue(self.mech_driver._is_status_active(port))

    def test_port_unsupported_status(self):
        """Verifies detection of unsupported status values for ports."""
        port_context = self._create_port_context_normal()
        port = port_context._port
        unsupported_states = [n_const.PORT_STATUS_BUILD,
                              n_const.PORT_STATUS_DOWN,
                              n_const.PORT_STATUS_ERROR,
                              n_const.PORT_STATUS_NOTAPPLICABLE]
        for state in unsupported_states:
            port['status'] = state
            self.assertFalse(self.mech_driver._is_status_active(port))

    def test_vmfex_vnic_type_and_vendor_info(self):
        """Verifies VM-FEX port is recognized as a supported vendor."""
        port_context = self._create_port_context_vmfex()
        vnic_type = port_context.current.get(portbindings.VNIC_TYPE,
                                             portbindings.VNIC_NORMAL)
        profile = port_context.current.get(portbindings.PROFILE, {})
        supported = self.ucsm_driver.check_vnic_type_and_vendor_info(
            vnic_type, profile)
        self.assertTrue(supported)

    def test_unsupported_vnic_type_and_vendor_info(self):
        """Verifies unsupported pci vendor is rejected."""
        port_context = self._create_port_context_bad()
        vnic_type = port_context.current.get(portbindings.VNIC_TYPE,
                                             portbindings.VNIC_NORMAL)
        profile = port_context.current.get(portbindings.PROFILE, {})
        supported = self.ucsm_driver.check_vnic_type_and_vendor_info(
            vnic_type, profile)
        self.assertFalse(supported)

    def test_sriov_vnic_type_and_vendor_info(self):
        """Verifies SR-IOV port and MACVTAP vnic_type are supported."""
        port_context = self._create_port_context_sriov()
        vnic_type = port_context.current.get(portbindings.VNIC_TYPE,
                                             portbindings.VNIC_NORMAL)
        profile = port_context.current.get(portbindings.PROFILE, {})
        supported = self.ucsm_driver.check_vnic_type_and_vendor_info(
            vnic_type, profile)
        self.assertTrue(supported)

    def test_normal_vnic_type(self):
        """Verifies NORMAL vnic type is not supported."""
        port_context = self._create_port_context_normal()
        vnic_type = port_context.current.get(portbindings.VNIC_TYPE,
                                             portbindings.VNIC_NORMAL)
        profile = port_context.current.get(portbindings.PROFILE, {})
        supported = self.ucsm_driver.check_vnic_type_and_vendor_info(
            vnic_type, profile)
        self.assertFalse(supported)

    def test_validate_vm_fex_port_cisco(self):
        """Verifies port's pci vendor info makes it VM-FEX capable."""
        port_context = self._create_port_context_vmfex()
        profile = port_context.current.get(portbindings.PROFILE, {})
        valid = self.ucsm_driver.is_vmfex_port(profile)
        self.assertTrue(valid)

    def test_validate_vm_fex_port_bad(self):
        """Verifies unsupported pci vendor is not VM-FEX capable."""
        port_context = self._create_port_context_bad()
        profile = port_context.current.get(portbindings.PROFILE, {})
        valid = self.ucsm_driver.is_vmfex_port(profile)
        self.assertFalse(valid)

    def test_validate_vm_fex_port_sriov(self):
        """Verifies valid SR-IOV port is not VM-FEX capable."""
        port_context = self._create_port_context_sriov()
        profile = port_context.current.get(portbindings.PROFILE, {})
        valid = self.ucsm_driver.is_vmfex_port(profile)
        # For ex: Intel PCI is supported but is not vm-fex.
        # so, should return False
        self.assertFalse(valid)

    def test_check_segment_vlan(self):
        """Verifies VLAN network segments are supported."""
        self.assertTrue(self.mech_driver.check_segment(VLAN_SEGMENT))

    def test_check_segment_vxlan(self):
        """Verifies VXLAN network segments are not supported."""
        self.assertFalse(self.mech_driver.check_segment(VXLAN_SEGMENT))

    def test_vmfex_update_port_precommit(self):
        """Verifies MD saves relevant info for VM-FEX ports into DB."""
        name = PORT_NAME2
        port_id = PORT_ID
        vnic_type = VNIC_DIRECT
        profile = {'pci_vendor_info': const.PCI_INFO_CISCO_VIC_1240}
        profile_name = "OS-PP-100"

        network_context = self._create_network_context()
        port_context = FakePortContext(name, port_id, vnic_type,
                                       profile, network_context)
        # Port Profile name and Vlan id are written to DB.
        self.mech_driver.update_port_precommit(port_context)
        # Look for presence of above entry in the DB.
        p_profile = self.db.get_port_profile_for_vlan(VLAN_ID_1,
            UCSM_IP_ADDRESS_1)
        self.assertEqual(profile_name, p_profile)
        # Look to see if flag is set for update_port_postcommit to
        # create Port Profile on UCS Manager.
        self.assertFalse(self.db.is_port_profile_created(VLAN_ID_1,
            UCSM_IP_ADDRESS_1))

    def test_sriov_update_port_precommit(self):
        """Verifies MD does not create Port Profiles for SR-IOV ports."""
        port_context = self._create_port_context_sriov()
        self.mech_driver.update_port_precommit(port_context)
        p_profile = self.db.get_port_profile_for_vlan(VLAN_ID_1,
            UCSM_IP_ADDRESS_1)
        self.assertIsNone(p_profile)

    def test_get_physnet(self):
        expected_physnet = 'test_physnet'
        port_context = self._create_port_context_normal()
        physnet = self.mech_driver._get_physnet(port_context)
        self.assertEqual(expected_physnet, physnet)

    def test_virtio_update_port_precommit(self):
        """Verifies MD adds VNIC Template to DB for Neutron virtio ports."""
        TEST_VNIC_TEMPLATE = 'Test-VNIC'
        TEST_PHYSNET = 'test_physnet'
        port_context = self._create_port_context_normal()

        def new_vnic_template_test(object):
            return True

        mock.patch.object(conf.UcsmConfig,
                          'is_vnic_template_configured',
                          new=new_vnic_template_test).start()

        def new_get_vnic_template_for_physnet(object, ucsm_ip, physnet):
            return ('org-root', 'Test-VNIC')

        mock.patch.object(conf.UcsmConfig,
                          'get_vnic_template_for_physnet',
                          new=new_get_vnic_template_for_physnet).start()

        vnic_template_path, vnic_template = (
            self.ucsm_config.get_vnic_template_for_physnet(
                UCSM_IP_ADDRESS_1, TEST_PHYSNET))
        self.assertEqual(TEST_VNIC_TEMPLATE, vnic_template)
        self.mech_driver.update_port_precommit(port_context)
        db_entry = self.db.get_vnic_template_vlan_entry(VLAN_ID_1,
                                                        TEST_VNIC_TEMPLATE,
                                                        UCSM_IP_ADDRESS_1,
                                                        TEST_PHYSNET)
        self.assertIsNotNone(db_entry)
        self.assertEqual(VLAN_ID_1, db_entry.vlan_id)

    def test_update_port_postcommit_success(self):
        """Verifies duplicate Port Profiles are not being created."""
        name = PORT_NAME
        port_id = PORT_ID
        vnic_type = VNIC_DIRECT
        profile = {'pci_vendor_info': const.PCI_INFO_CISCO_VIC_1240}

        network_context = self._create_network_context()
        port_context = FakePortContext(name, port_id, vnic_type,
                                       profile, network_context)
        self.mech_driver.bind_port(port_context)

        # Port Profile is added to DB and created on UCS Manager.
        self.mech_driver.update_port_precommit(port_context)
        self.assertFalse(self.db.is_port_profile_created(VLAN_ID_1,
            UCSM_IP_ADDRESS_1))

        # Call to UCS Manager driver top level method to create Port Profile
        # is mocked to a new method here. This method verifies input params
        # are correct.
        def new_create_portprofile(mech_context, profile_name, vlan_id,
                                   vnic_type, ucsm_ip, trunk_vlans):
            return True

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          'create_portprofile',
                          new=new_create_portprofile).start()

        self.mech_driver.update_port_postcommit(port_context)
        self.assertTrue(self.db.is_port_profile_created(VLAN_ID_1,
            UCSM_IP_ADDRESS_1))

    def test_update_port_postcommit_failure(self):
        """Verifies duplicate Port Profiles are not being created."""
        name = PORT_NAME
        port_id = PORT_ID
        vnic_type = VNIC_DIRECT
        profile = {'pci_vendor_info': const.PCI_INFO_CISCO_VIC_1240}

        network_context = self._create_network_context()
        port_context = FakePortContext(name, port_id, vnic_type,
                                       profile, network_context)
        self.mech_driver.bind_port(port_context)

        # Port Profile is added to DB and created on UCS Manager.
        self.mech_driver.update_port_precommit(port_context)
        self.assertFalse(self.db.is_port_profile_created(VLAN_ID_1,
            UCSM_IP_ADDRESS_1))

        # Call to UCS Manager driver top level method to create Port Profile
        # is mocked to a new method here. This method verifies input params
        # are correct.
        def new_create_portprofile(mech_context, profile_name, vlan_id,
                                   vnic_type, ucsm_ip, trunk_vlans):
            return False

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          'create_portprofile',
                          new=new_create_portprofile).start()

        self.mech_driver.update_port_postcommit(port_context)
        self.assertFalse(self.db.is_port_profile_created(VLAN_ID_1,
             UCSM_IP_ADDRESS_1))

    def test_update_port_postcommit_direct(self):
        """Verifies UCS Manager driver is called with correct parameters."""
        name = PORT_NAME
        port_id = PORT_ID
        vnic_direct = VNIC_DIRECT
        profile = {'pci_vendor_info': const.PCI_INFO_CISCO_VIC_1240}

        network_context = self._create_network_context()
        port_context = FakePortContext(name, port_id, vnic_direct,
                                       profile, network_context)
        self.mech_driver.bind_port(port_context)

        self.mech_driver.update_port_precommit(port_context)

        # Call to UCS Manager driver top level method to create Port Profile
        # is mocked to a new method here. This method verifies input params
        # are correct.
        def new_create_portprofile(mech_context, profile_name, vlan_id,
                                   vnic_type, ucsm_ip, trunk_vlans):
            self.assertEqual("OS-PP-100", profile_name)
            self.assertEqual(100, vlan_id)
            self.assertEqual(VNIC_DIRECT, vnic_type)

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          'create_portprofile',
                          new=new_create_portprofile).start()

        self.mech_driver.update_port_postcommit(port_context)

    def test_update_port_postcommit_macvtap(self):
        """Verifies UCS Manager driver is called with correct parameters."""
        name = PORT_NAME
        port_id = PORT_ID
        vnic_macvtap = VNIC_MACVTAP
        profile = {'pci_vendor_info': const.PCI_INFO_CISCO_VIC_1240}

        network_context = self._create_network_context()
        port_context = FakePortContext(name, port_id, vnic_macvtap,
                                       profile, network_context)
        self.mech_driver.bind_port(port_context)

        self.mech_driver.update_port_precommit(port_context)

        # Call to UCS Manager driver top level method to create Port Profile
        # is mocked to a new method here. This method verifies input params
        # are correct.
        def new_create_portprofile(mech_context, profile_name, vlan_id,
                                   vnic_type, ucsm_ip, trunk_vlans):
            self.assertEqual("OS-PP-100", profile_name)
            self.assertEqual(100, vlan_id)
            self.assertEqual(VNIC_MACVTAP, vnic_type)

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          'create_portprofile',
                          new=new_create_portprofile).start()

        self.mech_driver.update_port_postcommit(port_context)

    def test_update_port_postcommit_normal(self):
        """Verifies UCS Manager driver is called with correct parameters."""
        name = PORT_NAME
        port_id = PORT_ID
        vnic_type = VNIC_NORMAL
        profile = {'pci_vendor_info': const.PCI_INFO_CISCO_VIC_1240}

        network_context = self._create_network_context()
        port_context = FakePortContext(name, port_id, vnic_type,
                                       profile, network_context)
        self.mech_driver.bind_port(port_context)

        self.mech_driver.update_port_precommit(port_context)

        # Call to UCS Manager driver top level method to create Port Profile
        # is mocked to a new method here. This method verifies input params
        # are correct.
        def new_update_serviceprofile(mech_context, host_id, vlan_id):
            return True

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          'update_serviceprofile',
                          new=new_update_serviceprofile).start()

        self.mech_driver.update_port_postcommit(port_context)

    def test_vnic_template_db_methods(self):
        """Verifies VNIC Template DB methods."""
        TEST_VNIC_TEMPLATE_1 = 'Test-VNIC1'
        TEST_VNIC_TEMPLATE_2 = 'Test-VNIC2'
        TEST_PHYSNET_1 = 'test_physnet1'
        TEST_PHYSNET_2 = 'test_physnet2'
        self.db.add_vnic_template(VLAN_ID_1, UCSM_IP_ADDRESS_1,
                                  TEST_VNIC_TEMPLATE_1, TEST_PHYSNET_1)
        self.db.add_vnic_template(VLAN_ID_2, UCSM_IP_ADDRESS_2,
                                  TEST_VNIC_TEMPLATE_2, TEST_PHYSNET_2)

        db_entry1 = self.db.get_vnic_template_vlan_entry(VLAN_ID_1,
                                                         TEST_VNIC_TEMPLATE_1,
                                                         UCSM_IP_ADDRESS_1,
                                                         TEST_PHYSNET_1)
        self.assertIsNotNone(db_entry1)
        self.assertEqual(VLAN_ID_1, db_entry1.vlan_id)
        self.assertFalse(db_entry1.updated_on_ucs)

        self.db.set_vnic_template_updated(VLAN_ID_2, UCSM_IP_ADDRESS_2,
            TEST_VNIC_TEMPLATE_2, TEST_PHYSNET_2)
        db_entry2 = self.db.get_vnic_template_vlan_entry(VLAN_ID_2,
                                                         TEST_VNIC_TEMPLATE_2,
                                                         UCSM_IP_ADDRESS_2,
                                                         TEST_PHYSNET_2)
        self.assertIsNotNone(db_entry2)
        self.assertEqual(VLAN_ID_2, db_entry2.vlan_id)
        self.assertTrue(db_entry2.updated_on_ucs)

        self.db.delete_vnic_template_for_vlan(VLAN_ID_2)
        db_entry3 = self.db.get_vnic_template_vlan_entry(VLAN_ID_2,
                                                         TEST_VNIC_TEMPLATE_2,
                                                         UCSM_IP_ADDRESS_2,
                                                         TEST_PHYSNET_2)
        self.assertIsNone(db_entry3)

    def test_update_port_postcommit_vnic_template(self):
        """Verifies UCSM driver works correcly with VNIC Templates."""
        TEST_VNIC_TEMPLATE = 'Test-VNIC'
        TEST_PHYSNET = 'test_physnet'
        port_context = self._create_port_context_normal()
        self.ucsm_driver.ucsm_host_dict = UCSM_HOST_DICT

        self.mech_driver.bind_port(port_context)

        def new_vnic_template_test(object):
            return True

        mock.patch.object(conf.UcsmConfig,
                          'is_vnic_template_configured',
                          new=new_vnic_template_test).start()

        physnet = self.mech_driver._get_physnet(port_context)
        self.assertEqual(TEST_PHYSNET, physnet)

        def new_get_vnic_template_for_physnet(object, ucsm_ip, physnet):
            return ('org-root', 'Test-VNIC')

        mock.patch.object(conf.UcsmConfig,
                          'get_vnic_template_for_physnet',
                          new=new_get_vnic_template_for_physnet).start()

        vnic_template_path, vnic_template = (
            self.ucsm_config.get_vnic_template_for_physnet(
                UCSM_IP_ADDRESS_1, TEST_PHYSNET))

        self.assertIsNotNone(vnic_template)
        self.assertEqual(TEST_VNIC_TEMPLATE, vnic_template)

        self.mech_driver.update_port_precommit(port_context)

        def new_update_vnic_template(mech_context, host_id, vlan_id, physnet,
            vnic_template_path, vnic_template):
            return True

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          'update_vnic_template',
                          new=new_update_vnic_template).start()

        ucsm_ip = self.ucsm_driver.get_ucsm_ip_for_host(HOST1)
        self.assertEqual(UCSM_IP_ADDRESS_1, ucsm_ip)

        self.mech_driver.update_port_postcommit(port_context)

        db_entry = self.db.get_vnic_template_vlan_entry(VLAN_ID_1,
                                                        vnic_template,
                                                        UCSM_IP_ADDRESS_1,
                                                        TEST_PHYSNET)
        self.assertIsNotNone(db_entry)
        self.assertEqual(UCSM_IP_ADDRESS_1, db_entry.device_id)

    def test_bind_port_active(self):
        """Verifies bind_port sets the port status as active."""
        name = PORT_NAME
        port_id = PORT_ID
        vnic_type = VNIC_DIRECT
        profile = {'pci_vendor_info': const.PCI_INFO_CISCO_VIC_1240}

        network_context = FakeNetworkContext(VLAN_SEGMENTS_GOOD)
        port_context = FakePortContext(name, port_id, vnic_type,
                                       profile, network_context)
        self.mech_driver.bind_port(port_context)
        self.assertEqual(PORT_STATE_ACTIVE, port_context._port['status'])

    def test_ucs_manager_disconnect_fail(self):
        """Verifies UCS Manager driver is called with correct parameters."""

        handle = None
        ucsm_ip = UCSM_IP_ADDRESS_2
        self.assertRaises(exceptions.UcsmDisconnectFailed,
                          self.ucsm_driver.ucs_manager_disconnect,
                          handle, ucsm_ip)

    def test_generic_create_profile(self):
        """Test to verify duplicate creation exceptions.

        This is a generic test to mimic the behavior of any UCS Manager
        driver function that creates a profile on the UCS Manager. The
        first time the profile is created, the create succeeds if all
        parameters are correct. If we attempt to create it any number
        of times after that, UCS Manager throws an exception. This test
        code mimics that behavior by using counter to keep track of how
        many times 'update_serviceprofile' is being called.
        counter == 0 -> Simulates invalid input, so raise an exception.
        counter == 1 -> Simulates valid inputs and 1st creation request.
        counter > 1 -> Simulates duplicate creation request and results
        in UCS Manager throwing a duplicate creation request.
        """
        def static_vars(**kwargs):
            def decorate(func):
                for k in kwargs:
                    setattr(func, k, kwargs[k])
                return func
            return decorate

        @static_vars(counter=-1)
        def new_create_ucsm_profile(mech_context, host_id, vlan_id):
            new_create_ucsm_profile.counter += 1
            try:
                if new_create_ucsm_profile.counter == 0:
                    raise Exception("Invalid Operation")
                elif new_create_ucsm_profile.counter > 1:
                    raise Exception(const.DUPLICATE_EXCEPTION)
                else:
                    return True
            except Exception as e:
                if const.DUPLICATE_EXCEPTION in str(e):
                    return True
                else:
                    raise exceptions.UcsmConfigFailed(config=vlan_id,
                                            ucsm_ip=UCSM_IP_ADDRESS_1, exc=e)

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          'update_serviceprofile',
                          new=new_create_ucsm_profile).start()

        # Results in new_create_ucsm_profile being called with counter=-1
        self.assertRaises(exceptions.UcsmConfigFailed,
                          self.ucsm_driver.update_serviceprofile,
                          HOST1, VLAN_ID_1)

        # Results in new_create_ucsm_profile being called with counter=0
        self.assertTrue(self.ucsm_driver.update_serviceprofile(
                        HOST1, VLAN_ID_1))

        # Results in new_create_ucsm_profile being called with counter=1
        self.assertTrue(self.ucsm_driver.update_serviceprofile(
                        HOST1, VLAN_ID_1))

    def test_parse_ucsm_host_config(self):
        """Verifies parsing of Hostname:Service Profile config."""
        ucsm_sp_dict = {}
        ucsm_host_dict = {}
        cfg.CONF.ml2_cisco_ucsm.ucsm_host_list = ['Host1:SP1', 'Host2:SP2']
        cfg.CONF.ml2_cisco_ucsm.ucsm_ip = '1.1.1.1'
        expected_ip = '1.1.1.1'
        expected_sp1 = "org-root/ls-SP1"
        expected_sp2 = "org-root/ls-SP2"
        ucsm_sp_dict, ucsm_host_dict = conf.parse_ucsm_host_config()

        key = (cfg.CONF.ml2_cisco_ucsm.ucsm_ip, 'Host1')
        self.assertIn(key, ucsm_sp_dict)
        self.assertEqual(expected_sp1, ucsm_sp_dict[key])
        self.assertIn('Host1', ucsm_host_dict)
        self.assertEqual(expected_ip, ucsm_host_dict['Host1'])

        key = (cfg.CONF.ml2_cisco_ucsm.ucsm_ip, 'Host2')
        self.assertIn(key, ucsm_sp_dict)
        self.assertEqual(expected_sp2, ucsm_sp_dict.get(key))
        self.assertEqual(expected_ip, ucsm_host_dict.get('Host2'))

        key = (cfg.CONF.ml2_cisco_ucsm.ucsm_ip, 'Host3')
        self.assertNotIn(key, ucsm_sp_dict)
        self.assertIsNone(ucsm_host_dict.get('Host3'))

    def test_bad_ucsm_host_config(self):
        """Verifies malformed ucsm_host_list raises an error."""
        cfg.CONF.ml2_cisco_ucsm.ucsm_host_list = ['Host1:', 'Host2:SP2']
        self.assertRaisesRegex(cfg.Error, "Host1:",
            conf.parse_ucsm_host_config)

        cfg.CONF.ml2_cisco_ucsm.ucsm_host_list = ['Host1:SP1', 'Host2']
        self.assertRaisesRegex(cfg.Error, "Host2",
            conf.parse_ucsm_host_config)

    def test_parse_virtio_eth_ports(self):
        cfg.CONF.ml2_cisco_ucsm.ucsm_virtio_eth_ports = ['test-eth1',
                                                         'test-eth2']
        eth_port_list = conf.parse_virtio_eth_ports()
        self.assertNotIn('test-eth1', eth_port_list)
        self.assertIn(const.ETH_PREFIX + 'test-eth1', eth_port_list)

    def test_ucsm_host_config_with_path(self):
        """Verifies that ucsm_host_list can contain SP paths."""
        expected_service_profile1 = 'org-root/ls-SP1'
        expected_service_profile2 = 'org-root/sub-org1/ls-SP2'
        cfg.CONF.ml2_cisco_ucsm.ucsm_ip = '1.1.1.1'
        cfg.CONF.ml2_cisco_ucsm.ucsm_host_list = ['Host1:SP1',
            'Host2:org-root/sub-org1/ls-SP2']

        ucsm_sp_dict, ucsm_host_dict = conf.parse_ucsm_host_config()

        key = ('1.1.1.1', 'Host1')
        actual_service_profile1 = ucsm_sp_dict.get(key)
        self.assertEqual(expected_service_profile1, actual_service_profile1)

        key = ('1.1.1.1', 'Host2')
        actual_service_profile2 = ucsm_sp_dict.get(key)
        self.assertEqual(expected_service_profile2, actual_service_profile2)

    def test_host_id_to_hostname(self):
        host_id_with_domain1 = 'compute1.cisco.com'
        expected_hostname1 = 'compute1'

        hostname = self.mech_driver._get_host_id(
            host_id_with_domain1)
        self.assertEqual(expected_hostname1, hostname)

        host_id_with_domain2 = 'compute2.localdomain'
        expected_hostname2 = 'compute2'

        hostname = self.mech_driver._get_host_id(
            host_id_with_domain2)
        self.assertEqual(expected_hostname2, hostname)

        host_id3 = 'compute3'
        hostname = self.mech_driver._get_host_id(host_id3)
        self.assertEqual(host_id3, hostname)
