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


import sys

from oslo_config import cfg

from networking_cisco._i18n import _LE


from networking_cisco.apps.saf.agent.vdp import (
    lldpad_constants as vdp_const)
from networking_cisco.apps.saf.common import constants as com_const
from networking_cisco.apps.saf.common import utils
from networking_cisco.apps.saf.server.services import constants as const
from networking_cisco.apps.saf.server.services.firewall.native import (
    fw_constants as fw_const)


default_neutron_opts = {
    'DEFAULT': {
        'admin_port': 35357,
        'default_notification_level': 'INFO',
    },
}

default_dfa_agent_opts = {
    'dfa_agent': {
        'integration_bridge': 'br-int',
        'external_dfa_bridge': 'br-ethd',
    },
}

default_vdp_opts = {
    'vdp': {
        'mgrid2': vdp_const.VDP_MGRID,
        'typeid': vdp_const.VDP_TYPEID,
        'typeidver': vdp_const.VDP_TYPEID_VER,
        'vsiidfrmt': vdp_const.VDP_VSIFRMT_UUID,
        'hints': 'none',
        'filter': vdp_const.VDP_FILTER_GIDMACVID,
        'vdp_sync_timeout': vdp_const.VDP_SYNC_TIMEOUT,
    },
}

default_firewall_opts = {
    'firewall': {
        'device': fw_const.DEVICE,
        'sched_policy': fw_const.SCHED_POLICY,
        'fw_auto_serv_nwk_create': fw_const.AUTO_NWK_CREATE,
        'fw_service_host_profile': fw_const.HOST_PROF,
        'fw_service_host_fwd_mode': fw_const.HOST_FWD_MODE,
        'fw_service_part_vrf_profile': fw_const.PART_PROF,
        'fw_service_ext_profile': fw_const.EXT_PROF,
        'fw_service_ext_fwd_mode': fw_const.EXT_FWD_MODE,
        'fw_service_in_ip_start': fw_const.IN_IP_START,
        'fw_service_in_ip_end': fw_const.IN_IP_END,
        'fw_service_out_ip_start': fw_const.OUT_IP_START,
        'fw_service_out_ip_end': fw_const.OUT_IP_END,
        'fw_service_dummy_ip_subnet': fw_const.DUMMY_IP_SUBNET,
    },
}

DEFAULT_LOG_LEVELS = (
    "amqp=WARN, amqplib=WARN, oslo.messaging=WARN, pika=WARN, paramiko=WARN,"
    "paramiko.transport=WARN,"
    "paramiko.transport.sftp=WARN,"
    "pika.callback=WARN,oslo.messaging._drivers=WARN"
)

default_log_opts = {
    'dfa_log': {
        'use_syslog': 'False',
        'syslog_lgo_facility': 'LOG_USER',
        'log_dir': '.',
        'log_file': 'fabric_enabler.log',
        'log_level': 'WARNING',
        'log_format': '%(asctime)s %(levelname)8s [%(name)s] %(message)s',
        'log_date_format': '%Y-%m-%d %H:%M:%S',
        'default_log_levels': DEFAULT_LOG_LEVELS,
    },
}

default_sys_opts = {
    'sys': {
        'root_helper': 'sudo',
    },
}

default_dcnm_opts = {
    'dcnm': {
        'default_cfg_profile': 'defaultNetworkIpv4EfProfile',
        'default_vrf_profile': 'vrf-common-universal',
        'default_partition_name': 'CTX',
        'dcnm_net_ext': '(DCNM)',
        'gateway_mac': '20:20:00:00:00:AA',
        'dcnm_dhcp_leases': '/var/lib/dhcpd/dhcpd.leases',
        'dcnm_dhcp': 'false',
        'segmentation_reuse_timeout': com_const.SEG_REUSE_TIMEOUT,
        'vlan_id_min': const.VLAN_ID_MIN,
        'vlan_id_max': const.VLAN_ID_MAX,
        'vlan_reuse_timeout': const.VLAN_REUSE_TIMEOUT,
        'orchestrator_id': com_const.ORCHESTRATOR_ID
    },
}

default_notify_opts = {
    'dfa_notify': {
        'cisco_dfa_notify_queue': 'cisco_dfa_%(service_name)s_notify',
    },
}

default_opts_list = [
    default_log_opts,
    default_neutron_opts,
    default_dfa_agent_opts,
    default_vdp_opts,
    default_sys_opts,
    default_dcnm_opts,
    default_notify_opts,
    default_firewall_opts,
]


class CiscoDFAConfig(object):

    """Cisco DFA Mechanism Driver Configuration class."""

    def __init__(self, service_name=None):
        self.dfa_cfg = {}
        self._load_default_opts()
        args = sys.argv[1:]
        try:
            opts = [(args[i], args[i + 1]) for i in range(0, len(args), 2)]
        except IndexError:
            opts = []

        cfgfile = cfg.find_config_files(service_name)
        for k, v in opts:
            if k == '--config-file':
                cfgfile.insert(0, v)
        multi_parser = cfg.MultiConfigParser()
        read_ok = multi_parser.read(cfgfile)

        if len(read_ok) != len(cfgfile):
            raise cfg.Error(_LE("Failed to parse config file."))

        for parsed_file in multi_parser.parsed:
            for parsed_item in parsed_file.keys():
                if parsed_item not in self.dfa_cfg:
                    self.dfa_cfg[parsed_item] = {}
                for key, value in parsed_file[parsed_item].items():
                    self.dfa_cfg[parsed_item][key] = value[0]

        # Convert it to object.
        self._cfg = utils.Dict2Obj(self.dfa_cfg)

    def _load_default_opts(self):
        """Load default options."""

        for opt in default_opts_list:
            self.dfa_cfg.update(opt)

    @property
    def cfg(self):
        return self._cfg
