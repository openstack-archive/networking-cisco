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

import pprint
import sys

from oslo_config import cfg
import oslo_messaging
from oslo_utils import importutils

from neutron.common import config as common_config
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron import context as ctxt

from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_cfg_syncer)
from networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_cfg_validator)
from networking_cisco.plugins.cisco.common import cisco_constants

manager = importutils.try_import('ncclient.manager')
# USAGE:
# python asr1k_auto_config_check.py --config-file /etc/neutron/neutron.conf


class CiscoDevMgrRPC(object):
    """Agent side of the device manager RPC API."""

    def __init__(self, topic, host):
        self.host = host
        target = oslo_messaging.Target(topic=topic, version='1.0')
        self.client = n_rpc.get_client(target)

    def get_all_hosting_devices(self, context):
        """Get a list of all hosting devices."""
        cctxt = self.client.prepare()
        return cctxt.call(context,
                          'get_all_hosting_devices',
                          host=self.host)


class CiscoRoutingPluginRPC(object):
    """RoutingServiceHelper(Agent) side of the  routing RPC API."""

    def __init__(self, topic, host):
        self.host = host
        target = oslo_messaging.Target(topic=topic, version='1.1')
        self.client = n_rpc.get_client(target)

    def get_all_hosted_routers(self, context):
        """Make a remote process call to retrieve the sync data for
           routers that have been scheduled to a hosting device.

        :param context: session context
        """
        cctxt = self.client.prepare()
        return cctxt.call(context, 'cfg_sync_all_hosted_routers',
                          host=self.host)

    def get_hardware_router_type_id(self, context):
        """Get the ID for the ASR1k hardware router type."""
        cctxt = self.client.prepare()
        return cctxt.call(context,
                          'get_hardware_router_type_id',
                          host=self.host)


def get_nc_conn(hd):
    creds = hd['credentials']
    ncc_connection = manager.connect(host=hd['management_ip_address'],
                                     port=hd['protocol_port'],
                                     username=creds['user_name'],
                                     password=creds['password'],
                                     device_params={'name': "csr"}, timeout=30)

    return ncc_connection


def main():

    conf = cfg.CONF

    common_config.init(sys.argv[1:])
    conf(project='neutron')

    host = conf.host
    devmgr_rpc = CiscoDevMgrRPC(cisco_constants.DEVICE_MANAGER_PLUGIN, host)
    plugin_rpc = CiscoRoutingPluginRPC(topics.L3PLUGIN, host)

    context = ctxt.Context('', '')
    # TODO(create an admin context instead)

    hardware_router_type_id = plugin_rpc.get_hardware_router_type_id(context)
    print("Hardware router type ID: %s" % hardware_router_type_id)

    routers = plugin_rpc.get_all_hosted_routers(context)
    hosting_devs = devmgr_rpc.get_all_hosting_devices(context)

    print("ROUTERS: %s" % pprint.pformat(routers))

    for hd in hosting_devs['hosting_devices']:
        print("HOSTING DEVICE: %s, IP: %s\n-----------------" %
            (hd['id'], hd['management_ip_address']))

        if hd['template_id'] != hardware_router_type_id:
            continue

        conn = get_nc_conn(hd)

        cfg_cleaner = asr1k_cfg_syncer.ConfigSyncer(routers,
                                                    None,
                                                    hd,
                                                    test_mode=True)

        cfg_checker = asr1k_cfg_validator.ConfigValidator(routers,
                                                          hd,
                                                          conn)

        invalid_cfg = cfg_cleaner.delete_invalid_cfg(conn)
        missing_cfg = cfg_checker.process_routers_data(routers)

        print("Invalid Cfg: %s" % invalid_cfg)
        print("Missing Cfg: %s\n\n" % missing_cfg)

        conn.close_session()


if __name__ == "__main__":
    main()
