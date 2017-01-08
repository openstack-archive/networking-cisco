# Copyright 2017 Cisco Systems.
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

"""
This file contains the implementation of Topology Discovery of servers and
their associated leaf switches using Open source implementation of LLDP.
www.open-lldp.org
"""

from networking_cisco._i18n import _LE

from networking_cisco.apps.saf.agent.topo_disc import (
    topo_disc_constants as constants)
from networking_cisco.apps.saf.agent.topo_disc import pub_lldp_api as pub_lldp
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import dfa_sys_lib as sys_utils
from networking_cisco.apps.saf.common import utils

LOG = logging.getLogger(__name__)


class TopoIntfAttr(object):

    """Class that stores the interface attributes. """

    def __init__(self, protocol_interface, phy_interface):
        """Class Init. """
        self.init_params(protocol_interface, phy_interface)

    def init_params(self, protocol_interface, phy_interface):
        """Initializing parameters. """
        self.lldp_cfgd = False
        self.local_intf = protocol_interface
        self.phy_interface = phy_interface
        self.remote_evb_cfgd = False
        self.remote_evb_mode = None
        self.remote_mgmt_addr = None
        self.remote_system_desc = None
        self.remote_system_name = None
        self.remote_port = None
        self.remote_chassis_id_mac = None
        self.remote_port_id_mac = None
        self.local_evb_cfgd = False
        self.local_evb_mode = None
        self.local_mgmt_address = None
        self.local_system_desc = None
        self.local_system_name = None
        self.local_port = None
        self.local_chassis_id_mac = None
        self.local_port_id_mac = None
        self.db_retry_status = False
        self.topo_send_cnt = 0
        self.bond_interface = None
        self.bond_member_ports = None

    def update_lldp_status(self, status):
        """Update the LLDP cfg status. """
        self.lldp_cfgd = status

    def cmp_update_bond_intf(self, bond_interface):
        """Update the bond interface and its members.

        Update the bond interface, if this interface is a part of bond
        Return True if there's a change.
        """
        if bond_interface != self.bond_interface:
            self.bond_interface = bond_interface
            self.bond_member_ports = sys_utils.get_member_ports(bond_interface)
            return True
        return False

    def get_lldp_status(self):
        """Retrieve the LLDP cfg status. """
        return self.lldp_cfgd

    def get_db_retry_status(self):
        """Retrieve the RPC retru status.

        This retrieves the number of times RPC was retried with the server.
        """
        return self.db_retry_status

    def get_phy_interface(self):
        """Retrieves the physical interface. """
        return self.phy_interface

    def store_db_retry_status(self, status):
        """This stores the number of times RPC was retried with the server. """
        self.db_retry_status = status

    def get_topo_disc_send_cnt(self):
        """Retrieve the topology status send count for this interface. """
        return self.topo_send_cnt

    def incr_topo_disc_send_cnt(self):
        """Increment the topology status send count for this interface. """
        self.topo_send_cnt += 1

    def reset_topo_disc_send_cnt(self):
        """Reset the topology status send count for this interface. """
        self.topo_send_cnt = 0

    def remote_evb_mode_uneq_store(self, remote_evb_mode):
        """Saves the EVB mode, if it is not the same as stored. """
        if remote_evb_mode != self.remote_evb_mode:
            self.remote_evb_mode = remote_evb_mode
            return True
        return False

    def remote_evb_cfgd_uneq_store(self, remote_evb_cfgd):
        """This saves the EVB cfg, if it is not the same as stored. """
        if remote_evb_cfgd != self.remote_evb_cfgd:
            self.remote_evb_cfgd = remote_evb_cfgd
            return True
        return False

    def remote_mgmt_addr_uneq_store(self, remote_mgmt_addr):
        """This function saves the MGMT address, if different from stored. """
        if remote_mgmt_addr != self.remote_mgmt_addr:
            self.remote_mgmt_addr = remote_mgmt_addr
            return True
        return False

    def remote_sys_desc_uneq_store(self, remote_system_desc):
        """This function saves the system desc, if different from stored. """
        if remote_system_desc != self.remote_system_desc:
            self.remote_system_desc = remote_system_desc
            return True
        return False

    def remote_sys_name_uneq_store(self, remote_system_name):
        """This function saves the system name, if different from stored. """
        if remote_system_name != self.remote_system_name:
            self.remote_system_name = remote_system_name
            return True
        return False

    def remote_port_uneq_store(self, remote_port):
        """This function saves the port, if different from stored. """
        if remote_port != self.remote_port:
            self.remote_port = remote_port
            return True
        return False

    def remote_chassis_id_mac_uneq_store(self, remote_chassis_id_mac):
        """This function saves the Chassis MAC, if different from stored. """
        if remote_chassis_id_mac != self.remote_chassis_id_mac:
            self.remote_chassis_id_mac = remote_chassis_id_mac
            return True
        return False

    def remote_port_id_mac_uneq_store(self, remote_port_id_mac):
        """This function saves the port MAC, if different from stored. """
        if remote_port_id_mac != self.remote_port_id_mac:
            self.remote_port_id_mac = remote_port_id_mac
            return True
        return False


class TopoDiscPubApi(object):
    topo_intf_obj_dict = {}

    @classmethod
    def store_obj(cls, intf, obj):
        """Stores the topo object. """
        cls.topo_intf_obj_dict[intf] = obj

    @classmethod
    def get_lldp_status(cls, intf):
        """Retrieves the LLDP status. """
        if intf not in cls.topo_intf_obj_dict:
            LOG.error(_LE("Interface %s not configured at all"), intf)
            return False
        intf_obj = cls.topo_intf_obj_dict.get(intf)
        return intf_obj.get_lldp_status()


class TopoDisc(TopoDiscPubApi):

    """Topology Discovery Top level class once. """

    def __init__(self, cb, root_helper, intf_list=None, all_intf=True):
        """Initialization routine, to configure interface.

        Also create the periodic task.
        cb => Callback in case any of the interface TLV changes.
        intf_list => List of interfaces to be LLDP enabled and monitored.
        all_intf => Boolean that signifies if all physical interfaces are to
        be monitored. intf_list will be None, if this variable is True.
        """
        self.pub_lldp = pub_lldp.LldpApi(root_helper)
        self._init_cfg_interfaces(cb, intf_list, all_intf)
        per_task = utils.PeriodicTask(constants.PERIODIC_TASK_INTERVAL,
                                      self.periodic_discovery_task)
        per_task.run()

    def _init_cfg_interfaces(self, cb, intf_list=None, all_intf=True):
        """Configure the interfaces during init time. """
        if not all_intf:
            self.intf_list = intf_list
        else:
            self.intf_list = sys_utils.get_all_run_phy_intf()
        self.cb = cb
        self.intf_attr = {}
        self.cfg_lldp_interface_list(self.intf_list)

    def cfg_intf(self, protocol_interface, phy_interface=None):
        """Called by application to add an interface to the list. """
        self.intf_list.append(protocol_interface)
        self.cfg_lldp_interface(protocol_interface, phy_interface)

    def uncfg_intf(self, intf):
        """Called by application to remove an interface to the list.

        From an applications perspective, it makes sense to have this function.
        But, here no action can be taken for the following reasons, but just
        having it as a place-holder for tomorrow.
        => Can't remove interface from the list since DB in server may appear
           stale.
           self.intf_list.remove(intf)
        => One can just remove the interface DB, but need to retry that till
           it succeeds, so it has to be in periodic loop.
        => So, currently leaving it as is, since LLDP frames won't be obtained
           over the bridge, the periodic handler will automatically remove the
           DB for this interface from server
        """
        pass

    def create_attr_obj(self, protocol_interface, phy_interface):
        """Creates the local interface attribute object and stores it. """
        self.intf_attr[protocol_interface] = TopoIntfAttr(
            protocol_interface, phy_interface)
        self.store_obj(protocol_interface, self.intf_attr[protocol_interface])

    def get_attr_obj(self, intf):
        """Retrieve the interface object. """
        return self.intf_attr[intf]

    def cmp_store_tlv_params(self, intf, tlv_data):
        """Compare and store the received TLV.

        Compares the received TLV with stored TLV. Store the new TLV if it is
        different.
        """
        flag = False
        attr_obj = self.get_attr_obj(intf)
        remote_evb_mode = self.pub_lldp.get_remote_evb_mode(tlv_data)
        if attr_obj.remote_evb_mode_uneq_store(remote_evb_mode):
            flag = True
        remote_evb_cfgd = self.pub_lldp.get_remote_evb_cfgd(tlv_data)
        if attr_obj.remote_evb_cfgd_uneq_store(remote_evb_cfgd):
            flag = True
        remote_mgmt_addr = self.pub_lldp.get_remote_mgmt_addr(tlv_data)
        if attr_obj.remote_mgmt_addr_uneq_store(remote_mgmt_addr):
            flag = True
        remote_sys_desc = self.pub_lldp.get_remote_sys_desc(tlv_data)
        if attr_obj.remote_sys_desc_uneq_store(remote_sys_desc):
            flag = True
        remote_sys_name = self.pub_lldp.get_remote_sys_name(tlv_data)
        if attr_obj.remote_sys_name_uneq_store(remote_sys_name):
            flag = True
        remote_port = self.pub_lldp.get_remote_port(tlv_data)
        if attr_obj.remote_port_uneq_store(remote_port):
            flag = True
        remote_chassis_id_mac = self.pub_lldp.\
            get_remote_chassis_id_mac(tlv_data)
        if attr_obj.remote_chassis_id_mac_uneq_store(remote_chassis_id_mac):
            flag = True
        remote_port_id_mac = self.pub_lldp.get_remote_port_id_mac(tlv_data)
        if attr_obj.remote_port_id_mac_uneq_store(remote_port_id_mac):
            flag = True
        return flag

    def cfg_lldp_interface(self, protocol_interface, phy_interface=None):
        """Cfg LLDP on interface and create object. """
        if phy_interface is None:
            phy_interface = protocol_interface
        self.create_attr_obj(protocol_interface, phy_interface)
        ret = self.pub_lldp.enable_lldp(protocol_interface)
        attr_obj = self.get_attr_obj(protocol_interface)
        attr_obj.update_lldp_status(ret)

    def cfg_lldp_interface_list(self, intf_list):
        """This routine configures LLDP on the given interfaces list. """
        for intf in intf_list:
            self.cfg_lldp_interface(intf)

    def periodic_discovery_task(self):
        """Periodic task that checks the interface TLV attributes. """
        try:
            self._periodic_task_int()
        except Exception as exc:
            LOG.error(_LE("Exception caught in periodic discovery task %s"),
                      str(exc))

    def _check_bond_interface_change(self, phy_interface, attr_obj):
        """Check if there's any change in bond interface.

        First check if the interface passed itself is a bond-interface and then
        retrieve the member list and compare.
        Next, check if the interface passed is a part of the bond interface and
        then retrieve the member list and compare.
        """
        bond_phy = sys_utils.get_bond_intf(phy_interface)
        if sys_utils.is_intf_bond(phy_interface):
            bond_intf = phy_interface
        else:
            bond_intf = bond_phy
        # This can be an addition or removal of the interface to a bond.
        bond_intf_change = attr_obj.cmp_update_bond_intf(bond_intf)
        return bond_intf_change

    def _periodic_task_int(self):
        """Internal periodic discovery task routine to check TLV attributes.

        This routine retrieves the LLDP TLC's on all its configured interfaces.
        If the retrieved TLC is different than the stored TLV, it invokes the
        callback.
        """
        for intf in self.intf_list:
            attr_obj = self.get_attr_obj(intf)
            status = attr_obj.get_lldp_status()
            if not status:
                ret = self.pub_lldp.enable_lldp(intf)
                attr_obj.update_lldp_status(ret)
                continue
            bond_intf_change = self._check_bond_interface_change(
                attr_obj.get_phy_interface(), attr_obj)
            tlv_data = self.pub_lldp.get_lldp_tlv(intf)
            # This should take care of storing the information of interest
            if self.cmp_store_tlv_params(intf, tlv_data) or (
                attr_obj.get_db_retry_status() or bond_intf_change or (
                    attr_obj.get_topo_disc_send_cnt() > (
                    constants.TOPO_DISC_SEND_THRESHOLD))):
                # Passing the interface attribute object to CB
                ret = self.cb(intf, attr_obj)
                status = not ret
                attr_obj.store_db_retry_status(status)
                attr_obj.reset_topo_disc_send_cnt()
            else:
                attr_obj.incr_topo_disc_send_cnt()
