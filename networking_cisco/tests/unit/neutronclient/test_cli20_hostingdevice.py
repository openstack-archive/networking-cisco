# Copyright 2015 Cisco Systems, Inc.
# All Rights Reserved
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

import sys

import mock

from neutronclient.common import exceptions
from neutronclient import shell
from neutronclient.tests.unit import test_cli20

from networking_cisco.neutronclient import hostingdevice


class CLITestV20HostingDevice(test_cli20.CLITestV20Base):

    def setUp(self):
        # need to mock before super because extensions loaded on instantiation
        self._mock_extension_loading()
        super(CLITestV20HostingDevice, self).setUp()

    def _mock_extension_loading(self):
        ext_pkg = 'neutronclient.common.extension'
        contrib = mock.patch(ext_pkg + '._discover_via_entry_points').start()
        contrib.return_value = [("hostingdevice", hostingdevice)]
        return contrib

    def test_ext_cmd_loaded(self):
        shell.NeutronShell('2.0')
        ext_cmd = {
            'cisco-hosting-device-list': hostingdevice.HostingDeviceList,
            'cisco-hosting-device-create': hostingdevice.HostingDeviceCreate,
            'cisco-hosting-device-update': hostingdevice.HostingDeviceUpdate,
            'cisco-hosting-device-delete': hostingdevice.HostingDeviceDelete,
            'cisco-hosting-device-show': hostingdevice.HostingDeviceShow,
            'cisco-hosting-device-get-config':
                hostingdevice.HostingDeviceGetConfig}
        self.assertDictContainsSubset(ext_cmd, shell.COMMANDS['2.0'])

    def test_ext_cmd_help_doc_with_extension_name(self):
        shell.NeutronShell('2.0')
        ext_cmd = {
            'cisco-hosting-device-list': hostingdevice.HostingDeviceList,
            'cisco-hosting-device-create': hostingdevice.HostingDeviceCreate,
            'cisco-hosting-device-update': hostingdevice.HostingDeviceUpdate,
            'cisco-hosting-device-delete': hostingdevice.HostingDeviceDelete,
            'cisco-hosting-device-show': hostingdevice.HostingDeviceShow,
            'cisco-hosting-device-get-config':
                hostingdevice.HostingDeviceGetConfig}
        self.assertDictContainsSubset(ext_cmd, shell.COMMANDS['2.0'])
        for item in ext_cmd:
            cmdcls = shell.COMMANDS['2.0'].get(item)
            self.assertTrue(cmdcls.__doc__.startswith("[hostingdevice]"))

    def test_create_hosting_device(self):
        """Create hosting device."""
        resource = 'hosting_device'
        cmd = hostingdevice.HostingDeviceCreate(test_cli20.MyApp(sys.stdout),
                                                None)
        name = 'Device 1'
        template = 'Template 1'
        myid = 'myid'
        args = [name, template]
        position_names = ['name', 'template_id']
        position_values = [name, template]
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values)

    def test_create_hosting_device_id(self):
        """Create hosting device: --id this_id "Device 1" "Template 1"."""
        resource = 'hosting_device'
        cmd = hostingdevice.HostingDeviceCreate(test_cli20.MyApp(sys.stdout),
                                                None)
        name = 'Device 1'
        template = 'Template 1'
        myid = 'myid'
        args = ['--id', myid, name, template]
        position_names = ['name', 'template_id']
        position_values = [name, template]
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values,
                                   id=myid)

    def test_create_hosting_device_tenant(self):
        """Create hosting device: --tenant_id tenantid "Device 1" "Template
        1".
        """
        resource = 'hosting_device'
        cmd = hostingdevice.HostingDeviceCreate(test_cli20.MyApp(sys.stdout),
                                                None)
        name = 'Device 1'
        template = 'Template 1'
        myid = 'myid'
        args = ['--tenant_id', 'tenantid', name, template]
        position_names = ['name', 'template_id']
        position_values = [name, template]
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values,
                                   tenant_id='tenantid')

    def _test_create_hosting_device_optional_args(
            self, creds_id=None, credsid=None, desc=None, device_id=None,
            deviceid=None, mgmt_ip=None, mgmtip=None, mgmt_port=None,
            mgmtport=None, proto_port=None, protoport=None, admin_down=None,
            admindown=None, cfg_agt=None, cfgagt=None, tenant_bound=None,
            tenantbound=None, auto_delete=None, autodelete=None):
        resource = 'hosting_device'
        cmd = hostingdevice.HostingDeviceCreate(test_cli20.MyApp(sys.stdout),
                                                None)
        myid = 'myid'
        name = 'Device 1'
        template = 'Template 1'
        args = []
        expected = {}
        if creds_id is not None:
            args += ['--credentials_id', creds_id]
            expected['credentials_id'] = creds_id
        if credsid is not None:
            args += ['--credentials-id', credsid]
            expected['credentials_id'] = credsid
        if desc is not None:
            args += ['--description', desc]
            expected['description'] = desc
        if device_id is not None:
            args += ['--device_id', device_id]
            expected['device_id'] = device_id
        if deviceid is not None:
            args += ['--device-id', deviceid]
            expected['device_id'] = deviceid
        if mgmt_ip is not None:
            args += ['--management_ip_address', mgmt_ip]
            expected['management_ip_address'] = mgmt_ip
        if mgmtip is not None:
            args += ['--management-ip-address', mgmtip]
            expected['management_ip_address'] = mgmtip
        if mgmt_port is not None:
            args += ['--management_port', mgmt_port]
            expected['management_port_id'] = mgmt_port
        if mgmtport is not None:
            args += ['--management-port', mgmtport]
            expected['management_port_id'] = mgmtport
        if proto_port is not None:
            args += ['--protocol_port', proto_port]
            expected['protocol_port'] = proto_port
        if protoport is not None:
            args += ['--protocol-port', protoport]
            expected['protocol_port'] = protoport
        if admin_down is not None:
            args += ['--admin_state_down']
            expected['admin_state_up'] = False
        if admindown is not None:
            args += ['--admin-state-down']
            expected['admin_state_up'] = False
        if cfg_agt is not None:
            args += ['--cfg_agent_id', cfg_agt]
            expected['cfg_agent_id'] = cfg_agt
        if cfgagt is not None:
            args += ['--cfg-agent-id', cfgagt]
            expected['cfg_agent_id'] = cfgagt
        if tenant_bound is not None:
            args += ['--tenant_bound', tenant_bound]
            expected['tenant_bound'] = (tenant_bound
                                        if tenant_bound != "None" else None)
        if tenantbound is not None:
            args += ['--tenant-bound', tenantbound]
            expected['tenant_bound'] = (tenantbound
                                        if tenantbound != "None" else None)
        if auto_delete is not None:
            args += ['--auto_delete']
            expected['auto_delete'] = True
        if autodelete is not None:
            args += ['--auto-delete']
            expected['auto_delete'] = True
        position_names = ['name', 'template_id']
        position_values = [name, template]
        for p_v in position_values:
            args.append(p_v)
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values,
                                   **expected)

    def test_create_hosting_device_creds(self):
        self._test_create_hosting_device_optional_args(creds_id='some id')
        self._test_create_hosting_device_optional_args(credsid='some id')

    def test_create_hosting_device_description(self):
        self._test_create_hosting_device_optional_args(desc='some description')

    def test_create_hosting_device_device_id(self):
        self._test_create_hosting_device_optional_args(device_id='ABC123abc')
        self._test_create_hosting_device_optional_args(deviceid='ABC123abc')

    def test_create_hosting_device_mgmt_ip(self):
        self._test_create_hosting_device_optional_args(mgmt_ip='192.168.0.1')
        self._test_create_hosting_device_optional_args(mgmtip='192.168.0.1')

    def test_create_hosting_device_mgmt_port(self):
        self._test_create_hosting_device_optional_args(mgmt_port='a_port_id')
        self._test_create_hosting_device_optional_args(mgmtport='a_port_id')

    def test_create_hosting_device_proto_port(self):
        self._test_create_hosting_device_optional_args(proto_port='22')
        self._test_create_hosting_device_optional_args(protoport='22')

    def test_create_hosting_device_admin_down(self):
        self._test_create_hosting_device_optional_args(admin_down=True)
        self._test_create_hosting_device_optional_args(admindown=True)

    def test_create_hosting_device_cfg_agent(self):
        self._test_create_hosting_device_optional_args(cfg_agt='agent_1_id')
        self._test_create_hosting_device_optional_args(cfgagt='agent_1_id')

    def test_create_hosting_device_tenant_bound(self):
        self._test_create_hosting_device_optional_args(tenant_bound='None')
        self._test_create_hosting_device_optional_args(tenantbound='None')
        self._test_create_hosting_device_optional_args(tenant_bound='')
        self._test_create_hosting_device_optional_args(tenantbound='')
        self._test_create_hosting_device_optional_args(tenant_bound='some id')
        self._test_create_hosting_device_optional_args(tenantbound='some id')

    def test_create_hosting_device_auto_delete(self):
        self._test_create_hosting_device_optional_args(auto_delete=True)
        self._test_create_hosting_device_optional_args(autodelete=True)

    def test_create_hosting_device_full(self):
        self._test_create_hosting_device_optional_args(
            creds_id='some id', desc='some description', device_id='ABC123abc',
            mgmt_ip='192.168.0.1', mgmt_port='a_port_id', proto_port='22',
            admin_down=True, cfg_agt='agent_1_id', tenant_bound='None',
            auto_delete=True)
        self._test_create_hosting_device_optional_args(
            credsid='some id', desc='some description', deviceid='ABC123abc',
            mgmtip='192.168.0.1', mgmtport='a_port_id', protoport='22',
            admindown=True, cfgagt='agent_1_id', tenantbound='None',
            autodelete=True)

    def test_list_hosting_devices_detail(self):
        """list hosting devices: -D."""
        resources = "hosting_devices"
        cmd = hostingdevice.HostingDeviceList(test_cli20.MyApp(sys.stdout),
                                              None)
        response_contents = [{
            self.id_field: 'myid1', 'name': 'hosting_device_1_name',
            'description': 'fast router device', 'template_id': 'templ_id_1',
            'admin_state_up': True, 'status': 'ACTIVE'}, {
            self.id_field: 'myid2', 'name': 'hosting_device_2_name',
            'description': 'faster router device', 'template_id': 'templ_id_2',
            'admin_state_up': True, 'status': 'ACTIVE'}]
        self._test_list_resources(resources, cmd, True,
                                  response_contents=response_contents)

    def test_list_hosting_devices_sort(self):
        """list hosting devices: --sort-key name --sort-key id --sort-key asc
        --sort-key desc
        """
        resources = "hosting_devices"
        cmd = hostingdevice.HostingDeviceList(test_cli20.MyApp(sys.stdout),
                                              None)
        response_contents = [{
            self.id_field: 'myid1', 'name': 'hosting_device_1_name',
            'description': 'fast router device', 'template_id': 'templ_id_1',
            'admin_state_up': True, 'status': 'ACTIVE'}, {
            self.id_field: 'myid2', 'name': 'hosting_device_2_name',
            'description': 'faster router device', 'template_id': 'templ_id_2',
            'admin_state_up': True, 'status': 'ACTIVE'}]
        self._test_list_resources(resources, cmd,
                                  sort_key=["name", "id"],
                                  sort_dir=["asc", "desc"],
                                  response_contents=response_contents)

    def test_list_hosting_devices_limit(self):
        """list hosting devices: -P."""
        resources = "hosting_devices"
        cmd = hostingdevice.HostingDeviceList(test_cli20.MyApp(sys.stdout),
                                              None)
        response_contents = [{
            self.id_field: 'myid1', 'name': 'hosting_device_1_name',
            'description': 'fast router device', 'template_id': 'templ_id_1',
            'admin_state_up': True, 'status': 'ACTIVE'}, {
            self.id_field: 'myid2', 'name': 'hosting_device_2_name',
            'description': 'faster router device', 'template_id': 'templ_id_2',
            'admin_state_up': True, 'status': 'ACTIVE'}]
        self._test_list_resources(resources, cmd, page_size=1000,
                                  response_contents=response_contents)

    def test_update_hosting_device_exception(self):
        """Update hosting device: myid."""
        resource = 'hosting_device'
        cmd = hostingdevice.HostingDeviceUpdate(test_cli20.MyApp(sys.stdout),
                                                None)
        self.assertRaises(exceptions.CommandError, self._test_update_resource,
                          resource, cmd, 'myid', ['myid'], {})

    def _test_update_hosting_device(
            self, creds_id=None, credsid=None, name=None, desc=None,
            device_id=None, deviceid=None, mgmt_ip=None, mgmtip=None,
            proto_port=None, protoport=None, admin_up=None, adminup=None,
            admin_down=None, admindown=None, tenant_bound=None,
            tenantbound=None, auto_delete=None, autodelete=None,
            no_auto_delete=None, noautodelete=None):
        resource = 'hosting_device'
        cmd = hostingdevice.HostingDeviceUpdate(test_cli20.MyApp(sys.stdout),
                                                None)
        myid = 'myid'
        args = [myid]
        expected = {}
        if creds_id is not None:
            args += ['--credentials_id', creds_id]
            expected['credentials_id'] = creds_id
        if credsid is not None:
            args += ['--credentials-id', credsid]
            expected['credentials_id'] = credsid
        if name is not None:
            args += ['--name', name]
            expected['name'] = name
        if desc is not None:
            args += ['--description', desc]
            expected['description'] = desc
        if device_id is not None:
            args += ['--device_id', device_id]
            expected['device_id'] = device_id
        if deviceid is not None:
            args += ['--device-id', deviceid]
            expected['device_id'] = deviceid
        if mgmt_ip is not None:
            args += ['--management_ip_address', mgmt_ip]
            expected['management_ip_address'] = mgmt_ip
        if mgmtip is not None:
            args += ['--management-ip-address', mgmtip]
            expected['management_ip_address'] = mgmtip
        if proto_port is not None:
            args += ['--protocol_port', proto_port]
            expected['protocol_port'] = proto_port
        if protoport is not None:
            args += ['--protocol-port', protoport]
            expected['protocol_port'] = protoport
        if admin_up is not None:
            args += ['--admin_state_up']
            expected['admin_state_up'] = True
        if adminup is not None:
            args += ['--admin-state-up']
            expected['admin_state_up'] = True
        if admin_down is not None:
            args += ['--admin_state_down']
            expected['admin_state_up'] = False
        if admindown is not None:
            args += ['--admin-state-down']
            expected['admin_state_up'] = False
        if tenant_bound is not None:
            args += ['--tenant_bound', tenant_bound]
            expected['tenant_bound'] = (tenant_bound
                                        if tenant_bound != "None" else None)
        if tenantbound is not None:
            args += ['--tenant-bound', tenantbound]
            expected['tenant_bound'] = (tenantbound
                                        if tenantbound != "None" else None)
        if auto_delete is not None:
            args += ['--auto_delete']
            expected['auto_delete'] = True
        if autodelete is not None:
            args += ['--auto-delete']
            expected['auto_delete'] = True
        if no_auto_delete is not None:
            args += ['--no_auto_delete']
            expected['auto_delete'] = False
        if noautodelete is not None:
            args += ['--no-auto-delete']
            expected['auto_delete'] = False
        self._test_update_resource(resource, cmd, myid, args, expected)

    def test_update_hosting_device_creds(self):
        self._test_update_hosting_device(creds_id='some id')
        self._test_update_hosting_device(credsid='some id')

    def test_update_hosting_device_name(self):
        """Update hosting device: myid --name myname."""
        self._test_update_hosting_device(name='myname')

    def test_update_hosting_device_description(self):
        self._test_update_hosting_device(desc='some description')

    def test_update_hosting_device_device_id(self):
        self._test_update_hosting_device(device_id='ABC123abc')
        self._test_update_hosting_device(deviceid='ABC123abc')

    def test_update_hosting_device_mgmt_ip(self):
        self._test_update_hosting_device(mgmt_ip='192.168.0.1')
        self._test_update_hosting_device(mgmtip='192.168.0.1')

    def test_update_hosting_device_proto_port(self):
        self._test_update_hosting_device(proto_port='22')
        self._test_update_hosting_device(protoport='22')

    def test_update_hosting_device_admin_state(self):
        self._test_update_hosting_device(admin_up=True)
        self._test_update_hosting_device(adminup=True)
        self._test_update_hosting_device(admin_down=True)
        self._test_update_hosting_device(admindown=True)

    def test_update_hosting_device_tenant_bound(self):
        self._test_update_hosting_device(tenant_bound='None')
        self._test_update_hosting_device(tenantbound='None')
        self._test_update_hosting_device(tenant_bound='')
        self._test_update_hosting_device(tenantbound='')
        self._test_update_hosting_device(tenant_bound='some id')
        self._test_update_hosting_device(tenantbound='some id')

    def test_update_hosting_device_auto_delete(self):
        self._test_update_hosting_device(no_auto_delete=True)
        self._test_update_hosting_device(noautodelete=True)
        self._test_update_hosting_device(auto_delete=True)
        self._test_update_hosting_device(autodelete=True)

    def test_delete_hosting_device(self):
        """Delete hosting device: myid."""
        resource = 'hosting_device'
        cmd = hostingdevice.HostingDeviceDelete(test_cli20.MyApp(sys.stdout),
                                                None)
        myid = 'myid'
        args = [myid]
        self._test_delete_resource(resource, cmd, myid, args)

    def test_show_hosting_device(self):
        """Show hosting device: myid."""
        resource = 'hosting_device'
        cmd = hostingdevice.HostingDeviceShow(test_cli20.MyApp(sys.stdout),
                                              None)
        args = ['--fields', 'id', '--fields', 'name', self.test_id]
        self._test_show_resource(resource, cmd, self.test_id, args,
                                 ['id', 'name'])

    def test_get_hosting_device_config(self):
        """Get config of hosting device: myid."""
        resource = 'hosting_device'
        cmd = hostingdevice.HostingDeviceGetConfig(
            test_cli20.MyApp(sys.stdout), None)
        args = [self.test_id]
        attr = resource + "_path"
        p = getattr(self.client, attr)
        setattr(self.client, attr, p + hostingdevice.HOSTING_DEVICE_CONFIG)
        self._test_show_resource(resource, cmd, self.test_id, args)
