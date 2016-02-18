# Copyright 2015 Cisco Systems.
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


"""This file contains the implementation of OpenStack component of VDP.
VDP is a part of LLDP Agent Daemon (lldpad). For more information on VDP,
pls visit http://www.ieee802.org/1/pages/802.1bg.html
"""

from networking_cisco._i18n import _LE

from networking_cisco.apps.saf.agent.vdp import (
    lldpad_constants as vdp_const)
from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.common import constants
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import dfa_sys_lib as utils
from networking_cisco.apps.saf.common import utils as sys_utils

LOG = logging.getLogger(__name__)

# When timeout support becomes available in lldpad, this config will be
# enabled fixme(padkrish)
# OPTS = [
#    cfg.IntOpt('lldp_timeout',
#               default='0',
#               help=_('Timeout in seconds for lldptool commands')),
# ]


def enable_lldp(self, port_name, is_ncb=True, is_nb=False):
    '''Function to enable LLDP on the interface.'''

    if is_ncb:
        self.run_lldptool(["-L", "-i", port_name, "-g", "ncb",
                           "adminStatus=rxtx"])
    if is_nb:
        self.run_lldptool(["-L", "-i", port_name, "-g", "nb",
                           "adminStatus=rxtx"])


class LldpadDriver(object):

    """LLDPad driver class."""

    def __init__(self, port_name, phy_uplink, root_helper, is_ncb=True,
                 is_nb=False):
        '''Constructor.

        param port_name: Port where LLDP/EVB needs to be cfgd
        param phy_uplink: Physical Interface
        param root_helper: utility to use when running shell cmds.
        param is_ncb: Should LLDP be cfgd on Nearest Customer Bridge
        param is_nb: Should LLDP be cfgd on Nearest Bridge
        '''
        # Re-enable this once support becomes available in lldpad.
        # fixme(padkrish)
        # cfg.CONF.register_opts(OPTS)
        self.port_name = port_name
        self.phy_uplink = phy_uplink
        self.is_ncb = is_ncb
        self.is_nb = is_nb
        self.root_helper = root_helper
        self.mutex_lock = sys_utils.lock()
        self.read_vdp_cfg()
        self.vdp_vif_map = {}
        self.oui_vif_map = {}
        self.enable_lldp()
        sync_timeout_val = int(self.vdp_opts['vdp_sync_timeout'])
        vdp_periodic_task = sys_utils.PeriodicTask(sync_timeout_val,
                                                   self._vdp_refrsh_hndlr)
        self.vdp_periodic_task = vdp_periodic_task
        vdp_periodic_task.run()

    def clear_uplink(self):
        self.phy_uplink = None
        self.port_name = None
        self.vdp_periodic_task.stop()
        del self.vdp_vif_map
        del self.oui_vif_map

    def read_vdp_cfg(self):
        self._cfg = config.CiscoDFAConfig().cfg
        self.vdp_opts = dict()
        self.vdp_opts['mgrid'] = self._cfg.vdp.mgrid2
        self.vdp_opts['typeid'] = self._cfg.vdp.typeid
        self.vdp_opts['typeidver'] = self._cfg.vdp.typeidver
        self.vdp_opts['vsiidfrmt'] = self._cfg.vdp.vsiidfrmt
        self.vdp_opts['hints'] = self._cfg.vdp.hints
        self.vdp_opts['filter'] = self._cfg.vdp.filter
        self.vdp_opts['vdp_sync_timeout'] = self._cfg.vdp.vdp_sync_timeout

    def enable_lldp(self):
        '''Function to enable LLDP on the interface.'''
        if self.is_ncb:
            self.run_lldptool(["-L", "-i", self.port_name, "-g", "ncb",
                               "adminStatus=rxtx"])
        if self.is_nb:
            self.run_lldptool(["-L", "-i", self.port_name, "-g", "nb",
                               "adminStatus=rxtx"])

    def enable_evb(self):
        '''Function to enable EVB on the interface.'''
        if self.is_ncb:
            self.run_lldptool(["-T", "-i", self.port_name, "-g", "ncb",
                               "-V", "evb", "enableTx=yes"])
            ret = self.enable_gpid()
            return ret
        else:
            LOG.error(_LE("EVB cannot be set on NB"))
            return False

    def enable_gpid(self):
        '''Function to enable Group ID on the interface.

        This is needed to use the MAC, GID, VID Filter
        '''
        if self.is_ncb:
            self.run_lldptool(["-T", "-i", self.port_name, "-g", "ncb",
                               "-V", "evb", "-c", "evbgpid=yes"])
            return True
        else:
            LOG.error(_LE("GPID cannot be set on NB"))
            return False

    # fixme(padkrish)
    def _vdp_refrsh_hndlr(self):
        '''Periodic refresh of vNIC events to VDP

        VDP daemon itself has keepalives. This is needed on top of it
        to keep Orchestrator like OpenStack, VDP daemon and the physical
        switch in sync.
        '''
        LOG.debug("Refresh handler")
        try:
            if not self.vdp_vif_map:
                LOG.debug("vdp_vif_map not created, returning")
                return
            vdp_vif_map = dict.copy(self.vdp_vif_map)
            oui_vif_map = dict.copy(self.oui_vif_map)
            for key in vdp_vif_map.viewkeys():
                lvdp_dict = vdp_vif_map.get(key)
                loui_dict = oui_vif_map.get(key)
                if not lvdp_dict:
                    return
                if not loui_dict:
                    oui_id = ""
                    oui_data = ""
                else:
                    oui_id = loui_dict.get('oui_id')
                    oui_data = loui_dict.get('oui_data')
                with self.mutex_lock:
                    if key in self.vdp_vif_map:
                        LOG.debug("Sending Refresh for VSI %s", lvdp_dict)
                        vdp_vlan = self.send_vdp_assoc(
                            vsiid=lvdp_dict.get('vsiid'),
                            mgrid=lvdp_dict.get('mgrid'),
                            typeid=lvdp_dict.get('typeid'),
                            typeid_ver=lvdp_dict.get('typeid_ver'),
                            vsiid_frmt=lvdp_dict.get('vsiid_frmt'),
                            filter_frmt=lvdp_dict.get('filter_frmt'),
                            gid=lvdp_dict.get('gid'),
                            mac=lvdp_dict.get('mac'),
                            vlan=0, oui_id=oui_id, oui_data=oui_data,
                            sw_resp=True)
                # check validity.
                if not utils.is_valid_vlan_tag(vdp_vlan):
                    LOG.error(_LE("Returned vlan %(vlan)s is invalid."),
                              {'vlan': vdp_vlan})
                    # Need to invoke CB. So no return here.
                    vdp_vlan = 0
                exist_vdp_vlan = lvdp_dict.get('vdp_vlan')
                # Condition will be hit only during error cases when switch
                # reloads or when compute reloads
                if vdp_vlan != exist_vdp_vlan:
                    # Invoke the CB Function
                    cb_fn = lvdp_dict.get('vsw_cb_fn')
                    cb_data = lvdp_dict.get('vsw_cb_data')
                    if cb_fn:
                        cb_fn(cb_data, vdp_vlan)
                    lvdp_dict['vdp_vlan'] = vdp_vlan
        except Exception as e:
            LOG.error(_LE("Exception in Refrsh %s"), str(e))

    def run_lldptool(self, args):
        '''Function for invoking the lldptool utility'''
        full_args = ['lldptool'] + args
        try:
            utils.execute(full_args, root_helper=self.root_helper)
        except Exception as e:
            LOG.error(_LE("Unable to execute %(cmd)s. "
                      "Exception: %(exception)s"),
                      {'cmd': full_args, 'exception': e})

    def store_oui(self, port_uuid, oui_type, oui_data):
        '''Function for storing the OUI

        param uuid: UUID of the vNIC
        param oui_type: OUI ID
        param oui_data: OUI Opaque Data
        '''
        self.oui_vif_map[port_uuid] = {'oui_id': oui_type,
                                       'oui_data': oui_data}

    def store_vdp_vsi(self, port_uuid, mgrid, typeid, typeid_ver,
                      vsiid_frmt, vsiid, filter_frmt, gid, mac, vlan,
                      new_network, reply, oui_id, oui_data, vsw_cb_fn,
                      vsw_cb_data):
        '''Stores the vNIC specific info for VDP Refresh

        :param uuid: vNIC UUID
        :param mgrid: MGR ID
        :param typeid: Type ID
        :param typeid_ver: Version of the Type ID
        :param vsiid_frmt: Format of the following VSI argument
        :param vsiid: VSI value
        :param filter_frmt: Filter Format
        :param gid: Group ID the vNIC belongs to
        :param mac: MAC Address of the vNIC
        :param vlan: VLAN of the vNIC
        :param new_network: Is this the first vNIC of this network
        :param reply: Response from the switch
        :param oui_id: OUI Type
        :param oui_data: OUI Data
        :param vsw_cb_fn: Callback function from the app.
        :param vsw_cb_data: Callback data for the app.
        '''
        if port_uuid in self.vdp_vif_map:
            LOG.debug("Not Storing VDP VSI MAC %(mac)s UUID %(uuid)s",
                      {'mac': mac, 'uuid': vsiid})
        if new_network:
            vdp_vlan = reply
        else:
            vdp_vlan = vlan
        vdp_dict = {'vdp_vlan': vdp_vlan,
                    'mgrid': mgrid,
                    'typeid': typeid,
                    'typeid_ver': typeid_ver,
                    'vsiid_frmt': vsiid_frmt,
                    'vsiid': vsiid,
                    'filter_frmt': filter_frmt,
                    'mac': mac,
                    'gid': gid,
                    'vsw_cb_fn': vsw_cb_fn,
                    'vsw_cb_data': vsw_cb_data}
        self.vdp_vif_map[port_uuid] = vdp_dict
        LOG.debug("Storing VDP VSI MAC %(mac)s UUID %(uuid)s VDP VLAN "
                  "%(vlan)s", {'mac': mac, 'uuid': vsiid, 'vlan': vdp_vlan})
        if oui_id:
            self.store_oui(port_uuid, oui_id, oui_data)

    def clear_oui(self, port_uuid):
        '''Clears the OUI specific info

        :param uuid: vNIC UUID
        Currently only one OUI per VSI fixme(padkrish)
        '''
        if port_uuid in self.oui_vif_map:
            del self.oui_vif_map[port_uuid]
        else:
            LOG.debug("OUI does not exist")

    def clear_vdp_vsi(self, port_uuid):
        '''Stores the vNIC specific info for VDP Refresh

        :param uuid: vNIC UUID
        '''
        try:
            LOG.debug("Clearing VDP VSI MAC %(mac)s UUID %(uuid)s",
                      {'mac': self.vdp_vif_map[port_uuid].get('mac'),
                       'uuid': self.vdp_vif_map[port_uuid].get('vsiid')})
            del self.vdp_vif_map[port_uuid]
        except Exception:
            LOG.error(_LE("VSI does not exist"))
        self.clear_oui(port_uuid)

    def gen_cisco_vdp_oui(self, oui_id, oui_data):
        '''Cisco specific handler for constructing OUI arguments'''
        oui_list = []
        vm_name = oui_data.get('vm_name')
        if vm_name is not None:
            oui_str = "oui=%s," % oui_id
            oui_name_str = oui_str + "vm_name=" + vm_name
            oui_list.append(oui_name_str)
        ip_addr = oui_data.get('ip_addr')
        if ip_addr is not None:
            oui_str = "oui=%s," % oui_id
            ip_addr_str = oui_str + "ipv4_addr=" + ip_addr
            oui_list.append(ip_addr_str)
        vm_uuid = oui_data.get('vm_uuid')
        if vm_uuid is not None:
            oui_str = "oui=%s," % oui_id
            vm_uuid_str = oui_str + "vm_uuid=" + vm_uuid
            oui_list.append(vm_uuid_str)
        return oui_list

    def gen_oui_str(self, oui_list):
        '''Generate the OUI string for vdptool'''
        oui_str = []
        for oui in oui_list:
            oui_str.append('-c')
            oui_str.append(oui)
        return oui_str

    def construct_vdp_dict(self, mode, mgrid, typeid, typeid_ver, vsiid_frmt,
                           vsiid, filter_frmt, gid, mac, vlan, oui_id,
                           oui_data):
        '''Constructs the VDP Message

        Please refer http://www.ieee802.org/1/pages/802.1bg.html VDP
        Section for more detailed information
        :param mode: Associate or De-associate
        :param mgrid: MGR ID
        :param typeid: Type ID
        :param typeid_ver: Version of the Type ID
        :param vsiid_frmt: Format of the following VSI argument
        :param vsiid: VSI value
        :param filter_frmt: Filter Format
        :param gid: Group ID the vNIC belongs to
        :param mac: MAC Address of the vNIC
        :param vlan: VLAN of the vNIC
        :param oui_id: OUI Type
        :param oui_data: OUI Data
        :return vdp_keyword_str: Dictionary of VDP arguments and values
        '''
        vdp_keyword_str = {}
        if mgrid is None:
            mgrid = self.vdp_opts.get('mgrid')
        mgrid_str = "mgrid2=%s" % mgrid
        if typeid is None:
            typeid = self.vdp_opts.get('typeid')
        typeid_str = "typeid=%s" % typeid
        if typeid_ver is None:
            typeid_ver = self.vdp_opts.get('typeidver')
        typeid_ver_str = "typeidver=%s" % typeid_ver
        if int(vsiid_frmt) == int(self.vdp_opts.get('vsiidfrmt')):
            vsiid_str = "uuid=%s" % vsiid
        else:
            # Only format supported for now
            LOG.error(_LE("Unsupported VSIID Format1"))
            return vdp_keyword_str
        if vlan == constants.INVALID_VLAN:
            vlan = 0
        if int(filter_frmt) == vdp_const.VDP_FILTER_GIDMACVID:
            if not mac or gid == 0:
                LOG.error(_LE("Incorrect Filter Format Specified"))
                return vdp_keyword_str
            else:
                f = "filter=%s-%s-%s"
                filter_str = f % (vlan, mac, gid)
        elif int(filter_frmt) == vdp_const.VDP_FILTER_GIDVID:
            if gid == 0:
                LOG.error(_LE("NULL GID Specified"))
                return vdp_keyword_str
            else:
                filter_str = "filter=" + '%d' % vlan + "--" + '%ld' % gid
        elif int(filter_frmt) == vdp_const.VDP_FILTER_MACVID:
            if not mac:
                LOG.error(_LE("NULL MAC Specified"))
                return vdp_keyword_str
            else:
                filter_str = "filter=" + '%d' % vlan + "-" + mac
        elif int(filter_frmt) == vdp_const.VDP_FILTER_VID:
            filter_str = "filter=" + '%d' % vlan
        else:
            LOG.error(_LE("Incorrect Filter Format Specified"))
            return vdp_keyword_str
        oui_list = []
        if oui_id is not None and oui_data is not None:
            if oui_id is 'cisco':
                oui_list = self.gen_cisco_vdp_oui(oui_id, oui_data)
        mode_str = "mode=" + mode
        vdp_keyword_str = dict(mode=mode_str, mgrid=mgrid_str,
                               typeid=typeid_str, typeid_ver=typeid_ver_str,
                               vsiid=vsiid_str, filter=filter_str,
                               oui_list=oui_list)
        return vdp_keyword_str

    def send_vdp_query_msg(self, mode, mgrid, typeid, typeid_ver, vsiid_frmt,
                           vsiid, filter_frmt, gid, mac, vlan, oui_id,
                           oui_data):
        '''Constructs and Sends the VDP Query Message

        Please refer http://www.ieee802.org/1/pages/802.1bg.html VDP
        Section for more detailed information
        :param mode: Associate or De-associate
        :param mgrid: MGR ID
        :param typeid: Type ID
        :param typeid_ver: Version of the Type ID
        :param vsiid_frmt: Format of the following VSI argument
        :param vsiid: VSI value
        :param filter_frmt: Filter Format
        :param gid: Group ID the vNIC belongs to
        :param mac: MAC Address of the vNIC
        :param vlan: VLAN of the vNIC
        :param oui_id: OUI Type
        :param oui_data: OUI Data
        :param sw_resp: Flag indicating if response is required from the daemon
        :return reply: Reply from vdptool
        '''
        if not self.is_ncb:
            LOG.error(_LE("EVB cannot be set on NB"))
            return
        vdp_key_str = self.construct_vdp_dict(mode, mgrid, typeid,
                                              typeid_ver, vsiid_frmt, vsiid,
                                              filter_frmt, gid, mac, vlan,
                                              None, None)
        if len(vdp_key_str) == 0:
            LOG.error(_LE("NULL List"))
            return
        reply = self.run_vdptool(["-t", "-i", self.port_name, "-R", "-V", mode,
                                  "-c", vdp_key_str['mode'],
                                  "-c", vdp_key_str['mgrid'],
                                  "-c", vdp_key_str['typeid'],
                                  "-c", vdp_key_str['typeid_ver'],
                                  "-c", vdp_key_str['vsiid']])
        return reply

    def send_vdp_msg(self, mode, mgrid, typeid, typeid_ver, vsiid_frmt,
                     vsiid, filter_frmt, gid, mac, vlan, oui_id, oui_data,
                     sw_resp):
        '''Constructs and Sends the VDP Message

        Please refer http://www.ieee802.org/1/pages/802.1bg.html VDP
        Section for more detailed information
        :param mode: Associate or De-associate
        :param mgrid: MGR ID
        :param typeid: Type ID
        :param typeid_ver: Version of the Type ID
        :param vsiid_frmt: Format of the following VSI argument
        :param vsiid: VSI value
        :param filter_frmt: Filter Format
        :param gid: Group ID the vNIC belongs to
        :param mac: MAC Address of the vNIC
        :param vlan: VLAN of the vNIC
        :param oui_id: OUI Type
        :param oui_data: OUI Data
        :param sw_resp: Flag indicating if response is required from the daemon
        :return reply: Reply from vdptool
        '''
        if not self.is_ncb:
            LOG.error(_LE("EVB cannot be set on NB"))
            return
        vdp_key_str = self.construct_vdp_dict(mode, mgrid, typeid,
                                              typeid_ver, vsiid_frmt, vsiid,
                                              filter_frmt, gid, mac, vlan,
                                              oui_id, oui_data)
        if len(vdp_key_str) == 0:
            LOG.error(_LE("NULL List"))
            return
        oui_cmd_str = self.gen_oui_str(vdp_key_str['oui_list'])
        if sw_resp:
            # If filter is not VID and if VLAN is 0, Query for the TLV first,
            # if found VDP will return the VLAN. Add support for this once
            # vdptool has the support for querying exact VSI filters
            # fixme(padkrish)

            reply = self.run_vdptool(["-T", "-i", self.port_name, "-W",
                                      "-V", mode, "-c", vdp_key_str['mode'],
                                      "-c", vdp_key_str['mgrid'], "-c",
                                      vdp_key_str['typeid'],
                                      "-c", vdp_key_str['typeid_ver'], "-c",
                                      vdp_key_str['vsiid'], "-c",
                                      "hints=none", "-c",
                                      vdp_key_str['filter']],
                                     oui_args=oui_cmd_str)
        else:
            reply = self.run_vdptool(["-T", "-i", self.port_name,
                                      "-V", mode, "-c", vdp_key_str['mode'],
                                      "-c", vdp_key_str['mgrid'], "-c",
                                      vdp_key_str['typeid'],
                                      "-c", vdp_key_str['typeid_ver'], "-c",
                                      vdp_key_str['vsiid'], "-c",
                                      "hints=none", "-c",
                                      vdp_key_str['filter']],
                                     oui_args=oui_cmd_str)
        return reply

    def get_vlan_from_reply1(self, reply):
        '''Parse the reply from VDP daemon to get the VLAN value'''
        try:
            mode_str = reply.partition("mode = ")[2].split()[0]
            if mode_str != "assoc":
                return constants.INVALID_VLAN
        except Exception:
            LOG.error(_LE("Incorrect Reply,no mode information found: %s"),
                      reply)
            return constants.INVALID_VLAN
        try:
            f_ind = reply.index("filter = ")
        except Exception:
            LOG.error(_LE("Incorrect Reply,no filter information found: %s"),
                      reply)
            return constants.INVALID_VLAN
        try:
            l_ind = reply.rindex("filter = ")
        except Exception:
            LOG.error(_LE("Incorrect Reply,no filter information found: %s"),
                      reply)
            return constants.INVALID_VLAN
        if f_ind != l_ind:
            # Currently not supported if reply contains a filter keyword
            LOG.error(_LE("Err: not supported currently"))
            return constants.INVALID_VLAN
        try:
            vlan_val = reply.partition("filter = ")[2].split('-')[0]
            vlan = int(vlan_val)
        except ValueError:
            LOG.error(_LE("Reply not formatted correctly:"), reply)
            return constants.INVALID_VLAN
        return vlan

    def get_vlan_from_reply(self, reply):
        '''Parse the reply from VDP daemon to get the VLAN value'''
        try:
            f_ind = reply.index("filter")
        except Exception:
            LOG.error(_LE("Incorrect Reply, no filter information found %s"),
                      reply)
            return constants.INVALID_VLAN
        try:
            l_ind = reply.rindex("filter")
        except Exception:
            LOG.error(_LE("Incorrect Reply, no filter information found %s"),
                      reply)
            return constants.INVALID_VLAN
        if f_ind != l_ind:
            # Currently not supported if reply contains a filter keyword
            LOG.error(_LE("Err: not supported currently"))
            return constants.INVALID_VLAN
        try:
            filter_val = reply.partition("filter")[2]
            len_fil = len(filter_val)
            vlan_val = filter_val[4:len_fil].split('-')[0]
            vlan = int(vlan_val)
        except ValueError:
            LOG.error(_LE("Reply not formatted correctly %s"), reply)
            return constants.INVALID_VLAN
        return vlan

    def send_vdp_assoc(self, vsiid=None, mgrid=None, typeid=None,
                       typeid_ver=None, vsiid_frmt=vdp_const.VDP_VSIFRMT_UUID,
                       filter_frmt=vdp_const.VDP_FILTER_GIDMACVID, gid=0,
                       mac="", vlan=0, oui_id="", oui_data="", sw_resp=False):
        '''Sends the VDP Associate Message

        Please refer http://www.ieee802.org/1/pages/802.1bg.html VDP
        Section for more detailed information
        :param vsiid: VSI value, Only UUID supported for now
        :param mgrid: MGR ID
        :param typeid: Type ID
        :param typeid_ver: Version of the Type ID
        :param vsiid_frmt: Format of the following VSI argument
        :param filter_frmt: Filter Format. Only <GID,MAC,VID> supported for now
        :param gid: Group ID the vNIC belongs to
        :param mac: MAC Address of the vNIC
        :param vlan: VLAN of the vNIC
        :param oui_id: OUI Type
        :param oui_data: OUI Data
        :param sw_resp: Flag indicating if response is required from the daemon
        :return vlan: VLAN value returned by vdptool which in turn is given
        :             by Switch
        '''

        if sw_resp and filter_frmt == vdp_const.VDP_FILTER_GIDMACVID:
            reply = self.send_vdp_query_msg("assoc", mgrid, typeid, typeid_ver,
                                            vsiid_frmt, vsiid, filter_frmt,
                                            gid, mac, vlan, oui_id, oui_data)
            vlan_resp = self.get_vlan_from_reply(reply)
            if vlan_resp != constants.INVALID_VLAN:
                return vlan_resp
        reply = self.send_vdp_msg("assoc", mgrid, typeid, typeid_ver,
                                  vsiid_frmt, vsiid, filter_frmt, gid, mac,
                                  vlan, oui_id, oui_data, sw_resp)
        if sw_resp:
            vlan = self.get_vlan_from_reply1(reply)
            return vlan

    def send_vdp_deassoc(self, vsiid=None, mgrid=None, typeid=None,
                         typeid_ver=None,
                         vsiid_frmt=vdp_const.VDP_VSIFRMT_UUID,
                         filter_frmt=vdp_const.VDP_FILTER_GIDMACVID, gid=0,
                         mac="", vlan=0, oui_id="", oui_data="",
                         sw_resp=False):
        '''Sends the VDP Dis-Associate Message

        Please refer http://www.ieee802.org/1/pages/802.1bg.html VDP Section
        for more detailed information
        :param vsiid: VSI value, Only UUID supported for now
        :param mgrid: MGR ID
        :param typeid: Type ID
        :param typeid_ver: Version of the Type ID
        :param vsiid_frmt: Format of the following VSI argument
        :param filter_frmt: Filter Format. Only <GID,MAC,VID> supported for now
        :param gid: Group ID the vNIC belongs to
        :param mac: MAC Address of the vNIC
        :param vlan: VLAN of the vNIC
        :param oui_id: OUI Type
        :param oui_data: OUI Data
        :param sw_resp: Flag indicating if response is required from the daemon
        '''
        # Correct non-zero VLAN needs to be specified
        self.send_vdp_msg("deassoc", mgrid, typeid, typeid_ver,
                          vsiid_frmt, vsiid, filter_frmt, gid, mac, vlan,
                          oui_id, oui_data, sw_resp)

    def send_vdp_vnic_up(self, port_uuid=None, vsiid=None,
                         mgrid=None, typeid=None, typeid_ver=None,
                         vsiid_frmt=vdp_const.VDP_VSIFRMT_UUID,
                         filter_frmt=vdp_const.VDP_FILTER_GIDMACVID,
                         gid=0, mac="", vlan=0, oui=None,
                         new_network=False, vsw_cb_fn=None, vsw_cb_data=None):
        '''Interface function to apps, called for a vNIC UP.

        This currently sends an VDP associate message.
        Please refer http://www.ieee802.org/1/pages/802.1bg.html VDP
        Section for more detailed information
        :param uuid: uuid of the vNIC
        :param vsiid: VSI value, Only UUID supported for now
        :param mgrid: MGR ID
        :param typeid: Type ID
        :param typeid_ver: Version of the Type ID
        :param vsiid_frmt: Format of the following VSI argument
        :param filter_frmt: Filter Format. Only <GID,MAC,VID> supported for now
        :param gid: Group ID the vNIC belongs to
        :param mac: MAC Address of the vNIC
        :param vlan: VLAN of the vNIC
        :param oui_id: OUI Type
        :param oui_data: OUI Data
        :param sw_resp: Flag indicating if response is required from the daemon
        :return reply: VLAN reply from vdptool
        '''
        if oui is None:
            oui = {}
        oui_id = None
        oui_data = None
        if 'oui_id' in oui:
            oui_id = oui['oui_id']
            oui_data = oui
        reply = self.send_vdp_assoc(vsiid=vsiid, mgrid=mgrid, typeid=typeid,
                                    typeid_ver=typeid_ver,
                                    vsiid_frmt=vsiid_frmt,
                                    filter_frmt=filter_frmt, gid=gid, mac=mac,
                                    vlan=vlan, oui_id=oui_id,
                                    oui_data=oui_data, sw_resp=new_network)
        self.store_vdp_vsi(port_uuid, mgrid, typeid, typeid_ver,
                           vsiid_frmt, vsiid, filter_frmt, gid, mac, vlan,
                           new_network, reply, oui_id, oui_data, vsw_cb_fn,
                           vsw_cb_data)
        if new_network:
            return reply

    def send_vdp_vnic_down(self, port_uuid=None, vsiid=None, mgrid=None,
                           typeid=None, typeid_ver=None,
                           vsiid_frmt=vdp_const.VDP_VSIFRMT_UUID,
                           filter_frmt=vdp_const.VDP_FILTER_GIDMACVID,
                           gid=0, mac="", vlan=0, oui=""):
        '''Interface function to apps, called for a vNIC DOWN.

        This currently sends an VDP dis-associate message.
        Please refer http://www.ieee802.org/1/pages/802.1bg.html VDP
        Section for more detailed information
        :param uuid: uuid of the vNIC
        :param vsiid: VSI value, Only UUID supported for now
        :param mgrid: MGR ID
        :param typeid: Type ID
        :param typeid_ver: Version of the Type ID
        :param vsiid_frmt: Format of the following VSI argument
        :param filter_frmt: Filter Format. Only <GID,MAC,VID> supported for now
        :param gid: Group ID the vNIC belongs to
        :param mac: MAC Address of the vNIC
        :param vlan: VLAN of the vNIC
        :param oui_id: OUI Type
        :param oui_data: OUI Data
        :param sw_resp: Flag indicating if response is required from the daemon
        '''
        # Correct non-zero VLAN needs to be specified
        try:
            with self.mutex_lock:
                self.send_vdp_deassoc(vsiid=vsiid, mgrid=mgrid, typeid=typeid,
                                      typeid_ver=typeid_ver,
                                      vsiid_frmt=vsiid_frmt,
                                      filter_frmt=filter_frmt, gid=gid,
                                      mac=mac, vlan=vlan)
                self.clear_vdp_vsi(port_uuid)
        except Exception as e:
            LOG.error(_LE("VNIC Down exception %s"), e)

    def run_vdptool(self, args, oui_args=None):
        '''Function that runs the vdptool utility'''
        if oui_args is None:
            oui_args = []
        full_args = ['vdptool'] + args + oui_args
        try:
            return utils.execute(full_args, root_helper=self.root_helper)
        except Exception as e:
            LOG.error(_LE("Unable to execute %(cmd)s. "
                          "Exception: %(exception)s"),
                      {'cmd': full_args, 'exception': e})
