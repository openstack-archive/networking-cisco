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

import mock
import unittest

from networking_cisco.plugins.cisco.cpnr.netns import iflist
from networking_cisco.plugins.cisco.cpnr.netns import nslist


class TestNetNs(unittest.TestCase):

    @mock.patch('os.path')
    @mock.patch('os.listdir')
    def test_nslist(self, mock_listdir, mock_path):
        mock_path.exists.return_value = True
        mock_listdir.return_value = []
        mock_listdir.return_value.append(('qdhcp-1111111-2222222-3333333'))
        mock_listdir.return_value.append(('qdhcp-4444444-5555555-6666666'))
        nsdirs = nslist()
        self.assertEqual('qdhcp-1111111-2222222-3333333', nsdirs[0])
        self.assertEqual('qdhcp-4444444-5555555-6666666', nsdirs[1])

        mock_path.exists.return_value = False
        nsdirs = nslist()
        self.assertEqual([], nsdirs)

    @mock.patch('subprocess.check_output')
    def test_iflist(self, mock_check_output):
        ip_addr_str = (
            b'1: lo: <LOOPBACK,UP,LOWER_UP> mtu 16436 qdisc noqueue\n'
            b'  link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n'
            b'  inet 127.0.0.1/8 scope host lo\n'
            b'  inet6 ::1/128 scope host\n'
            b'      valid_lft forever preferred_lft forever\n '
            b'2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500'
            b' qdisc pfifo_fast qlen 1000\n '
            b'  link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff\n'
            b'  inet 10.1.1.1/24 brd 10.1.1.255 scope global eth0\n'
            b'  inet6 1111:2222:3333:4444:5555/64 scope link\n'
            b'      valid_lft forever preferred_lft forever\n'
            b'3: sit0: <NOARP> mtu 1480 qdisc noop\n'
            b'  link/sit 0.0.0.0 brd 0.0.0.0')

        mock_check_output.return_value = ip_addr_str
        interfaces = iflist()
        name, addr, mask = interfaces[0]
        self.assertEqual(b'lo', name)
        self.assertEqual(b'127.0.0.1', addr)
        self.assertEqual(b'8', mask)
        name, addr, mask = interfaces[1]
        self.assertEqual(b'eth0', name)
        self.assertEqual(b'10.1.1.1', addr)
        self.assertEqual(b'24', mask)

        # check ignore option
        interfaces = iflist(ignore=(b"lo",))
        name, addr, mask = interfaces[0]
        self.assertEqual(b'eth0', name)
        self.assertEqual(b'10.1.1.1', addr)
        self.assertEqual(b'24', mask)
        with self.assertRaises(IndexError):
            name, addr, mask = interfaces[1]

        interfaces = iflist(ignore=(b"eth0",))
        name, addr, mask = interfaces[0]
        self.assertEqual(b'lo', name)
        self.assertEqual(b'127.0.0.1', addr)
        self.assertEqual(b'8', mask)
        with self.assertRaises(IndexError):
            name, addr, mask = interfaces[1]

        # test with no input
        mock_check_output.return_value = ''
        interfaces = iflist()
        with self.assertRaises(IndexError):
            name, addr, mask = interfaces[0]
