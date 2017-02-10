# Copyright (c) 2017-2017 Cisco Systems, Inc.
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

"""
Implements REST API Client For Nexus
"""

import netaddr
import requests

from networking_cisco._i18n import _LE
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    exceptions as cexc)
from oslo_log import log as logging
from oslo_serialization import jsonutils

DEFAULT_HEADER = {"Content-type": "application/json", "Accept": "text/plain"}
COOKIE_HEADER = """
{"Cookie": %s, "Content-type": "application/json", "Accept": "text/plain"}"""
DEFAULT_SCHEME = "http"
ACCEPTED_CODES = [200, 201, 204]

LOG = logging.getLogger(__name__)


class CiscoNexusRestapiClient(object):

    def __init__(self, credentials,
                 accepted_codes=ACCEPTED_CODES,
                 scheme=DEFAULT_SCHEME,
                 timeout=30,
                 max_retries=2):
        """Initialize the rest api client for Nexus."""
        self.format = 'json'
        self.accepted_codes = accepted_codes
        self.action_prefix = 'http://%s/'
        self.scheme = scheme
        self.status = requests.codes.OK
        self.time_stats = {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.credentials = credentials

    def _get_cookie(self, mgmt_ip, config):
        """Performs authentication and retries cookie."""

        if mgmt_ip not in self.credentials:
            return None

        security_data = self.credentials[mgmt_ip]
        payload = {"aaaUser": {"attributes": {"name": security_data[0],
                                              "pwd": security_data[1]}}}
        headers = {"Content-type": "application/json", "Accept": "text/plain"}

        url = "http://{0}/api/aaaLogin.json".format(mgmt_ip)

        try:
            response = self.session.request('POST',
                           url,
                           data=jsonutils.dumps(payload),
                           headers=headers,
                           timeout=self.timeout * 2)
        except Exception as e:
            raise cexc.NexusConnectFailed(nexus_host=mgmt_ip,
                                         exc=e)

        self.status = response.status_code
        if response.status_code == requests.codes.OK:
            return response.headers.get('Set-Cookie')
        else:
            e = "REST API connect returned Error code: "
            e += str(self.status)
            raise cexc.NexusConnectFailed(nexus_host=mgmt_ip,
                                         exc=e)

    def send_request(self, method, action, body=None,
                    headers=None, ipaddr=None):
        """Perform the HTTP request.

        The response is in either JSON format or plain text. A GET method will
        invoke a JSON response while a PUT/POST/DELETE returns message from the
        the server in plain text format.
        Exception is raised when server replies with an INTERNAL SERVER ERROR
        status code (500) i.e. an error has occurred on the server or SERVICE
        UNAVAILABLE (404) i.e. server is not reachable.

        :param method: type of the HTTP request. POST, GET, PUT or DELETE
        :param action: path to which the client makes request
        :param body: dict of arguments which are sent as part of the request
        :param headers: header for the HTTP request
        :param server_ip: server_ip for the HTTP request.
        :returns: JSON or plain text in HTTP response
        """

        action = ''.join([self.scheme, '://%s/', action])
        if netaddr.valid_ipv6(ipaddr):
            # Enclose IPv6 address in [] in the URL
            action = action % ("[%s]" % ipaddr)
        else:
            # IPv4 address
            action = action % ipaddr

        config = action + " : " + body if body else action

        cookie = self._get_cookie(ipaddr, config)
        if not cookie or self.status != requests.codes.OK:
            return {}
        headers = {"Content-type": "application/json",
                   "Accept": "text/plain", "Cookie": cookie}

        for attempt in range(self.max_retries + 1):
            try:
                LOG.debug("[Nexus %(ipaddr)s attempt %(id)s]: Connecting.." %
                         {"ipaddr": ipaddr, "id": attempt})
                response = self.session.request(
                    method,
                    action,
                    data=body,
                    headers=headers,
                    timeout=self.timeout)
            except Exception as e:
                LOG.error(_LE(
                    "Exception raised %(err)s for Rest API %(cfg)s"),
                    {'err': str(e), 'cfg': config})
                raise cexc.NexusConfigFailed(nexus_host=ipaddr,
                                             config=config,
                                             exc=e)
            else:
                break

        status_string = requests.status_codes._codes[response.status_code][0]
        if response.status_code in self.accepted_codes:
            LOG.debug(
                "Good status %(status)s(%(code)d) returned for %(url)s",
                {'status': status_string,
                'code': response.status_code,
                'url': action})
            if 'application/json' in response.headers['content-type']:
                try:
                    return response.json()
                except ValueError:
                    return {}
        else:
            LOG.error(_LE(
                "Bad status %(status)s(%(code)d) returned for %(url)s"),
                {'status': status_string,
                'code': response.status_code,
                'url': action})
            LOG.error(_LE("Response text: %(txt)s"),
                      {'txt': response.text})
            raise cexc.NexusConfigFailed(nexus_host=ipaddr,
                                         config=action,
                                         exc=e)

    def rest_delete(self, action, ipaddr=None, body=None, headers=None):
        return self.send_request("DELETE", action, body=body,
                               headers=headers, ipaddr=ipaddr)

    def rest_get(self, action, ipaddr, body=None, headers=None):
        return self.send_request("GET", action, body=body,
                               headers=headers, ipaddr=ipaddr)

    def rest_post(self, action, ipaddr=None, body=None, headers=None):
        return self.send_request("POST", action, body=body,
                               headers=headers, ipaddr=ipaddr)
