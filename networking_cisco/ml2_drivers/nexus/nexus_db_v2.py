# Copyright (c) 2013-2016 Cisco Systems, Inc.
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
#

from oslo_db import exception as db_exc
from oslo_log import log as logging
from oslo_utils import excutils
from random import shuffle
import sqlalchemy as sa
from sqlalchemy.orm import aliased
import sqlalchemy.orm.exc as sa_exc
from sqlalchemy.sql import func

from networking_cisco import backwards_compatibility as bc
from networking_cisco.ml2_drivers.nexus import (
    constants as const)
from networking_cisco.ml2_drivers.nexus import (
    exceptions as c_exc)
from networking_cisco.ml2_drivers.nexus import (
    nexus_models_v2)

LOG = logging.getLogger(__name__)


def get_nexusport_binding(port_id, vlan_id, switch_ip, instance_id):
    """Lists a nexusport binding."""
    LOG.debug("get_nexusport_binding() called")
    return _lookup_all_nexus_bindings(port_id=port_id,
                                      vlan_id=vlan_id,
                                      switch_ip=switch_ip,
                                      instance_id=instance_id)


def get_nexus_switchport_binding(port_id, switch_ip):
    """Lists all bindings for this switch & port."""
    LOG.debug("get_nexus_switchport_binding() called")
    return _lookup_all_nexus_bindings(port_id=port_id,
                                      switch_ip=switch_ip)


def get_nexusvlan_binding(vlan_id, switch_ip):
    """Lists a vlan and switch binding."""
    LOG.debug("get_nexusvlan_binding() called")
    return _lookup_all_nexus_bindings(vlan_id=vlan_id, switch_ip=switch_ip)


def get_reserved_bindings(vlan_id, instance_id, switch_ip=None,
                          port_id=None):
    """Lists reserved bindings."""
    LOG.debug("get_reserved_bindings() called")
    if port_id:
        return _lookup_all_nexus_bindings(vlan_id=vlan_id,
                                          switch_ip=switch_ip,
                                          instance_id=instance_id,
                                          port_id=port_id)
    elif switch_ip:
        return _lookup_all_nexus_bindings(vlan_id=vlan_id,
                                          switch_ip=switch_ip,
                                          instance_id=instance_id)
    else:
        return _lookup_all_nexus_bindings(vlan_id=vlan_id,
                                          instance_id=instance_id)


def update_reserved_binding(vlan_id, switch_ip, instance_id,
                            port_id, is_switch_binding=True,
                            is_native=False, ch_grp=0):
    """Updates reserved binding.

    This overloads port bindings to support reserved Switch binding
    used to maintain the state of a switch so it can be viewed by
    all other neutron processes. There's also the case of
    a reserved port binding to keep switch information on a given
    interface.

    The values of these arguments is as follows:
    :param vlan_id: 0
    :param switch_ip: ip address of the switch
    :param instance_id: fixed string RESERVED_NEXUS_SWITCH_DEVICE_ID_R1
    :param port_id: switch-state of ACTIVE, RESTORE_S1, RESTORE_S2, INACTIVE
    :               port-expected port_id
    :param ch_grp:      0 if no port-channel else non-zero integer
    """
    if not port_id:
        LOG.warning("update_reserved_binding called with no state")
        return
    LOG.debug("update_reserved_binding called")
    session = bc.get_writer_session()
    if is_switch_binding:
        # For reserved switch binding
        binding = _lookup_one_nexus_binding(session=session,
                                            vlan_id=vlan_id,
                                            switch_ip=switch_ip,
                                            instance_id=instance_id)
        binding.port_id = port_id
    else:
        # For reserved port binding
        binding = _lookup_one_nexus_binding(session=session,
                                            vlan_id=vlan_id,
                                            switch_ip=switch_ip,
                                            instance_id=instance_id,
                                            port_id=port_id)
    binding.is_native = is_native
    binding.channel_group = ch_grp
    session.merge(binding)
    session.flush()
    return binding


def remove_reserved_binding(vlan_id, switch_ip, instance_id,
                            port_id):
    """Removes reserved binding.

    This overloads port bindings to support reserved Switch binding
    used to maintain the state of a switch so it can be viewed by
    all other neutron processes. There's also the case of
    a reserved port binding to keep switch information on a given
    interface.
    The values of these arguments is as follows:
    :param vlan_id: 0
    :param switch_ip: ip address of the switch
    :param instance_id: fixed string RESERVED_NEXUS_SWITCH_DEVICE_ID_R1
    :param port_id: switch-state of ACTIVE, RESTORE_S1, RESTORE_S2, INACTIVE
    :               port-expected port_id
    """
    if not port_id:
        LOG.warning("remove_reserved_binding called with no state")
        return
    LOG.debug("remove_reserved_binding called")
    session = bc.get_writer_session()
    binding = _lookup_one_nexus_binding(session=session,
                                        vlan_id=vlan_id,
                                        switch_ip=switch_ip,
                                        instance_id=instance_id,
                                        port_id=port_id)
    for bind in binding:
        session.delete(bind)
    session.flush()
    return binding


def get_reserved_switch_binding(switch_ip=None):
    """Get a reserved switch binding."""

    return get_reserved_bindings(
               const.NO_VLAN_OR_VNI_ID,
               const.RESERVED_NEXUS_SWITCH_DEVICE_ID_R1,
               switch_ip)


def add_reserved_switch_binding(switch_ip, state):
    """Add a reserved switch binding."""

    # overload port_id to contain switch state
    add_nexusport_binding(
        state,
        const.NO_VLAN_OR_VNI_ID,
        const.NO_VLAN_OR_VNI_ID,
        switch_ip,
        const.RESERVED_NEXUS_SWITCH_DEVICE_ID_R1)


def update_reserved_switch_binding(switch_ip, state):
    """Update a reserved switch binding."""

    # overload port_id to contain switch state
    update_reserved_binding(
        const.NO_VLAN_OR_VNI_ID,
        switch_ip,
        const.RESERVED_NEXUS_SWITCH_DEVICE_ID_R1,
        state)


def is_reserved_binding(binding):
    """Identifies switch & port operational bindings.

    There are two types of reserved bindings.

    1. The Switch binding purpose is to keep track of the switch state for when
       replay is enabled.  Keeping it in the db, allows for all processes to
       determine known state of each switch.
    2. The reserved port binding is used with baremetal transactions which
       don't rely on host to interface mapping in the ini file.  It is learned
       from the transaction and kept in the data base for further reference.
    """

    return (binding.instance_id in
           [const.RESERVED_NEXUS_SWITCH_DEVICE_ID_R1])


def add_provider_network(network_id, vlan_id):
    session = bc.get_writer_session()
    row = nexus_models_v2.NexusProviderNetwork(network_id=network_id,
                                               vlan_id=vlan_id)
    session.add(row)
    session.flush()
    return row


def delete_provider_network(network_id):
    session = bc.get_writer_session()
    row = session.query(nexus_models_v2.NexusProviderNetwork).filter_by(
        network_id=network_id).one_or_none()
    if row:
        session.delete(row)
        session.flush()


def is_provider_network(network_id):
    session = bc.get_reader_session()
    row = session.query(nexus_models_v2.NexusProviderNetwork).filter_by(
        network_id=network_id).one_or_none()
    return True if row else False


def is_provider_vlan(vlan_id):
    session = bc.get_reader_session()
    row = session.query(nexus_models_v2.NexusProviderNetwork).filter_by(
        vlan_id=vlan_id).one_or_none()
    return True if row else False


def get_nexusport_switch_bindings(switch_ip):
    """Lists all Nexus port switch bindings."""
    LOG.debug("get_nexusport_switch_bindings() called")
    return _lookup_all_nexus_bindings(switch_ip=switch_ip)


def add_nexusport_binding(port_id, vlan_id, vni, switch_ip, instance_id,
                          is_native=False, ch_grp=0):
    """Adds a nexusport binding."""
    LOG.debug("add_nexusport_binding() called")
    session = bc.get_writer_session()
    binding = nexus_models_v2.NexusPortBinding(port_id=port_id,
                  vlan_id=vlan_id,
                  vni=vni,
                  switch_ip=switch_ip,
                  instance_id=instance_id,
                  is_native=is_native,
                  channel_group=ch_grp)
    session.add(binding)
    session.flush()
    return binding


def remove_nexusport_binding(port_id, vlan_id, vni, switch_ip, instance_id):
    """Removes a nexusport binding."""
    LOG.debug("remove_nexusport_binding() called")
    session = bc.get_writer_session()
    binding = _lookup_all_nexus_bindings(session=session,
                                         vlan_id=vlan_id,
                                         vni=vni,
                                         switch_ip=switch_ip,
                                         port_id=port_id,
                                         instance_id=instance_id)
    for bind in binding:
        session.delete(bind)
    session.flush()
    return binding


def update_nexusport_binding(port_id, new_vlan_id):
    """Updates nexusport binding."""
    if not new_vlan_id:
        LOG.warning("update_nexusport_binding called with no vlan")
        return
    LOG.debug("update_nexusport_binding called")
    session = bc.get_writer_session()
    binding = _lookup_one_nexus_binding(session=session, port_id=port_id)
    binding.vlan_id = new_vlan_id
    session.merge(binding)
    session.flush()
    return binding


def remove_all_nexusport_bindings():
    """Removes all nexusport bindings."""

    LOG.debug("remove_all_nexusport_bindings() called")
    session = bc.get_writer_session()
    session.query(nexus_models_v2.NexusPortBinding).delete()
    session.flush()


def get_nexusvm_bindings(vlan_id, instance_id):
    """Lists nexusvm bindings."""
    LOG.debug("get_nexusvm_bindings() called")
    return _lookup_all_nexus_bindings(instance_id=instance_id,
                                      vlan_id=vlan_id)


def get_port_vlan_switch_binding(port_id, vlan_id, switch_ip):
    """Lists nexusvm bindings."""
    LOG.debug("get_port_vlan_switch_binding() called")
    return _lookup_all_nexus_bindings(port_id=port_id,
                                      switch_ip=switch_ip,
                                      vlan_id=vlan_id)


def get_port_switch_bindings(port_id, switch_ip):
    """List all vm/vlan bindings on a Nexus switch port."""
    LOG.debug("get_port_switch_bindings() called, "
              "port:'%(port_id)s', switch:'%(switch_ip)s'",
              {'port_id': port_id, 'switch_ip': switch_ip})
    try:
        return _lookup_all_nexus_bindings(port_id=port_id,
                                          switch_ip=switch_ip)
    except c_exc.NexusPortBindingNotFound:
        pass


def get_nexussvi_bindings():
    """Lists nexus svi bindings."""
    LOG.debug("get_nexussvi_bindings() called")
    return _lookup_all_nexus_bindings(port_id='router')


def _lookup_nexus_bindings(query_type, session=None, **bfilter):
    """Look up 'query_type' Nexus bindings matching the filter.

    :param query_type: 'all', 'one' or 'first'
    :param session: db session
    :param bfilter: filter for bindings query
    :returns: bindings if query gave a result, else
             raise NexusPortBindingNotFound.
    """
    if session is None:
        session = bc.get_reader_session()
    query_method = getattr(session.query(
        nexus_models_v2.NexusPortBinding).filter_by(**bfilter), query_type)
    try:
        bindings = query_method()
        if bindings:
            return bindings
    except sa_exc.NoResultFound:
        pass
    raise c_exc.NexusPortBindingNotFound(**bfilter)


def _lookup_all_nexus_bindings(session=None, **bfilter):
    return _lookup_nexus_bindings('all', session, **bfilter)


def _lookup_one_nexus_binding(session=None, **bfilter):
    return _lookup_nexus_bindings('one', session, **bfilter)


def _lookup_first_nexus_binding(session=None, **bfilter):
    return _lookup_nexus_bindings('first', session, **bfilter)


def add_nexusnve_binding(vni, switch_ip, device_id, mcast_group):
    """Adds a nexus nve binding."""
    LOG.debug("add_nexusnve_binding() called")
    session = bc.get_writer_session()
    binding = nexus_models_v2.NexusNVEBinding(vni=vni,
                                              switch_ip=switch_ip,
                                              device_id=device_id,
                                              mcast_group=mcast_group)
    session.add(binding)
    session.flush()
    return binding


def remove_nexusnve_binding(vni, switch_ip, device_id):
    """Remove the nexus nve binding."""
    LOG.debug("remove_nexusnve_binding() called")
    session = bc.get_writer_session()
    binding = (session.query(nexus_models_v2.NexusNVEBinding).
               filter_by(vni=vni, switch_ip=switch_ip,
                         device_id=device_id).one())
    if binding:
        session.delete(binding)
        session.flush()
        return binding


def remove_all_nexusnve_bindings():
    """Removes all nexusnve bindings."""

    LOG.debug("remove_all_nexusport_bindings() called")
    session = bc.get_writer_session()
    session.query(nexus_models_v2.NexusNVEBinding).delete()
    session.flush()


def get_nve_vni_switch_bindings(vni, switch_ip):
    """Return the nexus nve binding(s) per switch."""
    LOG.debug("get_nve_vni_switch_bindings() called")
    session = bc.get_reader_session()
    try:
        return (session.query(nexus_models_v2.NexusNVEBinding).
                filter_by(vni=vni, switch_ip=switch_ip).all())
    except sa_exc.NoResultFound:
        return None


def get_nve_vni_member_bindings(vni, switch_ip, device_id):
    """Return the nexus nve binding per switch and device_id."""
    LOG.debug("get_nve_vni_member_bindings() called")
    session = bc.get_reader_session()
    try:
        return (session.query(nexus_models_v2.NexusNVEBinding).
                filter_by(vni=vni, switch_ip=switch_ip,
                          device_id=device_id).all())
    except sa_exc.NoResultFound:
        return None


def get_nve_switch_bindings(switch_ip):
    """Return all the nexus nve bindings for one switch."""
    LOG.debug("get_nve_switch_bindings() called")
    session = bc.get_reader_session()
    try:
        return (session.query(nexus_models_v2.NexusNVEBinding).
                filter_by(switch_ip=switch_ip).all())
    except sa_exc.NoResultFound:
        return None


def get_nve_vni_deviceid_bindings(vni, device_id):
    """Return all the nexus nve bindings for one vni/one device_id."""
    LOG.debug("get_nve_vni_deviceid_bindings() called")
    session = bc.get_reader_session()
    try:
        return (session.query(nexus_models_v2.NexusNVEBinding).
                filter_by(vni=vni, device_id=device_id).all())
    except sa_exc.NoResultFound:
        return None


def _lookup_host_mappings(query_type, session=None, **bfilter):
    """Look up 'query_type' Nexus mappings matching the filter.

    :param query_type: 'all', 'one' or 'first'
    :param session: db session
    :param bfilter: filter for mappings query
    :returns: mappings if query gave a result, else
             raise NexusHostMappingNotFound.
    """
    if session is None:
        session = bc.get_reader_session()
    query_method = getattr(session.query(
        nexus_models_v2.NexusHostMapping).filter_by(**bfilter), query_type)
    try:
        mappings = query_method()
        if mappings:
            return mappings
    except sa_exc.NoResultFound:
        pass
    raise c_exc.NexusHostMappingNotFound(**bfilter)


def _lookup_all_host_mappings(session=None, **bfilter):
    return _lookup_host_mappings('all', session, **bfilter)


def _lookup_one_host_mapping(session=None, **bfilter):
    return _lookup_host_mappings('one', session, **bfilter)


def get_all_host_mappings():
    return(_lookup_all_host_mappings())


def get_host_mappings(host_id):
    return(_lookup_all_host_mappings(host_id=host_id))


def get_switch_host_mappings(switch_ip):
    return(_lookup_all_host_mappings(switch_ip=switch_ip))


def get_switch_and_host_mappings(host_id, switch_ip):
    return(_lookup_all_host_mappings(
        host_id=host_id, switch_ip=switch_ip))


def get_switch_if_host_mappings(switch_ip, if_id):
    return(_lookup_all_host_mappings(switch_ip=switch_ip,
                                     if_id=if_id))


def add_host_mapping(host_id, nexus_ip, interface, ch_grp, is_static):
    """Add Host to interface mapping entry into mapping data base.

    :param host_id: is the name of the host to add
    :param interface: is the interface for this host
    :param nexus_ip: is the ip addr of the nexus switch for this interface
    :param ch_grp: is the port channel this interface belos
    :param is_static: whether this is from conf file or learned from baremetal.
    """

    LOG.debug("add_nexusport_binding() called")
    session = bc.get_writer_session()
    mapping = nexus_models_v2.NexusHostMapping(host_id=host_id,
                  if_id=interface,
                  switch_ip=nexus_ip,
                  ch_grp=ch_grp,
                  is_static=is_static)
    try:
        session.add(mapping)
        session.flush()
    except db_exc.DBDuplicateEntry:
        with excutils.save_and_reraise_exception() as ctxt:
            if is_static:
                ctxt.reraise = False
                LOG.debug("Duplicate static entry encountered "
                          "host=%(host)s, if=%(if)s, ip=%(ip)s",
                          {'host': host_id, 'if': interface,
                           'ip': nexus_ip})

    return mapping


def update_host_mapping(host_id, interface, nexus_ip, new_ch_grp):
    """Change channel_group in host/interface mapping data base."""

    LOG.debug("update_host_mapping called")
    session = bc.get_writer_session()
    mapping = _lookup_one_host_mapping(
                  session=session,
                  host_id=host_id,
                  if_id=interface,
                  switch_ip=nexus_ip)
    mapping.ch_grp = new_ch_grp
    session.merge(mapping)
    session.flush()
    return mapping


def remove_host_mapping(interface, nexus_ip):
    """Remove host to interface mapping entry from mapping data base."""

    LOG.debug("remove_host_mapping() called")
    session = bc.get_writer_session()
    try:
        mapping = _lookup_one_host_mapping(
                      session=session,
                      if_id=interface,
                      switch_ip=nexus_ip)
        session.delete(mapping)
        session.flush()
    except c_exc.NexusHostMappingNotFound:
        pass


def remove_all_static_host_mappings():
    """Remove all entries defined in config file from mapping data base."""

    LOG.debug("remove_host_mapping() called")
    session = bc.get_writer_session()
    try:
        mapping = _lookup_all_host_mappings(
                      session=session,
                      is_static=True)
        for host in mapping:
            session.delete(host)
        session.flush()
    except c_exc.NexusHostMappingNotFound:
        pass


def _lookup_vpc_allocs(query_type, session=None, order=None, **bfilter):
    """Look up 'query_type' Nexus VPC Allocs matching the filter.

    :param query_type: 'all', 'one' or 'first'
    :param session: db session
    :param order: select what field to order data
    :param bfilter: filter for mappings query
    :returns: VPCs if query gave a result, else
             raise NexusVPCAllocNotFound.
    """

    if session is None:
        session = bc.get_reader_session()

    if order:
        query_method = getattr(session.query(
            nexus_models_v2.NexusVPCAlloc).filter_by(**bfilter).order_by(
                order),
            query_type)
    else:
        query_method = getattr(session.query(
            nexus_models_v2.NexusVPCAlloc).filter_by(**bfilter), query_type)

    try:
        vpcs = query_method()
        if vpcs:
            return vpcs
    except sa_exc.NoResultFound:
        pass

    raise c_exc.NexusVPCAllocNotFound(**bfilter)


def _lookup_vpc_count_min_max(session=None, **bfilter):
    """Look up count/min/max Nexus VPC Allocs for given switch.

    :param session: db session
    :param bfilter: filter for mappings query
    :returns: number of VPCs and min value if query gave a result,
             else raise NexusVPCAllocNotFound.
    """

    if session is None:
        session = bc.get_reader_session()

    try:
        res = session.query(
            func.count(nexus_models_v2.NexusVPCAlloc.vpc_id),
            func.min(nexus_models_v2.NexusVPCAlloc.vpc_id),
            func.max(nexus_models_v2.NexusVPCAlloc.vpc_id),
        ).filter(nexus_models_v2.NexusVPCAlloc.switch_ip ==
                 bfilter['switch_ip']).one()

        count = res[0]
        sw_min = res[1]
        sw_max = res[2]

        return count, sw_min, sw_max

    except sa_exc.NoResultFound:
        pass

    raise c_exc.NexusVPCAllocNotFound(**bfilter)


def _lookup_all_vpc_allocs(session=None, order=None, **bfilter):
    return _lookup_vpc_allocs('all', session, order, **bfilter)


def _lookup_one_vpc_allocs(session=None, **bfilter):
    return _lookup_vpc_allocs('one', session, **bfilter)


def _get_free_vpcids_on_switches(switch_ip_list):
    '''Get intersect list of free vpcids in list of switches.'''

    session = bc.get_reader_session()

    prev_view = aliased(nexus_models_v2.NexusVPCAlloc)
    query = session.query(prev_view.vpc_id)
    prev_swip = switch_ip_list[0]

    for ip in switch_ip_list[1:]:
        cur_view = aliased(nexus_models_v2.NexusVPCAlloc)
        cur_swip = ip
        query = query.join(cur_view, sa.and_(
            prev_view.switch_ip == prev_swip, prev_view.active == False,  # noqa
            cur_view.switch_ip == cur_swip, cur_view.active == False,     # noqa
            prev_view.vpc_id == cur_view.vpc_id))
        prev_view = cur_view
        prev_swip = cur_swip

    unique_vpcids = query.all()
    shuffle(unique_vpcids)
    return unique_vpcids


def get_all_switch_vpc_allocs(switch_ip):
    try:
        vpc_list = _lookup_all_vpc_allocs(
            order=nexus_models_v2.NexusVPCAlloc.vpc_id,
            switch_ip=switch_ip)
    except c_exc.NexusVPCAllocNotFound:
        vpc_list = []
    return vpc_list


def get_switch_vpc_count_min_max(switch_ip):
    return(_lookup_vpc_count_min_max(switch_ip=switch_ip))


def get_active_switch_vpc_allocs(switch_ip):
    return(_lookup_all_vpc_allocs(switch_ip=switch_ip, active=True))


def get_free_switch_vpc_allocs(switch_ip):
    return(_lookup_all_vpc_allocs(switch_ip=switch_ip, active=False))


def get_switch_vpc_alloc(switch_ip, vpc_id):
    return(_lookup_one_vpc_allocs(switch_ip=switch_ip, vpc_id=vpc_id))


def init_vpc_entries(nexus_ip, vpc_list):
    """Initialize switch/vpc entries in vpc alloc data base.

    param: nexus_ip  ip addr of the nexus switch for this interface
    param: vpc_list  list of vpc integers to create
    """

    LOG.debug("init_vpc_entries() called")

    if not vpc_list:
        return
    session = bc.get_writer_session()

    for vpc in vpc_list:
        vpc_alloc = nexus_models_v2.NexusVPCAlloc(
            switch_ip=nexus_ip,
            vpc_id=vpc,
            learned=False,
            active=False)
        session.add(vpc_alloc)
    session.flush()


def update_vpc_entry(nexus_ips, vpc_id, learned, active):
    """Change active state in vpc_allocate data base."""

    LOG.debug("update_vpc_entry called")

    session = bc.get_writer_session()

    with session.begin():
        for n_ip in nexus_ips:
            flipit = not active
            x = session.execute(
                sa.update(nexus_models_v2.NexusVPCAlloc).values({
                    'learned': learned,
                    'active': active}).where(sa.and_(
                        nexus_models_v2.NexusVPCAlloc.switch_ip == n_ip,
                        nexus_models_v2.NexusVPCAlloc.vpc_id == vpc_id,
                        nexus_models_v2.NexusVPCAlloc.active == flipit
                    )))
            if x.rowcount != 1:
                raise c_exc.NexusVPCAllocNotFound(
                    switch_ip=n_ip, vpc_id=vpc_id, active=active)


def alloc_vpcid(nexus_ips):
    """Allocate a vpc id for the given list of switch_ips."""

    LOG.debug("alloc_vpc() called")

    vpc_id = 0
    intersect = _get_free_vpcids_on_switches(nexus_ips)
    for intersect_tuple in intersect:
        try:
            update_vpc_entry(nexus_ips, intersect_tuple.vpc_id,
                             False, True)
            vpc_id = intersect_tuple.vpc_id
            break
        except Exception:
            LOG.exception(
                "This exception is expected if another controller "
                "beat us to vpcid %(vpcid)s for nexus %(ip)s",
                {'vpcid': intersect_tuple.vpc_id,
                 'ip': ', '.join(map(str, nexus_ips))})

    return vpc_id


def free_vpcid_for_switch_list(vpc_id, nexus_ips):
    """Free a vpc id for the given list of switch_ips."""

    LOG.debug("free_vpcid_for_switch_list() called")
    if vpc_id != 0:
        update_vpc_entry(nexus_ips, vpc_id, False, False)


def free_vpcid_for_switch(vpc_id, nexus_ip):
    """Free a vpc id for the given switch_ip."""

    LOG.debug("free_vpcid_for_switch() called")
    if vpc_id != 0:
        update_vpc_entry([nexus_ip], vpc_id, False, False)


def delete_vpcid_for_switch(vpc_id, switch_ip):
    """Removes unused vpcid for a switch.

    :param vpc_id: vpc id to remove
    :param switch_ip: ip address of the switch
    """

    LOG.debug("delete_vpcid_for_switch called")
    session = bc.get_writer_session()

    vpc = _lookup_one_vpc_allocs(vpc_id=vpc_id,
                                 switch_ip=switch_ip,
                                 active=False)
    session.delete(vpc)
    session.flush()
