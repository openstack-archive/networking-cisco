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

from oslo_log import log as logging
import oslo_messaging
from oslo_serialization import jsonutils
import six

from neutron import context as neutron_context
from neutron.db import api as db_api
from neutron.extensions import l3
from neutron_lib import constants

LOG = logging.getLogger(__name__)


class L3RouterCfgRpcCallback(object):
    """Cisco cfg agent rpc support in L3 routing service plugin."""

    # 1.0 L3PluginCfgAgentApi BASE_RPC_API_VERSION
    # 1.1 Added 'update_floatingip_statuses' method
    # 1.2 Added 'cfg_sync_all_hosted_routers' method
    target = oslo_messaging.Target(version='1.2')

    def __init__(self, l3plugin):
        self._l3plugin = l3plugin

    # version 1.0 API
    @db_api.retry_db_errors
    def cfg_sync_routers(self, context, host, router_ids=None,
                         hosting_device_ids=None):
        """Sync routers according to filters to a specific Cisco cfg agent.

        @param context: contains user information
        @param host: originator of callback
        @param router_ids: list of router ids to return information about
        @param hosting_device_ids: list of hosting device ids to get
        routers for.
        @return: a list of routers
                 with their hosting devices, interfaces and floating_ips
        """
        adm_context = neutron_context.get_admin_context()
        try:
            routers = (
                self._l3plugin.list_active_sync_routers_on_hosting_devices(
                    adm_context, host, router_ids, hosting_device_ids))
        except AttributeError:
            routers = []
        LOG.debug('Routers returned to Cisco cfg agent@%(agt)s:\n %(routers)s',
                  {'agt': host, 'routers': jsonutils.dumps(routers, indent=5)})
        return routers

    # version 1.2 API
    @db_api.retry_db_errors
    def cfg_sync_all_hosted_routers(self, context, host):
        adm_context = neutron_context.get_admin_context()
        try:
            routers = (
                self._l3plugin.list_all_routers_on_hosting_devices(
                    adm_context))
        except AttributeError:
            routers = []
        return routers

    # version 1.0 API
    def report_status(self, context, host, status_list):
        """Report status of a particular Neutron router by Cisco cfg agent.

        This is called by Cisco cfg agent when it has performed an operation
        on a Neutron router. Note that the agent may include status updates
        for multiple routers in one message.

        @param context: contains user information
        @param host: originator of callback
        @param status_list: list of status dicts for routers
                            Each list item is
                            {'router_id': <router_id>,
                             'operation': <attempted operation>
                             'status': <'SUCCESS'|'FAILURE'>,
                             'details': <optional explaining details>}
        """
        #TODO(bobmel): Update router status
        # State machine: CREATE: SCHEDULING -> PENDING_CREATE -> ACTIVE/ERROR
        #                UPDATE: PENDING_UPDATE -> ACTIVE/ERROR
        #                DELETE: PENDING_DELETE -> DELETED/ERROR
        # While in SCHEDULING|PENDING_* states, no operations on the router
        # are allowed. Need to handle lost ACKs by either periodic refreshes
        # or by maintaining timers on routers in SCHEDULING|PENDING_* states.
        LOG.debug("Config agent %(host)s reported status for Neutron"
                  "routers: %(routers)s", {'host': host, 'routers': []})

    # version 1.1 API
    @db_api.retry_db_errors
    def update_floatingip_statuses_cfg(self, context, router_id, fip_statuses):
        """Update operational status for one or several floating IPs.

        This is called by Cisco cfg agent to update the status of one or
        several floatingips.

        @param context: contains user information
        @param router_id: id of router associated with the floatingips
        @param router_id: dict with floatingip_id as key and status as value
        """
        with context.session.begin(subtransactions=True):
            for (floatingip_id, status) in six.iteritems(fip_statuses):
                LOG.debug("New status for floating IP %(floatingip_id)s: "
                          "%(status)s", {'floatingip_id': floatingip_id,
                                         'status': status})
                try:
                    self._l3plugin.update_floatingip_status(
                        context, floatingip_id, status)
                except l3.FloatingIPNotFound:
                    LOG.debug("Floating IP: %s no longer present.",
                              floatingip_id)
            # Find all floating IPs known to have been the given router
            # for which an update was not received. Set them DOWN mercilessly
            # This situation might occur for some asynchronous backends if
            # notifications were missed
            known_router_fips = self._l3plugin.get_floatingips(
                context, {'last_known_router_id': [router_id]})
            # Consider only floating ips which were disassociated in the API
            fips_to_disable = (fip['id'] for fip in known_router_fips
                               if not fip['router_id'])
            for fip_id in fips_to_disable:
                LOG.debug("update_fip_statuses: disable: %s", fip_id)
                self._l3plugin.update_floatingip_status(
                    context, fip_id, constants.FLOATINGIP_STATUS_DOWN)

    @db_api.retry_db_errors
    def update_port_statuses_cfg(self, context, port_ids, status):
        """Update the operational statuses of a list of router ports.

           This is called by the Cisco cfg agent to update the status of a list
           of ports.

           @param context: contains user information
           @param port_ids: list of ids of all the ports for the given status
           @param status: PORT_STATUS_ACTIVE/PORT_STATUS_DOWN.
        """
        with context.session.begin(subtransactions=True):
            self._l3plugin.update_router_port_statuses(context, port_ids,
                                                       status)
