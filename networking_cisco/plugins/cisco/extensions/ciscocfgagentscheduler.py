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
from neutron.api.v2 import base
from neutron.api.v2 import resource
from neutron.common import rpc as n_rpc
from neutron.extensions import agent
from neutron import manager
from neutron import policy
from neutron import wsgi
from neutron_lib import exceptions

from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.extensions import ciscohostingdevicemanager

PATH_PREFIX = "/dev_mgr"

LOG = logging.getLogger(__name__)


class InvalidCfgAgent(agent.AgentNotFound):
    message = _("Agent %(agent_id)s is not a Cisco cfg agent or has been "
                "disabled")


class HostingDeviceAssignedToCfgAgent(exceptions.Conflict):
    message = _("The hosting device %(hosting_device_id)s is already assigned "
                "to Cisco cfg agent %(agent_id)s.")


class HostingDeviceSchedulingFailed(exceptions.Conflict):
    message = _("Failed to assign hosting device %(hosting_device_id)s to "
                "Cisco cfg agent %(agent_id)s.")


class HostingDeviceNotAssignedToCfgAgent(exceptions.NotFound):
    message = _("The hosting device %(hosting_device_id)s is currently not "
                "assigned to Cisco cfg agent %(agent_id)s.")


CFG_AGENT_SCHEDULER_ALIAS = 'cisco-cfg-agent-scheduler'
CFG_AGENT_HOSTING_DEVICE = 'cfg-agent-hosting-device'
CFG_AGENT_HOSTING_DEVICES = CFG_AGENT_HOSTING_DEVICE + 's'
HOSTING_DEVICE_CFG_AGENT = 'hosting-device-cfg-agent'
HOSTING_DEVICE_CFG_AGENTS = HOSTING_DEVICE_CFG_AGENT + 's'


class HostingDeviceSchedulerController(wsgi.Controller):
    def get_plugin(self):
        plugin = manager.NeutronManager.get_service_plugins().get(
            cisco_constants.DEVICE_MANAGER)
        if not plugin:
            LOG.error(_LE('No Device manager service plugin registered to '
                          'handle hosting device scheduling'))
            msg = _('The resource could not be found.')
            raise webob.exc.HTTPNotFound(msg)
        return plugin

    def index(self, request, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "get_%s" % CFG_AGENT_HOSTING_DEVICES,
                       {})
        return plugin.list_hosting_devices_handled_by_cfg_agent(
            request.context, kwargs['agent_id'])

    def create(self, request, body, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "create_%s" % CFG_AGENT_HOSTING_DEVICE,
                       {})
        cfg_agent_id = kwargs['agent_id']
        hosting_device_id = body['hosting_device_id']
        result = plugin.assign_hosting_device_to_cfg_agent(
            request.context, cfg_agent_id, hosting_device_id)
        notify(request.context, 'agent.hosting_device.add', hosting_device_id,
               cfg_agent_id)
        return result

    def delete(self, request, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "delete_%s" % CFG_AGENT_HOSTING_DEVICE,
                       {})
        cfg_agent_id = kwargs['agent_id']
        hosting_device_id = kwargs['id']
        result = plugin.unassign_hosting_device_from_cfg_agent(
            request.context, cfg_agent_id, hosting_device_id)
        notify(request.context, 'agent.hosting_device.remove',
               hosting_device_id, cfg_agent_id)
        return result


class CfgAgentsHandlingHostingDeviceController(wsgi.Controller):
    def get_plugin(self):
        plugin = manager.NeutronManager.get_service_plugins().get(
            cisco_constants.DEVICE_MANAGER)
        if not plugin:
            LOG.error(_LE('No device manager service plugin registered to '
                          'handle hosting device scheduling'))
            msg = _('The resource could not be found.')
            raise webob.exc.HTTPNotFound(msg)
        return plugin

    def index(self, request, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "get_%s" % HOSTING_DEVICE_CFG_AGENTS,
            {})
        return plugin.list_cfg_agents_handling_hosting_device(
            request.context, kwargs['hosting_device_id'])


class Ciscocfgagentscheduler(extensions.ExtensionDescriptor):
    """Extension class supporting configuration agent scheduler."""
    @classmethod
    def get_name(cls):
        return "Cisco Configuration Agent Scheduler"

    @classmethod
    def get_alias(cls):
        return CFG_AGENT_SCHEDULER_ALIAS

    @classmethod
    def get_description(cls):
        return "Schedule hosting devices among Cisco configuration agents"

    @classmethod
    def get_namespace(cls):
        return ("http://docs.openstack.org/ext/" +
                CFG_AGENT_SCHEDULER_ALIAS + "/api/v1.0")

    @classmethod
    def get_updated(cls):
        return "2014-03-31T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        """Returns Ext Resources."""
        exts = []
        parent = dict(member_name="agent",
                      collection_name="agents")
        controller = resource.Resource(HostingDeviceSchedulerController(),
                                       base.FAULT_MAP)
        exts.append(extensions.ResourceExtension(CFG_AGENT_HOSTING_DEVICES,
                                                 controller, parent))
        parent = dict(member_name=ciscohostingdevicemanager.DEVICE,
                      collection_name=ciscohostingdevicemanager.DEVICES)
        controller = resource.Resource(
            CfgAgentsHandlingHostingDeviceController(), base.FAULT_MAP)
        exts.append(extensions.ResourceExtension(HOSTING_DEVICE_CFG_AGENTS,
                                                 controller, parent,
                                                 PATH_PREFIX))
        return exts

    def get_extended_resources(self, version):
        return {}


class CfgAgentSchedulerPluginBase(object):
    """REST API to operate the cfg agent scheduler.

    All of method must be in an admin context.
    """
    @abc.abstractmethod
    def assign_hosting_device_to_cfg_agent(self, context, id,
                                           hosting_device_id):
        pass

    @abc.abstractmethod
    def unassign_hosting_device_from_cfg_agent(self, context, id,
                                               hosting_device_id):
        pass

    @abc.abstractmethod
    def list_hosting_devices_handled_by_cfg_agent(self, context, id):
        pass

    @abc.abstractmethod
    def list_cfg_agents_handling_hosting_device(self, context,
                                                hosting_device_id):
        pass


def notify(context, action, hosting_device_id, cfg_agent_id):
    info = {'id': cfg_agent_id, 'hosting_device_id': hosting_device_id}
    notifier = n_rpc.get_notifier('hosting_device')
    notifier.info(context, action, {'cfg_agent': info})
