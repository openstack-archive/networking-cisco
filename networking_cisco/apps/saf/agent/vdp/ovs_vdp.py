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
from networking_cisco._i18n import _LE, _LI

from networking_cisco.apps.saf.agent.vdp import lldpad
from networking_cisco.apps.saf.agent.vdp import vdp_constants as constants
from networking_cisco.apps.saf.common import constants as cconstants
from networking_cisco.apps.saf.common import dfa_exceptions as dfae
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import dfa_sys_lib as ovs_lib
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


class OVSNeutronVdp(object):

    '''Implements the VDP specific changes in OVS

    Creating the veth pairs, programming the flows for VDP, deleting the VDP
    specific flows, communicating with VDP (lldpad) daemon using lldpad class
    are some of the functionality provided by this class.
    '''

    def __init__(self, uplink, integ_br, ext_br, root_helper,
                 vdp_mode=constants.VDP_SEGMENT_MODE):
        # self.root_helper = 'sudo'
        self.root_helper = root_helper
        self.uplink = uplink
        self.integ_br = integ_br
        self.ext_br = ext_br
        self.vdp_mode = vdp_mode
        self.local_vlan_map = {}
        self.lldpad_info = {}
        self.lldp_veth_port = None
        self.phy_peer_port_num = cconstants.INVALID_OFPORT
        self.int_peer_port_num = cconstants.INVALID_OFPORT
        self.int_peer_port = None
        self.phy_peer_port = None
        self.ext_br_obj = None
        self.integ_br_obj = None
        self.setup_lldpad = self.setup_lldpad_ports()

    def is_lldpad_setup_done(self):
        return self.setup_lldpad

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

    def gen_veth_str(self, const_str, intf_str):
        '''Generate a veth string

        Concatenates the constant string with remaining available length
        of interface string from trailing position
        '''
        avl_len = constants.MAX_VETH_NAME - len(const_str)
        if avl_len <= 0:
            LOG.error(_LE("veth string name too short"))
            raise dfae.DfaAgentFailed(reason="Veth Unavailable")
        start_pos = len(intf_str) - avl_len
        veth_str = const_str + intf_str[start_pos:]
        return veth_str

    def setup_lldpad_ports(self):
        '''Setup the flows for passing LLDP/VDP frames in OVS.'''
        # Creating the physical bridge and setting up patch ports is done by
        # OpenStack
        ovs_bridges = ovs_lib.get_bridges(self.root_helper)
        if self.ext_br not in ovs_bridges or self.integ_br not in ovs_bridges:
            LOG.error(_LE("Integ or Physical Bridge not configured by"
                          "OpenStack"))
            raise dfae.DfaAgentFailed(reason="Bridge Unavailable")
        br = ovs_lib.OVSBridge(self.ext_br, root_helper=self.root_helper)
        self.ext_br_obj = br
        int_br = ovs_lib.OVSBridge(self.integ_br, root_helper=self.root_helper)
        self.integ_br_obj = int_br

        self.phy_peer_port, self.int_peer_port = self.find_interconnect_ports()
        if self.phy_peer_port is None or self.int_peer_port is None:
            LOG.error(_LE("Integ or Physical Patch/Veth Ports not "
                          "configured by OpenStack"))
            raise dfae.DfaAgentFailed(reason="Ports Unconfigured")

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
            LOG.error(_LE("Uplink port not detected on external bridge"))
            return False
        if not br.port_exists(lldp_ovs_veth_str):
            lldp_ovs_portnum = br.add_port(lldp_ovs_veth)
        else:
            lldp_ovs_portnum = br.get_port_ofport(lldp_ovs_veth)
        if lldp_ovs_portnum == cconstants.INVALID_OFPORT:
            LOG.error(_LE("lldp veth port not detected on external bridge"))
            return False
        lldp_loc_veth.link.set_up()
        lldp_ovs_veth.link.set_up()
        # What about OVS restart cases fixme(padkrish)
        self.program_vdp_flows(lldp_ovs_portnum, phy_port_num)

        self.phy_peer_port_num = br.get_port_ofport(self.phy_peer_port)
        self.int_peer_port_num = int_br.get_port_ofport(self.int_peer_port)
        if (self.phy_peer_port_num == cconstants.INVALID_OFPORT or
                self.int_peer_port_num == cconstants.INVALID_OFPORT):
            LOG.error(_LE("int or phy peer OF Port not detected on Int or"
                      "Phy Bridge %(phy)s %(int)s"),
                      {'phy': self.phy_peer_port_num,
                       'int': self.int_peer_port_num})
            return False
        self.lldpad_info = (lldpad.LldpadDriver(lldp_loc_veth_str, self.uplink,
                                                self.root_helper))
        ret = self.lldpad_info.enable_evb()
        if not ret:
            LOG.error(_LE("Unable to cfg EVB"))
            return False
        self.lldp_veth_port = lldp_loc_veth_str
        LOG.info(_LI("Setting up lldpad ports complete"))
        return True

    def get_lldp_bridge_port(self):
        return self.lldp_veth_port

    def find_interconnect_ports(self):
        '''Find the internal veth or patch ports'''

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
        if lvm:
            if port_uuid not in lvm.port_uuid_list:
                LOG.error(_LE("port_uuid %s not in cache for port_down"),
                          port_uuid)
                return False
            vdp_vlan = lvm.late_binding_vlan
            lldpad_port.send_vdp_vnic_down(port_uuid=port_uuid,
                                           vsiid=port_uuid,
                                           gid=segmentation_id,
                                           mac=mac, vlan=vdp_vlan, oui=oui)
            lvm.port_uuid_list.pop(port_uuid, None)
            if not lvm.port_uuid_list:
                self.unprovision_vdp_overlay_networks(net_uuid, lvm.lvid,
                                                      vdp_vlan, oui)
                self.local_vlan_map.pop(net_uuid)
                LOG.debug("Deleting flows")
        else:
            # There's no logical change of this condition being hit
            # So, not returning False here.
            LOG.error(_LE("Local VLAN Map not available in port down"))
        return True

    def port_up_segment_mode(self, lldpad_port, port_name, port_uuid, mac,
                             net_uuid, segmentation_id, oui):
        lvm = self.local_vlan_map.get(net_uuid)
        if lvm and lvm.late_binding_vlan:
            vdp_vlan = lvm.late_binding_vlan
            ovs_cb_data = {'obj': self, 'mac': mac,
                           'port_uuid': port_uuid, 'net_uuid': net_uuid}
            lldpad_port.send_vdp_vnic_up(port_uuid=port_uuid,
                                         vsiid=port_uuid, gid=segmentation_id,
                                         mac=mac, vlan=vdp_vlan, oui=oui,
                                         vsw_cb_fn=self.vdp_vlan_change,
                                         vsw_cb_data=ovs_cb_data)
            lvm.port_uuid_list[port_uuid] = port_uuid
            return True
        else:
            int_br = self.integ_br_obj
            lvid = int_br.get_port_vlan_tag(port_name)
            if lvid != cconstants.INVALID_VLAN:
                ret, vdp_vlan = self.provision_vdp_overlay_networks(
                    port_uuid, mac, net_uuid, segmentation_id, lvid, oui)
                if not lvm:
                    lvm = LocalVlan(lvid, segmentation_id)
                    self.local_vlan_map[net_uuid] = lvm
                lvm.lvid = lvid
                lvm.port_uuid_list[port_uuid] = port_uuid
                if vdp_vlan != cconstants.INVALID_VLAN:
                    lvm.late_binding_vlan = vdp_vlan
                else:
                    LOG.error(_LE("Cannot provision VDP overlay"))
                return ret
            else:
                LOG.error(_LE("Invalid VLAN"))
                return False

    def send_vdp_port_event(self, port_uuid, mac, net_uuid,
                            segmentation_id, status, oui):
        '''Send vNIC UP/Down event to VDP

        :param port_uuid: a ovslib.VifPort object.
        :mac: MAC address of the VNIC
        :param net_uuid: the net_uuid this port is to be associated with.
        :param segmentation_id: the VID for 'vlan' or tunnel ID for 'tunnel'
        :param status: Type of port event. 'up' or 'down'
        :oui: OUI Parameters
        '''
        lldpad_port = self.lldpad_info
        if not lldpad_port:
            LOG.error(_LE("There is no LLDPad port available."))
            return False

        ret = False
        if status == 'up':
            if self.vdp_mode == constants.VDP_SEGMENT_MODE:
                port_name = self.ext_br_obj.get_ofport_name(port_uuid)
                if port_name is None:
                    LOG.error(_LE("Unknown portname for uuid %s"), port_uuid)
                    return False
                LOG.info(_LI('portname for uuid %s is '), port_name)
                ret = self.port_up_segment_mode(lldpad_port, port_name,
                                                port_uuid, mac, net_uuid,
                                                segmentation_id, oui)
        else:
            if self.vdp_mode == constants.VDP_SEGMENT_MODE:
                ret = self.port_down_segment_mode(lldpad_port, port_uuid,
                                                  mac, net_uuid,
                                                  segmentation_id, oui)
        return ret

    def unprovision_vdp_overlay_networks(self, net_uuid, lvid, vdp_vlan, oui):
        '''Provisions a overlay type network configured using VDP.

        :param net_uuid: the uuid of the network associated with this vlan.
        :lvid: Local VLAN ID
        :vdp_vlan: VDP VLAN ID
        :oui: OUI Parameters
        '''
        # check validity
        if not ovs_lib.is_valid_vlan_tag(vdp_vlan):
            LOG.error(_LE("Cannot unprovision VDP Overlay network for"
                      " net-id=%(net_uuid)s - Invalid "),
                      {'net_uuid': net_uuid})
            return

        LOG.info(_LI('unprovision_vdp_overlay_networks: add_flow for '
                     'Local Vlan %(local_vlan)s VDP VLAN %(vdp_vlan)s'),
                 {'local_vlan': lvid, 'vdp_vlan': vdp_vlan})
        # outbound
        self.ext_br_obj.delete_flows(
            in_port=self.phy_peer_port_num, dl_vlan=lvid)
        # inbound
        self.integ_br_obj.delete_flows(in_port=self.int_peer_port_num,
                                       dl_vlan=vdp_vlan)

    # fixme(padkrish)
    def vdp_vlan_change(self, vsw_cb_data, vdp_vlan):
        '''Callback Function from VDP when provider VLAN changes

        This will be called only during error cases when switch
        reloads or when compute reloads
        '''
        LOG.debug("In VDP VLAN change VLAN %s", vdp_vlan)
        if not vsw_cb_data:
            LOG.error(_LE("NULL vsw_cb_data Info received"))
            return
        net_uuid = vsw_cb_data.get('net_uuid')
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
        br = self.ext_br_obj
        LOG.debug("lvid %(lvid)s exist %(vlan)s",
                  {'lvid': lvid, 'vlan': exist_vdp_vlan})
        if vdp_vlan == exist_vdp_vlan:
            LOG.debug("No change in provider VLAN %s", vdp_vlan)
            return
        if ovs_lib.is_valid_vlan_tag(exist_vdp_vlan):
            # Clear the old flows
            # outbound
            br.delete_flows(in_port=self.phy_peer_port_num,
                            dl_vlan=lvid)
            # inbound
            self.integ_br_obj.delete_flows(in_port=self.int_peer_port_num,
                                           dl_vlan=exist_vdp_vlan)
        if ovs_lib.is_valid_vlan_tag(vdp_vlan):
            # Add the new flows
            # outbound
            br.add_flow(priority=4,
                        in_port=self.phy_peer_port_num, dl_vlan=lvid,
                        actions="mod_vlan_vid:%s,normal" % vdp_vlan)
            # inbound
            self.integ_br_obj.add_flow(priority=3,
                                       in_port=self.int_peer_port_num,
                                       dl_vlan=vdp_vlan,
                                       actions="mod_vlan_vid:%s,normal" % lvid)
        else:
            LOG.error(_LE("Returned vlan %s is invalid"), vdp_vlan)

        # Even if it's 0, it's still stored to reflect provider
        # hasn't allocated a VLAN from VDP, happens during error case.
        lvm.late_binding_vlan = vdp_vlan

    def provision_vdp_overlay_networks(self, port_uuid, mac, net_uuid,
                                       segmentation_id, lvid, oui):
        '''Provisions a overlay type network configured using VDP.

        :param port_uuid: the uuid of the VM port.
        :param mac: the MAC address of the VM.
        :param net_uuid: the uuid of the network associated with this vlan.
        :param segmentation_id: the VID for 'vlan' or tunnel ID for 'tunnel'
        :lvid: Local VLAN ID
        :oui: OUI Parameters
        '''
        lldpad_port = self.lldpad_info
        if lldpad_port:
            ovs_cb_data = {'obj': self, 'port_uuid': port_uuid, 'mac': mac,
                           'net_uuid': net_uuid}
            vdp_vlan = lldpad_port.send_vdp_vnic_up(
                port_uuid=port_uuid, vsiid=port_uuid, gid=segmentation_id,
                mac=mac, new_network=True, oui=oui,
                vsw_cb_fn=self.vdp_vlan_change, vsw_cb_data=ovs_cb_data)
        else:
            LOG.error(_LE("There is no LLDPad port available."))
            return False, cconstants.INVALID_VLAN
        # check validity
        if not ovs_lib.is_valid_vlan_tag(vdp_vlan):
            LOG.error(_LE("Cannot provision VDP Overlay network for"
                      " net-id=%(net_uuid)s - Invalid "),
                      {'net_uuid': net_uuid})
            return True, cconstants.INVALID_VLAN

        LOG.info(_LI('provision_vdp_overlay_networks: add_flow for '
                     'Local Vlan %(local_vlan)s VDP VLAN %(vdp_vlan)s'),
                 {'local_vlan': lvid, 'vdp_vlan': vdp_vlan})
        # outbound
        self.ext_br_obj.add_flow(priority=4,
                                 in_port=self.phy_peer_port_num, dl_vlan=lvid,
                                 actions="mod_vlan_vid:%s,normal" % vdp_vlan)
        # inbound
        self.integ_br_obj.add_flow(priority=3,
                                   in_port=self.int_peer_port_num,
                                   dl_vlan=vdp_vlan,
                                   actions="mod_vlan_vid:%s,normal" % lvid)
        return True, vdp_vlan
