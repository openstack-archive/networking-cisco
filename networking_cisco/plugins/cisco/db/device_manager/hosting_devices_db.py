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

from oslo_db import exception as db_exc
from oslo_log import log as logging
from oslo_utils import excutils
from oslo_utils import timeutils
from oslo_utils import uuidutils
from sqlalchemy import exc as sql_exc
from sqlalchemy.orm import exc

from neutron.db import common_db_mixin
from neutron.plugins.common import constants as svc_constants

from networking_cisco.plugins.cisco.db.device_manager import hd_models
from networking_cisco.plugins.cisco.extensions import ciscohostingdevicemanager

LOG = logging.getLogger(__name__)

AUTO_DELETE_DEFAULT = ciscohostingdevicemanager.AUTO_DELETE_DEFAULT


class HostingDeviceDBMixin(
        ciscohostingdevicemanager.CiscoHostingDevicePluginBase,
        common_db_mixin.CommonDbMixin):
    """A class implementing DB functionality for hosting devices."""

    def create_hosting_device(self, context, hosting_device):
        LOG.debug("create_hosting_device() called")
        hd = hosting_device['hosting_device']
        with context.session.begin(subtransactions=True):
            credentials_id = hd.get('credentials_id')
            if credentials_id is None:
                hdt_db = self._get_hosting_device_template(context,
                                                           hd['template_id'])
                credentials_id = hdt_db['default_credentials_id']
            hd_db = hd_models.HostingDevice(
                id=self._get_id(hd),
                complementary_id=hd.get('complementary_id'),
                tenant_id=hd['tenant_id'],
                template_id=hd['template_id'],
                credentials_id=credentials_id,
                name=hd.get('name'),
                description=hd.get('description'),
                device_id=hd.get('device_id'),
                admin_state_up=hd.get('admin_state_up', True),
                management_ip_address=hd['management_ip_address'],
                management_port_id=hd['management_port_id'],
                protocol_port=hd.get('protocol_port'),
                cfg_agent_id=hd.get('cfg_agent_id'),
                created_at=hd.get('created_at', timeutils.utcnow()),
                status=hd.get('status', svc_constants.ACTIVE),
                tenant_bound=hd.get('tenant_bound'),
                auto_delete=hd.get('auto_delete', AUTO_DELETE_DEFAULT))
            context.session.add(hd_db)
        return self._make_hosting_device_dict(hd_db)

    def update_hosting_device(self, context, id, hosting_device):
        LOG.debug("update_hosting_device() called")
        hd = hosting_device['hosting_device']
        with context.session.begin(subtransactions=True):
            #TODO(bobmel): handle tenant_bound changes
            hd_query = context.session.query(hd_models.HostingDevice)
            if not hd_query.filter_by(id=id).update(hd):
                raise ciscohostingdevicemanager.HostingDeviceNotFound(id=id)
            #TODO(bobmel): notify_agent on changes to credentials,
            # admin_state_up, tenant_bound
        return self.get_hosting_device(context, id)

    def delete_hosting_device(self, context, id):
        LOG.debug("delete_hosting_device() called")
        try:
            with context.session.begin(subtransactions=True):
                hd_query = context.session.query(hd_models.HostingDevice)
                if not hd_query.filter_by(id=id).delete():
                    raise ciscohostingdevicemanager.HostingDeviceNotFound(
                        id=id)
        except db_exc.DBError as e:
            with excutils.save_and_reraise_exception() as ctxt:
                if isinstance(e.inner_exception, sql_exc.IntegrityError):
                    ctxt.reraise = False
                    raise ciscohostingdevicemanager.HostingDeviceInUse(id=id)

    def get_hosting_device(self, context, id, fields=None):
        LOG.debug("get_hosting_device() called")
        hd_db = self._get_hosting_device(context, id)
        return self._make_hosting_device_dict(hd_db)

    def get_hosting_devices(self, context, filters=None, fields=None,
                            sorts=None, limit=None, marker=None,
                            page_reverse=False):
        LOG.debug("get_hosting_devices() called")
        return self._get_collection(context, hd_models.HostingDevice,
                                    self._make_hosting_device_dict,
                                    filters=filters, fields=fields,
                                    sorts=sorts, limit=limit,
                                    marker_obj=marker,
                                    page_reverse=page_reverse)

    def create_hosting_device_template(self, context, hosting_device_template):
        LOG.debug("create_hosting_device_template() called")
        hdt = hosting_device_template['hosting_device_template']
        #TODO(bobmel): check service types
        with context.session.begin(subtransactions=True):
            hdt_db = hd_models.HostingDeviceTemplate(
                id=self._get_id(hdt),
                tenant_id=hdt['tenant_id'],
                name=hdt.get('name'),
                enabled=hdt.get('enabled', True),
                host_category=hdt['host_category'],
                service_types=hdt.get('service_types'),
                image=hdt.get('image'),
                flavor=hdt.get('flavor'),
                default_credentials_id=hdt.get('default_credentials_id'),
                configuration_mechanism=hdt.get('configuration_mechanism'),
                protocol_port=hdt.get('protocol_port'),
                booting_time=hdt.get('booting_time'),
                slot_capacity=hdt['slot_capacity'],
                desired_slots_free=hdt['desired_slots_free'],
                tenant_bound=':'.join(hdt['tenant_bound']),
                device_driver=hdt['device_driver'],
                plugging_driver=hdt['plugging_driver'])
            context.session.add(hdt_db)
        return self._make_hosting_device_template_dict(hdt_db)

    def update_hosting_device_template(self, context,
                                       id, hosting_device_template):
        LOG.debug("update_hosting_device_template() called")
        hdt = hosting_device_template['hosting_device_template']
        tenant_bound = hdt.get('tenant_bound')
        if tenant_bound is not None:
            hdt['tenant_bound'] = ':'.join(tenant_bound)
        with context.session.begin(subtransactions=True):
            hdt_query = context.session.query(hd_models.HostingDeviceTemplate)
            if not hdt_query.filter_by(id=id).update(hdt):
                raise ciscohostingdevicemanager.HostingDeviceTemplateNotFound(
                    id=id)
        return self.get_hosting_device_template(context, id)

    def delete_hosting_device_template(self, context, id):
        LOG.debug("delete_hosting_device_template() called")
        try:
            with context.session.begin(subtransactions=True):
                hdt_query = context.session.query(
                    hd_models.HostingDeviceTemplate)
                if not hdt_query.filter_by(id=id).delete():
                    raise (ciscohostingdevicemanager.
                        HostingDeviceTemplateNotFound(id=id))
        except db_exc.DBError as e:
            with excutils.save_and_reraise_exception() as ctxt:
                if isinstance(e.inner_exception, sql_exc.IntegrityError):
                    ctxt.reraise = False
                    raise (ciscohostingdevicemanager.
                           HostingDeviceTemplateInUse(id=id))

    def get_hosting_device_template(self, context, id, fields=None):
        LOG.debug("get_hosting_device_template() called")
        hdt_db = self._get_hosting_device_template(context, id)
        return self._make_hosting_device_template_dict(hdt_db)

    def get_hosting_device_templates(self, context, filters=None, fields=None,
                                     sorts=None, limit=None, marker=None,
                                     page_reverse=False):
        LOG.debug("get_hosting_device_templates() called")
        return self._get_collection(context, hd_models.HostingDeviceTemplate,
                                    self._make_hosting_device_template_dict,
                                    filters=filters, fields=fields,
                                    sorts=sorts, limit=limit,
                                    marker_obj=marker,
                                    page_reverse=page_reverse)

    def _get_id(self, res):
        uuid = res.get('id')
        if uuid:
            return uuid
        return uuidutils.generate_uuid()

    def _get_hosting_device(self, context, id):
        try:
            return self._get_by_id(context, hd_models.HostingDevice, id)
        except exc.NoResultFound:
            raise ciscohostingdevicemanager.HostingDeviceNotFound(id=id)

    def _make_hosting_device_dict(self, hd, fields=None):
        res = {'id': hd['id'],
               'complementary_id': hd['complementary_id'],
               'tenant_id': hd['tenant_id'],
               'template_id': hd['template_id'],
               'credentials_id': hd['credentials_id'],
               'name': hd['name'],
               'description': hd['description'],
               'device_id': hd['device_id'],
               'admin_state_up': hd['admin_state_up'],
               'management_ip_address': hd['management_ip_address'],
               'management_port_id': hd['management_port_id'],
               'protocol_port': hd['protocol_port'],
               'cfg_agent_id': hd['cfg_agent_id'],
               'created_at': hd['created_at'],
               'status': hd['status'],
               'tenant_bound': hd['tenant_bound'],
               'auto_delete': hd['auto_delete']}
        return self._fields(res, fields)

    def _get_hosting_device_template(self, context, id):
        try:
            return self._get_by_id(context, hd_models.HostingDeviceTemplate,
                                   id)
        except exc.NoResultFound:
            raise ciscohostingdevicemanager.HostingDeviceTemplateNotFound(
                id=id)

    def _make_hosting_device_template_dict(self, hdt, fields=None):
        tb = hdt['tenant_bound'].split(':') if len(hdt['tenant_bound']) else []
        res = {'id': hdt['id'],
               'tenant_id': hdt['tenant_id'],
               'name': hdt['name'],
               'enabled': hdt['enabled'],
               'host_category': hdt['host_category'],
               'service_types': hdt['service_types'],
               'image': hdt['image'],
               'flavor': hdt['flavor'],
               'default_credentials_id': hdt['default_credentials_id'],
               'configuration_mechanism': hdt['configuration_mechanism'],
               'protocol_port': hdt['protocol_port'],
               'booting_time': hdt['booting_time'],
               'slot_capacity': hdt['slot_capacity'],
               'desired_slots_free': hdt['desired_slots_free'],
               'tenant_bound': tb,
               'device_driver': hdt['device_driver'],
               'plugging_driver': hdt['plugging_driver']}
        return self._fields(res, fields)
