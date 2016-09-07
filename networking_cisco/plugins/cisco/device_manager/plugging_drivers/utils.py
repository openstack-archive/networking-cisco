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


from functools import wraps
import time

from oslo_log import log as logging

from networking_cisco import backwards_compatibility as bc_attr

LOG = logging.getLogger(__name__)


MAX_ATTEMPTS = 4
SECONDS_BETWEEN_ATTEMPTS = 3
BACKOFF_MULTIPLIER = 2


def retry(ExceptionToCheck, tries=MAX_ATTEMPTS, delay=SECONDS_BETWEEN_ATTEMPTS,
          backoff=BACKOFF_MULTIPLIER):
    """Retry calling the decorated function using an exponential backoff.
    Reference: http://www.saltycrane.com/blog/2009/11/trying-out-retry
    -decorator-python/
    :param ExceptionToCheck: the exception to check. may be a tuple of
        exceptions to check
    :param tries: number of times to try (not retry) before giving up
    :param delay: initial delay between retries in seconds
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    """

    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    LOG.debug("%(ex)s. Retrying in %(sec)d seconds.",
                              {'ex': str(e), 'sec': mdelay})
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


class PluggingDriverUtilsMixin(object):

    def _mgmt_subnet_spec(self, context, mgmt_context):
        ip_addr = mgmt_context.get('mgmt_ip_address',
                                   bc_attr.ATTR_NOT_SPECIFIED)
        if ip_addr and ip_addr != bc_attr.ATTR_NOT_SPECIFIED:
            nw = self._core_plugin.get_network(context,
                                               mgmt_context['mgmt_nw_id'])
            ips = [{'ip_address': ip_addr, 'subnet_id': nw['subnets'][0]}]
        else:
            ips = bc_attr.ATTR_NOT_SPECIFIED
        return ips
