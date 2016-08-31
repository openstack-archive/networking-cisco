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
ML2 Mechanism Driver for Cisco Nexus1000V distributed virtual switches.
"""

import eventlet

from oslo_config import cfg
from oslo_log import log
from oslo_utils import excutils

from networking_cisco._i18n import _LE, _LI, _LW

from neutron.db import db_base_plugin_v2
from neutron.extensions import portbindings
from neutron.extensions import providernet
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2.common import exceptions as ml2_exc
from neutron.plugins.ml2 import driver_api as api

from neutron_lib import constants as n_const

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_client)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_db)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_sync)

LOG = log.getLogger(__name__)

cfg.CONF.import_group(
    'ml2_cisco_n1kv',
    'networking_cisco.plugins.ml2.drivers.cisco.n1kv.config')


class N1KVMechanismDriver(api.MechanismDriver):

    def initialize(self):
        # Extend extension to service mapping dict

        # TODO(sakvarma) Check if this mapping can be removed
        p_const.EXT_TO_SERVICE_MAPPING['cisco_n1kv_profile'] = (n1kv_const.
                                                                CISCO_N1KV)
        self.n1kvclient = n1kv_client.Client()

        self.sync_obj = n1kv_sync.N1kvSyncDriver(db_base_plugin_v2.
                                                 NeutronDbPluginV2())

        eventlet.spawn(self.sync_obj.do_sync)

        # Get VLAN/VXLAN network profiles name
        self.netp_name = {p_const.TYPE_VLAN: (
                              n1kv_const.DEFAULT_VLAN_NETWORK_PROFILE_NAME),
                          p_const.TYPE_VXLAN: (
                              n1kv_const.DEFAULT_VXLAN_NETWORK_PROFILE_NAME)}
        # Ensure network profiles are created on the VSM
        try:
            self._ensure_network_profiles_created_on_vsm()
        except (n1kv_exc.VSMConnectionFailed, n1kv_exc.VSMError):
            LOG.error(_LE("VSM failed to create default network profiles."))
        self.vif_type = portbindings.VIF_TYPE_OVS
        self.vif_details = {portbindings.CAP_PORT_FILTER: True,
                            portbindings.OVS_HYBRID_PLUG: True}
        self.supported_network_types = [p_const.TYPE_VLAN, p_const.TYPE_VXLAN]

    def _ensure_network_profiles_created_on_vsm(self):
        # Try to create logical networks and network profiles on the VSM if
        # they don't exist already.
        for netp_type in [p_const.TYPE_VLAN, p_const.TYPE_VXLAN]:
            try:
                netp = n1kv_db.get_network_profile_by_name(
                    self.netp_name[netp_type])
            except n1kv_exc.NetworkProfileNotFound:
                if netp_type == p_const.TYPE_VXLAN:
                    sub_type = n1kv_const.CLI_VXLAN_MODE_ENHANCED
                else:
                    sub_type = None
                # Create a network profile in Neutron DB
                netp = n1kv_db.add_network_profile(self.netp_name[netp_type],
                                                   netp_type, sub_type)
                try:
                    # Create a network profile on the VSM
                    self.n1kvclient.create_network_segment_pool(netp)
                # Catch any exception here and cleanup if so
                except (n1kv_exc.VSMConnectionFailed, n1kv_exc.VSMError):
                    with excutils.save_and_reraise_exception():
                        n1kv_db.remove_network_profile(netp.id)

    def _is_segment_valid_for_n1kv(self, segment_id, network_type):
        """Validate the segment for Cisco Nexus1000V."""
        if network_type not in self.supported_network_types:
            LOG.info(_LI("Cisco Nexus1000V: Ignoring request for "
                         "unsupported network type: %s. Network type VLAN "
                         "and VXLAN supported.") % network_type)
            return False
        if ((network_type == p_const.TYPE_VLAN and
             (n1kv_const.NEXUS_VLAN_RESERVED_MIN <= segment_id <=
              n1kv_const.NEXUS_VLAN_RESERVED_MAX))
            or (network_type == p_const.TYPE_VXLAN and
                segment_id < n1kv_const.NEXUS_VXLAN_MIN)):
            LOG.warning(_LW("Segment ID: %(seg_id)s for network type: "
                            "%(net_type)s is unsupported on Cisco Nexus "
                            "devices.") %
                        {"seg_id": segment_id,
                         "net_type": network_type})
            return False
        return True

    def create_network_precommit(self, context):
        """Update network binding information."""
        network = context.current
        segment = context.network_segments[0]
        network_type = segment['network_type']
        session = context._plugin_context.session
        # NoOp for unsupported network types
        if not self._is_segment_valid_for_n1kv(segment['segmentation_id'],
                                               network_type):
            return
        # update network binding here
        n1kv_db.update_network_binding_with_segment_id(
            net_id=network['id'], segment_id=segment['segmentation_id'],
            db_session=session)

    def create_network_postcommit(self, context):
        """Send network parameters to the VSM."""
        network = context.current
        segment = context.network_segments[0]
        network_type = segment['network_type']
        # NoOp for unsupported network types
        if not self._is_segment_valid_for_n1kv(segment['segmentation_id'],
                                               network_type):
            return
        session = context._plugin_context.session
        binding = n1kv_db.get_network_binding(network['id'], session)
        netp = n1kv_db.get_network_profile_by_uuid(binding.profile_id, session)
        network[providernet.SEGMENTATION_ID] = binding.segmentation_id
        try:
            self.n1kvclient.create_network_segment(network, netp)
        except(n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
            raise ml2_exc.MechanismDriverError()
        LOG.info(_LI("Create network(postcommit) succeeded for network: "
                     "%(network_id)s of type: %(network_type)s with segment "
                     "id: %(segment_id)s"),
                 {"network_id": network['id'],
                  "network_type": network_type,
                  "segment_id": segment['segmentation_id']})

    def update_network_postcommit(self, context):
        """Send updated network parameters to the VSM."""
        updated_network = context.current
        old_network = context.original
        segment = context.network_segments[0]
        network_type = segment['network_type']
        # NoOp for unsupported network types
        if not self._is_segment_valid_for_n1kv(segment['segmentation_id'],
                                               network_type):
            return
        modifiable_vals = ['name', 'shared']
        # Perform network update on VSM only if a modifiable value changed.
        if any(updated_network[val] != old_network[val]
               for val in modifiable_vals):
            try:
                self.n1kvclient.update_network_segment(updated_network)
            except(n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                raise ml2_exc.MechanismDriverError()
        LOG.info(_LI("Update network(postcommit) succeeded for network: %s") %
                 old_network['id'])

    def delete_network_postcommit(self, context):
        """Send network delete request to the VSM."""
        network = context.current
        segment = context.network_segments[0]
        network_type = segment['network_type']
        # NoOp for unsupported network types
        if not self._is_segment_valid_for_n1kv(segment['segmentation_id'],
                                               network_type):
            return
        try:
            self.n1kvclient.delete_network_segment(network['id'], network_type)
        except(n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
            raise ml2_exc.MechanismDriverError()
        LOG.info(_LI("Delete network(postcommit) succeeded for network: "
                     "%(network_id)s of type: %(network_type)s with segment "
                     "ID: %(segment_id)s"),
                 {"network_id": network['id'],
                  "network_type": network_type,
                  "segment_id": segment['segmentation_id']})

    def create_subnet_postcommit(self, context):
        """Send subnet parameters to the VSM."""
        subnet = context.current
        try:
            self.n1kvclient.create_ip_pool(subnet)
        except(n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
            raise ml2_exc.MechanismDriverError()
        LOG.info(_LI("Create subnet(postcommit) succeeded for subnet: "
                     "ID: %s"), subnet['id'])

    def update_subnet_postcommit(self, context):
        """Send updated subnet parameters to the VSM."""
        updated_subnet = context.current
        try:
            self.n1kvclient.update_ip_pool(updated_subnet)
        except(n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
            raise ml2_exc.MechanismDriverError()
        LOG.info(_LI("Update subnet(postcommit) succeeded for subnet: "
                     "ID: %s"), updated_subnet['id'])

    def delete_subnet_postcommit(self, context):
        """Send delete subnet notification to the VSM."""
        try:
            self.n1kvclient.delete_ip_pool(context.current['id'])
        except(n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
            raise ml2_exc.MechanismDriverError()
        LOG.info(_LI("Delete subnet(postcommit) succeeded for subnet: "
                     "ID: %s"), context.current['id'])

    def create_port_postcommit(self, context):
        """Send port parameters to the VSM."""
        port = context.current
        session = context._plugin_context.session
        binding = n1kv_db.get_policy_binding(port['id'], session)
        policy_profile = n1kv_db.get_policy_profile_by_uuid(session,
                                                            binding.profile_id)
        if policy_profile is None:
            raise ml2_exc.MechanismDriverError()
        vmnetwork_name = "%s%s_%s" % (n1kv_const.VM_NETWORK_PREFIX,
                                      binding.profile_id,
                                      port['network_id'])
        try:
            self.n1kvclient.create_n1kv_port(port,
                                             vmnetwork_name,
                                             policy_profile)
        except(n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
            raise ml2_exc.MechanismDriverError()
        LOG.info(_LI("Create port(postcommit) succeeded for port: "
                     "%(id)s on network: %(network_id)s with policy "
                     "profile ID: %(profile_id)s"),
                 {"network_id": port['network_id'],
                  "id": port['id'],
                  "profile_id": policy_profile.id})

    def update_port_postcommit(self, context):
        """Send port parameters to the VSM."""
        port = context.current
        old_port = context.original
        # Perform port update on VSM only if a router or DHCP port is bound.
        if (not old_port['binding:host_id'] and
                (port['device_owner'] in [n_const.DEVICE_OWNER_ROUTER_INTF,
                                          n_const.DEVICE_OWNER_DHCP])):
            session = context._plugin_context.session
            binding = n1kv_db.get_policy_binding(port['id'], session)
            policy_profile = n1kv_db.get_policy_profile_by_uuid(
                session, binding.profile_id)
            if policy_profile is None:
                raise ml2_exc.MechanismDriverError()
            vmnetwork_name = "%s%s_%s" % (n1kv_const.VM_NETWORK_PREFIX,
                                          binding.profile_id,
                                          port['network_id'])
            try:
                # Today an update is just a create, so we call create port
                self.n1kvclient.create_n1kv_port(port,
                                                 vmnetwork_name,
                                                 policy_profile)
            except(n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                raise ml2_exc.MechanismDriverError()
            LOG.info(_LI("Update port(postcommit) succeeded for port: "
                         "%(id)s on network: %(network_id)s with policy "
                         "profile ID: %(profile_id)s"),
                     {"network_id": port['network_id'],
                      "id": port['id'],
                      "profile_id": policy_profile.id})

    def delete_port_postcommit(self, context):
        """Send delete port notification to the VSM."""
        port = context.current
        profile_id = port.get(n1kv_const.N1KV_PROFILE, None)
        # If profile UUID is not present in the port object, we need
        # not send the port delete notification to the VSM since the port
        # does not exist on the VSM due to failure in create_port_precommit.
        if not profile_id:
            return

        vmnetwork_name = "%s%s_%s" % (n1kv_const.VM_NETWORK_PREFIX,
                                      profile_id,
                                      port['network_id'])
        try:
            self.n1kvclient.delete_n1kv_port(vmnetwork_name, port['id'])
        except(n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
            raise ml2_exc.MechanismDriverError()
        LOG.info(_LI("Delete port(postcommit) succeeded for port: "
                     "%(id)s on network: %(network_id)s with policy "
                     "profile ID: %(profile_id)s"),
                 {"network_id": port['network_id'],
                  "id": port['id'],
                  "profile_id": profile_id})

    def bind_port(self, context):
        segments = context.network.network_segments
        for segment in segments:
            if segment[api.NETWORK_TYPE] in self.supported_network_types:
                context.set_binding(segment[api.ID],
                                    self.vif_type,
                                    self.vif_details,
                                    status=n_const.PORT_STATUS_ACTIVE)
                return
            else:
                LOG.info(_LI("Port binding ignored for segment ID %(id)s, "
                             "segment %(segment)s and network type "
                             "%(nettype)s"),
                         {'id': segment[api.ID],
                          'segment': segment[api.SEGMENTATION_ID],
                          'nettype': segment[api.NETWORK_TYPE]})
