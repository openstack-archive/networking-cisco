# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
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
netns - context manager for network namespaces
"""

import ctypes
import os
import resource
import subprocess

from oslo_log import log as logging

from networking_cisco._i18n import _LW

LOG = logging.getLogger(__name__)

_libc = ctypes.CDLL('libc.so.6')

NETNS_DIR = "/var/run/netns/"


class Namespace(object):
    def __init__(self, name):
        self.parent_fd = open("/proc/self/ns/net")
        self.parent_fileno = self.parent_fd.fileno()
        self.target_fd = open(NETNS_DIR + str(name))
        self.target_fileno = self.target_fd.fileno()

    def __enter__(self):
        _libc.setns(self.target_fileno, 0)

    def __exit__(self, type, value, tb):
        _libc.setns(self.parent_fileno, 0)
        try:
            self.target_fd.close()
        except Exception:
            LOG.warning(_LW("Failed to close target_fd: %s"), self.target_fd)
            pass
        self.parent_fd.close()


def nslist():
    return os.listdir(NETNS_DIR) if os.path.exists(NETNS_DIR) else []


def iflist(ignore=set()):
    interfaces = []
    for line in subprocess.check_output(['ip', 'addr', 'show']).splitlines():
        if not line.strip().startswith(b'inet '):
            continue
        words = line.split()
        name = words[-1]
        if name in ignore:
            continue
        addr, _, mask = words[1].partition(b'/')
        interfaces.append((name, addr, mask))
    return interfaces


def increase_ulimit(ulimit):
    resource.setrlimit(resource.RLIMIT_NOFILE, (ulimit, ulimit))
