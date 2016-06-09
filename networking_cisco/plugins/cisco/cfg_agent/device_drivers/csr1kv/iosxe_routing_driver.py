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

import inspect
import logging
import netaddr
import re
import time
import xml.etree.ElementTree as ET

from oslo_config import cfg
from oslo_utils import importutils

from networking_cisco._i18n import _LE, _LI, _LW
from networking_cisco.plugins.cisco.cfg_agent import cfg_exceptions as cfg_exc
from networking_cisco.plugins.cisco.cfg_agent.device_drivers import (
    devicedriver_api)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.csr1kv import (
    cisco_csr1kv_snippets as snippets)
from networking_cisco.plugins.cisco.common.htparser import HTParser
from networking_cisco.plugins.cisco.extensions import ha

ncclient = importutils.try_import('ncclient')
manager = importutils.try_import('ncclient.manager')

LOG = logging.getLogger(__name__)


# N1kv constants
T1_PORT_NAME_PREFIX = 't1_p:'  # T1 port/network is for VXLAN
T2_PORT_NAME_PREFIX = 't2_p:'  # T2 port/network is for VLAN


class IosXeRoutingDriver(devicedriver_api.RoutingDriverBase):
    """Generic IOS XE Routing Driver.

    This driver encapsulates the configuration logic via NETCONF protocol to
    configure a generic (IOS-XE based) device for implementing
    Neutron L3 services. These services include routing, NAT and floating
    IPs (as per Neutron terminology).
    """

    DEV_NAME_LEN = 14

    def __init__(self, **device_params):
        try:
            self._host_ip = device_params['management_ip_address']
            self._host_ssh_port = device_params['protocol_port']
            credentials = device_params.get('credentials', {})
            self._username = credentials.get('user_name')
            self._password = credentials.get('password')
            self._timeout = (device_params.get('timeout') or
                             cfg.CONF.cfg_agent.device_connection_timeout)
            self._ncc_connection = None
            self._itfcs_enabled = False
        except KeyError as e:
            LOG.error(_LE("Missing device parameter:%s. Aborting "
                          "IosXeRoutingDriver initialization"), e)
            raise cfg_exc.InitializationException()

    ###### Public Functions ########
    def router_added(self, ri):
        self._create_vrf(ri)

    def router_removed(self, ri):
        self._remove_vrf(ri)

    def internal_network_added(self, ri, port):
        self._create_sub_interface(ri, port)
        if port.get(ha.HA_INFO) is not None and ri.get(ha.ENABLED, False):
            self._add_ha(ri, port)

    def internal_network_removed(self, ri, port):
        self._remove_sub_interface(port)

    def external_gateway_added(self, ri, ext_gw_port):
        self._create_sub_interface(ri, ext_gw_port)
        # set default route via this network's gateway ip
        self._add_default_route(ri, ext_gw_port)

    def external_gateway_removed(self, ri, ext_gw_port):
        # remove default route via this network's gateway ip
        self._remove_default_route(ri, ext_gw_port)
        # finally, remove external network sub-interface
        self._remove_sub_interface(ext_gw_port)

    def enable_internal_network_NAT(self, ri, port, ext_gw_port):
        self._add_internal_nw_nat_rules(ri, port, ext_gw_port)

    def disable_internal_network_NAT(self, ri, port, ext_gw_port):
        self._remove_internal_nw_nat_rules(ri, [port], ext_gw_port)

    def floating_ip_added(self, ri, ext_gw_port, floating_ip, fixed_ip):
        self._add_floating_ip(ri, floating_ip, fixed_ip)

    def floating_ip_removed(self, ri, ext_gw_port, floating_ip, fixed_ip):
        self._remove_floating_ip(ri, ext_gw_port, floating_ip, fixed_ip)

    def routes_updated(self, ri, action, route):
        self._update_routing_table(ri, action, route)

    def clear_connection(self):
        self._ncc_connection = None

    def cleanup_invalid_cfg(self, hd, routers):
        # at this point nothing to be done for CSR
        return

    def get_configuration(self):
        return self._get_running_config(split=False)

    ##### Internal Functions  ####

    def _create_sub_interface(self, ri, port):
        vrf_name = self._get_vrf_name(ri)
        ip_cidr = port['ip_cidr']
        net_mask = netaddr.IPNetwork(ip_cidr).netmask
        gateway_ip = ip_cidr.split('/')[0]
        sub_interface = self._get_interface_name_from_hosting_port(port)
        vlan = self._get_interface_vlan_from_hosting_port(port)
        self._do_create_sub_interface(sub_interface, vlan, vrf_name,
                                      gateway_ip, net_mask)

    def _remove_sub_interface(self, port):
        sub_interface = self._get_interface_name_from_hosting_port(port)
        self._do_remove_sub_interface(sub_interface)

    def _add_ha(self, ri, port):
        func_dict = {
            ha.HA_HSRP: self._add_ha_hsrp,
            ha.HA_VRRP: self._add_ha_vrrp,
            ha.HA_GLBP: self._add_ha_gblp
        }
        # invoke the right function for the ha type
        func_dict[ri[ha.DETAILS][ha.TYPE]](self, ri, port)

    def _add_ha_hsrp(self, ri, port):
        priority = ri[ha.DETAILS][ha.PRIORITY]
        port_ha_info = port[ha.HA_INFO]
        group = port_ha_info['group']
        ip = port_ha_info['ha_port']['fixed_ips'][0]['ip_address']
        if ip and group and priority:
            vrf_name = self._get_vrf_name(ri)
            sub_interface = self._get_interface_name_from_hosting_port(port)
            self._do_set_ha_hsrp(sub_interface, vrf_name, priority, group, ip)

    def _add_ha_vrrp(self, ri, port):
        raise NotImplementedError()

    def _add_ha_gblp(self, ri, port):
        raise NotImplementedError()

    def _remove_ha(self, ri, port):
        pass

    def _get_acl_name_from_vlan(self, vlan):
        return "acl_%s" % vlan

    def _add_internal_nw_nat_rules(self, ri, port, ext_port):
        vrf_name = self._get_vrf_name(ri)
        in_vlan = self._get_interface_vlan_from_hosting_port(port)
        acl_no = self._get_acl_name_from_vlan(in_vlan)
        internal_cidr = port['ip_cidr']
        internal_net = netaddr.IPNetwork(internal_cidr).network
        net_mask = netaddr.IPNetwork(internal_cidr).hostmask
        inner_itfc = self._get_interface_name_from_hosting_port(port)
        outer_itfc = self._get_interface_name_from_hosting_port(ext_port)
        self._nat_rules_for_internet_access(acl_no, internal_net,
                                            net_mask, inner_itfc,
                                            outer_itfc, vrf_name)

    def _remove_internal_nw_nat_rules(self, ri, ports, ext_port):
        acls = []
        # first disable nat in all inner ports
        for port in ports:
            in_itfc_name = self._get_interface_name_from_hosting_port(port)
            inner_vlan = self._get_interface_vlan_from_hosting_port(port)
            acls.append(self._get_acl_name_from_vlan(inner_vlan))
            self._remove_interface_nat(in_itfc_name, 'inside')
        # wait for two seconds
        LOG.debug("Sleep for 2 seconds before clearing NAT rules")
        time.sleep(2)
        # clear the NAT translation table
        self._remove_dyn_nat_translations()
        # remove dynamic nat rules and acls
        vrf_name = self._get_vrf_name(ri)
        ext_itfc_name = self._get_interface_name_from_hosting_port(ext_port)
        for acl in acls:
            self._remove_dyn_nat_rule(acl, ext_itfc_name, vrf_name)

    def _add_default_route(self, ri, ext_gw_port):
        ext_gw_ip = ext_gw_port['subnet']['gateway_ip']
        if ext_gw_ip:
            vrf_name = self._get_vrf_name(ri)
            conf_str = snippets.DEFAULT_ROUTE_CFG % (vrf_name, ext_gw_ip)
            if not self._cfg_exists(conf_str):
                conf_str = snippets.SET_DEFAULT_ROUTE % (vrf_name, ext_gw_ip)
                self._edit_running_config(conf_str, 'SET_DEFAULT_ROUTE')

    def _remove_default_route(self, ri, ext_gw_port):
        ext_gw_ip = ext_gw_port['subnet']['gateway_ip']
        if ext_gw_ip:
            vrf_name = self._get_vrf_name(ri)
            conf_str = snippets.DEFAULT_ROUTE_CFG % (vrf_name, ext_gw_ip)
            if self._cfg_exists(conf_str):
                conf_str = snippets.REMOVE_DEFAULT_ROUTE % (vrf_name,
                                                            ext_gw_ip)
                self._edit_running_config(conf_str, 'REMOVE_DEFAULT_ROUTE')

    def _add_floating_ip(self, ri, floating_ip, fixed_ip):
        vrf_name = self._get_vrf_name(ri)
        self._do_add_floating_ip(floating_ip, fixed_ip, vrf_name)

    def _remove_floating_ip(self, ri, ext_gw_port, floating_ip, fixed_ip):
        vrf_name = self._get_vrf_name(ri)
        out_itfc_name = self._get_interface_name_from_hosting_port(ext_gw_port)
        # first remove NAT from outer interface
        self._remove_interface_nat(out_itfc_name, 'outside')
        # clear the NAT translation table
        self._remove_dyn_nat_translations()
        # remove the floating ip
        self._do_remove_floating_ip(floating_ip, fixed_ip, vrf_name)
        # enable NAT on outer interface
        self._add_interface_nat(out_itfc_name, 'outside')

    def _update_routing_table(self, ri, action, route):
        vrf_name = self._get_vrf_name(ri)
        destination_net = netaddr.IPNetwork(route['destination'])
        dest = destination_net.network
        dest_mask = destination_net.netmask
        next_hop = route['nexthop']
        if action is 'replace':
            self._add_static_route(dest, dest_mask, next_hop, vrf_name)
        elif action is 'delete':
            self._remove_static_route(dest, dest_mask, next_hop, vrf_name)
        else:
            LOG.error(_LE('Unknown route command %s'), action)

    def _create_vrf(self, ri):
        vrf_name = self._get_vrf_name(ri)
        self._do_create_vrf(vrf_name)

    def _remove_vrf(self, ri):
        vrf_name = self._get_vrf_name(ri)
        self._do_remove_vrf(vrf_name)

    def _get_vrf_name(self, ri):
        return ri.router_name()[:self.DEV_NAME_LEN]

    def _get_connection(self):
        """Make SSH connection to the CSR.

        The external ncclient library is used for creating this connection.
        This method keeps state of any existing connections and reuses them if
        already connected. Also CSR1kv's interfaces (except management) are
        disabled by default when it is booted. So if connecting for the first
        time, driver will enable all other interfaces and keep that status in
        the `_itfcs_enabled` flag.
        """
        try:
            if self._ncc_connection and self._ncc_connection.connected:
                return self._ncc_connection
            else:
                self._ncc_connection = manager.connect(
                    host=self._host_ip, port=self._host_ssh_port,
                    username=self._username, password=self._password,
                    device_params={'name': "csr"}, timeout=self._timeout)
                if not self._itfcs_enabled:
                    self._itfcs_enabled = self._enable_itfcs(
                        self._ncc_connection)
            return self._ncc_connection
        except Exception as e:
            conn_params = {'host': self._host_ip, 'port': self._host_ssh_port,
                           'user': self._username,
                           'timeout': self._timeout, 'reason': e.message}
            raise cfg_exc.ConnectionException(**conn_params)

    def _get_interface_name_from_hosting_port(self, port):
        vlan = self._get_interface_vlan_from_hosting_port(port)
        int_no = self._get_interface_no_from_hosting_port(port)
        return 'GigabitEthernet%s.%s' % (int_no, vlan)

    @staticmethod
    def _get_interface_vlan_from_hosting_port(port):
        return port['hosting_info']['segmentation_id']

    @staticmethod
    def _get_interface_no_from_hosting_port(port):
        """Calculate interface number from the hosting port's name.

         Interfaces in the CSR1kv are created in pairs (T1 and T2) where
         T1 interface is used for VLAN and T2 interface for VXLAN traffic
         respectively. On the neutron side these are named T1 and T2 ports and
         follows the naming convention: <Tx_PORT_NAME_PREFIX>:<PAIR_INDEX>
         where the `PORT_NAME_PREFIX` indicates either VLAN or VXLAN and
         `PAIR_INDEX` is the pair number. `PAIR_INDEX` starts at 1.

         In CSR1kv, GigabitEthernet 0 is not present and GigabitEthernet 1
         is used as a management interface (Note: this might change in
         future). So the first (T1,T2) pair corresponds to
         (GigabitEthernet 2, GigabitEthernet 3) and so forth. This function
         extracts the `PAIR_INDEX` and calculates the corresponding interface
         number.

        :param port: neutron port corresponding to the interface.
        :return: number of the interface (eg: 1 in case of GigabitEthernet1)
        """
        _name = port['hosting_info']['hosting_port_name']
        if_type = _name.split(':')[0] + ':'
        if if_type == T1_PORT_NAME_PREFIX:
            return str(int(_name.split(':')[1]) * 2)
        elif if_type == T2_PORT_NAME_PREFIX:
            return str(int(_name.split(':')[1]) * 2 + 1)
        else:
            params = {'attribute': 'hosting_port_name', 'value': _name}
            raise cfg_exc.CSR1kvUnknownValueException(**params)

    def _get_interfaces(self):
        """Get a list of interfaces on this hosting device.

        :return: List of the interfaces
        """
        ios_cfg = self._get_running_config()
        parse = HTParser(ios_cfg)
        itfcs_raw = parse.find_lines("^interface GigabitEthernet")
        itfcs = [raw_if.strip().split(' ')[1] for raw_if in itfcs_raw]
        LOG.debug("Interfaces on hosting device: %s", itfcs)
        return itfcs

    def _get_interface_ip(self, interface_name):
        """Get the ip address for an interface.

        :param interface_name: interface_name as a string
        :return: ip address of interface as a string
        """
        ios_cfg = self._get_running_config()
        parse = HTParser(ios_cfg)
        children = parse.find_children("^interface %s" % interface_name)
        for line in children:
            if 'ip address' in line:
                ip_address = line.strip().split(' ')[2]
                LOG.debug("IP Address:%s", ip_address)
                return ip_address
        LOG.warning(_LW("Cannot find interface: %s"), interface_name)
        return None

    def _interface_exists(self, interface):
        """Check whether interface exists."""
        ios_cfg = self._get_running_config()
        parse = HTParser(ios_cfg)
        itfcs_raw = parse.find_lines("^interface " + interface)
        return len(itfcs_raw) > 0

    def _enable_itfcs(self, conn):
        """Enable the interfaces of a CSR1kv Virtual Router.

        When the virtual router first boots up, all interfaces except
        management are down. This method will enable all data interfaces.

        Note: In CSR1kv, GigabitEthernet 0 is not present. GigabitEthernet 1
        is used as management and GigabitEthernet 2 and up are used for data.
        This might change in future releases.

        Currently only the second and third Gig interfaces corresponding to a
        single (T1,T2) pair and configured as trunk for VLAN and VXLAN
        is enabled.

        :param conn: Connection object
        :return: True or False
        """

        #ToDo(Hareesh): Interfaces are hard coded for now. Make it dynamic.
        interfaces = ['GigabitEthernet 2', 'GigabitEthernet 3']
        try:
            for i in interfaces:
                conf_str = snippets.ENABLE_INTF % i
                rpc_obj = conn.edit_config(target='running', config=conf_str)
                if self._check_response(rpc_obj, 'ENABLE_INTF'):
                    LOG.info(_LI("Enabled interface %s "), i)
                    time.sleep(1)
        except Exception:
            return False
        return True

    def _get_vrfs(self):
        """Get the current VRFs configured in the device.

        :return: A list of vrf names as string
        """
        vrfs = []
        ios_cfg = self._get_running_config()
        parse = HTParser(ios_cfg)
        vrfs_raw = parse.find_lines("^vrf definition")
        for line in vrfs_raw:
            #  raw format ['ip vrf <vrf-name>',....]
            vrf_name = line.strip().split(' ')[2]
            vrfs.append(vrf_name)
        LOG.info(_LI("VRFs:%s"), vrfs)
        return vrfs

    def _get_capabilities(self):
        """Get the servers NETCONF capabilities.

        :return: List of server capabilities.
        """
        conn = self._get_connection()
        capabilities = []
        for c in conn.server_capabilities:
            capabilities.append(c)
        LOG.debug("Server capabilities: %s", capabilities)
        return capabilities

    def _get_running_config(self, split=True):
        """Get the CSR's current running config.

        :return: Current IOS running config as multiline string
        """
        conn = self._get_connection()
        config = conn.get_config(source="running")
        if config:
            root = ET.fromstring(config._raw)
            running_config = root[0][0]
            if split is True:
                rgx = re.compile("\r*\n+")
                ioscfg = rgx.split(running_config.text)
            else:
                ioscfg = running_config.text
            return ioscfg

    def _check_acl(self, acl_no, network, netmask):
        """Check a ACL config exists in the running config.

        :param acl_no: access control list (ACL) number
        :param network: network which this ACL permits
        :param netmask: netmask of the network
        :return:
        """
        exp_cfg_lines = ['ip access-list standard ' + str(acl_no),
                         ' permit ' + str(network) + ' ' + str(netmask)]
        ios_cfg = self._get_running_config()
        parse = HTParser(ios_cfg)
        acls_raw = parse.find_children(exp_cfg_lines[0])
        if acls_raw:
            if exp_cfg_lines[1] in acls_raw:
                return True
            LOG.error(_LE("Mismatch in ACL configuration for %s"), acl_no)
            return False
        LOG.debug("%s is not present in config", acl_no)
        return False

    def _cfg_exists(self, cfg_str):
        """Check a partial config string exists in the running config.

        :param cfg_str: config string to check
        :return : True or False
        """
        ios_cfg = self._get_running_config()
        parse = HTParser(ios_cfg)
        cfg_raw = parse.find_lines("^" + cfg_str)
        LOG.debug("_cfg_exists(): Found lines %s", cfg_raw)
        return len(cfg_raw) > 0

    def _set_interface(self, name, ip_address, mask):
        conf_str = snippets.SET_INTC % (name, ip_address, mask)
        self._edit_running_config(conf_str, 'SET_INTC')

    def _do_create_vrf(self, vrf_name):
        conf_str = snippets.CREATE_VRF % vrf_name
        self._edit_running_config(conf_str, 'CREATE_VRF')

    def _do_remove_vrf(self, vrf_name):
        if vrf_name in self._get_vrfs():
            conf_str = snippets.REMOVE_VRF % vrf_name
            self._edit_running_config(conf_str, 'REMOVE_VRF')

    def _do_create_sub_interface(self, sub_interface, vlan_id, vrf_name, ip,
                                mask):
        if vrf_name not in self._get_vrfs():
            LOG.error(_LE("VRF %s not present"), vrf_name)
        conf_str = snippets.CREATE_SUBINTERFACE % (sub_interface, vlan_id,
                                                   vrf_name, ip, mask)
        self._edit_running_config(conf_str, 'CREATE_SUBINTERFACE')

    def _do_remove_sub_interface(self, sub_interface):
        # optional: verify this is the correct sub_interface
        if self._interface_exists(sub_interface):
            conf_str = snippets.REMOVE_SUBINTERFACE % sub_interface
            self._edit_running_config(conf_str, 'REMOVE_SUBINTERFACE')

    def _do_set_ha_hsrp(self, sub_interface, vrf_name, priority, group, ip):
        if vrf_name not in self._get_vrfs():
            LOG.error(_LE("VRF %s not present"), vrf_name)
        conf_str = snippets.SET_INTC_HSRP % (sub_interface, vrf_name, group,
                                             priority, group, ip)
        action = "SET_INTC_HSRP (Group: %s, Priority: % s)" % (group, priority)
        self._edit_running_config(conf_str, action)

    def _do_remove_ha_hsrp(self, sub_interface, group):
        conf_str = snippets.REMOVE_INTC_HSRP % (sub_interface, group)
        action = ("REMOVE_INTC_HSRP (subinterface:%s, Group:%s)"
                  % (sub_interface, group))
        self._edit_running_config(conf_str, action)

    def _get_interface_cfg(self, interface):
        ios_cfg = self._get_running_config()
        parse = HTParser(ios_cfg)
        return parse.find_children('interface ' + interface)

    def _nat_rules_for_internet_access(self, acl_no, network,
                                       netmask,
                                       inner_itfc,
                                       outer_itfc,
                                       vrf_name):
        """Configure the NAT rules for an internal network.

        Configuring NAT rules in the CSR1kv is a three step process. First
        create an ACL for the IP range of the internal network. Then enable
        dynamic source NATing on the external interface of the CSR for this
        ACL and VRF of the neutron router. Finally enable NAT on the
        interfaces of the CSR where the internal and external networks are
        connected.

        :param acl_no: ACL number of the internal network.
        :param network: internal network
        :param netmask: netmask of the internal network.
        :param inner_itfc: (name of) interface connected to the internal
        network
        :param outer_itfc: (name of) interface connected to the external
        network
        :param vrf_name: VRF corresponding to this virtual router
        :return: True if configuration succeeded
        :raises: networking_cisco.plugins.cisco.cfg_agent.cfg_exceptions.
        CSR1kvConfigException
        """
        # Duplicate ACL creation throws error, so checking
        # it first. Remove it in future as this is not common in production
        acl_present = self._check_acl(acl_no, network, netmask)
        if not acl_present:
            conf_str = snippets.CREATE_ACL % (acl_no, network, netmask)
            self._edit_running_config(conf_str, 'CREATE_ACL')

        conf_str = snippets.SET_DYN_SRC_TRL_INTFC % (acl_no, outer_itfc,
                                                    vrf_name)
        self._edit_running_config(conf_str, 'SET_DYN_SRC_TRL_INTFC')

        conf_str = snippets.SET_NAT % (inner_itfc, 'inside')
        self._edit_running_config(conf_str, 'SET_NAT_INSIDE')
        conf_str = snippets.SET_NAT % (outer_itfc, 'outside')
        self._edit_running_config(conf_str, 'SET_NAT_OUTSIDE')

    def _add_interface_nat(self, itfc_name, itfc_type):
        conf_str = snippets.SET_NAT % (itfc_name, itfc_type)
        self._edit_running_config(conf_str, 'SET_NAT_' + itfc_type)

    def _remove_interface_nat(self, itfc_name, itfc_type):
        conf_str = snippets.REMOVE_NAT % (itfc_name, itfc_type)
        self._edit_running_config(conf_str, 'SET_NAT_' + itfc_type)

    def _remove_dyn_nat_rule(self, acl_no, outer_itfc_name, vrf_name):
        conf_str = snippets.SNAT_CFG % (acl_no, outer_itfc_name, vrf_name)
        if self._cfg_exists(conf_str):
            conf_str = snippets.REMOVE_DYN_SRC_TRL_INTFC % (
                acl_no, outer_itfc_name, vrf_name)
            self._edit_running_config(conf_str, 'REMOVE_DYN_SRC_TRL_INTFC')
        conf_str = snippets.REMOVE_ACL % acl_no
        self._edit_running_config(conf_str, 'REMOVE_ACL')

    def _remove_dyn_nat_translations(self):
        conf_str = snippets.CLEAR_DYN_NAT_TRANS
        self._edit_running_config(conf_str, 'CLEAR_DYN_NAT_TRANS')

    def _do_add_floating_ip(self, floating_ip, fixed_ip, vrf):
        conf_str = snippets.SET_STATIC_SRC_TRL % (fixed_ip, floating_ip, vrf)
        self._edit_running_config(conf_str, 'SET_STATIC_SRC_TRL')

    def _do_remove_floating_ip(self, floating_ip, fixed_ip, vrf):
        conf_str = snippets.REMOVE_STATIC_SRC_TRL % (
            fixed_ip, floating_ip, vrf)
        self._edit_running_config(conf_str, 'REMOVE_STATIC_SRC_TRL')

    def _get_floating_ip_cfg(self):
        ios_cfg = self._get_running_config()
        parse = HTParser(ios_cfg)
        res = parse.find_lines('ip nat inside source static')
        return res

    def _add_static_route(self, dest, dest_mask, next_hop, vrf):
        conf_str = snippets.SET_IP_ROUTE % (vrf, dest, dest_mask, next_hop)
        self._edit_running_config(conf_str, 'SET_IP_ROUTE')

    def _remove_static_route(self, dest, dest_mask, next_hop, vrf):
        conf_str = snippets.REMOVE_IP_ROUTE % (vrf, dest, dest_mask, next_hop)
        self._edit_running_config(conf_str, 'REMOVE_IP_ROUTE')

    def _get_static_route_cfg(self):
        ios_cfg = self._get_running_config()
        parse = HTParser(ios_cfg)
        return parse.find_lines('ip route')

    def caller_name(self, skip=2):
        """
        Get a name of a caller in the format module.class.method

       `skip` specifies how many levels of stack to skip while getting caller
       name. skip=1 means "who calls me", skip=2 "who calls my caller" etc.

       An empty string is returned if skipped levels exceed stack height
       """
        stack = inspect.stack()
        start = 0 + skip
        if len(stack) < start + 1:
            return ''
        parentframe = stack[start][0]

        name = []
        module = inspect.getmodule(parentframe)
        # `modname` can be None when frame is executed directly in console
        # TODO(asr1kteam): consider using __main__
        if module:
            name.append(module.__name__)
        # detect classname
        if 'self' in parentframe.f_locals:
            # I don't know any way to detect call from the object method
            # XXX: there seems to be no way to detect static method call,
            # it will be just a function call
            name.append(parentframe.f_locals['self'].__class__.__name__)
        codename = parentframe.f_code.co_name
        if codename != '<module>':  # top level usually
            name.append(codename)  # function or a method
        del parentframe
        return ".".join(name)

    # [ OR ]
    # curframe = inspect.currentframe()
    # calframe = inspect.getouterframes(curframe, 2)
    # return calframe[1][3]

    def _edit_running_config(self, conf_str, snippet):
        conn = self._get_connection()
        LOG.info(_LI("Config generated for [%(device)s] %(snip)s is:%(conf)s "
                 "caller:%(caller)s"),
                 {'device': self.hosting_device['id'],
                  'snip': snippet,
                  'conf': conf_str,
                  'caller': self.caller_name()})
        try:
            rpc_obj = conn.edit_config(target='running', config=conf_str)
            self._check_response(rpc_obj, snippet, conf_str=conf_str)
        except Exception as e:
            # Here we catch all exceptions caused by REMOVE_/DELETE_ configs
            # to avoid config agent to get stuck once it hits this condition.
            # This is needed since the current ncclient version (0.4.2)
            # generates an exception when an attempt to configure the device
            # fails by the device (ASR1K router) but it doesn't provide any
            # details about the error message that the device reported.
            # With ncclient 0.4.4 version and onwards the exception returns
            # also the proper error. Hence this code can be changed when the
            # ncclient version is increased.
            if re.search(r"REMOVE_|DELETE_", snippet):
                LOG.warning(_LW("Pass exception for %s"), snippet)
                pass
            elif isinstance(e, ncclient.operations.rpc.RPCError):
                e_tag = e.tag
                e_type = e.type
                params = {'snippet': snippet, 'type': e_type, 'tag': e_tag,
                          'dev_id': self.hosting_device['id'],
                          'ip': self._host_ip, 'confstr': conf_str}
                raise cfg_exc.CSR1kvConfigException(**params)

    def _check_response(self, rpc_obj, snippet_name, conf_str=None):
        """This function checks the rpc response object for status.

        This function takes as input the response rpc_obj and the snippet name
        that was executed. It parses it to see, if the last edit operation was
        a success or not.
            <?xml version="1.0" encoding="UTF-8"?>
            <rpc-reply message-id="urn:uuid:81bf8082-....-b69a-000c29e1b85c"
                       xmlns="urn:ietf:params:netconf:base:1.0">
                <ok />
            </rpc-reply>
        In case of error, CSR1kv sends a response as follows.
        We take the error type and tag.
            <?xml version="1.0" encoding="UTF-8"?>
            <rpc-reply message-id="urn:uuid:81bf8082-....-b69a-000c29e1b85c"
            xmlns="urn:ietf:params:netconf:base:1.0">
                <rpc-error>
                    <error-type>protocol</error-type>
                    <error-tag>operation-failed</error-tag>
                    <error-severity>error</error-severity>
                </rpc-error>
            </rpc-reply>
        :return: True if the config operation completed successfully
        :raises: networking_cisco.plugins.cisco.cfg_agent.cfg_exceptions.
        CSR1kvConfigException
        """
        LOG.debug("RPCReply for %(snippet_name)s is %(rpc_obj)s",
                  {'snippet_name': snippet_name, 'rpc_obj': rpc_obj.xml})
        xml_str = rpc_obj.xml
        if "<ok />" in xml_str:
            # LOG.debug("RPCReply for %s is OK", snippet_name)
            LOG.info(_LI("%s was successfully executed"), snippet_name)
            return True
        # Not Ok, we throw a ConfigurationException
        e_type = rpc_obj._root[0][0].text
        e_tag = rpc_obj._root[0][1].text
        params = {'snippet': snippet_name, 'type': e_type, 'tag': e_tag,
                  'dev_id': self.hosting_device['id'],
                  'ip': self._host_ip, 'confstr': conf_str}
        raise cfg_exc.CSR1kvConfigException(**params)
