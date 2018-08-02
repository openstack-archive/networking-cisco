# Copyright (c) 2013-2016 Cisco Systems, Inc.
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

from oslo_config import cfg
from oslo_config import types

from networking_cisco._i18n import _
from networking_cisco.config import base

nexus_sub_opts = [
    cfg.BoolOpt('https_verify', default=True,
        help=_('This configuration option defaults to True.'
               'When https_verify is True, the certification '
               'authority (CA) file must be in the Operating Systems '
               'repository or is a locally defined file whose name is '
               'provided in https_local_certificate.  Set https_verify '
               'to False to skip https certification checking thus '
               'making the connection insecure. When True, the Nexus '
               'device must be configured with both certificate and key '
               'files and enabled.  Refer to the "nxapi certificate" '
               'commands defined in the "Nexus 9K NXAPI Programmability '
               'Guide" for details.')),
    cfg.StrOpt('https_local_certificate',
        help=_('Configure a local certificate file to present in https '
               'requests. This is for experimental purposes when an '
               'official certificate from a Trust Certificate Authority '
               'is not yet available. The default configuration is None. '
               'An example configuration would look like '
               'https_local_certificate=/path/to/cafile.crt.')),
    cfg.StrOpt('intfcfg_portchannel',
        help=_('intfcfg_portchannel is a list of Nexus port-channel config '
               'CLI used when baremetal port-channels are created by the '
               'Nexus driver.  It is dependent on "vpc_pool" being '
               'configured.  Any number of Nexus port-channel commands '
               'separated by ";" can be provided.  When there are multiple '
               'interfaces in a baremetal event, the nexus driver checks to '
               'determine whether a port-channel is already applied to the '
               'interfaces; otherwise, it creates a port channel. This '
               'optional configuration allows the administrator to custom '
               'configure the port-channel.  When not configured, the nexus '
               'driver defaults to configuring "spanning-tree port type edge '
               'trunk;no lacp suspend-individual" beneath the port-channel. '
               'An example of this configuration is "intfcfg_portchannel=no '
               'lacp suspend-individual;spanning-tree port type edge '
               'trunk".')),
    cfg.StrOpt('nve_src_intf',
        help=_('Only valid if VXLAN overlay is configured and '
               'vxlan_global_config is set to True. The NVE source interface '
               'is a loopback interface that is configured on the switch with '
               'valid /32 IP address. This /32 IP address must be known by '
               'the transient devices in the transport network and the remote '
               'VTEPs.  This is accomplished by advertising it through a '
               'dynamic routing protocol in the transport network. If '
               'nve_src_intf is not defined, a default setting of 0 '
               'is used to create "loopback0".  This is configured for '
               'non-baremetal only.')),
    cfg.StrOpt('password', secret=True,
        help=_('The password of the Nexus Switch Administrator is required '
               'to allow configuration access to the Nexus switch.')),
    cfg.StrOpt('physnet',
        help=_('This is required if Nexus VXLAN overlay feature is '
               'configured.  It should be the physical network name defined '
               'in "network_vlan_ranges" (defined beneath the "ml2_type_vlan" '
               'section) that this switch is controlling.  The configured '
               '"physnet" is the physical network domain that is connected '
               'to this switch. The vlan ranges defined in '
               '"network_vlan_ranges" for a physical '
               'network are allocated dynamically and are unique per physical '
               'network. These dynamic vlans may be reused across physical '
               'networks.  This configuration applies to non-baremetal '
               'only.')),
    cfg.Opt('host_ports_mapping', default={}, sample_default='<None>',
        type=types.Dict(value_type=types.List(bounds=True)),
        help=_('A list of key:value pairs describing which host is '
               'connected to which physical port or portchannel on the '
               'Nexus switch. The format should look like:\n'
               'host_port_mapping='
               '<your-hostname>:[<intf_type><port>,<intf_type><port>],\n'
               '                  <your-second-host>:[<intf_type><port>]\n'
               'For example:\n'
               'host_port_mapping='
               'host-1:[ethernet1/1, ethernet1/2],\n'
               '                  host-2:[ethernet1/3],\n'
               '                  host-3:[port-channel20]\n'
               'Lines can be broken with indentation to ensure config files '
               'remain readable. '
               'All compute nodes must be configured while '
               'controllers are optional depending on your network '
               'configuration. Depending on the configuration of the '
               'host, the hostname is expected to be the '
               'full hostname (hostname.domainname) which can be derived '
               'by running "hostname -f" on the host itself. Valid '
               'intf_types are "ethernet" or "port-channel".  The default '
               'setting for <intf_type> is "ethernet" and need not be '
               'added to this setting. This configuration applies to VM '
               'deployments only.')),
    cfg.StrOpt('username',
        help=_('The username of the Nexus Switch Administrator is required '
               'to allow configuration access to the Nexus switch.')),
    cfg.StrOpt('vpc_pool',
        help=_('This is port-channel/VPC allocation pool of ids used with '
               'baremetal deployments only.  When there is a list of ethernet '
               'interfaces provided by Ironic to neutron in a port '
               'event, these are assumed to be a port-channel type '
               'configuration.  Ironic only knows about ethernet interfaces '
               'so it is up to the Nexus Driver to either learn the '
               'port channel if the user preconfigured the channel-group on '
               'the ethernet interfaces; otherwise, the driver will create a '
               'new port-channel and apply the channel-group to the ethernet '
               'interfaces.  This pool is the reserved port-channel IDs '
               'available for allocation by the Nexus driver for each switch. '
               'The full format for "vpc_pool" is '
               'vpc_pool=<start_vpc_no-end_vpc_no> | '
               '<vpc_no> {,<start_vpc_no-end_vpc_no> | <vpc_no>}. The "-" in '
               '<start_vpc_no,end_vpc_no> allows you to configure a range '
               'from start to end and <vpc_no> allows just individual '
               'numbers.  There can be any number of ranges and numbers '
               'separated by commas. There is no default value.  If not '
               'configured, the port-channel will only handle learned cases '
               'and attempts to create port-channels will fail since there is '
               'no id pool available from which to allocate an id. Once '
               'defined, it can be redefined by changing "vpc_pool" and '
               'restarting neutron. Existing VPC ids in the database are '
               'gathered and compared against the new "vpc_pool" config.  New '
               'configured vpcids not found in the database are added.  '
               'Inactive entries in the database not found in the new '
               'configured vpcids list are removed. An example of this '
               'configuration is `vpc_pool=1001-1025,1028`.')),
    base.RemainderOpt('host_port_mapping', deprecated_for_removal=True,
        deprecated_reason="Replaced by 'port_host_mapping' option")]

ml2_cisco_opts = [
    cfg.StrOpt('managed_physical_network',
        help=_('When "managed_physical_network" is configured, it restricts '
               'the network segment that the nexus driver supports. '
               'Setting it to a specific network name will limit the '
               'actions taken by this driver to only that network. The '
               'network name must match a name defined in the '
               '"network_vlan_ranges" configuration.  When '
               '"managed_physical_network" is not set, events for all '
               'network segments will be processed by the driver.')),
    cfg.BoolOpt('provider_vlan_auto_create', default=True,
        help=_('A flag indicating whether the Nexus driver should manage '
               'the creation and removal of VLANs for provider networks on '
               'the Nexus switches. When this flag is False, the Nexus'
               'driver will not create or remove VLANs for provider '
               'networks and the administrator needs to manage these '
               'interfaces manually or by external orchestration.')),
    cfg.BoolOpt('provider_vlan_auto_trunk', default=True,
        help=_('A flag indicating whether Nexus driver should manage '
               'the adding and removing of provider VLANs from trunk ports on '
               'the Nexus switches. When this flag is False, the Nexus '
               'driver will not add or remove provider VLANs from trunk '
               'ports and the administrator needs to manage these operations '
               'manually or by external orchestration.')),
    cfg.IntOpt('switch_heartbeat_time', default=30,
        help=_('Configuration replay is enabled by default by defining the '
               'time interval to 30 seconds.  This is the amount of time to '
               'check the state of all known Nexus device(s). To disable '
               'the replay feature, set this "switch_heartbeat_time" to 0 '
               'seconds.')),
    cfg.BoolOpt('vxlan_global_config', default=False,
        help=_('A flag indicating whether the Nexus driver should manage '
               'the creating and removing of the Nexus switch VXLAN global '
               'settings of "feature nv overlay", "feature '
               'vn-segment-vlan-based", "interface nve 1" and the NVE '
               'subcommand "source-interface loopback #". When set to the '
               'default of False, the Nexus driver will not add or remove '
               'these VXLAN settings and the administrator needs to manage '
               'these operations manually or by external orchestration.')),
]

nexus_switches = base.SubsectionOpt(
    'ml2_mech_cisco_nexus',
    dest='nexus_switches',
    help=_("Subgroups that allow you to specify the nexus switches to be "
           "managed by the nexus ML2 driver."),
    subopts=nexus_sub_opts)

cfg.CONF.register_opts(ml2_cisco_opts, "ml2_cisco")
cfg.CONF.register_opt(nexus_switches, "ml2_cisco")

#
# Format for ml2_conf_cisco.ini 'ml2_mech_cisco_nexus' is:
# {('<device ipaddr>', '<keyword>'): '<value>', ...}
#
# Example:
# {('1.1.1.1', 'username'): 'admin',
#  ('1.1.1.1', 'password'): 'mySecretPassword',
#  ('1.1.1.1', 'compute1'): '1/1', ...}
#
