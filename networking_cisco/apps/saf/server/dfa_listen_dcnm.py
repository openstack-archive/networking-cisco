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


import pika
import socket
import sys
import time
import traceback

from oslo_serialization import jsonutils

from networking_cisco._i18n import _LE, _LI

from networking_cisco.apps.saf.common import dfa_logger as logging

LOG = logging.getLogger(__name__)


class DCNMListener(object):

    """This AMQP client class listens to DCNM's AMQP notification and
    interacts with openstack for further tenant and network information.
    It also communicates with CPNR to populate DHCP data.
    """

    def __init__(self, name, ip, user, password, pqueue=None,
                 c_pri=100, d_pri=100):
        """Create a new instance of AMQP client.

        :param dict params: AMQP configuration parameters,
         e.g. AMQP server ip, port, user name, password, name of AMQP
         exchange and queue for DCNM notification.
        """
        # extract from input params
        self._server_ip = ip
        self._user = user
        self._pwd = password
        self._pq = pqueue
        self._create_pri = c_pri
        self._delete_pri = d_pri
        # exchange, queue name for receiving vCD events.
        self._port = 5672
        self._dcnm_exchange_name = 'DCNMExchange'
        self._dcnm_queue_name = socket.gethostname()
        # specify the key of interest.
        key = ('success.cisco.dcnm.event.auto-config.organization.'
               'partition.network.*')
        self._conn = None
        self.consume_channel = None
        try:
            credentials = None
            if self._user:
                credentials = pika.PlainCredentials(self._user, self._pwd)
            # create connection, channel
            self._conn = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self._server_ip,
                    port=self._port,
                    credentials=credentials))

            # create channels for consuming
            self.consume_channel = self._conn.channel()

            # declare vCD exchange
            self.consume_channel.exchange_declare(
                exchange=self._dcnm_exchange_name,
                exchange_type='topic',
                durable=True,
                auto_delete=False)

            result = self.consume_channel.queue_declare(
                queue=self._dcnm_queue_name,
                durable=True,
                auto_delete=False)
            self._dcnm_queue_name = result.method.queue
            self.consume_channel.queue_bind(exchange=self._dcnm_exchange_name,
                                            queue=self._dcnm_queue_name,
                                            routing_key=key)
            # for info only
            msg_count = result.method.message_count
            LOG.debug('The exchange %(exch)s queue %(que)s has '
                      'totally %(cnt)d messages. ',
                      {'exch': self._dcnm_exchange_name,
                       'que': self._dcnm_queue_name, 'cnt': msg_count})

            LOG.debug('DCNM Listener initialization done....')
        except Exception as ex:
            LOG.exception(_LE('Failed to initialize DCNMListener %s'), ex)

    def _cb_dcnm_msg(self, method, body):
        """Callback function to process DCNM network creation/update/deletion
        message received by AMQP.

        It also communicates with DCNM to extract info for CPNR record
        insertion/deletion.

        :param pika.channel.Channel ch: The channel instance.
        :param pika.Spec.Basic.Deliver method: The basic deliver method
                                               which includes routing key.
        :param pika.Spec.BasicProperties properties: properties
        :param str body: The message body.
        """
        LOG.debug('Routing_key: %(key)s, body: %(body)s.',
                  {'key': method.routing_key, 'body': body})
        partition_keyword = 'auto-config.organization.partition'
        network_keyword = partition_keyword + '.network'

        network_create_key = network_keyword + '.create'
        network_update_key = network_keyword + '.update'
        msg = jsonutils.loads(body)
        LOG.debug('_cb_dcnm_msg: RX message: %s', msg)

        if not msg:
            LOG.debug("error, return")
            return

        url = msg['link']
        url_fields = url.split('/')
        pre_project_name = url_fields[4]
        pre_partition_name = url_fields[6]
        pre_seg_id = url_fields[9]
        data = {"project_name": pre_project_name,
                "partition_name": pre_partition_name,
                "segmentation_id": pre_seg_id}
        if network_create_key in method.routing_key or (
                network_update_key in method.routing_key):
            pri = self._create_pri
            event_type = 'dcnm.network.create'
        else:
            pri = self._delete_pri
            event_type = 'dcnm.network.delete'

        if self._pq is not None:
            payload = (event_type, data)
            self._pq.put((pri, time.ctime, payload))

    def process_amqp_msgs(self):
        """Process AMQP queue messages.

        It connects to AMQP server and calls callbacks to process DCNM events,
        i.e. routing key containing '.cisco.dcnm.', once they arrive in the
        queue.
        """

        LOG.info(_LI('Starting process_amqp_msgs...'))
        while True:
            (mtd_fr, hdr_fr, body) = (None, None, None)
            try:
                if self.consume_channel:
                    (mtd_fr, hdr_fr, body) = self.consume_channel.basic_get(
                        self._dcnm_queue_name)
                if mtd_fr:
                    # Queue has messages.
                    LOG.info(_LI('RX message: %s'), body)
                    self._cb_dcnm_msg(mtd_fr, body)
                    self.consume_channel.basic_ack(mtd_fr.delivery_tag)
                else:
                    # Queue is empty.
                    try:
                        self._conn.sleep(1)
                    except AttributeError:
                        time.sleep(1)
            except Exception:
                exc_type, exc_value, exc_tb = sys.exc_info()
                tb_str = traceback.format_exception(exc_type,
                                                    exc_value, exc_tb)
                LOG.exception(_LE("Failed to read from queue: %(queue)s "
                              "%(exc_type)s, %(exc_value)s, %(exc_tb)s."), {
                                  'queue': self._dcnm_queue_name,
                                  'exc_type': exc_type,
                                  'exc_value': exc_value,
                                  'exc_tb': tb_str})
