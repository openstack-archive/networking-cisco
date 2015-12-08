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

"""Exceptions by Cisco Configuration Agent."""

from networking_cisco._i18n import _

from neutron.common import exceptions


class DriverException(exceptions.NeutronException):
    """Exception created by the Driver class."""


class DriverExpectedKeyNotSetException(DriverException):
    """An attribute expected to be set by plugin is missing"""
    message = (_("Value for expected key: %(key)s is missing."
                 "Driver cannot proceed"))


class InitializationException(DriverException):
    """Exception when initialization of Routing Driver object."""
    message = (_("Critical device parameter missing. Failed initializing "
                 "routing driver object."))


class ConnectionException(DriverException):
    """Connection exception when connecting to IOS XE hosting device."""
    message = (_("Failed connecting to Device. Reason: %(reason)s. "
                 "Connection params are User:%(user)s, Host:%(host)s, "
                 "Port:%(port)s, Device timeout:%(timeout)s."))


class CSR1kvConfigException(DriverException):
    """Configuration exception thrown when modifying the running config."""
    message = (_("Error executing snippet:%(snippet)s. "
                 "Hosting device:%(dev_id)s Mgmt IP:%(ip)s "
                 "ErrorType:%(type)s ErrorTag:%(tag)s Config string:%("
                 "confstr)s."))


class CSR1kvMissingInterfaceException(DriverException):
    """Configuration exception thrown when modifying the running config."""
    message = (_("Interface corresponding to port:%(id)s and mac-address:%("
                 "mac)s is missing in the CSR. Cannot proceed with interface"
                 "config."))


class CSR1kvUnknownValueException(DriverException):
    """CSR1kv Exception thrown when an unknown value is received."""
    message = (_("Data in attribute: %(attribute)s does not correspond to "
                 "expected value. Value received is %(value)s. "))


class DriverNotExist(DriverException):
    message = _("Driver %(driver)s does not exist.")


class DriverNotFound(DriverException):
    message = _("Driver not found for %(resource)s id:%(id)s.")


class DriverNotSetForMissingParameter(DriverException):
    message = _("Driver cannot be set for missing parameter:%(p)s.")


class HAParamsMissingException(DriverException):
    """MissingParams exception thrown when HA params are missing"""
    message = (_("For router: %(r_id)s and port: %(p_id)s, HA_ENABLED is set, "
                 "but port ha info is missing. Port details: %(port)s"))
