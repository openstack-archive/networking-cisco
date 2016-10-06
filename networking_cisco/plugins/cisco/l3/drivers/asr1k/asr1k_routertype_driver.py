# Copyright 2015 Cisco Systems, Inc.  All rights reserved.
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
from oslo_utils import uuidutils
from sqlalchemy.orm import exc

from neutron.extensions import l3
from neutron import manager
from neutron.plugins.common import constants

from neutron_lib import constants as l3_constants
from neutron_lib import exceptions as n_exc

from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.db.l3 import ha_db
from networking_cisco.plugins.cisco.db.l3.l3_router_appliance_db import (
    L3RouterApplianceDBMixin)
from networking_cisco.plugins.cisco.extensions import routerhostingdevice
from networking_cisco.plugins.cisco.extensions import routerrole
from networking_cisco.plugins.cisco.extensions import routertype
from networking_cisco.plugins.cisco.extensions import routertypeawarescheduler
from networking_cisco.plugins.cisco.l3 import drivers

from networking_cisco._i18n import _

from oslo_log import log as logging
LOG = logging.getLogger(__name__)

HOSTING_DEVICE_ATTR = routerhostingdevice.HOSTING_DEVICE_ATTR
ROUTER_ROLE_GLOBAL = cisco_constants.ROUTER_ROLE_GLOBAL
ROUTER_ROLE_LOGICAL_GLOBAL = cisco_constants.ROUTER_ROLE_LOGICAL_GLOBAL
ROUTER_ROLE_HA_REDUNDANCY = cisco_constants.ROUTER_ROLE_HA_REDUNDANCY

TENANT_HSRP_GRP_RANGE = 1
TENANT_HSRP_GRP_OFFSET = 1064
EXT_HSRP_GRP_RANGE = 1
EXT_HSRP_GRP_OFFSET = 1064

N_ROUTER_PREFIX = 'nrouter-'
DEV_NAME_LEN = 14


class TopologyNotSupportedByRouterError(n_exc.Conflict):
    message = _("Requested topology cannot be supported by router.")


class ASR1kL3RouterDriver(drivers.L3RouterBaseDriver):

    def create_router_precommit(self, context, router_context):
        pass

    def create_router_postcommit(self, context, router_context):
        pass

    def update_router_precommit(self, context, router_context):
        pass

    def update_router_postcommit(self, context, router_context):
        # Whenever a gateway is added to, or removed from, a router hosted on
        # a hosting device, we must ensure that a global router is running
        # (for add operation) or not running (for remove operation) on that
        # hosting device.
        current = router_context.current
        if current[HOSTING_DEVICE_ATTR] is None:
            return
        e_context = context.elevated()
        if current['gw_port_id']:
            self._conditionally_add_global_router(e_context, current)
        else:
            self._conditionally_remove_global_router(e_context, current, True)

    def delete_router_precommit(self, context, router_context):
        pass

    def delete_router_postcommit(self, context, router_context):
        pass

    def schedule_router_precommit(self, context, router_context):
        pass

    def schedule_router_postcommit(self, context, router_context):
        # When the hosting device hosts a Neutron router with external
        # connectivity, a "global" router (modeled as a Neutron router) must
        # also run on the hosting device (outside of any VRF) to enable the
        # connectivity.
        current = router_context.current
        if current['gw_port_id'] and current[HOSTING_DEVICE_ATTR] is not None:
            self._conditionally_add_global_router(context.elevated(), current)

    def unschedule_router_precommit(self, context, router_context):
        pass

    def unschedule_router_postcommit(self, context, router_context):
        # When there is no longer any router with external gateway hosted on
        # a hosting device, the global router on that hosting device can also
        # be removed.
        current = router_context.current
        hd_id = current[HOSTING_DEVICE_ATTR]
        if current['gw_port_id'] and hd_id is not None:
            self._conditionally_remove_global_router(context.elevated(),
                                                     current)

    def add_router_interface_precommit(self, context, r_port_context):
        # Inside an ASR1k, VLAN sub-interfaces are used to connect to internal
        # neutron networks. Only one such sub-interface can be created for each
        # VLAN. As the VLAN sub-interface is added to the VRF representing the
        # Neutron router, we must only allow one Neutron router to attach to a
        # particular Neutron subnet/network.
        if (r_port_context.router_context.current[routerrole.ROUTER_ROLE_ATTR]
                == ROUTER_ROLE_HA_REDUNDANCY):
            # redundancy routers can be exempt as we check the user visible
            # routers and the request will be rejected there.
            return
        e_context = context.elevated()
        if r_port_context.current is None:
            sn = self._core_plugin.get_subnet(e_context,
                                              r_port_context.current_subnet_id)
            net_id = sn['network_id']
        else:
            net_id = r_port_context.current['network_id']
        filters = {'network_id': [net_id],
                   'device_owner': [l3_constants.DEVICE_OWNER_ROUTER_INTF]}
        for port in self._core_plugin.get_ports(e_context,
                                                filters=filters):
            router_id = port['device_id']
            if router_id is None:
                continue
            router = self._l3_plugin.get_router(e_context, router_id)
            if router[routerrole.ROUTER_ROLE_ATTR] is None:
                raise TopologyNotSupportedByRouterError()

    def add_router_interface_postcommit(self, context, r_port_context):
        pass

    def remove_router_interface_precommit(self, context, r_port_context):
        pass

    def remove_router_interface_postcommit(self, context, r_port_context):
        pass

    def create_floatingip_precommit(self, context, fip_context):
        pass

    def create_floatingip_postcommit(self, context, fip_context):
        pass

    def update_floatingip_precommit(self, context, fip_context):
        pass

    def update_floatingip_postcommit(self, context, fip_context):
        pass

    def delete_floatingip_precommit(self, context, fip_context):
        pass

    def delete_floatingip_postcommit(self, context, fip_context):
        pass

    def ha_interface_ip_address_needed(self, context, router, port,
                                       ha_settings_db, ha_group_uuid):
        if port['device_owner'] == l3_constants.DEVICE_OWNER_ROUTER_GW:
            return False
        else:
            return True

    def generate_ha_group_id(self, context, router, port, ha_settings_db,
                             ha_group_uuid):
        if port['device_owner'] == l3_constants.DEVICE_OWNER_ROUTER_GW:
            ri_name = self._router_name(router['id'])[8:DEV_NAME_LEN]
            group_id = int(ri_name, 16) % TENANT_HSRP_GRP_RANGE
            group_id += TENANT_HSRP_GRP_OFFSET
            return group_id
        else:
            net_id_digits = port['network_id'][:6]
            group_id = int(net_id_digits, 16) % EXT_HSRP_GRP_RANGE
            group_id += EXT_HSRP_GRP_OFFSET
            return group_id

    def _conditionally_add_global_router(self, context, router):
        # We could filter on hosting device id but we don't so we get all
        # global routers for this router type. We can then use that count to
        # determine which ha priority a new global router should get.
        filters = {
            routerrole.ROUTER_ROLE_ATTR: [ROUTER_ROLE_GLOBAL],
            routertype.TYPE_ATTR: [router[routertype.TYPE_ATTR]]}
        global_routers = {
            r[HOSTING_DEVICE_ATTR]: r for r in self._l3_plugin.get_routers(
                context, filters=filters, fields=[HOSTING_DEVICE_ATTR])}
        hosting_device_id = router[HOSTING_DEVICE_ATTR]
        if hosting_device_id not in global_routers:
            # must create global router on hosting device
            # all global routers are connected to the external network
            ext_nw = router[l3.EXTERNAL_GW_INFO]['network_id']
            r_spec = {'router': {
                # global routers are not tied to any tenant
                'tenant_id': '',
                'name': self._global_router_name(hosting_device_id),
                'admin_state_up': True,
                l3.EXTERNAL_GW_INFO: {'network_id': ext_nw}}}
            global_router, r_hd_b_db = self._l3_plugin.do_create_router(
                context, r_spec, router[routertype.TYPE_ATTR], False, True,
                hosting_device_id, ROUTER_ROLE_GLOBAL)
            log_global_router = (
                self._conditionally_add_logical_global_router(context,
                                                              router))
            # make the global router a redundancy router for the logical
            # global router (which we treat as a hidden "user visible
            # router" (how's that for a contradiction! :-) )
            with context.session.begin(subtransactions=True):
                ha_priority = (
                    ha_db.DEFAULT_MASTER_PRIORITY -
                    len(global_routers) * ha_db.PRIORITY_INCREASE_STEP)
                r_b_b = ha_db.RouterRedundancyBinding(
                    redundancy_router_id=global_router['id'],
                    priority=ha_priority,
                    user_router_id=log_global_router['id'])
                context.session.add(r_b_b)
            self._l3_plugin.add_type_and_hosting_device_info(context,
                                                             global_router)
            for ni in self._l3_plugin.get_notifiers(context, [global_router]):
                if ni['notifier']:
                    ni['notifier'].routers_updated(context, ni['routers'])

    def _conditionally_remove_global_router(self, context, router,
                                            update_operation=False):
        filters = {HOSTING_DEVICE_ATTR: [router[HOSTING_DEVICE_ATTR]]}
        invert_filters = {'gw_port_id': [None]}
        num_rtrs = self._l3_plugin.get_routers_count_extended(
            context, filters=filters, invert_filters=invert_filters)
        if ((num_rtrs <= 2 and update_operation is False) or
                (num_rtrs <= 1 and update_operation is True)):
            # there are one or two routers left and one of them may be a
            # global router, which can then be deleted
            filters[routerrole.ROUTER_ROLE_ATTR] = [ROUTER_ROLE_GLOBAL]
            global_routers = self._l3_plugin.get_routers(context,
                                                         filters=filters)
            if global_routers:
                try:
                    # can remove the global router as it will no longer be used
                    self._l3_plugin.delete_router(
                        context, global_routers[0]['id'], unschedule=False)
                except (exc.ObjectDeletedError, l3.RouterNotFound) as e:
                    LOG.warning(e)
                self._conditionally_remove_logical_global_router(context,
                                                                 router)

    def _conditionally_add_logical_global_router(self, context, router):
        # Since HA is also enabled on the global routers on each hosting device
        # those global routers need HA settings and VIPs. We represent that
        # using a Neutron router that is never instantiated/hosted. That
        # Neutron router is referred to as the "logical global" router.
        filters = {routerrole.ROUTER_ROLE_ATTR: [ROUTER_ROLE_LOGICAL_GLOBAL],
                   routertype.TYPE_ATTR: [router[routertype.TYPE_ATTR]]}
        logical_global_routers = self._l3_plugin.get_routers(
            context, filters=filters)
        if not logical_global_routers:
            ext_nw = router[l3.EXTERNAL_GW_INFO]['network_id']
            r_spec = {'router': {
                # global routers are not tied to any tenant
                'tenant_id': '',
                'name': self._global_router_name('', logical=True),
                'admin_state_up': True,
                l3.EXTERNAL_GW_INFO: {'network_id': ext_nw},
                # set auto-schedule to false to keep this router un-hosted
                routertypeawarescheduler.AUTO_SCHEDULE_ATTR: False}}
            # notifications should never be sent for this logical router!
            logical_global_router, r_hd_b_db = (
                self._l3_plugin.do_create_router(
                    context, r_spec, router[routertype.TYPE_ATTR], False,
                    True, None, ROUTER_ROLE_LOGICAL_GLOBAL))
            self._provision_ha(context, logical_global_router)
        else:
            logical_global_router = logical_global_routers[0]
            with context.session.begin(subtransactions=True):
                self._update_ha_redundancy_level(context,
                                                 logical_global_router, 1)
        return logical_global_router

    def _provision_ha(self, context, logical_global_router):
        with context.session.begin(subtransactions=True):
            ha_group_uuid = uuidutils.generate_uuid()
            group_id = self.generate_ha_group_id(
                context, logical_global_router,
                {'device_owner': l3_constants.DEVICE_OWNER_ROUTER_GW}, {},
                ha_group_uuid)
            subnet_id = logical_global_router[l3.EXTERNAL_GW_INFO][
                'external_fixed_ips'][0]['subnet_id']
            r_ha_s = ha_db.RouterHASetting(
                router_id=logical_global_router['id'],
                ha_type=cfg.CONF.ha.default_ha_mechanism,
                redundancy_level=1,
                priority=ha_db.DEFAULT_MASTER_PRIORITY,
                probe_connectivity=False,
                probe_target=None,
                probe_interval=None)
            context.session.add(r_ha_s)
            r_ha_g = ha_db.RouterHAGroup(
                id=ha_group_uuid,
                tenant_id='',
                ha_type=r_ha_s.ha_type,
                group_identity=group_id,
                ha_port_id=logical_global_router['gw_port_id'],
                extra_port_id=None,
                subnet_id=subnet_id,
                user_router_id=logical_global_router['id'],
                timers_config='',
                tracking_config='',
                other_config='')
            context.session.add(r_ha_g)

    def _conditionally_remove_logical_global_router(self, context, router):
        filters = {routerrole.ROUTER_ROLE_ATTR: [ROUTER_ROLE_GLOBAL],
                   routertype.TYPE_ATTR: [router[routertype.TYPE_ATTR]]}
        num_rtrs = self._l3_plugin.get_routers_count(context, filters=filters)
        filters[routerrole.ROUTER_ROLE_ATTR] = [ROUTER_ROLE_LOGICAL_GLOBAL]
        log_global_routers = self._l3_plugin.get_routers(context,
                                                         filters=filters)
        if not log_global_routers:
            # this should not happen but ...
            return
        if num_rtrs == 0:
            # There are no global routers left so the logical global router
            # can also be deleted.
            # We use parent class method as no special operations beyond what
            # the base implemenation does are needed for logical global router
            try:
                super(L3RouterApplianceDBMixin, self._l3_plugin).delete_router(
                    context, log_global_routers[0]['id'])
            except (exc.ObjectDeletedError, l3.RouterNotFound) as e:
                LOG.warning(e)
        else:
            self._update_ha_redundancy_level(context, log_global_routers[0],
                                             -1)

    def _update_ha_redundancy_level(self, context, logical_global_router,
                                    delta):
        with context.session.begin(subtransactions=True):
            log_g_router_db = self._l3_plugin._get_router(
                context, logical_global_router['id'])
            log_g_router_db.ha_settings.redundancy_level += delta
            context.session.add(log_g_router_db.ha_settings)

    def _router_name(self, router_id):
        return N_ROUTER_PREFIX + router_id

    def _global_router_name(self, hosting_device_id, logical=False):
        if logical is True:
            return cisco_constants.LOGICAL_ROUTER_ROLE_NAME
        else:
            return '%s-%s' % (cisco_constants.ROUTER_ROLE_NAME_PREFIX,
                              hosting_device_id[-cisco_constants.ROLE_ID_LEN:])

    @property
    def _core_plugin(self):
        return manager.NeutronManager.get_plugin()

    @property
    def _l3_plugin(self):
        return manager.NeutronManager.get_service_plugins().get(
            constants.L3_ROUTER_NAT)
