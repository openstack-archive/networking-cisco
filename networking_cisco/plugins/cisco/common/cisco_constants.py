# Copyright 2011 Cisco Systems, Inc.  All rights reserved.
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

# Constants related to device manager
# ===================================
# Service type for device manager plugin
DEVICE_MANAGER = "DEVICE_MANAGER"

# RPC topic for device manager
DEVICE_MANAGER_PLUGIN = 'n-devmgr-plugin'


# Type and topic for Cisco cfg agent
# ==================================
AGENT_TYPE_CFG = 'Cisco cfg agent'
AGENT_TYPE_L3_CFG = 'Cisco l3 cfg agent'

# Topic for Cisco configuration agent
CFG_AGENT = 'cisco_cfg_agent'
# Topic for routing service helper in Cisco configuration agent
CFG_AGENT_L3_ROUTING = 'cisco_cfg_agent_l3_routing'

# Device manager and (hosting) devices
# ====================================
# Default name of hosting device template for network nodes
# hosting Linux network namespace-based Neutron routers.
NETWORK_NODE_TEMPLATE = 'NetworkNode_template'

# Statuses of hosting devices
# ===========================
# Active means the hosting device is up, responds to pings and is configurable
HD_ACTIVE = 'ACTIVE'
# Not responding means that hosting device does not respond to pings but has
# not yet been determined to be dead or faulty
HD_NOT_RESPONDING = 'NOT RESPONDING'
# Error means that hosting device has been determined to be faulty, meaning it
# may respond to pings but other symptoms indicate it is faulty
HD_ERROR = 'ERROR'
# Dead means that hosting device has been determined to be dead in that it
# does not respond to pings even given multiple, repeated attempts
HD_DEAD = 'DEAD'


# Routing service
# ==============
# Default name of router type for Neutron routers implemented
# as Linux network namespaces in network nodes.
NAMESPACE_ROUTER_TYPE = 'Namespace_Neutron_router'

# Default name of router type for Neutron routers implemented
# as VRFs inside a CSR1kv VM instance.
CSR1KV_ROUTER_TYPE = 'CSR1kv_router'

# Default name of router type for Neutron routers implemented
# as VRFs inside a ASR1k physical device.
ASR1K_ROUTER_TYPE = 'ASR1k_router'

# Router roles
ROUTER_ROLE_GLOBAL = 'Global'
ROUTER_ROLE_LOGICAL_GLOBAL = 'Logical-Global'
ROUTER_ROLE_HA_REDUNDANCY = 'HA-Redundancy'
ALLOWED_ROUTER_ROLES = [ROUTER_ROLE_GLOBAL, ROUTER_ROLE_LOGICAL_GLOBAL,
                        ROUTER_ROLE_HA_REDUNDANCY]

# Prefix of name given to global routers
ROUTER_ROLE_NAME_PREFIX = ROUTER_ROLE_GLOBAL + '-router'
LOGICAL_ROUTER_ROLE_NAME = ROUTER_ROLE_LOGICAL_GLOBAL + '-router'
# Number of characters of hosting device id added to role name
ROLE_ID_LEN = 17

# The status of a Neutron Router created using the
# Cisco service plugin is one of the following:
# Created but not scheduled nor deployed
ROUTER_PENDING_CREATE = "PENDING_CREATE"
#  Scheduling in progress
ROUTER_SCHEDULING = 'SCHEDULING'
# Backlogged due to unsuccessful scheduling attempt
ROUTER_BACKLOGGED = 'BACKLOGGED'
# Backlogged due to non-ready hosting device (e.g., still booting)
ROUTER_WAITING_HOST = 'AWAITING_HOST'
# Deployed and configured
ROUTER_ACTIVE = "ACTIVE"
# Deletion in progress (by cfg agent)
ROUTER_PENDING_DELETE = "PENDING_DELETE"
# Some db states in flight so all info is not yet available
ROUTER_INFO_INCOMPLETE = "INFO_INCOMPLETE"
# Values for network profile fields
ADD_TENANTS = 'add_tenants'
REMOVE_TENANTS = 'remove_tenants'
