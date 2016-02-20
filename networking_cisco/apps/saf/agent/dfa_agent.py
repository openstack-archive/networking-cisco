# Copyright 2015 Cisco Systems, Inc.
# All Rights Reserved.
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


import os
import platform
import sys
import time

import eventlet
eventlet.monkey_patch()
from oslo_serialization import jsonutils

from networking_cisco._i18n import _LE, _LI

from networking_cisco.apps.saf.agent import iptables_driver as iptd
from networking_cisco.apps.saf.agent.vdp import dfa_vdp_mgr as vdpm
from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.common import constants
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import rpc
from networking_cisco.apps.saf.common import utils


LOG = logging.getLogger(__name__)

thishost = platform.node()


class RpcCallBacks(object):

    """RPC call back methods."""

    def __init__(self, vdpd, ipt_drvr):
        self._vdpd = vdpd
        self._iptd = ipt_drvr

    def send_vm_info(self, context, msg):
        vm_info = eval(msg)
        LOG.debug('Received %(vm_info)s for %(instance)s', (
            {'vm_info': vm_info, 'instance': vm_info.get('inst_name')}))
        # Call VDP/LLDPad API to send the info
        self._vdpd.vdp_vm_event(vm_info)

        # Enqueue the vm info for updating iptables.
        oui = vm_info.get('oui')
        if oui and oui.get('ip_addr') != '0.0.0.0' and self._iptd:
            rule_info = dict(mac=vm_info.get('vm_mac'), ip=oui.get('ip_addr'),
                             port=vm_info.get('port_uuid'),
                             status=vm_info.get('status'))
            self._iptd.enqueue_event(rule_info)

    def update_ip_rule(self, context, msg):
        rule_info = eval(msg)
        LOG.debug('RX Info : %s', rule_info)
        # Update the iptables for this rule
        if self._iptd:
            self._iptd.enqueue_event(rule_info)

    def send_msg_to_agent(self, context, msg):
        msg_type = context.get('type')
        uplink = jsonutils.loads(msg)
        LOG.debug("Received %(context)s and %(msg)s", (
            {'context': context, 'msg': uplink}))
        if msg_type == constants.UPLINK_NAME:
            LOG.debug("uplink is %(uplink)s", uplink)
            self._vdpd.dfa_uplink_restart(uplink)


class DfaAgent(object):

    """DFA agent."""

    def __init__(self, host, rpc_qn):
        self._host_name = host
        self._cfg = config.CiscoDFAConfig('neutron').cfg
        self._my_host = self._cfg.DEFAULT.host if self._cfg.DEFAULT.host else (
            utils.find_agent_host_id(host))
        self._qn = '_'.join((rpc_qn, self._my_host))
        LOG.debug('Starting DFA Agent on %s', self._my_host)

        # List of task in the agent
        self.agent_task_list = []

        # This flag indicates the agent started for the first time.
        self._need_uplink_info = True

        # Initialize iptables driver. This will be used to update the ip
        # rules in iptables, after launching an instance.

        if (self._cfg.dcnm.dcnm_dhcp.lower() == 'true'):
            self._iptd = iptd.IptablesDriver(self._cfg)
        else:
            self._iptd = None
            LOG.debug("Using native dhcp, iptable driver is not needed")

        # Setup RPC client for sending heartbeat to controller
        self._url = self._cfg.dfa_rpc.transport_url
        self.setup_client_rpc()

        # Initialize VPD manager.
        br_int = self._cfg.dfa_agent.integration_bridge
        br_ext = self._cfg.dfa_agent.external_dfa_bridge
        config_dict = {'integration_bridge': br_int,
                       'external_bridge': br_ext,
                       'host_id': self._my_host,
                       'root_helper': self._cfg.sys.root_helper,
                       'node_list': self._cfg.general.node,
                       'node_uplink_list': self._cfg.general.node_uplink}

        self._vdpm = vdpm.VdpMgr(config_dict, self.clnt, self._host_name)
        self.pool = eventlet.GreenPool()
        self.setup_rpc()

    def setup_client_rpc(self):
        """Setup RPC client for dfa agent."""
        # Setup RPC client.
        self.clnt = rpc.DfaRpcClient(self._url, constants.DFA_SERVER_QUEUE,
                                     exchange=constants.DFA_EXCHANGE)

    def send_heartbeat(self):
        context = {}
        args = jsonutils.dumps(dict(when=time.ctime(), agent=thishost))
        msg = self.clnt.make_msg('heartbeat', context, msg=args)
        resp = self.clnt.cast(msg)
        LOG.debug("send_heartbeat: resp = %s", resp)

    def request_uplink_info(self):
        context = {}
        msg = self.clnt.make_msg('request_uplink_info',
                                 context, agent=self._my_host)
        try:
            resp = self.clnt.call(msg)
            LOG.debug("request_uplink_info: resp = %s", resp)
            self._need_uplink_info = resp
        except rpc.MessagingTimeout:
            LOG.error(_LE("RPC timeout: Request for uplink info failed."))

    def setup_rpc(self):
        """Setup RPC server for dfa agent."""

        endpoints = RpcCallBacks(self._vdpm, self._iptd)
        self.server = rpc.DfaRpcServer(self._qn, self._my_host, self._url,
                                       endpoints,
                                       exchange=constants.DFA_EXCHANGE)

    def start_rpc(self):
        self.server.start()
        LOG.debug('starting RPC server on the agent.')
        self.server.wait()

    def stop_rpc(self):
        self.server.stop()

    def start_rpc_task(self):
        thrd = utils.EventProcessingThread('Agent_RPC_Server',
                                           self, 'start_rpc')
        thrd.start()
        return thrd

    def start_iptables_task(self):
        thrd = self._iptd.create_thread()
        thrd.start()
        return thrd

    def start_tasks(self):
        rpc_thrd = self.start_rpc_task()
        self.agent_task_list.append(rpc_thrd)
        if (self._iptd):
            ipt_thrd = self.start_iptables_task()
            self.agent_task_list.append(ipt_thrd)


def save_my_pid(cfg):

    mypid = os.getpid()

    pid_path = cfg.dfa_log.pid_dir
    pid_file = cfg.dfa_log.pid_agent_file
    if pid_path and pid_file:
        try:
            if not os.path.exists(pid_path):
                os.makedirs(pid_path)
        except OSError:
            LOG.error(_LE('Fail to create %s'), pid_path)
            return

        pid_file_path = os.path.join(pid_path, pid_file)

        LOG.debug('dfa_agent pid=%s', mypid)
        with open(pid_file_path, 'w') as fn:
            fn.write(str(mypid))


def main():

    # Setup logger
    cfg = config.CiscoDFAConfig().cfg
    logging.setup_logger('dfa_enabler', cfg)

    # Get pid of the process and save it.
    save_my_pid(cfg)

    # Create DFA agent object
    dfa_agent = DfaAgent(thishost, constants.DFA_AGENT_QUEUE)

    LOG.debug('Starting tasks in agent...')
    try:
        # Start all task in the agent.
        dfa_agent.start_tasks()

        # Endless loop
        while True:
            start = time.time()

            # Send heartbeat to controller, data includes:
            # - timestamp
            # - host name
            dfa_agent.send_heartbeat()

            # If the agent comes up for the fist time (could be after crash),
            # ask for the uplink info.
            if dfa_agent._need_uplink_info:
                dfa_agent.request_uplink_info()

            for trd in dfa_agent.agent_task_list:
                if not trd.am_i_active:
                    LOG.info(_LI("Thread %s is not active."), trd.name)

            end = time.time()
            delta = end - start
            eventlet.sleep(constants.HB_INTERVAL - delta)
    except Exception as e:
        dfa_agent.stop_rpc()
        LOG.exception(_LE('Exception %s is received'), str(e))
        LOG.error(_LE('Exception %s is received'), str(e))
        sys.exit("ERROR: %s" % str(e))

if __name__ == '__main__':
    sys.exit(main())
