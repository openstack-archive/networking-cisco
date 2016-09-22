# Copyright 2015 Cisco Systems, Inc.  All rights reserved.
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

from networking_cisco._i18n import _

from neutron.api import extensions
from neutron_lib import exceptions as nexception

from neutron_lib.api import converters as conv

from networking_cisco import backwards_compatibility as bc_attr


HA_ALIAS = 'router_ha'
HA = 'cisco_ha'
ENABLED = HA + ':enabled'
DETAILS = HA + ':details'
HA_INFO = 'ha_info'
TYPE = 'type'
PRIORITY = 'priority'
STATE = 'state'
HA_ACTIVE = 'ACTIVE'
HA_STANDBY = 'STANDBY'
HA_STATES = [HA_ACTIVE, HA_STANDBY]
REDUNDANCY_LEVEL = 'redundancy_level'
REDUNDANCY_ROUTERS = 'redundancy_routers'
ROUTER_ID = 'id'
PROBE_CONNECTIVITY = 'probe_connectivity'
PROBE_TARGET = 'probe_target'
PROBE_INTERVAL = 'probe_interval'
HA_VRRP = 'VRRP'
HA_HSRP = 'HSRP'
HA_GLBP = 'GLBP'
HA_TYPES = [HA_VRRP, HA_HSRP, HA_GLBP]
# number of additional routers for HA redundancy
MIN_REDUNDANCY_LEVEL = 1
MAX_REDUNDANCY_LEVEL = 3

EXTENDED_ATTRIBUTES_2_0 = {
    'routers': {
        ENABLED: {'allow_post': True, 'allow_put': True,
                  'convert_to': conv.convert_to_boolean,
                  'default': bc_attr.ATTR_NOT_SPECIFIED,
                  'is_visible': True},
        DETAILS: {
            'allow_post': True, 'allow_put': True,
            'is_visible': True,
            'default': bc_attr.ATTR_NOT_SPECIFIED,
            'enforce_policy': True,
            'validate': {
                'type:dict_or_nodata': {
                    TYPE: {'allow_post': True, 'allow_put': True,
                           'type:values': HA_TYPES,
                           'default': bc_attr.ATTR_NOT_SPECIFIED,
                           'is_visible': True},
                    STATE: {
                        'allow_post': False, 'allow_put': False,
                        'type:values': HA_STATES,
                        'default': bc_attr.ATTR_NOT_SPECIFIED,
                        'is_visible': True},
                    PRIORITY: {'allow_post': True, 'allow_put': True,
                               'convert_to': conv.convert_to_int,
                               'type:non_negative': None,
                               'default': bc_attr.ATTR_NOT_SPECIFIED,
                               'is_visible': True},
                    REDUNDANCY_LEVEL: {'allow_post': True, 'allow_put': True,
                                       'convert_to': conv.convert_to_int,
                                       'type:range': [MIN_REDUNDANCY_LEVEL,
                                                      MAX_REDUNDANCY_LEVEL],
                                       'default': bc_attr.ATTR_NOT_SPECIFIED,
                                       'is_visible': True},
                    PROBE_CONNECTIVITY: {'allow_post': True,
                                         'allow_put': True,
                                         'convert_to': conv.convert_to_boolean,
                                         'default': bc_attr.ATTR_NOT_SPECIFIED,
                                         'is_visible': True},
                    PROBE_TARGET: {'allow_post': True, 'allow_put': True,
                                   'type:ip_address': None,
                                   'default': bc_attr.ATTR_NOT_SPECIFIED,
                                   'is_visible': True},
                    PROBE_INTERVAL: {'allow_post': True, 'allow_put': True,
                                     'convert_to': conv.convert_to_int,
                                     'type:non_negative': None,
                                     'default': bc_attr.ATTR_NOT_SPECIFIED,
                                     'is_visible': True},
                    REDUNDANCY_ROUTERS: {
                        'allow_post': False, 'allow_put': False,
                        'is_visible': True,
                        'default': bc_attr.ATTR_NOT_SPECIFIED,
                        'enforce_policy': True,
                        'validate': {'type:dict_or_nodata': {
                            ROUTER_ID: {
                                'allow_post': False, 'allow_put': False,
                                'type:uuid': None},
                            STATE: {
                                'allow_post': False, 'allow_put': False,
                                'type:values': HA_STATES,
                                'default': bc_attr.ATTR_NOT_SPECIFIED},
                            PRIORITY: {
                                'allow_post': False, 'allow_put': False,
                                'convert_to': conv.convert_to_int,
                                'type:non_negative': None,
                                'default': bc_attr.ATTR_NOT_SPECIFIED}
                        }}
                    }
                }
            }
        }
    }
}


class Ha(extensions.ExtensionDescriptor):
    """Extension class to support HA by VRRP, HSRP and GLBP.

    This class is used by Neutron's extension framework to support
    HA redundancy by VRRP, HSRP and GLBP for Neutron Routers.

    Attribute 'ha_type' can be one of 'vrrp', 'hsrp' and 'glbp'
    Attribute 'redundancy_level' specifies the number of routers
              added for redundancy and can be 1, 2, or 3.

    To create a router with HSRP-based HA with 2 extra routers
    for redundancy using the CLI with admin rights:

       (shell) router-create <router_name> --ha:ha_type hsrp \
       --ha:redundancy_level 2
    """

    @classmethod
    def get_name(cls):
        return "High-availability for routing service"

    @classmethod
    def get_alias(cls):
        return HA_ALIAS

    @classmethod
    def get_description(cls):
        return "High availability by VRRP, HSRP, and GLBP"

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/ha/api/v1.0"

    @classmethod
    def get_updated(cls):
        return "2013-12-07T10:00:00-00:00"

    def get_extended_resources(self, version):
        if version == "2.0":
            return EXTENDED_ATTRIBUTES_2_0
        else:
            return {}


# HA exceptions
class HADisabled(nexception.Conflict):
    message = _("HA support is disabled")


class HADisabledHAType(nexception.Conflict):
    message = _("HA type %(ha_type)s is administratively disabled")


class HARedundancyLevel(nexception.BadRequest):
    message = _("Redundancy level for HA must be 1, 2, or 3")


class HATypeCannotBeChanged(nexception.Conflict):
    message = _("HA type cannot be changed for a router with HA enabled")


class HATypeNotCompatibleWithFloatingIP(nexception.BadRequest):
    message = _("HA type %(ha_type) cannot be used with FloatingIP")
