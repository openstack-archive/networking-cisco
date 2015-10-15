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

from neutron.api import extensions
from neutron.api.v2 import attributes as attr


ROUTERHOSTINGDEVICE = 'routerhost'
ROUTERHOSTINGDEVICE_ALIAS = ROUTERHOSTINGDEVICE
HOSTING_DEVICE_ATTR = ROUTERHOSTINGDEVICE + ':hosting_device'

EXTENDED_ATTRIBUTES_2_0 = {
    'routers': {
        HOSTING_DEVICE_ATTR: {'allow_post': False, 'allow_put': False,
                              'default': attr.ATTR_NOT_SPECIFIED,
                              'is_visible': True},
    }
}


class Routerhostingdevice(extensions.ExtensionDescriptor):
    """Extension class to introduce hosting device information for routers.

    This class is used by Neutron's extension framework to add hosting_device
    attribute to Neutron Routers implemented in virtual/physical appliances.
    """

    @classmethod
    def get_name(cls):
        return "Hosting info for routing service"

    @classmethod
    def get_alias(cls):
        return ROUTERHOSTINGDEVICE_ALIAS

    @classmethod
    def get_description(cls):
        return ("Introduces hosting_device attribute for Neutron routers "
                "implemented in virtual/physical appliances")

    @classmethod
    def get_namespace(cls):
        return ("http://docs.openstack.org/ext/" + ROUTERHOSTINGDEVICE +
                "/api/v1.0")

    @classmethod
    def get_updated(cls):
        return "2014-02-07T10:00:00-00:00"

    def get_extended_resources(self, version):
        if version == "2.0":
            return EXTENDED_ATTRIBUTES_2_0
        else:
            return {}
