# Copyright 2015 Cisco Systems, Inc.
# All rights reserved.
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

from networking_cisco._i18n import _

from neutronclient.common import extension


class NetworkProfile(extension.NeutronClientExtension):
    resource = 'network_profile'
    resource_plural = '%ss' % resource
    object_path = '/%s' % resource_plural
    resource_path = '/%s/%%s' % resource_plural
    versions = ['2.0']
    segment_types = ['vlan', 'overlay']
    segment_sub_types = ['native', 'enhanced']
    allow_names = True


class NetworkProfileList(extension.ClientExtensionList, NetworkProfile):
    """List network profiles that belong to a given tenant."""

    shell_command = 'cisco-network-profile-list'
    list_columns = ['id', 'name', 'segment_type', 'sub_type', 'segment_range',
                    'physical_network', 'multicast_ip_index',
                    'multicast_ip_range']
    pagination_support = True
    sorting_support = True


class NetworkProfileShow(extension.ClientExtensionShow, NetworkProfile):
    """Show information of a given network profile."""

    shell_command = 'cisco-network-profile-show'


class NetworkProfileCreate(extension.ClientExtensionCreate, NetworkProfile):
    """Create a network profile."""

    shell_command = 'cisco-network-profile-create'

    def add_known_arguments(self, parser):
        parser.add_argument('name',
                            help=_('Name for network profile.'))
        parser.add_argument('segment_type',
                            choices=self.segment_types,
                            help='Segment type.')
        parser.add_argument('--sub_type',
                            choices=self.segment_sub_types,
                            help=_('Sub-type for the segment. Available '
                                   'sub-types for overlay segments: '
                                   'native, enhanced.'))
        parser.add_argument('--segment_range',
                            help=_('Range for the segment.'))
        parser.add_argument('--physical_network',
                            help=_('Name for the physical network.'))
        parser.add_argument('--multicast_ip_range',
                            help=_('Multicast IPv4 range.'))
        parser.add_argument("--add-tenant",
                            action='append', dest='add_tenants',
                            help=_("Add tenant to the network profile. "
                                   "You can repeat this option."))

    def args2body(self, parsed_args):
        body = {self.resource: {'name': parsed_args.name}}
        if parsed_args.segment_type:
            body[self.resource].update({'segment_type':
                                        parsed_args.segment_type})
        if parsed_args.sub_type:
            body[self.resource].update({'sub_type':
                                        parsed_args.sub_type})
        if parsed_args.segment_range:
            body[self.resource].update({'segment_range':
                                        parsed_args.segment_range})
        if parsed_args.physical_network:
            body[self.resource].update({'physical_network':
                                        parsed_args.physical_network})
        if parsed_args.multicast_ip_range:
            body[self.resource].update({'multicast_ip_range':
                                        parsed_args.multicast_ip_range})
        if parsed_args.add_tenants:
            body[self.resource].update({'add_tenants':
                                        parsed_args.add_tenants})
        return body


class NetworkProfileDelete(extension.ClientExtensionDelete, NetworkProfile):
    """Delete a given network profile."""

    shell_command = 'cisco-network-profile-delete'
