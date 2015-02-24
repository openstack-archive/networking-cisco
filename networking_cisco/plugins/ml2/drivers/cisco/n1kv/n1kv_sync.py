# Copyright 2015 Cisco Systems, Inc.
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
ML2 Sync for periodic MD5 based resource sync between Neutron and VSM
"""

import eventlet
import hashlib

from oslo_config import cfg
from oslo_log import log

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import n1kv_client
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import n1kv_db

import neutron.db.api as db
from neutron.extensions import providernet
from neutron.i18n import _LW
from neutron.plugins.common import constants as p_const

LOG = log.getLogger(__name__)

NETWORK_PROFILES = 'network_profiles'
NETWORKS = 'networks'
SUBNETS = 'subnets'
PORTS = 'ports'
VMNETWORKS = 'vmnetworks'
BRIDGE_DOMAINS = 'bridge_domains'


class N1kvSyncDriver(object):

    def __init__(self, db_base_plugin_obj):
        self.n1kvclient = n1kv_client.Client()
        self.db_base_plugin = db_base_plugin_obj
        self.sync_resource = {NETWORK_PROFILES: False,
                              NETWORKS: False,
                              SUBNETS: False,
                              PORTS: False}
        self.sync_sleep_duration = cfg.CONF.ml2_cisco_n1kv.sync_interval
        self.bd_names = []

    def do_sync(self):
        """Begin sync with VSM when triggered from N1KV mech driver."""
        while True:
            try:
                vsm_hosts = self.n1kvclient.get_vsm_hosts()
                for vsm_ip in vsm_hosts:
                    self._md5_hash_comparison(vsm_ip)
                    create_res_order = [NETWORK_PROFILES, NETWORKS, SUBNETS,
                                        PORTS]
                    vsm_neutron_res_info_combined = {}
                    for res in create_res_order:
                        if self.sync_resource[res]:
                            if res == PORTS:
                                vsm_res_uuids = self._get_vsm_resource(
                                    VMNETWORKS, vsm_ip)
                            else:
                                vsm_res_uuids = set(self._get_vsm_resource(
                                    res, vsm_ip))
                                if res == NETWORKS:
                                    bd_info = self._get_vsm_resource(
                                        BRIDGE_DOMAINS, vsm_ip=vsm_ip)
                                    self.bd_names = bd_info.keys()
                            neutron_res_info = self._get_neutron_resource(res)
                            vsm_neutron_res_info_combined[res] = (
                                vsm_res_uuids, neutron_res_info)
                    for res in create_res_order:
                        if self.sync_resource[res]:
                            getattr(self, '_sync_create_%s' % res)(
                                vsm_neutron_res_info_combined[res], vsm_ip)
                    for res in reversed(create_res_order):
                        if self.sync_resource[res]:
                            getattr(self, '_sync_delete_%s' % res)(
                                vsm_neutron_res_info_combined[res], vsm_ip)
            except(n1kv_exc.VSMConnectionFailed, n1kv_exc.VSMError):
                LOG.warning(_LW('Sync thread exception: VSM unreachable'))
            eventlet.sleep(seconds=self.sync_sleep_duration)

    def _md5_hash_comparison(self, vsm_ip):
        """
        Perform md5 hash comparison between VSM and neutron objects.

        Fetches, computes and compares md5 hashes for VSM and neutron;
        then decides for which object the sync should be triggered
        :param vsm_ip: string representing the IP address of the VSM
        """
        # get md5 hashes from VSM here
        vsm_md5_dict = {}
        vsm_md5 = self._get_vsm_resource('md5_hashes', vsm_ip)
        vsm_md5_properties = vsm_md5[n1kv_const.MD5_HASHES][
            n1kv_const.PROPERTIES]
        vsm_md5_dict[NETWORK_PROFILES] = vsm_md5_properties[
            n1kv_const.NETWORK_PROFILE_MD5]
        vsm_md5_dict[SUBNETS] = vsm_md5_properties[n1kv_const.SUBNET_MD5]
        vsm_md5_dict[NETWORKS] = vsm_md5_properties[n1kv_const.NETWORK_MD5]
        vsm_md5_dict[PORTS] = vsm_md5_properties[n1kv_const.PORT_MD5]
        vsm_consolidated_md5 = vsm_md5_properties[n1kv_const.CONSOLIDATED_MD5]
        # get md5 hashes for neutron here
        resources = [NETWORK_PROFILES, SUBNETS, NETWORKS, PORTS]
        neutron_md5_dict = {}
        for res in resources:
            res_info = self._get_neutron_resource(res)
            res_uuids = self._get_uuids(res, res_info)
            neutron_md5_dict[res] = self._compute_resource_md5(res_uuids)
        neutron_consolidated_md5 = hashlib.md5()
        for res in resources:
            neutron_consolidated_md5.update(neutron_md5_dict[res])
        if neutron_consolidated_md5.hexdigest() != vsm_consolidated_md5:
            LOG.debug("State mismatch detected.")
            for (res, neutron_md5_hash) in neutron_md5_dict.items():
                md5_match = neutron_md5_hash == vsm_md5_dict[res]
                LOG.debug("MD5 %(resource)s match: %(match)s",
                          {'resource': res, 'match': md5_match})
                if not md5_match:
                    LOG.debug("Schedule sync for: %s", res)
                    self.sync_resource[res] = True
                else:
                    self.sync_resource[res] = False
        else:
            self.sync_resource = {res: False for res in resources}
            LOG.debug("State in sync for vsm_ip: %s", vsm_ip)

    def _compute_resource_md5(self, uuids):
        """
        Computes the md5 hashes, given a set of UUIDs

        :param uuids: List of UUIDs for a resource
        :returns: md5 hash string
        """
        res_md5 = hashlib.md5()
        for uuid in sorted(uuids):
            res_md5.update(uuid)
        return res_md5.hexdigest()

    def _get_uuids(self, res, res_info):
        """
        Return list of UUIDs for the given resource.

        Given the resource name and list of SQL objects or
        dictionaries, returns the UUID list for them
        :param res: name of resource
        :param res_info: list of objects or dictionaries
        :returns: list of UUIDs
        """
        if res != NETWORK_PROFILES:
            return [info['id'] for info in res_info]
        return [info.id for info in res_info]

    def _get_neutron_resource(self, res):
        """
        Fetches the UUIDs for the specified resource from neutron database.

        :param res: name of the resource viz. network_profiles,
                    subnets, networks
        :returns: list of SQL objects or dictionaries for res
        """
        return getattr(n1kv_db, 'get_%s' % res)(self.db_base_plugin)

    def _get_vsm_resource(self, res, vsm_ip):
        """
        Fetches the UUIDs for the specified resource from VSM.

        :param res: name of the resource viz. network_profiles,
                    subnets, networks
        :returns: list of UUIDs for res
        """
        return getattr(self.n1kvclient, 'list_%s' % res)(vsm_ip)

    def _sync_create_network_profiles(self, combined_res_info, vsm_ip):
        """
        Sync network profiles by creating missing ones on VSM.

        :param combined_res_info: tuple containing VSM and neutron information
        :param vsm_ip: string representing the IP address of the VSM
        """
        (vsm_net_profile_uuids, neutron_net_profiles) = combined_res_info
        for np_obj in neutron_net_profiles:
            if np_obj.id not in vsm_net_profile_uuids:
                # create these network profiles on VSM
                try:
                    self.n1kvclient.create_network_segment_pool(np_obj, vsm_ip)
                except n1kv_exc.VSMError as e:
                    LOG.warning(_LW('Sync Exception: Network profile creation '
                                'on VSM failed: %s'), e.message)

    def _sync_delete_network_profiles(self, combined_res_info, vsm_ip):
        """
        Sync network profiles by deleting extraneous ones from VSM.

        :param combined_res_info: tuple containing VSM and neutron information
        :param vsm_ip: string representing the IP address of the VSM
        """
        (vsm_net_profile_uuids, neutron_net_profiles) = combined_res_info
        neutron_net_profile_uuids = set(self._get_uuids(NETWORK_PROFILES,
                                                        neutron_net_profiles))
        for np_id in vsm_net_profile_uuids - neutron_net_profile_uuids:
            # delete these network profiles from VSM
            try:
                self.n1kvclient.delete_network_segment_pool(np_id,
                                                            vsm_ip=vsm_ip)
            except n1kv_exc.VSMError as e:
                LOG.warning(_LW('Sync Exception: Network profile deletion on '
                            'VSM failed: %s'), e.message)

    def _sync_create_networks(self, combined_res_info, vsm_ip):
        """
        Sync networks by creating missing ones on VSM.

        :param combined_res_info: tuple containing VSM and neutron information
        :param vsm_ip: string representing the IP address of the VSM
        """
        (vsm_net_uuids, neutron_nets) = combined_res_info
        for network in neutron_nets:
            if network['id'] not in vsm_net_uuids:
                network_profile = n1kv_db.get_network_profile_by_network(
                    network['id'])
                binding = n1kv_db.get_network_binding(network['id'])
                network[providernet.SEGMENTATION_ID] = binding.segmentation_id
                network[providernet.NETWORK_TYPE] = binding.network_type
                # create these networks on VSM
                try:
                    self.n1kvclient.create_network_segment(network,
                                                           network_profile,
                                                           vsm_ip)
                except n1kv_exc.VSMError as e:
                    LOG.warning(_LW('Sync Exception: Network creation on VSM '
                                'failed: %s'), e.message)

    def _sync_delete_networks(self, combined_res_info, vsm_ip):
        """
        Sync networks by deleting extraneous ones from VSM.

        :param combined_res_info : tuple containing VSM and neutron information
        :param vsm_ip: string representing the IP address of the VSM
        """
        (vsm_net_uuids, neutron_nets) = combined_res_info
        neutron_net_uuids = set(self._get_uuids(NETWORKS, neutron_nets))
        for net_id in vsm_net_uuids - neutron_net_uuids:
            # delete these networks from VSM
            try:
                bd_name = net_id + n1kv_const.BRIDGE_DOMAIN_SUFFIX
                if bd_name in self.bd_names:
                    segment_type = p_const.TYPE_VXLAN
                else:
                    segment_type = p_const.TYPE_VLAN
                self.n1kvclient.delete_network_segment(net_id, segment_type,
                                                       vsm_ip=vsm_ip)
            except n1kv_exc.VSMError as e:
                LOG.warning(_LW('Sync Exception: Network deletion on VSM '
                            'failed: %s'), e.message)

    def _sync_create_subnets(self, combined_res_info, vsm_ip):
        """
        Sync subnets by creating missing ones on VSM.

        :param combined_res_info: tuple containing VSM and neutron information
        :param vsm_ip: string representing the IP address of the VSM
        """
        (vsm_subnet_uuids, neutron_subnets) = combined_res_info
        for subnet in neutron_subnets:
            if subnet['id'] not in vsm_subnet_uuids:
                # create these subnets on VSM
                try:
                    self.n1kvclient.create_ip_pool(subnet, vsm_ip=vsm_ip)
                except n1kv_exc.VSMError as e:
                    LOG.warning(_LW('Sync Exception: Subnet creation on VSM '
                                'failed: %s'), e.message)

    def _sync_delete_subnets(self, combined_res_info, vsm_ip):
        """
        Sync subnets by deleting extraneous ones from VSM.

        :param combined_res_info: tuple containing VSM and neutron information
        :param vsm_ip: string representing the IP address of the VSM
        """
        (vsm_subnet_uuids, neutron_subnets) = combined_res_info
        neutron_subnet_uuids = set(self._get_uuids(SUBNETS, neutron_subnets))
        for sub_id in vsm_subnet_uuids - neutron_subnet_uuids:
            # delete these subnets from the VSM
            try:
                self.n1kvclient.delete_ip_pool(sub_id, vsm_ip=vsm_ip)
            except n1kv_exc.VSMError as e:
                LOG.warning(_LW('Sync Exception: Subnet deletion on VSM '
                            'failed: %s'), e.message)

    def _sync_create_ports(self, combined_res_info, vsm_ip):
        """
        Sync ports by creating missing ones on VSM.

        :param combined_res_info: tuple containing VSM and neutron information
        :param vsm_ip: string representing the IP address of the VSM
        """
        (vsm_vmn_dict, neutron_ports) = combined_res_info
        vsm_port_uuids = set()
        for (k, v) in vsm_vmn_dict.items():
            port_dict = v['properties']
            port_ids = set(port_dict['portId'].split(','))
            vsm_port_uuids = vsm_port_uuids.union(port_ids)
        for port in neutron_ports:
            if port['id'] not in vsm_port_uuids:
                # create these ports on VSM
                network_uuid = port['network_id']
                binding = n1kv_db.get_policy_binding(port['id'])
                policy_profile_id = binding.profile_id
                policy_profile = n1kv_db.get_policy_profile_by_uuid(
                    db.get_session(), policy_profile_id)
                vmnetwork_name = "%s%s_%s" % (n1kv_const.VM_NETWORK_PREFIX,
                                              policy_profile_id,
                                              network_uuid)
                try:
                    self.n1kvclient.create_n1kv_port(port, vmnetwork_name,
                                                     policy_profile,
                                                     vsm_ip=vsm_ip)
                except n1kv_exc.VSMError as e:
                    LOG.warning(_LW('Sync Exception: Port creation on VSM '
                                'failed: %s'), e.message)

    def _sync_delete_ports(self, combined_res_info, vsm_ip):
        """
        Sync ports by deleting extraneous ones from VSM.

        :param combined_res_info: tuple containing VSM and neutron information
        :param vsm_ip: string representing the IP address of the VSM
        """
        (vsm_vmn_dict, neutron_ports) = combined_res_info
        vsm_port_uuids = set()
        for (k, v) in vsm_vmn_dict.items():
            port_dict = v['properties']
            port_ids = set(port_dict['portId'].split(','))
            vsm_port_uuids = vsm_port_uuids.union(port_ids)
        neutron_port_uuids = set(self._get_uuids(PORTS, neutron_ports))
        for (vmnetwork_name, props) in vsm_vmn_dict.items():
            port_dict = props['properties']
            port_ids = port_dict['portId'].split(',')
            for port_id in port_ids:
                if port_id not in neutron_port_uuids:
                    # delete these ports from VSM
                    try:
                        self.n1kvclient.delete_n1kv_port(vmnetwork_name,
                                                         port_id,
                                                         vsm_ip=vsm_ip)
                    except n1kv_exc.VSMError as e:
                        LOG.warning(_LW('Sync Exception: Port deletion on VSM '
                                    'failed: %s'), e.message)
