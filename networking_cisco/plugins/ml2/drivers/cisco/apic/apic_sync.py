# Copyright (c) 2014 Cisco Systems Inc.
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

from oslo_log import log as logging
from oslo_service import loopingcall

from networking_cisco._i18n import _LW
from networking_cisco.plugins.ml2.drivers.cisco.apic import constants
from networking_cisco.plugins.ml2.drivers.cisco.apic import exceptions as aexc

from neutron import context
from neutron import manager
from neutron.plugins.ml2 import db as l2_db
from neutron.plugins.ml2 import driver_context

from neutron_lib import constants as n_constants

LOG = logging.getLogger(__name__)


class SynchronizerBase(object):

    def __init__(self, driver, interval=None):
        self.core_plugin = manager.NeutronManager.get_plugin()
        self.driver = driver
        self.interval = interval

    def sync(self, f, *args, **kwargs):
        """Fire synchronization based on interval.

        Interval can be >0 for 'sync periodically' and
        <=0 for 'no sync'
        """
        if self.interval and self.interval > 0:
            loop_call = loopingcall.FixedIntervalLoopingCall(f, *args,
                                                             **kwargs)
            loop_call.start(interval=self.interval)
            return loop_call


class ApicBaseSynchronizer(SynchronizerBase):

    def sync_base(self):
        self.sync(self._sync_base)

    def _sync_base(self):
        ctx = context.get_admin_context()
        # Sync Networks
        # Unroll to avoid unwanted additions during sync
        networks = [x for x in self.core_plugin.get_networks(ctx)]
        for network in networks:
            if constants.APIC_SYNC_NETWORK == network['name']:
                continue

            mech_context = driver_context.NetworkContext(
                self.core_plugin, ctx, network)
            try:
                self.driver.create_network_postcommit(mech_context)
            except aexc.ReservedSynchronizationName as e:
                LOG.debug(e.message)
            except Exception as e:
                LOG.warning(_LW("Create network postcommit failed for "
                                "network %(net_id)s: %(message)s"),
                            net_id=network['id'], message=e.message)
        # Sync Subnets
        subnets = [x for x in self.core_plugin.get_subnets(ctx)]
        for subnet in subnets:
            mech_context = driver_context.SubnetContext(self.core_plugin, ctx,
                                                        subnet)
            try:
                self.driver.create_subnet_postcommit(mech_context)
            except Exception as e:
                LOG.warning(_LW("Create subnet postcommit failed for "
                                "subnet %(sub_id)s: %(message)s"),
                            sub_id=subnet['id'], message=e.message)
        # Sync Ports (compute/gateway/dhcp)
        ports = [x for x in self.core_plugin.get_ports(ctx)]
        for port in ports:
            binding = l2_db.get_locked_port_and_binding(ctx.session,
                                                        port['id'])[1]
            levels = l2_db.get_binding_levels(ctx.session, port['id'],
                                              binding.host)
            network = self.core_plugin.get_network(ctx, port['network_id'])
            mech_context = driver_context.PortContext(self.core_plugin, ctx,
                                                      port, network, binding,
                                                      levels)
            try:
                self.driver.create_port_postcommit(mech_context)
            except Exception as e:
                LOG.warning(_LW("Create port postcommit failed for "
                                "port %(port_id)s: %(message)s"),
                            port_id=port['id'], message=e.message)


class ApicRouterSynchronizer(SynchronizerBase):

    def sync_router(self):
        self.sync(self._sync_router)

    def _sync_router(self):
        ctx = context.get_admin_context()
        # Sync Router Interfaces
        filters = {'device_owner': [n_constants.DEVICE_OWNER_ROUTER_INTF]}
        ports = [x for x in self.core_plugin.get_ports(ctx, filters=filters)]
        for interface in ports:
            try:
                self.driver.add_router_interface_postcommit(
                    ctx, interface['device_id'],
                    {'port_id': interface['id']})
            except Exception:
                LOG.warning(_LW("Add interface postcommit failed for "
                                "port %s"), interface['id'])
