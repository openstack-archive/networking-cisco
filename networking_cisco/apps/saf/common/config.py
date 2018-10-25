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


from oslo_config import cfg

from keystoneauth1 import loading as ks_loading

from networking_cisco import _i18n
from networking_cisco.apps.saf.agent.vdp import (
    lldpad_constants as vdp_const)
from networking_cisco.apps.saf.common import constants as com_const
from networking_cisco.apps.saf.server.services import constants as const
from networking_cisco.apps.saf.server.services.firewall.native import (
    fw_constants as fw_const)


cfg.CONF.import_group('keystone_authtoken', 'keystonemiddleware.auth_token')


neutron_opts = [
    cfg.StrOpt('username', default='neutron'),
    cfg.StrOpt('project_name', default='service'),
    cfg.StrOpt('user_domain_name', default='default'),
    cfg.StrOpt('project_domain_name', default='default')
]
cfg.CONF.register_opts(neutron_opts, 'neutron')


NOVA_CONF_SECTION = 'nova'
ks_loading.register_auth_conf_options(cfg.CONF, NOVA_CONF_SECTION)
ks_loading.register_session_conf_options(cfg.CONF, NOVA_CONF_SECTION)


nova_opts = [
    cfg.StrOpt('region_name',
               help=_i18n._('Name of nova region to use. Useful if keystone '
                            'manages more than one region.')),
    cfg.StrOpt('endpoint_type',
               default='public',
               choices=['public', 'admin', 'internal'],
               help=_i18n._('Type of the nova endpoint to use.  This endpoint '
                            'will be looked up in the keystone catalog and '
                            'should be one of public, internal or admin.')),
]
cfg.CONF.register_opts(nova_opts, group=NOVA_CONF_SECTION)


dfa_agent_opts = [
    cfg.StrOpt('intergration_bridge', default='br-int'),
    cfg.StrOpt('external_dfa_brdige', default='br-ethd')
]
cfg.CONF.register_opts(dfa_agent_opts, 'dfa_agent')


vdp_opts = [
    cfg.StrOpt('mgrid2', default=vdp_const.VDP_MGRID),
    cfg.StrOpt('typeid', default=vdp_const.VDP_TYPEID),
    cfg.StrOpt('typeidver', default=vdp_const.VDP_TYPEID_VER),
    cfg.StrOpt('vsiidfrmt', default=vdp_const.VDP_VSIFRMT_UUID),
    cfg.StrOpt('hints', default='none'),
    cfg.StrOpt('filter', default=vdp_const.VDP_FILTER_GIDMACVID),
    cfg.StrOpt('vdp_sync_timeout', default=vdp_const.VDP_SYNC_TIMEOUT),
]
cfg.CONF.register_opts(vdp_opts, 'vdp')


firewall_opts = [
    cfg.StrOpt('device', default=fw_const.DEVICE),
    cfg.StrOpt('sched_policy', default=fw_const.SCHED_POLICY),
    cfg.StrOpt('fw_mgmt_ip'),
    cfg.StrOpt('fw_username'),
    cfg.StrOpt('fw_passport'),
    cfg.StrOpt('fw_interface_in'),
    cfg.StrOpt('fw_interface_out'),
    cfg.StrOpt('fw_auto_serv_nwk_create', default=fw_const.AUTO_NWK_CREATE),
    cfg.StrOpt('fw_service_host_profile', default=fw_const.HOST_PROF),
    cfg.StrOpt('fw_service_host_fwd_mode', default=fw_const.HOST_FWD_MODE),
    cfg.StrOpt('fw_service_part_vrf_profile', default=fw_const.PART_PROF),
    cfg.StrOpt('fw_service_ext_profile', default=fw_const.EXT_PROF),
    cfg.StrOpt('fw_service_ext_fwd_mode', default=fw_const.EXT_FWD_MODE),
    cfg.StrOpt('fw_service_in_ip_start', default=fw_const.IN_IP_START),
    cfg.StrOpt('fw_service_in_ip_end', default=fw_const.IN_IP_END),
    cfg.StrOpt('fw_service_out_ip_start', default=fw_const.OUT_IP_START),
    cfg.StrOpt('fw_service_out_ip_end', default=fw_const.OUT_IP_END),
    cfg.StrOpt('fw_service_dummy_ip_subnet', default=fw_const.DUMMY_IP_SUBNET)
]
cfg.CONF.register_opts(firewall_opts, 'firewall')


DEFAULT_LOG_LEVELS = (
    "amqp=WARN, amqplib=WARN, oslo.messaging=WARN, pika=WARN, paramiko=WARN,"
    "paramiko.transport=WARN,"
    "paramiko.transport.sftp=WARN,"
    "pika.callback=WARN,oslo.messaging._drivers=WARN"
)

dfa_log_opts = [
    cfg.BoolOpt('use_syslog', default=False),
    cfg.StrOpt('syslog_lgo_facility', default='LOG_USER'),
    cfg.StrOpt('log_dir', default='.'),
    cfg.StrOpt('log_file', default='fabric_enabler.log'),
    cfg.StrOpt('log_level', default='WARNING'),
    cfg.StrOpt('log_format',
               default='%(asctime)s %(levelname)8s [%(name)s] %(message)s'),
    cfg.StrOpt('log_date_format', default='%Y-%m-%d %H:%M:%S'),
    cfg.StrOpt('default_log_levels', default=DEFAULT_LOG_LEVELS)
]
cfg.CONF.register_opts(dfa_log_opts, 'dfa_log')


sys_opts = [
    cfg.StrOpt('root_helper', default='sudo')
]
cfg.CONF.register_opts(sys_opts, 'sys')


dcnm_opts = [
        cfg.StrOpt('default_cfg_profile',
                   default='defaultNetworkIpv4EfProfile'),
        cfg.StrOpt('default_vrf_profile',
                   default='vrf-common-universal'),
        cfg.StrOpt('default_partition_name', default='CTX'),
        cfg.StrOpt('dcnm_net_ext', default='(DCNM)'),
        cfg.StrOpt('gateway_mac', default='20:20:00:00:00:AA'),
        cfg.StrOpt('dcnm_dhcp_leases', default='/var/lib/dhcpd/dhcpd.leases'),
        cfg.StrOpt('dcnm_dhcp', default='false'),
        cfg.StrOpt('dcnm_ip'),
        cfg.StrOpt('dcnm_user'),
        cfg.StrOpt('dcnm_password'),
        cfg.StrOpt('timeout_resp'),
        cfg.StrOpt('segmentation_reuse_timeout',
                   default=com_const.SEG_REUSE_TIMEOUT),
        cfg.StrOpt('segmentation_id_min'),
        cfg.StrOpt('segmentation_id_max'),
        cfg.StrOpt('vlan_id_min', default=const.VLAN_ID_MIN),
        cfg.StrOpt('vlan_id_max', default=const.VLAN_ID_MAX),
        cfg.StrOpt('vlan_reuse_timeout', default=const.VLAN_REUSE_TIMEOUT),
        cfg.StrOpt('orchestrator_id', default=com_const.ORCHESTRATOR_ID),
]
cfg.CONF.register_opts(dcnm_opts, 'dcnm')


dfa_notify_opts = [
    cfg.StrOpt('cisco_dfa_notify_queue',
               default='cisco_dfa_%(service_name)s_notify')
]
cfg.CONF.register_opts(dfa_notify_opts, 'dfa_notify')


loadbalance_opts = [
    cfg.BoolOpt('lb_enabled', default=False),
    cfg.BoolOpt('lb_native', default=True)
]
cfg.CONF.register_opts(loadbalance_opts, 'loadbalance')


class CiscoDFAConfig(object):

    """Cisco DFA Mechanism Driver Configuration class."""

    @property
    def cfg(self):
        return cfg.CONF
