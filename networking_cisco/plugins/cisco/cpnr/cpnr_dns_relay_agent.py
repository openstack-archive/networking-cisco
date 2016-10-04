# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
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


import eventlet
import os
import signal
import socket
import struct
import time
import uuid

from neutron.common import config
from neutron.common import exceptions
from oslo_config import cfg
from oslo_log import log as logging

from networking_cisco._i18n import _, _LE, _LW
from networking_cisco.plugins.cisco.cpnr.cpnr_client import UnexpectedError
from networking_cisco.plugins.cisco.cpnr import debug_stats
from networking_cisco.plugins.cisco.cpnr import netns

LOG = logging.getLogger(__name__)

DEBUG_STATS_MIN_WRITE_INTERVAL = 30
MONITOR_INTERVAL = 1
CLEANUP_INTERVAL = 30
STALE_REQUEST_TMO = 120
RECV_BUFFER_SIZE = 4096
NS_RELAY_PENDING = 'NS_RELAY_PENDING'
NS_RELAY_RUNNING = 'NS_RELAY_RUNNING'
NS_RELAY_DELETING = 'NS_RELAY_DELETING'
NS_PREFIX = 'qdhcp'
DNS_SERVER_PORT = 53
RLIMIT_NOFILE_LIMIT = 16384

OPTS = [
    cfg.StrOpt('external_interface',
               default='lo',
               help=_('Interface for communicating with DHCP/DNS server.')),
    cfg.StrOpt('dns_server_addr',
               default='127.0.0.1',
               help=_('DNS server IP address.')),
    cfg.IntOpt('dns_server_port',
               default=53,
               help=_('DNS server UDP port number.')),
    cfg.BoolOpt('enable_dns_stats',
                default=False,
                help=_('Enable DNS stats.')),
    cfg.IntOpt('dns_stats_interval',
               default=60,
               help=_('DNS stats polling interval.'))
]


class DnsRelayAgent(object):
    """Relay DNS packets between neutron networks and external DNS server.

    Receives unicast DNS requests via sockets which are opened in each neutron
    network namespace.  Additional DNS options are appended to the request
    to indicate from which network the request originated. Requests are then
    forwarded to the configured DNS server address.

    Receives unicast DNS responses from the DNS server via socket opened in
    the global network namespace.  Additional options are stripped from the
    response. The response is then forwarded to the originating network.
    """

    def __init__(self):
        self.conf = cfg.CONF
        self.ns_states = {}
        self.request_info_by_msgid = {}
        self.ext_sock = None
        self.ext_addr = ""
        self.ns_lock = eventlet.semaphore.Semaphore()
        self.debug_stats = debug_stats.DebugStats('dns')
        self.kill_now = False

    def serve(self):
        self.greenpool = eventlet.GreenPool(4)
        self.greenpool.spawn_n(self._server_network_relay)
        self.greenpool.spawn_n(self._namespace_monitor)
        self.greenpool.spawn_n(self._cleanup_stale_requests)
        if self.conf.cisco_pnr.enable_dns_stats:
            self.greenpool.spawn_n(self._write_debug_stats)
        self.greenpool.waitall()

    def _signal_handler(self, signum, frame):
        LOG.debug('Recieved the signal %s', signum)
        self.kill_now = True

    def _namespace_monitor(self):

        while True:
            if self.kill_now:
                break
            eventlet.sleep(MONITOR_INTERVAL)

            # Get list of network namespaces on system
            try:
                curr_ns = set(netns.nslist())
            except Exception:
                LOG.error(_LE('Failed to get current namespace set'))
                continue

            # For each unknown namespace, start a relay thread
            for ns in curr_ns:
                if not ns.startswith(NS_PREFIX) or ns in self.ns_states:
                    continue
                self.ns_states[ns] = NS_RELAY_PENDING
                eventlet.spawn_n(self._client_network_relay, ns)

            # Set state to DELETING for any unknown namespaces
            for ns in self.ns_states:
                if ns in curr_ns:
                    continue
                self.ns_states[ns] = NS_RELAY_DELETING
        LOG.debug('Namespace Monitor exiting')

    def _server_network_relay(self):

        # Open a socket in the global namespace for DNS
        try:
            self.ext_sock, self.ext_addr, ext_port = (
                self._open_dns_ext_socket())
        except Exception:
            LOG.exception(_LE('Failed to open dns external '
                              'socket in global ns'))
            return
        recvbuf = bytearray(RECV_BUFFER_SIZE)
        LOG.debug("Opened dns external server socket on addr:%s:%i",
                  self.ext_addr, ext_port)

        # Forward DNS responses from external to internal networks
        while True:
            if self.kill_now:
                break
            try:
                self.ext_sock.settimeout(1)
                size = self.ext_sock.recv_into(recvbuf)
                pkt = DnsPacket.parse(recvbuf, size)
                msgid = pkt.get_msgid()
                LOG.debug("got dns response pkt, msgid =  %i", msgid)
                if msgid not in self.request_info_by_msgid:
                    LOG.debug('Could not find request by msgid %i', msgid)
                    continue
                int_sock, int_addr, int_port, createtime, viewid = (
                    self.request_info_by_msgid[msgid])
                self.debug_stats.increment_pkts_from_server(viewid)
                LOG.debug("forwarding response to internal namespace "
                          "at %s:%i", int_addr, int_port)
                int_sock.sendto(recvbuf[:size], (int_addr, int_port))
                del self.request_info_by_msgid[msgid]
                self.debug_stats.increment_pkts_to_client(viewid)
            except socket.timeout:
                pass
            except Exception:
                LOG.exception(_LE('Failed to forward dns response'))
        LOG.debug('Server Network relay exiting')

    def _client_network_relay(self, namespace):

        # Open a socket in the DNS network namespace
        try:
            with self.ns_lock, netns.Namespace(namespace):
                int_sock, int_addr, int_port = self._open_dns_int_socket()
        except exceptions.BaseException:
            LOG.exception(_LE('Failed to open dns server socket in %s'),
                          namespace)
            del self.ns_states[namespace]
            return
        self.ns_states[namespace] = NS_RELAY_RUNNING
        recvbuf = bytearray(RECV_BUFFER_SIZE)
        LOG.debug("Opened dns server socket on ns: %s, addr:%s:%i",
                  namespace, int_addr, int_port)

        # Convert the namespace into a view id
        viewid = self._convert_namespace_to_viewid(namespace)

        self.debug_stats.add_network_stats(viewid)

        # Forward DNS requests from internal to external networks
        while self.ns_states[namespace] != NS_RELAY_DELETING:
            if self.kill_now:
                break
            try:
                int_sock.settimeout(1)
                size, (src_addr, src_port) = int_sock.recvfrom_into(recvbuf)
                LOG.debug("got dns request from ns: %s", namespace)
                self.debug_stats.increment_pkts_from_client(viewid)
                pkt = DnsPacket.parse(recvbuf, size)
                pkt.set_viewid(viewid)

                # Store off some state to know where to forward response later
                msgid = pkt.get_msgid()
                createtime = time.time()
                self.request_info_by_msgid[msgid] = [int_sock,
                                    src_addr, src_port, createtime, viewid]
                LOG.debug("forwarding request to external nameserver")
                self.ext_sock.send(pkt.data())
                self.debug_stats.increment_pkts_to_server(viewid)
            except socket.timeout:
                pass
            except Exception:
                LOG.exception(_LE('Failed to forward dns request to server '
                                'from %s'), namespace)

        # Cleanup socket and internal state
        try:
            del self.ns_states[namespace]
            self.debug_stats.del_network_stats(viewid)
            int_sock.close()
        except Exception:
            LOG.warning(_LW('Failed to cleanup dns relay for %s'), namespace)
        LOG.debug('Client network relay exiting')

    def _open_dns_ext_socket(self):

        # find configured external interface ip address
        for ifname, addr, mask in netns.iflist():
            if ifname == self.conf.cisco_pnr.external_interface:
                break
        else:
            raise UnexpectedError(msg='Failed to find external '
                                      'interface matching config')

        # open, bind, and connect UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind((addr, 0))    # any available port
        addr, port = s.getsockname()
        s.connect((self.conf.cisco_pnr.dns_server_addr,
                   self.conf.cisco_pnr.dns_server_port))
        return s, addr, port

    def _open_dns_int_socket(self):

        # list interfaces, make sure there is at least one
        interfaces = netns.iflist(ignore=("lo",))
        if not interfaces:
            raise UnexpectedError(msg="Failed to find "
                                  "single interface in dhcp namespace")
        ifname, addr, mask = interfaces[0]

        # open socket for receiving DNS requests and sending DNS responses
        # on internal net
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((addr, DNS_SERVER_PORT))

        return s, addr, DNS_SERVER_PORT

    def _cleanup_stale_requests(self):

        while True:
            if self.kill_now:
                break
            eventlet.sleep(CLEANUP_INTERVAL)

            currtime = time.time()
            for msgid in self.request_info_by_msgid.keys():
                reqvals = self.request_info_by_msgid[msgid]
                createtime = reqvals[3]
                if (currtime - createtime) > STALE_REQUEST_TMO:
                    del self.request_info_by_msgid[msgid]
        LOG.debug('Cleanup thread exiting')

    def _convert_namespace_to_viewid(self, namespace):
        netid = namespace[6:]
        netid = uuid.UUID(netid)
        return str(netid.int & 0x7fffffff)

    def _write_debug_stats(self):
        polling_interval = max(DEBUG_STATS_MIN_WRITE_INTERVAL,
                               self.conf.cisco_pnr.dns_stats_interval)
        while True:
            eventlet.sleep(polling_interval)
            self.debug_stats.write_stats_to_file()


class DnsPacket(object):

    # Byte array representation of common TXT RR fields that will be inserted
    # in each request
    #    Format is:
    #       - domain name ("10_cpnr_info5cisco3com0")
    #       - rr type (2 bytes, value = 16)
    #       - class (2 bytes, value = 1)
    #       - ttl (4 bytes, value = 0)
    TXT_RR = bytearray(b'\x0a\x5f\x63\x70\x6e\x72\x5f\x69\x6e\x66\x6f\x05'
                       b'\x63\x69\x73\x63\x6f\x03\x63\x6f\x6d\x00\x00\x10'
                       b'\x00\x01\x00\x00\x00\x00')

    QUERY_TYPE_AND_CLASS = 4
    TYPE_CLASS_AND_TTL_LENGTH = 8
    OPTIONAL_RR = 41
    COUNTS_LENGTH = 8  # Question, Answer, Authority and Additional RR Count.
    IDENTIFIER_FLAGS_AND_CODES_LENGTH = 4

    def __init__(self):
        self.buf = ''
        self.msgid = ''
        self.isreq = False
        self.viewid = ""
        self.arcnt = 0
        self.txt_insert_pos = -1
        self.optlen = 0

    @classmethod
    def parse(cls, buf, buflen):
        pkt = DnsPacket()

        # parse out the header
        (pkt.msgid,) = cls.struct('!H').unpack_from(buf, 0)
        (info,) = cls.struct('B').unpack_from(buf, 2)
        pos = DnsPacket.IDENTIFIER_FLAGS_AND_CODES_LENGTH

        # check if query
        isquery = not (info & 0x80)
        if not isquery:
            pkt.buf = buf
            LOG.debug("DNS packet is a response")
            return pkt

        LOG.debug("DNS packet is a query")
        pkt.isreq = True

        (qdcnt,) = cls.struct('!H').unpack_from(buf, 4)
        (ancnt,) = cls.struct('!H').unpack_from(buf, 6)
        (nscnt,) = cls.struct('!H').unpack_from(buf, 8)
        (arcnt,) = cls.struct('!H').unpack_from(buf, 10)
        pkt.arcnt = arcnt
        pos += DnsPacket.COUNTS_LENGTH

        LOG.debug('Parsed pkt: msgid %s qdcnt %i ancnt %i nscnt %i '
                  'arcnt %i', pkt.msgid, qdcnt, ancnt, nscnt, arcnt)

        for i in range(qdcnt):
            pos = cls.skip_over_domain_name(buf, pos)
            pos += DnsPacket.QUERY_TYPE_AND_CLASS

        if ancnt != 0 or nscnt != 0:
            # unexpected, log and return packet
            LOG.debug('Unexpected answers in query, ancnt %i nscnt %i',
                      ancnt, nscnt)
            pkt.buf = buf
            return pkt

        # walk through additional section, check for OPT RR (if present, must
        # come last)
        tmp_pos = pos
        for i in range(arcnt):
            tmp_pos = cls.skip_over_domain_name(buf, tmp_pos)
            (type,) = cls.struct('!H').unpack_from(buf, tmp_pos)
            tmp_pos += DnsPacket.TYPE_CLASS_AND_TTL_LENGTH
            (rdlen,) = cls.struct('!H').unpack_from(buf, tmp_pos)
            tmp_pos += 2 + rdlen  # rdlength and rdata

            if type == DnsPacket.OPTIONAL_RR:
                pkt.optlen = buflen - pos
                break
            else:
                pos = tmp_pos
        pkt.txt_insert_pos = pos
        pkt.buf = buf
        return pkt

    def get_msgid(self):
        return self.msgid

    def set_viewid(self, id):
        self.viewid = id

    def data(self):
        if not self.isreq or not self.viewid:
            return self.buf

        # make a copy of OPT RR, if present
        opt_data = ''
        if self.optlen != 0:
            opt_data = self.buf[self.txt_insert_pos:self.txt_insert_pos +
                                self.optlen]

        # insert TXT RR and data into buf
        pos = self.txt_insert_pos
        self.buf[pos:pos + len(DnsPacket.TXT_RR)] = DnsPacket.TXT_RR
        pos += len(DnsPacket.TXT_RR)
        txt_str = 'view: %s' % (self.viewid,)
        self.struct('!HB%is' %
                    (len(txt_str),)).pack_into(self.buf, pos,
                                               len(txt_str) + 1,
                                               len(txt_str),
                                               txt_str.encode('utf-8'))

        pos += 3 + len(txt_str)

        # bump up arcnt
        self.arcnt += 1
        self.struct('!H').pack_into(self.buf, 10, self.arcnt)

        # copy OPT RR back in at end if presesnt
        if opt_data:
            self.buf[pos:pos + len(opt_data)] = opt_data
            pos += len(opt_data)

        return self.buf[:pos]

    @classmethod
    def skip_over_domain_name(cls, buf, pos):
        tmplen = -1
        while tmplen != 0:
            (tmplen,) = cls.struct('B').unpack_from(buf, pos)
            if (tmplen & 0x80) and (tmplen & 0x40):
                pos += 2  # length and pointer, comes last
                break
            else:
                pos += 1 + tmplen
        return pos

    structcache = {}

    @classmethod
    def struct(cls, fmt):
        return cls.structcache.setdefault(fmt, struct.Struct(fmt))


def main():
    try:
        netns.increase_ulimit(RLIMIT_NOFILE_LIMIT)
    except Exception:
        LOG.error(_LE('Failed to increase ulimit for DNS relay'))
    if os.getuid() != 0:
        config.setup_logging()
        LOG.error(_LE('Must run dns relay as root'))
        return
    eventlet.monkey_patch()
    cfg.CONF.register_opts(OPTS, 'cisco_pnr')
    cfg.CONF(project='neutron')
    config.setup_logging()
    relay = DnsRelayAgent()
    signal.signal(signal.SIGINT, relay._signal_handler)
    signal.signal(signal.SIGTERM, relay._signal_handler)
    relay.serve()

if __name__ == "__main__":
    main()
