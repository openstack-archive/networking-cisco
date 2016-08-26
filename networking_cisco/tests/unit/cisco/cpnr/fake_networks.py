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

from neutron.agent.linux import dhcp
from neutron_lib import constants as const


fake_tenant_id = 'aaaaaaaa-aaaa-aaaa-aaaaaaaaaaaa'
fake_subnet1_allocation_pools = dhcp.DictModel(dict(id='', start='172.9.9.2',
                                               end='172.9.9.254'))
fake_host_route = dhcp.DictModel(dict(id='', destination='40.0.1.0/24',
                                      nexthop='40.0.0.2'))
fake_subnet1 = dhcp.DictModel(dict(id='bbbbbbbb-bbbb-bbbb-bbbbbbbbbbbb',
                              network_id='12345678-1234-5678-1234567890ab',
                              cidr='172.9.9.0/24', enable_dhcp=True, name='',
                              tenant_id=fake_tenant_id,
                              gateway_ip='172.9.9.1',
                              host_routes=[fake_host_route],
                              dns_nameservers=['8.8.8.8'], ip_version=4,
                              ipv6_ra_mode=None, ipv6_address_mode=None,
                              allocation_pools=fake_subnet1_allocation_pools))

fake_subnet2_allocation_pools = dhcp.DictModel(dict(id='', start='172.9.8.2',
                                               end='172.9.8.254'))
fake_subnet2 = dhcp.DictModel(dict(id='dddddddd-dddd-dddd-dddddddddddd',
                              network_id='12345678-1234-5678-1234567890ab',
                              cidr='172.9.8.0/24', enable_dhcp=False, name='',
                              tenant_id=fake_tenant_id, gateway_ip='172.9.8.1',
                              host_routes=[], dns_nameservers=[], ip_version=4,
                              allocation_pools=fake_subnet2_allocation_pools))

fake_subnet3 = dhcp.DictModel(dict(id='bbbbbbbb-1111-2222-bbbbbbbbbbbb',
                              network_id='12345678-1234-5678-1234567890ab',
                              cidr='192.168.1.1/24', enable_dhcp=True))

fake_ipv6_subnet = dhcp.DictModel(dict(id='bbbbbbbb-1111-2222-bbbbbbbbbbbb',
                                  network_id='12345678-1234-5678-1234567890ab',
                                  cidr='2001:0db8::0/64', enable_dhcp=True,
                                  tenant_id=fake_tenant_id,
                                  gateway_ip='2001:0db8::1', ip_version=6,
                                  ipv6_ra_mode='slaac',
                                  ipv6_address_mode=None))

fake_meta_subnet = dhcp.DictModel(dict(id='bbbbbbbb-1111-2222-bbbbbbbbbbbb',
                                  network_id='12345678-1234-5678-1234567890ab',
                                  cidr='169.254.169.252/30',
                                  gateway_ip='169.254.169.253',
                                  enable_dhcp=True))

fake_fixed_ip1 = dhcp.DictModel(dict(id='', subnet_id=fake_subnet1.id,
                                ip_address='172.9.9.9'))
fake_fixed_ip2 = dhcp.DictModel(dict(id='', subnet_id=fake_subnet1.id,
                                ip_address='172.9.9.10'))
fake_fixed_ip3 = dhcp.DictModel(dict(id='', subnet_id=fake_subnet1.id,
                                ip_address='172.9.9.11'))
fake_fixed_ip4 = dhcp.DictModel(dict(id='', subnet_id=fake_subnet1.id,
                                ip_address='172.9.9.12'))
fake_fixed_ip5 = dhcp.DictModel(dict(id='', subnet_id=fake_subnet1.id,
                                ip_address='172.9.9.13'))
fake_fixed_ip6 = dhcp.DictModel(dict(id='', subnet_id=fake_subnet1.id,
                                ip_address='172.9.9.18'))
fake_fixed_ipv6 = dhcp.DictModel(dict(id='', subnet_id=fake_ipv6_subnet.id,
                                 ip_address='2001:db8::a8bb:ccff:fedd:ee99'))
fake_meta_fixed_ip = dhcp.DictModel(dict(id='', subnet=fake_meta_subnet,
                                    ip_address='169.254.169.254'))
fake_allocation_pool_subnet1 = dhcp.DictModel(dict(id='', start='172.9.9.2',
                                              end='172.9.9.254'))
fake_extra_dhcp_opts = dhcp.DictModel(dict(id='',
                                           opt_name='vendor-class-identifier',
                                           opt_value='cis'))

fake_port1 = dhcp.DictModel(dict(id='12345678-1234-aaaa-1234567890ab',
                            device_id='dhcp-12345678-1234-aaaa-1234567890ab',
                            device_owner='',
                            allocation_pools=fake_subnet1_allocation_pools,
                            mac_address='aa:bb:cc:dd:ee:ff',
                            network_id='12345678-1234-5678-1234567890ab',
                            fixed_ips=[fake_fixed_ip1, fake_fixed_ipv6],
                            extra_dhcp_opts=[fake_extra_dhcp_opts]))

fake_port2 = dhcp.DictModel(dict(id='12345678-1234-aaaa-123456789000',
                            device_id='dhcp-12345678-1234-aaaa-123456789000',
                            device_owner='',
                            mac_address='aa:bb:cc:dd:ee:99',
                            network_id='12345678-1234-5678-1234567890ab',
                            fixed_ips=[fake_fixed_ip2]))

fake_port3 = dhcp.DictModel(dict(id='12345678-1234-aaaa-123456777000',
                            device_id='dhcp-12345678-1234-aaaa-123456777000',
                            device_owner='',
                            mac_address='aa:bb:cc:dd:ff:ee',
                            network_id='12345678-1234-5678-90ab-123456777000',
                            fixed_ips=[fake_fixed_ip3, fake_fixed_ip4]))

fake_port4 = dhcp.DictModel(dict(id='12345678-1234-aaaa-123456777001',
                            device_id='dhcp-12345678-1234-aaaa-123456777001',
                            device_owner='',
                            mac_address='aa:bb:cc:ff:dd:ee',
                            network_id='12345678-1234-5678-90ab-123456777000',
                            fixed_ips=[fake_fixed_ip5, fake_fixed_ip6]))

fake_ipv6_port = dhcp.DictModel(dict(id='12345678-1234-aaaa-123456789000',
                                device_owner='',
                                mac_address='aa:bb:cc:dd:ee:99',
                                network_id='12345678-1234-5678-1234567890ab',
                                fixed_ips=[fake_fixed_ipv6]))

fake_meta_port = dhcp.DictModel(dict(id='12345678-1234-aaaa-1234567890ab',
                                mac_address='aa:bb:cc:dd:ee:ff',
                                network_id='12345678-1234-5678-1234567890ab',
                                device_owner=const.DEVICE_OWNER_ROUTER_INTF,
                                device_id='forzanapoli',
                                fixed_ips=[fake_meta_fixed_ip]))


FAKE_NETWORK_UUID = '12345678-1234-5678-1234567890ab'
FAKE_NETWORK_DHCP_NS = "qdhcp-%s" % FAKE_NETWORK_UUID

fake_network = dhcp.NetModel(dict(id=FAKE_NETWORK_UUID,
                             tenant_id='aaaaaaaa-aaaa-aaaa-aaaaaaaaaaaa',
                             admin_state_up=True,
                             subnets=[fake_subnet1, fake_subnet2],
                             ports=[fake_port1]))

fake_network_ipv6 = dhcp.NetModel(dict(
                             id='12345678-1234-5678-1234567890ab',
                             tenant_id='aaaaaaaa-aaaa-aaaa-aaaaaaaaaaaa',
                             admin_state_up=True,
                             subnets=[fake_ipv6_subnet],
                             ports=[fake_ipv6_port]))

fake_network_ipv6_ipv4 = dhcp.NetModel(dict(
                             id='12345678-1234-5678-1234567890ab',
                             tenant_id='aaaaaaaa-aaaa-aaaa-aaaaaaaaaaaa',
                             admin_state_up=True,
                             subnets=[fake_ipv6_subnet, fake_subnet1],
                             ports=[fake_port1]))

fake_net1 = dhcp.NetModel(dict(
        id='12345678-1234-5678-90ab-1234567890ab',
        tenant_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        admin_state_up=True,
        subnets=[fake_subnet1, fake_ipv6_subnet],
        ports=[fake_port1]))

fake_net2 = dhcp.NetModel(dict(
        id='12345678-1234-5678-90ab-1234567890ab',
        tenant_id='aaaaaaaa-aaaa-aaaa-aaaaaaaaaaaa',
        admin_state_up=True,
        subnets=[fake_subnet1, fake_ipv6_subnet],
        ports=[fake_port1, fake_port2]))

fake_net3 = dhcp.NetModel(dict(
        id='12345678-1234-5678-90ab-123456777000',
        tenant_id='aaaaaaaa-aaaa-aaaa-aaaaaaaaaaaa',
        admin_state_up=True,
        subnets=[fake_subnet1],
        ports=[fake_port3, fake_port4]))

empty_network = dhcp.NetModel(dict(
        id='12345678-1234-5678-1234567890ab',
        tenant_id='aaaaaaaa-aaaa-aaaa-aaaaaaaaaaaa',
        admin_state_up=True,
        subnets=[fake_subnet1],
        ports=[]))

fake_meta_network = dhcp.NetModel(dict(id='12345678-1234-5678-1234567890ab',
               tenant_id='aaaaaaaa-aaaa-aaaa-aaaaaaaaaaaa',
               admin_state_up=True,
               subnets=[fake_meta_subnet],
               ports=[fake_meta_port]))
