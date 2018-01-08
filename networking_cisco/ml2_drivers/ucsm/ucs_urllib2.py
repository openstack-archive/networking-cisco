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
import urllib2
from urllib2 import *  # noqa

from oslo_config import cfg


def build_opener(*handlers):
    if not cfg.CONF.ml2_cisco_ucsm.ucsm_https_verify:
        # SSL certificate checking has been turned off. Try to create
        # a default context.
        try:
            ctx = ssl.create_default_context()
        except Exception:
            # Python version does not support creation of default
            # context. In that case, proceed with the regular
            # build_opener.
            return urllib2.build_opener(*handlers)
        else:
            # Update successfully created context to ignore
            # SSL certificates on this HTTPS connection.
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return urllib2.build_opener(urllib2.HTTPSHandler(context=ctx),
                *handlers)
    else:
        # SSL certificate checking has not be turned off. Continue
        # using the unmodified build_opener().
        return urllib2.build_opener(*handlers)
