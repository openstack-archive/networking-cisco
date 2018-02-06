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

import warnings

from oslo_config import cfg
from oslo_log import log as logging

from networking_cisco._i18n import _

from networking_cisco.config import base

from networking_cisco.plugins.ml2.drivers.cisco.ucsm import constants as const

LOG = logging.getLogger(__name__)

""" Cisco UCS Manager ML2 Mechanism driver specific configuration.

Following are user configurable options for UCS Manager ML2 Mechanism
driver. The ucsm_username, ucsm_password, and ucsm_ip are
required options in single UCS Manager mode. A repetitive block starting
with ml2_cisco_ucsm_ip signals multi-UCSM configuration. When both are
present, the multi-UCSM config will only take effect.
"""

CONF = cfg.CONF

ml2_cisco_ucsm_opts = [
    cfg.StrOpt('ucsm_ip',
               help=_('Cisco UCS Manager IP address. This is a required field '
                      'to communicate with a Cisco UCS Manager.')),
    cfg.ListOpt('supported_pci_devs',
                default=[const.PCI_INFO_CISCO_VIC_1240,
                         const.PCI_INFO_INTEL_82599],
                help=_('SR-IOV and VM-FEX vendors to be handled by the '
                       'driver. xxxx:yyyy represents vendor_id:product_id '
                       'of the PCI networking devices that the driver needs '
                       'to handle. It is implicit that the SR-IOV capable '
                       'devices specified here should be supported on the UCS '
                       'platform.')),
    cfg.BoolOpt('ucsm_https_verify',
                default=True,
                help=_('The UCSM driver will always perform SSL certificate '
                       'checking on the UCS Managers that it is connecting '
                       'to. This checking can be disabled by setting this '
                       'global configuration to False. '
                       'Disabling this check will leave the connection to UCS '
                       'Manager insecure and vulnerable to man-in-the-middle '
                       'attacks.')),
]

ml2_cisco_ucsm_common = [
    cfg.StrOpt('ucsm_username',
               help=_('Username for UCS Manager. This is a required field '
                      'to communicate with a Cisco UCS Manager.')),
    cfg.StrOpt('ucsm_password',
               secret=True,  # do not expose value in the logs
               help=_('Password for UCS Manager. This is a required field '
                      'to communicate with a Cisco UCS Manager.')),
    cfg.ListOpt('ucsm_virtio_eth_ports',
                default=[const.ETH0, const.ETH1],
                help=_('Ethernet port names to be used for virtio ports. '
                       'This config lets the Cloud Admin specify what ports '
                       'on the UCS Servers can be used for OpenStack virtual '
                       'port configuration. The names should match the '
                       'names on the UCS Manager.')),
    cfg.DictOpt('ucsm_host_list',
                help=_('Hostname to Service profile mapping for UCS Manager '
                       'controlled hosts. This Service profile '
                       'should not be associated with a Service Profile '
                       'Template. If the Service Profile is not specified '
                       'with a path, the driver assumes that it is at the '
                       'root level on the UCSM. For example: '
                       'Hostname1:Serviceprofile1, '
                       'Hostname2:Serviceprofile2')),
    cfg.StrOpt('sriov_qos_policy',
               help=_('A pre-defined QoS policy name. This optional config '
                      'allows the cloud admin to pre-create a QoS policy on '
                      'the UCSM. If this config is present, the UCSM driver '
                      'will associate this QoS policy with every Port profile '
                      'it creates for SR-IOV ports.')),
    cfg.StrOpt('sp_template_list',
               help=_('Service Profile Template config for this UCSM. The '
                      'configuration to be provided should be a list where '
                      'each element in the list represents information for '
                      'a single Service Profile Template on that UCSM. Each '
                      'element is mapping of a Service Profile Template\'s '
                      'path, its name and a list of all UCS Servers '
                      'controlled by this template. For example:\n'
                      'sp_template_list = '
                      'SP_Template1_path:SP_Template1:Host1,Host2\n'
                      '                   '
                      'SP_Template2_path:SP_Template2:Host3,Host4\n'
                      'This is an optional config with no defaults')),
    cfg.StrOpt('vnic_template_list',
               help=_('VNIC Profile Template config per UCSM. Allows the '
                      'cloud admin to specify a VNIC Template on the UCSM '
                      'that is attached to every vNIC connected to a specific '
                      'physical network. Each element in this list has 3 '
                      'parts: the physical network that is defined in neutron '
                      'configuration, the VNIC Template with its path in '
                      'UCSM, the vNIC on the UCS Servers that is connected to '
                      'this physical network. For example:\n'
                      'vnic_template_list = '
                      'physnet1:vnic_template_path1:vt1\n'
                      '                     '
                      'physnet2:vnic_template_path2:vt2\n'
                      'This is an optional config with no defaults.')),
]

sriov_opts = [
    base.RemainderOpt('network_name',
                      dest="network_vlans",
                      help=_('SR-IOV Multi-VLAN trunk config section is an '
                             'optional config section to accomodate the '
                             'scenario where an application using an SR-IOV '
                             'port to communicate would like to send traffic '
                             'on multiple application specific VLANs not '
                             'known to OpenStack. This config section is '
                             'applicable across all UCSMs specified as part '
                             'of the OpenStack cloud. The names of the '
                             'neutron networks on which the SR-IOV ports are '
                             'going to be created have to be known ahead of '
                             'time and should be associated with a list or '
                             'range of application VLANs using the following '
                             'format:\n'
                             '<neutron network name>=<comma separated list of '
                             'VLAN-ids or VLAN-id ranges> '
                             'For example:\ntest_network1=5,7-9')),
]

ucsms = base.SubsectionOpt(
    'ml2_cisco_ucsm_ip',
    dest='ucsms',
    help=_("Subgroups that allow you to specify the UCSMs to be "
           "managed by the UCSM ML2 driver."),
    subopts=ml2_cisco_ucsm_common)

CONF.register_opts(ml2_cisco_ucsm_opts, "ml2_cisco_ucsm")
CONF.register_opts(ml2_cisco_ucsm_common, "ml2_cisco_ucsm")
CONF.register_opt(ucsms, "ml2_cisco_ucsm")
CONF.register_opts(sriov_opts, "sriov_multivlan_trunk")


def parse_pci_vendor_config():
    vendor_list = []
    vendor_config_list = CONF.ml2_cisco_ucsm.supported_pci_devs
    for vendor in vendor_config_list:
        vendor_product = vendor.split(':')
        if len(vendor_product) != 2:
            raise cfg.Error(_("UCS Mech Driver: Invalid PCI device "
                              "config: %s") % vendor)
        vendor_list.append(vendor)
    return vendor_list


def load_single_ucsm_config():
    # If no valid single configuration, skip this
    if not CONF.ml2_cisco_ucsm.ucsm_ip:
        return
    ucsm_ip = CONF.ml2_cisco_ucsm.ucsm_ip

    # Clear any previously loaded single ucsm config
    CONF.clear_override("ucsms", group="ml2_cisco_ucsm")

    if ucsm_ip in CONF.ml2_cisco_ucsm.ucsms:
        warnings.warn("UCSM %(ip)s is defined in the main [ml2_cisco_ucsm] "
                      "config group and the [ml2_cisco_ucsm_ip:%(ip)s] "
                      "config group. Using the configs from the"
                      "[ml2_cisco_ucsm_ip:%(ip)s] group. To remove this "
                      "warning remove the duplicated UCSM information from "
                      "the [ml2_cisco_ucsm] group in your config file."
                      % {"ip": ucsm_ip})
        return

    # Create a group to represent the single ucsms config
    CONF.register_opts(ml2_cisco_ucsm_common, "single_ucsm_config")

    # Inject config values from main ml2_cisco_ucsm group into the single ucsm
    # group
    for opt in ml2_cisco_ucsm_common:
        if opt.dest not in CONF.ml2_cisco_ucsm:
            continue
        CONF.set_override(opt.dest, CONF.ml2_cisco_ucsm[opt.dest],
                          group="single_ucsm_config")

    # Inject the single UCSM into the ucsms dictionary as an override so we can
    # clear it again later
    ucsms = dict(CONF.ml2_cisco_ucsm.ucsms)
    ucsms[ucsm_ip] = CONF.single_ucsm_config
    CONF.set_override("ucsms", ucsms, group="ml2_cisco_ucsm")


class UcsmConfig(object):
    """ML2 Cisco UCSM Mechanism Driver Configuration class."""

    def __init__(self):
        self._sp_templates = {}
        load_single_ucsm_config()

    @property
    def multi_ucsm_mode(self):
        if CONF.ml2_cisco_ucsm.ucsms:
            return True
        return False

    @property
    def ucsm_host_dict(self):
        host_dict = {}
        if CONF.ml2_cisco_ucsm.ucsms:
            for ip, ucsm in CONF.ml2_cisco_ucsm.ucsms.items():
                for host, sp in (ucsm.ucsm_host_list or {}).items():
                    host_dict[host] = ip
        return host_dict

    @property
    def ucsm_sp_dict(self):
        sp_dict = {}
        if CONF.ml2_cisco_ucsm.ucsms:
            for ip, ucsm in CONF.ml2_cisco_ucsm.ucsms.items():
                for host, sp in (ucsm.ucsm_host_list or {}).items():
                    if '/' not in sp:
                        sp_dict[(ip, host)] = (
                            const.SERVICE_PROFILE_PATH_PREFIX + sp.strip())
                    else:
                        sp_dict[(ip, host)] = sp.strip()
        return sp_dict

    def get_all_ucsm_ips(self):
        if CONF.ml2_cisco_ucsm.ucsms:
            return list(CONF.ml2_cisco_ucsm.ucsms)

    def get_ucsm_eth_port_list(self, ucsm_ip):
        conf = CONF.ml2_cisco_ucsm
        if ucsm_ip in conf.ucsms:
            return list(map(lambda x: const.ETH_PREFIX + x,
                        conf.ucsms[ucsm_ip].ucsm_virtio_eth_ports))

    def _all_sp_templates(self):
        if self._sp_templates:
            return self._sp_templates
        for ip, ucsm in CONF.ml2_cisco_ucsm.ucsms.items():
            sp_template_mappings = (ucsm.get('sp_template_list') or "").split()
            for mapping in sp_template_mappings:
                data = mapping.split(":")
                if len(data) != 3:
                    raise cfg.Error(_('UCS Mech Driver: Invalid Service '
                                      'Profile Template config %s') % mapping)
                host_list = data[2].split(',')
                for host in host_list:
                    self._sp_templates[host] = (ip, data[0], data[1])
        return self._sp_templates

    def is_service_profile_template_configured(self):
        if self._all_sp_templates():
            return True
        return False

    def get_sp_template_path_for_host(self, host):
        template_info = self._all_sp_templates().get(host)
        # template_info should be a tuple containing
        # (ucsm_ip, sp_template_path, sp_template)
        return template_info[1] if template_info else None

    def get_sp_template_for_host(self, host):
        template_info = self._all_sp_templates().get(host)
        # template_info should be a tuple containing
        # (ucsm_ip, sp_template_path, sp_template)
        return template_info[2] if template_info else None

    def get_ucsm_ip_for_sp_template_host(self, host):
        template_info = self._all_sp_templates().get(host)
        # template_info should be a tuple containing
        # (ucsm_ip, sp_template_path, sp_template)
        return template_info[0] if template_info else None

    def get_sp_template_list_for_ucsm(self, ucsm_ip):
        sp_template_info_list = []
        template_info = self._all_sp_templates()
        for host, template in template_info.items():
            if ucsm_ip == template[0]:
                LOG.debug('SP Template: %s in UCSM : %s',
                          template[2], template[0])
                sp_template_info_list.append(template)
        return sp_template_info_list

    def add_sp_template_config_for_host(self, host, ucsm_ip,
                                        sp_template_path,
                                        sp_template):
        templates = self._all_sp_templates()
        templates[host] = (ucsm_ip, sp_template_path, sp_template)

    def update_sp_template_config(self, host_id, ucsm_ip,
                                  sp_template_with_path):
        sp_template_info = sp_template_with_path.rsplit('/', 1)
        LOG.debug('SP Template path: %s SP Template: %s',
            sp_template_info[0], sp_template_info[1])
        self.add_sp_template_config_for_host(
            host_id, ucsm_ip, sp_template_info[0], sp_template_info[1])

    def _vnic_template_data_for_ucsm_ip(self, ucsm_ip):
        if ucsm_ip not in CONF.ml2_cisco_ucsm.ucsms:
            return []
        template_list = (
            CONF.ml2_cisco_ucsm.ucsms[ucsm_ip].vnic_template_list or "")
        mappings = []
        vnic_template_mappings = template_list.split()
        for mapping in vnic_template_mappings:
            data = mapping.split(":")
            if len(data) != 3:
                raise cfg.Error(_("UCS Mech Driver: Invalid VNIC Template "
                                  "config: %s") % mapping)
            data[1] = data[1] or const.VNIC_TEMPLATE_PARENT_DN
            mappings.append(data)
        return mappings

    def is_vnic_template_configured(self):
        for ip, ucsm in CONF.ml2_cisco_ucsm.ucsms.items():
            if ucsm.vnic_template_list:
                return True
        return False

    def get_vnic_template_for_physnet(self, ucsm_ip, physnet):
        vnic_template_mappings = self._vnic_template_data_for_ucsm_ip(ucsm_ip)
        for mapping in vnic_template_mappings:
            if mapping[0] == physnet:
                return (mapping[1], mapping[2])
        return (None, None)

    def get_vnic_template_for_ucsm_ip(self, ucsm_ip):
        vnic_template_info_list = []
        vnic_template_mappings = self._vnic_template_data_for_ucsm_ip(ucsm_ip)
        for mapping in vnic_template_mappings:
            vnic_template_info_list.append((mapping[1], mapping[2]))
        return vnic_template_info_list

    def get_sriov_multivlan_trunk_config(self, network):
        vlans = []
        config = cfg.CONF.sriov_multivlan_trunk.network_vlans.get(network)
        if not config:
            return vlans

        vlanlist = config.split(',')
        for vlan in vlanlist:
            if '-' in vlan:
                start_vlan, sep, end_vlan = (vlan.partition('-'))
                vlans.extend(list(range(int(start_vlan.strip()),
                                        int(end_vlan.strip()) + 1, 1)))
            else:
                vlans.append(int(vlan))
        return vlans

    def get_sriov_qos_policy(self, ucsm_ip):
        return (CONF.ml2_cisco_ucsm.ucsms[ucsm_ip].sriov_qos_policy or
                CONF.ml2_cisco_ucsm.sriov_qos_policy)
