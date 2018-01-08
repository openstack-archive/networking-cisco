# Copyright (c) 2017 Cisco Systems, Inc.
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

from oslo_log import log

from networking_cisco import backwards_compatibility as bc
from networking_cisco.ml2_drivers.nexus import (
    nexus_helpers as nexus_help)

LOG = log.getLogger(__name__)


class NexusMDTrunkHandler(object):
    """Cisco Nexus Mechanism Driver Trunk Handler.

    This class contains methods called by the cisco_nexus MD for
    processing trunk subports.
    """
    def is_trunk_parentport(self, port):
        return 'trunk_details' in port

    def is_trunk_subport(self, port):
        return port['device_owner'] == bc.trunk_consts.TRUNK_SUBPORT_OWNER

    def is_trunk_subport_baremetal(self, port):
        context = bc.get_context()
        el_context = context.elevated()

        subport_obj = bc.trunk_objects.SubPort.get_object(
            el_context, port_id=port['id'])
        if subport_obj:
            trunk_obj = bc.trunk_objects.Trunk.get_object(
                el_context, id=subport_obj.trunk_id)
            trunk_port = bc.get_plugin().get_port(
                el_context, trunk_obj.port_id)
            return nexus_help.is_baremetal(trunk_port)
        else:
            return False

    def update_subports(self, port):
        """Set port attributes for trunk subports.

        For baremetal deployments only, set the neutron port attributes
        during the bind_port event.
        """
        trunk_details = port.get('trunk_details')
        subports = trunk_details['sub_ports']

        host_id = port.get(bc.dns.DNSNAME)
        context = bc.get_context()
        el_context = context.elevated()

        for subport in subports:
            bc.get_plugin().update_port(el_context, subport['port_id'],
                {'port':
                 {bc.portbindings.HOST_ID: host_id,
                  'device_owner': bc.trunk_consts.TRUNK_SUBPORT_OWNER}})

        # Set trunk to ACTIVE status.
        trunk_obj = bc.trunk_objects.Trunk.get_object(
            el_context, id=trunk_details['trunk_id'])
        trunk_obj.update(status=bc.trunk_consts.ACTIVE_STATUS)
