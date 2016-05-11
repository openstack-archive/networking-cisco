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
from oslo_config import cfg

from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_cfg_syncer)

from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_routing_driver as driver)

from networking_cisco.plugins.cisco.common.htparser import HTParser


cfg.CONF.register_opts(driver.ASR1K_DRIVER_OPTS, "multi_region")

ASR_RUNNING_CFG_NO_R2_JSON_JUST_INTERFACES = [
    "interface Port-channel10",
    " no ip address",
    "!",
    "interface Port-channel10.165",
    " description OPENSTACK_NEUTRON_0000001_INTF",
    " encapsulation dot1Q 165",
    " ip address 10.23.229.153 255.255.255.240",
    " ip nat outside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 10.23.229.152",
    " standby 1064 timers 1 3",
    " standby 1064 priority 20",
    " standby 1064 name neutron-hsrp-1064-165",
    "!",
    "interface Port-channel10.2005",
    " description OPENSTACK_NEUTRON_0000001_INTF",
    " encapsulation dot1Q 2005",
    " vrf forwarding nrouter-9ad979-0000001",
    " ip address 192.168.3.15 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 192.168.3.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 10",
    " standby 1064 name neutron-hsrp-1064-2005",
    "!",
    "interface Port-channel10.2029",
    " description OPENSTACK_NEUTRON_0000001_INTF",
    " encapsulation dot1Q 2029",
    " vrf forwarding nrouter-9ad979-0000001",
    " ip address 192.168.2.15 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 192.168.2.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 10",
    " standby 1064 name neutron-hsrp-1064-2029",
    "!",
    "interface Port-channel10.2031",
    " description OPENSTACK_NEUTRON_0000001_INTF",
    " encapsulation dot1Q 2031",
    " vrf forwarding nrouter-9ad979-0000001",
    " ip address 192.168.1.30 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 192.168.1.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 10",
    " standby 1064 name neutron-hsrp-1064-2031",
    "!",
    "interface Port-channel10.2044",
    " description OPENSTACK_NEUTRON_0000001_INTF",
    " encapsulation dot1Q 2044",
    " vrf forwarding nrouter-9ad979-0000001",
    " ip address 192.168.0.4 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 192.168.0.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 10",
    " standby 1064 name neutron-hsrp-1064-2044",
    "!",
    "interface Port-channel10.2499",
    " ip nat outside",
    "!",
    "interface TenGigabitEthernet0/0/0",
    " no ip address",
    " cdp enable",
    " channel-group 10 mode active",
    "!",
    "interface TenGigabitEthernet0/1/0",
    " no ip address",
    " cdp enable",
    " channel-group 10 mode active",
    "!",
    "interface TenGigabitEthernet0/3/0",
    " no ip address",
    " shutdown",
    "!",
    "interface GigabitEthernet0",
    " vrf forwarding Mgmt-intf",
    " ip address 172.20.231.19 255.255.255.0",
    " negotiation auto",
    " no mop enabled",
    "!"
]

# A basic ASR running-cfg that doesn't have multi-region enabled
ASR_BASIC_RUNNING_CFG_NO_MULTI_REGION = [
    "!",
    "vrf definition Mgmt-intf",
    " !",
    " address-family ipv4",
    " exit-address-family",
    " !",
    " address-family ipv6",
    " exit-address-family",
    "!",
    "vrf definition nrouter-3ea5f9",
    " !",
    " address-family ipv4",
    " exit-address-family",
    " !",
    " address-family ipv6",
    " exit-address-family",
    "!",
    "interface Port-channel10",
    " no ip address",
    "!",
    "interface Port-channel10.2564",
    " description OPENSTACK_NEUTRON_INTF",
    " encapsulation dot1Q 2564",
    " vrf forwarding nrouter-3ea5f9",
    " ip address 10.2.0.4 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 10.2.0.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 97",
    " standby 1064 name neutron-hsrp-1064-2564",
    "!",
    "interface Port-channel10.3000",
    " description OPENSTACK_NEUTRON_INTF",
    " encapsulation dot1Q 3000",
    " ip address 172.16.0.105 255.255.0.0",
    " ip nat outside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 172.16.0.104",
    " standby 1064 timers 1 3",
    " standby 1064 priority 97",
    " standby 1064 name neutron-hsrp-1064-3000",
    "!",
    "interface TenGigabitEthernet0/0/0",
    " no ip address",
    " cdp enable",
    " channel-group 10 mode active",
    "!",
    "interface TenGigabitEthernet0/1/0",
    " no ip address",
    " cdp enable",
    " channel-group 10 mode active",
    "!",
    "interface TenGigabitEthernet0/3/0",
    " no ip address",
    " shutdown",
    "!",
    "interface GigabitEthernet0",
    " vrf forwarding Mgmt-intf",
    " ip address 172.20.231.19 255.255.255.0",
    " negotiation auto",
    " no mop enabled",
    "!",
    "ip nat pool nrouter-3ea5f9_nat_pool 172.16.0.124"
    " 172.16.0.124 netmask 255.255.0.0",
    "ip nat inside source static 10.2.0.5 172.16.0.126"
    " vrf nrouter-3ea5f9 redundancy neutron-hsrp-1064-3000",
    "ip nat inside source list neutron_acl_2564_47f1a63e pool"
    " nrouter-3ea5f9_nat_pool vrf nrouter-3ea5f9 overload",
    "ip forward-protocol nd",
    "!",
    "ip route vrf Mgmt-intf 0.0.0.0 0.0.0.0 172.20.231.1",
    "ip route vrf nrouter-3ea5f9 0.0.0.0 0.0.0.0"
    " Port-channel10.3000 172.16.0.1",
    "!",
    "ip access-list standard neutron_acl_2564_47f1a63e",
    " permit 10.2.0.0 0.0.0.255",
    "!",
    "end",
    ""
]

# basic ASR running cfg emulating an openstack deployment with
# region label 0000002
ASR_BASIC_RUNNING_CFG = [
    "!",
    "vrf definition Mgmt-intf",
    " !",
    " address-family ipv4",
    " exit-address-family",
    " !",
    " address-family ipv6",
    " exit-address-family",
    "!",
    "vrf definition nrouter-3ea5f9-0000002",
    " !",
    " address-family ipv4",
    " exit-address-family",
    " !",
    " address-family ipv6",
    " exit-address-family",
    "!",
    "interface Port-channel10",
    " no ip address",
    "!",
    "interface Port-channel10.2564",
    " description OPENSTACK_NEUTRON_0000002_INTF",
    " encapsulation dot1Q 2564",
    " vrf forwarding nrouter-3ea5f9-0000002",
    " ip address 10.2.0.4 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 10.2.0.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 97",
    " standby 1064 name neutron-hsrp-1064-2564",
    "!",
    "interface Port-channel10.3000",
    " description OPENSTACK_NEUTRON_0000002_INTF",
    " encapsulation dot1Q 3000",
    " ip address 172.16.0.105 255.255.0.0",
    " ip nat outside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 172.16.0.104",
    " standby 1064 timers 1 3",
    " standby 1064 priority 97",
    " standby 1064 name neutron-hsrp-1064-3000",
    "!",
    "interface TenGigabitEthernet0/0/0",
    " no ip address",
    " cdp enable",
    " channel-group 10 mode active",
    "!",
    "interface TenGigabitEthernet0/1/0",
    " no ip address",
    " cdp enable",
    " channel-group 10 mode active",
    "!",
    "interface TenGigabitEthernet0/3/0",
    " no ip address",
    " shutdown",
    "!",
    "interface GigabitEthernet0",
    " vrf forwarding Mgmt-intf",
    " ip address 172.20.231.19 255.255.255.0",
    " negotiation auto",
    " no mop enabled",
    "!",
    "ip nat pool nrouter-3ea5f9-0000002_nat_pool 172.16.0.124"
    " 172.16.0.124 netmask 255.255.0.0",
    "ip nat inside source static 10.2.0.5 172.16.0.126 vrf"
    " nrouter-3ea5f9-0000002 redundancy neutron-hsrp-1064-3000",
    "ip nat inside source list neutron_acl_0000002_2564_47f1a63e pool"
    " nrouter-3ea5f9-0000002_nat_pool vrf nrouter-3ea5f9-0000002 overload",
    "ip forward-protocol nd",
    "!",
    "ip route vrf Mgmt-intf 0.0.0.0 0.0.0.0 172.20.231.1",
    "ip route vrf nrouter-3ea5f9-0000002 0.0.0.0 0.0.0.0"
    " Port-channel10.3000 172.16.0.1",
    "!",
    "ip access-list standard neutron_acl_0000002_2564_47f1a63e",
    " permit 10.2.0.0 0.0.0.255",
    "!",
    "end",
    ""
]

# with intentionally invalid interfaces configuration that mismatches
# against neutron-db
ASR_RUNNING_CFG_WITH_INVALID_INTFS = [
    "interface Port-channel10",
    " no ip address",
    "!",
    "interface Port-channel10.165",
    " description OPENSTACK_NEUTRON_0000001_INTF",
    " encapsulation dot1Q 165",
    " ip address 10.23.229.153 255.255.255.240",
    " ip nat outside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 10.23.229.152",
    " standby 1064 timers 1 3",
    " standby 1064 priority 20",
    " standby 1064 name neutron-hsrp-1064-165",
    "!",
    "interface Port-channel10.2005",
    " description OPENSTACK_NEUTRON_0000001_INTF",
    " encapsulation dot1Q 2005",
    " vrf forwarding nrouter-9ad979-0000001",
    " ip address 192.168.3.15 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 192.168.3.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 10",
    " standby 1064 name neutron-hsrp-1064-2005",
    "!",
    "interface Port-channel10.2029",
    " description OPENSTACK_NEUTRON_0000001_INTF",
    " encapsulation dot1Q 2029",
    " vrf forwarding nrouter-9ad979-0000001",
    " ip address 192.168.2.15 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 192.168.2.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 10",
    " standby 1064 name neutron-hsrp-1064-2029",
    "!",
    "interface Port-channel10.2031",
    " description OPENSTACK_NEUTRON_0000001_INTF",
    " encapsulation dot1Q 2031",
    " vrf forwarding nrouter-9ad979-0000001",
    " ip address 192.168.1.30 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 192.168.1.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 10",
    " standby 1064 name neutron-hsrp-1064-2031",
    "!",
    "interface Port-channel10.2044",
    " description OPENSTACK_NEUTRON_0000001_INTF",
    " encapsulation dot1Q 2044",
    " vrf forwarding nrouter-9ad979-0000001",
    " ip address 192.168.0.4 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 192.168.0.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 10",
    " standby 1064 name neutron-hsrp-1064-2044",
    "!",
    "interface Port-channel10.2499",
    " ip nat outside",
    "!",
    "interface Port-channel10.2536",
    " description OPENSTACK_NEUTRON_0000002_INTF",
    " encapsulation dot1Q 2535",
    " vrf forwarding nrouter-92740e-0000002",
    " ip address 192.168.0.7 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 192.168.0.1",
    " standby 1064 timers 1 3",
    " standby 1064 name neutron-hsrp-1064-2535",
    "!",
    "interface Port-channel10.2564",
    " description OPENSTACK_NEUTRON_0000002_INTF",
    " encapsulation dot1Q 2564",
    " vrf forwarding nrouter-3ea5f9-0000002",
    " ip address 10.2.0.4 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 10.2.0.1",
    " standby 1064 timers 1 3",
    " standby 1064 priority 97",
    " standby 1064 name neutron-hsrp-1064-2564",
    "!",
    "interface Port-channel10.2577",
    " description OPENSTACK_NEUTRON_0000002_INTF",
    " encapsulation dot1Q 2577",
    " vrf forwarding nrouter-bdc5b5-0000002",
    " ip address 20.20.20.3 255.255.255.0",
    " ip nat inside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 20.20.20.1",
    " standby 1064 timers 1 3",
    " standby 1064 name neutron-hsrp-1064-2577",
    "!",
    "interface Port-channel10.3000",
    " description OPENSTACK_NEUTRON_0000002_INTF",
    " encapsulation dot1Q 3000",
    " ip address 172.16.0.105 255.255.0.0",
    " ip nat outside",
    " standby delay minimum 30 reload 60",
    " standby version 2",
    " standby 1064 ip 172.16.0.107",
    " standby 1064 timers 1 3",
    " standby 1064 priority 97",
    " standby 1064 name neutron-hsrp-1064-3000",
    "!",
    "interface TenGigabitEthernet0/0/0",
    " no ip address",
    " cdp enable",
    " channel-group 10 mode active",
    "!",
    "interface TenGigabitEthernet0/1/0",
    " no ip address",
    " cdp enable",
    " channel-group 10 mode active",
    "!",
    "interface TenGigabitEthernet0/3/0",
    " no ip address",
    " shutdown",
    "!",
    "interface GigabitEthernet0",
    " vrf forwarding Mgmt-intf",
    " ip address 172.20.231.19 255.255.255.0",
    " negotiation auto",
    " no mop enabled"
]

TEST_ACL_RUNNING_CFG = [
    " vrf nrouter-bdc5b5-0000002 redundancy neutron-hsrp-1064-3000",
    "ip nat inside source static 10.2.0.5 172.16.0.126"
    " vrf nrouter-3ea5f9-0000002 redundancy neutron-hsrp-1064-3000",
    "ip nat inside source list neutron_acl_0000002_2564_471f1a63e pool"
    " nrouter-3ea5f9-0000002_nat_pool vrf nrouter-3ea5f9-0000002 overload",
    "ip nat inside source list neutron_acl_0000002_2535_86f655d1 pool"
    " nrouter-92740e-0000002_nat_pool vrf nrouter-92740e-0000002 overload",
    "ip nat inside source list neutron_acl_0000001_2005_xxxxxxxx pool"
    " nrouter-9ad979-0000001_nat_pool vrf nrouter-9ad979-0000001 overload",
    "ip nat inside source list neutron_acl_0000001_2029_yyyyyyyy pool"
    " nrouter-9ad979-0000001_nat_pool vrf nrouter-9ad979-0000001 overload",
    "ip nat inside source list neutron_acl_0000001_2031_zzzzzzzz pool"
    " nrouter-9ad979-0000001_nat_pool vrf nrouter-9ad979-0000001 overload",
    "ip nat inside source list neutron_acl_0000001_2044_11111111 pool"
    " nrouter-9ad979-0000001_nat_pool vrf nrouter-9ad979-0000001 overload",
    "ip nat inside source list neutron_acl_0000002_2577_3f70129a pool"
    " nrouter-bdc5b5-0000002_nat_pool vrf nrouter-bdc5b5-0000002 overload",
    "!",
    "ip access-list standard neutron_acl_0000001_2005_xxxxxxxx",
    " permit 192.168.3.0 0.0.0.255",
    "ip access-list standard neutron_acl_0000001_2029_yyyyyyyy",
    " permit 192.168.2.0 0.0.0.255",
    "ip access-list standard neutron_acl_0000001_2031_zzzzzzzz",
    " permit 192.168.1.0 0.0.0.255",
    "ip access-list standard neutron_acl_0000001_2044_11111111",
    " permit 192.168.0.0 0.0.0.255",
    "ip access-list standard neutron_acl_0000002_2535_86f655d1",
    " permit 192.168.0.0 0.0.0.255",
    "ip access-list standard neutron_acl_0000002_2564_47f1a63e",
    " permit 10.2.0.0 0.0.0.255",
    "ip access-list standard neutron_acl_0000002_2577_3f70129a",
    " permit 20.20.20.0 0.0.0.255"
]

# simulated neutron-db dictionary
NEUTRON_DB = [
    {
        "_floatingips": [
            {
                "fixed_ip_address": "20.20.20.7",
                "floating_ip_address": "172.16.0.120",
                "floating_network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
                "id": "1b8c01d7-fd60-4e09-9282-9c0085fe8ac6",
                "port_id": "c590b5f8-3fe5-4428-b3c0-fbe82a00d388",
                "router_id": "bdc5b513-7fee-4fe0-9514-78602246d6ee",
                "status": "ACTIVE",
                "tenant_id": "2386c5d814814fb68b037ab7aec784f8"
            },
            {
                "fixed_ip_address": "20.20.20.5",
                "floating_ip_address": "172.16.0.118",
                "floating_network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
                "id": "e8f26319-8c42-43ae-92d9-4e1ae789a48d",
                "port_id": "828ac37a-f730-4cc2-bcfc-08e62ca3cdb8",
                "router_id": "bdc5b513-7fee-4fe0-9514-78602246d6ee",
                "status": "ACTIVE",
                "tenant_id": "2386c5d814814fb68b037ab7aec784f8"
            }
        ],
        "_interfaces": [
            {
                "admin_state_up": True,
                "allowed_address_pairs": [],
                "binding:host_id": "asr1k-k7-controller-1-R2",
                "binding:profile": {},
                "binding:vif_details": {
                    "ovs_hybrid_plug": True,
                    "port_filter": True
                },
                "binding:vif_type": "ovs",
                "binding:vnic_type": "normal",
                "device_id": "7bee1420-d86f-43d3-bdd7-38750b77830a",
                "device_owner": "network:router_interface",
                "extra_dhcp_opts": [],
                "extra_subnets": [],
                "fixed_ips": [
                    {
                        "ip_address": "20.20.20.3",
                        "prefixlen": 24,
                        "subnet_id": "90c10f81-47f2-487c-ad1b-c7212c378e08"
                    }
                ],
                "ha_info": {
                    "group": "1064",
                    "ha_port": {
                        "admin_state_up": True,
                        "allowed_address_pairs": [],
                        "binding:host_id": "",
                        "binding:profile": {},
                        "binding:vif_details": {},
                        "binding:vif_type": "unbound",
                        "binding:vnic_type": "normal",
                        "device_id": "bdc5b513-7fee-4fe0-9514-78602246d6ee",
                        "device_owner": "network:router_interface",
                        "extra_dhcp_opts": [],
                        "extra_subnets": [],
                        "fixed_ips": [
                            {
                                "ip_address": "20.20.20.1",
                                "prefixlen": 24,
                                "subnet_id": "90c10f81-47f2-"
                                             "487c-ad1b-c7212c378e08"
                            }
                        ],
                        "id": "eda14976-481b-4dd4-a6c1-835dfd658dbd",
                        "mac_address": "fa:16:3e:1e:bf:be",
                        "name": "",
                        "network_id": "08aedf4f-dd83-4c1c-84f5-759430331eae",
                        "security_groups": [],
                        "status": "DOWN",
                        "subnets": [
                            {
                                "cidr": "20.20.20.0/24",
                                "gateway_ip": "20.20.20.1",
                                "id": "90c10f81-47f2-487c-ad1b-c7212c378e08",
                                "ipv6_ra_mode": None
                            }
                        ],
                        "tenant_id": "2386c5d814814fb68b037ab7aec784f8"
                    },
                    "other_config": "",
                    "timers_config": "",
                    "tracking_config": "",
                    "type": "HSRP"
                },
                "hosting_info": {
                    "hosting_mac": "fa:16:3e:4f:33:fb",
                    "hosting_port_id": "3f70129a-aefd-47ee-94d7-06ce9abf3cba",
                    "hosting_port_name": "",
                    "physical_interface": "Port-channel10",
                    "segmentation_id": 2577
                },
                "id": "3f70129a-aefd-47ee-94d7-06ce9abf3cba",
                "mac_address": "fa:16:3e:4f:33:fb",
                "name": "",
                "network_id": "08aedf4f-dd83-4c1c-84f5-759430331eae",
                "security_groups": [],
                "status": "ACTIVE",
                "subnets": [
                    {
                        "cidr": "20.20.20.0/24",
                        "gateway_ip": "20.20.20.1",
                        "id": "90c10f81-47f2-487c-ad1b-c7212c378e08",
                        "ipv6_ra_mode": None
                    }
                ],
                "tenant_id": ""
            }
        ],
        "admin_state_up": True,
        "cisco_ha:details": {
            "priority": 100,
            "probe_connectivity": False,
            "redundancy_level": 1,
            "redundancy_routers": [
                {
                    "id": "e7f8b39b-2d87-4eb7-9102-fd24eb3a2416",
                    "priority": 97,
                    "state": "STANDBY"
                }
            ],
            "state": "ACTIVE",
            "type": "HSRP"
        },
        "cisco_ha:enabled": True,
        "external_gateway_info": {
            "external_fixed_ips": [
                {
                    "ip_address": "172.16.0.116",
                    "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                }
            ],
            "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269"
        },
        "gw_port": {
            "admin_state_up": True,
            "allowed_address_pairs": [],
            "binding:host_id": "asr1k-k7-controller-1-R2",
            "binding:profile": {},
            "binding:vif_details": {
                "ovs_hybrid_plug": True,
                "port_filter": True
            },
            "binding:vif_type": "ovs",
            "binding:vnic_type": "normal",
            "device_id": "bdc5b513-7fee-4fe0-9514-78602246d6ee",
            "device_owner": "network:router_gateway",
            "extra_dhcp_opts": [],
            "extra_subnets": [],
            "fixed_ips": [
                {
                    "ip_address": "172.16.0.116",
                    "prefixlen": 16,
                    "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                }
            ],
            "ha_info": {
                "group": "1064",
                "ha_port": {
                    "admin_state_up": True,
                    "allowed_address_pairs": [],
                    "binding:host_id": "asr1k-k7-controller-1-R2",
                    "binding:profile": {},
                    "binding:vif_details": {
                        "ovs_hybrid_plug": True,
                        "port_filter": True
                    },
                    "binding:vif_type": "ovs",
                    "binding:vnic_type": "normal",
                    "device_id": "bdc5b513-7fee-4fe0-9514-78602246d6ee",
                    "device_owner": "network:router_gateway",
                    "extra_dhcp_opts": [],
                    "extra_subnets": [],
                    "fixed_ips": [
                        {
                            "ip_address": "172.16.0.116",
                            "prefixlen": 16,
                            "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                        }
                    ],
                    "id": "bb32ab93-88e7-4c80-aeec-387703cba0ea",
                    "mac_address": "fa:16:3e:ef:c0:88",
                    "name": "",
                    "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
                    "security_groups": [],
                    "status": "ACTIVE",
                    "subnets": [
                        {
                            "cidr": "172.16.0.0/16",
                            "gateway_ip": "172.16.0.1",
                            "id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b",
                            "ipv6_ra_mode": None
                        }
                    ],
                    "tenant_id": ""
                },
                "other_config": "",
                "timers_config": "",
                "tracking_config": "",
                "type": "HSRP"
            },
            "hosting_info": {
                "hosting_mac": "fa:16:3e:ef:c0:88",
                "hosting_port_id": "bb32ab93-88e7-4c80-aeec-387703cba0ea",
                "hosting_port_name": "",
                "physical_interface": "Port-channel10",
                "segmentation_id": 3000
            },
            "id": "bb32ab93-88e7-4c80-aeec-387703cba0ea",
            "mac_address": "fa:16:3e:ef:c0:88",
            "name": "",
            "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
            "security_groups": [],
            "status": "ACTIVE",
            "subnets": [
                {
                    "cidr": "172.16.0.0/16",
                    "gateway_ip": "172.16.0.1",
                    "id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b",
                    "ipv6_ra_mode": None
                }
            ],
            "tenant_id": ""
        },
        "gw_port_id": "bb32ab93-88e7-4c80-aeec-387703cba0ea",
        "hosting_device": {
            "admin_state_up": True,
            "booting_time": 360,
            "created_at": "2015-11-16 22:54:18",
            "credentials": {
                "password": "cisco123",
                "user_name": "admin"
            },
            "host_category": "Hardware",
            "id": "00000000-0000-0000-0000-000000000003",
            "management_ip_address": "172.20.231.19",
            "name": "ASR1k template",
            "protocol_port": 22,
            "service_types": "router:FW:VPN",
            "status": "ACTIVE",
            "template_id": "00000000-0000-0000-0000-000000000003",
            "timeout": None
        },
        "id": "bdc5b513-7fee-4fe0-9514-78602246d6ee",
        "name": "ROUTER1",
        "router_type": {
            "cfg_agent_driver": "neutron.plugins.cisco.cfg_agent."
                                "device_drivers.asr1k.asr1k_routing_driver."
                                "ASR1kRoutingDriver",
            "cfg_agent_service_helper": "neutron.plugins.cisco.cfg_agent."
                                        "service_helpers.routing_svc_helper."
                                        "RoutingServiceHelper",
            "id": "00000000-0000-0000-0000-000000000003",
            "name": "ASR1k_router"
        },
        "routerhost:hosting_device": "00000000-0000-0000-0000-000000000003",
        "routerrole:role": None,
        "routertype-aware-scheduler:auto_schedule": True,
        "routertype-aware-scheduler:share_hosting_device": True,
        "routertype:id": "00000000-0000-0000-0000-000000000003",
        "routes": [],
        "share_host": True,
        "status": "ACTIVE",
        "tenant_id": "2386c5d814814fb68b037ab7aec784f8"
    },
    {
        "_floatingips": [
            {
                "fixed_ip_address": "10.2.0.5",
                "floating_ip_address": "172.16.0.126",
                "floating_network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
                "id": "0b38bc64-7b01-440d-94fa-4e967f410aa6",
                "port_id": "c186b8d5-a835-4128-a7e0-20b273defc02",
                "router_id": "17478180-082c-4dbc-a35b-e7fdfb260cd6",
                "status": "ACTIVE",
                "tenant_id": "ec3a24a6ffa244aab77501f5cea69be9"
            }
        ],
        "_interfaces": [
            {
                "admin_state_up": True,
                "allowed_address_pairs": [],
                "binding:host_id": "asr1k-k7-controller-1-R2",
                "binding:profile": {},
                "binding:vif_details": {
                    "ovs_hybrid_plug": True,
                    "port_filter": True
                },
                "binding:vif_type": "ovs",
                "binding:vnic_type": "normal",
                "device_id": "3ea5f9f9-0ecf-4595-b8be-3f340f2c82e3",
                "device_owner": "network:router_interface",
                "extra_dhcp_opts": [],
                "extra_subnets": [],
                "fixed_ips": [
                    {
                        "ip_address": "10.2.0.4",
                        "prefixlen": 24,
                        "subnet_id": "eee64e1c-e7e8-4b06-9161-148ca25bb04d"
                    }
                ],
                "ha_info": {
                    "group": "1064",
                    "ha_port": {
                        "admin_state_up": True,
                        "allowed_address_pairs": [],
                        "binding:host_id": "",
                        "binding:profile": {},
                        "binding:vif_details": {},
                        "binding:vif_type": "unbound",
                        "binding:vnic_type": "normal",
                        "device_id": "17478180-082c-4dbc-a35b-e7fdfb260cd6",
                        "device_owner": "network:router_interface",
                        "extra_dhcp_opts": [],
                        "extra_subnets": [],
                        "fixed_ips": [
                            {
                                "ip_address": "10.2.0.1",
                                "prefixlen": 24,
                                "subnet_id": "eee64e1c-e7e8-4b06-9161"
                                             "-148ca25bb04d"
                            }
                        ],
                        "id": "f1d20abe-b7ec-4f14-91f5-3465e1b0fd6b",
                        "mac_address": "fa:16:3e:1c:d5:40",
                        "name": "",
                        "network_id": "b26c62fa-3fa8-4615-ad8d-bf7bdd443712",
                        "security_groups": [],
                        "status": "DOWN",
                        "subnets": [
                            {
                                "cidr": "10.2.0.0/24",
                                "gateway_ip": "10.2.0.1",
                                "id": "eee64e1c-e7e8-4b06-9161-148ca25bb04d",
                                "ipv6_ra_mode": None
                            }
                        ],
                        "tenant_id": "ec3a24a6ffa244aab77501f5cea69be9"
                    },
                    "other_config": "",
                    "timers_config": "",
                    "tracking_config": "",
                    "type": "HSRP"
                },
                "hosting_info": {
                    "hosting_mac": "fa:16:3e:69:50:00",
                    "hosting_port_id": "47f1a63e-2c75-4975-aeac-e1f69b9904b6",
                    "hosting_port_name": "",
                    "physical_interface": "Port-channel10",
                    "segmentation_id": 2564
                },
                "id": "47f1a63e-2c75-4975-aeac-e1f69b9904b6",
                "mac_address": "fa:16:3e:69:50:00",
                "name": "",
                "network_id": "b26c62fa-3fa8-4615-ad8d-bf7bdd443712",
                "security_groups": [],
                "status": "ACTIVE",
                "subnets": [
                    {
                        "cidr": "10.2.0.0/24",
                        "gateway_ip": "10.2.0.1",
                        "id": "eee64e1c-e7e8-4b06-9161-148ca25bb04d",
                        "ipv6_ra_mode": None
                    }
                ],
                "tenant_id": ""
            }
        ],
        "admin_state_up": True,
        "cisco_ha:details": {
            "priority": 100,
            "probe_connectivity": False,
            "redundancy_level": 1,
            "redundancy_routers": [
                {
                    "id": "3ea5f9f9-0ecf-4595-b8be-3f340f2c82e3",
                    "priority": 97,
                    "state": "STANDBY"
                }
            ],
            "state": "ACTIVE",
            "type": "HSRP"
        },
        "cisco_ha:enabled": True,
        "external_gateway_info": {
            "external_fixed_ips": [
                {
                    "ip_address": "172.16.0.125",
                    "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                }
            ],
            "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269"
        },
        "gw_port": {
            "admin_state_up": True,
            "allowed_address_pairs": [],
            "binding:host_id": "asr1k-k7-controller-1-R2",
            "binding:profile": {},
            "binding:vif_details": {
                "ovs_hybrid_plug": True,
                "port_filter": True
            },
            "binding:vif_type": "ovs",
            "binding:vnic_type": "normal",
            "device_id": "3ea5f9f9-0ecf-4595-b8be-3f340f2c82e3",
            "device_owner": "network:router_gateway",
            "extra_dhcp_opts": [],
            "extra_subnets": [],
            "fixed_ips": [
                {
                    "ip_address": "172.16.0.125",
                    "prefixlen": 16,
                    "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                }
            ],
            "ha_info": {
                "group": "1064",
                "ha_port": {
                    "admin_state_up": True,
                    "allowed_address_pairs": [],
                    "binding:host_id": "asr1k-k7-controller-1-R2",
                    "binding:profile": {},
                    "binding:vif_details": {
                        "ovs_hybrid_plug": True,
                        "port_filter": True
                    },
                    "binding:vif_type": "ovs",
                    "binding:vnic_type": "normal",
                    "device_id": "17478180-082c-4dbc-a35b-e7fdfb260cd6",
                    "device_owner": "network:router_gateway",
                    "extra_dhcp_opts": [],
                    "extra_subnets": [],
                    "fixed_ips": [
                        {
                            "ip_address": "172.16.0.124",
                            "prefixlen": 16,
                            "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                        }
                    ],
                    "id": "b7f1d6eb-7016-4bcd-93d5-9f5254bd672e",
                    "mac_address": "fa:16:3e:01:8a:85",
                    "name": "",
                    "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
                    "security_groups": [],
                    "status": "ACTIVE",
                    "subnets": [
                        {
                            "cidr": "172.16.0.0/16",
                            "gateway_ip": "172.16.0.1",
                            "id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b",
                            "ipv6_ra_mode": None
                        }
                    ],
                    "tenant_id": ""
                },
                "other_config": "",
                "timers_config": "",
                "tracking_config": "",
                "type": "HSRP"
            },
            "hosting_info": {
                "hosting_mac": "fa:16:3e:4c:47:f2",
                "hosting_port_id": "7d71cf06-2463-4350-a5ee-a8bb09c5466c",
                "hosting_port_name": "",
                "physical_interface": "Port-channel10",
                "segmentation_id": 3000
            },
            "id": "7d71cf06-2463-4350-a5ee-a8bb09c5466c",
            "mac_address": "fa:16:3e:4c:47:f2",
            "name": "",
            "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
            "security_groups": [],
            "status": "ACTIVE",
            "subnets": [
                {
                    "cidr": "172.16.0.0/16",
                    "gateway_ip": "172.16.0.1",
                    "id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b",
                    "ipv6_ra_mode": None
                }
            ],
            "tenant_id": ""
        },
        "gw_port_id": "7d71cf06-2463-4350-a5ee-a8bb09c5466c",
        "hosting_device": {
            "admin_state_up": True,
            "booting_time": 360,
            "created_at": "2015-11-16 22:54:18",
            "credentials": {
                "password": "cisco123",
                "user_name": "admin"
            },
            "host_category": "Hardware",
            "id": "00000000-0000-0000-0000-000000000003",
            "management_ip_address": "172.20.231.19",
            "name": "ASR1k template",
            "protocol_port": 22,
            "service_types": "router:FW:VPN",
            "status": "ACTIVE",
            "template_id": "00000000-0000-0000-0000-000000000003",
            "timeout": None
        },
        "id": "3ea5f9f9-0ecf-4595-b8be-3f340f2c82e3",
        "name": "rally_net_vm4FfgSGedr94BsU_HA_backup_1",
        "router_type": {
            "cfg_agent_driver": "neutron.plugins.cisco.cfg_agent."
                                "device_drivers.asr1k.asr1k_routing_driver."
                                "ASR1kRoutingDriver",
            "cfg_agent_service_helper": "neutron.plugins.cisco.cfg_agent."
                                        "service_helpers.routing_svc_helper."
                                        "RoutingServiceHelper",
            "id": "00000000-0000-0000-0000-000000000003",
            "name": "ASR1k_router"
        },
        "routerhost:hosting_device": "00000000-0000-0000-0000-000000000003",
        "routerrole:role": "HA-Redundancy",
        "routertype-aware-scheduler:auto_schedule": True,
        "routertype-aware-scheduler:share_hosting_device": True,
        "routertype:id": "00000000-0000-0000-0000-000000000003",
        "routes": [],
        "share_host": True,
        "status": "ACTIVE",
        "tenant_id": ""
    },
    {
        "_floatingips": [
            {
                "fixed_ip_address": "192.168.0.9",
                "floating_ip_address": "172.16.0.109",
                "floating_network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
                "id": "0e6807b0-0de8-4df2-bd9d-6c822d512dcc",
                "port_id": "b488932b-c0dd-40ee-bc84-a35a01e3c967",
                "router_id": "92740eb5-3604-421a-91a3-04561af775fc",
                "status": "ACTIVE",
                "tenant_id": "ecf8697e8dc04fef8be7c7f9c3594de9"
            }
        ],
        "_interfaces": [
            {
                "admin_state_up": True,
                "allowed_address_pairs": [],
                "binding:host_id": "asr1k-k7-controller-1-R2",
                "binding:profile": {},
                "binding:vif_details": {
                    "ovs_hybrid_plug": True,
                    "port_filter": True
                },
                "binding:vif_type": "ovs",
                "binding:vnic_type": "normal",
                "device_id": "0562d6c6-0732-4d68-9eb2-e423e7bef004",
                "device_owner": "network:router_interface",
                "extra_dhcp_opts": [],
                "extra_subnets": [],
                "fixed_ips": [
                    {
                        "ip_address": "192.168.0.7",
                        "prefixlen": 24,
                        "subnet_id": "6fdaaae3-4034-4890-ab60-1411527e4556"
                    }
                ],
                "ha_info": {
                    "group": "1064",
                    "ha_port": {
                        "admin_state_up": True,
                        "allowed_address_pairs": [],
                        "binding:host_id": "",
                        "binding:profile": {},
                        "binding:vif_details": {},
                        "binding:vif_type": "unbound",
                        "binding:vnic_type": "normal",
                        "device_id": "92740eb5-3604-421a-91a3-04561af775fc",
                        "device_owner": "network:router_interface",
                        "extra_dhcp_opts": [],
                        "extra_subnets": [],
                        "fixed_ips": [
                            {
                                "ip_address": "192.168.0.1",
                                "prefixlen": 24,
                                "subnet_id": "6fdaaae3-4034-4890-ab60-"
                                             "1411527e4556"
                            }
                        ],
                        "id": "4f4be053-1ee1-4193-a0c4-d03dce548986",
                        "mac_address": "fa:16:3e:79:67:80",
                        "name": "",
                        "network_id": "5ca17eaa-8761-48b3-9284-983d9c0983df",
                        "security_groups": [],
                        "status": "DOWN",
                        "subnets": [
                            {
                                "cidr": "192.168.0.0/24",
                                "gateway_ip": "192.168.0.1",
                                "id": "6fdaaae3-4034-4890-ab60-1411527e4556",
                                "ipv6_ra_mode": None
                            }
                        ],
                        "tenant_id": "ecf8697e8dc04fef8be7c7f9c3594de9"
                    },
                    "other_config": "",
                    "timers_config": "",
                    "tracking_config": "",
                    "type": "HSRP"
                },
                "hosting_info": {
                    "hosting_mac": "fa:16:3e:e8:a3:24",
                    "hosting_port_id": "86f655d1-49b4-44c9-b91e-ec683be80ce8",
                    "hosting_port_name": "",
                    "physical_interface": "Port-channel10",
                    "segmentation_id": 2535
                },
                "id": "86f655d1-49b4-44c9-b91e-ec683be80ce8",
                "mac_address": "fa:16:3e:e8:a3:24",
                "name": "",
                "network_id": "5ca17eaa-8761-48b3-9284-983d9c0983df",
                "security_groups": [],
                "status": "ACTIVE",
                "subnets": [
                    {
                        "cidr": "192.168.0.0/24",
                        "gateway_ip": "192.168.0.1",
                        "id": "6fdaaae3-4034-4890-ab60-1411527e4556",
                        "ipv6_ra_mode": None
                    }
                ],
                "tenant_id": ""
            }
        ],
        "admin_state_up": True,
        "cisco_ha:details": {
            "priority": 100,
            "probe_connectivity": False,
            "redundancy_level": 1,
            "redundancy_routers": [
                {
                    "id": "ea0f1fde-e00f-49f1-aa60-6e30c1197ea5",
                    "priority": 97,
                    "state": "STANDBY"
                }
            ],
            "state": "ACTIVE",
            "type": "HSRP"
        },
        "cisco_ha:enabled": True,
        "external_gateway_info": {
            "external_fixed_ips": [
                {
                    "ip_address": "172.16.0.101",
                    "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                }
            ],
            "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269"
        },
        "gw_port": {
            "admin_state_up": True,
            "allowed_address_pairs": [],
            "binding:host_id": "asr1k-k7-controller-1-R2",
            "binding:profile": {},
            "binding:vif_details": {
                "ovs_hybrid_plug": True,
                "port_filter": True
            },
            "binding:vif_type": "ovs",
            "binding:vnic_type": "normal",
            "device_id": "92740eb5-3604-421a-91a3-04561af775fc",
            "device_owner": "network:router_gateway",
            "extra_dhcp_opts": [],
            "extra_subnets": [],
            "fixed_ips": [
                {
                    "ip_address": "172.16.0.101",
                    "prefixlen": 16,
                    "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                }
            ],
            "ha_info": {
                "group": "1064",
                "ha_port": {
                    "admin_state_up": True,
                    "allowed_address_pairs": [],
                    "binding:host_id": "asr1k-k7-controller-1-R2",
                    "binding:profile": {},
                    "binding:vif_details": {
                        "ovs_hybrid_plug": True,
                        "port_filter": True
                    },
                    "binding:vif_type": "ovs",
                    "binding:vnic_type": "normal",
                    "device_id": "92740eb5-3604-421a-91a3-04561af775fc",
                    "device_owner": "network:router_gateway",
                    "extra_dhcp_opts": [],
                    "extra_subnets": [],
                    "fixed_ips": [
                        {
                            "ip_address": "172.16.0.101",
                            "prefixlen": 16,
                            "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                        }
                    ],
                    "id": "f8695a3d-28cd-4833-aecd-b5b64cb7f7a9",
                    "mac_address": "fa:16:3e:96:ed:91",
                    "name": "",
                    "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
                    "security_groups": [],
                    "status": "ACTIVE",
                    "subnets": [
                        {
                            "cidr": "172.16.0.0/16",
                            "gateway_ip": "172.16.0.1",
                            "id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b",
                            "ipv6_ra_mode": None
                        }
                    ],
                    "tenant_id": ""
                },
                "other_config": "",
                "timers_config": "",
                "tracking_config": "",
                "type": "HSRP"
            },
            "hosting_info": {
                "hosting_mac": "fa:16:3e:96:ed:91",
                "hosting_port_id": "f8695a3d-28cd-4833-aecd-b5b64cb7f7a9",
                "hosting_port_name": "",
                "physical_interface": "Port-channel10",
                "segmentation_id": 3000
            },
            "id": "f8695a3d-28cd-4833-aecd-b5b64cb7f7a9",
            "mac_address": "fa:16:3e:96:ed:91",
            "name": "",
            "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
            "security_groups": [],
            "status": "ACTIVE",
            "subnets": [
                {
                    "cidr": "172.16.0.0/16",
                    "gateway_ip": "172.16.0.1",
                    "id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b",
                    "ipv6_ra_mode": None
                }
            ],
            "tenant_id": ""
        },
        "gw_port_id": "f8695a3d-28cd-4833-aecd-b5b64cb7f7a9",
        "hosting_device": {
            "admin_state_up": True,
            "booting_time": 360,
            "created_at": "2015-11-16 22:54:18",
            "credentials": {
                "password": "cisco123",
                "user_name": "admin"
            },
            "host_category": "Hardware",
            "id": "00000000-0000-0000-0000-000000000003",
            "management_ip_address": "172.20.231.19",
            "name": "ASR1k template",
            "protocol_port": 22,
            "service_types": "router:FW:VPN",
            "status": "ACTIVE",
            "template_id": "00000000-0000-0000-0000-000000000003",
            "timeout": None
        },
        "id": "92740eb5-3604-421a-91a3-04561af775fc",
        "name": "ROUTER-1",
        "router_type": {
            "cfg_agent_driver": "neutron.plugins.cisco.cfg_agent."
                                "device_drivers.asr1k.asr1k_routing_driver."
                                "ASR1kRoutingDriver",
            "cfg_agent_service_helper": "neutron.plugins.cisco.cfg_agent."
                                        "service_helpers.routing_svc_helper."
                                        "RoutingServiceHelper",
            "id": "00000000-0000-0000-0000-000000000003",
            "name": "ASR1k_router"
        },
        "routerhost:hosting_device": "00000000-0000-0000-0000-000000000003",
        "routerrole:role": None,
        "routertype-aware-scheduler:auto_schedule": True,
        "routertype-aware-scheduler:share_hosting_device": True,
        "routertype:id": "00000000-0000-0000-0000-000000000003",
        "routes": [],
        "share_host": True,
        "status": "ACTIVE",
        "tenant_id": "ecf8697e8dc04fef8be7c7f9c3594de9"
    },
    {
        "admin_state_up": True,
        "cisco_ha:details": {
            "priority": 100,
            "probe_connectivity": False,
            "redundancy_level": 2,
            "redundancy_routers": [
                {
                    "id": "213fd355-78c3-44cc-bd6e-492b9ade2602",
                    "priority": 97,
                    "state": "STANDBY"
                },
                {
                    "id": "15315cc4-d00d-446d-bf6e-b077faaefaa1",
                    "priority": 100,
                    "state": "STANDBY"
                }
            ],
            "state": "ACTIVE",
            "type": "HSRP"
        },
        "cisco_ha:enabled": True,
        "external_gateway_info": {
            "external_fixed_ips": [
                {
                    "ip_address": "172.16.0.105",
                    "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                }
            ],
            "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269"
        },
        "gw_port": {
            "admin_state_up": True,
            "allowed_address_pairs": [],
            "binding:host_id": "asr1k-k7-controller-1-R2",
            "binding:profile": {},
            "binding:vif_details": {
                "ovs_hybrid_plug": True,
                "port_filter": True
            },
            "binding:vif_type": "ovs",
            "binding:vnic_type": "normal",
            "device_id": "213fd355-78c3-44cc-bd6e-492b9ade2602",
            "device_owner": "network:router_gateway",
            "extra_dhcp_opts": [],
            "extra_subnets": [],
            "fixed_ips": [
                {
                    "ip_address": "172.16.0.105",
                    "prefixlen": 16,
                    "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                }
            ],
            "ha_info": {
                "group": "1064",
                "ha_port": {
                    "admin_state_up": True,
                    "allowed_address_pairs": [],
                    "binding:host_id": "",
                    "binding:profile": {},
                    "binding:vif_details": {},
                    "binding:vif_type": "unbound",
                    "binding:vnic_type": "normal",
                    "device_id": "a2617b46-78ef-49ba-95b5-0f3ff90f1f91",
                    "device_owner": "network:router_gateway",
                    "extra_dhcp_opts": [],
                    "extra_subnets": [],
                    "fixed_ips": [
                        {
                            "ip_address": "172.16.0.104",
                            "prefixlen": 16,
                            "subnet_id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b"
                        }
                    ],
                    "id": "b768491c-4b76-492f-a0ee-56bc50867a07",
                    "mac_address": "fa:16:3e:77:ae:bb",
                    "name": "",
                    "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
                    "security_groups": [],
                    "status": "DOWN",
                    "subnets": [
                        {
                            "cidr": "172.16.0.0/16",
                            "gateway_ip": "172.16.0.1",
                            "id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b",
                            "ipv6_ra_mode": None
                        }
                    ],
                    "tenant_id": ""
                },
                "other_config": "",
                "timers_config": "",
                "tracking_config": "",
                "type": "HSRP"
            },
            "hosting_info": {
                "hosting_mac": "fa:16:3e:97:ec:f2",
                "hosting_port_id": "527b7bc0-d6ba-4d07-932a-60e96da86173",
                "hosting_port_name": "",
                "physical_interface": "Port-channel10",
                "segmentation_id": 3000
            },
            "id": "527b7bc0-d6ba-4d07-932a-60e96da86173",
            "mac_address": "fa:16:3e:97:ec:f2",
            "name": "",
            "network_id": "7a38a5fd-3ad9-4952-ab08-4def22407269",
            "security_groups": [],
            "status": "ACTIVE",
            "subnets": [
                {
                    "cidr": "172.16.0.0/16",
                    "gateway_ip": "172.16.0.1",
                    "id": "8f9c885d-a2ad-4fff-8127-2d4b3af6015b",
                    "ipv6_ra_mode": None
                }
            ],
            "tenant_id": ""
        },
        "gw_port_id": "527b7bc0-d6ba-4d07-932a-60e96da86173",
        "hosting_device": {
            "admin_state_up": True,
            "booting_time": 360,
            "created_at": "2015-11-16 22:54:18",
            "credentials": {
                "password": "cisco123",
                "user_name": "admin"
            },
            "host_category": "Hardware",
            "id": "00000000-0000-0000-0000-000000000003",
            "management_ip_address": "172.20.231.19",
            "name": "ASR1k template",
            "protocol_port": 22,
            "service_types": "router:FW:VPN",
            "status": "ACTIVE",
            "template_id": "00000000-0000-0000-0000-000000000003",
            "timeout": None
        },
        "id": "213fd355-78c3-44cc-bd6e-492b9ade2602",
        "name": "Global-router-0000-000000000003",
        "router_type": {
            "cfg_agent_driver": "neutron.plugins.cisco.cfg_agent."
                                "device_drivers.asr1k.asr1k_routing_driver."
                                "ASR1kRoutingDriver",
            "cfg_agent_service_helper": "neutron.plugins.cisco.cfg_agent."
                                        "service_helpers.routing_svc_helper."
                                        "RoutingServiceHelper",
            "id": "00000000-0000-0000-0000-000000000003",
            "name": "ASR1k_router"
        },
        "routerhost:hosting_device": "00000000-0000-0000-0000-000000000003",
        "routerrole:role": "Global",
        "routertype-aware-scheduler:auto_schedule": False,
        "routertype-aware-scheduler:share_hosting_device": True,
        "routertype:id": "00000000-0000-0000-0000-000000000003",
        "routes": [],
        "share_host": True,
        "status": "ACTIVE",
        "tenant_id": ""
    }
]


class ASR1kCfgSyncer(base.BaseTestCase):

    def setUp(self):
        super(ASR1kCfgSyncer, self).setUp()

        # self._read_neutron_db_data()
        self.router_db_info = NEUTRON_DB
        self.hosting_device_info = {
            'id': '00000000-0000-0000-0000-000000000003'}
        self.driver = mock.Mock()
        self.config_syncer = asr1k_cfg_syncer.ConfigSyncer(self.router_db_info,
                                                      self.driver,
                                                      self.hosting_device_info)

    def test_delete_invalid_cfg_empty_routers_list(self):
        """
        expected invalid_cfg
        [u'ip nat inside source static 10.2.0.5 172.16.0.126 vrf'
          ' nrouter-3ea5f9 redundancy neutron-hsrp-1064-3000',
         u'ip nat inside source list neutron_acl_2564 pool'
          ' nrouter-3ea5f9_nat_pool vrf nrouter-3ea5f9 overload',
         u'ip nat pool nrouter-3ea5f9_nat_pool 172.16.0.124'
          ' 172.16.0.124 netmask 255.255.0.0',
         u'ip route vrf nrouter-3ea5f9 0.0.0.0 0.0.0.0'
          ' Port-channel10.3000 172.16.0.1',
         u'ip access-list standard neutron_acl_2564',
         <IOSCfgLine # 83 'interface Port-channel10.2564'>,
         <IOSCfgLine # 96 'interface Port-channel10.3000'>,
         u'nrouter-3ea5f9']
        """

        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

        # simulate a blank neutron-db
        router_db_info = []

        self.config_syncer = asr1k_cfg_syncer.ConfigSyncer(router_db_info,
                                                      self.driver,
                                                      self.hosting_device_info)
        self.config_syncer.get_running_config = mock.Mock(
            return_value=ASR_BASIC_RUNNING_CFG_NO_MULTI_REGION)

        invalid_cfg = self.config_syncer.delete_invalid_cfg()
        self.assertEqual(8, len(invalid_cfg))

    def test_delete_invalid_cfg_with_multi_region_and_empty_routers_list(self):
        """
        This test verifies that the  cfg-syncer will delete invalid cfg
        if the neutron-db (routers dictionary list) happens to be empty.

        Since the neutron-db router_db_info is empty, all region 0000002
        running-config should be deleted.

        Expect 8 invalid configs found

        ['ip nat inside source static 10.2.0.5 172.16.0.126'
          ' vrf nrouter-3ea5f9-0000002 redundancy neutron-hsrp-1064-3000',
         'ip nat inside source list neutron_acl_0000002_2564 pool '
         'nrouter-3ea5f9-0000002_nat_pool vrf nrouter-3ea5f9-0000002 overload',
         'ip nat pool nrouter-3ea5f9-0000002_nat_pool '
          '172.16.0.124 172.16.0.124 netmask 255.255.0.0',
         'ip route vrf nrouter-3ea5f9-0000002 0.0.0.0 0.0.0.0'
          ' Port-channel10.3000 172.16.0.1',
         'ip access-list standard neutron_acl_0000002_2564',
         <IOSCfgLine # 83 'interface Port-channel10.2564'>,
         <IOSCfgLine # 96 'interface Port-channel10.3000'>,
         'nrouter-3ea5f9-0000002']
        """

        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        cfg.CONF.set_override('region_id', '0000002', 'multi_region')
        cfg.CONF.set_override('other_region_ids', ['0000001'], 'multi_region')

        # simulate a blank neutron-db
        router_db_info = []
        self.config_syncer = asr1k_cfg_syncer.ConfigSyncer(router_db_info,
                                                      self.driver,
                                                      self.hosting_device_info)

        self.config_syncer.get_running_config = mock.Mock(
            return_value=ASR_BASIC_RUNNING_CFG)

        invalid_cfg = self.config_syncer.delete_invalid_cfg()

        self.assertEqual(8, len(invalid_cfg))

    def test_clean_interfaces_basic_multi_region_enabled(self):
        """
        In this test, we are simulating a cfg-sync, clean_interfaces for
        region 0000002 cfg-agent.  Running-cfg only exists for region
        0000001.

        At the end of test, we should expect zero entries in invalid_cfg.
        """

        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        cfg.CONF.set_override('region_id', '0000002', 'multi_region')
        cfg.CONF.set_override('other_region_ids', ['0000001'], 'multi_region')

        intf_segment_dict = self.config_syncer.intf_segment_dict
        segment_nat_dict = self.config_syncer.segment_nat_dict

        conn = self.driver._get_connection()

        parsed_cfg = HTParser(ASR_RUNNING_CFG_NO_R2_JSON_JUST_INTERFACES)

        invalid_cfg = self.config_syncer.clean_interfaces(conn,
                                              intf_segment_dict,
                                              segment_nat_dict,
                                              parsed_cfg)
        self.assertEqual([], invalid_cfg)

    def test_clean_interfaces_multi_region_disabled(self):
        """
        In this test, we are simulating a cfg-sync, clean_interfaces for
        region 0000002 cfg-agent.  Running-cfg only exists for region
        0000001, but multi_region is disabled.

        At the end of test, we should expect zero entries in invalid_cfg.
        """
        cfg.CONF.set_override('enable_multi_region', False, 'multi_region')

        intf_segment_dict = self.config_syncer.intf_segment_dict
        segment_nat_dict = self.config_syncer.segment_nat_dict

        conn = self.driver._get_connection()

        parsed_cfg = HTParser(ASR_RUNNING_CFG_NO_R2_JSON_JUST_INTERFACES)

        invalid_cfg = self.config_syncer.clean_interfaces(conn,
                                              intf_segment_dict,
                                              segment_nat_dict,
                                              parsed_cfg)
        self.assertEqual([], invalid_cfg)

    def test_clean_interfaces_R2_run_cfg_present_multi_region_enabled(self):
        """
        In this test, we are simulating a cfg-sync, clean_interfaces for
        region 0000002 cfg-agent.  Existing running-cfg exists for region
        0000001 and 0000002.

        At the end of test, we should expect zero entries in invalid_cfg.
        """
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        cfg.CONF.set_override('region_id', '0000002', 'multi_region')
        cfg.CONF.set_override('other_region_ids', ['0000001'], 'multi_region')

        intf_segment_dict = self.config_syncer.intf_segment_dict
        segment_nat_dict = self.config_syncer.segment_nat_dict

        conn = self.driver._get_connection()

        parsed_cfg = HTParser(ASR_BASIC_RUNNING_CFG)

        invalid_cfg = self.config_syncer.clean_interfaces(conn,
                                              intf_segment_dict,
                                              segment_nat_dict,
                                              parsed_cfg)
        self.assertEqual([], invalid_cfg)

    def test_clean_interfaces_R2_with_invalid_intfs(self):
        """
        In this test, we are simulating a cfg-sync, clean_interfaces for
        region 0000002 cfg-agent.  Existing running-cfg exists for region
        0000001 and 0000002.

        At the end of test, we should expect two invalid intfs
        detected.

        invalid tenant router, int Po10.2536 (invalid segment-id)
        invalid ext-gw-port, int Po10.3000 (invalid HSRP VIP)
        """
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        cfg.CONF.set_override('region_id', '0000002', 'multi_region')
        cfg.CONF.set_override('other_region_ids', ['0000001'], 'multi_region')

        intf_segment_dict = self.config_syncer.intf_segment_dict
        segment_nat_dict = self.config_syncer.segment_nat_dict

        conn = self.driver._get_connection()
        parsed_cfg = HTParser(ASR_RUNNING_CFG_WITH_INVALID_INTFS)

        invalid_cfg = self.config_syncer.clean_interfaces(conn,
                                              intf_segment_dict,
                                              segment_nat_dict,
                                              parsed_cfg)

        self.assertEqual(2, len(invalid_cfg))

    def test_clean_acls_basic_running_cfg(self):
        """
        region 1 acls should be ignored
        """
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        cfg.CONF.set_override('region_id', '0000002', 'multi_region')
        cfg.CONF.set_override('other_region_ids', ['0000001'], 'multi_region')

        intf_segment_dict = self.config_syncer.intf_segment_dict
        segment_nat_dict = self.config_syncer.segment_nat_dict

        conn = self.driver._get_connection()

        parsed_cfg = HTParser(TEST_ACL_RUNNING_CFG)

        invalid_cfg = self.config_syncer.clean_acls(conn,
                                                    intf_segment_dict,
                                                    segment_nat_dict,
                                                    parsed_cfg)

        self.assertEqual([], invalid_cfg)

    def test_clean_nat_pool_overload_basic_running_cfg(self):
        """
        region 1 acls should be ignored
        """
        cfg.CONF.set_override('enable_multi_region', True, 'multi_region')
        cfg.CONF.set_override('region_id', '0000002', 'multi_region')
        cfg.CONF.set_override('other_region_ids', ['0000001'], 'multi_region')

        router_id_dict = self.config_syncer.router_id_dict
        intf_segment_dict = self.config_syncer.intf_segment_dict
        segment_nat_dict = self.config_syncer.segment_nat_dict

        conn = self.driver._get_connection()

        parsed_cfg = HTParser(TEST_ACL_RUNNING_CFG)
        invalid_cfg = self.config_syncer.clean_nat_pool_overload(conn,
                                                     router_id_dict,
                                                     intf_segment_dict,
                                                     segment_nat_dict,
                                                     parsed_cfg)

        self.assertEqual([], invalid_cfg)
