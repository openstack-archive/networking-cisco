# Copyright 2014 Cisco Systems, Inc.
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
import abc

import six

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants)

from neutron.api import extensions
from neutron.api.v2 import base
from neutron import manager
from neutron.services import service_base as sb

from neutron_lib.api import converters as conv
from neutron_lib import constants as lib_constants


POLICY_PROFILE = 'policy_profile'
POLICY_PROFILES = 'policy_profiles'
# Attribute Map
RESOURCE_ATTRIBUTE_MAP = {
    POLICY_PROFILES: {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': lib_constants.UUID_PATTERN},
               'is_visible': True},
        'name': {'allow_post': False, 'allow_put': False,
                 'is_visible': True, 'default': ''},
        'add_tenant': {
            'allow_post': True, 'allow_put': True,
            'is_visible': True, 'default': None,
            'convert_to': conv.convert_none_to_empty_list},
        'remove_tenant': {
            'allow_post': True, 'allow_put': True,
            'is_visible': True, 'default': None,
            'convert_to': conv.convert_none_to_empty_list},
    },
    'policy_profile_bindings': {
        'profile_id': {'allow_post': False, 'allow_put': False,
                       'validate': {'type:regex': lib_constants.UUID_PATTERN},
                       'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'is_visible': True},
    },
}


class Policy_profile(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "Cisco Nexus1000V Policy Profiles"

    @classmethod
    def get_alias(cls):
        return 'policy_profile'

    @classmethod
    def get_description(cls):
        return "Profile includes the type of profile for N1kv"

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/dfa/policy_profile/api/v2.0"

    @classmethod
    def get_updated(cls):
        return "2014-11-23T10:00:00-00:00"

    @classmethod
    def get_plugin_interface(cls):
        return PolicyProfilePluginBase

    @classmethod
    def get_resources(cls):
        """Returns Extended Resources."""
        exts = []
        plugin = (manager.NeutronManager.
                  get_service_plugins()[constants.CISCO_N1KV])
        for resource_name in [POLICY_PROFILE, 'policy_profile_binding']:
            collection_name = resource_name + 's'
            controller = base.create_resource(
                collection_name,
                resource_name,
                plugin,
                RESOURCE_ATTRIBUTE_MAP.get(collection_name))
            ex = extensions.ResourceExtension(collection_name,
                                              controller)
            exts.append(ex)
        return exts


@six.add_metaclass(abc.ABCMeta)
class PolicyProfilePluginBase(sb.ServicePluginBase):

    def get_plugin_name(self):
        return constants.CISCO_N1KV

    def get_plugin_type(self):
        return constants.CISCO_N1KV

    def get_plugin_description(self):
        return 'Cisco N1KV Policy Profile'

    @abc.abstractmethod
    def get_policy_profiles(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_policy_profile(self, context, profile_id, fields=None):
        pass

    @abc.abstractmethod
    def update_policy_profile(self, context, profile_id, policyp):
        pass
