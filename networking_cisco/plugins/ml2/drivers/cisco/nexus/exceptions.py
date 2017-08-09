# Copyright (c) 2013-2016 Cisco Systems, Inc.
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

"""Exceptions used by Cisco Nexus ML2 mechanism driver."""

from neutron_lib import exceptions

from networking_cisco._i18n import _


class NexusCredentialNotFound(exceptions.NeutronException):
    """Credential for this switch_ip cannot be found."""
    message = _("Credential for switch %(switch_ip)s could not be found.")


class CredentialNotFound(exceptions.NeutronException):
    """Credential with this ID cannot be found."""
    message = _("Credential %(credential_id)s could not be found.")


class CredentialNameNotFound(exceptions.NeutronException):
    """Credential Name could not be found."""
    message = _("Credential %(credential_name)s could not be found.")


class CredentialAlreadyExists(exceptions.NeutronException):
    """Credential name already exists."""
    message = _("Credential %(credential_name)s already exists "
                "for tenant %(tenant_id)s.")


class NexusConnectFailed(exceptions.NeutronException):
    """Failed to connect to Nexus switch."""
    message = _("Unable to connect to Nexus %(nexus_host)s. Reason: %(exc)s.")


class NexusConfigFailed(exceptions.NeutronException):
    """Failed to configure Nexus switch."""
    message = _("Failed to configure Nexus switch: %(nexus_host)s "
                "Config: %(config)s. Reason: %(exc)s.")


class NexusPortBindingNotFound(exceptions.NeutronException):
    """NexusPort Binding is not present."""
    message = _("Nexus Port Binding (%(filters)s) is not present")

    def __init__(self, **kwargs):
        filters = ','.join('%s=%s' % i for i in kwargs.items())
        super(NexusPortBindingNotFound, self).__init__(filters=filters)


class NexusHostMappingNotFound(exceptions.NeutronException):
    """NexusHost Mapping is not present."""
    message = _("Nexus Host Mapping (%(filters)s) is not present")

    def __init__(self, **kwargs):
        filters = ','.join('%s=%s' % i for i in kwargs.items())
        super(NexusHostMappingNotFound, self).__init__(filters=filters)


class NexusVPCAllocNotFound(exceptions.NeutronException):
    """Nexus VPC alloc is not present."""
    message = _("Nexus VPC Alloc (%(filters)s) is not present.")

    def __init__(self, **kwargs):
        filters = ','.join('%s=%s' % i for i in kwargs.items())
        super(NexusVPCAllocNotFound, self).__init__(filters=filters)


class NexusVPCAllocFailure(exceptions.NeutronException):
    """Nexus VPC alloc Failure."""
    message = _("Unable to allocate vpcid for all switches (%s).")

    def __init__(self, **kwargs):
        filters = ','.join('%s=%s' % i for i in kwargs.items())
        super(NexusVPCAllocFailure, self).__init__(filters=filters)


class NexusVPCAllocIncorrectArgCount(exceptions.NeutronException):
    """Nexus VPC alloc args count incorrect."""
    message = _("Nexus VPC Alloc init failed. "
                "Expected 2 args for start,end "
                "received %(count)d), content %(content)s.")


class NexusVPCLearnedNotConsistent(exceptions.NeutronException):
    """Learned Channel group not consistent on interface set in switches."""
    message = _("Learned Nexus channel group not consistent on "
                "this interface set: first interface %(first)s, "
                "second interface %(second)s.  "
                "Check Nexus Config and make consistent.")


class NexusVPCExpectedNoChgrp(exceptions.NeutronException):
    """Allocated Channel group not consistent on interface set in switches."""
    message = _("Channel group state in baremetal interface set not "
                "consistent: first interface %(first)s, "
                "second interface %(second)s.  "
                "Check Nexus Config and make consistent.")


class NexusMissingRequiredFields(exceptions.NeutronException):
    """Missing required fields to configure nexus switch."""
    message = _("Missing required field(s) to configure nexus switch: "
                "%(fields)s")


class NoNexusSviSwitch(exceptions.NeutronException):
    """No usable nexus switch found."""
    message = _("No usable Nexus switch found to create SVI interface.")


class SubnetNotSpecified(exceptions.NeutronException):
    """Subnet id not specified."""
    message = _("No subnet_id specified for router gateway.")


class SubnetInterfacePresent(exceptions.NeutronException):
    """Subnet SVI interface already exists."""
    message = _("Subnet %(subnet_id)s has an interface on %(router_id)s.")


class PortIdForNexusSvi(exceptions.NeutronException):
        """Port Id specified for Nexus SVI."""
        message = _('Nexus hardware router gateway only uses Subnet Ids.')


class PhysnetNotConfigured(exceptions.NeutronException):
    """Variable 'physnet' is not configured."""
    message = _("Configuration variable 'physnet' is not configured "
                "for host_id %(host_id)s. Switch information found = "
                "%(host_connections)s")


class NoDynamicSegmentAllocated(exceptions.NeutronException):
    """VLAN dynamic segment not allocated."""
    message = _("VLAN dynamic segment not created for Nexus VXLAN overlay "
                "static segment. Network segment = %(network_segment)s "
                "physnet = %(physnet)s")
