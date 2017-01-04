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
#


"""
This file provides a wrapper to novaclient API, for getting the instacne's
information such as display_name.
"""
from keystoneauth1.identity import generic
from keystoneauth1 import session
from novaclient import api_versions
from novaclient import client as nova_client
from novaclient import exceptions as nexc

from networking_cisco._i18n import _LE

from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.common import dfa_logger as logging


LOG = logging.getLogger(__name__)


class DFAInstanceAPI(object):

    """This class provides API to get information for a given instance."""

    def __init__(self):
        self._cfg = config.CiscoDFAConfig().cfg
        self._inst_info_cache = {}
        user = self._cfg.nova.username
        project = self._cfg.nova.project_name
        passwd = self._cfg.nova.password
        url = self._cfg.nova.auth_url
        region = self._cfg.nova.region_name
        u_domain = self._cfg.nova.user_domain_name
        p_domain = self._cfg.nova.project_domain_name
        api_v = self._cfg.nova.api_version
        auth = generic.Password(auth_url=url,
                                username=user,
                                password=passwd,
                                project_name=project,
                                project_domain_name=p_domain,
                                user_domain_name=u_domain)
        sess = session.Session(auth=auth)

        self._novaclnt = nova_client.Client(api_versions.APIVersion(api_v),
                                     session=sess,
                                     region_name=region)
        LOG.debug('DFAInstanceAPI: initialization done...')

    def _get_instances_for_project(self, project_id):
        """Return all instances for a given project.

        :project_id: UUID of project (tenant)
        """
        search_opts = {'marker': None,
                       'all_tenants': True,
                       'project_id': project_id}
        try:
            servers = self._novaclnt.servers.list(True, search_opts)
            LOG.debug('_get_instances_for_project: servers=%s', servers)
            return servers
        except nexc.Unauthorized:
            emsg = (_LE('Failed to get novaclient:Unauthorised '
                    'project_id=%(proj)s user=%(user)s'),
                    {'proj': self._project_id, 'user': self._user_name})
            LOG.exception(emsg)
            raise nexc.ClientException(emsg)
        except nexc.AuthorizationFailure as err:
            emsg = (_LE("Failed to get novaclient %s"))
            LOG.exception(emsg, err)
            raise nexc.ClientException(emsg % err)

    def get_instance_for_uuid(self, uuid, project_id):
        """Return instance name for given uuid of an instance and project.

        :uuid: Instance's UUID
        :project_id: UUID of project (tenant)
        """
        instance_name = self._inst_info_cache.get((uuid, project_id))
        if instance_name:
            return instance_name
        instances = self._get_instances_for_project(project_id)
        for inst in instances:
            if inst.id.replace('-', '') == uuid:
                LOG.debug('get_instance_for_uuid: name=%s', inst.name)
                instance_name = inst.name
                self._inst_info_cache[(uuid, project_id)] = instance_name
                return instance_name
        return instance_name
