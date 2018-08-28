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

import webob.exc

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from oslo_utils import uuidutils
import six

from networking_cisco._i18n import _
from networking_cisco import backwards_compatibility as bc
from networking_cisco.config import base

LOG = logging.getLogger(__name__)

credentials_subopts = [
    cfg.StrOpt('name',
        help=_('name of credential')),
    cfg.StrOpt('description',
        help=_('description of credential')),
    cfg.StrOpt('user_name',
        help=_('the user name')),
    cfg.StrOpt('password',
        help=_('the password'),
        secret=True),
    cfg.StrOpt('type',
        help=_('the credential type'))
]


hosting_device_credentials = base.SubsectionOpt(
    'cisco_hosting_device_credential',
    dest='cisco_hosting_device_credential',
    help=_("Subgroups that allow you to specify the hosting device "
           "credentials"),
    subopts=credentials_subopts)


template_subopts = [
    cfg.StrOpt('name'),
    cfg.BoolOpt('enabled'),
    cfg.StrOpt('host_category'),
    cfg.StrOpt('service_types'),
    cfg.StrOpt('image'),
    cfg.StrOpt('flavor'),
    cfg.StrOpt('default_credentials_id'),
    cfg.StrOpt('configuration_mechanism'),
    cfg.IntOpt('protocol_port'),
    cfg.IntOpt('booting_time'),
    cfg.IntOpt('slot_capacity'),
    cfg.IntOpt('desired_slots_free'),
    cfg.StrOpt('tenant_bound'),
    cfg.StrOpt('device_driver'),
    cfg.StrOpt('plugging_driver')
]


hosting_device_templates = base.SubsectionOpt(
    'cisco_hosting_device_template',
    dest='cisco_hosting_device_template',
    help=_("Subgroups that allow you to specify the hosting device templates"),
    subopts=template_subopts)


hosting_device_subopts = [
    cfg.StrOpt('template_id'),
    cfg.StrOpt('credentials_id'),
    cfg.StrOpt('name'),
    cfg.StrOpt('description'),
    cfg.StrOpt('device_id'),
    cfg.BoolOpt('admin_state_up'),
    cfg.StrOpt('management_ip_address'),
    cfg.IntOpt('protocol_port'),
    cfg.StrOpt('tenant_bound'),
    cfg.BoolOpt('auto_delete')
]


hosting_devices = base.SubsectionOpt(
    'cisco_hosting_device',
    dest='cisco_hosting_device',
    help=_("Subgroups that allow you to specify the hosting devices"),
    subopts=hosting_device_subopts)


router_type_subopts = [
    cfg.StrOpt('name'),
    cfg.StrOpt('description'),
    cfg.StrOpt('template_id'),
    cfg.BoolOpt('ha_enabled_by_default'),
    cfg.BoolOpt('shared'),
    cfg.IntOpt('slot_need'),
    cfg.StrOpt('scheduler'),
    cfg.StrOpt('driver'),
    cfg.StrOpt('cfg_agent_service_helper'),
    cfg.StrOpt('cfg_agent_driver')
]


router_types = base.SubsectionOpt(
    'cisco_router_type',
    dest='cisco_router_type',
    help=_("Subgroups that allow you to specify the hosting devices"),
    subopts=router_type_subopts)


hwvlantrunkingdrivers_subopts = [
    base.RemainderOpt('interfaces')
]

hwvlantrunkingdrivers = base.SubsectionOpt(
    'HwVLANTrunkingPlugDriver',
    dest='HwVLANTrunkingPlugDriver',
    help=_("Subgroups that allow you to specify trunking driver interfaces"),
    subopts=hwvlantrunkingdrivers_subopts)

cfg.CONF.register_opt(hosting_device_credentials)
cfg.CONF.register_opt(hosting_device_templates)
cfg.CONF.register_opt(hosting_devices)
cfg.CONF.register_opt(router_types)
cfg.CONF.register_opt(hwvlantrunkingdrivers)


def get_specific_config(prefix):
    """Retrieve config based on the format [<prefix>:<value>].

    returns: a dict, {<UUID>: {<key1>:<value1>, <key2>:<value2>, ...}}
    """
    conf_dict = {}
    for uuid, val in cfg.CONF.get(prefix, {}).items():
        conf_dict[uuid] = dict(val)
    return conf_dict


def verify_resource_dict(res_dict, is_create, attr_info):
    """Verifies required attributes are in resource dictionary, res_dict.

    Also checking that an attribute is only specified if it is allowed
    for the given operation (create/update).

    Attribute with default values are considered to be optional.

    This function contains code taken from function 'prepare_request_body' in
    attributes.py.
    """
    if ((bc.NEUTRON_VERSION >= bc.NEUTRON_NEWTON_VERSION) and 'tenant_id'
            in res_dict):
        res_dict['project_id'] = res_dict['tenant_id']
    if is_create:  # POST
        for attr, attr_vals in six.iteritems(attr_info):
            if attr_vals['allow_post']:
                if 'default' not in attr_vals and attr not in res_dict:
                    msg = _("Failed to parse request. Required attribute '%s' "
                            "not specified") % attr
                    raise webob.exc.HTTPBadRequest(msg)
                res_dict[attr] = res_dict.get(attr, attr_vals.get('default'))
            else:
                if attr in res_dict:
                    msg = _("Attribute '%s' not allowed in POST") % attr
                    raise webob.exc.HTTPBadRequest(msg)
    else:  # PUT
        for attr, attr_vals in six.iteritems(attr_info):
            if attr in res_dict and not attr_vals['allow_put']:
                msg = _("Cannot update read-only attribute %s") % attr
                raise webob.exc.HTTPBadRequest(msg)

    for attr, attr_vals in six.iteritems(attr_info):
        if (attr not in res_dict or
                res_dict[attr] is bc.constants.ATTR_NOT_SPECIFIED):
            continue
        # Convert values if necessary
        if 'convert_to' in attr_vals:
            res_dict[attr] = attr_vals['convert_to'](res_dict[attr])
        # Check that configured values are correct
        if 'validate' not in attr_vals:
            continue
        for rule in attr_vals['validate']:
            _ensure_format(rule, attr, res_dict)
            res = bc.validators[rule](res_dict[attr],
                                      attr_vals['validate'][rule])
            if res:
                msg_dict = dict(attr=attr, reason=res)
                msg = (_("Invalid input for %(attr)s. Reason: %(reason)s.") %
                       msg_dict)
                raise webob.exc.HTTPBadRequest(msg)
    return res_dict


def uuidify(val):
    """Takes an integer and transforms it to a UUID format.

    returns: UUID formatted version of input.
    """
    if uuidutils.is_uuid_like(val):
        return val
    else:
        try:
            int_val = int(val, 16)
        except ValueError:
            with excutils.save_and_reraise_exception():
                LOG.error("Invalid UUID format %s. Please provide an "
                          "integer in decimal (0-9) or hex (0-9a-e) "
                          "format", val)
        res = str(int_val)
        num = 12 - len(res)
        return "00000000-0000-0000-0000-" + "0" * num + res


def _ensure_format(rule, attribute, res_dict):
    """Verifies that attribute in res_dict is properly formatted.

    Since, in the .ini-files, lists are specified as ':' separated text and
    UUID values can be plain integers we need to transform any such values
    into proper format. Empty strings are converted to None if validator
    specifies that None value is accepted.
    """
    if rule == 'type:uuid' or (rule == 'type:uuid_or_none' and
                               res_dict[attribute]):
        res_dict[attribute] = uuidify(res_dict[attribute])
    elif rule == 'type:uuid_list':
        if not res_dict[attribute]:
            res_dict[attribute] = []
        else:
            temp_list = res_dict[attribute].split(':')
            res_dict[attribute] = []
            for item in temp_list:
                res_dict[attribute].append = uuidify(item)
    elif rule == 'type:string_or_none' and res_dict[attribute] == "":
        res_dict[attribute] = None


def obtain_hosting_device_credentials_from_config():
    """Obtains credentials from config file and stores them in memory.
    To be called before hosting device templates defined in the config file
    are created.
    """
    cred_dict = get_specific_config('cisco_hosting_device_credential')
    attr_info = {
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': None}, 'is_visible': True,
                 'default': ''},
        'description': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:string': None},
                        'is_visible': True, 'default': ''},
        'user_name': {'allow_post': True, 'allow_put': True,
                      'validate': {'type:string': None},
                      'is_visible': True, 'default': ''},
        'password': {'allow_post': True, 'allow_put': True,
                     'validate': {'type:string': None},
                     'is_visible': True, 'default': ''},
        'type': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': None}, 'is_visible': True,
                 'default': ''}}
    credentials = {}
    for cred_uuid, kv_dict in cred_dict.items():
        # ensure cred_uuid is properly formatted
        cred_uuid = uuidify(cred_uuid)
        verify_resource_dict(kv_dict, True, attr_info)
        credentials[cred_uuid] = kv_dict
    return credentials
