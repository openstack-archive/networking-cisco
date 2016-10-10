# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
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

import re

from oslo_config import cfg
from oslo_log import log as logging

from neutron.common import constants as l3_constants
from neutron.common import exceptions as n_exc
from neutron.extensions import l3
from neutron import manager
from neutron.plugins.common import constants as svc_constants

from networking_cisco._i18n import _, _LI, _LE
from networking_cisco.plugins.cisco.device_manager.plugging_drivers import (
    hw_vlan_trunking_driver as hw_vlan)
from networking_cisco.plugins.cisco.extensions import routerrole

LOG = logging.getLogger(__name__)


APIC_OWNED = 'apic_owned_'
APIC_SNAT_SUBNET = 'host-snat-pool-for-internal-use'
APIC_SNAT_NET = 'host-snat-network-for-internal-use'
EXTERNAL_GW_INFO = l3.EXTERNAL_GW_INFO
UUID_REGEX = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
DEVICE_OWNER_ROUTER_GW = l3_constants.DEVICE_OWNER_ROUTER_GW
DEVICE_OWNER_ROUTER_INTF = l3_constants.DEVICE_OWNER_ROUTER_INTF
ROUTER_ROLE_ATTR = routerrole.ROUTER_ROLE_ATTR


ACI_ASR1K_DRIVER_OPTS = [
    cfg.StrOpt('aci_transit_nets_config_file', default=None,
               help=_("ACI with ASR transit network configuration file.")),
]

cfg.CONF.register_opts(ACI_ASR1K_DRIVER_OPTS, "general")

DEFAULT_EXT_DICT = {'gateway_ip': '1.103.2.254',
                    'cidr_exposed': '1.103.2.1/24'}


class AciDriverConfigInvalidFileFormat(n_exc.BadRequest):
    message = _("The ACI Driver config file format is invalid")


class AciDriverConfigMissingGatewayIp(n_exc.BadRequest):
    message = _("The ACI Driver config is missing a gateway_ip "
                "parameter for %(ext_net)s.")


class AciDriverConfigMissingCidrExposed(n_exc.BadRequest):
    message = _("The ACI Driver config is missing a cidr_exposed "
                "parameter for %(ext_net)s.")


class AciDriverConfigMissingSegmentationId(n_exc.BadRequest):
    message = _("The ACI Driver config is missing a segmentation_id "
                "parameter for %(ext_net)s.")


class AciDriverNoAciDriverInstalledOrConfigured(n_exc.BadRequest):
    message = _("The ACI plugin driver is either not installed or "
                "the neutron configuration is incorrect.")


class AciVLANTrunkingPlugDriver(hw_vlan.HwVLANTrunkingPlugDriver):
    """Driver class for Cisco ACI-based devices.

    The driver works with VLAN segmented Neutron networks. It
    determines which workflow is active (GBP or Neutron), and
    uses that implementation to get the information needed for
    the networks between the hosting device and the ACI fabric.
    """
    # once initialized _device_network_interface_map is dictionary
    _device_network_interface_map = None
    _apic_driver = None
    _l3_plugin = None

    def __init__(self):
        super(AciVLANTrunkingPlugDriver, self).__init__()
        self._cfg_file = cfg.CONF.general.aci_transit_nets_config_file
        self._get_ext_net_name = None
        self._default_ext_dict = DEFAULT_EXT_DICT
        self._transit_nets_cfg = {}
        self._get_vrf_context = None

    def _sanity_check_config(self, config):
        for network in config.keys():
            if config.get(network).get('gateway_ip') is None:
                raise AciDriverConfigMissingGatewayIp(ext_net=network)
            if config.get(network).get('cidr_exposed') is None:
                raise AciDriverConfigMissingCidrExposed(ext_net=network)

    @property
    def transit_nets_cfg(self):
        if self._cfg_file:
            networks_dict = open(self._cfg_file, 'r').read()
            try:
                self._transit_nets_cfg = eval(networks_dict)
                self._sanity_check_config(self._transit_nets_cfg)
            except SyntaxError:
                raise AciDriverConfigInvalidFileFormat
        else:
            self._transit_nets_cfg = {}
        return self._transit_nets_cfg

    @property
    def get_ext_net_name(self):
        # Ensure that we have an APIC driver
        if self.apic_driver:
            return self._get_ext_net_name

    @property
    def get_vrf_context(self):
        if self.apic_driver:
            return self._get_vrf_context

    def _get_vrf_context_gbp(self, context, router_id, port_db):
        l3p_id = self.apic_driver.gbp_plugin.get_l3p_id_from_router_id(
            context.elevated(), router_id)
        if l3p_id:
            return {'vrf_id': l3p_id,
                    'vrf_name': l3p_id,
                    'vrf_tenant': None}

    def _get_vrf_context_neutron(self, context, router_id, port_db):
        router = self.l3_plugin.get_router(context, router_id)
        vrf_info = self.apic_driver.get_router_vrf_and_tenant(router)
        details = {}
        if self.apic_driver.per_tenant_context:
            details['vrf_id'] = router['tenant_id']
        else:
            details['vrf_id'] = str(vrf_info['aci_name'])
        details['vrf_name'] = vrf_info['aci_name']
        details['vrf_tenant'] = vrf_info['aci_tenant']
        return details

    def _get_external_network_dict(self, context, port_db):
        """Get external network information

        Get the information about the external network,
        so that it can be used to create the hidden port,
        subnet, and network.
        """
        if port_db.device_owner == DEVICE_OWNER_ROUTER_GW:
            network = self._core_plugin.get_network(context,
                port_db.network_id)
        else:
            router = self.l3_plugin.get_router(context,
                port_db.device_id)
            ext_gw_info = router.get(EXTERNAL_GW_INFO)
            if not ext_gw_info:
                return {}, None
            network = self._core_plugin.get_network(context,
                ext_gw_info['network_id'])

        # network names in GBP workflow need to be reduced, since
        # the network may contain UUIDs
        external_network = self.get_ext_net_name(network['name'])
        # TODO(tbachman): see if we can get rid of the default
        transit_net = self.transit_nets_cfg.get(
            external_network) or self._default_ext_dict
        transit_net['network_name'] = external_network
        return transit_net, network

    @property
    def l3_plugin(self):
        if not self._l3_plugin:
            self._l3_plugin = manager.NeutronManager.get_service_plugins().get(
                svc_constants.L3_ROUTER_NAT)
        return self._l3_plugin

    @property
    def apic_driver(self):
        """Get APIC driver

        There are different drivers for the GBP workflow
        and Neutron workflow for APIC. First see if the GBP
        workflow is active, and if so get the APIC driver for it.
        If the GBP service isn't installed, try to get the driver
        from the Neutron (APIC ML2) workflow.
        """
        if not self._apic_driver:
            try:
                self._apic_driver = (
                    manager.NeutronManager.get_service_plugins()[
                        'GROUP_POLICY'].policy_driver_manager.policy_drivers[
                            'apic'].obj)
                self._get_ext_net_name = self._get_ext_net_name_gbp
                self._get_vrf_context = self._get_vrf_context_gbp
            except KeyError:
                    LOG.info(_LI("GBP service plugin not present -- will "
                                 "try APIC ML2 plugin."))
            if not self._apic_driver:
                try:
                    self._apic_driver = (
                        self._core_plugin.mechanism_manager.mech_drivers[
                            'cisco_apic_ml2'].obj)
                    self._get_ext_net_name = self._get_ext_net_name_neutron
                    self._get_vrf_context = self._get_vrf_context_neutron
                except KeyError:
                    LOG.error(_LE("APIC ML2 plugin not present: "
                                  "no APIC ML2 driver could be found."))
                    raise AciDriverNoAciDriverInstalledOrConfigured()
        return self._apic_driver

    def _snat_subnet_for_ext_net(self, context, subnet, net):
        """Determine if an SNAT subnet is for this external network.

        This method determines if a given SNAT subnet is intended for
        the passed external network.

        For APIC ML2/Neutron workflow, SNAT subnets are created on
        a separate network from the external network. The association
        with an external network is made by putting the name of the
        external network in the name of the SNAT network name, using
        a well-known prefix.
        """
        if subnet['network_id'] == net['id']:
            return True

        network = self._core_plugin.get_network(
            context.elevated(), subnet['network_id'])
        ext_net_name = network['name']
        if (APIC_SNAT_NET + '-') in ext_net_name:
            # This is APIC ML2 mode -- we need to strip the prefix
            ext_net_name = ext_net_name[len(APIC_SNAT_NET + '-'):]
            if net['id'] == ext_net_name:
                return True
        return False

    def _add_snat_info(self, context, router, net, hosting_info):
        if net:
            snat_ips = self.apic_driver.get_snat_ip_for_vrf(context,
                router['tenant_id'], net)
            snat_subnets = self._core_plugin.get_subnets(
                context.elevated(), {'name': [APIC_SNAT_SUBNET]})
            if snat_subnets and snat_ips:
                hosting_info['snat_subnets'] = []
                for subnet in snat_subnets:
                    # Skip any SNAT subnets that aren't on this external
                    # network
                    if not self._snat_subnet_for_ext_net(context, subnet, net):
                        continue
                    snat_subnet = {'id': router['tenant_id'],
                                   'ip': snat_ips['host_snat_ip'],
                                   'cidr': subnet['cidr']}
                    hosting_info['snat_subnets'].append(snat_subnet)

    def extend_hosting_port_info(self, context, port_db, hosting_device,
                                 hosting_info):
        """Get the segmenetation ID and interface

        This extends the hosting info attribute with the segmentation ID
        and physical interface used on the external router to connect to
        the ACI fabric. The segmentation ID should have been set already
        by the call to allocate_hosting_port, but if it's not present, use
        the value from the port resource.
        """
        if hosting_info.get('segmentation_id') is None:
            LOG.debug('No segmentation ID in hosting_info -- assigning')
            hosting_info['segmentation_id'] = (
                port_db.hosting_info.get('segmentation_id'))
        is_external = (port_db.device_owner == DEVICE_OWNER_ROUTER_GW)
        hosting_info['physical_interface'] = self._get_interface_info(
            hosting_device['id'], port_db.network_id, is_external)
        ext_dict, net = self._get_external_network_dict(context, port_db)
        if is_external and ext_dict:
            hosting_info['network_name'] = ext_dict['network_name']
            hosting_info['cidr_exposed'] = ext_dict['cidr_exposed']
            hosting_info['gateway_ip'] = ext_dict['gateway_ip']
            details = self.get_vrf_context(context,
                                           port_db['device_id'], port_db)
            router_id = port_db.device_id
            router = self.l3_plugin.get_router(context, router_id)
            # skip routers not created by the user -- they will have
            # empty-string tenant IDs
            if router.get(ROUTER_ROLE_ATTR):
                return
            hosting_info['vrf_id'] = details['vrf_id']
            if ext_dict.get('global_config'):
                hosting_info['global_config'] = (
                    ext_dict['global_config'])
            self._add_snat_info(context, router, net, hosting_info)
        else:
            if ext_dict.get('interface_config'):
                hosting_info['interface_config'] = ext_dict['interface_config']

    def allocate_hosting_port(self, context, router_id, port_db, network_type,
                              hosting_device_id):
        """Get the VLAN and port for this hosting device

        The VLAN used between the APIC and the external router is stored
        by the APIC driver.  This calls into the APIC driver to first get
        the ACI VRF information associated with this port, then uses that
        to look up the VLAN to use for this port to the external router
        (kept as part of the L3 Out policy in ACI).
        """
        # If this is a router interface, the VLAN comes from APIC.
        # If it's the gateway, the VLAN comes from the segment ID
        if port_db.get('device_owner') == DEVICE_OWNER_ROUTER_GW:
            ext_dict, net = self._get_external_network_dict(context, port_db)
            # If an OpFlex network is used on the external network,
            # the actual segment ID comes from the config file
            if net and net.get('provider:network_type') == 'opflex':
                if ext_dict.get('segmentation_id'):
                    return {'allocated_port_id': port_db.id,
                            'allocated_vlan': ext_dict['segmentation_id']}
                else:
                    raise AciDriverConfigMissingSegmentationId(ext_net=net)
            return super(AciVLANTrunkingPlugDriver,
                         self).allocate_hosting_port(
                             context, router_id,
                             port_db, network_type, hosting_device_id)

        # shouldn't happen, but just in case
        if port_db.get('device_owner') != DEVICE_OWNER_ROUTER_INTF:
            return

        # get the external network that this port connects to.
        # if there isn't an external gateway yet on the router,
        # then don't allocate a port

        router = self.l3_plugin.get_router(context, router_id)
        gw_info = router[EXTERNAL_GW_INFO]
        if not gw_info:
            return
        network_id = gw_info.get('network_id')

        networks = self._core_plugin.get_networks(
            context.elevated(), {'id': [network_id]})
        l3out_network = networks[0]
        l3out_name = self.get_ext_net_name(l3out_network['name'])
        # For VLAN apic driver provides VLAN tag
        details = self.get_vrf_context(context, router_id, port_db)
        if details is None:
            LOG.debug('aci_vlan_trunking_driver: No vrf_details')
            return
        vrf_name = details.get('vrf_name')
        vrf_tenant = details.get('vrf_tenant')
        allocated_vlan = self.apic_driver.l3out_vlan_alloc.get_vlan_allocated(
            l3out_name, vrf_name, vrf_tenant=vrf_tenant)
        if allocated_vlan is None:
            if not vrf_tenant:
                # TODO(tbachman): I can't remember why this is here
                return super(AciVLANTrunkingPlugDriver,
                             self).allocate_hosting_port(
                                 context, router_id,
                                 port_db, network_type, hosting_device_id
                             )
            # Database must have been messed up if this happens ...
            return
        return {'allocated_port_id': port_db.id,
                'allocated_vlan': allocated_vlan}

    # TODO(tbahcman): get these from the drivers
    def _get_ext_net_name_gbp(self, network_name):
        """Get the external network name

        The name of the external network used in the APIC
        configuration file can be different from the name
        of the external network in Neutron, especially using
        the GBP workflow
        """
        prefix = network_name[:re.search(UUID_REGEX, network_name).start() - 1]
        return prefix.strip(APIC_OWNED)

    def _get_ext_net_name_neutron(self, network_name):
        """Get the external network name

        For Neutron workflow, the network name is returned
        as-is.
        """
        return network_name
