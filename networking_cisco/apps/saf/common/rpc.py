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


from oslo_config import cfg
import oslo_messaging as messaging

from networking_cisco.apps.saf.common import dfa_logger as logging

LOG = logging.getLogger(__name__)


# RPC exceptions
RPCException = messaging.MessagingException
RemoteError = messaging.RemoteError
MessagingTimeout = messaging.MessagingTimeout


class DfaRpcClient(object):

    """RPC Client class for DFA enabler."""

    def __init__(self, transport_url, topic, exchange=None, fanout=False):
        super(DfaRpcClient, self).__init__()
        transport = messaging.get_transport(cfg.CONF, url=transport_url)
        target = messaging.Target(exchange=exchange,
                                  topic=topic, fanout=fanout)
        self._client = messaging.RPCClient(transport, target)

    def make_msg(self, method, context, **kwargs):
        return {'method': method,
                'context': context,
                'args': kwargs}

    def call(self, msg):
        return self._rpc_call(msg)

    def cast(self, msg):
        return self._rpc_cast(msg)

    def _rpc_call(self, msg):
        return self._client.call(msg['context'], msg['method'], **msg['args'])

    def _rpc_cast(self, msg):
        return self._client.cast(msg['context'], msg['method'], **msg['args'])


class DfaRpcServer(object):

    """RPC server class for DFA enabler."""

    def __init__(self, topic, server, url, endpoints, exchange=None,
                 fanout=False, executor='eventlet'):
        super(DfaRpcServer, self).__init__()
        transport = messaging.get_transport(cfg.CONF, url=url)
        target = messaging.Target(exchange=exchange, topic=topic,
                                  server=server, fanout=fanout)
        endpoints = [endpoints]
        self._server = messaging.get_rpc_server(transport, target, endpoints,
                                                executor=executor)
        LOG.debug('RPC server: topic=%s, server=%s, endpoints=%s' % (
            topic, server, endpoints))

    def start(self):
        if self._server:
            self._server.start()

    def wait(self):
        if self._server:
            self._server.wait()

    def stop(self):
        pass


class DfaNotificationEndpoints(object):

    """Notification endpoints."""

    def __init__(self, endp):
        self._endpoint = endp

    def info(self, ctxt, publisher_id, event_type, payload, metadata):
        self._endpoint.callback(metadata.get('timestamp'), event_type, payload)


class DfaNotifcationListener(object):

    """RPC Client class for DFA enabler."""

    def __init__(self, topic, url, endpoints, exchange=None, fanout=False):
        super(DfaNotifcationListener, self).__init__()
        transport = messaging.get_transport(cfg.CONF, url=url)
        targets = [messaging.Target(exchange=exchange,
                                    fanout=fanout,
                                    topic=topic)]
        endpoints = [endpoints]
        self._listener = messaging.get_notification_listener(transport,
                                                             targets,
                                                             endpoints)

    def start(self):
        if self._listener:
            self._listener.start()

    def wait(self):
        if self._listener:
            self._listener.wait()
