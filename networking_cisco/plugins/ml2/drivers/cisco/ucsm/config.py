# Copyright 2015-2016 Cisco Systems, Inc.
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

from networking_cisco._i18n import _

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
    cfg.ListOpt('ucsm_virtio_eth_ports',
                default=[const.ETH0, const.ETH1],
                help=_('List of comma separated names of ports that could '
                       'be used to configure VLANs for Neutron virtio '
                       'ports. The names should match the names on the '
                       'UCS Manager.')),
    cfg.StrOpt('sriov_qos_policy',
               help=_('Name of QoS Policy pre-defined in UCSM, to be '
                      'applied to all VM-FEX Port Profiles. This is '
                      'an optional parameter.')),
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
    sp_dict = {}
    host_dict = {}
    if cfg.CONF.ml2_cisco_ucsm.ucsm_host_list:
        host_config_list = cfg.CONF.ml2_cisco_ucsm.ucsm_host_list
        for host in host_config_list:
            hostname, sep, service_profile = host.partition(':')
            if not sep or not service_profile:
                raise cfg.Error(_("UCS Mech Driver: Invalid Host Service "
                                  "Profile config: %s") % host)
            key = (cfg.CONF.ml2_cisco_ucsm.ucsm_ip, hostname)
            if '/' not in service_profile:
                # Assuming the service profile is at the root level
                # and the path is not specified. This option
                # allows backward compatability with earlier config
                # format
                sp_dict[key] = (const.SERVICE_PROFILE_PATH_PREFIX +
                    service_profile.strip())
            else:
                # Assuming the complete path to Service Profile has
                # been provided in the config. The Service Profile
                # could be in an sub-org.
                sp_dict[key] = service_profile.strip()

            LOG.debug('Service Profile for %s is %s',
                hostname, sp_dict.get(key))
            host_dict[hostname] = cfg.CONF.ml2_cisco_ucsm.ucsm_ip
        return sp_dict, host_dict


@debtcollector.removals.remove(message=DEPRECATION_MESSAGE)
def parse_virtio_eth_ports():
    eth_port_list = []
    if not cfg.CONF.ml2_cisco_ucsm.ucsm_virtio_eth_ports:
        raise cfg.Error(_("UCS Mech Driver: Ethernet Port List "
                          "not provided. Cannot properly support "
                          "Neutron virtual ports on this setup."))

    for eth_port in cfg.CONF.ml2_cisco_ucsm.ucsm_virtio_eth_ports:
        eth_port_list.append(const.ETH_PREFIX + str(eth_port).strip())

    return eth_port_list


class UcsmConfig(object):
    """ML2 Cisco UCSM Mechanism Driver Configuration class."""
    ucsm_dict = {}
    ucsm_port_dict = {}
    sp_template_dict = {}
    vnic_template_dict = {}
    multivlan_trunk_dict = {}
    sriov_qos_policy = {}
    multi_ucsm_mode = False
    sp_template_mode = False
    vnic_template_mode = False

    def __init__(self):
        """Create a single UCSM or Multi-UCSM dict."""
        self._create_multi_ucsm_dicts()
        if cfg.CONF.ml2_cisco_ucsm.ucsm_ip and not self.ucsm_dict:
            self._create_single_ucsm_dicts()

        if not self.ucsm_dict:
            raise cfg.Error(_('Insufficient UCS Manager configuration has '
                              'been provided to the plugin'))

    @debtcollector.removals.remove(message=DEPRECATION_MESSAGE)
    def _create_single_ucsm_dicts(self):
        """Creates a dictionary of UCSM data for 1 UCS Manager."""
        ucsm_info = []
        eth_port_list = []
        ucsm_info.append(cfg.CONF.ml2_cisco_ucsm.ucsm_password)
        ucsm_info.append(cfg.CONF.ml2_cisco_ucsm.ucsm_username)
        self.ucsm_dict[cfg.CONF.ml2_cisco_ucsm.ucsm_ip] = ucsm_info
        eth_port_list = parse_virtio_eth_ports()
        if eth_port_list:
            self.ucsm_port_dict[cfg.CONF.ml2_cisco_ucsm.ucsm_ip] = (
                eth_port_list)

    def _create_multi_ucsm_dicts(self):
        """Creates a dictionary of all UCS Manager data from config."""
        username = None
        password = None
        multi_parser = cfg.MultiConfigParser()
        read_ok = multi_parser.read(cfg.CONF.config_file)

        if len(read_ok) != len(cfg.CONF.config_file):
            raise cfg.Error(_('Some config files were not parsed properly'))

        for parsed_file in multi_parser.parsed:
            for parsed_item in parsed_file.keys():
                dev_id, sep, dev_ip = parsed_item.partition(':')
                dev_ip = dev_ip.strip()
                if dev_id.lower() == 'ml2_cisco_ucsm_ip':
                    ucsm_info = []
                    eth_port_list = []
                    for dev_key, value in parsed_file[parsed_item].items():
                        config_item = dev_key.lower()
                        if config_item == 'ucsm_virtio_eth_ports':
                            for eth_port in value[0].split(','):
                                eth_port_list.append(
                                    const.ETH_PREFIX + str(eth_port).strip())
                            self.ucsm_port_dict[dev_ip] = eth_port_list
                        elif config_item == 'sp_template_list':
                            self._parse_sp_template_list(dev_ip, value)
                            self.sp_template_mode = True
                        elif config_item == 'vnic_template_list':
                            self._parse_vnic_template_list(dev_ip, value)
                            self.vnic_template_mode = True
                        elif config_item == 'sriov_qos_policy':
                            LOG.debug('QoS Policy: %s', value[0].strip())
                            self.sriov_qos_policy[dev_ip] = value[0].strip()
                        elif dev_key.lower() == 'ucsm_username':
                            username = value[0].strip()
                        else:
                            password = value[0].strip()
                        ucsm_info = (username, password)
                        self.ucsm_dict[dev_ip] = ucsm_info
                        self.multi_ucsm_mode = True
                if dev_id.lower() == 'sriov_multivlan_trunk':
                    for dev_key, value in parsed_file[parsed_item].items():
                        self._parse_sriov_multivlan_trunk_config(dev_key,
                                                                 value)

    def get_credentials_for_ucsm_ip(self, ucsm_ip):
        if ucsm_ip in self.ucsm_dict:
            return self.ucsm_dict.get(ucsm_ip)

    def get_all_ucsm_ips(self):
        return self.ucsm_dict.keys()

    def get_ucsm_eth_port_list(self, ucsm_ip):
        if ucsm_ip in self.ucsm_port_dict:
            return self.ucsm_port_dict[ucsm_ip]

    def _parse_sp_template_list(self, ucsm_ip, sp_template_config):
        sp_template_list = []
        for sp_template_temp in sp_template_config:
            sp_template_list = sp_template_temp.split()
            for sp_template in sp_template_list:
                sp_template_path, sep, template_hosts = (
                    sp_template.partition(':'))
                if not sp_template_path or not sep or not template_hosts:
                    raise cfg.Error(_('UCS Mech Driver: Invalid Service '
                                      'Profile Template config %s')
                                    % sp_template_config)
                sp_temp, sep, hosts = template_hosts.partition(':')
                LOG.debug('SP Template Path: %s, SP Template: %s, '
                    'Hosts: %s', sp_template_path, sp_temp, hosts)
                host_list = hosts.split(',')
                for host in host_list:
                    value = (ucsm_ip, sp_template_path, sp_temp)
                    self.sp_template_dict[host] = value
                    LOG.debug('SP Template Dict key: %s, value: %s',
                              host, value)

    def is_service_profile_template_configured(self):
        return self.sp_template_mode

    def get_sp_template_path_for_host(self, host):
        template_info = self.sp_template_dict.get(host)
        # template_info should be a tuple containing
        # (ucsm_ip, sp_template_path, sp_template)
        return template_info[1] if template_info else None

    def get_sp_template_for_host(self, host):
        template_info = self.sp_template_dict.get(host)
        # template_info should be a tuple containing
        # (ucsm_ip, sp_template_path, sp_template)
        return template_info[2] if template_info else None

    def get_ucsm_ip_for_sp_template_host(self, host):
        template_info = self.sp_template_dict.get(host)
        # template_info should be a tuple containing
        # (ucsm_ip, sp_template_path, sp_template)
        return template_info[0] if template_info else None

    def get_sp_template_list_for_ucsm(self, ucsm_ip):
        sp_template_info_list = []
        hosts = self.sp_template_dict.keys()
        for host in hosts:
            value = self.sp_template_dict.get(host)
            if ucsm_ip in value:
                LOG.debug('SP Template: %s in UCSM : %s',
                          value[2], value[0])
                sp_template_info_list.append(value)
        return sp_template_info_list

    def _parse_vnic_template_list(self, ucsm_ip, vnic_template_config):
        vnic_template_mapping = []
        for vnic_template_temp in vnic_template_config:
            vnic_template_mapping = vnic_template_temp.split()
            for mapping in vnic_template_mapping:
                physnet, sep, vnic_template = mapping.partition(':')
                if not sep or not vnic_template:
                    raise cfg.Error(_("UCS Mech Driver: Invalid VNIC Template "
                                      "config: %s") % physnet)

                vnic_template_path, sep, vnic_template_name = (
                    vnic_template.partition(':'))
                if not vnic_template_path:
                    vnic_template_path = const.VNIC_TEMPLATE_PARENT_DN
                if not vnic_template_name:
                    raise cfg.Error(_("UCS Mech Driver: Invalid VNIC Template "
                                      "name for physnet: %s") % physnet)

                key = (ucsm_ip, physnet)
                value = (vnic_template_path, vnic_template_name)
                self.vnic_template_dict[key] = value
                LOG.debug('VNIC Template key: %s, value: %s',
                    key, value)

    def is_vnic_template_configured(self):
        return self.vnic_template_mode

    def get_vnic_template_for_physnet(self, ucsm_ip, physnet):
        key = (ucsm_ip, physnet)
        if key in self.vnic_template_dict:
            return self.vnic_template_dict.get(key)
        else:
            return (None, None)

    def get_vnic_template_for_ucsm_ip(self, ucsm_ip):
        vnic_template_info_list = []
        keys = self.vnic_template_dict.keys()
        for key in keys:
            LOG.debug('VNIC template dict key : %s', key)
            if ucsm_ip in key:
                value = self.vnic_template_dict.get(key)
                LOG.debug('Appending VNIC Template %s to the list.',
                    value[1])
                vnic_template_info_list.append(
                    self.vnic_template_dict.get(key))
        return vnic_template_info_list

    def _parse_sriov_multivlan_trunk_config(self, net_name, vlan_list):
        vlan_range_indicator = '-'
        vlans = []
        key = net_name
        for vlan_entry in vlan_list[0].split(','):
            if vlan_range_indicator in vlan_entry:
                start_vlan, sep, end_vlan = (
                    vlan_entry.partition(vlan_range_indicator))
                vlans = vlans + list(range(int(start_vlan.strip()),
                    int(end_vlan.strip()) + 1, 1))
            else:
                vlans.append(int(vlan_entry.strip()))
        self.multivlan_trunk_dict[key] = vlans

    def get_sriov_multivlan_trunk_config(self, network):
        if network in self.multivlan_trunk_dict:
            return self.multivlan_trunk_dict[network]
        else:
            return None

    def get_sriov_qos_policy(self, ucsm_ip):
        if cfg.CONF.ml2_cisco_ucsm.sriov_qos_policy:
            return cfg.CONF.ml2_cisco_ucsm.sriov_qos_policy
        else:
            LOG.debug('Predefined QoS Policy on UCSM %s : %s', ucsm_ip,
                self.sriov_qos_policy.get(ucsm_ip))
            return self.sriov_qos_policy.get(ucsm_ip)
