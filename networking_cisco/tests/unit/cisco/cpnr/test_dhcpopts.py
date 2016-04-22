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

import mock

from neutron.tests import base

from networking_cisco.plugins.cisco.cpnr import dhcpopts


class TestDhcpopts(base.BaseTestCase):
    def test_format_for_classless_static_routes_options(self):
        expected = '20:a9:fe:a9:fe:0a:0a:00:02'
        value = dhcpopts.format_for_options('classless-static-routes',
                        '32.169.254.169.254 10.10.0.2')
        self.assertEqual(expected, value)

    def test_format_for_ip_forwarding_options(self):
        expected = '01'
        flag = True
        value = dhcpopts.format_for_options('ip-forwarding', flag)
        self.assertEqual(expected, value)

    def test_format_for_dhcp_renewal_time_options(self):
        expected = '00:00:01:2c'
        value = dhcpopts.format_for_options('dhcp-renewal-time', 300)
        self.assertEqual(expected, value)

    def test_format_for_domain_name_options(self):
        expected = '65:78:61:6d:70:6c:65:2e:63:6f:6d:2e'
        value = dhcpopts.format_for_options('domain-name', 'example.com.')
        self.assertEqual(expected, value)

    @mock.patch('networking_cisco.plugins.cisco.cpnr.dhcpopts._format_value')
    def test_format_for_options_exception(self, mock_format):
        expected = ''
        mock_format.get.side_effect = Exception
        value = dhcpopts.format_for_options('subnet-mask', '10.10.0.1')
        self.assertEqual(expected, value)

    @mock.patch('networking_cisco.plugins.cisco.cpnr.dhcpopts._format_value')
    def test_format_for_options_unknown_option(self, mock_format):
        expected = None
        value = dhcpopts.format_for_options('someoption', 'somevalue')
        self.assertEqual(expected, value)

    def test_format_route_list_value(self):
        expected = '20a9fea9fe0a0a0002'
        value = dhcpopts._format_value('route-list',
                        '32.169.254.169.254 10.10.0.2')
        self.assertEqual(expected, value)

    def test_format_bool_value(self):
        expected = '01'
        flag = True
        value = dhcpopts._format_value('bool', flag)
        self.assertEqual(expected, value)

    def test_format_int32_value(self):
        expected = '0000012c'
        value = dhcpopts._format_value('int32', 300)
        self.assertEqual(expected, value)

    def test_format_string_value(self):
        expected = '6578616d706c652e636f6d2e'
        value = dhcpopts._format_value('string', 'example.com.')
        self.assertEqual(expected, value)

    def test_format_ip_value(self):
        expected = '0a0a0001'
        value = dhcpopts._format_value('ip', '10.10.0.1')
        self.assertEqual(expected, value)

    def test_format_comma_separated_value(self):
        expected = '0a0a00016578616d706c652e636f6d'
        value = dhcpopts._format_value('ip, string', '10.10.0.1 example.com')
        self.assertEqual(expected, value)

    def test_format_none_value(self):
        expected = ''
        value = dhcpopts._format_value('none', 'none')
        self.assertEqual(expected, value)

    def test_format_route_list_value_exception(self):
        expected = ''
        try:
            value = dhcpopts._format_value('route-list',
                        '32.169.254.169.254 ip-adress')
        except ValueError:
            value = ''
        self.assertEqual(expected, value)
