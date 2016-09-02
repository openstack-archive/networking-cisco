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

from oslo_log import log as logging
import webob.exc

from networking_cisco._i18n import _, _LE

from neutron.api import extensions
from neutron.api.v2 import attributes as attr
from neutron.api.v2 import base
from neutron.api.v2 import resource
from neutron.common import rpc as n_rpc
from neutron.extensions import l3
from neutron import manager
from neutron.plugins.common import constants as svc_constants
from neutron import policy
from neutron import wsgi

from neutron_lib.api import converters as conv
from neutron_lib import exceptions as n_exc

from networking_cisco.plugins.cisco.extensions import ciscohostingdevicemanager


LOG = logging.getLogger(__name__)


class InvalidHostingDevice(n_exc.NotFound):
    message = _("Hosting device %(hosting_device_id)s does not exist or has "
                "been disabled.")


class RouterHostedByHostingDevice(n_exc.Conflict):
    message = _("The router %(router_id)s is already hosted by the hosting "
                "device %(hosting_device_id)s.")


class RouterSchedulingFailed(n_exc.Conflict):
    message = _("Failed scheduling router %(router_id)s to hosting device "
                "%(hosting_device_id)s")


class RouterReschedulingFailed(n_exc.Conflict):
    message = _("Failed rescheduling router %(router_id)s: no eligible "
                "hosting device found.")


class RouterNotHostedByHostingDevice(n_exc.Conflict):
    message = _("The router %(router_id)s is not hosted by hosting device "
                "%(hosting_device_id)s.")


class RouterHostingDeviceMismatch(n_exc.Conflict):
    message = _("Cannot host %(router_type)s router %(router_id)s "
                "on hosting device %(hosting_device_id)s.")


ROUTERTYPE_AWARE_SCHEDULER_ALIAS = 'routertype-aware-scheduler'
DEVICE_L3_ROUTER = 'hosting-device-l3-router'
DEVICE_L3_ROUTERS = DEVICE_L3_ROUTER + 's'
L3_ROUTER_DEVICE = 'l3-router-hosting-device'
L3_ROUTER_DEVICES = L3_ROUTER_DEVICE + 's'
AUTO_SCHEDULE_ATTR = ROUTERTYPE_AWARE_SCHEDULER_ALIAS + ':auto_schedule'
SHARE_HOST_ATTR = ROUTERTYPE_AWARE_SCHEDULER_ALIAS + ':share_hosting_device'


class RouterHostingDeviceSchedulerController(wsgi.Controller):
    def get_plugin(self):
        plugin = manager.NeutronManager.get_service_plugins().get(
            svc_constants.L3_ROUTER_NAT)
        if not plugin:
            LOG.error(_LE('No L3 router service plugin registered to '
                          'handle routertype-aware scheduling'))
            msg = _('The resource could not be found.')
            raise webob.exc.HTTPNotFound(msg)
        return plugin

    def index(self, request, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "get_%s" % DEVICE_L3_ROUTERS, {})
        return plugin.list_routers_on_hosting_device(
            request.context, kwargs['hosting_device_id'])

    def create(self, request, body, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "create_%s" % DEVICE_L3_ROUTER, {})
        hosting_device_id = kwargs['hosting_device_id']
        router_id = body['router_id']
        result = plugin.add_router_to_hosting_device(
            request.context, hosting_device_id, router_id)
        notify(request.context, 'hosting_device.router.add', router_id,
               hosting_device_id)
        return result

    def delete(self, request, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "delete_%s" % DEVICE_L3_ROUTER, {})
        hosting_device_id = kwargs['hosting_device_id']
        router_id = kwargs['id']
        result = plugin.remove_router_from_hosting_device(
            request.context, hosting_device_id, router_id)
        notify(request.context, 'hosting_device.router.remove', router_id,
               hosting_device_id)
        return result


class HostingDevicesHostingRouterController(wsgi.Controller):
    def get_plugin(self):
        plugin = manager.NeutronManager.get_service_plugins().get(
            svc_constants.L3_ROUTER_NAT)
        if not plugin:
            LOG.error(_LE('No L3 router service plugin registered to '
                          'handle routertype-aware scheduling'))
            msg = _('The resource could not be found.')
            raise webob.exc.HTTPNotFound(msg)
        return plugin

    def index(self, request, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "get_%s" % L3_ROUTER_DEVICES, {})
        return plugin.list_hosting_devices_hosting_router(request.context,
                                                          kwargs['router_id'])


EXTENDED_ATTRIBUTES_2_0 = {
    'routers': {
        AUTO_SCHEDULE_ATTR: {'allow_post': True, 'allow_put': True,
                             'convert_to': conv.convert_to_boolean,
                             'validate': {'type:boolean': None},
                             'default': attr.ATTR_NOT_SPECIFIED,
                             'is_visible': True},
        SHARE_HOST_ATTR: {'allow_post': True, 'allow_put': False,
                          'convert_to': conv.convert_to_boolean,
                          'validate': {'type:boolean': None},
                          'default': attr.ATTR_NOT_SPECIFIED,
                          'is_visible': True},
    }
}


class Routertypeawarescheduler(extensions.ExtensionDescriptor):
    """Extension class supporting l3 agent scheduler."""
    @classmethod
    def get_name(cls):
        return "Cisco routertype aware Scheduler"

    @classmethod
    def get_alias(cls):
        return ROUTERTYPE_AWARE_SCHEDULER_ALIAS

    @classmethod
    def get_description(cls):
        return "Schedule routers to Cisco hosting devices"

    @classmethod
    def get_namespace(cls):
        return ("http://docs.openstack.org/ext/" +
                ROUTERTYPE_AWARE_SCHEDULER_ALIAS + "/api/v1.0")

    @classmethod
    def get_updated(cls):
        return "2014-03-31T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        """Returns Ext Resources."""
        exts = []
        parent = dict(member_name=ciscohostingdevicemanager.DEVICE,
                      collection_name=ciscohostingdevicemanager.DEVICES)
        controller = resource.Resource(
            RouterHostingDeviceSchedulerController(), base.FAULT_MAP)
        exts.append(extensions.ResourceExtension(
            DEVICE_L3_ROUTERS, controller, parent, path_prefix="/dev_mgr"))
        parent = dict(member_name="router",
                      collection_name=l3.ROUTERS)
        controller = resource.Resource(
            HostingDevicesHostingRouterController(), base.FAULT_MAP)
        exts.append(extensions.ResourceExtension(L3_ROUTER_DEVICES, controller,
                                                 parent))
        return exts

    def get_extended_resources(self, version):
        if version == "2.0":
            return EXTENDED_ATTRIBUTES_2_0
        else:
            return {}


class RouterTypeAwareSchedulerPluginBase(object):
    """REST API to operate the routertype-aware scheduler.

    All of method must be in an admin context.
    """
    @abc.abstractmethod
    def add_router_to_hosting_device(self, context, hosting_device_id,
                                     router_id):
        pass

    @abc.abstractmethod
    def remove_router_from_hosting_device(self, context, hosting_device_id,
                                          router_id):
        pass

    @abc.abstractmethod
    def list_routers_on_hosting_device(self, context, hosting_device_id):
        pass

    @abc.abstractmethod
    def list_hosting_devices_hosting_router(self, context, router_id):
        pass


def notify(context, action, router_id, hosting_device_id):
    info = {'id': hosting_device_id, 'router_id': router_id}
    notifier = n_rpc.get_notifier('router')
    notifier.info(context, action, {'hosting_device': info})
