# Copyright 2015 Cisco Systems, Inc.
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
#


import mock
import six

from neutron.tests import base

from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.common import constants
from networking_cisco.apps.saf.db import dfa_db_models as dbm
from networking_cisco.apps.saf.server import cisco_dfa_rest as cdr
from networking_cisco.apps.saf.server import dfa_events_handler as deh
from networking_cisco.apps.saf.server import dfa_fail_recovery as dfr
from networking_cisco.apps.saf.server import dfa_instance_api as dia
from networking_cisco.apps.saf.server.services.firewall.native import (
    fw_mgr as fw_native)

FAKE_NETWORK_NAME = 'test_dfa_network'
FAKE_NETWORK_ID = '949fdd05-a26a-4819-a829-9fc2285de6ff'
FAKE_CFG_PROF_ID = '8c30f360ffe948109c28ab56f69a82e1'
FAKE_SEG_ID = 12345
FAKE_PROJECT_NAME = 'test_dfa_project'
FAKE_ORCH_ID = 'test_openstack'
FAKE_PROJECT_ID = 'aee5da7e699444889c662cf7ec1c8de7'
FAKE_CFG_PROFILE_NAME = 'defaultNetworkL2Profile'
FAKE_INSTANCE_NAME = 'test_dfa_instance'
FAKE_SUBNET_ID = '1a3c5ee1-cb92-4fd8-bff1-8312ac295d64'
FAKE_PORT_ID = 'ea0d92cf-d0cb-4ed2-bbcf-ed7c6aaea4cb'
FAKE_DEVICE_ID = '20305657-78b7-48f4-a7cd-1edf3edbfcad'
FAKE_SECURITY_GRP_ID = '4b5b387d-cf21-4594-b926-f5a5c602295f'
FAKE_MAC_ADDR = 'fa:16:3e:70:15:c4'
FAKE_IP_ADDR = '23.24.25.4'
FAKE_GW_ADDR = '23.24.25.1'
FAKE_DHCP_IP_START = '23.24.25.2'
FAKE_DHCP_IP_END = '23.24.25.254'
FAKE_HOST_ID = 'test_dfa_host'
FAKE_FWD_MODE = 'proxy-gateway'
FAKE_DCNM_USERNAME = 'cisco'
FAKE_DCNM_PASSWD = 'password'
FAKE_DCNM_IP = '1.1.2.2'


class FakeClass(object):
    """Fake class"""
    @classmethod
    def imitate(cls, *others):
        for other in others:
            for name in other.__dict__:
                try:
                    setattr(cls, name, mock.Mock())
                except (TypeError, AttributeError):
                    pass
        return cls


class FakeProject(object):
    """Fake Project class."""
    def __init__(self, proj_id, name, dci_id, desc):
        self.id = proj_id
        self.name = name
        self.dci_id = dci_id
        self.description = desc


class TestDFAServer(base.BaseTestCase):
    """Test cases for DFA Server class."""

    def setUp(self):
        super(TestDFAServer, self).setUp()

        # Mocking some modules
        self.dcnmpatcher = mock.patch(cdr.__name__ + '.DFARESTClient')
        self.mdcnm = self.dcnmpatcher.start()

        self.keys_patcher = mock.patch(deh.__name__ + '.EventsHandler')
        self.mkeys = self.keys_patcher.start()

        self.inst_api_patcher = mock.patch(dia.__name__ + '.DFAInstanceAPI')
        self.m_inst_api = self.inst_api_patcher.start()

        self.module_patcher = mock.patch.dict('sys.modules',
                                              {'pika': mock.Mock()})
        self.module_patcher.start()

        from networking_cisco.apps.saf.server import dfa_listen_dcnm as dld
        from networking_cisco.apps.saf.server import dfa_server as ds
        self.dld_patcher = mock.patch(dld.__name__ + '.DCNMListener')
        self.dld = self.dld_patcher.start()

        ds.DfaServer.__bases__ = (FakeClass.imitate(
            dfr.DfaFailureRecovery, dbm.DfaDBMixin, fw_native.FwMgr),)

        ds.DfaServer.get_all_projects.return_value = []
        ds.DfaServer.get_all_networks.return_value = []
        ds.DfaServer._setup_rpc = mock.Mock()
        # TODO(padkrish) Have UT for this function. This may mean over-riding
        # the mocking of get_segmentid_range of DCNM client to return a range.
        ds.DfaServer.register_segment_dcnm = mock.Mock()
        # Setting DCNM parameters.
        config.default_dcnm_opts['dcnm']['dcnm_ip'] = FAKE_DCNM_IP
        config.default_dcnm_opts['dcnm']['dcnm_user'] = FAKE_DCNM_USERNAME
        config.default_dcnm_opts['dcnm']['dcnm_password'] = FAKE_DCNM_PASSWD
        config.default_dcnm_opts['dcnm']['timeout_resp'] = 0.01
        config.default_dcnm_opts['dcnm']['segmentation_id_min'] = 10000
        config.default_dcnm_opts['dcnm']['segmentation_id_max'] = 20000
        config.default_dcnm_opts['dcnm']['orchestrator_id'] = FAKE_ORCH_ID
        self.cfg = config.CiscoDFAConfig().cfg
        self.segid = int(self.cfg.dcnm.segmentation_id_min) + 10
        self.seg_Drvr = mock.patch(
            'networking_cisco.apps.saf.db.dfa_db_models.'
            'DfaSegmentTypeDriver').start()

        self.dfa_server = ds.DfaServer(self.cfg)
        mock.patch.object(self.dfa_server, '_get_segmentation_id',
                          return_value=12345).start()
        mock.patch.object(self.dfa_server.seg_drvr,
                          'allocate_segmentation_id',
                          return_value=12345).start()
        self.dciid = str(123)
        self.proj_desc = 'Unit Test Project'
        projs = [
            FakeProject(FAKE_PROJECT_ID, FAKE_PROJECT_NAME,
                        self.dciid, self.proj_desc)]
        self.dfa_server.get_all_projects.return_value = projs
        self.dfa_server._load_project_info_cache()
        self.part_name = self.cfg.dcnm.default_partition_name

    def _get_port_info(self):
        port_info = {'port': {
            'status': 'ACTIVE',
            'binding:host_id': FAKE_HOST_ID,
            'allowed_address_pairs': [],
            'extra_dhcp_opts': [],
            'device_owner': 'compute:nova',
            'binding:profile': {},
            'fixed_ips': [{'subnet_id': FAKE_SUBNET_ID,
                           'ip_address': FAKE_IP_ADDR}],
            'id': FAKE_PORT_ID,
            'security_groups': [FAKE_SECURITY_GRP_ID],
            'device_id': FAKE_DEVICE_ID,
            'name': '',
            'admin_state_up': True,
            'network_id': FAKE_NETWORK_ID,
            'tenant_id': FAKE_PROJECT_ID,
            'binding:vif_details': {'port_filter': True,
                                    'ovs_hybrid_plug': True},
            'binding:vnic_type': 'normal',
            'binding:vif_type': 'ovs',
            'mac_address': FAKE_MAC_ADDR}}
        return port_info

    def _load_network_info(self):
        dnet = mock.Mock()
        dnet.network_id = FAKE_NETWORK_ID
        dnet.segmentation_id = self.segid
        dnet.config_profile = FAKE_CFG_PROFILE_NAME
        dnet.fwd_mod = FAKE_FWD_MODE
        dnet.tenant_id = FAKE_PROJECT_ID
        dnet.name = FAKE_NETWORK_NAME
        self.dfa_server.get_all_networks.return_value = [dnet]
        self.dfa_server._load_network_info()

    def test_update_project_info_cache(self):
        """Test case for update project info."""

        pid = FAKE_PROJECT_ID
        name = FAKE_PROJECT_NAME
        dciid = 1000
        result = constants.RESULT_SUCCESS
        self.dfa_server.update_project_info_cache(pid, dci_id=dciid,
                                                  name=name, opcode='add')
        self.assertTrue(self.dfa_server.add_project_db.called)
        self.assertFalse(self.dfa_server.update_project_entry.called)
        self.assertFalse(self.dfa_server.del_project_db.called)
        self.dfa_server.add_project_db.assert_called_with(pid, name,
                                                          dciid, result)

        self.dfa_server.update_project_info_cache(pid, dci_id=dciid,
                                                  name=name,
                                                  opcode='update')
        self.assertTrue(self.dfa_server.update_project_entry.called)
        self.assertFalse(self.dfa_server.del_project_db.called)
        self.dfa_server.update_project_entry.assert_called_with(pid, dciid,
                                                                result)

    def test_project_create_event(self):
        """Test case for project create event."""

        dciid = str(12345)
        proj_desc = 'Unit Test Project'
        proj_info = {'resource_info': FAKE_PROJECT_ID}
        proj = mock.Mock()
        proj.name = FAKE_PROJECT_NAME
        proj.description = proj_desc
        part_name = self.cfg.dcnm.default_partition_name
        self.dfa_server.keystone_event._service.projects.get.return_value = (
            proj)

        self.dfa_server.project_create_event(proj_info)
        # Try it with DCI id
        proj.name = FAKE_PROJECT_NAME + ':dci_id:' + dciid
        self.dfa_server.project_create_event(proj_info)
        expected_calls = [
            mock.call(FAKE_ORCH_ID, FAKE_PROJECT_NAME, part_name, None,
                      proj.description),
            mock.call(FAKE_ORCH_ID, FAKE_PROJECT_NAME, part_name, dciid,
                      proj.description)]
        self.assertEqual(
            expected_calls,
            self.dfa_server.dcnm_client.create_project.call_args_list)

    def test_project_update_event(self):
        """Test case for project update event."""

        proj_info = {'resource_info': FAKE_PROJECT_ID}
        proj = mock.Mock()
        proj.name = FAKE_PROJECT_NAME + ':dci_id:' + self.dciid
        proj.description = self.proj_desc
        self.dfa_server.keystone_event._service.projects.get.return_value = (
            proj)

        self.dfa_server.project_update_event(proj_info)
        # Project update event is called with the same parameters. It is
        # expected that there is no call to update_project.
        self.assertFalse(
            self.dfa_server.dcnm_client.update_project.called)

        # Try with updating the project by name.
        proj.name = FAKE_PROJECT_NAME + 'new' + ':dci_id:' + self.dciid
        self.dfa_server.project_update_event(proj_info)
        self.assertFalse(
            self.dfa_server.dcnm_client.update_project.called)

        # Try with updating the dci_id of the project.
        proj.name = FAKE_PROJECT_NAME + ':dci_id:' + str(124)
        self.dfa_server.project_update_event(proj_info)
        self.assertTrue(
            self.dfa_server.dcnm_client.update_project.called)
        expected_calls = [mock.call(FAKE_PROJECT_NAME,
                                    self.cfg.dcnm.default_partition_name,
                                    dci_id=str(124))]
        self.assertEqual(
            expected_calls,
            self.dfa_server.dcnm_client.update_project.call_args_list)

    def test_project_delete_event(self):
        """Test case for project delete event."""

        proj_name = FAKE_PROJECT_NAME
        proj_info = {'resource_info': FAKE_PROJECT_ID}
        part_name = self.cfg.dcnm.default_partition_name

        self.dfa_server.project_delete_event(proj_info)

        # Check information sent to dcnm and api that deleting the entry from
        # DB is called.
        self.dfa_server.dcnm_client.delete_project.assert_called_with(
            proj_name, part_name)

        self.dfa_server.del_project_db.assert_called_with(FAKE_PROJECT_ID)

    def test_network_create_event(self):
        """Test case for network create event."""

        network_info = {'network':
                        {'name': FAKE_NETWORK_NAME,
                         'tenant_id': FAKE_PROJECT_ID,
                         'id': FAKE_NETWORK_ID}}
        dcnmclnt = self.dfa_server.dcnm_client
        dcnmclnt.get_config_profile_for_network.return_value = (
            FAKE_CFG_PROFILE_NAME, FAKE_FWD_MODE)
        self.dfa_server.network_create_event(network_info)
        dfa_net = self.dfa_server.network[FAKE_NETWORK_ID]
        expected_calls = [mock.call(FAKE_NETWORK_ID, dfa_net, 'openstack',
                                    constants.RESULT_SUCCESS)]
        self.assertEqual(expected_calls,
                         self.dfa_server.add_network_db.call_args_list)

    def test_subnet_create_event(self):
        """Test case for subnet create event."""

        network_info = {'network':
                        {'name': FAKE_NETWORK_NAME,
                         'tenant_id': FAKE_PROJECT_ID,
                         'id': FAKE_NETWORK_ID}}
        subnet_info = {'subnet': {
            'network_id': FAKE_NETWORK_ID,
            'tenant_id': FAKE_PROJECT_ID,
            'allocation_pools': [
                {'start': FAKE_DHCP_IP_START, 'end': FAKE_DHCP_IP_END}],
            'gateway_ip': FAKE_GW_ADDR,
            'ip_version': 4,
            'cidr': FAKE_IP_ADDR + '/24',
            'id': FAKE_SUBNET_ID}}

        dcnmclnt = self.dfa_server.dcnm_client
        dcnmclnt.get_config_profile_for_network.return_value = (
            FAKE_CFG_PROFILE_NAME, FAKE_FWD_MODE)
        self.dfa_server.network_create_event(network_info)

        fake_network = mock.Mock()
        fake_network.source = 'dcnm'
        fake_network.name = FAKE_NETWORK_NAME
        self.dfa_server.get_network.return_value = fake_network
        self.dfa_server.subnet_create_event(subnet_info)
        self.assertFalse(self.dfa_server.dcnm_client.create_network.called)

        fake_network.source = 'openstack'
        self.dfa_server.subnet_create_event(subnet_info)
        self.assertTrue(self.dfa_server.dcnm_client.create_network.called)
        create_call = self.dfa_server.dcnm_client.create_network.call_args
        arg1, arg2 = create_call
        self.assertTrue(arg1[0] == FAKE_PROJECT_NAME)
        self.assertTrue(
            arg1[1].__dict__ == self.dfa_server.network[FAKE_NETWORK_ID])
        self.assertTrue(
            arg1[2].__dict__ == self.dfa_server.subnet[FAKE_SUBNET_ID])

    def test_network_delete_event(self):
        """Test case for network delete event."""

        self._load_network_info()
        network_info = {'network_id': FAKE_NETWORK_ID}
        self.dfa_server.get_vms.return_value = []
        self.dfa_server.network_delete_event(network_info)
        self.assertTrue(self.dfa_server.dcnm_client.delete_network.called)
        dcall = self.dfa_server.dcnm_client.delete_network.call_args
        arg1, arg2 = dcall
        self.assertTrue(arg1[0] == FAKE_PROJECT_NAME)
        self.assertTrue(arg1[1].name == FAKE_NETWORK_NAME)
        self.assertTrue(arg1[1].segmentation_id == self.segid)
        self.dfa_server.seg_drvr.release_segmentation_id.assert_called_with(
            self.segid)
        self.assertTrue(self.dfa_server.delete_network_db.called)

    def test_dcnm_network_create_event(self):
        """Test case for DCNM network create event."""

        network_info = {'segmentation_id': FAKE_SEG_ID,
                        'project_name': FAKE_PROJECT_NAME,
                        'partition_name': self.part_name}
        self.dfa_server.get_network_by_segid.return_value = None
        self.dfa_server.get_project_id.return_value = FAKE_PROJECT_ID

        dcnm_network = {'segmentId': FAKE_SEG_ID,
                        'profileName': FAKE_CFG_PROFILE_NAME,
                        'networkName': FAKE_NETWORK_NAME,
                        'organizationName': FAKE_PROJECT_NAME,
                        'dhcpScope': None,
                        'netmaskLength': 24,
                        'gateway': FAKE_GW_ADDR}
        self.dfa_server.dcnm_client.get_network.return_value = dcnm_network
        dcnmclnt = self.dfa_server.dcnm_client
        dcnmclnt.config_profile_fwding_mode_get.return_value = FAKE_FWD_MODE

        self.dfa_server.dcnm_network_create_event(network_info)

        # Check the results.
        self.dfa_server.dcnm_client.get_network.assert_called_with(
            FAKE_PROJECT_NAME, FAKE_SEG_ID)
        for netid, dcnmnet in six.iteritems(self.dfa_server.network):
            self.dfa_server.add_network_db.assert_called_with(
                netid, dcnmnet, 'DCNM', constants.RESULT_SUCCESS)
        self.assertTrue(self.dfa_server.neutronclient.create_network.called)
        net_ext_name = self.cfg.dcnm.dcnm_net_ext
        call_args = self.dfa_server.neutronclient.create_network.call_args
        cargs, ckwargs = call_args
        net_name = ckwargs.get('body').get('network').get('name')
        self.assertTrue(net_name == (
            FAKE_NETWORK_NAME + net_ext_name + str(FAKE_SEG_ID)))
        self.assertTrue(self.dfa_server.neutronclient.create_subnet.called)

    def test_dcnm_network_delete_event(self):
        """Test case for DCNM network delete event."""

        self._load_network_info()
        network_info = {'segmentation_id': (
            self.dfa_server.network[FAKE_NETWORK_ID]['segmentation_id'])}

        dcnmnet = mock.Mock()
        dcnmnet.network_id = FAKE_NETWORK_ID
        self.dfa_server.get_network_by_segid.return_value = dcnmnet
        self.dfa_server.dcnm_network_delete_event(network_info)

        # Check the results.
        self.assertTrue(self.dfa_server.network == {})
        self.dfa_server.neutronclient.delete_network.assert_called_with(
            FAKE_NETWORK_ID)
        self.dfa_server.delete_network_db.assert_called_with(FAKE_NETWORK_ID)

    def test_port_create_event(self):
        """Test case for port create event."""

        port_info = self._get_port_info()
        self._load_network_info()
        self.dfa_server._inst_api.get_instance_for_uuid.return_value = (
            FAKE_INSTANCE_NAME)
        self.dfa_server.dcnm_dhcp = True
        self.dfa_server.port_create_event(port_info)

        # Check the output/calls
        self.assertTrue(self.dfa_server.neutron_event.send_vm_info.called)
        call_args = self.dfa_server.neutron_event.send_vm_info.call_args
        cargs, ckwargs = call_args
        self.assertTrue(cargs[0] == FAKE_HOST_ID)
        self.assertTrue(str(self.dfa_server.port[FAKE_PORT_ID]) == cargs[1])
        self.assertTrue(self.dfa_server.add_vms_db.called)
        call_args = self.dfa_server.add_vms_db.call_args
        cargs, ckwargs = call_args
        self.assertTrue(self.dfa_server.port[FAKE_PORT_ID] == cargs[0])
        self.assertTrue(constants.RESULT_SUCCESS == cargs[1])

    def test_port_update_event(self):
        """Test case for port update event."""

        port_info = self._get_port_info()
        mvm = mock.Mock()
        mvm.host = None
        mvm.port_id = FAKE_PORT_ID
        self.dfa_server.get_vm.return_value = mvm
        self.dfa_server._inst_api.get_instance_for_uuid.return_value = (
            FAKE_INSTANCE_NAME)
        self.dfa_server.port_update_event(port_info)

        # Check the results.
        self.dfa_server.neutron_event.send_vm_info.assert_called_with(
            port_info['port']['binding:host_id'],
            str(self.dfa_server.port[port_info['port']['id']]))
        params = dict(columns=dict(
            instance_id=FAKE_DEVICE_ID.replace('-', ''),
            host=port_info['port']['binding:host_id'],
            result=constants.RESULT_SUCCESS,
            name=FAKE_INSTANCE_NAME))
        self.dfa_server.update_vm_db.assert_called_with(
            port_info['port']['id'], **params)

    def test_port_delete_event(self):
        """Test case for port delete event."""

        vm = mock.Mock()
        vm.mac = FAKE_MAC_ADDR
        vm.port_id = FAKE_PORT_ID
        vm.segmentation_id = self.segid
        vm.network_id = FAKE_NETWORK_ID,
        vm.port_id = FAKE_PORT_ID
        vm.ip = FAKE_IP_ADDR
        vm.gw_mac = FAKE_GW_ADDR
        vm.instance_id = FAKE_DEVICE_ID
        vm.fwd_mod = FAKE_FWD_MODE
        vm.host = FAKE_HOST_ID
        vm.name = FAKE_INSTANCE_NAME
        self.dfa_server.get_vm.return_value = vm
        vm_info = dict(status='down', vm_mac=vm.mac,
                       segmentation_id=vm.segmentation_id,
                       host=vm.host, port_uuid=vm.port_id,
                       net_uuid=vm.network_id,
                       oui=dict(ip_addr=vm.ip, vm_name=vm.name,
                                vm_uuid=vm.instance_id, gw_mac=vm.gw_mac,
                                fwd_mod=vm.fwd_mod, oui_id='cisco'))
        port_info = {'port_id': FAKE_PORT_ID}

        # Check the output/calls
        self.dfa_server.port_delete_event(port_info)
        self.assertTrue(self.dfa_server.neutron_event.send_vm_info.called)
        call_args = self.dfa_server.neutron_event.send_vm_info.call_args
        cargs, ckwargs = call_args
        self.assertTrue(cargs[0] == FAKE_HOST_ID)
        self.assertTrue(str(vm_info) == cargs[1])
        self.dfa_server.delete_vm_db.assert_called_with(vm.port_id)

    def test_add_dhcp_port(self):
        """Test add dhcp port"""
        self.dfa_server.get_vm.return_value = None
        port_info = self._get_port_info().get("port")
        self._load_network_info()
        self.dfa_server._inst_api.get_instance_for_uuid.return_value = (
            FAKE_INSTANCE_NAME)
        self.dfa_server.dcnm_dhcp = False
        self.dfa_server.add_dhcp_port(port_info)

        # Check the output/calls

        self.assertTrue(self.dfa_server.neutron_event.send_vm_info.called)
        call_args = self.dfa_server.neutron_event.send_vm_info.call_args
        cargs, ckwargs = call_args
        self.assertEqual(FAKE_HOST_ID, cargs[0])
        self.assertEqual(str(self.dfa_server.port[FAKE_PORT_ID]), cargs[1])
        self.assertEqual(self.dfa_server.port[FAKE_PORT_ID]["oui"]["vm_name"],
                         "dhcp-10010-4")
        self.assertTrue(self.dfa_server.add_vms_db.called)
        call_args = self.dfa_server.add_vms_db.call_args
        cargs, ckwargs = call_args
        self.assertEqual(self.dfa_server.port[FAKE_PORT_ID], cargs[0])
        self.assertEqual(constants.RESULT_SUCCESS, cargs[1])

    def test_correct_dhcp_ports(self):
        """Test case for port delete event."""
        port_info = self._get_port_info().get("port")
        port_info["device_owner"] = "network:dhcp"
        ports_list_data = {"ports": [port_info]}
        self.dfa_server.neutronclient.list_ports.return_value = ports_list_data
        self.dfa_server.neutron_event._clients.get.return_value = True
        self.dfa_server.add_dhcp_port = mock.Mock()
        self.dfa_server.correct_dhcp_ports(FAKE_NETWORK_ID)

        self.assertTrue(self.dfa_server.add_dhcp_port.called)
        call_args = self.dfa_server.add_dhcp_port.call_args
        cargs, ckwargs = call_args
        self.assertEqual(FAKE_PORT_ID, cargs[0].get("id"))

    def test_strip_wait_dhcp(self):
        vm = mock.Mock
        vm.mac = FAKE_MAC_ADDR
        vm.port_id = FAKE_PORT_ID
        vm.segmentation_id = self.segid
        vm.network_id = FAKE_NETWORK_ID,
        vm.port_id = FAKE_PORT_ID
        vm.ip = "10.10.10.10W"
        vm.gw_mac = FAKE_GW_ADDR
        vm.instance_id = FAKE_DEVICE_ID
        vm.fwd_mod = FAKE_FWD_MODE
        vm.host = FAKE_HOST_ID
        vm.name = FAKE_INSTANCE_NAME

        self.dfa_server.strip_wait_dhcp(vm)

        self.assertTrue(self.dfa_server.update_vm_db.called)
        call_args = self.dfa_server.update_vm_db.call_args
        cargs, ckwargs = call_args
        self.assertEqual(FAKE_PORT_ID, cargs[0])
        self.assertEqual("10.10.10.10", ckwargs.get("columns").get("ip"))
