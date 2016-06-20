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

from binascii import hexlify
import mock
import socket

from networking_cisco.plugins.cisco.cpnr.cpnr_client import UnexpectedError
from networking_cisco.plugins.cisco.cpnr.cpnr_dhcp_relay_agent import (
    DhcpPacket)
from networking_cisco.plugins.cisco.cpnr.cpnr_dhcp_relay_agent import (
    DhcpRelayAgent)
from networking_cisco.plugins.cisco.cpnr.cpnr_dhcp_relay_agent import cfg
from networking_cisco.plugins.cisco.cpnr.cpnr_dhcp_relay_agent import OPTS
import unittest


class TestDhcpRelayAgent(unittest.TestCase):

    @mock.patch('networking_cisco.plugins.cisco.'
                'cpnr.cpnr_dhcp_relay_agent.netns')
    @mock.patch('socket.socket')
    def test_open_dhcp_ext_socket(self, mock_socket, mock_netns):
        cfg.CONF.register_opts(OPTS, 'cisco_pnr')
        relay = DhcpRelayAgent()
        mock_netns.iflist.return_value = []
        mock_netns.iflist.return_value.append(('lo', '127.0.0.1',
                                               '255.0.0.0'))
        sock, addr = relay._open_dhcp_ext_socket()

        self.assertTrue(mock_netns.iflist.called, "Failed to call iflist.")

        mock_socket.assert_has_calls([
            mock.call(socket.AF_INET, socket.SOCK_DGRAM),
            mock.call().bind(('127.0.0.1', 67)),
            mock.call().connect(('127.0.0.1', 67))]
        )

        # check exception thrown if no interfaces
        with self.assertRaises(UnexpectedError):
            mock_netns.iflist.return_value = []
            sock, addr = relay._open_dhcp_ext_socket()

        # check exception thrown if no matching interfaces
        with self.assertRaises(UnexpectedError):
            mock_netns.iflist.return_value = []
            mock_netns.iflist.return_value.append(('eth1', '10.0.1.3',
                                                   '255.255.255.0'))
            sock, addr = relay._open_dhcp_ext_socket()

        # check matching interface found if not first in list
        mock_netns.iflist.return_value.append(('eth0', '10.0.0.10',
                                               '255.255.255.0'))
        mock_netns.iflist.return_value.append(('lo', '127.0.0.1',
                                               '255.0.0.0'))
        sock, addr = relay._open_dhcp_ext_socket()

    @mock.patch('networking_cisco.plugins.cisco.'
                'cpnr.cpnr_dhcp_relay_agent.netns')
    @mock.patch('socket.socket')
    def test_open_dhcp_int_socket(self, mock_socket, mock_netns):
        cfg.CONF.register_opts(OPTS, 'cisco_pnr')
        relay = DhcpRelayAgent()

        mock_netns.iflist.return_value = []
        mock_netns.iflist.return_value.append(('eth0', '10.1.1.7',
                                               '255.255.255.0'))
        recv_s, send_s, addr = relay._open_dhcp_int_socket()

        self.assertTrue(mock_netns.iflist.called, "Failed to call iflist.")

        mock_socket.assert_has_calls([
            mock.call(socket.AF_INET, socket.SOCK_DGRAM),
            mock.call().setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1),
            mock.call().setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1),
            mock.call().bind(('0.0.0.0', 67)),
            mock.call(socket.AF_INET, socket.SOCK_DGRAM),
            mock.call().setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1),
            mock.call().setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1),
            mock.call().bind(('10.1.1.7', 67))]
        )

        # check exception thrown if no interfaces
        with self.assertRaises(UnexpectedError):
            mock_netns.iflist.return_value = []
            recv_s, send_s, addr = relay._open_dhcp_int_socket()

    def test_convert_ns_to_vpnid(self):
        cfg.CONF.register_opts(OPTS, 'cisco_pnr')
        relay = DhcpRelayAgent()
        namespace = 'qdhcp-a207e329-9476-4746-91a7-fb1cce171a81'
        vpnid = relay._convert_ns_to_vpnid(namespace)
        expected = 'a7fb1cce171a81'
        self.assertEqual(expected, vpnid)


class TestDhcpPacket(unittest.TestCase):

    def test_parse(self):
        # DHCP packet contains relay agent option 82
        data_str = ('0101 0600 6f75 7345 0000 0000 0000 0000'
            '0000 0000 0000 0000 c0a8 3204 fa16 3ea5'
            '9fa4 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 6382 5363'
            '3501 013d 0701 fa16 3ea5 9fa4 3902 0240'
            '3707 0103 060c 0f1c 2a3c 0c75 6468 6370'
            '2031 2e32 302e 3152 1898 000b 040a 0a01'
            '0205 040a 0a01 0297 0801 a7fb 1cce 171a'
            '81ff')

        buf = bytearray.fromhex(data_str)
        packet = DhcpPacket.parse(buf)
        # Test client address
        self.assertEqual('0.0.0.0', packet.get_ciaddr())
        # Test relay agent options
        expected_relay_options = {152: b'',
                                  11: '10.10.1.2',
                                  5: '10.10.1.2',
                                  151: b'a7fb1cce171a81'}
        actual_packet_options = {code: packet.get_relay_option(code)
                                 for code in [152, 11, 5, 151]}
        self.assertEqual(expected_relay_options, actual_packet_options)

        # Unsuccessful case of undefined relay agent sub-options
        with self.assertRaises(KeyError):
            packet.get_relay_option(220)

    def test_data(self):
        # DHCP packet contains relay agent option 82
        data_str = ('0101 0600 6f75 7345 0000 0000 0000 0000'
            '0000 0000 0000 0000 c0a8 3204 fa16 3ea5'
            '9fa4 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 0000 0000'
            '0000 0000 0000 0000 0000 0000 6382 5363'
            '3501 013d 0701 fa16 3ea5 9fa4 3902 0240'
            '3707 0103 060c 0f1c 2a3c 0c75 6468 6370'
            '2031 2e32 302e 3152 1898 000b 040a 0a01'
            '0205 040a 0a01 0297 0801 a7fb 1cce 171a'
            '81ff')
        buf = bytearray.fromhex(data_str)
        pktbuf = bytearray(4096)
        pktbuf[0:len(buf)] = buf
        packet = DhcpPacket.parse(pktbuf)
        hex_data = hexlify(packet.data())
        self.assertIn(hexlify(packet.ciaddr), hex_data)
        self.assertIn(hexlify(packet.giaddr), hex_data)

        expected_relay_options = {152: b'',
                                  11: '10.10.1.2',
                                  5: '10.10.1.2',
                                  151: b'a7fb1cce171a81'}
        # Find relay agent sub-options in data
        self.assertIn(self.get_relay_opt_hex(expected_relay_options[11]),
            hex_data)
        self.assertIn(self.get_relay_opt_hex(expected_relay_options[5]),
            hex_data)
        self.assertIn(b"01" + expected_relay_options[151],
            hex_data)
        self.assertIn(expected_relay_options[152],
            hex_data)

    def get_relay_opt_hex(self, value):
        return hexlify(socket.inet_aton(value))
