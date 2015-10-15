# Copyright 2015 Cisco Systems, Inc.
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

from oslo_config import cfg
from oslo_log import log as logging

from networking_cisco.plugins.ml2.drivers.cisco.ucsm import constants as const

LOG = logging.getLogger(__name__)

""" Cisco UCS Manager ML2 Mechanism driver specific configuration.

Following are user configurable options for UCS Manager ML2 Mechanism
driver. The ucsm_username, ucsm_password, and ucsm_ip are
required options. Additional configuration knobs are provided to pre-
create UCS Manager port profiles.
"""

ml2_cisco_ucsm_opts = [
    cfg.ListOpt('supported_pci_devs',
                default=[const.PCI_INFO_CISCO_VIC_1240,
                         const.PCI_INFO_INTEL_82599],
                help=_('List of comma separated vendor_id:product_id of '
                       'SR_IOV capable devices supported by this MD. This MD '
                       'supports both VM-FEX and SR-IOV devices.')),

]

cfg.CONF.register_opts(ml2_cisco_ucsm_opts, "ml2_cisco_ucsm")


def parse_pci_vendor_config():
    vendor_list = []
    vendor_config_list = cfg.CONF.ml2_cisco_ucsm.supported_pci_devs
    for vendor in vendor_config_list:
        vendor_product = vendor.split(':')
        if len(vendor_product) != 2:
            raise cfg.Error(_("UCS Mech Driver: Invalid PCI device "
                              "config: %s") % vendor)
        vendor_list.append(vendor)
    return vendor_list


class UcsmConfig(object):
    """ML2 Cisco UCSM Mechanism Driver Configuration class."""
    ucsm_dict = {}

    def __init__(self):
        self._create_ucsm_dict()

    def _create_ucsm_dict(self):
        """Create a dictionary of all UCS Manager data from the config file."""
        multi_parser = cfg.MultiConfigParser()
        read_ok = multi_parser.read(cfg.CONF.config_file)

        if len(read_ok) != len(cfg.CONF.config_file):
            raise cfg.Error(_('Some config files were not parsed properly'))

        for parsed_file in multi_parser.parsed:
            for parsed_item in parsed_file.keys():
                dev_id, sep, dev_ip = parsed_item.partition(':')
                if dev_id.lower() == 'ml2_cisco_ucsm_ip':
                    ucsm_info = []
                    for dev_key, value in parsed_file[parsed_item].items():
                        ucsm_info.append(value[0])
                    self.ucsm_dict[dev_ip] = ucsm_info

    def get_credentials_for_ucsm_ip(self, ucsm_ip):
        if ucsm_ip in self.ucsm_dict:
            return self.ucsm_dict[ucsm_ip]

    def get_all_ucsm_ips(self):
        return self.ucsm_dict.keys()
