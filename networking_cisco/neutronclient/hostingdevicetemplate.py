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

from __future__ import print_function

import argparse
import six

from networking_cisco._i18n import _

from neutronclient.common import extension
from neutronclient.neutron import v2_0 as neutronV20


TEMPLATE = 'hosting_device_template'


def _add_updatable_args(parser):
    parser.add_argument(
        '--name',
        help=_('Name of this hosting device template.'))
    parser.add_argument(
        '--disabled',
        dest='enabled',
        action='store_false',
        help=_('Make the hosting device template disabled.'),
        default=argparse.SUPPRESS)
    parser.add_argument(
        '--service-types',
        help=_('Service types supported by this hosting device template.'))
    parser.add_argument(
        '--service_types',
        help=argparse.SUPPRESS)
    parser.add_argument(
        '--image',
        help=_('Glance image used by this hosting device template.'))
    parser.add_argument(
        '--flavor',
        help=_('Nova flavor used by this hosting device template.'))
    parser.add_argument(
        '--credentials-id',
        dest='default_credentials_id',
        help=_('Id of credentials used by default for hosting devices '
               'based on this template.'))
    parser.add_argument(
        '--credentials_id',
        dest='default_credentials_id',
        help=argparse.SUPPRESS)
    parser.add_argument(
        '--config-mechanism',
        dest='configuration_mechanism',
        help=_('Method used to configure hosting devices based on this '
               'template.'))
    parser.add_argument(
        '--config_mechanism',
        dest='configuration_mechanism',
        help=argparse.SUPPRESS)
    parser.add_argument(
        '--protocol-port',
        help=_('TCP/UDP port used for management of hosting devices based on '
               'this template.'))
    parser.add_argument(
        '--protocol_port',
        help=argparse.SUPPRESS)
    parser.add_argument(
        '--booting-time',
        help=_('Typical time to boot hosting devices based on this template.'))
    parser.add_argument(
        '--booting_time',
        help=argparse.SUPPRESS)
    parser.add_argument(
        '--tenant-bound',
        help=_('Tenant allowed place service instances in hosting devices '
               'based on this template.'),
        default=argparse.SUPPRESS)
    parser.add_argument(
        '--tenant_bound',
        help=argparse.SUPPRESS,
        default=argparse.SUPPRESS)


def _updatable_args2body(parsed_args, body):
    neutronV20.update_dict(parsed_args, body[TEMPLATE], [
        'name', 'enabled', 'service_types', 'image', 'flavor',
        'default_credentials_id', 'configuration_mechanism', 'protocol_port',
        'booting_time'])
    # handle tenant_bound separately as we want to allow it to be set to None
    if hasattr(parsed_args, 'tenant_bound'):
        if (isinstance(parsed_args.tenant_bound, six.string_types) and
                parsed_args.tenant_bound.lower() == 'none'):
            parsed_args.tenant_bound = None
        body[TEMPLATE].update({'tenant_bound': parsed_args.tenant_bound})


class HostingDeviceTemplate(extension.NeutronClientExtension):
    resource = TEMPLATE
    resource_plural = '%ss' % resource
    object_path = '/dev_mgr/%s' % resource_plural
    resource_path = '/dev_mgr/%s/%%s' % resource_plural
    versions = ['2.0']
    allow_names = True


class HostingDeviceTemplateList(extension.ClientExtensionList,
                                HostingDeviceTemplate):
    """List hosting device templates that belong to a given tenant."""

    shell_command = 'cisco-hosting-device-template-list'
    list_columns = ['id', 'name', 'host_category', 'service_types',
                    'enabled']
    pagination_support = True
    sorting_support = True


class HostingDeviceTemplateShow(extension.ClientExtensionShow,
                                HostingDeviceTemplate):
    """Show information of a given hosting device template."""

    shell_command = 'cisco-hosting-device-template-show'


class HostingDeviceTemplateCreate(extension.ClientExtensionCreate,
                                  HostingDeviceTemplate):
    """Create a hosting device template for a given tenant."""

    shell_command = 'cisco-hosting-device-template-create'

    def add_known_arguments(self, parser):
        _add_updatable_args(parser)
        parser.add_argument(
            '--id',
            help=_('Id for this hosting device template.'))
        parser.add_argument(
            '--slot-capacity',
            help=_('Capacity (in slots) for hosting devices based on this '
                   'template.'))
        parser.add_argument(
            '--slot_capacity',
            help=argparse.SUPPRESS)
        parser.add_argument(
            '--desired-slots-free',
            help=_('Number of slots to keep available in hosting devices '
                   'based on this template.'))
        parser.add_argument(
            '--desired_slots_free',
            help=argparse.SUPPRESS)
        parser.add_argument(
            '--device-driver',
            help=_('Device driver module to use for hosting devices based on '
                   'this template.'))
        parser.add_argument(
            '--device_driver',
            help=argparse.SUPPRESS)
        parser.add_argument(
            '--plugging-driver',
            help=_('Plugging driver module to use for hosting devices based '
                   'on this template.'))
        parser.add_argument(
            '--plugging_driver',
            help=argparse.SUPPRESS)

        parser.add_argument(
            'name', metavar='NAME',
            help=_('Name of this hosting device template.'))
        parser.add_argument(
            'host_category', metavar='HOST_CATEGORY',
            help=_('Host category for this hosting device template. One of '
                   'VM, Hardware, or, Network_Node.'))

    def args2body(self, parsed_args):
        body = {self.resource: {'name': parsed_args.name,
                                'host_category': parsed_args.host_category}}
        _updatable_args2body(parsed_args, body)
        neutronV20.update_dict(parsed_args, body[self.resource],
                               ['id', 'tenant_id', 'slot_capacity',
                                'desired_slots_free', 'device_driver',
                                'plugging_driver'])
        return body


class HostingDeviceTemplateDelete(extension.ClientExtensionDelete,
                                  HostingDeviceTemplate):
    """Delete a given hosting device template."""

    shell_command = 'cisco-hosting-device-template-delete'


class HostingDeviceTemplateUpdate(extension.ClientExtensionUpdate,
                                  HostingDeviceTemplate):

    """Update hosting device template's information."""

    shell_command = 'cisco-hosting-device-template-update'

    def add_known_arguments(self, parser):
        # adding enable here so that it is available for update only as it is
        # True by default and not meaningful in the create operation
        parser.add_argument(
            '--enabled',
            dest='enabled',
            action='store_true',
            help=_('Make the hosting device template enabled.'),
            default=argparse.SUPPRESS)
        _add_updatable_args(parser)

    def args2body(self, parsed_args):
        body = {self.resource: {}}
        _updatable_args2body(parsed_args, body)
        return body
