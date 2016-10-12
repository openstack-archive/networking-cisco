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


import re
import requests
import sys

from oslo_serialization import jsonutils

from networking_cisco._i18n import _LE, _LI

from networking_cisco.apps.saf.common import dfa_exceptions as dexc
from networking_cisco.apps.saf.common import dfa_logger as logging


LOG = logging.getLogger(__name__)
UNKNOWN_SRVN_NODE_IP = '0.0.0.0'
UNKNOWN_DCI_ID = -1


class DFARESTClient(object):

    """DFA client class that provides APIs to interact with DCNM."""

    def __init__(self, cfg):
        self._base_ver = '7.1(0)'
        self._is_iplus = False
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
        self._exp_time = 100000
        self._resp_ok = (requests.codes.ok, requests.codes.created,
                         requests.codes.accepted)

        self.dcnm_protocol = self.get_dcnm_protocol()
        # Fill the urls for DCNM Rest API's.
        self.fill_urls()

        self._cur_ver = self.get_version()
        self._detect_iplus()

        # Update the default network profile based on version of DCNM.
        self._set_default_cfg_profile()
        self._default_md = None

    def _detect_iplus(self):
        """Check the DCNM version and determine if it's for iplus"""

        ver_expr = "([0-9]+)\.([0-9]+)\((.*)\)"
        re.compile(ver_expr)
        v1 = re.match(ver_expr, self._cur_ver)
        v2 = re.match(ver_expr, self._base_ver)

        if int(v1.group(1)) > int(v2.group(1)):
            self._is_iplus = True
        elif int(v1.group(1)) == int(v2.group(1)):
            if int(v1.group(2)) > int(v2.group(2)):
                self._is_iplus = True
            elif int(v1.group(2)) == int(v2.group(2)):
                self._is_iplus = v1.group(3) >= v2.group(3)

        LOG.info(_LI("DCNM version: %(cur_ver)s, iplus: %(is_iplus)s"),
                 {'cur_ver': self._cur_ver, 'is_iplus': self._is_iplus})

    def _failure_msg(self, response):
        return "[%s] %s" % (response.status_code, response.text)

    def get_segmentid_range(self, orchestrator_id):
        """Get segment id range from DCNM. """

        url = "%s/%s" % (self._segmentid_ranges_url, orchestrator_id)

        res = self._send_request('GET', url, None, 'segment-id range')
        if res and res.status_code in self._resp_ok:
            return res.json()

    def set_segmentid_range(self, orchestrator_id, segid_min, segid_max):
        """set segment id range in DCNM. """

        url = self._segmentid_ranges_url

        payload = {'orchestratorId': orchestrator_id,
                   'segmentIdRanges': "%s-%s" % (segid_min, segid_max)}

        res = self._send_request('POST', url, payload, 'segment-id range')
        if not (res and res.status_code in self._resp_ok):
            LOG.error(_LE("Failed to set segment id range for orchestrator "
                          "%(orch)s on DCNM: %(text)s"),
                      {'orch': orchestrator_id, 'text': res.text})
            raise dexc.DfaClientRequestFailed(reason=self._failure_msg(res))

    def update_segmentid_range(self, orchestrator_id, segid_min, segid_max):
        """update segment id range in DCNM. """
        url = "%s/%s" % (self._segmentid_ranges_url, orchestrator_id)

        payload = {'orchestratorId': orchestrator_id,
                   'segmentIdRanges': "%s-%s" % (segid_min, segid_max)}

        res = self._send_request('PUT', url, payload, 'segment-id range')
        if not (res and res.status_code in self._resp_ok):
            LOG.error(_LE("Failed to update segment id range for orchestrator "
                          "%(orch)s on DCNM: %(text)s"),
                      {'orch': orchestrator_id, 'text': res.text})
            raise dexc.DfaClientRequestFailed(reason=self._failure_msg(res))

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
                                            if self._is_iplus else
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

        try:
            res = self._send_request('GET', url, payload, 'config-profile')
            if res and res.status_code in self._resp_ok:
                return res.json()
        except dexc.DfaClientRequestFailed:
            LOG.error(_LE("Failed to send requst to DCNM."))

    def _get_settings(self):
        """Get global mobility domain from DCNM."""
        url = self._global_settings_url
        payload = {}
        res = self._send_request('GET', url, payload, 'settings')
        if res and res.status_code in self._resp_ok:
            return res.json()

    def _set_default_mobility_domain(self):
        settings = self._get_settings()
        LOG.info(_LI("settings is %s") % settings)

        if ('globalMobilityDomain' in settings.keys()):
            global_md = settings.get('globalMobilityDomain')
            self._default_md = global_md.get('name')
            LOG.info(_LI("setting default md to be %s") % self._default_md)
        else:
            self._default_md = "md0"

    def _create_org(self, orch_id, name, desc):
        """Create organization on the DCNM.

        :param orch_id: orchestrator ID
        :param name: Name of organization
        :param desc: Description of organization
        """
        url = self._org_url
        payload = {
            "organizationName": name,
            "description": name if len(desc) == 0 else desc,
            "orchestrationSource": orch_id}

        return self._send_request('POST', url, payload, 'organization')

    def _create_or_update_partition(self, org_name, part_name, desc,
                                    dci_id=UNKNOWN_DCI_ID, vrf_prof=None,
                                    service_node_ip=UNKNOWN_SRVN_NODE_IP,
                                    operation='POST'):
        """Send create or update partition request to the DCNM.

        :param org_name: name of organization
        :param part_name: name of partition
        :param desc: description of partition
        :dci_id: DCI ID for inter-DC
        :vrf_prof: VRF Profile Name
        :service_node_ip: Service Node's Address
        """
        if part_name is None:
            part_name = self._part_name
        if vrf_prof is None or dci_id == UNKNOWN_DCI_ID or (
           service_node_ip == UNKNOWN_SRVN_NODE_IP):
            part_info = self._get_partition(org_name, part_name)
        if vrf_prof is None:
            vrf_prof = self.get_partition_vrfProf(org_name, part_name,
                                                  part_info=part_info)
        if dci_id == UNKNOWN_DCI_ID:
            dci_id = self.get_partition_dciId(org_name, part_name,
                                              part_info=part_info)
        if service_node_ip == UNKNOWN_SRVN_NODE_IP:
            service_node_ip = self.get_partition_serviceNodeIp(
                org_name, part_name, part_info=part_info)
        url = ((self._create_part_url % (org_name)) if operation == 'POST' else
               self._update_part_url % (org_name, part_name))

        payload = {
            "partitionName": part_name,
            "description": part_name if len(desc) == 0 else desc,
            "serviceNodeIpAddress": service_node_ip,
            "organizationName": org_name}

        # Check the DCNM version and find out whether it is need to have
        # extra payload for the new version when creating/updating a partition.
        if self._is_iplus:
            # Need to add extra payload for the new version.
            enable_dci = "true" if dci_id and int(dci_id) != 0 else "false"
            extra_payload = {
                "vrfProfileName": vrf_prof,
                "vrfName": ':'.join((org_name, part_name)),
                "dciId": dci_id,
                "enableDCIExtension": enable_dci}
            payload.update(extra_payload)

        return self._send_request(operation, url, payload, 'partition')

    def _get_partition(self, org_name, part_name=None):
        """send get partition request to the DCNM.

        :param org_name: name of organization
        :param part_name: name of partition
        """
        if part_name is None:
            part_name = self._part_name
        url = self._update_part_url % (org_name, part_name)
        res = self._send_request("GET", url, '', 'partition')
        if res and res.status_code in self._resp_ok:
            return res.json()

    def update_partition_static_route(self, org_name, part_name,
                                      static_ip_list, vrf_prof=None,
                                      service_node_ip=None):
        """Send static route update requests to DCNM.

        :param org_name: name of organization
        :param part_name: name of partition
        :static_ip_list: List of static IP addresses
        :vrf_prof: VRF Profile
        :service_node_ip: Service Node IP address
        """
        if part_name is None:
            part_name = self._part_name
        if vrf_prof is None:
            vrf_prof = self.default_vrf_profile
        operation = 'PUT'
        url = (self._update_part_url % (org_name, part_name))
        ip_str = ''
        ip_cnt = 0
        for ip in static_ip_list:
            ip_sub = "$n0" + str(ip_cnt) + "=" + str(ip) + ";"
            ip_str = ip_str + ip_sub
            ip_cnt = ip_cnt + 1
        cfg_args = {
            "$vrfName=" + org_name + ':' + part_name + ";"
            "$include_serviceNodeIpAddress=" + service_node_ip + ";"
            + ip_str
        }
        cfg_args = ';'.join(cfg_args)
        payload = {
            "partitionName": part_name,
            "organizationName": org_name,
            "dciExtensionStatus": "Not configured",
            "vrfProfileName": vrf_prof,
            "vrfName": ':'.join((org_name, part_name)),
            "configArg": cfg_args}

        res = self._send_request(operation, url, payload, 'partition')
        return (res is not None and res.status_code in self._resp_ok)

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
        if 'mobDomainName' in network_info:
            vlan_id = network_info['vlanId']
            mob_dom_name = network_info['mobDomainName']
            url = self._network_mob_url % (org_name, part_name, vlan_id,
                                           mob_dom_name)
        else:
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

    def _login_request(self, url_login):
        """Internal function to send login request. """

        expiration_time = self._exp_time
        payload = {'expirationTime': expiration_time}
        # TODO(padkrish), after testing with certificates, make the
        # verify option configurable.
        res = requests.post(url_login,
                            data=jsonutils.dumps(payload),
                            headers=self._req_headers,
                            auth=(self._user, self._pwd),
                            timeout=self.timeout_resp, verify=False)
        session_id = ''
        if res and res.status_code in self._resp_ok:
            session_id = res.json().get('Dcnm-Token')
        self._req_headers.update({'Dcnm-Token': session_id})

    def _login(self):
        """Login request to DCNM. """

        self._login_request(self._login_url)

    def _logout_request(self, url_logout):
        """Internal logout request to DCNM. """

        requests.post(url_logout,
                      headers=self._req_headers,
                      timeout=self.timeout_resp, verify=False)

    def _logout(self, url_arg=None):
        """Logout request to DCNM."""

        self._logout_request(self._logout_url)

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
                                   timeout=self.timeout_resp, verify=False)
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

        if self._is_iplus:
            # Need to add the vrf name to the network info
            prof = self._config_profile_get(network.config_profile)
            if prof and prof.get('profileSubType') == 'network:universal':
                # For universal profile vrf has to e organization:partition
                network_info["vrfName"] = ':'.join((tenant_name,
                                                    self._part_name))
            else:
                # Otherwise, it should be left empty.
                network_info["vrfName"] = ""

        LOG.info(_LI("Creating %s network in DCNM."), network_info)

        res = self._create_network(network_info)
        if res and res.status_code in self._resp_ok:
            LOG.info(_LI("Created %s network in DCNM."), network_info)
        else:
            LOG.error(_LE("Failed to create %s network in DCNM."),
                      network_info)
            raise dexc.DfaClientRequestFailed(reason=res)

    def create_service_network(self, tenant_name, network, subnet,
                               dhcp_range=True):
        """Create network on the DCNM.

        :param tenant_name: name of tenant the network belongs to
        :param network: network parameters
        :param subnet: subnet parameters of the network
        """
        network_info = {}
        subnet_ip_mask = subnet.cidr.split('/')
        if self._default_md is None:
            self._set_default_mobility_domain()
        vlan_id = '0'
        gw_ip = subnet.gateway_ip
        part_name = network.part_name
        if not part_name:
            part_name = self._part_name

        if network.vlan_id:
            vlan_id = str(network.vlan_id)
            if network.mob_domain_name is not None:
                mob_domain_name = network.mob_domain_name
            else:
                mob_domain_name = self._default_md
        else:
            mob_domain_name = None

        seg_id = str(network.segmentation_id)
        seg_str = "$segmentId=" + seg_id
        cfg_args = [
            seg_str,
            "$netMaskLength=" + subnet_ip_mask[1],
            "$gatewayIpAddress=" + gw_ip,
            "$networkName=" + network.name,
            "$vlanId=" + vlan_id,
            "$vrfName=" + tenant_name + ':' + part_name
        ]
        cfg_args = ';'.join(cfg_args)

        ip_range = ','.join(["%s-%s" % (p['start'], p['end']) for p in
                             subnet.allocation_pools])

        dhcp_scopes = {'ipRange': ip_range,
                       'subnet': subnet.cidr,
                       'gateway': gw_ip}

        network_info = {"vlanId": vlan_id,
                        "mobilityDomainId": mob_domain_name,
                        "profileName": network.config_profile,
                        "networkName": network.name,
                        "configArg": cfg_args,
                        "organizationName": tenant_name,
                        "partitionName": part_name,
                        "description": network.name,
                        "netmaskLength": subnet_ip_mask[1],
                        "gateway": gw_ip}
        if seg_id:
            network_info["segmentId"] = seg_id
        if dhcp_range:
            network_info["dhcpScope"] = dhcp_scopes
        if hasattr(subnet, 'secondary_gw'):
            network_info["secondaryGateway"] = subnet.secondary_gw
        if self._is_iplus:
            # Need to add the vrf name to the network info
            prof = self._config_profile_get(network.config_profile)
            if prof and prof.get('profileSubType') == 'network:universal':
                # For universal profile vrf has to e organization:partition
                network_info["vrfName"] = ':'.join((tenant_name, part_name))
            else:
                # Otherwise, it should be left empty.
                network_info["vrfName"] = ""

        LOG.info(_LI("Creating %s network in DCNM."), network_info)

        res = self._create_network(network_info)
        if res and res.status_code in self._resp_ok:
            LOG.info(_LI("Created %s network in DCNM."), network_info)
        else:
            LOG.error(_LE("Failed to create %s network in DCNM."),
                      network_info)
            raise dexc.DfaClientRequestFailed(reason=self._failure_msg(res))

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

    def delete_service_network(self, tenant_name, network):
        """Delete service network on the DCNM.

        :param tenant_name: name of tenant the network belongs to
        :param network: object that contains network parameters
        """

        network_info = {}
        part_name = network.part_name
        if not part_name:
            part_name = self._part_name
        seg_id = str(network.segmentation_id)
        if network.vlan:
            vlan_id = str(network.vlan)
            if network.mob_domain_name is not None:
                mob_domain_name = network.mob_domain_name
            else:
                # The current way will not work since _default_md is obtained
                # during create_service_network. It's preferrable to get it
                # during init TODO(padkrish)
                if self._default_md is None:
                    self._set_default_mobility_domain()
                mob_domain_name = self._default_md
            network_info = {
                'organizationName': tenant_name,
                'partitionName': part_name,
                'mobDomainName': mob_domain_name,
                'vlanId': vlan_id,
                'segmentId': seg_id,
            }
        else:
            network_info = {
                'organizationName': tenant_name,
                'partitionName': part_name,
                'segmentId': seg_id,
            }
        LOG.debug("Deleting %s network in DCNM.", network_info)

        res = self._delete_network(network_info)
        if res and res.status_code in self._resp_ok:
            LOG.debug("Deleted %s network in DCNM.", network_info)
        else:
            LOG.error(_LE("Failed to delete %s network in DCNM."),
                      network_info)
            raise dexc.DfaClientRequestFailed(reason=self._failure_msg(res))

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

    def delete_partition(self, org_name, partition_name):
        """Send partition delete request to DCNM.

        :param partition_name: name of partition to be deleted
        """
        res = self._delete_partition(org_name, partition_name)
        if res and res.status_code in self._resp_ok:
            LOG.debug("Deleted %s partition in DCNM.", partition_name)
        else:
            LOG.error(_LE("Failed to delete %(part)s partition in DCNM."
                      "Response: %(res)s"),
                      ({'part': partition_name, 'res': res}))
            raise dexc.DfaClientRequestFailed(reason=self._failure_msg(res))

    def create_project(self, orch_id, org_name, part_name, dci_id, desc=None):
        """Create project on the DCNM.

        :param orch_id: orchestrator ID
        :param org_name: name of organization.
        :param part_name: name of partition.
        :param dci_id: Data Center interconnect id.
        :param desc: description of project.
        """
        desc = desc or org_name
        res = self._create_org(orch_id, org_name, desc)
        if res and res.status_code in self._resp_ok:
            LOG.debug("Created %s organization in DCNM.", org_name)
        else:
            LOG.error(_LE("Failed to create %(org)s organization in DCNM."
                      "Response: %(res)s"), {'org': org_name, 'res': res})
            raise dexc.DfaClientRequestFailed(reason=res)

        self.create_partition(org_name, part_name, dci_id,
                              self.default_vrf_profile, desc=desc)

    def update_project(self, org_name, part_name, dci_id=UNKNOWN_DCI_ID,
                       service_node_ip=UNKNOWN_SRVN_NODE_IP,
                       vrf_prof=None, desc=None):
        """Update project on the DCNM.

        :param org_name: name of organization.
        :param part_name: name of partition.
        :param dci_id: Data Center interconnect id.
        :param desc: description of project.
        """
        desc = desc or org_name
        res = self._create_or_update_partition(org_name, part_name, desc,
                                               dci_id=dci_id,
                                               service_node_ip=service_node_ip,
                                               vrf_prof=vrf_prof,
                                               operation='PUT')
        if res and res.status_code in self._resp_ok:
            LOG.debug("Update %s partition in DCNM.", part_name)
        else:
            LOG.error(_LE("Failed to update %(part)s partition in DCNM."
                      "Response: %(res)s"), {'part': part_name, 'res': res})
            raise dexc.DfaClientRequestFailed(reason=res)

    def create_partition(self, org_name, part_name, dci_id, vrf_prof,
                         service_node_ip=None, desc=None):
        """Create partition on the DCNM.

        :param org_name: name of organization to be created
        :param part_name: name of partition to be created
        :param dci_id: DCI ID
        :vrf_prof: VRF profile for the partition
        :param service_node_ip: Specifies the Default route IP address.
        :param desc: string that describes organization
        """
        desc = desc or org_name
        res = self._create_or_update_partition(org_name, part_name,
                                               desc, dci_id=dci_id,
                                               service_node_ip=service_node_ip,
                                               vrf_prof=vrf_prof)
        if res and res.status_code in self._resp_ok:
            LOG.debug("Created %s partition in DCNM.", part_name)
        else:
            LOG.error(_LE("Failed to create %(part)s partition in DCNM."
                      "Response: %(res)s"), ({'part': part_name, 'res': res}))
            raise dexc.DfaClientRequestFailed(reason=self._failure_msg(res))

    def get_partition_vrfProf(self, org_name, part_name=None, part_info=None):
        """get VRF Profile for the partition from the DCNM.

        :param org_name: name of organization
        :param part_name: name of partition
        """
        vrf_profile = None
        if part_info is None:
            part_info = self._get_partition(org_name, part_name)
            LOG.info(_LI("query result from dcnm for partition info is %s"),
                     part_info)
        if ("vrfProfileName" in part_info):
            vrf_profile = part_info.get("vrfProfileName")
        return vrf_profile

    def get_partition_dciId(self, org_name, part_name, part_info=None):
        """get DCI ID for the partition.

        :param org_name: name of organization
        :param part_name: name of partition
        """
        if part_info is None:
            part_info = self._get_partition(org_name, part_name)
            LOG.info(_LI("query result from dcnm for partition info is %s"),
                     part_info)
        if part_info is not None and "dciId" in part_info:
            return part_info.get("dciId")

    def get_partition_serviceNodeIp(self, org_name, part_name, part_info=None):
        """get Service Node IP address from the DCNM.

        :param org_name: name of organization
        :param part_name: name of partition
        """
        if part_info is None:
            part_info = self._get_partition(org_name, part_name)
            LOG.info(_LI("query result from dcnm for partition info is %s"),
                     part_info)
        if part_info is not None and "serviceNodeIpAddress" in part_info:
            return part_info.get("serviceNodeIpAddress")

    def get_partition_segmentId(self, org_name, part_name, part_info=None):
        """get partition Segment ID from the DCNM.

        :param org_name: name of organization
        :param part_name: name of partition
        """
        if part_info is None:
            part_info = self._get_partition(org_name, part_name)
            LOG.info(_LI("query result from dcnm for partition info is %s"),
                     part_info)
        if part_info is not None and "partitionSegmentId" in part_info:
            return part_info.get("partitionSegmentId")

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

        url = '%s://%s/rest/dcnm-version' % (self.dcnm_protocol, self._ip)
        payload = {}

        try:
            res = self._send_request('GET', url, payload, 'dcnm-version')
            if res and res.status_code in self._resp_ok:
                return res.json().get('Dcnm-Version')
        except dexc.DfaClientRequestFailed as exc:
            LOG.error(_LE("Failed to get DCNM version."))
            sys.exit(_LE("ERROR: Failed to connect to DCNM: %s"), exc)

    def _verify_protocol(self, protocol):
        try:
            self._login_request("%s://%s/rest/logon" % (protocol, self._ip))
            self._logout_request("%s://%s/rest/logout" % (protocol, self._ip))
        except (requests.HTTPError, requests.Timeout,
                requests.ConnectionError) as exc:
            LOG.error(_LE("Login Test failed for %(protocol)s Exc %(exc)s."),
                      {'protocol': protocol, 'exc': exc})
            return False
        return True

    def get_dcnm_protocol(self):
        """Routine to find out if DCNM is using http or https.

        DCNM 10 (Fuji-4) and above does not support http. Only https is
        supported and enabled by default.
        Prior DCNM versions supported both http and https. But, only http
        was enabled by default.
        So, enabler needs to find out if DCNM is supporting http or https to
        be friendly with the existing installed setups.
        """
        if self._verify_protocol('https'):
            return 'https'
        if self._verify_protocol('http'):
            return 'http'
        sys.exit(_LE("ERROR: Both http and https test failed"))

    def _build_url(self, url_remaining):
        """This function builds the URL from host, protocol and string. """
        return self.host_protocol_url + url_remaining

    def fill_urls(self):
        """This assigns the URL's based on the protocol. """

        protocol = self.dcnm_protocol
        self._org_url = '%s://%s/rest/auto-config/organizations' % (
            (protocol, self._ip))
        self._create_network_url = ('%s://%s/' % (protocol, self._ip) +
                                    'rest/auto-config/organizations'
                                    '/%s/partitions/%s/networks')
        self.host_protocol_url = '%s://%s/' % (protocol, self._ip)
        self._create_network_url = self._build_url(
            'rest/auto-config/organizations'
            '/%s/partitions/%s/networks')
        self._cfg_profile_list_url = '%s://%s/rest/auto-config/profiles' % (
            (protocol, self._ip))
        self._cfg_profile_get_url = self._cfg_profile_list_url + '/%s'
        self._global_settings_url = self._build_url(
            'rest/auto-config/settings')
        self._create_part_url = self._build_url(
            'rest/auto-config/organizations/%s/partitions')
        self._update_part_url = self._build_url(
            'rest/auto-config/organizations/%s/partitions/%s')
        self._del_org_url = self._build_url(
            'rest/auto-config/organizations/%s')
        self._del_part = self._build_url(
            'rest/auto-config/organizations/%s/partitions/%s')
        self._network_url = self._build_url(
            'rest/auto-config/organizations/%s/partitions/'
            '%s/networks/segment/%s')
        self._network_mob_url = self._build_url(
            'rest/auto-config/organizations/%s/partitions/'
            '%s/networks/vlan/%s/mobility-domain/%s')
        self._segmentid_ranges_url = self._build_url(
            'rest/settings/segmentid-ranges')
        self._login_url = self._build_url('rest/logon')
        self._logout_url = self._build_url('rest/logout')
