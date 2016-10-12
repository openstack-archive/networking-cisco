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

import copy

import mock
from oslo_utils import uuidutils
from webob import exc

from networking_cisco import backwards_compatibility as bc
from networking_cisco.plugins.cisco.common import utils
from networking_cisco.plugins.cisco.extensions import routertype

from neutron.tests import base
from neutron.tests.unit.api.v2 import test_base
from neutron.tests.unit.extensions import base as test_extensions_base


_uuid = uuidutils.generate_uuid
_get_path = test_base._get_path


class RouterTypeTestCase(test_extensions_base.ExtensionTestCase):
    fmt = 'json'

    def setUp(self):
        super(RouterTypeTestCase, self).setUp()
        # NOTE(bobmel): The routertype extension is for the router service. We
        # therefore add 'router' to supported extensions of the core plugin
        # used in these test. That way, NeutronManager will return that plugin
        # as the l3 router service plugin.
        self._setUpExtension(
            'networking_cisco.plugins.cisco.extensions.routertype.'
            'RoutertypePluginBase',
            None, routertype.RESOURCE_ATTRIBUTE_MAP, routertype.Routertype, '',
            supported_extension_aliases=['router',
                                         routertype.ROUTERTYPE_ALIAS])

    def test_create_routertype(self):
        dummy_driver = ('networking_cisco.plugins.cisco.l3.schedulers.'
                        'noop_l3_router_hosting_device_scheduler.'
                        'NoopL3RouterHostingDeviceScheduler')
        rt_id = _uuid()
        tenant_id = _uuid()
        data = {'routertype': {
            'id': None,
            'tenant_id': tenant_id,
            'name': 'Fancy router type 1',
            'description': 'Lightning fast router type',
            'template_id': _uuid(),
            'ha_enabled_by_default': False,
            'shared': True,
            'slot_need': 200,
            'scheduler': dummy_driver,
            'driver': dummy_driver,
            'cfg_agent_service_helper': dummy_driver,
            'cfg_agent_driver': dummy_driver}}

        if bc.NEUTRON_VERSION >= bc.NEUTRON_NEWTON_VERSION:
            data['routertype']['project_id'] = tenant_id

        return_value = copy.copy(data['routertype'])
        return_value.update({'id': rt_id})

        instance = self.plugin.return_value
        instance.create_routertype.return_value = return_value
        res = self.api.post(_get_path('routertypes', fmt=self.fmt),
                            self.serialize(data),
                            content_type='application/%s' % self.fmt)
        instance.create_routertype.assert_called_with(mock.ANY,
                                                      routertype=data)
        self.assertEqual(res.status_int, exc.HTTPCreated.code)
        res = self.deserialize(res)
        self.assertIn('routertype', res)
        self.assertEqual(res['routertype'], return_value)

    def test_routertype_list(self):
        rt_id = _uuid()
        return_value = [{'tenant_id': _uuid(),
                         'id': rt_id}]

        instance = self.plugin.return_value
        instance.get_routertypes.return_value = return_value

        res = self.api.get(_get_path('routertypes', fmt=self.fmt))

        instance.get_routertypes.assert_called_with(mock.ANY, fields=mock.ANY,
                                                    filters=mock.ANY)
        self.assertEqual(res.status_int, exc.HTTPOk.code)

    def test_routertype_get(self):
        rt_id = _uuid()
        return_value = {'tenant_id': _uuid(),
                        'id': rt_id}

        instance = self.plugin.return_value
        instance.get_routertype.return_value = return_value

        res = self.api.get(_get_path('routertypes',
                                     id=rt_id, fmt=self.fmt))

        instance.get_routertype.assert_called_with(mock.ANY, rt_id,
                                                   fields=mock.ANY)
        self.assertEqual(res.status_int, exc.HTTPOk.code)
        res = self.deserialize(res)
        self.assertIn('routertype', res)
        self.assertEqual(res['routertype'], return_value)

    def test_routertype_update(self):
        rt_id = _uuid()
        update_data = {'routertype': {'name': 'Even fancier router type'}}
        return_value = {'tenant_id': _uuid(), 'id': rt_id}

        instance = self.plugin.return_value
        instance.update_routertype.return_value = return_value

        res = self.api.put(_get_path('routertypes', id=rt_id, fmt=self.fmt),
                           self.serialize(update_data))

        instance.update_routertype.assert_called_with(
            mock.ANY, rt_id, routertype=update_data)
        self.assertEqual(res.status_int, exc.HTTPOk.code)
        res = self.deserialize(res)
        self.assertIn('routertype', res)
        self.assertEqual(res['routertype'], return_value)

    def test_routertype_delete(self):
        self._test_entity_delete('routertype')


class TestRouterTypeAttributeValidators(base.BaseTestCase):

    def test_convert_validate_driver(self):
        drv = ('networking_cisco.plugins.cisco.cfg_agent.device_drivers.'
               'dummy_driver.DummyRoutingDriver')
        res = utils.convert_validate_driver_class(drv)
        self.assertEqual(res, drv)

        self.assertRaises(utils.DriverNotFound,
                          utils.convert_validate_driver_class,
                          'this.is.not.a.driver')
