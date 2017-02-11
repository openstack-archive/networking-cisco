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


"""This file contains the mixin class implementation of OVS extensions for VDP.
VDP is a part of LLDP Agent Daemon (lldpad). For more information on VDP,
pls visit http://www.ieee802.org/1/pages/802.1bg.html
"""
import six

from networking_cisco._i18n import _LE, _LI

from networking_cisco.apps.saf.agent.vdp import lldpad
from networking_cisco.apps.saf.agent.vdp import vdp_constants as constants
from networking_cisco.apps.saf.common import constants as cconstants
from networking_cisco.apps.saf.common import dfa_exceptions as dfae
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import dfa_sys_lib as ovs_lib
from networking_cisco.apps.saf.common import utils as sys_utils
from neutron.agent.linux import ip_lib

LOG = logging.getLogger(__name__)


def is_uplink_already_added(root_helper, br_ex, port_name):
    br, port_exist = ovs_lib.port_exists_glob(root_helper, port_name)
    if not port_exist:
        return False
    else:
        if br == br_ex:
            return True
        else:
            LOG.error(_LE("Port %(port)s added to wrong bridge %(br)s "
                      "Given %(br_ex)s"), {'port': port_name, 'br': br,
                                           'br_ex': br_ex})
            return False


def delete_uplink_and_flows(root_helper, br_ex, port_name):
    glob_delete_vdp_flows(br_ex, root_helper)
    port_exist = is_uplink_already_added(root_helper, br_ex, port_name)
    if port_exist:
        ovs_lib.delete_port_glob(root_helper, br_ex, port_name)
        lldp_ovs_veth_str = constants.LLDPAD_OVS_VETH_PORT + port_name
        ovs_lib.delete_port_glob(root_helper, br_ex, lldp_ovs_veth_str)


def glob_delete_vdp_flows(br_ex, root_helper):
    br = ovs_lib.OVSBridge(br_ex, root_helper=root_helper)
    br.delete_flows(dl_dst=constants.NCB_DMAC, dl_type=constants.LLDP_ETYPE)
    br.delete_flows(dl_dst=constants.NCB_DMAC,
                    dl_type=constants.VDP22_ETYPE)


def is_bridge_present(br, root_helper):
    ovs_bridges = ovs_lib.get_bridges(root_helper)
    if br in ovs_bridges:
        return True
    else:
        return False


class LocalVlan(object):

    def __init__(self, vlan, segmentation_id):
        self.vlan = vlan
        self.segmentation_id = segmentation_id
        self.late_binding_vlan = 0
        self.lvid = cconstants.INVALID_VLAN
        self.port_uuid_list = {}
        # Generally for the same network, there will be only one VDP VLAN
        # However, Inconsistencies can arise. This dictionary is to keep track
        # of all VLAN's floating around for different vNIC's of the same
        # network.
        self.port_vdp_vlan_dict = {}

    def set_port_uuid(self, port_uuid, vdp_vlan, fail_reason):
        if port_uuid not in self.port_uuid_list:
            port_vlan_set = [port_uuid, vdp_vlan, fail_reason]
            self.port_uuid_list[port_uuid] = port_vlan_set
            self.set_port_vlan(vdp_vlan)

    def set_portid_fail_reason(self, port_id, fail_reason):
        if port_id not in self.port_uuid_list:
            LOG.error(_LE("Unable to set fail_reason, port_uuid %s not "
                          "created"), port_id)
            return
        self.port_uuid_list[port_id][2] = fail_reason

    def get_portid_fail_reason(self, port_id):
        if port_id not in self.port_uuid_list:
            return None
        return self.port_uuid_list[port_id][2]

    def get_portid_vlan(self, port_id):
        if port_id not in self.port_uuid_list:
            return cconstants.INVALID_VLAN
        return self.port_uuid_list[port_id][1]

    def set_portid_vlan(self, port_id, new_vlan):
        self.port_uuid_list[port_id][1] = new_vlan

    def set_port_vlan(self, vdp_vlan):
        if not ovs_lib.is_valid_vlan_tag(vdp_vlan):
            LOG.info(_LI("Passed Invalid vlan in set_port_vlan"))
            return
        if vdp_vlan not in self.port_vdp_vlan_dict:
            self.port_vdp_vlan_dict[vdp_vlan] = 0
        self.port_vdp_vlan_dict[vdp_vlan] += 1

    def reset_port_vlan(self, vdp_vlan):
        if not ovs_lib.is_valid_vlan_tag(vdp_vlan):
            LOG.info(_LI("Passed Invalid vlan in reset_port_vlan"))
            return
        if vdp_vlan not in self.port_vdp_vlan_dict:
            LOG.error(_LE("wrongly called, no VLAN's present"))
            self.port_vdp_vlan_dict[vdp_vlan] = 0
        else:
            self.port_vdp_vlan_dict[vdp_vlan] -= 1
            if not self.port_vdp_vlan_dict[vdp_vlan]:
                del self.port_vdp_vlan_dict[vdp_vlan]

    def decr_reset_vlan(self, port_uuid, new_vlan):
        vlan = self.get_portid_vlan(port_uuid)
        self.reset_port_vlan(vlan)
        self.set_portid_vlan(port_uuid, new_vlan)
        self.set_port_vlan(new_vlan)

    def set_fail_reason(self, port_uuid, fail_reason):
        self.set_portid_fail_reason(port_uuid, fail_reason)

    def any_valid_vlan(self):
        return len(self.port_vdp_vlan_dict) != 0

    def any_consistent_vlan(self):
        if len(self.port_vdp_vlan_dict) != 1:
            return False
        for vlan in six.iterkeys(self.port_vdp_vlan_dict):
            return vlan
        return self.port_vdp_vlan_dict.keys()[0]


class OVSNeutronVdp(object):

    """Implements the VDP specific changes in OVS.

    Creating the veth pairs, programming the flows for VDP, deleting the VDP
    specific flows, communicating with VDP (lldpad) daemon using lldpad class
    are some of the functionality provided by this class.
    """

    def __init__(self, uplink, integ_br, ext_br, root_helper,
                 vdp_vlan_cb, vdp_mode=constants.VDP_SEGMENT_MODE):
        # self.root_helper = 'sudo'
        self.root_helper = root_helper
        self.uplink = uplink
        self.integ_br = integ_br
        self.ext_br = ext_br
        self.vdp_mode = vdp_mode
        self.local_vlan_map = {}
        self.lldpad_info = {}
        self.lldp_local_veth_port = None
        self.lldp_ovs_veth_port = None
        self.ovs_vdp_lock = sys_utils.lock()
        self.phy_peer_port_num = cconstants.INVALID_OFPORT
        self.int_peer_port_num = cconstants.INVALID_OFPORT
        self.int_peer_port = None
        self.phy_peer_port = None
        self.ext_br_obj = None
        self.integ_br_obj = None
        self.vdp_vlan_cb = vdp_vlan_cb
        self.uplink_fail_reason = ""
        self.setup_lldpad = self.setup_lldpad_ports()
        if not self.setup_lldpad:
            return
        flow_check_periodic_task = sys_utils.PeriodicTask(
            cconstants.FLOW_CHECK_INTERVAL, self._flow_check_handler)
        self.flow_check_periodic_task = flow_check_periodic_task
        flow_check_periodic_task.run()

    def is_lldpad_setup_done(self):
        return self.setup_lldpad

    def _check_bridge_flow(self, flow, out_vlan, in_vlan):
        out_vlan_flow_str = 'dl_vlan=' + str(out_vlan)
        in_vlan_flow_str = 'actions=mod_vlan_vid:' + str(in_vlan)
        flow_str = out_vlan_flow_str + ' ' + in_vlan_flow_str
        flow_partition = flow.partition(flow_str)[1]
        return len(flow_partition) != 0
        if not len(flow_partition):
            return False
        return True

    def _flow_check_handler_internal(self):
        """Periodic handler to check if installed flows are present.

        This handler runs periodically to check if installed flows are present.
        This function cannot detect and delete the stale flows, if present.
        It requires more complexity to delete stale flows. Generally, stale
        flows are not present. So, that logic is not put here.
        """
        integ_flow = self.integ_br_obj.dump_flows_for(
            in_port=self.int_peer_port_num)
        ext_flow = self.ext_br_obj.dump_flows_for(
            in_port=self.phy_peer_port_num)
        for net_uuid, lvm in six.iteritems(self.local_vlan_map):
            vdp_vlan = lvm.any_consistent_vlan()
            flow_required = False
            if not (vdp_vlan and ovs_lib.is_valid_vlan_tag(vdp_vlan)):
                return
            if not self._check_bridge_flow(integ_flow, vdp_vlan, lvm.lvid):
                LOG.error(_LE("Flow for VDP Vlan %(vdp_vlan)s, Local vlan "
                              "%(lvid)s not present on Integ bridge"),
                          {'vdp_vlan': vdp_vlan, 'lvid': lvm.lvid})
                flow_required = True
            if not self._check_bridge_flow(ext_flow, lvm.lvid, vdp_vlan):
                LOG.error(_LE("Flow for VDP Vlan %(vdp_vlan)s, Local vlan "
                              "%(lvid)s not present on External bridge"),
                          {'vdp_vlan': vdp_vlan, 'lvid': lvm.lvid})
                flow_required = True
            if flow_required:
                LOG.info(_LI("Programming flows for lvid %(lvid)s vdp vlan"
                             " %(vdp)s"),
                         {'lvid': lvm.lvid, 'vdp': vdp_vlan})
                self.program_vm_ovs_flows(lvm.lvid, 0, vdp_vlan)

    def _flow_check_handler(self):
        """Top level routine to check OVS flow consistency. """
        LOG.info(_LI("In _flow_check_handler"))
        try:
            with self.ovs_vdp_lock:
                self._flow_check_handler_internal()
        except Exception as e:
            LOG.error(_LE("Exception in _flow_check_handler_internal %s"),
                      str(e))

    def program_vdp_flows(self, lldp_ovs_portnum, phy_port_num):
        br = self.ext_br_obj
        high_prio = constants.VDP_FLOW_PRIO
        br.add_flow(priority=high_prio, in_port=lldp_ovs_portnum,
                    dl_dst=constants.NCB_DMAC, dl_type=constants.LLDP_ETYPE,
                    actions="output:%s" % phy_port_num)
        br.add_flow(priority=high_prio, in_port=phy_port_num,
                    dl_dst=constants.NCB_DMAC, dl_type=constants.LLDP_ETYPE,
                    actions="output:%s" % lldp_ovs_portnum)
        br.add_flow(priority=high_prio, in_port=lldp_ovs_portnum,
                    dl_dst=constants.NCB_DMAC, dl_type=constants.VDP22_ETYPE,
                    actions="output:%s" % phy_port_num)
        br.add_flow(priority=high_prio, in_port=phy_port_num,
                    dl_dst=constants.NCB_DMAC, dl_type=constants.VDP22_ETYPE,
                    actions="output:%s" % lldp_ovs_portnum)

    def delete_vdp_flows(self):
        br = self.ext_br_obj
        br.delete_flows(dl_dst=constants.NCB_DMAC,
                        dl_type=constants.LLDP_ETYPE)
        br.delete_flows(dl_dst=constants.NCB_DMAC,
                        dl_type=constants.VDP22_ETYPE)

    def clear_obj_params(self):
        LOG.debug("Clearing Uplink Params")
        self.flow_check_periodic_task.stop()
        # How is the IP link/veth going to be removed?? fixme(padkrish)
        # IF the veth is removed, no need to unconfigure lldp/evb
        self.delete_vdp_flows()
        lldp_ovs_veth_str = constants.LLDPAD_OVS_VETH_PORT + self.uplink
        br = self.ext_br_obj
        br.delete_port(lldp_ovs_veth_str)
        br.delete_port(self.uplink)
        self.lldpad_info.clear_uplink()
        del self.lldpad_info
        # It's ok if the veth remains even if the uplink changes, worst case
        # the number of veth's will be the number of physical server ports.
        # It's not a common occurrence for uplink to change, even if so
        # the unused veth can be removed manually.
        # Reason for not removing it is the same as given in function below.
        # ip_lib.IPDevice(lldp_ovs_veth_str, self.root_helper).link.delete()

    def program_vm_ovs_flows(self, lvid, old_vlan, new_vlan):
        if old_vlan:
            # outbound
            self.ext_br_obj.delete_flows(in_port=self.phy_peer_port_num,
                                         dl_vlan=lvid)
            # inbound
            self.integ_br_obj.delete_flows(in_port=self.int_peer_port_num,
                                           dl_vlan=old_vlan)
        if new_vlan:
            # outbound
            self.ext_br_obj.add_flow(priority=4,
                                     in_port=self.phy_peer_port_num,
                                     dl_vlan=lvid,
                                     actions="mod_vlan_vid:%s,normal" %
                                             new_vlan)
            # inbound
            self.integ_br_obj.add_flow(priority=3,
                                       in_port=self.int_peer_port_num,
                                       dl_vlan=new_vlan,
                                       actions="mod_vlan_vid:%s,normal" % lvid)

    def gen_veth_str(self, const_str, intf_str):
        """Generate a veth string.

        Concatenates the constant string with remaining available length
        of interface string from trailing position.
        """
        avl_len = constants.MAX_VETH_NAME - len(const_str)
        if avl_len <= 0:
            LOG.error(_LE("veth string name too short"))
            raise dfae.DfaAgentFailed(reason="Veth Unavailable")
        start_pos = len(intf_str) - avl_len
        veth_str = const_str + intf_str[start_pos:]
        return veth_str

    def setup_lldpad_ports(self):
        """Setup the flows for passing LLDP/VDP frames in OVS. """
        # Creating the physical bridge and setting up patch ports is done by
        # OpenStack
        ovs_bridges = ovs_lib.get_bridges(self.root_helper)
        if self.ext_br not in ovs_bridges or self.integ_br not in ovs_bridges:
            self.uplink_fail_reason = cconstants.bridge_not_cfgd_reason % (
                ovs_bridges, self.integ_br, self.ext_br)
            LOG.error(_LE("%s"), self.uplink_fail_reason)
            raise dfae.DfaAgentFailed(reason=self.uplink_fail_reason)
        br = ovs_lib.OVSBridge(self.ext_br, root_helper=self.root_helper)
        self.ext_br_obj = br
        int_br = ovs_lib.OVSBridge(self.integ_br, root_helper=self.root_helper)
        self.integ_br_obj = int_br

        self.phy_peer_port, self.int_peer_port = self.find_interconnect_ports()
        if self.phy_peer_port is None or self.int_peer_port is None:
            self.uplink_fail_reason = cconstants.veth_not_cfgd_reason % (
                self.phy_peer_port, self.int_peer_port)
            LOG.error(_LE("%s"), self.uplink_fail_reason)
            raise dfae.DfaAgentFailed(reason=self.uplink_fail_reason)
        lldp_ovs_veth_str = constants.LLDPAD_OVS_VETH_PORT + self.uplink
        if len(lldp_ovs_veth_str) > constants.MAX_VETH_NAME:
            lldp_ovs_veth_str = self.gen_veth_str(
                constants.LLDPAD_OVS_VETH_PORT,
                self.uplink)
        lldp_loc_veth_str = constants.LLDPAD_LOC_VETH_PORT + self.uplink
        if len(lldp_loc_veth_str) > constants.MAX_VETH_NAME:
            lldp_loc_veth_str = self.gen_veth_str(
                constants.LLDPAD_LOC_VETH_PORT,
                self.uplink)
        ip_wrapper = ip_lib.IPWrapper()
        self.delete_vdp_flows()
        br.delete_port(lldp_ovs_veth_str)
        if ip_lib.device_exists(lldp_ovs_veth_str):
            # What about OVS restart cases fixme(padkrish)

            # IMPORTANT.. The link delete should be done only for non-restart
            # cases. Otherwise, The MAC address of the veth interface changes
            # for every delete/create. So, if lldpad has the association sent
            # already, retriggering it will make the ASSOC appear as coming
            # from another station and more than one VSI instance will appear
            # at the Leaf. Deleting the assoc and creating the assoc for new
            # veth is not optimal. fixme(padkrish)
            # ip_lib.IPDevice(lldp_ovs_veth_str,self.root_helper).link.delete()
            lldp_loc_veth = ip_wrapper.device(lldp_loc_veth_str)
            lldp_ovs_veth = ip_wrapper.device(lldp_ovs_veth_str)
        else:
            # fixme(padkrish) Due to above reason, do the vethcreate below only
            # if it doesn't exist and not deleted.
            lldp_loc_veth, lldp_ovs_veth = (
                ip_wrapper.add_veth(lldp_loc_veth_str,
                                    lldp_ovs_veth_str))
        if not br.port_exists(self.uplink):
            phy_port_num = br.add_port(self.uplink)
        else:
            phy_port_num = br.get_port_ofport(self.uplink)
        if phy_port_num == cconstants.INVALID_OFPORT:
            self.uplink_fail_reason = cconstants.invalid_uplink_ofport_reason
            LOG.error(_LE("%s"), self.uplink_fail_reason)
            return False
        if not br.port_exists(lldp_ovs_veth_str):
            lldp_ovs_portnum = br.add_port(lldp_ovs_veth)
        else:
            lldp_ovs_portnum = br.get_port_ofport(lldp_ovs_veth)
        if lldp_ovs_portnum == cconstants.INVALID_OFPORT:
            self.uplink_fail_reason = cconstants.lldp_ofport_not_detect_reason
            LOG.error(_LE("%s"), self.uplink_fail_reason)
            return False
        lldp_loc_veth.link.set_up()
        lldp_ovs_veth.link.set_up()
        # What about OVS restart cases fixme(padkrish)
        self.program_vdp_flows(lldp_ovs_portnum, phy_port_num)

        self.phy_peer_port_num = br.get_port_ofport(self.phy_peer_port)
        self.int_peer_port_num = int_br.get_port_ofport(self.int_peer_port)
        if (self.phy_peer_port_num == cconstants.INVALID_OFPORT or
                self.int_peer_port_num == cconstants.INVALID_OFPORT):
            self.uplink_fail_reason = cconstants.invalid_peer_ofport_reason % (
                self.phy_peer_port_num, self.int_peer_port_num)
            LOG.error(_LE("%s"), self.uplink_fail_reason)
            return False
        self.lldpad_info = (lldpad.LldpadDriver(lldp_loc_veth_str, self.uplink,
                                                self.root_helper))
        ret = self.lldpad_info.enable_evb()
        if not ret:
            self.uplink_fail_reason = cconstants.evb_cfg_fail_reason
            LOG.error(_LE("%s"), self.uplink_fail_reason)
            return False
        self.lldp_local_veth_port = lldp_loc_veth_str
        self.lldp_ovs_veth_port = lldp_ovs_veth_str
        LOG.info(_LI("Setting up lldpad ports complete"))
        return True

    def get_uplink_fail_reason(self):
        return self.uplink_fail_reason

    def get_lldp_local_bridge_port(self):
        return self.lldp_local_veth_port

    def get_lldp_ovs_bridge_port(self):
        return self.lldp_ovs_veth_port

    def find_interconnect_ports(self):
        """Find the internal veth or patch ports. """

        phy_port_list = self.ext_br_obj.get_port_name_list()
        int_port_list = self.integ_br_obj.get_port_name_list()
        for port in phy_port_list:
            # Use get Interface  xxx type
            is_patch = ovs_lib.is_patch(self.root_helper, port)
            if is_patch:
                # Get the peer for this patch
                peer_port = ovs_lib.get_peer(self.root_helper, port)
                if peer_port in int_port_list:
                    return port, peer_port
        # A solution is needed for veth pairs also, fixme(padkrish)
        # ip_wrapper.get_devices() returns all the devices
        # Pick the ones whose type is veth (?) and get the other pair
        # Combination of "ethtool -S xxx" command and "ip tool" command.
        return None, None

    def port_down_segment_mode(self, lldpad_port, port_uuid, mac,
                               net_uuid, segmentation_id, oui):
        lvm = self.local_vlan_map.get(net_uuid)
        if not lvm:
            fail_reason = "Local VLAN Map not available in port_down"
            LOG.error(_LE("%s"), fail_reason)
            return {'result': False, 'fail_reason': fail_reason}
        if port_uuid not in lvm.port_uuid_list:
            fail_reason = "port_uuid %s not in cache for port_down" % (
                port_uuid)
            LOG.error(_LE("%s"), fail_reason)
            return {'result': False, 'fail_reason': fail_reason}
        vdp_vlan = lvm.late_binding_vlan
        lldpad_port.send_vdp_vnic_down(port_uuid=port_uuid,
                                       vsiid=port_uuid,
                                       gid=segmentation_id,
                                       mac=mac, vlan=vdp_vlan, oui=oui)
        lvm.port_uuid_list.pop(port_uuid, None)
        lvm.reset_port_vlan(vdp_vlan)
        # Check here that if all the VM's in that network has
        # 0 as VLAN (dis-assoc sent by switch, but flow not removed), then
        # also remove the flow by calling unprovision. Do this after the
        # pop instruction above.
        # Check with the late binding vlan, if that still points to
        # old_vlan, remove the flow and make late_binding_vlan as 0
        # late_binding_vlan should reflect the VLAN that is installed
        # for the flow.
        if not lvm.port_uuid_list:
            self.unprovision_vdp_overlay_networks(net_uuid, lvm.lvid,
                                                  vdp_vlan, oui)
            self.local_vlan_map.pop(net_uuid)
            LOG.info(_LI("No valid ports, clearing flows"))
        else:
            # There are ports present in the network case.
            if not lvm.any_valid_vlan():
                # This condition will be hit when there are still ports
                # remaining in the network, but none of them have a valid
                # VLAN. i.e. Dis-assoc sent by switch for all ports except
                # one, vdp_vlan_change will not remove flows, since there's
                # a valid port left with a VLAN. Now, user removes the VM
                # with valid port. Now flow has to be deleted since
                # there's no valid port with a VLAN.
                self.unprovision_vdp_overlay_networks(net_uuid, lvm.lvid,
                                                      vdp_vlan, oui)
                lvm.late_binding_vlan = 0
                LOG.info(_LI("unprovisioned Local %(lvid)s, VDP %(vdp)s VLAN "
                             "since no VM has valid VLAN"),
                         {'lvid': lvm.lvid, 'vdp': vdp_vlan})
            else:
                # There are still valid VLAN's present.
                # Say, out of 3 VM's one VM got a VLAN change due to which
                # the new flow will be programmed according to new vlan.
                # The VM with new VLAN gets deleted.
                # Say, for whatever reason, the other VM's in the 'same'
                # network didn't gets changed to new VLAN.
                # VLAN change function won't be called and so it will
                # be stranded with stale flow unless the below
                # functionality of putting back the old VLAN is there.
                vlan_other = lvm.any_consistent_vlan()
                if vlan_other and ovs_lib.is_valid_vlan_tag(vlan_other) and (
                   vlan_other != lvm.late_binding_vlan):
                    self.program_vm_ovs_flows(lvm.lvid, vdp_vlan, vlan_other)
                    lvm.late_binding_vlan = vlan_other
                    self.vdp_nego_req = True
                    LOG.info(_LI("Reprogrammed old Flows Local %(lvid)s "
                                 "VDP %(vdp)s Other %(other)s VLANs"),
                             {'lvid': lvm.lvid, 'vdp': vdp_vlan,
                              'other': vlan_other})
        return {'result': True, 'fail_reason': None}

    def port_up_segment_mode(self, lldpad_port, port_name, port_uuid, mac,
                             net_uuid, segmentation_id, oui):
        lvm = self.local_vlan_map.get(net_uuid)
        if lvm and lvm.late_binding_vlan and (not lvm.vdp_nego_req):
            vdp_vlan = lvm.late_binding_vlan
            ovs_cb_data = {'obj': self, 'mac': mac,
                           'port_uuid': port_uuid, 'net_uuid': net_uuid}
            vlan, fail_reason = lldpad_port.send_vdp_vnic_up(
                port_uuid=port_uuid, vsiid=port_uuid, gid=segmentation_id,
                mac=mac, vlan=vdp_vlan, oui=oui,
                vsw_cb_fn=self.vdp_vlan_change, vsw_cb_data=ovs_cb_data)
            lvm.set_port_uuid(port_uuid, vdp_vlan, fail_reason)
            return {'result': True, 'fail_reason': fail_reason}
        else:
            int_br = self.integ_br_obj
            lvid = int_br.get_port_vlan_tag(port_name)
            if lvid != cconstants.INVALID_VLAN:
                provision_reply = self.provision_vdp_overlay_networks(
                    port_uuid, mac, net_uuid, segmentation_id, lvid, oui)
                vdp_vlan = provision_reply.get('vdp_vlan')
                if not lvm:
                    lvm = LocalVlan(lvid, segmentation_id)
                    self.local_vlan_map[net_uuid] = lvm
                lvm.lvid = lvid
                # This is just populating the list of ports in a network.
                # The vdp_vlan that's a part of port_list is just for debugging
                # So, it's ok to populate the port UUID list even if VDP VLAN
                # is invalid.
                lvm.set_port_uuid(port_uuid, vdp_vlan,
                                  provision_reply.get('fail_reason'))
                if vdp_vlan != cconstants.INVALID_VLAN:
                    lvm.late_binding_vlan = vdp_vlan
                    lvm.vdp_nego_req = False
                else:
                    LOG.error(_LE("Cannot provision VDP overlay"))
                return {'result': provision_reply.get('result'),
                        'fail_reason': provision_reply.get('fail_reason')}
            else:
                fail_reason = "Invalid OVS VLAN for port %s" % (port_name)
                LOG.error(_LE("%s"), fail_reason)
                return {'result': False,
                        'fail_reason': fail_reason}

    def send_vdp_port_event_internal(self, port_uuid, mac, net_uuid,
                                     segmentation_id, status, oui):
        """Send vNIC UP/Down event to VDP.

        :param port_uuid: a ovslib.VifPort object.
        :mac: MAC address of the VNIC
        :param net_uuid: the net_uuid this port is to be associated with.
        :param segmentation_id: the VID for 'vlan' or tunnel ID for 'tunnel'
        :param status: Type of port event. 'up' or 'down'
        :oui: OUI Parameters
        """
        lldpad_port = self.lldpad_info
        if not lldpad_port:
            fail_reason = "There is no LLDPad port available."
            LOG.error(_LE("%s"), fail_reason)
            return {'result': False, 'fail_reason': fail_reason}

        if status == 'up':
            if self.vdp_mode == constants.VDP_SEGMENT_MODE:
                port_name = self.ext_br_obj.get_ofport_name(port_uuid)
                if port_name is None:
                    fail_reason = "Unknown portname for uuid %s" % (port_uuid)
                    LOG.error(_LE("%s"), fail_reason)
                    return {'result': False, 'fail_reason': fail_reason}
                LOG.info("Status up: portname for uuid %(uuid)s is %(port)s",
                         {'uuid': port_uuid, 'port': port_name})
                ret = self.port_up_segment_mode(lldpad_port, port_name,
                                                port_uuid, mac, net_uuid,
                                                segmentation_id, oui)
        else:
            if self.vdp_mode == constants.VDP_SEGMENT_MODE:
                LOG.info(_LI("Status down for portname uuid %s"), port_uuid)
                ret = self.port_down_segment_mode(lldpad_port, port_uuid,
                                                  mac, net_uuid,
                                                  segmentation_id, oui)
        return ret

    def send_vdp_port_event(self, port_uuid, mac, net_uuid,
                            segmentation_id, status, oui):
        """Send vNIC UP/Down event to VDP.

        :param port: a ovslib.VifPort object.
        :param net_uuid: the net_uuid this port is to be associated with.
        :param segmentation_id: the VID for 'vlan' or tunnel ID for 'tunnel'
        :param status: Type of port event. 'up' or 'down'
        """
        try:
            with self.ovs_vdp_lock:
                ret = self.send_vdp_port_event_internal(port_uuid, mac,
                                                        net_uuid,
                                                        segmentation_id,
                                                        status, oui)
                return ret
        except Exception as e:
            LOG.error(_LE("Exception in send_vdp_port_event %s") % str(e))
            return {'result': False, 'fail_reason': str(e)}

    def get_lvid_vdp_vlan(self, net_uuid, port_uuid):
        """Retrieve the Local Vlan ID and VDP Vlan. """

        lvm = self.local_vlan_map.get(net_uuid)
        if not lvm:
            LOG.error(_LE("lvm not yet created, get_lvid_vdp_lan "
                          "return error"))
            return cconstants.INVALID_VLAN, cconstants.INVALID_VLAN
        vdp_vlan = lvm.get_portid_vlan(port_uuid)
        lvid = lvm.lvid
        LOG.info("Return from lvid_vdp_vlan lvid %(lvid)s vdp_vlan %(vdp)s",
                 {'lvid': lvid, 'vdp': vdp_vlan})
        return lvid, vdp_vlan

    def unprovision_vdp_overlay_networks(self, net_uuid, lvid, vdp_vlan, oui):
        """Unprovisions a overlay type network configured using VDP.

        :param net_uuid: the uuid of the network associated with this vlan.
        :lvid: Local VLAN ID
        :vdp_vlan: VDP VLAN ID
        :oui: OUI Parameters
        """
        # check validity
        if not ovs_lib.is_valid_vlan_tag(vdp_vlan):
            LOG.error(_LE("Cannot unprovision VDP Overlay network for"
                      " net-id=%(net_uuid)s - Invalid "),
                      {'net_uuid': net_uuid})
            return

        LOG.info(_LI('unprovision_vdp_overlay_networks: add_flow for '
                     'Local Vlan %(local_vlan)s VDP VLAN %(vdp_vlan)s'),
                 {'local_vlan': lvid, 'vdp_vlan': vdp_vlan})
        self.program_vm_ovs_flows(lvid, vdp_vlan, 0)

    def vdp_vlan_change_internal(self, vsw_cb_data, vdp_vlan, fail_reason):
        """Callback Function from VDP when provider VLAN changes.

        This will be called only during error cases when switch
        reloads or when compute reloads.
        """
        LOG.debug("In VDP VLAN change VLAN %s", vdp_vlan)
        if not vsw_cb_data:
            LOG.error(_LE("NULL vsw_cb_data Info received"))
            return
        net_uuid = vsw_cb_data.get('net_uuid')
        port_uuid = vsw_cb_data.get('port_uuid')
        lvm = self.local_vlan_map.get(net_uuid)
        if not lvm:
            LOG.error(_LE("Network %s is not in the local vlan map"), net_uuid)
            return
        lldpad_port = self.lldpad_info
        if not lldpad_port:
            LOG.error(_LE("There is no LLDPad port available."))
            return
        exist_vdp_vlan = lvm.late_binding_vlan
        lvid = lvm.vlan
        LOG.debug("lvid %(lvid)s exist %(vlan)s",
                  {'lvid': lvid, 'vlan': exist_vdp_vlan})
        lvm.decr_reset_vlan(port_uuid, vdp_vlan)
        lvm.set_fail_reason(port_uuid, fail_reason)
        self.vdp_vlan_cb(port_uuid, lvid, vdp_vlan, fail_reason)
        if vdp_vlan == exist_vdp_vlan:
            LOG.debug("No change in provider VLAN %s", vdp_vlan)
            return
        # Logic is if the VLAN changed to 0, clear the flows only if none of
        # the VM's in the network has a valid VLAN.
        if not ovs_lib.is_valid_vlan_tag(vdp_vlan):
            if ovs_lib.is_valid_vlan_tag(exist_vdp_vlan) and not (
               lvm.any_valid_vlan()):
                # Clear the old flows
                LOG.debug("Clearing flows, no valid vlans")
                self.program_vm_ovs_flows(lvid, exist_vdp_vlan, 0)
                lvm.late_binding_vlan = 0
            lvm.vdp_nego_req = False
        else:
            # If any VM gets a VLAN change, we immediately modify the flow.
            # This is done to not wait for all VM's VLAN getting updated from
            # switch. Logic is if any VM gts a new VLAN, the other VM's of the
            # same network will be updated eventually.
            if vdp_vlan != exist_vdp_vlan and (
               ovs_lib.is_valid_vlan_tag(vdp_vlan)):
                # Add the new flows and remove the old flows
                LOG.warn("Non Zero VDP Vlan change %s %s" %
                         (vdp_vlan, exist_vdp_vlan))
                self.program_vm_ovs_flows(lvid, exist_vdp_vlan, vdp_vlan)
                lvm.late_binding_vlan = vdp_vlan
                lvm.vdp_nego_req = False
            else:
                LOG.error(_LE("Invalid or same VLAN Exist %(exist)s "
                              "New %(new)s VLANs"),
                          {'exist': exist_vdp_vlan, 'new': vdp_vlan})

    def vdp_vlan_change(self, vsw_cb_data, vdp_vlan, fail_reason):
        """Callback Function from VDP when provider VLAN changes.

        This will be called only during error cases when switch
        reloads or when compute reloads.
        """
        LOG.debug("In VDP VLAN change VLAN %s" % vdp_vlan)
        try:
            with self.ovs_vdp_lock:
                self.vdp_vlan_change_internal(vsw_cb_data, vdp_vlan,
                                              fail_reason)
        except Exception as e:
            LOG.error(_LE("Exception in vdp_vlan_change %s") % str(e))

    def provision_vdp_overlay_networks(self, port_uuid, mac, net_uuid,
                                       segmentation_id, lvid, oui):
        """Provisions a overlay type network configured using VDP.

        :param port_uuid: the uuid of the VM port.
        :param mac: the MAC address of the VM.
        :param net_uuid: the uuid of the network associated with this vlan.
        :param segmentation_id: the VID for 'vlan' or tunnel ID for 'tunnel'
        :lvid: Local VLAN ID
        :oui: OUI Parameters
        """
        lldpad_port = self.lldpad_info
        if lldpad_port:
            ovs_cb_data = {'obj': self, 'port_uuid': port_uuid, 'mac': mac,
                           'net_uuid': net_uuid}
            vdp_vlan, fail_reason = lldpad_port.send_vdp_vnic_up(
                port_uuid=port_uuid, vsiid=port_uuid, gid=segmentation_id,
                mac=mac, new_network=True, oui=oui,
                vsw_cb_fn=self.vdp_vlan_change, vsw_cb_data=ovs_cb_data)
        else:
            fail_reason = "There is no LLDPad port available."
            LOG.error(_LE("%s"), fail_reason)
            return {'result': False, 'vdp_vlan': cconstants.INVALID_VLAN,
                    'fail_reason': fail_reason}
        # check validity
        if not ovs_lib.is_valid_vlan_tag(vdp_vlan):
            LOG.error(_LE("Cannot provision VDP Overlay network for"
                      " net-id=%(net_uuid)s - Invalid "),
                      {'net_uuid': net_uuid})
            return {'result': True, 'vdp_vlan': cconstants.INVALID_VLAN,
                    'fail_reason': fail_reason}

        LOG.info(_LI('provision_vdp_overlay_networks: add_flow for '
                     'Local Vlan %(local_vlan)s VDP VLAN %(vdp_vlan)s'),
                 {'local_vlan': lvid, 'vdp_vlan': vdp_vlan})
        self.program_vm_ovs_flows(lvid, 0, vdp_vlan)
        return {'result': True, 'vdp_vlan': vdp_vlan, 'fail_reason': None}

    def pop_local_cache(self, port_uuid, mac, net_uuid, lvid, vdp_vlan,
                        segmentation_id):
        """Populate the local cache after restart. """

        LOG.info("Populating the OVS VDP cache with port %(port_uuid)s, "
                 "mac %(mac)s net %(net_uuid)s lvid %(lvid)s vdpvlan "
                 "%(vdp_vlan)s seg %(seg)s",
                 {'port_uuid': port_uuid, 'mac': mac, 'net_uuid': net_uuid,
                  'lvid': lvid, 'vdp_vlan': vdp_vlan, 'seg': segmentation_id})
        lvm = self.local_vlan_map.get(net_uuid)
        if not lvm:
            lvm = LocalVlan(lvid, segmentation_id)
            self.local_vlan_map[net_uuid] = lvm
        lvm.lvid = lvid
        lvm.set_port_uuid(port_uuid, vdp_vlan, None)
        if vdp_vlan != cconstants.INVALID_VLAN:
            lvm.late_binding_vlan = vdp_vlan
            lvm.vdp_nego_req = False
