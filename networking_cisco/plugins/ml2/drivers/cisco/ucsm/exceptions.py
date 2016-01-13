# Copyright 2015 Cisco Systems, Inc.
# All rights reserved.
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

"""Exceptions used by Cisco UCSM ML2 mechanism driver."""

from networking_cisco._i18n import _

from neutron.common import exceptions


class UcsmConnectFailed(exceptions.NeutronException):
    message = _("Unable to connect to UCS Manager %(ucsm_ip)s. "
                "Reason: %(exc)s.")


class UcsmConfigReadFailed(exceptions.NeutronException):
    message = _("Unable to read config from UCS Manager %(ucsm_ip)s. "
                "Reason: %(exc)s.")


class UcsmConfigFailed(exceptions.NeutronException):
    message = _("Failed to configure %(config)s on UCS Manager %(ucsm_ip)s. "
                "Reason: %(exc)s.")


class UcsmConfigDeleteFailed(exceptions.NeutronException):
    message = _("Failed to delete %(config)s on UCS Manager %(ucsm_ip)s. "
                "Reason: %(exc)s.")


class UcsmDisconnectFailed(exceptions.NeutronException):
    message = _("Disconnect to UCS Manager %(ucsm_ip)s failed. "
                "Reason: %(exc)s.")
