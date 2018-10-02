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

from datetime import datetime
import eventlet
eventlet.monkey_patch()  # noqa

import pprint
import sys
import time

from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging
from oslo_service import loopingcall
from oslo_service import periodic_task
from oslo_service import service
from oslo_utils import importutils

from neutron.agent import rpc as agent_rpc
from neutron.common import config as common_config
from neutron.common import rpc as n_rpc
from neutron import manager
from neutron import service as neutron_service

from networking_cisco._i18n import _
from networking_cisco import backwards_compatibility as bc
from networking_cisco.backwards_compatibility import neutron_agent_conf
from networking_cisco.backwards_compatibility import topics
from networking_cisco.plugins.cisco.cfg_agent import device_status
from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)
from networking_cisco.plugins.cisco.device_manager import config


LOG = logging.getLogger(__name__)

# Constants for agent registration.
REGISTRATION_RETRY_DELAY = 2
MAX_REGISTRATION_ATTEMPTS = 30

ISO8601_TIME_FORMAT = bc.constants.ISO8601_TIME_FORMAT


class CiscoDeviceManagementApi(object):
    """Agent side of the device manager RPC API."""

    def __init__(self, topic, host):
        self.host = host
        target = oslo_messaging.Target(topic=topic, version='1.0')
        self.client = n_rpc.get_client(target)

    def report_dead_hosting_devices(self, context, hd_ids=None):
        """Report that a hosting device cannot be contacted (presumed dead).

        :param: context: session context
        :param: hosting_device_ids: list of non-responding hosting devices
        :return: None
        """
        cctxt = self.client.prepare()
        cctxt.cast(context, 'report_non_responding_hosting_devices',
                   host=self.host, hosting_device_ids=hd_ids)

    def report_revived_hosting_devices(self, context, hd_ids=None):
        cctxt = self.client.prepare(version='1.1')
        cctxt.cast(context, 'update_hosting_device_status',
                   host=self.host,
                   status_info={c_constants.HD_ACTIVE: hd_ids})

    def register_for_duty(self, context):
        """Report that a config agent is ready for duty."""
        cctxt = self.client.prepare()
        return cctxt.call(context, 'register_for_duty', host=self.host)

    def get_hosting_devices_for_agent(self, context):
        """Get a list of hosting devices assigned to this agent."""
        cctxt = self.client.prepare()
        return cctxt.call(context,
                          'get_hosting_devices_for_agent',
                          host=self.host)

OPTS = [
    cfg.IntOpt('rpc_loop_interval', default=10,
               help=_("Interval when the process_services() loop "
                      "executes in seconds. This is when the config agent "
                      "lets each service helper to process its neutron "
                      "resources.")),
    cfg.StrOpt('routing_svc_helper_class',
               default='networking_cisco.plugins.cisco.cfg_agent.'
                       'service_helpers.routing_svc_helper.'
                       'RoutingServiceHelper',
               help=_("Path of the routing service helper class.")),
    cfg.BoolOpt('enable_heartbeat',
                default=True,
                help=_("If enabled, the agent will maintain a heartbeat "
                       "against its hosting-devices. If a device dies "
                       "and recovers, the agent will then trigger a "
                       "configuration resync.")),
    cfg.IntOpt('heartbeat_interval', default=5,
               help=_("Interval in seconds when the config agent runs the "
                      "backlog / hosting-device heart beat task.")),
    cfg.IntOpt('max_device_sync_attempts', default=6,
               help=_("Maximum number of attempts for a device sync.")),
    cfg.IntOpt('max_device_sync_batch_size', default=64,
               help=_("The largest number of routers to fetch in one "
                      "RPC call.")),
    cfg.IntOpt('keepalive_interval', default=10,
               help=_("Interval in seconds when the config agent sents a "
                      "timestamp to the plugin to say that it is alive.")),
    cfg.IntOpt('report_iteration', default=6,
               help=_("The iteration where the config agent sends a full "
                      "status report to the plugin.  The default is every "
                      "6th iteration of the keep alive interval. This "
                      "means with default value of keepalive_interval "
                      "(10sec), a full report is sent once every "
                      "6*10 = 60 seconds.")),
]

cfg.CONF.register_opts(OPTS, "cfg_agent")


class CiscoCfgAgent(manager.Manager):
    """Cisco Cfg Agent.

    This class defines a generic configuration agent for cisco devices which
    implement network services in the cloud backend. It is based on the
    (reference) l3-agent, but has been enhanced to support multiple services
    in addition to routing.

    The agent acts like as a container for services and does not do any
    service specific processing or configuration itself.
    All service specific processing is delegated to service helpers which
    the agent loads. Thus routing specific updates are processed by the
    routing service helper, firewall by firewall helper etc.
    A further layer of abstraction is implemented by using device drivers for
    encapsulating all configuration operations of a service on a device.
    Device drivers are specific to a particular device/service VM eg: ASR1k.

    The main entry points in this class are the `process_services()` and
    `_backlog_task()` .
    """
    target = oslo_messaging.Target(version='1.1')

    def __init__(self, host, conf=None):
        self.conf = conf or cfg.CONF
        self._credentials = (
            config.obtain_hosting_device_credentials_from_config())
        self._dev_status = device_status.DeviceStatus()
        self._dev_status.enable_heartbeat = (
            self.conf.cfg_agent.enable_heartbeat)
        self.context = bc.context.get_admin_context_without_session()

        self._initialize_rpc(host)
        self._initialize_service_helpers(host)
        self._start_periodic_tasks()
        super(CiscoCfgAgent, self).__init__(host=self.conf.host)

    def _initialize_rpc(self, host):
        self.devmgr_rpc = CiscoDeviceManagementApi(
            c_constants.DEVICE_MANAGER_PLUGIN, host)

    def _initialize_service_helpers(self, host):
        svc_helper_class = self.conf.cfg_agent.routing_svc_helper_class
        try:
            self.routing_service_helper = importutils.import_object(
                svc_helper_class, host, self.conf, self)
        except ImportError as e:
            LOG.warning("Error in loading routing service helper. Class "
                        "specified is %(class)s. Reason:%(reason)s",
                        {'class': self.conf.cfg_agent.routing_svc_helper_class,
                         'reason': e})
            self.routing_service_helper = None

    def _start_periodic_tasks(self):
        self.loop = loopingcall.FixedIntervalLoopingCall(self.process_services)
        self.loop.start(interval=self.conf.cfg_agent.rpc_loop_interval)

    def after_start(self):
        hds = self.get_assigned_hosting_devices()
        if hds is None:
            LOG.warning("Unable to fetch hosting devices to monitor. Certain "
                        "hosting devices in DEAD state may not be revived. "
                        "Restart config agent to trigger new attempts.")
        else:
            LOG.info("To manage hosting devices %s", hds)
            self._dev_status.backlog_hosting_devices(hds)
        LOG.info("Cisco cfg agent started")

    def get_routing_service_helper(self):
        return self.routing_service_helper

    def get_hosting_device_password(self, credentials_id):
        creds = self._credentials.get(credentials_id)
        return creds['password'] if creds else None

    # Periodic tasks
    @periodic_task.periodic_task(spacing=cfg.CONF.cfg_agent.heartbeat_interval)
    def _backlog_task(self, context):
        """Process backlogged devices."""
        LOG.debug("Processing backlog.")
        self._process_backlogged_hosting_devices(context)

    # Main orchestrator
    @lockutils.synchronized('cisco-cfg-agent', 'neutron-')
    def process_services(self, device_ids=None, removed_devices_info=None):
        """Process services managed by this config agent.

        This method is invoked by any of three scenarios.

        1. Invoked by a periodic task running every `RPC_LOOP_INTERVAL`
        seconds. This is the most common scenario.
        In this mode, the method is called without any arguments.

        2. Called by the `_process_backlogged_hosting_devices()` as part of
        the backlog processing task. In this mode, a list of device_ids
        are passed as arguments. These are the list of backlogged
        hosting devices that are now reachable and we want to sync services
        on them.

        3. Called by the `hosting_devices_removed()` method. This is when
        the config agent has received a notification from the plugin that
        some hosting devices are going to be removed. The payload contains
        the details of the hosting devices and the associated neutron
        resources on them which should be processed and removed.

        To avoid race conditions with these scenarios, this function is
        protected by a lock.

        This method goes on to invoke `process_service()` on the
        different service helpers.

        :param device_ids: List of devices that are now available and needs to
            be processed
        :param removed_devices_info: Info about the hosting devices which are
            going to be removed and details of the resources hosted on them.
            Expected Format::

                {
                 'hosting_data': {'hd_id1': {'routers': [id1, id2, ...]},
                                  'hd_id2': {'routers': [id3, id4, ...]}, ...},
                 'deconfigure': True/False
                }

        :returns: None

        """
        LOG.debug("Processing services started")
        # Now we process only routing service, additional services will be
        # added in future
        if self.routing_service_helper:
            self.routing_service_helper.process_service(device_ids,
                                                        removed_devices_info)
        else:
            LOG.warning("No routing service helper loaded")
        LOG.debug("Processing services completed")

    def _process_backlogged_hosting_devices(self, context):
        """Process currently backlogged devices.

        Go through the currently backlogged devices and process them.
        For devices which are now reachable (compared to last time), we call
        `process_services()` passing the now reachable device's id.
        For devices which have passed the `hosting_device_dead_timeout` and
        hence presumed dead, execute a RPC to the plugin informing that.

        heartbeat revision
        res['reachable'] - hosting device went from Unknown to Active state
                           process_services(...)
        res['revived']   - hosting device went from Dead to Active
                           inform device manager that the hosting
                           device is now responsive
        res['dead']      - hosting device went from Unknown to Dead
                           inform device manager that the hosting
                           device is non-responding

        As additional note for the revived case:
            Although the plugin was notified, there may be some lag
            before the plugin actually can reschedule it's backlogged routers.

            If process_services(device_ids...) isn't successful initially,
            subsequent device syncs will be attempted until
            MAX_DEVICE_SYNC_ATTEMPTS occurs.  Main process_service task
            will resume if sync_devices is populated.

        :param context: RPC context
        :return: None
        """
        driver_mgr = self.get_routing_service_helper().driver_manager
        res = self._dev_status.check_backlogged_hosting_devices(driver_mgr)
        if res['reachable']:
            self.process_services(device_ids=res['reachable'])
        if res['revived']:
            LOG.debug("Reporting revived hosting devices: %s " %
                      res['revived'])
            # trigger a sync only on the revived hosting-devices
            if self.conf.cfg_agent.enable_heartbeat is True:
                self.devmgr_rpc.report_revived_hosting_devices(
                    context, hd_ids=res['revived'])
                self.process_services(device_ids=res['revived'])
        if res['dead']:
            LOG.debug("Reporting dead hosting devices: %s", res['dead'])
            self.devmgr_rpc.report_dead_hosting_devices(context,
                                                        hd_ids=res['dead'])

    def agent_updated(self, context, payload):
        """Deal with agent updated RPC message."""
        try:
            if payload['admin_state_up']:
                #TODO(hareeshp): implement agent updated handling
                pass
        except KeyError as e:
            LOG.error("Invalid payload format for received RPC message "
                      "`agent_updated`. Error is %(error)s. Payload is "
                      "%(payload)s", {'error': e, 'payload': payload})

    def hosting_devices_assigned_to_cfg_agent(self, context, payload):
        """Deal with hosting devices assigned to this config agent."""
        LOG.debug("Got hosting device assigned, payload: %s" % payload)
        try:
            if payload['hosting_device_ids']:
                #TODO(hareeshp): implement assignment of hosting devices
                self.routing_service_helper.fullsync = True
        except KeyError as e:
            LOG.error("Invalid payload format for received RPC message "
                      "`hosting_devices_assigned_to_cfg_agent`. Error is "
                      "%(error)s. Payload is %(payload)s",
                      {'error': e, 'payload': payload})

    def hosting_devices_unassigned_from_cfg_agent(self, context, payload):
        """Deal with hosting devices unassigned from this config agent."""
        try:
            if payload['hosting_device_ids']:
                #TODO(hareeshp): implement unassignment of hosting devices
                pass
        except KeyError as e:
            LOG.error("Invalid payload format for received RPC message "
                      "`hosting_devices_unassigned_from_cfg_agent`. Error "
                      "is %(error)s. Payload is %(payload)s",
                      {'error': e, 'payload': payload})

    def hosting_devices_removed(self, context, payload):
        """Deal with hosting device removed RPC message."""
        try:
            if payload['hosting_data']:
                if payload['hosting_data'].keys():
                    self.process_services(removed_devices_info=payload)
        except KeyError as e:
            LOG.error("Invalid payload format for received RPC message "
                      "`hosting_devices_removed`. Error is %(error)s. Payload "
                      "is %(payload)s", {'error': e, 'payload': payload})

    def get_assigned_hosting_devices(self, max_retry_attempts=3):
        context = bc.context.get_admin_context_without_session()
        for attempts in range(max_retry_attempts):
            try:
                return self.devmgr_rpc.get_hosting_devices_for_agent(context)
            except Exception:
                LOG.warning("Failed attempt to fetch hosting devices to "
                            "manage. Retrying in %0.2f second.",
                            REGISTRATION_RETRY_DELAY)
                time.sleep(REGISTRATION_RETRY_DELAY)
        return None

    def get_hosting_device_configuration(self, context, payload):
        LOG.debug('Processing request to fetching running config')
        hd_id = payload['hosting_device_id']
        svc_helper = self.routing_service_helper
        if hd_id and svc_helper:
            LOG.debug('Fetching running config for %s' % hd_id)
            drv = svc_helper.driver_manager.get_driver_for_hosting_device(
                hd_id)
            rc = drv.get_configuration()
            if rc:
                LOG.debug('Fetched %(chars)d characters long running config '
                          'for %(hd_id)s' % {'chars': len(rc), 'hd_id': hd_id})
                return rc
        LOG.debug('Unable to get running config')
        return


class CiscoCfgAgentWithStateReport(CiscoCfgAgent):

    def __init__(self, host, conf=None):
        self.state_rpc = agent_rpc.PluginReportStateAPI(topics.PLUGIN)
        self.agent_state = {
            'binary': 'neutron-cisco-cfg-agent',
            'host': host,
            'topic': c_constants.CFG_AGENT,
            'configurations': {},
            'start_flag': True,
            'agent_type': c_constants.AGENT_TYPE_CFG}
        self.use_call = True
        self._initialize_rpc(host)
        self._agent_registration()
        super(CiscoCfgAgentWithStateReport, self).__init__(host=host,
                                                           conf=conf)

        self.report_iteration = self.conf.cfg_agent.report_iteration
        keepalive_interval = self.conf.cfg_agent.keepalive_interval
        if keepalive_interval:
            self.heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            self.heartbeat.start(interval=keepalive_interval)
            self.keepalive_iteration = 0

    def _agent_registration(self):
        """Register this agent with the server.

        This method registers the cfg agent with the neutron server so hosting
        devices can be assigned to it. In case the server is not ready to
        accept registration (it sends a False) then we retry registration
        for `MAX_REGISTRATION_ATTEMPTS` with a delay of
        `REGISTRATION_RETRY_DELAY`. If there is no server response or a
        failure to register after the required number of attempts,
        the agent stops itself.
        """
        for attempts in range(MAX_REGISTRATION_ATTEMPTS):
            context = bc.context.get_admin_context_without_session()
            self.send_agent_report(self.agent_state, context)
            try:
                res = self.devmgr_rpc.register_for_duty(context)
            except Exception:
                res = False
                LOG.warning("[Agent registration] Rpc exception. Neutron "
                            "may not be available or busy. Retrying "
                            "in %0.2f seconds ", REGISTRATION_RETRY_DELAY)
            if res is True:
                LOG.info("[Agent registration] Agent successfully registered")
                return
            elif res is False:
                LOG.warning("[Agent registration] Neutron server said "
                            "that device manager was not ready. Retrying "
                            "in %0.2f seconds ", REGISTRATION_RETRY_DELAY)
                time.sleep(REGISTRATION_RETRY_DELAY)
            elif res is None:
                LOG.error("[Agent registration] Neutron server said that "
                          "no device manager was found. Cannot continue. "
                          "Exiting!")
                raise SystemExit(_("Cfg Agent exiting"))
        LOG.error("[Agent registration] %d unsuccessful registration "
                  "attempts. Exiting!", MAX_REGISTRATION_ATTEMPTS)
        raise SystemExit(_("Cfg Agent exiting"))

    def _report_state(self):
        """Report state to the plugin.

        This task run every `keepalive_interval` period.
        Collects, creates and sends a summary of the services currently
        managed by this agent. Data is collected from the service helper(s).
        Refer the `configurations` dict for the parameters reported.
        :return: None
        """
        LOG.debug("Report state task started")
        self.keepalive_iteration += 1
        if self.keepalive_iteration == self.report_iteration:
            self._prepare_full_report_data()
            self.keepalive_iteration = 0
            LOG.debug("State report: %s", pprint.pformat(self.agent_state))
        else:
            self.agent_state.pop('configurations', None)
            self.agent_state['local_time'] = datetime.now().strftime(
                ISO8601_TIME_FORMAT)
            LOG.debug("State report: %s", self.agent_state)
        self.send_agent_report(self.agent_state, self.context)

    def _prepare_full_report_data(self):
        configurations = {}
        service_agents = []
        self.agent_state['configurations'] = configurations
        if self.routing_service_helper:
            service_agents.append(c_constants.AGENT_TYPE_L3_CFG)
            configurations = self.routing_service_helper.collect_state(
                self.agent_state['configurations'])
        non_responding = self._dev_status.get_backlogged_hosting_devices_info()
        monitored_hosting_devices = (self._dev_status.
                                     get_monitored_hosting_devices_info())
        configurations['non_responding_hosting_devices'] = non_responding
        configurations['monitored_hosting_devices'] = monitored_hosting_devices
        configurations['service_agents'] = service_agents
        self.agent_state['configurations'] = configurations
        self.agent_state['local_time'] = datetime.now().strftime(
            ISO8601_TIME_FORMAT)

    def send_agent_report(self, report, context):
        """Send the agent report via RPC."""
        try:
            self.state_rpc.report_state(context, report, self.use_call)
            report.pop('start_flag', None)
            self.use_call = False
            LOG.debug("Send agent report successfully completed")
        except AttributeError:
            # This means the server does not support report_state
            LOG.warning("Neutron server does not support state report. "
                        "State report for this agent will be disabled.")
            self.heartbeat.stop()
            return
        except Exception:
            LOG.warning("Failed sending agent report!")


def _mock_stuff():
    import mock

    targets = ['networking_cisco.plugins.cisco.cfg_agent.device_drivers.'
               'iosxe.iosxe_routing_driver.manager']
    ncc_patchers = []
    ncclient_mock = mock.MagicMock()
    ok_xml_obj = mock.MagicMock()
    ok_xml_obj.xml = "<ok />"
    ncclient_mock.connect.return_value.edit_config.return_value = ok_xml_obj
    for target in targets:
        patcher = mock.patch(target, ncclient_mock)
        patcher.start()
        ncc_patchers.append(patcher)

    targets = ['networking_cisco.plugins.cisco.cfg_agent.device_drivers.'
               'iosxe.iosxe_routing_driver.IosXeRoutingDriver.'
               '_get_running_config',
               'networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k.'
               'asr1k_cfg_syncer.ConfigSyncer.get_running_config']
    fake_running_config = ("interface GigabitEthernet1\n"
                           "ip address 10.0.0.10 255.255.255.255\n"
                           "ip route 0.0.0.0 0.0.0.0 GigabitEthernet1 "
                           "10.0.0.1")
    g_r_c_patchers = []
    g_r_c_mock = mock.MagicMock(return_value=fake_running_config)
    for target in targets:
        patcher = mock.patch(target, g_r_c_mock)
        patcher.start()
        g_r_c_patchers.append(patcher)

    is_pingable_mock = mock.MagicMock(return_value=True)
    pingable_patcher = mock.patch(
        'networking_cisco.plugins.cisco.cfg_agent.device_status._is_pingable',
        is_pingable_mock)
    pingable_patcher.start()


# NOTE(bobmel): call mock_ncclient() in main() of cfg_agent.py to run config
# agent with a fake ncclient. That mocked mode of running the config agent is
# useful for end-2-end-like debugging without actual backend hosting devices.
def mock_ncclient():
    import mock
    from ncclient.transport import errors as ncc_exc
    from networking_cisco.plugins.cisco.common import (cisco_ios_xe_simulator
        as cisco_ios_xe)
    import os

    def _fake_connect(host, port, username, password, device_params, timeout):
        sim = cisco_ios_xe.CiscoIOSXESimulator(
            '', host, "255.255.255.0", port, username, password,
            device_params, "GigabitEthernet0", timeout)
        connection_mock = mock.MagicMock()
        connection_mock.edit_config.side_effect = _get_fake_edit_config(sim)
        connection_mock.get_config.side_effect = (
            _get_fake_get_config(sim))
        return connection_mock

    def _get_fake_edit_config(simulator):

        def edit_config(config, format='xml', target='candidate',
                        default_operation=None, test_option=None,
                        error_option=None):
            if not _fake_is_pingable(rc_emul.host_ip):
                raise ncc_exc.SSHError('SSH error')
            rc_emul.edit_config(config)
            print(rc_emul.get_config())
            return ok_xml_obj

        ok_xml_obj = mock.MagicMock()
        ok_xml_obj.xml = "<ok />"
        rc_emul = simulator
        return edit_config

    def _get_fake_get_config(simulator):

        def get_running_config(source):
            if not _fake_is_pingable(rc_emul.host_ip):
                raise ncc_exc.SSHError('SSH error')
            head = ('<?xml version="1.0" encoding="UTF-8"?><rpc-reply '
                    'message-id="urn:uuid:ec8bab72-a500-11e5-a92f'
                    '-74a2e6d55908" xmlns="urn:ietf:params:xml:ns:netconf:'
                    'base:1.0"><data><cli-config-data-block>!')
            tail = '</cli-config-data-block></data></rpc-reply>'
            raw_rc = rc_emul.get_config()
            return cisco_ios_xe.FakeRunningConfig(head + raw_rc + tail)

        rc_emul = simulator
        return get_running_config

    def _fake_is_pingable(ip):
        # if a file with a certain name (derived from the 'ip' argument):
        #
        #     /opt/stack/data/neutron/DEAD__10_0_5_8       (ip = 10.0.5.8)
        #
        # exists then the (faked) hosting device with that IP address
        # will appear to NOT respond to pings
        path = '/opt/stack/data/neutron'
        indicator_filename = path + '/DEAD_' + str(ip).replace('.', '_')
        return not os.path.isfile(indicator_filename)

    def _fake_can_connect(ip, port):
        # if a file with a certain name (derived from the 'ip' and
        # 'port's arguments):
        #
        #     /opt/stack/data/neutron/DEAD__10_0_5_8__22       (ip = 10.0.5.8
        #                                                       port = 22)
        #
        # exists then the (faked) hosting device with that IP address
        # will appear NOT to have that port open
        path = '/opt/stack/data/neutron'
        indicator_filename = (path + '/DEAD__' + str(ip).replace('.', '_') +
                              '__' + str(port))
        return not os.path.isfile(indicator_filename)

    targets = ['networking_cisco.plugins.cisco.cfg_agent.device_drivers.'
               'iosxe.iosxe_routing_driver.manager']
    ncc_patchers = []
    ncclient_mgr_mock = mock.MagicMock()
    ncclient_mgr_mock.connect.side_effect = _fake_connect

    for target in targets:
        patcher = mock.patch(target, ncclient_mgr_mock)
        patcher.start()
        ncc_patchers.append(patcher)

    is_pingable_mock = mock.MagicMock()
    is_pingable_mock.side_effect = _fake_is_pingable
    pingable_patcher = mock.patch(
        'networking_cisco.plugins.cisco.cfg_agent.device_status._is_pingable',
        is_pingable_mock)
    pingable_patcher.start()

    can_connect_mock = mock.MagicMock(side_effect=_fake_can_connect)
    can_connect_patcher = mock.patch(
        'networking_cisco.plugins.cisco.cfg_agent.device_status._can_connect',
        can_connect_mock)
    can_connect_patcher.start()


def main(manager='networking_cisco.plugins.cisco.cfg_agent.'
                 'cfg_agent.CiscoCfgAgentWithStateReport'):
    # NOTE(bobmel): call _mock_stuff() to run config agent with fake ncclient
    # This mocked mode of running the config agent is useful for end-2-end-like
    # debugging without actual backend hosting devices.
    #_mock_stuff()
    #mock_ncclient()
    conf = cfg.CONF
    conf.register_opts(OPTS, "cfg_agent")
    bc.config.register_agent_state_opts_helper(conf)
    bc.config.register_root_helper(conf)
    conf.register_opts(neutron_agent_conf.INTERFACE_OPTS)
    conf.register_opts(neutron_agent_conf.EXTERNAL_PROCESS_OPTS)
    common_config.init(sys.argv[1:])
    conf(project='neutron')
    bc.config.setup_logging()
    server = neutron_service.Service.create(
        binary='neutron-cisco-cfg-agent',
        topic=c_constants.CFG_AGENT,
        report_interval=cfg.CONF.AGENT.report_interval,
        manager=manager)
    service.launch(cfg.CONF, server).wait()
