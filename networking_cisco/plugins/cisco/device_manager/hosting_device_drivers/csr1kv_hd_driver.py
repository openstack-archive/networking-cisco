# Copyright 2014 Cisco Systems, Inc.  All rights reserved.
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
from oslo_utils import excutils

from networking_cisco._i18n import _, _LE

from networking_cisco.plugins.cisco.device_manager import (
    hosting_device_drivers)

LOG = logging.getLogger(__name__)


# Length mgmt port UUID to be part of VM's config drive filename
CFG_DRIVE_UUID_START = 24
CFG_DRIVE_UUID_LEN = 12

CSR1KV_HD_DRIVER_OPTS = [
    cfg.StrOpt('csr1kv_configdrive_template', default='csr1kv_cfg_template',
               help=_("CSR1kv configdrive template file.")),
]

cfg.CONF.register_opts(CSR1KV_HD_DRIVER_OPTS, "hosting_devices")


class CSR1kvHostingDeviceDriver(hosting_device_drivers.HostingDeviceDriver):

    def hosting_device_name(self):
        return "CSR1kv"

    def create_config(self, context, credentials_info, connectivity_info):
        mgmt_port = connectivity_info['mgmt_port']
        mgmt_ip = mgmt_port['fixed_ips'][0]['ip_address']
        params = {'<user_name>': credentials_info.get('user_name', ''),
                  '<password>': credentials_info.get('password', ''),
                  '<ip>': mgmt_ip,
                  '<mask>': connectivity_info['netmask'],
                  '<gw>': connectivity_info['gateway_ip'],
                  '<name_server_1>': connectivity_info['name_server_1'],
                  '<name_server_2>': connectivity_info['name_server_2']}
        try:
            cfg_template_filename = (
                cfg.CONF.general.templates_path + "/" +
                cfg.CONF.hosting_devices.csr1kv_configdrive_template)
            vm_cfg_data = ''
            with open(cfg_template_filename, 'r') as cfg_template_file:
                # insert proper instance values in the template
                for line in cfg_template_file:
                    tokens = line.strip('\n').split(' ')
                    line = ' '.join(map(lambda x: params.get(x, x),
                                        tokens)) + '\n'
                    vm_cfg_data += line
            return {'iosxe_config.txt': vm_cfg_data}
        except IOError:
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE('Failed to create initial device '
                                  'configuration.'))
