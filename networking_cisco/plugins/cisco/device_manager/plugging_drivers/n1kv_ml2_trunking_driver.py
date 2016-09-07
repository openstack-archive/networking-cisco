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

import eventlet

from oslo_config import cfg
from oslo_log import log as logging
from sqlalchemy.orm import exc
from sqlalchemy.sql import expression as expr

from networking_cisco._i18n import _, _LE, _LI, _LW

from neutron import context as n_context
from neutron.db import models_v2
from neutron.extensions import providernet as pr_net
from neutron import manager
from neutron_lib import exceptions as n_exc

from networking_cisco import backwards_compatibility as bc_attr
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.db.device_manager import hd_models
import networking_cisco.plugins.cisco.device_manager.plugging_drivers as plug
from networking_cisco.plugins.cisco.device_manager.plugging_drivers import (
    n1kv_plugging_constants as n1kv_const)
from networking_cisco.plugins.cisco.device_manager.plugging_drivers import (
    utils)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import constants

LOG = logging.getLogger(__name__)


N1KV_TRUNKING_DRIVER_OPTS = [
    cfg.StrOpt('management_port_profile', default='osn_mgmt_pp',
               help=_("Name of N1kv port profile for management ports.")),
    cfg.StrOpt('t1_port_profile', default='osn_t1_pp',
               help=_("Name of N1kv port profile for T1 ports (i.e., ports "
                      "carrying traffic from VXLAN segmented networks).")),
    cfg.StrOpt('t2_port_profile', default='osn_t2_pp',
               help=_("Name of N1kv port profile for T2 ports (i.e., ports "
                      "carrying traffic from VLAN segmented networks).")),
    cfg.StrOpt('t1_network_profile', default='osn_t1_np',
               help=_("Name of N1kv network profile for T1 networks (i.e., "
                      "trunk networks for VXLAN segmented traffic).")),
    cfg.StrOpt('t2_network_profile', default='osn_t2_np',
               help=_("Name of N1kv network profile for T2 networks (i.e., "
                      "trunk networks for VLAN segmented traffic).")),
]

cfg.CONF.register_opts(N1KV_TRUNKING_DRIVER_OPTS, "n1kv")

MIN_LL_VLAN_TAG = 10
MAX_LL_VLAN_TAG = 200
FULL_VLAN_SET = set(range(MIN_LL_VLAN_TAG, MAX_LL_VLAN_TAG + 1))
DELETION_ATTEMPTS = 5
SECONDS_BETWEEN_DELETION_ATTEMPTS = 3

# Port lookups can fail so retries are needed
MAX_HOSTING_PORT_LOOKUP_ATTEMPTS = 10
SECONDS_BETWEEN_HOSTING_PORT_LOOKSUPS = 2


class N1kvML2TrunkingPlugDriver(plug.PluginSidePluggingDriver,
                                utils.PluggingDriverUtilsMixin):
    """Driver class for service VMs used with the N1kv ML2 mechanism driver.

    The driver makes use of the N1kv drivers VLAN trunk feature.
    """
    _mgmt_port_profile_id = None
    _t1_port_profile_id = None
    _t2_port_profile_id = None
    _t1_network_profile_id = None
    _t2_network_profile_id = None
    _t1_net_id = None
    _t2_net_id = None

    @property
    def _core_plugin(self):
        try:
            return self._plugin
        except AttributeError:
            self._plugin = manager.NeutronManager.get_plugin()
            return self._plugin

    @classmethod
    def _get_profile_id(cls, p_type, resource, name):
        try:
            tenant_id = manager.NeutronManager.get_service_plugins()[
                cisco_constants.DEVICE_MANAGER].l3_tenant_id()
        except AttributeError:
            return
        if tenant_id is None:
            return
        if p_type == 'net_profile':
            plugin = manager.NeutronManager.\
                get_service_plugins().get(constants.CISCO_N1KV_NET_PROFILE)
            profiles = plugin.get_network_profiles(
                n_context.get_admin_context(),
                {'tenant_id': [tenant_id], 'name': [name]},
                ['id'])
        else:
            plugin = manager.NeutronManager.get_service_plugins().get(
                constants.CISCO_N1KV)
            profiles = plugin.get_policy_profiles(
                n_context.get_admin_context(),
                {'tenant_id': [tenant_id], 'name': [name]},
                ['id'])
        if len(profiles) == 1:
            return profiles[0]['id']
        elif len(profiles) > 1:
            # Profile must have a unique name.
            LOG.error(_LE('The %(resource)s %(name)s does not have unique '
                          'name. Please refer to admin guide and create one.'),
                      {'resource': resource, 'name': name})
        else:
            # Profile has not been created.
            LOG.error(_LE('There is no %(resource)s %(name)s. Please refer to '
                          'admin guide and create one.'),
                      {'resource': resource, 'name': name})

    @classmethod
    def mgmt_port_profile_id(cls):
        if cls._mgmt_port_profile_id is None:
            cls._mgmt_port_profile_id = cls._get_profile_id(
                'port_profile', 'N1kv port profile',
                cfg.CONF.n1kv.management_port_profile)
        return cls._mgmt_port_profile_id

    @classmethod
    def t1_port_profile_id(cls):
        if cls._t1_port_profile_id is None:
            cls._t1_port_profile_id = cls._get_profile_id(
                'port_profile', 'N1kv port profile',
                cfg.CONF.n1kv.t1_port_profile)
        return cls._t1_port_profile_id

    @classmethod
    def t2_port_profile_id(cls):
        if cls._t2_port_profile_id is None:
            cls._t2_port_profile_id = cls._get_profile_id(
                'port_profile', 'N1kv port profile',
                cfg.CONF.n1kv.t2_port_profile)
        return cls._t2_port_profile_id

    @classmethod
    def t1_network_profile_id(cls):
        if cls._t1_network_profile_id is None:
            cls._t1_network_profile_id = cls._get_profile_id(
                'net_profile', 'N1kv network profile',
                cfg.CONF.n1kv.t1_network_profile)
        return cls._t1_network_profile_id

    @classmethod
    def t2_network_profile_id(cls):
        if cls._t2_network_profile_id is None:
            cls._t2_network_profile_id = cls._get_profile_id(
                'net_profile', 'N1kv network profile',
                cfg.CONF.n1kv.t2_network_profile)
        return cls._t2_network_profile_id

    def create_hosting_device_resources(self, context, complementary_id,
                                        tenant_id, mgmt_context, max_hosted):
        mgmt_port = None
        t_p = []
        if mgmt_context and mgmt_context.get('mgmt_nw_id') and tenant_id:
            # Create port for mgmt interface
            p_spec = {'port': {
                'tenant_id': tenant_id,
                'admin_state_up': True,
                'name': 'mgmt',
                'network_id': mgmt_context['mgmt_nw_id'],
                'mac_address': bc_attr.ATTR_NOT_SPECIFIED,
                'fixed_ips': self._mgmt_subnet_spec(context, mgmt_context),
                'n1kv:profile': self.mgmt_port_profile_id(),
                'device_id': "",
                # Use device_owner attribute to ensure we can query for these
                # ports even before Nova has set device_id attribute.
                'device_owner': complementary_id}}
            try:
                mgmt_port = self._core_plugin.create_port(context, p_spec)
                t1_net_id = self._get_t1_network_id(context, tenant_id)
                t2_net_id = self._get_t2_network_id(context, tenant_id)
                for i in range(max_hosted):
                    # Create T1 trunk network for this router
                    index = str(i + 1)
                    # Create trunk port T1 for VXLAN
                    p_spec['port'].update(
                        {'name': n1kv_const.T1_PORT_NAME + index,
                         'network_id': t1_net_id,
                         'fixed_ips': bc_attr.ATTR_NOT_SPECIFIED,
                         'mac_address': bc_attr.ATTR_NOT_SPECIFIED,
                         'n1kv:profile': self.t1_port_profile_id()})
                    t_p.append(self._core_plugin.create_port(context, p_spec))
                    # Create trunk port T2 for VLAN
                    p_spec['port'].update(
                        {'name': n1kv_const.T2_PORT_NAME + index,
                         'network_id': t2_net_id,
                         'fixed_ips': bc_attr.ATTR_NOT_SPECIFIED,
                         'mac_address': bc_attr.ATTR_NOT_SPECIFIED,
                         'n1kv:profile': self.t2_port_profile_id()})
                    t_p.append(self._core_plugin.create_port(context, p_spec))
            except n_exc.NeutronException as e:
                LOG.error(_LE('Error %s when creating service VM resources. '
                              'Cleaning up.'), e)
                resources = {'ports': t_p}
                self.delete_hosting_device_resources(
                    context, tenant_id, mgmt_port, **resources)
                mgmt_port = None
                t_p = []
        return {'mgmt_port': mgmt_port, 'ports': t_p}

    def get_hosting_device_resources(self, context, id, complementary_id,
                                     tenant_id, mgmt_nw_id):
        ports = []
        mgmt_port = None
        # Ports for hosting device may not yet have 'device_id' set to
        # Nova assigned uuid of VM instance. However, those ports will still
        # have 'device_owner' attribute set to complementary_id. Hence, we
        # use both attributes in the query to ensure we find all ports.
        query = context.session.query(models_v2.Port)
        query = query.filter_by(tenant_id=tenant_id)
        query = query.filter(expr.or_(
            expr.and_(models_v2.Port.device_id != '',
                      models_v2.Port.device_id == id),
            models_v2.Port.device_owner == complementary_id))
        for port_db in query:
            if port_db.network_id != mgmt_nw_id:
                ports.append({'id': port_db.id})
            else:
                mgmt_port = {'id': port_db.id}
        return {'mgmt_port': mgmt_port, 'ports': ports}

    def delete_hosting_device_resources(self, context, tenant_id, mgmt_port,
                                        **kwargs):
        attempts = 1
        port_ids = set(p['id'] for p in kwargs['ports'])

        while mgmt_port is not None or port_ids:
            if attempts == DELETION_ATTEMPTS:
                LOG.warning(_LW('Aborting resource deletion after %d '
                                'unsuccessful attempts'), DELETION_ATTEMPTS)
                return
            else:
                if attempts > 1:
                    eventlet.sleep(SECONDS_BETWEEN_DELETION_ATTEMPTS)
                LOG.info(_LI('Resource deletion attempt %d starting'),
                         attempts)
            # Remove anything created.
            if mgmt_port is not None:
                ml = {mgmt_port['id']}
                self._delete_resources(context, "management port",
                                       self._core_plugin.delete_port,
                                       n_exc.PortNotFound, ml)
                if not ml:
                    mgmt_port = None
            self._delete_resources(context, "trunk port",
                                   self._core_plugin.delete_port,
                                   n_exc.PortNotFound, port_ids)
            attempts += 1
        self._safe_delete_t1_network(context, tenant_id)
        self._safe_delete_t2_network(context, tenant_id)
        LOG.info(_LI('Resource deletion succeeded'))

    def _delete_resources(self, context, name, deleter, exception_type,
                          resource_ids):
        for item_id in resource_ids.copy():
            try:
                deleter(context, item_id)
                resource_ids.remove(item_id)
            except exception_type:
                resource_ids.remove(item_id)
            except n_exc.NeutronException as e:
                LOG.error(_LE('Failed to delete %(resource_name) %(net_id)s '
                              'for service vm due to %(err)s'),
                          {'resource_name': name, 'net_id': item_id, 'err': e})

    def setup_logical_port_connectivity(self, context, port_db,
                                        hosting_device_id):
        # Add the VLAN to the VLANs that the hosting port trunks.
        #TODO(bobmel): update trunking on port once N1kv supports that
        return
        # if (port_db is None or port_db.hosting_info is None or
        #         port_db.hosting_info.hosting_port is None):
        #     return

    def teardown_logical_port_connectivity(self, context, port_db,
                                           hosting_device_id):
        # Remove the VLAN from the VLANs that the hosting port trunks.
        #TODO(bobmel): update trunking on port once N1kv supports that
        return
        # if (port_db is None or port_db.hosting_info is None or
        #         port_db.hosting_info.hosting_port is None):
        #     return

    def extend_hosting_port_info(self, context, port_db, hosting_device,
                                 hosting_info):
        hosting_info['segmentation_id'] = port_db.hosting_info.segmentation_id

    def allocate_hosting_port(self, context, router_id, port_db, network_type,
                              hosting_device_id):
        allocations = self._get_router_ports_with_hosting_info_qry(
            context, router_id).all()
        trunk_mappings = {}
        if not allocations:
            # Router has no ports with hosting port allocated to them yet
            # whatsoever, so we select an unused port (that trunks networks
            # of correct type) on the hosting device.
            id_allocated_port = self._get_unused_service_vm_trunk_port(
                context, hosting_device_id, network_type)
        else:
            # Router has at least one port with hosting port allocated to it.
            # If there is only one allocated hosting port then it may be for
            # the wrong network type. Iterate to determine the hosting port.
            id_allocated_port = None
            for item in allocations:
                if item.hosting_info['network_type'] == network_type:
                    # For VXLAN we need to determine used link local tags.
                    # For VLAN we don't need to but the following lines will
                    # be performed once anyway since we break out of the
                    # loop later. That does not matter.
                    tag = item.hosting_info['segmentation_id']
                    trunk_mappings[item['network_id']] = tag
                    id_allocated_port = item.hosting_info['hosting_port_id']
                else:
                    port_twin_id = item.hosting_info['hosting_port_id']
                if network_type == 'vlan':
                    # For a router port belonging to a VLAN network we can
                    # break here since we now know (or have information to
                    # determine) hosting_port and the VLAN tag is provided by
                    # the core plugin.
                    break
            if id_allocated_port is None:
                # Router only had hosting port for wrong network
                # type allocated yet. So get that port's sibling.
                id_allocated_port = self._get_other_port_id_in_pair(
                    context, port_twin_id, hosting_device_id)
        if id_allocated_port is None:
            # Database must have been messed up if this happens ...
            LOG.debug('n1kv_trunking_driver: Could not allocate hosting port')
            return
        if network_type == 'vxlan':
            # For VXLAN we choose the (link local) VLAN tag
            used_tags = set(trunk_mappings.values())
            allocated_vlan = min(sorted(FULL_VLAN_SET - used_tags))
        else:
            # For VLAN core plugin provides VLAN tag.
            trunk_mappings[port_db['network_id']] = None
            tags = self._core_plugin.get_networks(
                context, {'id': [port_db['network_id']]},
                [pr_net.SEGMENTATION_ID])
            allocated_vlan = (None if tags == []
                              else tags[0].get(pr_net.SEGMENTATION_ID))
        if allocated_vlan is None:
            # Database must have been messed up if this happens ...
            LOG.debug('n1kv_trunking_driver: Could not allocate VLAN')
            return
        return {'allocated_port_id': id_allocated_port,
                'allocated_vlan': allocated_vlan}

    def _get_t1_network_id(self, context, tenant_id, create=True):
        if self._t1_net_id:
            return self._t1_net_id
        t1_sn = self._core_plugin.get_subnets(
            context, filters={'tenant_id': [tenant_id],
                              'cidr': [n1kv_const.T1_SUBNET_CIDR]},
            fields=['network_id'])
        if t1_sn:
            self._t1_net_id = t1_sn[0]['network_id']
        elif create is True:
            self._t1_net_id = self._get_create_t_network_id(
                context, tenant_id, 'T1', n1kv_const.T1_NETWORK_NAME,
                self.t1_network_profile_id(), n1kv_const.T1_SUBNET_NAME,
                n1kv_const.T1_SUBNET_CIDR)
        return self._t1_net_id

    def _get_t2_network_id(self, context, tenant_id, create=True):
        if self._t2_net_id:
            return self._t2_net_id
        t2_sn = self._core_plugin.get_subnets(
            context, filters={'tenant_id': [tenant_id],
                              'cidr': [n1kv_const.T2_SUBNET_CIDR]},
            fields=['network_id'])
        if t2_sn:
            self._t2_net_id = t2_sn[0]['network_id']
        elif create is True:
            self._t2_net_id = self._get_create_t_network_id(
                context, tenant_id, 'T2', n1kv_const.T2_NETWORK_NAME,
                self.t1_network_profile_id(), n1kv_const.T2_SUBNET_NAME,
                n1kv_const.T2_SUBNET_CIDR)
        return self._t2_net_id

    def _get_create_t_network_id(self, context, tenant_id, type_name,
                                 net_name, net_profile, subnet_name,
                                 subnet_cidr):
            # the network that on which trunk ports are created
            n_spec = {'network': {'tenant_id': tenant_id,
                                  'admin_state_up': True,
                                  'name': net_name,
                                  'shared': False,
                                  'port_security_enabled': False,
                                  'n1kv:profile_id': net_profile}}
            net = self._core_plugin.create_network(context, n_spec)
            LOG.debug('Created %(t)s network with name %(name)s and id %(id)s',
                      {'t': type_name, 'name': net_name, 'id': net['id']})
            # Until Nova allows spinning up VMs with VIFs on networks without
            # subnet(s) we create "dummy" subnets for the trunk networks
            s_spec = {'subnet': {
                'tenant_id': tenant_id,
                'network_id': net['id'],
                'admin_state_up': True,
                'name': subnet_name,
                'cidr': subnet_cidr,
                'enable_dhcp': False,
                'gateway_ip': bc_attr.ATTR_NOT_SPECIFIED,
                'allocation_pools': bc_attr.ATTR_NOT_SPECIFIED,
                'ip_version': 4,
                'dns_nameservers': bc_attr.ATTR_NOT_SPECIFIED,
                'host_routes': bc_attr.ATTR_NOT_SPECIFIED}}
            sn = self._core_plugin.create_subnet(context, s_spec)
            LOG.debug('Created %(t_n)s subnet with name %(name)s, id %(id)s '
                      'and CIDR %(cidr)s',
                      {'t_n': type_name, 'name': subnet_name, 'id': sn['id'],
                       'cidr': subnet_cidr})
            return sn['network_id']

    def _safe_delete_t1_network(self, context, tenant_id):
        if self._get_t1_network_id(context, tenant_id, create=False) is None:
            # no t1 network exists so abort
            return
        if self._core_plugin.get_ports_count(context, filters=None) > 0:
            # other trunk ports are using the t1 network so abort
            return
        self._core_plugin.delete_network(context, self._t1_net_id)
        LOG.debug('Deleted unused T1 network with id %(id)s',
                  {'id': self._t1_net_id})
        self._t1_net_id = None

    def _safe_delete_t2_network(self, context, tenant_id):
        if self._get_t2_network_id(context, tenant_id, create=False) is None:
            # no t2 network exists so abort
            return
        if self._core_plugin.get_ports_count(context, filters=None) > 0:
            # other trunk ports are using the t2 network so abort
            return
        self._core_plugin.delete_network(context, self._t2_net_id)
        LOG.debug('Deleted unused T2 network with id %(id)s',
                  {'id': self._t2_net_id})
        self._t2_net_id = None

    def _get_trunk_mappings(self, context, hosting_port_id):
        query = context.session.query(hd_models.HostedHostingPortBinding)
        query = query.filter(
            hd_models.HostedHostingPortBinding.hosting_port_id ==
            hosting_port_id)
        return dict((hhpb.logical_port['network_id'], hhpb.segmentation_id)
                    for hhpb in query)

    def _get_unused_service_vm_trunk_port(self, context, hd_id, network_type):
        name = (n1kv_const.T2_PORT_NAME if network_type == 'vlan'
                else n1kv_const.T1_PORT_NAME)
        attempts = 0
        res = []
        while True:
            # mysql> SELECT * FROM ports WHERE device_id = 'hd_id1' AND
            # id NOT IN (SELECT hosting_port_id FROM hostedhostingportbindings)
            # AND
            # name LIKE '%t1%'
            # ORDER BY name;
            stmt = context.session.query(
                hd_models.HostedHostingPortBinding.hosting_port_id).subquery()
            query = context.session.query(models_v2.Port.id)
            query = query.filter(
                expr.and_(models_v2.Port.device_id == hd_id,
                          ~models_v2.Port.id.in_(stmt),
                          models_v2.Port.name.like('%' + name + '%')))
            query = query.order_by(models_v2.Port.name)
            res = query.first()
            if res is None:
                if attempts >= MAX_HOSTING_PORT_LOOKUP_ATTEMPTS:
                    # This should not happen ...
                    LOG.error(_LE('Hosting port DB inconsistency for '
                                  'hosting device %s'), hd_id)
                    return
                else:
                    # The service VM may not have plugged its VIF into the
                    # Neutron Port yet so we wait and make another lookup.
                    attempts += 1
                    LOG.info(_LI('Attempt %(attempt)d to find trunk ports for '
                                 'hosting device %(hd_id)s failed. Trying '
                                 'again in %(time)d seconds.'),
                             {'attempt': attempts, 'hd_id': hd_id,
                              'time': SECONDS_BETWEEN_HOSTING_PORT_LOOKSUPS})
                    eventlet.sleep(SECONDS_BETWEEN_HOSTING_PORT_LOOKSUPS)
            else:
                break
        return res[0]

    def _get_router_ports_with_hosting_info_qry(self, context, router_id,
                                                device_owner=None,
                                                hosting_port_id=None):
        # Query for a router's ports that have trunking information
        query = context.session.query(models_v2.Port)
        query = query.join(
            hd_models.HostedHostingPortBinding,
            models_v2.Port.id ==
            hd_models.HostedHostingPortBinding.logical_port_id)
        query = query.filter(models_v2.Port.device_id == router_id)
        if device_owner is not None:
            query = query.filter(models_v2.Port.device_owner == device_owner)
        if hosting_port_id is not None:
            query = query.filter(
                hd_models.HostedHostingPortBinding.hosting_port_id ==
                hosting_port_id)
        return query

    def _get_other_port_id_in_pair(self, context, port_id, hosting_device_id):
        query = context.session.query(models_v2.Port)
        query = query.filter(models_v2.Port.id == port_id)
        try:
            port = query.one()
            name, index = port['name'].split(':')
            name += ':'
            if name == n1kv_const.T1_PORT_NAME:
                other_port_name = n1kv_const.T2_PORT_NAME + index
            else:
                other_port_name = n1kv_const.T1_PORT_NAME + index
            query = context.session.query(models_v2.Port)
            query = query.filter(models_v2.Port.device_id == hosting_device_id,
                                 models_v2.Port.name == other_port_name)
            other_port = query.one()
            return other_port['id']
        except (exc.NoResultFound, exc.MultipleResultsFound):
            # This should not happen ...
            LOG.error(_LE('Port trunk pair DB inconsistency for port %s'),
                      port_id)
            return
