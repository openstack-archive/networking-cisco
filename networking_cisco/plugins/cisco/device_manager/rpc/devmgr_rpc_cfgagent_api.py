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
#

from oslo_log import log as logging
import oslo_messaging

from neutron.common import rpc as n_rpc

from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)
from networking_cisco.plugins.cisco.extensions import ciscocfgagentscheduler

LOG = logging.getLogger(__name__)


CFGAGENT_SCHED = ciscocfgagentscheduler.CFG_AGENT_SCHEDULER_ALIAS


class DeviceMgrCfgAgentNotifyAPI(object):
    """API for Device manager service plugin to notify Cisco cfg agent."""

    def __init__(self, devmgr_plugin, topic=c_constants.CFG_AGENT):
        self._dmplugin = devmgr_plugin
        target = oslo_messaging.Target(topic=topic, version='1.1')
        self.client = n_rpc.get_client(target)

    def _host_notification(self, context, method, payload, host):
        """Notify the cfg agent that is handling the hosting device."""
        LOG.debug('Notify Cisco cfg agent at %(host)s the message '
                  '%(method)s', {'host': host, 'method': method})
        cctxt = self.client.prepare(server=host)
        cctxt.cast(context, method, payload=payload)

    def _agent_notification(self, context, method, hosting_devices, operation):
        """Notify individual Cisco cfg agents."""
        admin_context = context.is_admin and context or context.elevated()
        for hosting_device in hosting_devices:
            agents = self._dmplugin.get_cfg_agents_for_hosting_devices(
                admin_context, hosting_device['id'], admin_state_up=True,
                schedule=True)
            for agent in agents:
                LOG.debug('Notify %(agent_type)s at %(topic)s.%(host)s the '
                          'message %(method)s',
                          {'agent_type': agent.agent_type,
                           'topic': agent.topic,
                           'host': agent.host,
                           'method': method})
                cctxt = self.client.prepare(server=agent.host)
                cctxt.cast(context, method)

    def agent_updated(self, context, admin_state_up, host):
        """Updates cfg agent on <host> to enable or disable it."""
        self._host_notification(context, 'agent_updated',
                                {'admin_state_up': admin_state_up}, host)

    def hosting_devices_unassigned_from_cfg_agent(self, context, ids, host):
        """Notify cfg agent to no longer handle some hosting devices.

        This notification relieves the cfg agent in <host> of responsibility
        to monitor and configure hosting devices with id specified in <ids>.
        """
        self._host_notification(context,
                                'hosting_devices_unassigned_from_cfg_agent',
                                {'hosting_device_ids': ids}, host)

    def hosting_devices_assigned_to_cfg_agent(self, context, ids, host):
        """Notify cfg agent to now handle some hosting devices.

        This notification relieves the cfg agent in <host> of responsibility
        to monitor and configure hosting devices with id specified in <ids>.
        """
        self._host_notification(context,
                                'hosting_devices_assigned_to_cfg_agent',
                                {'hosting_device_ids': ids}, host)

    def hosting_devices_removed(self, context, hosting_data, deconfigure,
                                host):
        """Notify cfg agent that some hosting devices have been removed.

        This notification informs the cfg agent in <host> that the
        hosting devices in the <hosting_data> dictionary have been removed
        from the hosting device pool. The <hosting_data> dictionary also
        contains the ids of the affected logical resources for each hosting
        devices:
             {'hd_id1': {'routers': [id1, id2, ...],
                         'fw': [id1, ...],
                         ...},
              'hd_id2': {'routers': [id3, id4, ...]},
                         'fw': [id1, ...],
                         ...},
              ...}
        The <deconfigure> argument is True if any configurations for the
        logical resources should be removed from the hosting devices
        """
        if hosting_data:
            self._host_notification(context, 'hosting_devices_removed',
                                    {'hosting_data': hosting_data,
                                     'deconfigure': deconfigure}, host)

    # version 1,1
    def get_hosting_device_configuration(self, context, id):
        """Fetch configuration of hosting device with id.

        The configuration agent should respond with the running config of
        the hosting device.
        """
        admin_context = context.is_admin and context or context.elevated()
        agents = self._dmplugin.get_cfg_agents_for_hosting_devices(
            admin_context, [id], admin_state_up=True, schedule=True)
        if agents:
            cctxt = self.client.prepare(server=agents[0].host)
            return cctxt.call(context, 'get_hosting_device_configuration',
                              payload={'hosting_device_id': id})
