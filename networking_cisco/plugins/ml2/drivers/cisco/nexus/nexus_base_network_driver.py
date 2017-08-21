# Copyright (c) 2013-2016 Cisco Systems, Inc.
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
Base class driver for SSH and RESTAPI Client.  Some APIs are
called by upper layer code but only apply to either RESTAPIs drivers
or SSH drivers.  Having base class which simply performs 'pass'
is necessary so these two drivers get required actions without
breaking the other driver. Drivers defined in this base are
mostly those called externally.
"""

import os
import threading
import time

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class CiscoNexusBaseDriver(object):
    """Nexus Driver Base Class."""
    def __init__(self, nexus_switches):
        self.nexus_switches = nexus_switches
        self.time_stats = {}

    def keep_ssh_caching(self):
        pass

    def init_ssh_caching(self):
        pass

    def capture_and_print_timeshot(self, start_time, which,
                                   other=99, switch="0.0.0.0"):
        """Determine delta, keep track, and print results."""

        curr_timeout = time.time() - start_time
        if which in self.time_stats:
            self.time_stats[which]["total_time"] += curr_timeout
            self.time_stats[which]["total_count"] += 1
            if (curr_timeout < self.time_stats[which]["min"]):
                self.time_stats[which]["min"] = curr_timeout
            if (curr_timeout > self.time_stats[which]["max"]):
                self.time_stats[which]["max"] = curr_timeout
        else:
            self.time_stats[which] = {
                "total_time": curr_timeout,
                "total_count": 1,
                "min": curr_timeout,
                "max": curr_timeout}
        LOG.debug("NEXUS_TIME_STATS %(switch)s, pid %(pid)d, tid %(tid)d: "
                  "%(which)s_timeout %(curr)f count %(count)d "
                  "average %(ave)f other %(other)d min %(min)f max %(max)f",
                  {'switch': switch,
                  'pid': os.getpid(),
                  'tid': threading.current_thread().ident,
                  'which': which,
                  'curr': curr_timeout,
                  'count': self.time_stats[which]["total_count"],
                  'ave': (self.time_stats[which]["total_time"] /
                          self.time_stats[which]["total_count"]),
                  'other': other,
                  'min': self.time_stats[which]["min"],
                  'max': self.time_stats[which]["max"]})

    def close_session(self, nexus_host):
        pass

    def get_interface_switch(self, nexus_host,
                             intf_type, interface):
        """Get the interface data from host.

        :param nexus_host: IP address of Nexus switch
        :param intf_type:  String which specifies interface type.
                           example: ethernet
        :param interface:  String indicating which interface.
                           example: 1/19
        :returns: response
        """
        return None

    def initialize_all_switch_interfaces(self, interfaces,
                                         switch_ip=None, replay=True):
        """Configure Nexus interface and get port channel number.

        :param interfaces:  List of interfaces for a given switch.
                            ch_grp can be altered as last arg
                            to each interface. If no ch_grp,
                            this arg will be zero.
        :param switch_ip: IP address of Nexus switch
        :param replay: Whether in replay path
        """
        pass

    def get_nexus_type(self, nexus_host):
        """Given the nexus host, get the type of Nexus switch.

        :param nexus_host: IP address of Nexus switch
        :returns: Nexus type
        """
        return None

    def set_all_vlan_states(self, nexus_host, vlanid_range):
        """Set the VLAN states to active."""
        pass

    def start_create_vlan(self):
        """Returns an XML snippet for start of create VLAN."""
        return None, ''

    def get_create_vlan(self, nexus_host, vlanid, vni, conf_str):
        """Returns an XML snippet for create VLAN."""
        return conf_str

    def end_create_vlan(self, conf_str):
        """Returns an XML snippet for terminate of create VLAN."""
        return conf_str

    def create_vlan(self, nexus_host, vlanid, vni):
        """Create a VLAN on a Nexus Switch.

        Creates a VLAN given the VLAN ID and possible VxLAN ID.
        """
        pass

    def delete_vlan(self, nexus_host, vlanid):
        """Delete a VLAN on Nexus Switch given the VLAN ID."""
        pass

    def disable_vlan_on_trunk_int(self, nexus_host, vlanid, intf_type,
                                  interface, is_native):
        """Disable a VLAN on a trunk interface."""
        pass

    def send_edit_string(self, nexus_host, path, confstr,
                         check_to_close_session=True):
        """Sends any XML snippet to Nexus switch."""
        pass

    def send_enable_vlan_on_trunk_int(self, nexus_host, vlanid, intf_type,
                                      interface, is_native):
        """Gathers and sends an interface trunk XML snippet."""
        pass

    def create_and_trunk_vlan(self, nexus_host, vlan_id, intf_type,
                              nexus_port, vni, is_native):
        """Create VLAN and trunk it on the specified ports."""
        pass

    def enable_vxlan_feature(self, nexus_host, nve_int_num, src_intf):
        """Enable VXLAN on the switch."""
        pass

    def disable_vxlan_feature(self, nexus_host):
        """Disable VXLAN on the switch."""
        pass

    def create_nve_member(self, nexus_host, nve_int_num, vni, mcast_group):
        """Add a member configuration to the NVE interface."""
        pass

    def delete_nve_member(self, nexus_host, nve_int_num, vni):
        """Delete a member configuration on the NVE interface."""
        pass
