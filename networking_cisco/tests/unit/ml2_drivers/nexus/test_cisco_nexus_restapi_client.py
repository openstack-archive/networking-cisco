# Copyright (c) 2017 Cisco Systems, Inc.
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
Basic Test Class to verify REST API Client code "nexus_restapi_client.py"
"""

import mock
import requests

from networking_cisco.ml2_drivers.nexus import (
    constants as const)
from networking_cisco.ml2_drivers.nexus import (
    nexus_restapi_network_driver as rest)

from neutron.tests.unit import testlib_api
from oslo_serialization import jsonutils


class TestCiscoNexusRestapiClient(testlib_api.SqlTestCase):

    """Unit tests for Cisco REST API client."""

    def setUp(self):
        self.nexus_dict = self._build_nexus_switch_db()
        self.mock_Session = mock.Mock()
        mock.patch.object(requests,
                 'Session',
                 return_value=self.mock_Session).start()
        self.r_driver = rest.CiscoNexusRestapiDriver(self.nexus_dict)
        super(TestCiscoNexusRestapiClient, self).setUp()

    def json(self):

        return {u'imdata': [{u'eqptCh': {u'attributes': {
                u'descr': u'Nexus9000 C9396PX Chassis'}}}]}

    def json_cli(self):

        return {u'ins_api': {u'outputs': {u'output': [{
                u'msg': u'Success', u'body': {}, u'code': u'200'}, {
                u'msg': u'Success', u'body': {}, u'code': u'200'}, {
                u'body': u'warning', u'msg': u'Success', u'code': u'200'}]},
                u'version': u'1.0', u'type': u'cli_conf', u'sid': u'eoc'}}

    def json_err(self):

        raise Exception("json_err raising an exception")

    def _request_on_count(self, username, password, verify,
                          match_range=None, json_usr=None):

        """Generate side effect for restapi client Session.

        This method verifies the username, password, and verify settings
        are correct as input into restapi client request calls.  This
        verifies the credential data base is built correctly and
        arguments are fed into the restapi client apis correctly.

        Additionally, this method will set the status code to 403
        based on count to values in match_range list.  This
        status_code indicates the cookie has expired and needs to
        be refreshed to continue chatting with the host.

        Usage Example:

        The following call will verify username and password in the data
        for POST requests trying to do a AAAlogin. For all requests,
        the verify argument is checked against the verify arg passed into
        request.  On the 4th request call, it will return 403 which should
        force a cookie refresh.
        _request_on_count('admin', 'Shhh1', '/path/to/cafile.crt', ['4'])
        """

        self.verify = verify

        def _side_effect_request(
            method, url,
            params=None,
            data=None,
            headers=None,
            cookies=None,
            files=None,
            auth=None,
            timeout=None,
            allow_redirects=True,
            proxies=None,
            hooks=None,
            stream=None,
            verify=None,
            cert=None,
            json=None):

            if not hasattr(self, "count"):
                self.count = 0

            headers = {'content-type': 'application/json'}
            if self.verify != verify:
                raise Exception("request() 'verify' is incorrect")

            rsp = requests.models.Response

            match = False
            if match_range is not None:
                self.count += 1
                match = self.count in match_range

            if match:

                rsp.status_code = 403

            elif method == "POST" and "aaaLogin" in url:

                testdata = jsonutils.loads(data)
                if (password != testdata['aaaUser']['attributes']['pwd']):
                    raise Exception("request() 'password' is incorrect.")
                if (username != testdata['aaaUser']['attributes']['name']):
                    raise Exception("request() 'username' is incorrect.")

                rsp.status_code = 200
                rsp.headers = {'Set-Cookie': 'this is a test'}

            elif method == "POST" and "cli_conf" in data:

                rsp.status_code = 200
                rsp.headers = headers
                rsp.json = self.json_cli

            elif method == "GET":

                rsp.status_code = 200
                rsp.headers = headers
                rsp.json = self.json

            if json_usr:
                rsp.json = json_usr

            return rsp

        return _side_effect_request

    def _build_nexus_switch_db(self):
        nexus_dict = {}
        nexus_dict['1.1.1.1'] = {}
        nexus_dict['1.1.1.1'][const.USERNAME] = 'admin'
        nexus_dict['1.1.1.1'][const.PASSWORD] = 'Shhhh1'
        nexus_dict['1.1.1.1'][const.HTTPS_VERIFY] = True
        nexus_dict['1.1.1.1'][const.HTTPS_CERT] = (
            '/home/caboucha/test_src/openstack-outfiles/nexus.crt')
        nexus_dict['2.2.2.2'] = {}
        nexus_dict['2.2.2.2'][const.USERNAME] = 'admin'
        nexus_dict['2.2.2.2'][const.PASSWORD] = 'Shhhh2'
        nexus_dict['2.2.2.2'][const.HTTPS_VERIFY] = True
        nexus_dict['2.2.2.2'][const.HTTPS_CERT] = None
        nexus_dict['3.3.3.3'] = {}
        nexus_dict['3.3.3.3'][const.USERNAME] = 'admin'
        nexus_dict['3.3.3.3'][const.PASSWORD] = 'Shhhh3'
        nexus_dict['3.3.3.3'][const.HTTPS_VERIFY] = False
        nexus_dict['3.3.3.3'][const.HTTPS_CERT] = None
        nexus_dict['4.4.4.4'] = {}
        nexus_dict['4.4.4.4'][const.USERNAME] = 'admin'
        nexus_dict['4.4.4.4'][const.PASSWORD] = 'Shhhh1'
        nexus_dict['4.4.4.4'][const.HTTPS_VERIFY] = True
        nexus_dict['4.4.4.4'][const.HTTPS_CERT] = (
            '/home/caboucha/test_src/openstack-outfiles/nexus.crt')
        nexus_dict['4.4.4.4'][const.IF_PC] = 'user cmd1;user cmd2'
        nexus_dict['5.5.5.5'] = {}
        nexus_dict['5.5.5.5'][const.USERNAME] = 'admin'
        nexus_dict['5.5.5.5'][const.PASSWORD] = 'Shhhh1'
        nexus_dict['5.5.5.5'][const.HTTPS_VERIFY] = False
        nexus_dict['5.5.5.5'][const.HTTPS_CERT] = None
        nexus_dict['5.5.5.5'][const.IF_PC] = 'user cmd1;user cmd2'

        return nexus_dict

    def _check_get_nexus_type(self, ipaddr, expected_count):

        nexus_type = self.r_driver.get_nexus_type(ipaddr)
        if nexus_type != const.NEXUS_9K:
            raise Exception("test_verify_with_local_certificate")

        self.assertEqual(expected_count,
                         self.mock_Session.request.call_count,
                        "Expecting call count of 2")
        self.mock_Session.reset_mock()

    def _check_verify(self, ipaddr, username, password, verify):

        config = {'request.side_effect':
                  self._request_on_count(username, password,
                                         verify, range(4, 5))}
        self.mock_Session.configure_mock(**config)

        # Request called twice: 1-get initial cookie,
        # 2-get nexus type
        self._check_get_nexus_type(ipaddr, 2)

        # Request called once: only get nexus type since cookie exists
        self._check_get_nexus_type(ipaddr, 1)

        # Request called 3 times: 1-first get nexus type returns 403,
        # 2- get another cookie, 3-successful get nexus type
        self._check_get_nexus_type(ipaddr, 3)

    def test_verify_with_local_certificate(self):

        ipaddr = '1.1.1.1'
        self._check_verify(ipaddr,
                           self.nexus_dict[ipaddr][const.USERNAME],
                           self.nexus_dict[ipaddr][const.PASSWORD],
                           self.nexus_dict[ipaddr][const.HTTPS_CERT])

    def test_verify_with_nonlocal_certificate(self):

        ipaddr = '2.2.2.2'
        self._check_verify(ipaddr,
                           self.nexus_dict[ipaddr][const.USERNAME],
                           self.nexus_dict[ipaddr][const.PASSWORD],
                           self.nexus_dict[ipaddr][const.HTTPS_VERIFY])

    def test_verify_no_certificate(self):

        ipaddr = '3.3.3.3'
        self._check_verify(ipaddr,
                           self.nexus_dict[ipaddr][const.USERNAME],
                           self.nexus_dict[ipaddr][const.PASSWORD],
                           self.nexus_dict[ipaddr][const.HTTPS_VERIFY])

    def test_verify_for_cli_with_local_cert(self):
        # Since the config contains const.IF_PC, it will cause
        # _send_cli_config_string to get called as opposed to
        # send_edit_string.  This is a different authentication path
        # through the client's send_request since it sends CLI
        # events instead of RESTAPI events to the Nexus.

        ipaddr = '4.4.4.4'
        config = {'request.side_effect':
                  self._request_on_count(
                      self.nexus_dict[ipaddr][const.USERNAME],
                      self.nexus_dict[ipaddr][const.PASSWORD],
                      self.nexus_dict[ipaddr][const.HTTPS_CERT])}
        self.mock_Session.configure_mock(**config)

        self.r_driver._apply_user_port_channel_config(
            '4.4.4.4', 44)

        # The verify value passed in send_request is checked
        # in side_effect handling.  If incorrect, exception raised.
        # No need to check again.
        self.mock_Session.reset_mock()

    def test_verify_for_cli_no_cert(self):
        # Since the config contains const.IF_PC, it will cause
        # _send_cli_config_string to get called as opposed to
        # send_edit_string.  This is a different authentication path
        # through the client's send_request since it sends CLI
        # events instead of RESTAPI events to the Nexus.

        ipaddr = '5.5.5.5'
        config = {'request.side_effect':
                  self._request_on_count(
                      self.nexus_dict[ipaddr][const.USERNAME],
                      self.nexus_dict[ipaddr][const.PASSWORD],
                      self.nexus_dict[ipaddr][const.HTTPS_VERIFY])}
        self.mock_Session.configure_mock(**config)

        self.r_driver._apply_user_port_channel_config(
            '5.5.5.5', 44)

        # The verify value passed in send_request is checked
        # in side_effect handling.  If incorrect, exception raised.
        # No need to check again.
        self.mock_Session.reset_mock()

    def test_bad_json_with_get_nexus_type(self):

        ipaddr = '3.3.3.3'
        config = {'request.side_effect':
                  self._request_on_count(
                      self.nexus_dict[ipaddr][const.USERNAME],
                      self.nexus_dict[ipaddr][const.PASSWORD],
                      self.nexus_dict[ipaddr][const.HTTPS_VERIFY],
                      json_usr=self.json_err)}
        self.mock_Session.configure_mock(**config)

        nexus_type = self.r_driver.get_nexus_type(ipaddr)
        if nexus_type != -1:
            raise Exception("bad json content test failed.")

        self.mock_Session.reset_mock()
