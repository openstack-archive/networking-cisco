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

import copy

from oslo_log import log as logging

from neutron.common import constants as l3_constants

from networking_cisco.plugins.cisco.cfg_agent.service_helpers import (
    routing_svc_helper as helper)
from networking_cisco.plugins.cisco.extensions import routerrole

ROUTER_ROLE_ATTR = routerrole.ROUTER_ROLE_ATTR
LOG = logging.getLogger(__name__)


class RoutingServiceHelperAci(helper.RoutingServiceHelper):

    def __init__(self, host, conf, cfg_agent):
        super(RoutingServiceHelperAci, self).__init__(
            host, conf, cfg_agent)
        self._router_ids_by_vrf = {}
        self._router_ids_by_vrf_and_ext_net = {}

    def _process_new_ports(self, ri, new_ports, ex_gw_port, list_port_ids_up):
        # Only add internal networks if we have an
        # external gateway -- otherwise we have no parameters
        # to use to configure the interface (e.g. VRF, IP, etc.)
        if ex_gw_port:
            super(RoutingServiceHelperAci,
                  self)._process_new_ports(
                      ri, new_ports, ex_gw_port, list_port_ids_up)

    def _process_old_ports(self, ri, old_ports, ex_gw_port):
        gw_port = ex_gw_port or ri.ex_gw_port
        for p in old_ports:
            LOG.debug("++ removing port id = %s (gw = %s)" %
                      (p['id'], gw_port))
            # We can only clear the port if we stil have all
            # the relevant information (VRF and external network
            # parameters), which come from the GW port. Go ahead
            # and remove the interface from our internal state
            if gw_port:
                self._internal_network_removed(ri, p, gw_port)
            ri.internal_ports.remove(p)

    def _enable_disable_ports(self, ri, ex_gw_port, internal_ports):
        pass

    def _process_gateway_set(self, ri, ex_gw_port, list_port_ids_up):
        super(RoutingServiceHelperAci,
              self)._process_gateway_set(ri, ex_gw_port, list_port_ids_up)
        # transitioned -- go enable any interfaces
        interfaces = ri.router.get(l3_constants.INTERFACE_KEY, [])
        new_ports = [p for p in interfaces
                     if (p['admin_state_up'] and
                         p not in ri.internal_ports)]
        self._process_new_ports(ri, new_ports, ex_gw_port, list_port_ids_up)

    def _process_gateway_cleared(self, ri, ex_gw_port):
        super(RoutingServiceHelperAci,
              self)._process_gateway_cleared(ri, ex_gw_port)

        # remove the internal networks at this time,
        # while the gateway information is still available
        # (has VRF network parameters)
        del_ports = copy.copy(ri.internal_ports)
        self._process_old_ports(ri, del_ports, ex_gw_port)

    def _add_rid_to_vrf_list(self, ri):
        """Add router ID to a VRF list.

        In order to properly manage VRFs in the ASR, their
        usage has to be tracked. VRFs are provided with neutron
        router objects in their hosting_info fields of the gateway ports.
        This means that the VRF is only available when the gateway port
        of the router is set. VRFs can span routers, and even OpenStack
        tenants, so lists of routers that belong to the same VRF are
        kept in a dictionary, with the VRF name as the key.
        """
        if ri.ex_gw_port or ri.router.get('gw_port'):
            driver = self.driver_manager.get_driver(ri.id)
            vrf_name = driver._get_vrf_name(ri)
            if not vrf_name:
                return
            if not self._router_ids_by_vrf.get(vrf_name):
                LOG.debug("++ CREATING VRF %s" % vrf_name)
                driver._do_create_vrf(vrf_name)
            self._router_ids_by_vrf.setdefault(vrf_name, set()).add(
                ri.router['id'])

    def _remove_rid_from_vrf_list(self, ri):
        """Remove router ID from a VRF list.

        This removes a router from the list of routers that's kept
        in a map, using a VRF ID as the key. If the VRF exists, the
        router is removed from the list if it's present. If the last
        router in the list is removed, then the driver's method to
        remove the VRF is called and the map entry for that
        VRF is deleted.
        """
        if ri.ex_gw_port or ri.router.get('gw_port'):
            driver = self.driver_manager.get_driver(ri.id)
            vrf_name = driver._get_vrf_name(ri)
            if self._router_ids_by_vrf.get(vrf_name) and (
                    ri.router['id'] in self._router_ids_by_vrf[vrf_name]):
                self._router_ids_by_vrf[vrf_name].remove(ri.router['id'])
                # If this is the last router in a VRF, then we can safely
                # delete the VRF from the router config (handled by the driver)
                if not self._router_ids_by_vrf.get(vrf_name):
                    LOG.debug("++ REMOVING VRF %s" % vrf_name)
                    driver._remove_vrf(ri)
                    del self._router_ids_by_vrf[vrf_name]

    def _internal_network_added(self, ri, port, ex_gw_port):
        super(RoutingServiceHelperAci, self)._internal_network_added(
            ri, port, ex_gw_port)
        driver = self.driver_manager.get_driver(ri.id)
        vrf_name = driver._get_vrf_name(ri)
        net_name = ex_gw_port['hosting_info'].get('network_name')
        self._router_ids_by_vrf_and_ext_net.setdefault(
            vrf_name, {}).setdefault(net_name, set()).add(ri.router['id'])

    def _internal_network_removed(self, ri, port, ex_gw_port):
        """Remove an internal router port

        Check to see if this is the last port to be removed for
        a given network scoped by a VRF (note: there can be
        different mappings between VRFs and networks -- 1-to-1,
        1-to-n, n-to-1, n-to-n -- depending on the configuration
        and workflow used). If it is the last port, set the flag
        indicating that the internal sub-interface for that netowrk
        on the ASR should be deleted
        """
        itfc_deleted = False
        driver = self.driver_manager.get_driver(ri.id)
        vrf_name = driver._get_vrf_name(ri)
        network_name = ex_gw_port['hosting_info'].get('network_name')
        if self._router_ids_by_vrf_and_ext_net.get(
            vrf_name, {}).get(network_name) and (
                ri.router['id'] in
                self._router_ids_by_vrf_and_ext_net[vrf_name][network_name]):
            # If this is the last port for this neutron router,
            # then remove this router from the list
            if len(ri.internal_ports) == 1 and port in ri.internal_ports:
                self._router_ids_by_vrf_and_ext_net[
                    vrf_name][network_name].remove(ri.router['id'])

                # Check if any other routers in this VRF have this network,
                # and if not, set the flag to remove the interface
                if not self._router_ids_by_vrf_and_ext_net[vrf_name].get(
                        network_name):
                    LOG.debug("++ REMOVING NETWORK %s" % network_name)
                    itfc_deleted = True
                    del self._router_ids_by_vrf_and_ext_net[
                        vrf_name][network_name]
                    if not self._router_ids_by_vrf_and_ext_net.get(vrf_name):
                        del self._router_ids_by_vrf_and_ext_net[vrf_name]

        driver.internal_network_removed(ri, port,
                                        itfc_deleted=itfc_deleted)
        if ri.snat_enabled and ex_gw_port:
            driver.disable_internal_network_NAT(ri, port, ex_gw_port,
                                                itfc_deleted=itfc_deleted)
