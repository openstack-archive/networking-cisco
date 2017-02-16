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

"""This file contains the public API's for interacting with LLDPAD. """

from networking_cisco._i18n import _LE

from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import dfa_sys_lib as utils

LOG = logging.getLogger(__name__)


class LldpApi(object):

    """LLDP API Class. """

    def __init__(self, root_helper):
        self.root_helper = root_helper

    def enable_lldp(self, port_name, is_ncb=True, is_nb=False):
        """Function to enable LLDP on the interface. """
        reply = None
        if is_ncb:
            reply = self.run_lldptool(["-L", "-i", port_name, "-g", "ncb",
                                       "adminStatus=rxtx"])
        elif is_nb:
            reply = self.run_lldptool(["-L", "-i", port_name, "-g", "nb",
                                       "adminStatus=rxtx"])
        else:
            LOG.error(_LE("Both NCB and NB are not selected to "
                          "enable LLDP"))
            return False
        if reply is None:
            return False
        exp_str = "adminstatus=rxtx"
        if exp_str in reply.replace(" ", "").lower():
            return True
        else:
            return False

    def get_lldp_tlv(self, port_name, is_ncb=True, is_nb=False):
        """Function to Query LLDP TLV on the interface. """
        reply = None
        if is_ncb:
            reply = self.run_lldptool(["get-tlv", "-n", "-i", port_name,
                                       "-g", "ncb"])
        elif is_nb:
            reply = self.run_lldptool(["get-tlv", "-n", "-i", port_name,
                                       "-g", "nb"])
        else:
            LOG.error(_LE("Both NCB and NB are not selected to "
                          "query LLDP"))
        return reply

    def run_lldptool(self, args):
        """Function for invoking the lldptool utility. """
        full_args = ['lldptool'] + args
        try:
            return utils.execute(full_args, root_helper=self.root_helper)
        except Exception as exc:
            LOG.error(_LE("Unable to execute %(cmd)s. "
                          "Exception: %(exception)s"),
                      {'cmd': full_args, 'exception': str(exc)})

    def _check_common_tlv_format(self, tlv_complete_data, tlv_data_pattern,
                                 tlv_string):
        """Check for the common TLV format. """
        if tlv_complete_data is None:
            return False, None
        tlv_string_split = tlv_complete_data.split(tlv_string)
        if len(tlv_string_split) < 2:
            return False, None
        next_tlv_list = tlv_string_split[1].split('TLV')[0]
        tlv_val_set = next_tlv_list.split(tlv_data_pattern)
        if len(tlv_val_set) < 2:
            return False, None
        return True, tlv_val_set

    def get_remote_evb_cfgd(self, tlv_data):
        """Returns IF EVB TLV is present in the TLV. """
        return self._check_common_tlv_format(
            tlv_data, "mode:", "EVB Configuration TLV")[0]

    def get_remote_evb_mode(self, tlv_data):
        """Returns the EVB mode in the TLV. """
        ret, parsed_val = self._check_common_tlv_format(
            tlv_data, "mode:", "EVB Configuration TLV")
        if not ret:
            return None
        mode_val = parsed_val[1].split()[0].strip()
        return mode_val

    def get_remote_mgmt_addr(self, tlv_data):
        """Returns Remote Mgmt Addr from the TLV. """
        ret, parsed_val = self._check_common_tlv_format(
            tlv_data, "IPv4:", "Management Address TLV")
        if not ret:
            return None
        addr_fam = 'IPv4:'
        addr = parsed_val[1].split('\n')[0].strip()
        return addr_fam + addr

    def get_remote_sys_desc(self, tlv_data):
        """Returns Remote Sys Desc from the TLV. """
        ret, parsed_val = self._check_common_tlv_format(
            tlv_data, "\n", "System Description TLV")
        if not ret:
            return None
        return parsed_val[1].strip()

    def get_remote_sys_name(self, tlv_data):
        """Returns Remote Sys Name from the TLV. """
        ret, parsed_val = self._check_common_tlv_format(
            tlv_data, "\n", "System Name TLV")
        if not ret:
            return None
        return parsed_val[1].strip()

    def get_remote_port(self, tlv_data):
        """Returns Remote Port from the TLV. """
        ret, parsed_val = self._check_common_tlv_format(
            tlv_data, "\n", "Port Description TLV")
        if not ret:
            return None
        return parsed_val[1].strip()

    def get_remote_chassis_id_mac(self, tlv_data):
        """Returns Remote Chassis ID MAC from the TLV. """
        ret, parsed_val = self._check_common_tlv_format(
            tlv_data, "MAC:", "Chassis ID TLV")
        if not ret:
            return None
        mac = parsed_val[1].split('\n')
        return mac[0].strip()

    def get_remote_port_id_mac(self, tlv_data):
        """Returns Remote Port ID MAC from the TLV. """
        ret, parsed_val = self._check_common_tlv_format(
            tlv_data, "MAC:", "Port ID TLV")
        if not ret:
            return None
        mac = parsed_val[1].split('\n')
        return mac[0].strip()

    def get_remote_port_id_local(self, tlv_data):
        """Returns Remote Port ID Local from the TLV. """
        ret, parsed_val = self._check_common_tlv_format(
            tlv_data, "Local:", "Port ID TLV")
        if not ret:
            return None
        local = parsed_val[1].split('\n')
        return local[0].strip()
