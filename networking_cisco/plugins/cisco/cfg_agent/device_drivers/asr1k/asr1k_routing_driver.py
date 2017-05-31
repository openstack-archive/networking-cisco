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
import netaddr

from oslo_config import cfg

from networking_cisco._i18n import _, _LE, _LI
from networking_cisco import backwards_compatibility as bc
from networking_cisco.plugins.cisco.cfg_agent import cfg_exceptions as cfg_exc
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_cfg_syncer)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_snippets)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.csr1kv import (
    cisco_csr1kv_snippets as snippets)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.csr1kv import (
    iosxe_routing_driver as iosxe_driver)
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routerrole

LOG = logging.getLogger(__name__)


DEVICE_OWNER_ROUTER_GW = bc.constants.DEVICE_OWNER_ROUTER_GW
ROUTER_ROLE_ATTR = routerrole.ROUTER_ROLE_ATTR
ROUTER_ROLE_HA_REDUNDANCY = cisco_constants.ROUTER_ROLE_HA_REDUNDANCY
ROUTER_ROLE_GLOBAL = cisco_constants.ROUTER_ROLE_GLOBAL

ASR1K_DRIVER_OPTS = [
    cfg.BoolOpt('enable_multi_region',
                default=False,
                help=_("If enabled, the agent will maintain a heartbeat "
                       "against its hosting devices. If a device dies and "
                       "recovers, the agent will then trigger a configuration "
                       "resync.")),
    cfg.StrOpt('region_id',
               default='L3FR001',
               help=_("Label to use for this deployments region-id")),
    cfg.ListOpt('other_region_ids',
                default=['L3FR002', 'L3FR003'],
                help=_("Label for other region-ids")),
]

cfg.CONF.register_opts(ASR1K_DRIVER_OPTS, "multi_region")


class ASR1kRoutingDriver(iosxe_driver.IosXeRoutingDriver):

    def __init__(self, **device_params):
        super(ASR1kRoutingDriver, self).__init__(**device_params)
        self._fullsync = False
        self._deployment_id = "zxy"
        self.hosting_device = {'id': device_params.get('id'),
                               'device_id': device_params.get('device_id')}

    # ============== Public functions ==============
    def send_empty_cfg(self):
        LOG.debug("send empty config")
        conf_str = asr1k_snippets.EMPTY_SNIPPET
        self._edit_running_config(conf_str, 'EMPTY_SNIPPET')

    def internal_network_added(self, ri, port):
        if self._is_port_v6(port):
            LOG.debug("Adding IPv6 internal network port: %(port)s for router "
                      "%(r_id)s", {'port': port, 'r_id': ri.id})
            gw_ip = self._get_item(
                port['subnets'], port['ip_info']['subnet_id'],
                'id')['gateway_ip']
            self._create_sub_interface_v6(ri, port, False, gw_ip)
        else:
            # IPv4 handling
            if self._is_global_router(ri):
                # The global router is modeled as the default vrf in the ASR1k.
                # When an external gateway is configured, a normal "internal"
                # interface is created in the default vrf that is in the same
                # subnet as the ext-net.
                LOG.debug("Attaching Global router %(r_id)s to external "
                          "network using port %(p_id)s", {'r_id': ri.id,
                                                          'p_id': port['id']})
                self.external_gateway_added(ri, port)
            else:
                LOG.debug("Adding IPv4 internal network port: %(p_id)s "
                          "for router %(r_id)s", {'p_id': port['id'],
                                                  'r_id': ri.id})
                details = port['change_details']
                LOG.debug('Add - change details: former: %(f_ips)s, old: '
                          '%(o_ips)s, new: %(n_ips)s, current: %(c_ips)s',
                          {'f_ips': [p['fixed_ips'][0]['ip_address'] for p in
                                     details['former_ports']],
                           'o_ips': [p['fixed_ips'][0]['ip_address'] for p in
                                     details['old_ports']],
                           'n_ips': [p['fixed_ips'][0]['ip_address'] for p in
                                     details['new_ports']],
                           'c_ips': [p['fixed_ips'][0]['ip_address'] for p in
                                     details['current_ports']]})
                former_ports = details['former_ports']
                old_ports = details['old_ports']
                if port['ip_info']['is_primary'] is False:
                    # port to be configured as a secondary
                    LOG.debug('Configuring %(ip)s as SECONDARY address for '
                              'port %(p_id)s of router %(r_id)s',
                              {'ip': port['fixed_ips'][0]['ip_address'],
                               'p_id': port['id'], 'r_id': ri.id})
                    self._set_secondary_ipv4(ri, port)
                elif not former_ports:
                    # port is first one on network so must create sub-interface
                    # and configure port as primary
                    LOG.debug('Creating sub-interface and configuring %(ip)s '
                              'as PRIMARY address for first port %(p_id)s on '
                              'network for router %(r_id)s',
                              {'ip': port['fixed_ips'][0]['ip_address'],
                               'p_id': port['id'], 'r_id': ri.id})
                    self._create_sub_interface(ri, port)
                elif old_ports and old_ports[0] == former_ports[0]['id']:
                    # former primary will be deleted so sub-interface already
                    # exists so can just configure port as primary
                    LOG.debug('Configuring %(ip)s as PRIMARY address for port '
                              '%(p_id)s of router %(r_id)s since port '
                              '%(fp_id)s providing former primary address '
                              '%(f_ip)s is to be deleted',
                              {'ip': port['fixed_ips'][0]['ip_address'],
                               'p_id': port['id'], 'r_id': ri.id,
                               'fp_id': former_ports[0]['id'],
                               'f_ip': former_ports[0]['fixed_ips'][0][
                                   'ip_address']})
                    self._set_primary_ipv4(ri, port)
                else:
                    # port is the new primary
                    LOG.debug('Configuring %(ip)s as new PRIMARY address for '
                              'port %(p_id)s of router %(r_id)s',
                              {'ip': port['fixed_ips'][0]['ip_address'],
                               'p_id': port['id'], 'r_id': ri.id})
                    self._set_primary_ipv4(ri, port)
                    # former primary remains and thus must become a secondary
                    LOG.debug('Configuring %(ip)s as SECONDARY address for '
                              'former primary port %(p_id)s of router '
                              '%(r_id)s',
                              {'ip': former_ports[0]['fixed_ips'][0][
                                  'ip_address'],
                               'p_id': former_ports[0]['id'], 'r_id': ri.id})
                    self._set_subnet_info(
                        former_ports[0],
                        former_ports[0]['fixed_ips'][0]['subnet_id'], False)
                    self._set_secondary_ipv4(ri, former_ports[0])

    def internal_network_removed(self, ri, port):
        if self._is_global_router(ri):
            self._remove_sub_interface(port)
        else:
            details = port['change_details']
            LOG.debug('Remove - change details: former: %(f_ips)s, old: '
                      '%(o_ips)s, new: %(n_ips)s, current: %(c_ips)s',
                      {'f_ips': [p['fixed_ips'][0]['ip_address'] for p in
                                 details['former_ports']],
                       'o_ips': [p['fixed_ips'][0]['ip_address'] for p in
                                 details['old_ports']],
                       'n_ips': [p['fixed_ips'][0]['ip_address'] for p in
                                 details['new_ports']],
                       'c_ips': [p['fixed_ips'][0]['ip_address'] for p in
                                 details['current_ports']]})
            former_ports = details['former_ports']
            new_ports = details['new_ports']
            current_ports = details['current_ports']
            if port['ip_info']['is_primary'] is False:
                LOG.debug('Port %(p_id)s that provides %(ip)s used as '
                          'SECONDARY address is to be removed',
                          {'p_id': port['id'],
                           'ip': port['fixed_ips'][0]['ip_address']})
                # since port is a secondary it can just be removed
                if current_ports:
                    # only explicitly de-configure if other ports on same
                    # network remain since the sub-interface removal will
                    # otherwise take care of secondaries automatically
                    LOG.debug('IPv4 address %(ip)s of port %(p_id)s is '
                              'DECONFIGURED as SECONDARY address since router '
                              '%(r_id)s has other ports on the network',
                              {'ip': port['fixed_ips'][0]['ip_address'],
                               'p_id': port['id'], 'r_id': ri.id})
                    self._remove_secondary_ipv4(ri, port)
            elif len(former_ports) == 1:
                # port was the only port on network (thus also the primary)
                if not new_ports:
                    # no new port on that network is added so we can just
                    # remove the sub-interface
                    LOG.debug('Port %(p_id)s that provides %(ip)s used as '
                              'PRIMARY address is to be removed and router '
                              '%(r_id)s has NO new ports NOR remaining ports '
                              'on network so SUB-INTERFACE WILL BE DELETED.',
                              {'p_id': port['id'],
                               'ip': port['fixed_ips'][0]['ip_address'],
                               'r_id': ri.id})
                    self._remove_sub_interface(port)
                else:
                    # the new primary has already be configured as new ports
                    # are processed before ports that have been removed
                    # NOTHING MORE TO DD
                    LOG.debug('The router (%(r_id)s)\'s ONLY port %(p_id)s on '
                              'network that thus provided %(ip)s used as '
                              'PRIMARY address is to be removed. But '
                              'the router has a NEW port %(np_id)s on network '
                              'that with IPv4 %(n_ip)s has already been '
                              'configured as primary so NOTHING MORE TO DO '
                              'HERE.',
                              {'r_id': ri.id, 'p_id': port['id'],
                               'ip': port['fixed_ips'][0]['ip_address'],
                               'np_id': current_ports[0]['id'],
                               'n_ip': current_ports[0]['fixed_ips'][0][
                                   'ip_address']})
            elif not new_ports:
                # port was one of several ports on network but no new ports
                # were added so one of the existing ports (if any exist) will
                # change role from secondary to be the new primary
                if current_ports:
                    LOG.debug('Port %(p_id)s that provides %(ip)s used as '
                              'PRIMARY address is to be removed. But router '
                              '%(r_id)s has other REMAINING port %(fp_id)s '
                              'with IPv4 address %(f_ip)s that is '
                              'RECONFIGURED from secondary to primary.',
                              {'p_id': port['id'],
                               'ip': port['fixed_ips'][0]['ip_address'],
                               'r_id': ri.id,
                               'fp_id': current_ports[0]['id'],
                               'f_ip': current_ports[0]['fixed_ips'][0][
                                   'ip_address']})
                    self._set_subnet_info(
                        current_ports[0],
                        current_ports[0]['fixed_ips'][0]['subnet_id'], False)
                    self._remove_secondary_ipv4(ri, current_ports[0])
                    current_ports[0]['ip_info']['is_primary'] = True
                    self._set_primary_ipv4(ri, current_ports[0])
                else:
                    # no ports on that network remain so we can just remove
                    # the sub-interface
                    LOG.debug('Port %(p_id)s that provides %(ip)s used as '
                              'PRIMARY address is to be removed. Router '
                              '%(r_id)s has NO remaining ports NOR any new '
                              'ports on network so SUB-INTERFACE WILL BE '
                              'DELETED.',
                              {'p_id': port['id'],
                               'ip': port['fixed_ips'][0]['ip_address'],
                               'r_id': ri.id})
                    self._remove_sub_interface(port)
            elif new_ports[0]['id'] == current_ports[0]['id']:
                # one of the new ports is the new primary at it will already
                # have overwritten the old primary so we're done
                # NOTHING MORE TO DO
                LOG.debug('Port %(p_id)s that provides %(ip)s used as '
                          'PRIMARY address is to be removed. But router '
                          '%(r_id)s has a NEW port %(np_id)s with IPv4 '
                          'address %(n_ip)s that has already been'
                          'CONFIGURED AS PRIMARY ',
                          {'p_id': port['id'],
                           'ip': port['fixed_ips'][0]['ip_address'],
                           'r_id': ri.id,
                           'np_id': current_ports[0]['id'],
                           'n_ip': current_ports[0]['fixed_ips'][0][
                               'ip_address']})
            else:
                # no new new port is a new primary so one of the existing
                # ports will change role from secondary to be the new primary
                LOG.debug('Port %(p_id)s that provides %(ip)s used as '
                          'PRIMARY address is to be removed. But router '
                          '%(r_id)s has new ports and a REMAINING port '
                          '%(fp_id)s with IPv4 address %(f_ip)s that is '
                          'RECONFIGURED FROM SECONDARY TO PRIMARY.',
                          {'p_id': port['id'],
                           'ip': port['fixed_ips'][0]['ip_address'],
                           'r_id': ri.id,
                           'fp_id': current_ports[0]['id'],
                           'f_ip': current_ports[0]['fixed_ips'][0][
                               'ip_address']})
                self._set_subnet_info(
                    current_ports[0],
                    current_ports[0]['fixed_ips'][0]['subnet_id'], False)
                self._remove_secondary_ipv4(ri, current_ports[0])
                current_ports[0]['ip_info']['is_primary'] = True
                self._set_primary_ipv4(ri, current_ports[0])

    def external_gateway_added(self, ri, ext_gw_port):
        # global router handles IP assignment, HSRP setup
        # tenant router handles interface creation and default route
        # within VRFs
        if self._is_global_router(ri):
            self._handle_external_gateway_added_global_router(ri, ext_gw_port)
        else:
            self._handle_external_gateway_added_normal_router(ri, ext_gw_port)

    def external_gateway_removed(self, ri, ext_gw_port):
        if self._is_global_router(ri):
            self._remove_sub_interface(ext_gw_port)
        else:
            ex_gw_ip = self._get_item(ext_gw_port['subnets'],
                                      ext_gw_port['ip_info']['subnet_id'],
                                      'id')['gateway_ip']
            if (ex_gw_ip and
                    ext_gw_port['device_owner'] == DEVICE_OWNER_ROUTER_GW):
                # Remove default route via this network's gateway ip
                if self._is_port_v6(ext_gw_port):
                    self._remove_default_route_v6(ri, ex_gw_ip, ext_gw_port)
                else:
                    self._set_nat_pool(ri, ext_gw_port, True)
                    self._remove_default_route(ri, ext_gw_port)

    def floating_ip_added(self, ri, ext_gw_port, floating_ip, fixed_ip):
        self._add_floating_ip_asr1k(ri, ext_gw_port, floating_ip, fixed_ip)

    def floating_ip_removed(self, ri, ext_gw_port, floating_ip, fixed_ip):
        self._remove_floating_ip(ri, ext_gw_port, floating_ip, fixed_ip)

    def disable_internal_network_NAT(self, ri, port, ext_gw_port,
                                     itfc_deleted=False):
        self._remove_internal_nw_nat_rules(ri, [port], ext_gw_port,
                                           itfc_deleted)

    def enable_router_interface(self, ri, port):
        # Enable the router interface
        interface = self._get_interface_name_from_hosting_port(port)
        self._enable_sub_interface(interface)

    def disable_router_interface(self, ri, port=None):
        # Disable the router interface
        if not port:
            ex_gw_port = ri.router.get('gw_port', None)
            if ex_gw_port:
                ext_interface = (self._get_interface_name_from_hosting_port(
                                 ex_gw_port))
                self._disable_sub_interface(ext_interface)
            internal_ports = ri.router.get(bc.constants.INTERFACE_KEY, [])
            for port in internal_ports:
                internal_interface = (
                        self._get_interface_name_from_hosting_port(port))
                self._disable_sub_interface(internal_interface)
        else:
            interface = self._get_interface_name_from_hosting_port(port)
            self._disable_sub_interface(interface)

    def cleanup_invalid_cfg(self, hd, routers):
        cfg_syncer = asr1k_cfg_syncer.ConfigSyncer(routers, self, hd)
        cfg_syncer.delete_invalid_cfg()

    def get_configuration(self):
        return self._get_running_config(split=False)

    # ============== Internal "preparation" functions  ==============
    def _get_vrf_name(self, ri):
        """
        overloaded method for generating a vrf_name that supports
        region_id
        """
        router_id = ri.router_name()[:self.DEV_NAME_LEN]
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region

        if is_multi_region_enabled:
            region_id = cfg.CONF.multi_region.region_id
            vrf_name = "%s-%s" % (router_id, region_id)
        else:
            vrf_name = router_id
        return vrf_name

    def _get_acl_name_from_vlan(self, vlan):
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region

        if is_multi_region_enabled:
            region_id = cfg.CONF.multi_region.region_id
            acl_name = "neutron_acl_%s_%s" % (region_id, vlan)
        else:
            acl_name = "neutron_acl_%s" % vlan
        return acl_name

    def _generate_acl_num_from_port(self, port):
        port_id = port['id'][:8]  # Taking only the first 8 chars
        vlan = self._get_interface_vlan_from_hosting_port(port)
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region

        if is_multi_region_enabled:
            region_id = cfg.CONF.multi_region.region_id
            acl_name = "neutron_acl_%s_%s_%s" % (region_id, vlan, port_id)
        else:
            acl_name = "neutron_acl_%s_%s" % (vlan, port_id)
        return acl_name

    def _get_interface_name_from_hosting_port(self, port):
        """
        Extract the underlying subinterface name for a port
        e.g. Port-channel10.200 or GigabitEthernet0/0/0.500
        """
        try:
            vlan = port['hosting_info']['segmentation_id']
            int_prefix = port['hosting_info']['physical_interface']
            return '%s.%s' % (int_prefix, vlan)
        except KeyError as e:
            params = {'key': e}
            raise cfg_exc.DriverExpectedKeyNotSetException(**params)

    @staticmethod
    def _set_subnet_info(port, subnet_id, is_primary=True):
        ip = next((i['ip_address'] for i in port['fixed_ips']
                   if i['subnet_id'] == subnet_id), None)
        if ip is None:
            # there will be KeyError exception later if this happens
            LOG.error(_LE('Port %(p_id)s lacks IP address on subnet %(s_id)s'),
                      {'p_id': port['id'], 's_id': subnet_id})
            return
        subnet = next(sn for sn in port['subnets'] if sn['id'] == subnet_id)
        prefixlen = netaddr.IPNetwork(subnet['cidr']).prefixlen
        port['ip_info'] = {'subnet_id': subnet_id, 'is_primary': is_primary,
                           'ip_cidr': "%s/%s" % (ip, prefixlen)}

    @staticmethod
    def _get_item(list_containing_dicts_entries, attribute_value,
                  attribute_name='subnet_id'):
        """Searches a list of dicts and returns the first matching entry

        The dict entry returned contains the attribute 'attribute_name' whose
        value equals 'attribute_value'. If no such dict is found in the list
        an empty dict is returned.
        """
        for item in list_containing_dicts_entries:
            if item.get(attribute_name) == attribute_value:
                return item
        return {}

    def _enable_itfcs(self, conn):
        """For ASR we don't need to do anything"""
        return True

    def _handle_external_gateway_added_global_router(self, ri, ext_gw_port):
        # TODO(bobmel): Get the HA virtual IP correctly
        # NOTE(sridar): This seems to work fine. Keeping this todo until
        #               more testing.
        subnet_id = ext_gw_port['ip_info']['subnet_id']
        if self._is_port_v6(ext_gw_port):
            LOG.debug("Adding IPv6 external network port: %(port)s on "
                      "subnet: (subnet)s for global router %(r_id)s",
                      {'port': ext_gw_port['id'], 'subnet': subnet_id,
                       'r_id': ri.id})
            virtual_gw_port = ext_gw_port[ha.HA_INFO]['ha_port']
            sub_itfc_ip = self._get_item(virtual_gw_port['fixed_ips'],
                                         subnet_id)['ip_address']
            self._create_sub_interface_v6(ri, ext_gw_port, True, sub_itfc_ip)
        else:
            LOG.debug("Adding IPv4 external network port: %(port)s on "
                      "subnet: (subnet)s for global router %(r_id)s",
                      {'port': ext_gw_port['id'], 'subnet': subnet_id,
                       'r_id': ri.id})
            self._create_external_sub_interface(ri, ext_gw_port)

    def _handle_external_gateway_added_normal_router(self, ri, ext_gw_port):
        # Default routes are mapped to tenant router VRFs. Global Router
        # is not aware of tenant routers with ext network assigned. Thus,
        # default route must be handled per tenant router.
        ex_gw_ip = self._get_item(
            ext_gw_port['subnets'], ext_gw_port['ip_info']['subnet_id'],
            'id')['gateway_ip']

        sub_interface = self._get_interface_name_from_hosting_port(ext_gw_port)
        vlan_id = self._get_interface_vlan_from_hosting_port(ext_gw_port)
        if (self._fullsync and
                int(vlan_id) in self._existing_cfg_dict['interfaces']):
            LOG.debug("Sub-interface already exists, will not create it")
        else:
            LOG.debug("Adding IPv4 external network port: %(port)s for tenant "
                      "router %(r_id)s", {'port': ext_gw_port['id'],
                                          'r_id': ri.id})
            if ri.router['admin_state_up'] and ext_gw_port['admin_state_up']:
                self._enable_sub_interface(sub_interface)
            else:
                self._disable_sub_interface(sub_interface)

        if ex_gw_ip:
            # Set default route via this network's gateway ip
            if self._is_port_v6(ext_gw_port):
                self._add_default_route_v6(ri, ex_gw_ip, ext_gw_port)
            else:
                self._set_nat_pool(ri, ext_gw_port, False)
                self._add_default_route(ri, ext_gw_port)

    def _create_sub_interface(self, ri, port):
        vlan = self._get_interface_vlan_from_hosting_port(port)
        if (self._fullsync and
                int(vlan) in self._existing_cfg_dict['interfaces']):
            LOG.info(_LI("Sub-interface already exists, will not create it"))
            return
        vrf_name = self._get_vrf_name(ri)
        net_mask = netaddr.IPNetwork(port['ip_info']['ip_cidr']).netmask
        # get port's ip address for the subnet we're processing
        ip = self._get_item(port['fixed_ips'],
                            port['ip_info']['subnet_id'])['ip_address']
        sub_interface = self._get_interface_name_from_hosting_port(port)
        self._do_create_sub_interface(sub_interface, vlan, vrf_name, ip,
                                      net_mask)
        self._conditionally_add_ha_hsrp_asr1k(ri, port)

    def _create_external_sub_interface(self, ri, port):
        vlan = self._get_interface_vlan_from_hosting_port(port)
        if (self._fullsync and
                int(vlan) in self._existing_cfg_dict['interfaces']):
            LOG.info(_LI("Sub-interface already exists, will not create it"))
            return
        net_mask = netaddr.IPNetwork(port['ip_info']['ip_cidr']).netmask
        # get port's ip address for the subnet we're processing
        ip = self._get_item(port['fixed_ips'],
                            port['ip_info']['subnet_id'])['ip_address']
        sub_interface = self._get_interface_name_from_hosting_port(port)
        if port['ip_info']['is_primary'] is True:
            self._do_create_external_sub_interface(sub_interface, vlan, ip,
                                                   net_mask)
        else:
            # this will only happen for global routers or when a tenant
            # router is connected to multiple subnets on the same network
            self._do_set_secondary(sub_interface, ip, net_mask)
        self._conditionally_add_ha_hsrp_asr1k(ri, port)

    def _set_primary_ipv4(self, ri, port):
        sub_interface = self._get_interface_name_from_hosting_port(port)
        ip = self._get_item(port['fixed_ips'],
                            port['ip_info']['subnet_id'])['ip_address']
        net_mask = netaddr.IPNetwork(port['ip_info']['ip_cidr']).netmask
        self._do_set_primary(sub_interface, ip, net_mask)
        self._conditionally_add_ha_hsrp_asr1k(ri, port)

    def _set_secondary_ipv4(self, ri, port):
        net_mask = netaddr.IPNetwork(
            port['ip_info']['ip_cidr']).netmask
        # get port's ip address for the subnet we're processing
        subnet_id = port['ip_info']['subnet_id']
        ip = self._get_item(port['fixed_ips'], subnet_id)['ip_address']
        sub_interface = self._get_interface_name_from_hosting_port(
            port)
        self._do_set_secondary(sub_interface, ip, net_mask)
        self._conditionally_add_ha_hsrp_asr1k(ri, port)

    def _remove_secondary_ipv4(self, ri, port):
        net_mask = netaddr.IPNetwork(
            port['ip_info']['ip_cidr']).netmask
        # get port's ip address for the subnet we're processing
        subnet_id = port['ip_info']['subnet_id']
        ip = self._get_item(port['fixed_ips'], subnet_id)['ip_address']
        sub_interface = self._get_interface_name_from_hosting_port(
            port)
        self._do_unset_secondary(sub_interface, ip, net_mask)
        self._conditionally_remove_ha_hsrp_asr1k(ri, port, sub_interface)

    def _do_create_sub_interface(self, sub_interface, vlan_id, vrf_name, ip,
                                 mask):
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        if is_multi_region_enabled:
            region_id = cfg.CONF.multi_region.region_id
            conf_str = asr1k_snippets.CREATE_SUBINTERFACE_REGION_ID_WITH_ID % (
                sub_interface, region_id, vlan_id, vrf_name, ip, mask)
        else:
            conf_str = asr1k_snippets.CREATE_SUBINTERFACE_WITH_ID % (
                sub_interface, vlan_id, vrf_name, ip, mask)
        self._edit_running_config(conf_str, 'CREATE_SUBINTERFACE_WITH_ID')

    def _do_create_external_sub_interface(self, sub_interface, vlan_id, ip,
                                          mask):
        is_multi_region_enabled = cfg.CONF.multi_region.enable_multi_region
        if is_multi_region_enabled:
            region_id = cfg.CONF.multi_region.region_id
            conf_str = (
                asr1k_snippets.CREATE_SUBINTERFACE_EXT_REGION_ID_WITH_ID % (
                    sub_interface, region_id, vlan_id, ip, mask))
        else:
            conf_str = (
                asr1k_snippets.CREATE_SUBINTERFACE_EXTERNAL_WITH_ID % (
                    sub_interface, vlan_id, ip, mask))
        self._edit_running_config(conf_str, 'CREATE_SUBINTERFACE_WITH_ID')

    def _do_set_primary(self, sub_interface, ip, mask):
        conf_str = (
            asr1k_snippets.SET_INTERFACE_PRIMARY_IP % (
                    sub_interface, ip, mask))
        self._edit_running_config(conf_str, 'SET_SUBINTERFACE_PRIMARY_IP')

    def _do_unset_primary(self, sub_interface, ip, mask):
        conf_str = (
            asr1k_snippets.REMOVE_INTERFACE_PRIMARY_IP % (
                sub_interface, ip, mask))
        self._edit_running_config(conf_str, 'REMOVE_SUBINTERFACE_PRIMARY_IP')

    def _do_set_secondary(self, sub_interface, ip, mask):
        conf_str = (
            asr1k_snippets.SET_INTERFACE_SECONDARY_IP % (
                    sub_interface, ip, mask))
        self._edit_running_config(conf_str, 'SET_SUBINTERFACE_SECONDARY_IP')

    def _do_unset_secondary(self, sub_interface, ip, mask):
        conf_str = (
            asr1k_snippets.REMOVE_INTERFACE_SECONDARY_IP % (
                sub_interface, ip, mask))
        self._edit_running_config(conf_str, 'REMOVE_SUBINTERFACE_SECONDARY_IP')

    def _enable_sub_interface(self, sub_interface):
        LOG.debug("Enabling network sub interface: %s", sub_interface)
        conf_str = snippets.ENABLE_INTF % sub_interface
        self._edit_running_config(conf_str, 'ENABLE_INTF')

    def _disable_sub_interface(self, sub_interface):
        LOG.debug("Disabling network sub interface: %s", sub_interface)
        conf_str = snippets.DISABLE_INTF % sub_interface
        self._edit_running_config(conf_str, 'DISABLE_INTF')

    def _set_nat_pool(self, ri, gw_port, is_delete):
        vrf_name = self._get_vrf_name(ri)
        if ri.router.get(ROUTER_ROLE_ATTR) == ROUTER_ROLE_HA_REDUNDANCY:
            the_port = gw_port[ha.HA_INFO]['ha_port']
        else:
            the_port = gw_port
        subnet_id = gw_port['ip_info']['subnet_id']
        fixed_ip = self._get_item(the_port['fixed_ips'], subnet_id)
        pool_ip = fixed_ip['ip_address']
        pool_ip_prefix_len = fixed_ip['prefixlen']
        #TODO(ebobmel) We need to modify the pool name generation if we
        #              will have multiple NAT pools per VRF
        pool_name = "%s_nat_pool" % (vrf_name)
        pool_net = "%s/%s" % (pool_ip, pool_ip_prefix_len)
        pool_net = netaddr.IPNetwork(pool_net)
        if self._fullsync and pool_ip in self._existing_cfg_dict['pools']:
            LOG.info(_LI("Pool already exists, skipping"))
            return

        try:
            if is_delete:
                conf_str = asr1k_snippets.DELETE_NAT_POOL % (
                    pool_name, pool_ip, pool_ip, pool_net.netmask)
                # TODO(update so that hosting device name is passed down)
                self._edit_running_config(conf_str, 'DELETE_NAT_POOL')
            else:
                conf_str = asr1k_snippets.CREATE_NAT_POOL % (
                    pool_name, pool_ip, pool_ip, pool_net.netmask)
                # TODO(update so that hosting device name is passed down)
                self._edit_running_config(conf_str, 'CREATE_NAT_POOL')
        #except cfg_exc.CSR1kvConfigException as cse:
        except Exception as cse:
            LOG.error(_LE("Temporary disable NAT_POOL exception handling: %s"),
                      cse)

    def _add_default_route(self, ri, ext_gw_port):
        if self._fullsync and (ri.router_id in
                               self._existing_cfg_dict['routes']):
            LOG.debug("Default route already exists, skipping")
            return
        ext_gw_ip = self._get_item(
            ext_gw_port['subnets'], ext_gw_port['ip_info']['subnet_id'],
            'id')['gateway_ip']
        if ext_gw_ip:
            vrf_name = self._get_vrf_name(ri)
            out_itfc = self._get_interface_name_from_hosting_port(ext_gw_port)
            conf_str = asr1k_snippets.SET_DEFAULT_ROUTE_WITH_INTF % (
                vrf_name, out_itfc, ext_gw_ip)
            self._edit_running_config(conf_str, 'SET_DEFAULT_ROUTE_WITH_INTF')

    def _remove_default_route(self, ri, ext_gw_port):
        ext_gw_ip = self._get_item(
            ext_gw_port['subnets'], ext_gw_port['ip_info']['subnet_id'],
            'id')['gateway_ip']
        if ext_gw_ip:
            vrf_name = self._get_vrf_name(ri)
            out_itfc = self._get_interface_name_from_hosting_port(ext_gw_port)
            conf_str = asr1k_snippets.REMOVE_DEFAULT_ROUTE_WITH_INTF % (
                vrf_name, out_itfc, ext_gw_ip)
            self._edit_running_config(conf_str,
                                      'REMOVE_DEFAULT_ROUTE_WITH_INTF')

    def _conditionally_add_ha_hsrp_asr1k(self, ri, port):
        if ri.router.get(ha.ENABLED, False):
            if port.get(ha.HA_INFO) is None:
                # We are missing HA data, candidate for retrying
                params = {'r_id': ri.router_id, 'p_id': port['id'],
                          'port': port}
                raise cfg_exc.HAParamsMissingException(**params)
        else:
            return
        priority = None
        if ri.router.get(ROUTER_ROLE_ATTR) in (ROUTER_ROLE_HA_REDUNDANCY,
                                               ROUTER_ROLE_GLOBAL):
            for router in ri.router[ha.DETAILS][ha.REDUNDANCY_ROUTERS]:
                if ri.router['id'] == router['id']:
                    priority = router[ha.PRIORITY]
        else:
            priority = ri.router[ha.DETAILS][ha.PRIORITY]
        port_ha_info = port[ha.HA_INFO]
        group = port_ha_info['group']
        subnet_id = port['ip_info']['subnet_id']
        vip = self._get_item(port_ha_info['ha_port']['fixed_ips'],
                             subnet_id)['ip_address']
        vlan = port['hosting_info']['segmentation_id']
        if vip and group and priority:
            is_primary = port['ip_info']['is_primary']
            sub_interface = self._get_interface_name_from_hosting_port(port)
            self._do_add_ha_hsrp_asr1k(sub_interface, priority, group, vip,
                                       vlan, is_primary)

    def _conditionally_remove_ha_hsrp_asr1k(self, ri, port, sub_interface):
        if ri.router.get(ha.ENABLED, False):
            if port.get(ha.HA_INFO) is None:
                ip = self._get_item(port['fixed_ips'],
                                    port['ip_info']['subnet_id'])['ip_address']
                LOG.warning(
                    _LI("Could not remove HSRP VIP address for port %(p_id)s "
                        "with interface IP %(addr)s because plugin did not "
                        "provide needed information. Manual removal by admin "
                        "required."), {'p_id': port['id'], 'addr': ip})
                return
        else:
            return
        subnet_id = port['ip_info']['subnet_id']
        is_primary = port['ip_info']['is_primary']
        port_ha_info = port[ha.HA_INFO]
        group = port_ha_info['group']
        hsrp_ip = self._get_item(port_ha_info['ha_port']['fixed_ips'],
                                 subnet_id)['ip_address']
        self._do_remove_ha_hsrp_asr1k(sub_interface, group, hsrp_ip,
                                      is_primary=is_primary)

    def _do_add_ha_hsrp_asr1k(self, sub_interface, priority, group, vip, vlan,
                              is_primary=True):
        if is_primary is True:
            conf_str = asr1k_snippets.SET_INTC_ASR_HSRP_EXTERNAL % (
                sub_interface, group, priority, group, vip, group, group,
                group, vlan)
            self._edit_running_config(conf_str, 'SET_INTC_ASR_HSRP_EXTERNAL')
        else:
            conf_str = asr1k_snippets.SET_INTC_ASR_SECONDARY_HSRP_EXTERNAL % (
                sub_interface, group, vip)
            self._edit_running_config(conf_str,
                                      'SET_INTC_ASR_SECONDARY_HSRP_EXTERNAL')

    def _do_remove_ha_hsrp_asr1k(self, sub_interface, group, ip,
                                 is_primary=True):
        if is_primary is False:
            conf_str = (asr1k_snippets.REMOVE_INTC_ASR_SECONDARY_HSRP_EXTERNAL
                        % (sub_interface, group, ip))
            self._edit_running_config(
                conf_str, 'REMOVE_INTC_ASR_SECONDARY_HSRP_EXTERNAL')
        else:
            LOG.debug('Standby IP address is not secondary so not removing '
                      'that configuration')

    def _create_sub_interface_v6(self, ri, port, is_external=False, gw_ip=""):
        if self._v6_port_needs_config(port) is not True:
            return
        vrf_name = self._get_vrf_name(ri)
        ip_cidr = port['ip_info']['ip_cidr']
        vlan = self._get_interface_vlan_from_hosting_port(port)
        sub_interface = self._get_interface_name_from_hosting_port(port)
        self._do_create_sub_interface_v6(sub_interface, vlan, vrf_name,
                                         ip_cidr, is_external)
        # Always do HSRP
        self._add_ha_HSRP_v6(ri, port, ip_cidr, is_external)

    def _do_create_sub_interface_v6(self, sub_interface, vlan_id, vrf_name,
                                    ip_cidr, is_external=False):
        if is_external is True:
            conf_str = asr1k_snippets.CREATE_SUBINTERFACE_V6_NO_VRF_WITH_ID % (
                sub_interface, self._deployment_id, vlan_id,
                ip_cidr)
        else:
            conf_str = asr1k_snippets.CREATE_SUBINTERFACE_V6_WITH_ID % (
                sub_interface, self._deployment_id, vlan_id,
                vrf_name, ip_cidr)
        self._edit_running_config(conf_str, '%s CREATE_SUBINTERFACE_V6' %
                                  self.hosting_device['name'])

    def _add_default_route_v6(self, ri, gw_ip, gw_port):
        vrf_name = self._get_vrf_name(ri)
        conf_str = asr1k_snippets.SET_DEFAULT_ROUTE_V6_WITH_INTF % (
            vrf_name, gw_ip)
        self._edit_running_config(conf_str, 'SET_DEFAULT_ROUTE_V6_WITH_INTF')

    def _remove_default_route_v6(self, ri, gw_ip, gw_port):
        vrf_name = self._get_vrf_name(ri)
        sub_interface = self._get_interface_name_from_hosting_port(gw_port)
        self._remove_default_static_route_v6(gw_ip, vrf_name, sub_interface)

    def _remove_default_static_route_v6(self, gw_ip, vrf, out_intf):
        conf_str = asr1k_snippets.REMOVE_DEFAULT_ROUTE_V6_WITH_INTF % (
            vrf, gw_ip)
        self._edit_running_config(conf_str,
                                  'REMOVE_DEFAULT_ROUTE_V6_WITH_INTF')

    def _add_ha_HSRP_v6(self, ri, port, ip, is_external=False):
        if self._v6_port_needs_config(port) is not True:
            return
        vlan = self._get_interface_vlan_from_hosting_port(port)
        group = vlan
        asr_ent = self.hosting_device
        priority = asr_ent['order']
        sub_interface = self._get_interface_name_from_hosting_port(port)
        self._set_ha_HSRP_v6(sub_interface, priority, group, is_external)

    def _port_needs_config(self, port):
        #ToDo(Hareesh): Need to check this!
        if not self._port_is_hsrp(port):
            LOG.debug("Ignoring non-HSRP interface")
            return False
        asr_ent = self._get_asr_ent_from_port(port)
        if asr_ent['name'] != self.hosting_device['name']:
            LOG.debug("Ignoring interface for non-target ASR1k")
            return False
        return True

    @staticmethod
    def _port_is_hsrp(port):
        hsrp_types = [bc.constants.DEVICE_OWNER_ROUTER_HA_INTF]
        return port['device_owner'] in hsrp_types

    @staticmethod
    def _is_global_router(ri):
        return (ri.router.get(ROUTER_ROLE_ATTR) ==
                cisco_constants.ROUTER_ROLE_GLOBAL)

    @classmethod
    def _is_port_v6(cls, port):
        cidr = cls._get_item(port['subnets'],
                             port['ip_info']['subnet_id'], 'id')['cidr']
        return netaddr.IPNetwork(cidr).version == 6

    @staticmethod
    def _get_hsrp_grp_num_from_ri(ri):
        return ri.router['ha_info']['group']

    def _add_internal_nw_nat_rules(self, ri, port, ext_port):
        vrf_name = self._get_vrf_name(ri)
        acl_no = self._generate_acl_num_from_port(port)
        internal_cidr = port['ip_info']['ip_cidr']
        internal_net = netaddr.IPNetwork(internal_cidr).network
        net_mask = netaddr.IPNetwork(internal_cidr).hostmask
        inner_itfc = self._get_interface_name_from_hosting_port(port)
        outer_itfc = self._get_interface_name_from_hosting_port(ext_port)
        self._nat_rules_for_internet_access(acl_no, internal_net,
                                            net_mask, inner_itfc,
                                            outer_itfc, vrf_name)

    def _nat_rules_for_internet_access(self, acl_no, network, netmask,
                                       inner_itfc, outer_itfc, vrf_name):
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
        acl_present = self._check_acl(acl_no, network, netmask)
        if not acl_present:
            conf_str = snippets.CREATE_ACL % (acl_no, network, netmask)
            self._edit_running_config(conf_str, 'CREATE_ACL')

        pool_name = "%s_nat_pool" % vrf_name
        conf_str = asr1k_snippets.SET_DYN_SRC_TRL_POOL % (acl_no, pool_name,
                                                          vrf_name)
        try:
            self._edit_running_config(conf_str, 'SET_DYN_SRC_TRL_POOL')
        except Exception as dyn_nat_e:
            LOG.info(_LI("Ignore exception for SET_DYN_SRC_TRL_POOL: %s. "
                         "The config seems to be applied properly but netconf "
                         "seems to report an error."), dyn_nat_e)

        conf_str = snippets.SET_NAT % (inner_itfc, 'inside')
        self._edit_running_config(conf_str, 'SET_NAT')

        conf_str = snippets.SET_NAT % (outer_itfc, 'outside')
        self._edit_running_config(conf_str, 'SET_NAT')

    def _remove_internal_nw_nat_rules(self, ri, ports, ext_port,
                                      intf_deleted=False):
        """
        Removes the NAT rules already configured when an internal network is
        removed.

        :param ri          -- router-info object
        :param ports       -- list of affected ports where network nat rules
                              was affected
        :param ext_port    -- external facing port
        :param intf_deleted-- If True, indicates that the subinterface was
                              deleted.
        """
        acls = []
        # first disable nat in all inner ports
        for port in ports:
            in_itfc_name = self._get_interface_name_from_hosting_port(port)
            acls.append(self._generate_acl_num_from_port(port))
            is_alone = len(port['change_details']['current_ports']) == 1
            if not intf_deleted and is_alone is True:
                self._remove_interface_nat(in_itfc_name, 'inside')
        # There is a possibility that the dynamic NAT rule cannot be removed
        # from the running config, if there is still traffic in the inner
        # interface causing a rule to be present in the NAT translation
        # table. For this we give 2 seconds for the 'inside NAT rule' to
        # expire and then clear the NAT translation table manually. This can
        # be costly and hence is not enabled here, pending further
        # sinvestigation.

        # LOG.debug("Sleep for 2 seconds before clearing NAT rules")
        # time.sleep(2)
        # clear the NAT translation table
        # self._remove_dyn_nat_translations()

        # remove dynamic nat rules and acls
        vrf_name = self._get_vrf_name(ri)
        ext_itfc_name = self._get_interface_name_from_hosting_port(ext_port)
        for acl in acls:
            self._remove_dyn_nat_rule(acl, ext_itfc_name, vrf_name)

    def _remove_dyn_nat_rule(self, acl_no, outer_itfc_name, vrf_name):
        try:
            pool_name = "%s_nat_pool" % (vrf_name)
            confstr = (asr1k_snippets.REMOVE_DYN_SRC_TRL_POOL %
                (acl_no, pool_name, vrf_name))
            self._edit_running_config(confstr, 'REMOVE_DYN_SRC_TRL_POOL')
        except cfg_exc.CSR1kvConfigException as cse:
            LOG.error(_LE("temporary disable REMOVE_DYN_SRC_TRL_POOL"
                      " exception handling: %s"), (cse))

        conf_str = snippets.REMOVE_ACL % acl_no
        self._edit_running_config(conf_str, 'REMOVE_ACL')

    def _add_floating_ip_asr1k(self, ri, ex_gw_port, floating_ip, fixed_ip):
        vrf_name = self._get_vrf_name(ri)
        self._do_add_floating_ip_asr1k(floating_ip, fixed_ip, vrf_name,
                                       ex_gw_port)

    def _do_add_floating_ip_asr1k(self, floating_ip, fixed_ip, vrf,
                                  ex_gw_port):
        """
        To implement a floating ip, an ip static nat is configured in the
        underlying router ex_gw_port contains data to derive the vlan
        associated with related subnet for the fixed ip.  The vlan in turn
        is applied to the redundancy parameter for setting the IP NAT.
        """
        vlan = ex_gw_port['hosting_info']['segmentation_id']
        hsrp_grp = ex_gw_port[ha.HA_INFO]['group']

        LOG.debug("add floating_ip: %(fip)s, fixed_ip: %(fixed_ip)s, "
                  "vrf: %(vrf)s, ex_gw_port: %(port)s",
                  {'fip': floating_ip, 'fixed_ip': fixed_ip, 'vrf': vrf,
                   'port': ex_gw_port})

        confstr = (asr1k_snippets.SET_STATIC_SRC_TRL_NO_VRF_MATCH %
            (fixed_ip, floating_ip, vrf, hsrp_grp, vlan))
        self._edit_running_config(confstr, 'SET_STATIC_SRC_TRL_NO_VRF_MATCH')

    def _remove_floating_ip(self, ri, ext_gw_port, floating_ip, fixed_ip):
        vrf_name = self._get_vrf_name(ri)
        self._asr_do_remove_floating_ip(floating_ip,
                                        fixed_ip,
                                        vrf_name,
                                        ext_gw_port)

    def _asr_do_remove_floating_ip(self, floating_ip,
                                   fixed_ip, vrf, ex_gw_port):
        vlan = ex_gw_port['hosting_info']['segmentation_id']
        hsrp_grp = ex_gw_port[ha.HA_INFO]['group']

        confstr = (asr1k_snippets.REMOVE_STATIC_SRC_TRL_NO_VRF_MATCH %
            (fixed_ip, floating_ip, vrf, hsrp_grp, vlan))
        self._edit_running_config(confstr,
                                  'REMOVE_STATIC_SRC_TRL_NO_VRF_MATCH')
