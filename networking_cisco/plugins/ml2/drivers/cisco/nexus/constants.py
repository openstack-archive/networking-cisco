# Copyright (c) 2011-2016 Cisco Systems, Inc.
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
#


CREDENTIAL_USERNAME = 'user_name'
CREDENTIAL_PASSWORD = 'password'

USERNAME = 'username'
PASSWORD = 'password'
SSHPORT = 'ssh_port'

NETWORK_ADMIN = 'network_admin'

TYPE_NEXUS_VXLAN = 'nexus_vxlan'

# TODO(rpothier) Add back in provider segment support.
PROVIDER_SEGMENT = 'provider_segment'

NVE_INT_NUM = '1'
NEXUS_MAX_VLAN_NAME_LEN = 32

NO_DUPLICATE = 0
DUPLICATE_VLAN = 1
DUPLICATE_PORT = 2

NEXUS_TYPE_INVALID = -1
NEXUS_3K = 3
NEXUS_5K = 5
NEXUS_7K = 7
NEXUS_9K = 9

MAX_NEXUS_SSH_SESSIONS = 8

REPLAY_FAILURES = '_replay_failures'
FAIL_CONTACT = '_contact'
FAIL_CONFIG = '_config'

RESERVED_NEXUS_SWITCH_DEVICE_ID_R1 = "RESERVED_NEXUS_SWITCH_DEVICE_ID_R1"
RESERVED_NEXUS_PORT_DEVICE_ID_R1 = "RESERVED_NEXUS_PORT_DEVICE_ID_R1"
NO_PORT_ID = "NONE"
NO_VLAN_OR_VNI_ID = '0'
SWITCH_ACTIVE = "ACTIVE"
SWITCH_RESTORE_S1 = "RESTORE_S1"
SWITCH_RESTORE_S2 = "RESTORE_S2"
SWITCH_INACTIVE = "INACTIVE"

CREATE_VLAN_SEND_SIZE = 20
CREATE_VLAN_BATCH = 200
CREATE_PORT_VLAN_LENGTH = 20

NOT_NATIVE = False
