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
#

import time

from networking_cisco._i18n import _LE, _LI

from networking_cisco.apps.saf.common import constants
from networking_cisco.apps.saf.common import dfa_exceptions as dexc
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import utils

LOG = logging.getLogger(__name__)


class DfaFailureRecovery(object):

    """Failure recovery class."""

    def __init__(self, cfg):
        super(DfaFailureRecovery, self).__init__(cfg)
        self._cfg = cfg

    @property
    def cfg(self):
        return self._cfg

    def add_events(self, **kwargs):
        """Add failure event into the queue."""

        event_q = kwargs.get('event_queue')
        pri = kwargs.get('priority')
        if not event_q or not pri:
            return

        try:
            event_type = 'server.failure.recovery'
            payload = {}
            timestamp = time.ctime()
            data = (event_type, payload)
            event_q.put((pri, timestamp, data))
            LOG.debug('Added failure recovery event to the queue.')
        except Exception as exc:
            LOG.exception(_LE('Error: %(exc)s for event %(event)s'),
                          {'exc': str(exc), 'event': event_type})
            raise exc

    def failure_recovery(self, fail_info):
        """Failure recovery task.

        In case of failure in projects, network and VM create/delete, this
        task goes through all failure cases and try the request.
        """
        # Read failed entries from project database and send request
        # (create/delete - depends on failure type) to DCNM

        # 1. Try failure recovery for create project.
        LOG.info(_LI("Started failure_recovery."))
        projs = self.get_fialed_projects_entries(constants.CREATE_FAIL)
        for proj in projs:
            LOG.debug("Failure recovery for project %(name)s.", (
                {'name': proj.name}))
            # Try to create the project in DCNM
            try:
                self.dcnm_client.create_project(self.cfg.dcnm.orchestrator_id,
                                                proj.name,
                                                self.cfg.dcnm.
                                                default_partition_name,
                                                proj.dci_id)
            except dexc.DfaClientRequestFailed as e:
                LOG.error(_LE("failure_recovery: Failed to create %(proj)s "
                              "on DCNM : %(reason)s"),
                          {'proj': proj.name, 'reason': str(e)})
            else:
                # Request is sent successfully, update the database.
                self.update_project_info_cache(proj.id, dci_id=proj.dci_id,
                                               name=proj.name,
                                               opcode='update')
                LOG.debug('Success on failure recovery for '
                          'project %(name)s', {'name': proj.name})

        # 1.1 Try failure recovery for update project.
        projs = self.get_fialed_projects_entries(constants.UPDATE_FAIL)
        for proj in projs:
            LOG.debug("Failure recovery for project %(name)s.", (
                {'name': proj.name}))
            # This was failure of updating DCI id of the project in DCNM.
            try:
                self.dcnm_client.update_project(proj.name,
                                                self.cfg.dcnm.
                                                default_partition_name,
                                                proj.dci_id)
            except dexc.DfaClientRequestFailed as exc:
                LOG.error(_LE("failure_recovery: Failed to update %(proj)s "
                              "on DCNM : %(reason)s"),
                          {'proj': proj.name, 'reason': str(exc)})
            else:
                # Request is sent successfully, update the database.
                self.update_project_info_cache(proj.id,
                                               dci_id=proj.dci_id,
                                               name=proj.name,
                                               opcode='update')
                LOG.debug('Success on failure recovery update for '
                          'project %(name)s', {'name': proj.name})

        # 2. Try failure recovery for create network.
        nets = self.get_all_networks()
        for net in nets:
            if (net.result == constants.CREATE_FAIL
                    and net.source.lower() == 'openstack'):
                net_id = net.network_id
                try:
                    subnets = self.neutron_event.nclient.list_subnets(
                        network_id=net_id).get('subnets')
                except dexc.ConnectionFailed:
                    LOG.exception(_LE('Failed to get subnets list.'))
                    continue

                for subnet in subnets:
                    tenant_name = self.get_project_name(subnet['tenant_id'])
                    snet = utils.Dict2Obj(subnet)
                    try:
                        # Check if config_profile is not NULL.
                        if not net.config_profile:
                            cfgp, fwd_mod = (
                                self.dcnm_client.
                                get_config_profile_for_network(net.name))
                            net.config_profile = cfgp
                            net.fwd_mod = fwd_mod
                        self.dcnm_client.create_network(tenant_name, net, snet,
                                                        self.dcnm_dhcp)
                    except dexc.DfaClientRequestFailed:
                        # Still is failure, only log the error.
                        LOG.error(_LE('Failed to create network %(net)s.'),
                                  {'net': net.name})
                    else:
                        # Request is sent to DCNM, update the database
                        params = dict(
                            columns=dict(config_profile=net.config_profile,
                                         fwd_mod=net.fwd_mod,
                                         result=constants.RESULT_SUCCESS))
                        self.update_network(net_id, **params)
                        LOG.debug("Success on failure recovery to create "
                                  "%(net)s", {'net': net.name})

        # 3. Try Failure recovery for VM create and delete.
        instances = self.get_vms()
        for vm in instances:
            vm_info = dict(status=vm.status,
                           vm_mac=vm.mac,
                           segmentation_id=vm.segmentation_id,
                           host=vm.host,
                           port_uuid=vm.port_id,
                           net_uuid=vm.network_id,
                           oui=dict(ip_addr=vm.ip,
                                    vm_name=vm.name,
                                    vm_uuid=vm.instance_id,
                                    gw_mac=vm.gw_mac,
                                    fwd_mod=vm.fwd_mod,
                                    oui_id='cisco'))
            if vm.result == constants.CREATE_FAIL:
                try:
                    self.neutron_event.send_vm_info(str(vm.host), str(vm_info))
                except Exception as e:
                    # Failed to send info to the agent. Keep the data in the
                    # database as failure to send it later.
                    LOG.error(_LE('Failed to send VM info to agent. '
                                  'Reason %s'), str(e))
                else:
                    params = dict(columns=dict(
                        result=constants.RESULT_SUCCESS))
                    self.update_vm_db(vm.port_id, **params)
                    LOG.info(_LI('Created VM %(vm)s.'), {'vm': vm.name})

        for vm in instances:
            if vm.result == constants.DELETE_FAIL:
                vm_info['status'] = 'down'
                try:
                    self.neutron_event.send_vm_info(str(vm.host), str(vm_info))
                except Exception as e:
                    LOG.error(_LE('Failed to send VM info to agent. '
                                  'Reason %s'), str(e))
                else:
                    self.delete_vm_db(vm.port_id)
                    LOG.info(_LI('Deleted VM %(vm)s from DB.'),
                             {'vm': vm.name})

        # 4. Try failure recovery for delete network.
        for net in nets:
            if (net.result == constants.DELETE_FAIL
                    and net.source.lower() == 'openstack'):
                net_id = net.network_id
                segid = net.segmentation_id
                tenant_name = self.get_project_name(net.tenant_id)
                try:
                    self.dcnm_client.delete_network(tenant_name, net)
                except dexc.DfaClientRequestFailed:
                    # Still is failure, only log the error.
                    LOG.error(_LE('Failed to delete network %(net)s.'),
                              {'net': net.name})
                else:
                    # Request is sent to DCNM, delete the entry
                    # from database and return the segmentation id to the
                    # pool.
                    self.delete_network_db(net_id)
                    self.segmentation_pool.add(segid)
                    LOG.debug("Success on failure recovery to deleted "
                              "%(net)s", {'net': net.name})

        # 5. Try failure recovery for delete project.
        projs = self.get_fialed_projects_entries(constants.DELETE_FAIL)
        for proj in projs:
            LOG.debug("Failure recovery for project %(name)s.", (
                {'name': proj.name}))
            # Try to delete the project in DCNM
            try:
                self.dcnm_client.delete_project(proj.name,
                                                self.cfg.dcnm.
                                                default_partition_name)
            except dexc.DfaClientRequestFailed as e:
                # Failed to delete project in DCNM.
                # Save the info and mark it as failure and retry it later.
                LOG.error(_LE("Failure recovery is failed to delete "
                          "%(project)s on DCNM : %(reason)s"),
                          {'project': proj.name, 'reason': str(e)})
            else:
                # Delete was successful, now update the database.
                self.update_project_info_cache(proj.id, opcode='delete')
                LOG.debug("Success on failure recovery to deleted "
                          "%(project)s", {'project': proj.name})

        # 6. Do failure recovery for Firewall service
        self.fw_retry_failures()

        # 7. DHCP port consistency check for HA.
        if self.need_dhcp_check():
            nets = self.get_all_networks()
            for net in nets:
                net_id = net.network_id
                LOG.debug("dhcp consistency check for net id %s", net_id)
                self.correct_dhcp_ports(net_id)
            self.decrement_dhcp_check()
        LOG.info(_LI("Finished failure_recovery."))
