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

from novaclient import client
from novaclient import exceptions as nova_exc
from novaclient import utils as n_utils
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import uuidutils

from networking_cisco._i18n import _, _LE, _LI

from neutron import manager

from networking_cisco.plugins.cisco.common import (cisco_constants as
                                                   c_constants)

LOG = logging.getLogger(__name__)


SERVICE_VM_LIB_OPTS = [
    cfg.StrOpt('templates_path',
               default='/opt/stack/data/neutron/cisco/templates',
               help=_("Path to templates for hosting devices.")),
    cfg.StrOpt('service_vm_config_path',
               default='/opt/stack/data/neutron/cisco/config_drive',
               help=_("Path to config drive files for service VM instances.")),
]

cfg.CONF.register_opts(SERVICE_VM_LIB_OPTS, "general")


class ServiceVMManager(object):

    def __init__(self, is_auth_v3, user=None, passwd=None,
                 l3_admin_tenant=None, auth_url='', keystone_session=None):

        if is_auth_v3:
            self._nclient = client.Client('2', session=keystone_session,
                                          service_type="compute")
        else:
            self._nclient = client.Client('2', user, passwd, l3_admin_tenant,
                                          auth_url, service_type="compute")

    @property
    def _core_plugin(self):
        try:
            return self._plugin
        except AttributeError:
            self._plugin = manager.NeutronManager.get_plugin()
            return self._plugin

    def nova_services_up(self):
        """Checks if required Nova services are up and running.

        returns: True if all needed Nova services are up, False otherwise
        """
        required = set(['nova-conductor', 'nova-cert', 'nova-scheduler',
                       'nova-compute'])
        try:
            services = self._nclient.services.list()
        # There are several individual Nova client exceptions but they have
        # no other common base than Exception, hence the long list.
        except (nova_exc.UnsupportedVersion, nova_exc.CommandError,
                nova_exc.AuthorizationFailure, nova_exc.NoUniqueMatch,
                nova_exc.AuthSystemNotFound, nova_exc.NoTokenLookupException,
                nova_exc.EndpointNotFound, nova_exc.AmbiguousEndpoints,
                nova_exc.ConnectionRefused, nova_exc.ClientException,
                Exception) as e:
            LOG.error(_LE('Failure determining running Nova services: %s'), e)
            return False
        return not bool(required.difference(
            [service.binary for service in services
             if service.status == 'enabled' and service.state == 'up']))

    def get_service_vm_status(self, vm_id):
        try:
            status = self._nclient.servers.get(vm_id).status
        # There are several individual Nova client exceptions but they have
        # no other common base than Exception, hence the long list.
        except (nova_exc.UnsupportedVersion, nova_exc.CommandError,
                nova_exc.AuthorizationFailure, nova_exc.NoUniqueMatch,
                nova_exc.AuthSystemNotFound, nova_exc.NoTokenLookupException,
                nova_exc.EndpointNotFound, nova_exc.AmbiguousEndpoints,
                nova_exc.ConnectionRefused, nova_exc.ClientException,
                Exception) as e:
            LOG.error(_LE('Failed to get status of service VM instance '
                          '%(id)s, due to %(err)s'), {'id': vm_id, 'err': e})
            status = c_constants.SVM_ERROR
        return status

    #TODO(remove fake function later)
    def dispatch_service_vm(self, context, instance_name, vm_image,
                            vm_flavor, hosting_device_drv,
                            credentials_info, connectivity_info,
                            ports=None):
        if self._core_plugin.__class__.__name__ != 'CSR1kv_OVSNeutronPluginV2':
            return self.dispatch_service_vm_real(
                context, instance_name, vm_image, vm_flavor,
                hosting_device_drv, credentials_info, connectivity_info, ports)
        else:
            return self.dispatch_service_vm_fake(
                context, instance_name, vm_image, vm_flavor,
                hosting_device_drv, credentials_info, connectivity_info, ports)

    def dispatch_service_vm_real(
            self, context, instance_name, vm_image, vm_flavor,
            hosting_device_drv, credentials_info, connectivity_info,
            ports=None):
        mgmt_port = connectivity_info['mgmt_port']
        nics = [{'port-id': mgmt_port['id']}]
        for port in ports or {}:
            nics.append({'port-id': port['id']})

        try:
            image = n_utils.find_resource(self._nclient.images, vm_image)
            flavor = n_utils.find_resource(self._nclient.flavors, vm_flavor)
        except (nova_exc.CommandError, Exception) as e:
            LOG.error(_LE('Failure finding needed Nova resource: %s'), e)
            return

        try:
            # Assumption for now is that this does not need to be
            # plugin dependent, only hosting device type dependent.
            files = hosting_device_drv.create_config(context, credentials_info,
                                                     connectivity_info)
        except IOError:
            return

        try:
            server = self._nclient.servers.create(
                instance_name, image.id, flavor.id, nics=nics, files=files,
                config_drive=(files != {}))
        # There are several individual Nova client exceptions but they have
        # no other common base than Exception, therefore the long list.
        except (nova_exc.UnsupportedVersion, nova_exc.CommandError,
                nova_exc.AuthorizationFailure, nova_exc.NoUniqueMatch,
                nova_exc.AuthSystemNotFound, nova_exc.NoTokenLookupException,
                nova_exc.EndpointNotFound, nova_exc.AmbiguousEndpoints,
                nova_exc.ConnectionRefused, nova_exc.ClientException,
                Exception) as e:
            LOG.error(_LE('Failed to create service VM instance: %s'), e)
            return
        return {'id': server.id}

    #TODO(remove fake function later)
    def delete_service_vm(self, context, vm_id):
        if self._core_plugin.__class__.__name__ != 'CSR1kv_OVSNeutronPluginV2':
            return self.delete_service_vm_real(context, vm_id)
        else:
            return self.delete_service_vm_fake(context, vm_id)

    def delete_service_vm_real(self, context, vm_id):
        try:
            self._nclient.servers.delete(vm_id)
            return True
        # There are several individual Nova client exceptions but they have
        # no other common base than Exception, therefore the long list.
        except (nova_exc.UnsupportedVersion, nova_exc.CommandError,
                nova_exc.AuthorizationFailure, nova_exc.NoUniqueMatch,
                nova_exc.AuthSystemNotFound, nova_exc.NoTokenLookupException,
                nova_exc.EndpointNotFound, nova_exc.AmbiguousEndpoints,
                nova_exc.ConnectionRefused, nova_exc.ClientException,
                Exception) as e:
            LOG.error(_LE('Failed to delete service VM instance %(id)s, '
                          'due to %(err)s'), {'id': vm_id, 'err': e})
            return False

    # TODO(bobmel): Move this to fake_service_vm_lib.py file with
    # FakeServiceVMManager
    def dispatch_service_vm_fake(self, context, instance_name, vm_image,
                                 vm_flavor, hosting_device_drv,
                                 credentials_info, connectivity_info,
                                 ports=None):
        mgmt_port = connectivity_info['mgmt_port']
        try:
            # Assumption for now is that this does not need to be
            # plugin dependent, only hosting device type dependent.
            hosting_device_drv.create_config(context, credentials_info,
                                             connectivity_info)
        except IOError:
            return

        vm_id = uuidutils.generate_uuid()
        if mgmt_port is not None:
            p_dict = {'port': {'device_id': vm_id,
                               'device_owner': 'nova'}}
            self._core_plugin.update_port(context, mgmt_port['id'], p_dict)

        for port in ports or {}:
            p_dict = {'port': {'device_id': vm_id,
                               'device_owner': 'nova'}}
            self._core_plugin.update_port(context, port['id'], p_dict)

        myserver = {'server': {'adminPass': "MVk5HPrazHcG",
                    'id': vm_id,
                    'links': [{'href': "http://openstack.example.com/v2/"
                                       "openstack/servers/" + vm_id,
                               'rel': "self"},
                              {'href': "http://openstack.example.com/"
                                       "openstack/servers/" + vm_id,
                               'rel': "bookmark"}]}}

        return myserver['server']

    def delete_service_vm_fake(self, context, vm_id):
        result = True

        try:
            ports = self._core_plugin.get_ports(context,
                                                filters={'device_id': [vm_id]})
            for port in ports:
                self._core_plugin.delete_port(context, port['id'])
        except Exception as e:
            LOG.error(_LE('Failed to delete service VM %(id)s due to %(err)s'),
                      {'id': vm_id, 'err': e})
            result = False
        return result

    def interface_attach(self, vm_id, port_id):
        self._nclient.servers.interface_attach(vm_id, port_id=port_id,
                                               net_id=None, fixed_ip=None)
        LOG.debug('Nova interface add succeeded on VM:%(vm)s for port:%(id)s',
                  {'vm': vm_id, 'id': port_id})

    def interface_detach(self, vm_id, port_id):
        self._nclient.servers.interface_detach(vm_id, port_id)
        LOG.debug('Nova interface detach succeeded on VM:%(vm)s for '
                  'port:%(id)s', {'vm': vm_id, 'id': port_id})

    def vm_interface_list(self, vm_id):
        servers = self._nclient.servers.interface_list(vm_id)
        ips = []
        for s in servers:
            ips.append(s.fixed_ips[0]['ip_address'])
        LOG.info(_LI('Interfaces connected on VM:%(vm_id)s is %(ips)s'),
                 {'ips': ips, 'vm_id': vm_id})
