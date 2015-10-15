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

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils
import six

from neutron.db import agents_db
from neutron.db import agentschedulers_db

from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)
from networking_cisco.plugins.cisco.db.device_manager.hd_models import (
    HostingDevice)
from networking_cisco.plugins.cisco.extensions import ciscocfgagentscheduler

LOG = logging.getLogger(__name__)


COMPOSITE_AGENTS_SCHEDULER_OPTS = [
    cfg.IntOpt('cfg_agent_down_time', default=60,
               help=_('Seconds of no status update until a cfg agent '
                      'is considered down.')),
    cfg.StrOpt('configuration_agent_scheduler_driver',
               default='networking_cisco.plugins.cisco.device_manager.'
                       'scheduler.hosting_device_cfg_agent_scheduler.'
                       'HostingDeviceCfgAgentScheduler',
               help=_('Driver to use for scheduling hosting device to a Cisco '
                      'configuration agent')),
]

cfg.CONF.register_opts(COMPOSITE_AGENTS_SCHEDULER_OPTS, "general")


class CfgAgentSchedulerDbMixin(
        ciscocfgagentscheduler.CfgAgentSchedulerPluginBase,
        agentschedulers_db.AgentSchedulerDbMixin):
    """Mixin class to add cfg agent scheduler extension."""

    cfg_agent_scheduler = None

    @classmethod
    def is_agent_down(cls, heart_beat_time,
                      timeout=cfg.CONF.general.cfg_agent_down_time):
        return timeutils.is_older_than(heart_beat_time, timeout)

    def auto_schedule_hosting_devices(self, context, host):
        if self.cfg_agent_scheduler:
            cfg_agent = self.cfg_agent_scheduler.auto_schedule_hosting_devices(
                self, context, host)
            if not cfg_agent:
                return False
            with context.session.begin(subtransactions=True):
                query = context.session.query(HostingDevice)
                query = query.filter_by(cfg_agent_id=None)
                for hosting_device in query:
                    self._bind_hosting_device_to_cfg_agent(
                        context, hosting_device, cfg_agent)
            return True
        return False

    def assign_hosting_device_to_cfg_agent(self, context, cfg_agent_id,
                                           hosting_device_id):
        """Make config agent handle an (unassigned) hosting device."""
        hd_db = self._get_hosting_device(context, hosting_device_id)
        if hd_db.cfg_agent_id:
            if hd_db.cfg_agent_id == cfg_agent_id:
                return
            LOG.debug('Hosting device %(hd_id)s has already been assigned to '
                      'Cisco cfg agent %(agent_id)s',
                      {'hd_id': hosting_device_id, 'agent_id': cfg_agent_id})
            raise ciscocfgagentscheduler.HostingDeviceAssignedToCfgAgent(
                hosting_device_id=hosting_device_id, agent_id=cfg_agent_id)
        cfg_agent_db = self._get_agent(context, cfg_agent_id)
        if (cfg_agent_db.agent_type != c_constants.AGENT_TYPE_CFG or
                cfg_agent_db.admin_state_up is not True):
            raise ciscocfgagentscheduler.InvalidCfgAgent(agent_id=cfg_agent_id)
        self._bind_hosting_device_to_cfg_agent(context, hd_db, cfg_agent_db)
        cfg_notifier = self.agent_notifiers.get(c_constants.AGENT_TYPE_CFG)
        if cfg_notifier:
            cfg_notifier.hosting_devices_assigned_to_cfg_agent(
                context, [hosting_device_id], cfg_agent_db.host)

    def unassign_hosting_device_from_cfg_agent(self, context, cfg_agent_id,
                                               hosting_device_id):
        """Make config agent handle an (unassigned) hosting device."""
        hd_db = self._get_hosting_device(context, hosting_device_id)
        if hd_db.cfg_agent_id is None and cfg_agent_id is None:
            return
        elif hd_db.cfg_agent_id != cfg_agent_id:
            LOG.debug('Hosting device %(hd_id)s is not assigned to Cisco '
                      'cfg agent %(agent_id)s',
                      {'hd_id': hosting_device_id,
                       'agent_id': cfg_agent_id})
            raise ciscocfgagentscheduler.HostingDeviceNotAssignedToCfgAgent(
                hosting_device_id=hosting_device_id, agent_id=cfg_agent_id)
        cfg_agent_db = self._get_agent(context, cfg_agent_id)
        cfg_notifier = self.agent_notifiers.get(c_constants.AGENT_TYPE_CFG)
        if cfg_notifier:
            cfg_notifier.hosting_devices_unassigned_from_cfg_agent(
                context, [hosting_device_id], cfg_agent_db.host)
        self._bind_hosting_device_to_cfg_agent(context, hd_db, None)

    def list_hosting_devices_handled_by_cfg_agent(self, context, cfg_agent_id):
        return {'hosting_devices': self.get_hosting_devices(
            context, filters={'cfg_agent_id': [cfg_agent_id]})}

    def list_cfg_agents_handling_hosting_device(self, context,
                                                hosting_device_id):
        hd = self.get_hosting_device(context, hosting_device_id)
        cfg_agents = [self.get_agent(context, hd['cfg_agent_id'])] if hd[
            'cfg_agent_id'] else []
        return {'agents': cfg_agents}

    def get_cfg_agents(self, context, active=None, filters=None):
        query = context.session.query(agents_db.Agent)
        query = query.filter(
            agents_db.Agent.agent_type == c_constants.AGENT_TYPE_CFG)
        if active is not None:
            query = (query.filter(agents_db.Agent.admin_state_up == active))
        if filters:
            for key, value in six.iteritems(filters):
                column = getattr(agents_db.Agent, key, None)
                if column:
                    query = query.filter(column.in_(value))
        cfg_agents = query.all()
        if active is not None:
            cfg_agents = [cfg_agent for cfg_agent in cfg_agents
                          if not self.is_agent_down(
                              cfg_agent['heartbeat_timestamp'])]
        return cfg_agents

    def get_cfg_agents_for_hosting_devices(self, context, hosting_device_ids,
                                           admin_state_up=None,
                                           schedule=False):
        if not hosting_device_ids:
            return []
        with context.session.begin(subtransactions=True):
            query = self.get_hosting_devices_qry(context, hosting_device_ids)
            if admin_state_up is not None:
                query = query.filter(
                    agents_db.Agent.admin_state_up == admin_state_up)
            agents = []
            cfg_notifier = self.agent_notifiers.get(c_constants.AGENT_TYPE_CFG)
            for hosting_device in query:
                current_agent = hosting_device.cfg_agent
                if (current_agent and self.is_agent_down(
                        current_agent['heartbeat_timestamp']) and schedule):
                    # hosting device is handled by dead cfg agent so we'll try
                    # to reassign it to another cfg agent
                    current_agent = None
                if current_agent is None:
                    if schedule:
                        # only active cfg agents are considered by scheduler
                        agent = (
                            self.cfg_agent_scheduler.schedule_hosting_device(
                                self, context, hosting_device))
                        if agent is None:
                            continue
                        self._bind_hosting_device_to_cfg_agent(
                            context, hosting_device, agent)
                        agents.append(agent)
                        if cfg_notifier:
                            cfg_notifier.hosting_devices_assigned_to_cfg_agent(
                                context, [hosting_device['id']], agent['host'])
                else:
                    agents.append(hosting_device.cfg_agent)
            return agents

    def _bind_hosting_device_to_cfg_agent(self, context, hosting_device_db,
                                          cfg_agent_db):
        with context.session.begin(subtransactions=True):
            if not hosting_device_db:
                LOG.debug('Hosting device to schedule not specified')
                return
            hosting_device_db.cfg_agent = cfg_agent_db
            context.session.add(hosting_device_db)
