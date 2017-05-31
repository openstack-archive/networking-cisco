# Copyright 2017 Cisco Systems, Inc.  All rights reserved.
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

from neutron_lib import constants
from oslo_utils import uuidutils

from networking_cisco import backwards_compatibility as bc
from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routerrole


_uuid = uuidutils.generate_uuid
HA_INFO = 'ha_info'
ROUTER_ROLE_HA_REDUNDANCY = c_constants.ROUTER_ROLE_HA_REDUNDANCY
ROUTER_ROLE_GLOBAL = c_constants.ROUTER_ROLE_GLOBAL


class CfgAgentTestSupportMixin(object):

    def create_router_port(self, network_uuid, vlan_tag, k, num_subnets,
                           router_id, admin_state_up=True,
                           mac_address='ca:fe:de:ad:be:ef',
                           device_owner=constants.DEVICE_OWNER_ROUTER_INTF,
                           ha_enabled=True, ha_group=1060,
                           is_user_visible=True):
        int_fixed_ips = []
        int_subnets = []
        ha_fixed_ips = []
        sn_ids = sorted([_uuid() for i in range(num_subnets)])
        phy_infc = 'GigabitEthernet0/0/0'
        for i in range(num_subnets):
            sn_id = sn_ids[i]
            if device_owner == constants.DEVICE_OWNER_ROUTER_INTF:
                prefix_len = 24
                host_id = 4
            else:
                prefix_len = 28 if i == 0 else 27
                host_id = 1
            int_fixed_ips.append({'ip_address': '%s.4.%s.%s' % (k, i, host_id),
                                  'prefixlen': prefix_len,
                                  'subnet_id': sn_id})
            int_subnets.append({'id': sn_id,
                                'cidr': '%s.4.%s.0/%s' % (k, i, prefix_len),
                                'gateway_ip': '%s.4.%s.1' % (k, i)})
            ha_fixed_ips.append({'ip_address': '%s.4.%s.254' % (k, i),
                                 'prefixlen': prefix_len,
                                 'subnet_id': sn_id})
        port = {
            'id': _uuid(),
            'network_id': network_uuid,
            'admin_state_up': admin_state_up,
            'device_owner': device_owner,
            'device_id': router_id,
            'fixed_ips': int_fixed_ips,
            'mac_address': mac_address,
            'subnets': int_subnets,
            'hosting_info': {
                'physical_interface': phy_infc,
                'segmentation_id': vlan_tag
            }
        }
        if ha_enabled is True:
            port[HA_INFO] = {'group': ha_group}
            if (device_owner == constants.DEVICE_OWNER_ROUTER_INTF or
                    is_user_visible is False):
                port[HA_INFO]['ha_port'] = {
                    'id': _uuid(),
                    'fixed_ips': ha_fixed_ips,
                    'subnets': int_subnets,
                    'network_id': network_uuid,
                    'admin_state_up': admin_state_up,
                    'device_owner': device_owner,
                    'mac_address': mac_address
                }
            else:
                port[HA_INFO]['ha_port'] = port
        return port

    def prepare_router_data(self, set_gateway=True, enable_snat=None,
                            num_ext_subnets=1, num_internal_ports=1,
                            same_internal_nw=False, is_global=False,
                            ha_enabled=True, is_user_visible=True):
        router_id = _uuid()
        if set_gateway is True:
            ex_gw_port = self.create_router_port(
                _uuid(), 100, 19, num_ext_subnets, router_id,
                device_owner=constants.DEVICE_OWNER_ROUTER_GW)
        else:
            ex_gw_port = None
        int_ports = []
        num_internal_subnets = 1 if is_global is False else num_ext_subnets
        nw_uuid = _uuid()
        vlan_tag = 200
        for j in range(num_internal_ports):
            k = 35 + j
            if ha_enabled is True:
                group_id = 1060 + j
                p = self.create_router_port(
                    nw_uuid, vlan_tag, k, num_internal_subnets, router_id,
                    ha_group=group_id)
            else:
                p = self.create_router_port(
                    nw_uuid, vlan_tag, k, num_internal_subnets, router_id,
                    ha_enabled=False)
            int_ports.append(p)
            if same_internal_nw is False:
                nw_uuid = _uuid()
                vlan_tag += 1

        hosting_device = {
            'id': _uuid(),
            'name': "CSR1kv_template",
            'booting_time': 300,
            'host_category': "VM",
            'management_ip_address': '20.0.0.5',
            'protocol_port': 22,
            'credentials': {
                'username': "user",
                'password': "4getme"
            }
        }
        router = {
            'id': router_id,
            'status': 'ACTIVE',
            'admin_state_up': True,
            bc.constants.INTERFACE_KEY: int_ports,
            'routes': [],
            'hosting_device': hosting_device,
            'router_type': ''
        }
        if is_global is True:
            router['gw_port'] = None
            router[routerrole.ROUTER_ROLE_ATTR] = ROUTER_ROLE_GLOBAL
        else:
            router['gw_port'] = ex_gw_port
            if is_user_visible is True:
                router[routerrole.ROUTER_ROLE_ATTR] = None
            else:
                router[routerrole.ROUTER_ROLE_ATTR] = ROUTER_ROLE_HA_REDUNDANCY
        if enable_snat is not None:
            router['enable_snat'] = enable_snat
        if ha_enabled is True:
            ha_details = {
                'priority': 10,
                'redundancy_level': 1,
                'state': 'ACTIVE',
                'type': 'HSRP',
                'redundancy_routers': [{'id': _uuid(),
                                        'priority': 20,
                                        'state': 'STANDBY'}]
            }
            if is_global is True:
                ha_details['redundancy_level'] = 2
                ha_details['redundancy_routers'].append({'id': router_id,
                                                         'priority': 10,
                                                         'state': 'ACTIVE'})
            router[ha.ENABLED] = True
            router[ha.DETAILS] = ha_details
        else:
            router[ha.ENABLED] = False
        return router, int_ports

    def prepare_hosting_device_params(self):
        device_params = {
            'management_ip_address': 'fake_ip',
            'protocol_port': 22,
            'credentials': {
                'user_name': "stack",
                'password': "cisco"
            },
            'timeout': None,
            'id': '0000-1',
            'device_id': 'ASR-1'
        }
        return device_params
