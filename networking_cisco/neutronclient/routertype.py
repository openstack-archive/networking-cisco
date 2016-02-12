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

from networking_cisco._i18n import _

from neutronclient.common import extension
from neutronclient.neutron import v2_0 as neutronV20


ROUTER_TYPE = 'routertype'


def _add_updatable_args(parser):
    parser.add_argument(
        '--name',
        help=_('Name of this router type.'))
    parser.add_argument(
        '--description',
        help=_('Description of this router type.'))
    parser.add_argument(
        '--ha-enabled',
        dest='ha_enabled_by_default',
        action='store_true',
        help=_('Make HA enabled for the router type.'),
        default=argparse.SUPPRESS)
    parser.add_argument(
        '--ha_enabled',
        dest='ha_enabled_by_default',
        action='store_true',
        help=argparse.SUPPRESS,
        default=argparse.SUPPRESS)
    parser.add_argument(
        '--unshared',
        dest='shared',
        action='store_false',
        help=_('Make router type NOT shared among tenants.'),
        default=argparse.SUPPRESS)
    parser.add_argument(
        '--slot-need',
        help=_('Number of slots routers of this type consumes.'))
    parser.add_argument(
        '--slot_need',
        help=argparse.SUPPRESS)


def _updatable_args2body(parsed_args, body):
    neutronV20.update_dict(parsed_args, body[ROUTER_TYPE],
                           ['name', 'description', 'ha_enabled_by_default',
                            'shared', 'slot_need'])


class RouterType(extension.NeutronClientExtension):
    resource = ROUTER_TYPE
    resource_plural = '%ss' % resource
    object_path = '/%s' % resource_plural
    resource_path = '/%s/%%s' % resource_plural
    versions = ['2.0']
    allow_names = True


class RouterTypeList(extension.ClientExtensionList, RouterType):
    """List router types that belong to a given tenant."""

    shell_command = 'cisco-router-type-list'
    list_columns = ['id', 'name', 'description', 'template_id']
    pagination_support = True
    sorting_support = True


class RouterTypeShow(extension.ClientExtensionShow, RouterType):
    """Show information of a given router type."""

    shell_command = 'cisco-router-type-show'


class RouterTypeCreate(extension.ClientExtensionCreate, RouterType):
    """Create a router type for a given tenant."""

    shell_command = 'cisco-router-type-create'

    def add_known_arguments(self, parser):
        _add_updatable_args(parser)
        parser.add_argument(
            '--id',
            help=_('Id for this router type.'))

        parser.add_argument(
            'template_id', metavar='TEMPLATE',
            help=_('Hosting device template to associate router type with.'))
        parser.add_argument(
            'scheduler',
            metavar='SCHEDULER',
            help=_('Scheduler module to use for routers of this router type.'))
        parser.add_argument(
            'driver',
            metavar='PLUGIN_DRIVER',
            help=_('Driver module to use in plugin for routers of this router '
                   'type.'))
        parser.add_argument(
            'cfg_agent_service_helper',
            metavar='SERVICE_HELPER',
            help=_('Service helper in config agent to use for routers of this '
                   'router type.'))
        parser.add_argument(
            'cfg_agent_driver',
            metavar='AGENT_DRIVER',
            help=_('Device driver in config agent to use for routers of this '
                   'router type.'))

    def args2body(self, parsed_args):
        client = self.get_client()
        _template_id = neutronV20.find_resourceid_by_name_or_id(
            client, 'hosting_device_template', parsed_args.template_id)
        body = {self.resource: {
            'template_id': _template_id,
            'scheduler': parsed_args.scheduler,
            'driver': parsed_args.driver,
            'cfg_agent_service_helper': parsed_args.cfg_agent_service_helper,
            'cfg_agent_driver': parsed_args.cfg_agent_driver}}
        _updatable_args2body(parsed_args, body)
        neutronV20.update_dict(parsed_args, body[self.resource],
                               ['id', 'tenant_id'])
        return body


class RouterTypeDelete(extension.ClientExtensionDelete, RouterType):
    """Delete a given router type."""

    shell_command = 'cisco-router-type-delete'


class RouterTypeUpdate(extension.ClientExtensionUpdate, RouterType):
    """Update router type's information."""

    shell_command = 'cisco-router-type-update'

    def add_known_arguments(self, parser):
        # adding ha_disabled here so that it is available for update only as
        # HA is disabled by default and not meaningful in the create operation
        parser.add_argument(
            '--ha-disabled',
            dest='ha_enabled_by_default',
            action='store_false',
            help=_('Make HA disabled for the router type.'),
            default=argparse.SUPPRESS)
        parser.add_argument(
            '--ha_disabled',
            dest='ha_enabled_by_default',
            action='store_false',
            help=argparse.SUPPRESS,
            default=argparse.SUPPRESS)
        # adding shared here so that it is available for update only as it is
        # True by default and not meaningful in the create operation
        parser.add_argument(
            '--shared',
            dest='shared',
            action='store_true',
            help=_('Make router type shared among tenants.'),
            default=argparse.SUPPRESS)
        _add_updatable_args(parser)

    def args2body(self, parsed_args):
        body = {self.resource: {}}
        _updatable_args2body(parsed_args, body)
        return body
