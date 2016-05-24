# Copyright 2015 Cisco Systems, Inc.  All rights reserved.
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

# ===================================================
# Create Subinterface
# $(config)interface GigabitEthernet 2.500
# $(config)description OPENSTACK_NEUTRON_INTF
# $(config)encapsulation dot1Q 500
# $(config)vrf forwarding nrouter-abc-e7d4y5
# $(config)ip address 192.168.0.1 255.255.255.0
# ===================================================
CREATE_SUBINTERFACE_WITH_ID = """
<config>
        <cli-config-data>
            <cmd>interface %s</cmd>
            <cmd>description OPENSTACK_NEUTRON_INTF</cmd>
            <cmd>encapsulation dot1Q %s</cmd>
            <cmd>vrf forwarding %s</cmd>
            <cmd>ip address %s %s</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Create Subinterface
# $(config)interface GigabitEthernet 2.500
# $(config)description OPENSTACK_NEUTRON_L3FR001_INTF
# $(config)encapsulation dot1Q 500
# $(config)vrf forwarding nrouter-e7d4y5-L3FR001
# $(config)ip address 192.168.0.1 255.255.255.0
# ===================================================
CREATE_SUBINTERFACE_REGION_ID_WITH_ID = """
<config>
        <cli-config-data>
            <cmd>interface %s</cmd>
            <cmd>description OPENSTACK_NEUTRON_%s_INTF</cmd>
            <cmd>encapsulation dot1Q %s</cmd>
            <cmd>vrf forwarding %s</cmd>
            <cmd>ip address %s %s</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Create Subinterface (External. no VRF)
# $(config)interface GigabitEthernet 2.500
# $(config)description OPENSTACK_NEUTRON_L3FR001_INTF
# $(config)encapsulation dot1Q 500
# $(config)ip address 192.168.0.1 255.255.255.0
# ===================================================
CREATE_SUBINTERFACE_EXTERNAL_WITH_ID = """
<config>
        <cli-config-data>
            <cmd>interface %s</cmd>
            <cmd>description OPENSTACK_NEUTRON_EXTERNAL_INTF</cmd>
            <cmd>encapsulation dot1Q %s</cmd>
            <cmd>ip address %s %s</cmd>
        </cli-config-data>
</config>
"""

CREATE_SUBINTERFACE_EXT_REGION_ID_WITH_ID = """
<config>
        <cli-config-data>
            <cmd>interface %s</cmd>
            <cmd>description OPENSTACK_NEUTRON_%s_INTF</cmd>
            <cmd>encapsulation dot1Q %s</cmd>
            <cmd>ip address %s %s</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Enable HSRP on a Subinterface
# $(config)interface GigabitEthernet0/0/0.314
# $(config)vrf forwarding nrouter-e7d4y5
# $(config)standby version 2
# $(config)standby delay minimum 30 reload 60
# $(config)standby 1621 priority 10
# $(config)standby 1621 ip 10.0.3.1
# $(config)standby 1621 timers 1 3
# ===================================================
SET_INTC_ASR_HSRP = """
<config>
        <cli-config-data>
            <cmd>interface %s</cmd>
            <cmd>vrf forwarding %s</cmd>
            <cmd>standby version 2</cmd>
            <cmd>standby delay minimum 30 reload 60</cmd>
            <cmd>standby %s priority %s</cmd>
            <cmd>standby %s ip %s</cmd>
            <cmd>standby %s timers 1 3</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Enable HSRP on a External Network Subinterface
# $(config)interface GigabitEthernet0/0/0.314
# $(config)standby version 2
# $(config)standby delay minimum 30 reload 60
# $(config)standby 1621 priority 10
# $(config)standby 1621 ip 10.0.3.1
# $(config)standby 1621 timers 1 3
# $(config)standby 1621 name neutron-hsrp-1621-314
# ===================================================
SET_INTC_ASR_HSRP_EXTERNAL = """
<config>
        <cli-config-data>
            <cmd>interface %s</cmd>
            <cmd>standby version 2</cmd>
            <cmd>standby delay minimum 30 reload 60</cmd>
            <cmd>standby %s priority %s</cmd>
            <cmd>standby %s ip %s</cmd>
            <cmd>standby %s timers 1 3</cmd>
            <cmd>standby %s name neutron-hsrp-%s-%s</cmd>
        </cli-config-data>
</config>
"""

# ===========================================================================
# Set Static source translation on an interface
# Syntax: ip nat inside source static <fixed_ip> <floating_ip>
# .......vrf <vrf_name> redundancy <hsrp group name>
# eg: $(config)ip nat inside source static 192.168.0.1 121.158.0.5
#    ..........vrf nrouter-e7d4y5 redundancy neutron-hsrp-1621-314
# ==========================================================================
SET_STATIC_SRC_TRL_NO_VRF_MATCH = """
<config>
        <cli-config-data>
            <cmd>ip nat inside source static %s %s vrf %s redundancy neutron-hsrp-%s-%s</cmd> # NOQA
        </cli-config-data>
</config>
"""

# ===========================================================================
# Remove Static source translation on an interface
# Syntax: no ip nat inside source static <fixed_ip> <floating_ip>
# .......vrf <vrf_name> redundancy <hsrp group name>
# eg: $(config)no ip nat inside source static 192.168.0.1 121.158.0.5
#    ..........vrf nrouter-e7d4y5 redundancy neutron-hsrp-1621-314
# ==========================================================================
REMOVE_STATIC_SRC_TRL_NO_VRF_MATCH = """
<config>
        <cli-config-data>
            <cmd>no ip nat inside source static %s %s vrf %s redundancy neutron-hsrp-%s-%s</cmd> # NOQA
        </cli-config-data>
</config>
"""

# =============================================================================
# Set default ip route with interface
# Syntax: ip route vrf <vrf-name> 0.0.0.0 0.0.0.0 <interface> <next hop>
# eg:
# $(config)ip route vrf nrouter-e7d4y5 0.0.0.0  0.0.0.0 po10.304 10.0.100.255
# =============================================================================
# ToDo(Hareesh): Seems unused, remove commented below after testing
# DEFAULT_ROUTE_WITH_INTF_CFG = 'ip route vrf %s 0.0.0.0 0.0.0.0 %s %s'

SET_DEFAULT_ROUTE_WITH_INTF = """
<config>
        <cli-config-data>
            <cmd>ip route vrf %s 0.0.0.0 0.0.0.0 %s %s</cmd>
        </cli-config-data>
</config>
"""

# =============================================================================
# Remove default ip route
# Syntax: ip route vrf <vrf-name> 0.0.0.0 0.0.0.0 <interface> <next hop>
# eg:
#   $(config)ip route vrf nrouter-e7d4y5 0.0.0.0 0.0.0.0 po10.304 10.0.100.255
# =============================================================================
REMOVE_DEFAULT_ROUTE_WITH_INTF = """
<config>
        <cli-config-data>
            <cmd>no ip route vrf %s 0.0.0.0 0.0.0.0 %s %s</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Create VRF definition
# $(config)vrf definition nrouter-e7d4y5
# $(config)address-family ipv4
# $(config)exit-address-family
# $(config)address-family ipv6
# $(config)exit-address-family
# ===================================================
CREATE_VRF_DEFN = """
<config>
        <cli-config-data>
            <cmd>vrf definition %s</cmd>
            <cmd>address-family ipv4</cmd>
            <cmd>exit-address-family</cmd>
            <cmd>address-family ipv6</cmd>
            <cmd>exit-address-family</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Remove VRF definition
# $(config)no vrf definition nrouter-e7d4y5
# ===================================================
REMOVE_VRF_DEFN = """
<config>
        <cli-config-data>
            <cmd>no vrf definition %s</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Create V6 Subinterface (With deployement id)
# $(config)interface GigabitEthernet 2.500
# $(config)description OPENSTACK_NEUTRON-Region_XY_INTF
# $(config)encapsulation dot1Q 500
# $(config)vrf forwarding nrouter-abc-e7d4y5
# $(config)ipv6 address 2001:DB8:CAFE:A::1/64
# ===================================================
CREATE_SUBINTERFACE_V6_WITH_ID = """
<config>
        <cli-config-data>
            <cmd>interface %s</cmd>
            <cmd>description OPENSTACK_NEUTRON-%s_INTF</cmd>
            <cmd>encapsulation dot1Q %s</cmd>
            <cmd>vrf forwarding %s</cmd>
            <cmd>ipv6 address %s</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Create Subinterface (with deployment_id)
# $(config)interface GigabitEthernet 2.500
# $(config)description OPENSTACK_NEUTRON-Region_XY_INTF
# $(config)encapsulation dot1Q 500
# $(config)ipv6 address 2001:DB8:CAFE:A::1/64
# ===================================================
CREATE_SUBINTERFACE_V6_NO_VRF_WITH_ID = """
<config>
        <cli-config-data>
            <cmd>interface %s</cmd>
            <cmd>description OPENSTACK_NEUTRON-%s_INTF</cmd>
            <cmd>encapsulation dot1Q %s</cmd>
            <cmd>ipv6 address %s</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Enable HSRP on a Subinterface
# $(config)interface GigabitEthernet0/0/0.314
# $(config)vrf forwarding nrouter-e7d4y5
# $(config)standby version 2
# $(config)standby 1621 ipv6 autoconfig
# $(config)standby 1621 priority 10
# $(config)standby 1621 preempt
# $(config)standby 1621 timers 1 3
# $(config)standby 1621 name neutron-hsrp-1621-314
# ===================================================
SET_INTC_ASR_HSRP_V6 = """
<config>
        <cli-config-data>
            <cmd>interface %s</cmd>
            <cmd>standby version 2</cmd>
            <cmd>standby %s ipv6 autoconfig</cmd>
            <cmd>standby %s priority %s</cmd>
            <cmd>standby %s preempt</cmd>
            <cmd>standby %s authentication OPEN</cmd>
            <cmd>standby %s timers 1 3</cmd>
            <cmd>standby %s name neutron-hsrp-%s-%s</cmd>
        </cli-config-data>
</config>
"""

# =============================================================================
# Set default ipv6 route with interface
# Syntax: ipv6 route vrf <vrf-name> ::/0 <interface> nexthop-vrf default
# eg:
# $(config)ipv6 route vrf nrouter-e7d4y5 ::/0 po10.304 nexthop-vrf default
# =============================================================================
# ToDo(Hareesh): Seems unused, remove commented below after testing
# DEFAULT_ROUTE_V6_WITH_INTF_CFG = 'ipv6 route vrf %s ::/0 %s %s'

SET_DEFAULT_ROUTE_V6_WITH_INTF = """
<config>
        <cli-config-data>
            <cmd>ipv6 route vrf %s ::/0 %s nexthop-vrf default</cmd>
        </cli-config-data>
</config>
"""

# ============================================================================
# Remove default ipv6 route
# Syntax: no ipv6 route vrf <vrf-name> ::/0 <interface> nexthop-vrf default
# eg:
# $(config)no ipv6 route vrf nrouter-e7d4y5 ::/0 po10.304 nexthop-vrf default
# ============================================================================
REMOVE_DEFAULT_ROUTE_V6_WITH_INTF = """
<config>
        <cli-config-data>
            <cmd>no ipv6 route vrf %s ::/0 %s nexthop-vrf default</cmd>
        </cli-config-data>
</config>
"""

# ===========================================================================
# Set Dynamic source translation with NAT pool
# Syntax: ip nat inside source list <acl_no> pool <pool_name>
#     ....vrf <vrf_name> overload
# eg: $(config)ip nat inside source list acl_500
#    ....pool nrouter-e7d4y5-pool vrf nrouter-e7d4y5 overload
# ==========================================================================
# ToDo(Hareesh): Seems unused, remove commented below after testing
# SNAT_POOL_CFG = "ip nat inside source list %s pool %s vrf %s overload"

SET_DYN_SRC_TRL_POOL = """
<config>
        <cli-config-data>
            <cmd>ip nat inside source list %s pool %s vrf %s overload</cmd>
        </cli-config-data>
</config>
"""

# ===========================================================================
# Remove Dynamic source translation with NAT pool
# Syntax: no ip nat inside source list <acl_no> pool <pool_name>
#     ...vrf <vrf_name> overload
# eg: $(config)no ip nat inside source list acl_500
#    ..........pool nrouter-e7d4y5-pool vrf nrouter-e7d4y5 overload
# ==========================================================================
REMOVE_DYN_SRC_TRL_POOL = """
<config>
        <cli-config-data>
            <cmd>no ip nat inside source list %s pool %s vrf %s overload</cmd>
        </cli-config-data>
</config>
"""

# ===========================================================================
# Create a NAT pool
# Syntax: ip nat pool <pool_name> <start_ip> <end_ip> netmask <netmask_value>
# eg:
# $(config)ip nat pool TEST_POOL 192.168.0.20 192.168.0.35 netmask 255.255.0.0
# ==========================================================================
CREATE_NAT_POOL = """
<config>
        <cli-config-data>
            <cmd>ip nat pool %s %s %s netmask %s</cmd>
        </cli-config-data>
</config>
"""

# ===========================================================================
# Delete a NAT pool
# Syntax:no ip nat pool <pool_name> <start_ip> <end_ip> netmask <netmask_value>
# eg:
# $(config)no ip nat pool TEST_POOL 192.168.0.20 192.168.0.35
# .........netmask 255.255.0.0
# ==========================================================================
DELETE_NAT_POOL = """
<config>
        <cli-config-data>
            <cmd>no ip nat pool %s %s %s netmask %s</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Disable HSRP preempt on an interface
# $(config)interface GigabitEthernet 2.500
# $(config)no standby 1621 preempt
# ===================================================
REMOVE_INTC_ASR_HSRP_PREEMPT = """
<config>
        <cli-config-data>
            <cmd>interface %s</cmd>
            <cmd>no standby %s preempt</cmd>
        </cli-config-data>
</config>
"""

# ===================================================
# Empty snippet (for polling netconf session status)
# ===================================================
EMPTY_SNIPPET = """
<config>
        <cli-config-data>
            <cmd>do cd</cmd>
        </cli-config-data>
</config>
"""
