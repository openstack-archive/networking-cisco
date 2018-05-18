# Copyright 2018 Cisco Systems, Inc.
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

import ssl
from ssl import *  # noqa

from oslo_config import cfg

CONF = cfg.CONF


# The ucsmsdk disables verification of ssl certificates by default. Override
# the SSLContext class to enable certificate checking if https_verify is set to
# True.
class SSLContext(ssl.SSLContext):
    def __init__(self, *args, **kwargs):
        super(SSLContext, self).__init__(*args, **kwargs)
        self.verify_mode = ssl.CERT_REQUIRED if (
            CONF.ml2_cisco_ucsm.ucsm_https_verify) else ssl.CERT_NONE


# Override wrap_socket function for when the ucsmsdk is using the
# TLS1Connection function
def wrap_socket(sock, keyfile=None, certfile=None,
                server_side=False, cert_reqs=ssl.CERT_NONE,
                ssl_version=ssl.PROTOCOL_SSLv23, ca_certs=None,
                do_handshake_on_connect=True,
                suppress_ragged_eofs=True,
                ciphers=None):
    cert_reqs = ssl.CERT_REQUIRED if (
            CONF.ml2_cisco_ucsm.ucsm_https_verify) else ssl.CERT_NONE
    return ssl.wrap_socket(sock=sock, keyfile=keyfile, certfile=certfile,
                     server_side=server_side, cert_reqs=cert_reqs,
                     ssl_version=ssl_version, ca_certs=ca_certs,
                     do_handshake_on_connect=do_handshake_on_connect,
                     suppress_ragged_eofs=suppress_ragged_eofs,
                     ciphers=ciphers)
