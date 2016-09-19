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
import abc

import six

from neutron.api import extensions
from neutron.api.v2 import attributes
from neutron.api.v2 import base
from neutron import manager
from neutron.services import service_base as sb

from neutron_lib.api import converters as conv
from neutron_lib import constants as lib_constants

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import constants

NETWORK_PROFILE = 'network_profile'
NETWORK_PROFILES = NETWORK_PROFILE + 's'
NETWORK_PROFILE_BINDING = NETWORK_PROFILE + '_binding'
NETWORK_PROFILE_BINDINGS = NETWORK_PROFILE_BINDING + 's'
# Attribute Map
RESOURCE_ATTRIBUTE_MAP = {
    NETWORK_PROFILES: {
        'id': {
            'allow_post': False, 'allow_put': False,
            'validate': {'type:uuid': lib_constants.UUID_PATTERN},
            'is_visible': True
        },
        'name': {
            'allow_post': True, 'allow_put': True,
            'is_visible': True, 'default': ''
        },
        'segment_type': {
            'allow_post': True, 'allow_put': False,
            'is_visible': True,
            'default': ''
        },
        'sub_type': {
            'allow_post': True, 'allow_put': False,
            'is_visible': True,
            'default': attributes.ATTR_NOT_SPECIFIED
        },
        'multicast_ip_range': {
            'allow_post': True, 'allow_put': True,
            'is_visible': True,
            'default': attributes.ATTR_NOT_SPECIFIED
        },
        'multicast_ip_index': {
            'allow_post': False, 'allow_put': False,
            'is_visible': False, 'default': '0'
        },
        'physical_network': {
            'allow_post': True, 'allow_put': False,
            'is_visible': True,
            'default': attributes.ATTR_NOT_SPECIFIED
        },
        'tenant_id': {
            'allow_post': True, 'allow_put': False,
            'is_visible': False,
            'default': attributes.ATTR_NOT_SPECIFIED
        },
        'add_tenants': {
            'allow_post': True, 'allow_put': True,
            'is_visible': True, 'default': None,
            'convert_to': conv.convert_none_to_empty_list
        },
        'remove_tenants': {
            'allow_post': True, 'allow_put': True,
            'is_visible': True, 'default': None,
            'convert_to': conv.convert_none_to_empty_list,
        },
    },
    NETWORK_PROFILE_BINDINGS: {
        'profile_id': {'allow_post': False, 'allow_put': False,
                       'validate': {'type:regex': lib_constants.UUID_PATTERN},
                       'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'is_visible': True},
    },
}


class Network_profile(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "Cisco Nexus1000V Network Profiles"

    @classmethod
    def get_alias(cls):
        return 'network_profile'

    @classmethod
    def get_description(cls):
        return "Profile includes the network type of profile for N1kv"

    @classmethod
    def get_updated(cls):
        return "2014-11-23T10:00:00-00:00"

    @classmethod
    def get_plugin_interface(cls):
        return NetworkProfilePluginBase

    @classmethod
    def get_resources(cls):
        """Returns Extended Resources."""
        exts = []
        plugin = (manager.NeutronManager.
                  get_service_plugins()[constants.CISCO_N1KV_NET_PROFILE])
        resource_names = [NETWORK_PROFILE, NETWORK_PROFILE_BINDING]
        collection_names = [NETWORK_PROFILES, NETWORK_PROFILE_BINDINGS]
        for resource_name, collection_name in zip(resource_names,
                                                  collection_names):
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
class NetworkProfilePluginBase(sb.ServicePluginBase):

    def get_plugin_name(self):
        return constants.CISCO_N1KV_NET_PROFILE

    def get_plugin_type(self):
        return constants.CISCO_N1KV_NET_PROFILE

    def get_plugin_description(self):
        return 'Cisco N1KV Network Profile'

    @abc.abstractmethod
    def get_network_profiles(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_network_profile(self, context, profile_id, fields=None):
        pass

    @abc.abstractmethod
    def create_network_profile(self, context, netp, fields=None):
        pass

    @abc.abstractmethod
    def update_network_profile(self, context, profile_id, netp):
        pass

    @abc.abstractmethod
    def delete_network_profile(self, context, profile_id):
        pass
