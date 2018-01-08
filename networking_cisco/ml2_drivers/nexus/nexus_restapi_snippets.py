# Copyright (c) 2017-2017 Cisco Systems, Inc.
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

# This section is organized by N9K CLI commands

# show inventory
PATH_GET_NEXUS_TYPE = 'api/mo/sys/ch.json'

# conf t
#   vlan <a,n-y>
#     state active
PATH_ALL = 'api/mo.json'
BODY_VLAN_ALL_BEG = '{"topSystem": { "children": [ {"bdEntity":'
BODY_VLAN_ALL_BEG += ' { "children": ['
BODY_VLAN_ALL_INCR = '  {"l2BD": {"attributes": {"fabEncap": "vlan-%s",'
BODY_VLAN_ALL_INCR += ' "pcTag": "1", "adminSt": "active"}}}'
BODY_VXLAN_ALL_INCR = '  {"l2BD": {"attributes": {"fabEncap": "vlan-%s",'
BODY_VXLAN_ALL_INCR += ' "pcTag": "1", "adminSt": "active",'
BODY_VXLAN_ALL_INCR += ' "accEncap": "vxlan-%s"}}}'
BODY_VLAN_ALL_CONT = ','
BODY_VLAN_ALL_END = '  ]}}]}}'

# The following was added to make simple Test case results more readible.
BODY_VLAN_ADD_START = (BODY_VLAN_ALL_BEG + BODY_VLAN_ALL_INCR +
BODY_VLAN_ALL_CONT)

BODY_VLAN_ADD_NEXT = BODY_VLAN_ALL_INCR + BODY_VLAN_ALL_CONT

BODY_VLAN_ADD = (BODY_VLAN_ALL_BEG + BODY_VLAN_ALL_INCR +
BODY_VLAN_ALL_CONT + BODY_VLAN_ALL_END)

BODY_VXLAN_ADD = (BODY_VLAN_ALL_BEG + BODY_VXLAN_ALL_INCR +
BODY_VLAN_ALL_CONT + BODY_VLAN_ALL_END)

BODY_PORT_CH_BEG = '{"topSystem": { "children": [ '
BODY_PORT_CH_BEG += ' { "interfaceEntity": { "children": ['
BODY_PORT_CH_BEG += ' { "pcAggrIf": { "attributes": '
BODY_PORT_CH_BEG += '{ "id": "po%s" '
BODY_PORT_CH_END = '} } ] } } ] } }'

BODY_ADD_PORT_CH = BODY_PORT_CH_BEG + ' } } } ] } }, {"vpcEntity": '
BODY_ADD_PORT_CH += '{ "children": [ { "vpcInst": { "children": [ '
BODY_ADD_PORT_CH += '{ "vpcDom": { "children": [ '
BODY_ADD_PORT_CH += '{ "vpcIf": { "attributes": { "id": "%s" }, '
BODY_ADD_PORT_CH += '"children": [ { "vpcRsVpcConf": '
BODY_ADD_PORT_CH += '{ "attributes": { "tDn": "sys/intf/aggr-[po%s]"'
BODY_ADD_PORT_CH += ' } } } ] } }'
BODY_ADD_PORT_CH += '] } } ]' + BODY_PORT_CH_END

# BODY_ADD_PORT_CH_P2 does
# Beneath "int port-channel x" configure
# "spanning-tree port type edge trunk ;no lacp suspend-individual",
BODY_ADD_STP_PORT_CH = '{ "stpEntity": { "children": [ '
BODY_ADD_STP_PORT_CH += ' { "stpInst": { "children": [ '
BODY_ADD_STP_PORT_CH += ' { "stpIf": { "attributes": { '
BODY_ADD_STP_PORT_CH += ' "id": "po%s", "mode": "trunk"'
BODY_ADD_STP_PORT_CH += ' } } } ] } } ] } }'
BODY_ADD_PORT_CH_P2 = BODY_PORT_CH_BEG + ', "ctrl": "graceful-conv"'
BODY_ADD_PORT_CH_P2 += '} } } ] } },'
BODY_ADD_PORT_CH_P2 += BODY_ADD_STP_PORT_CH
BODY_ADD_PORT_CH_P2 += '] } }'

BODY_DEL_PORT_CH = BODY_PORT_CH_BEG + ', "status": "deleted" } '
BODY_DEL_PORT_CH += BODY_PORT_CH_END

BODY_ADD_CH_GRP = BODY_PORT_CH_BEG + ', "isExplicit": "no", '
BODY_ADD_CH_GRP += '"pcMode": "active" },'
BODY_ADD_CH_GRP += '"children": [ { "pcShadowAggrIf": {'
BODY_ADD_CH_GRP += '"attributes": { "id": "po%s" } } }, '
BODY_ADD_CH_GRP += '{ "pcRsMbrIfs": { "attributes": { '
BODY_ADD_CH_GRP += '"isMbrForce": "yes", '
BODY_ADD_CH_GRP += '"tDn": "sys/intf/%s"'
BODY_ADD_CH_GRP += '} } } ] ' + BODY_PORT_CH_END

BODY_DEL_CH_GRP = BODY_PORT_CH_BEG + ' },'
BODY_DEL_CH_GRP += '"children": [ { "pcRsMbrIfs": {'
BODY_DEL_CH_GRP += ' "attributes": { "status": "deleted",'
BODY_DEL_CH_GRP += '"tDn": "sys/intf/%s"'
BODY_DEL_CH_GRP += '} } } ] ' + BODY_PORT_CH_END

# conf t
#   vlan <n>
#     state active
PATH_VLAN = 'api/mo/sys/bd/bd-[vlan-%s].json'
BODY_VLAN_ACTIVE = '{"l2BD": {"attributes": {"adminSt": "active"}}}'

# conf t
#   vlan <n>
#     state active
#     vn-segment <vni>
BODY_VXLAN_ACTIVE = '{"l2BD": {"attributes": {"adminSt": "active",'
BODY_VXLAN_ACTIVE += ' "accEncap": "vxlan-%s"}}}'

# conf t
#   int ethernet x/x  OR int port-channel n
# where %s is "phys-[eth1/19]" OR "aggr-[po50]"
PATH_IF = 'api/mo/sys/intf/%s.json'
# THEN
#      switchport trunk native vlan <vlan>
#      switchport trunk allowed vlan none | add <vlan> | remove <vlan>
# first %s is "l1PhysIf" | "pcAggrIf", 2nd trunkvlan string, 3rd one
# native vlan
BODY_PORT_CH_MODE = '"mode": "trunk",'
BODY_TRUNKVLAN = '{"%s": {"attributes": {%s "trunkVlans": "%s"}}}'
BODY_NATIVE_TRUNKVLAN = '{"%s": {"attributes": {%s "trunkVlans": "%s",'
BODY_NATIVE_TRUNKVLAN += ' "nativeVlan": "%s"}}}'

# conf t
#   feature nv overlay
PATH_VXLAN_STATE = 'api/mo/sys/fm/nvo.json'
# where %s is "enable" | "disable"
BODY_VXLAN_STATE = '{"fmNvo": {"attributes": {"adminSt": "%s"}}}'

# conf t
#   feature vn-segment-vlan-based
PATH_VNSEG_STATE = 'api/mo/sys/fm/vnsegment.json'
BODY_VNSEG_STATE = '{"fmVnSegment": {"attributes": {"adminSt": "%s"}}}'

# conf t
#   int nve%s
#     no shut
#     source-interface loopback %s
PATH_NVE_CREATE = 'api/mo/sys/epId-%s.json'
BODY_NVE_CREATE = '{"nvoEp": {"attributes": {"epId": "%s"}}}'
BODY_NVE_ADD_LOOPBACK = '{"nvoEp": {"attributes": {"adminSt": "%s",'
BODY_NVE_ADD_LOOPBACK += ' "sourceInterface": "lo%s"}}}'

# conf t
#   int nve%s
#     no shut
#     source-interface loopback %s

# conf t
#   int nve%s
#     [no] member vni %s mcast-group %s
PATH_VNI_UPDATE = 'api/mo/sys/epId-%s/nws/vni-%s.json'
BODY_VNI_UPDATE = '{"nvoNw": {"attributes": {"vni": "%s", "vniRangeMin": "%s",'
BODY_VNI_UPDATE += ' "vniRangeMax": "%s", "mcastGroup": "%s", "isMcastRange":'
BODY_VNI_UPDATE += ' "yes", "suppressARP": "no", "associateVrfFlag": "no"}}}'

# channel-group x mode active is not immediately available beneath the
# ethernet interface data.  Instead one needs to gather pc channel members
# and search for ethernet interface.
PATH_GET_PC_MEMBERS = 'api/mo/sys/intf.json?query-target=subtree&'
PATH_GET_PC_MEMBERS += 'target-subtree-class=pcRsMbrIfs'

PATH_USER_CMDS = 'ins'
BODY_USER_CONF_CMDS = '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
BODY_USER_CONF_CMDS += '<ins_api>\n<type>cli_conf</type>\n'
BODY_USER_CONF_CMDS += '<version>1.0</version>\n'
BODY_USER_CONF_CMDS += '<chunk>0</chunk>\n'
BODY_USER_CONF_CMDS += '<sid>%s</sid>\n'
BODY_USER_CONF_CMDS += '<input>%s</input>\n'
BODY_USER_CONF_CMDS += '<output_format>json</output_format>\n'
BODY_USER_CONF_CMDS += '</ins_api>\n'
