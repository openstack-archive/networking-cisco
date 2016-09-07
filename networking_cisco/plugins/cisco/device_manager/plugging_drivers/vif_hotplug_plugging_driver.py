# Copyright 2015 Cisco Systems, Inc.  All rights reserved.
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
eventlet.monkey_patch()

from novaclient import exceptions as nova_exc
from oslo_log import log as logging
from sqlalchemy.sql import expression as expr

from neutron.db import models_v2
from neutron import manager
from neutron_lib import exceptions as n_exc

from networking_cisco import backwards_compatibility as bc_attr
from networking_cisco._i18n import _, _LE, _LW
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.device_manager import plugging_drivers
from networking_cisco.plugins.cisco.device_manager.plugging_drivers import (
    utils)

LOG = logging.getLogger(__name__)

DELETION_ATTEMPTS = 4
SECONDS_BETWEEN_DELETION_ATTEMPTS = 1


class PortNotUnBoundException(n_exc.InUse):
    message = _("Port: %(port_id)s not unbound yet.")


class VIFHotPlugPluggingDriver(plugging_drivers.PluginSidePluggingDriver,
                               utils.PluggingDriverUtilsMixin):
    """Driver class for service VMs used with Neutron plugins supporting
    VIF hot-plug.
    """

    def __init__(self):
        self._gt_pool = eventlet.GreenPool()

    @property
    def _core_plugin(self):
        return manager.NeutronManager.get_plugin()

    @property
    def _dev_mgr(self):
        return manager.NeutronManager.get_service_plugins().get(
            cisco_constants.DEVICE_MANAGER)

    def create_hosting_device_resources(self, context, complementary_id,
                                        tenant_id, mgmt_context, max_hosted):
        """Create resources for a hosting device in a plugin specific way."""
        mgmt_port = None
        if mgmt_context and mgmt_context.get('mgmt_nw_id') and tenant_id:
            # Create port for mgmt interface
            p_spec = {'port': {
                'tenant_id': tenant_id,
                'admin_state_up': True,
                'name': 'mgmt',
                'network_id': mgmt_context['mgmt_nw_id'],
                'mac_address': bc_attr.ATTR_NOT_SPECIFIED,
                'fixed_ips': self._mgmt_subnet_spec(context, mgmt_context),
                'device_id': "",
                # Use device_owner attribute to ensure we can query for these
                # ports even before Nova has set device_id attribute.
                'device_owner': complementary_id}}
            try:
                mgmt_port = self._core_plugin.create_port(context, p_spec)
            except n_exc.NeutronException as e:
                LOG.error(_LE('Error %s when creating management port. '
                              'Cleaning up.'), e)
                self.delete_hosting_device_resources(
                    context, tenant_id, mgmt_port)
                mgmt_port = None
        # We are setting the 'ports' to an empty list as it is expected by
        # the callee: device_handling_db._create_csr1kv_vm_hosting_device()
        return {'mgmt_port': mgmt_port, 'ports': []}

    def get_hosting_device_resources(self, context, id, complementary_id,
                                     tenant_id, mgmt_nw_id):
        """Returns information about all resources for a hosting device."""
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
                raise Exception
            else:
                mgmt_port = port
        return {'mgmt_port': mgmt_port}

    def delete_hosting_device_resources(self, context, tenant_id, mgmt_port,
                                        **kwargs):
        """Deletes resources for a hosting device in a plugin specific way."""

        if mgmt_port is not None:
            try:
                self._cleanup_hosting_port(context, mgmt_port['id'])
            except n_exc.NeutronException as e:
                LOG.error(_LE("Unable to delete port:%(port)s after %(tries)d"
                              " attempts due to exception %(exception)s. "
                              "Skipping it"), {'port': mgmt_port['id'],
                                               'tries': DELETION_ATTEMPTS,
                                               'exception': str(e)})

    @utils.retry(n_exc.NeutronException, DELETION_ATTEMPTS,
                 SECONDS_BETWEEN_DELETION_ATTEMPTS)
    def _delete_resource_port(self, context, port_id):
        try:
            self._core_plugin.delete_port(context, port_id)
            LOG.debug("Port %s deleted successfully", port_id)
        except n_exc.PortNotFound:
            LOG.warning(_LW('Trying to delete port:%s, but port is not found'),
                        port_id)

    @utils.retry(PortNotUnBoundException, tries=6)
    def _is_port_unbound(self, context, port_db):
        # Nova will unbind the port asynchronously after the unplug. So we need
        # to expire the port db to fetch the updated info.
        context.session.expire(port_db)
        port_db = self._core_plugin._get_port(context, port_db.id)
        if port_db.device_id == '' and port_db.device_owner == '':
            return True
        else:
            raise PortNotUnBoundException(port_id=port_db.id)

    def _cleanup_hosting_port(self, context, port_id):
        # Needs a bit of time for gateway port to unbind
        eventlet.sleep(2)
        port_db = self._core_plugin._get_port(context, port_id)
        if self._is_port_unbound(context, port_db):
            LOG.debug("Port:%s unbound. Going to delete it", port_db.name)
            self._delete_resource_port(context, port_id)

    def _attach_hosting_port(self, hosting_device_id, hosting_port_id):
        # Give a little bit of time for CSR to get out of vm building state
        eventlet.sleep(10)
        try:
            self.svc_vm_mgr.interface_attach(
                hosting_device_id, hosting_port_id)
            LOG.debug("_attach_hosting_port Setup logical port completed")
        except Exception as e:
            LOG.error(_LE("_attach_hosting_port Failed to attach interface:"
                          "%(p_id)s on hosting device:%(hd_id)s due to "
                          "error %(error)s"), {'p_id': hosting_port_id,
                                               'hd_id': hosting_device_id,
                                               'error': str(e)})

    def setup_logical_port_connectivity(self, context, port_db,
                                        hosting_device_id):
        """Establishes connectivity for a logical port.

        This is done by hot plugging the interface(VIF) corresponding to the
        port from the CSR.
        """
        hosting_port = port_db.hosting_info.hosting_port
        if hosting_port:
            try:
                self._dev_mgr.svc_vm_mgr.interface_attach(hosting_device_id,
                                                          hosting_port.id)
                LOG.debug("Setup logical port completed for port:%s",
                          port_db.id)
            except nova_exc.Conflict as e:
                # CSR is still in vm_state building
                LOG.debug("Failed to attach interface - spawn thread "
                          "error %(error)s", {'error': str(e)})
                self._gt_pool.spawn_n(self._attach_hosting_port,
                                      hosting_device_id, hosting_port.id)
            except Exception as e:
                LOG.error(_LE("Failed to attach interface mapped to port:"
                              "%(p_id)s on hosting device:%(hd_id)s due to "
                              "error %(error)s"), {'p_id': hosting_port.id,
                                                   'hd_id': hosting_device_id,
                                                   'error': str(e)})

    def teardown_logical_port_connectivity(self, context, port_db,
                                           hosting_device_id):
        """Removes connectivity for a logical port.

        Unplugs the corresponding data interface from the CSR.
        """
        if port_db is None or port_db.get('id') is None:
            LOG.warning(_LW("Port id is None! Cannot remove port "
                            "from hosting_device:%s"), hosting_device_id)
            return
        hosting_port_id = port_db.hosting_info.hosting_port.id
        try:
            self._dev_mgr.svc_vm_mgr.interface_detach(hosting_device_id,
                                                      hosting_port_id)
            self._gt_pool.spawn_n(self._cleanup_hosting_port, context,
                                  hosting_port_id)
            LOG.debug("Teardown logicalport completed for port:%s", port_db.id)

        except Exception as e:
            LOG.error(_LE("Failed to detach interface corresponding to port:"
                          "%(p_id)s on hosting device:%(hd_id)s due to "
                          "error %(error)s"), {'p_id': hosting_port_id,
                                               'hd_id': hosting_device_id,
                                               'error': str(e)})

    def extend_hosting_port_info(self, context, port_db, hosting_device,
                                 hosting_info):
        """Extends hosting information for a logical port."""
        return

    def allocate_hosting_port(self, context, router_id, port_db, network_type,
                              hosting_device_id):
        """Allocates a hosting port for a logical port.

        We create a hosting port for the router port
        """
        l3admin_tenant_id = self._dev_mgr.l3_tenant_id()
        hostingport_name = 'hostingport_' + port_db['id'][:8]
        p_spec = {'port': {
                  'tenant_id': l3admin_tenant_id,
                  'admin_state_up': True,
                  'name': hostingport_name,
                  'network_id': port_db['network_id'],
                  'mac_address': bc_attr.ATTR_NOT_SPECIFIED,
                  'fixed_ips': [],
                  'device_id': '',
                  'device_owner': '',
                  'port_security_enabled': False}}
        try:
            hosting_port = self._core_plugin.create_port(context, p_spec)
        except n_exc.NeutronException as e:
            LOG.error(_LE('Error %s when creating hosting port'
                          'Cleaning up.'), e)
            self.delete_hosting_device_resources(
                context, l3admin_tenant_id, hosting_port)
            hosting_port = None
        finally:
            if hosting_port:
                return {'allocated_port_id': hosting_port['id'],
                        'allocated_vlan': None}
            else:
                return None
