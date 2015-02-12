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
#

import re

import requests
from requests import exceptions as r_exc
from requests_mock.contrib import fixture as mock_fixture

from networking_cisco.plugins.cisco.cfg_agent.device_drivers import (
    cisco_csr_rest_client as csr_client)
from neutron.tests import base


TEST_VRF = 'nrouter-123456'
BASE_URL = 'https://%s:55443/api/v1/'
LOCAL_URL = 'https://localhost:55443/api/v1/'

URI_HOSTNAME = 'global/host-name'
URI_USERS = 'global/local-users'
URI_AUTH = 'auth/token-services'
URI_INTERFACE_GE1 = 'interfaces/GigabitEthernet1'


class CiscoCsrBaseTestCase(base.BaseTestCase):

    """Helper methods to register mock intercepts - used by child classes."""

    def setUp(self, host='localhost', tunnel_ip='10.10.10.10', timeout=None):
        super(CiscoCsrBaseTestCase, self).setUp()
        self.base_url = BASE_URL % host
        self.requests = self.useFixture(mock_fixture.Fixture())
        info = {'rest_mgmt_ip': host,
                'username': 'stack', 'password': 'cisco', 'timeout': timeout}
        self.csr = csr_client.CsrRestClient(info)

    def _register_local_get(self, uri, json=None,
                            result_code=requests.codes.OK):
        self.requests.register_uri(
            'GET',
            LOCAL_URL + uri,
            status_code=result_code,
            json=json)

    def _register_local_post(self, uri, resource_id,
                             result_code=requests.codes.CREATED):
        self.requests.register_uri(
            'POST',
            LOCAL_URL + uri,
            status_code=result_code,
            headers={'location': LOCAL_URL + uri + '/' + str(resource_id)})

    def _register_local_delete(self, uri, resource_id, json=None,
                               result_code=requests.codes.NO_CONTENT):
        self.requests.register_uri(
            'DELETE',
            LOCAL_URL + uri + '/' + str(resource_id),
            status_code=result_code,
            json=json)

    def _register_local_delete_by_id(self, resource_id,
                                     result_code=requests.codes.NO_CONTENT):
        local_resource_re = re.compile(LOCAL_URL + '.+%s$' % resource_id)
        self.requests.register_uri(
            'DELETE',
            local_resource_re,
            status_code=result_code)

    def _register_local_put(self, uri, resource_id,
                            result_code=requests.codes.NO_CONTENT):
        self.requests.register_uri('PUT',
                                   LOCAL_URL + uri + '/' + resource_id,
                                   status_code=result_code)

    def _register_local_get_not_found(self, uri, resource_id,
                                      result_code=requests.codes.NOT_FOUND):
        self.requests.register_uri(
            'GET',
            LOCAL_URL + uri + '/' + str(resource_id),
            status_code=result_code)

    def _helper_register_auth_request(self):
        self.requests.register_uri('POST',
                                   LOCAL_URL + URI_AUTH,
                                   status_code=requests.codes.OK,
                                   json={'token-id': 'dummy-token'})


class TestCsrLoginRestApi(CiscoCsrBaseTestCase):

    """Test logging into CSR to obtain token-id."""

    def test_get_token(self):
        """Obtain the token and its expiration time."""
        self._helper_register_auth_request()
        self.assertTrue(self.csr.authenticate())
        self.assertEqual(requests.codes.OK, self.csr.status)
        self.assertIsNotNone(self.csr.token)

    def test_unauthorized_token_request(self):
        """Negative test of invalid user/password."""
        self.requests.register_uri('POST',
                                   LOCAL_URL + URI_AUTH,
                                   status_code=requests.codes.UNAUTHORIZED)
        self.csr.auth = ('stack', 'bogus')
        self.assertIsNone(self.csr.authenticate())
        self.assertEqual(requests.codes.UNAUTHORIZED, self.csr.status)

    def _simulate_wrong_host(self, request):
        if 'wrong-host' in request.url:
            raise r_exc.ConnectionError()

    def test_non_existent_host(self):
        """Negative test of request to non-existent host."""
        self.requests.add_matcher(self._simulate_wrong_host)
        self.csr.host = 'wrong-host'
        self.csr.token = 'Set by some previously successful access'
        self.assertIsNone(self.csr.authenticate())
        self.assertEqual(requests.codes.NOT_FOUND, self.csr.status)
        self.assertIsNone(self.csr.token)

    def _simulate_token_timeout(self, request):
        raise r_exc.Timeout()

    def test_timeout_on_token_access(self):
        """Negative test of a timeout on a request."""
        self.requests.add_matcher(self._simulate_token_timeout)
        self.assertIsNone(self.csr.authenticate())
        self.assertEqual(requests.codes.REQUEST_TIMEOUT, self.csr.status)
        self.assertIsNone(self.csr.token)


class TestCsrGetRestApi(CiscoCsrBaseTestCase):

    """Test CSR GET REST API."""

    def test_valid_rest_gets(self):
        """Simple GET requests.

        First request will do a post to get token (login). Assumes
        that there are two interfaces on the CSR.
        """

        self._helper_register_auth_request()
        self._register_local_get(URI_HOSTNAME,
                                 json={u'kind': u'object#host-name',
                                       u'host-name': u'Router'})
        self._register_local_get(URI_USERS,
                                 json={u'kind': u'collection#local-user',
                                       u'users': ['peter', 'paul', 'mary']})

        actual = self.csr.get_request(URI_HOSTNAME)
        self.assertEqual(requests.codes.OK, self.csr.status)
        self.assertIn('host-name', actual)
        self.assertIsNotNone(actual['host-name'])

        actual = self.csr.get_request(URI_USERS)
        self.assertEqual(requests.codes.OK, self.csr.status)
        self.assertIn('users', actual)


class TestCsrPostRestApi(CiscoCsrBaseTestCase):

    """Test CSR POST REST API."""

    def setUp(self, host='localhost', tunnel_ip='10.10.10.10', timeout=None):
        """Setup for each test in this suite.

        Each test case will have a normal authentication mock response
        registered here, although they may replace it, as needed.
        """
        super(TestCsrPostRestApi, self).setUp(host, tunnel_ip, timeout)
        self._helper_register_auth_request()

    def test_post_requests(self):
        """Simple POST requests (repeatable).

        First request will do a post to get token (login). Assumes
        that there are two interfaces (Ge1 and Ge2) on the CSR.
        """

        interface_re = re.compile('https://localhost:55443/.*/interfaces/'
                                  'GigabitEthernet\d/statistics')
        self.requests.register_uri('POST',
                                   interface_re,
                                   status_code=requests.codes.NO_CONTENT)

        actual = self.csr.post_request(
            'interfaces/GigabitEthernet1/statistics',
            payload={'action': 'clear'})
        self.assertEqual(requests.codes.NO_CONTENT, self.csr.status)
        self.assertIsNone(actual)
        actual = self.csr.post_request(
            'interfaces/GigabitEthernet2/statistics',
            payload={'action': 'clear'})
        self.assertEqual(requests.codes.NO_CONTENT, self.csr.status)
        self.assertIsNone(actual)

    def test_post_with_location(self):
        """Create a user and verify that location returned."""
        self.requests.register_uri(
            'POST',
            LOCAL_URL + URI_USERS,
            status_code=requests.codes.CREATED,
            headers={'location': LOCAL_URL + URI_USERS + '/test-user'})
        location = self.csr.post_request(
            URI_USERS,
            payload={'username': 'test-user',
                     'password': 'pass12345',
                     'privilege': 15})
        self.assertEqual(requests.codes.CREATED, self.csr.status)
        self.assertIn(URI_USERS + '/test-user', location)

    def test_post_missing_required_attribute(self):
        """Negative test of POST with missing mandatory info."""
        self.requests.register_uri('POST',
                                   LOCAL_URL + URI_USERS,
                                   status_code=requests.codes.BAD_REQUEST)
        self.csr.post_request(URI_USERS,
                              payload={'password': 'pass12345',
                                       'privilege': 15})
        self.assertEqual(requests.codes.BAD_REQUEST, self.csr.status)

    def test_post_invalid_attribute(self):
        """Negative test of POST with invalid info."""
        self.requests.register_uri('POST',
                                   LOCAL_URL + URI_USERS,
                                   status_code=requests.codes.BAD_REQUEST)
        self.csr.post_request(URI_USERS,
                              payload={'username': 'test-user',
                                       'password': 'pass12345',
                                       'privilege': 20})
        self.assertEqual(requests.codes.BAD_REQUEST, self.csr.status)

    def test_post_already_exists(self):
        """Negative test of a duplicate POST.

        Uses the lower level _do_request() API to just perform the POST and
        obtain the response, without any error processing.
        """

        self.requests.register_uri(
            'POST',
            LOCAL_URL + URI_USERS,
            status_code=requests.codes.CREATED,
            headers={'location': LOCAL_URL + URI_USERS + '/test-user'})

        location = self.csr._do_request(
            'POST',
            URI_USERS,
            payload={'username': 'test-user',
                     'password': 'pass12345',
                     'privilege': 15},
            more_headers=csr_client.HEADER_CONTENT_TYPE_JSON)
        self.assertEqual(requests.codes.CREATED, self.csr.status)
        self.assertIn(URI_USERS + '/test-user', location)
        self.csr.post_request(URI_USERS,
                              payload={'username': 'test-user',
                                       'password': 'pass12345',
                                       'privilege': 20})

        self.requests.register_uri(
            'POST',
            LOCAL_URL + URI_USERS,
            status_code=requests.codes.NOT_FOUND,
            json={u'error-code': -1,
                  u'error-message': u'user test-user already exists'})

        self.csr._do_request(
            'POST',
            URI_USERS,
            payload={'username': 'test-user',
                     'password': 'pass12345',
                     'privilege': 15},
            more_headers=csr_client.HEADER_CONTENT_TYPE_JSON)
        # Note: For local-user, a 404 error is returned. For
        # site-to-site connection a 400 is returned.
        self.assertEqual(requests.codes.NOT_FOUND, self.csr.status)

    def test_post_changing_value(self):
        """Negative test of a POST trying to change a value."""
        self.requests.register_uri(
            'POST',
            LOCAL_URL + URI_USERS,
            status_code=requests.codes.CREATED,
            headers={'location': LOCAL_URL + URI_USERS + '/test-user'})

        location = self.csr.post_request(
            URI_USERS,
            payload={'username': 'test-user',
                     'password': 'pass12345',
                     'privilege': 15})
        self.assertEqual(requests.codes.CREATED, self.csr.status)
        self.assertIn(URI_USERS + '/test-user', location)

        self.requests.register_uri(
            'POST',
            LOCAL_URL + URI_USERS,
            status_code=requests.codes.NOT_FOUND,
            json={u'error-code': -1,
                  u'error-message': u'user test-user already exists'})

        actual = self.csr.post_request(URI_USERS,
                                       payload={'username': 'test-user',
                                                'password': 'changed',
                                                'privilege': 15})
        self.assertEqual(requests.codes.NOT_FOUND, self.csr.status)
        expected = {u'error-code': -1,
                    u'error-message': u'user test-user already exists'}
        self.assertDictSupersetOf(expected, actual)


class TestCsrPutRestApi(CiscoCsrBaseTestCase):

    """Test CSR PUT REST API."""

    def _save_resources(self):
        self._register_local_get(URI_HOSTNAME,
                                 json={u'kind': u'object#host-name',
                                       u'host-name': u'Router'})
        interface_info = {u'kind': u'object#interface',
                          u'description': u'Changed description',
                          u'if-name': 'interfaces/GigabitEthernet1',
                          u'proxy-arp': True,
                          u'subnet-mask': u'255.255.255.0',
                          u'icmp-unreachable': True,
                          u'nat-direction': u'',
                          u'icmp-redirects': True,
                          u'ip-address': u'192.168.200.1',
                          u'verify-unicast-source': False,
                          u'type': u'ethernet'}
        self._register_local_get(URI_INTERFACE_GE1,
                                 json=interface_info)
        details = self.csr.get_request(URI_HOSTNAME)
        if self.csr.status != requests.codes.OK:
            self.fail("Unable to save original host name")
        self.original_host = details['host-name']
        details = self.csr.get_request(URI_INTERFACE_GE1)
        if self.csr.status != requests.codes.OK:
            self.fail("Unable to save interface Ge1 description")
        self.original_if = details
        self.csr.token = None

    def _restore_resources(self, user, password):
        """Restore the host name and interface description.

        Must restore the user and password, so that authentication
        token can be obtained (as some tests corrupt auth info).
        Will also clear token, so that it gets a fresh token.
        """

        self._register_local_put('global', 'host-name')
        self._register_local_put('interfaces', 'GigabitEthernet1')

        self.csr.auth = (user, password)
        self.csr.token = None
        payload = {'host-name': self.original_host}
        self.csr.put_request(URI_HOSTNAME, payload=payload)
        if self.csr.status != requests.codes.NO_CONTENT:
            self.fail("Unable to restore host name after test")
        payload = {'description': self.original_if['description'],
                   'if-name': self.original_if['if-name'],
                   'ip-address': self.original_if['ip-address'],
                   'subnet-mask': self.original_if['subnet-mask'],
                   'type': self.original_if['type']}
        self.csr.put_request(URI_INTERFACE_GE1,
                             payload=payload)
        if self.csr.status != requests.codes.NO_CONTENT:
            self.fail("Unable to restore I/F Ge1 description after test")

    def setUp(self, host='localhost', tunnel_ip='10.10.10.10', timeout=None):
        """Setup for each test in this suite.

        Each test case will have a normal authentication mock response
        registered here, although they may replace it, as needed. In
        addition, resources are saved, before each test is run, and
        restored, after each test completes.
        """
        super(TestCsrPutRestApi, self).setUp(host, tunnel_ip, timeout)
        self._helper_register_auth_request()
        self._save_resources()
        self.addCleanup(self._restore_resources, 'stack', 'cisco')

    def test_put_requests(self):
        """Simple PUT requests (repeatable).

        First request will do a post to get token (login). Assumes
        that there are two interfaces on the CSR (Ge1 and Ge2).
        """

        self._register_local_put('interfaces', 'GigabitEthernet1')
        self._register_local_put('global', 'host-name')

        actual = self.csr.put_request(URI_HOSTNAME,
                                      payload={'host-name': 'TestHost'})
        self.assertEqual(requests.codes.NO_CONTENT, self.csr.status)
        self.assertIsNone(actual)

        actual = self.csr.put_request(URI_HOSTNAME,
                                      payload={'host-name': 'TestHost2'})
        self.assertEqual(requests.codes.NO_CONTENT, self.csr.status)
        self.assertIsNone(actual)

    def test_change_interface_description(self):
        """Test that interface description can be changed.

        This was a problem with an earlier version of the CSR image and is
        here to prevent regression.
        """
        self._register_local_put('interfaces', 'GigabitEthernet1')
        payload = {'description': u'Changed description',
                   'if-name': self.original_if['if-name'],
                   'ip-address': self.original_if['ip-address'],
                   'subnet-mask': self.original_if['subnet-mask'],
                   'type': self.original_if['type']}
        actual = self.csr.put_request(URI_INTERFACE_GE1, payload=payload)
        self.assertEqual(requests.codes.NO_CONTENT, self.csr.status)
        self.assertIsNone(actual)
        actual = self.csr.get_request(URI_INTERFACE_GE1)
        self.assertEqual(requests.codes.OK, self.csr.status)
        self.assertIn('description', actual)
        self.assertEqual(u'Changed description',
                         actual['description'])

    def ignore_test_change_to_empty_interface_description(self):
        """Test that interface description can be changed to empty string.

        This is here to prevent regression, where the CSR was rejecting
        an attempt to set the description to an empty string.
        """
        self._register_local_put('interfaces', 'GigabitEthernet1')
        payload = {'description': '',
                   'if-name': self.original_if['if-name'],
                   'ip-address': self.original_if['ip-address'],
                   'subnet-mask': self.original_if['subnet-mask'],
                   'type': self.original_if['type']}
        actual = self.csr.put_request(URI_INTERFACE_GE1, payload=payload)
        self.assertEqual(requests.codes.NO_CONTENT, self.csr.status)
        self.assertIsNone(actual)
        actual = self.csr.get_request(URI_INTERFACE_GE1)
        self.assertEqual(requests.codes.OK, self.csr.status)
        self.assertIn('description', actual)
        self.assertEqual('', actual['description'])


class TestCsrDeleteRestApi(CiscoCsrBaseTestCase):

    """Test CSR DELETE REST API."""

    def setUp(self, host='localhost', tunnel_ip='10.10.10.10', timeout=None):
        """Setup for each test in this suite.

        Each test case will have a normal authentication mock response
        registered here, although they may replace it, as needed.
        """
        super(TestCsrDeleteRestApi, self).setUp(host, tunnel_ip, timeout)
        self._helper_register_auth_request()

    def _make_dummy_user(self):
        """Create a user that will be later deleted."""
        self.requests.register_uri(
            'POST',
            LOCAL_URL + URI_USERS,
            status_code=requests.codes.CREATED,
            headers={'location': LOCAL_URL + URI_USERS + '/dummy'})
        self.csr.post_request(URI_USERS,
                              payload={'username': 'dummy',
                                       'password': 'dummy',
                                       'privilege': 15})
        self.assertEqual(requests.codes.CREATED, self.csr.status)

    def test_delete_requests(self):
        """Simple DELETE requests (creating entry first)."""
        self._register_local_delete(URI_USERS, 'dummy')
        self._make_dummy_user()
        self.csr.token = None  # Force login
        self.csr.delete_request(URI_USERS + '/dummy')
        self.assertEqual(requests.codes.NO_CONTENT, self.csr.status)
        # Delete again, but without logging in this time
        self._make_dummy_user()
        self.csr.delete_request(URI_USERS + '/dummy')
        self.assertEqual(requests.codes.NO_CONTENT, self.csr.status)

    def test_delete_non_existent_entry(self):
        """Negative test of trying to delete a non-existent user."""
        expected = {u'error-code': -1,
                    u'error-message': u'user unknown not found'}
        self._register_local_delete(URI_USERS, 'unknown',
                                    result_code=requests.codes.NOT_FOUND,
                                    json=expected)
        actual = self.csr.delete_request(URI_USERS + '/unknown')
        self.assertEqual(requests.codes.NOT_FOUND, self.csr.status)
        self.assertDictSupersetOf(expected, actual)

    def test_delete_not_allowed(self):
        """Negative test of trying to delete the host-name."""
        self._register_local_delete(
            'global', 'host-name',
            result_code=requests.codes.METHOD_NOT_ALLOWED)
        self.csr.delete_request(URI_HOSTNAME)
        self.assertEqual(requests.codes.METHOD_NOT_ALLOWED,
                         self.csr.status)


class TestCsrRestApiFailures(CiscoCsrBaseTestCase):

    """Test failure cases common for all REST APIs.

    Uses the lower level _do_request() to just perform the operation and get
    the result, without any error handling.
    """

    def setUp(self, host='localhost', tunnel_ip='10.10.10.10', timeout=0.1):
        """Setup for each test in this suite.

        Each test case will have a normal authentication mock response
        registered here, although they may replace it, as needed.
        """
        super(TestCsrRestApiFailures, self).setUp(host, tunnel_ip, timeout)
        self._helper_register_auth_request()

    def _simulate_timeout(self, request):
        if URI_HOSTNAME in request.path_uri:
            raise r_exc.Timeout()

    def test_request_for_non_existent_resource(self):
        """Negative test of non-existent resource on REST request."""
        self.requests.register_uri('POST',
                                   LOCAL_URL + 'no/such/request',
                                   status_code=requests.codes.NOT_FOUND)
        self.csr.post_request('no/such/request')
        self.assertEqual(requests.codes.NOT_FOUND, self.csr.status)
        # The result is HTTP 404 message, so no error content to check

    def _simulate_get_timeout(self, request):
        """Will raise exception for any host request to this resource."""
        if URI_HOSTNAME in request.path_url:
            raise r_exc.Timeout()

    def test_timeout_during_request(self):
        """Negative test of timeout during REST request."""
        self.requests.add_matcher(self._simulate_get_timeout)
        self.csr._do_request('GET', URI_HOSTNAME)
        self.assertEqual(requests.codes.REQUEST_TIMEOUT, self.csr.status)

    def _simulate_auth_failure(self, request):
        """First time auth POST is done, re-report unauthorized."""
        if URI_AUTH in request.path_url and not self.called_once:
            self.called_once = True
            resp = requests.Response()
            resp.status_code = requests.codes.UNAUTHORIZED
            return resp

    def test_token_expired_on_request(self):
        """Token expired before trying a REST request.

        First, the token is set to a bogus value, to force it to
        try to authenticate on the GET request. Second, a mock that
        runs once, will simulate an auth failure. Third, the normal
        auth mock will simulate success.
        """

        self._register_local_get(URI_HOSTNAME,
                                 json={u'kind': u'object#host-name',
                                       u'host-name': u'Router'})
        self.called_once = False
        self.requests.add_matcher(self._simulate_auth_failure)
        self.csr.token = '123'  # These are 44 characters, so won't match
        actual = self.csr._do_request('GET', URI_HOSTNAME)
        self.assertEqual(requests.codes.OK, self.csr.status)
        self.assertIn('host-name', actual)
        self.assertIsNotNone(actual['host-name'])

    def test_failed_to_obtain_token_for_request(self):
        """Negative test of unauthorized user for REST request."""
        self.csr.auth = ('stack', 'bogus')
        self._register_local_get(URI_HOSTNAME,
                                 result_code=requests.codes.UNAUTHORIZED)
        self.csr._do_request('GET', URI_HOSTNAME)
        self.assertEqual(requests.codes.UNAUTHORIZED, self.csr.status)
