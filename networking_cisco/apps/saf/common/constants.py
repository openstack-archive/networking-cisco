# Copyright 2015 Cisco Systems, Inc.
# All Rights Reserved.
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


# RPC message type exchange between server and agent.
VM_INFO = 1000
UPDATE_IP_RULE = 1001
UPLINK_NAME = 1002

DID_LEN = 36

# RPC queue name on agent side.
DFA_AGENT_QUEUE = 'dfa_agent'

# RPC queue name on server side.
DFA_SERVER_QUEUE = 'dfa_server_q'
DFA_EXCHANGE = 'dfa'

RESULT_FAIL = 'FAIL'
RESULT_SUCCESS = 'SUCCESS'
CREATE_FAIL = 'CREATE:FAIL'
DELETE_FAIL = 'DELETE:FAIL'
UPDATE_FAIL = 'UPDATE:FAIL'
SUBNET_PENDING = 'SUBNET:PENDING'

DHCP_PORT_CHECK = 3
DHCP_PREFIX = 'dhcp'
LBAAS_PREFIX = 'lbaas'

MAIN_INTERVAL = 5

# Process queues interval
PROCESS_QUE_INTERVAL = 1

# Failure recovery interval
FAIL_REC_INTERVAL = 60

# Heartbeat interval
HB_INTERVAL = 30

# Segmentation ID reuse after 1 hour
SEG_REUSE_TIMEOUT = 1

# Default Orchestrator ID
ORCHESTRATOR_ID = 'Openstack'

# Special return value for an invalid OVS ofport
INVALID_OFPORT = -1
INVALID_VLAN = -1

MIN_VLAN_TAG = 1
MAX_VLAN_TAG = 4094

VM_MSG_TYPE = 50
UPLINK_MSG_TYPE = 51
VM_BULK_SYNC_MSG_TYPE = 52

UPLINK_DET_INTERVAL = 10
ERR_PROC_INTERVAL = 20
# IF 'down' is seen twice continuously
UPLINK_DOWN_THRES = 3

# Timer to check for the presence of flows
FLOW_CHECK_INTERVAL = 60

Q_UPL_PRIO = 1
Q_VM_PRIO = 2

RES_SEGMENT = "SEGMENT"
RES_VLAN = "VLAN"
RES_IN_SUBNET = 'IN_SUB'
RES_OUT_SUBNET = 'OUT_SUB'

uplink_down_reason = "Uplink went down"
uplink_undiscovered_reason = "Uplink not yet discovered"
port_transition_bond_down_reason = \
    "Physical port became port of bond interface, intermittent down"
port_transition_bond_up_reason = \
    "Physical port became port of bond interface, intermittent up"
bridge_not_cfgd_reason = \
    "Integ or Physical Bridge not created by Openstack. Bridge_list: " \
    "%s Integ Br: %s Ext Br: %s"
veth_not_cfgd_reason = \
    "Integ or Physical Patch/Veth Ports not configured by Openstack. " \
    "Ext Peer: %s Integ Peer: %s"
invalid_uplink_ofport_reason = "Uplink OF port not detected on external bridge"
lldp_ofport_not_detect_reason = \
    "lldp veth port not detected on external bridge"
invalid_peer_ofport_reason = \
    "int or phy peer OF Port not detected on Int or Phy Bridge. " \
    "Phy Peer: %s Int Peer: %s"
evb_cfg_fail_reason = "Unable to cfg EVB"
