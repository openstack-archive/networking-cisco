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
import pprint as pp
import re
import six
import xml.etree.ElementTree as ET

from oslo_config import cfg
from oslo_log import log as logging

from neutron_lib import constants

from networking_cisco._i18n import _LI

from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_snippets as asr_snippets)
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.common.htparser import HTParser
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routerrole

LOG = logging.getLogger(__name__)


ROUTER_ROLE_ATTR = routerrole.ROUTER_ROLE_ATTR

NROUTER_REGEX = "nrouter-(\w{6,6})"
NROUTER_MULTI_REGION_REGEX = "nrouter-(\w{6,6})-(\w{1,7})"

VRF_REGEX = "ip vrf " + NROUTER_REGEX
VRF_REGEX_NEW = "vrf definition " + NROUTER_REGEX

VRF_MULTI_REGION_REGEX = "ip vrf " + NROUTER_MULTI_REGION_REGEX
VRF_MULTI_REGION_REGEX_NEW = "vrf definition " + NROUTER_MULTI_REGION_REGEX

#INTF_NAME_REGEX = "(PortChannel\d+|\d+Ethernet\d+\/d+\/d+)"

INTF_REGEX = "interface \S+\.(\d+)"
INTF_DESC_REGEX = "\s*description OPENSTACK_NEUTRON_INTF"
INTF_DESC_MULTI_REGION_REGEX = ("\s*description"
    " OPENSTACK_NEUTRON_(\w{1,7})_INTF")
VRF_EXT_INTF_REGEX = "\s*ip vrf forwarding .*"
VRF_INTF_REGEX = "\s*ip vrf forwarding " + NROUTER_REGEX
VRF_INTF_MULTI_REGION_REGEX = ("\s*ip vrf forwarding " +
    NROUTER_MULTI_REGION_REGEX)
VRF_EXT_INTF_REGEX_NEW = "\s*vrf forwarding .*"
VRF_INTF_REGEX_NEW = "\s*vrf forwarding " + NROUTER_REGEX
VRF_INTF_MULTI_REGION_REGEX_NEW = ("\s*vrf forwarding " +
    NROUTER_MULTI_REGION_REGEX)
DOT1Q_REGEX = "\s*encapsulation dot1Q (\d+)"
INTF_NAT_REGEX = "\s*ip nat (inside|outside)"
HSRP_REGEX = "\s*standby (\d+) .*"

INTF_V4_ADDR_REGEX = ("\s*ip address (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
HSRP_V4_VIP_REGEX = "\s*standby (\d+) ip (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"

SNAT_REGEX = ("ip nat inside source static"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) vrf " +
    NROUTER_REGEX +
    " redundancy neutron-hsrp-(\d+)-(\d+)")

SNAT_MULTI_REGION_REGEX = ("ip nat inside source static"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    " vrf " + NROUTER_MULTI_REGION_REGEX +
    " redundancy neutron-hsrp-(\d+)-(\d+)")

SNAT_REGEX_OLD = ("ip nat inside source static"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) vrf " +
    NROUTER_REGEX +
    " redundancy neutron-hsrp-grp-(\d+)-(\d+)")

SNAT_MULTI_REGION_REGEX_OLD = ("ip nat inside source static"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) vrf " +
    NROUTER_MULTI_REGION_REGEX +
    " redundancy neutron-hsrp-grp-(\d+)-(\d+)")

NAT_POOL_REGEX = ("ip nat pool " +
    NROUTER_REGEX +
    "_nat_pool (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) netmask"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
NAT_POOL_MULTI_REGION_REGEX = ("ip nat pool " + NROUTER_MULTI_REGION_REGEX +
    "_nat_pool (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) netmask"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")

NAT_OVERLOAD_REGEX = ("ip nat inside source list neutron_acl_(\d+)"
    " interface \S+\.(\d+) vrf " +
    NROUTER_REGEX +
    " overload")
NAT_OVERLOAD_MULTI_REGION_REGEX = ("ip nat inside source list"
    " neutron_acl_(\d+) interface \S+\.(\d+) vrf " +
    NROUTER_MULTI_REGION_REGEX + " overload")

NAT_POOL_OVERLOAD_REGEX = ("ip nat inside source list"
    " neutron_acl_(\d+)_(\w{1,8}) pool " +
    NROUTER_REGEX +
    "_nat_pool vrf " +
    NROUTER_REGEX +
    " overload")
NAT_POOL_OVERLOAD_MULTI_REGION_REGEX = ("ip nat inside source"
    " list neutron_acl_(\w{1,7})_(\d+)_(\w{1,8}) pool " +
    NROUTER_MULTI_REGION_REGEX +
    "_nat_pool vrf " +
    NROUTER_MULTI_REGION_REGEX +
    " overload")

ACL_REGEX = "ip access-list standard neutron_acl_(\d+)_(\w{1,8})"
ACL_MULTI_REGION_REGEX = ("ip access-list standard neutron_acl_" +
                          "(\w{1,7})_(\d+)_(\w{1,8})")
ACL_CHILD_REGEX = ("\s*permit (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")

DEFAULT_ROUTE_REGEX = ("ip route vrf " +
    NROUTER_REGEX + " 0\.0\.0\.0 0\.0\.0\.0 \S+\.(\d+)"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
DEFAULT_ROUTE_MULTI_REGION_REGEX = ("ip route vrf " +
    NROUTER_MULTI_REGION_REGEX +
    " 0\.0\.0\.0 0\.0\.0\.0 \S+\.(\d+)"
    " (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")

DEFAULT_ROUTE_V6_REGEX_BASE = ("ipv6 route vrf " +
    NROUTER_REGEX +
    " ::/0 %s\.(\d+) ([0-9A-Fa-f:]+) nexthop-vrf default")
DEFAULT_ROUTE_V6_MULTI_REGION_REGEX_BASE = ("ipv6 route vrf " +
    NROUTER_MULTI_REGION_REGEX +
    " ::/0 %s\.(\d+) ([0-9A-Fa-f:]+) nexthop-vrf default")

TENANT_ROUTE_V6_REGEX_BASE = ("ipv6 route ([0-9A-Fa-f:/]+)"
    " %s.(\d+) nexthop-vrf " +
    NROUTER_REGEX)
TENANT_ROUTE_V6_MULTI_REGION_REGEX_BASE = ("ipv6 route ([0-9A-Fa-f:/]+)"
    " %s.(\d+) nexthop-vrf " +
    NROUTER_MULTI_REGION_REGEX)

INTF_V6_ADDR_REGEX = "\s*ipv6 address ([0-9A-Fa-f:]+)\/(\d+)"


XML_FREEFORM_SNIPPET = "<config><cli-config-data>%s</cli-config-data></config>"
XML_CMD_TAG = "<cmd>%s</cmd>"


def is_port_v6(port):
    prefix = port['subnets'][0]['cidr']
    if netaddr.IPNetwork(prefix).version == 6:
        return True
    else:
        return False


class ConfigSyncer(object):

    def __init__(self, router_db_info, driver,
                 hosting_device_info, test_mode=False):
        self.existing_cfg_dict = {}
        self.driver = driver
        self.hosting_device_info = hosting_device_info
        self.existing_cfg_dict['interfaces'] = {}
        self.existing_cfg_dict['dyn_nat'] = {}
        self.existing_cfg_dict['static_nat'] = {}
        self.existing_cfg_dict['acls'] = {}
        self.existing_cfg_dict['routes'] = {}
        self.existing_cfg_dict['pools'] = {}

        self.segment_gw_dict = {}

        router_id_dict, interface_segment_dict, segment_nat_dict = \
            self.process_routers_data(router_db_info)
        self.router_id_dict = router_id_dict
        self.intf_segment_dict = interface_segment_dict
        self.segment_nat_dict = segment_nat_dict
        self.test_mode = test_mode
        if (cfg.CONF.multi_region.enable_multi_region):
            self.route_regex = DEFAULT_ROUTE_MULTI_REGION_REGEX
        else:
            self.route_regex = DEFAULT_ROUTE_REGEX

    def process_routers_data(self, routers):
        hd_id = self.hosting_device_info['id']
        router_id_dict = {}
        interface_segment_dict = {}
        segment_nat_dict = {}

        for router in routers:
            if 'hosting_device' not in router:
                continue

            if router['hosting_device']['id'] != hd_id:
                continue

            short_router_id = router['id'][0:6]
            router_id_dict[short_router_id] = router

            interfaces = []
            if '_interfaces' in router.keys():
                interfaces += router['_interfaces']

            # Orgnize interfaces, indexed by segment_id
            for interface in interfaces:
                hosting_info = interface['hosting_info']
                segment_id = hosting_info['segmentation_id']
                if segment_id not in interface_segment_dict:
                    interface_segment_dict[segment_id] = []
                    if segment_id not in segment_nat_dict:
                        segment_nat_dict[segment_id] = False
                interface['is_external'] = (
                    router[ROUTER_ROLE_ATTR] ==
                    cisco_constants.ROUTER_ROLE_GLOBAL)
                interface_segment_dict[segment_id].append(interface)

            # Mark which segments have NAT enabled
            # i.e., the segment is present on at least 1 router with
            # both external and internal networks present
            if 'gw_port' in router.keys():
                gw_port = router['gw_port']
                gw_segment_id = gw_port['hosting_info']['segmentation_id']

                if (router[ROUTER_ROLE_ATTR] ==
                    cisco_constants.ROUTER_ROLE_GLOBAL):

                    if (gw_segment_id not in self.segment_gw_dict):
                        self.segment_gw_dict[gw_segment_id] = gw_port

                if '_interfaces' in router.keys():
                    interfaces = router['_interfaces']
                    for intf in interfaces:
                        if intf['device_owner'] == \
                            constants.DEVICE_OWNER_ROUTER_INTF:
                            if is_port_v6(intf) is not True:
                                intf_segment_id = \
                                    intf['hosting_info']['segmentation_id']
                                segment_nat_dict[gw_segment_id] = True
                                segment_nat_dict[intf_segment_id] = True

        return router_id_dict, interface_segment_dict, segment_nat_dict

    def delete_invalid_cfg(self, conn=None):
        router_id_dict = self.router_id_dict
        intf_segment_dict = self.intf_segment_dict
        segment_nat_dict = self.segment_nat_dict

        if not conn:
            conn = self.driver._get_connection()

        LOG.info(_LI("neutron router db records"))

        for router_id, router in six.iteritems(router_id_dict):
            #LOG.info("ROUTER ID: %s   DATA: %s\n\n" % (router_id, router))
            LOG.info(_LI("ROUTER_ID: %s"), router_id)

        LOG.info(_LI("\n"))

        for segment_id, intf_list in six.iteritems(intf_segment_dict):
            LOG.info(_LI("SEGMENT_ID: %s"), (segment_id))
            for intf in intf_list:
                dev_owner = intf['device_owner']
                dev_id = intf['device_id'][0:6]
                ip_addr = intf['fixed_ips'][0]['ip_address']
                intf_info = "    INTF: %s, %s, %s" % \
                            (ip_addr, dev_id, dev_owner)
                LOG.info(intf_info)

        running_cfg = self.get_running_config(conn)
        parsed_cfg = HTParser(running_cfg)

        invalid_cfg = []

        invalid_cfg += self.clean_snat(conn,
                                       router_id_dict,
                                       intf_segment_dict,
                                       segment_nat_dict,
                                       parsed_cfg)

        invalid_cfg += self.clean_nat_pool_overload(conn,
                                                    router_id_dict,
                                                    intf_segment_dict,
                                                    segment_nat_dict,
                                                    parsed_cfg)

        invalid_cfg += self.clean_nat_pool(conn,
                                           router_id_dict,
                                           intf_segment_dict,
                                           segment_nat_dict,
                                           parsed_cfg)

        invalid_cfg += self.clean_routes(conn,
                                         router_id_dict,
                                         intf_segment_dict,
                                         segment_nat_dict,
                                         parsed_cfg,
                                         self.route_regex)
        invalid_cfg += self.clean_acls(conn,
                                       intf_segment_dict,
                                       segment_nat_dict,
                                       parsed_cfg)

        invalid_cfg += self.clean_interfaces(conn,
                                             intf_segment_dict,
                                             segment_nat_dict,
                                             parsed_cfg)

        invalid_cfg += self.clean_vrfs(conn, router_id_dict, parsed_cfg)
        LOG.debug("invalid_cfg = %s " % (pp.pformat(invalid_cfg)))
        return invalid_cfg

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

    def get_ostk_router_ids(self, router_id_dict):
        ostk_router_ids = []
        for router_id, router in six.iteritems(router_id_dict):
            ostk_router_ids.append(router_id)
        return ostk_router_ids

    def get_running_config_router_ids(self, parsed_cfg):
        rconf_ids = []
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region

        if (is_multi_region_enabled):
            vrf_regex_new = VRF_MULTI_REGION_REGEX_NEW
        else:
            vrf_regex_new = VRF_REGEX_NEW

        for parsed_obj in parsed_cfg.find_objects(vrf_regex_new):
            LOG.info(_LI("VRF object: %s"), (str(parsed_obj)))
            match_obj = re.match(vrf_regex_new, parsed_obj.text)
            router_id = match_obj.group(1)
            LOG.info(_LI("    First 6 digits of router ID: %s\n"),
                        (router_id))
            if (is_multi_region_enabled):
                region_id = match_obj.group(2)
                LOG.info(_LI("    region ID: %s\n"),
                            (region_id))
                my_region_id = cfg.CONF.multi_region.region_id
                if (my_region_id == region_id):
                    rconf_ids.append(router_id)
            else:
                rconf_ids.append(router_id)

        return rconf_ids

    def clean_vrfs(self, conn, router_id_dict, parsed_cfg):
        ostk_router_ids = self.get_ostk_router_ids(router_id_dict)
        rconf_ids = self.get_running_config_router_ids(parsed_cfg)

        source_set = set(ostk_router_ids)
        dest_set = set(rconf_ids)

        # add_set = source_set.difference(dest_set)
        del_set = dest_set.difference(source_set)

        LOG.info(_LI("VRF DB set: %s"), (source_set))
        LOG.info(_LI("VRFs to delete: %s"), (del_set))
        # LOG.info("VRFs to add: %s" % (add_set))

        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        invalid_vrfs = []
        for router_id in del_set:
            if (is_multi_region_enabled):
                my_region_id = cfg.CONF.multi_region.region_id
                invalid_vrfs.append("nrouter-%s-%s" % (router_id,
                                                       my_region_id))
            else:
                invalid_vrfs.append("nrouter-%s" % (router_id))

        if not self.test_mode:
            for vrf_name in invalid_vrfs:
                confstr = asr_snippets.REMOVE_VRF_DEFN % vrf_name
                conn.edit_config(target='running', config=confstr)

        LOG.debug("invalid_vrfs = %s" % (pp.pformat(invalid_vrfs)))
        return invalid_vrfs

    def get_single_cfg(self, cfg_line):
        if len(cfg_line) != 1:
            return None
        else:
            return cfg_line[0]

    def clean_nat_pool(self,
                       conn,
                       router_id_dict,
                       intf_segment_dict,
                       segment_nat_dict,
                       parsed_cfg):
        delete_pool_list = []

        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        if (is_multi_region_enabled):
            nat_pool_regex = NAT_POOL_MULTI_REGION_REGEX
        else:
            nat_pool_regex = NAT_POOL_REGEX

        pools = parsed_cfg.find_objects(nat_pool_regex)
        for pool in pools:
            LOG.info(_LI("\nNAT pool: %s"), (pool))
            match_obj = re.match(nat_pool_regex, pool.text)
            if (is_multi_region_enabled):
                router_id, region_id, start_ip, end_ip, netmask = (
                    match_obj.group(1, 2, 3, 4, 5))
                my_region_id = cfg.CONF.multi_region.region_id
                other_region_ids = cfg.CONF.multi_region.other_region_ids
                if region_id != my_region_id:
                    if region_id not in other_region_ids:
                        delete_pool_list.append(pool.text)
                    else:
                        # skip because some other deployment owns
                        # this configuration
                        continue
            else:
                router_id, start_ip, end_ip, netmask = (
                    match_obj.group(1, 2, 3, 4))

            # Check that VRF exists in openstack DB info
            if router_id not in router_id_dict:
                LOG.info(_LI("router not found for NAT pool, deleting"))
                delete_pool_list.append(pool.text)
                continue

            # Check that router has external network
            router = router_id_dict[router_id]
            if "gw_port" not in router:
                LOG.info(_LI("router has no gw_port, pool is invalid,"
                             " deleting"))
                delete_pool_list.append(pool.text)
                continue

            # Check IPs and netmask
            # TODO(sridar) rework this to old model, further
            # investigation needed and cleanup.
            # pool_info = router['gw_port']['nat_pool_info']
            # pool_ip = pool_info['pool_ip']
            # pool_net = netaddr.IPNetwork(pool_info['pool_cidr'])
            pool_ip = str(router['gw_port']['fixed_ips'][0]['ip_address'])
            # pool_net = router['gw_port']['subnets'][0]['cidr']
            pool_net = netaddr.IPNetwork(
                router['gw_port']['subnets'][0]['cidr'])

            if start_ip != pool_ip:
                LOG.info(_LI("start IP %(start_ip)s for "
                             "pool does not match %(pool_ip)s, deleting") %
                         {'start_ip': start_ip, 'pool_ip': pool_ip})
                delete_pool_list.append(pool.text)
                continue

            if end_ip != pool_ip:
                LOG.info(_LI("end IP for pool does not match, deleting"))
                delete_pool_list.append(pool.text)
                continue

            if netmask != str(pool_net.netmask):
                LOG.info(
                    _LI("netmask for pool does not match, netmask:%(netmask)s,"
                      " pool_netmask:%(pool_netmask)s, deleting") %
                      {'netmask': netmask, 'pool_netmask': pool_net.netmask})
                delete_pool_list.append(pool.text)
                continue

            self.existing_cfg_dict['pools'][pool_ip] = pool

        if not self.test_mode:
            for pool_cfg in delete_pool_list:
                del_cmd = XML_CMD_TAG % ("no %s" % (pool_cfg))
                confstr = XML_FREEFORM_SNIPPET % (del_cmd)
                LOG.info(_LI("Delete pool: %s"), del_cmd)
                conn.edit_config(target='running', config=confstr)
        LOG.debug("delete_pool_list = %s " % (pp.pformat(delete_pool_list)))
        return delete_pool_list

    def clean_routes(self,
                     conn,
                     router_id_dict,
                     intf_segment_dict,
                     segment_nat_dict,
                     parsed_cfg,
                     route_regex):
        delete_route_list = []
        routes = parsed_cfg.find_objects(route_regex)
        for route in routes:
            LOG.info(_LI("\ndefault route: %s"), (route))
            match_obj = re.match(route_regex, route.text)
            is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
            if (is_multi_region_enabled):
                router_id, region_id, segment_id, next_hop = (
                    match_obj.group(1, 2, 3, 4))
                LOG.info(_LI("    router_id: %(router_id)s,"
                             ", region_id: %(region_id)s, segment_id:"
                             " %(segment_id)s, next_hop: %(next_hop)s") %
                         {'router_id': router_id,
                          'region_id': region_id,
                          'segment_id': segment_id,
                          'next_hop': next_hop})
                my_region_id = cfg.CONF.multi_region.region_id
                other_region_ids = cfg.CONF.multi_region.other_region_ids
                if region_id != my_region_id:
                    if region_id not in other_region_ids:
                        delete_route_list.append(route.text)
                    else:
                        # skip because some other deployment owns
                        # this configuration
                        continue
            else:
                router_id, segment_id, next_hop = (
                    match_obj.group(1, 2, 3))

            LOG.info(_LI("    router_id: %(router_id)s, segment_id:"
                         " %(segment_id)s, next_hop: %(next_hop)s") %
                     {'router_id': router_id,
                      'segment_id': segment_id,
                      'next_hop': next_hop})

            # Check that VRF exists in openstack DB info
            if router_id not in router_id_dict:
                LOG.info(_LI("router not found for route, deleting"))
                delete_route_list.append(route.text)
                continue

            # Check that router has external network and segment_id matches
            router = router_id_dict[router_id]
            if "gw_port" not in router:
                LOG.info(_LI("router has no gw_port, route is invalid,"
                             " deleting"))
                delete_route_list.append(route.text)
                continue

            gw_port = router['gw_port']
            gw_segment_id = gw_port['hosting_info']['segmentation_id']
            if int(segment_id) != gw_segment_id:
                LOG.info(_LI("route segment_id does not match router's gw"
                         " segment_id, deleting"))
                delete_route_list.append(route.text)
                continue

            # Check that nexthop matches gw_ip of external network
            gw_ip = gw_port['subnets'][0]['gateway_ip']
            if next_hop.lower() != gw_ip.lower():
                LOG.info(_LI("route has incorrect next-hop, deleting"))
                delete_route_list.append(route.text)
                continue

            self.existing_cfg_dict['routes'][router_id] = route

        if not self.test_mode:
            for route_cfg in delete_route_list:
                del_cmd = XML_CMD_TAG % ("no %s" % (route_cfg))
                confstr = XML_FREEFORM_SNIPPET % (del_cmd)
                LOG.info(_LI("Delete default route: %(del_cmd)s") %
                         {'del_cmd': del_cmd})
                conn.edit_config(target='running', config=confstr)

        LOG.debug("delete_route_list = %s " % (pp.pformat(delete_route_list)))
        return delete_route_list

    def clean_snat(self, conn, router_id_dict,
                   intf_segment_dict, segment_nat_dict, parsed_cfg):
        delete_fip_list = []
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        if (is_multi_region_enabled):
            snat_regex_old = SNAT_MULTI_REGION_REGEX_OLD
            snat_regex = SNAT_MULTI_REGION_REGEX
        else:
            snat_regex_old = SNAT_REGEX_OLD
            snat_regex = SNAT_REGEX

        # Delete any entries with old style 'hsrp-grp-x-y' grp name
        floating_ip_old_rules = parsed_cfg.find_objects(snat_regex_old)
        for snat_rule in floating_ip_old_rules:
            LOG.info(_LI("\n Rule is old format, deleting: %(snat_rule)s") %
                     {'snat_rule': snat_rule.text})

            delete_fip_list.append(snat_rule.text)

        floating_ip_nats = parsed_cfg.find_objects(snat_regex)
        for snat_rule in floating_ip_nats:
            LOG.info(_LI("\nstatic nat rule: %(snat_rule)s") %
                     {'snat_rule': snat_rule})
            match_obj = re.match(snat_regex, snat_rule.text)
            if is_multi_region_enabled:
                (inner_ip, outer_ip, router_id, region_id,
                    hsrp_num, segment_id) = match_obj.group(1, 2, 3, 4, 5, 6)
                my_region_id = cfg.CONF.multi_region.region_id
                other_region_ids = cfg.CONF.multi_region.other_region_ids
                if region_id != my_region_id:
                    if region_id not in other_region_ids:
                        delete_fip_list.append(snat_rule.text)
                    else:
                        # skip because some other deployment owns
                        # this configuration
                        continue
            else:
                inner_ip, outer_ip, router_id, hsrp_num, segment_id = (
                    match_obj.group(1, 2, 3, 4, 5))

            segment_id = int(segment_id)
            hsrp_num = int(hsrp_num)

            LOG.info(_LI("   in_ip: %(inner_ip)s, out_ip: %(outer_ip)s, "
                         "router_id: %(router_id)s, hsrp_num: %(hsrp_num)s,"
                         " segment_id: %(segment_id)s") %
                     {'inner_ip': inner_ip,
                      'outer_ip': outer_ip,
                      'router_id': router_id,
                      'hsrp_num': hsrp_num,
                      'segment_id': segment_id})

            # Check that VRF exists in openstack DB info
            if router_id not in router_id_dict:
                LOG.info(_LI("router not found for rule, deleting"))
                delete_fip_list.append(snat_rule.text)
                continue

            # Check that router has external network and segment_id matches
            router = router_id_dict[router_id]
            if "gw_port" not in router:
                LOG.info(_LI("router has no gw_port,"
                             " snat is invalid, deleting"))
                delete_fip_list.append(snat_rule.text)
                continue

            # Check that hsrp group name is correct
            gw_port = router['gw_port']
            #gw_net_id = gw_port['network_id']
            #gw_hsrp_num = self._get_hsrp_grp_num_from_net_id(gw_net_id)
            gw_hsrp_num = int(gw_port[ha.HA_INFO]['group'])
            gw_segment_id = int(gw_port['hosting_info']['segmentation_id'])
            if segment_id != gw_segment_id:
                LOG.info(_LI("snat segment_id does not match router's"
                         " gw segment_id, deleting"))
                delete_fip_list.append(snat_rule.text)
                continue

            if hsrp_num != gw_hsrp_num:
                LOG.info(_LI("snat hsrp group does not match router gateway's"
                         " hsrp group, deleting"))
                delete_fip_list.append(snat_rule.text)
                continue

            # Check that in,out ip pair matches a floating_ip defined on router
            if '_floatingips' not in router:
                LOG.info(_LI("Router has no floating IPs defined,"
                         " snat rule is invalid, deleting"))
                delete_fip_list.append(snat_rule.text)
                continue

            fip_match_found = False
            for floating_ip in router['_floatingips']:
                if inner_ip == floating_ip['fixed_ip_address'] and \
                   outer_ip == floating_ip['floating_ip_address']:
                    fip_match_found = True
                    break
            if fip_match_found is False:
                LOG.info(_LI("snat rule does not match defined floating IPs,"
                         " deleting"))
                delete_fip_list.append(snat_rule.text)
                continue

            self.existing_cfg_dict['static_nat'][outer_ip] = snat_rule

        if not self.test_mode:
            for fip_cfg in delete_fip_list:
                del_cmd = XML_CMD_TAG % ("no %s" % (fip_cfg))
                confstr = XML_FREEFORM_SNIPPET % (del_cmd)
                LOG.info(_LI("Delete SNAT: %(del_cmd)s") %
                         {'del_cmd': del_cmd})
                conn.edit_config(target='running', config=confstr)

        LOG.debug("delete_fip_list = %s " % (pp.pformat(delete_fip_list)))
        return delete_fip_list

    def clean_nat_pool_overload(self,
                                conn,
                                router_id_dict,
                                intf_segment_dict,
                                segment_nat_dict,
                                parsed_cfg):
        delete_nat_list = []

        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        if (is_multi_region_enabled):
            nat_pool_overload_regex = NAT_POOL_OVERLOAD_MULTI_REGION_REGEX
        else:
            nat_pool_overload_regex = NAT_POOL_OVERLOAD_REGEX

        nat_overloads = parsed_cfg.find_objects(nat_pool_overload_regex)
        for nat_rule in nat_overloads:
            LOG.info(_LI("\nnat overload rule: %(nat_rule)s") %
                     {'nat_rule': nat_rule})
            match_obj = re.match(nat_pool_overload_regex, nat_rule.text)
            if is_multi_region_enabled:
                (region_id, segment_id, port_id,
                 pool_router_id, pool_region_id, router_id) = (
                    match_obj.group(1, 2, 3, 4, 5, 6))
                if (region_id != pool_region_id):
                    LOG.info(_LI("region id mismatch, deleting"))
                    delete_nat_list.append(nat_rule.text)
                    continue

                my_region_id = cfg.CONF.multi_region.region_id
                other_region_ids = cfg.CONF.multi_region.other_region_ids
                if (region_id != my_region_id):
                    if region_id not in other_region_ids:
                        delete_nat_list.append(nat_rule.text)
                    else:
                        # skip because some other deployment owns
                        # this configuration
                        continue
            else:
                segment_id, pool_router_id, router_id = (
                    match_obj.group(1, 2, 3))
                segment_id, port_id, pool_router_id, router_id = (
                    match_obj.group(1, 2, 3, 4))

            segment_id = int(segment_id)

            # Check that VRF exists in openstack DB info
            if router_id not in router_id_dict:
                LOG.info(_LI("router not found for rule, deleting"))
                delete_nat_list.append(nat_rule.text)
                continue

            # Check that correct pool is specified
            if pool_router_id != router_id:
                LOG.info(_LI("Pool and VRF name mismatch, deleting"))
                delete_nat_list.append(nat_rule.text)
                continue

            # Check that router has external network
            router = router_id_dict[router_id]
            if "gw_port" not in router:
                LOG.info(_LI("router has no gw_port,"
                         " nat overload is invalid, deleting"))
                delete_nat_list.append(nat_rule.text)
                continue

            # Check that router has internal network interface on segment_id
            intf_match_found = False
            if '_interfaces' in router:
                for intf in router['_interfaces']:
                    if intf['device_owner'] == \
                        constants.DEVICE_OWNER_ROUTER_INTF:

                        intf_segment_id = \
                            int(intf['hosting_info']['segmentation_id'])
                        if intf_segment_id == segment_id:
                            intf_match_found = True
                            break

            if intf_match_found is False:
                LOG.info(_LI("router does not have this internal network"
                         " assigned, deleting rule"))
                delete_nat_list.append(nat_rule.text)
                continue

            self.existing_cfg_dict['dyn_nat'][segment_id] = nat_rule

        if not self.test_mode:
            for nat_cfg in delete_nat_list:
                del_cmd = XML_CMD_TAG % ("no %s" % (nat_cfg))
                confstr = XML_FREEFORM_SNIPPET % (del_cmd)
                LOG.info(_LI("Delete NAT overload: %(del_cmd)s") %
                         {'del_cmd': del_cmd})
                conn.edit_config(target='running', config=confstr)

        LOG.debug("delete_nat_list = %s " % (pp.pformat(delete_nat_list)))
        return delete_nat_list

    def check_acl_permit_rules_valid(self, segment_id, acl, intf_segment_dict):
        permit_rules = acl.re_search_children(ACL_CHILD_REGEX)
        for permit_rule in permit_rules:
            LOG.info(_LI("   permit rule: %(permit_rule)s") %
                     {'permit_rule': permit_rule})
            match_obj = re.match(ACL_CHILD_REGEX, permit_rule.text)
            net_ip, hostmask = match_obj.group(1, 2)

            cfg_subnet = netaddr.IPNetwork("%s/%s" % (net_ip, hostmask))

            db_subnet = netaddr.IPNetwork("255.255.255.255/32")  # dummy value
            try:
                intf_list = intf_segment_dict[segment_id]
                for intf in intf_list:
                    if intf['device_owner'] == \
                       constants.DEVICE_OWNER_ROUTER_INTF:
                        subnet_cidr = intf['subnets'][0]['cidr']
                        db_subnet = netaddr.IPNetwork(subnet_cidr)
                        break
            except KeyError:
                LOG.info(_LI("KeyError when attemping to validate segment_id"))
                return False

            LOG.info(_LI("   cfg_subnet: %(cfg_net)s/%(cfg_prefix_len)s,"
                     " db_subnet: %(db_net)s/%(db_prefix_len)s") %
                     {'cfg_net': cfg_subnet.network,
                      'cfg_prefix_len': cfg_subnet.prefixlen,
                      'db_net': db_subnet.network,
                      'db_prefix_len': db_subnet.prefixlen})

            if cfg_subnet.network != db_subnet.network or \
               cfg_subnet.prefixlen != db_subnet.prefixlen:
                LOG.info(_LI("ACL subnet does not match subnet info"
                         " in openstack DB, deleting ACL"))
                return False

        return True

    def clean_acls(self, conn, intf_segment_dict,
                   segment_nat_dict, parsed_cfg):

        delete_acl_list = []
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        if (is_multi_region_enabled):
            acl_regex = ACL_MULTI_REGION_REGEX
        else:
            acl_regex = ACL_REGEX

        acls = parsed_cfg.find_objects(acl_regex)
        for acl in acls:
            LOG.info(_LI("\nacl: %(acl)s") % {'acl': acl})
            match_obj = re.match(acl_regex, acl.text)

            if (is_multi_region_enabled):
                region_id = match_obj.group(1)
                segment_id = int(match_obj.group(2))
                port_id = match_obj.group(3)
                if region_id != cfg.CONF.multi_region.region_id:
                    if region_id not in cfg.CONF.multi_region.other_region_ids:
                        delete_acl_list.append(acl.text)
                    else:
                        # skip because some other deployment owns
                        # this configuration
                        continue
            else:
                segment_id = int(match_obj.group(1))
                port_id = match_obj.group(2)

            LOG.info(_LI("   segment_id: %(seg_id)s, port_id: %(port_id)s") %
                     {'seg_id': segment_id, 'port_id': port_id})

            # Check that segment_id exists in openstack DB info
            if segment_id not in intf_segment_dict:
                LOG.info(_LI("Segment ID not found, deleting acl"))
                delete_acl_list.append(acl.text)
                continue

            # Check that permit rules match subnets defined on openstack intfs
            if self.check_acl_permit_rules_valid(segment_id,
                                                 acl,
                                                 intf_segment_dict) is False:
                delete_acl_list.append(acl.text)
                continue

            self.existing_cfg_dict['acls'][segment_id] = acl

        if not self.test_mode:
            for acl_cfg in delete_acl_list:
                del_cmd = XML_CMD_TAG % ("no %s" % (acl_cfg))
                confstr = XML_FREEFORM_SNIPPET % (del_cmd)
                LOG.info(_LI("Delete ACL: %(del_cmd)s") % {'del_cmd': del_cmd})
                conn.edit_config(target='running', config=confstr)

        LOG.debug("delete_acl_list = %s" % (pp.pformat(delete_acl_list)))
        return delete_acl_list

    def subintf_real_ip_check_gw_port(self, gw_port, ip_addr, netmask):
        """
        checks running-cfg derived ip_addr and netmask against neutron-db
        gw_port
        """
        if (gw_port is not None):
            target_ip = gw_port['fixed_ips'][0]['ip_address']
            target_net = netaddr.IPNetwork(gw_port['subnets'][0]['cidr'])

            if (ip_addr != target_ip):
                LOG.info(_LI("Subintf real IP is incorrect, deleting"))
                return False
            if (netmask != str(target_net.netmask)):
                LOG.info(_LI("Subintf has incorrect netmask, deleting"))
                return False

            return True

        return False

    def subintf_real_ip_check(self, intf_list, is_external, ip_addr, netmask):

        for target_intf in intf_list:
            target_ip = target_intf['fixed_ips'][0]['ip_address']
            target_net = netaddr.IPNetwork(target_intf['subnets'][0]['cidr'])
            LOG.info(_LI("target ip,net: %(target_ip)s,%(target_net)s,"
                         " actual ip,net %(ip_addr)s,%(netmask)s") %
                     {'target_ip': target_ip,
                      'target_net': target_net,
                      'ip_addr': ip_addr,
                      'netmask': netmask})

            if ip_addr != target_ip:
                LOG.info(_LI("Subintf real IP is incorrect, deleting"))
                return False
            if netmask != str(target_net.netmask):
                LOG.info(_LI("Subintf has incorrect netmask, deleting"))
                return False

            return True

        return False

    def subintf_real_ipv6_check(self,
                                intf_list,
                                is_external,
                                ipv6_addr,
                                prefixlen):

        if is_external:
            target_type = constants.DEVICE_OWNER_ROUTER_GW
        else:
            target_type = constants.DEVICE_OWNER_ROUTER_INTF

        for target_intf in intf_list:
            if target_intf['device_owner'] == target_type:

                target_ip = \
                    netaddr.IPAddress(
                        target_intf['fixed_ips'][0]['ip_address'])

                target_prefixlen = \
                    netaddr.IPNetwork(
                        target_intf['subnets'][0]['cidr']).prefixlen

                LOG.info(_LI("target ip,prefixlen: %(target_ip)s,"
                             "%(target_prefixlen)s, actual ip,"
                             "prefixlen %(ipv6_addr)s,%(prefixlen)s") %
                         {'target_ip': target_ip,
                          'target_prefixlen': target_prefixlen,
                          'ipv6_addr': ipv6_addr,
                          'prefixlen': prefixlen})

                if target_ip != netaddr.IPAddress(ipv6_addr):
                    LOG.info(_LI("Subintf IPv6 addr is incorrect, deleting"))
                    return False

                if target_prefixlen != int(prefixlen):
                    LOG.info(_LI("Subintf IPv6 prefix length"
                             " is incorrect, deleting"))
                    return False

                return True

        return False

    def gw_port_hsrp_ip_check(self, gw_port, ip_addr):

        if (gw_port is not None):
            ha_port = gw_port[ha.HA_INFO]['ha_port']

            target_ip = ha_port['fixed_ips'][0]['ip_address']
            LOG.info(_LI("target_ip: %(target_ip)s, actual_ip: %(ip_addr)s") %
                     {'target_ip': target_ip,
                      'ip_addr': ip_addr})
            if ip_addr != target_ip:
                LOG.info(_LI("HSRP VIP mismatch on gw_port, deleting"))
                return False
            else:
                return True
        return False

    def subintf_hsrp_ip_check(self, intf_list, is_external, ip_addr):
        for target_intf in intf_list:
            ha_intf = target_intf[ha.HA_INFO]['ha_port']
            target_ip = ha_intf['fixed_ips'][0]['ip_address']
            LOG.info(_LI("target_ip: %(target_ip)s, actual_ip: %(ip_addr)s") %
                     {'target_ip': target_ip,
                      'ip_addr': ip_addr})
            if ip_addr != target_ip:
                LOG.info(_LI("HSRP VIP mismatch, deleting"))
                return False

            return True

        return False

    # Returns True if interface has correct NAT config
    def clean_interfaces_nat_check(self, intf, segment_nat_dict):
        intf_nat_type = intf.re_search_children(INTF_NAT_REGEX)
        intf_nat_type = self.get_single_cfg(intf_nat_type)

        if intf_nat_type is not None:
            intf_nat_type = intf_nat_type.re_match(INTF_NAT_REGEX, group=1)

        LOG.info(_LI("NAT Type: %s"), intf_nat_type)

        intf.nat_type = intf_nat_type

        if (intf.segment_id in segment_nat_dict and
            segment_nat_dict[intf.segment_id] is True):
            if intf.is_external:
                if intf_nat_type != "outside":
                    nat_cmd = XML_CMD_TAG % (intf.text)
                    nat_cmd += XML_CMD_TAG % ("ip nat outside")
                    confstr = XML_FREEFORM_SNIPPET % (nat_cmd)
                    LOG.info(_LI("NAT type mismatch, should be outside"))
                    return False
            else:
                if intf_nat_type != "inside":
                    nat_cmd = XML_CMD_TAG % (intf.text)
                    nat_cmd += XML_CMD_TAG % ("ip nat inside")
                    confstr = XML_FREEFORM_SNIPPET % (nat_cmd)
                    LOG.info(_LI("NAT type mismatch, should be inside"))
                    return False
        else:
            if intf_nat_type is not None:
                nat_cmd = XML_CMD_TAG % (intf.text)
                nat_cmd += XML_CMD_TAG % ("no ip nat %s" % (intf_nat_type))
                confstr = XML_FREEFORM_SNIPPET % (nat_cmd)
                LOG.info(_LI("NAT type mismatch, should have no NAT, %s"),
                         (confstr))
                return False

        return True

    def clean_interfaces_ipv4_hsrp_check(self, intf, intf_db_dict):
        # Check HSRP VIP
        hsrp_vip_cfg_list = intf.re_search_children(HSRP_V4_VIP_REGEX)
        if len(hsrp_vip_cfg_list) < 1:
            LOG.info(_LI("Interface is missing HSRP VIP, deleting"))
            return False

        hsrp_vip_cfg = hsrp_vip_cfg_list[0]
        match_obj = re.match(HSRP_V4_VIP_REGEX, hsrp_vip_cfg.text)
        hsrp_vip_grp_num, hsrp_vip = match_obj.group(1, 2)

        if intf.is_external:
            return self.gw_port_hsrp_ip_check(
                                            intf_db_dict[intf.segment_id],
                                            hsrp_vip)
        else:
            return self.subintf_hsrp_ip_check(
                                            intf_db_dict[intf.segment_id],
                                            intf.is_external,
                                            hsrp_vip)

    def clean_interfaces_ipv4_check(self, intf, intf_db_dict):

        # Check that real IP address is correct
        ipv4_addr = intf.re_search_children(INTF_V4_ADDR_REGEX)
        if len(ipv4_addr) < 1:
            LOG.info(_LI("Subintf has no IP address, deleting"))
            return False

        ipv4_addr_cfg = ipv4_addr[0]
        match_obj = re.match(INTF_V4_ADDR_REGEX, ipv4_addr_cfg.text)
        ip_addr, netmask = match_obj.group(1, 2)

        if intf.is_external:
            return self.subintf_real_ip_check_gw_port(
                                            intf_db_dict[intf.segment_id],
                                            ip_addr, netmask)
        else:
            return self.subintf_real_ip_check(
                                            intf_db_dict[intf.segment_id],
                                            intf.is_external,
                                            ip_addr, netmask)

    def clean_interfaces_ipv6_check(self, intf, intf_segment_dict):
        # Check that real IP address is correct
        ipv6_addr = intf.re_search_children(INTF_V6_ADDR_REGEX)
        if len(ipv6_addr) < 1:
            LOG.info(_LI("Subintf has no IPv6 address, deleting"))
            return False

        ipv6_addr_cfg = ipv6_addr[0]
        match_obj = re.match(INTF_V6_ADDR_REGEX, ipv6_addr_cfg.text)
        ipv6_addr, prefixlen = match_obj.group(1, 2)

        return self.subintf_real_ipv6_check(intf_segment_dict[intf.segment_id],
                                            intf.is_external,
                                            ipv6_addr, prefixlen)

    def clean_interfaces(self, conn, intf_segment_dict,
                         segment_nat_dict, parsed_cfg):
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        if (is_multi_region_enabled):
            intf_desc_regex = INTF_DESC_MULTI_REGION_REGEX
            vrf_intf_regex_new = VRF_INTF_MULTI_REGION_REGEX_NEW
        else:
            intf_desc_regex = INTF_DESC_REGEX
            vrf_intf_regex_new = VRF_INTF_REGEX_NEW
        runcfg_intfs = [obj for obj in parsed_cfg.find_objects("^interf")
                        if obj.re_search_children(intf_desc_regex)]

        pending_delete_list = []

        # TODO(nh0556) split this big function into smaller functions
        for intf in runcfg_intfs:
            LOG.info(_LI("ASR interface: %s"), (intf))

            # check for region-id
            if is_multi_region_enabled:
                intf_desc = intf.re_search_children(intf_desc_regex)
                intf_desc = self.get_single_cfg(intf_desc)

                if not intf_desc:
                    LOG.info(_LI("Interface doesn't have "
                                 "a interface description, ignoring %s") % (
                             intf.text))
                    continue
                else:
                    intf_desc_region_id = (
                        intf_desc.re_match(INTF_DESC_MULTI_REGION_REGEX,
                                           group=1))
                    if (intf_desc_region_id is None):
                        # if no matching description field is found,
                        # assume that the interface is not owned by Openstack
                        LOG.info(_LI("Interface description doesn't have"
                                     "region-id, ignoring %s") % intf.text)
                        continue
                    else:
                        # since region-id was found, check if it's valid
                        my_region_id = cfg.CONF.multi_region.region_id
                        other_region_ids = (
                            cfg.CONF.multi_region.other_region_ids)
                        if intf_desc_region_id != my_region_id:
                            if (intf_desc_region_id not in other_region_ids):
                                pending_delete_list.append(intf)
                            else:
                                # skip because some other deployment owns
                                # this configuration
                                continue

            # obtain segment_id from interface definition
            intf.segment_id = int(intf.re_match(INTF_REGEX, group=1))
            LOG.info(_LI("  segment_id: %s"), (intf.segment_id))

            # Delete any interfaces where config doesn't match DB
            # Correct config will be added after clearing invalid cfg

            # TODO(Check that interface name e.g. Port-channel10 matches)
            # TODO(that specified in .ini file)

            # Check that the interface segment_id exists in the current DB data
            if (intf.segment_id not in intf_segment_dict and
               intf.segment_id not in self.segment_gw_dict):
                LOG.info(_LI("Invalid segment ID, delete interface"))
                pending_delete_list.append(intf)
                continue

            if (intf.segment_id in self.segment_gw_dict):
                intf.is_external = True
            else:
                intf.is_external = False

            # Check if dot1q config is correct
            dot1q_cfg = intf.re_search_children(DOT1Q_REGEX)
            dot1q_cfg = self.get_single_cfg(dot1q_cfg)

            if dot1q_cfg is None:
                LOG.info(_LI("Missing DOT1Q config, delete interface"))
                pending_delete_list.append(intf)
                continue
            else:
                dot1q_num = int(dot1q_cfg.re_match(DOT1Q_REGEX, group=1))
                if dot1q_num != int(intf.segment_id):
                    LOG.info(_LI("DOT1Q mismatch, delete interface"))
                    pending_delete_list.append(intf)
                    continue

            # Is this an "external network" segment_id?
            if intf.is_external:
                db_intf = self.segment_gw_dict[intf.segment_id]
            else:
                db_intf = intf_segment_dict[intf.segment_id][0]

            # intf.is_external = db_intf['is_external']
            intf.has_ipv6 = is_port_v6(db_intf)

            # Check VRF config
            if intf.is_external:
                vrf_cfg = intf.re_search_children(VRF_EXT_INTF_REGEX_NEW)
                vrf_cfg = self.get_single_cfg(vrf_cfg)
                LOG.info(_LI("VRF: %s"), (vrf_cfg))

                if vrf_cfg is not None:  # external network has no vrf
                    LOG.info(_LI("External network shouldn't"
                             " have VRF, deleting intf"))
                    pending_delete_list.append(intf)
                    continue
            else:
                vrf_cfg = intf.re_search_children(vrf_intf_regex_new)
                vrf_cfg = self.get_single_cfg(vrf_cfg)
                LOG.info(_LI("VRF: %s"), (vrf_cfg))
                if not vrf_cfg:
                    LOG.info(_LI("Internal network missing valid VRF,"
                             " deleting intf"))
                    pending_delete_list.append(intf)
                    continue

                # check for VRF mismatch
                match_obj = re.match(vrf_intf_regex_new, vrf_cfg.text)
                router_id = match_obj.group(1)
                if (is_multi_region_enabled):
                    region_id = match_obj.group(2)
                    my_region_id = cfg.CONF.multi_region.region_id
                    other_region_ids = cfg.CONF.multi_region.other_region_ids
                    if region_id != my_region_id:
                        if (region_id not in other_region_ids):
                            pending_delete_list.append(intf)
                        else:
                            # skip because some other deployment owns
                            # this configuration
                            continue

                # router_id device_id/ha_port_device_id check
                if (ha.HA_INFO in db_intf):
                    ha_port_device_id = (db_intf[ha.HA_INFO]
                                         ['ha_port']['device_id'])
                else:
                    ha_port_device_id = None

                if (router_id != db_intf["device_id"][0:6] and
                    (ha_port_device_id is not None and
                     router_id != ha_port_device_id[0:6])):

                    LOG.info(_LI("Internal network VRF mismatch,"
                                 " deleting intf,"
                                 " router_id: %(router_id)s,"
                                 " db_intf_dev_id: %(db_intf_dev_id)s") %
                             {'router_id': router_id,
                              'db_intf_dev_id': db_intf["device_id"]})
                    pending_delete_list.append(intf)
                    continue

            # self.existing_cfg_dict['interfaces'][intf.segment_id] = intf

            correct_grp_num = int(db_intf[ha.HA_INFO]['group'])

            if intf.is_external:
                intf_db = self.segment_gw_dict
            else:
                intf_db = intf_segment_dict

            if intf.has_ipv6 is False:
                if self.clean_interfaces_nat_check(intf,
                                                   segment_nat_dict) \
                    is False:
                    pending_delete_list.append(intf)
                    continue
                if self.clean_interfaces_ipv4_check(intf,
                                                    intf_db) \
                    is False:
                    pending_delete_list.append(intf)
                    continue
                if self.clean_interfaces_ipv4_hsrp_check(intf,
                                                         intf_db) \
                    is False:
                    pending_delete_list.append(intf)
                    continue
            else:
                if self.clean_interfaces_ipv6_check(intf, intf_db) \
                    is False:
                    pending_delete_list.append(intf)
                    continue

            # Delete if there's any hsrp config with wrong group number
            #del_hsrp_cmd = XML_CMD_TAG % (intf.text)
            hsrp_cfg_list = intf.re_search_children(HSRP_REGEX)
            needs_hsrp_delete = False
            for hsrp_cfg in hsrp_cfg_list:
                hsrp_num = int(hsrp_cfg.re_match(HSRP_REGEX, group=1))
                if hsrp_num != correct_grp_num:
                    needs_hsrp_delete = True
                    #del_hsrp_cmd += XML_CMD_TAG % ("no %s" % (hsrp_cfg.text))

            if needs_hsrp_delete:
                LOG.info(_LI("Bad HSRP config for interface, deleting"))
                pending_delete_list.append(intf)
                continue
                #confstr = XML_FREEFORM_SNIPPET % (del_hsrp_cmd)
                #LOG.info("Deleting bad HSRP config: %s" % (confstr))
                #rpc_obj = conn.edit_config(target='running', config=confstr)

            self.existing_cfg_dict['interfaces'][intf.segment_id] = intf.text

        if not self.test_mode:
            for intf in pending_delete_list:
                del_cmd = XML_CMD_TAG % ("no %s" % (intf.text))
                confstr = XML_FREEFORM_SNIPPET % (del_cmd)
                LOG.info(_LI("Deleting %s"), (intf.text))
                #LOG.info(confstr)
                conn.edit_config(target='running', config=confstr)

        LOG.debug("pending_delete_list (interfaces) = %s" %
                  pp.pformat(pending_delete_list))
        return pending_delete_list
