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

from networking_cisco._i18n import _

from neutron.api import extensions
from neutron.api.v2 import attributes as attr
from neutron.api.v2 import resource_helper
from neutron.plugins.common import constants
from neutron_lib import exceptions

from neutron_lib.api import converters as conv

from networking_cisco.plugins.cisco.common import utils


ROUTERTYPE = 'routertype'
ROUTERTYPE_ALIAS = ROUTERTYPE
TYPE_ATTR = ROUTERTYPE + ':id'
ROUTER_TYPES = ROUTERTYPE + 's'

RESOURCE_ATTRIBUTE_MAP = {
    ROUTER_TYPES: {
        'id': {'allow_post': True, 'allow_put': False,
               'validate': {'type:uuid_or_none': None}, 'is_visible': True,
               'default': None, 'primary_key': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': None}, 'is_visible': True,
                 'default': ''},
        'description': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:string_or_none': None},
                        'is_visible': True, 'default': None},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True, 'is_visible': True},
        'template_id': {'allow_post': True, 'allow_put': False,
                        'required_by_policy': True,
                        'validate': {'type:uuid': None}, 'is_visible': True},
        'ha_enabled_by_default': {'allow_post': True, 'allow_put': True,
                                  'convert_to': conv.convert_to_boolean,
                                  'validate': {'type:boolean': None},
                                  'default': False, 'is_visible': True},
        'shared': {'allow_post': True, 'allow_put': False,
                   'convert_to': conv.convert_to_boolean,
                   'validate': {'type:boolean': None}, 'default': True,
                   'is_visible': True},
        #TODO(bobmel): add HA attribute: One of None, 'GPLB', 'VRRP', or 'HSRP'
        'slot_need': {'allow_post': True, 'allow_put': True,
                      'validate': {'type:non_negative': None},
                      'convert_to': conv.convert_to_int,
                      'default': 0, 'is_visible': True},
        'scheduler': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'convert_to': utils.convert_validate_driver_class,
                      'is_visible': True},
        'driver': {'allow_post': True, 'allow_put': False,
                   'required_by_policy': True,
                   'convert_to': utils.convert_validate_driver_class,
                   'is_visible': True},
        'cfg_agent_service_helper': {
            'allow_post': True, 'allow_put': False,
            'required_by_policy': True,
            'convert_to': utils.convert_validate_driver_class,
            'is_visible': True},
        'cfg_agent_driver': {'allow_post': True, 'allow_put': False,
                             'required_by_policy': True,
                             'convert_to': utils.convert_validate_driver_class,
                             'is_visible': True},
    }
}

EXTENDED_ATTRIBUTES_2_0 = {
    'routers': {
        TYPE_ATTR: {'allow_post': True, 'allow_put': True,
                    'validate': {'type:string': None},
                    'default': attr.ATTR_NOT_SPECIFIED,
                    'is_visible': True},
    }
}


class Routertype(extensions.ExtensionDescriptor):
    """Extension class to define different types of Neutron routers.

    This class is used by Neutron's extension framework to support
    definition of different types of Neutron Routers.

    Attribute 'router_type:id' is the uuid or name of a certain router type.
    It can be set during creation of Neutron router. If a Neutron router is
    moved (by admin user) to a hosting device of a different hosting device
    type, the router type of the Neutron router will also change. Non-admin
    users can request that a Neutron router's type is changed.

    To create a router of router type <name>:

       (shell) router-create <router_name> --router_type:id <uuid_or_name>
    """

    @classmethod
    def get_name(cls):
        return "Router types for routing service"

    @classmethod
    def get_alias(cls):
        return ROUTERTYPE_ALIAS

    @classmethod
    def get_description(cls):
        return "Introduces router types for Neutron Routers"

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/" + ROUTERTYPE + "/api/v2.0"

    @classmethod
    def get_updated(cls):
        return "2014-02-07T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        """Returns Ext Resources."""
        plural_mappings = resource_helper.build_plural_mappings(
            {}, RESOURCE_ATTRIBUTE_MAP)
        attr.PLURALS.update(plural_mappings)
        return resource_helper.build_resource_info(plural_mappings,
                                                   RESOURCE_ATTRIBUTE_MAP,
                                                   constants.L3_ROUTER_NAT)

    def get_extended_resources(self, version):
        if version == "2.0":
            return EXTENDED_ATTRIBUTES_2_0
        else:
            return {}


# router_type exceptions
class RouterTypeInUse(exceptions.InUse):
    message = _("Router type %(id)s in use.")


class RouterTypeNotFound(exceptions.NotFound):
    message = _("Router type %(id)s does not exist")


class MultipleRouterTypes(exceptions.NeutronException):
    message = _("Multiple router type with same name %(name)s exist. Id "
                "must be used to specify router type.")


class SchedulerNotFound(exceptions.NetworkNotFound):
    message = _("Scheduler %(scheduler)s does not exist")


class RouterTypeAlreadyDefined(exceptions.NeutronException):
    message = _("Router type %(type)s already exists")


class NoSuchHostingDeviceTemplateForRouterType(exceptions.NeutronException):
    message = _("No hosting device template with id %(type)s exists")


class HostingDeviceTemplateUsedByRouterType(exceptions.NeutronException):
    message = _("Router type %(type)s already defined for Hosting device "
                "template with id %(type)s")


class RouterTypeHasRouters(exceptions.NeutronException):
    message = _("Router type %(type)s cannot be deleted since routers "
                "of that type exists")


class RoutertypePluginBase(object):
    """REST API to manage router types.

    All methods except listing require admin context.
    """
    @abc.abstractmethod
    def create_routertype(self, context, routertype):
        """Creates a router type.
         Also binds it to the specified hosting device template.
         """
        pass

    @abc.abstractmethod
    def update_routertype(self, context, id, routertype):
        """Updates a router type."""
        pass

    @abc.abstractmethod
    def delete_routertype(self, context, id):
        """Deletes a router type."""
        pass

    @abc.abstractmethod
    def get_routertype(self, context, id, fields=None):
        """Lists defined router type."""
        pass

    @abc.abstractmethod
    def get_routertypes(self, context, filters=None, fields=None,
                        sorts=None, limit=None, marker=None,
                        page_reverse=False):
        """Lists defined router types."""
        pass
