# Copyright (c) 2013-2017 Cisco Systems, Inc.
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
ML2 Mechanism Driver for Cisco Nexus platforms.
"""

import eventlet
import os
import threading
import time

from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_utils import excutils

from networking_cisco import backwards_compatibility as bc
from networking_cisco.backwards_compatibility import constants as p_const
from networking_cisco.backwards_compatibility import ml2_api as api
from networking_cisco.backwards_compatibility import runtime_utils

from networking_cisco.ml2_drivers.nexus import (
    config as conf)
from networking_cisco.ml2_drivers.nexus import (
    constants as const)
from networking_cisco.ml2_drivers.nexus import (
    exceptions as excep)
from networking_cisco.ml2_drivers.nexus import (
    nexus_db_v2 as nxos_db)
from networking_cisco.ml2_drivers.nexus import (
    nexus_helpers as nexus_help)
from networking_cisco.ml2_drivers.nexus import trunk
from networking_cisco.services.trunk import nexus_trunk


LOG = logging.getLogger(__name__)

HOST_NOT_FOUND = "Host %s not defined in switch configuration section."

# Delay the start of the monitor thread to avoid problems with Neutron server
# process forking. One problem observed was ncclient RPC sync close_session
# call hanging during initial _monitor_thread() processing to replay existing
# database.
DELAY_MONITOR_THREAD = 30

CONF = cfg.CONF


class CiscoNexusCfgMonitor(object):
    """Replay config on communication failure between OpenStack to Nexus."""

    def __init__(self, driver, mdriver):
        self._driver = driver
        self._mdriver = mdriver
        switch_connections = self._mdriver.get_switch_ips()
        for switch_ip in switch_connections:
            self._mdriver.set_switch_ip_and_active_state(
                switch_ip, const.SWITCH_INACTIVE)
            # this initialization occurs later for replay case
            if not self._mdriver.is_replay_enabled():
                try:
                    self._initialize_trunk_interfaces_to_none(
                        switch_ip, replay=False)
                except Exception:
                    pass

    def _configure_nexus_type(self, switch_ip, nexus_type):
        if nexus_type not in (const.NEXUS_3K, const.NEXUS_5K,
            const.NEXUS_7K, const.NEXUS_9K):
            LOG.debug("Received invalid Nexus type %(nexus_type)d "
                "for switch ip %(switch_ip)s",
                {'nexus_type': nexus_type, 'switch_ip': switch_ip})
            return
        if (self._mdriver.get_switch_nexus_type(switch_ip) ==
           const.NEXUS_TYPE_INVALID):
            self._mdriver.set_switch_nexus_type(switch_ip, nexus_type)

    def _initialize_trunk_interfaces_to_none(self, switch_ip, replay=True):
        """Initialize all nexus interfaces to trunk allowed none."""

        try:
            # The following determines if the switch interfaces are
            # in place.  If so, make sure they have a basic trunk
            # configuration applied to none.
            switch_ifs = self._mdriver._get_switch_interfaces(
                switch_ip, cfg_only=(False if replay else True))
            if not switch_ifs:
                LOG.debug("Skipping switch %s which has no configured "
                          "interfaces",
                          switch_ip)
                return
            self._driver.initialize_all_switch_interfaces(
                switch_ifs, switch_ip)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.warning("Unable to initialize interfaces to "
                            "switch %(switch_ip)s",
                            {'switch_ip': switch_ip})
                self._mdriver.register_switch_as_inactive(switch_ip,
                    'replay init_interface')

        if self._mdriver.is_replay_enabled():
            return

    def replay_config(self, switch_ip):
        """Sends pending config data in OpenStack to Nexus."""
        LOG.debug("Replaying config for switch ip %(switch_ip)s",
                  {'switch_ip': switch_ip})

        # Before replaying all config, initialize trunk interfaces
        # to none as required.  If this fails, the switch may not
        # be up all the way.  Quit and retry later.
        try:
            self._initialize_trunk_interfaces_to_none(switch_ip)
        except Exception:
            return

        nve_bindings = nxos_db.get_nve_switch_bindings(switch_ip)

        # If configured to set global VXLAN values and
        # there exists VXLAN data base entries, then configure
        # the "interface nve" entry on the switch.
        if (len(nve_bindings) > 0 and
           cfg.CONF.ml2_cisco.vxlan_global_config):
            LOG.debug("Nexus: Replay NVE Interface")
            loopback = self._mdriver.get_nve_loopback(switch_ip)
            self._driver.enable_vxlan_feature(switch_ip,
                const.NVE_INT_NUM, loopback)

        for x in nve_bindings:
            try:
                self._driver.create_nve_member(switch_ip,
                    const.NVE_INT_NUM, x.vni, x.mcast_group)
            except Exception as e:
                LOG.error("Failed to configure nve_member for "
                    "switch %(switch_ip)s, vni %(vni)s"
                    "Reason:%(reason)s ",
                    {'switch_ip': switch_ip, 'vni': x.vni,
                     'reason': e})
                self._mdriver.register_switch_as_inactive(switch_ip,
                    'replay create_nve_member')
                return

        try:
            port_bindings = nxos_db.get_nexusport_switch_bindings(switch_ip)
        except excep.NexusPortBindingNotFound:
            LOG.warning("No port entries found for switch ip "
                        "%(switch_ip)s during replay.",
                        {'switch_ip': switch_ip})
            return

        try:
            self._mdriver.configure_switch_entries(
                switch_ip, port_bindings)
        except Exception as e:
                LOG.error("Unexpected exception while replaying "
                    "entries for switch %(switch_ip)s, Reason:%(reason)s ",
                    {'switch_ip': switch_ip, 'reason': e})
                self._mdriver.register_switch_as_inactive(switch_ip,
                    'replay switch_entries')

    def check_connections(self):
        """Check connection between OpenStack to Nexus device."""
        switch_connections = self._mdriver.get_all_switch_ips()

        for switch_ip in switch_connections:
            state = self._mdriver.get_switch_ip_and_active_state(switch_ip)
            config_failure = self._mdriver.get_switch_replay_failure(
                const.FAIL_CONFIG, switch_ip)
            contact_failure = self._mdriver.get_switch_replay_failure(
                const.FAIL_CONTACT, switch_ip)
            LOG.debug("check_connections() thread %(thid)d, switch "
                      "%(switch_ip)s state %(state)s "
                      "contact_failure %(contact_failure)d "
                      "config_failure %(config_failure)d ",
                      {'thid': threading.current_thread().ident,
                       'switch_ip': switch_ip, 'state': state,
                       'contact_failure': contact_failure,
                       'config_failure': config_failure})
            try:
                # Send a simple get nexus type to determine if
                # the switch is up
                nexus_type = self._driver.get_nexus_type(switch_ip)
            except Exception:
                if state != const.SWITCH_INACTIVE:
                    LOG.error("Lost connection to switch ip "
                        "%(switch_ip)s", {'switch_ip': switch_ip})
                    self._mdriver.set_switch_ip_and_active_state(
                        switch_ip, const.SWITCH_INACTIVE)
                else:
                    self._mdriver.incr_switch_replay_failure(
                        const.FAIL_CONTACT, switch_ip)
            else:
                if state == const.SWITCH_RESTORE_S2:
                    try:
                        self._mdriver.configure_next_batch_of_vlans(switch_ip)
                    except Exception as e:
                        LOG.error("Unexpected exception while replaying "
                                  "entries for switch %(switch_ip)s, "
                                  "Reason:%(reason)s ",
                                  {'switch_ip': switch_ip, 'reason': e})
                        self._mdriver.register_switch_as_inactive(
                            switch_ip, 'replay next_vlan_batch')
                    continue

                if state == const.SWITCH_INACTIVE:
                    self._configure_nexus_type(switch_ip, nexus_type)
                    LOG.info("Re-established connection to switch "
                        "ip %(switch_ip)s",
                        {'switch_ip': switch_ip})

                    self._mdriver.set_switch_ip_and_active_state(
                        switch_ip, const.SWITCH_RESTORE_S1)
                    self.replay_config(switch_ip)

                    # If replay failed, it stops trying to configure db entries
                    # and sets switch state to inactive so this caller knows
                    # it failed.  If it did fail, we increment the
                    # retry counter else reset it to 0.
                    if self._mdriver.get_switch_ip_and_active_state(
                        switch_ip) == const.SWITCH_INACTIVE:
                        self._mdriver.incr_switch_replay_failure(
                            const.FAIL_CONFIG, switch_ip)
                        LOG.warning("Replay config failed for "
                                    "ip %(switch_ip)s",
                                    {'switch_ip': switch_ip})
                    else:
                        self._mdriver.reset_switch_replay_failure(
                            const.FAIL_CONFIG, switch_ip)
                        self._mdriver.reset_switch_replay_failure(
                            const.FAIL_CONTACT, switch_ip)
                        LOG.info("Replay config successful for "
                            "ip %(switch_ip)s",
                            {'switch_ip': switch_ip})


class CiscoNexusMechanismDriver(api.MechanismDriver):

    """Cisco Nexus ML2 Mechanism Driver."""

    def _load_nexus_cfg_driver(self):
        """Load Nexus Config driver.
        :raises SystemExit of 1 if driver cannot be loaded
        """

        try:
            loaded_class = runtime_utils.load_class_by_alias_or_classname(
                'networking_cisco.ml2.nexus_driver', 'restapi')
            return loaded_class(CONF.ml2_cisco.nexus_switches)
        except ImportError:
            LOG.error("Error loading Nexus Config driver 'restapi'")
            raise SystemExit(1)

    def _validate_vpc_alloc_config(self, switch_ip):
        # Validates content of user supplied vpc-pool config.

        # :param switch_ip: ip address of a given switch
        # :returns: list of user configured vpcs for pool.
        #           empty list returned on error.
        #           return error indicator

        value = CONF.ml2_cisco.nexus_switches[switch_ip][const.VPCPOOL] or ''
        new_list = set()
        vpc_range = value.split(',')
        # test != '' handles when value is '' or consecutive ',,' exist
        vpc_range = [test.strip() for test in vpc_range if test != '']
        if not vpc_range:
            return [], False
        for vpcid in vpc_range:
            try:
                minmax = [int(r.strip()) for r in vpcid.split('-')]
            except Exception:
                LOG.error("Unexpected value %(bad)s configured "
                          "in vpc-pool config %(all)s for switch "
                          "%(switchip)s. Ignoring entire config.",
                          {'bad': vpcid, 'all': value,
                          'switchip': switch_ip})
                return [], True

            if len(minmax) > 2:
                LOG.error("Incorrectly formatted range %(bad)s "
                          "config in vpc-pool config %(all)s for switch "
                          "%(switchip)s. Ignoring entire config.",
                          {'bad': vpcid, 'all': value,
                          'switchip': switch_ip})
                return [], True

            # In case user provided 500-400, lets make it 400-500.
            minmax.sort()
            start = minmax[0]
            end = minmax[0] + 1 if len(minmax) == 1 else minmax[1] + 1
            if (start >= const.MINVPC and start <= const.MAXVPC and
                end - 1 >= const.MINVPC and end - 1 <= const.MAXVPC):
                new_list.update(range(start, end))
            else:
                LOG.error("Invalid Port-channel range value %(bad)s "
                          "received in vpc-pool config %(all)s for "
                          "switch %(switchip)s. Ignoring entire config.",
                          {'bad': vpcid, 'all': value,
                          'switchip': switch_ip})
                return [], True

        return list(new_list), False

    def _compare_vpcpool_lists(self, old_list, new_list):
        # Compare existing list and new config list and
        # return list of those requiring removal and those
        # requiring addition.

        rm_list = []
        add_list = list(new_list)  # make copy of new_list
        for old in old_list:
            if old.vpc_id in add_list:
                add_list.remove(old.vpc_id)
            # else not in add_list only remove those that
            # are not active
            elif not old.active:
                rm_list.append(old.vpc_id)

        return rm_list, add_list

    def _get_vpcpool_changes_needed(self, switch_ip):
        # Determine which vpcs need addition and removal
        # from VPC data base.

        # Get list of vpcs already configured
        old_list = nxos_db.get_all_switch_vpc_allocs(switch_ip)

        # Get list of configured vpcs desired
        new_list, error = self._validate_vpc_alloc_config(switch_ip)

        # on error, Do nothing. Leave existing db intact.
        if error:
            return [], []

        # Compare lists and generate list for those to be added/removed.
        return self._compare_vpcpool_lists(old_list, new_list)

    def _initialize_vpc_alloc_pools(self):
        # When there is a user vpc_pool configuration,
        # determine what needs to be added/removed
        # vpc data base and apply those changes.

        for switch_ip, attrs in CONF.ml2_cisco.nexus_switches.items():
            rm_list, add_list = self._get_vpcpool_changes_needed(switch_ip)
            nxos_db.init_vpc_entries(switch_ip, add_list)
            for rm in rm_list:
                nxos_db.delete_vpcid_for_switch(rm, switch_ip)

    def _initialize_host_port_mappings(self):
        nxos_db.remove_all_static_host_mappings()
        for switch_ip, attrs in CONF.ml2_cisco.nexus_switches.items():
            for host, ports in attrs.host_port_mapping.items():
                for if_id in ports.split(','):
                    if_type, port = (nexus_help.split_interface_name(if_id))
                    interface = nexus_help.format_interface_name(if_type, port)
                    nxos_db.add_host_mapping(host, switch_ip,
                                             interface, 0, True)
            for host, intfs in attrs.host_ports_mapping.items():
                for if_id in intfs:
                    if_type, port = nexus_help.split_interface_name(if_id)
                    interface = nexus_help.format_interface_name(if_type, port)
                    nxos_db.add_host_mapping(host, switch_ip, interface, 0,
                                             True)

    def initialize(self):
        # Load host port mappings from the config file
        self._initialize_host_port_mappings()

        # Save dynamic switch information
        self._switch_state = {}

        self.driver = self._load_nexus_cfg_driver()
        self._initialize_vpc_alloc_pools()

        # This method is only called once regardless of number of
        # api/rpc workers defined.
        self._ppid = os.getpid()

        self.monitor = CiscoNexusCfgMonitor(self.driver, self)
        self.timer = None
        self.monitor_timeout = conf.cfg.CONF.ml2_cisco.switch_heartbeat_time
        self.monitor_lock = threading.Lock()
        self.context = bc.get_context()
        self.trunk = trunk.NexusMDTrunkHandler()
        nexus_trunk.NexusTrunkDriver.create()
        LOG.info("CiscoNexusMechanismDriver: initialize() called "
                 "pid %(pid)d thid %(tid)d", {'pid': self._ppid,
                 'tid': threading.current_thread().ident})
        # Start the monitor thread
        if self.is_replay_enabled():
            eventlet.spawn_after(DELAY_MONITOR_THREAD, self._monitor_thread)

    def is_replay_enabled(self):
        return conf.cfg.CONF.ml2_cisco.switch_heartbeat_time > 0

    def set_switch_ip_and_active_state(self, switch_ip, state):
        if not self.is_replay_enabled():
            return
        try:
            nxos_db.get_reserved_switch_binding(
                switch_ip)
        except excep.NexusPortBindingNotFound:
            nxos_db.add_reserved_switch_binding(
                switch_ip, state)

        # overload port_id to contain switch state
        nxos_db.update_reserved_switch_binding(
            switch_ip, state)

    def get_switch_ip_and_active_state(self, switch_ip):
        if not self.is_replay_enabled():
            return const.SWITCH_ACTIVE

        binding = nxos_db.get_reserved_switch_binding(
                      switch_ip)
        if len(binding) == 1:
            return binding[0].port_id
        else:
            return const.SWITCH_INACTIVE

    def _switch_defined(self, switch_ip):
        """Verify this ip address is defined (for Nexus)."""
        switch = cfg.CONF.ml2_cisco.nexus_switches.get(switch_ip)
        if switch and switch.username and switch.password:
            return True
        else:
            return False

    def register_switch_as_inactive(self, switch_ip, func_name):
        self.set_switch_ip_and_active_state(switch_ip, const.SWITCH_INACTIVE)
        LOG.exception(
            "Nexus Driver cisco_nexus failed in %(func_name)s",
            {'func_name': func_name})

    def is_switch_active(self, switch_ip):
        if self.is_replay_enabled():
            switch_state = self.get_switch_ip_and_active_state(switch_ip)
            active_states = [const.SWITCH_ACTIVE, const.SWITCH_RESTORE_S2]
            return switch_state in active_states
        else:
            return True

    def set_switch_nexus_type(self, switch_ip, type):
        self._switch_state[switch_ip, '_nexus_type'] = type

    def get_switch_nexus_type(self, switch_ip):
        if (switch_ip, '_nexus_type') in self._switch_state:
            return self._switch_state[switch_ip, '_nexus_type']
        else:
            return -1

    def _save_switch_vlan_range(self, switch_ip, vlan_range):
        self._switch_state[switch_ip, '_vlan_range'] = vlan_range

    def _get_switch_vlan_range(self, switch_ip):
        if (switch_ip, '_vlan_range') in self._switch_state:
            return self._switch_state[switch_ip, '_vlan_range']
        else:
            return []

    def _save_switch_vxlan_range(self, switch_ip, vxlan_range):
        self._switch_state[switch_ip, '_vxlan_range'] = vxlan_range

    def _get_switch_vxlan_range(self, switch_ip):
        if (switch_ip, '_vxlan_range') in self._switch_state:
            return self._switch_state[switch_ip, '_vxlan_range']
        else:
            return []

    def _pop_vlan_range(self, switch_ip, size):
        """Extract a specific number of vlans from storage.

        Purpose: Can only send a limited number of vlans
        to Nexus at a time.

        Sample Use Cases:
        1) vlan_range is a list of vlans.  If there is a
        list 1000, 1001, 1002, thru 2000 and size is 6,
        then the result is '1000-1005' and 1006 thru 2000
        is pushed back into storage.
        2) if the list is 1000, 1003, 1004, 1006 thru 2000
        and size is 6, then the result is
        '1000, 1003-1004, 1006-1008' and 1009 thru 2000
        is pushed back into storage for next time.
        """
        vlan_range = self._get_switch_vlan_range(switch_ip)
        sized_range = ''
        fr = 0
        to = 0
        # if vlan_range not empty and haven't met requested size
        while size > 0 and vlan_range:
            vlan_id, vni = vlan_range.pop(0)
            size -= 1
            if fr == 0 and to == 0:
                fr = vlan_id
                to = vlan_id
            else:
                diff = vlan_id - to
                if diff == 1:
                    to = vlan_id
                else:
                    if fr == to:
                        sized_range += str(to) + ','
                    else:
                        sized_range += str(fr) + '-'
                        sized_range += str(to) + ','
                    fr = vlan_id
                    to = vlan_id
        if fr != 0:
            if fr == to:
                sized_range += str(to)
            else:
                sized_range += str(fr) + '-'
                sized_range += str(to)
            self._save_switch_vlan_range(switch_ip, vlan_range)

        return sized_range

    def _valid_replay_key(self, fail_key, switch_ip):
        if (switch_ip, const.REPLAY_FAILURES) not in self._switch_state:
            self._switch_state[switch_ip, const.REPLAY_FAILURES] = {
                const.FAIL_CONTACT: 0,
                const.FAIL_CONFIG: 0}

        return fail_key in self._switch_state[switch_ip,
                                              const.REPLAY_FAILURES]

    def reset_switch_replay_failure(self, fail_key, switch_ip):
        if self._valid_replay_key(fail_key, switch_ip):
            self._switch_state[switch_ip, const.REPLAY_FAILURES][fail_key] = 0

    def incr_switch_replay_failure(self, fail_key, switch_ip):
        if self._valid_replay_key(fail_key, switch_ip):
            self._switch_state[switch_ip, const.REPLAY_FAILURES][fail_key] += 1

    def get_switch_replay_failure(self, fail_key, switch_ip):
        if self._valid_replay_key(fail_key, switch_ip):
            return self._switch_state[switch_ip,
                   const.REPLAY_FAILURES][fail_key]
        else:
            return 0

    def get_all_switch_ips(self):
        """Using reserved switch binding get all switch ips."""

        switch_connections = []
        try:
            bindings = nxos_db.get_reserved_switch_binding()
        except excep.NexusPortBindingNotFound:
            LOG.error("No switch bindings in the port data base")
            bindings = []
        for switch in bindings:
            switch_connections.append(switch.switch_ip)

        return switch_connections

    def _get_port_uuid(self, port):
        # Trunk subport's don't have the 'device_id' set so use port 'id'
        # as the UUID.
        uuid_key = 'id' if self.trunk.is_trunk_subport(port) else 'device_id'
        return port.get(uuid_key)

    def _valid_network_segment(self, segment):
        return (cfg.CONF.ml2_cisco.managed_physical_network is None or
                cfg.CONF.ml2_cisco.managed_physical_network ==
                segment[api.PHYSICAL_NETWORK])

    def _is_supported_deviceowner(self, port):
        return (port['device_owner'].startswith('compute') or
                port['device_owner'].startswith('baremetal') or
                port['device_owner'].startswith('manila') or
                port['device_owner'] in [
                    bc.trunk_consts.TRUNK_SUBPORT_OWNER,
                    bc.constants.DEVICE_OWNER_DHCP,
                    bc.constants.DEVICE_OWNER_ROUTER_INTF,
                    bc.constants.DEVICE_OWNER_ROUTER_GW,
                    bc.constants.DEVICE_OWNER_ROUTER_HA_INTF])

    def _is_status_down(self, port):
        # ACTIVE, BUILD status indicates a port is up or coming up.
        # DOWN, ERROR status indicates the port is down.
        return (port['status'] in [bc.constants.PORT_STATUS_DOWN,
                                   bc.constants.PORT_STATUS_ERROR])

    def _get_baremetal_switch_info(self, link_info):
        """Get switch_info dictionary from context."""

        try:
            switch_info = link_info['switch_info']
            if not isinstance(switch_info, dict):
                switch_info = jsonutils.loads(switch_info)
        except Exception as e:
            LOG.error("switch_info can't be decoded: %(exp)s",
                      {"exp": e})
            switch_info = {}

        return switch_info

    def _baremetal_set_binding(self, context, all_link_info=None):
        selected = False
        for segment in context.segments_to_bind:
            if (segment[api.NETWORK_TYPE] == p_const.TYPE_VLAN and
                segment[api.SEGMENTATION_ID]):
                context.set_binding(
                    segment[api.ID],
                    bc.portbindings.VIF_TYPE_OTHER,
                    {},
                    status=bc.constants.PORT_STATUS_ACTIVE)
                LOG.debug(
                    "Baremetal binding selected: segment ID %(id)s, segment "
                    "%(seg)s, phys net %(physnet)s, and network type "
                    "%(nettype)s with %(count)d link_info",
                    {'id': segment[api.ID],
                     'seg': segment[api.SEGMENTATION_ID],
                     'physnet': segment[api.PHYSICAL_NETWORK],
                     'nettype': segment[api.NETWORK_TYPE],
                     'count': len(all_link_info) if all_link_info else 0})
                selected = True
                break

        return selected

    def _supported_baremetal_transaction(self, context):
        """Verify transaction is complete and for us."""

        port = context.current

        if self.trunk.is_trunk_subport_baremetal(port):
            return self._baremetal_set_binding(context)

        if not nexus_help.is_baremetal(port):
            return False

        if bc.portbindings.PROFILE not in port:
            return False

        profile = port[bc.portbindings.PROFILE]

        if 'local_link_information' not in profile:
            return False

        all_link_info = profile['local_link_information']

        selected = False
        for link_info in all_link_info:

            if 'port_id' not in link_info:
                return False

            switch_info = self._get_baremetal_switch_info(
                              link_info)
            if 'switch_ip' in switch_info:
                switch_ip = switch_info['switch_ip']
            else:
                return False

            if self._switch_defined(switch_ip):
                selected = True
            else:
                LOG.warning("Skip switch %s.  Not configured "
                            "in ini file" % switch_ip)

        if not selected:
            return False

        selected = self._baremetal_set_binding(context, all_link_info)
        if selected:
            self._init_baremetal_trunk_interfaces(
                context.current, context.top_bound_segment)

            if self.trunk.is_trunk_parentport(port):
                self.trunk.update_subports(port)

        return selected

    def _get_baremetal_switches(self, port):
        """Get switch ip addresses from baremetal transaction.

        This method is used to extract switch information
        from the transaction where VNIC_TYPE is baremetal.

        :param port: Received port transaction
        :returns: list of all switches
        :returns: list of only switches which are active
        """

        all_switches = set()
        active_switches = set()
        all_link_info = port[bc.portbindings.PROFILE]['local_link_information']
        for link_info in all_link_info:
            switch_info = self._get_baremetal_switch_info(link_info)
            if not switch_info:
                continue
            switch_ip = switch_info['switch_ip']

            # If not for Nexus
            if not self._switch_defined(switch_ip):
                continue

            all_switches.add(switch_ip)
            if self.is_switch_active(switch_ip):
                active_switches.add(switch_ip)

        return list(all_switches), list(active_switches)

    def _get_baremetal_connections(self, port,
                                   only_active_switch=False,
                                   from_segment=False):
        """Get switch ips and interfaces from baremetal transaction.

        This method is used to extract switch/interface
        information from transactions where VNIC_TYPE is
        baremetal.

        :param port: Received port transaction
        :param only_active_switch: Indicator for selecting
                     connections with switches that are active
        :param from_segment: only return interfaces from the
                   segment/transaction as opposed to
                   say port channels which are learned.
        :Returns: list of switch_ip, intf_type, port_id, is_native
        """

        connections = []

        is_native = False if self.trunk.is_trunk_subport(port) else True

        all_link_info = port[bc.portbindings.PROFILE]['local_link_information']

        for link_info in all_link_info:

            # Extract port info
            intf_type, port = nexus_help.split_interface_name(
                                  link_info['port_id'])

            # Determine if this switch is to be skipped
            switch_info = self._get_baremetal_switch_info(
                              link_info)
            if not switch_info:
                continue
            switch_ip = switch_info['switch_ip']

            # If not for Nexus
            if not self._switch_defined(switch_ip):
                continue

            # Requested connections for only active switches
            if (only_active_switch and
                not self.is_switch_active(switch_ip)):
                continue

            ch_grp = 0
            if not from_segment:
                try:
                    reserved = nxos_db.get_switch_if_host_mappings(
                        switch_ip,
                        nexus_help.format_interface_name(
                            intf_type, port))
                    if reserved[0].ch_grp > 0:
                        ch_grp = reserved[0].ch_grp
                        intf_type, port = nexus_help.split_interface_name(
                            '', ch_grp)
                except excep.NexusHostMappingNotFound:
                    pass

            connections.append((switch_ip, intf_type, port,
                                is_native, ch_grp))

        return connections

    def _init_baremetal_trunk_interfaces(self, port_seg, segment):
        """Initialize baremetal switch interfaces and DB entry.

        With baremetal transactions, the interfaces are not
        known during initialization so they must be initialized
        when the transactions are received.
        * Reserved switch entries are added if needed.
        * Reserved port entries are added.
        * Determine if port channel is configured on the
          interface and store it so we know to create a port-channel
          binding instead of that defined in the transaction.
          In this case, the RESERVED binding is the ethernet interface
          with port-channel stored in channel-group field.
          When this channel-group is not 0, we know to create a port binding
          as a port-channel instead of interface ethernet.
        """

        # interfaces list requiring switch initialization and
        # reserved port and port_binding db entry creation
        list_to_init = []

        # interfaces list requiring reserved port and port_binding
        # db entry creation
        inactive_switch = []

        connections = self._get_baremetal_connections(
                          port_seg, False, True)
        for switch_ip, intf_type, port, is_native, _ in connections:
            try:
                nxos_db.get_switch_if_host_mappings(
                    switch_ip,
                    nexus_help.format_interface_name(intf_type, port))
            except excep.NexusHostMappingNotFound:
                if self.is_switch_active(switch_ip):
                    # channel-group added later
                    list_to_init.append(
                        (switch_ip, intf_type, port, is_native, 0))
                else:
                    inactive_switch.append(
                        (switch_ip, intf_type, port, is_native, 0))

        # channel_group is appended to tuples in list_to_init
        self.driver.initialize_baremetal_switch_interfaces(list_to_init)

        host_id = port_seg.get('dns_name')
        if host_id is None:
            host_id = const.RESERVED_PORT_HOST_ID

        # Add inactive list to list_to_init to create RESERVED
        # port data base entries
        list_to_init += inactive_switch
        for switch_ip, intf_type, port, is_native, ch_grp in list_to_init:
            nxos_db.add_host_mapping(
                host_id,
                switch_ip,
                nexus_help.format_interface_name(intf_type, port),
                ch_grp, False)

    def _get_host_switches(self, host_id):
        """Get switch IPs from configured host mapping.

        This method is used to extract switch information
        from transactions where VNIC_TYPE is normal.
        Information is extracted from ini file which
        is stored in _nexus_switches.

        :param host_id: host_name from transaction
        :returns: list of all switches
        :returns: list of only switches which are active
        """

        all_switches = set()
        active_switches = set()

        try:
            host_list = nxos_db.get_host_mappings(host_id)
            for mapping in host_list:
                all_switches.add(mapping.switch_ip)
                if self.is_switch_active(mapping.switch_ip):
                    active_switches.add(mapping.switch_ip)
        except excep.NexusHostMappingNotFound:
            pass

        return list(all_switches), list(active_switches)

    def _get_host_connections(self, host_id,
                              only_active_switch=False):
        """Get switch IPs and interfaces from config host mapping.

        This method is used to extract switch/interface
        information from ini files when VNIC_TYPE is
        normal.  The ini files contain host to interface
        mappings.

        :param host_id: Host name from transaction
        :param only_active_switch: Indicator for selecting only
                   connections for switches that are active
        :returns: list of switch_ip, intf_type, port_id, is_native
        """

        host_found = False
        host_connections = []
        try:
            host_ifs = nxos_db.get_host_mappings(host_id)
        except excep.NexusHostMappingNotFound:
            host_ifs = []
        for ifs in host_ifs:
            host_found = True
            if (only_active_switch and
                not self.is_switch_active(ifs.switch_ip)):
                continue
            intf_type, port = nexus_help.split_interface_name(
                ifs.if_id, ifs.ch_grp)
            # is_native set to const.NOT_NATIVE for
            # VNIC_TYPE of normal
            host_connections.append((
                ifs.switch_ip, intf_type, port,
                const.NOT_NATIVE, ifs.ch_grp))

        if not host_found:
            LOG.warning(HOST_NOT_FOUND, host_id)

        return host_connections

    def _get_port_connections(self, port, host_id,
                              only_active_switch=False):
        if nexus_help.is_baremetal(port):
            return self._get_baremetal_connections(port, only_active_switch)
        else:
            return self._get_host_connections(host_id, only_active_switch)

    def _get_active_port_connections(self, port, host_id):
        return self._get_port_connections(port, host_id, True)

    def _get_switch_interfaces(self, requested_switch_ip, cfg_only=False):
        """Get switch interfaces from host mapping DB.

        For a given switch, this returns all known port
        interfaces for a given switch.  These have been
        learned from received baremetal transactions and
        from configuration file.

        :param requested_switch_ip: switch_ip
        :returns: list of switch_ip, intf_type, port_id, is_native
        """

        switch_ifs = []

        try:
            port_info = nxos_db.get_switch_host_mappings(
                            requested_switch_ip)
        except excep.NexusHostMappingNotFound:
            port_info = []

        for binding in port_info:
            if cfg_only and not binding.is_static:
                continue
            intf_type, port = nexus_help.split_interface_name(
                                  binding.if_id)
            switch_ifs.append(
                (requested_switch_ip, intf_type, port,
                const.NOT_NATIVE, binding.ch_grp))
        return switch_ifs

    def get_switch_ips(self):
        switch_connections = []
        for switch_ip, attrs in CONF.ml2_cisco.nexus_switches.items():
            if attrs.get("username"):
                switch_connections.append(switch_ip)
        return switch_connections

    def _get_switch_nve_info(self, host_id):
        host_nve_connections = set()
        try:
            host_data = nxos_db.get_host_mappings(host_id)
        except excep.NexusHostMappingNotFound:
            host_data = []
        for host in host_data:
            if host.is_static:
                host_nve_connections.add(host.switch_ip)

        if not host_nve_connections:
            LOG.warning(HOST_NOT_FOUND, host_id)

        return sorted(host_nve_connections)

    def _configure_nve_db(self, vni, device_id, mcast_group, host_id):
        """Create the nexus NVE database entry.

        Called during update precommit port event.
        """
        host_nve_connections = self._get_switch_nve_info(host_id)
        for switch_ip in host_nve_connections:
            if not nxos_db.get_nve_vni_member_bindings(vni, switch_ip,
                                                       device_id):
                nxos_db.add_nexusnve_binding(vni, switch_ip, device_id,
                                             mcast_group)

    def get_nve_loopback(self, switch_ip):
        return CONF.ml2_cisco.nexus_switches[switch_ip].get(
            const.NVE_SRC_INTF, '0')

    def _configure_nve_member(self, vni, device_id, mcast_group, host_id):
        """Add "member vni" configuration to the NVE interface.

        Called during update postcommit port event.
        """
        host_nve_connections = self._get_switch_nve_info(host_id)

        for switch_ip in host_nve_connections:

            # If configured to set global VXLAN values then
            #   If this is the first database entry for this switch_ip
            #   then configure the "interface nve" entry on the switch.
            if cfg.CONF.ml2_cisco.vxlan_global_config:
                nve_bindings = nxos_db.get_nve_switch_bindings(switch_ip)
                if len(nve_bindings) == 1:
                    LOG.debug("Nexus: create NVE interface")
                    loopback = self.get_nve_loopback(switch_ip)
                    self.driver.enable_vxlan_feature(switch_ip,
                        const.NVE_INT_NUM, loopback)

            # If this is the first database entry for this (VNI, switch_ip)
            # then configure the "member vni #" entry on the switch.
            member_bindings = nxos_db.get_nve_vni_switch_bindings(vni,
                                                                  switch_ip)
            if len(member_bindings) == 1:
                LOG.debug("Nexus: add member")
                self.driver.create_nve_member(switch_ip, const.NVE_INT_NUM,
                                              vni, mcast_group)

    def _delete_nve_db(self, vni, device_id, mcast_group, host_id):
        """Delete the nexus NVE database entry.

        Called during delete precommit port event.
        """
        rows = nxos_db.get_nve_vni_deviceid_bindings(vni, device_id)
        for row in rows:
            nxos_db.remove_nexusnve_binding(vni, row.switch_ip, device_id)

    def _delete_nve_member(self, vni, device_id, mcast_group, host_id):
        """Remove "member vni" configuration from the NVE interface.

        Called during delete postcommit port event.
        """
        host_nve_connections = self._get_switch_nve_info(host_id)
        for switch_ip in host_nve_connections:

            if not nxos_db.get_nve_vni_switch_bindings(vni, switch_ip):
                self.driver.delete_nve_member(switch_ip,
                    const.NVE_INT_NUM, vni)
            if (cfg.CONF.ml2_cisco.vxlan_global_config and
                not nxos_db.get_nve_switch_bindings(switch_ip)):
                self.driver.disable_vxlan_feature(switch_ip)

    def _configure_nxos_db(self, port, vlan_id, device_id, host_id, vni,
                           is_provider_vlan):
        """Create the nexus database entry.

        Called during update precommit port event.
        """
        connections = self._get_port_connections(port, host_id)
        for switch_ip, intf_type, nexus_port, is_native, ch_grp in connections:
            port_id = nexus_help.format_interface_name(
                intf_type, nexus_port, ch_grp)
            try:
                nxos_db.get_nexusport_binding(port_id, vlan_id, switch_ip,
                                              device_id)
            except excep.NexusPortBindingNotFound:
                nxos_db.add_nexusport_binding(port_id, str(vlan_id), str(vni),
                                              switch_ip, device_id,
                                              is_native)

    def _gather_config_parms(self, is_provider_vlan, vlan_id):
        """Collect auto_create, auto_trunk from config."""
        if is_provider_vlan:
            auto_create = cfg.CONF.ml2_cisco.provider_vlan_auto_create
            auto_trunk = cfg.CONF.ml2_cisco.provider_vlan_auto_trunk
        else:
            auto_create = True
            auto_trunk = True
        return auto_create, auto_trunk

    def _configure_port_binding(self, is_provider_vlan, duplicate_type,
                                is_native,
                                switch_ip, vlan_id,
                                intf_type, nexus_port, vni):
        """Conditionally calls vlan and port Nexus drivers."""

        # This implies VLAN, VNI, and Port are all duplicate.
        # Then there is nothing to configure in Nexus.
        if duplicate_type == const.DUPLICATE_PORT:
            return

        auto_create, auto_trunk = self._gather_config_parms(
            is_provider_vlan, vlan_id)

        # if type DUPLICATE_VLAN, don't create vlan
        if duplicate_type == const.DUPLICATE_VLAN:
            auto_create = False

        if auto_create and auto_trunk:
            LOG.debug("Nexus: create vlan %s and add to interface", vlan_id)
            self.driver.create_and_trunk_vlan(
                switch_ip, vlan_id, intf_type,
                nexus_port, vni, is_native)
        elif auto_create:
            LOG.debug("Nexus: create vlan %s", vlan_id)
            self.driver.create_vlan(switch_ip, vlan_id, vni)
        elif auto_trunk:
            LOG.debug("Nexus: trunk vlan %s", vlan_id)
            self.driver.send_enable_vlan_on_trunk_int(
                switch_ip, vlan_id,
                intf_type, nexus_port, is_native)

    def _get_compressed_vlan_list(self, pvlan_ids):
        """Generate a compressed vlan list ready for XML using a vlan set.

        Sample Use Case:

        Input vlan set:
        --------------
        1 - s = set([11, 50, 25, 30, 15, 16, 3, 8, 2, 1])
        2 - s = set([87, 11, 50, 25, 30, 15, 16, 3, 8, 2, 1, 88])

        Returned compressed XML list:
        ----------------------------
        1 - compressed_list = ['1-3', '8', '11', '15-16', '25', '30', '50']
        2 - compressed_list = ['1-3', '8', '11', '15-16', '25', '30',
                               '50', '87-88']
        """

        if not pvlan_ids:
            return []

        pvlan_list = list(pvlan_ids)
        pvlan_list.sort()
        compressed_list = []
        begin = -1
        prev_vlan = -1
        for port_vlan in pvlan_list:
            if prev_vlan == -1:
                prev_vlan = port_vlan
            else:
                if (port_vlan - prev_vlan) == 1:
                    if begin == -1:
                        begin = prev_vlan
                    prev_vlan = port_vlan
                else:
                    if begin == -1:
                        compressed_list.append(str(prev_vlan))
                    else:
                        compressed_list.append("%d-%d" % (begin, prev_vlan))
                        begin = -1
                    prev_vlan = port_vlan

        if begin == -1:
            compressed_list.append(str(prev_vlan))
        else:
            compressed_list.append("%s-%s" % (begin, prev_vlan))
        return compressed_list

    def _restore_port_binding(self,
                             switch_ip, pvlan_ids,
                             port, native_vlan):
        """Restores a set of vlans for a given port."""

        intf_type, nexus_port = nexus_help.split_interface_name(port)

        # If native_vlan is configured, this is isolated since
        # two configs (native + trunk) must be sent for this vlan only.
        if native_vlan != 0:
            self.driver.send_enable_vlan_on_trunk_int(
                switch_ip, native_vlan,
                intf_type, nexus_port, True)
            # If this is the only vlan
            if len(pvlan_ids) == 1:
                return

        concat_vlans = ''
        compressed_vlans = self._get_compressed_vlan_list(pvlan_ids)
        for pvlan in compressed_vlans:

            if concat_vlans == '':
                concat_vlans = "%s" % pvlan
            else:
                concat_vlans += ",%s" % pvlan

            # if string starts getting a bit long, send it.
            if len(concat_vlans) >= const.CREATE_PORT_VLAN_LENGTH:
                self.driver.send_enable_vlan_on_trunk_int(
                    switch_ip, concat_vlans,
                    intf_type, nexus_port, False)
                concat_vlans = ''

        # Send remaining vlans if any
        if len(concat_vlans):
            self.driver.send_enable_vlan_on_trunk_int(
                    switch_ip, concat_vlans,
                    intf_type, nexus_port, False)

    def _restore_vxlan_entries(self, switch_ip, vlans):
        """Restore vxlan entries on a Nexus switch."""

        count = 1
        conf_str = ''
        vnsegment_sent = 0
        path_str, conf_str = self.driver.start_create_vlan()
        # At this time, this will only configure vni information when needed
        while vnsegment_sent < const.CREATE_VLAN_BATCH and vlans:
            vlan_id, vni = vlans.pop(0)
            # Add it to the batch
            conf_str = self.driver.get_create_vlan(
                switch_ip, vlan_id, vni, conf_str)
            # batch size has been met
            if (count == const.CREATE_VLAN_SEND_SIZE):
                conf_str = self.driver.end_create_vlan(conf_str)
                self.driver.send_edit_string(switch_ip, path_str, conf_str)
                vnsegment_sent += count
                conf_str = ''
                count = 1
            else:
                count += 1

        # batch size was not met
        if conf_str:
            vnsegment_sent += count
            conf_str = self.driver.end_create_vlan(conf_str)
            self.driver.send_edit_string(switch_ip, path_str, conf_str)
            conf_str = ''

        LOG.debug("Switch %s VLAN vn-segment replay summary: %d",
                  switch_ip, vnsegment_sent)

    def _configure_port_entries(self, port, vlan_id, device_id, host_id, vni,
                                is_provider_vlan):
        """Create a nexus switch entry.

        if needed, create a VLAN in the appropriate switch or port and
        configure the appropriate interfaces for this VLAN.

        Called during update postcommit port event.
        """
        connections = self._get_active_port_connections(port, host_id)

        # (nexus_port,switch_ip) will be unique in each iteration.
        # But switch_ip will repeat if host has >1 connection to same switch.
        # So track which switch_ips already have vlan created in this loop.
        vlan_already_created = []
        starttime = time.time()

        for switch_ip, intf_type, nexus_port, is_native, _ in connections:

            try:
                all_bindings = nxos_db.get_nexusvlan_binding(
                    vlan_id, switch_ip)
            except excep.NexusPortBindingNotFound:
                LOG.warning("Switch %(switch_ip)s and Vlan "
                            "%(vlan_id)s not found in port binding "
                            "database. Skipping this update",
                            {'switch_ip': switch_ip, 'vlan_id': vlan_id})
                continue

            previous_bindings = [row for row in all_bindings
                    if row.instance_id != device_id]
            if previous_bindings and (switch_ip in vlan_already_created):
                duplicate_type = const.DUPLICATE_VLAN
            else:
                vlan_already_created.append(switch_ip)
                duplicate_type = const.NO_DUPLICATE
            port_starttime = time.time()
            try:
                self._configure_port_binding(
                    is_provider_vlan, duplicate_type,
                    is_native,
                    switch_ip, vlan_id,
                    intf_type, nexus_port,
                    vni)
            except Exception:
                with excutils.save_and_reraise_exception():
                    self.driver.capture_and_print_timeshot(
                        port_starttime, "port_configerr",
                        switch=switch_ip)
                    self.driver.capture_and_print_timeshot(
                        starttime, "configerr",
                        switch=switch_ip)
            self.driver.capture_and_print_timeshot(
                port_starttime, "port_config",
                switch=switch_ip)
        self.driver.capture_and_print_timeshot(
            starttime, "config")

    def configure_next_batch_of_vlans(self, switch_ip):
        """Get next batch of vlans and send them to Nexus."""

        next_range = self._pop_vlan_range(
                          switch_ip, const.CREATE_VLAN_BATCH)
        if next_range:
            try:
                self.driver.set_all_vlan_states(
                    switch_ip, next_range)
            except Exception:
                with excutils.save_and_reraise_exception():
                    LOG.error("Error encountered restoring vlans "
                        "for switch %(switch_ip)s",
                        {'switch_ip': switch_ip})
                    self._save_switch_vlan_range(switch_ip, [])

        vxlan_range = self._get_switch_vxlan_range(switch_ip)
        if vxlan_range:
            try:
                self._restore_vxlan_entries(switch_ip, vxlan_range)
            except Exception:
                with excutils.save_and_reraise_exception():
                    LOG.error("Error encountered restoring vxlans "
                        "for switch %(switch_ip)s",
                        {'switch_ip': switch_ip})
                    self._save_switch_vxlan_range(switch_ip, [])

        # if no more vlans to restore, we're done. go active.
        if (not self._get_switch_vlan_range(switch_ip) and
            not self._get_switch_vxlan_range(switch_ip)):
            self.set_switch_ip_and_active_state(
                switch_ip, const.SWITCH_ACTIVE)
            LOG.info("Restore of Nexus switch "
                "ip %(switch_ip)s is complete",
                {'switch_ip': switch_ip})
        else:
            LOG.debug(("Restored batch of VLANS on "
                "Nexus switch ip %(switch_ip)s"),
                {'switch_ip': switch_ip})

    def configure_switch_entries(self, switch_ip, port_bindings):
        """Create a nexus switch entry in Nexus.

        The port_bindings is sorted by vlan_id, vni, port_id.
        When there is a change in vlan_id or vni, then vlan
        data is configured in Nexus device.
        Otherwise we check if there is a change in port_id
        where we configure the port with vlan trunk config.

        Called during switch replay event.
        """
        prev_vlan = -1
        prev_vni = -1
        prev_port = None
        prev_native_vlan = 0
        starttime = time.time()

        port_bindings.sort(key=lambda x: (x.port_id, x.vlan_id, x.vni))
        self.driver.capture_and_print_timeshot(
            starttime, "replay_t2_aft_sort",
            switch=switch_ip)

        # Let's make these lists a set to exclude duplicates
        vlans = set()
        pvlans = set()
        interface_count = 0
        duplicate_port = 0
        vlan_count = 0
        for port in port_bindings:
            if nxos_db.is_reserved_binding(port):
                continue

            auto_create, auto_trunk = self._gather_config_parms(
                nxos_db.is_provider_vlan(port.vlan_id), port.vlan_id)
            if port.port_id == prev_port:
                if port.vlan_id == prev_vlan and port.vni == prev_vni:
                    # Same port/Same Vlan - skip duplicate
                    duplicate_port += 1
                    continue
                else:
                    # Same port/different Vlan - track it
                    vlan_count += 1
                    if auto_create:
                        vlans.add((port.vlan_id, port.vni))
                    if auto_trunk:
                        pvlans.add(port.vlan_id)
                    if port.is_native:
                        prev_native_vlan = port.vlan_id
            else:
                # Different port - write out interface trunk on previous port
                if prev_port:
                    interface_count += 1
                    LOG.debug("Switch %s port %s replay summary: unique vlan "
                              "count %d, duplicate port entries %d",
                              switch_ip, prev_port, vlan_count, duplicate_port)
                duplicate_port = 0
                vlan_count = 0
                if pvlans:
                    self._restore_port_binding(
                        switch_ip, pvlans, prev_port, prev_native_vlan)
                    pvlans.clear()
                    prev_native_vlan = 0
                # Start tracking new port
                if auto_create:
                    vlans.add((port.vlan_id, port.vni))
                if auto_trunk:
                    pvlans.add(port.vlan_id)
                prev_port = port.port_id
                if port.is_native:
                    prev_native_vlan = port.vlan_id

        if pvlans:
            LOG.debug("Switch %s port %s replay summary: unique vlan "
                      "count %d, duplicate port entries %d",
                      switch_ip, port.port_id, vlan_count, duplicate_port)
            self._restore_port_binding(
                switch_ip, pvlans, prev_port, prev_native_vlan)

        LOG.debug("Replayed total %d ports for Switch %s",
                  interface_count + 1, switch_ip)

        self.driver.capture_and_print_timeshot(
            starttime, "replay_part_1",
            switch=switch_ip)
        vlans = list(vlans)
        if vlans:
            vlans.sort()
            vlan, vni = vlans[0]
            if vni == 0:
                self._save_switch_vlan_range(switch_ip, vlans)
            else:
                self._save_switch_vxlan_range(switch_ip, vlans)

        self.set_switch_ip_and_active_state(
            switch_ip, const.SWITCH_RESTORE_S2)
        self.configure_next_batch_of_vlans(switch_ip)
        self.driver.capture_and_print_timeshot(
            starttime, "replay_part_2",
            switch=switch_ip)

    def _delete_nxos_db(self, unused, vlan_id, device_id, host_id, vni,
                        is_provider_vlan):
        """Delete the nexus database entry.

        Called during delete precommit port event.
        """
        try:
            rows = nxos_db.get_nexusvm_bindings(vlan_id, device_id)
            for row in rows:
                nxos_db.remove_nexusport_binding(row.port_id, row.vlan_id,
                                    row.vni, row.switch_ip, row.instance_id)
        except excep.NexusPortBindingNotFound:
            return

    def _delete_port_channel_resources(self, host_id, switch_ip,
                                       intf_type, nexus_port, port_id):
        '''This determines if port channel id needs to be freed.'''

        # if this connection is not a port-channel, nothing to do.
        if intf_type != 'port-channel':
            return

        # Check if this driver created it and its no longer needed.
        try:
            vpc = nxos_db.get_switch_vpc_alloc(
                switch_ip, nexus_port)
        except excep.NexusVPCAllocNotFound:
            # This can occur for non-baremetal configured
            # port-channels.  Nothing more to do.
            return

        # if this isn't one which was allocated or learned,
        # don't do any further processing.
        if not vpc.active:
            return

        # Is this port-channel still in use?
        # If so, nothing more to do.
        try:
            nxos_db.get_nexus_switchport_binding(port_id, switch_ip)
            return
        except excep.NexusPortBindingNotFound:
            pass

        # need to get ethernet interface name
        try:
            mapping = nxos_db.get_switch_and_host_mappings(
                host_id, switch_ip)
            eth_type, eth_port = nexus_help.split_interface_name(
                mapping[0].if_id)
        except excep.NexusHostMappingNotFound:
            return

        # Remove the channel group from ethernet interface
        # and remove port channel from this switch.
        if not vpc.learned:
            self.driver.delete_ch_grp_to_interface(
                switch_ip, eth_type, eth_port,
                nexus_port)
            self.driver.delete_port_channel(switch_ip,
                nexus_port)
        try:
            nxos_db.free_vpcid_for_switch(nexus_port, switch_ip)
        except excep.NexusVPCAllocNotFound:
            # Not all learned port channels will be in this db when
            # they're outside the configured vpc_pool so
            # this exception may be possible.
            pass

    def _delete_switch_entry(self, port, vlan_id, device_id, host_id, vni,
                             is_provider_vlan):
        """Delete the nexus switch entry.

        By accessing the current db entries determine if switch
        configuration can be removed.

        Called during delete postcommit port event.
        """

        connections = self._get_active_port_connections(port, host_id)

        # (nexus_port,switch_ip) will be unique in each iteration.
        # But switch_ip will repeat if host has >1 connection to same switch.
        # So track which switch_ips already have vlan removed in this loop.
        vlan_already_removed = []
        for switch_ip, intf_type, nexus_port, is_native, _ in connections:

            # if there are no remaining db entries using this vlan on this
            # nexus switch port then remove vlan from the switchport trunk.
            port_id = nexus_help.format_interface_name(intf_type, nexus_port)
            auto_create = True
            auto_trunk = True
            if is_provider_vlan:
                auto_create = cfg.CONF.ml2_cisco.provider_vlan_auto_create
                auto_trunk = cfg.CONF.ml2_cisco.provider_vlan_auto_trunk

            try:
                nxos_db.get_port_vlan_switch_binding(port_id, vlan_id,
                                                     switch_ip)
            except excep.NexusPortBindingNotFound:
                pass
            else:
                continue

            if auto_trunk:
                self.driver.disable_vlan_on_trunk_int(
                    switch_ip, vlan_id, intf_type, nexus_port,
                    is_native)

            # if there are no remaining db entries using this vlan on this
            # nexus switch then remove the vlan.
            if auto_create:
                try:
                    nxos_db.get_nexusvlan_binding(vlan_id, switch_ip)
                except excep.NexusPortBindingNotFound:
                    # Do not perform a second time on same switch
                    if switch_ip not in vlan_already_removed:
                        self.driver.delete_vlan(switch_ip, vlan_id)
                        vlan_already_removed.append(switch_ip)

            self._delete_port_channel_resources(
                host_id, switch_ip, intf_type, nexus_port, port_id)

        if nexus_help.is_baremetal(port):
            connections = self._get_baremetal_connections(
                port, False, True)
            for switch_ip, intf_type, nexus_port, is_native, _ in connections:
                if_id = nexus_help.format_interface_name(
                    intf_type, nexus_port)
                try:
                    mapping = nxos_db.get_switch_if_host_mappings(
                        switch_ip, if_id)
                    ch_grp = mapping[0].ch_grp
                except excep.NexusHostMappingNotFound:
                    ch_grp = 0
                bind_port_id = nexus_help.format_interface_name(
                    intf_type, nexus_port, ch_grp)
                binding = nxos_db.get_port_switch_bindings(
                    bind_port_id,
                    switch_ip)
                if not binding:
                    nxos_db.remove_host_mapping(if_id, switch_ip)

    def _is_segment_nexus_vxlan(self, segment):
        return segment[api.NETWORK_TYPE] == const.TYPE_NEXUS_VXLAN

    def _get_segments(self, top_segment, bottom_segment):
        # Return vlan segment and vxlan segment (if configured).
        if top_segment is None:
            return None, None
        elif self._is_segment_nexus_vxlan(top_segment):
            return bottom_segment, top_segment
        else:
            return top_segment, None

    def _is_vm_migrating(self, context, vlan_segment, orig_vlan_segment):
        if not vlan_segment and orig_vlan_segment:
            current_host_id = context.current.get(bc.portbindings.HOST_ID)
            original_host_id = context.original.get(bc.portbindings.HOST_ID)
            if current_host_id and original_host_id:
                return current_host_id != original_host_id

    def _log_missing_segment(self):
        LOG.debug("Nexus: Segment is None, Event not processed.")

    def _is_valid_segment(self, segment):
        valid_segment = True
        if segment:
            if (segment[api.NETWORK_TYPE] != p_const.TYPE_VLAN or
                not self._valid_network_segment(segment)):
                LOG.debug("Nexus: Segment is an invalid type or not "
                          "supported by this driver. Network type = "
                          "%(network_type)s Physical network = "
                          "%(phy_network)s. Event not processed.",
                          {'network_type': segment[api.NETWORK_TYPE],
                           'phy_network': segment[api.PHYSICAL_NETWORK]})
                valid_segment = False
        else:
            self._log_missing_segment()
            valid_segment = False

        return valid_segment

    def _port_action_vlan(self, port, segment, func, vni):
        """Verify configuration and then process event."""

        # Verify segment.
        if not self._is_valid_segment(segment):
            return

        device_id = self._get_port_uuid(port)

        if nexus_help.is_baremetal(port):
            host_id = port.get('dns_name')
        else:
            host_id = port.get(bc.portbindings.HOST_ID)

        vlan_id = segment.get(api.SEGMENTATION_ID)
        is_provider = nxos_db.is_provider_vlan(vlan_id)

        settings = {"vlan_id": vlan_id,
                    "device_id": device_id,
                    "host_id": host_id}
        missing_fields = [field for field, value in settings.items()
                          if (field != 'host_id' and not value)]
        if not missing_fields:
            func(port, vlan_id, device_id, host_id, vni, is_provider)
        else:
            raise excep.NexusMissingRequiredFields(
                fields=' '.join(missing_fields))

    def _port_action_vxlan(self, port, segment, func):
        """Verify configuration and then process event."""

        # If the segment is None, just log a warning message and return.
        if segment is None:
            self._log_missing_segment()
            return

        device_id = port.get('device_id')
        mcast_group = segment.get(api.PHYSICAL_NETWORK)
        host_id = port.get(bc.portbindings.HOST_ID)
        vni = segment.get(api.SEGMENTATION_ID)

        if vni and device_id and mcast_group and host_id:
            func(vni, device_id, mcast_group, host_id)
            return vni
        else:
            fields = "vni " if not vni else ""
            fields += "device_id " if not device_id else ""
            fields += "mcast_group " if not mcast_group else ""
            fields += "host_id" if not host_id else ""
            raise excep.NexusMissingRequiredFields(fields=fields)

    def _monitor_thread(self):
        """Periodically restarts the monitor thread."""
        with self.monitor_lock:
            self.monitor.check_connections()

        self.timer = threading.Timer(self.monitor_timeout,
                                     self._monitor_thread)
        self.timer.start()

    def _stop_monitor_thread(self):
        """Terminates the monitor thread."""
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def create_network_precommit(self, context):
        network = context.current
        if network.get('is_provider_network', False):
            nxos_db.add_provider_network(
                network['id'], network[bc.providernet.SEGMENTATION_ID])

    def delete_network_postcommit(self, context):
        if nxos_db.is_provider_network(context.current['id']):
            nxos_db.delete_provider_network(context.current['id'])

    @lockutils.synchronized('cisco-nexus-portlock')
    def create_port_postcommit(self, context):
        """Create port non-database commit event."""

        # No new events are handled until replay
        # thread has put the switch in active state.
        # If a switch is in active state, verify
        # the switch is still in active state
        # before accepting this new event.
        #
        # If create_port_postcommit fails, it causes
        # other openstack dbs to be cleared and
        # retries for new VMs will stop.  Subnet
        # transactions will continue to be retried.

        vlan_segment, vxlan_segment = self._get_segments(
                                        context.top_bound_segment,
                                        context.bottom_bound_segment)
        # Verify segment.
        if not self._is_valid_segment(vlan_segment):
            return

        port = context.current
        if self._is_supported_deviceowner(port):
            if nexus_help.is_baremetal(context.current):
                all_switches, active_switches = (
                    self._get_baremetal_switches(context.current))
            else:
                host_id = context.current.get(bc.portbindings.HOST_ID)
                all_switches, active_switches = (
                    self._get_host_switches(host_id))

            # Verify switch is still up before replay
            # thread checks.
            verified_active_switches = []
            for switch_ip in active_switches:
                try:
                    self.driver.get_nexus_type(switch_ip)
                    verified_active_switches.append(switch_ip)
                except Exception as e:
                    LOG.error("Failed to ping "
                        "switch ip %(switch_ip)s error %(exp_err)s",
                        {'switch_ip': switch_ip, 'exp_err': e})

            LOG.debug("Create Stats:  thread %(thid)d, "
                      "all_switches %(all)d, "
                      "active %(active)d, verified %(verify)d",
                      {'thid': threading.current_thread().ident,
                      'all': len(all_switches),
                      'active': len(active_switches),
                      'verify': len(verified_active_switches)})

            # if host_id is valid and there is no active
            # switches remaining
            if all_switches and not verified_active_switches:
                raise excep.NexusConnectFailed(
                    nexus_host=all_switches[0], config="None",
                    exc="Create Failed: Port event can not "
                    "be processed at this time.")

    @lockutils.synchronized('cisco-nexus-portlock')
    def update_port_precommit(self, context):
        """Update port pre-database transaction commit event."""
        vlan_segment, vxlan_segment = self._get_segments(
            context.top_bound_segment, context.bottom_bound_segment)
        orig_vlan_segment, orig_vxlan_segment = self._get_segments(
            context.original_top_bound_segment,
            context.original_bottom_bound_segment)

        if (self._is_vm_migrating(context, vlan_segment, orig_vlan_segment) or
            self._is_status_down(context.current)):
            vni = (self._port_action_vxlan(
                context.original, orig_vxlan_segment, self._delete_nve_db)
                if orig_vxlan_segment else 0)
            self._port_action_vlan(context.original, orig_vlan_segment,
                                   self._delete_nxos_db, vni)
        elif self._is_supported_deviceowner(context.current):
            vni = self._port_action_vxlan(context.current, vxlan_segment,
                        self._configure_nve_db) if vxlan_segment else 0
            self._port_action_vlan(context.current, vlan_segment,
                                   self._configure_nxos_db, vni)

    @lockutils.synchronized('cisco-nexus-portlock')
    def update_port_postcommit(self, context):
        """Update port non-database commit event."""
        vlan_segment, vxlan_segment = self._get_segments(
            context.top_bound_segment, context.bottom_bound_segment)
        orig_vlan_segment, orig_vxlan_segment = self._get_segments(
            context.original_top_bound_segment,
            context.original_bottom_bound_segment)

        if (self._is_vm_migrating(context, vlan_segment, orig_vlan_segment) or
                self._is_status_down(context.current)):
            vni = (self._port_action_vxlan(
                context.original, orig_vxlan_segment,
                self._delete_nve_member) if orig_vxlan_segment else 0)
            self._port_action_vlan(context.original, orig_vlan_segment,
                                   self._delete_switch_entry, vni)
        elif self._is_supported_deviceowner(context.current):
            if nexus_help.is_baremetal(context.current):
                all_switches, active_switches = (
                    self._get_baremetal_switches(context.current))
            else:
                host_id = context.current.get(bc.portbindings.HOST_ID)
                all_switches, active_switches = (
                    self._get_host_switches(host_id))

            # if switches not active but host_id is valid
            if not active_switches and all_switches:
                raise excep.NexusConnectFailed(
                    nexus_host=all_switches[0], config="None",
                    exc="Update Port Failed: Nexus Switch "
                    "is down or replay in progress")
            vni = self._port_action_vxlan(context.current, vxlan_segment,
                        self._configure_nve_member) if vxlan_segment else 0
            self._port_action_vlan(context.current, vlan_segment,
                                   self._configure_port_entries, vni)

    @lockutils.synchronized('cisco-nexus-portlock')
    def delete_port_precommit(self, context):
        """Delete port pre-database commit event."""
        if self._is_supported_deviceowner(context.current):
            vlan_segment, vxlan_segment = self._get_segments(
                                                context.top_bound_segment,
                                                context.bottom_bound_segment)
            vni = self._port_action_vxlan(context.current, vxlan_segment,
                             self._delete_nve_db) if vxlan_segment else 0
            self._port_action_vlan(context.current, vlan_segment,
                                   self._delete_nxos_db, vni)

    @lockutils.synchronized('cisco-nexus-portlock')
    def delete_port_postcommit(self, context):
        """Delete port non-database commit event."""
        if self._is_supported_deviceowner(context.current):
            vlan_segment, vxlan_segment = self._get_segments(
                                                context.top_bound_segment,
                                                context.bottom_bound_segment)
            vni = self._port_action_vxlan(context.current, vxlan_segment,
                             self._delete_nve_member) if vxlan_segment else 0
            self._port_action_vlan(context.current, vlan_segment,
                                   self._delete_switch_entry, vni)

    def bind_port(self, context):
        LOG.debug("Attempting to bind port %(port)s on network %(network)s",
                  {'port': context.current['id'],
                   'network': context.network.current['id']})

        # Check to determine if there are segments to bind
        if not context.segments_to_bind:
            return

        #
        # if is VNIC_TYPE baremetal and all required config is intact,
        #    accept this transaction
        # otherwise check if vxlan for us
        #
        if self._supported_baremetal_transaction(context):
            return

        for segment in context.segments_to_bind:
            if self._is_segment_nexus_vxlan(segment):

                # Find physical network setting for this host.
                host_id = context.current.get(bc.portbindings.HOST_ID)
                host_connections = self._get_port_connections(
                                       context.current,
                                       host_id)
                if not host_connections:
                    return

                for switch_ip, _, _, _, _ in host_connections:
                    physnet = CONF.ml2_cisco.nexus_switches[switch_ip].get(
                        const.PHYSNET)
                    if physnet:
                        break
                else:
                    raise excep.PhysnetNotConfigured(host_id=host_id,
                                             host_connections=host_connections)

                # Allocate dynamic vlan segment.
                vlan_segment = {api.NETWORK_TYPE: p_const.TYPE_VLAN,
                                api.PHYSICAL_NETWORK: physnet}
                context.allocate_dynamic_segment(vlan_segment)

                # Retrieve the dynamically allocated segment.
                # Database has provider_segment dictionary key.
                network_id = context.current['network_id']
                db_ref = bc.get_db_ref(self.context)
                dynamic_segment = bc.segments_db.get_dynamic_segment(
                    db_ref, network_id, physnet)

                # Have other drivers bind the VLAN dynamic segment.
                if dynamic_segment:
                    context.continue_binding(segment[api.ID],
                                             [dynamic_segment])
                else:
                    raise excep.NoDynamicSegmentAllocated(
                                        network_segment=network_id,
                                        physnet=physnet)
            else:
                LOG.debug("No binding required for segment ID %(id)s, "
                          "segment %(seg)s, phys net %(physnet)s, and "
                          "network type %(nettype)s",
                          {'id': segment[api.ID],
                           'seg': segment[api.SEGMENTATION_ID],
                           'physnet': segment[api.PHYSICAL_NETWORK],
                           'nettype': segment[api.NETWORK_TYPE]})
