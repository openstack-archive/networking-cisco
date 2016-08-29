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

import abc

from oslo_utils import netutils
import six

from networking_cisco._i18n import _

from neutron.api import extensions
from neutron.api.v2 import attributes as attr
from neutron.api.v2 import resource_helper
from neutron.services.service_base import ServicePluginBase
from neutron_lib import exceptions as nexception

from neutron_lib.api import converters as conv

from networking_cisco.plugins.cisco.common import cisco_constants as constants
from networking_cisco.plugins.cisco.common import utils


# Hosting device and hosting device template exceptions
class HostingDeviceInvalidPortValue(nexception.InvalidInput):
    message = _("Invalid value for port %(port)s")


class HostingDeviceInUse(nexception.InUse):
    message = _("Hosting device %(id)s in use.")


class HostingDeviceMgmtPortNotFound(nexception.InUse):
    message = _("Specified management port %(id)s does not exist.")


class HostingDeviceNotFound(nexception.NotFound):
    message = _("Hosting device %(id)s does not exist")


class HostingDeviceTemplateNotFound(nexception.NotFound):
    message = _("Hosting device template %(id)s does not exist")


class HostingDeviceTemplateInUse(nexception.InUse):
    message = _("Hosting device template %(id)s in use.")


class TenantBoundNotUUIDListOrNone(nexception.NetworkNotFound):
    message = _("Attribute tenant_bound must be a list of tenant ids or None")


def convert_validate_port_value(port):
    if port is None:
        return port

    if netutils.is_valid_port(port):
        return int(port)
    else:
        raise HostingDeviceInvalidPortValue(port=port)


def convert_empty_string_to_none(value):
    if value == "":
        return None
    else:
        return value


# Hosting device belong to one of the following categories:
VM_CATEGORY = 'VM'
HARDWARE_CATEGORY = 'Hardware'
NETWORK_NODE_CATEGORY = 'Network_Node'

HOSTING_DEVICE_MANAGER_ALIAS = 'dev_mgr'
DEVICE = 'hosting_device'
DEVICES = DEVICE + 's'
DEVICE_TEMPLATE = DEVICE + '_template'
DEVICE_TEMPLATES = DEVICE_TEMPLATE + 's'

AUTO_DELETE_DEFAULT = False

# Attribute Map
RESOURCE_ATTRIBUTE_MAP = {
    DEVICES: {
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True, 'is_visible': True},
        'id': {'allow_post': True, 'allow_put': False,
               'validate': {'type:uuid_or_none': None},
               'default': None, 'is_visible': True,
               'primary_key': True},
        'template_id': {'allow_post': True, 'allow_put': False,
                        'validate': {'type:uuid': None},
                        'required_by_policy': True, 'is_visible': True},
        'credentials_id': {'allow_post': True, 'allow_put': True,
                           'default': None,
                           'validate': {'type:uuid_or_none': None},
                           'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string_or_none': None},
                 'default': None, 'is_visible': True},
        'description': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:string_or_none': None},
                        'default': None, 'is_visible': True},
        'device_id': {'allow_post': True, 'allow_put': True,
                      'validate': {'type:string_or_none': None},
                      'default': None, 'is_visible': True},
        'admin_state_up': {'allow_post': True, 'allow_put': True,
                           'convert_to': conv.convert_to_boolean,
                           'default': True, 'is_visible': True},
        'management_ip_address': {'allow_post': True, 'allow_put': False,
                                  'validate': {'type:ip_address': None},
                                  'is_visible': True},
        'management_port_id': {'allow_post': True, 'allow_put': False,
                               'validate': {'type:uuid_or_none': None},
                               'default': None, 'is_visible': True},
        'protocol_port': {'allow_post': True, 'allow_put': False,
                          'convert_to': convert_validate_port_value,
                          'default': None, 'is_visible': True},
        'cfg_agent_id': {'allow_post': True, 'allow_put': False,
                         'validate': {'type:uuid_or_none': None},
                         'default': None, 'is_visible': True},
        'created_at': {'allow_post': False, 'allow_put': False,
                       'is_visible': True},
        'status': {'allow_post': False, 'allow_put': False,
                   'default': None, 'is_visible': True},
        'tenant_bound': {'allow_post': True, 'allow_put': True,
                         'convert_to': convert_empty_string_to_none,
                         'validate': {'type:uuid_or_none': None},
                         'default': None, 'is_visible': True},
        'auto_delete': {'allow_post': True, 'allow_put': True,
                        'convert_to': conv.convert_to_boolean,
                        'default': AUTO_DELETE_DEFAULT, 'is_visible': True},
    },
    DEVICE_TEMPLATES: {
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True, 'is_visible': True},
        'id': {'allow_post': True, 'allow_put': False,
               'validate': {'type:uuid_or_none': None}, 'default': None,
               'is_visible': True, 'primary_key': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string_or_none': None},
                 'default': None, 'is_visible': True},
        'enabled': {'allow_post': True, 'allow_put': True,
                    'convert_to': conv.convert_to_boolean,
                    'default': True, 'is_visible': True},
        'host_category': {'allow_post': True, 'allow_put': False,
                          'validate': {'type:values': [VM_CATEGORY,
                                                       HARDWARE_CATEGORY,
                                                       NETWORK_NODE_CATEGORY]},
                          'required_by_policy': True, 'is_visible': True},
        #TODO(bobmel): validate service_types
        'service_types': {'allow_post': True, 'allow_put': True,
                          'default': None, 'is_visible': True},
        'image': {'allow_post': True, 'allow_put': True,
                  'validate': {'type:string_or_none': None},
                  'default': None, 'is_visible': True},
        'flavor': {'allow_post': True, 'allow_put': True,
                   'validate': {'type:string_or_none': None},
                   'default': None, 'is_visible': True},
        'default_credentials_id': {'allow_post': True, 'allow_put': True,
                                   'validate': {'type:uuid': None},
                                   'is_visible': True},
        'configuration_mechanism': {'allow_post': True, 'allow_put': True,
                                    'validate': {'type:string_or_none': None},
                                    'is_visible': True},
        'protocol_port': {'allow_post': True, 'allow_put': True,
                          'convert_to': convert_validate_port_value,
                          'default': None, 'is_visible': True},
        'booting_time': {'allow_post': True, 'allow_put': True,
                         'validate': {'type:non_negative': 0},
                         'convert_to': conv.convert_to_int,
                         'default': None, 'is_visible': True},
        'slot_capacity': {'allow_post': True, 'allow_put': False,
                          'validate': {'type:non_negative': 0},
                          'convert_to': conv.convert_to_int,
                          'default': 0, 'is_visible': True},
        'desired_slots_free': {'allow_post': True, 'allow_put': False,
                               'validate': {'type:non_negative': 0},
                               'convert_to': conv.convert_to_int,
                               'default': 0, 'is_visible': True},
        'tenant_bound': {'allow_post': True, 'allow_put': True,
                         'validate': {'type:uuid_list': []},
                         'default': [], 'is_visible': True},
        'device_driver': {'allow_post': True, 'allow_put': False,
                          'convert_to': utils.convert_validate_driver_class,
                          'is_visible': True},
        'plugging_driver': {'allow_post': True, 'allow_put': False,
                            'convert_to': utils.convert_validate_driver_class,
                            'is_visible': True},
    }
}


class Ciscohostingdevicemanager(extensions.ExtensionDescriptor):
    """Hosting device and template extension."""

    @classmethod
    def get_name(cls):
        return "Cisco hosting device manager"

    @classmethod
    def get_alias(cls):
        return HOSTING_DEVICE_MANAGER_ALIAS

    @classmethod
    def get_description(cls):
        return "Extension for manager of hosting devices and their templates"

    @classmethod
    def get_namespace(cls):
        # todo
        return ("http://docs.openstack.org/ext/" +
                HOSTING_DEVICE_MANAGER_ALIAS + "/api/v2.0")

    @classmethod
    def get_updated(cls):
        return "2014-03-31T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        """Returns Ext Resources."""
        plural_mappings = resource_helper.build_plural_mappings(
            {}, RESOURCE_ATTRIBUTE_MAP)
        attr.PLURALS.update(plural_mappings)
        action_map = {DEVICE: {'get_hosting_device_config': 'GET'}}
        return resource_helper.build_resource_info(plural_mappings,
                                                   RESOURCE_ATTRIBUTE_MAP,
                                                   constants.DEVICE_MANAGER,
                                                   action_map=action_map)

    def get_extended_resources(self, version):
        if version == "2.0":
            return RESOURCE_ATTRIBUTE_MAP
        else:
            return {}


@six.add_metaclass(abc.ABCMeta)
class CiscoHostingDevicePluginBase(ServicePluginBase):

    def get_plugin_name(self):
        return constants.DEVICE_MANAGER

    def get_plugin_type(self):
        return constants.DEVICE_MANAGER

    def get_plugin_description(self):
        return ("Cisco Device Manager Service Plugin for management of "
                "hosting devices and their templates.")

    @abc.abstractmethod
    def create_hosting_device(self, context, hosting_device):
        pass

    @abc.abstractmethod
    def update_hosting_device(self, context, id, hosting_device):
        pass

    @abc.abstractmethod
    def delete_hosting_device(self, context, id):
        pass

    @abc.abstractmethod
    def get_hosting_device(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def get_hosting_devices(self, context, filters=None, fields=None,
                            sorts=None, limit=None, marker=None,
                            page_reverse=False):
        pass

    @abc.abstractmethod
    def get_hosting_device_config(self, context, id):
        pass

    @abc.abstractmethod
    def create_hosting_device_template(self, context,
                                       hosting_device_template):
        pass

    @abc.abstractmethod
    def update_hosting_device_template(self, context, id,
                                       hosting_device_template):
        pass

    @abc.abstractmethod
    def delete_hosting_device_template(self, context, id):
        pass

    @abc.abstractmethod
    def get_hosting_device_template(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def get_hosting_device_templates(self, context, filters=None, fields=None,
                                     sorts=None, limit=None, marker=None,
                                     page_reverse=False):
        pass
