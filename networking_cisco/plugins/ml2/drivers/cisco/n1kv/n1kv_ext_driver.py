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

"""Extensions Driver for Cisco Nexus1000V."""

from oslo_config import cfg
from oslo_log import log
from oslo_utils import uuidutils

from networking_cisco._i18n import _LE

from neutron.api import extensions as api_extensions
from neutron.extensions import providernet
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2.common import exceptions as ml2_exc
from neutron.plugins.ml2 import driver_api as api

from networking_cisco import backwards_compatibility as bc_attr
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    extensions)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_db)

LOG = log.getLogger(__name__)


class CiscoN1kvExtensionDriver(api.ExtensionDriver):
    """Cisco N1KV ML2 Extension Driver."""

    # List of supported extensions for cisco Nexus1000V.
    _supported_extension_alias = "n1kv"

    def initialize(self):
        api_extensions.append_api_extensions_path(extensions.__path__)

    @property
    def extension_alias(self):
        """
        Supported extension alias.

        :returns: alias identifying the core API extension supported
                  by this driver
        """
        return self._supported_extension_alias

    def process_create_port(self, context, data, result):
        """Implementation of abstract method from ExtensionDriver class."""
        port_id = result.get('id')
        policy_profile_attr = data.get(constants.N1KV_PROFILE)
        tenant_id = context.tenant_id or data.get('tenant_id')
        default_policy_profile_name = (cfg.CONF.ml2_cisco_n1kv.
                                       default_policy_profile)
        if not bc_attr.is_attr_set(policy_profile_attr):
            policy_profile_attr = default_policy_profile_name
        with context.session.begin(subtransactions=True):
            try:
                if not uuidutils.is_uuid_like(policy_profile_attr):
                    policy_profile = n1kv_db.get_policy_profile_by_name(
                        policy_profile_attr,
                        context.session)
                else:
                    policy_profile = (n1kv_db.get_policy_profile_by_uuid(
                        context.session,
                        policy_profile_attr))
                n1kv_db.get_profile_binding(db_session=context.session,
                                            tenant_id=tenant_id,
                                            profile_id=policy_profile.id)
            except n1kv_exc.PolicyProfileNotFound:
                LOG.error(_LE("Policy Profile %(profile)s does "
                              "not exist."), {"profile": policy_profile_attr})
                raise ml2_exc.ExtensionDriverError(driver='N1Kv ML2')
            except n1kv_exc.ProfileTenantBindingNotFound:
                if context.is_admin:
                    session = context.session
                    n1kv_db.update_policy_profile_binding_with_tenant_id(
                        policy_profile.id, tenant_id, session)
                elif (cfg.CONF.ml2_cisco_n1kv.restrict_policy_profiles and
                        policy_profile.name != default_policy_profile_name):
                    LOG.error(_LE("Policy Profile %s is "
                                  "not owned by this tenant.") %
                              policy_profile_attr)
                    raise ml2_exc.ExtensionDriverError(driver='N1Kv ML2')
            n1kv_db.add_policy_binding(port_id,
                                       policy_profile.id,
                                       context.session)
        result[constants.N1KV_PROFILE] = policy_profile.id

    def extend_port_dict(self, session, model, result):
        """Implementation of abstract method from ExtensionDriver class."""
        port_id = result.get('id')
        with session.begin(subtransactions=True):
            try:
                res = n1kv_db.get_policy_binding(port_id, session)
                result[constants.N1KV_PROFILE] = res.profile_id
            except n1kv_exc.PortBindingNotFound:
                # Do nothing if the port binding is not found.
                pass

    def process_create_network(self, context, data, result):
        """Implementation of abstract method from ExtensionDriver class."""
        net_id = result.get('id')
        prov_net_type = data.get(providernet.NETWORK_TYPE)
        net_prof_attr = data.get(constants.N1KV_PROFILE)
        tenant_id = context.tenant_id
        if not bc_attr.is_attr_set(net_prof_attr):
            if not bc_attr.is_attr_set(prov_net_type):
                network_type = cfg.CONF.ml2.tenant_network_types[0]
            else:
                network_type = prov_net_type
            if network_type == p_const.TYPE_VLAN:
                net_prof_attr = constants.DEFAULT_VLAN_NETWORK_PROFILE_NAME
            elif network_type == p_const.TYPE_VXLAN:
                net_prof_attr = constants.DEFAULT_VXLAN_NETWORK_PROFILE_NAME
            else:
                # This network type is not supported with network profiles
                return
        with context.session.begin(subtransactions=True):
            try:
                if not uuidutils.is_uuid_like(net_prof_attr):
                    net_prof_attr = n1kv_db.get_network_profile_by_name(
                        net_prof_attr, context.session)
                else:
                    net_prof_attr = n1kv_db.get_network_profile_by_uuid(
                        net_prof_attr, context.session)
                n1kv_db.get_profile_binding(db_session=context.session,
                                            tenant_id=tenant_id,
                                            profile_id=net_prof_attr.id)
            except n1kv_exc.NetworkProfileNotFound:
                LOG.error(_LE("Network Profile %s does "
                              "not exist.") % net_prof_attr)
                raise ml2_exc.ExtensionDriverError(driver='N1Kv ML2')
            except n1kv_exc.ProfileTenantBindingNotFound:
                if (cfg.CONF.ml2_cisco_n1kv.restrict_network_profiles and
                        net_prof_attr.name not in [
                            constants.DEFAULT_VLAN_NETWORK_PROFILE_NAME,
                            constants.DEFAULT_VXLAN_NETWORK_PROFILE_NAME]):
                    LOG.error(_LE("Network Profile %s is "
                                  "not owned by this tenant.") %
                              net_prof_attr.name)
                    raise ml2_exc.ExtensionDriverError(driver='N1Kv ML2')
            segment_type = net_prof_attr.segment_type
            n1kv_db.add_network_binding(net_id, segment_type,
                                        0,
                                        net_prof_attr.id,
                                        context.session)
            data[providernet.NETWORK_TYPE] = segment_type
        result[constants.N1KV_PROFILE] = net_prof_attr.id

    def extend_network_dict(self, session, model, result):
        """Implementation of abstract method from ExtensionDriver class."""
        net_id = result.get('id')
        with session.begin(subtransactions=True):
            try:
                res = n1kv_db.get_network_binding(net_id, session)
                result[constants.N1KV_PROFILE] = res.profile_id
            except n1kv_exc.NetworkBindingNotFound:
                # Do nothing if the network binding is not found.
                pass
