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


"""This module provides APIs for communicating with DCNM."""


import requests

from oslo_serialization import jsonutils

from networking_cisco._i18n import _LE, _LI

from networking_cisco.apps.saf.common import dfa_exceptions as dexc
from networking_cisco.apps.saf.common import dfa_logger as logging


LOG = logging.getLogger(__name__)


class DFARESTClient(object):

    """DFA client class that provides APIs to interact with DCNM."""

    def __init__(self, cfg):
        self._base_ver = '7.1(0)'
        self._ip = cfg.dcnm.dcnm_ip
        self._user = cfg.dcnm.dcnm_user
        self._pwd = cfg.dcnm.dcnm_password
        self._part_name = cfg.dcnm.default_partition_name
        if (not self._ip) or (not self._user) or (not self._pwd):
            msg = ("[DFARESTClient] Input DCNM IP, user name or password"
                   "parameter is not specified")
            raise ValueError(msg)

        self._req_headers = {'Accept': 'application/json',
                             'Content-Type': 'application/json; charset=UTF-8'}

        self.default_cfg_profile = cfg.dcnm.default_cfg_profile
        self.default_vrf_profile = cfg.dcnm.default_vrf_profile
        # url timeout: 10 seconds
        self.timeout_resp = (10 if not cfg.dcnm.timeout_resp else
                             cfg.dcnm.timeout_resp)

        # urls
        self._org_url = 'http://%s/rest/auto-config/organizations' % self._ip
        self._create_network_url = ('http://%s/' % self._ip +
                                    'rest/auto-config/organizations'
                                    '/%s/partitions/%s/networks')
        self._cfg_profile_list_url = ('http://%s/rest/auto-config/profiles' %
                                      self._ip)
        self._cfg_profile_get_url = self._cfg_profile_list_url + '/%s'
        self._create_part_url = ('http://%s/rest/auto-config/' % self._ip +
                                 'organizations/%s/partitions')
        self._update_part_url = ('http://%s/rest/auto-config/' % self._ip +
                                 'organizations/%s/partitions/%s')
        self._del_org_url = ('http://%s/rest/auto-config/organizations' %
                             self._ip + '/%s')
        self._del_part = ('http://%s/rest/auto-config/organizations' %
                          self._ip + '/%s/partitions/%s')
        self._network_url = ('http://%s/rest/auto-config/organizations' %
                             self._ip + '/%s/partitions/%s/networks/'
                             'segment/%s')
        self._login_url = 'http://%s/rest/logon' % (self._ip)
        self._logout_url = 'http://%s/rest/logout' % (self._ip)
        self._exp_time = 100000
        self._resp_ok = (200, 201, 202)

        self._cur_ver = self.get_version()

        # Update the default network profile based on version of DCNM.
        self._set_default_cfg_profile()

    @property
    def is_iplus(self):
        """Check the DCNM version."""

        return self._cur_ver >= self._base_ver

    def _set_default_cfg_profile(self):
        """Set default network config profile.

        Check whether the default_cfg_profile value exist in the current
        version of DCNM. If not, set it to new default value which is supported
        by latest version.
        """
        try:
            cfgplist = self.config_profile_list()
            if self.default_cfg_profile not in cfgplist:
                self.default_cfg_profile = ('defaultNetworkUniversalEfProfile'
                                            if self.is_iplus else
                                            'defaultNetworkIpv4EfProfile')
        except dexc.DfaClientRequestFailed:
            LOG.error(_LE("Failed to send requst to DCNM."))
            self.default_cfg_profile = 'defaultNetworkIpv4EfProfile'

    def _create_network(self, network_info):
        """Send create network request to DCNM.

        :param network_info: network parameters to be created on DCNM
        """
        url = self._create_network_url % (network_info['organizationName'],
                                          network_info['partitionName'])
        payload = network_info

        LOG.info(_LI('url %(url)s payload %(payload)s'),
                 {'url': url, 'payload': payload})
        return self._send_request('POST', url, payload, 'network')

    def _config_profile_get(self, thisprofile):
        """Get information of a config profile from DCNM.

        :param thisprofile: network config profile in request
        """
        url = self._cfg_profile_get_url % (thisprofile)
        payload = {}

        res = self._send_request('GET', url, payload, 'config-profile')
        if res and res.status_code in self._resp_ok:
            return res.json()

    def _config_profile_list(self):
        """Get list of supported config profile from DCNM."""
        url = self._cfg_profile_list_url
        payload = {}

        res = self._send_request('GET', url, payload, 'config-profile')
        if res and res.status_code in self._resp_ok:
            return res.json()

    def _create_org(self, name, desc):
        """Create organization on the DCNM.

        :param name: Name of organization
        :param desc: Description of organization
        """
        url = self._org_url
        payload = {
            "organizationName": name,
            "description": name if len(desc) == 0 else desc,
            "orchestrationSource": "OpenStack Controller"}

        return self._send_request('POST', url, payload, 'organization')

    def _create_or_update_partition(self, org_name, part_name, dci_id, desc,
                                    operation='POST'):
        """Send create or update partition request to the DCNM.

        :param org_name: name of organization
        :param part_name: name of partition
        :param desc: description of partition
        """
        url = ((self._create_part_url % (org_name)) if operation == 'POST' else
               self._update_part_url % (org_name, part_name))

        payload = {
            "partitionName": part_name,
            "description": part_name if len(desc) == 0 else desc,
            "organizationName": org_name}

        # Check the DCNM version and find out whether it is need to have
        # extra payload for the new version when creating/updating a partition.
        if self.is_iplus:
            # Need to add extra payload for the new version.
            extra_payload = {
                "vrfProfileName": self.default_vrf_profile,
                "vrfName": ':'.join((org_name, part_name)),
                "dciId": dci_id,
                "enableDCIExtension": ("true" if dci_id and int(dci_id) != 0
                                       else "false")}
            payload.update(extra_payload)

        return self._send_request(operation, url, payload, 'partition')

    def _delete_org(self, org_name):
        """Send organization delete request to DCNM.

        :param org_name: name of organization to be deleted
        """
        url = self._del_org_url % (org_name)
        return self._send_request('DELETE', url, '', 'organization')

    def _delete_partition(self, org_name, partition_name):
        """Send partition delete request to DCNM.

        :param org_name: name of organization
        :param partition_name: name of partition
        """
        url = self._del_part % (org_name, partition_name)
        return self._send_request('DELETE', url, '', 'partition')

    def _delete_network(self, network_info):
        """Send network delete request to DCNM.

        :param network_info: contains network info to be deleted.
        """
        org_name = network_info.get('organizationName', '')
        part_name = network_info.get('partitionName', '')
        segment_id = network_info['segmentId']
        url = self._network_url % (org_name, part_name, segment_id)
        return self._send_request('DELETE', url, '', 'network')

    def _get_network(self, network_info):
        """Send network get request to DCNM.

        :param network_info: contains network info to query.
        """
        org_name = network_info.get('organizationName', '')
        part_name = network_info.get('partitionName', '')
        segment_id = network_info['segmentId']
        url = self._network_url % (org_name, part_name, segment_id)
        return self._send_request('GET', url, '', 'network')

    def _login(self):
        """Login request to DCNM."""

        url_login = self._login_url
        expiration_time = self._exp_time

        payload = {'expirationTime': expiration_time}
        res = requests.post(url_login,
                            data=jsonutils.dumps(payload),
                            headers=self._req_headers,
                            auth=(self._user, self._pwd),
                            timeout=self.timeout_resp)
        session_id = ''
        if res and res.status_code in self._resp_ok:
            session_id = res.json().get('Dcnm-Token')
        self._req_headers.update({'Dcnm-Token': session_id})

    def _logout(self):
        """Logout request to DCNM."""

        url_logout = self._logout_url
        requests.post(url_logout,
                      headers=self._req_headers,
                      timeout=self.timeout_resp)

    def _send_request(self, operation, url, payload, desc):
        """Send request to DCNM."""

        res = None
        try:
            payload_json = None
            if payload and payload != '':
                payload_json = jsonutils.dumps(payload)
            self._login()
            desc_lookup = {'POST': ' creation', 'PUT': ' update',
                           'DELETE': ' deletion', 'GET': ' get'}

            res = requests.request(operation, url, data=payload_json,
                                   headers=self._req_headers,
                                   timeout=self.timeout_resp)
            desc += desc_lookup.get(operation, operation.lower())
            LOG.info(_LI("DCNM-send_request: %(desc)s %(url)s %(pld)s"),
                     {'desc': desc, 'url': url, 'pld': payload})

            self._logout()
        except (requests.HTTPError, requests.Timeout,
                requests.ConnectionError) as exc:
            LOG.exception(_LE('Error during request: %s'), exc)
            raise dexc.DfaClientRequestFailed(reason=exc)

        return res

    def config_profile_list(self):
        """Return config profile list from DCNM."""

        these_profiles = self._config_profile_list() or []
        profile_list = [q for p in these_profiles for q in
                        [p.get('profileName')]]
        return profile_list

    def config_profile_fwding_mode_get(self, profile_name):
        """Return forwarding mode of given config profile."""

        profile_params = self._config_profile_get(profile_name)
        fwd_cli = 'fabric forwarding mode proxy-gateway'
        if profile_params and fwd_cli in profile_params['configCommands']:
            return 'proxy-gateway'
        else:
            return 'anycast-gateway'

    def get_config_profile_for_network(self, net_name):
        """Get the list of profiles."""

        cfgplist = self.config_profile_list()
        cfgname = net_name.partition(':')[2]

        cfgtuple = set()
        for cfg_prof in cfgplist:
            if cfg_prof.startswith('defaultNetwork'):
                cfg_alias = (cfg_prof.split('defaultNetwork')[1].
                             split('Profile')[0])
            elif cfg_prof.endswith('Profile'):
                cfg_alias = cfg_prof.split('Profile')[0]
            else:
                cfg_alias = cfg_prof
            cfgtuple.update([(cfg_prof, cfg_alias)])
        cfgp = [a for a, b in cfgtuple if cfgname == b]
        prof = cfgp[0] if cfgp else self.default_cfg_profile
        fwd_mod = self.config_profile_fwding_mode_get(prof)
        return (prof, fwd_mod)

    def create_network(self, tenant_name, network, subnet,
                       dhcp_range=True):
        """Create network on the DCNM.

        :param tenant_name: name of tenant the network belongs to
        :param network: network parameters
        :param subnet: subnet parameters of the network
        """
        seg_id = str(network.segmentation_id)
        subnet_ip_mask = subnet.cidr.split('/')
        gw_ip = subnet.gateway_ip
        cfg_args = [
            "$segmentId=" + seg_id,
            "$netMaskLength=" + subnet_ip_mask[1],
            "$gatewayIpAddress=" + gw_ip,
            "$networkName=" + network.name,
            "$vlanId=0",
            "$vrfName=" + tenant_name + ':' + self._part_name
        ]
        cfg_args = ';'.join(cfg_args)

        ip_range = ','.join(["%s-%s" % (p['start'], p['end']) for p in
                             subnet.allocation_pools])

        dhcp_scopes = {'ipRange': ip_range,
                       'subnet': subnet.cidr,
                       'gateway': gw_ip}

        network_info = {"segmentId": seg_id,
                        "vlanId": "0",
                        "mobilityDomainId": "None",
                        "profileName": network.config_profile,
                        "networkName": network.name,
                        "configArg": cfg_args,
                        "organizationName": tenant_name,
                        "partitionName": self._part_name,
                        "description": network.name,
                        "netmaskLength": subnet_ip_mask[1],
                        "gateway": gw_ip}
        if dhcp_range:
            network_info["dhcpScope"] = dhcp_scopes

        if self.is_iplus:
            # Need to add the vrf name to the network info
            prof = self._config_profile_get(network.config_profile)
            if prof and prof.get('profileSubType') == 'network:universal':
                # For universal profile vrf has to e organization:partition
                network_info["vrfName"] = ':'.join((tenant_name,
                                                    self._part_name))
            else:
                # Otherwise, it should be left empty.
                network_info["vrfName"] = ""

        LOG.debug("Creating %s network in DCNM.", network_info)

        res = self._create_network(network_info)
        if res and res.status_code in self._resp_ok:
            LOG.debug("Created %s network in DCNM.", network_info)
        else:
            LOG.error(_LE("Failed to create %s network in DCNM."),
                      network_info)
            raise dexc.DfaClientRequestFailed(reason=res)

    def delete_network(self, tenant_name, network):
        """Delete network on the DCNM.

        :param tenant_name: name of tenant the network belongs to
        :param network: object that contains network parameters
        """
        seg_id = network.segmentation_id
        network_info = {
            'organizationName': tenant_name,
            'partitionName': self._part_name,
            'segmentId': seg_id,
        }
        LOG.debug("Deleting %s network in DCNM.", network_info)

        res = self._delete_network(network_info)
        if res and res.status_code in self._resp_ok:
            LOG.debug("Deleted %s network in DCNM.", network_info)
        else:
            LOG.error(_LE("Failed to delete %s network in DCNM."),
                      network_info)
            raise dexc.DfaClientRequestFailed(reason=res)

    def delete_project(self, tenant_name, part_name):
        """Delete project on the DCNM.

        :param tenant_name: name of project.
        :param part_name: name of partition.
        """
        res = self._delete_partition(tenant_name, part_name)
        if res and res.status_code in self._resp_ok:
            LOG.debug("Deleted %s partition in DCNM.", part_name)
        else:
            LOG.error(_LE("Failed to delete %(part)s partition in DCNM."
                      "Response: %(res)s"), {'part': part_name, 'res': res})
            raise dexc.DfaClientRequestFailed(reason=res)

        res = self._delete_org(tenant_name)
        if res and res.status_code in self._resp_ok:
            LOG.debug("Deleted %s organization in DCNM.", tenant_name)
        else:
            LOG.error(_LE("Failed to delete %(org)s organization in DCNM."
                      "Response: %(res)s"), {'org': tenant_name, 'res': res})
            raise dexc.DfaClientRequestFailed(reason=res)

    def create_project(self, org_name, part_name, dci_id, desc=None):
        """Create project on the DCNM.

        :param org_name: name of organization.
        :param part_name: name of partition.
        :param dci_id: Data Center interconnect id.
        :param desc: description of project.
        """
        desc = desc or org_name
        res = self._create_org(org_name, desc)
        if res and res.status_code in self._resp_ok:
            LOG.debug("Created %s organization in DCNM.", org_name)
        else:
            LOG.error(_LE("Failed to create %(org)s organization in DCNM."
                      "Response: %(res)s"), {'org': org_name, 'res': res})
            raise dexc.DfaClientRequestFailed(reason=res)

        res = self._create_or_update_partition(org_name, part_name,
                                               dci_id, desc)
        if res and res.status_code in self._resp_ok:
            LOG.debug("Created %s partition in DCNM.", part_name)
        else:
            LOG.error(_LE("Failed to create %(part)s partition in DCNM."
                      "Response: %(res)s"), {'part': part_name, 'res': res})
            raise dexc.DfaClientRequestFailed(reason=res)

    def update_project(self, org_name, part_name, dci_id, desc=None):
        """Update project on the DCNM.

        :param org_name: name of organization.
        :param part_name: name of partition.
        :param dci_id: Data Center interconnect id.
        :param desc: description of project.
        """
        desc = desc or org_name
        res = self._create_or_update_partition(org_name, part_name, dci_id,
                                               desc, operation='PUT')
        if res and res.status_code in self._resp_ok:
            LOG.debug("Update %s partition in DCNM.", part_name)
        else:
            LOG.error(_LE("Failed to update %(part)s partition in DCNM."
                      "Response: %(res)s"), {'part': part_name, 'res': res})
            raise dexc.DfaClientRequestFailed(reason=res)

    def list_networks(self, org, part):
        """Return list of networks from DCNM.

        :param org: name of organization.
        :param part: name of partition.
        """
        if org and part:
            list_url = self._del_part + '/networks'
            list_url = list_url % (org, part)
            res = self._send_request('GET', list_url, '', 'networks')
            if res and res.status_code in self._resp_ok:
                return res.json()

    def list_organizations(self):
        """Return list of organizations from DCNM."""

        try:
            res = self._send_request('GET', self._org_url, '', 'organizations')
            if res and res.status_code in self._resp_ok:
                return res.json()
        except dexc.DfaClientRequestFailed:
            LOG.error(_LE("Failed to send request to DCNM."))

    def get_network(self, org, segid):
        """Return given network from DCNM.

        :param org: name of organization.
        :param segid: segmentation id of the network.
        """
        network_info = {
            'organizationName': org,
            'partitionName': self._part_name,
            'segmentId': segid,
        }
        res = self._get_network(network_info)
        if res and res.status_code in self._resp_ok:
            return res.json()

    def get_version(self):
        """Get the DCNM version."""

        url = 'http://%s/rest/dcnm-version' % self._ip
        payload = {}

        try:
            res = self._send_request('GET', url, payload, 'dcnm-version')
            if res and res.status_code in self._resp_ok:
                return res.json().get('Dcnm-Version')
        except dexc.DfaClientRequestFailed:
            LOG.error(_LE("Failed to get DCNM version."))
