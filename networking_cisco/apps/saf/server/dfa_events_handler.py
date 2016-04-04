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


import socket

from networking_cisco._i18n import _LE

from keystoneclient.v3 import client
from neutronclient.v2_0 import client as nc

from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.common import constants
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import rpc


LOG = logging.getLogger(__name__)


class EventsHandler(object):

    """This class defines methods to listen and process events."""

    def __init__(self, ser_name, pqueue, c_pri, d_pri):
        self._service = None
        self._service_name = ser_name
        self._clients = {}
        self._pq = pqueue
        self._create_pri = c_pri
        self._update_pri = c_pri
        self._delete_pri = d_pri
        self._cfg = config.CiscoDFAConfig(ser_name).cfg
        self._q_agent = constants.DFA_AGENT_QUEUE
        self._url = self._cfg.dfa_rpc.transport_url
        dfaq = self._cfg.dfa_notify.cisco_dfa_notify_queue % (
            {'service_name': ser_name})
        notify_queue = self._cfg.DEFAULT.notification_topics.split(',')
        self._notify_queue = dfaq if dfaq in notify_queue else None
        self._token = self._cfg.DEFAULT.admin_token
        if self._service_name == 'keystone':
            endpoint = self._cfg.DEFAULT.admin_endpoint
            admin_port = self._cfg.DEFAULT.admin_port
            if endpoint:
                self._endpoint_url = (endpoint + 'v3/') % (
                    {'admin_port': admin_port if admin_port else '35357'})
            else:
                host = self._cfg.DEFAULT.admin_bind_host
                proto = self._cfg.DEFAULT.auth_protocol
                self._endpoint_url = '%(proto)s://%(host)s:%(port)s/v3/' % (
                    {'proto': proto if proto else 'http',
                     'host': host if host else 'localhost',
                     'port': admin_port if admin_port else '35357'})
            self._service = client.Client(token=self._cfg.DEFAULT.admin_token,
                                          endpoint=self._endpoint_url)

        # Setup notification listener for the events.
        self._setup_notification_listener(self._notify_queue, self._url)

    @property
    def nclient(self):
        user = self._cfg.keystone_authtoken.username
        tenant = self._cfg.keystone_authtoken.project_name
        passw = self._cfg.keystone_authtoken.password
        if self._cfg.keystone_authtoken.auth_url:
            uri = self._cfg.keystone_authtoken.auth_url + '/v2.0'
        else:
            proto = self._cfg.keystone_authtoken.auth_protocol
            auth_host = self._cfg.keystone_authtoken.auth_host
            auth_port = self._cfg.keystone_authtoken.auth_port
            uri = '%(proto)s://%(host)s:%(port)s/v2.0' % (
                {'proto': proto if proto else 'http',
                 'host': auth_host if auth_host else 'localhost',
                 'port': auth_port if auth_port else '35357'})

        if user and tenant and passw and uri:
            return nc.Client(username=user, tenant_name=tenant, password=passw,
                             auth_url=uri)

    def _setup_notification_listener(self, topic_name, url):
        """Setup notification listener for a service."""

        self.notify_listener = rpc.DfaNotifcationListener(
            topic_name, url, rpc.DfaNotificationEndpoints(self))

    def start(self):
        if self.notify_listener:
            self.notify_listener.start()

    def wait(self):
        if self.notify_listener:
            self.notify_listener.wait()

    def create_rpc_client(self, thishost):
        clnt = self._clients.get(thishost)
        if clnt is None:
            try:
                host_ip = socket.gethostbyname(thishost)
            except socket.gaierror:
                LOG.error(_LE('Invalid host name for agent: %s'), thishost)
            else:
                clnt = rpc.DfaRpcClient(self._url,
                                        '_'.join((self._q_agent, thishost)),
                                        exchange=constants.DFA_EXCHANGE)
                self._clients[thishost] = clnt
                LOG.debug('Created client for agent: %(host)s:%(ip)s',
                          {'host': thishost, 'ip': host_ip})

    def callback(self, timestamp, event_type, payload):
        """Callback method for processing events in notification queue.

        :param timestamp: time the message is received.
        :param event_type: event type in the notification queue such as
                           identity.project.created, identity.project.deleted.
        :param payload: Contains information of an event
        """
        try:
            data = (event_type, payload)
            LOG.debug('RX NOTIFICATION ==>\nevent_type: %(event)s, '
                      'payload: %(payload)s\n', (
                          {'event': event_type, 'payload': payload}))
            if 'create' in event_type:
                pri = self._create_pri
            elif 'delete' in event_type:
                pri = self._delete_pri
            elif 'update' in event_type:
                pri = self._update_pri
            else:
                pri = self._delete_pri
            self._pq.put((pri, timestamp, data))

        except Exception as exc:
            LOG.exception(_LE('Error: %(err)s for event %(event)s'),
                          {'err': str(exc), 'event': event_type})

    def event_handler(self):
        """Wait on queue for listening to the events."""

        if not self._notify_queue:
            LOG.error(_LE('event_handler: no notification queue for %s'),
                      self._service_name)
            return

        LOG.debug('calling event handler for %s', self)
        self.start()
        self.wait()

    def send_vm_info(self, thishost, msg):
        clnt = self._clients.get(thishost)
        if clnt is None:
            LOG.debug("send_vm_info: Agent on %s is not active.", thishost)
            return

        context = {}
        thismsg = clnt.make_msg('send_vm_info', context, msg=msg)
        resp = clnt.call(thismsg)
        LOG.debug("send_vm_info: resp = %s", resp)

    def update_ip_rule(self, thishost, msg):
        clnt = self._clients.get(thishost)
        if clnt is None:
            LOG.debug("update_ip_rule: Agent on %s is not active.", thishost)
            return

        context = {}
        thismsg = clnt.make_msg('update_ip_rule', context, msg=msg)
        resp = clnt.call(thismsg)
        LOG.debug("update_ip_rule: resp = %s", resp)

    def send_msg_to_agent(self, thishost, msg_type, msg):
        clnt = self._clients.get(thishost)
        if clnt is None:
            LOG.debug("send_msg_to_agent: Agent on %s is not active.",
                      thishost)
            return

        context = {'type': msg_type}
        thismsg = clnt.make_msg('send_msg_to_agent', context, msg=msg)
        resp = clnt.call(thismsg)
        LOG.debug("send_msg_to_agent: resp = %s", resp)
