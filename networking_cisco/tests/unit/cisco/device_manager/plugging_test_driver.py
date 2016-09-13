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

import eventlet

from oslo_log import log as logging
from sqlalchemy.sql import expression as expr

from networking_cisco._i18n import _LE, _LI, _LW

from neutron.api.v2 import attributes
from neutron.db import models_v2

from neutron_lib import exceptions as n_exc

from networking_cisco.plugins.cisco.device_manager.plugging_drivers import (
    n1kv_ml2_trunking_driver)

LOG = logging.getLogger(__name__)


DELETION_ATTEMPTS = 5
SECONDS_BETWEEN_DELETION_ATTEMPTS = 3


class TestPluggingDriver(n1kv_ml2_trunking_driver.N1kvML2TrunkingPlugDriver):
    """Driver class for unit tests."""

    def create_hosting_device_resources(self, context, complementary_id,
                                        tenant_id, mgmt_context, max_hosted):
        mgmt_port = None
        if mgmt_context and mgmt_context.get('mgmt_nw_id') and tenant_id:
            # Create port for mgmt interface
            p_spec = {'port': {
                'tenant_id': tenant_id,
                'admin_state_up': True,
                'name': 'mgmt',
                'network_id': mgmt_context['mgmt_nw_id'],
                'mac_address': attributes.ATTR_NOT_SPECIFIED,
                'fixed_ips': self._mgmt_subnet_spec(context, mgmt_context),
                'device_id': "",
                # Use device_owner attribute to ensure we can query for these
                # ports even before Nova has set device_id attribute.
                'device_owner': complementary_id}}
            try:
                mgmt_port = self._core_plugin.create_port(context,
                                                          p_spec)
            except n_exc.NeutronException as e:
                LOG.error(_LE('Error %s when creating service VM resources. '
                              'Cleaning up.'), e)
                resources = {}
                self.delete_hosting_device_resources(
                    context, tenant_id, mgmt_port, **resources)
                mgmt_port = None
        return {'mgmt_port': mgmt_port}

    def get_hosting_device_resources(self, context, id, complementary_id,
                                     tenant_id, mgmt_nw_id):
        ports, nets, subnets = [], [], []
        mgmt_port = None
        # Ports for hosting device may not yet have 'device_id' set to
        # Nova assigned uuid of VM instance. However, those ports will still
        # have 'device_owner' attribute set to complementary_id. Hence, we
        # use both attributes in the query to ensure we find all ports.
        query = context.session.query(models_v2.Port)
        query = query.filter(expr.or_(
            models_v2.Port.device_id == id,
            models_v2.Port.device_owner == complementary_id))
        for port in query:
            if port['network_id'] != mgmt_nw_id:
                ports.append(port)
                nets.append({'id': port['network_id']})
                subnets.append({'id': port['fixed_ips'][0]['subnet_id']})
            else:
                mgmt_port = port
        return {'mgmt_port': mgmt_port,
                'ports': ports, 'networks': nets, 'subnets': subnets}

    def delete_hosting_device_resources(self, context, tenant_id, mgmt_port,
                                        **kwargs):
        attempts = 1
        while mgmt_port is not None:
            if attempts == DELETION_ATTEMPTS:
                LOG.warning(_LW('Aborting resource deletion after %d '
                                'unsuccessful attempts'), DELETION_ATTEMPTS)
                return
            else:
                if attempts > 1:
                    eventlet.sleep(SECONDS_BETWEEN_DELETION_ATTEMPTS)
                LOG.info(_LI('Resource deletion attempt %d starting'),
                         attempts)
            # Remove anything created.
            if mgmt_port is not None:
                ml = {mgmt_port['id']}
                self._delete_resources(context, "management port",
                                       self._core_plugin.delete_port,
                                       n_exc.PortNotFound, ml)
                if not ml:
                    mgmt_port = None
            attempts += 1
        LOG.info(_LI('Resource deletion succeeded'))

    def _delete_resources(self, context, name, deleter, exception_type,
                          resource_ids):
        for item_id in resource_ids.copy():
            try:
                deleter(context, item_id)
                resource_ids.remove(item_id)
            except exception_type:
                resource_ids.remove(item_id)
            except n_exc.NeutronException as e:
                LOG.error(_LE('Failed to delete %(resource_name) %(net_id)s '
                              'for service vm due to %(err)s'),
                          {'resource_name': name, 'net_id': item_id, 'err': e})

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
        return {'allocated_port_id': None,
                'allocated_vlan': None}
