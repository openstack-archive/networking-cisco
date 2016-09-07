# Copyright 2015 Cisco Systems, Inc.
# All Rights Reserved.
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
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from sqlalchemy.orm import exc

from networking_cisco._i18n import _LE

from neutron.api import extensions as api_extensions
import neutron.db.api as db
from neutron.db import common_db_mixin as base_db
from neutron.plugins.common import constants as p_const
from neutron_lib import exceptions as n_exc

from networking_cisco import backwards_compatibility as bc_attr
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    extensions)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_client)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_db)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_models)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv.extensions import (
    network_profile as network_profile_module)

LOG = logging.getLogger(__name__)

cfg.CONF.import_group(
    'ml2_cisco_n1kv',
    'networking_cisco.plugins.ml2.drivers.cisco.n1kv.config')


class NetworkProfile_db_mixin(network_profile_module.NetworkProfilePluginBase,
                              base_db.CommonDbMixin):
    """Network Profile Mixin class."""

    def _make_network_profile_dict(self, network_profile, fields=None):
        res = {"id": network_profile["id"],
               "name": network_profile["name"],
               "segment_type": network_profile["segment_type"],
               "sub_type": network_profile["sub_type"],
               "multicast_ip_index": network_profile["multicast_ip_index"],
               "multicast_ip_range": network_profile["multicast_ip_range"],
               "physical_network": network_profile["physical_network"]}
        return self._fields(res, fields)

    def _get_network_collection_for_tenant(self, db_session, model, tenant_id):
        net_profile_ids = n1kv_db.get_profiles_for_tenant(
            db_session=db_session,
            tenant_id=tenant_id,
            profile_type=n1kv_const.NETWORK)
        # get default VLAN and VXLAN network profile objects
        default_vlan_profile = n1kv_db.get_network_profile_by_name(
            n1kv_const.DEFAULT_VLAN_NETWORK_PROFILE_NAME)
        default_vxlan_profile = n1kv_db.get_network_profile_by_name(
            n1kv_const.DEFAULT_VXLAN_NETWORK_PROFILE_NAME)
        # append IDs of default network profiles to the net_profile_ids list
        net_profile_ids.append(default_vlan_profile.id)
        net_profile_ids.append(default_vxlan_profile.id)
        network_profiles = (db_session.query(model).filter(model.id.in_(
            net_profile_ids)))
        return [self._make_network_profile_dict(p) for p in network_profiles]

    def _add_network_profile(self, network_profile, db_session=None):
        """Create a network profile."""
        db_session = db_session or db.get_session()
        with db_session.begin(subtransactions=True):
            kwargs = {"name": network_profile["name"],
                      "segment_type": network_profile["segment_type"]}
            if network_profile["segment_type"] == p_const.TYPE_VXLAN:
                kwargs["multicast_ip_index"] = 0
                kwargs["multicast_ip_range"] = network_profile[
                    "multicast_ip_range"]
                kwargs["sub_type"] = network_profile["sub_type"]
            elif network_profile["segment_type"] == n1kv_const.TYPE_TRUNK:
                kwargs["sub_type"] = network_profile["sub_type"]
            net_profile = n1kv_models.NetworkProfile(**kwargs)
            db_session.add(net_profile)
            return net_profile

    def _get_network_profile(self, db_session, prof_id):
        try:
            return (db_session.query(n1kv_models.NetworkProfile).
                    filter_by(id=prof_id).one())
        except exc.NoResultFound:
            raise n1kv_exc.NetworkProfileNotFound(profile=prof_id)

    def _get_network_profiles(self, db_session=None, physical_network=None):
        """
        Retrieve all network profiles.

        Get Network Profiles on a particular physical network, if physical
        network is specified. If no physical network is specified, return
        all network profiles.
        """
        db_session = db_session or db.get_session()
        if physical_network:
            return (db_session.query(n1kv_models.NetworkProfile).
                    filter_by(physical_network=physical_network))
        return db_session.query(n1kv_models.NetworkProfile)

    def _remove_network_profile(self, nprofile_id, db_session=None):
        """Delete a network profile."""
        db_session = db_session or db.get_session()
        with db_session.begin(subtransactions=True):
            nprofile = (db_session.query(n1kv_models.NetworkProfile).
                        filter_by(id=nprofile_id).first())
            if nprofile:
                db_session.delete(nprofile)
            # also delete all bindings with this profile
            db_session.query(n1kv_models.ProfileBinding).filter_by(
                profile_id=nprofile_id).delete()
            return nprofile

    def _is_reserved_name(self, profile_name):
        """Check if the input arg is a reserved name."""
        reserved_names = [n1kv_const.DEFAULT_VLAN_NETWORK_PROFILE_NAME,
                          n1kv_const.DEFAULT_VXLAN_NETWORK_PROFILE_NAME]
        return profile_name in reserved_names

    def _validate_network_profile(self, net_p):
        """
        Validate completeness of a network profile arguments.

        :param net_p: network profile object
        """
        if self._is_reserved_name(net_p["name"]):
            msg = _LE("Reserved name used for network profile name")
            LOG.error(msg)
            raise n_exc.InvalidInput(error_message=msg)
        if net_p["segment_type"] == "":
            msg = _LE("Arguments segment_type missing"
                      " for network profile %s") % net_p["name"]
            LOG.error(msg)
            raise n_exc.InvalidInput(error_message=msg)
        segment_type = net_p["segment_type"].lower()
        if segment_type == n1kv_const.CLI_SEG_TYPE_OVERLAY:
            # Convert from CLI to internal type
            segment_type = p_const.TYPE_VXLAN
            net_p["segment_type"] = p_const.TYPE_VXLAN
        if segment_type not in [p_const.TYPE_VLAN,
                                p_const.TYPE_VXLAN,
                                n1kv_const.TYPE_TRUNK]:
            msg = _LE("Segment_type should either be vlan, vxlan, "
                      "or trunk")
            LOG.error(msg)
            raise n_exc.InvalidInput(error_message=msg)
        if segment_type == p_const.TYPE_VLAN:
            if "physical_network" not in net_p:
                msg = _LE("Argument physical_network missing "
                          "for network profile %s") % net_p["name"]
                LOG.error(msg)
                raise n_exc.InvalidInput(error_message=msg)
        if segment_type in [n1kv_const.TYPE_TRUNK,
                            p_const.TYPE_VXLAN]:
            if not bc_attr.is_attr_set(net_p.get("sub_type")):
                msg = _LE("Argument sub_type missing "
                          "for network profile %s") % net_p["name"]
                LOG.error(msg)
                raise n_exc.InvalidInput(error_message=msg)
        if segment_type == p_const.TYPE_VXLAN:
            sub_type = net_p['sub_type']
            # Validate sub-type
            allowed_sub_types = [n1kv_const.CLI_VXLAN_MODE_NATIVE,
                                 n1kv_const.CLI_VXLAN_MODE_ENHANCED]
            if sub_type not in allowed_sub_types:
                msg = _LE("Sub_type should be either 'native' or 'enhanced'")
                LOG.error(msg)
                raise n_exc.InvalidInput(error_message=msg)
            if sub_type != n1kv_const.CLI_VXLAN_MODE_NATIVE:
                net_p['multicast_ip_range'] = '0.0.0.0'
            else:
                group_ip = cfg.CONF.ml2_type_vxlan.vxlan_group
                multicast_ip_range = net_p.get("multicast_ip_range")
                if not bc_attr.is_attr_set(multicast_ip_range):
                    if not group_ip:
                        msg = (_LE("Argument multicast_ip_range missing"
                                   " for VXLAN multicast network profile %s")
                               % net_p["name"])
                        LOG.error(msg)
                        raise n_exc.InvalidInput(error_message=msg)
                    else:
                        # Use the global value from conf
                        net_p['multicast_ip_range'] = "-".join(
                            [group_ip, group_ip])
                self._validate_multicast_ip_range(net_p)
        else:
            net_p['multicast_ip_range'] = '0.0.0.0'

    def _validate_multicast_ip_range(self, network_profile):
        """
        Validate multicast ip range values.

        :param network_profile: network profile object
        """
        try:
            min_ip, max_ip = (network_profile
                              ['multicast_ip_range'].split('-', 1))
        except ValueError:
            msg = _LE("Invalid multicast ip address range. "
                      "example range: 224.1.1.1-224.1.1.10")
            LOG.error(msg)
            raise n_exc.InvalidInput(error_message=msg)
        for ip in [min_ip, max_ip]:
            try:
                if not netaddr.IPAddress(ip).is_multicast():
                    msg = _LE("%s is not a valid multicast ip address") % ip
                    LOG.error(msg)
                    raise n_exc.InvalidInput(error_message=msg)
                if netaddr.IPAddress(ip) <= netaddr.IPAddress('224.0.0.255'):
                    msg = _LE("%s is reserved multicast ip address") % ip
                    LOG.error(msg)
                    raise n_exc.InvalidInput(error_message=msg)
            except netaddr.AddrFormatError:
                msg = _LE("%s is not a valid ip address") % ip
                LOG.error(msg)
                raise n_exc.InvalidInput(error_message=msg)
        if netaddr.IPAddress(min_ip) > netaddr.IPAddress(max_ip):
            msg = (_LE("Invalid multicast IP range '%(min_ip)s-%(max_ip)s':"
                       " Range should be from low address to high address")
                   % {'min_ip': min_ip, 'max_ip': max_ip})
            LOG.error(msg)
            raise n_exc.InvalidInput(error_message=msg)

    def _create_profile_binding(self, db_session, tenant_id, profile_id):
        """Create Network Profile association with a tenant."""
        db_session = db_session or db.get_session()
        try:
            binding = n1kv_db.get_profile_binding(db_session=db_session,
                                                  tenant_id=tenant_id,
                                                  profile_id=profile_id)
        except n1kv_exc.ProfileTenantBindingNotFound:
            with db_session.begin(subtransactions=True):
                binding = n1kv_db.add_profile_tenant_binding(
                    profile_type=n1kv_const.NETWORK,
                    profile_id=profile_id,
                    tenant_id=tenant_id,
                    db_session=db_session)
        return binding

    def _network_profile_in_use(self, db_session, prof_id):
        """Verify whether a segment is allocated for given network profile."""
        with db_session.begin(subtransactions=True):
            return (db_session.query(n1kv_models.N1kvNetworkBinding).
                    filter_by(profile_id=prof_id)).first()

    def get_network_profile(self, context, prof_id, fields=None):
        """
        Retrieve a network profile for the given UUID.

        :param context: neutron api request context
        :param prof_id: UUID representing network profile to fetch
        :params fields: a list of strings that are valid keys in a network
                        profile dictionary. Only these fields will be returned
        :returns: network profile dictionary
        """
        profile = self._get_network_profile(context.session, prof_id)
        return self._make_network_profile_dict(profile, fields)

    def get_network_profiles(self, context, filters=None, fields=None):
        """
        Retrieve a list of network profiles.

        Retrieve all network profiles if tenant is admin. For a non-admin
        tenant, retrieve all network profiles belonging to this tenant only.
        :param context: neutron api request context
        :param filters: a dictionary with keys that are valid keys for a
                        network profile object. Values in this dictiontary are
                        an iterable containing values that will be used for an
                        exact match comparison for that value. Each result
                        returned by this function will have matched one of the
                        values for each key in filters
        :params fields: a list of strings that are valid keys in a network
                        profile dictionary. Only these fields will be returned
        :returns: list of all network profiles
        """
        if (context.is_admin or
            not cfg.CONF.ml2_cisco_n1kv.restrict_network_profiles):
            return self._get_collection(context, n1kv_models.NetworkProfile,
                                        self._make_network_profile_dict,
                                        filters=filters, fields=fields)
        return self._get_network_collection_for_tenant(context.session,
                                                       n1kv_models.
                                                       NetworkProfile,
                                                       context.tenant_id)

    def get_network_profile_bindings(self, context, filters=None, fields=None):
        network_profiles_collection = self.get_network_profiles(
            context, filters, fields)
        bindings = []
        for net_prof in network_profiles_collection:
            bindings.append({'profile_id': net_prof['id'], 'tenant_id':
                context.tenant_id})
        return bindings

    def create_network_profile(self, context, network_profile, fields=None):
        """
        Create a network profile.

        :param context: neutron api request context
        :param network_profile: network profile dictionary
        :returns: network profile dictionary
        """
        np = network_profile["network_profile"]
        self._validate_network_profile(np)
        with context.session.begin(subtransactions=True):
            net_profile = self._add_network_profile(db_session=context.session,
                                                    network_profile=np)
            self._create_profile_binding(context.session, context.tenant_id,
                                         net_profile.id)
            if np.get(n1kv_const.ADD_TENANTS):
                for tenant in np[n1kv_const.ADD_TENANTS]:
                    self._create_profile_binding(context.session,
                                                 tenant,
                                                 net_profile.id)
        return self._make_network_profile_dict(net_profile)

    def delete_network_profile(self, context, prof_id):
        """
        Delete a network profile.

        :param context: neutron api request context
        :param prof_id: UUID representing network profile to delete
        :returns: deleted network profile dictionary
        """
        # Check whether the network profile is in use.
        if self._network_profile_in_use(context.session, prof_id):
            raise n1kv_exc.NetworkProfileInUse(profile=prof_id)
        # Check whether default network profile is being deleted.
        np = self._get_network_profile(context.session, prof_id)
        if self._is_reserved_name(np['name']):
            raise n1kv_exc.ProfileDeletionNotSupported(profile=np['name'])
        nprofile = self._remove_network_profile(prof_id, context.session)
        return self._make_network_profile_dict(nprofile)

    def update_network_profile(self, context, prof_id, network_profile):
        pass


class NetworkProfilePlugin(NetworkProfile_db_mixin):
    """Implementation of the Cisco N1KV Network Profile Service Plugin."""
    supported_extension_aliases = ["network_profile"]

    def __init__(self):
        super(NetworkProfilePlugin, self).__init__()
        api_extensions.append_api_extensions_path(extensions.__path__)
        # Initialize N1KV client
        self.n1kvclient = n1kv_client.Client()

    def get_network_profiles(self, context, filters=None, fields=None):
        """Return Cisco N1KV network profiles."""
        return super(NetworkProfilePlugin, self).get_network_profiles(context,
                                                                      filters,
                                                                      fields)

    def get_network_profile(self, context, prof_id, fields=None):
        """Return Cisco N1KV network profile by its UUID."""
        return super(NetworkProfilePlugin, self).get_network_profile(context,
                                                                     prof_id,
                                                                     fields)

    def get_network_profile_bindings(self, context,
                                     filters=None,
                                     fields=None):
        return super(NetworkProfilePlugin,
                     self).get_network_profile_bindings(context, fields,
                                                        filters)

    def create_network_profile(self, context, network_profile, fields=None):
        """
        Create a network profile.

        :param context: neutron api request context
        :param network_profile: network profile dictionary
        :returns: network profile object
        """
        with context.session.begin(subtransactions=True):
            net_p = super(NetworkProfilePlugin,
                          self).create_network_profile(context,
                                                       network_profile)
        try:
            # Create a network profile on the VSM
            self.n1kvclient.create_network_segment_pool(net_p)
        # Catch any exception here and cleanup if so
        except (n1kv_exc.VSMConnectionFailed, n1kv_exc.VSMError):
            with excutils.save_and_reraise_exception():
                super(NetworkProfilePlugin,
                      self).delete_network_profile(context, net_p['id'])
        return net_p

    def delete_network_profile(self, context, prof_id):
        """
        Delete a network profile.

        :param context: neutron api request context
        :param prof_id: UUID of the network profile to delete
        :returns: deleted network profile object
        """
        with context.session.begin(subtransactions=True):
            net_p = (super(NetworkProfilePlugin, self).
                delete_network_profile(context, prof_id))
        self.n1kvclient.delete_network_segment_pool(prof_id)
        log_net_name = prof_id + n1kv_const.LOGICAL_NETWORK_SUFFIX
        self.n1kvclient.delete_logical_network(log_net_name)
        return net_p

    def update_network_profile(self, context, prof_id, network_profile):
        """
        Update a network profile.

        :param context: neutron api request context
        :param prof_id: UUID of the network profile to update
        :param network_profile: dictionary containing network profile object
        """
        session = context.session
        with session.begin(subtransactions=True):
            net_p = (super(NetworkProfilePlugin, self).
                     update_network_profile(context,
                                            prof_id,
                                            network_profile))
        # Update and handle exception on VSM
        # TODO(sopatwar): Add update method to n1kv_client
        return net_p
