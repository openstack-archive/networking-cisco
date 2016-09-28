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

import mock

from neutron.tests import base

from neutron_lib import exceptions as n_exc

from networking_cisco.plugins.cisco.device_manager.plugging_drivers.\
    vif_hotplug_plugging_driver import(VIFHotPlugPluggingDriver)


class TestVIFHotPlugPluggingDriver(base.BaseTestCase):

    def setUp(self):
        super(TestVIFHotPlugPluggingDriver, self).setUp()

    def test_delete_resource_port_fail_always(self):
        mgmt_port_id = 'fake_port_id'
        mocked_plugin = mock.MagicMock()
        mock_ctx = mock.MagicMock()
        mocked_plugin.delete_port = mock.MagicMock(
            side_effect=n_exc.NeutronException)

        with mock.patch.object(VIFHotPlugPluggingDriver, '_core_plugin') as (
                plugin):
            plugin.__get__ = mock.MagicMock(return_value=mocked_plugin)
            vif_plugging_driver = VIFHotPlugPluggingDriver()
            self.assertRaises(
                n_exc.NeutronException,
                vif_plugging_driver._delete_resource_port,
                mock_ctx,
                mgmt_port_id)

    def test_delete_resource_port_fail_only_twice(self):
        mgmt_port_id = 'fake_port_id'
        mocked_plugin = mock.MagicMock()
        mock_ctx = mock.MagicMock()
        mocked_plugin.delete_port = mock.MagicMock(
            side_effect=[n_exc.NeutronException, n_exc.NeutronException,
                         mock.Mock])
        with mock.patch.object(VIFHotPlugPluggingDriver,
                               '_core_plugin') as plugin:
            plugin.__get__ = mock.MagicMock(return_value=mocked_plugin)
            vif_plugging_driver = VIFHotPlugPluggingDriver()
            vif_plugging_driver._delete_resource_port(mock_ctx, mgmt_port_id)
            self.assertEqual(3, mocked_plugin.delete_port.call_count)

    def test_delete_resource_port_handle_port_not_found(self):
        mgmt_port_id = 'fake_port_id'
        mocked_plugin = mock.MagicMock()
        mock_ctx = mock.MagicMock()
        mocked_plugin.delete_port = mock.MagicMock(
            side_effect=n_exc.PortNotFound(port_id=mgmt_port_id))
        with mock.patch.object(VIFHotPlugPluggingDriver,
                               '_core_plugin') as plugin:
            plugin.__get__ = mock.MagicMock(return_value=mocked_plugin)
            vif_plugging_driver = VIFHotPlugPluggingDriver()
            vif_plugging_driver._delete_resource_port(mock_ctx, mgmt_port_id)
            self.assertEqual(1, mocked_plugin.delete_port.call_count)

    @mock.patch.object(VIFHotPlugPluggingDriver, '_dev_mgr')
    def test_setup_logical_port_connectivity(self, mock_svc_vm_mgr):
        hosting_port_obj = mock.MagicMock(id='hosting_port_id')
        hosting_info_obj = mock.MagicMock(hosting_port=hosting_port_obj)
        mock_portdb = mock.MagicMock(hosting_info=hosting_info_obj)

        hosting_device_id = 'fake_hosting_device_id'
        mocked_plugin = mock.MagicMock()
        mock_ctx = mock.MagicMock()
        with mock.patch.object(VIFHotPlugPluggingDriver,
                               '_core_plugin') as plugin:
            plugin.__get__ = mock.MagicMock(return_value=mocked_plugin)
            vif_plugging_driver = VIFHotPlugPluggingDriver()
            vif_plugging_driver.setup_logical_port_connectivity(
                mock_ctx, mock_portdb, hosting_device_id)
            vif_plugging_driver._dev_mgr.svc_vm_mgr.interface_attach\
                .assert_called_once_with(hosting_device_id,
                mock_portdb.hosting_info.hosting_port.id)

    def test_create_hosting_device_resources(self):
        complementary_id = 'fake_complementary_id'
        tenant_id = 'fake_tenantid'
        mgmt_context = {'mgmt_nw_id': 'fake_mgmt_nw_id',
                        'mgmt_sec_grp_id': 'fake_mgmt_sec_grp_id'}
        max_hosted = 'fake_max_hosted'
        mocked_plugin = mock.MagicMock()
        mock_ctx = mock.MagicMock()
        with mock.patch.object(VIFHotPlugPluggingDriver,
                               '_core_plugin') as plugin:
            plugin.__get__ = mock.MagicMock(return_value=mocked_plugin)
            vif_plugging_driver = VIFHotPlugPluggingDriver()
            vif_plugging_driver.create_hosting_device_resources(
                mock_ctx, complementary_id, tenant_id, mgmt_context,
                max_hosted)
            self.assertEqual(True, mocked_plugin.create_port.called)
            self.assertEqual(1, mocked_plugin.create_port.call_count)

    def test_create_hosting_device_resources_exception(self):
        complementary_id = 'fake_complementary_id'
        tenant_id = 'fake_tenantid'
        mgmt_context = {'mgmt_nw_id': 'fake_mgmt_nw_id',
                        'mgmt_sec_grp_id': 'fake_mgmt_sec_grp_id'}
        max_hosted = 'fake_max_hosted'
        mock_delete_resources = mock.MagicMock()
        mocked_plugin = mock.MagicMock()
        mocked_plugin.create_port = mock.MagicMock(
            side_effect=n_exc.NeutronException)

        mock_ctx = mock.MagicMock()
        with mock.patch.object(VIFHotPlugPluggingDriver,
                               '_core_plugin') as plugin:
            plugin.__get__ = mock.MagicMock(return_value=mocked_plugin)
            vif_plugging_driver = VIFHotPlugPluggingDriver()
            vif_plugging_driver.delete_hosting_device_resources = (
                mock_delete_resources)
            result = vif_plugging_driver.create_hosting_device_resources(
                mock_ctx, complementary_id, tenant_id, mgmt_context,
                max_hosted)
            self.assertEqual(True, mocked_plugin.create_port.called)
            self.assertEqual(1, mocked_plugin.create_port.call_count)
            self.assertEqual(True, mock_delete_resources.called)
            self.assertEqual(1, mock_delete_resources.call_count)
            self.assertIsNone(result['mgmt_port'])
            self.assertEqual([], result['ports'])
