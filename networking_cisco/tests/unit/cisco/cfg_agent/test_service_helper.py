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

import mock

from networking_cisco.plugins.cisco.cfg_agent.service_helpers import (
    service_helper)
from neutron.tests import base


fake_q_name = 'fake_q_name'
fake_data = 'fake_data'


class FakeServiceHelper(service_helper.ServiceHelperBase):

    def __init__(self):
        super(FakeServiceHelper, self).__init__()

    def process_service(self, device_ids=None, removed_devices_info=None):
        pass


class TestServiceHelperBase(base.BaseTestCase):

    def setUp(self):
        super(TestServiceHelperBase, self).setUp()
        self.svc_helper = FakeServiceHelper()
        self.observer = FakeServiceHelper()

    def test_register(self):
        self.svc_helper._observers = []
        self.svc_helper.register(self.observer)
        self.assertEqual([self.observer], self.svc_helper._observers)

    def test_test_register_err(self):
        self.svc_helper._observers = [self.observer]
        self.assertRaises(ValueError,
                          self.svc_helper.register, self.observer)

    def test_unregister(self):
        self.svc_helper._observers = [self.observer]
        self.svc_helper.unregister(self.observer)
        self.assertEqual([], self.svc_helper._observers)

    def test_unregister_err(self):
        self.svc_helper._observers = []
        self.assertRaises(ValueError,
                          self.svc_helper.unregister, self.observer)

    def test_notify(self):
        self.observer.update = mock.Mock()
        self.svc_helper._observers = [self.observer]
        self.svc_helper.notify(resource=None)
        self.observer.update.assert_called_once_with(None)


class TestQueueMixin(base.BaseTestCase):

    def setUp(self):
        super(TestQueueMixin, self).setUp()

    def test_enqueue_dequeue(self):
        queue_mixin = service_helper.QueueMixin()
        queue_mixin.enqueue(fake_q_name, fake_data)
        self.assertTrue(fake_q_name in queue_mixin._queues)
        self.assertEqual(fake_data, queue_mixin.dequeue(fake_q_name))
        self.assertEqual(None, queue_mixin.dequeue(fake_q_name))

    def test_dequeue_err(self):
        queue_mixin = service_helper.QueueMixin()
        self.assertRaises(ValueError, queue_mixin.dequeue, fake_q_name)

    def test_qsize(self):
        queue_mixin = service_helper.QueueMixin()
        queue_mixin.enqueue(fake_q_name, fake_data)
        self.assertEqual(1, queue_mixin.qsize(fake_q_name))

    def test_qsize_err(self):
        queue_mixin = service_helper.QueueMixin()
        self.assertRaises(ValueError, queue_mixin.qsize, fake_q_name)
