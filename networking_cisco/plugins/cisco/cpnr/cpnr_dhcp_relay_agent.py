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


import binascii
import eventlet
import os
import signal
import socket
import struct

from neutron.common import config
from oslo_config import cfg
from oslo_log import log as logging

from networking_cisco._i18n import _LE, _LW, _
from networking_cisco.plugins.cisco.cpnr.cpnr_client import UnexpectedError
from networking_cisco.plugins.cisco.cpnr import debug_stats
from networking_cisco.plugins.cisco.cpnr import netns

LOG = logging.getLogger(__name__)

DEBUG_STATS_MIN_WRITE_INTERVAL = 30
MONITOR_INTERVAL = 1
RECV_BUFFER_SIZE = 4096
NS_RELAY_PENDING = 'NS_RELAY_PENDING'
NS_RELAY_RUNNING = 'NS_RELAY_RUNNING'
NS_RELAY_DELETING = 'NS_RELAY_DELETING'
DHCP_CLIENT_PORT = 68
DHCP_SERVER_PORT = 67
RLIMIT_NOFILE_LIMIT = 16384

# Relay agent information options.
LINK_SELECTION = 5
SERVER_IDENTIFIER_OVERRIDE = 11
RELAY_AGENT_INFO = 82
VSS = 151
VSS_CONTROL = 152
END = 255

OPTS = [
    cfg.StrOpt('http_server',
               default="localhost:8080",
               help=_('External HTTP server, should conform to '
                      '<server_name:port> format.')),
    cfg.StrOpt('admin_email',
               default='test@example.com',
               help=_('Email address of admin for internal DNS domain.')),
    cfg.StrOpt('external_interface',
               default='lo',
               help=_('Interface for communicating with DHCP/DNS server.')),
    cfg.StrOpt('dhcp_server_addr',
               default='127.0.0.1',
               help=_('DHCP server IP address.')),
    cfg.IntOpt('dhcp_server_port',
               default=67,
               help=_('DHCP server UDP port number.')),
    cfg.BoolOpt('enable_dhcp_stats',
                default=False,
                help=_('Enable DHCP stats.')),
    cfg.IntOpt('dhcp_stats_interval',
               default=60,
               help=_('DHCP stats polling interval.'))
]


class DhcpRelayAgent(object):
    """Relay DHCP packets between neutron networks and external DHCP server.

    Receives broadcast and unicast DHCP requests via sockets which are opened
    in each neutron dhcp network namespace.  Additional DHCP options are
    appended to the request to indicate from which network the request
    originated. Requests are then forwarded to the configured DHCP server
    address.

    Receives unicast DHCP responses from the DHCP server via socket opened in
    the global network namespace.  Additional options are stripped from the
    response. The response is then forwarded to the originating network.
    """

    def __init__(self):
        self.conf = cfg.CONF
        self.ns_states = {}
        self.int_sockets_by_vpn = {}
        self.ext_sock = None
        self.ext_addr = ""
        self.ns_lock = eventlet.semaphore.Semaphore()
        self.int_sock_retries = 0
        self.debug_stats = debug_stats.DebugStats('dhcp')
        self.kill_now = False

    def serve(self):
        self.greenpool = eventlet.GreenPool(3)
        self.greenpool.spawn_n(self._server_network_relay)
        self.greenpool.spawn_n(self._namespace_monitor)
        if self.conf.cisco_pnr.enable_dhcp_stats:
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
                if not ns.startswith("qdhcp") or ns in self.ns_states:
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

        # Open a socket in the global namespace for DHCP
        try:
            self.ext_sock, self.ext_addr = self._open_dhcp_ext_socket()
        except Exception:
            LOG.exception(_LE("Failed to open dhcp external socket in "
                              "global ns"))
            return
        recvbuf = bytearray(RECV_BUFFER_SIZE)

        # Forward DHCP responses from external to internal networks
        while True:
            if self.kill_now:
                break
            try:
                self.ext_sock.settimeout(1)
                size = self.ext_sock.recv_into(recvbuf)
                pkt = DhcpPacket.parse(recvbuf)
                vpnid = pkt.get_relay_option(151)
                ciaddr = pkt.get_ciaddr()
                if vpnid not in self.int_sockets_by_vpn:
                    continue
                int_sock = self.int_sockets_by_vpn[vpnid]
                self.debug_stats.increment_pkts_from_server(vpnid)
                if ciaddr == "0.0.0.0":
                    ciaddr = "255.255.255.255"
                LOG.debug('Forwarding DHCP response for vpn %s', vpnid)
                int_sock.sendto(recvbuf[:size], (ciaddr, DHCP_CLIENT_PORT))
                self.debug_stats.increment_pkts_to_client(vpnid)
            except socket.timeout:
                pass
            except Exception:
                LOG.exception(_LE('Failed to forward dhcp response'))
        LOG.debug('Server network relay exiting')

    def _client_network_relay(self, namespace):

        # Open a socket in the DHCP network namespace
        try:
            with self.ns_lock, netns.Namespace(namespace):
                recv_sock, send_sock, int_addr = self._open_dhcp_int_socket()
        except Exception:
            self.int_sock_retries += 1
            if self.int_sock_retries >= 2:
                LOG.exception(_LE('Failed to open dhcp server socket in %s'),
                              namespace)
                self.int_sock_retries = 0
            del self.ns_states[namespace]
            return
        self.int_sock_retries = 0
        self.ns_states[namespace] = NS_RELAY_RUNNING
        vpnid = self._convert_ns_to_vpnid(namespace)
        self.debug_stats.add_network_stats(vpnid)
        self.int_sockets_by_vpn[vpnid] = send_sock
        recvbuf = bytearray(RECV_BUFFER_SIZE)
        LOG.debug('Opened dhcp server socket on ns:%s, addr:%s, vpn:%s',
                  namespace, int_addr, vpnid)
        # Forward DHCP requests from internal to external networks
        while self.ns_states[namespace] != NS_RELAY_DELETING:
            if self.kill_now:
                break
            try:
                recv_sock.settimeout(1)
                recv_sock.recv_into(recvbuf)
                pkt = DhcpPacket.parse(recvbuf)
                options = [(5, int_addr),
                           (11, int_addr),
                           (151, vpnid),
                           (152, '')]
                for option in options:
                    pkt.set_relay_option(*option)
                pkt.set_giaddr(self.ext_addr)
                self.debug_stats.increment_pkts_from_client(vpnid)
                LOG.debug('Forwarding DHCP request for vpn %s', vpnid)
                self.ext_sock.send(pkt.data())
                self.debug_stats.increment_pkts_to_server(vpnid)
            except socket.timeout:
                pass
            except Exception:
                LOG.exception(_LE('Failed to forward dhcp to server from %s'),
                              namespace)

        # Cleanup socket and internal state
        try:
            del self.ns_states[namespace]
            del self.int_sockets_by_vpn[vpnid]
            self.debug_stats.del_network_stats(vpnid)
            recv_sock.close()
            send_sock.close()
        except Exception:
            LOG.warning(_LW('Failed to cleanup relay for %s'), namespace)
        LOG.debug('Client network relay exiting')

    def _open_dhcp_ext_socket(self):

        # find configured external interface ip address
        for ifname, addr, mask in netns.iflist():
            if ifname == self.conf.cisco_pnr.external_interface:
                break
        else:
            raise UnexpectedError(msg='Failed to find external intf '
                                      'matching config')

        # open, bind, and connect UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind((addr, DHCP_SERVER_PORT))
        s.connect((self.conf.cisco_pnr.dhcp_server_addr,
                   self.conf.cisco_pnr.dhcp_server_port))
        return s, addr

    def _open_dhcp_int_socket(self):

        # list interfaces, fail if not exactly one
        interfaces = netns.iflist(ignore=("lo",))
        if not interfaces:
            raise UnexpectedError(msg="failed to find single interface "
                                      "in dhcp ns")
        addr = interfaces[0][1]

        # open socket for receiving DHCP requests on internal net
        recv_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        recv_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        recv_s.bind(("0.0.0.0", DHCP_SERVER_PORT))

        # open socket for sending DHCP responses on internal net
        send_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        send_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        send_s.bind((addr, DHCP_SERVER_PORT))

        return recv_s, send_s, addr

    def _convert_ns_to_vpnid(self, ns):
        return ns.replace('-', '')[-14:]

    def _write_debug_stats(self):
        polling_interval = max(DEBUG_STATS_MIN_WRITE_INTERVAL,
                               self.conf.cisco_pnr.dhcp_stats_interval)
        while True:
            eventlet.sleep(polling_interval)
            self.debug_stats.write_stats_to_file()


class DhcpPacket(object):

    def __init__(self):
        self.buf = ''
        self.ciaddr = ''
        self.giaddr = ''
        self.relay_options = {}

    @classmethod
    def parse(cls, buf):
        """Parse DHCP Packet.

        1. To get client IP Address(ciaddr).
        2. To get relaying gateway IP Address(giaddr).
        3. To get DHCP Relay Agent Information Option Suboption
        such as Link Selection, VSS, Server Identifier override.
        """

        pkt = DhcpPacket()
        (pkt.ciaddr,) = cls.struct('4s').unpack_from(buf, 12)
        (pkt.giaddr,) = cls.struct('4s').unpack_from(buf, 24)
        cls.struct('4s').pack_into(buf, 24, b'')
        pos = 240
        while pos < len(buf):
            (opttag,) = cls.struct('B').unpack_from(buf, pos)
            if opttag == 0:
                pos += 1
                continue
            if opttag == END:
                pkt.end = pos
                break
            (optlen,) = cls.struct('B').unpack_from(buf, pos + 1)
            startpos = pos
            pos += 2
            if opttag != RELAY_AGENT_INFO:
                pos += optlen
                continue
            optend = pos + optlen
            while pos < optend:
                (subopttag, suboptlen) = cls.struct('BB').unpack_from(buf, pos)
                fmt = '%is' % (suboptlen,)
                (val,) = cls.struct(fmt).unpack_from(buf, pos + 2)
                pkt.relay_options[subopttag] = val
                pos += suboptlen + 2
            cls.struct('%is' % (optlen + 2)).pack_into(buf, startpos, b'')
        pkt.buf = buf
        return pkt

    def get_relay_option(self, code):
        value = self.relay_options[code]
        if code in (LINK_SELECTION, SERVER_IDENTIFIER_OVERRIDE):
            value = socket.inet_ntoa(value)
        elif code == VSS:
            value = binascii.hexlify(value[1:])
        return value

    def set_relay_option(self, code, value):
        if code == LINK_SELECTION or code == SERVER_IDENTIFIER_OVERRIDE:
            value = socket.inet_aton(value)
        elif code == VSS:
            value = binascii.unhexlify("01" + value)
        self.relay_options[code] = value

    def get_ciaddr(self):
        return socket.inet_ntoa(self.ciaddr)

    def set_giaddr(self, addr):
        self.giaddr = socket.inet_aton(addr)

    def data(self):
        self.struct('4s').pack_into(self.buf, 12, self.ciaddr)
        self.struct('4s').pack_into(self.buf, 24, self.giaddr)
        opttag = 82
        optlen = 0
        for val in self.relay_options.values():
            optlen += len(val) + 2
        self.struct('BB').pack_into(self.buf, self.end, opttag, optlen)
        self.end += 2
        for code, val in self.relay_options.items():
            fmt = 'BB%is' % (len(val),)
            self.struct(fmt).pack_into(self.buf, self.end, code, len(val), val)
            self.end += len(val) + 2
        self.struct('B').pack_into(self.buf, self.end, 255)
        return self.buf[:self.end + 1]

    structcache = {}

    @classmethod
    def struct(cls, fmt):
        return cls.structcache.setdefault(fmt, struct.Struct(fmt))


def main():
    try:
        netns.increase_ulimit(RLIMIT_NOFILE_LIMIT)
    except Exception:
        LOG.error(_LE('Failed to increase ulimit for DHCP relay'))
    eventlet.monkey_patch()
    cfg.CONF.register_opts(OPTS, 'cisco_pnr')
    cfg.CONF(project='neutron')
    config.setup_logging()
    if os.getuid() != 0:
        LOG.error(_LE('Must run dhcp relay as root'))
        return
    relay = DhcpRelayAgent()
    signal.signal(signal.SIGINT, relay._signal_handler)
    signal.signal(signal.SIGTERM, relay._signal_handler)
    relay.serve()

if __name__ == "__main__":
    main()
