# Copyright (c) 2017-2017 Cisco Systems, Inc.
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
Implements a Nexus-OS NETCONF over SSHv2 API Client
"""

import re
import time

from oslo_log import log as logging

from networking_cisco._i18n import _LE, _LW

from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    config as conf)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    constants as const)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    exceptions as cexc)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_base_network_driver as basedrvr)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_db_v2 as nxos_db)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_helpers as nexus_help)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_restapi_client as client)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_restapi_snippets as snipp)

LOG = logging.getLogger(__name__)


class CiscoNexusRestapiDriver(basedrvr.CiscoNexusBaseDriver):
    """Nexus Driver Restapi Class."""
    def __init__(self):
        conf.ML2MechCiscoConfig()
        credentials = self._build_credentials(
            conf.ML2MechCiscoConfig.nexus_dict)
        self.client = self._import_client(credentials)
        super(CiscoNexusRestapiDriver, self).__init__()
        LOG.debug("ML2 Nexus RESTAPI Drivers initialized.")

    def _import_client(self, credentials):
        """Import the local RESTAPI client module.

        This method was created to mirror original ssh driver so
        test code was in sync.

        """

        return client.CiscoNexusRestapiClient(credentials)

    def _build_credentials(self, nexus_switches):
        """Build credential table for Rest API Client.

        :param nexus_switches: switch config
        :returns credentials: switch credentials list
        """

        credential_attr = [const.USERNAME, const.PASSWORD]

        credentials = {}
        for switch_ip, option in nexus_switches:
            if option in credential_attr:
                value = nexus_switches[switch_ip, option]
                if switch_ip in credentials:
                    credential_tuple = credentials[switch_ip]
                else:
                    credential_tuple = (None, None)
                if option == const.USERNAME:
                    credential_tuple = (value,
                        credential_tuple[1])
                else:
                    credential_tuple = (
                        credential_tuple[0],
                        value)
                credentials[switch_ip] = credential_tuple
        return credentials

    def get_interface_switch(self, nexus_host,
                             intf_type, interface):
        """Get the interface data from host.

        :param nexus_host: IP address of Nexus switch
        :param intf_type:  String which specifies interface type.
                           example: ethernet
        :param interface:  String indicating which interface.
                           example: 1/19
        :returns response: Returns interface data
        """

        if intf_type == "ethernet":
            path_interface = "phys-[eth" + interface + "]"
        else:
            path_interface = "aggr-[po" + interface + "]"

        action = snipp.PATH_IF % path_interface

        starttime = time.time()
        response = self.client.rest_get(action, nexus_host)
        self.capture_and_print_timeshot(starttime, "getif",
            switch=nexus_host)
        LOG.debug("GET call returned interface %(if_type)s %(interface)s "
            "config", {'if_type': intf_type, 'interface': interface})
        return response

    def _get_interface_switch_trunk_present(
        self, nexus_host, intf_type, interface):
        """Check if 'switchport trunk allowed vlan' present.

        :param nexus_host: IP address of Nexus switch
        :param intf_type:  String which specifies interface type.
                           example: ethernet
        :param interface:  String indicating which interface.
                           example: 1/19
        :returns found:    True if config already present
        """
        result = self.get_interface_switch(nexus_host, intf_type, interface)
        try:
            if_type = 'l1PhysIf' if intf_type == "ethernet" else 'pcAggrIf'
            vlan_list = result['imdata'][0][if_type]
            vlan_list = vlan_list['attributes']['trunkVlans']
            if vlan_list != "1-4094":
                found = True
            else:
                found = False
        except Exception:
            found = False

        return found

    def add_ch_grp_to_interface(
        self, nexus_host, if_type, port, ch_grp):
        """Applies channel-group n to ethernet interface."""

        if if_type != "ethernet":
            LOG.error(_LE("Unexpected interface type %(iftype)s when "
                      "adding change group"), {'iftype': if_type})
            return

        starttime = time.time()

        path_snip = snipp.PATH_ALL
        path_interface = "phys-[eth" + port + "]"

        body_snip = snipp.BODY_ADD_CH_GRP % (ch_grp, ch_grp, path_interface)

        self.send_edit_string(nexus_host, path_snip, body_snip)

        self.capture_and_print_timeshot(
            starttime, "add_ch_group",
            switch=nexus_host)

    def delete_ch_grp_to_interface(
        self, nexus_host, if_type, port, ch_grp):
        """Removes channel-group n from ethernet interface."""

        if if_type != "ethernet":
            LOG.error(_LE("Unexpected interface type %(iftype)s when "
                      "deleting change group"), {'iftype': if_type})
            return

        starttime = time.time()

        path_snip = snipp.PATH_ALL

        path_interface = "phys-[eth" + port + "]"
        body_snip = snipp.BODY_DEL_CH_GRP % (ch_grp, path_interface)

        self.send_edit_string(nexus_host, path_snip, body_snip)

        self.capture_and_print_timeshot(
            starttime, "del_ch_group",
            switch=nexus_host)

    def _apply_user_port_channel_config(self, nexus_host, vpc_nbr):
        """Adds STP and no lacp suspend config to port channel. """

        vpc_str = str(vpc_nbr)
        path_snip = snipp.PATH_ALL

        body_snip = snipp.BODY_ADD_PORT_CH_P2 % (vpc_str, vpc_str)

        self.send_edit_string(nexus_host, path_snip, body_snip)

    def create_port_channel(self, nexus_host, vpc_nbr):
        """Creates port channel n on Nexus switch."""

        starttime = time.time()

        vpc_str = str(vpc_nbr)
        path_snip = snipp.PATH_ALL
        body_snip = snipp.BODY_ADD_PORT_CH % (vpc_str, vpc_str, vpc_str)

        self.send_edit_string(nexus_host, path_snip, body_snip)

        self._apply_user_port_channel_config(nexus_host, vpc_nbr)

        self.send_enable_vlan_on_trunk_int(
            nexus_host, "", 'port-channel',
            vpc_str, False, add_mode=True)

        self.capture_and_print_timeshot(
            starttime, "create_port_channel",
            switch=nexus_host)

    def delete_port_channel(self, nexus_host, vpc_nbr):
        """Deletes delete port channel on Nexus switch."""

        starttime = time.time()

        path_snip = snipp.PATH_ALL
        body_snip = snipp.BODY_DEL_PORT_CH % (vpc_nbr)

        self.send_edit_string(nexus_host, path_snip, body_snip)

        self.capture_and_print_timeshot(
            starttime, "delete_port_channel",
            switch=nexus_host)

    def _get_port_channel_group(
        self, nexus_host, intf_type, interface):
        """Look for 'channel-group x' config and return x.

        :param nexus_host: IP address of Nexus switch
        :param intf_type:  String which specifies interface type.
                           example: ethernet
        :param interface:  String indicating which interface.
                           example: 1/19
        :returns pc_group: Returns port channel group if
                           present else 0
        """

        ch_grp = 0

        # channel-group only applied to ethernet,
        # otherwise, return 0
        if intf_type != 'ethernet':
            return ch_grp

        match_key = "eth" + interface

        action = snipp.PATH_GET_PC_MEMBERS

        starttime = time.time()
        result = self.client.rest_get(action, nexus_host)
        self.capture_and_print_timeshot(starttime, "getpc",
            switch=nexus_host)
        try:
            for pcmbr in result['imdata']:
                mbr_data = pcmbr['pcRsMbrIfs']['attributes']
                if mbr_data['tSKey'] == match_key:
                    _, nbr = mbr_data['parentSKey'].split("po")
                    ch_grp = int(nbr)
                    break
        except Exception:
            pass

        LOG.debug("GET interface %(key)s port channel is %(pc)d",
            {'key': match_key, 'pc': ch_grp})

        return ch_grp

    def initialize_baremetal_switch_interfaces(self, interfaces):
        """Initialize Nexus interfaces and for initial baremetal event.

        This get/create port channel number, applies channel-group to
        ethernet interface, and initializes trunking on interface.

        :param interface: Receive a list of interfaces containing:

        nexus_host: IP address of Nexus switch
        intf_type:  String which specifies interface type.
                    example: ethernet
        interface:  String indicating which interface.
                       example: 1/19
        is_native:  Whether native vlan must be configured.
        ch_grp:     May replace port channel to each entry.
                    channel number is 0 if none
        """
        if not interfaces:
            return

        max_ifs = len(interfaces)
        starttime = time.time()

        # build host list in case you need to allocate vpc_id
        prev_ch_grp = -1
        nexus_ip_list = []
        for (nexus_host, intf_type, nexus_port,
            is_native, ch_grp) in interfaces:
            nexus_ip_list.append(nexus_host)
            if prev_ch_grp != -1 and prev_ch_grp != ch_grp:
                # LOG error Baremetal set does not have matching ch_grp
                LOG.error(_LE("Inconsistent change group stored in "
                    "port entries. Saw %(ch_grp)d expected "
                    "%(p_ch_grp)d for switch %(switch)s interface "
                    "%(intf)s."), {
                    'ch_grp': ch_grp,
                    'p_ch_grp': prev_ch_grp,
                    'switch': nexus_host,
                    'intf': nexus_help.format_interface_name(
                        intf_type, nexus_port)})
                return
            prev_ch_grp = ch_grp

        ch_grp = 0
        for i, (nexus_host, intf_type, nexus_port, is_native,
            ch_grp_saved) in enumerate(interfaces):

            add_trunk_mode = False
            if max_ifs > 1 and ch_grp_saved == 0:

                learned_ch_grp = self._get_port_channel_group(
                    nexus_host, intf_type, nexus_port)

                if i == 0:   # if first in the set
                    if learned_ch_grp == 0:
                        # When allocating vpcid, it must be unique for
                        # all switches in the set.
                        ch_grp = nxos_db.alloc_vpcid(nexus_ip_list)
                        self.create_port_channel(nexus_host, ch_grp)
                        learned = False
                        add_trunk_mode = True
                        self.add_ch_grp_to_interface(
                            nexus_host, intf_type, nexus_port, ch_grp)
                    else:
                        ch_grp = learned_ch_grp
                        learned = True
                    save_1st_if = (nexus_host + ', ' +
                        intf_type + ':' + nexus_port + ', ')
                else:
                    if learned:
                        if learned_ch_grp != ch_grp:
                            this_if = (nexus_host + ', ' + intf_type +
                                ':' + nexus_port +
                                ', vpc=' + str(learned_ch_grp))
                            raise cexc.NexusVPCLearnedNotConsistent(
                                first=save_1st_if + 'vpc=' + str(ch_grp),
                                second=this_if)
                        # if newly learned ch_grp
                        if ch_grp_saved == 0:
                            nxos_db.update_vpc_entry(
                                nexus_host, ch_grp, learned, True)
                    elif learned_ch_grp != 0:
                        # Remove port-channels just created
                        for y in range(i):
                            self.delete_port_channel(
                                nexus_ip_list[y], ch_grp)
                        nxos_db.free_vpcid_for_switch_list(
                            ch_grp, nexus_ip_list)
                        raise cexc.NexusVPCExpectedNoChgrp(
                            first=save_1st_if + 'vpc=None',
                            second=this_if)
                    else:
                        self.create_port_channel(nexus_host, ch_grp)
                        self.add_ch_grp_to_interface(
                            nexus_host, intf_type, nexus_port, ch_grp)
                if ch_grp is not 0:
                    # if channel-group returned, init port-channel
                    # instead of the provided ethernet interface
                    intf_type = 'port-channel'
                    nexus_port = str(ch_grp)

            elif i == 0:
                ch_grp = ch_grp_saved

            #substitute content of ch_grp
            no_chgrp_len = len(interfaces[i]) - 1
            interfaces[i] = interfaces[i][:no_chgrp_len] + (ch_grp,)

            present = self._get_interface_switch_trunk_present(
                nexus_host, intf_type, nexus_port)
            if not present:
                self.send_enable_vlan_on_trunk_int(
                    nexus_host, "", intf_type, nexus_port, False,
                    add_trunk_mode)

        self.capture_and_print_timeshot(
            starttime, "init_bmif",
            switch=nexus_host)

    def initialize_all_switch_interfaces(self, interfaces,
                                         switch_ip=None, replay=True):
        """Configure Nexus interface and get port channel number.

        Called during switch replay or just init if no replay
        is configured.  For latter case, only configured interfaces
        are affected by this method.

        During switch replay, the change group from the
        host mapping data base is used.  There is no attempt
        to relearn port-channel from the Nexus switch.  What
        we last knew it to be will persist.

        :param interfaces:  List of interfaces for a given switch.
                            ch_grp can be altered as last arg
                            to each interface. If no ch_grp,
                            this arg will be zero.
        :param switch_ip: IP address of Nexus switch
        :param replay: Whether in replay path
        """
        if not interfaces:
            return

        starttime = time.time()

        if replay:
            try:
                vpcs = nxos_db.get_active_switch_vpc_allocs(switch_ip)
            except cexc.NexusVPCAllocNotFound:
                vpcs = []
            for vpc in vpcs:
                # if this is an allocated vpc, then recreate it
                if not vpc.learned:
                    self.create_port_channel(switch_ip, vpc.vpc_id)

        for i, (nexus_host, intf_type, nexus_port, is_native,
            ch_grp) in enumerate(interfaces):
            add_trunk_mode = False
            if replay and ch_grp != 0:
                try:
                    vpc = nxos_db.get_switch_vpc_alloc(switch_ip, ch_grp)
                    if not vpc.learned:
                        add_trunk_mode = True
                    self.add_ch_grp_to_interface(
                        nexus_host, intf_type, nexus_port, ch_grp)
                except cexc.NexusVPCAllocNotFound:
                    pass
                # if channel-group exists, switch to port-channel
                # instead of the provided ethernet interface
                intf_type = 'port-channel'
                nexus_port = str(ch_grp)

            #substitute content of ch_grp
            no_chgrp_len = len(interfaces[i]) - 1
            interfaces[i] = interfaces[i][:no_chgrp_len] + (ch_grp,)

            present = self._get_interface_switch_trunk_present(
                nexus_host, intf_type, nexus_port)
            if not present:
                self.send_enable_vlan_on_trunk_int(
                    nexus_host, "", intf_type, nexus_port, False,
                    add_trunk_mode)

        self.capture_and_print_timeshot(
            starttime, "get_allif",
            switch=nexus_host)

    def get_nexus_type(self, nexus_host):
        """Given the nexus host, get the type of Nexus switch.

        :param nexus_host: IP address of Nexus switch
        :returns Nexus type
        """

        starttime = time.time()
        response = self.client.rest_get(
            snipp.PATH_GET_NEXUS_TYPE, nexus_host)
        self.capture_and_print_timeshot(
            starttime, "gettype",
            switch=nexus_host)

        if response:
            try:
                result = response['imdata'][0]["eqptCh"]['attributes']['descr']
            except Exception:
                result = ''
            nexus_type = re.findall(
                "Nexus\s*(\d)\d+\s*[0-9A-Z]+\s*"
                "[cC]hassis",
                result)
            if len(nexus_type) > 0:
                LOG.debug("GET call returned Nexus type %d",
                    int(nexus_type[0]))
                return int(nexus_type[0])

        LOG.warning(_LW("GET call failed to return Nexus type"))
        return -1

    def start_create_vlan(self):
        """Returns REST API path and config start."""

        return snipp.PATH_ALL, snipp.BODY_VLAN_ALL_BEG

    def end_create_vlan(self, conf_str):
        """Returns current config + end of config."""

        conf_str += snipp.BODY_VLAN_ALL_END
        return conf_str

    def get_create_vlan(self, nexus_host, vlanid, vni, conf_str):
        """Returns an XML snippet for create VLAN on a Nexus Switch."""

        starttime = time.time()

        if vni:
            body_snip = snipp.BODY_VXLAN_ALL_INCR % (vlanid, vni)
        else:
            body_snip = snipp.BODY_VLAN_ALL_INCR % vlanid
        conf_str += body_snip + snipp.BODY_VLAN_ALL_CONT

        self.capture_and_print_timeshot(
            starttime, "get_create_vlan",
            switch=nexus_host)

        return conf_str

    def set_all_vlan_states(self, nexus_host, vlanid_range):
        """Set the VLAN states to active."""

        starttime = time.time()

        if not vlanid_range:
            LOG.warning("Exiting set_all_vlan_states: No vlans to configure")
            return

        # Eliminate possible whitespace and separate vlans by commas
        vlan_id_list = re.sub(r'\s', '', vlanid_range).split(',')
        if not vlan_id_list or not vlan_id_list[0]:
            LOG.warning("Exiting set_all_vlan_states: No vlans to configure")
            return

        path_str, body_vlan_all = self.start_create_vlan()
        while vlan_id_list:
            rangev = vlan_id_list.pop(0)
            if '-' in rangev:
                fr, to = rangev.split('-')
                max = int(to) + 1
                for vlan_id in range(int(fr), max):
                    body_vlan_all = self.get_create_vlan(
                        nexus_host, vlan_id, 0, body_vlan_all)
            else:
                body_vlan_all = self.get_create_vlan(
                    nexus_host, rangev, 0, body_vlan_all)

        body_vlan_all = self.end_create_vlan(body_vlan_all)
        self.send_edit_string(
            nexus_host, path_str, body_vlan_all)

        self.capture_and_print_timeshot(
            starttime, "set_all_vlan_states",
            switch=nexus_host)

    def create_vlan(self, nexus_host,
                    vlanid, vlanname, vni):
        """Given switch, vlanid, vni, Create a VLAN on Switch."""

        starttime = time.time()
        path_snip, body_snip = self.start_create_vlan()
        body_snip = self.get_create_vlan(nexus_host, vlanid, vni, body_snip)
        body_snip = self.end_create_vlan(body_snip)

        self.send_edit_string(nexus_host, path_snip, body_snip)

        self.capture_and_print_timeshot(
            starttime, "create_vlan_seg",
            switch=nexus_host)

    def delete_vlan(self, nexus_host, vlanid):
        """Delete a VLAN on Nexus Switch given the VLAN ID."""
        starttime = time.time()

        path_snip = snipp.PATH_VLAN % vlanid
        self.client.rest_delete(path_snip, nexus_host)

        self.capture_and_print_timeshot(
            starttime, "del_vlan",
            switch=nexus_host)

    def _get_vlan_body_on_trunk_int(self, nexus_host, vlanid, intf_type,
                                    interface, is_native, is_delete,
                                    add_mode):
        """Prepares an XML snippet for VLAN on a trunk interface.

        :param nexus_host: IP address of Nexus switch
        :param vlanid:     Vlanid(s) to add to interface
        :param intf_type:  String which specifies interface type.
                           example: ethernet
        :param interface:  String indicating which interface.
                           example: 1/19
        :param is_native:  Is native vlan config desired?
        :param is_delete:  Is this a delete operation?
        :param add_mode:   Add mode trunk
        :returns           path_snippet, body_snippet
        """

        starttime = time.time()

        LOG.debug("NexusDriver get if body config for host %s: "
                  "if_type %s port %s",
                  nexus_host, intf_type, interface)
        if intf_type == "ethernet":
            body_if_type = "l1PhysIf"
            path_interface = "phys-[eth" + interface + "]"
        else:
            body_if_type = "pcAggrIf"
            path_interface = "aggr-[po" + interface + "]"

        path_snip = (snipp.PATH_IF % (path_interface))

        mode = snipp.BODY_PORT_CH_MODE if add_mode else ''
        if is_delete:
            increment_it = "-"
            debug_desc = "delif"
            native_vlan = ""
        else:
            native_vlan = 'vlan-' + str(vlanid)
            debug_desc = "createif"
            if vlanid is "":
                increment_it = ""
            else:
                increment_it = "+"

        if is_native:
            body_snip = (snipp.BODY_NATIVE_TRUNKVLAN %
                (body_if_type, mode, increment_it + str(vlanid),
                str(native_vlan)))
        else:
            body_snip = (snipp.BODY_TRUNKVLAN %
                (body_if_type, mode, increment_it + str(vlanid)))

        self.capture_and_print_timeshot(
            starttime, debug_desc,
            switch=nexus_host)

        return path_snip, body_snip

    def disable_vlan_on_trunk_int(self, nexus_host, vlanid, intf_type,
                                  interface, is_native):
        """Disable a VLAN on a trunk interface."""

        starttime = time.time()

        path_snip, body_snip = self._get_vlan_body_on_trunk_int(
            nexus_host, vlanid, intf_type, interface,
            is_native, True, False)
        self.send_edit_string(nexus_host, path_snip, body_snip)
        self.capture_and_print_timeshot(
            starttime, "delif",
            switch=nexus_host)

    def send_edit_string(self, nexus_host, path_snip, body_snip,
                         check_to_close_session=True):
        """Sends rest Post request to Nexus switch."""

        starttime = time.time()
        LOG.debug("NexusDriver edit config for host %s: path: %s body: %s",
                  nexus_host, path_snip, body_snip)
        self.client.rest_post(path_snip, nexus_host, body_snip)
        self.capture_and_print_timeshot(
            starttime, "send_edit",
            switch=nexus_host)

    def send_enable_vlan_on_trunk_int(self, nexus_host, vlanid, intf_type,
                                      interface, is_native, add_mode=False):
        """Gathers and sends an interface trunk XML snippet."""

        path_snip, body_snip = self._get_vlan_body_on_trunk_int(
            nexus_host, vlanid, intf_type, interface,
            is_native, False, add_mode)
        self.send_edit_string(nexus_host, path_snip, body_snip)

    def create_and_trunk_vlan(self, nexus_host, vlan_id,
                              vlan_name, intf_type,
                              nexus_port, vni,
                              is_native):
        """Create VLAN and trunk it on the specified ports."""

        starttime = time.time()

        self.create_vlan(nexus_host, vlan_id, vlan_name, vni)
        LOG.debug("NexusDriver created VLAN: %s", vlan_id)

        if nexus_port:
            self.send_enable_vlan_on_trunk_int(
                nexus_host, vlan_id,
                intf_type, nexus_port,
                is_native)

        self.capture_and_print_timeshot(
            starttime, "create_all",
            switch=nexus_host)

    def enable_vxlan_feature(self, nexus_host, nve_int_num, src_intf):
        """Enable VXLAN on the switch."""

        # Configure the "feature" commands and NVE interface
        # (without "member" subcommand configuration).
        # The Nexus 9K will not allow the "interface nve" configuration
        # until the "feature nv overlay" command is issued and installed.
        # To get around the N9K failing on the "interface nve" command
        # send the two XML snippets down separately.

        starttime = time.time()

        ## Do CLI 'feature nv overlay'
        self.send_edit_string(nexus_host, snipp.PATH_VXLAN_STATE,
                              (snipp.BODY_VXLAN_STATE % "enabled"))

        # Do CLI 'feature vn-segment-vlan-based'
        self.send_edit_string(nexus_host, snipp.PATH_VNSEG_STATE,
                              (snipp.BODY_VNSEG_STATE % "enabled"))

        # Do CLI 'int nve1' to Create nve1
        self.send_edit_string(
            nexus_host,
            (snipp.PATH_NVE_CREATE % nve_int_num),
            (snipp.BODY_NVE_CREATE % nve_int_num))

        # Do CLI 'no shut
        #         source-interface loopback %s'
        # beneath int nve1
        self.send_edit_string(
            nexus_host,
            (snipp.PATH_NVE_CREATE % nve_int_num),
            (snipp.BODY_NVE_ADD_LOOPBACK % ("enabled", src_intf)))
        self.capture_and_print_timeshot(
            starttime, "enable_vxlan",
            switch=nexus_host)

    def disable_vxlan_feature(self, nexus_host):
        """Disable VXLAN on the switch."""

        # Removing the "feature nv overlay" configuration also
        # removes the "interface nve" configuration.

        starttime = time.time()

        # Do CLI 'no feature nv overlay'
        self.send_edit_string(nexus_host, snipp.PATH_VXLAN_STATE,
                              (snipp.BODY_VXLAN_STATE % "disabled"))

        # Do CLI 'no feature vn-segment-vlan-based'
        self.send_edit_string(nexus_host, snipp.PATH_VNSEG_STATE,
                              (snipp.BODY_VNSEG_STATE % "disabled"))

        self.capture_and_print_timeshot(
            starttime, "disable_vxlan",
            switch=nexus_host)

    def create_nve_member(self, nexus_host, nve_int_num, vni, mcast_group):
        """Add a member configuration to the NVE interface."""

        # Do CLI [no] member vni %s mcast-group %s
        # beneath int nve1

        starttime = time.time()

        path = snipp.PATH_VNI_UPDATE % (nve_int_num, vni)
        body = snipp.BODY_VNI_UPDATE % (vni, vni, vni, mcast_group)
        self.send_edit_string(nexus_host, path, body)

        self.capture_and_print_timeshot(
            starttime, "create_nve",
            switch=nexus_host)

    def delete_nve_member(self, nexus_host, nve_int_num, vni):
        """Delete a member configuration on the NVE interface."""

        starttime = time.time()

        path_snip = snipp.PATH_VNI_UPDATE % (nve_int_num, vni)
        self.client.rest_delete(path_snip, nexus_host)

        self.capture_and_print_timeshot(
            starttime, "delete_nve",
            switch=nexus_host)
