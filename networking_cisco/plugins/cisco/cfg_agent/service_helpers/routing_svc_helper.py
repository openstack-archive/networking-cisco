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

import collections
import eventlet
import netaddr
import pprint as pp

# from ncclient.transport import errors as ncc_errors
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging
from oslo_utils import excutils
from oslo_utils import importutils
import six

from neutron.common import constants as l3_constants
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron.common import utils as common_utils
from neutron import context as n_context

from networking_cisco._i18n import _
from networking_cisco._i18n import _LE
from networking_cisco._i18n import _LI
from networking_cisco._i18n import _LW
from networking_cisco.plugins.cisco.cfg_agent import cfg_exceptions
from networking_cisco.plugins.cisco.cfg_agent.device_drivers import driver_mgr
from networking_cisco.plugins.cisco.cfg_agent import device_status
from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routerrole

ncc_errors = importutils.try_import('ncclient.transport.errors')

LOG = logging.getLogger(__name__)


N_ROUTER_PREFIX = 'nrouter-'
ROUTER_ROLE_ATTR = routerrole.ROUTER_ROLE_ATTR


class RouterInfo(object):
    """Wrapper class around the (neutron) router dictionary.

    Information about the neutron router is exchanged as a python dictionary
    between plugin and config agent. RouterInfo is a wrapper around that dict,
    with attributes for common parameters. These attributes keep the state
    of the current router configuration, and are used for detecting router
    state changes when an updated router dict is received.

    This is a modified version of the RouterInfo class defined in the
    (reference) l3-agent implementation, for use with cisco config agent.
    """

    def __init__(self, router_id, router):
        self.router_id = router_id
        self.ex_gw_port = None
        self._snat_enabled = None
        self._snat_action = None
        self.internal_ports = []
        self.floating_ips = []
        self._router = None
        self.router = router
        self.routes = []
        self.ha_info = router.get('ha_info')

    @property
    def router(self):
        return self._router

    @property
    def id(self):
        return self.router_id

    @property
    def snat_enabled(self):
        return self._snat_enabled

    @router.setter
    def router(self, value):
        self._router = value
        if not self._router:
            return
        # enable_snat by default if it wasn't specified by plugin
        self._snat_enabled = self._router.get('enable_snat', True)

    def router_name(self):
        return N_ROUTER_PREFIX + self.router_id

    @property
    def ha_enabled(self):
        ha_enabled = self.router.get(ha.ENABLED, False)
        return ha_enabled


class CiscoRoutingPluginApi(object):
    """RoutingServiceHelper(Agent) side of the routing RPC API."""

    def __init__(self, topic, host):
        self.host = host
        target = oslo_messaging.Target(topic=topic, version='1.0')
        self.client = n_rpc.get_client(target)

    def get_routers(self, context, router_ids=None, hd_ids=None):
        """Make a remote process call to retrieve the sync data for routers.

        :param context: session context
        :param router_ids: list of  routers to fetch
        :param hd_ids : hosting device ids, only routers assigned to these
                        hosting devices will be returned.
        """
        cctxt = self.client.prepare(version='1.1')
        return cctxt.call(context, 'cfg_sync_routers', host=self.host,
                          router_ids=router_ids, hosting_device_ids=hd_ids)

    def get_hardware_router_type_id(self, context):
        """Get the ID for the ASR1k hardware router type."""
        cctxt = self.client.prepare()
        return cctxt.call(context,
                          'get_hardware_router_type_id',
                          host=self.host)

    def update_floatingip_statuses(self, context, router_id, fip_statuses):
        """Make a remote process call to update operational status for one or
        several floating IPs.

        @param context: contains user information
        @param router_id: id of router associated with the floatingips
        @param fip_statuses: dict with floatingip_id as key and status as value
        """
        cctxt = self.client.prepare(version='1.1')
        return cctxt.call(context, 'update_floatingip_statuses_cfg',
                          router_id=router_id, fip_statuses=fip_statuses)

    def send_update_port_statuses(self, context, port_ids, status):
        """Call the pluging to update the port status which updates the DB.

        :param context: contains user information
        :param port_ids: list of ids of the ports associated with the status
        :param status: value of the status for the given port list (port_ids)
        """
        cctxt = self.client.prepare(version='1.1')
        return cctxt.call(context, 'update_port_statuses_cfg',
                          port_ids=port_ids, status=status)


class RoutingServiceHelper(object):

    target = oslo_messaging.Target(version='1.1')

    def __init__(self, host, conf, cfg_agent):
        self.conf = conf
        self.cfg_agent = cfg_agent
        self.context = n_context.get_admin_context_without_session()
        self.plugin_rpc = CiscoRoutingPluginApi(topics.L3PLUGIN, host)
        self._dev_status = device_status.DeviceStatus()
        self._dev_status.enable_heartbeat = (
            self.conf.cfg_agent.enable_heartbeat)
        self._drivermgr = driver_mgr.DeviceDriverManager()

        self.router_info = {}
        self.updated_routers = set()
        self.removed_routers = set()
        self.sync_devices = set()
        self.sync_devices_attempts = 0
        self.fullsync = True
        self.topic = '%s.%s' % (c_constants.CFG_AGENT_L3_ROUTING, host)

        self.hardware_router_type = None
        self.hardware_router_type_id = None

        self._setup_rpc()

    def _setup_rpc(self):
        self.conn = n_rpc.create_connection()
        self.endpoints = [self]
        self.conn.create_consumer(self.topic, self.endpoints, fanout=False)
        self.conn.consume_in_threads()

    ### Notifications from Plugin ####

    def router_deleted(self, context, routers):
        """Deal with router deletion RPC message."""
        LOG.debug('Got router deleted notification for %s', routers)
        self.removed_routers.update(routers)

    def routers_updated(self, context, routers):
        """Deal with routers modification and creation RPC message."""
        LOG.debug('Got routers updated notification :%s', routers)
        if routers:
            # This is needed for backward compatibility
            if isinstance(routers[0], dict):
                routers = [router['id'] for router in routers]
            self.updated_routers.update(routers)

    def router_removed_from_hosting_device(self, context, routers):
        LOG.debug('Got router removed from hosting device: %s', routers)
        self.router_deleted(context, routers)

    def router_added_to_hosting_device(self, context, routers):
        LOG.debug('Got router added to hosting device :%s', routers)
        self.routers_updated(context, routers)

    # version 1.1
    def routers_removed_from_hosting_device(self, context, router_ids):
        LOG.debug('Got routers removed from hosting device: %s', router_ids)
        self.router_deleted(context, router_ids)

    # Routing service helper public methods

    @property
    def driver_manager(self):
        return self._drivermgr

    def process_service(self, device_ids=None, removed_devices_info=None):
        try:
            LOG.debug("Routing service processing started")
            resources = {}
            routers = []
            removed_routers = []
            all_routers_flag = False
            if self.fullsync:
                LOG.debug("FullSync flag is on. Starting fullsync")
                # Setting all_routers_flag and clear the global full_sync flag
                all_routers_flag = True
                self.fullsync = False
                self.router_info = {}
                self.updated_routers.clear()
                self.removed_routers.clear()
                self.sync_devices.clear()
                routers = self._fetch_router_info(all_routers=True)
                LOG.debug("All routers: %s" % (pp.pformat(routers)))
                if routers is not None:
                    self._cleanup_invalid_cfg(routers)
            else:
                if self.updated_routers:
                    router_ids = list(self.updated_routers)
                    LOG.debug("Updated routers:%s", router_ids)
                    self.updated_routers.clear()
                    routers = self._fetch_router_info(router_ids=router_ids)
                    LOG.debug("Updated routers:%s" % (pp.pformat(routers)))
                if device_ids:
                    LOG.debug("Adding new devices:%s", device_ids)
                    self.sync_devices = set(device_ids) | self.sync_devices
                if self.sync_devices:
                    self._handle_sync_devices(routers)
                if removed_devices_info:
                    if removed_devices_info.get('deconfigure'):
                        ids = self._get_router_ids_from_removed_devices_info(
                            removed_devices_info)
                        self.removed_routers = self.removed_routers | set(ids)
                if self.removed_routers:
                    removed_routers_ids = list(self.removed_routers)
                    LOG.debug("Removed routers:%s",
                              pp.pformat(removed_routers_ids))
                    for r in removed_routers_ids:
                        if r in self.router_info:
                            removed_routers.append(self.router_info[r].router)

            # Sort on hosting device
            if routers:
                resources['routers'] = routers
            if removed_routers:
                resources['removed_routers'] = removed_routers
            hosting_devices = self._sort_resources_per_hosting_device(
                resources)

            # Dispatch process_services() for each hosting device
            pool = eventlet.GreenPool()
            for device_id, resources in hosting_devices.items():
                routers = resources.get('routers', [])
                removed_routers = resources.get('removed_routers', [])
                pool.spawn_n(self._process_routers, routers, removed_routers,
                             device_id, all_routers=all_routers_flag)
            pool.waitall()
            if removed_devices_info:
                for hd_id in removed_devices_info['hosting_data']:
                    self.driver_manager.remove_driver_for_hosting_device(hd_id)
            LOG.debug("Routing service processing successfully completed")
        except Exception:
            LOG.exception(_LE("Failed processing routers"))
            self.fullsync = True

    def collect_state(self, configurations):
        """Collect state from this helper.

        A set of attributes which summarizes the state of the routers and
        configurations managed by this config agent.
        :param configurations: dict of configuration values
        :return dict of updated configuration values
        """
        num_ex_gw_ports = 0
        num_interfaces = 0
        num_floating_ips = 0
        router_infos = self.router_info.values()
        num_routers = len(router_infos)
        num_hd_routers = collections.defaultdict(int)
        for ri in router_infos:
            ex_gw_port = ri.router.get('gw_port')
            if ex_gw_port:
                num_ex_gw_ports += 1
            num_interfaces += len(ri.router.get(
                l3_constants.INTERFACE_KEY, []))
            num_floating_ips += len(ri.router.get(
                l3_constants.FLOATINGIP_KEY, []))
            hd = ri.router['hosting_device']
            if hd:
                num_hd_routers[hd['id']] += 1
        routers_per_hd = dict((hd_id, {'routers': num})
                              for hd_id, num in num_hd_routers.items())
        non_responding = self._dev_status.get_backlogged_hosting_devices()
        configurations['total routers'] = num_routers
        configurations['total ex_gw_ports'] = num_ex_gw_ports
        configurations['total interfaces'] = num_interfaces
        configurations['total floating_ips'] = num_floating_ips
        configurations['hosting_devices'] = routers_per_hd
        configurations['non_responding_hosting_devices'] = non_responding
        return configurations

    # Routing service helper internal methods

    def _cleanup_invalid_cfg(self, routers):

        # dict with hd id as key and associated routers list as val
        hd_routermapping = collections.defaultdict(list)
        for router in routers:
            hd_routermapping[router['hosting_device']['id']].append(router)

        # call cfg cleanup specific to device type from its driver
        for hd_id, routers in six.iteritems(hd_routermapping):
            temp_res = {"id": hd_id,
                        "hosting_device": routers[0]['hosting_device'],
                        "router_type": routers[0]['router_type']}
            driver = self.driver_manager.set_driver(temp_res)

            driver.cleanup_invalid_cfg(
                routers[0]['hosting_device'], routers)

    def _fetch_router_info(self, router_ids=None, device_ids=None,
                           all_routers=False):
        """Fetch router dict from the routing plugin.

        :param router_ids: List of router_ids of routers to fetch
        :param device_ids: List of device_ids whose routers to fetch
        :param all_routers:  If True fetch all the routers for this agent.
        :return: List of router dicts of format:
                 [ {router_dict1}, {router_dict2},.....]
        """
        try:
            if all_routers:
                return self.plugin_rpc.get_routers(self.context)
            if router_ids:
                return self.plugin_rpc.get_routers(self.context,
                                                   router_ids=router_ids)
            if device_ids:
                return self.plugin_rpc.get_routers(self.context,
                                                   hd_ids=device_ids)
        except oslo_messaging.MessagingException:
            LOG.exception(_LE("RPC Error in fetching routers from plugin"))
            self.fullsync = True

    def _handle_sync_devices(self, routers):
        """
        Handles routers during a device_sync.

        This method performs post-processing on routers fetched from the
        routing plugin during a device sync.  Routers are first fetched
        from the plugin based on the list of device_ids.  Since fetched
        routers take precedence over pending work, matching router-ids
        buffered in update_routers and removed_routers are discarded.
        The existing router cache is also cleared in order to properly
        trigger updates and deletes.  Lastly, invalid configuration in
        the underlying hosting-device is deleted via _cleanup_invalid_cfg.

        Modifies updated_routers, removed_routers, and sync_devices
        attributes

        :param routers: working list of routers as populated in
                        process_services
        """
        sync_devices_list = list(self.sync_devices)
        LOG.debug("Fetching routers on:%s", sync_devices_list)
        fetched_routers = self._fetch_router_info(device_ids=sync_devices_list)

        if fetched_routers:
            LOG.debug("[sync_devices] Fetched routers :%s",
                      pp.pformat(fetched_routers))

            # clear router_config cache
            for router_dict in fetched_routers:
                self.updated_routers.discard(router_dict['id'])
                self.removed_routers.discard(router_dict['id'])
                LOG.debug("[sync_devices] invoking "
                          "_router_removed(%s)",
                          router_dict['id'])
                self._router_removed(router_dict['id'],
                                     deconfigure=False)

            self._cleanup_invalid_cfg(fetched_routers)
            routers.extend(fetched_routers)
            self.sync_devices.clear()
            LOG.debug("[sync_devices] %s finished",
                      sync_devices_list)
        else:
            # If the initial attempt to sync a device
            # failed, retry again (by not clearing sync_devices)
            # Normal updated_routers processing is still allowed
            # to happen
            self.sync_devices_attempts += 1

            if (self.sync_devices_attempts >=
                cfg.CONF.cfg_agent.max_device_sync_attempts):

                LOG.debug("Max number [%d / %d ] of sync_devices "
                          "attempted.  No further retries will "
                          "be attempted." %
                          (self.sync_devices_attempts,
                           cfg.CONF.cfg_agent.max_device_sync_attempts))
                self.sync_devices.clear()
                self.sync_devices_attempts = 0
            else:
                LOG.debug("Fetched routers was blank for sync attempt "
                          "[%d / %d], will attempt resync of %s devices "
                          "again in the next iteration" %
                          (self.sync_devices_attempts,
                           cfg.CONF.cfg_agent.max_device_sync_attempts,
                           pp.pformat(self.sync_devices)))

    @staticmethod
    def _get_router_ids_from_removed_devices_info(removed_devices_info):
        """Extract router_ids from the removed devices info dict.

        :param removed_devices_info: Dict of removed devices and their
               associated resources.
        Format:
                {
                  'hosting_data': {'hd_id1': {'routers': [id1, id2, ...]},
                                   'hd_id2': {'routers': [id3, id4, ...]},
                                   ...
                                  },
                  'deconfigure': True/False
                }
        :return removed_router_ids: List of removed router ids
        """
        removed_router_ids = []
        for hd_id, resources in removed_devices_info['hosting_data'].items():
            removed_router_ids += resources.get('routers', [])
        return removed_router_ids

    @staticmethod
    def _sort_resources_per_hosting_device(resources):
        """This function will sort the resources on hosting device.

        The sorting on hosting device is done by looking up the
        `hosting_device` attribute of the resource, and its `id`.

        :param resources: a dict with key of resource name
        :return dict sorted on the hosting device of input resource. Format:
        hosting_devices = {
                            'hd_id1' : {'routers':[routers],
                                        'removed_routers':[routers], .... }
                            'hd_id2' : {'routers':[routers], .. }
                            .......
                            }
        """
        hosting_devices = {}
        for key in resources.keys():
            for r in resources.get(key) or []:
                if r.get('hosting_device') is None:
                    continue
                hd_id = r['hosting_device']['id']
                hosting_devices.setdefault(hd_id, {})
                hosting_devices[hd_id].setdefault(key, []).append(r)
        return hosting_devices

    def _adjust_router_list_for_global_router(self, routers):
        """
        Pushes 'Global' routers to the end of the router list, so that
        deleting default route occurs before deletion of external nw subintf
        """
        #ToDo(Hareesh): Simplify if possible
        for r in routers:
            if r[ROUTER_ROLE_ATTR] == c_constants.ROUTER_ROLE_GLOBAL:
                LOG.debug("Global router:%s found. Moved to the end of list "
                          "for processing", r['id'])
                routers.remove(r)
                routers.append(r)

    def _process_routers(self, routers, removed_routers,
                         device_id=None, all_routers=False):
        """Process the set of routers.

        Iterating on the set of routers received and comparing it with the
        set of routers already in the routing service helper, new routers
        which are added are identified. Before processing check the
        reachability (via ping) of hosting device where the router is hosted.
        If device is not reachable it is backlogged.

        For routers which are only updated, call `_process_router()` on them.

        When all_routers is set to True (because of a full sync),
        this will result in the detection and deletion of routers which
        have been removed.

        Whether the router can only be assigned to a particular hosting device
        is decided and enforced by the plugin. No checks are done here.

        :param routers: The set of routers to be processed
        :param removed_routers: the set of routers which where removed
        :param device_id: Id of the hosting device
        :param all_routers: Flag for specifying a partial list of routers
        :return: None
        """
        try:
            if all_routers:
                prev_router_ids = set(self.router_info)
            else:
                prev_router_ids = set(self.router_info) & set(
                    [router['id'] for router in routers])
            cur_router_ids = set()
            deleted_routerids_list = []

            for r in routers:
                if not r['admin_state_up']:
                        continue
                cur_router_ids.add(r['id'])

            # identify list of routers(ids) that no longer exist
            for router_id in prev_router_ids - cur_router_ids:
                deleted_routerids_list.append(router_id)
            if removed_routers:
                self._adjust_router_list_for_global_router(removed_routers)
                for router in removed_routers:
                    deleted_routerids_list.append(router['id'])

            self._adjust_router_list_for_global_router(routers)
            # First process create/updated routers
            for r in routers:
                LOG.debug("Processing router[id:%(id)s, role:%(role)s]",
                          {'id': r['id'], 'role': r[ROUTER_ROLE_ATTR]})
                if r['id'] in deleted_routerids_list:
                    continue
                if r['status'] == c_constants.ROUTER_INFO_INCOMPLETE:
                    # The plugin could not fill in all the info due to
                    # timing and db settling down. So put this router
                    # back in updated_routers, we will pull again on the
                    # sync time.
                    LOG.debug("Router: %(id)s INFO_INCOMPLETE",
                              {'id': r['id']})
                    self.updated_routers.add(r['id'])
                    continue
                try:
                    if not r['admin_state_up']:
                        continue
                    cur_router_ids.add(r['id'])
                    hd = r['hosting_device']
                    if not self._dev_status.is_hosting_device_reachable(hd):
                        LOG.info(_LI("Router: %(id)s is on an unreachable "
                                     "hosting device. "), {'id': r['id']})
                        continue
                    if r['id'] not in self.router_info:
                        self._router_added(r['id'], r)
                    ri = self.router_info[r['id']]
                    ri.router = r
                    self._process_router(ri)
                except ncc_errors.SessionCloseError as e:
                    LOG.exception(
                        _LE("ncclient Unexpected session close %s"), e)
                    if not self._dev_status.is_hosting_device_reachable(
                        r['hosting_device']):
                        LOG.debug("Lost connectivity to Hosting Device %s" %
                                  r['hosting_device']['id'])
                        # Will rely on heartbeat to detect hd state
                        # and schedule resync when hd comes back
                    else:
                        # retry the router update on the next pass
                        self.updated_routers.add(r['id'])
                        LOG.debug("RETRY_RTR_UPDATE %s" % (r['id']))

                    continue
                except KeyError as e:
                    LOG.exception(_LE("Key Error, missing key: %s"), e)
                    self.updated_routers.add(r['id'])
                    continue
                except cfg_exceptions.DriverException as e:
                    LOG.exception(_LE("Driver Exception on router:%(id)s. "
                                      "Error is %(e)s"), {'id': r['id'],
                                                          'e': e})
                    self.updated_routers.update([r['id']])
                    continue
                LOG.debug("Done processing router[id:%(id)s, role:%(role)s]",
                          {'id': r['id'], 'role': r[ROUTER_ROLE_ATTR]})
            # Finally process removed routers
            for router_id in deleted_routerids_list:
                LOG.debug("Processing deleted router:%s", router_id)
                self._router_removed(router_id)
        except Exception:
            LOG.exception(_LE("Exception in processing routers on device:%s"),
                          device_id)
            self.sync_devices.add(device_id)

    def _send_update_port_statuses(self, port_ids, status):
        """Sends update notifications to set the operational status of the
        list of router ports provided. To make each notification doesn't exceed
        the RPC length, each message contains a maximum of MAX_PORTS_IN_BATCH
        port ids.

        :param port_ids: List of ports to update the status
        :param status: operational status to update
                       (ex: l3_constants.PORT_STATUS_ACTIVE)
        """
        if not port_ids:
            return

        MAX_PORTS_IN_BATCH = 50
        list_chunks_ports = [port_ids[i:i + MAX_PORTS_IN_BATCH]
            for i in six.moves.range(0, len(port_ids), MAX_PORTS_IN_BATCH)]
        for chunk_ports in list_chunks_ports:
            self.plugin_rpc.send_update_port_statuses(self.context,
                                                      chunk_ports, status)

    def _get_internal_port_changes(self, ri, internal_ports):
        existing_port_ids = set([p['id'] for p in ri.internal_ports])
        current_port_ids = set([p['id'] for p in internal_ports
                                if p['admin_state_up']])
        new_ports = [p for p in internal_ports
                     if
                     p['id'] in (current_port_ids - existing_port_ids)]
        old_ports = [p for p in ri.internal_ports
                     if p['id'] not in current_port_ids]

        new_port_ids = [p['id'] for p in new_ports]
        old_port_ids = [p['id'] for p in old_ports]
        LOG.debug("++ new_port_ids = %s" % (pp.pformat(new_port_ids)))
        LOG.debug("++ old_port_ids = %s" % (pp.pformat(old_port_ids)))

        return new_ports, old_ports

    def _enable_disable_ports(self, ri, ex_gw_port, internal_ports):
        if not ri.router['admin_state_up']:
            self._disable_router_interface(ri)
        else:
            if ex_gw_port:
                if not ex_gw_port['admin_state_up']:
                    self._disable_router_interface(ri, ex_gw_port)
                else:
                    self._enable_router_interface(ri, ex_gw_port)
            for port in internal_ports:
                if not port['admin_state_up']:
                    self._disable_router_interface(ri, port)
                else:
                    self._enable_router_interface(ri, port)

    def _process_new_ports(self, ri, new_ports, ex_gw_port, list_port_ids_up):
        for p in new_ports:
            self._set_subnet_info(p)
            self._internal_network_added(ri, p, ex_gw_port)
            ri.internal_ports.append(p)
            list_port_ids_up.append(p['id'])

    def _process_old_ports(self, ri, old_ports, ex_gw_port):
        for p in old_ports:
            self._internal_network_removed(ri, p, ri.ex_gw_port)
            ri.internal_ports.remove(p)

    def _process_gateway_set(self, ri, ex_gw_port, list_port_ids_up):
        self._set_subnet_info(ex_gw_port)
        self._external_gateway_added(ri, ex_gw_port)
        list_port_ids_up.append(ex_gw_port['id'])

    def _process_gateway_cleared(self, ri, ex_gw_port):
        self._external_gateway_removed(ri, ex_gw_port)

    def _add_rid_to_vrf_list(self, ri):
        # not needed in base service helper
        pass

    def _remove_rid_from_vrf_list(self, ri):
        # not needed in base service helper
        pass

    def _process_router(self, ri):
        """Process a router, apply latest configuration and update router_info.

        Get the router dict from  RouterInfo and proceed to detect changes
        from the last known state. When new ports or deleted ports are
        detected, `internal_network_added()` or `internal_networks_removed()`
        are called accordingly. Similarly changes in ex_gw_port causes
         `external_gateway_added()` or `external_gateway_removed()` calls.
        Next, floating_ips and routes are processed. Also, latest state is
        stored in ri.internal_ports and ri.ex_gw_port for future comparisons.

        :param ri : RouterInfo object of the router being processed.
        :return:None
        :raises: networking_cisco.plugins.cisco.cfg_agent.cfg_exceptions.
        DriverException if the configuration operation fails.
        """
        try:
            ex_gw_port = ri.router.get('gw_port')
            ri.ha_info = ri.router.get('ha_info', None)
            gateway_set = ex_gw_port and not ri.ex_gw_port
            gateway_cleared = not ex_gw_port and ri.ex_gw_port
            internal_ports = ri.router.get(l3_constants.INTERFACE_KEY, [])
            # Once the gateway is set, then we know which VRF
            # this router belongs to. Keep track of it in our
            # lists of routers, organized as a dictionary by
            # VRF name
            if gateway_set:
                self._add_rid_to_vrf_list(ri)

            new_ports, old_ports = self._get_internal_port_changes(
                ri, internal_ports)

            list_port_ids_up = []

            self._process_new_ports(ri, new_ports,
                                    ex_gw_port, list_port_ids_up)

            self._process_old_ports(ri, old_ports, ex_gw_port)

            if gateway_set:
                self._process_gateway_set(ri, ex_gw_port,
                                          list_port_ids_up)
            elif gateway_cleared:
                self._process_gateway_cleared(ri, ri.ex_gw_port)

            self._send_update_port_statuses(list_port_ids_up,
                                            l3_constants.PORT_STATUS_ACTIVE)
            if ex_gw_port:
                self._process_router_floating_ips(ri, ex_gw_port)

            if ri.router[ROUTER_ROLE_ATTR] not in \
                    [c_constants.ROUTER_ROLE_GLOBAL,
                     c_constants.ROUTER_ROLE_LOGICAL_GLOBAL]:
                self._enable_disable_ports(ri, ex_gw_port, internal_ports)

                if gateway_cleared:
                    # Remove this router from the list of routers by VRF
                    self._remove_rid_from_vrf_list(ri)

            ri.ex_gw_port = ex_gw_port
            self._routes_updated(ri)
        except cfg_exceptions.HAParamsMissingException as e:
            self.updated_routers.update([ri.router_id])
            LOG.warning(e)
        except cfg_exceptions.DriverException as e:
            with excutils.save_and_reraise_exception():
                self.updated_routers.update([ri.router_id])
                LOG.error(e)

    def _process_router_floating_ips(self, ri, ex_gw_port):
        """Process a router's floating ips.

        Compare floatingips configured in device (i.e., those fips in
        the ri.floating_ips "cache") with the router's updated floating ips
        (in ri.router.floating_ips) and determine floating_ips which were
        added or removed. Notify driver of the change via
        `floating_ip_added()` or `floating_ip_removed()`. Also update plugin
        with status of fips.

        :param ri:  RouterInfo object of the router being processed.
        :param ex_gw_port: Port dict of the external gateway port.
        :return: None
        :raises: networking_cisco.plugins.cisco.cfg_agent.cfg_exceptions.
        DriverException if the configuration operation fails.
        """

        # fips that exist in neutron db (i.e., the desired "truth")
        current_fips = ri.router.get(l3_constants.FLOATINGIP_KEY, [])
        # ids of fips that exist in neutron db
        current_fip_ids = {fip['id'] for fip in current_fips}
        # ids of fips that are configured in device
        configured_fip_ids = {fip['id'] for fip in ri.floating_ips}

        id_to_current_fip_map = {}

        fips_to_add = []
        # iterate of fips that exist in neutron db
        for configured_fip in current_fips:
            if configured_fip['port_id']:
                # store to later check if this fip has been remapped
                id_to_current_fip_map[configured_fip['id']] = configured_fip
                if configured_fip['id'] not in configured_fip_ids:
                    # Ensure that we add only after remove, in case same
                    # fixed_ip is mapped to different floating_ip within
                    # the same loop cycle. If add occurs before first,
                    # cfg will fail because of existing entry with
                    # identical fixed_ip
                    fips_to_add.append(configured_fip)

        fip_ids_to_remove = configured_fip_ids - current_fip_ids
        LOG.debug("fip_ids_to_add: %s" % fips_to_add)
        LOG.debug("fip_ids_to_remove: %s" % fip_ids_to_remove)

        fips_to_remove = []
        fip_statuses = {}
        # iterate over fips that are configured in device
        for configured_fip in ri.floating_ips:
            if configured_fip['id'] in fip_ids_to_remove:
                fips_to_remove.append(configured_fip)
                self._floating_ip_removed(
                    ri, ri.ex_gw_port, configured_fip['floating_ip_address'],
                    configured_fip['fixed_ip_address'])
                fip_statuses[configured_fip['id']] = (
                    l3_constants.FLOATINGIP_STATUS_DOWN)
                LOG.debug("Add to fip_statuses DOWN id:%s fl_ip:%s fx_ip:%s",
                          configured_fip['id'],
                          configured_fip['floating_ip_address'],
                          configured_fip['fixed_ip_address'])
            else:
                # handle possibly required remapping of a fip
                # ip address that fip currently is configured for
                configured_fixed_ip = configured_fip['fixed_ip_address']
                new_fip = id_to_current_fip_map[configured_fip['id']]
                # ip address that fip should be configured for
                current_fixed_ip = new_fip['fixed_ip_address']
                if (current_fixed_ip and configured_fixed_ip and
                        current_fixed_ip != configured_fixed_ip):
                    floating_ip = configured_fip['floating_ip_address']
                    self._floating_ip_removed(ri, ri.ex_gw_port,
                                              floating_ip, configured_fixed_ip)
                    fip_statuses[configured_fip['id']] = (
                        l3_constants.FLOATINGIP_STATUS_DOWN)
                    fips_to_remove.append(configured_fip)
                    fips_to_add.append(new_fip)

        for configured_fip in fips_to_remove:
            # remove fip from "cache" of fips configured in device
            ri.floating_ips.remove(configured_fip)

        for configured_fip in fips_to_add:
            self._floating_ip_added(ri, ex_gw_port,
                                    configured_fip['floating_ip_address'],
                                    configured_fip['fixed_ip_address'])
            # add fip to "cache" of fips configured in device
            ri.floating_ips.append(configured_fip)
            fip_statuses[configured_fip['id']] = (
                l3_constants.FLOATINGIP_STATUS_ACTIVE)
            LOG.debug("Add to fip_statuses ACTIVE id:%s fl_ip:%s fx_ip:%s",
                      configured_fip['id'],
                      configured_fip['floating_ip_address'],
                      configured_fip['fixed_ip_address'])

        if fip_statuses:
            LOG.debug("Sending floatingip_statuses_update: %s", fip_statuses)
            self.plugin_rpc.update_floatingip_statuses(
                self.context, ri.router_id, fip_statuses)

    def _router_added(self, router_id, router):
        """Operations when a router is added.

        Create a new RouterInfo object for this router and add it to the
        service helpers router_info dictionary.  Then `router_added()` is
        called on the device driver.

        :param router_id: id of the router
        :param router: router dict
        :return: None
        """
        ri = RouterInfo(router_id, router)
        driver = self.driver_manager.set_driver(router)
        if router[ROUTER_ROLE_ATTR] in [
            c_constants.ROUTER_ROLE_GLOBAL,
            c_constants.ROUTER_ROLE_LOGICAL_GLOBAL]:
            # No need to create a vrf for Global or logical global routers
            LOG.debug("Skipping router_added device processing for %(id)s as "
                      "its role is %(role)s",
                      {'id': router_id, 'role': router[ROUTER_ROLE_ATTR]})
        else:
            driver.router_added(ri)
        self.router_info[router_id] = ri

    def _router_removed(self, router_id, deconfigure=True):
        """Operations when a router is removed.

        Get the RouterInfo object corresponding to the router in the service
        helpers's router_info dict. If deconfigure is set to True,
        remove this router's configuration from the hosting device.
        :param router_id: id of the router
        :param deconfigure: if True, the router's configuration is deleted from
        the hosting device.
        :return: None
        """
        ri = self.router_info.get(router_id)
        if ri is None:
            LOG.warning(_LW("Info for router %s was not found. "
                            "Skipping router removal"), router_id)
            return
        ri.router['gw_port'] = None
        ri.router[l3_constants.INTERFACE_KEY] = []
        ri.router[l3_constants.FLOATINGIP_KEY] = []
        try:
            hd = ri.router['hosting_device']
            # We proceed to removing the configuration from the device
            # only if (a) deconfigure is set to True (default)
            # (b) the router's hosting device is reachable.
            if (deconfigure and
                    self._dev_status.is_hosting_device_reachable(hd)):
                self._process_router(ri)
                driver = self.driver_manager.get_driver(router_id)
                driver.router_removed(ri)
                self.driver_manager.remove_driver(router_id)
            del self.router_info[router_id]
            self.removed_routers.discard(router_id)
        except cfg_exceptions.DriverException:
            LOG.warning(_LW("Router remove for router_id: %s was incomplete. "
                            "Adding the router to removed_routers list"),
                        router_id)
            self.removed_routers.add(router_id)
            # remove this router from updated_routers if it is there. It might
            # end up there too if exception was thrown earlier inside
            # `_process_router()`
            self.updated_routers.discard(router_id)
        except ncc_errors.SessionCloseError as e:
            LOG.exception(_LE("ncclient Unexpected session close %s"
                              " while attempting to remove router"), e)
            if not self._dev_status.is_hosting_device_reachable(hd):
                LOG.debug("Lost connectivity to Hosting Device %s" % hd['id'])
                # rely on heartbeat to detect HD state
                # and schedule resync when the device comes back
            else:
                # retry the router removal on the next pass
                self.removed_routers.add(router_id)
                LOG.debug("Interim connectivity lost to hosting device %s, "
                          "enqueuing router %s in removed_routers set" %
                          pp.pformat(hd), router_id)

    def _internal_network_added(self, ri, port, ex_gw_port):
        driver = self.driver_manager.get_driver(ri.id)
        driver.internal_network_added(ri, port)
        if ri.snat_enabled and ex_gw_port:
            driver.enable_internal_network_NAT(ri, port, ex_gw_port)

    def _internal_network_removed(self, ri, port, ex_gw_port):
        driver = self.driver_manager.get_driver(ri.id)
        driver.internal_network_removed(ri, port)
        if ri.snat_enabled and ex_gw_port:
            #ToDo(Hareesh): Check if the intfc_deleted attribute is needed
            driver.disable_internal_network_NAT(ri, port, ex_gw_port,
                                                itfc_deleted=True)

    def _external_gateway_added(self, ri, ex_gw_port):
        driver = self.driver_manager.get_driver(ri.id)
        driver.external_gateway_added(ri, ex_gw_port)
        if ri.snat_enabled and ri.internal_ports:
            for port in ri.internal_ports:
                driver.enable_internal_network_NAT(ri, port, ex_gw_port)

    def _external_gateway_removed(self, ri, ex_gw_port):
        driver = self.driver_manager.get_driver(ri.id)
        if ri.snat_enabled and ri.internal_ports:
            for port in ri.internal_ports:
                driver.disable_internal_network_NAT(ri, port, ex_gw_port)
        driver.external_gateway_removed(ri, ex_gw_port)

    def _floating_ip_added(self, ri, ex_gw_port, floating_ip, fixed_ip):
        driver = self.driver_manager.get_driver(ri.id)
        driver.floating_ip_added(ri, ex_gw_port, floating_ip, fixed_ip)

    def _floating_ip_removed(self, ri, ex_gw_port, floating_ip, fixed_ip):
        driver = self.driver_manager.get_driver(ri.id)
        driver.floating_ip_removed(ri, ex_gw_port, floating_ip, fixed_ip)

    def _enable_router_interface(self, ri, port):
        driver = self.driver_manager.get_driver(ri.id)
        driver.enable_router_interface(ri, port)

    def _disable_router_interface(self, ri, port=None):
        driver = self.driver_manager.get_driver(ri.id)
        driver.disable_router_interface(ri, port)

    def _routes_updated(self, ri):
        """Update the state of routes in the router.

        Compares the current routes with the (configured) existing routes
        and detect what was removed or added. Then configure the
        logical router in the hosting device accordingly.
        :param ri: RouterInfo corresponding to the router.
        :return: None
        :raises: networking_cisco.plugins.cisco.cfg_agent.cfg_exceptions.
        DriverException if the configuration operation fails.
        """
        new_routes = ri.router['routes']
        old_routes = ri.routes
        adds, removes = common_utils.diff_list_of_dict(old_routes,
                                                       new_routes)
        for route in adds:
            LOG.debug("Added route entry is '%s'", route)
            # remove replaced route from deleted route
            for del_route in removes:
                if route['destination'] == del_route['destination']:
                    removes.remove(del_route)
            driver = self.driver_manager.get_driver(ri.id)
            driver.routes_updated(ri, 'replace', route)

        for route in removes:
            LOG.debug("Removed route entry is '%s'", route)
            driver = self.driver_manager.get_driver(ri.id)
            driver.routes_updated(ri, 'delete', route)
        ri.routes = new_routes

    @staticmethod
    def _set_subnet_info(port):
        ips = port['fixed_ips']
        if not ips:
            raise Exception(_("Router port %s has no IP address") % port['id'])
        if len(ips) > 1:
            LOG.error(_LE("Ignoring multiple IPs on router port %s"),
                      port['id'])

        port_subnets = port['subnets']

        num_subnets_on_port = len(port_subnets)
        LOG.debug("number of subnets associated with port = %d" %
                  num_subnets_on_port)
        # TODO(What should we do if multiple subnets are somehow associated)
        # TODO(with a port?)
        if (num_subnets_on_port > 1):
            LOG.error(_LE("Ignoring port with multiple subnets associated"))
            raise Exception(("Multiple subnets configured on port.  %s") %
                            pp.pformat(port_subnets))
        else:
            subnet = port_subnets[0]
            prefixlen = netaddr.IPNetwork(subnet['cidr']).prefixlen
            port['ip_cidr'] = "%s/%s" % (ips[0]['ip_address'], prefixlen)
