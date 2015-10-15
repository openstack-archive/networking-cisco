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

import networking_cisco.plugins.cisco.device_manager.plugging_drivers as plug


class NoopPluggingDriver(plug.PluginSidePluggingDriver):
    """This class defines a no-op plugging driver."""

    def create_hosting_device_resources(self, context, complementary_id,
                                        tenant_id, mgmt_context, max_hosted):
        return {'mgmt_port': None, 'ports': []}

    def get_hosting_device_resources(self, context, id, complementary_id,
                                     tenant_id, mgmt_nw_id):
        return {'mgmt_port': None, 'ports': []}

    def delete_hosting_device_resources(self, context, tenant_id, mgmt_port,
                                        **kwargs):
        pass

    def setup_logical_port_connectivity(self, context, port_db,
                                        hosting_device_id):
        pass

    def teardown_logical_port_connectivity(self, context, port_db,
                                        hosting_device_id):
        pass

    def extend_hosting_port_info(self, context, port_db, hosting_device,
                                 hosting_info):
        pass

    def allocate_hosting_port(self, context, router_id, port_db, network_type,
                              hosting_device_id):
        pass
