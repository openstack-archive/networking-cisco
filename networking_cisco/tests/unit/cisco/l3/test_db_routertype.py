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

from oslo_config import cfg
from oslo_log import log as logging
import six
import webob.exc

from networking_cisco._i18n import _LE

from neutron.common import exceptions as n_exc
from neutron import context as n_context
from neutron import manager
from neutron.plugins.common import constants
from neutron.tests.unit.db import test_db_base_plugin_v2

from neutron_lib import constants as n_const

import networking_cisco
from networking_cisco import backwards_compatibility as bc
from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)
from networking_cisco.plugins.cisco.db.device_manager import (
    hosting_device_manager_db as hdm_db)
from networking_cisco.plugins.cisco.extensions import (
    ciscohostingdevicemanager as ciscodevmgr)
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routertype
from networking_cisco.tests.unit.cisco.device_manager import (
    device_manager_test_support)
from networking_cisco.tests.unit.cisco.device_manager.test_db_device_manager \
    import DeviceManagerTestCaseMixin
from networking_cisco.tests.unit.cisco.l3 import l3_router_test_support

LOG = logging.getLogger(__name__)


policy_path = (os.path.abspath(networking_cisco.__path__[0]) +
               '/../etc/policy.json')

CORE_PLUGIN_KLASS = device_manager_test_support.CORE_PLUGIN_KLASS
L3_PLUGIN_KLASS = l3_router_test_support.L3_PLUGIN_KLASS

NS_ROUTERTYPE_NAME = c_constants.NAMESPACE_ROUTER_TYPE
VM_ROUTERTYPE_NAME = c_constants.CSR1KV_ROUTER_TYPE
HW_ROUTERTYPE_NAME = "HW_router"

NOOP_SCHEDULER = ('networking_cisco.plugins.cisco.l3.schedulers.'
                  'noop_l3_router_hosting_device_scheduler.'
                  'NoopL3RouterHostingDeviceScheduler')
NOOP_RT_DRIVER = ('networking_cisco.plugins.cisco.l3.drivers.'
                  'noop_routertype_driver.NoopL3RouterDriver')
NOOP_AGT_SVC_HELPER = NOOP_SCHEDULER
NOOP_AGT_DRV = NOOP_SCHEDULER

TEST_SLOT_NEED = 2

RT_SETTINGS = {
    NS_ROUTERTYPE_NAME: {
        'slot_need': 0,
        'scheduler': NOOP_SCHEDULER,
        'router_type_driver': NOOP_RT_DRIVER,
        'cfg_agent_driver': NOOP_AGT_DRV},
    VM_ROUTERTYPE_NAME: {
        'slot_need': TEST_SLOT_NEED,
        'scheduler': 'networking_cisco.plugins.cisco.l3.schedulers.'
                     'l3_router_hosting_device_scheduler.'
                     'L3RouterHostingDeviceLongestRunningScheduler',
        'driver': NOOP_RT_DRIVER,
        'cfg_agent_service_helper': NOOP_AGT_SVC_HELPER,
        'cfg_agent_driver': NOOP_AGT_DRV},
    HW_ROUTERTYPE_NAME: {
        'slot_need': 200,
        'scheduler': 'networking_cisco.plugins.cisco.l3.schedulers.'
                     'l3_router_hosting_device_scheduler.'
                     'L3RouterHostingDeviceRandomScheduler',
        'driver': NOOP_RT_DRIVER,
        'cfg_agent_service_helper': NOOP_AGT_SVC_HELPER,
        'cfg_agent_driver': NOOP_AGT_DRV}}


class RoutertypeTestCaseMixin(object):

    def _create_routertype(self, fmt, template_id, name, slot_need,
                           expected_res_status=None, **kwargs):
        data = self._get_test_routertype_attr(template_id=template_id,
                                              name=name, slot_need=slot_need,
                                              **kwargs)
        data.update({'tenant_id': kwargs.get('tenant_id', self._tenant_id)})
        data = {'routertype': data}
        rt_req = self.new_create_request('routertypes', data, fmt)
        if kwargs.get('set_context') and 'tenant_id' in kwargs:
            # create a specific auth context for this request
            rt_req.environ['neutron.context'] = n_context.Context(
                '', kwargs['tenant_id'])
        hd_res = rt_req.get_response(self.ext_api)
        if expected_res_status:
            self.assertEqual(hd_res.status_int, expected_res_status)
        return hd_res

    @contextlib.contextmanager
    def routertype(self, template_id, name='router type 1',
                   slot_need=TEST_SLOT_NEED, fmt=None, no_delete=False,
                   **kwargs):
        if not fmt:
            fmt = self.fmt
        res = self._create_routertype(fmt, template_id, name, slot_need,
                                      **kwargs)
        if res.status_int >= 400:
            raise webob.exc.HTTPClientError(code=res.status_int)
        routertype = self.deserialize(fmt or self.fmt, res)
        yield routertype
        if not no_delete:
            self._delete('routertypes', routertype['routertype']['id'])

    def _get_test_routertype_attr(self, template_id, name='router type 1',
                                  slot_need=TEST_SLOT_NEED, **kwargs):
        data = {
            'name': name,
            'description': kwargs.get('description'),
            'template_id': template_id,
            'ha_enabled_by_default': kwargs.get('ha_enabled_by_default',
                                                False),
            'shared': kwargs.get('shared', True),
            'slot_need': slot_need,
            'scheduler': kwargs.get('scheduler', NOOP_SCHEDULER),
            'driver': NOOP_RT_DRIVER,
            'cfg_agent_service_helper': NOOP_AGT_SVC_HELPER,
            'cfg_agent_driver': kwargs.get('cfg_agent_driver', NOOP_AGT_DRV)}
        return data

    def _get_non_admin_routertype_attr(self, template_id, name='router type 1',
                                       slot_need=TEST_SLOT_NEED, **kwargs):
        subset = {'id', 'name', 'description', 'tenant_id',
                  'ha_enabled_by_default'}
        attr_dict = self._get_test_routertype_attr(template_id, name,
                                                   slot_need, **kwargs)
        return {kv[0]: kv[1] for kv in attr_dict.items() if kv[0] in subset}

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
        self.assertEqual(sorted([i['id'] for i in res[resource_plural]]),
                         sorted([i[resource]['id'] for i in items]))

    def _test_create_routertypes(self, mappings=None):
        if mappings is None:
            mappings = {}
        for mapping in mappings:
            template = mapping['template']
            if template is None:
                self._routertypes[mapping['router_type']] = None
            else:
                routertype_name = mapping['router_type']
                self._create_routertype(
                    self.fmt, template['hosting_device_template']['id'],
                    routertype_name,
                    RT_SETTINGS[routertype_name]['slot_need'],
                    scheduler=RT_SETTINGS[routertype_name]['scheduler'],
                    ha_enabled_by_default=self._is_ha_tests)

    def _test_remove_routertypes(self, delete_routers=True):
        if delete_routers:
            auto_deleted_router_ids = set()
            routers = self._list('routers')['routers']
            for r in routers:
                # Exclude any redundancy routers as they are removed
                # automatically when removing the user visible router
                for rr_info in r.get(
                        ha.DETAILS,
                        {ha.REDUNDANCY_ROUTERS: []})[ha.REDUNDANCY_ROUTERS]:
                    auto_deleted_router_ids.add(rr_info['id'])
            for r in routers:
                if r['id'] in auto_deleted_router_ids:
                    continue
                # Remove any static routes
                if r.get('routes'):
                    self._update('routers', r['id'],
                                 {'router': {'routes': None}})
                # Remove any floatingips using the router
                for fip in self._list(
                        'floatingips',
                        query_params='router_id=%s' % r['id'])['floatingips']:
                    try:
                        self._delete('floatingips', fip['id'])
                    except n_exc.NeutronException as e:
                        # since this is a cleanup after a UT execution we
                        # just log it and then ignore it. The subsequent router
                        # delete should anyway capture more serious errors.
                        LOG.error(_LE('Encountered error during router clean '
                                      'up: '), e)
                # Remove any router interfaces
                for p in self._list(
                        'ports',
                        query_params='device_id=%s&device_owner=%s' % (
                            r['id'],
                            n_const.DEVICE_OWNER_ROUTER_INTF))['ports']:
                    # get_ports can be mocked in some tests so we need to
                    # ensure we get a port that is indeed a router port.
                    try:
                        if (p.get('device_owner') ==
                                n_const.DEVICE_OWNER_ROUTER_INTF and
                                'fixed_ips' in p and 'id' in p):
                            req = self.new_action_request(
                                'routers', {'port_id': p['id']}, r['id'],
                                "remove_router_interface")
                            req.get_response(self.ext_api)
                    except n_exc.NeutronException as e:
                        # since this is a cleanup after a UT execution we
                        # just log it and then ignore it. The subsequent router
                        # delete should anyway capture more serious errors
                        LOG.error(_LE('Encountered error during router clean '
                                      'up: '), e)
                # Remove the router, we don't capture any exceptions here as
                # that may hide real bugs
                self._delete('routers', r['id'])
        for rt in self._list('routertypes')['routertypes']:
            # we don't capture any exceptions here as that may hide real bugs
            self._delete('routertypes', rt['id'])


class L3TestRoutertypeExtensionManager(
        l3_router_test_support.TestL3RouterBaseExtensionManager):

    def get_resources(self):
        # most of the resources are added in our super class
        res = super(L3TestRoutertypeExtensionManager, self).get_resources()
        ext_mgr = (device_manager_test_support.
                   TestDeviceManagerExtensionManager())
        for item in ext_mgr.get_resources():
            res.append(item)
        return res


class TestRoutertypeDBPlugin(test_db_base_plugin_v2.NeutronDbPluginV2TestCase,
                             RoutertypeTestCaseMixin,
                             DeviceManagerTestCaseMixin):

    hdm_db.HostingDeviceManagerMixin.path_prefix = "/dev_mgr"
    resource_prefix_map = dict(
        (k, "/dev_mgr")
        for k in ciscodevmgr.RESOURCE_ATTRIBUTE_MAP.keys())

    def setUp(self, core_plugin=None, l3_plugin=None,
              dm_plugin=None, ext_mgr=None):
        if not core_plugin:
            core_plugin = CORE_PLUGIN_KLASS
        if l3_plugin is None:
            l3_plugin = L3_PLUGIN_KLASS
        service_plugins = {'l3_plugin_name': l3_plugin}
        if dm_plugin is not None:
            service_plugins['dm_plugin_name'] = dm_plugin
        cfg.CONF.set_override('api_extensions_path',
                              l3_router_test_support.extensions_path)
        if not ext_mgr:
            ext_mgr = L3TestRoutertypeExtensionManager()
        super(TestRoutertypeDBPlugin, self).setUp(
            plugin=core_plugin, service_plugins=service_plugins,
            ext_mgr=ext_mgr)
        self.l3_plugin = manager.NeutronManager.get_service_plugins()[
            constants.L3_ROUTER_NAT]
        # Ensure we use policy definitions from our repo
        cfg.CONF.set_override('policy_file', policy_path, 'oslo_policy')

    def test_create_routertype(self):
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            attrs = self._get_test_routertype_attr(hdt_id)
            with self.routertype(hdt_id) as rt:
                for k, v in six.iteritems(attrs):
                    self.assertEqual(rt['routertype'][k], v)

    def test_show_routertype(self):
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            attrs = self._get_test_routertype_attr(hdt_id)
            with self.routertype(hdt_id) as rt:
                req = self.new_show_request('routertypes',
                                            rt['routertype']['id'],
                                            fmt=self.fmt)
                res = self.deserialize(self.fmt,
                                       req.get_response(self.ext_api))
                for k, v in six.iteritems(attrs):
                    self.assertEqual(res['routertype'][k], v)

    def test_show_routertype_non_admin(self):
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            tenant_id = hdt['hosting_device_template']['tenant_id']
            with self.routertype(hdt_id) as rt:
                rt_id = rt['routertype']['id']
                non_admin_ctx = n_context.Context('', tenant_id)
                req = self._req('GET', 'routertypes', None, self.fmt, id=rt_id,
                                context=non_admin_ctx)
                res = self.deserialize(self.fmt,
                                       req.get_response(self.ext_api))
                attrs = self._get_non_admin_routertype_attr(hdt_id)
                attrs['id'] = rt_id
                attrs['tenant_id'] = tenant_id
                if bc.NEUTRON_VERSION >= bc.NEUTRON_NEWTON_VERSION:
                    attrs['project_id'] = tenant_id
                self.assertEqual(len(res['routertype']), len(attrs))
                for k, v in six.iteritems(attrs):
                    self.assertEqual(res['routertype'][k], v)

    def test_list_routertypes(self):
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            with self.routertype(hdt_id, 'rt1') as rt1,\
                    self.routertype(hdt_id, 'rt2') as rt2,\
                    self.routertype(hdt_id, 'rt3') as rt3:
                self._test_list_resources('routertype', [rt1, rt2, rt3],
                                          query_params='template_id=' + hdt_id)

    def test_update_routertype(self):
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            new_name = 'new_name_1'
            attrs = self._get_test_routertype_attr(hdt_id)
            attrs['name'] = new_name
            with self.routertype(hdt_id) as rt:
                rt_id = rt['routertype']['id']
                data = {'routertype': {'name': new_name}}
                req = self.new_update_request('routertypes', data, rt_id)
                res = self.deserialize(self.fmt,
                                       req.get_response(self.ext_api))
                for k, v in six.iteritems(attrs):
                    self.assertEqual(res['routertype'][k], v)

    def test_delete_routertype(self):
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            with self.routertype(hdt_id, no_delete=True) as rt:
                rt_id = rt['routertype']['id']
                req = self.new_delete_request('routertypes', rt_id)
                res = req.get_response(self.ext_api)
                self.assertEqual(res.status_int, 204)
                ctx = n_context.get_admin_context()
                self.assertRaises(routertype.RouterTypeNotFound,
                                  self.l3_plugin.get_routertype, ctx, rt_id)

    def test_routertype_policy(self):
        with self.hosting_device_template() as hdt:
            hdt_id = hdt['hosting_device_template']['id']
            tenant_id = hdt['hosting_device_template']['tenant_id']
            with self.routertype(hdt_id) as rt:
                rt_id = rt['routertype']['id']
                non_admin_ctx = n_context.Context('', tenant_id)
                # create fails
                self._create_routertype(
                    self.fmt, hdt_id, 'fast_routers', 10,
                    webob.exc.HTTPForbidden.code, tenant_id=tenant_id,
                    set_context=True)
                # show succeeds
                self._show('routertypes', rt_id,
                           webob.exc.HTTPOk.code, non_admin_ctx)
                # update fails
                self._update('routertypes', rt_id,
                             {'routertype': {'name': 'new_name'}},
                             webob.exc.HTTPForbidden.code, non_admin_ctx)
                # delete fails
                self._delete('routertypes', rt_id,
                             webob.exc.HTTPNotFound.code, non_admin_ctx)
