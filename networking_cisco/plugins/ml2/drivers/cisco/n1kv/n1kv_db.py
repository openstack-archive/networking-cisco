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

import sqlalchemy.orm.exc as sa_exc
from sqlalchemy import sql

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import config
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import n1kv_models

from neutron import context as ncontext
import neutron.db.api as db
from neutron.db import models_v2
from neutron.plugins.common import constants as p_const


def add_network_binding(network_id,
                        network_type,
                        segment_id,
                        netp_id,
                        db_session=None):
    """
    Create the network to network profile binding.

    :param db_session: database session
    :param network_id: UUID representing the network
    :param network_type: string representing type of network (VLAN, VXLAN)
    :param segment_id: integer representing VLAN or VXLAN ID
    :param netp_id: network profile ID based on which this network
                    is created
    """
    db_session = db_session or db.get_session()
    binding = n1kv_models.N1kvNetworkBinding(network_id=network_id,
                                             network_type=network_type,
                                             segmentation_id=segment_id,
                                             profile_id=netp_id)
    db_session.add(binding)
    db_session.flush()
    return binding


def update_network_binding_with_segment_id(net_id,
                                           segment_id,
                                           db_session):
    """
    Update the network to network profile binding

    :param net_id: UUID representing the network
    :param segment_id: integer representing VLAN or VXLAN ID
    :param db_session: database session
    """
    with db_session.begin(subtransactions=True):
        db_session.query(n1kv_models.N1kvNetworkBinding).filter_by(
            network_id=net_id).update({'segmentation_id': segment_id})


def update_policy_profile_binding_with_tenant_id(profile_id,
                                                 tenant_id, db_session):
    with db_session.begin(subtransactions=True):
        db_session.query(n1kv_models.ProfileBinding).filter_by(
            profile_id=profile_id, profile_type='policy',
            tenant_id=n1kv_const.TENANT_ID_NOT_SET
        ).update({'tenant_id': tenant_id})


def get_network_profile_by_type(segment_type, db_session=None):
    """
    Retrieve a network profile using its type.

    :param segment_type: string repsresenting the type of segment
    :param db_session: database session
    :returns: network profile of the given segment type
    """
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.NetworkProfile).
                filter_by(segment_type=segment_type).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.NetworkProfileNotFound(profile=segment_type)


def get_network_profile_by_name(name, db_session=None):
    """Retrieve a network profile using its name."""
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.NetworkProfile).
                filter_by(name=name).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.NetworkProfileNotFound(profile=name)


def get_network_profile_by_uuid(netp_id, db_session=None):
    """Retrieve a network profile using its UUID."""
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.NetworkProfile).
                filter_by(id=netp_id).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.NetworkProfileNotFound(profile=netp_id)


def add_network_profile(netp_name, netp_type,
                        netp_sub_type=None, db_session=None):
    """
    Create a network profile.

    :param netp_name: string representing the name of the network profile
    :param netp_type: string representing the type of the network profile
    :param netp_sub_type: string representing sub-type of the network profile
    :param db_session: database session
    :returns: network profile object
    """
    db_session = db_session or db.get_session()
    netp = n1kv_models.NetworkProfile(name=netp_name,
                                      segment_type=netp_type,
                                      sub_type=netp_sub_type)
    db_session.add(netp)
    db_session.flush()
    return netp


def remove_network_profile(netp_id, db_session=None):
    """
    Delete a network profile.

    :param netp_id: string representing the UUID of the network profile
    :param db_session: database session
    """
    db_session = db_session or db.get_session()
    nprofile = (db_session.query(n1kv_models.NetworkProfile).
                filter_by(id=netp_id).first())
    if nprofile:
        db_session.delete(nprofile)
        db_session.flush()


def get_policy_profile_by_name(name, db_session=None):
    """
    Retrieve policy profile by name.

    :param name: string representing the name of the policy profile
    :param db_session: database session
    :returns: policy profile object
    """
    db_session = db_session or db.get_session()
    vsm_hosts = config.get_vsm_hosts()
    pp = n1kv_models.PolicyProfile
    pprofiles = db_session.query(pp).filter(
        sql.and_(pp.name == name, pp.vsm_ip.in_(vsm_hosts))).all()
    if pprofiles and check_policy_profile_exists_on_all_vsm(pprofiles,
                                                            vsm_hosts):
        return pprofiles[0]
    else:
        raise n1kv_exc.PolicyProfileNotFound(profile=name)


def get_policy_profile_by_uuid(db_session, pprofile_id):
    """
    Retrieve policy profile by its UUID.

    :param db_session: database session
    :param profile_id: string representing the UUID of the policy profile
    :returns: policy profile object
    """
    db_session = db_session or db.get_session()
    vsm_hosts = config.get_vsm_hosts()
    pp = n1kv_models.PolicyProfile
    pprofiles = (db_session.query(pp).
                 filter(sql.and_(pp.id == pprofile_id,
                 pp.vsm_ip.in_(vsm_hosts))).all())
    if pprofiles and check_policy_profile_exists_on_all_vsm(pprofiles,
                                                            vsm_hosts):
        return pprofiles[0]
    else:
        raise n1kv_exc.PolicyProfileNotFound(profile=pprofile_id)


def get_policy_profiles_by_host(vsm_ip, db_session=None):
    """
    Retrieve policy profile by host.

    :param vsm_ip: string representing the ip address of the host(VSM)
    :param db_session: database session
    :returns: policy profile object
    """
    db_session = db_session or db.get_session()
    with db_session.begin(subtransactions=True):
        try:
            return (db_session.query(n1kv_models.PolicyProfile).
                    filter_by(vsm_ip=vsm_ip))
        except sa_exc.NoResultFound:
            raise n1kv_exc.PolicyProfileNotFound(profile=vsm_ip)


def get_profile_binding(tenant_id, profile_id, db_session=None):
    """Get Profile - Tenant binding."""
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.ProfileBinding).filter_by(
                tenant_id=tenant_id, profile_id=profile_id).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.ProfileTenantBindingNotFound(profile_id=profile_id)


def get_profiles_for_tenant(db_session, tenant_id, profile_type):
    """Get network or policy profile IDs for a tenant."""
    bindings = (db_session.query(n1kv_models.ProfileBinding.profile_id)
                .filter_by(tenant_id=tenant_id,
                           profile_type=profile_type).all())
    return [profile_id for (profile_id, ) in bindings]


def policy_profile_in_use(profile_id, db_session=None):
    """
    Checks if a policy profile is being used in a port binding.
    :param profile_id: UUID of the policy profile to be checked
    :param db_session: database session
    :returns: boolean
    """
    db_session = db_session or db.get_session()
    ret = (db_session.query(n1kv_models.N1kvPortBinding).
           filter_by(profile_id=profile_id).first())
    return bool(ret)


def check_policy_profile_exists_on_all_vsm(pprofiles, vsm_hosts):
    """Checks if policy profile is present on all VSM.
    :param pprofiles: all the port profile rows for a particular profile
    :param vsm_hosts: list of configured VSMs
    :returns: boolean
    """
    return (len(pprofiles) == len(vsm_hosts) and
            len(set(pprofile['id'] for pprofile in pprofiles)) == 1)


def get_network_binding(network_id, db_session=None):
    """
    Retrieve network binding.

    :param network_id: string representing the UUID of the network
    :param db_session: database session
    :returns: network to network profile binding object
    """
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.N1kvNetworkBinding).
                filter_by(network_id=network_id).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.NetworkBindingNotFound(network_id=network_id)


def add_policy_binding(port_id, pprofile_id, db_session=None):
    """
    Create the port to policy profile binding.

    :param port_id: string representing the UUID of the port
    :param pprofile_id: string representing the UUID of the policy profile
    :param db_session: database session
    :returns: port to policy profile binding object
    """
    db_session = db_session or db.get_session()
    with db_session.begin(subtransactions=True):
        binding = n1kv_models.N1kvPortBinding(port_id=port_id,
                                              profile_id=pprofile_id)
        db_session.add(binding)
        return binding


def add_profile_tenant_binding(profile_type, profile_id, tenant_id,
                               db_session):
    db_session = db_session or db.get_session()
    with db_session.begin(subtransactions=True):
        binding = n1kv_models.ProfileBinding(profile_type=profile_type,
                                             profile_id=profile_id,
                                             tenant_id=tenant_id)
        db_session.add(binding)
        return binding


def remove_profile_tenant_binding(profile_type, profile_id, tenant_id,
                                  db_session):
    db_session = db_session or db.get_session()
    with db_session.begin(subtransactions=True):
        binding = get_profile_binding(tenant_id=tenant_id,
                                      profile_id=profile_id,
                                      db_session=db_session)
        db_session.delete(binding)


def get_policy_binding(port_id, db_session=None):
    """
    Retrieve port to policy profile binding.

    :param port_id: string representing the UUID of the port
    :param db_session: database session
    :returns: port to policy profile binding object
    """
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.N1kvPortBinding).
                filter_by(port_id=port_id).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.PortBindingNotFound(port_id=port_id)


def get_network_profiles(db_base_plugin=None):
    """
    Get details for all network profiles from N1kv table of the neutron db.

    :returns: List of network profile objects
    """
    db_session = db.get_session()
    return db_session.query(n1kv_models.NetworkProfile).all()


def get_networks(db_base_plugin):
    """
    Get details for all networks, from non-N1kv tables of the neutron database.

    :param db_base_plugin: Instance of the NeutronDbPluginV2 class
    :returns: list of network dictionaries
    """
    context = ncontext.get_admin_context()
    return db_base_plugin.get_networks(context)


def get_subnets(db_base_plugin):
    """
    Get details for all subnets, from non-N1kv tables of the neutron database

    :param db_base_plugin: Instance of the NeutronDbPluginV2 class
    :returns: list of subnet dictionaries
    """
    context = ncontext.get_admin_context()
    return db_base_plugin.get_subnets(context)


def get_ports(db_base_plugin):
    """
    Get details for all ports, from non-N1kv tables of the neutron database

    :param db_base_plugin:  Instance of the NeutronDbPluginV2 class
    :returns: list of port dictionaries
    """
    context = ncontext.get_admin_context()
    return db_base_plugin.get_ports(context)


def get_network_profile_by_network(network_id):
    """
    Given a network, get all the details of its network profile

    :param network_id: UUID of the network
    :returns: network profile object
    """
    db_session = db.get_session()
    network_profile_local = (db_session.query(n1kv_models.N1kvNetworkBinding).
                             filter_by(network_id=network_id).one())
    return (db_session.query(n1kv_models.NetworkProfile).
            filter_by(id=network_profile_local.profile_id).one())


def get_vxlan_networks():
    """
    Get all VxLAN networks.

    :return: A list of all VxLAN networks
    """
    db_session = db.get_session()
    network_binding_rows = db_session.query(
        models_v2.Network, n1kv_models.N1kvNetworkBinding).filter(
            models_v2.Network.id ==
            n1kv_models.N1kvNetworkBinding.network_id).filter(
                n1kv_models.N1kvNetworkBinding.network_type ==
                p_const.TYPE_VXLAN).all()
    return [network for (network, binding) in network_binding_rows]
