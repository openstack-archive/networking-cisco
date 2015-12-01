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

import debtcollector

from oslo_config import cfg
from oslo_log import log as logging

from networking_cisco.plugins.ml2.drivers.cisco.ucsm import constants as const

LOG = logging.getLogger(__name__)
DEPRECATION_MESSAGE = "This will be removed in the N cycle."

""" Cisco UCS Manager ML2 Mechanism driver specific configuration.

Following are user configurable options for UCS Manager ML2 Mechanism
driver. The ucsm_username, ucsm_password, and ucsm_ip are
required options in single UCS Manager mode. A repetitive block starting
with ml2_cisco_ucsm_ip signals multi-UCSM configuration. When both are
present, the multi-UCSM config will only take effect.
"""

ml2_cisco_ucsm_opts = [
    cfg.StrOpt('ucsm_ip',
               help=_('Cisco UCS Manager IP address. This is a required field '
                      'to communicate with a Cisco UCS Manager.')),
    cfg.StrOpt('ucsm_username',
               help=_('Username for UCS Manager. This is a required field '
                      'to communicate with a Cisco UCS Manager.')),
    cfg.StrOpt('ucsm_password',
               secret=True,  # do not expose value in the logs
               help=_('Password for UCS Manager. This is a required field '
                      'to communicate with a Cisco UCS Manager.')),
    cfg.ListOpt('supported_pci_devs',
                default=[const.PCI_INFO_CISCO_VIC_1240,
                         const.PCI_INFO_INTEL_82599],
                help=_('List of comma separated vendor_id:product_id of '
                       'SR_IOV capable devices supported by this MD. This MD '
                       'supports both VM-FEX and SR-IOV devices.')),
    cfg.ListOpt('ucsm_host_list',
                help=_('List of comma separated Host:Service Profile tuples '
                       'providing the Service Profile associated with each '
                       'Host to be supported by this MD.')),
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


@debtcollector.removals.remove(message=DEPRECATION_MESSAGE)
def parse_ucsm_host_config():
    host_dict = {}
    if cfg.CONF.ml2_cisco_ucsm.ucsm_host_list:
        host_config_list = cfg.CONF.ml2_cisco_ucsm.ucsm_host_list
        for host in host_config_list:
            host_sp = host.split(':')
            if len(host_sp) != 2:
                raise cfg.Error(_("UCS Mech Driver: Invalid Host Service "
                                  "Profile config: %s") % host)
            key = host_sp[0]
            host_dict[key] = host_sp[1]
        return host_dict


class UcsmConfig(object):
    """ML2 Cisco UCSM Mechanism Driver Configuration class."""
    ucsm_dict = {}

    def __init__(self):
        """Create a single UCSM or Multi-UCSM dict."""
        self._create_multi_ucsm_dict()
        if cfg.CONF.ml2_cisco_ucsm.ucsm_ip and not self.ucsm_dict:
            self._create_single_ucsm_dict()

        if not self.ucsm_dict:
            raise cfg.Error(_('Insufficient UCS Manager configuration has '
                              'been provided to the plugin'))

    @debtcollector.removals.remove(message=DEPRECATION_MESSAGE)
    def _create_single_ucsm_dict(self):
        """Creates a dictionary of UCSM data for 1 UCS Manager."""
        ucsm_info = []
        ucsm_info.append(cfg.CONF.ml2_cisco_ucsm.ucsm_password)
        ucsm_info.append(cfg.CONF.ml2_cisco_ucsm.ucsm_username)
        self.ucsm_dict[cfg.CONF.ml2_cisco_ucsm.ucsm_ip] = ucsm_info

    def _create_multi_ucsm_dict(self):
        """Creates a dictionary of all UCS Manager data from config."""
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
