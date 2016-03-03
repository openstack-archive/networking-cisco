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

from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_cfg_syncer)
from networking_cisco.plugins.cisco.common.htparser import HTParser
from neutron.tests import base


CFG = """
!
interface TenGigabitEthernet0/0/0
 ip address 1.1.2.1 255.255.255.0
 no cdp enable
!
interface Serial1/0
 no ip address
!
ip access-list standard neutron_acl_2033_5c409ae1
 permit 10.10.0.0 0.0.255.255
    dummy-input
 dummy-input2
!
interface Port-channel11.2000
 description OPENSTACK_NEUTRON_EXTERNAL_INTF
 encapsulation dot1Q 2000
 ip address 15.15.6.117 255.255.0.0
 ip nat outside
 standby delay minimum 30 reload 60
 standby version 2
 standby 1064 ip 15.15.6.116
 standby 1064 timers 1 3
 standby 1064 priority 97
 standby 1064 name neutron-hsrp-1064-2000
 !
interface Port-channel11.2033
 description OPENSTACK_NEUTRON_INTF
 encapsulation dot1Q 2033
 vrf forwarding nrouter-6c5541
 ip address 10.10.0.12 255.255.0.0
 ip nat inside

interface Port-channel11.2055
 ip address 20.20.20.1 255.255.255.0
"""

FIND_LINES = "find_lines"
FIND_CHILDREN = "find_children"
FIND_OBJECTS = "find_objects"
RE_SEARCH_CHILDREN = "re_search_children"
ACL_CHILD_REGEX = asr1k_cfg_syncer.ACL_CHILD_REGEX


class TestHTParser(base.BaseTestCase):
    def setUp(self):
        super(TestHTParser, self).setUp()
        self.cfg = [x for x in CFG.splitlines()]

    def _execute(self, function_name, linespec):
        return getattr(HTParser(self.cfg), function_name)(linespec)

    def test_find_lines_singleline(self):
        linespec = "^interface TenGigabitEthernet0/0/0"
        expected = ["interface TenGigabitEthernet0/0/0"]
        actual = self._execute(FIND_LINES, linespec)
        self.assertEqual(expected, actual)

    def test_find_lines_mutliline(self):
        extra_cfg = [
            'interface TenGigabitEthernet0/0/0',
            '    no ip address',
            '    channel-group 10 mode active',
            '    !'
        ]
        self.cfg.extend(extra_cfg)
        linespec = "^interface TenGigabitEthernet0/0/0"
        exp = ["interface TenGigabitEthernet0/0/0",
               "interface TenGigabitEthernet0/0/0"]
        act = self._execute(FIND_LINES, linespec)
        self.assertEqual(exp, act)

    def test_find_lines_similiarlines(self):
        extra_cfg = [
            'interface TenGigabitEthernet0/0/1',
            '    no ip address',
            '    channel-group 10 mode active',
            '    !'
        ]
        self.cfg.extend(extra_cfg)
        linespec = "^interface TenGigabitEthernet0/0/0"
        exp = ["interface TenGigabitEthernet0/0/0"]
        act = self._execute(FIND_LINES, linespec)
        self.assertEqual(exp, act)

    def test_find_lines_multiple(self):
        extra_cfg = [
            'interface TenGigabitEthernet0/0/1',
            '    no ip address',
            '    channel-group 10 mode active',
            '    !'
        ]
        self.cfg.extend(extra_cfg)
        linespec = "^interface TenGigabitEthernet"
        exp = ["interface TenGigabitEthernet0/0/0",
               "interface TenGigabitEthernet0/0/1"]
        act = self._execute(FIND_LINES, linespec)
        self.assertEqual(exp, act)

    def test_find_lines_vrf_def(self):
        extra_cfg = [
            'vrf definition nrouter-bf7c12',
            ' !',
            ' address-family ipv4',
            ' exit-address-family',
            ' !',
            ' address-family ipv6',
            ' exit-address-family',
            ' !',
        ]
        self.cfg.extend(extra_cfg)
        linespec = "^vrf definition"
        exp = ["vrf definition nrouter-bf7c12"]
        act = self._execute(FIND_LINES, linespec)
        self.assertEqual(exp, act)

    def test_find_children_interface(self):
        linespec = "^interface TenGigabitEthernet0/0/0"
        exp = ["interface TenGigabitEthernet0/0/0",
               " ip address 1.1.2.1 255.255.255.0",
               " no cdp enable"]
        act = self._execute(FIND_CHILDREN, linespec)
        self.assertEqual(exp, act)

    def test_find_children_acl(self):
        linespec = "ip access-list standard neutron_acl_2033_5c409ae1"
        exp = ['ip access-list standard neutron_acl_2033_5c409ae1',
               ' permit 10.10.0.0 0.0.255.255',
               ' dummy-input2']
        act = self._execute(FIND_CHILDREN, linespec)
        self.assertEqual(exp, act)

    def test_find_children_acl_multiline(self):
        extra_cfg = [
            'ip access-list standard neutron_acl_1234_5678',
            '    permit 10.10.0.0 0.0.255.255'
        ]
        self.cfg.extend(extra_cfg)
        linespec = "ip access-list standard neutron_acl_*"
        exp = ['ip access-list standard neutron_acl_2033_5c409ae1',
               ' permit 10.10.0.0 0.0.255.255',
               ' dummy-input2',
               'ip access-list standard neutron_acl_1234_5678',
               '    permit 10.10.0.0 0.0.255.255']
        act = self._execute(FIND_CHILDREN, linespec)
        self.assertEqual(exp, act)

    def test_find_children_acl_no_find(self):
        linespec = "ip access-list standard neutron_acl_xyz"
        exp = []
        act = self._execute(FIND_CHILDREN, linespec)
        self.assertEqual(exp, act)

    def test_find_children_interface_spec(self):
        linespec = "^interface Port-channel11.2055"
        exp = ['interface Port-channel11.2055',
               ' ip address 20.20.20.1 255.255.255.0']
        act = self._execute(FIND_CHILDREN, linespec)
        self.assertEqual(exp, act)

    # Object based tests
    def test_find_objects(self):
        linespec = "^interface TenGigabitEthernet0/0/0"
        exp = ['interface TenGigabitEthernet0/0/0',
               ' ip address 1.1.2.1 255.255.255.0',
               ' no cdp enable']
        act = self._execute(FIND_OBJECTS, linespec)
        self.assertEqual(1, len(act))
        self.assertEqual(exp, act[0].str_list())

    def test_find_objects_no_find(self):
        linespec = "^interface TenGigabitEthernet0/0/1"
        exp = []
        act = self._execute(FIND_OBJECTS, linespec)
        self.assertEqual(exp, act)

    def test_re_search_children_interface(self):
        linespec = "^interf"
        child_linespec = "\s*no ip*"
        exp = ['interface Serial1/0', ' no ip address']
        parse = HTParser(self.cfg)
        act = [obj for obj in parse.find_objects(linespec)
               if obj.re_search_children(child_linespec)]
        self.assertEqual(1, len(act))
        self.assertEqual(exp, act[0].str_list())

    def test_re_search_children_acl(self):
        linespec = "^ip access"
        child_linespec = ACL_CHILD_REGEX
        exp = ['ip access-list standard neutron_acl_2033_5c409ae1',
               ' permit 10.10.0.0 0.0.255.255',
               ' dummy-input2']
        parse = HTParser(self.cfg)
        act = [obj for obj in parse.find_objects(linespec)
               if obj.re_search_children(child_linespec)]
        self.assertEqual(1, len(act))
        self.assertEqual(exp, act[0].str_list())

    def test_re_match_nat(self):
        linespec = "^interf"
        child_linespec = "\s*ip nat inside"
        match_regex = "^interface (\S+)"
        exp = 'Port-channel11.2033'
        parse = HTParser(self.cfg)
        act = [obj for obj in parse.find_objects(linespec)
               if obj.re_search_children(child_linespec)]
        self.assertEqual(1, len(act))
        self.assertEqual(exp, act[0].re_match(match_regex))

    def test_build_indent_based_list__singleline_noindent(self):
        LINE = 'cfg_line'
        cfg = LINE
        parser = HTParser(cfg)
        parser.find_objects("fake_object")
        self.assertEqual([(0, LINE)], parser._indent_list)

    def test_build_indent_based_list__multiline_noindent(self):
        LINE = 'cfg_line'
        cfg = LINE + '\n' + LINE
        parser = HTParser(cfg)
        parser.find_objects("fake_object")
        res = [(0, LINE), (0, LINE)]
        self.assertEqual(res, parser._indent_list)

    def test_build_indent_based_list__singleline_indent(self):
        LINE = '  cfg_line'
        cfg = LINE
        parser = HTParser(cfg)
        parser.find_objects("fake_object")
        self.assertEqual([(2, LINE)], parser._indent_list)

    def test_build_indent_based_list__singleline_comment(self):
        LINE = '!'
        cfg = LINE
        parser = HTParser(cfg)
        parser.find_objects("fake_object")
        self.assertEqual([], parser._indent_list)

    def test_build_indent_based_list__multiline_indent(self):
        LINE = '  cfg_line'
        cfg = LINE + '\n' + LINE
        parser = HTParser(cfg)
        parser.find_objects("fake_object")
        res = [(2, LINE), (2, LINE)]
        self.assertEqual(res, parser._indent_list)

    def test_init__multiline_blank(self):
        LINE = ""
        cfg = LINE + "\n" + LINE + "\n" + LINE
        parser = HTParser(cfg)
        parser.find_objects("fake_object")
        self.assertEqual([], parser._indent_list)

    def test_init__multiline_mixed(self):
        LINE = " cfg_line"
        cfg = LINE + "\n" + "  \n" + LINE
        parser = HTParser(cfg)
        parser.find_objects("fake_object")
        res = [(1, ' cfg_line'), (1, ' cfg_line')]
        self.assertEqual(res, parser._indent_list)

    def test_init__multiline_mixed_different_indent(self):
        LINE = "cfg_line"
        cfg = "  " + LINE + "\n" + "  \n" + "   " + LINE
        parser = HTParser(cfg)
        parser.find_objects("fake_object")
        res = [(2, '  cfg_line'), (3, '   cfg_line')]
        self.assertEqual(res, parser._indent_list)
