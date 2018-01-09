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

from neutron.tests.unit import testlib_api

from networking_cisco.backwards_compatibility import ml2_api as api

from networking_cisco import backwards_compatibility as bc
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import (
    mech_cisco_ucsm as md)
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import config as conf
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import constants as const
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import exceptions
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import ucsm_db
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import ucsm_network_driver
from networking_cisco.tests.unit.ml2.drivers.cisco.ucsm import (
    test_cisco_ucsm_common as mocked)


CONF = cfg.CONF

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
PORT_STATE_ACTIVE = bc.constants.PORT_STATUS_ACTIVE
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

PORT_PROFILE_1 = 'OS-PP-100'


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
            'device_owner': bc.constants.DEVICE_OWNER_DHCP,
            bc.portbindings.HOST_ID: HOST1,
            bc.portbindings.VNIC_TYPE: vnic_type,
            bc.portbindings.PROFILE: profile
        }
        self._network = network_context
        self._segment = network_context.network_segments[0]
        self.session = bc.get_writer_session()

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


class FakeServiceProfile(object):
    """Fake Service Profile class for testing only."""
    def __init__(self, service_profile):
        self.sp = service_profile
        self.pn_dn = 'org-root/ls-'
        self.dn = 'org-root'
        self.oper_src_templ_name = (
            self.pn_dn + self.dn)
        self.pn_dn = self.pn_dn + self.sp

    def __iter__(self):
        return self

    def __next__(self):
        return self

    def next(self):
        return self.__next__()


class FakeServer(object):
    def __init__(self, server):
        self.name = server


class FakeUcsmHandle(object):
    """Ucsm connection handle for testing purposes only."""

    def __init__(self, port_profile=None, query_dn=None, invalid_classid=None):
        self._port_profile = port_profile
        self._query_dn = query_dn
        self._invalid_classid = invalid_classid
        self._times_called = 0
        self.sp_list = ['org-root/ls-SP1']
        self.sp_list_temp = []

    def query_dn(self, dn):
        self._times_called += 1

        if self._invalid_classid:
            return FakeServer('nope')
        elif self._query_dn:
            return self._query_dn
        elif dn == 'org-root/ls-SP1':
            return FakeServer(HOST1)
        elif self._times_called == 1:
            return None
        elif self._times_called == 2:
            raise Exception("Port profile still in use by VMs.")
        else:
            return self._port_profile

    def query_classid(self, class_id):
        if self._invalid_classid:
            self.sp_list_temp = [FakeServiceProfile('nope'),
                FakeServiceProfile('nope')]
        else:
            self.sp_list_temp = [FakeServiceProfile('SP1'),
                FakeServiceProfile('SP2')]
        return self.sp_list_temp

    def remove_mo(self, p_profile):
        self._port_profile = None

    def commit(self):
        return

    def logout(self):
        return


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
            mech_instance.ucsm_conf = conf.UcsmConfig()

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          '__init__',
                          new=new_ucsm_driver_init).start()

        self.mech_driver = md.CiscoUcsmMechanismDriver()
        self.mech_driver.initialize()
        self.vif_type = const.VIF_TYPE_802_QBH
        self.db = ucsm_db.UcsmDbModel()
        self.ucsm_driver = ucsm_network_driver.CiscoUcsmDriver()
        self.ucsm_driver.ucsm_db = ucsm_db.UcsmDbModel()
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

    def test_port_supported_deviceowner(self):
        """Verifies detection of supported set of device owners for ports."""
        port_context = self._create_port_context_normal()
        port = port_context._port
        supported_owners = [bc.constants.DEVICE_OWNER_ROUTER_HA_INTF,
                            bc.constants.DEVICE_OWNER_DHCP,
                            'compute:nova']
        for owner in supported_owners:
            port['device_owner'] = owner
            self.assertTrue(self.mech_driver._is_supported_deviceowner(port))

    def test_port_unsupported_deviceowner(self):
        """Verifies detection of unsupported device owners for ports."""
        port_context = self._create_port_context_normal()
        port = port_context._port
        unsupported_owners = [bc.constants.DEVICE_OWNER_ROUTER_INTF,
                              bc.constants.DEVICE_OWNER_ROUTER_GW,
                              bc.constants.DEVICE_OWNER_FLOATINGIP,
                              bc.constants.DEVICE_OWNER_ROUTER_SNAT,
                              bc.constants.DEVICE_OWNER_LOADBALANCER,
                              bc.constants.DEVICE_OWNER_LOADBALANCERV2,
                              'controller:foobar']
        for owner in unsupported_owners:
            port['device_owner'] = owner
            self.assertFalse(self.mech_driver._is_supported_deviceowner(port))

    def test_port_supported_status(self):
        """Verifies detection of supported status values for ports."""
        port_context = self._create_port_context_normal()
        port = port_context._port
        port['status'] = bc.constants.PORT_STATUS_ACTIVE
        self.assertTrue(self.mech_driver._is_status_active(port))

    def test_port_unsupported_status(self):
        """Verifies detection of unsupported status values for ports."""
        port_context = self._create_port_context_normal()
        port = port_context._port
        unsupported_states = [bc.constants.PORT_STATUS_BUILD,
                              bc.constants.PORT_STATUS_DOWN,
                              bc.constants.PORT_STATUS_ERROR,
                              bc.constants.PORT_STATUS_NOTAPPLICABLE]
        for state in unsupported_states:
            port['status'] = state
            self.assertFalse(self.mech_driver._is_status_active(port))

    def test_vmfex_vnic_type_and_vendor_info(self):
        """Verifies VM-FEX port is recognized as a supported vendor."""
        port_context = self._create_port_context_vmfex()
        vnic_type = port_context.current.get(bc.portbindings.VNIC_TYPE,
                                             bc.portbindings.VNIC_NORMAL)
        profile = port_context.current.get(bc.portbindings.PROFILE, {})
        supported = self.ucsm_driver.check_vnic_type_and_vendor_info(
            vnic_type, profile)
        self.assertTrue(supported)

    def test_unsupported_vnic_type_and_vendor_info(self):
        """Verifies unsupported pci vendor is rejected."""
        port_context = self._create_port_context_bad()
        vnic_type = port_context.current.get(bc.portbindings.VNIC_TYPE,
                                             bc.portbindings.VNIC_NORMAL)
        profile = port_context.current.get(bc.portbindings.PROFILE, {})
        supported = self.ucsm_driver.check_vnic_type_and_vendor_info(
            vnic_type, profile)
        self.assertFalse(supported)

    def test_sriov_vnic_type_and_vendor_info(self):
        """Verifies SR-IOV port and MACVTAP vnic_type are supported."""
        port_context = self._create_port_context_sriov()
        vnic_type = port_context.current.get(bc.portbindings.VNIC_TYPE,
                                             bc.portbindings.VNIC_NORMAL)
        profile = port_context.current.get(bc.portbindings.PROFILE, {})
        supported = self.ucsm_driver.check_vnic_type_and_vendor_info(
            vnic_type, profile)
        self.assertTrue(supported)

    def test_normal_vnic_type(self):
        """Verifies NORMAL vnic type is not supported."""
        port_context = self._create_port_context_normal()
        vnic_type = port_context.current.get(bc.portbindings.VNIC_TYPE,
                                             bc.portbindings.VNIC_NORMAL)
        profile = port_context.current.get(bc.portbindings.PROFILE, {})
        supported = self.ucsm_driver.check_vnic_type_and_vendor_info(
            vnic_type, profile)
        self.assertFalse(supported)

    def test_validate_vm_fex_port_cisco(self):
        """Verifies port's pci vendor info makes it VM-FEX capable."""
        port_context = self._create_port_context_vmfex()
        profile = port_context.current.get(bc.portbindings.PROFILE, {})
        valid = self.ucsm_driver.is_vmfex_port(profile)
        self.assertTrue(valid)

    def test_validate_vm_fex_port_bad(self):
        """Verifies unsupported pci vendor is not VM-FEX capable."""
        port_context = self._create_port_context_bad()
        profile = port_context.current.get(bc.portbindings.PROFILE, {})
        valid = self.ucsm_driver.is_vmfex_port(profile)
        self.assertFalse(valid)

    def test_validate_vm_fex_port_sriov(self):
        """Verifies valid SR-IOV port is not VM-FEX capable."""
        port_context = self._create_port_context_sriov()
        profile = port_context.current.get(bc.portbindings.PROFILE, {})
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

    @mock.patch.object(ucsm_db.UcsmDbModel, 'delete_sp_template_for_vlan')
    @mock.patch.object(ucsm_db.UcsmDbModel, 'delete_vnic_template_for_vlan')
    @mock.patch.object(ucsm_db.UcsmDbModel, 'delete_vlan_entry')
    def test_delete_network_precommit_no_segments(
            self, mock_delete_vlan_entry, mock_delete_vnic,
            mock_delete_sp_template):
        self.mech_driver.delete_network_precommit(FakeNetworkContext([]))
        self.assertFalse(mock_delete_vlan_entry.called)
        self.assertFalse(mock_delete_vnic.called)
        self.assertFalse(mock_delete_sp_template.called)

    @mock.patch.object(ucsm_db.UcsmDbModel, 'delete_sp_template_for_vlan')
    @mock.patch.object(ucsm_db.UcsmDbModel, 'delete_vnic_template_for_vlan')
    @mock.patch.object(ucsm_db.UcsmDbModel, 'delete_vlan_entry')
    def test_delete_network_precommit_vlan_segment(
            self, mock_delete_vlan_entry, mock_delete_vnic,
            mock_delete_sp_template):
        network_context = self._create_network_context()
        vlan_id = network_context.network_segments[0]['segmentation_id']
        self.mech_driver.delete_network_precommit(network_context)
        mock_delete_vlan_entry.assert_called_once_with(vlan_id)
        mock_delete_vnic.assert_called_once_with(vlan_id)
        mock_delete_sp_template.assert_called_once_with(vlan_id)

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
        ucsm = cfg.CONF.ml2_cisco_ucsm.ucsms['1.1.1.1']
        cfg.CONF.set_override("ucsm_host_list",
                              {'Host1': 'SP1', 'Host2': 'SP2'},
                              group=ucsm._group)
        expected_ip = '1.1.1.1'
        expected_sp1 = "org-root/ls-SP1"
        expected_sp2 = "org-root/ls-SP2"

        ucsm_sp_dict = self.ucsm_config.ucsm_sp_dict
        ucsm_host_dict = self.ucsm_config.ucsm_host_dict

        key = (expected_ip, 'Host1')
        self.assertIn(key, ucsm_sp_dict)
        self.assertEqual(expected_sp1, ucsm_sp_dict[key])
        self.assertIn('Host1', ucsm_host_dict)
        self.assertEqual(expected_ip, ucsm_host_dict['Host1'])

        key = (expected_ip, 'Host2')
        self.assertIn(key, ucsm_sp_dict)
        self.assertEqual(expected_sp2, ucsm_sp_dict.get(key))
        self.assertEqual(expected_ip, ucsm_host_dict.get('Host2'))

        key = (expected_ip, 'Host3')
        self.assertNotIn(key, ucsm_sp_dict)
        self.assertIsNone(ucsm_host_dict.get('Host3'))

    def test_parse_virtio_eth_ports(self):
        """Verifies eth_port_list contains a fully-formed path."""
        eth_port_list = (
            CONF.ml2_cisco_ucsm.ucsms['1.1.1.1'].ucsm_virtio_eth_ports)
        self.assertNotIn('eth4', eth_port_list)
        self.assertIn(const.ETH_PREFIX + 'eth4', eth_port_list)

    def test_ucsm_host_config_with_path(self):
        """Verifies that ucsm_host_list can contain SP paths."""
        expected_service_profile1 = 'org-root/ls-SP1'
        expected_service_profile2 = 'org-root/sub-org1/ls-SP2'
        ucsm = cfg.CONF.ml2_cisco_ucsm.ucsms['1.1.1.1']
        cfg.CONF.set_override("ucsm_host_list",
                              {'Host1': 'SP1',
                               'Host2': 'org-root/sub-org1/ls-SP2'},
                              group=ucsm._group)

        ucsm_sp_dict = self.ucsm_config.ucsm_sp_dict

        key = ('1.1.1.1', 'Host1')
        actual_service_profile1 = ucsm_sp_dict.get(key)
        self.assertEqual(expected_service_profile1, actual_service_profile1)

        key = ('1.1.1.1', 'Host2')
        actual_service_profile2 = ucsm_sp_dict.get(key)
        self.assertEqual(expected_service_profile2, actual_service_profile2)

    def test_host_id_to_hostname(self):
        """Verifies extraction of hostname from host-id from Nova."""
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

    def test_port_profile_delete_table_add(self):
        """Verifies that add and get of 1 PP to delete table works."""
        self.db.add_port_profile_to_delete_table('OS-PP-100', '10.10.10.10')
        self.assertTrue(self.db.has_port_profile_to_delete('OS-PP-100',
            '10.10.10.10'))

    def test_pp_delete_table_add_multiple(self):
        """Verifies that add and get of multiple PPs to delete table works."""
        self.db.add_port_profile_to_delete_table("OS-PP-100", "10.10.10.10")
        self.db.add_port_profile_to_delete_table("OS-PP-200", "10.10.10.10")
        all_pps = self.db.get_all_port_profiles_to_delete()
        for pp in all_pps:
            self.assertEqual("10.10.10.10", pp.device_id)

    def test_remove_port_profile_from_table(self):
        """Verifies that removing entry from PP delete table works."""
        self.db.add_port_profile_to_delete_table("OS-PP-100", "10.10.10.10")
        self.db.remove_port_profile_to_delete("OS-PP-100", "10.10.10.10")
        self.assertFalse(self.db.has_port_profile_to_delete("OS-PP-100",
            "10.10.10.10"))

    def test_remove_non_existent_port_profile_from_table(self):
        """Verifies that removing previously deleted PP works."""
        self.assertIsNone(self.db.remove_port_profile_to_delete(
            "OS-PP-100", "10.10.10.10"))

    def test_port_profile_delete_on_ucsm(self):
        """Verifies that the PP delete retry logic."""
        handle = FakeUcsmHandle(PORT_PROFILE_1)

        # 1st call to delete_port_profile is designed to not find
        # the PP on the UCSM
        self.ucsm_driver._delete_port_profile(
            handle, PORT_PROFILE_1, UCSM_IP_ADDRESS_1)

        # No entry added to the PP delete table
        self.assertFalse(self.ucsm_driver.ucsm_db.has_port_profile_to_delete(
            PORT_PROFILE_1, UCSM_IP_ADDRESS_1))

        # 2nd call to delete_port_profile is designed to raise exception
        self.ucsm_driver._delete_port_profile(
            handle, PORT_PROFILE_1, UCSM_IP_ADDRESS_1)

        # Failed delete results in entry being created in the PP delete table
        self.assertTrue(self.ucsm_driver.ucsm_db.has_port_profile_to_delete(
            PORT_PROFILE_1, UCSM_IP_ADDRESS_1))

    def test_add_sp_template_config_to_db(self):
        """Verifies the SP template dict has been created properly."""
        host_id = HOST1
        ucsm_ip = UCSM_IP_ADDRESS_1
        sp_template_with_path = "/org-root/test/ls-SP-Test"
        sp_template_info = sp_template_with_path.rsplit('/', 1)

        self.ucsm_config.update_sp_template_config(host_id, ucsm_ip,
                                                   sp_template_with_path)

        ucsm = CONF.ml2_cisco_ucsm.ucsms[UCSM_IP_ADDRESS_1]
        self.assertEqual(sp_template_info[1],
                         ucsm.sp_template_list[HOST1].name)
        self.assertEqual(sp_template_info[0],
                         ucsm.sp_template_list[HOST1].path)

    def test_get_ucsm_ip_for_host_success(self):
        """Verfies that ucsm_ip to Service Profile mapping is successful."""
        host_id = HOST1
        ucsm_ip = UCSM_IP_ADDRESS_1
        sp_template_with_path = "/org-root/test/ls-SP-Test"

        self.ucsm_config.update_sp_template_config(host_id, ucsm_ip,
                                                   sp_template_with_path)
        self.assertEqual(ucsm_ip, self.ucsm_driver.get_ucsm_ip_for_host(
            host_id))

    def test_get_ucsm_ip_for_host_failure(self):
        """Tests that case where UCSM does not control this host."""
        def new_learn_sp_and_template_for_host(mech_instance, host_id):
            return None

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          '_learn_sp_and_template_for_host',
                          new=new_learn_sp_and_template_for_host).start()

        self.assertIsNone(self.ucsm_driver.get_ucsm_ip_for_host('Hostname3'))

    def test_learn_sp_and_template_for_host_exp(self):
        """Tests case where reading config from UCSM generates exception."""
        host_id = HOST1

        def mocked_connect(self, ucsm_ip):
            handle = mock.Mock()
            return handle

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          'ucs_manager_connect',
                          new=mocked_connect).start()

        self.assertRaises(exceptions.UcsmConfigReadFailed,
                          self.ucsm_driver._learn_sp_and_template_for_host,
                          host_id)

    def test_learn_sp_and_template_for_host_error(self):
        """Tests case where learning config from UCSM gives diff host.`"""
        host_id = HOST1

        def mocked_connect(self, ucsm_ip):
            handle = FakeUcsmHandle(PORT_PROFILE_1, FakeServer(HOST2))
            return handle

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          'ucs_manager_connect',
                          new=mocked_connect).start()

        self.assertIsNone(
            self.ucsm_driver._learn_sp_and_template_for_host(host_id))

    def test_learn_sp_and_template_for_host_success(self):
        """Tests case where learning config from UCSM gives correct host.`"""
        host_id = HOST1
        expected_ucsm_ip = '2.2.2.2'

        def mocked_connect(self, ucsm_ip):
            if ucsm_ip == expected_ucsm_ip:
                handle = FakeUcsmHandle()
            else:
                handle = FakeUcsmHandle(invalid_classid=True)
            return handle

        mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                          'ucs_manager_connect',
                          new=mocked_connect).start()

        actual_ucsm_ip = self.ucsm_driver._learn_sp_and_template_for_host(
            host_id)

        self.assertEqual(expected_ucsm_ip, actual_ucsm_ip)

        # Resetting the ucsm_host_dict value to what the other tests expect.
        self.ucsm_driver.ucsm_host_dict[HOST1] = '1.1.1.1'
