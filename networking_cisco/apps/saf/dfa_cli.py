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

"""CLI module for fabric enabler."""

from __future__ import print_function

import cmd
import itertools
import pkg_resources
import platform
from prettytable import PrettyTable
import six
import sys

from oslo_serialization import jsonutils

from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.common import constants
from networking_cisco.apps.saf.common import dfa_exceptions as dexc
from networking_cisco.apps.saf.common import rpc
from networking_cisco.apps.saf.common import utils
from networking_cisco.apps.saf.server import cisco_dfa_rest as cdr


class DfaCli(cmd.Cmd):

    """Represents fabric enabler command line interface."""

    prompt = '(enabler) '
    intro = 'Fabric Enabler Command Line Interface'

    def __init__(self):
        self.ctl_host = platform.node()
        cmd.Cmd.__init__(self)
        self._cfg = config.CiscoDFAConfig().cfg
        self.dcnm_client = cdr.DFARESTClient(self._cfg)
        self.setup_client_rpc()
        self.clnt = None

    def setup_client_rpc(self):
        url = self._cfg.dfa_rpc.transport_url % (
            {'ip': self.ctl_host})
        self.clnt = rpc.DfaRpcClient(url, constants.DFA_SERVER_QUEUE)

    def set_static_ip_address(self, ipaddr, macaddr):
        context = {}
        args = jsonutils.dumps(dict(mac=macaddr, ip=ipaddr))
        msg = self.clnt.make_msg('set_static_ip_address', context, msg=args)
        resp = self.clnt.cast(msg)
        return resp

    def do_set_static_ip(self, line):
        args = line.split()
        ip_mac = dict(itertools.izip_longest(args[::2], args[1::2],
                                             fillvalue=''))
        ipaddr = ip_mac.get('--ip')
        macaddr = ip_mac.get('--mac')
        # Some sanity check.
        if (not ipaddr or not macaddr or
                not utils.is_valid_ipv4(ipaddr)
                or not utils.is_valid_mac(macaddr)):
            print('Invalid input parameters.\n'
                  'Usage:'
                  ' set_static_ip --mac <mac address> --ip <ip address>')
            return

        self.set_static_ip_address(ipaddr, macaddr)

    def do_get_config_profile(self, line):
        try:
            cfgp_list = self.dcnm_client.config_profile_list()
            if not cfgp_list:
                print('No config profile found.')
                return
        except dexc.DfaClientRequestFailed:
            print('Failed to access DCNM.')
            return

        cfg_table = PrettyTable(['Config Profile Name', 'Alias'])
        for cfg in cfgp_list:
            if cfg.startswith('defaultNetwork'):
                cfg_alias = cfg.split('defaultNetwork')[1].split('Profile')[0]
            elif cfg.endswith('Profile'):
                cfg_alias = cfg.split('Profile')[0]
            else:
                cfg_alias = cfg
            cfg_table.add_row([cfg, cfg_alias])

        print(cfg_table)

    def do_list_networks(self, line):
        tenant_name = line
        if not tenant_name:
            print('Tenant name is required.')
            return

        try:
            part_name = self._cfg.dcnm.default_partition_name
            net_list = self.dcnm_client.list_networks(tenant_name, part_name)
            if not net_list:
                print('No network found.')
                return
        except dexc.DfaClientRequestFailed:
            print('Failed to access DCNM.')
            return

        list_table = None
        for net in net_list:
            columns = net.keys()
            if list_table is None:
                list_table = PrettyTable(columns)
            if list_table:
                list_table.add_row(net.values())

        print(list_table)

    def do_get_network(self, line):
        args = line.split()
        if len(args) < 2:
            print('Invalid parameters')
            return

        if not args[1].isdigit():
            print('Invalid segmentation id %s.', args[1])
            return

        try:
            net = self.dcnm_client.get_network(args[0], args[1])
            if not net:
                print('No network found.')
                return
        except dexc.DfaClientRequestFailed:
            print('Failed to access DCNM.')
            return

        net_table = PrettyTable(net.keys())
        row = []
        for key, val in six.iteritems(net):
            if key == 'configArg' or key == 'dhcpScope':
                val = str(val)
            row.append(val)
        net_table.add_row(row)

        print(net_table)

    def do_list_organizations(self, line):
        '''Get list of organization on DCNM.'''

        org_list = self.dcnm_client.list_organizations()
        if not org_list:
            print('No organization found.')
            return

        org_table = PrettyTable(['Organization Name'])
        for org in org_list:
            org_table.add_row([org['organizationName']])

        print(org_table)

    def do_get_dcnm_version(self, line):
        '''Get current version of DCNM.'''

        ver = self.dcnm_client.get_version()

        print(ver)

    def do_get_enabler_version(self, line):
        '''Get current fabric enabler's package version.'''

        print('Version: %s' % pkg_resources.get_distribution(
            "networking-cisco").version)

    def help_get_config_profile(self):
        print('\n'.join(['get_config_profile',
                         'Display supported configuration profile in DCNM']))

    def help_list_networks(self):
        print('\n'.join(['list_networks tenant-name',
                         'Display list of network for given tenant.']))

    def help_get_network(self):
        print('\n'.join(['get_network tenant-name segmentation_id',
                         'Display network details.']))

    def help_set_static_ip(self):
        print('\n'.join(['set_static_ip --mac <mac address> --ip <ip address>',
                         'Set static ip address for an instance.']))

    def emptyline(self):
        return

    def do_prompt(self, line):
        '''Set prompt for the command line.'''

        self.prompt = line + ' '

    def do_quit(self, line):
        '''exit the program.'''

        sys.exit(1)

    def do_EOF(self, line):
        '''Use Ctrl-D to exit the program.'''

        return True

    # Shortcuts
    do_q = do_quit


def dfa_cli():
    # Add default config file.
    if len(sys.argv[1:]) % 2:
        sys.argv.append("")
    sys.argv.append('--config-file')
    sys.argv.append('/etc/saf/enabler_conf.ini')
    DfaCli().cmdloop()

if __name__ == '__main__':
    sys.exit(dfa_cli())
