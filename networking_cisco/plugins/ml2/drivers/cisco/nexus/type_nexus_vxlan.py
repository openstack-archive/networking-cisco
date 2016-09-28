# Copyright (c) 2014-2016 Cisco Systems, Inc.
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

import netaddr
import six

from oslo_config import cfg
from oslo_log import log
from oslo_utils import excutils
import sqlalchemy as sa

from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    constants as const)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_models_v2)

from networking_cisco._i18n import _, _LE, _LI, _LW

from neutron.db import api as db_api
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2.drivers import type_tunnel
from neutron_lib import exceptions as exc

LOG = log.getLogger(__name__)

# Nexus switches start VNI at 4096 = max VLAN + 2 (2 for reserved VLAN 0, 4095)
MIN_NEXUS_VNI = p_const.MAX_VLAN_TAG + 2

nexus_vxlan_opts = [
    cfg.ListOpt('vni_ranges',
                default=[],
                help=_("List of global VNID ranges in the format - a:b, c:d."
                       "Multiple ranges can be separated by a comma")),
    cfg.ListOpt('mcast_ranges',
                default=[],
                help=_("List of multicast groups to be used for global VNIDs"
                       "in the format - a:b,c,e:f."))
]

cfg.CONF.register_opts(nexus_vxlan_opts, "ml2_type_nexus_vxlan")


class NexusVxlanTypeDriver(type_tunnel.TunnelTypeDriver):
    def __init__(self):
        super(NexusVxlanTypeDriver, self).__init__(
            nexus_models_v2.NexusVxlanAllocation)

    def _get_mcast_group_for_vni(self, session, vni):
        mcast_grp = (session.query(nexus_models_v2.NexusMcastGroup).
                     filter_by(associated_vni=vni).first())
        if not mcast_grp:
            mcast_grp = self._allocate_mcast_group(session, vni)
        return mcast_grp

    def get_type(self):
        return const.TYPE_NEXUS_VXLAN

    def initialize(self):
        self.tunnel_ranges = []
        self.conf_mcast_ranges = cfg.CONF.ml2_type_nexus_vxlan.mcast_ranges
        self._verify_vni_ranges()
        self.sync_allocations()

    def _verify_vni_ranges(self):
        try:
            self.conf_vxlan_ranges = self._parse_nexus_vni_ranges(
                cfg.CONF.ml2_type_nexus_vxlan.vni_ranges, self.tunnel_ranges)
            LOG.info(_LI("Cisco Nexus VNI ranges: %s"), self.conf_vxlan_ranges)
        except Exception:
            LOG.exception(_LE("Failed to parse vni_ranges. "
                              "Service terminated!"))
            raise SystemExit()

    def _parse_nexus_vni_ranges(self, tunnel_ranges, current_range):
        for entry in tunnel_ranges:
            entry = entry.strip()
            try:
                tun_min, tun_max = entry.split(':')
                tun_min = tun_min.strip()
                tun_max = tun_max.strip()
                tunnel_range = int(tun_min), int(tun_max)
            except ValueError as ex:
                raise exc.NetworkTunnelRangeError(tunnel_range=entry, error=ex)

            self._parse_nexus_vni_range(tunnel_range)
            current_range.append(tunnel_range)

        LOG.info(_LI("Nexus VXLAN ID ranges: %(range)s"),
                 {'range': current_range})

    def _parse_nexus_vni_range(self, tunnel_range):
        """Raise an exception for invalid tunnel range or malformed range."""
        for ident in tunnel_range:
            if not self._is_valid_nexus_vni(ident):
                raise exc.NetworkTunnelRangeError(
                    tunnel_range=tunnel_range,
                    error=_("%(id)s is not a valid Nexus VNI value.") %
                    {'id': ident})

        if tunnel_range[1] < tunnel_range[0]:
            raise exc.NetworkTunnelRangeError(
                tunnel_range=tunnel_range,
                error=_("End of tunnel range is less than start of "
                        "tunnel range."))

    def _is_valid_nexus_vni(self, vni):
        return MIN_NEXUS_VNI <= vni <= p_const.MAX_VXLAN_VNI

    def _parse_mcast_ranges(self):
        ranges = (range.split(':') for range in self.conf_mcast_ranges)
        for low, high in ranges:
            for mcast_ip in netaddr.iter_iprange(low, high):
                if mcast_ip.is_multicast():
                    yield str(mcast_ip)

    def _allocate_mcast_group(self, session, vni):
        allocs = dict(session.query(nexus_models_v2.
                                    NexusMcastGroup.mcast_group,
                      sa.func.count(nexus_models_v2.
                                    NexusMcastGroup.mcast_group)).
                      group_by(nexus_models_v2.
                               NexusMcastGroup.mcast_group).all())

        mcast_for_vni = None
        for mcast_ip in self._parse_mcast_ranges():
            if not six.u(mcast_ip) in allocs:
                mcast_for_vni = mcast_ip
                break
        try:
            if not mcast_for_vni:
                mcast_for_vni = min(allocs, key=allocs.get)
        except ValueError:
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE("Unable to allocate a multicast group for "
                                  "VNID:%s"), vni)

        alloc = nexus_models_v2.NexusMcastGroup(mcast_group=mcast_for_vni,
                                associated_vni=vni)

        session.add(alloc)
        session.flush()
        return mcast_for_vni

    def allocate_tenant_segment(self, session):
        alloc = self.allocate_partially_specified_segment(session)
        if not alloc:
            return
        vni = alloc.vxlan_vni
        mcast_group = self._get_mcast_group_for_vni(session, vni)
        return {api.NETWORK_TYPE: const.TYPE_NEXUS_VXLAN,
                api.PHYSICAL_NETWORK: mcast_group,
                api.SEGMENTATION_ID: alloc.vxlan_vni}

    def sync_allocations(self):
        """
        Synchronize vxlan_allocations table with configured tunnel ranges.
        """

        # determine current configured allocatable vnis
        vxlan_vnis = set()
        for tun_min, tun_max in self.tunnel_ranges:
            vxlan_vnis |= set(six.moves.range(tun_min, tun_max + 1))

        session = db_api.get_session()
        with session.begin(subtransactions=True):
            # remove from table unallocated tunnels not currently allocatable
            # fetch results as list via all() because we'll be iterating
            # through them twice
            allocs = (session.query(nexus_models_v2.NexusVxlanAllocation).
                      with_lockmode("update").all())
            # collect all vnis present in db
            existing_vnis = set(alloc.vxlan_vni for alloc in allocs)
            # collect those vnis that needs to be deleted from db
            vnis_to_remove = [alloc.vxlan_vni for alloc in allocs
                              if (alloc.vxlan_vni not in vxlan_vnis and
                                  not alloc.allocated)]
            # Immediately delete vnis in chunks. This leaves no work for
            # flush at the end of transaction
            bulk_size = 100
            chunked_vnis = (vnis_to_remove[i:i + bulk_size] for i in
                            range(0, len(vnis_to_remove), bulk_size))
            for vni_list in chunked_vnis:
                session.query(nexus_models_v2.NexusVxlanAllocation).filter(
                    nexus_models_v2.NexusVxlanAllocation.
                    vxlan_vni.in_(vni_list)).delete(
                        synchronize_session=False)
            # collect vnis that need to be added
            vnis = list(vxlan_vnis - existing_vnis)
            chunked_vnis = (vnis[i:i + bulk_size] for i in
                            range(0, len(vnis), bulk_size))
            for vni_list in chunked_vnis:
                bulk = [{'vxlan_vni': vni, 'allocated': False}
                        for vni in vni_list]
                session.execute(nexus_models_v2.NexusVxlanAllocation.
                                __table__.insert(), bulk)

    def reserve_provider_segment(self, session, segment):
        if self.is_partial_segment(segment):
            alloc = self.allocate_partially_specified_segment(session)
            if not alloc:
                raise exc.NoNetworkAvailable
        else:
            segmentation_id = segment.get(api.SEGMENTATION_ID)
            alloc = self.allocate_fully_specified_segment(
                session, vxlan_vni=segmentation_id)
            if not alloc:
                raise exc.TunnelIdInUse(tunnel_id=segmentation_id)
        return {api.NETWORK_TYPE: p_const.TYPE_VXLAN,
                api.PHYSICAL_NETWORK: None,
                api.SEGMENTATION_ID: alloc.vxlan_vni}

    def release_segment(self, session, segment):
        vxlan_vni = segment[api.SEGMENTATION_ID]

        inside = any(lo <= vxlan_vni <= hi for lo, hi in self.tunnel_ranges)

        with session.begin(subtransactions=True):
            query = (session.query(nexus_models_v2.NexusVxlanAllocation).
                     filter_by(vxlan_vni=vxlan_vni))
            if inside:
                count = query.update({"allocated": False})
                if count:
                    mcast_row = (
                        session.query(nexus_models_v2.NexusMcastGroup)
                        .filter_by(associated_vni=vxlan_vni).first())
                    session.delete(mcast_row)
                    LOG.debug("Releasing vxlan tunnel %s to pool",
                              vxlan_vni)
            else:
                count = query.delete()
                if count:
                    LOG.debug("Releasing vxlan tunnel %s outside pool",
                              vxlan_vni)

        if not count:
            LOG.warning(_LW("vxlan_vni %s not found"), vxlan_vni)

    def add_endpoint(self, ip, udp_port):
        pass

    def delete_endpoint(self, ip):
        pass

    def delete_endpoint_by_host_or_ip(self, host, ip):
        pass

    def get_endpoint_by_host(self, host):
        pass

    def get_endpoint_by_ip(self, ip):
        pass

    def get_endpoints(self):
        pass
