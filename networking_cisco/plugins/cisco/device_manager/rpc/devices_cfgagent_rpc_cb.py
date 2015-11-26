# Copyright 2014 Cisco Systems, Inc.  All rights reserved.
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

import oslo_messaging
import six

from networking_cisco.plugins.cisco.common import cisco_constants as const


class DeviceMgrCfgRpcCallback(object):
    """Cisco cfg agent rpc support in Device mgr service plugin."""

    target = oslo_messaging.Target(version='1.1')

    def __init__(self, plugin):
        self._dmplugin = plugin

    def report_non_responding_hosting_devices(self, context, host,
                                              hosting_device_ids):
        """Report that a hosting device is determined to be dead.

        @param: context - contains user information
        @param: host - originator of callback
        @param: hosting_device_ids - list of non-responding hosting devices
        @return: -
        """
        # let the generic status update callback function handle this callback
        self.update_hosting_device_status(context, host,
                                          {const.HD_DEAD: hosting_device_ids})

    def register_for_duty(self, context, host):
        """Report that Cisco cfg agent is ready for duty.

        This function is supposed to be called when the agent has started,
        is ready to take on assignments and before any callbacks to fetch
        logical resources are issued.

        @param: context - contains user information
        @param: host - originator of callback
        @return: True if successfully registered, False if not successfully
                 registered, None if no handler found
                 If unsuccessful the agent should retry registration a few
                 seconds later
        """
        # schedule any non-handled hosting devices
        return self._dmplugin.auto_schedule_hosting_devices(context, host)

    # version 1.1
    def update_hosting_device_status(self, context, host, status_info):
        """Report status changes for hosting devices.

        @param: context - contains user information
        @param: host - originator of callback
        @param: status_info - Dictionary with list of hosting device ids
                              for each type of hosting device status to be
                              updated, i.e.,
              dict {HD_ACTIVE: list_of_ids_of_active_hds,
                    HD_NOT_RESPONDING: list_of_ids_of_not_responding_hds,
                    HD_DEAD: list_of_ids_of_dead_hds,
                    ...}
        @return: -
        """
        for status, hd_ids in six.iteritems(status_info):
            # update hosting device entry in db to new status
            hd_spec = {'hosting_device': {'status': status}}
            for hd_id in hd_ids:
                self._dmplugin.update_hosting_device(context, hd_id, hd_spec)
            if status == const.HD_DEAD or status == const.HD_ERROR:
                self._dmplugin.handle_non_responding_hosting_devices(
                    context, host, hd_ids)
            # For status == const.HD_NOT_RESPONDING we do nothing more here as
            # we'll later act on the dead or faulty status change.
            # For status == const.HD_ACTIVE the change in status to active will
            # make the router scheduler consider the now active hosting devices
            # and that is enough so we do nothing more here.
