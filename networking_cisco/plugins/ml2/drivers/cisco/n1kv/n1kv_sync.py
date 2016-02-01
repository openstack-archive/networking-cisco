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
import six

from oslo_config import cfg
from oslo_log import log

from networking_cisco._i18n import _LE, _LW

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import config
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import n1kv_client
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import n1kv_db

import neutron.db.api as db
from neutron.extensions import providernet
from neutron.plugins.common import constants as p_const

LOG = log.getLogger(__name__)


class N1kvSyncDriver(object):

    def __init__(self, db_base_plugin_obj):
        self.n1kvclient = n1kv_client.Client()
        self.db_base_plugin = db_base_plugin_obj
        self.sync_resource = {n1kv_const.NETWORK_PROFILES: False,
                              n1kv_const.NETWORKS: False,
                              n1kv_const.SUBNETS: False,
                              n1kv_const.PORTS: False}
        self.sync_sleep_duration = cfg.CONF.ml2_cisco_n1kv.sync_interval
        # default to True so that BDs for all VSMs are synced at a neutron
        # restart
        self.sync_bds = {vsm_ip: True for vsm_ip in
                         config.get_vsm_hosts()}
        self.bd_names = set()

    @property
    def need_sync(self):
        return any(self.sync_resource.values())

    @staticmethod
    def _compute_resource_md5(uuids):
        """Computes the md5 hashes, given a set of UUIDs.

        :param uuids: List of UUIDs for a resource
        :return: md5 hash string
        """
        res_md5 = hashlib.md5()
        for uuid in sorted(uuids):
            res_md5.update(six.b(uuid))
        return res_md5.hexdigest()

    @staticmethod
    def _get_uuids(res, res_info):
        """Get UUIDS of given resources.

        Given the resource name and list of SQL objects or
        dictionaries, return the UUID list for them.

        :param res: name of resource
        :param res_info: list of objects or dictionaries
        :return: list of UUIDs
        """
        return [info['id'] for info in res_info]

    def _get_neutron_md5_dict(self):
        neutron_md5_dict = {}
        for res in self.sync_resource.keys():
            res_info = self._get_neutron_resource(res)
            res_uuids = self._get_uuids(res, res_info)
            neutron_md5_dict[res] = self._compute_resource_md5(
                res_uuids)
        return neutron_md5_dict

    def _resources_needing_sync(self, resource_list):
        return filter(lambda x: self.sync_resource[x], resource_list)

    def do_sync(self):
        """
        Entry point function for VSM-Neutron sync.

        Triggered on an eventlet from the N1kv mechanism driver.
        """
        while True:
            try:
                vsm_hosts = config.get_vsm_hosts()
                for vsm_ip in vsm_hosts:
                    try:
                        self._sync_vsm(vsm_ip=vsm_ip)
                    except n1kv_exc.VSMConnectionFailed:
                        LOG.warning(_LW('Sync thread exception: VSM '
                                        '%s unreachable.') % vsm_ip)
                    except n1kv_exc.VSMError:
                        LOG.warning(_LW('Sync thread exception: Internal '
                                        'server error on VSM %s.') % vsm_ip)
            except Exception as e:
                LOG.warning(_LW('Sync thread exception: %s') % e.message)
            eventlet.sleep(seconds=self.sync_sleep_duration)

    def _sync_vsm(self, vsm_ip):
        # modifies the field sync_resource
        self._md5_hash_comparison(vsm_ip)
        if self.need_sync or self.sync_bds[vsm_ip]:
            LOG.debug('Sync started for VSM %s.' % vsm_ip)
            self.n1kvclient.send_sync_notification(n1kv_const.SYNC_START,
                                                   vsm_ip=vsm_ip)
            if self.need_sync:
                create_res_order = [n1kv_const.NETWORK_PROFILES,
                                    n1kv_const.NETWORKS,
                                    n1kv_const.SUBNETS,
                                    n1kv_const.PORTS]
                vsm_neutron_res_combined = self._get_vsm_neutron_resources(
                    create_res_order, vsm_ip=vsm_ip)
                # delete extraneous resources on VSM
                self._sync_resources(reversed(create_res_order),
                                     vsm_neutron_res_combined,
                                     'delete',
                                     vsm_ip)
                # create resources missing on VSM
                self._sync_resources(create_res_order,
                                     vsm_neutron_res_combined,
                                     'create',
                                     vsm_ip)
            # sync BDs on neutron restart
            if self.sync_bds[vsm_ip]:
                LOG.debug('Syncing bridge domains for VSM %s.' % vsm_ip)
                vsm_bds = set(self._get_vsm_resource(
                    n1kv_const.BRIDGE_DOMAINS, vsm_ip=vsm_ip).keys())
                neutron_vxlan_nets = n1kv_db.get_vxlan_networks()
                self._sync_bridge_domains((vsm_bds, neutron_vxlan_nets),
                                          vsm_ip=vsm_ip)
            self.n1kvclient.send_sync_notification(n1kv_const.SYNC_END,
                                                   vsm_ip=vsm_ip)
            LOG.debug('Sync completed for VSM %s.' % vsm_ip)
        else:
            self.n1kvclient.send_sync_notification(n1kv_const.SYNC_NO_CHANGE,
                                                   vsm_ip=vsm_ip)

    def _md5_hash_comparison(self, vsm_ip):
        """Compare md5 hashes between neutron and VSM.

        Fetches, computes and compares md5 hashes for VSM and neutron;
        then decides for which object the sync should be triggered.
        """
        # get md5 hashes from VSM here
        vsm_md5_dict = {}
        vsm_md5_properties = self._get_vsm_resource('md5_hashes', vsm_ip)[
            n1kv_const.MD5_HASHES][n1kv_const.PROPERTIES]
        (vsm_md5_dict[n1kv_const.NETWORK_PROFILES],
         vsm_md5_dict[n1kv_const.SUBNETS],
         vsm_md5_dict[n1kv_const.NETWORKS],
         vsm_md5_dict[n1kv_const.PORTS],
         vsm_consolidated_md5) = (
             vsm_md5_properties[n1kv_const.NETWORK_PROFILE_MD5],
             vsm_md5_properties[n1kv_const.SUBNET_MD5],
             vsm_md5_properties[n1kv_const.NETWORK_MD5],
             vsm_md5_properties[n1kv_const.PORT_MD5],
             vsm_md5_properties[n1kv_const.CONSOLIDATED_MD5])

        # order for resources has to be fixed as underneath since the
        # consolidated md5 depends on resource type order
        resources = [n1kv_const.NETWORK_PROFILES, n1kv_const.SUBNETS,
                     n1kv_const.NETWORKS, n1kv_const.PORTS]
        # update the consolidated md5 hash for Neutron
        neutron_consolidated_md5 = hashlib.md5()
        neutron_md5_dict = self._get_neutron_md5_dict()
        for res in resources:
            neutron_consolidated_md5.update(six.b(neutron_md5_dict[res]))

        # compare VSM and Neutron md5 hashes here
        if neutron_consolidated_md5.hexdigest() != vsm_consolidated_md5:
            LOG.debug('State mismatch detected for VSM %s.' % vsm_ip)
            for (res, neutron_md5_hash) in neutron_md5_dict.items():
                is_match = neutron_md5_hash == vsm_md5_dict[res]
                LOG.debug('MD5 %(resource)s match: %(match)s' %
                          {'resource': res, 'match': is_match})
                if not is_match:
                    LOG.debug('Schedule sync for: %s' % res)
                    self.sync_resource[res] = True
                else:
                    self.sync_resource[res] = False
        else:
            for res in self.sync_resource.keys():
                self.sync_resource[res] = False
            LOG.debug("State in sync for VSM %s" % vsm_ip)

    def _get_vsm_neutron_resources(self, resource_types, vsm_ip):
        """Get combined info on neutron and VSM resources.

        :param resource_types: list of resources types viz network_profiles,
                               networks etc.
        :param vsm_ip: IP of the VSM whose resources are needed
        :return: dictionary with key as the resource name and value as a
                 two-tuple constituted by list of UUIDs from VSM and list of
                 SQL objects from Neutron
        """
        vsm_neutron_res_combined = {}
        for res in self._resources_needing_sync(resource_types):
            if res == n1kv_const.PORTS:
                vsm_res_uuids = self._get_vsm_resource(
                    n1kv_const.VMNETWORKS, vsm_ip)
            else:
                vsm_res_uuids = set(self._get_vsm_resource(res, vsm_ip))
                if res == n1kv_const.NETWORKS:
                    bd_info = self._get_vsm_resource(n1kv_const.BRIDGE_DOMAINS,
                                                     vsm_ip=vsm_ip)
                    self.bd_names = set(bd_info.keys())
            neutron_res_info = self._get_neutron_resource(res)
            vsm_neutron_res_combined[res] = (vsm_res_uuids, neutron_res_info)
        return vsm_neutron_res_combined

    def _sync_resources(self, res_order, vsm_neutron_res_combined,
                        action, vsm_ip):
        """Create or delete resources from the VSM.

        Call sync_create or sync_delete methods, depending on 'action' string,
        for out of sync resources.

        :param res_order: order for resource creation/deletion
        :param vsm_neutron_res_combined: dictionary of resources from both
                                         VSM and neutron
        :param action: create/delete
        :param vsm_ip: IP of the VSM that has to be synced
        """
        for res in self._resources_needing_sync(res_order):
            getattr(self, '_sync_%s_%s' % (action, res))(
                vsm_neutron_res_combined[res], vsm_ip)

    def _get_neutron_resource(self, res):
        """Fetches specified resource objects from neutron database.

        :param res: name of the resource viz. network_profiles,
                    subnets, networks
        :return: list of SQL objects or dictionaries for res
        """
        return getattr(n1kv_db, 'get_%s' % res)(self.db_base_plugin)

    def _get_vsm_resource(self, res, vsm_ip):
        """Fetches the UUIDs for the specified resource from VSM.

        :param res: name of the resource viz. network_profiles, subnets,
                    networks
        :param vsm_ip: IP address of the VSM
        :return: list of UUIDs for res
        """
        return getattr(self.n1kvclient, 'list_%s' % res)(vsm_ip)

    def _sync_create_network_profiles(self, combined_res_info, vsm_ip):
        """Sync network profiles by creating missing ones on VSM."""
        (vsm_net_profile_uuids, neutron_net_profiles) = combined_res_info
        for np_obj in neutron_net_profiles:
            if np_obj['id'] not in vsm_net_profile_uuids:
                # create these network profiles on VSM
                try:
                    self.n1kvclient.create_network_segment_pool(np_obj, vsm_ip)
                except (n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                    LOG.warning(_LW('Sync exception: Network profile creation '
                                    'failed for %s.') % np_obj['id'])

    def _sync_delete_network_profiles(self, combined_res_info, vsm_ip):
        """Sync network profiles by deleting extraneous ones from VSM."""
        (vsm_net_profile_uuids, neutron_net_profiles) = combined_res_info
        neutron_net_profile_uuids = set(self._get_uuids(
            n1kv_const.NETWORK_PROFILES, neutron_net_profiles))
        for np_id in vsm_net_profile_uuids - neutron_net_profile_uuids:
            # delete these network profiles from VSM
            try:
                self.n1kvclient.delete_network_segment_pool(np_id,
                                                            vsm_ip=vsm_ip)
                log_net_name = np_id + n1kv_const.LOGICAL_NETWORK_SUFFIX
                self.n1kvclient.delete_logical_network(log_net_name,
                                                       vsm_ip=vsm_ip)
            except (n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                LOG.warning(_LW('Sync exception: Network profile deletion '
                                'failed. for %s') % np_id)

    def _sync_create_networks(self, combined_res_info, vsm_ip):
        """Sync networks by creating missing ones on VSM."""
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
                                                           vsm_ip=vsm_ip)
                except (n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                    LOG.warning(_LW('Sync exception: Network create failed '
                                    'for %s.') % network['id'])

    def _sync_delete_networks(self, combined_res_info, vsm_ip):
        """Sync networks by deleting extraneous ones from VSM."""
        (vsm_net_uuids, neutron_nets) = combined_res_info
        neutron_net_uuids = set(self._get_uuids(
            n1kv_const.NETWORKS, neutron_nets))
        for net_id in vsm_net_uuids - neutron_net_uuids:
            # delete these networks from VSM
            bd_name = net_id + n1kv_const.BRIDGE_DOMAIN_SUFFIX
            if bd_name in self.bd_names:
                segment_type = p_const.TYPE_VXLAN
            else:
                segment_type = p_const.TYPE_VLAN
            try:
                self.n1kvclient.delete_network_segment(net_id, segment_type,
                                                       vsm_ip=vsm_ip)
            except (n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                LOG.warning(_LW('Sync exception: Network delete failed for '
                                '%s.') % net_id)

    def _sync_create_subnets(self, combined_res_info, vsm_ip):
        """Sync subnets by creating missing ones on VSM."""
        (vsm_subnet_uuids, neutron_subnets) = combined_res_info
        missing_subnets = [subnet for subnet in neutron_subnets if subnet[
            'id'] not in vsm_subnet_uuids]
        for subnet in missing_subnets:
            try:
                self.n1kvclient.create_ip_pool(subnet, vsm_ip=vsm_ip)
            except (n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                LOG.warning(_LW('Sync Exception: Subnet create failed for '
                                '%s.') % subnet['id'])

    def _sync_delete_subnets(self, combined_res_info, vsm_ip):
        """Sync subnets by deleting extraneous ones from VSM."""
        (vsm_subnet_uuids, neutron_subnets) = combined_res_info
        neutron_subnet_uuids = set(self._get_uuids(n1kv_const.SUBNETS,
                                                   neutron_subnets))
        for sub_id in vsm_subnet_uuids - neutron_subnet_uuids:
            # delete these subnets from the VSM
            try:
                self.n1kvclient.delete_ip_pool(sub_id, vsm_ip=vsm_ip)
            except (n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                LOG.warning(_LW('Sync Exception: Subnet delete failed for '
                                '%s.') % sub_id)

    def _sync_create_ports(self, combined_res_info, vsm_ip):
        """Sync ports by creating missing ones on VSM."""
        (vsm_vmn_dict, neutron_ports) = combined_res_info
        vsm_port_uuids = set()
        for port_dict in vsm_vmn_dict.values():
            port_props = port_dict['properties']
            port_ids = set(port_props['portId'].split(','))
            vsm_port_uuids = vsm_port_uuids.union(port_ids)
        missing_ports = [port for port in neutron_ports if port['id'] not in
                         vsm_port_uuids]
        for port in missing_ports:
            # create these ports on VSM
            try:
                network_uuid = port['network_id']
                binding = n1kv_db.get_policy_binding(port['id'])
                policy_profile_id = binding.profile_id
                policy_profile = n1kv_db.get_policy_profile_by_uuid(
                    db.get_session(), policy_profile_id)
                if not policy_profile:
                    LOG.error(_LE("Cannot sync port with id %(port_id)s "
                                  "because policy profile with id "
                                  "%(profile_id)s does not exist."),
                              {"port_id": port['id'],
                               "profile_name": policy_profile})
                    continue
                vmnetwork_name = "%s%s_%s" % (n1kv_const.VM_NETWORK_PREFIX,
                                          policy_profile_id, network_uuid)
                self.n1kvclient.create_n1kv_port(port, vmnetwork_name,
                                                 policy_profile, vsm_ip=vsm_ip)
            except (n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                LOG.warning(_LW('Sync Exception: Port create failed for '
                                '%s.') % port['id'])
            except n1kv_exc.PolicyProfileNotFound:
                LOG.warning(_LW('Sync Exception: Port create failed as Policy '
                                'profile %s does not exist on all VSM'),
                            policy_profile_id)

    def _sync_delete_ports(self, combined_res_info, vsm_ip):
        """Sync ports by deleting extraneous ones from VSM."""
        (vsm_vmn_dict, neutron_ports) = combined_res_info
        vsm_port_uuids = set()
        for port_dict in vsm_vmn_dict.values():
            port_props = port_dict['properties']
            port_ids = set(port_props['portId'].split(','))
            vsm_port_uuids = vsm_port_uuids.union(port_ids)
        neutron_port_uuids = set(self._get_uuids(n1kv_const.PORTS,
                                                 neutron_ports))
        for (vmnetwork_name, port_dict) in vsm_vmn_dict.items():
            port_props = port_dict['properties']
            port_ids = port_props['portId'].split(',')
            extra_ports = [port for port in port_ids if port not in
                           neutron_port_uuids]
            for port_id in extra_ports:
                # delete these ports from VSM
                try:
                    self.n1kvclient.delete_n1kv_port(vmnetwork_name, port_id,
                                                     vsm_ip=vsm_ip)
                except (n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                    LOG.warning(_LW('Sync Exception: Port delete failed for %s'
                                    '.') % port_id)

    def _sync_bridge_domains(self, combined_res_info, vsm_ip):
        """
        Sync bridge domains by creating/deleting them on the VSM.

        :param combined_res_info: a two tuple storing the list of VSM BDs
                                  and the list of neutron networks
        :param vsm_ip: IP of the VSM being synced
        """
        # create missing BDs on VSM
        (vsm_bds, neutron_vxlan_nets) = combined_res_info
        need_bd_sync = False
        for network in neutron_vxlan_nets:
            bd_name = network['id'] + n1kv_const.BRIDGE_DOMAIN_SUFFIX
            if bd_name not in vsm_bds:
                binding = n1kv_db.get_network_binding(network['id'])
                netp = n1kv_db.get_network_profile_by_uuid(binding.profile_id)
                network[providernet.SEGMENTATION_ID] = binding.segmentation_id
                network[providernet.NETWORK_TYPE] = binding.network_type
                # create this BD on VSM
                try:
                    self.n1kvclient.create_bridge_domain(network,
                                                         netp,
                                                         vsm_ip=vsm_ip)
                except(n1kv_exc.VSMConnectionFailed, n1kv_exc.VSMError):
                    LOG.warning(_LW('Sync Exception: Bridge domain creation '
                                    'failed for %s.') % bd_name)
                    need_bd_sync = True
        # delete extraneous BDs from VSM
        neutron_bds = {net_id + n1kv_const.BRIDGE_DOMAIN_SUFFIX for net_id in
                       self._get_uuids(n1kv_const.NETWORKS,
                                       neutron_vxlan_nets)}
        for bd in vsm_bds - neutron_bds:
            try:
                # delete this BD from VSM
                self.n1kvclient.delete_bridge_domain(bd, vsm_ip=vsm_ip)
            except (n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                LOG.warning(_LW('Sync Exception: Bridge domain deletion '
                                'failed for %s.') % bd)
                need_bd_sync = True
        self.sync_bds[vsm_ip] = need_bd_sync
