# Copyright 2015 Cisco Systems, Inc.
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


# Nexus VLAN and VXLAN reserved segment range
NEXUS_VLAN_RESERVED_MIN = 3968
NEXUS_VLAN_RESERVED_MAX = 4047
NEXUS_VXLAN_MIN = 4096
NEXUS_VXLAN_MAX = 16000000

# Nexus1000V reserved default network profile names
DEFAULT_VLAN_NETWORK_PROFILE_NAME = 'cisco_n1kv_default_vlan_network_profile'
DEFAULT_VXLAN_NETWORK_PROFILE_NAME = 'cisco_n1kv_default_vxlan_network_profile'

# Affix values
VM_NETWORK_PREFIX = 'vmn_'
BRIDGE_DOMAIN_SUFFIX = '_bd'
LOGICAL_NETWORK_SUFFIX = '_log_net'


# VSM response keys
PROPERTIES = 'properties'
ID = 'id'

# Network Profile Types
TYPE_TRUNK = 'trunk'

# Network Profile attributes
ADD_TENANTS = 'add_tenants'
REMOVE_TENANTS = 'remove_tenants'

# VXLAN modes
MODE_NATIVE_VXLAN = 'native_vxlan'
MODE_UNICAST = 'unicast'

# VXLAN strings used in CLI
CLI_SEG_TYPE_OVERLAY = 'overlay'
CLI_VXLAN_MODE_NATIVE = 'native'
CLI_VXLAN_MODE_ENHANCED = 'enhanced'

# Attribute extension identifier
N1KV_PROFILE = 'n1kv:profile'
CISCO_N1KV = 'CISCO_N1KV'
CISCO_N1KV_NET_PROFILE = 'CISCO_N1KV_NET_PROFILE'

# Profile Types
POLICY = 'policy'
NETWORK = 'network'

TENANT_ID_NOT_SET = 'tenant_id_not_set'

NETWORK_PROFILES = 'network_profiles'
NETWORKS = 'networks'
SUBNETS = 'subnets'
PORTS = 'ports'
VMNETWORKS = 'vmnetworks'
BRIDGE_DOMAINS = 'bridge_domains'

#Values for MD5 hashes
MD5_HASHES = 'md5_hashes'
NETWORK_PROFILE_MD5 = 'network_profile_md5'
NETWORK_MD5 = 'network_md5'
SUBNET_MD5 = 'subnet_md5'
PORT_MD5 = 'port_md5'
CONSOLIDATED_MD5 = 'consolidated_md5'

SYNC_START = 'start'
SYNC_END = 'end'
SYNC_NO_CHANGE = 'no-change'
