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

"""Exceptions used by Cisco Nexus1000V ML2 mechanism driver."""

from networking_cisco._i18n import _

from neutron.common import exceptions


class VSMConnectionFailed(exceptions.ServiceUnavailable):
    """No response from Cisco Nexus1000V VSM."""
    message = _("Connection to VSM failed: %(reason)s.")


class VSMError(exceptions.NeutronException):
    """A response from Cisco Nexus1000V VSM was not HTTP OK."""
    message = _("Internal VSM Error: %(reason)s.")


class NetworkBindingNotFound(exceptions.NotFound):
    """Network Binding for network cannot be found."""
    message = _("Network Binding for network %(network_id)s could "
                "not be found.")


class PortBindingNotFound(exceptions.NotFound):
    """Port Binding for port cannot be found."""
    message = _("Port Binding for port %(port_id)s could "
                "not be found.")


class NetworkProfileNotFound(exceptions.NotFound):
    """Network Profile with given UUID/name/network-type cannot be found."""
    message = _("Network Profile %(profile)s could not be found.")


class PolicyProfileNotFound(exceptions.NotFound):
    """Policy Profile with given UUID/name cannot be found."""
    message = _("Policy Profile %(profile)s could not be found.")


class ProfileTenantBindingNotFound(exceptions.NotFound):
    """Profile to Tenant binding for given profile ID cannot be found."""
    message = _("Profile-Tenant binding for profile %(profile_id)s could "
                "not be found.")


class NetworkProfileInUse(exceptions.InUse):
    """Network Profile with the given UUID is in use."""
    message = _("One or more network segments belonging to network "
                "profile %(profile)s is in use.")


class ProfileDeletionNotSupported(exceptions.NeutronException):
    """Deletion of default network profile is not supported."""
    message = _("Deletion of default network profile %(profile)s "
                "is not supported.")
