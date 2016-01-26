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

from networking_cisco._i18n import _


n1kv_opts = [
    cfg.ListOpt('n1kv_vsm_ips',
               help=_("Comma Separated IP Addresses of the Cisco Nexus1000V "
                      "VSMs.")),
    cfg.StrOpt('username',
               help=_("Username for all configured Cisco Nexus1000V VSMs.")),
    cfg.StrOpt('password',
               help=_("Password for all configured Cisco Nexus1000V VSMs."),
               secret=True),
    cfg.StrOpt('default_policy_profile', default='default-pp',
               help=_("Cisco Nexus1000V default policy profile.")),
    cfg.BoolOpt('restrict_policy_profiles', default=False,
               help=_("Restrict the visibility of policy profiles to the "
                      "tenants.")),
    cfg.IntOpt('poll_duration', default=60,
               help=_("Cisco Nexus1000V policy profile polling duration in "
                      "seconds.")),
    cfg.IntOpt('http_pool_size', default=4,
               help=_("Number of threads to use to make HTTP requests.")),
    cfg.IntOpt('http_timeout', default=15,
               help=_("HTTP timeout, in seconds, for connections to the "
                      "Cisco Nexus1000V VSMs.")),
    cfg.IntOpt('sync_interval', default=300,
               help=_("Time interval between consecutive neutron-VSM syncs.")),
    cfg.IntOpt('max_vsm_retries', default=2,
               help=_("Maximum number of retry attempts for VSM REST API.")),
    cfg.BoolOpt('restrict_network_profiles', default=False,
               help=_("Restrict the visibility of network profiles to the "
                      "tenants.")),
]


cfg.CONF.register_opts(n1kv_opts, "ml2_cisco_n1kv")


def get_vsm_hosts():
    """Retrieve a list of VSM ip addresses.
    :return: list of VSM ip addresses
    """
    return cfg.CONF.ml2_cisco_n1kv.n1kv_vsm_ips
