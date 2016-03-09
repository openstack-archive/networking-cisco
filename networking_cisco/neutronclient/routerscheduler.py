# Copyright 2015 Cisco Systems.
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

from __future__ import print_function

from networking_cisco._i18n import _

from neutronclient.common import extension
from neutronclient.neutron import v2_0 as neutronV20
from neutronclient.neutron.v2_0 import router

from networking_cisco.neutronclient import hostingdevice


R_RESOURCE = 'router'
DEVICE_L3_ROUTERS = '/hosting-device-l3-routers'


class RoutersOnHostingDevice(extension.NeutronClientExtension):
    resource = R_RESOURCE
    resource_plural = '%ss' % resource
    object_path = '/%s' % resource_plural
    resource_path = '/%s/%%s' % resource_plural
    versions = ['2.0']
    allow_names = True


class AddRouterToHostingDevice(extension.ClientExtensionCreate,
                               RoutersOnHostingDevice):
    """Add a router to hosting device."""

    shell_command = 'cisco-hosting-device-router-add'

    def get_parser(self, prog_name):
        parser = super(AddRouterToHostingDevice, self).get_parser(prog_name)
        parser.add_argument(
            'hosting_device',
            help=_('Name or id of the hosting device.'))
        parser.add_argument(
            'router',
            help=_('Name or id of router to add.'))
        return parser

    def execute(self, parsed_args):
        self.log.debug('run(%s)' % parsed_args)
        neutron_client = self.get_client()
        neutron_client.format = parsed_args.request_format
        _id_hd = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, 'hosting_device', parsed_args.hosting_device)
        _id_r = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, 'router', parsed_args.router)
        self.add_router_to_hosting_device(neutron_client, _id_hd,
                                          {'router_id': _id_r})
        print(_('Added router \'%(router)s\' to hosting device \'%(hd)s\'') % {
            'router': parsed_args.router, 'hd': parsed_args.hosting_device},
            file=self.app.stdout, end='')
        return [], []

    def add_router_to_hosting_device(self, client, hosting_device_id, body):
        """Adds a router to hosting device."""
        res_path = hostingdevice.HostingDevice.resource_path
        return client.post((res_path + DEVICE_L3_ROUTERS) %
                           hosting_device_id, body=body)


class RemoveRouterFromHostingDevice(extension.ClientExtensionCreate,
                                    RoutersOnHostingDevice):
    """Remove a router from Hosting Device."""

    shell_command = 'cisco-hosting-device-router-remove'

    def get_parser(self, prog_name):
        parser = super(RemoveRouterFromHostingDevice, self).get_parser(
            prog_name)
        parser.add_argument(
            'hosting_device',
            help=_('Name or id of the hosting device.'))
        parser.add_argument(
            'router',
            help=_('Name or id of router to remove.'))
        return parser

    def execute(self, parsed_args):
        self.log.debug('run(%s)' % parsed_args)
        neutron_client = self.get_client()
        neutron_client.format = parsed_args.request_format
        _id_hd = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, 'hosting_device', parsed_args.hosting_device)
        _id_r = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, 'router', parsed_args.router)
        self.remove_router_from_hosting_device(neutron_client, _id_hd, _id_r)
        print(_('Removed router \'%(router)s\' from hosting device \'%(hd)s\'')
              % {'router': parsed_args.router,
                 'hd': parsed_args.hosting_device}, file=self.app.stdout,
              end='')
        return [], []

    def remove_router_from_hosting_device(self, client, hosting_device_id,
                                          router_id):
        """Remove a router from hosting_device."""
        res_path = hostingdevice.HostingDevice.resource_path
        return client.delete((res_path + DEVICE_L3_ROUTERS + "/%s") % (
            hosting_device_id, router_id))


class RoutersOnHostingDeviceList(extension.ClientExtensionList,
                                 RoutersOnHostingDevice):

    shell_command = 'cisco-hosting-device-list-hosted-routers'
    _formatters = {'external_gateway_info':
                   router._format_external_gateway_info}
    list_columns = ['id', 'name', 'external_gateway_info']

    def get_parser(self, prog_name):
        parser = super(RoutersOnHostingDeviceList, self).get_parser(prog_name)
        parser.add_argument(
            'hosting_device',
            help=_('Name or id of the hosting device to query.'))
        return parser

    def call_server(self, neutron_client, search_opts, parsed_args):
        _id = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, 'hosting_device', parsed_args.hosting_device)
        data = self.list_routers_on_hosting_device(neutron_client, _id,
                                                   **search_opts)
        return data

    def list_routers_on_hosting_device(self, client, hosting_device_id,
                                       **_params):
        """Fetches a list of routers hosted on a hosting device."""
        res_path = hostingdevice.HostingDevice.resource_path
        return client.get((res_path + DEVICE_L3_ROUTERS) %
                          hosting_device_id, params=_params)


HD_RESOURCE = 'hosting_device'
L3_ROUTER_DEVICES = '/l3-router-hosting-devices'


class HostingDeviceHostingRouter(extension.NeutronClientExtension):
    resource = HD_RESOURCE
    resource_plural = '%ss' % resource
    object_path = '/%s' % resource_plural
    resource_path = '/%s/%%s' % resource_plural
    versions = ['2.0']
    allow_names = True


class HostingDeviceHostingRouterList(extension.ClientExtensionList,
                                     HostingDeviceHostingRouter):

    shell_command = 'cisco-router-list-hosting-devices'
    list_columns = ['id', 'name', 'status', 'admin_state_up', 'template_id']

    def get_parser(self, prog_name):
        parser = super(HostingDeviceHostingRouterList, self).get_parser(
            prog_name)
        parser.add_argument('router',
                            help=_('Name or id of router to query.'))
        return parser

    def call_server(self, neutron_client, search_opts, parsed_args):
        _id = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, 'router', parsed_args.router)
        data = self.list_hosting_devices_hosting_routers(neutron_client, _id,
                                                         **search_opts)
        return data

    def list_hosting_devices_hosting_routers(self, client, router_id,
                                             **_params):
        """Fetches a list of hosting devices hosting a router."""
        return client.get((client.router_path + L3_ROUTER_DEVICES) %
                          router_id, params=_params)
