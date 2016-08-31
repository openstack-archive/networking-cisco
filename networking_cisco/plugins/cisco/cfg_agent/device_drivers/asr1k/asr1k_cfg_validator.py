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

import netaddr

from networking_cisco.plugins.cisco.common.htparser import HTParser

from neutron_lib import constants

from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routerrole

import re
import xml.etree.ElementTree as ET


ROUTER_ROLE_ATTR = routerrole.ROUTER_ROLE_ATTR

"""
Compares ASR running-config and neutron DB state, informs caller
if any configuration was missing from running-config.
"""


class ConfigValidator(object):
    def __init__(self, router_db_info, hosting_device_info, conn):
        self.hosting_device_info = hosting_device_info
        self.routers = router_db_info
        self.conn = conn

    def check_running_config(self):
        return self.process_routers_data(self.routers)

    def populate_segment_nat_dict(self, segment_nat_dict, routers):
        hd_id = self.hosting_device_info['id']
        for router in routers:
            if 'hosting_device' not in router:
                continue

            if router['hosting_device']['id'] != hd_id:
                continue

            # Mark which segments have NAT enabled
            # i.e., the segment is present on at least 1 router with
            # both external and internal networks present
            if 'gw_port' in router.keys():
                gw_port = router['gw_port']
                gw_segment_id = gw_port['hosting_info']['segmentation_id']
                if '_interfaces' in router.keys():
                    interfaces = router['_interfaces']
                    for intf in interfaces:
                        if intf['device_owner'] == \
                            constants.DEVICE_OWNER_ROUTER_INTF:
                            intf_segment_id = \
                                intf['hosting_info']['segmentation_id']
                            segment_nat_dict[gw_segment_id] = True
                            segment_nat_dict[intf_segment_id] = True

    def process_routers_data(self, routers):
        hd_id = self.hosting_device_info['id']
        segment_nat_dict = {}
        #conn = self.driver._get_connection() #TODO(init ncclient properly)
        running_cfg = self.get_running_config(self.conn)
        parsed_cfg = HTParser(running_cfg)

        self.populate_segment_nat_dict(segment_nat_dict, routers)

        missing_cfg = []
        for router in routers:
            if 'hosting_device' not in router:
                continue

            if router['hosting_device']['id'] != hd_id:
                continue

            missing_cfg += self.check_router(router,
                                             parsed_cfg,
                                             segment_nat_dict)

        return missing_cfg

    def check_router(self, router, running_config, segment_nat_dict):
        if router[ROUTER_ROLE_ATTR] == cisco_constants.ROUTER_ROLE_GLOBAL:
            missing_cfg = self.check_global_router(router,
                                                   running_config,
                                                   segment_nat_dict)
        else:
            missing_cfg = self.check_tenant_router(router,
                                                   running_config,
                                                   segment_nat_dict)
        return missing_cfg

    def check_tenant_router(self, router, running_config, segment_nat_dict):
        missing_cfg = []
        missing_cfg += self.check_vrf(router, running_config)
        missing_cfg += self.check_nat_pool(router, running_config)
        missing_cfg += self.check_default_route(router, running_config)
        missing_cfg += self.check_acls(router, running_config)
        missing_cfg += self.check_fips(router, running_config)
        missing_cfg += self.check_interfaces(router,
                                             running_config,
                                             segment_nat_dict,
                                             is_external=False)
        return missing_cfg

    def check_global_router(self, router, running_config, segment_nat_dict):
        missing_cfg = []
        missing_cfg += self.check_interfaces(router,
                                             running_config,
                                             segment_nat_dict,
                                             is_external=True)
        return missing_cfg

    def get_running_config(self, conn):
        """Get the CSR's current running config.
        :return: Current IOS running config as multiline string
        """
        config = conn.get_config(source="running")
        if config:
            root = ET.fromstring(config._raw)
            running_config = root[0][0]
            rgx = re.compile("\r*\n+")
            ioscfg = rgx.split(running_config.text)
            return ioscfg

    def get_vrf_name(self, router):
        short_router_id = router['id'][0:6]
        return "nrouter-%s" % short_router_id

    def set_ip_cidr(self, intf):
        port_subnets = intf['subnets']
        subnet = port_subnets[0]
        prefixlen = netaddr.IPNetwork(subnet['cidr']).prefixlen
        intf['ip_cidr'] = "%s/%s" % (intf['fixed_ips'][0]['ip_address'],
                                     prefixlen)

    def get_interface_name_from_hosting_port(self, port):
        """
        generates the underlying subinterface name for a port
        e.g. Port-channel10.200
        """
        vlan = port['hosting_info']['segmentation_id']
        int_prefix = port['hosting_info']['physical_interface']
        return '%s.%s' % (int_prefix, vlan)

    def check_vrf(self, router, running_config):
        missing_cfg = []
        vrf_name = self.get_vrf_name(router)
        vrf_str = "vrf definition %s" % vrf_name
        vrf_substrs = [" address-family ipv4",
                       " address-family ipv6"]
        vrf_cfg = running_config.find_children(vrf_str)
        if not vrf_cfg:
            missing_cfg.append({"cfg": vrf_cfg})
        else:
            for substr in vrf_substrs:
                if substr not in vrf_cfg:
                    missing_cfg.append({"parent": vrf_str,
                                        "cfg": substr})
        return missing_cfg

    def check_nat_pool(self, router, running_config):
        missing_cfg = []

        if 'gw_port' not in router:
            return missing_cfg
        gw_port = router['gw_port']

        vrf_name = self.get_vrf_name(router)
        pool_name = "%s_nat_pool" % (vrf_name)
        pool_info = gw_port['nat_pool_info']
        pool_ip = pool_info['pool_ip']
        pool_net = netaddr.IPNetwork(pool_info['pool_cidr'])
        nat_pool_str = "ip nat pool %s %s %s netmask %s" % (pool_name,
                                                            pool_ip,
                                                            pool_ip,
                                                            pool_net.netmask)

        pool_cfg = running_config.find_lines(nat_pool_str)
        if not pool_cfg:
            missing_cfg.append({"cfg": nat_pool_str})

        if "_interfaces" in router:
            interfaces = router['_interfaces']
            for intf in interfaces:
                segment_id = intf['hosting_info']['segmentation_id']
                acl_name = "neutron_acl_%s" % segment_id

                nat_overload_str = "ip nat inside source list %s" \
                                   " pool %s vrf %s overload"
                nat_overload_str = nat_overload_str % (acl_name,
                                                       pool_name,
                                                       vrf_name)
                overload_cfg = running_config.find_lines(nat_overload_str)
                if not overload_cfg:
                    missing_cfg.append({"cfg": nat_overload_str})

        return missing_cfg

    def check_default_route(self, router, running_config):
        missing_cfg = []

        if 'gw_port' not in router:
            return missing_cfg

        vrf_name = self.get_vrf_name(router)

        gw_port = router['gw_port']
        ext_gw_ip = gw_port['subnets'][0]['gateway_ip']

        intf_name = self.get_interface_name_from_hosting_port(gw_port)

        route_str = "ip route vrf %s 0.0.0.0 0.0.0.0 %s %s" % (vrf_name,
                                                               intf_name,
                                                               ext_gw_ip)

        route_cfg = running_config.find_lines(route_str)
        if not route_cfg:
            missing_cfg.append({"cfg": route_str})

        return missing_cfg

    def check_acls(self, router, running_config):
        missing_cfg = []

        if "_interfaces" not in router:
            return missing_cfg

        interfaces = router["_interfaces"]
        for intf in interfaces:
            segment_id = intf['hosting_info']['segmentation_id']
            acl_name = "neutron_acl_%s" % segment_id
            self.set_ip_cidr(intf)
            internal_cidr = intf['ip_cidr']
            internal_net = netaddr.IPNetwork(internal_cidr).network
            net_mask = netaddr.IPNetwork(internal_cidr).hostmask

            acl_str = "ip access-list standard %s" % acl_name
            permit_str = " permit %s %s" % (internal_net, net_mask)

            acl_cfg = running_config.find_children(acl_str)
            if not acl_cfg:
                missing_cfg.append({"cfg": acl_str})
            else:
                if permit_str not in acl_cfg:
                    missing_cfg.append({"parent": acl_str, "cfg": permit_str})

        return missing_cfg

    def check_fips(self, router, running_config):
        missing_cfg = []

        if "_floatingips" not in router:
            return missing_cfg

        ex_gw_port = router['gw_port']
        vrf_name = self.get_vrf_name(router)

        fips = router["_floatingips"]
        for fip in fips:
            segment_id = ex_gw_port['hosting_info']['segmentation_id']
            hsrp_grp = ex_gw_port['nat_pool_info']['group']

            fip_str = "ip nat inside source static %s %s" \
                      " vrf %s redundancy neutron-hsrp-%s-%s"

            fip_str = fip_str % (fip['fixed_ip_address'],
                                 fip['floating_ip_address'],
                                 vrf_name,
                                 hsrp_grp,
                                 segment_id)

            fip_cfg = running_config.find_lines(fip_str)
            if not fip_cfg:
                missing_cfg.append({"cfg": fip_str})

        return missing_cfg

    def check_interfaces(self, router, running_config,
                         segment_nat_dict, is_external):
        missing_cfg = []

        if "_interfaces" not in router:
            return missing_cfg

        vrf_name = self.get_vrf_name(router)
        priority = router[ha.DETAILS][ha.PRIORITY]

        interfaces = router["_interfaces"]
        for intf in interfaces:
            segment_id = intf['hosting_info']['segmentation_id']
            intf_name = self.get_interface_name_from_hosting_port(intf)

            intf_str = "interface %s" % intf_name

            intf_cfg = running_config.find_children(intf_str)

            if not intf_cfg:
                missing_cfg.append({"cfg": intf_str})
            else:
                self.set_ip_cidr(intf)
                netmask = netaddr.IPNetwork(intf['ip_cidr']).netmask
                hsrp_vip = intf['fixed_ips'][0]['ip_address']
                port_ha_info = intf[ha.HA_INFO]
                hsrp_grp = port_ha_info['group']
                phys_ip = port_ha_info['ha_port']['fixed_ips'][0]['ip_address']

                sub_strs = [" description OPENSTACK_NEUTRON_INTF",
                            " encapsulation dot1Q %s" % segment_id,
                            " ip address %s %s" % (hsrp_vip, netmask),
                            " standby version 2",
                            " standby delay minimum 30 reload 60",
                            " standby %s priority %s" % (hsrp_grp, priority),
                            " standby %s ip %s" % (hsrp_grp, phys_ip),
                            " standby %s timers 1 3" % hsrp_grp]

                if not is_external:
                    sub_strs.append(" vrf forwarding %s" % vrf_name)

                if segment_id in segment_nat_dict:
                    if is_external:
                        sub_strs.append(" ip nat outside")
                    else:
                        sub_strs.append(" ip nat inside")

                for substr in sub_strs:
                    if substr not in intf_cfg:
                        missing_cfg.append({"parent": intf_str,
                                            "cfg": substr})

        return missing_cfg
