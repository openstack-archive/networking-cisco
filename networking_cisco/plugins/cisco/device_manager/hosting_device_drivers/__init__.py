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

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class HostingDeviceDriver(object):
    """This class defines the API for hosting device drivers.

    These are used by Cisco (routing service) plugin to perform
    various (plugin independent) operations on hosting devices.
    """

    @abc.abstractmethod
    def hosting_device_name(self):
        pass

    @abc.abstractmethod
    def create_config(self, context, credentials_info, connectivity_info):
        """Creates configuration(s) for a service VM.

        This function can be used to make initial configurations. The
        configuration(s) is/are injected in the VM's file system using
        Nova's configdrive feature.

        Called when a service VM-based hosting device is to be created.
        This function should cleanup after itself in case of error.

        @param context: contains user information
        @param credentials_info: dictionary with login credentials to be
        injected into the hosting device
                  {'user_name': <user name>,
                   'password': <password>}
        @param connectivity_info: dictionary with management connectivity
        information needed by hosting device to communicate
                {'mgmt_port': <neutron port for management>,
                 'gateway_ip': <gateway ip address of management subnet
                 'netmask': <netmask of management subnet>
                 'name_server_1: <ip of domain name server 1>,
                 'name_server_2: <ip of domain name server 2>}

        returns: Dict with file names and their corresponding content strings:
                 {filename1: content_string1, filename2: content_string2, ...}
                 The file system of the VM will contain files with the
                 specified file names and content. If the dict is empty no
                 config drive will be used.
        """
        pass
