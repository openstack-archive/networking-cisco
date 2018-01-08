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

from oslo_config import cfg
from oslo_log import log

from networking_cisco import backwards_compatibility as bc
from networking_cisco.backwards_compatibility import cb_events as events
from networking_cisco.backwards_compatibility import cb_registry as registry

from networking_cisco.ml2_drivers.nexus import (
    constants as const)
from networking_cisco.ml2_drivers.nexus import (
    nexus_helpers as nexus_help)

LOG = log.getLogger(__name__)


class NexusTrunkHandler(object):
    """Cisco Nexus Trunk Handler.

    This class contains methods called by the trunk infrastruture
    to be processed by the cisco_nexus MD.
    """

    def __init__(self):
        self.plugin = bc.get_plugin()

    def _unbind_subport(self, context, port_id, status):
        self.plugin.update_port(context, port_id,
                                {'port':
                                 {bc.portbindings.HOST_ID: None,
                                  'status': status}})

    def trunk_update_postcommit(self, resource, event, trunk_plugin, payload):
        current_trunk_data = payload.current_trunk.to_dict()
        trunkport = self.plugin.get_port(
            payload.context, current_trunk_data['port_id'])

        if (nexus_help.is_baremetal(trunkport) and
            current_trunk_data['status'] != bc.constants.PORT_STATUS_ACTIVE):
            for subport in current_trunk_data['sub_ports']:
                self._unbind_subport(payload.context, subport['port_id'],
                                     current_trunk_data['status'])

    def subport_postcommit(self, resource, event, trunk_plugin, payload):
        trunkport = self.plugin.get_port(
            payload.context, payload.current_trunk.port_id)

        if (nexus_help.is_baremetal(trunkport) and
            trunkport['status'] == bc.constants.PORT_STATUS_ACTIVE):
            host_id = trunkport.get(bc.dns.DNSNAME)
            subport = payload.subports[0]
            trunk_subport = subport.to_dict()

            # Set the subport port attributes to match the parent port.
            if event == events.AFTER_CREATE:
                self.plugin.update_port(
                    payload.context, trunk_subport['port_id'],
                    {'port':
                     {bc.portbindings.HOST_ID: host_id,
                      'device_owner': bc.trunk_consts.TRUNK_SUBPORT_OWNER}})
            elif event == events.AFTER_DELETE:
                self._unbind_subport(
                    payload.context, trunk_subport['port_id'],
                    bc.constants.PORT_STATUS_DOWN)

            # Trunk drivers are responsible for setting the trunk
            # status. Use the trunk parent port's status.
            trunk_obj = bc.trunk_objects.Trunk.get_object(
                payload.context, id=payload.trunk_id)
            trunk_obj.update(status=trunkport['status'])


class NexusTrunkDriver(bc.trunk_base.DriverBase):
    """Cisco Nexus Trunk Driver.

    This class contains methods required to work with the trunk infrastruture.
    """
    @property
    def is_loaded(self):
        try:
            return (const.CISCO_NEXUS_ML2_MECH_DRIVER_V2 in
                    cfg.CONF.ml2.mechanism_drivers)
        except cfg.NoSuchOptError:
            return False

    def register(self, resource, event, trigger, **kwargs):
        super(NexusTrunkDriver, self).register(
            resource, event, trigger, **kwargs)
        self._handler = NexusTrunkHandler()

        registry.subscribe(self._handler.trunk_update_postcommit,
                           bc.trunk_consts.TRUNK, events.AFTER_UPDATE)
        for event in (events.AFTER_CREATE, events.AFTER_DELETE):
            registry.subscribe(self._handler.subport_postcommit,
                               bc.trunk_consts.SUBPORTS, event)

    @classmethod
    def create(cls):
        SUPPORTED_INTERFACES = (
            bc.portbindings.VIF_TYPE_OTHER,
        )

        SUPPORTED_SEGMENTATION_TYPES = (
            bc.trunk_consts.VLAN,
        )

        return cls(const.CISCO_NEXUS_ML2_MECH_DRIVER_V2,
                   SUPPORTED_INTERFACES,
                   SUPPORTED_SEGMENTATION_TYPES,
                   None,
                   can_trunk_bound_port=True)
