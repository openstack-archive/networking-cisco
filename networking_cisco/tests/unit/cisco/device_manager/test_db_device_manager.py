# Copyright 2014 Cisco Systems, Inc.  All rights reserved.
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

import os

import contextlib
import mock

from oslo_config import cfg
from oslo_utils import importutils
import six
import webob.exc

from neutron.api import extensions as api_ext
from neutron.common import config
from neutron import context as n_context
from neutron.manager import NeutronManager
from neutron.plugins.common import constants as svc_constants
from neutron.tests.unit.db import test_db_base_plugin_v2

import networking_cisco
from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)
from networking_cisco.plugins.cisco.db.device_manager import (
    hosting_device_manager_db as hdm_db)
from networking_cisco.plugins.cisco.device_manager.rpc import (
    devmgr_rpc_cfgagent_api)
from networking_cisco.plugins.cisco.device_manager import service_vm_lib
from networking_cisco.plugins.cisco.extensions import ciscohostingdevicemanager
from networking_cisco.tests.unit.cisco.device_manager import (
    device_manager_test_support)


policy_path = (os.path.abspath(networking_cisco.__path__[0]) +
               '/../etc/policy.json')

DB_DM_PLUGIN_KLASS = (
    'networking_cisco.plugins.cisco.db.device_manager.'
    'hosting_device_manager_db.HostingDeviceManagerMixin')

NN_CATEGORY = ciscohostingdevicemanager.NETWORK_NODE_CATEGORY
NN_TEMPLATE_NAME = c_constants.NETWORK_NODE_TEMPLATE
NS_ROUTERTYPE_NAME = c_constants.NAMESPACE_ROUTER_TYPE
VM_CATEGORY = ciscohostingdevicemanager.VM_CATEGORY
VM_TEMPLATE_NAME = "CSR1kv_template"
VM_BOOTING_TIME = 420
VM_SLOT_CAPACITY = 3
VM_DESIRED_SLOTS_FREE = 3
VM_ROUTERTYPE_NAME = c_constants.CSR1KV_ROUTER_TYPE
HW_CATEGORY = ciscohostingdevicemanager.HARDWARE_CATEGORY
HW_TEMPLATE_NAME = "HW_template"
HW_ROUTERTYPE_NAME = "HW_router"

L3_ROUTER_NAT = svc_constants.L3_ROUTER_NAT

DEFAULT_SERVICE_TYPES = "router"
NETWORK_NODE_SERVICE_TYPES = "router:fwaas:vpn"

NOOP_DEVICE_DRIVER = ('networking_cisco.plugins.cisco.device_manager.'
                      'hosting_device_drivers.noop_hd_driver.'
                      'NoopHostingDeviceDriver')
NOOP_PLUGGING_DRIVER = ('networking_cisco.plugins.cisco.device_manager.'
                        'plugging_drivers.noop_plugging_driver.'
                        'NoopPluggingDriver')

TEST_DEVICE_DRIVER = NOOP_DEVICE_DRIVER
TEST_PLUGGING_DRIVER = ('networking_cisco.tests.unit.cisco.device_manager.'
                        'plugging_test_driver.TestPluggingDriver')

DESCRIPTION = "default description"
SHARED = True
ACTION = "allow"
ENABLED = True
ADMIN_STATE_UP = True

UNBOUND = None
REQUESTER = True
OTHER = False

DEFAULT_CREDENTIALS_ID = device_manager_test_support._uuid()


class DeviceManagerTestCaseMixin(object):

    def _create_hosting_device(self, fmt, template_id, management_port_id,
                               admin_state_up, expected_res_status=None,
                               **kwargs):
        data = {'hosting_device': self._get_test_hosting_device_attr(
            template_id=template_id, management_port_id=management_port_id,
            admin_state_up=admin_state_up, **kwargs)}
        hd_req = self.new_create_request('hosting_devices', data, fmt)
        if kwargs.get('set_context') and 'tenant_id' in kwargs:
            # create a specific auth context for this request
            hd_req.environ['neutron.context'] = n_context.Context(
                '', kwargs['tenant_id'])
        hd_res = hd_req.get_response(self.ext_api)
        if expected_res_status:
            self.assertEqual(expected_res_status, hd_res.status_int)
        return hd_res

    @contextlib.contextmanager
    def hosting_device(self, template_id, management_port_id=None, fmt=None,
                       admin_state_up=True, no_delete=False,
                       set_port_device_id=True, **kwargs):
        if not fmt:
            fmt = self.fmt
        res = self._create_hosting_device(fmt, template_id, management_port_id,
                                          admin_state_up, **kwargs)
        if res.status_int >= 400:
            raise webob.exc.HTTPClientError(code=res.status_int)
        hosting_device = self.deserialize(fmt or self.fmt, res)
        if set_port_device_id is True and management_port_id is not None:
            data = {'port': {
                'device_id': hosting_device['hosting_device']['id'],
                'device_owner': 'Nova'}}
            req = self.new_update_request('ports', data, management_port_id)
            res = self.deserialize(self.fmt, req.get_response(self.api))
        yield hosting_device
        if not no_delete:
            self._delete('hosting_devices',
                         hosting_device['hosting_device']['id'])

    def _create_hosting_device_template(self, fmt, name, enabled,
                                        host_category,
                                        expected_res_status=None, **kwargs):
        data = {'hosting_device_template':
                self._get_test_hosting_device_template_attr(
                    name=name, enabled=enabled, host_category=host_category,
                    **kwargs)}
        hdt_req = self.new_create_request('hosting_device_templates', data,
                                          fmt)
        if kwargs.get('set_context') and 'tenant_id' in kwargs:
            # create a specific auth context for this request
            hdt_req.environ['neutron.context'] = n_context.Context(
                '', kwargs['tenant_id'])
        hdt_res = hdt_req.get_response(self.ext_api)
        if expected_res_status:
            self.assertEqual(expected_res_status, hdt_res.status_int)
        return hdt_res

    @contextlib.contextmanager
    def hosting_device_template(self, fmt=None, name='device_template_1',
                                enabled=True, host_category=VM_CATEGORY,
                                no_delete=False, **kwargs):
        if not fmt:
            fmt = self.fmt
        res = self._create_hosting_device_template(fmt, name, enabled,
                                                   host_category, **kwargs)
        if res.status_int >= 400:
            raise webob.exc.HTTPClientError(code=res.status_int)
        hd_template = self.deserialize(fmt or self.fmt, res)
        yield hd_template
        if not no_delete:
            self._delete('hosting_device_templates',
                         hd_template['hosting_device_template']['id'])

    def _get_test_hosting_device_attr(self, template_id, management_port_id,
                                      admin_state_up=True, **kwargs):
        data = {
            'tenant_id': kwargs.get('tenant_id', self._tenant_id),
            'template_id': template_id,
            'credentials_id': kwargs.get('credentials_id'),
            'device_id': kwargs.get('device_id', 'mfc_device_id'),
            'admin_state_up': admin_state_up,
            'management_ip_address': kwargs.get('management_ip_address',
                                                '10.0.100.10'),
            'management_port_id': management_port_id,
            'protocol_port': kwargs.get('protocol_port', 22),
            'cfg_agent_id': kwargs.get('cfg_agent_id'),
            'tenant_bound': kwargs.get('tenant_bound'),
            'auto_delete': kwargs.get('auto_delete', False)}
        return data

    def _get_test_hosting_device_template_attr(self, name='device_template_1',
                                               enabled=True,
                                               host_category=VM_CATEGORY,
                                               **kwargs):
        data = {
            'tenant_id': kwargs.get('tenant_id', self._tenant_id),
            'name': name,
            'enabled': enabled,
            'host_category': host_category,
            'service_types': kwargs.get('service_types',
                                        DEFAULT_SERVICE_TYPES),
            'image': kwargs.get('image'),
            'flavor': kwargs.get('flavor'),
            'default_credentials_id': kwargs.get('default_credentials_id',
                                                 DEFAULT_CREDENTIALS_ID),
            'configuration_mechanism': kwargs.get('configuration_mechanism'),
            'protocol_port': kwargs.get('protocol_port', 22),
            'booting_time': kwargs.get('booting_time', 0),
            'slot_capacity': kwargs.get('slot_capacity', 0),
            'desired_slots_free': kwargs.get('desired_slots_free', 0),
            'tenant_bound': kwargs.get('tenant_bound', []),
            'device_driver': kwargs.get('device_driver', NOOP_DEVICE_DRIVER),
            'plugging_driver': kwargs.get('plugging_driver',
                                          NOOP_PLUGGING_DRIVER)}
        return data

    def _test_list_resources(self, resource, items,
                             neutron_context=None,
                             query_params=None):
        if resource.endswith('y'):
            resource_plural = resource.replace('y', 'ies')
        else:
            resource_plural = resource + 's'

        res = self._list(resource_plural,
                         neutron_context=neutron_context,
                         query_params=query_params)
        resource = resource.replace('-', '_')
        self.assertEqual(sorted([i[resource]['id'] for i in items]),
                         sorted([i['id'] for i in res[resource_plural]]))

    def _replace_hosting_device_status(self, attrs, old_status, new_status):
        if attrs['status'] is old_status:
            attrs['status'] = new_status
        return attrs

    def _test_create_hosting_device_templates(self):
        # template for network nodes.
        nnt = self._create_hosting_device_template(self.fmt, NN_TEMPLATE_NAME,
                                                   True, NN_CATEGORY)
        nw_node_template = self.deserialize(self.fmt, nnt)
        vmt = self._create_hosting_device_template(
            self.fmt, VM_TEMPLATE_NAME, True, VM_CATEGORY,
            booting_time=VM_BOOTING_TIME,
            slot_capacity=VM_SLOT_CAPACITY,
            desired_slots_free=VM_DESIRED_SLOTS_FREE,
            device_driver=TEST_DEVICE_DRIVER,
            plugging_driver=TEST_PLUGGING_DRIVER)
        vm_template = self.deserialize(self.fmt, vmt)
        hwt = self._create_hosting_device_template(
            self.fmt, HW_TEMPLATE_NAME, True, HW_CATEGORY)
        hw_template = self.deserialize(self.fmt, hwt)
        return {'network_node': {'template': nw_node_template,
                                 'router_type': NS_ROUTERTYPE_NAME},
                'vm': {'template': vm_template,
                       'router_type': VM_ROUTERTYPE_NAME},
                'hw': {'template': hw_template,
                       'router_type': HW_ROUTERTYPE_NAME}}

    def _test_remove_hosting_device_templates(self):
        for hdt in self._list('hosting_device_templates')[
                'hosting_device_templates']:
            self._delete('hosting_device_templates', hdt['id'])


class TestDeviceManagerDBPlugin(
    test_db_base_plugin_v2.NeutronDbPluginV2TestCase,
    DeviceManagerTestCaseMixin,
        device_manager_test_support.DeviceManagerTestSupportMixin):

    hdm_db.HostingDeviceManagerMixin.path_prefix = "/dev_mgr"
    resource_prefix_map = dict(
        (k, "/dev_mgr")
        for k in ciscohostingdevicemanager.RESOURCE_ATTRIBUTE_MAP.keys())

    def setUp(self, core_plugin=None, dm_plugin=None, ext_mgr=None):
        if dm_plugin is None:
            dm_plugin = DB_DM_PLUGIN_KLASS
        service_plugins = {'dm_plugin_name': dm_plugin}
        cfg.CONF.set_override('api_extensions_path',
                              device_manager_test_support.extensions_path)
        # for these tests we need to enable overlapping ips
        cfg.CONF.set_default('allow_overlapping_ips', True)
        hdm_db.HostingDeviceManagerMixin.supported_extension_aliases = (
            [ciscohostingdevicemanager.HOSTING_DEVICE_MANAGER_ALIAS])
        super(TestDeviceManagerDBPlugin, self).setUp(
            plugin=core_plugin, service_plugins=service_plugins,
            ext_mgr=ext_mgr)
        # Ensure we use policy definitions from our repo
        cfg.CONF.set_override('policy_file', policy_path, 'oslo_policy')
        if not ext_mgr:
            self.plugin = importutils.import_object(dm_plugin)
            ext_mgr = api_ext.PluginAwareExtensionManager(
                device_manager_test_support.extensions_path,
                {c_constants.DEVICE_MANAGER: self.plugin})
            app = config.load_paste_app('extensions_test_app')
            self.ext_api = api_ext.ExtensionMiddleware(app, ext_mgr=ext_mgr)

        self._mock_l3_admin_tenant()
        self._create_mgmt_nw_for_tests(self.fmt)
        self._devmgr = NeutronManager.get_service_plugins()[
            c_constants.DEVICE_MANAGER]
        # in unit tests we don't use keystone so we mock that session
        self._devmgr._svc_vm_mgr_obj = service_vm_lib.ServiceVMManager(
            True, None, None, None, '', keystone_session=mock.MagicMock())
        self._mock_svc_vm_create_delete(self._devmgr)
        self._other_tenant_id = device_manager_test_support._uuid()
        self._devmgr._core_plugin = NeutronManager.get_plugin()

    def tearDown(self):
        self._test_remove_all_hosting_devices()
        self._remove_mgmt_nw_for_tests()
        super(TestDeviceManagerDBPlugin, self).tearDown()

    def test_create_vm_hosting_device(self):
        with self.hosting_device_template() as hdt:
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                creds = device_manager_test_support._uuid()
                attrs = self._get_test_hosting_device_attr(
                    template_id=hdt['hosting_device_template']['id'],
                    management_port_id=mgmt_port['port']['id'],
                    auto_delete=True, credentials_id=creds)
                with self.hosting_device(
                        template_id=hdt['hosting_device_template']['id'],
                        management_port_id=mgmt_port['port']['id'],
                        auto_delete=True, credentials_id=creds) as hd:
                    for k, v in six.iteritems(attrs):
                        self.assertEqual(v, hd['hosting_device'][k])

    def test_create_hw_hosting_device(self):
        with self.hosting_device_template(host_category=HW_CATEGORY) as hdt:
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                creds = device_manager_test_support._uuid()
                attrs = self._get_test_hosting_device_attr(
                    template_id=hdt['hosting_device_template']['id'],
                    management_port_id=mgmt_port['port']['id'],
                    credentials_id=creds)
                with self.hosting_device(
                        template_id=hdt['hosting_device_template']['id'],
                        management_port_id=mgmt_port['port']['id'],
                        credentials_id=creds) as hd:
                    for k, v in six.iteritems(attrs):
                        self.assertEqual(v, hd['hosting_device'][k])

    def test_show_hosting_device(self):
        device_id = "device_XYZ"
        with self.hosting_device_template() as hdt:
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                creds = device_manager_test_support._uuid()
                attrs = self._get_test_hosting_device_attr(
                    device_id=device_id,
                    template_id=hdt['hosting_device_template']['id'],
                    management_port_id=mgmt_port['port']['id'],
                    credentials_id=creds)
                with self.hosting_device(
                        device_id=device_id,
                        template_id=hdt['hosting_device_template']['id'],
                        management_port_id=mgmt_port['port']['id'],
                        credentials_id=creds) as hd:
                    req = self.new_show_request(
                        'hosting_devices', hd['hosting_device']['id'],
                        fmt=self.fmt)
                    res = self.deserialize(self.fmt,
                                           req.get_response(self.ext_api))
                    for k, v in six.iteritems(attrs):
                        self.assertEqual(v, res['hosting_device'][k])

    def test_list_hosting_devices(self):
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            with self.port(subnet=self._mgmt_subnet) as mgmt_port1,\
                    self.port(subnet=self._mgmt_subnet) as mgmt_port2,\
                    self.port(subnet=self._mgmt_subnet) as mgmt_port3:
                mp1_id = mgmt_port1['port']['id']
                mp2_id = mgmt_port2['port']['id']
                mp3_id = mgmt_port3['port']['id']
                with self.hosting_device(
                        name='hd1', template_id=hdt_id,
                        management_port_id=mp1_id) as hd1,\
                        self.hosting_device(
                            name='hd2', template_id=hdt_id,
                            management_port_id=mp2_id) as hd2,\
                        self.hosting_device(
                            name='hd3', template_id=hdt_id,
                            management_port_id=mp3_id) as hd3:
                    self._test_list_resources(
                        'hosting_device', [hd1, hd2, hd3],
                        query_params='template_id=' + hdt_id)

    def test_update_hosting_device(self):
        new_device_id = "device_XYZ"
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                mgmt_port_id = mgmt_port['port']['id']
                creds = device_manager_test_support._uuid()
                attrs = self._get_test_hosting_device_attr(
                    device_id=new_device_id,
                    template_id=hdt['hosting_device_template']['id'],
                    management_port_id=mgmt_port['port']['id'],
                    credentials_id=creds)
                with self.hosting_device(
                        template_id=hdt_id,
                        management_port_id=mgmt_port_id,
                        credentials_id=creds) as hd:
                    data = {'hosting_device': {'device_id': new_device_id}}
                    req = self.new_update_request('hosting_devices', data,
                                                  hd['hosting_device']['id'])
                    res = self.deserialize(self.fmt,
                                           req.get_response(self.ext_api))
                    for k, v in six.iteritems(attrs):
                        self.assertEqual(v, res['hosting_device'][k])

    def test_delete_hosting_device_not_in_use_succeeds(self):
        ctx = n_context.get_admin_context()
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                mgmt_port_id = mgmt_port['port']['id']
                with self.hosting_device(template_id=hdt_id,
                                         management_port_id=mgmt_port_id,
                                         no_delete=True) as hd:
                    hd_id = hd['hosting_device']['id']
                    req = self.new_delete_request('hosting_devices', hd_id)
                    res = req.get_response(self.ext_api)
                    self.assertEqual(204, res.status_int)
                    self.assertRaises(
                        ciscohostingdevicemanager.HostingDeviceNotFound,
                        self.plugin.get_hosting_device, ctx, hd_id)

    def test_delete_hosting_device_in_use_fails(self):
        ctx = n_context.get_admin_context()
        with self.hosting_device_template(slot_capacity=1) as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                mgmt_port_id = mgmt_port['port']['id']
                with self.hosting_device(
                        template_id=hdt_id,
                        management_port_id=mgmt_port_id) as hd:
                    with mock.patch.object(
                            hdm_db.HostingDeviceManagerMixin,
                            '_dispatch_pool_maintenance_job'):
                        hd_id = hd['hosting_device']['id']
                        hd_db = self._devmgr._get_hosting_device(ctx, hd_id)
                        resource = self._get_fake_resource()
                        self.assertTrue(
                            self._devmgr.acquire_hosting_device_slots(
                                ctx, hd_db, resource, 'router', L3_ROUTER_NAT,
                                1))
                        self.assertRaises(
                            ciscohostingdevicemanager.HostingDeviceInUse,
                            self._devmgr.delete_hosting_device, ctx, hd_id)
                        req = self.new_show_request('hosting_devices', hd_id,
                                                    fmt=self.fmt)
                        res = req.get_response(self.ext_api)
                        self.assertEqual(200, res.status_int)
                        self._devmgr.release_hosting_device_slots(ctx, hd_db,
                                                                  resource, 1)

    def test_get_hosting_device_configuration(self):
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                mgmt_port_id = mgmt_port['port']['id']
                with self.hosting_device(
                        template_id=hdt_id,
                        management_port_id=mgmt_port_id) as hd:
                    hd_id = hd['hosting_device']['id']
                    rpc = devmgr_rpc_cfgagent_api.DeviceMgrCfgAgentNotifyAPI(
                        self._devmgr)
                    self._devmgr.agent_notifiers = {
                        c_constants.AGENT_TYPE_CFG: rpc}
                    self._devmgr.get_cfg_agents_for_hosting_devices = None
                    with mock.patch.object(rpc.client, 'prepare',
                                           return_value=rpc.client) as (
                            mock_prepare),\
                        mock.patch.object(rpc.client, 'call') as mock_call,\
                        mock.patch.object(
                            self._devmgr,
                            'get_cfg_agents_for_hosting_devices') as agt_mock:
                        agt_mock.return_value = [mock.MagicMock()]
                        agent_host = 'an_agent_host'
                        agt_mock.return_value[0].host = agent_host
                        fake_running_config = 'a fake running config'
                        mock_call.return_value = fake_running_config
                        ctx = n_context.Context(
                            user_id=None, tenant_id=None, is_admin=False,
                            overwrite=False)
                        res = self._devmgr.get_hosting_device_config(ctx,
                                                                     hd_id)
                        self.assertEqual(fake_running_config, res)
                        agt_mock.assert_called_once_with(
                            mock.ANY, [hd_id], admin_state_up=True,
                            schedule=True)
                        mock_prepare.assert_called_with(server=agent_host)
                        mock_call.assert_called_with(
                            mock.ANY, 'get_hosting_device_configuration',
                            payload={'hosting_device_id': hd_id})

    def test_get_hosting_device_configuration_no_agent_found(self):
        ctx = n_context.Context(user_id=None, tenant_id=None, is_admin=False,
                                overwrite=False)
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                mgmt_port_id = mgmt_port['port']['id']
                with self.hosting_device(
                        template_id=hdt_id,
                        management_port_id=mgmt_port_id) as hd:
                    hd_id = hd['hosting_device']['id']
                    rpc = devmgr_rpc_cfgagent_api.DeviceMgrCfgAgentNotifyAPI(
                        self._devmgr)
                    self._devmgr.agent_notifiers = {
                        c_constants.AGENT_TYPE_CFG: rpc}
                    self._devmgr.get_cfg_agents_for_hosting_devices = None
                    with mock.patch.object(rpc.client, 'prepare',
                                           return_value=rpc.client) as (
                            mock_prepare),\
                        mock.patch.object(rpc.client, 'call') as mock_call,\
                        mock.patch.object(
                            self._devmgr,
                            'get_cfg_agents_for_hosting_devices') as agt_mock:
                        agt_mock.return_value = []
                        res = self._devmgr.get_hosting_device_config(ctx,
                                                                     hd_id)
                        self.assertIsNone(res)
                        agt_mock.assert_called_once_with(
                            mock.ANY, [hd_id], admin_state_up=True,
                            schedule=True)
                        self.assertEqual(0, mock_prepare.call_count)
                        self.assertEqual(0, mock_call.call_count)

    def test_hosting_device_policy(self):
        device_id = "device_XYZ"
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            tenant_id = hdt['hosting_device_template']['tenant_id']
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                mgmt_port_id = mgmt_port['port']['id']
                creds = device_manager_test_support._uuid()
                with self.hosting_device(
                        device_id=device_id,
                        template_id=hdt_id,
                        management_port_id=mgmt_port_id,
                        credentials_id=creds) as hd:
                    hd_id = hd['hosting_device']['id']
                    # create fails
                    self._create_hosting_device(
                        self.fmt, hdt_id, mgmt_port_id, True,
                        webob.exc.HTTPForbidden.code,
                        tenant_id=tenant_id, set_context=True)
                    non_admin_ctx = n_context.Context('', tenant_id)
                    # show fails
                    self._show('hosting_devices', hd_id,
                               webob.exc.HTTPNotFound.code, non_admin_ctx)
                    # update fails
                    self._update('hosting_devices', hd_id,
                                 {'hosting_device': {'name': 'new_name'}},
                                 webob.exc.HTTPForbidden.code, non_admin_ctx)
                    # delete fails
                    self._delete('hosting_devices', hd_id,
                                 webob.exc.HTTPNotFound.code, non_admin_ctx)
                    # get config fails
                    req = self.new_show_request(
                        'hosting_devices', hd_id, self.fmt,
                        'get_hosting_device_config')
                    req.environ['neutron.context'] = non_admin_ctx
                    res = req.get_response(self._api_for_resource(
                        'hosting_devices'))
                    self.assertEqual(webob.exc.HTTPNotFound.code,
                                     res.status_int)

    def test_create_vm_hosting_device_template(self):
        attrs = self._get_test_hosting_device_template_attr()

        with self.hosting_device_template() as hdt:
            for k, v in six.iteritems(attrs):
                self.assertEqual(v, hdt['hosting_device_template'][k])

    def test_create_hw_hosting_device_template(self):
        attrs = self._get_test_hosting_device_template_attr(
            host_category=HW_CATEGORY)

        with self.hosting_device_template(host_category=HW_CATEGORY) as hdt:
            for k, v in six.iteritems(attrs):
                self.assertEqual(v, hdt['hosting_device_template'][k])

    def test_create_nn_hosting_device_template(self):
        attrs = self._get_test_hosting_device_template_attr(
            host_category=NN_CATEGORY)

        with self.hosting_device_template(host_category=NN_CATEGORY) as hdt:
            for k, v in six.iteritems(attrs):
                self.assertEqual(v, hdt['hosting_device_template'][k])

    def test_show_hosting_device_template(self):
        name = "hosting_device_template1"
        attrs = self._get_test_hosting_device_template_attr(name=name)
        with self.hosting_device_template(name=name) as hdt:
            req = self.new_show_request('hosting_device_templates',
                                        hdt['hosting_device_template']['id'],
                                        fmt=self.fmt)
            res = self.deserialize(self.fmt,
                                   req.get_response(self.ext_api))
            for k, v in six.iteritems(attrs):
                self.assertEqual(v, res['hosting_device_template'][k])

    def test_list_hosting_device_templates(self):
        with self.hosting_device_template(name='hdt1',
                                          host_category=VM_CATEGORY,
                                          image='an_image') as hdt1,\
                self.hosting_device_template(name='hdt2',
                                             host_category=HW_CATEGORY,
                                             image='an_image') as hdt2,\
                self.hosting_device_template(name='hdt3',
                                             host_category=NN_CATEGORY,
                                             image='an_image') as hdt3:
            self._test_list_resources(
                'hosting_device_template', [hdt1, hdt2, hdt3],
                query_params='image=an_image')

    def test_update_hosting_device_template(self):
        name = "new_hosting_device_template1"
        attrs = self._get_test_hosting_device_template_attr(name=name)
        with self.hosting_device_template() as hdt:
            data = {'hosting_device_template': {'name': name}}
            req = self.new_update_request('hosting_device_templates', data,
                                          hdt['hosting_device_template']['id'])
            res = self.deserialize(self.fmt,
                                   req.get_response(self.ext_api))
            for k, v in six.iteritems(attrs):
                self.assertEqual(v, res['hosting_device_template'][k])

    def test_delete_hosting_device_template_not_in_use_succeeds(self):
        ctx = n_context.get_admin_context()
        with self.hosting_device_template(no_delete=True) as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            req = self.new_delete_request('hosting_device_templates', hdt_id)
            res = req.get_response(self.ext_api)
            self.assertEqual(204, res.status_int)
            self.assertRaises(
                ciscohostingdevicemanager.HostingDeviceTemplateNotFound,
                self._devmgr.get_hosting_device_template, ctx, hdt_id)

    def test_delete_hosting_device_template_in_use_fails(self):
        ctx = n_context.get_admin_context()
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                mgmt_port_id = mgmt_port['port']['id']
                with self.hosting_device(template_id=hdt_id,
                                         management_port_id=mgmt_port_id):
                    self.assertRaises(
                        ciscohostingdevicemanager.HostingDeviceTemplateInUse,
                        self._devmgr.delete_hosting_device_template, ctx,
                        hdt_id)
                    req = self.new_show_request('hosting_device_templates',
                                                hdt_id, fmt=self.fmt)
                    res = req.get_response(self.ext_api)
                    self.assertEqual(200, res.status_int)

    def test_hosting_device_template_policy(self):
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            tenant_id = hdt['hosting_device_template']['tenant_id']
            # create fails
            self._create_hosting_device_template(
                self.fmt, 'my_template', True, 'Hardware',
                webob.exc.HTTPForbidden.code,
                tenant_id=tenant_id, set_context=True)
            non_admin_ctx = n_context.Context('', tenant_id)
            # show fail
            self._show('hosting_device_templates', hdt_id,
                       webob.exc.HTTPNotFound.code, non_admin_ctx)
            # update fail
            self._update('hosting_device_templates', hdt_id,
                         {'hosting_device_template': {'enabled': False}},
                         webob.exc.HTTPForbidden.code, non_admin_ctx)
            # delete fail
            self._delete('hosting_device_templates', hdt_id,
                         webob.exc.HTTPNotFound.code, non_admin_ctx)

    # driver request test helper
    def _test_get_driver(self, get_method, id=None, test_for_none=False,
                         is_admin=False):
        with self.hosting_device_template() as hdt:
            context = self._get_test_context(
                tenant_id=hdt['hosting_device_template']['tenant_id'],
                is_admin=is_admin)
            driver_getter = getattr(self._devmgr, get_method)
            template_id = id or hdt['hosting_device_template']['id']
            driver = driver_getter(context, template_id)
            if test_for_none:
                self.assertIsNone(driver)
            else:
                self.assertIsNotNone(driver)

    # driver request tests
    def test_get_hosting_device_driver(self):
        self._test_get_driver('get_hosting_device_driver')

    def test_get_non_existent_hosting_device_driver_returns_none(self):
        self._test_get_driver('get_hosting_device_driver', 'bogus_id', True)

    def test_get_plugging_device_driver(self):
        self._test_get_driver('get_hosting_device_plugging_driver')

    def test_get_non_existent_plugging_device_driver_returns_none(self):
        self._test_get_driver('get_hosting_device_plugging_driver', 'bogus_id',
                              True)

    # get device info tests
    def test_get_device_info_for_agent(self):
        device_id = "device_XYZ"
        with self.hosting_device_template() as hdt, self.port(
                subnet=self._mgmt_subnet) as mgmt_port:
            creds = device_manager_test_support._uuid()
            mgmt_ip = mgmt_port['port']['fixed_ips'][0]['ip_address']
            with self.hosting_device(
                    device_id=device_id,
                    template_id=hdt['hosting_device_template']['id'],
                    management_port_id=mgmt_port['port']['id'],
                    credentials_id=creds) as hd:
                context = self._get_test_context(
                    tenant_id=hdt['hosting_device_template']['tenant_id'],
                    is_admin=True)
                hd_id = hd['hosting_device']['id']
                hd_db = self._devmgr._get_hosting_device(context, hd_id)
                info = self._devmgr.get_device_info_for_agent(context, hd_db)
                self.assertEqual(mgmt_ip, info['management_ip_address'])

    def test_get_device_info_for_agent_no_mgmt_port(self):
        device_id = "device_XYZ"
        with self.hosting_device_template() as hdt:
            creds = device_manager_test_support._uuid()
            mgmt_ip = '192.168.0.55'
            with self.hosting_device(
                    device_id=device_id,
                    template_id=hdt['hosting_device_template']['id'],
                    management_ip_address=mgmt_ip,
                    management_port_id=None,
                    credentials_id=creds) as hd:
                context = self._get_test_context(
                    tenant_id=hdt['hosting_device_template']['tenant_id'],
                    is_admin=True)
                hd_id = hd['hosting_device']['id']
                hd_db = self._devmgr._get_hosting_device(context, hd_id)
                info = self._devmgr.get_device_info_for_agent(context, hd_db)
                self.assertEqual(mgmt_ip, info['management_ip_address'])

    def _set_ownership(self, bound_status, tenant_id, other_tenant_id=None):
        if bound_status == UNBOUND:
            return None
        elif bound_status == OTHER:
            return other_tenant_id or self._other_tenant_id
        else:
            return tenant_id

    # slot allocation and release test helper:
    # succeeds means returns True, fails means returns False
    def _test_slots(self, expected_result=True, expected_bind=UNBOUND,
                    expected_allocation=VM_SLOT_CAPACITY,
                    num_requested=VM_SLOT_CAPACITY,
                    slot_capacity=VM_SLOT_CAPACITY, initial_bind=UNBOUND,
                    bind=False, auto_delete=True, is_admin=False,
                    pool_maintenance_expected=True, test_release=False,
                    expected_release_result=True, expected_final_allocation=0,
                    expected_release_bind=UNBOUND,
                    num_to_release=VM_SLOT_CAPACITY,
                    release_pool_maintenance_expected=True):
        with self.hosting_device_template(
                slot_capacity=slot_capacity) as hdt:
            with self.port(subnet=self._mgmt_subnet) as mgmt_port:
                resource = self._get_fake_resource()
                tenant_bound = self._set_ownership(
                    initial_bind, resource['tenant_id'])
                with self.hosting_device(
                        template_id=hdt['hosting_device_template']['id'],
                        management_port_id=mgmt_port['port']['id'],
                        tenant_bound=tenant_bound,
                        auto_delete=auto_delete) as hd:
                    context = self._get_test_context(
                        tenant_id=hdt['hosting_device_template']['tenant_id'],
                        is_admin=is_admin)
                    hd_db = self._devmgr._get_hosting_device(
                        context, hd['hosting_device']['id'])
                    with mock.patch.object(
                            hdm_db.HostingDeviceManagerMixin,
                            '_dispatch_pool_maintenance_job') as pm_mock:
                        result = self._devmgr.acquire_hosting_device_slots(
                            context, hd_db, resource, 'router', L3_ROUTER_NAT,
                            num_requested, bind)
                        allocation = self._devmgr.get_slot_allocation(
                            context, resource_id=resource['id'])
                        self.assertEqual(expected_result, result)
                        self.assertEqual(expected_allocation, allocation)
                        expected_bind = self._set_ownership(
                            expected_bind, resource['tenant_id'])
                        self.assertEqual(expected_bind, hd_db.tenant_bound)
                        if pool_maintenance_expected:
                            pm_mock.assert_called_once_with(mock.ANY)
                            num_calls = 1
                        else:
                            pm_mock.assert_not_called()
                            num_calls = 0
                        if test_release:
                            result = self._devmgr.release_hosting_device_slots(
                                context, hd_db, resource, num_to_release)
                            if not test_release:
                                return
                            allocation = self._devmgr.get_slot_allocation(
                                context, resource_id=resource['id'])
                            self.assertEqual(expected_release_result, result)
                            self.assertEqual(expected_final_allocation,
                                             allocation)
                            expected_release_bind = self._set_ownership(
                                expected_release_bind, resource['tenant_id'])
                            self.assertEqual(expected_release_bind,
                                             hd_db.tenant_bound)
                            if release_pool_maintenance_expected:
                                num_calls += 1
                            self.assertEqual(num_calls, pm_mock.call_count)
                        else:
                            # ensure we clean up everything
                            num_to_release = 0
                        to_clean_up = num_requested - num_to_release
                        if to_clean_up < 0:
                            to_clean_up = num_requested
                        if to_clean_up:
                            self._devmgr.release_hosting_device_slots(
                                context, hd_db, resource, to_clean_up)

    # slot allocation tests
    def test_acquire_with_slot_surplus_in_owned_hosting_device_succeeds(self):
        self._test_slots(expected_bind=REQUESTER, initial_bind=REQUESTER,
                         bind=True)

    def test_acquire_with_slot_surplus_in_shared_hosting_device_succeeds(self):
        self._test_slots()

    def test_acquire_with_slot_surplus_take_hosting_device_ownership_succeeds(
            self):
        self._test_slots(expected_bind=REQUESTER, initial_bind=UNBOUND,
                         bind=True)

    def test_acquire_with_slot_surplus_drop_hosting_device_ownership_succeeds(
            self):
        self._test_slots(expected_bind=UNBOUND, initial_bind=REQUESTER,
                         bind=False)

    def test_acquire_slots_release_hosting_device_ownership_affects_all(self):
        #TODO(bobmel): Implement this unit test
        pass

    def test_acquire_slots_in_other_owned_hosting_device_fails(self):
        self._test_slots(expected_result=False, expected_bind=OTHER,
                         expected_allocation=0, initial_bind=OTHER,
                         pool_maintenance_expected=False)

    def test_acquire_slots_take_ownership_of_other_owned_hosting_device_fails(
            self):
        self._test_slots(expected_result=False, expected_bind=OTHER,
                         expected_allocation=0, initial_bind=OTHER,
                         bind=True, pool_maintenance_expected=False)

    def test_acquire_slots_take_ownership_of_multi_tenant_hosting_device_fails(
            self):
        #TODO(bobmel): Implement this unit test
        pass

    def test_acquire_with_slot_deficit_in_owned_hosting_device_fails(self):
        self._test_slots(expected_result=False, expected_bind=REQUESTER,
                         expected_allocation=0, initial_bind=REQUESTER,
                         num_requested=VM_SLOT_CAPACITY + 1)

    def test_acquire_with_slot_deficit_in_shared_hosting_device_fails(self):
        self._test_slots(expected_result=False, expected_bind=UNBOUND,
                         expected_allocation=0,
                         num_requested=VM_SLOT_CAPACITY + 1)

    def test_acquire_with_slot_deficit_in_other_owned_hosting_device_fails(
            self):
        self._test_slots(expected_result=False, expected_bind=OTHER,
                         expected_allocation=0, initial_bind=OTHER,
                         num_requested=VM_SLOT_CAPACITY + 1,
                         pool_maintenance_expected=False)

    # slot release tests
    def test_release_allocated_slots_in_owned_hosting_device_succeeds(self):
        self._test_slots(expected_bind=REQUESTER, initial_bind=REQUESTER,
                         bind=True, test_release=True,
                         expected_release_bind=REQUESTER,
                         expected_final_allocation=1,
                         num_to_release=VM_SLOT_CAPACITY - 1)

    def test_release_allocated_slots_in_shared_hosting_device_succeeds(self):
        self._test_slots(test_release=True, expected_final_allocation=1,
                         num_to_release=VM_SLOT_CAPACITY - 1)

    def test_release_all_slots_returns_hosting_device_ownership(self):
        self._test_slots(expected_bind=REQUESTER, initial_bind=REQUESTER,
                         bind=True, test_release=True,
                         expected_release_bind=UNBOUND)

    def test_release_slots_in_other_owned_hosting_device_fails(self):
        self._test_slots(expected_result=False, expected_bind=OTHER,
                         expected_allocation=0, initial_bind=OTHER,
                         pool_maintenance_expected=False,
                         test_release=True, expected_release_result=False,
                         expected_release_bind=OTHER,
                         expected_final_allocation=0,
                         num_to_release=VM_SLOT_CAPACITY - 1,
                         release_pool_maintenance_expected=False)

    def test_release_too_many_slots_in_owned_hosting_device_fails(self):
        self._test_slots(expected_bind=REQUESTER, initial_bind=REQUESTER,
                         bind=True, test_release=True,
                         expected_release_result=False,
                         expected_release_bind=REQUESTER,
                         expected_final_allocation=VM_SLOT_CAPACITY,
                         num_to_release=VM_SLOT_CAPACITY + 1)

    def test_release_too_many_slots_in_shared_hosting_device_fails(self):
        self._test_slots(test_release=True, expected_release_result=False,
                         expected_release_bind=UNBOUND,
                         expected_final_allocation=VM_SLOT_CAPACITY,
                         num_to_release=VM_SLOT_CAPACITY + 1)

    def test_release_too_many_slots_in_other_owned_hosting_device_fails(
            self):
        self._test_slots(expected_result=False, expected_bind=OTHER,
                         expected_allocation=0, initial_bind=OTHER,
                         pool_maintenance_expected=False,
                         test_release=True, expected_release_result=False,
                         expected_release_bind=OTHER,
                         expected_final_allocation=0,
                         num_to_release=VM_SLOT_CAPACITY + 1,
                         release_pool_maintenance_expected=False)

    def test_release_all_slots_by_negative_num_argument_shared_hosting_device(
            self):
        self._test_slots(test_release=True, expected_final_allocation=0,
                         num_to_release=-1)

    def test_release_all_slots_by_negative_num_argument_owned_hosting_device(
            self):
        self._test_slots(expected_bind=REQUESTER, initial_bind=REQUESTER,
                 bind=True, test_release=True, expected_release_bind=UNBOUND,
                 expected_final_allocation=0, num_to_release=-1)

    # hosting device deletion test helper
    def _test_delete(self, to_delete=None, auto_delete=None, no_delete=None,
                     force_delete=True, expected_num_remaining=0):
        auto_delete = auto_delete or [True, False, False, True, True]
        no_delete = no_delete or [True, True, True, True, True]
        with self.hosting_device_template() as hdt1,\
                self.hosting_device_template() as hdt2:
            hdt0_id = hdt1['hosting_device_template']['id']
            hdt1_id = hdt2['hosting_device_template']['id']
            with self.port(subnet=self._mgmt_subnet,
                           no_delete=no_delete[0]) as mgmt_port0,\
                    self.port(subnet=self._mgmt_subnet,
                              no_delete=no_delete[1]) as mgmt_port1,\
                    self.port(subnet=self._mgmt_subnet,
                              no_delete=no_delete[2]) as mgmt_port2,\
                    self.port(subnet=self._mgmt_subnet,
                              no_delete=no_delete[3]) as mgmt_port3,\
                    self.port(subnet=self._mgmt_subnet,
                              no_delete=no_delete[4]) as mgmt_port4:
                mp0_id = mgmt_port0['port']['id']
                mp1_id = mgmt_port1['port']['id']
                mp2_id = mgmt_port2['port']['id']
                mp3_id = mgmt_port3['port']['id']
                mp4_id = mgmt_port4['port']['id']
                with self.hosting_device(
                        device_id='0_hdt0_id', template_id=hdt0_id,
                        management_port_id=mp0_id, auto_delete=auto_delete[0],
                        no_delete=no_delete[0]),\
                    self.hosting_device(
                        device_id='1_hdt1_id', template_id=hdt1_id,
                        management_port_id=mp1_id, auto_delete=auto_delete[1],
                        no_delete=no_delete[1]),\
                    self.hosting_device(
                        device_id='2_hdt0_id', template_id=hdt0_id,
                        management_port_id=mp2_id, auto_delete=auto_delete[2],
                        no_delete=no_delete[2]),\
                    self.hosting_device(
                        device_id='3_hdt0_id', template_id=hdt0_id,
                        management_port_id=mp3_id,
                        auto_delete=auto_delete[3],
                        no_delete=no_delete[3]),\
                    self.hosting_device(
                        device_id='4_hdt1_id', template_id=hdt1_id,
                        management_port_id=mp4_id, auto_delete=auto_delete[4],
                        no_delete=no_delete[4]):
                        context = self._get_test_context(is_admin=True)
                        if to_delete is None:
                            self._devmgr.delete_all_hosting_devices(
                                context, force_delete)
                        elif to_delete == 0:
                            template = (
                                self._devmgr._get_hosting_device_template(
                                    context, hdt0_id))
                            (self._devmgr.
                                delete_all_hosting_devices_by_template(
                                    context, template, force_delete))
                        else:
                            template = (
                                self._devmgr._get_hosting_device_template(
                                    context, hdt1_id))
                            (self._devmgr.
                                delete_all_hosting_devices_by_template(
                                    context, template, force_delete))
                        result_hds = self._list(
                            'hosting_devices')['hosting_devices']
                        self.assertEqual(expected_num_remaining,
                                         len(result_hds))

    # hosting device deletion tests
    def test_delete_all_hosting_devices(self):
        self._test_delete()

    def test_delete_all_managed_hosting_devices(self):
        self._test_delete(no_delete=[True, False, False, True, True],
                          force_delete=False, expected_num_remaining=2)

    def test_delete_all_hosting_devices_by_template(self):
        self._test_delete(to_delete=1, expected_num_remaining=3,
                          no_delete=[False, True, False, False, True])

    def test_delete_all_managed_hosting_devices_by_template(self):
        self._test_delete(to_delete=1, expected_num_remaining=4,
                          no_delete=[False, False, False, False, True],
                          force_delete=False)

    # handled failed hosting device test helper
    def _test_failed_hosting_device(self, host_category=VM_CATEGORY,
                                    expected_num_remaining=0,
                                    auto_delete=True, no_delete=True):
        with self.hosting_device_template(host_category=host_category) as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            with self.port(subnet=self._mgmt_subnet,
                           no_delete=no_delete) as mgmt_port:
                with self.hosting_device(
                        template_id=hdt_id,
                        management_port_id=mgmt_port['port']['id'],
                        auto_delete=auto_delete, no_delete=no_delete) as hd:
                    with mock.patch('neutron.manager.NeutronManager.'
                                    'get_service_plugins'):
                        hd_id = hd['hosting_device']['id']
                        m2 = mock.MagicMock()
                        self._devmgr.agent_notifiers = {
                            c_constants.AGENT_TYPE_CFG: m2}
                        context = self._get_test_context()
                        self._devmgr.handle_non_responding_hosting_devices(
                            context, None, [hd_id])
                        result_hds = self._list('hosting_devices')[
                            'hosting_devices']
                        self.assertEqual(expected_num_remaining,
                                         len(result_hds))
                        l3mock = (NeutronManager.get_service_plugins().get().
                                  handle_non_responding_hosting_devices)
                        l3mock.assert_called_once_with(mock.ANY, mock.ANY,
                                                       {hd_id: {}})
                        if expected_num_remaining == 0:
                            m2.hosting_devices_removed.assert_called_once_with(
                                mock.ANY, {hd_id: {}}, False, None)

    # handled failed hosting device tests
    def test_failed_managed_vm_based_hosting_device_gets_deleted(self):
        self._test_failed_hosting_device()

    def test_failed_non_managed_vm_based_hosting_device_not_deleted(self):
        self._test_failed_hosting_device(expected_num_remaining=1,
                                         auto_delete=False, no_delete=False)

    def test_failed_non_vm_based_hosting_device_not_deleted(self):
        self._test_failed_hosting_device(host_category=HW_CATEGORY,
                                         expected_num_remaining=1,
                                         no_delete=False)

    # hosting device pool maintenance test helper
    def _test_pool_maintenance(self, desired_slots_free=10, slot_capacity=3,
                               host_category=VM_CATEGORY, expected=15,
                               define_credentials=True):
        with self.hosting_device_template(
                host_category=host_category, slot_capacity=slot_capacity,
                desired_slots_free=desired_slots_free,
                plugging_driver=TEST_PLUGGING_DRIVER) as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            creds_id = (DEFAULT_CREDENTIALS_ID if define_credentials is True
                        else 'non_existent_id')
            credentials = {'user_name': 'bob', 'password': 'tooEasy'}
            with mock.patch.dict(
                    self.plugin._credentials,
                    {creds_id: credentials}),\
                    self.port(subnet=self._mgmt_subnet,
                              no_delete=True) as mgmt_port1,\
                    self.port(subnet=self._mgmt_subnet,
                              no_delete=True) as mgmt_port2:
                with self.hosting_device(
                        template_id=hdt_id,
                        management_port_id=mgmt_port1['port']['id'],
                        auto_delete=True, no_delete=True),\
                     self.hosting_device(
                         template_id=hdt_id,
                         management_port_id=mgmt_port2['port']['id'],
                         auto_delete=True, no_delete=True):
                    context = self._get_test_context(is_admin=True)
                    template = self._devmgr._get_hosting_device_template(
                        context, hdt_id)

                    self._devmgr._gt_pool = mock.MagicMock()
                    self._devmgr._gt_pool.spawn_n.side_effect = (
                        lambda fcn, ctx, tmplt: fcn(ctx, tmplt))
                    self._devmgr._dispatch_pool_maintenance_job(
                        template)
                    result_hds = self._list(
                        'hosting_devices')['hosting_devices']
                    self.assertEqual(expected, len(result_hds) * slot_capacity)
            self._devmgr.delete_all_hosting_devices(context, True)

    # hosting device pool maintenance tests
    def test_vm_based_hosting_device_excessive_slot_deficit_adds_slots(self):
        self._test_pool_maintenance()

    def test_vm_based_hosting_device_excessive_slot_deficit_no_credentials(
            self):
        # no slots are added if credentials for template are missing
        self._test_pool_maintenance(expected=6, define_credentials=False)

    def test_vm_based_hosting_device_marginal_slot_deficit_no_change(self):
        self._test_pool_maintenance(desired_slots_free=7, expected=6)

    def test_vm_based_hosting_device_excessive_slot_surplus_removes_slots(
            self):
        self._test_pool_maintenance(desired_slots_free=3, expected=3)

    def test_vm_based_hosting_device_marginal_slot_surplus_no_change(self):
        self._test_pool_maintenance(desired_slots_free=5, expected=6)

    def test_hw_based_hosting_device_no_change(self):
        self._test_pool_maintenance(host_category=HW_CATEGORY, expected=6)
