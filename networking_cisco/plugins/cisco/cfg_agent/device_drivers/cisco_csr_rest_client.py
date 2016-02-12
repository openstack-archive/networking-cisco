# Copyright 2015 Cisco Systems, Inc.  All rights reserved.
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

import six
import time

from oslo_log import log as logging
from oslo_serialization import jsonutils
import requests
from requests import exceptions as r_exc

from networking_cisco._i18n import _LE, _LW


TIMEOUT = 20.0

LOG = logging.getLogger(__name__)
HEADER_CONTENT_TYPE_JSON = {'content-type': 'application/json'}
URL_BASE = 'https://%(host)s/api/v1/%(resource)s'


class CsrRestClient(object):

    """REST CsrRestClient for accessing the Cisco Cloud Services Router."""

    def __init__(self, settings):
        self.port = str(settings.get('protocol_port', 55443))
        self.host = ':'.join([settings.get('rest_mgmt_ip', ''), self.port])
        self.auth = (settings['username'], settings['password'])
        self.token = None
        self.status = requests.codes.OK
        self.timeout = settings.get('timeout')
        self.max_tries = 5
        self.session = requests.Session()

    def _response_info_for(self, response, method):
        """Return contents or location from response.

        For a POST or GET with a 200 response, the response content
        is returned.

        For a POST with a 201 response, return the header's location,
        which contains the identifier for the created resource.

        If there is an error, return the response content, so that
        it can be used in error processing ('error-code', 'error-message',
        and 'detail' fields).
        """
        if method in ('POST', 'GET') and self.status == requests.codes.OK:
            LOG.debug('RESPONSE: %s', response.json())
            return response.json()
        if method == 'POST' and self.status == requests.codes.CREATED:
            return response.headers.get('location', '')
        if self.status >= requests.codes.BAD_REQUEST and response.content:
            if six.b('error-code') in response.content:
                content = jsonutils.loads(response.content)
                LOG.debug("Error response content %s", content)
                return content

    def _request(self, method, url, **kwargs):
        """Perform REST request and save response info."""
        try:
            LOG.debug("%(method)s: Request for %(resource)s payload: "
                      "%(payload)s",
                      {'method': method.upper(), 'resource': url,
                       'payload': kwargs.get('data')})
            start_time = time.time()
            response = self.session.request(method, url, verify=False,
                                            timeout=self.timeout, **kwargs)
            LOG.debug("%(method)s Took %(time).2f seconds to process",
                      {'method': method.upper(),
                       'time': time.time() - start_time})
        except (r_exc.Timeout, r_exc.SSLError) as te:
            # Should never see SSLError, unless requests package is old (<2.0)
            timeout_val = 0.0 if self.timeout is None else self.timeout
            LOG.warning(_LW("%(method)s: Request timeout%(ssl)s "
                            "(%(timeout).3f sec) for CSR(%(host)s)"),
                        {'method': method,
                         'timeout': timeout_val,
                         'ssl': '(SSLError)'
                         if isinstance(te, r_exc.SSLError) else '',
                         'host': self.host})
            self.status = requests.codes.REQUEST_TIMEOUT
        except r_exc.ConnectionError:
            LOG.exception(_LE("%(method)s: Unable to connect to "
                              "CSR(%(host)s)"),
                          {'method': method, 'host': self.host})
            self.status = requests.codes.NOT_FOUND
        except Exception as e:
            LOG.error(_LE("%(method)s: Unexpected error for CSR (%(host)s): "
                          "%(error)s"),
                      {'method': method, 'host': self.host, 'error': e})
            self.status = requests.codes.INTERNAL_SERVER_ERROR
        else:
            self.status = response.status_code
            LOG.debug("%(method)s: Completed [%(status)s]",
                      {'method': method, 'status': self.status})
            return self._response_info_for(response, method)

    def authenticate(self):
        """Obtain a token to use for subsequent CSR REST requests.

        This is called when there is no token yet, or if the token has expired
        and attempts to use it resulted in an UNAUTHORIZED REST response.
        """

        url = URL_BASE % {'host': self.host, 'resource': 'auth/token-services'}
        headers = {'Content-Length': '0',
                   'Accept': 'application/json'}
        headers.update(HEADER_CONTENT_TYPE_JSON)
        LOG.debug("%(auth)s with CSR %(host)s",
                  {'auth': 'Authenticating' if self.token is None
                   else 'Reauthenticating', 'host': self.host})
        self.token = None
        response = self._request("POST", url, headers=headers, auth=self.auth)
        if response:
            self.token = response['token-id']
            LOG.debug("Successfully authenticated with CSR %s", self.host)
            return True
        LOG.error(_LE("Failed authentication with CSR %(host)s [%(status)s]"),
                  {'host': self.host, 'status': self.status})

    def _do_request(self, method, resource, payload=None, more_headers=None,
                    full_url=False):
        """Perform a REST request to a CSR resource.

        If this is the first time interacting with the CSR, a token will
        be obtained. If the request fails, due to an expired token, the
        token will be obtained and the request will be retried once more.
        """

        if self.token is None:
            if not self.authenticate():
                return

        if full_url:
            url = resource
        else:
            url = ('https://%(host)s/api/v1/%(resource)s' %
                   {'host': self.host, 'resource': resource})
        headers = {'Accept': 'application/json', 'X-auth-token': self.token}
        if more_headers:
            headers.update(more_headers)
        if payload:
            payload = jsonutils.dumps(payload)
        response = self._request(method, url, data=payload, headers=headers)
        if self.status == requests.codes.UNAUTHORIZED:
            if not self.authenticate():
                return
            headers['X-auth-token'] = self.token
            response = self._request(method, url, data=payload,
                                     headers=headers)
        if self.status != requests.codes.REQUEST_TIMEOUT:
            return response
        LOG.error(_LE("%(method)s: Request timeout for CSR(%(host)s)"),
                  {'method': method, 'host': self.host})

    def get_request(self, resource, full_url=False):
        """Perform a REST GET requests for a CSR resource."""
        return self._do_request('GET', resource, full_url=full_url)

    def post_request(self, resource, payload=None):
        """Perform a POST request to a CSR resource."""
        return self._do_request('POST', resource, payload=payload,
                                more_headers=HEADER_CONTENT_TYPE_JSON)

    def put_request(self, resource, payload=None):
        """Perform a PUT request to a CSR resource."""
        return self._do_request('PUT', resource, payload=payload,
                                more_headers=HEADER_CONTENT_TYPE_JSON)

    def delete_request(self, resource):
        """Perform a DELETE request on a CSR resource."""
        return self._do_request('DELETE', resource,
                                more_headers=HEADER_CONTENT_TYPE_JSON)
