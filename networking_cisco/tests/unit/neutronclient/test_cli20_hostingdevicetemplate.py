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

from neutronclient import shell
from neutronclient.tests.unit import test_cli20

from networking_cisco.neutronclient import hostingdevicetemplate


class CLITestV20HostingDeviceTemplate(test_cli20.CLITestV20Base):

    def setUp(self):
        # need to mock before super because extensions loaded on instantiation
        self._mock_extension_loading()
        super(CLITestV20HostingDeviceTemplate, self).setUp()
        self.non_admin_status_resources.append('hosting_device_template')

    def _mock_extension_loading(self):
        ext_pkg = 'neutronclient.common.extension'
        contrib = mock.patch(ext_pkg + '._discover_via_entry_points').start()
        contrib.return_value = [("hostingdevicetemplate",
                                 hostingdevicetemplate)]
        return contrib

    def test_ext_cmd_loaded(self):
        shell.NeutronShell('2.0')
        ext_cmd = {
            'cisco-hosting-device-template-list':
                hostingdevicetemplate.HostingDeviceTemplateList,
            'cisco-hosting-device-template-create':
                hostingdevicetemplate.HostingDeviceTemplateCreate,
            'cisco-hosting-device-template-update':
                hostingdevicetemplate.HostingDeviceTemplateUpdate,
            'cisco-hosting-device-template-delete':
                hostingdevicetemplate.HostingDeviceTemplateDelete,
            'cisco-hosting-device-template-show':
                hostingdevicetemplate.HostingDeviceTemplateShow}
        self.assertDictContainsSubset(ext_cmd, shell.COMMANDS['2.0'])

    def test_ext_cmd_help_doc_with_extension_name(self):
        shell.NeutronShell('2.0')
        ext_cmd = {
            'cisco-hosting-device-template-list':
                hostingdevicetemplate.HostingDeviceTemplateList,
            'cisco-hosting-device-template-create':
                hostingdevicetemplate.HostingDeviceTemplateCreate,
            'cisco-hosting-device-template-update':
                hostingdevicetemplate.HostingDeviceTemplateUpdate,
            'cisco-hosting-device-template-delete':
                hostingdevicetemplate.HostingDeviceTemplateDelete,
            'cisco-hosting-device-template-show':
                hostingdevicetemplate.HostingDeviceTemplateShow}
        self.assertDictContainsSubset(ext_cmd, shell.COMMANDS['2.0'])
        for item in ext_cmd:
            cmdcls = shell.COMMANDS['2.0'].get(item)
            self.assertTrue(cmdcls.__doc__.startswith(
                "[hostingdevicetemplate]"))

    def test_create_hosting_device_template(self):
        """Create hosting device template."""
        resource = 'hosting_device_template'
        cmd = hostingdevicetemplate.HostingDeviceTemplateCreate(
            test_cli20.MyApp(sys.stdout), None)
        name = 'Device template 1'
        host_category = 'Hardware'
        myid = 'myid'
        args = [name, host_category]
        position_names = ['name', 'host_category']
        position_values = [name, host_category]
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values)

    def test_create_hosting_device_template_id(self):
        """Create hosting device template: --id this_id "Device 1" "Template
        1".
        """
        resource = 'hosting_device_template'
        cmd = hostingdevicetemplate.HostingDeviceTemplateCreate(
            test_cli20.MyApp(sys.stdout), None)
        name = 'Device template 1'
        host_category = 'Hardware'
        myid = 'myid'
        args = ['--id', myid, name, host_category]
        position_names = ['name', 'host_category']
        position_values = [name, host_category]
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values,
                                   id=myid)

    def test_create_hosting_device_template_tenant(self):
        """Create hosting device template: --tenant_id tenantid "Device 1"
        "Template 1".
        """
        resource = 'hosting_device_template'
        cmd = hostingdevicetemplate.HostingDeviceTemplateCreate(
            test_cli20.MyApp(sys.stdout), None)
        name = 'Device template 1'
        host_category = 'Hardware'
        myid = 'myid'
        args = ['--tenant_id', 'tenantid', name, host_category]
        position_names = ['name', 'host_category']
        position_values = [name, host_category]
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values,
                                   tenant_id='tenantid')

    def _test_create_hosting_device_template_optional_args(
            self, disabled=None, service_types=None, servicetypes=None,
            image=None, flavor=None, creds_id=None, credsid=None,
            conf_mech=None, confmech=None, proto_port=None, protoport=None,
            boot_time=None, boottime=None, slot_capacity=None,
            slotcapacity=None, slots_free=None, slotsfree=None,
            tenant_bound=None, tenantbound=None, dev_drv=None, devdrv=None,
            plug_drv=None, plugdrv=None):
        resource = 'hosting_device_template'
        cmd = hostingdevicetemplate.HostingDeviceTemplateCreate(
            test_cli20.MyApp(sys.stdout), None)
        myid = 'myid'
        name = 'Device template 1'
        host_category = 'Hardware'
        args = []
        expected = {}
        if disabled is not None:
            args += ['--disabled']
            expected['enabled'] = False
        if service_types is not None:
            args += ['--service_types', service_types]
            expected['service_types'] = service_types
        if servicetypes is not None:
            args += ['--service-types', servicetypes]
            expected['service_types'] = servicetypes
        if image is not None:
            args += ['--image', image]
            expected['image'] = image
        if flavor is not None:
            args += ['--flavor', flavor]
            expected['flavor'] = flavor
        if creds_id is not None:
            args += ['--credentials_id', creds_id]
            expected['default_credentials_id'] = creds_id
        if credsid is not None:
            args += ['--credentials-id', credsid]
            expected['default_credentials_id'] = credsid
        if conf_mech is not None:
            args += ['--config_mechanism', conf_mech]
            expected['configuration_mechanism'] = conf_mech
        if confmech is not None:
            args += ['--config-mechanism', confmech]
            expected['configuration_mechanism'] = confmech
        if proto_port is not None:
            args += ['--protocol_port', proto_port]
            expected['protocol_port'] = proto_port
        if protoport is not None:
            args += ['--protocol-port', protoport]
            expected['protocol_port'] = protoport
        if boot_time is not None:
            args += ['--booting_time', boot_time]
            expected['booting_time'] = boot_time
        if boottime is not None:
            args += ['--booting-time', boottime]
            expected['booting_time'] = boottime
        if slot_capacity is not None:
            args += ['--slot_capacity', slot_capacity]
            expected['slot_capacity'] = slot_capacity
        if slotcapacity is not None:
            args += ['--slot-capacity', slotcapacity]
            expected['slot_capacity'] = slotcapacity
        if slots_free is not None:
            args += ['--desired_slots_free', slots_free]
            expected['desired_slots_free'] = slots_free
        if slotsfree is not None:
            args += ['--desired-slots-free', slotsfree]
            expected['desired_slots_free'] = slotsfree
        if dev_drv is not None:
            args += ['--device_driver', dev_drv]
            expected['device_driver'] = dev_drv
        if devdrv is not None:
            args += ['--device-driver', devdrv]
            expected['device_driver'] = devdrv
        if plug_drv is not None:
            args += ['--plugging_driver', plug_drv]
            expected['plugging_driver'] = plug_drv
        if plugdrv is not None:
            args += ['--plugging-driver', plugdrv]
            expected['plugging_driver'] = plugdrv
        if tenant_bound is not None:
            args += ['--tenant_bound', tenant_bound]
            expected['tenant_bound'] = (tenant_bound
                                        if tenant_bound != "None" else None)
        if tenantbound is not None:
            args += ['--tenant-bound', tenantbound]
            expected['tenant_bound'] = (tenantbound
                                        if tenantbound != "None" else None)
        position_names = ['name', 'host_category']
        position_values = [name, host_category]
        for p_v in position_values:
            args.append(p_v)
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values,
                                   **expected)

    def test_create_hosting_device_template_disabled(self):
        self._test_create_hosting_device_template_optional_args(disabled=True)

    def test_create_hosting_device_template_service_types(self):
        self._test_create_hosting_device_template_optional_args(
            service_types="L3,FW")
        self._test_create_hosting_device_template_optional_args(
            servicetypes="L3,FW")

    def test_create_hosting_device_template_image(self):
        self._test_create_hosting_device_template_optional_args(
            image="some_glance_image")

    def test_create_hosting_device_template_flavor(self):
        self._test_create_hosting_device_template_optional_args(
            flavor="some_nova_flavor")

    def test_create_hosting_device_template_creds(self):
        self._test_create_hosting_device_template_optional_args(
            creds_id='some id')
        self._test_create_hosting_device_template_optional_args(
            credsid='some id')

    def test_create_hosting_device_template_conf_mech(self):
        self._test_create_hosting_device_template_optional_args(
            conf_mech='netconf')
        self._test_create_hosting_device_template_optional_args(
            conf_mech='netconf')

    def test_create_hosting_device_template_proto_port(self):
        self._test_create_hosting_device_template_optional_args(
            proto_port='22')
        self._test_create_hosting_device_template_optional_args(
            protoport='22')

    def test_create_hosting_device_template_boot_time(self):
        self._test_create_hosting_device_template_optional_args(
            boot_time='3000')
        self._test_create_hosting_device_template_optional_args(
            boottime='3000')

    def test_create_hosting_device_template_slot_capacity(self):
        self._test_create_hosting_device_template_optional_args(
            slot_capacity='10000')
        self._test_create_hosting_device_template_optional_args(
            slotcapacity='10000')

    def test_create_hosting_device_template_desired_slots_free(self):
        self._test_create_hosting_device_template_optional_args(
            slots_free='200')
        self._test_create_hosting_device_template_optional_args(
            slotsfree='200')

    def test_create_hosting_device_template_tenant_bound(self):
        self._test_create_hosting_device_template_optional_args(
            tenant_bound='None')
        self._test_create_hosting_device_template_optional_args(
            tenantbound='None')
        self._test_create_hosting_device_template_optional_args(
            tenant_bound='')
        self._test_create_hosting_device_template_optional_args(
            tenantbound='')
        self._test_create_hosting_device_template_optional_args(
            tenant_bound='some id')
        self._test_create_hosting_device_template_optional_args(
            tenantbound='some id')

    def test_create_hosting_device_template_device_driver(self):
        self._test_create_hosting_device_template_optional_args(
            dev_drv='my.device.driver:class_name')
        self._test_create_hosting_device_template_optional_args(
            devdrv='my.device.driver:class_name')

    def test_create_hosting_device_template_plugging_driver(self):
        self._test_create_hosting_device_template_optional_args(
            plug_drv='my.plugging.driver:class_name')
        self._test_create_hosting_device_template_optional_args(
            plugdrv='my.plugging.driver:class_name')

    def test_create_hosting_device_template_full(self):
        self._test_create_hosting_device_template_optional_args(
            disabled=True, service_types="L3,FW", image="some_glance_image",
            flavor="some_nova_flavor", creds_id="some id",
            conf_mech="netconf", proto_port="22", boot_time="3000",
            slot_capacity="20000", slots_free="150", tenant_bound="None",
            dev_drv='my.device.driver:class_name',
            plug_drv='my.plugging.driver:class_name')
        self._test_create_hosting_device_template_optional_args(
            disabled=True, servicetypes="L3,FW", image="some_glance_image",
            flavor="some_nova_flavor", credsid="some id",
            conf_mech="netconf", proto_port="22", boottime="3000",
            slotcapacity="20000", slotsfree="150", tenantbound="None",
            devdrv='my.device.driver:class_name',
            plugdrv='my.plugging.driver:class_name')

    def test_list_hosting_device_templates_detail(self):
        """list hosting device templates: -D."""
        resources = "hosting_device_templates"
        cmd = hostingdevicetemplate.HostingDeviceTemplateList(
            test_cli20.MyApp(sys.stdout), None)
        response_contents = [{
            self.id_field: 'myid1', 'name': 'device_template_1_name',
            'host_category': 'VM', 'service_types': "L3,FW",
            'image': 'some_glance_image_1', 'enabled': True}, {
            self.id_field: 'myid2', 'name': 'device_template_2_name',
            'host_category': 'VM', 'service_types': "L3,FW",
            'image': 'some_glance_image_2', 'enabled': True}]
        self._test_list_resources(resources, cmd, True,
                                  response_contents=response_contents)

    def test_list_hosting_device_templates_sort(self):
        """list hosting device templates: --sort-key name --sort-key id
        --sort-key asc
        --sort-key desc
        """
        resources = "hosting_device_templates"
        cmd = hostingdevicetemplate.HostingDeviceTemplateList(
            test_cli20.MyApp(sys.stdout), None)
        response_contents = [{
            self.id_field: 'myid1', 'name': 'device_template_1_name',
            'host_category': 'VM', 'service_types': "L3,FW",
            'image': 'some_glance_image_1', 'enabled': True}, {
            self.id_field: 'myid2', 'name': 'device_template_2_name',
            'host_category': 'VM', 'service_types': "L3,FW",
            'image': 'some_glance_image_2', 'enabled': True}]
        self._test_list_resources(resources, cmd,
                                  sort_key=["name", "id"],
                                  sort_dir=["asc", "desc"],
                                  response_contents=response_contents)

    def test_list_hosting_device_templates_limit(self):
        """list hosting device templates: -P."""
        resources = "hosting_device_templates"
        cmd = hostingdevicetemplate.HostingDeviceTemplateList(
            test_cli20.MyApp(sys.stdout), None)
        response_contents = [{
            self.id_field: 'myid1', 'name': 'device_template_1_name',
            'host_category': 'VM', 'service_types': "L3,FW",
            'image': 'some_glance_image_1', 'enabled': True}, {
            self.id_field: 'myid2', 'name': 'device_template_2_name',
            'host_category': 'VM', 'service_types': "L3,FW",
            'image': 'some_glance_image_2', 'enabled': True}]
        self._test_list_resources(resources, cmd, page_size=1000,
                                  response_contents=response_contents)

    def _test_update_hosting_device_template(
            self, name=None, disabled=None, service_types=None,
            servicetypes=None, image=None, flavor=None, creds_id=None,
            credsid=None, conf_mech=None, confmech=None, proto_port=None,
            protoport=None, boot_time=None, boottime=None, tenant_bound=None,
            tenantbound=None):
        resource = 'hosting_device_template'
        cmd = hostingdevicetemplate.HostingDeviceTemplateUpdate(
            test_cli20.MyApp(sys.stdout), None)
        myid = 'myid'
        args = [myid]
        expected = {}
        if name is not None:
            args += ['--name', name]
            expected['name'] = name
        if disabled is not None:
            args += ['--disabled']
            expected['enabled'] = False
        if service_types is not None:
            args += ['--service_types', service_types]
            expected['service_types'] = service_types
        if servicetypes is not None:
            args += ['--service-types', servicetypes]
            expected['service_types'] = servicetypes
        if image is not None:
            args += ['--image', image]
            expected['image'] = image
        if flavor is not None:
            args += ['--flavor', flavor]
            expected['flavor'] = flavor
        if creds_id is not None:
            args += ['--credentials_id', creds_id]
            expected['default_credentials_id'] = creds_id
        if credsid is not None:
            args += ['--credentials-id', credsid]
            expected['default_credentials_id'] = credsid
        if conf_mech is not None:
            args += ['--config_mechanism', conf_mech]
            expected['configuration_mechanism'] = conf_mech
        if confmech is not None:
            args += ['--config-mechanism', confmech]
            expected['configuration_mechanism'] = confmech
        if proto_port is not None:
            args += ['--protocol_port', proto_port]
            expected['protocol_port'] = proto_port
        if protoport is not None:
            args += ['--protocol-port', protoport]
            expected['protocol_port'] = protoport
        if boot_time is not None:
            args += ['--booting_time', boot_time]
            expected['booting_time'] = boot_time
        if boottime is not None:
            args += ['--booting-time', boottime]
            expected['booting_time'] = boottime
        if tenant_bound is not None:
            args += ['--tenant_bound', tenant_bound]
            expected['tenant_bound'] = (tenant_bound
                                        if tenant_bound != "None" else None)
        if tenantbound is not None:
            args += ['--tenant-bound', tenantbound]
            expected['tenant_bound'] = (tenantbound
                                        if tenantbound != "None" else None)
        self._test_update_resource(resource, cmd, myid, args, expected)

    def test_update_hosting_device_template_disabled(self):
        self._test_update_hosting_device_template(disabled=True)

    def test_update_hosting_device_template_service_types(self):
        self._test_update_hosting_device_template(service_types="L3,FW")
        self._test_update_hosting_device_template(servicetypes="L3,FW")

    def test_update_hosting_device_template_image(self):
        self._test_update_hosting_device_template(image="some_glance_image")

    def test_update_hosting_device_template_flavor(self):
        self._test_update_hosting_device_template(flavor="some_nova_flavor")

    def test_update_hosting_device_template_creds(self):
        self._test_update_hosting_device_template(creds_id='some id')
        self._test_update_hosting_device_template(credsid='some id')

    def test_update_hosting_device_template_conf_mech(self):
        self._test_update_hosting_device_template(conf_mech='netconf')
        self._test_update_hosting_device_template(conf_mech='netconf')

    def test_update_hosting_device_template_proto_port(self):
        self._test_update_hosting_device_template(proto_port='22')
        self._test_update_hosting_device_template(protoport='22')

    def test_update_hosting_device_template_boot_time(self):
        self._test_update_hosting_device_template(boot_time='3000')
        self._test_update_hosting_device_template(boottime='3000')

    def test_update_hosting_device_template_tenant_bound(self):
        self._test_update_hosting_device_template(tenant_bound='None')
        self._test_update_hosting_device_template(tenantbound='None')
        self._test_update_hosting_device_template(tenant_bound='')
        self._test_update_hosting_device_template(tenantbound='')
        self._test_update_hosting_device_template(tenant_bound='some id')
        self._test_update_hosting_device_template(tenantbound='some id')

    def test_update_hosting_device_template_full(self):
        self._test_update_hosting_device_template(
            disabled=True, service_types="L3,FW", image="some_glance_image",
            flavor="some_nova_flavor", creds_id="some id",
            conf_mech="netconf", proto_port="22", boot_time="3000",
            tenant_bound="None")
        self._test_update_hosting_device_template(
            disabled=True, servicetypes="L3,FW", image="some_glance_image",
            flavor="some_nova_flavor", credsid="some id",
            conf_mech="netconf", proto_port="22", boottime="3000",
            tenantbound="None")

    def test_delete_hosting_device_template(self):
        """Delete hosting device template: myid."""
        resource = 'hosting_device_template'
        cmd = hostingdevicetemplate.HostingDeviceTemplateDelete(
            test_cli20.MyApp(sys.stdout), None)
        myid = 'myid'
        args = [myid]
        self._test_delete_resource(resource, cmd, myid, args)

    def test_show_hosting_device_template(self):
        """Show hosting device template: myid."""
        resource = 'hosting_device_template'
        cmd = hostingdevicetemplate.HostingDeviceTemplateShow(
            test_cli20.MyApp(sys.stdout), None)
        args = ['--fields', 'id', '--fields', 'name', self.test_id]
        self._test_show_resource(resource, cmd, self.test_id, args,
                                 ['id', 'name'])
