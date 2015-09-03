# Copyright 2013 OpenStack Foundation
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

"""
Implements a Nexus-OS NETCONF over SSHv2 API Client
"""

import re

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from oslo_utils import importutils

from neutron.i18n import _LW

from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    config as conf)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    constants as const)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    exceptions as cexc)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (
    nexus_snippets as snipp)

LOG = logging.getLogger(__name__)


class CiscoNexusDriver(object):
    """Nexus Driver Main Class."""
    def __init__(self):
        self.ncclient = None
        self.nexus_switches = conf.ML2MechCiscoConfig.nexus_dict
        self.connections = {}
        self._close_ssh_session = True if (
            cfg.CONF.ml2_cisco.never_cache_ssh_connection or
            (cfg.CONF.rpc_workers + cfg.CONF.api_workers) >=
            const.MAX_NEXUS_SSH_SESSIONS) else False

    def _import_ncclient(self):
        """Import the NETCONF client (ncclient) module.

        The ncclient module is not installed as part of the normal Neutron
        distributions. It is imported dynamically in this module so that
        the import can be mocked, allowing unit testing without requiring
        the installation of ncclient.

        """
        return importutils.import_module('ncclient.manager')

    def _get_close_ssh_session(self):
        return self._close_ssh_session

    def _close_session(self, mgr, nexus_host):
        """Close the connection to the nexus switch."""
        if mgr:
            self.connections.pop(nexus_host, None)
            mgr.close_session()

    def _get_config(self, nexus_host, filter=''):
        """Get Nexus Host Configuration:

           :param nexus_host: IP address of switch
           :param filter: filter string in XML format

           :returns: Configuration requested in string format

           """

        # For loop added to handle stale ncclient handle after switch reboot.
        # If the attempt fails,
        #     close the session, save first exception
        #     loop back around
        #     try again
        #     then quit
        for retry_count in (1, 2):
            mgr = self.nxos_connect(nexus_host)
            try:
                data_xml = mgr.get(filter=('subtree', filter)).data_xml
            except Exception as e:
                try:
                    self._close_session(mgr, nexus_host)
                except Exception:
                    pass

                # if transaction is snipp.EXEC_GET_INVENTORY_SNIPPET,
                # don't retry since this is used as a ping to
                # validate connection and retry is already built
                # into replay code.
                if snipp.EXEC_GET_INVENTORY_SNIPPET == filter:
                    raise cexc.NexusConfigFailed(nexus_host=nexus_host,
                                                 config=filter,
                                                 exc=e)

                # if first try, save first exception and retry
                if retry_count == 1:
                    first_exc = e
                else:
                    raise cexc.NexusConfigFailed(nexus_host=nexus_host,
                                                 config=filter,
                                                 exc=first_exc)
            else:
                return data_xml

    def _edit_config(self, nexus_host, target='running', config='',
                     allowed_exc_strs=None, check_to_close_session=True):
        """Modify switch config for a target config type.

        :param nexus_host: IP address of switch to configure
        :param target: Target config type
        :param config: Configuration string in XML format
        :param allowed_exc_strs: Exceptions which have any of these strings
                                 as a subset of their exception message
                                 (str(exception)) can be ignored
        :param check_to_close_session: Set to False when configured to close
                                       the ssh session is not to be checked.

        :raises: NexusConfigFailed: if _edit_config() encountered an exception
                                    not containing one of allowed_exc_strs

        """
        if not allowed_exc_strs:
            allowed_exc_strs = []

        # For loop added to handle stale ncclient handle after switch reboot.
        # If the attempt fails and not an allowed exception,
        #     close the session, save first exception
        #     loop back around
        #     try again
        #     then quit
        for retry_count in (1, 2):
            mgr = self.nxos_connect(nexus_host)
            LOG.debug("NexusDriver edit config: %s", config)
            try:
                mgr.edit_config(target=target, config=config)
                break
            except Exception as e:
                for exc_str in allowed_exc_strs:
                    if exc_str in unicode(e):
                        return
                try:
                    self._close_session(mgr, nexus_host)
                except Exception:
                    pass
                if retry_count == 1:
                    first_exc = e
                else:
                    # Raise a Neutron exception. Include a description of
                    # the original ncclient exception.
                    raise cexc.NexusConfigFailed(nexus_host=nexus_host,
                                                 config=config,
                                                 exc=first_exc)

        # if configured, close the ncclient ssh session.
        if check_to_close_session and self._get_close_ssh_session():
            self._close_session(mgr, nexus_host)

    def nxos_connect(self, nexus_host):
        """Make SSH connection to the Nexus Switch."""
        if getattr(self.connections.get(nexus_host), 'connected', None):
            return self.connections[nexus_host]

        if not self.ncclient:
            self.ncclient = self._import_ncclient()
        nexus_ssh_port = int(self.nexus_switches[nexus_host, 'ssh_port'])
        nexus_user = self.nexus_switches[nexus_host, const.USERNAME]
        nexus_password = self.nexus_switches[nexus_host, const.PASSWORD]
        hostkey_verify = cfg.CONF.ml2_cisco.host_key_checks
        try:
            # With new ncclient version, we can pass device_params...
            man = self.ncclient.connect(host=nexus_host,
                                        port=nexus_ssh_port,
                                        username=nexus_user,
                                        password=nexus_password,
                                        hostkey_verify=hostkey_verify,
                                        device_params={"name": "nexus"})
        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original ncclient exception.
            raise cexc.NexusConnectFailed(nexus_host=nexus_host, exc=e)

        self.connections[nexus_host] = man
        return self.connections[nexus_host]

    def create_xml_snippet(self, customized_config):
        """Create XML snippet.

        Creates the Proper XML structure for the Nexus Switch Configuration.
        and also does 'copy run start' if configured to do so.  This
        latter command allows configuration to persist on the switch after
        reboot.
        """
        if conf.cfg.CONF.ml2_cisco.persistent_switch_config:
            customized_config += (snipp.EXEC_SAVE_CONF_SNIPPET)

        conf_xml_snippet = snipp.EXEC_CONF_SNIPPET % (customized_config)
        return conf_xml_snippet

    def get_interface_switch_trunk_allowed(self, nexus_host,
                                           intf_type, interface):
        """Given the nexus host and specific interface data, get the
           interface data from host and determine if
           'switchport trunk allowed vlan' is configured.

           :param nexus_host: IP address of Nexus switch
           :param intf_type:  String which specifies interface type.
                              example: ethernet
           :param interface:  String indicating which interface.
                              example: 1/19

           :returns False:     On error or when config CLI not present.
                    True:      When config CLI is present.
           """

        confstr = snipp.EXEC_GET_INTF_SNIPPET % (intf_type, interface)
        response = self._get_config(nexus_host, confstr)
        LOG.debug("GET call returned interface %(if_type)s %(interface)s "
            "config", {'if_type': intf_type, 'interface': interface})
        if response and re.search("switchport trunk allowed vlan", response):
            return True
        return False

    def get_version(self, nexus_host):
        """Given the nexus host, get the version data.

        :param nexus_host: IP address of Nexus switch

        :returns version number
        """

        confstr = snipp.EXEC_GET_VERSION_SNIPPET
        response = self._get_config(nexus_host, confstr)
        LOG.debug("GET call returned version")
        version = None
        if response:
            version = re.findall(
                "\<sys_ver_str\>([\x20-\x7e]+)\<\/sys_ver_str\>", response)
        return version

    def get_nexus_type(self, nexus_host):
        """Given the nexus host, get the type of Nexus switch.

        :param nexus_host: IP address of Nexus switch

        :returns Nexus type
        """

        confstr = snipp.EXEC_GET_INVENTORY_SNIPPET
        response = self._get_config(nexus_host, confstr)
        if response:
            nexus_type = re.findall(
                "\<[mod:]*desc\>\"*Nexus\s*(\d)\d+\s*[0-9A-Z]+\s*"
                "[cC]hassis\s*\"*\<\/[mod:]*desc\>",
                response)
            if len(nexus_type) > 0:
                LOG.debug("GET call returned Nexus type %d",
                    int(nexus_type[0]))
                return int(nexus_type[0])
        LOG.warn(_LW("GET call failed to return Nexus type"))
        return -1

    def create_vlan(self, nexus_host, vlanid, vlanname, vni):
        """Create a VLAN on a Nexus Switch.

        Creates a VLAN given the VLAN ID, name and possible VxLAN ID.
        """
        if vni:
            snippet = (snipp.CMD_VLAN_CONF_VNSEGMENT_SNIPPET %
                       (vlanid, vlanname, vni))
        else:
            snippet = snipp.CMD_VLAN_CONF_SNIPPET % (vlanid, vlanname)

        confstr = self.create_xml_snippet(snippet)

        LOG.debug("NexusDriver: ")

        self._edit_config(nexus_host, target='running', config=confstr,
                          allowed_exc_strs=["VLAN with the same name exists"],
                          check_to_close_session=False)

        # Enable VLAN active and no-shutdown states. Some versions of
        # Nexus switch do not allow state changes for the extended VLAN
        # range (1006-4094), but these errors can be ignored (default
        # values are appropriate).
        for snippet in [snipp.CMD_VLAN_ACTIVE_SNIPPET,
                        snipp.CMD_VLAN_NO_SHUTDOWN_SNIPPET]:
            try:
                check_to_close_session = False if (
                    snippet == snipp.CMD_VLAN_ACTIVE_SNIPPET) else True
                confstr = self.create_xml_snippet(snippet % vlanid)
                self._edit_config(
                    nexus_host,
                    target='running',
                    config=confstr,
                    allowed_exc_strs=["Can't modify state for extended",
                                      "Command is only allowed on VLAN"],
                    check_to_close_session=check_to_close_session)
            except cexc.NexusConfigFailed:
                with excutils.save_and_reraise_exception():
                    self.delete_vlan(nexus_host, vlanid)

    def delete_vlan(self, nexus_host, vlanid):
        """Delete a VLAN on Nexus Switch given the VLAN ID."""
        confstr = snipp.CMD_NO_VLAN_CONF_SNIPPET % vlanid
        confstr = self.create_xml_snippet(confstr)
        self._edit_config(nexus_host, target='running', config=confstr,
                          allowed_exc_strs=["None of the VLANs exist"])

    def build_intf_confstr(self, snippet, intf_type, interface, vlanid):
        """Build the VLAN config string xml snippet to be used."""
        confstr = snippet % (intf_type, interface, vlanid, intf_type)
        confstr = self.create_xml_snippet(confstr)
        return confstr

    def enable_vlan_on_trunk_int(self, nexus_host, vlanid, intf_type,
                                 interface):
        """Enable a VLAN on a trunk interface.

           :param nexus_host: IP address of Nexus switch
           :param vlanid:     Vlanid to add to interface
           :param intf_type:  String which specifies interface type.
                              example: ethernet
           :param interface:  String indicating which interface.
                              example: 1/19

           :returns None: if config was successfully
                    Exception object: See _edit_config for details
           """
        response = self.get_interface_switch_trunk_allowed(nexus_host,
            intf_type, interface)
        #
        # If 'switchport trunk allowed vlan' not configured on the
        # switch, configure the VLAN onto the interface without the
        # 'add' keyword to define initial vlan config; otherwise
        # include the 'add' keyword.
        #
        snippet = (snipp.CMD_INT_VLAN_SNIPPET if (response is False)
            else snipp.CMD_INT_VLAN_ADD_SNIPPET)
        confstr = self.build_intf_confstr(
            snippet=snippet,
            intf_type=intf_type,
            interface=interface,
            vlanid=vlanid
        )
        self._edit_config(nexus_host, target='running',
                          config=confstr)
        LOG.debug("Successfully added switchport trunk vlan %(vlanid)s "
            "on int %(if_type)s %(interface)s.",
            {'vlanid': vlanid, 'if_type': intf_type,
             'interface': interface})

    def disable_vlan_on_trunk_int(self, nexus_host, vlanid, intf_type,
                                  interface):
        """Disable a VLAN on a trunk interface."""
        confstr = (snipp.CMD_NO_VLAN_INT_SNIPPET %
                   (intf_type, interface, vlanid, intf_type))
        confstr = self.create_xml_snippet(confstr)
        self._edit_config(nexus_host, target='running', config=confstr)

    def create_and_trunk_vlan(self, nexus_host, vlan_id, vlan_name,
                              intf_type, nexus_port, vni):
        """Create VLAN and trunk it on the specified ports."""
        self.create_vlan(nexus_host, vlan_id, vlan_name, vni)
        LOG.debug("NexusDriver created VLAN: %s", vlan_id)
        if nexus_port:
            self.enable_vlan_on_trunk_int(nexus_host, vlan_id, intf_type,
                                          nexus_port)

    def create_vlan_svi(self, nexus_host, vlan_id, gateway_ip):
        """Create VLAN vn_segment."""
        confstr = snipp.CMD_VLAN_SVI_SNIPPET % (vlan_id, gateway_ip)
        confstr = self.create_xml_snippet(confstr)
        LOG.debug("NexusDriver: ")
        self._edit_config(nexus_host, target='running', config=confstr)

    def delete_vlan_svi(self, nexus_host, vlan_id):
        """Delete VLAN vn_segment."""
        confstr = snipp.CMD_NO_VLAN_SVI_SNIPPET % vlan_id
        confstr = self.create_xml_snippet(confstr)
        LOG.debug("NexusDriver: ")
        self._edit_config(nexus_host, target='running', config=confstr)

    def enable_vxlan_feature(self, nexus_host, nve_int_num, src_intf):
        """Enable VXLAN on the switch."""

        # Configure the "feature" commands and NVE interface
        # (without "member" subcommand configuration).
        # The Nexus 9K will not allow the "interface nve" configuration
        # until the "feature nv overlay" command is issued and installed.
        # To get around the N9K failing on the "interface nve" command
        # send the two XML snippets down separately.
        confstr = self.create_xml_snippet(snipp.CMD_FEATURE_VXLAN_SNIPPET)
        LOG.debug("NexusDriver: ")
        self._edit_config(nexus_host, config=confstr)

        confstr = self.create_xml_snippet((snipp.CMD_INT_NVE_SNIPPET %
                                           (nve_int_num, src_intf)))
        LOG.debug("NexusDriver: ")
        self._edit_config(nexus_host, config=confstr)

    def disable_vxlan_feature(self, nexus_host):
        """Disable VXLAN on the switch."""

        # Removing the "feature" commands also removes the  NVE interface.
        confstr = self.create_xml_snippet(snipp.CMD_NO_FEATURE_VXLAN_SNIPPET)
        LOG.debug("NexusDriver: ")
        self._edit_config(nexus_host, config=confstr)

    def create_nve_member(self, nexus_host, nve_int_num, vni, mcast_group):
        """Add a member configuration to the NVE interface."""
        confstr = self.create_xml_snippet((snipp.CMD_INT_NVE_MEMBER_SNIPPET %
                                           (nve_int_num, vni, mcast_group)))
        LOG.debug("NexusDriver: ")
        self._edit_config(nexus_host, config=confstr)

    def delete_nve_member(self, nexus_host, nve_int_num, vni):
        """Delete a member configuration on the NVE interface."""
        confstr = self.create_xml_snippet((snipp.CMD_INT_NVE_NO_MEMBER_SNIPPET
                                           % (nve_int_num, vni)))
        LOG.debug("NexusDriver: ")
        self._edit_config(nexus_host, config=confstr)
