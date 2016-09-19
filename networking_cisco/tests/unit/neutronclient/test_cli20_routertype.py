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

from networking_cisco.neutronclient import routertype


class CLITestV20RouterType(test_cli20.CLITestV20Base):

    def setUp(self):
        # need to mock before super because extensions loaded on instantiation
        self._mock_extension_loading()
        super(CLITestV20RouterType, self).setUp()
        self.non_admin_status_resources.append('routertype')

    def _mock_extension_loading(self):
        ext_pkg = 'neutronclient.common.extension'
        contrib = mock.patch(ext_pkg + '._discover_via_entry_points').start()
        contrib.return_value = [("routertype", routertype)]
        return contrib

    def test_ext_cmd_loaded(self):
        shell.NeutronShell('2.0')
        ext_cmd = {'cisco-router-type-list': routertype.RouterTypeList,
                   'cisco-router-type-create': routertype.RouterTypeCreate,
                   'cisco-router-type-update': routertype.RouterTypeUpdate,
                   'cisco-router-type-delete': routertype.RouterTypeDelete,
                   'cisco-router-type-show': routertype.RouterTypeShow}
        self.assertDictContainsSubset(ext_cmd, shell.COMMANDS['2.0'])

    def test_ext_cmd_help_doc_with_extension_name(self):
        shell.NeutronShell('2.0')
        ext_cmd = {'cisco-router-type-list': routertype.RouterTypeList,
                   'cisco-router-type-create': routertype.RouterTypeCreate,
                   'cisco-router-type-update': routertype.RouterTypeUpdate,
                   'cisco-router-type-delete': routertype.RouterTypeDelete,
                   'cisco-router-type-show': routertype.RouterTypeShow}
        self.assertDictContainsSubset(ext_cmd, shell.COMMANDS['2.0'])
        for item in ext_cmd:
            cmdcls = shell.COMMANDS['2.0'].get(item)
            self.assertTrue(cmdcls.__doc__.startswith("[routertype]"))

    def test_create_router_type(self):
        """Create router type."""
        resource = 'routertype'
        cmd = routertype.RouterTypeCreate(test_cli20.MyApp(sys.stdout), None)
        template = 'Template 1'
        scheduler = 'my.scheduler:class_name'
        plugin_driver = 'my.plugin.driver:class_name'
        svc_helper = 'my.service.helper:class_name'
        agent_driver = 'my.agent.driver:class_name'
        myid = 'myid'
        args = [template, scheduler, plugin_driver, svc_helper, agent_driver]
        position_names = ['template_id', 'scheduler', 'driver',
                          'cfg_agent_service_helper', 'cfg_agent_driver']
        position_values = [template, scheduler, plugin_driver, svc_helper,
                           agent_driver]
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values)

    def test_create_router_type_id(self):
        """Create router type: --id this_id myname."""
        resource = 'routertype'
        cmd = routertype.RouterTypeCreate(test_cli20.MyApp(sys.stdout), None)
        template = 'Template 1'
        scheduler = 'my.scheduler:class_name'
        plugin_driver = 'my.plugin.driver:class_name'
        svc_helper = 'my.service.helper:class_name'
        agent_driver = 'my.agent.driver:class_name'
        myid = 'myid'
        args = ['--id', myid, template, scheduler, plugin_driver,
                svc_helper, agent_driver]
        position_names = ['template_id', 'scheduler', 'driver',
                          'cfg_agent_service_helper', 'cfg_agent_driver']
        position_values = [template, scheduler, plugin_driver, svc_helper,
                           agent_driver]
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values,
                                   id=myid)

    def test_create_router_type_tenant(self):
        """Create router type: --tenant_id tenantid myname."""
        resource = 'routertype'
        cmd = routertype.RouterTypeCreate(test_cli20.MyApp(sys.stdout), None)
        template = 'Template 1'
        scheduler = 'my.scheduler:class_name'
        plugin_driver = 'my.plugin.driver:class_name'
        svc_helper = 'my.service.helper:class_name'
        agent_driver = 'my.agent.driver:class_name'
        myid = 'myid'
        args = ['--tenant_id', 'tenantid', template, scheduler, plugin_driver,
                svc_helper, agent_driver]
        position_names = ['template_id', 'scheduler', 'driver',
                          'cfg_agent_service_helper', 'cfg_agent_driver']
        position_values = [template, scheduler, plugin_driver, svc_helper,
                           agent_driver]
        self._test_create_resource(resource, cmd, None, myid, args,
                                   position_names, position_values,
                                   tenant_id='tenantid')

    def _test_create_router_type_optional_args(
            self, name=None, desc=None, ha_enabled=None, haenabled=None,
            unshared=None, slot_need=None, slotneed=None):
        resource = 'routertype'
        cmd = routertype.RouterTypeCreate(test_cli20.MyApp(sys.stdout),
                                          None)
        myid = 'myid'
        template = 'Template 1'
        scheduler = 'my.scheduler:class_name'
        plugin_driver = 'my.plugin.driver:class_name'
        svc_helper = 'my.service.helper:class_name'
        agent_driver = 'my.agent.driver:class_name'
        args = []
        expected = {}
        if desc is not None:
            args += ['--description', desc]
            expected['description'] = desc
        if ha_enabled is not None:
            args += ['--ha_enabled']
            expected['ha_enabled_by_default'] = True
        if haenabled is not None:
            args += ['--ha-enabled']
            expected['ha_enabled_by_default'] = True
        if unshared is not None:
            args += ['--unshared']
            expected['shared'] = False
        if slot_need is not None:
            args += ['--slot_need', slot_need]
            expected['slot_need'] = slot_need
        if slotneed is not None:
            args += ['--slot-need', slotneed]
            expected['slot_need'] = slotneed
        position_names = ['template_id', 'scheduler', 'driver',
                          'cfg_agent_service_helper', 'cfg_agent_driver']
        position_values = [template, scheduler, plugin_driver, svc_helper,
                           agent_driver]
        for p_v in position_values:
            args.append(p_v)
        self._test_create_resource(resource, cmd, name, myid, args,
                                   position_names, position_values,
                                   **expected)

    def test_create_router_type_name(self):
        self._test_create_router_type_optional_args('some name')

    def test_create_router_type_description(self):
        self._test_create_router_type_optional_args(desc='some description')

    def test_create_router_type_ha(self):
        self._test_create_router_type_optional_args(ha_enabled=True)
        self._test_create_router_type_optional_args(haenabled=True)

    def test_create_router_type_unshared(self):
        self._test_create_router_type_optional_args(unshared=False)

    def test_create_router_type_slots(self):
        self._test_create_router_type_optional_args(slot_need='5')
        self._test_create_router_type_optional_args(slotneed='5')

    def test_create_router_type_full(self):
        self._test_create_router_type_optional_args(
            'some name', desc='some description', ha_enabled=True,
            unshared=False, slot_need='5')
        self._test_create_router_type_optional_args(
            'some name', desc='some description', haenabled=True,
            unshared=False, slotneed='5')

    def test_list_router_types_detail(self):
        """list routers: -D."""
        resources = "routertypes"
        cmd = routertype.RouterTypeList(test_cli20.MyApp(sys.stdout), None)
        response_contents = [{
            self.id_field: 'myid1', 'name': 'router_type_1_name',
            'description': 'fast router', 'template_id': 'templ_id_1'}, {
            self.id_field: 'myid2', 'name': 'router_type_2_name',
            'description': 'faster router', 'template_id': 'templ_id_2'}]
        self._test_list_resources(resources, cmd, True,
                                  response_contents=response_contents)

    def test_list_router_types_sort(self):
        """list routertypes: --sort-key name --sort-key id --sort-key asc
        --sort-key desc
        """
        resources = "routertypes"
        cmd = routertype.RouterTypeList(test_cli20.MyApp(sys.stdout), None)
        response_contents = [{
            self.id_field: 'myid1', 'name': 'router_type_1_name',
            'description': 'fast router', 'template_id': 'templ_id_1'}, {
            self.id_field: 'myid2', 'name': 'router_type_2_name',
            'description': 'faster router', 'template_id': 'templ_id_2'}]
        self._test_list_resources(resources, cmd,
                                  sort_key=["name", "id"],
                                  sort_dir=["asc", "desc"],
                                  response_contents=response_contents)

    def test_list_router_types_limit(self):
        """list routertypes: -P."""
        resources = "routertypes"
        cmd = routertype.RouterTypeList(test_cli20.MyApp(sys.stdout), None)
        response_contents = [{
            self.id_field: 'myid1', 'name': 'router_type_1_name',
            'description': 'fast router', 'template_id': 'templ_id_1'}, {
            self.id_field: 'myid2', 'name': 'router_type_2_name',
            'description': 'faster router', 'template_id': 'templ_id_2'}]
        self._test_list_resources(resources, cmd, page_size=1000,
                                  response_contents=response_contents)

    def test_update_router_type_exception(self):
        """Update routertype: myid."""
        resource = 'routertype'
        cmd = routertype.RouterTypeUpdate(test_cli20.MyApp(sys.stdout), None)
        self.assertRaises(exceptions.CommandError, self._test_update_resource,
                          resource, cmd, 'myid', ['myid'], {})

    def _test_update_router_type(
            self, name=None, desc=None, ha_enabled=None, haenabled=None,
            ha_disabled=None, hadisabled=None, unshared=None, shared=None,
            slot_need=None, slotneed=None):
        resource = 'routertype'
        cmd = routertype.RouterTypeUpdate(test_cli20.MyApp(sys.stdout),
                                          None)
        myid = 'myid'
        args = [myid]
        expected = {}
        if name is not None:
            args += ['--name', name]
            expected['name'] = name
        if desc is not None:
            args += ['--description', desc]
            expected['description'] = desc
        if ha_enabled is not None:
            args += ['--ha_enabled']
            expected['ha_enabled_by_default'] = True
        if haenabled is not None:
            args += ['--ha-enabled']
            expected['ha_enabled_by_default'] = True
        if ha_disabled is not None:
            args += ['--ha_disabled']
            expected['ha_enabled_by_default'] = False
        if hadisabled is not None:
            args += ['--ha-disabled']
            expected['ha_enabled_by_default'] = False
        if shared is not None:
            args += ['--shared']
            expected['shared'] = True
        if unshared is not None:
            args += ['--unshared']
            expected['shared'] = False
        if slot_need is not None:
            args += ['--slot_need', slot_need]
            expected['slot_need'] = slot_need
        if slotneed is not None:
            args += ['--slot-need', slotneed]
            expected['slot_need'] = slotneed
        self._test_update_resource(resource, cmd, myid, args, expected)

    def test_update_router_type_name(self):
        """Update routertype: myid --name myname."""
        self._test_update_router_type(name='myname')

    def test_update_router_type_description(self):
        self._test_update_router_type(desc='some description')

    def test_update_router_type_ha(self):
        self._test_update_router_type(ha_enabled=True)
        self._test_update_router_type(haenabled=True)
        self._test_update_router_type(ha_disabled=True)
        self._test_update_router_type(hadisabled=True)

    def test_update_router_type_sharing(self):
        self._test_update_router_type(shared=True)
        self._test_update_router_type(unshared=True)

    def test_update_router_type_slots(self):
        self._test_update_router_type(slot_need='5')
        self._test_update_router_type(slotneed='5')

    def test_update_router_type_full(self):
        self._test_update_router_type(name='myname', desc='some description',
                                      ha_enabled=True, shared=True,
                                      slot_need='5')
        self._test_update_router_type(name='myname', desc='some description',
                                      haenabled=True, shared=True,
                                      slotneed='5')
        self._test_update_router_type(name='myname', desc='some description',
                                      ha_disabled=True, unshared=True,
                                      slot_need='5')
        self._test_update_router_type(name='myname', desc='some description',
                                      hadisabled=True, unshared=True,
                                      slotneed='5')

    def test_delete_router_type(self):
        """Delete routertype: myid."""
        resource = 'routertype'
        cmd = routertype.RouterTypeDelete(test_cli20.MyApp(sys.stdout), None)
        myid = 'myid'
        args = [myid]
        self._test_delete_resource(resource, cmd, myid, args)

    def test_show_router_type(self):
        """Show routertype: myid."""
        resource = 'routertype'
        cmd = routertype.RouterTypeShow(test_cli20.MyApp(sys.stdout), None)
        args = ['--fields', 'id', '--fields', 'name', self.test_id]
        self._test_show_resource(resource, cmd, self.test_id, args,
                                 ['id', 'name'])
