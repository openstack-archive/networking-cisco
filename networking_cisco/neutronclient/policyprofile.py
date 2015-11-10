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

from neutronclient.common import extension
from neutronclient.i18n import _


class PolicyProfile(extension.NeutronClientExtension):
    resource = 'policy_profile'
    resource_plural = '%ss' % resource
    object_path = '/%s' % resource_plural
    resource_path = '/%s/%%s' % resource_plural
    versions = ['2.0']
    allow_names = True


class PolicyProfileList(extension.ClientExtensionList, PolicyProfile):
    """List policy profiles that belong to a given tenant."""

    shell_command = 'cisco-policy-profile-list'
    list_columns = ['id', 'name']
    pagination_support = True
    sorting_support = True


class PolicyProfileShow(extension.ClientExtensionShow, PolicyProfile):
    """Show information of a given policy profile."""

    shell_command = 'cisco-policy-profile-show'


class UpdatePolicyProfile(extension.ClientExtensionUpdate, PolicyProfile):
    """Update policy profile's information."""

    shell_command = 'cisco-policy-profile-update'

    def get_parser(self, prog_name):
        parser = super(UpdatePolicyProfile, self).get_parser(prog_name)
        parser.add_argument("--add-tenant",
                            action='append',
                            dest='add_tenant',
                            help=_("Add tenant to the policy profile."))
        parser.add_argument("--remove-tenant",
                            action='append',
                            dest='remove_tenant',
                            help=_("Remove tenant from the policy profile."))
        return parser

    def args2body(self, parsed_args):
        body = {self.resource: {}}
        if parsed_args.add_tenant:
            body[self.resource]['add_tenant'] = parsed_args.add_tenant
        if parsed_args.remove_tenant:
            body[self.resource]['remove_tenant'] = parsed_args.remove_tenant
        return body
