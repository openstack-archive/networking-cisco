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

from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils
import six

from neutron import context as n_context
from neutron.db import agents_db
from neutron.db import agentschedulers_db
from neutron.extensions import agent as ext_agent

from networking_cisco._i18n import _, _LI
from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)
from networking_cisco.plugins.cisco.db.device_manager.hd_models import (
    HostingDevice)
from networking_cisco.plugins.cisco.extensions import ciscocfgagentscheduler

LOG = logging.getLogger(__name__)


COMPOSITE_AGENTS_SCHEDULER_OPTS = [
    cfg.IntOpt('cfg_agent_down_time', default=30,
               help=_('Seconds of no status update until a cfg agent '
                      'is considered down.')),
    cfg.StrOpt('configuration_agent_scheduler_driver',
               default='networking_cisco.plugins.cisco.device_manager.'
                       'scheduler.hosting_device_cfg_agent_scheduler.'
                       'HostingDeviceCfgAgentScheduler',
               help=_('Driver to use for scheduling hosting device to a Cisco '
                      'configuration agent')),
    cfg.IntOpt('cfg_agent_monitoring_interval', default=20,
               help=("Maximal time (in seconds) between checks of config "
                     "agent status"))

]

cfg.CONF.register_opts(COMPOSITE_AGENTS_SCHEDULER_OPTS, "general")


class CfgAgentSchedulerDbMixin(
        ciscocfgagentscheduler.CfgAgentSchedulerPluginBase,
        agentschedulers_db.AgentSchedulerDbMixin):
    """Mixin class to add cfg agent scheduler extension."""

    # Scheduler of hosting devices to configuration agent
    cfg_agent_scheduler = None

    # Cache of statuses of cfg agents:
    # dict {<hd_id>: {'timestamp': <datetime.now()>
    _cfg_agent_statuses = {}

    @classmethod
    def is_agent_down(cls, heart_beat_time,
                      timeout=cfg.CONF.general.cfg_agent_down_time):
        return timeutils.is_older_than(heart_beat_time, timeout)

    def auto_schedule_hosting_devices(self, context, host):
        if self.cfg_agent_scheduler:
            cfg_agent_db = (
                self.cfg_agent_scheduler.auto_schedule_hosting_devices(
                    self, context, host))
            if not cfg_agent_db:
                return False
            with context.session.begin(subtransactions=True):
                query = context.session.query(HostingDevice)
                query = query.filter_by(cfg_agent_id=None)
                for hosting_device in query:
                    self._bind_hosting_device_to_cfg_agent(
                        context, hosting_device, cfg_agent_db)
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
        cfg_agents_db = query.all()
        if active is not None:
            cfg_agents_db = [
                cfg_agent_db for cfg_agent_db in cfg_agents_db
                if not self.is_agent_down(cfg_agent_db.heartbeat_timestamp)]
        return cfg_agents_db

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
            agent_assigned_hd_ids = {}
            for hosting_device_db in query:
                current_agent_db = hosting_device_db.cfg_agent
                if current_agent_db:
                    self.set_monitor_timestamp(current_agent_db,
                                               timeutils.utcnow())
                    if (self.is_agent_down(
                            current_agent_db.heartbeat_timestamp) and
                            schedule):
                        # hosting device is handled by dead cfg agent so we'll
                        # try to reassign it to another cfg agent
                        LOG.info(_LI('Config agent %(agent_id)s is not alive. '
                                     'Un-assigning hosting device %(hd_id)s '
                                     'managed by it.'),
                                 {'agent_id': current_agent_db.id,
                                  'hd_id': hosting_device_db.id})
                        hosting_device_db.cfg_agent = None
                if hosting_device_db.cfg_agent is None:
                    if schedule:
                        # only active cfg agents are considered by scheduler
                        agent_db = (
                            self.cfg_agent_scheduler.schedule_hosting_device(
                                self, context, hosting_device_db))
                        if agent_db is None:
                            continue
                        self._bind_hosting_device_to_cfg_agent(
                            context, hosting_device_db, agent_db)
                        agents.append(agent_db)
                        try:
                            agent_assigned_hd_ids[agent_db.id][
                                'hd_ids'].append(hosting_device_db.id)
                        except KeyError:
                            agent_assigned_hd_ids[agent_db.id] = {
                                'agent_host': agent_db.host,
                                'hd_ids': [hosting_device_db.id]}
                else:
                    agents.append(hosting_device_db.cfg_agent)
            self._notify_assignment(context, agent_assigned_hd_ids)
            return agents

    def _bind_hosting_device_to_cfg_agent(self, context, hosting_device_db,
                                          cfg_agent_db):
        with context.session.begin(subtransactions=True):
            if not hosting_device_db:
                LOG.debug('Hosting device to schedule not specified')
                return
            LOG.info(_LI('Assigning hosting device %(hd_id)s to config agent '
                         '%(agent_id)s.'),
                     {'hd_id': hosting_device_db.id,
                      'agent_id':
                          cfg_agent_db.id if cfg_agent_db else None})
            hosting_device_db.cfg_agent = cfg_agent_db
            context.session.add(hosting_device_db)

    @lockutils.synchronized('devicemonitor', 'neutron-')
    def set_monitor_timestamp(self, agent, timestamp):
        self._cfg_agent_statuses[agent['id']] = {'timestamp': timestamp}

    def _sync_config_agent_monitoring(self, context):
        LOG.debug('Syncing monitored config agents')
        agents = self.get_agents(
            context, filters={'agent_type': [c_constants.AGENT_TYPE_CFG]},
            fields=['id'])
        self._cfg_agent_statuses = {agent['id']: {
            'timestamp': timeutils.utcnow()}
                                    for agent in agents}
        LOG.debug('Monitored config agents %s:' %
                  self._cfg_agent_statuses.keys())

    @lockutils.synchronized('devicemonitor', 'neutron-')
    def _check_config_agents(self):
        e_context = n_context.get_admin_context()
        if not self._cfg_agent_statuses:
            self._sync_config_agent_monitoring(e_context)
        to_remove = []
        LOG.debug('In _check_config_agents: Monitored config agents %s:' %
                  self._cfg_agent_statuses.keys())
        for cfg_agent_id, info in six.iteritems(self._cfg_agent_statuses):
            if self.should_check_agent(info['timestamp']):
                # agent has not been checked recently so do it now
                LOG.debug('Must check status of config agent %s' %
                          cfg_agent_id)
                try:
                    agent = self.get_agent(e_context, cfg_agent_id)
                except ext_agent.AgentNotFound:
                    LOG.debug('Config agent %s does not exist anymore. Will '
                              'remove it from monitored config agents' %
                              cfg_agent_id)
                    to_remove.append(cfg_agent_id)
                    continue
                info['timestamp'] = timeutils.utcnow()
                if self.is_agent_down(agent['heartbeat_timestamp']):
                    LOG.info(_LI('Config agent %s is not alive. Un-assigning '
                                 'hosting devices managed by it.'),
                             cfg_agent_id)
                    self._reschedule_hosting_devices(e_context, cfg_agent_id)
        for cfg_agent_id in to_remove:
            LOG.debug('Removing config agent %s from monitored config agents' %
                      cfg_agent_id)
            del self._cfg_agent_statuses[cfg_agent_id]

    def _reschedule_hosting_devices(self, context, cfg_agent_id):
        with context.session.begin(subtransactions=True):
            agent_assigned_hd_ids = {}
            filters = {'cfg_agent_id': [cfg_agent_id]}
            for hd_db in self._get_collection_query(context, HostingDevice,
                                                    filters=filters):
                agent_db = self.cfg_agent_scheduler.schedule_hosting_device(
                    self, context, hd_db)
                LOG.info(_LI('Un-assigning hosting device %(hd_id)s from '
                             'config agent %(agent_id)s.'),
                         {'hd_id': hd_db.id, 'agent_id': cfg_agent_id})
                if agent_db is None:
                    hd_db.cfg_agent_id = None
                else:
                    self._bind_hosting_device_to_cfg_agent(context, hd_db,
                                                           agent_db)
                    try:
                        agent_assigned_hd_ids[agent_db.id]['hd_ids'].append(
                            hd_db.id)
                    except KeyError:
                        agent_assigned_hd_ids[agent_db.id] = {
                            'agent_host': agent_db.host,
                            'hd_ids': [hd_db.id]}
        self._notify_assignment(context, agent_assigned_hd_ids)

    def _notify_assignment(self, context, agent_assigned_hd_ids):
        cfg_notifier = self.agent_notifiers.get(c_constants.AGENT_TYPE_CFG)
        if cfg_notifier:
            for agent_id, info in six.iteritems(agent_assigned_hd_ids):
                cfg_notifier.hosting_devices_assigned_to_cfg_agent(
                    context, info['hd_ids'], info['agent_host'])

    @classmethod
    def should_check_agent(
            cls, heart_beat_time,
            timeout=cfg.CONF.general.cfg_agent_monitoring_interval):
        return timeutils.is_older_than(heart_beat_time, timeout)
