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

import abc
import six

from oslo_log import log as logging

from networking_cisco._i18n import _

from six.moves import queue as Queue

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class ServiceHelperBase(object):

    def __init__(self):
        self._observers = []

    def register(self, observer):
        LOG.debug("Attaching observer: %(ob)s to subject: %(sub)s",
                  {'ob': observer.__class__.__name__,
                   'sub': self.__class__.__name__})
        if observer not in self._observers:
            self._observers.append(observer)
        else:
            raise ValueError(_("Observer: %(ob)s is already registered to "
                             "subject: %(sub)s"),
                             {'ob': observer.__class__.__name__,
                              'sub': self.__class__.__name__})

    def unregister(self, observer):
        LOG.debug("Dettaching observer: %(ob)s from subject: %(sub)s",
                  {'ob': observer.__class__.__name__,
                   'sub': self.__class__.__name__})
        if observer in self._observers:
            self._observers.remove(observer)
        else:
            raise ValueError(_("Observer: %(ob)s is not attached to "
                               "subject: %(sub)s"),
                             {'ob': observer.__class__.__name__,
                              'sub': self.__class__.__name__})

    def notify(self, resource, **kwargs):
        """Calls all observers attached to the given subject."""
        LOG.debug("Notifying all observers of this subject")
        for observer in self._observers:
            LOG.debug("Notifying observer: %s", observer.__class__.__name__)
            observer.update(resource, **kwargs)

    def update(self, resource, **kwargs):
        """For future support."""
        LOG.debug("Update received")

    @abc.abstractmethod
    def process_service(self, *args, **kwargs):
        raise NotImplementedError


class QueueMixin(object):
    def __init__(self):
        super(QueueMixin, self).__init__()
        self._queues = {}

    def enqueue(self, qname, data):
        if qname not in self._queues:
            self._queues[qname] = Queue.Queue()
        queue = self._queues[qname]
        queue.put(data)

    def dequeue(self, qname):
        if qname not in self._queues:
            raise ValueError(_("queue %s is not defined"), qname)
        try:
            return self._queues[qname].get(block=False)
        except Queue.Empty:
            return None

    def qsize(self, qname):
        """Return the approximate size of the queue."""
        if qname in self._queues:
            return self._queues[qname].qsize()
        else:
            raise ValueError(_("queue %s is not defined"), qname)
