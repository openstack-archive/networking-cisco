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

import copy
import random

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import uuidutils
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import exc
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import expression as expr

from networking_cisco._i18n import _, _LW

from neutron.common import exceptions as n_exc
from neutron.common import utils
from neutron.db import l3_db
from neutron.db import model_base
from neutron.db import models_v2
from neutron.extensions import l3

from neutron_lib import constants as l3_constants

from networking_cisco import backwards_compatibility as bc_attr
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.common import utils as cisco_utils
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routerrole
from networking_cisco.plugins.cisco.extensions import routertype

LOG = logging.getLogger(__name__)


RouterPort = l3_db.RouterPort

HA_GROUP = 'group'
HA_PORT = 'ha_port'

MAX_VRRP_GROUPS = 4094
MAX_HSRP_GROUPS = 4094
MAX_GLBP_GROUPS = 1023

is_attr_set = bc_attr.is_attr_set
ATTR_NOT_SPECIFIED = bc_attr.ATTR_NOT_SPECIFIED
EXTERNAL_GW_INFO = l3.EXTERNAL_GW_INFO
DEVICE_OWNER_ROUTER_GW = l3_constants.DEVICE_OWNER_ROUTER_GW
DEVICE_OWNER_ROUTER_INTF = l3_constants.DEVICE_OWNER_ROUTER_INTF
DEVICE_OWNER_ROUTER_HA_INTF = l3_constants.DEVICE_OWNER_ROUTER_HA_INTF
ROUTER_ROLE_HA_REDUNDANCY = cisco_constants.ROUTER_ROLE_HA_REDUNDANCY

DEFAULT_MASTER_PRIORITY = 100
PRIORITY_INCREASE_STEP = -3
REDUNDANCY_ROUTER_SUFFIX = '_HA_backup_'
DEFAULT_PING_INTERVAL = 5
PROBE_TARGET_OPT_NAME = 'default_probe_target'

LOOKUP_RETRIES = 5
RETRY_INTERVAL = 3

router_appliance_opts = [
    cfg.BoolOpt('ha_support_enabled', default=True,
                help=_("Enables high-availability support")),
    cfg.BoolOpt('ha_enabled_by_default', default=False,
                help=_("Enables high-availability functionality for Neutron "
                       "router even if user does not explicitly request it")),
    cfg.IntOpt('default_ha_redundancy_level', default=ha.MIN_REDUNDANCY_LEVEL,
               help=_("Default number of routers added for redundancy when "
                      "high-availability by VRRP, HSRP, or GLBP is used")),
    cfg.StrOpt('default_ha_mechanism', default=ha.HA_HSRP,
               help=_("Default mechanism used to implement "
                      "high-availability")),
    cfg.ListOpt('disabled_ha_mechanisms', default=[],
                help=_("List of administratively disabled high-availability "
                       "mechanisms (VRRP, HSRP, GBLP)")),
    cfg.BoolOpt('connectivity_probing_enabled_by_default', default=False,
                help=_("Enables connectivity probing for high-availability "
                       "even if user does not explicitly request it")),
    cfg.StrOpt('default_probe_target', default=None,
               help=_("Host that will be probe target for high-availability "
                      "connectivity probing if user does not specify it")),
    cfg.StrOpt('default_ping_interval', default=DEFAULT_PING_INTERVAL,
               help=_("Time (in seconds) between probes for high-availability "
                      "connectivity probing if user does not specify it")),
]

cfg.CONF.register_opts(router_appliance_opts, "ha")


class RouterHASetting(model_base.BASEV2):
    """Represents HA settings for router visible to user."""
    __tablename__ = 'cisco_router_ha_settings'

    router_id = sa.Column(sa.String(36),
                          sa.ForeignKey('routers.id', ondelete='CASCADE'),
                          primary_key=True)
    router = orm.relationship(
        l3_db.Router,
        backref=orm.backref('ha_settings', cascade='all', uselist=False))
    # 'ha_type' can be 'VRRP', 'HSRP', or 'GLBP'
    ha_type = sa.Column(sa.String(255))
    # 'redundancy_level' is number of extra routers for redundancy
    redundancy_level = sa.Column(sa.Integer,
                                 server_default=str(ha.MIN_REDUNDANCY_LEVEL))
    # 'priority' is the priority used in VRRP, HSRP, and GLBP
    priority = sa.Column(sa.Integer)
    # 'probe_connectivity' is True if ICMP echo pinging is enabled
    probe_connectivity = sa.Column(sa.Boolean)
    # 'probe_target' is ip address of host that is probed
    probe_target = sa.Column(sa.String(64))
    # 'ping_interval' is the time between probes
    probe_interval = sa.Column(sa.Integer)
    # 'state' is the state of the user visible router: HA_ACTIVE or HA_STANDBY
    state = sa.Column(sa.Enum(ha.HA_ACTIVE, ha.HA_STANDBY, name='ha_states'),
                      default=ha.HA_ACTIVE, server_default=ha.HA_ACTIVE)


class RouterHAGroup(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents an HA group as used in VRRP, HSRP, and GLBP."""
    __tablename__ = 'cisco_router_ha_groups'

    # 'ha_type' can be 'VRRP', 'HSRP', or 'GLBP'
    ha_type = sa.Column(sa.String(255))
    # 'group_identity'
    group_identity = sa.Column(sa.String(255))
    # 'ha_port_id' is id of port used for virtual IP address
    ha_port_id = sa.Column(sa.String(36),
                           sa.ForeignKey('ports.id', ondelete='CASCADE'),
                           primary_key=True)
    ha_port = orm.relationship(
        models_v2.Port,
        primaryjoin='Port.id==RouterHAGroup.ha_port_id')
    # 'extra_port_id' is id of port for user visible router's extra ip address
    extra_port_id = sa.Column(sa.String(36),
                              sa.ForeignKey('ports.id', ondelete='SET NULL'),
                              nullable=True)
    extra_port = orm.relationship(
        models_v2.Port,
        primaryjoin='Port.id==RouterHAGroup.extra_port_id')
    # 'subnet_id' is id of subnet that this HA group serves
    subnet_id = sa.Column(sa.String(36),
                          sa.ForeignKey('subnets.id'),
                          nullable=True)
    # 'user_router_id' is id of router visible to the user
    user_router_id = sa.Column(sa.String(36),
                               sa.ForeignKey('routers.id'))
    # 'timers_config' holds timer specific configurations
    timers_config = sa.Column(sa.String(255))
    # 'tracking_config' holds tracking object specific configurations
    tracking_config = sa.Column(sa.String(255))
    # 'other_config' holds other method specific configurations
    other_config = sa.Column(sa.String(255))


class RouterRedundancyBinding(model_base.BASEV2):
    """Represents binding between an HA enabled router and its
    redundancy routers.
    """
    __tablename__ = 'cisco_router_redundancy_bindings'

    # 'redundancy_router_id' is id of a redundancy router
    redundancy_router_id = sa.Column(sa.String(36),
                                     sa.ForeignKey('routers.id',
                                                   ondelete='CASCADE'),
                                     primary_key=True)
    redundancy_router = orm.relationship(
        l3_db.Router,
        primaryjoin='Router.id==RouterRedundancyBinding.redundancy_router_id',
        backref=orm.backref('redundancy_binding', cascade='save-update, merge',
                            passive_deletes='all', uselist=False))
    # 'priority' is the priority used in VRRP, HSRP, and GLBP
    priority = sa.Column(sa.Integer)
    # 'state' is the state of the redundancy router: HA_ACTIVE or HA_STANDBY
    state = sa.Column(sa.Enum(ha.HA_ACTIVE, ha.HA_STANDBY, name='ha_states'),
                      default=ha.HA_STANDBY, server_default=ha.HA_STANDBY)
    # 'user_router_id' is id of router visible to the user
    user_router_id = sa.Column(sa.String(36),
                               sa.ForeignKey('routers.id'))
    user_router = orm.relationship(
        l3_db.Router,
        primaryjoin='Router.id==RouterRedundancyBinding.user_router_id',
        backref=orm.backref('redundancy_bindings',
                            order_by=priority, cascade='all'))
    __mapper_args__ = {
        'confirm_deleted_rows': False
    }


class HA_db_mixin(object):
    """Mixin class to support VRRP, HSRP, and GLBP based HA for routing."""

    def _ensure_create_ha_compliant(self, router, router_type):
        """To be called in create_router() BEFORE router is created in DB."""
        details = router.pop(ha.DETAILS, {})
        if details == ATTR_NOT_SPECIFIED:
            details = {}
        res = {ha.ENABLED: router.pop(ha.ENABLED, ATTR_NOT_SPECIFIED),
               ha.DETAILS: details}

        if not is_attr_set(res[ha.ENABLED]):
            res[ha.ENABLED] = router_type['ha_enabled_by_default']
        if res[ha.ENABLED] and not cfg.CONF.ha.ha_support_enabled:
            raise ha.HADisabled()
        if not res[ha.ENABLED]:
            return res
        if not is_attr_set(details.get(ha.TYPE, ATTR_NOT_SPECIFIED)):
            details[ha.TYPE] = cfg.CONF.ha.default_ha_mechanism
        if details[ha.TYPE] in cfg.CONF.ha.disabled_ha_mechanisms:
            raise ha.HADisabledHAType(ha_type=details[ha.TYPE])
        if not is_attr_set(details.get(ha.REDUNDANCY_LEVEL,
                                       ATTR_NOT_SPECIFIED)):
            details[ha.REDUNDANCY_LEVEL] = (
                cfg.CONF.ha.default_ha_redundancy_level)
        if not is_attr_set(details.get(ha.PROBE_CONNECTIVITY,
                                       ATTR_NOT_SPECIFIED)):
            details[ha.PROBE_CONNECTIVITY] = (
                cfg.CONF.ha.connectivity_probing_enabled_by_default)
        if not is_attr_set(details.get(ha.PROBE_TARGET, ATTR_NOT_SPECIFIED)):
            details[ha.PROBE_TARGET] = cfg.CONF.ha.default_probe_target
        if not is_attr_set(details.get(ha.PROBE_INTERVAL, ATTR_NOT_SPECIFIED)):
            details[ha.PROBE_INTERVAL] = cfg.CONF.ha.default_ping_interval
        return res

    def _create_redundancy_routers(self, context, new_router, ha_settings,
                                   new_router_db, ports=None, expire_db=False):
        """To be called in create_router() AFTER router has been
        created in DB.
        """
        if (ha.ENABLED not in ha_settings or
                not ha_settings[ha.ENABLED]):
            new_router[ha.HA] = {ha.ENABLED: False}
            return
        ha_spec = ha_settings[ha.DETAILS]
        priority = ha_spec.get(ha.PRIORITY, DEFAULT_MASTER_PRIORITY)
        with context.session.begin(subtransactions=True):
            r_ha_s_db = RouterHASetting(
                router_id=new_router['id'],
                ha_type=ha_spec[ha.TYPE],
                redundancy_level=ha_spec[ha.REDUNDANCY_LEVEL],
                priority=priority,
                probe_connectivity=ha_spec[ha.PROBE_CONNECTIVITY],
                probe_target=ha_spec[ha.PROBE_TARGET],
                probe_interval=ha_spec[ha.PROBE_INTERVAL])
            context.session.add(r_ha_s_db)
        if r_ha_s_db.probe_connectivity and r_ha_s_db.probe_target is None:
            LOG.warning(_LW("Connectivity probing for high-availability is "
                            "enabled but probe target is not specified. Please"
                            " configure option \'default_probe_target\'."))
        e_context = context.elevated()
        if new_router_db.gw_port:
            # generate ha settings and extra port for router gateway (VIP) port
            gw_port = self._core_plugin._make_port_dict(new_router_db.gw_port)
            self._create_ha_group(e_context, new_router, gw_port, r_ha_s_db)
        self._add_redundancy_routers(e_context, 1,
                                     ha_spec[ha.REDUNDANCY_LEVEL] + 1,
                                     new_router, ports or [], r_ha_s_db)
        if expire_db:
            context.session.expire(new_router_db)
        self._extend_router_dict_ha(new_router, new_router_db)

    def _ensure_update_ha_compliant(self, router, current_router,
                                    r_hd_binding_db):
        """To be called in update_router() BEFORE router has been
        updated in DB.
        """
        auto_enable_ha = r_hd_binding_db.router_type.ha_enabled_by_default
        requested_ha_details = router.pop(ha.DETAILS, {})
        # If ha_details are given then ha is assumed to be enabled even if
        # it is not explicitly specified or if auto_enable_ha says so.
        # Note that None is used to indicate that request did not include any
        # ha information was provided!
        requested_ha_enabled = router.pop(
            ha.ENABLED, True if requested_ha_details or auto_enable_ha is True
            else None)
        res = {}
        ha_currently_enabled = current_router.get(ha.ENABLED, False)
        # Note: must check for 'is True' as None implies attribute not given
        if requested_ha_enabled is True or ha_currently_enabled is True:
            if not cfg.CONF.ha.ha_support_enabled:
                raise ha.HADisabled()
            curr_ha_details = current_router.get(ha.DETAILS, {})
            if ha.TYPE in requested_ha_details:
                requested_ha_type = requested_ha_details[ha.TYPE]
                if (ha.TYPE in curr_ha_details and
                        requested_ha_type != curr_ha_details[ha.TYPE]):
                    raise ha.HATypeCannotBeChanged()
                elif requested_ha_type in cfg.CONF.ha.disabled_ha_mechanisms:
                    raise ha.HADisabledHAType(ha_type=requested_ha_type)
        if requested_ha_enabled:
            res[ha.ENABLED] = requested_ha_enabled
            if requested_ha_details:
                res[ha.DETAILS] = requested_ha_details
        elif requested_ha_enabled is False:
            res[ha.ENABLED] = False
        return res

    def _teardown_redundancy_router_gw_connectivity(self, context, router,
                                                    router_db,
                                                    plugging_driver):
        """To be called in update_router() if the router gateway is to change
        BEFORE router has been updated in DB .
        """
        if not router[ha.ENABLED]:
            # No HA currently enabled so we're done
            return
        e_context = context.elevated()
        # since gateway is about to change the ha group for the current gateway
        # is removed, a new one will be created later
        self._delete_ha_group(e_context, router_db.gw_port_id)
        # teardown connectivity for the gw ports on the redundancy routers
        # and remove those ports as new ones will be created later
        rr_ids = []
        for r_b_db in router_db.redundancy_bindings:
            if plugging_driver is not None:
                plugging_driver.teardown_logical_port_connectivity(
                    e_context, r_b_db.redundancy_router.gw_port,
                    r_b_db.redundancy_router.hosting_info.hosting_device_id)
            self._update_router_no_notify(
                e_context, r_b_db.redundancy_router_id,
                {'router': {EXTERNAL_GW_INFO: None, ha.ENABLED: False}})
            rr_ids.append(r_b_db.redundancy_router_id)
        self.notify_routers_updated(e_context, rr_ids)

    def _update_redundancy_routers(self, context, updated_router,
                                   update_specification, requested_ha_settings,
                                   updated_router_db, gateway_changed):
        """To be called in update_router() AFTER router has been
        updated in DB.
        """
        router_requested = update_specification['router']
        ha_settings_db = updated_router_db.ha_settings
        ha_enabled_requested = requested_ha_settings.get(ha.ENABLED, False)
        if not (updated_router[ha.ENABLED] or ha_enabled_requested):
            # No HA currently enabled and no HA requested so we're done
            return
        # The redundancy routers need interfaces on the same networks as the
        # user visible router.
        ports = self._get_router_interfaces(updated_router_db)
        e_context = context.elevated()
        if not updated_router[ha.ENABLED] and ha_enabled_requested:
            # No HA currently enabled but HA requested
            router_requested.update(requested_ha_settings)
            router_requested[EXTERNAL_GW_INFO] = (
                updated_router[EXTERNAL_GW_INFO])
            requested_ha_settings = self._ensure_create_ha_compliant(
                router_requested, updated_router_db.hosting_info.router_type)
            self._create_redundancy_routers(
                e_context, updated_router, requested_ha_settings,
                updated_router_db, ports, expire_db=True)
            return
        rr_ids = self._get_redundancy_router_ids(context, updated_router['id'])
        ha_details_update_spec = requested_ha_settings.get(ha.DETAILS)
        if (updated_router[ha.ENABLED] and not requested_ha_settings.get(
                ha.ENABLED, updated_router[ha.ENABLED])):
            # HA currently enabled but HA disable requested
            # delete ha settings and extra port for gateway (VIP) port
            self._delete_ha_group(e_context, updated_router_db.gw_port_id)
            self._remove_redundancy_routers(e_context, rr_ids, ports, True)
            with context.session.begin(subtransactions=True):
                context.session.delete(ha_settings_db)
        elif ha_details_update_spec:
            # HA currently enabled and HA setting update (other than
            # disable HA) requested
            old_redundancy_level = ha_settings_db.redundancy_level
            ha_settings_db.update(ha_details_update_spec)
            diff = (ha_details_update_spec.get(ha.REDUNDANCY_LEVEL,
                                               old_redundancy_level) -
                    old_redundancy_level)
            with context.session.begin(subtransactions=True):
                context.session.add(ha_settings_db)
            if diff < 0:
                # Remove -diff redundancy routers
                #TODO(bobmel): Ensure currently active router is excluded
                to_remove = rr_ids[len(rr_ids) + diff:]
                rr_ids = rr_ids[:len(rr_ids) + diff]
                self._remove_redundancy_routers(e_context, to_remove, ports)
            elif diff > 0:
                # Add diff redundancy routers
                start = old_redundancy_level + 1
                stop = start + diff
                self._add_redundancy_routers(e_context, start, stop,
                                             updated_router, ports,
                                             ha_settings_db, False)
            if gateway_changed is True:
                self._change_ha_for_gateway(e_context, updated_router,
                                            updated_router_db, ha_settings_db,
                                            router_requested, expire=True)
            else:
                # Notify redundancy routers about changes
                self.notify_routers_updated(e_context, rr_ids)

        elif gateway_changed is True:
            # HA currently enabled (and to remain so) nor any HA setting update
            # and gateway has changed
            self._change_ha_for_gateway(e_context, updated_router,
                                        updated_router_db, ha_settings_db,
                                        router_requested)
        # pick up updates to other attributes where it makes sense
        # and push - right now it is only admin_state_up.
        if 'admin_state_up' in update_specification['router']:
            other_updates_spec = {'router': {'admin_state_up':
                update_specification['router']['admin_state_up']}}
            self._process_other_router_updates(e_context, updated_router_db,
                                               other_updates_spec)
        # Ensure we get latest state from DB
        context.session.expire(updated_router_db)
        self._extend_router_dict_ha(updated_router, updated_router_db)

    def _change_ha_for_gateway(self, context, router, router_db,
                               ha_settings_db, update_spec, expire=False):
        # generate ha settings and extra port for router gateway VIP
        if router_db.gw_port is None:
            # gateway was removed and since gw's of redundancy routers are
            # removed by _teardown_redundancy_router_gw_connectivity we're done
            return
        gw_port = self._core_plugin._make_port_dict(router_db.gw_port)
        self._create_ha_group(context, router, gw_port, ha_settings_db)
        if expire is True:
            context.session.expire(router_db)
        # Now add gw to redundancy routers
        rr_ids = []
        for r_b_db in router_db.redundancy_bindings:
            spec = {EXTERNAL_GW_INFO: copy.copy(router[EXTERNAL_GW_INFO])}
            spec[EXTERNAL_GW_INFO].pop('external_fixed_ips', None)
            spec[ha.ENABLED] = False
            self._update_router_no_notify(
                context, r_b_db.redundancy_router_id, {'router': spec})
            rr_ids.append(r_b_db.redundancy_router_id)
        self.notify_routers_updated(context, rr_ids)

    def _process_other_router_updates(self, context, router_db, update_spec):
        rr_ids = []
        for r_b_db in router_db.redundancy_bindings:
            update_spec['router'][ha.ENABLED] = False
            self._update_router_no_notify(
                context, r_b_db.redundancy_router_id, update_spec)
            rr_ids.append(r_b_db.redundancy_router_id)
        self.notify_routers_updated(context, rr_ids)

    def _add_redundancy_routers(self, context, start_index, stop_index,
                                user_visible_router, ports=None,
                                ha_settings_db=None, create_ha_group=True):
        """Creates a redundancy router and its interfaces on
        the specified subnets.
        """
        priority = (DEFAULT_MASTER_PRIORITY +
                    (start_index - 1) * PRIORITY_INCREASE_STEP)
        r = copy.deepcopy(user_visible_router)
        # No tenant_id so redundancy routers are hidden from user
        r['tenant_id'] = ''
        name = r['name']
        redundancy_r_ids = []
        for i in range(start_index, stop_index):
            del r['id']
            # We don't replicate the user visible router's routes, instead
            # they are populated to redundancy routers for get router(s) ops
            r.pop('routes', None)
            # Redundancy routers will never have a route spec themselves
            # The redundancy routers must have HA disabled
            r[ha.ENABLED] = False
            r['name'] = name + REDUNDANCY_ROUTER_SUFFIX + str(i)
            # set role so that purpose of this router can be easily determined
            r[routerrole.ROUTER_ROLE_ATTR] = ROUTER_ROLE_HA_REDUNDANCY
            gw_info = r[EXTERNAL_GW_INFO]
            if gw_info and gw_info['external_fixed_ips']:
                # Ensure ip addresses are not specified as they cannot be
                # same as visible router's ip addresses.
                for e_fixed_ip in gw_info['external_fixed_ips']:
                    e_fixed_ip.pop('ip_address', None)
            r = self.create_router(context, {'router': r})
            LOG.debug("Created redundancy router %(index)d with router id "
                      "%(r_id)s", {'index': i, 'r_id': r['id']})
            priority += PRIORITY_INCREASE_STEP
            r_b_b = RouterRedundancyBinding(
                redundancy_router_id=r['id'],
                priority=priority,
                user_router_id=user_visible_router['id'])
            context.session.add(r_b_b)
            redundancy_r_ids.append(r['id'])
        for port_db in ports or []:
            port = self._core_plugin._make_port_dict(port_db)
            self._add_redundancy_router_interfaces(
                context, user_visible_router, None, port,
                redundancy_r_ids, ha_settings_db, create_ha_group)

    def _remove_redundancy_routers(self, context, router_ids, ports,
                                   delete_ha_groups=False):
        """Deletes all interfaces of the specified redundancy routers
        and then the redundancy routers themselves.
        """
        subnets_info = [{'subnet_id': port['fixed_ips'][0]['subnet_id']}
                        for port in ports]
        for r_id in router_ids:
            for i in range(len(subnets_info)):
                self.remove_router_interface(context, r_id, subnets_info[i])
                LOG.debug("Removed interface on %(s_id)s to redundancy router "
                          "with %(r_id)s",
                          {'s_id': ports[i]['network_id'], 'r_id': r_id})
                # There is only one ha group per network so only delete once
                if delete_ha_groups and r_id == router_ids[0]:
                    self._delete_ha_group(context, ports[i]['id'])
            self.delete_router(context, r_id)
            LOG.debug("Deleted redundancy router %s", r_id)

    def _get_router_interfaces(self, router_db,
                               port_type=DEVICE_OWNER_ROUTER_INTF):
        return [p['port'] for p in router_db.attached_ports if
                p['port_type'] == port_type]

    def _delete_redundancy_routers(self, context, router_db):
        """To be called in delete_router() BEFORE router has been
        deleted in DB. The router should have not interfaces.
        """
        e_context = context.elevated()
        for binding in router_db.redundancy_bindings:
            self.delete_router(e_context, binding.redundancy_router_id)
            LOG.debug("Deleted redundancy router %s",
                      binding.redundancy_router_id)
        if router_db.gw_port_id:
            # delete ha settings and extra port for gateway (VIP) port
            self._delete_ha_group(e_context, router_db.gw_port_id)

    def _add_redundancy_router_interfaces(self, context, router, itfc_info,
                                          new_port, redundancy_router_ids=None,
                                          ha_settings_db=None,
                                          create_ha_group=True):
        """To be called in add_router_interface() AFTER interface has been
        added to router in DB.
        """
        # There are essentially three cases where we add interface to a
        # redundancy router:
        # 1. HA is enabled on a user visible router that has one or more
        #    interfaces.
        # 2. Redundancy level is increased so one or more redundancy routers
        #    are added.
        # 3. An interface is added to a user visible router.
        #
        # For 1: An HA GROUP MUST BE CREATED and EXTRA PORTS MUST BE CREATED
        #        for each redundancy router. The id of extra port should be
        #        specified in the interface_info argument of the
        #        add_router_interface call so that we ADD BY PORT.
        # For 2: HA group need NOT be created as it will already exist (since
        #        there is already at least on redundancy router). EXTRA PORTS
        #        MUST BE CREATED for each added redundancy router. The id
        #        of extra port should be specified in the interface_info
        #        argument of the add_router_interface call so that we ADD BY
        #        PORT.
        # For 3: if the interface for the user_visible_router was added by ...
        #   a) PORT:   An HA GROUP MUST BE CREATED and and EXTRA PORTS MUST BE
        #              CREATED for each redundancy router. The id of extra port
        #              should be specified in the interface_info argument of
        #              the add_router_interface call so that we ADD BY PORT.
        #   b) SUBNET: There are two cases to consider. If the added interface
        #              of the user_visible_router has ...
        #        b1) 1 SUBNET:   An HA GROUP MUST BE CREATED and and EXTRA
        #                        PORTS MUST BE CREATED for each redundancy
        #                        router. The id of extra port should be
        #                        specified in the interface_info argument of
        #                        the add_router_interface call so we ADD BY
        #                        PORT.
        #        b2) >1 SUBNETS: HA group need NOT be created as it will
        #                        already exist (since the redundancy routers
        #                        should already have extra ports to which the
        #                        (IPv6) subnet is added. Extra ports need
        #                        thus NOT be created. The subnet id should be
        #                        added to the existing extra ports.
        router_id = router['id']
        if ha_settings_db is None:
            ha_settings_db = self._get_ha_settings_by_router_id(context,
                                                                router_id)
        if ha_settings_db is None:
            return
        e_context = context.elevated()
        add_by_subnet = (itfc_info is not None and 'subnet_id' in itfc_info and
                         len(new_port['fixed_ips']) > 1)
        if (add_by_subnet is False or (itfc_info is None and
                                       create_ha_group is True)):
            # generate ha settings and extra port for router (VIP) port
            self._create_ha_group(e_context, router, new_port, ha_settings_db)
        fixed_ips = self._get_fixed_ips_subnets(new_port['fixed_ips'])
        for r_id in (redundancy_router_ids or
                     self._get_redundancy_router_ids(e_context, router_id)):
            if add_by_subnet is True:
                # need to add subnet to redundancy router port
                ports = self._core_plugin.get_ports(
                    e_context,
                    filters={'device_id': [r_id],
                             'network_id': [new_port['network_id']]},
                    fields=['fixed_ips', 'id'])
                redundancy_port = ports[0]
                fixed_ips = redundancy_port['fixed_ips']
                fixed_ip = {'subnet_id': itfc_info['subnet_id']}
                fixed_ips.append(fixed_ip)
                self._core_plugin.update_port(
                    e_context, redundancy_port['id'],
                    {'port': {'fixed_ips': fixed_ips}})
            else:
                redundancy_port = self._create_hidden_port(
                    e_context, new_port['network_id'], '', fixed_ips)
                interface_info = {'port_id': redundancy_port['id']}
                self.add_router_interface(e_context, r_id, interface_info)

    def _update_redundancy_router_interfaces(self, context, router,
                                             port, modified_port_data,
                                             redundancy_router_ids=None,
                                             ha_settings_db=None):
        """To be called when the router interfaces are updated,
        like in the case of change in port admin_state_up status
        """
        router_id = router['id']
        if ha_settings_db is None:
            ha_settings_db = self._get_ha_settings_by_router_id(context,
                                                                router_id)
        if ha_settings_db is None:
            return
        e_context = context.elevated()

        rr_ids = self._get_redundancy_router_ids(e_context, router_id)
        port_info_list = self._core_plugin.get_ports(
            e_context, filters={'device_id': rr_ids,
                                'network_id': [port['network_id']]},
            fields=['device_id', 'id'])
        for port_info in port_info_list:
            self._core_plugin.update_port(e_context, port_info['id'],
                                          modified_port_data)
        self._update_hidden_port(e_context, port['id'], modified_port_data)

    def _create_ha_group(self, context, router, port, ha_settings_db):
        driver = self._get_router_type_driver(context,
                                              router[routertype.TYPE_ATTR])
        if driver is None:
            return
        ha_group_uuid = uuidutils.generate_uuid()
        # use HA group as device instead of the router to hide this port
        with context.session.begin(subtransactions=True):
            group_id = (driver.generate_ha_group_id(context, router, port,
                                                    ha_settings_db,
                                                    ha_group_uuid) or
                        self._generate_ha_group_id(context, router, port,
                                                   ha_settings_db,
                                                   ha_group_uuid))
            timers_cfg = driver.get_ha_group_timers_parameters(
                context, router, port, ha_settings_db, ha_group_uuid)
            tracking_cfg = driver.get_ha_group_tracking_parameters(
                context, router, port, ha_settings_db, ha_group_uuid)
            other_cfg = driver.get_other_ha_group_parameters(
                context, router, port, ha_settings_db, ha_group_uuid)
            if driver.ha_interface_ip_address_needed(
                    context, router, port, ha_settings_db, ha_group_uuid):
                fixed_ips = self._get_fixed_ips_subnets(port['fixed_ips'])
                extra_port = self._create_hidden_port(
                    context, port['network_id'], ha_group_uuid,
                    fixed_ips, port['device_owner'])
                extra_port_id = extra_port['id']
            else:
                extra_port_id = None
            subnet_id = (port['fixed_ips'][0]['subnet_id']
                         if port['fixed_ips'] else None)
            r_ha_g = RouterHAGroup(
                id=ha_group_uuid,
                tenant_id=port['tenant_id'],
                ha_type=ha_settings_db.ha_type,
                group_identity=group_id,
                ha_port_id=port['id'],
                extra_port_id=extra_port_id,
                subnet_id=subnet_id,
                user_router_id=router['id'],
                timers_config=timers_cfg,
                tracking_config=tracking_cfg,
                other_config=other_cfg)
            context.session.add(r_ha_g)
        return r_ha_g

    def _get_fixed_ips_subnets(self, fixed_ips):
        subnets = copy.copy(fixed_ips)
        for s in subnets:
            s.pop('ip_address', None)
        return subnets

    def _remove_redundancy_router_interfaces(self, context, router_id,
                                             old_port):
        """To be called in delete_router_interface() BEFORE interface has been
        removed from router in DB.
        """
        ha_settings = self._get_ha_settings_by_router_id(context, router_id)
        if ha_settings is None or old_port is None:
            return
        e_context = context.elevated()
        rr_ids = self._get_redundancy_router_ids(e_context, router_id)
        port_info_list = self._core_plugin.get_ports(
            e_context, filters={'device_id': rr_ids,
                                'network_id': [old_port['network_id']]},
            fields=['device_id', 'id'])
        for port_info in port_info_list:
            interface_info = {'port_id': port_info['id']}
            self.remove_router_interface(e_context, port_info['device_id'],
                                         interface_info)
        self._delete_ha_group(e_context, old_port['id'])

    def _redundancy_routers_for_floatingip(
            self, context, router_id, redundancy_router_ids=None,
            ha_settings_db=None):
        """To be called in update_floatingip() to get the
            redundant router ids.
        """
        if ha_settings_db is None:
            ha_settings_db = self._get_ha_settings_by_router_id(context,
                                                                router_id)
        if ha_settings_db is None:
            return

        e_context = context.elevated()
        router_ids = []
        for r_id in (redundancy_router_ids or
                     self._get_redundancy_router_ids(e_context, router_id)):
            router_ids.append(r_id)

        return router_ids

    def _update_hidden_port(self, context, ha_port_id, modified_port_data):
        hag = self._get_ha_group_by_ha_port_id(context, ha_port_id)
        if hag is not None:
            self._core_plugin.update_port(context, hag.extra_port_id,
                                          modified_port_data)

    def _delete_ha_group(self, context, ha_port_id):
        hag = self._get_ha_group_by_ha_port_id(context, ha_port_id)
        if hag is not None and hag.extra_port_id is not None:
            self._core_plugin.delete_port(context, hag.extra_port_id,
                                          l3_port_check=False)
            with context.session.begin(subtransactions=True):
                context.session.delete(hag)

    def _extend_router_dict_ha(self, router_res, router_db):
        if utils.is_extension_supported(self, ha.HA_ALIAS):
            ha_s = router_db.ha_settings
            rr_b = router_db.redundancy_binding
            if rr_b and rr_b.user_router:
                # include static routes from user visible router
                temp = {}
                self._extend_router_dict_extraroute(temp,
                                                    rr_b.user_router)
                if temp['routes']:
                    router_res['routes'].extend(temp['routes'])
            router_res[ha.ENABLED] = False if ha_s is None else True
            if router_res[ha.ENABLED]:
                ha_details = {ha.TYPE: ha_s.ha_type,
                              ha.PRIORITY: ha_s.priority,
                              ha.STATE: ha_s.state,
                              ha.REDUNDANCY_LEVEL: ha_s.redundancy_level,
                              ha.PROBE_CONNECTIVITY: ha_s.probe_connectivity}
                if ha_details[ha.PROBE_CONNECTIVITY]:
                    ha_details.update({ha.PROBE_TARGET: ha_s.probe_target,
                                       ha.PROBE_INTERVAL: ha_s.probe_interval})
                ha_details[ha.REDUNDANCY_ROUTERS] = (
                    [{'id': b.redundancy_router_id, ha.PRIORITY: b.priority,
                      ha.STATE: b.state}
                     for b in router_db.redundancy_bindings])
                router_res[ha.DETAILS] = ha_details
            else:
                # ensure any router details are removed
                router_res.pop(ha.DETAILS, None)

    def _populate_ha_information(self, context, router):
        """To be called when router information, including router interface
        list, (for the l3_cfg_agent) has been collected so it is extended
        with ha information.
        """
        r_r_b = self._get_redundancy_router_bindings(
            context, redundancy_router_id=router['id'])
        if not r_r_b:
            if router[ha.ENABLED]:
                # The router is a user visible router with HA enabled.
                user_router_id = router['id']
                fips = []
            else:
                # The router is a user visible router with HA disabled.
                # Nothing more to do here.
                return
        else:
            # The router is a redundancy router.
            # Need to fetch floatingip configurations from user visible router
            # so they can be added to the redundancy routers.
            user_router_id = r_r_b[0].user_router_id
            fips = self.get_floatingips(context,
                                        {'router_id': [user_router_id]})
        if router['id'] != user_router_id:
            # We add the HA settings from user visible router to
            # its redundancy routers.
            user_router_db = self._get_router(context, user_router_id)
            self._extend_router_dict_ha(router, user_router_db)
        # The interfaces of the user visible router must use the
        # IP configuration of the extra ports in the HA groups.
        hags = self._get_subnet_id_indexed_ha_groups(context, user_router_id)
        e_context = context.elevated()
        if router.get('gw_port'):
            modified_interfaces = []
            interface_port = self._populate_port_ha_information(
                e_context, router['gw_port'], router['id'], hags,
                user_router_id, modified_interfaces)
            if not interface_port:
                # The router has a gw_port but cannot find the port info yet
                # so mark this router to have incomplete info and bail.
                # The cfg_agent puts this in the updated_routers to ask again.
                router['status'] = cisco_constants.ROUTER_INFO_INCOMPLETE
                return
            if modified_interfaces:
                router['gw_port'] = interface_port
        modified_interfaces = []
        for itfc in router.get(l3_constants.INTERFACE_KEY, []):
            interface_port = self._populate_port_ha_information(
                e_context, itfc, router['id'], hags, user_router_id,
                modified_interfaces)
            if not interface_port:
                # the router has interfaces but cannot find the port info yet
                # so mark this router to have incomplete info and bail
                # the cfg_agent will put this in the updated_list to ask again
                router['status'] = cisco_constants.ROUTER_INFO_INCOMPLETE
                return
        if modified_interfaces:
            router[l3_constants.INTERFACE_KEY] = modified_interfaces
        if fips:
            router[l3_constants.FLOATINGIP_KEY] = fips

    def _populate_port_ha_information(self, context, port, router_id, hags,
                                      user_router_id, modified_interfaces):
        subnet_id = port['fixed_ips'][0]['subnet_id']
        try:
            hag = hags[subnet_id]
        except KeyError:
            # Oops, the subnet_id was not found. Probably because the DB
            # insertion of that HA group is still in progress by another
            # process and has not been committed to the DB yet.
            # Let's retry a few times to see if the DB entry turns up.
            LOG.debug('No HA group info for router: %(r_id)s and subnet: '
                      '%(s_id)s was found when populating HA info for port: '
                      '%(p_id)s. Will now make additional lookup attempts.',
                      {'r_id': router_id, 's_id': subnet_id,
                       'p_id': port['id']})
            try:
                hag = self._get_ha_group_for_subnet_id(context, router_id,
                                                       subnet_id)
            except exc.NoResultFound:
                hag = None
        if hag is None:
            LOG.debug('Failed to fetch the HA group info for for router: '
                      '%(r_id)s and subnet: %(s_id)s. Giving up. No HA '
                      'info will be added to the router\'s port: %(p_id)s.',
                      {'r_id': router_id, 's_id': subnet_id,
                       'p_id': port['id']})
            # we leave it to the L3 config agent to handle this
            return
        else:
            LOG.debug('Successfully fetched the HA group info for '
                      'router: %(r_id)s and subnet: %(s_id)s from DB',
                      {'r_id': router_id, 's_id': subnet_id})
            hags[subnet_id] = hag
        if router_id == user_router_id:
            # If the router interface need no dedicated IP address we just
            # set the HA (VIP) port to the port itself. The config agent
            # driver will know how to handle this "signal".
            p_id = hag.extra_port_id or port['id']
            try:
                interface_port = self._core_plugin.get_port(context, p_id)
            except n_exc.PortNotFound:
                LOG.debug('**** NO Port Info for '
                    'router: %(r_id)s : Port: %(p_id)s from DB',
                    {'r_id': router_id, 'p_id': port['id']})
                return
            LOG.debug('**** Fetched Port Info for '
                'router: %(r_id)s : Port: %(p_id)s from DB',
                {'r_id': router_id, 'p_id': port['id']})
            self._populate_mtu_and_subnets_for_ports(context, [interface_port])
            modified_interfaces.append(interface_port)
            ha_port = port
        else:
            try:
                ha_port = self._core_plugin.get_port(context, hag.ha_port_id)
            except n_exc.PortNotFound:
                LOG.debug('**** NO Port Info for '
                    'router(BAK): %(r_id)s : Port: %(p_id)s from DB',
                    {'r_id': router_id, 'p_id': hag.ha_port_id})
                return
            LOG.debug('**** Fetched Port Info for '
                'router(BAK): %(r_id)s : Port: %(p_id)s from DB',
                {'r_id': router_id, 'p_id': hag.ha_port_id})
            self._populate_mtu_and_subnets_for_ports(context, [ha_port])
            interface_port = port
        interface_port[ha.HA_INFO] = {
            ha.TYPE: hag.ha_type,
            HA_GROUP: hag.group_identity,
            'timers_config': hag.timers_config,
            'tracking_config': hag.tracking_config,
            'other_config': hag.other_config,
            HA_PORT: ha_port}
        return interface_port

    def _create_hidden_port(self, context, network_id, device_id, fixed_ips,
                            port_type=DEVICE_OWNER_ROUTER_INTF):
        """Creates port used specially for HA purposes."""
        port = {'port': {
            'tenant_id': '',  # intentionally not set
            'network_id': network_id,
            'mac_address': bc_attr.ATTR_NOT_SPECIFIED,
            'fixed_ips': fixed_ips,
            'device_id': device_id,
            'device_owner': port_type,
            'admin_state_up': True,
            'name': ''}}
        if utils.is_extension_supported(self._core_plugin, "dns-integration"):
                port['port'].update(dns_name='')
        return self._core_plugin.create_port(context, port)

    def _get_ha_settings_by_router_id(self, context, router_id):
        query = context.session.query(RouterHASetting)
        query = query.filter(RouterHASetting.router_id == router_id)
        try:
            r_ha_s = query.one()
        except (exc.NoResultFound, exc.MultipleResultsFound):
            return
        return r_ha_s

    def _get_ha_group_by_ha_port_id(self, context, port_id):
        query = context.session.query(RouterHAGroup)
        query = query.filter(RouterHAGroup.ha_port_id == port_id)
        try:
            r_ha_g = query.one()
        except (exc.NoResultFound, exc.MultipleResultsFound):
            return
        return r_ha_g

    def _get_subnet_id_indexed_ha_groups(self, context, router_id,
                                         load_virtual_port=False):
        query = context.session.query(RouterHAGroup)
        query = query.filter(RouterHAGroup.user_router_id == router_id)
        if load_virtual_port:
            query = query.options(joinedload('redundancy_router'))
        return {hag['subnet_id']: hag for hag in query}

    @cisco_utils.retry(exc.NoResultFound, LOOKUP_RETRIES, RETRY_INTERVAL, 1)
    def _get_ha_group_for_subnet_id(self, context, router_id, subnet_id):
        query = context.session.query(RouterHAGroup)
        query = query.filter_by(user_router_id=router_id,
                                subnet_id=subnet_id)
        LOG.debug('Trying to fetch HA group info for router: %(r_id)s and '
                  'subnet: %(s_id)s', {'r_id': router_id,
                                       's_id': subnet_id})
        return query.one()

    def _get_redundancy_router_bindings(self, context, router_id=None,
                                        redundancy_router_id=None):
        query = context.session.query(RouterRedundancyBinding)
        if router_id is not None:
            query = query.filter(
                RouterRedundancyBinding.user_router_id == router_id)
        if redundancy_router_id is not None:
            query = query.filter(
                RouterRedundancyBinding.redundancy_router_id ==
                redundancy_router_id)
        query = query.order_by(RouterRedundancyBinding.priority)
        return query.all()

    def _get_redundancy_router_ids(self, context, router_id):
        return [binding.redundancy_router_id for binding in
                self._get_redundancy_router_bindings(context,
                                                     router_id=router_id)]

    def _generate_ha_group_id(self, context, router, port, ha_settings_db,
                              ha_group_uuid):
        #TODO(bob-melander): Generate "guaranteed" unique id
        if ha_settings_db.ha_type == ha.HA_HSRP:
            return random.randint(0, MAX_HSRP_GROUPS)
        elif ha_settings_db.ha_type == ha.HA_VRRP:
            return random.randint(0, MAX_VRRP_GROUPS)
        else:
            # ha_type must be ha_type.GLBP
            return random.randint(0, MAX_GLBP_GROUPS)

    # Overloaded function from l3_db
    def get_router_for_floatingip(self, context, internal_port,
                                  internal_subnet, external_network_id):
        """We need to over-load this function so that we only return the
        user visible router and never its redundancy routers (as they never
        have floatingips associated with them).
        """
        gw_port = orm.aliased(models_v2.Port, name="gw_port")
        routerport_qry = context.session.query(
            RouterPort.router_id, models_v2.IPAllocation.ip_address).join(
            models_v2.Port, models_v2.IPAllocation).filter(
            models_v2.Port.network_id == internal_port['network_id'],
            RouterPort.port_type.in_(l3_constants.ROUTER_INTERFACE_OWNERS),
            models_v2.IPAllocation.subnet_id == internal_subnet['id']
        ).join(gw_port, gw_port.device_id == RouterPort.router_id).filter(
            gw_port.network_id == external_network_id,
            gw_port.device_owner == l3_constants.DEVICE_OWNER_ROUTER_GW
        ).distinct()

        # Ensure that redundancy routers (in a ha group) are not returned,
        # since only the user visible router should have floatingips.
        # This can be done by checking that the id of routers does not
        # appear in the 'redundancy_router_id' column in the
        # 'cisco_router_redundancy_bindings' table.
        routerport_qry = routerport_qry.outerjoin(
            RouterRedundancyBinding,
            RouterRedundancyBinding.redundancy_router_id ==
            RouterPort.router_id)
        routerport_qry = routerport_qry.filter(
            RouterRedundancyBinding.redundancy_router_id == expr.null())

        first_router_id = None
        for router_id, interface_ip in routerport_qry:
            if interface_ip == internal_subnet['gateway_ip']:
                return router_id
            if not first_router_id:
                first_router_id = router_id
        if first_router_id:
            return first_router_id

        raise l3.ExternalGatewayForFloatingIPNotFound(
            subnet_id=internal_subnet['id'],
            external_network_id=external_network_id,
            port_id=internal_port['id'])
