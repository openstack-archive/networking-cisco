# Copyright 2015-2016 Cisco Systems, Inc.
# All rights reserved.
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

# VIF_DETAILS attribute for port profile name used by the Nova VIF driver.
VIF_DETAILS_PROFILEID = 'profileid'

# Supported network interface cards
PCI_INFO_CISCO_VIC_1240 = "1137:0071"
PCI_INFO_INTEL_82599 = "8086:10c9"

VLAN_PATH = "fabric/lan"
VLAN_COMPRESSION_TYPE = "included"
DESCR = "Created by OpenStack UCSM Mech Driver"
PORT_PROFILESETDN = "fabric/lan/profiles"

# High Performance mode to be set within Port profiles for "Direct" mode.
HIGH_PERF = "high-perf-reqd"
NONE = "none"

# Max ports that this port profile can be applied to
MAX_PORTS = 64

VIF_TYPE_802_QBH = '802.1qbh'

VNIC_PATH_PREFIX = "/vnic-"
VLAN_PATH_PREFIX = "/if-"
VLAN_PROFILE_PATH_PREFIX = "/net-"
VLAN_PROFILE_NAME_PREFIX = "OS-"
PORT_PROFILE_NAME_PREFIX = "OS-PP-"
CLIENT_PROFILE_NAME_PREFIX = "OS-CL-"
CLIENT_PROFILE_PATH_PREFIX = "/cl-"
SERVICE_PROFILE_PATH_PREFIX = "org-root/ls-"

ETH0 = "eth0"
ETH1 = "eth1"
ETH_PREFIX = "/ether-"
DUPLICATE_EXCEPTION = "object already exists"

SP_TEMPLATE_PARENT_DN = "org-root/ls-"
SP_TEMPLATE_PREFIX = "/ls-"
VNIC_TEMPLATE_PARENT_DN = "org-root/lan-conn-templ-"
VNIC_TEMPLATE_PREFIX = "/lan-conn-templ-"
TRANSPORT = "ethernet"
