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

from networking_cisco._i18n import _, _LE
from networking_cisco import backwards_compatibility as bc
from neutron.api.v2 import attributes

LOG = logging.getLogger(__name__)


def get_specific_config(prefix):
    """Retrieve config based on the format [<prefix>:<value>].

    returns: a dict, {<UUID>: {<key1>:<value1>, <key2>:<value2>, ...}}
    """
    conf_dict = {}
    multi_parser = cfg.MultiConfigParser()
    read_ok = multi_parser.read(cfg.CONF.config_file)
    if len(read_ok) != len(cfg.CONF.config_file):
        raise cfg.Error(_("Some config files were not parsed properly"))

    for parsed_file in multi_parser.parsed:
        for parsed_item in parsed_file.keys():
            p_i = parsed_item.lower()
            if p_i.startswith(prefix):
                section_type, uuid = p_i.split(':')
                if section_type == prefix:
                    conf_dict[uuid] = {k: v[0] for (k, v) in parsed_file[
                        parsed_item].items()}
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
                res_dict[attr] is bc.ATTR_NOT_SPECIFIED):
            continue
        # Convert values if necessary
        if 'convert_to' in attr_vals:
            res_dict[attr] = attr_vals['convert_to'](res_dict[attr])
        # Check that configured values are correct
        if 'validate' not in attr_vals:
            continue
        for rule in attr_vals['validate']:
            _ensure_format(rule, attr, res_dict)
            res = attributes.validators[rule](res_dict[attr],
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
                LOG.error(_LE("Invalid UUID format %s. Please provide an "
                              "integer in decimal (0-9) or hex (0-9a-e) "
                              "format"), val)
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
