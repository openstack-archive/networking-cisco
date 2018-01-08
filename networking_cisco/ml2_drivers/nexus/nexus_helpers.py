# Copyright (c) 2017 Cisco Systems, Inc.
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

"""
ML2 Nexus Driver - Helper Methods
"""

from networking_cisco import backwards_compatibility as bc


def format_interface_name(intf_type, port, ch_grp=0):
    """Method to format interface name given type, port.

    Given interface type, port, and channel-group, this
    method formats an interface name.  If channel-group is
    non-zero, then port-channel is configured.

    :param intf_type: Such as 'ethernet' or 'port-channel'
    :param port: unique identification -- 1/32 or 1
    :ch_grp: If non-zero, ignore other params and format
             port-channel<ch_grp>
    :returns: the full formatted interface name.
              ex: ethernet:1/32, port-channel:1
    """
    if ch_grp > 0:
        return 'port-channel:%s' % str(ch_grp)

    return '%s:%s' % (intf_type.lower(), port)


def split_interface_name(interface, ch_grp=0):
    """Method to split interface type, id from name.

    Takes an interface name or just interface suffix
    and returns interface type and number separately.

    :param interface: interface name or just suffix
    :param ch_grp: if non-zero, ignore interface
                   name and return 'port-channel' grp
    :returns: interface type like 'ethernet'
    :returns: returns suffix to interface name
    """

    interface = interface.lower()
    if ch_grp != 0:
        intf_type = 'port-channel'
        port = str(ch_grp)
    elif ':' in interface:
        intf_type, port = interface.split(':')
    elif interface.startswith('ethernet'):
        interface = interface.replace(" ", "")
        _, intf_type, port = interface.partition('ethernet')
    elif interface.startswith('port-channel'):
        interface = interface.replace(" ", "")
        _, intf_type, port = interface.partition('port-channel')
    else:
        intf_type, port = 'ethernet', interface

    return intf_type, port


def is_baremetal(port):
    """Identifies ironic baremetal transactions.

    There are two types of transactions.

    1. A host transaction which is dependent on host to interface mapping
       config stored in the ml2_conf.ini file. The VNIC type for this is
       'normal' which is the assumed condition.
    2. A baremetal transaction which comes from the ironic project where the
       interfaces are provided in the port transaction. In this case the
       VNIC_TYPE is 'baremetal'.
    """
    return port[bc.portbindings.VNIC_TYPE] == bc.portbindings.VNIC_BAREMETAL
