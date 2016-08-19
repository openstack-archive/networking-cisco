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


import datetime
import os
import six
import socket
import struct
import sys
import threading
from threading import Lock
import time
import traceback
import uuid


TIME_FORMAT = '%a %b %d %H:%M:%S %Y'


class PeriodicTask(object):

    """Periodic task"""

    def __init__(self, interval, func, **kwargs):
        self._interval = interval
        self._fn = func
        self._kwargs = kwargs
        self.stop_flag = False
        self._excq = kwargs.get('excq')

    def run(self):
        try:
            if self.stop_flag:
                return
            start = time.time()
            self._fn(**self._kwargs)
            end = time.time()
            delta = end - start
            self.thrd = threading.Timer(self._interval - delta, self.run)
            self.thrd.start()
        except Exception as e:
            if self._excq:
                emsg = ('%(name)s : %(excp)s' % {'name': self._fn.__name__,
                                                 'excp': str(e)})
                self._excq.put(emsg, block=False)

    def stop(self):
        try:
            self.thrd.cancel()
            self.stop_flag = True
        except Exception as e:
            if self._excq:
                emsg = ('Exception in timer stop %s' % str(e))
                self._excq.put(emsg, block=False)


class EventProcessingThread(threading.Thread):

    """Event processing thread."""

    def __init__(self, name, obj, task, excq=None):
        super(EventProcessingThread, self).__init__(name=name)
        self._thread_name = name
        self._hdlr = obj
        self._task = task
        self._excq = excq

    def run(self):
        try:
            getattr(self._hdlr, self._task)()
        except Exception:
            if self._excq:
                exc_type, exc_value, exc_tb = sys.exc_info()
                tbstr = traceback.format_exception(exc_type, exc_value, exc_tb)
                exstr = str(dict(name=self._thread_name, tb=tbstr))
                self._excq.put(exstr, block=False)

    @property
    def am_i_active(self):
        return self.isAlive()

    @property
    def name(self):
        return self._thread_name


class Dict2Obj(object):

    """Convert a dictionary to an object."""

    def __init__(self, d):
        for key, val in six.iteritems(d):
            # Check if it is nested dictionary
            if isinstance(val, dict):
                setattr(self, key, Dict2Obj(val))
            else:
                setattr(self, key, val)

    def __getattr__(self, val):
        return self.__dict__.get(val)


def get_uuid():
    return str(uuid.uuid4())


def lock():
    return Lock()


def utc_time(ct):
    if ct:
        return datetime.datetime.strptime(ct, TIME_FORMAT)


def utc_time_lapse(lapse):
    current_time = utc_time(time.ctime())
    hour_lapse = current_time - datetime.timedelta(hours=lapse)
    return hour_lapse


def is_valid_ipv4(addr):
    try:
        socket.inet_aton(addr)
        return True
    except socket.error:
        return False


def is_valid_mac(addr):
    """Check the syntax of a given mac address.

    The acceptable format is xx:xx:xx:xx:xx:xx
    """
    addrs = addr.split(':')
    if len(addrs) != 6:
        return False
    for m in addrs:
        try:
            if int(m, 16) > 255:
                return False
        except ValueError:
            return False
    return True


def make_cidr(gw, mask):
    """Create network address in CIDR format.

    Return network address for a given gateway address and netmask.
    """
    try:
        int_mask = (0xFFFFFFFF << (32 - int(mask))) & 0xFFFFFFFF
        gw_addr_int = struct.unpack('>L', socket.inet_aton(gw))[0] & int_mask
        return (socket.inet_ntoa(struct.pack("!I", gw_addr_int)) +
                '/' + str(mask))
    except (socket.error, struct.error, ValueError, TypeError):
        return


def find_agent_host_id(this_host):
    """Returns the neutron agent host id for RHEL-OSP6 HA setup."""

    host_id = this_host
    try:
        for root, dirs, files in os.walk('/run/resource-agents'):
            for fi in files:
                if 'neutron-scale-' in fi:
                    host_id = 'neutron-n-' + fi.split('-')[2]
                    break
        return host_id
    except IndexError:
        return host_id
