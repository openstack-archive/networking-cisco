# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import mock
import socket
import ssl

from oslo_config import cfg

from neutron.tests import base

from networking_cisco.ml2_drivers.ucsm import ucs_ssl
from networking_cisco.ml2_drivers.ucsm import ucsm_network_driver

from ucsmsdk import ucsdriver


class TestCiscoUcsmSSL(base.BaseTestCase):

    """Unit tests for SSL overrides."""

    def test_SSLContext_verify_true(self):
        cfg.CONF.set_override("ucsm_https_verify", True,
                              group="ml2_cisco_ucsm")
        context = ucs_ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_SSLContext_verify_false(self):
        cfg.CONF.set_override("ucsm_https_verify", False,
                              group="ml2_cisco_ucsm")
        context = ucs_ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        self.assertEqual(context.verify_mode, ssl.CERT_NONE)

    def test_wrap_socket_verify_true(self):
        cfg.CONF.set_override("ucsm_https_verify", True,
                              group="ml2_cisco_ucsm")
        sock = socket.socket()
        wrapped_sock = ucs_ssl.wrap_socket(sock)
        context = wrapped_sock.context
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        wrapped_sock.close()

    def test_wrap_socket_verify_false(self):
        cfg.CONF.set_override("ucsm_https_verify", False,
                              group="ml2_cisco_ucsm")
        sock = socket.socket()
        wrapped_sock = ucs_ssl.wrap_socket(sock)
        context = wrapped_sock.context
        self.assertEqual(context.verify_mode, ssl.CERT_NONE)
        wrapped_sock.close()

    def test_wrap_socket_verify_false_cert_reqs_true(self):
        cfg.CONF.set_override("ucsm_https_verify", False,
                              group="ml2_cisco_ucsm")
        sock = socket.socket()
        wrapped_sock = ucs_ssl.wrap_socket(sock,
                                           cert_reqs=ssl.CERT_REQUIRED)
        context = wrapped_sock.context

        self.assertNotEqual(context.verify_mode, ssl.CERT_REQUIRED)
        wrapped_sock.close()

    def test_wrap_socket_verify_true_cert_reqs_false(self):
        cfg.CONF.set_override("ucsm_https_verify", True,
                              group="ml2_cisco_ucsm")
        sock = socket.socket()
        wrapped_sock = ucs_ssl.wrap_socket(sock,
                                           cert_reqs=ssl.CERT_NONE)
        context = wrapped_sock.context
        self.assertNotEqual(context.verify_mode, ssl.CERT_NONE)
        wrapped_sock.close()


class TestUcsmsdkPatch(base.BaseTestCase):

    """Unit tests for Cisco ML2 UCS Manager SSL override for ucsmsdk."""

    # Test monkey patched ssl lib gets loaded
    @mock.patch.object(ucsm_network_driver.CiscoUcsmDriver,
                       "_create_host_and_sp_dicts_from_config")
    def test_ucsmsdk_ssl_monkey_patch(self, mock_create_host):
        network_driver = ucsm_network_driver.CiscoUcsmDriver()
        self.assertNotEqual(ucsdriver.ssl, ucs_ssl)

        network_driver._import_ucsmsdk()
        self.assertEqual(ucsdriver.ssl, ucs_ssl)

    @mock.patch.object(ucsdriver.socket, "create_connection")
    def test_ucsmsdk_default_behaviour_of_ssl_cert_checking(self,
                                                            mocked_socket):
        mocked_socket.side_effect = lambda *_: socket.socket()

        # First connection method
        tls_context = ucsdriver.TLSConnection('127.0.0.1', port=7777)
        tls_context.connect()

        self.assertEqual(tls_context.sock.context.verify_mode, ssl.CERT_NONE)
        tls_context.close()

        # Second connection method
        tls1_context = ucsdriver.TLS1Connection('127.0.0.1', port=7777)
        tls1_context.connect()

        self.assertEqual(tls1_context.sock.context.verify_mode, ssl.CERT_NONE)
        tls1_context.close()
