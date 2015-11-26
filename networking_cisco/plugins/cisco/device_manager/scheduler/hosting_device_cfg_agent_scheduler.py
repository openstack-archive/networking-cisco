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
# Based on Neutron L3 Agent scheduler.

import random

from oslo_log import log as logging
from sqlalchemy.orm import exc

from neutron.db import agents_db

from networking_cisco._i18n import _LW
from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)
from networking_cisco.plugins.cisco.db.scheduler import cfg_agentschedulers_db

LOG = logging.getLogger(__name__)


class HostingDeviceCfgAgentScheduler(object):
    """A scheduler for Cisco (hosting) device manager service plugin.

    It schedules hosting devices to Cisco cfg agents. The scheduling is a
    simple random selection among qualified candidates.
    """

    def auto_schedule_hosting_devices(self, plugin, context, agent_host):
        """Schedules unassociated hosting devices to Cisco cfg agent.

        Schedules hosting devices to agent running on <agent_host>.
        """
        query = context.session.query(agents_db.Agent)
        query = query.filter_by(agent_type=c_constants.AGENT_TYPE_CFG,
                                host=agent_host, admin_state_up=True)
        try:
            cfg_agent_db = query.one()
        except (exc.MultipleResultsFound, exc.NoResultFound):
            LOG.debug('No enabled Cisco cfg agent on host %s', agent_host)
            return
        if cfg_agentschedulers_db.CfgAgentSchedulerDbMixin.is_agent_down(
                cfg_agent_db.heartbeat_timestamp):
            LOG.warning(_LW('Cisco cfg agent %s is not alive'),
                        cfg_agent_db.id)
        return cfg_agent_db

    def schedule_hosting_device(self, plugin, context, hosting_device):
        """Selects Cisco cfg agent that will configure <hosting_device>."""
        active_cfg_agents = plugin.get_cfg_agents(context, active=True)
        if not active_cfg_agents:
            LOG.warning(_LW('There are no active Cisco cfg agents'))
            # No worries, once a Cisco cfg agent is started and
            # announces itself any "dangling" hosting devices
            # will be scheduled to it.
            return
        LOG.debug('Randomly selecting a Cisco cfg agent among %d candidates' %
                  len(active_cfg_agents))
        return random.choice(active_cfg_agents)


class StingyHostingDeviceCfgAgentScheduler(HostingDeviceCfgAgentScheduler):
    """
    This scheduler will assign a hosting device to an agent that has
    the fewest hosting devices associated to it
    """
    def schedule_hosting_device(self, plugin, context, hosting_device):
        active_cfg_agents = plugin.get_cfg_agents(context, active=True)
        if not active_cfg_agents:
            LOG.warning(_LW('There are no active Cisco cfg agents'))
            return
        else:
            cfg_agent_hosting_devices = []
            for active_cfg_agent in active_cfg_agents:
                hosting_devices = (
                    plugin.list_hosting_devices_handled_by_cfg_agent(
                        context, active_cfg_agent.id))
                LOG.debug("Cfg agent %s now handling %d hosting devices" % (
                    active_cfg_agent.id,
                    len(hosting_devices.get('hosting_devices'))))
                num_hosting_devices = len(hosting_devices.get(
                    'hosting_devices'))
                cfg_agent_hosting_devices.append((active_cfg_agent,
                                                  num_hosting_devices))
            cfg_agent_hosting_devices = sorted(
                cfg_agent_hosting_devices,
                key=lambda agent_hosting_device: agent_hosting_device[1])
            return cfg_agent_hosting_devices.pop(0)[0]
