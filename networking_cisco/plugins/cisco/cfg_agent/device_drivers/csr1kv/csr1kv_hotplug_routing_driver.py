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

import logging
from lxml import etree
import netaddr
from xml.dom import minidom
import xml.etree.ElementTree as ET

from networking_cisco.plugins.cisco.cfg_agent import cfg_exceptions as cfg_exc
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.csr1kv import (
    cisco_csr1kv_snippets as snippets)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.csr1kv.\
    csr1kv_routing_driver import CSR1kvRoutingDriver
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.csr1kv.\
    csr1kv_routing_driver import save_config

from networking_cisco._i18n import _LI

LOG = logging.getLogger(__name__)


class CSR1kvHotPlugRoutingDriver(CSR1kvRoutingDriver):
    """CSR1kv Hotplugging Routing Driver."""

    def __init__(self, **device_params):
        super(CSR1kvHotPlugRoutingDriver, self).__init__(**device_params)

    @save_config
    def internal_network_added(self, ri, port):
        self._csr_configure_interface(ri, port)

    @save_config
    def internal_network_removed(self, ri, port):
        self._csr_deconfigure_interface(port)

    @save_config
    def external_gateway_added(self, ri, ex_gw_port):
        self._csr_configure_interface(ri, ex_gw_port)
        ex_gw_ip = ex_gw_port['subnets'][0]['gateway_ip']
        if ex_gw_ip:
            # Set default route via this network's gateway ip
            self._csr_add_default_route(ri, ex_gw_ip)

    @save_config
    def external_gateway_removed(self, ri, ex_gw_port):
        ex_gw_ip = ex_gw_port['subnets'][0]['gateway_ip']
        if ex_gw_ip:
            self._csr_remove_default_route(ri, ex_gw_ip)
        self._csr_deconfigure_interface(ex_gw_port)

    def _enable_intfs(self, conn):
        return True

    def _csr_configure_interface(self, ri, port):
        vrf_name = self._csr_get_vrf_name(ri)
        ip_cidr = port['ip_cidr']
        netmask = netaddr.IPNetwork(ip_cidr).netmask
        gateway_ip = ip_cidr.split('/')[0]
        interface_name = self._get_interface_name_from_hosting_port(port)
        if not interface_name:
            params = {'id': port['id'], 'mac': port['mac_address']}
            raise cfg_exc.CSR1kvMissingInterfaceException(**params)
        self._configure_interface_mac(interface_name, port['mac_address'])
        self._configure_interface(interface_name, vrf_name,
                                  gateway_ip, netmask)

    def _configure_interface_mac(self, if_name, mac):
        confstr = snippets.CONFIGURE_INTERFACE_MAC % (if_name, mac)
        self._edit_running_config(confstr, 'CONFIGURE_INTERFACE_MAC')

    def _configure_interface(self, if_name, vrf_name, ip, netmask):
        confstr = snippets.CONFIGURE_INTERFACE % (if_name, vrf_name,
                                                  ip, netmask)
        self._edit_running_config(confstr, 'CONFIGURE_INTERFACE')

    def _csr_deconfigure_interface(self, port):
        if_name = self._get_interface_name_from_hosting_port(port)
        if if_name and self._interface_exists(if_name):
            self._deconfigure_interface(if_name)
        else:
            LOG.debug("Interface %s not present. Not deconfiguring"), if_name

    def _deconfigure_interface(self, if_name):
        confstr = snippets.DECONFIGURE_INTERFACE % if_name
        self._edit_running_config(confstr, 'DECONFIGURE_INTERFACE')

    def _get_interface_name_from_hosting_port(self, port):
        # The VIF hotplugged into the CSR uses the hosting port, hence we take
        # its mac to identify the interface
        mac = netaddr.EUI(port['hosting_info']['hosting_mac'])
        mac_interface_dict = self._get_VNIC_mapping()
        if mac in mac_interface_dict:
            interface_name = mac_interface_dict[mac]
            LOG.info(_LI("Interface name for hosting port with mac:%(mac)s "
                         "is %(name)s"), {'mac': mac, 'name': interface_name})
            return interface_name

    def _generate_acl_num_from_hosting_port(self, port):
        # In the case of the hotplug driver, we use the interface number
        hosting_port_name = port['hosting_info']['hosting_port_name']
        return hosting_port_name.lstrip("hostingport_")

    def _get_VNIC_mapping(self):
        """Returns a dict of mac addresses(EUI format) and interface names"""
        conn = self._get_connection()
        rpc_obj = conn.get(filter=snippets.GET_VNIC_MAPPING)
        raw_xml = etree.fromstring(rpc_obj.xml)
        formatted_xml = self._prettify(raw_xml)
        root = etree.fromstring(formatted_xml)
        # ToDo: Finalize correct namespace used. Differs among CSR builds.
        # Either namespaces={'ns0': 'urn:ietf:params:netconf:base:1.0'}) OR
        # namespaces={'ns0': 'urn:ietf:params:xml:ns:netconf:base:1.0'})
        subelements = root.xpath(
            '/ns0:rpc-reply/ns0:data/ns0:cli-oper-data-block/ns0:item/'
            'ns0:response',
            namespaces={'ns0': 'urn:ietf:params:xml:ns:netconf:base:1.0'})
        raw_value = subelements[0].text
        raw_list = raw_value.rstrip().split('\n')
        response_dict = {}
        for i in raw_list:
            if 'GigabitEthernet' in i:  # We got a vnic mapping line
                tags = i.split()
                response_dict[netaddr.EUI(tags[2])] = tags[0]
        return response_dict

    def _prettify(self, elem):
        """Return a namespace added and prettified XML string for element."""
        rough_string = ET.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        res = reparsed.toprettyxml(indent="\t")
        return res

    def _csr_add_internalnw_nat_rules(self, ri, port, ex_port):
        vrf_name = self._csr_get_vrf_name(ri)
        num = self._generate_acl_num_from_hosting_port(port)
        acl_no = 'acl_' + str(num)
        internal_cidr = port['ip_cidr']
        internal_net = netaddr.IPNetwork(internal_cidr).network
        netmask = netaddr.IPNetwork(internal_cidr).hostmask
        outer_ip = ex_port['fixed_ips'][0]['ip_address']
        inner_intfc = self._get_interface_name_from_hosting_port(port)
        outer_intfc = self._get_interface_name_from_hosting_port(ex_port)
        self._nat_rules_for_internet_access(acl_no, internal_net,
                                            netmask, inner_intfc,
                                            outer_intfc, vrf_name,
                                            outer_ip)

    def _nat_rules_for_internet_access(self, acl_no, network,
                                       netmask,
                                       inner_intfc,
                                       outer_intfc,
                                       vrf_name,
                                       outer_ip):
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
        :param inner_intfc: (name of) interface connected to the internal
        network
        :param outer_intfc: (name of) interface connected to the external
        network
        :param vrf_name: VRF corresponding to this virtual router
        :return: True if configuration succeeded
        :raises: networking_cisco.plugins.cisco.cfg_agent.cfg_exceptions.
        CSR1kvConfigException
        """
        conn = self._get_connection()
        # Duplicate ACL creation throws error, so checking
        # it first. Remove it in future as this is not common in production
        acl_present = self._check_acl(acl_no, network, netmask)
        if not acl_present:
            confstr = snippets.CREATE_ACL % (acl_no, network, netmask)
            rpc_obj = conn.edit_config(target='running', config=confstr)
            self._check_response(rpc_obj, 'CREATE_ACL')

        #remove acl_ prefix from acl_no to get the hosting port id
        pool_name = 'pool_' + acl_no.lstrip('acl_')
        confstr = snippets.SET_NAT_POOL % (pool_name, outer_ip,
                                           outer_ip, '30')
        rpc_obj = conn.edit_config(target='running', config=confstr)
        self._check_response(rpc_obj, 'SET_NAT_POOL')

        confstr = snippets.SET_DYN_SRC_TRL_POOL % (acl_no, pool_name,
                                                   vrf_name)
        rpc_obj = conn.edit_config(target='running', config=confstr)
        self._check_response(rpc_obj, 'CREATE_SNAT_POOL')

        confstr = snippets.SET_NAT % (inner_intfc, 'inside')
        rpc_obj = conn.edit_config(target='running', config=confstr)
        self._check_response(rpc_obj, 'SET_NAT')

        confstr = snippets.SET_NAT % (outer_intfc, 'outside')
        rpc_obj = conn.edit_config(target='running', config=confstr)
        self._check_response(rpc_obj, 'SET_NAT')

    def _remove_dyn_nat_rule(self, acl_no, outer_intfc_name, vrf_name):
        conn = self._get_connection()
        #remove acl_ prefix from acl_no to get the hosting port id
        pool_name = 'pool_' + acl_no.lstrip('acl_')
        confstr = snippets.SNAT_POOL_CFG % (acl_no, pool_name, vrf_name)
        if self._cfg_exists(confstr):
            confstr = snippets.REMOVE_DYN_SRC_TRL_POOL % (acl_no,
                                                          pool_name,
                                                          vrf_name)
            rpc_obj = conn.edit_config(target='running', config=confstr)
            self._check_response(rpc_obj, 'REMOVE_DYN_SRC_TRL_POOL')

        confstr = snippets.REMOVE_NAT_POOL % pool_name
        rpc_obj = conn.edit_config(target='running', config=confstr)
        self._check_response(rpc_obj, 'SET_NAT_POOL')

        confstr = snippets.REMOVE_ACL % acl_no
        rpc_obj = conn.edit_config(target='running', config=confstr)
        self._check_response(rpc_obj, 'REMOVE_ACL')
