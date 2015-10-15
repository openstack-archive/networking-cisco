# Copyright 2014 Cisco Systems, Inc.  All rights reserved.
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

# Constants for the N1kv plugging drivers.

# These cidr defines will go away when Nova allows spinning up
# VMs with vifs on networks without subnet(s).
T1_SUBNET_CIDR = '172.16.0.0/13'
T2_SUBNET_CIDR = '172.24.0.0/13'

# T1 port/network is for VXLAN
T1_PORT_NAME = 't1_p:'
# T2 port/network is for VLAN
T2_PORT_NAME = 't2_p:'
T1_NETWORK_NAME = 't1_net'
T2_NETWORK_NAME = 't2_net'
T1_SUBNET_NAME = 't1_subnet'
T2_SUBNET_NAME = 't2_subnet'
