# Copyright 2015 Cisco Systems, Inc.
# All Rights Reserved.
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
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    extensions)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_client)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_db)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    n1kv_models)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import config
from networking_cisco.plugins.ml2.drivers.cisco.n1kv.extensions import (
    policy_profile)

from neutron.api import extensions as api_extensions
import neutron.db.api as db
from neutron.db import common_db_mixin as base_db
from neutron.i18n import _LW

LOG = logging.getLogger(__name__)

cfg.CONF.import_group(
    'ml2_cisco_n1kv',
    'networking_cisco.plugins.ml2.drivers.cisco.n1kv.config')


class PolicyProfile_db_mixin(policy_profile.PolicyProfilePluginBase,
                             base_db.CommonDbMixin):
    """Policy Profile Mixin class."""

    def _make_policy_profile_dict(self, pprofile, fields=None):
        res = {"id": pprofile["id"], "name": pprofile["name"]}
        return self._fields(res, fields)

    def _policy_profile_exists(self, pprofile_id, vsm_ip=None):
        db_session = db.get_session()
        if vsm_ip is None:
            return self.n1kv_db.get_policy_profile_by_uuid(db_session,
                                                           pprofile_id)
        else:
            return (db_session.query(n1kv_models.PolicyProfile).
                    filter_by(id=pprofile_id, vsm_ip=vsm_ip).first())

    def _create_policy_profile(self, pprofile_id, pprofile_name, vsm_ip):
        """Create a policy profile."""
        db_session = db.get_session()
        pprofile = n1kv_models.PolicyProfile(id=pprofile_id,
                                             name=pprofile_name,
                                             vsm_ip=vsm_ip)
        db_session.add(pprofile)
        db_session.flush()
        return pprofile

    def _add_policy_profile(self, pprofile_id, name, vsm_ip,
                            tenant_id=None):
        """
        Add Policy profile and tenant binding.

        :param pprofile_id: UUID representing the policy profile
        :param name: string representing the name for the
                     policy profile
        :param vsm_ip: VSM IP from which policy profile is retrieved
        :param tenant_id: UUID representing the tenant
        """
        if not self._policy_profile_exists(pprofile_id, vsm_ip):
            self._create_policy_profile(pprofile_id, name, vsm_ip)

    def _get_policy_profiles(self):
        """Retrieve all policy profiles."""
        db_session = db.get_session()
        return db_session.query(n1kv_models.PolicyProfile)

    def _get_policy_profile(self, session, pprofile_id):
        profile = n1kv_db.get_policy_profile_by_uuid(session, pprofile_id)
        if profile is None:
            raise n1kv_exc.PolicyProfileNotFound(profile=pprofile_id)
        else:
            return profile

    def _get_policy_collection_for_tenant(self, db_session, model, tenant_id):
        profile_ids = (db_session.query(n1kv_models.
                       ProfileBinding.profile_id)
                       .filter_by(tenant_id=tenant_id).
                       filter_by(profile_type=n1kv_const.POLICY).all())
        profiles = db_session.query(model).filter(model.id.in_(
            pid[0] for pid in profile_ids))
        return [self._make_policy_profile_dict(p) for p in profiles]

    def _get_policy_profiles_by_host(self, vsm_ip):
        """Retrieve policy profiles by vsm_ip."""
        return n1kv_db.get_policy_profiles_by_host(vsm_ip)

    def _remove_policy_profile(self, pprofile_id, vsm_ip):
        """Delete a policy profile."""
        db_session = db.get_session()
        pprofile = (db_session.query(n1kv_models.PolicyProfile).
                    filter_by(id=pprofile_id, vsm_ip=vsm_ip).first())
        if pprofile:
            db_session.delete(pprofile)
            db_session.flush()

    def get_policy_profile(self, context, pprofile_id, fields=None):
        """
        Retrieve a policy profile for the given UUID.

        :param context: neutron api request context
        :param pprofile_id: UUID representing policy profile to fetch
        :param fields: a list of strings that are valid keys in a policy
                       profile dictionary. Only these fields will be returned
        :returns: policy profile dictionary
        """
        profile = self._get_policy_profile(context.session, pprofile_id)
        return self._make_policy_profile_dict(profile, fields)

    def get_policy_profiles(self, context, filters=None, fields=None):
        """
        Retrieve a list of policy profiles.

        Retrieve all policy profiles if tenant is admin. For a non-admin
        tenant, retrieve all policy profiles belonging to this tenant only.
        :param context: neutron api request context
        :param filters: a dictionary with keys that are valid keys for a
                        policy profile object. Values in this dictiontary are
                        an iterable containing values that will be used for an
                        exact match comparison for that value. Each result
                        returned by this function will have matched one of the
                        values for each key in filters
        :param fields: a list of strings that are valid keys in a policy
                       profile dictionary. Only these fields will be returned
        :returns: list of all policy profiles
        """
        db_session = db.get_session()

        if (context.is_admin or
            not cfg.CONF.ml2_cisco_n1kv.restrict_policy_profiles):
            pp_list = self._get_collection(context, n1kv_models.PolicyProfile,
                                        self._make_policy_profile_dict,
                                        filters=filters, fields=fields)
        else:
            pp_list = self._get_policy_collection_for_tenant(context.session,
                                                          n1kv_models.
                                                          PolicyProfile,
                                                          context.tenant_id)

        # Uniquify the port profile ids
        pp_ids = set(pp['id'] for pp in pp_list)

        # recreate the pp_list for unique profile ids
        pp_list = []
        for pp_id in pp_ids:
            try:
                pp_list.append(self._make_policy_profile_dict(
                    self._get_policy_profile(db_session, pp_id)))
            except n1kv_exc.PolicyProfileNotFound:
                # Only return profiles on all VSMs
                pass
        return pp_list

    def _check_policy_profile_on_any_vsm(self, pprofile_id, db_session=None):
        """Checks if policy profile is present on any VSM"""
        db_session = db_session or db.get_session()
        return (db_session.query(n1kv_models.PolicyProfile).
                filter_by(id=pprofile_id).count())


class PolicyProfilePlugin(PolicyProfile_db_mixin):
    """Implementation of the Cisco N1KV Policy Profile Service Plugin."""
    supported_extension_aliases = ["policy_profile"]

    def __init__(self):
        super(PolicyProfilePlugin, self).__init__()
        api_extensions.append_api_extensions_path(extensions.__path__)
        # Initialize N1KV client
        self.n1kvclient = n1kv_client.Client()
        eventlet.spawn(self._poll_policy_profiles)

    def _poll_policy_profiles(self):
        """Start a green thread to pull policy profiles from VSM."""
        while True:
            self._populate_policy_profiles()
            eventlet.sleep(cfg.CONF.ml2_cisco_n1kv.poll_duration)

    def _populate_policy_profiles(self):
        """Populate all the policy profiles from VSM."""
        hosts = config.get_vsm_hosts()
        for vsm_ip in hosts:
            try:
                policy_profiles = self.n1kvclient.list_port_profiles(vsm_ip)
                vsm_profiles = {}
                plugin_profiles_set = set()
                # Fetch policy profiles from VSM
                for profile_name in policy_profiles:
                    profile_id = (policy_profiles[profile_name]
                                  [n1kv_const.PROPERTIES][n1kv_const.ID])
                    vsm_profiles[profile_id] = profile_name
                # Fetch policy profiles previously populated
                for profile in self._get_policy_profiles_by_host(vsm_ip):
                    plugin_profiles_set.add(profile.id)
                vsm_profiles_set = set(vsm_profiles)
                # Update database if the profile sets differ.
                if vsm_profiles_set.symmetric_difference(plugin_profiles_set):
                    # Add new profiles to database if they were created in VSM
                    for pid in vsm_profiles_set.difference(
                                                plugin_profiles_set):
                        self._add_policy_profile(pid, vsm_profiles[pid],
                                                 vsm_ip)
                    # Delete profiles from database if they were deleted in VSM
                    for pid in plugin_profiles_set.difference(
                                                   vsm_profiles_set):
                        if not n1kv_db.policy_profile_in_use(pid):
                            self._remove_policy_profile(pid, vsm_ip)
                        else:
                            LOG.warning(_LW('Policy profile %s in use'), pid)
            except (n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
                with excutils.save_and_reraise_exception(reraise=False):
                    LOG.warning(_LW('No policy profile populated from VSM'))
        self.sanitize_policy_profile_table()

    def get_policy_profiles(self, context, filters=None, fields=None):
        """
        Return Cisco N1KV policy profiles.

        :param context: neutron api request context
        :param filters: a dictionary with keys that are valid keys for a
                        subnet object. Values in this dictiontary are an
                        iterable containing values that will be used for an
                        exact match comparison for that value. Each result
                        returned by this function will have matched one of the
                        values for each key in filters
        :param fields: a list of strings that are valid keys in a subnet
                       dictionary. Only these fields will be returned.
        :returns: list of dictionaries of policy profiless
        """
        return super(PolicyProfilePlugin, self).get_policy_profiles(context,
                                                                    filters,
                                                                    fields)

    def get_policy_profile(self, context, pprofile_id, fields=None):
        """
        Retrieve a policy profile for the given UUID.

        :param context: neutron api request context
        :param pprofile_id: UUID representing policy profile to fetch
        :param fields: a list of strings that are valid keys in a policy
                       profile dictionary. Only these fields will be returned
        :returns: policy profile dictionary
        """
        return super(PolicyProfilePlugin, self).get_policy_profile(context,
                                                                   pprofile_id,
                                                                   fields)

    def sanitize_policy_profile_table(self):
        """Clear policy profiles from stale VSM."""
        db_session = db.get_session()
        hosts = config.get_vsm_hosts()
        vsm_info = db_session.query(
            n1kv_models.PolicyProfile.vsm_ip).distinct()
        if vsm_info is None or hosts is None:
            return
        vsm_ips = [vsm_ip[0] for vsm_ip in vsm_info if vsm_ip[0] not in hosts]
        for vsm_ip in vsm_ips:
            pprofiles = n1kv_db.get_policy_profiles_by_host(vsm_ip, db_session)
            for pprofile in pprofiles:
                # Do not delete profile if it is in use and if it
                # is the only VSM to have it configured
                pp_in_use = n1kv_db.policy_profile_in_use(pprofile['id'],
                                                          db_session)
                num_vsm_using_pp = db_session.query(
                    n1kv_models.PolicyProfile).filter_by(
                    id=pprofile['id']).count()
                if (not pp_in_use) or (num_vsm_using_pp > 1):
                    db_session.delete(pprofile)
                    db_session.flush()
                else:
                    LOG.warning(_LW('Cannot delete policy profile %s '
                                    'as it is in use.'), pprofile['id'])
