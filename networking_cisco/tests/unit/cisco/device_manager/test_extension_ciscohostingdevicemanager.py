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
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.common import utils
from networking_cisco.plugins.cisco.extensions import ciscohostingdevicemanager

from neutron.tests import base
from neutron.tests.unit.api.v2 import test_base
from neutron.tests.unit.extensions import base as test_extensions_base

_uuid = uuidutils.generate_uuid
_get_path = test_base._get_path


class CiscoHostingDeviceManagerTestCase(
    test_extensions_base.ExtensionTestCase):
    fmt = 'json'

    def setUp(self):
        super(CiscoHostingDeviceManagerTestCase, self).setUp()
        self._setUpExtension(
            'networking_cisco.plugins.cisco.extensions.'
            'ciscohostingdevicemanager.CiscoHostingDevicePluginBase',
            cisco_constants.DEVICE_MANAGER,
            ciscohostingdevicemanager.RESOURCE_ATTRIBUTE_MAP,
            ciscohostingdevicemanager.Ciscohostingdevicemanager, 'dev_mgr')

    def test_create_hosting_device(self):
        hd_id = _uuid()
        data = {'hosting_device': {
            'id': None,
            'tenant_id': _uuid(),
            'template_id': _uuid(),
            'credentials_id': None,
            'name': 'SuperDeviceXYZ',
            'description': 'The latest and greatest device',
            'device_id': 'device_id_string1',
            'admin_state_up': True,
            'management_ip_address': '10.0.100.10',
            'management_port_id': _uuid(),
            'protocol_port': 22,
            'cfg_agent_id': None,
            'tenant_bound': None,
            'auto_delete': True}}

        if bc.NEUTRON_VERSION >= bc.NEUTRON_NEWTON_VERSION:
            data['hosting_device']['project_id'] = (
                               data['hosting_device']['tenant_id'])
        return_value = copy.copy(data['hosting_device'])
        return_value.update({'id': hd_id})

        instance = self.plugin.return_value
        instance.create_hosting_device.return_value = return_value
        res = self.api.post(_get_path('dev_mgr/hosting_devices', fmt=self.fmt),
                            self.serialize(data),
                            content_type='application/%s' % self.fmt)
        instance.create_hosting_device.assert_called_with(mock.ANY,
                                                          hosting_device=data)
        self.assertEqual(res.status_int, exc.HTTPCreated.code)
        res = self.deserialize(res)
        self.assertIn('hosting_device', res)
        self.assertEqual(res['hosting_device'], return_value)

    def test_hosting_device_list(self):
        hd_id = _uuid()
        return_value = [{'tenant_id': _uuid(),
                         'id': hd_id}]

        instance = self.plugin.return_value
        instance.get_hosting_devices.return_value = return_value

        res = self.api.get(_get_path('dev_mgr/hosting_devices', fmt=self.fmt))

        instance.get_hosting_devices.assert_called_with(mock.ANY,
                                                        fields=mock.ANY,
                                                        filters=mock.ANY)
        self.assertEqual(res.status_int, exc.HTTPOk.code)

    def test_hosting_device_get(self):
        hd_id = _uuid()
        return_value = {'tenant_id': _uuid(),
                        'id': hd_id}

        instance = self.plugin.return_value
        instance.get_hosting_device.return_value = return_value

        res = self.api.get(_get_path('dev_mgr/hosting_devices', id=hd_id,
                                     fmt=self.fmt))

        instance.get_hosting_device.assert_called_with(mock.ANY, hd_id,
                                                       fields=mock.ANY)
        self.assertEqual(res.status_int, exc.HTTPOk.code)
        res = self.deserialize(res)
        self.assertIn('hosting_device', res)
        self.assertEqual(res['hosting_device'], return_value)

    def test_hosting_device_update(self):
        hd_id = _uuid()
        update_data = {'hosting_device': {'device_id': 'new_device_id'}}
        return_value = {'tenant_id': _uuid(), 'id': hd_id}

        instance = self.plugin.return_value
        instance.update_hosting_device.return_value = return_value

        res = self.api.put(_get_path('dev_mgr/hosting_devices', id=hd_id,
                                     fmt=self.fmt),
                           self.serialize(update_data))

        instance.update_hosting_device.assert_called_with(
            mock.ANY, hd_id, hosting_device=update_data)
        self.assertEqual(res.status_int, exc.HTTPOk.code)
        res = self.deserialize(res)
        self.assertIn('hosting_device', res)
        self.assertEqual(res['hosting_device'], return_value)

    def test_hosting_device_delete(self):
        self._test_entity_delete('hosting_device')

    def test_create_hosting_device_template(self):
        hdt_id = _uuid()
        device_driver = ('networking_cisco.plugins.cisco.device_manager.'
                         'hosting_device_drivers.noop_hd_driver.'
                         'NoopHostingDeviceDriver')
        plugging_driver = ('networking_cisco.plugins.cisco.device_manager.'
                           'plugging_drivers.noop_plugging_driver.'
                           'NoopPluggingDriver')
        data = {'hosting_device_template': {
            'id': None,
            'tenant_id': _uuid(),
            'name': 'HostingDeviceTemplate1',
            'enabled': True,
            'host_category': ciscohostingdevicemanager.VM_CATEGORY,
            'service_types': 'router:firewall:vpn',
            'image': None,
            'flavor': None,
            'default_credentials_id': _uuid(),
            'configuration_mechanism': None,
            'protocol_port': 22,
            'booting_time': 10,
            'slot_capacity': 5000,
            'desired_slots_free': 300,
            'tenant_bound': [_uuid(), _uuid(), _uuid()],
            'device_driver': device_driver,
            'plugging_driver': plugging_driver}}

        if bc.NEUTRON_VERSION >= bc.NEUTRON_NEWTON_VERSION:
            data['hosting_device_template']['project_id'] = (
                               data['hosting_device_template']['tenant_id'])
        return_value = copy.copy(data['hosting_device_template'])
        return_value.update({'id': hdt_id})

        instance = self.plugin.return_value
        instance.create_hosting_device_template.return_value = return_value
        res = self.api.post(_get_path('dev_mgr/hosting_device_templates',
                                      fmt=self.fmt),
                            self.serialize(data),
                            content_type='application/%s' % self.fmt)
        instance.create_hosting_device_template.assert_called_with(
            mock.ANY, hosting_device_template=data)
        self.assertEqual(res.status_int, exc.HTTPCreated.code)
        res = self.deserialize(res)
        self.assertIn('hosting_device_template', res)
        self.assertEqual(res['hosting_device_template'], return_value)

    def test_hosting_device_template_list(self):
        hdt_id = _uuid()
        return_value = [{'tenant_id': _uuid(),
                         'id': hdt_id}]

        instance = self.plugin.return_value
        instance.get_hosting_device_templates.return_value = return_value

        res = self.api.get(_get_path('dev_mgr/hosting_device_templates',
                                     fmt=self.fmt))

        instance.get_hosting_device_templates.assert_called_with(
            mock.ANY, fields=mock.ANY, filters=mock.ANY)
        self.assertEqual(res.status_int, exc.HTTPOk.code)

    def test_hosting_device_template_get(self):
        hdt_id = _uuid()
        return_value = {'tenant_id': _uuid(),
                        'id': hdt_id}

        instance = self.plugin.return_value
        instance.get_hosting_device_template.return_value = return_value

        res = self.api.get(_get_path('dev_mgr/hosting_device_templates',
                                     id=hdt_id, fmt=self.fmt))

        instance.get_hosting_device_template.assert_called_with(
            mock.ANY, hdt_id, fields=mock.ANY)
        self.assertEqual(res.status_int, exc.HTTPOk.code)
        res = self.deserialize(res)
        self.assertIn('hosting_device_template', res)
        self.assertEqual(res['hosting_device_template'], return_value)

    def test_hosting_device_template_update(self):
        hdt_id = _uuid()
        update_data = {'hosting_device_template': {'name': 'new_name'}}
        return_value = {'tenant_id': _uuid(), 'id': hdt_id}

        instance = self.plugin.return_value
        instance.update_hosting_device_template.return_value = return_value

        res = self.api.put(_get_path('dev_mgr/hosting_device_templates',
                                     id=hdt_id, fmt=self.fmt),
                           self.serialize(update_data))

        instance.update_hosting_device_template.assert_called_with(
            mock.ANY, hdt_id, hosting_device_template=update_data)
        self.assertEqual(res.status_int, exc.HTTPOk.code)
        res = self.deserialize(res)
        self.assertIn('hosting_device_template', res)
        self.assertEqual(res['hosting_device_template'], return_value)

    def test_hosting_device_template_delete(self):
        self._test_entity_delete('hosting_device_template')


class TestCiscoHostingDeviceManagerAttributeValidators(base.BaseTestCase):

    def test_convert_validate_port_value(self):
        msg = ciscohostingdevicemanager.convert_validate_port_value(None)
        self.assertIsNone(msg)

        msg = ciscohostingdevicemanager.convert_validate_port_value('10')
        self.assertEqual(msg, 10)

        self.assertRaises(
            ciscohostingdevicemanager.HostingDeviceInvalidPortValue,
            ciscohostingdevicemanager.convert_validate_port_value,
            '-10')

        self.assertRaises(
            ciscohostingdevicemanager.HostingDeviceInvalidPortValue,
            ciscohostingdevicemanager.convert_validate_port_value,
            '90000')

        self.assertRaises(
            ciscohostingdevicemanager.HostingDeviceInvalidPortValue,
            ciscohostingdevicemanager.convert_validate_port_value,
            'not a port number')

    def test_convert_validate_driver(self):
        drv = ('networking_cisco.plugins.cisco.device_manager.plugging_drivers'
               '.noop_plugging_driver.NoopPluggingDriver')
        res = utils.convert_validate_driver_class(drv)
        self.assertEqual(res, drv)

        self.assertRaises(
            utils.DriverNotFound, utils.convert_validate_driver_class,
            'this.is.not.a.driver')
