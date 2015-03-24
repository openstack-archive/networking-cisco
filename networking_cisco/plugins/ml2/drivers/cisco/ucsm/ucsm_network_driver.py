# Copyright 2015 Cisco Systems, Inc.
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import six

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils
from neutron.i18n import _LE, _LI
from neutron.extensions import portbindings

from networking_cisco.plugins.ml2.drivers.cisco.ucsm import config as config
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import constants as const
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import exceptions as cexc

LOG = logging.getLogger(__name__)


class CiscoUcsmDriver(object):

    """UCS Manager Driver Main Class."""

    def __init__(self):
        LOG.debug("UCS Manager Network driver found")
        self.ucsmsdk = None
        self.ucsm_ip = cfg.CONF.ml2_cisco_ucsm.ucsm_ip
        self.username = cfg.CONF.ml2_cisco_ucsm.ucsm_username
        self.password = cfg.CONF.ml2_cisco_ucsm.ucsm_password
        LOG.debug("UCS Manager Network driver Ip: %s", self.ucsm_ip)

        self.supported_sriov_vnic_types = [portbindings.VNIC_DIRECT,
                                           portbindings.VNIC_MACVTAP]
        self.supported_pci_devs = config.parse_pci_vendor_config()
        self.ucsm_host_dict = config.parse_ucsm_host_config()

    def _validate_config(self):
        if not cfg.CONF.ml2_cisco_ucsm.get('ucsm_ip'):
            msg = _('UCS Manager IP address is not provided')
            LOG.error(msg)
        if not cfg.CONF.ml2_cisco_ucsm.get('ucsm_username'):
            msg = _('UCS Manager username is not provided')
            LOG.error(msg)
        if not cfg.CONF.ml2_cisco_ucsm.get('ucsm_password'):
            msg = _('UCS Manager password is not provided')
            LOG.error(msg)

    def check_vnic_type_and_vendor_info(self, vnic_type, profile):
        """Checks if this vnic_type and vendor device info are supported.

        Returns True if:
        1. the port vnic_type is direct or macvtap and
        2. the vendor_id and product_id of the port is supported by
        this MD
        Useful in determining if this MD should bind the current
        port.
        """
        # Check for vnic_type
        if vnic_type not in self.supported_sriov_vnic_types:
            LOG.info(_LI('Non SR-IOV vnic_type: %s.'), vnic_type)
            return False

        if not profile:
            LOG.debug("Port binding missing profile info")
            return False

        # Check for vendor_info
        return self._check_for_supported_vendor(profile)

    def _check_for_supported_vendor(self, profile):
        """Checks if the port belongs to a supported vendor.

        Returns True for supported_pci_devs.
        """
        vendor_info = profile.get('pci_vendor_info')
        if not vendor_info:
            LOG.debug("Port binding missing pci vendor info")
            return False
        if vendor_info not in self.supported_pci_devs:
            LOG.debug("Unsupported vendor and product type %s",
                      str(vendor_info))
            return False
        return True

    def is_vmfex_port(self, profile):
        """Checks if the port is a VMFEX port.

        Returns True only for port that support VM-FEX.
        It is important to distinguish between the two since Port Profiles
        on the UCS Manager are created only for the VM-FEX ports.
        """
        vendor_info = profile.get('pci_vendor_info')

        return vendor_info == const.PCI_INFO_CISCO_VIC_1240

    def _import_ucsmsdk(self):
        """Imports the Ucsm SDK module.

        This module is not installed as part of the normal Neutron
        distributions. It is imported dynamically in this module so that
        the import can be mocked, allowing unit testing without requiring
        the installation of UcsSdk.

        """
        return importutils.import_module('UcsSdk')

    def ucs_manager_connect(self):
        """Connects to a UCS Manager."""
        self._validate_config()

        if not self.ucsmsdk:
            self.ucsmsdk = self._import_ucsmsdk()

        handle = self.ucsmsdk.UcsHandle()
        try:
            handle.Login(self.ucsm_ip, self.username, self.password)
        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConnectFailed(ucsm_ip=self.ucsm_ip, exc=e)

        return handle

    def _get_all_portprofiles(self, handle):
        """Gets all port profiles from a specific UCS Manager."""

        # Get Managed Object VnicProfile
        try:
            port_profiles = handle.GetManagedObject(
                None,
                self.ucsmsdk.VnicProfile.ClassId())

        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigReadFailed(ucsm_ip=self.ucsm_ip, exc=e)
        return port_profiles

    def _create_vlanprofile(self, handle, vlan_id):
        """Creates VLAN profile to be assosiated with the Port Profile."""
        vlan_name = self.make_vlan_name(vlan_id)
        vlan_profile_dest = (const.VLAN_PATH + const.VLAN_PROFILE_PATH_PREFIX +
                             vlan_name)
        LOG.debug("Creating Vlan Profile: %s", vlan_name)

        try:
            vp1 = handle.GetManagedObject(
                None,
                self.ucsmsdk.FabricLanCloud.ClassId(),
                {self.ucsmsdk.FabricLanCloud.DN: const.VLAN_PATH})
            if not vp1:
                LOG.debug("UCS Manager network driver Vlan Profile "
                          "path at %s missing", const.VLAN_PATH)
                return False

            #Create a vlan profile with the given vlan_id
            vp2 = handle.AddManagedObject(
                vp1,
                self.ucsmsdk.FabricVlan.ClassId(),
                {self.ucsmsdk.FabricVlan.COMPRESSION_TYPE:
                 const.VLAN_COMPRESSION_TYPE,
                 self.ucsmsdk.FabricVlan.DN: vlan_profile_dest,
                 self.ucsmsdk.FabricVlan.SHARING: const.NONE,
                 self.ucsmsdk.FabricVlan.PUB_NW_NAME: "",
                 self.ucsmsdk.FabricVlan.ID: str(vlan_id),
                 self.ucsmsdk.FabricVlan.MCAST_POLICY_NAME: "",
                 self.ucsmsdk.FabricVlan.NAME: vlan_name,
                 self.ucsmsdk.FabricVlan.DEFAULT_NET: "no"})
            if not vp2:
                LOG.debug("UCS Manager network driver could not create Vlan "
                          "Profile %s", vlan_name)
                return False

            LOG.debug("UCS Manager network driver created Vlan Profile %s "
                      "at %s", vlan_name, vlan_profile_dest)
            return True

        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigFailed(config=vlan_name,
                                        ucsm_ip=self.ucsm_ip, exc=e)

    def _create_port_profile(self, handle, profile_name, vlan_id, vnic_type):
        """Creates a Port Profile on the UCS Manager.

        Significant parameters set in the port profile are:
        1. Port profile name - Should match what was set in vif_details
        2. High performance mode - For VM-FEX to be enabled/configured on
        the port using this port profile, this mode should be enabled.
        3. Vlan id - Vlan id used by traffic to and from the port.
        """
        port_profile_dest = (const.PORT_PROFILESETDN + const.VNIC_PATH_PREFIX +
                             profile_name)
        # Max ports that this port profile can be applied to
        max_ports = 64

        vlan_name = self.make_vlan_name(vlan_id)
        vlan_associate_path = (const.PORT_PROFILESETDN +
                               const.VNIC_PATH_PREFIX + profile_name +
                               const.VLAN_PATH_PREFIX + vlan_name)
        cl_profile_name = const.CLIENT_PROFILE_NAME_PREFIX + str(vlan_id)
        cl_profile_dest = (const.PORT_PROFILESETDN + const.VNIC_PATH_PREFIX +
                           profile_name + const.CLIENT_PROFILE_PATH_PREFIX +
                           cl_profile_name)

        # Check if direct or macvtap mode
        if vnic_type == portbindings.VNIC_DIRECT:
            port_mode = const.HIGH_PERF
        else:
            port_mode = const.NONE

        try:
            port_profile = handle.GetManagedObject(
                None,
                self.ucsmsdk.VnicProfileSet.ClassId(),
                {self.ucsmsdk.VnicProfileSet.DN: const.PORT_PROFILESETDN})

            if not port_profile:
                LOG.debug("UCS Manager network driver Port Profile path at "
                          "%s missing", const.PORT_PROFILESETDN)
                return False

            # Create a port profile on the UCS Manager
            p_profile = handle.AddManagedObject(
                port_profile,
                self.ucsmsdk.VnicProfile.ClassId(),
                {self.ucsmsdk.VnicProfile.NAME: profile_name,
                 self.ucsmsdk.VnicProfile.POLICY_OWNER: "local",
                 self.ucsmsdk.VnicProfile.NW_CTRL_POLICY_NAME: "",
                 self.ucsmsdk.VnicProfile.PIN_TO_GROUP_NAME: "",
                 self.ucsmsdk.VnicProfile.DN: port_profile_dest,
                 self.ucsmsdk.VnicProfile.DESCR: const.DESCR,
                 self.ucsmsdk.VnicProfile.QOS_POLICY_NAME: "",
                 self.ucsmsdk.VnicProfile.HOST_NW_IOPERF: port_mode,
                 self.ucsmsdk.VnicProfile.MAX_PORTS: max_ports})
            if not p_profile:
                LOG.debug("UCS Manager network driver could not create Port "
                          "Profile %s at %s", profile_name, port_profile_dest)
                return False

            LOG.debug("UCS Manager network driver associating Vlan Profile "
                      "with Port Profile at %s", vlan_associate_path)
            # Associate port profile with vlan profile
            mo = handle.AddManagedObject(
                p_profile,
                self.ucsmsdk.VnicEtherIf.ClassId(),
                {self.ucsmsdk.VnicEtherIf.DN: vlan_associate_path,
                 self.ucsmsdk.VnicEtherIf.NAME: vlan_name,
                 self.ucsmsdk.VnicEtherIf.DEFAULT_NET: "yes"}, True)
            if not mo:
                LOG.debug("UCS Manager network driver cannot associate Vlan "
                          "Profile %s to Port Profile %s", vlan_name,
                          profile_name)
                return False

            LOG.debug("UCS Manager network driver created Port Profile %s "
                      "at %s", profile_name, port_profile_dest)

            cl_profile = handle.AddManagedObject(
                p_profile,
                self.ucsmsdk.VmVnicProfCl.ClassId(),
                {self.ucsmsdk.VmVnicProfCl.ORG_PATH: ".*",
                 self.ucsmsdk.VmVnicProfCl.DN: cl_profile_dest,
                 self.ucsmsdk.VmVnicProfCl.NAME: cl_profile_name,
                 self.ucsmsdk.VmVnicProfCl.POLICY_OWNER: "local",
                 self.ucsmsdk.VmVnicProfCl.SW_NAME: ".*",
                 self.ucsmsdk.VmVnicProfCl.DC_NAME: ".*",
                 self.ucsmsdk.VmVnicProfCl.DESCR: const.DESCR})
            if not cl_profile:
                LOG.debug("UCS Manager network driver could not create Client "
                          "Profile %s at %s", cl_profile_name, cl_profile_dest)
                return False

            LOG.debug("UCS Manager network driver created Client Profile %s "
                      "at %s", cl_profile_name, cl_profile_dest)
            return True

        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigFailed(config=profile_name,
                                        ucsm_ip=self.ucsm_ip, exc=e)

    def create_portprofile(self, profile_name, vlan_id, vnic_type):
        """Top level method to create Port Profiles on the UCS Manager.

        Calls all the methods responsible for the individual tasks that
        ultimately result in the creation of the Port Profile on the UCS
        Manager.
        """
        # Connect to UCS Manager
        handle = self.ucs_manager_connect()
        if not handle:
            LOG.error(_LE('UCS Manager network driver failed to connect '
                          'to UCS Manager.'))
            return False

        try:
            handle.StartTransaction()
            # Create Vlan Profile
            if not self._create_vlanprofile(handle, vlan_id):
                LOG.error(_LE('UCS Manager network driver failed to create '
                              'Vlan Profile for vlan %s'), str(vlan_id))
                return False

            # Create Port Profile
            if not self._create_port_profile(handle, profile_name, vlan_id,
                                             vnic_type):
                LOG.error(_LE('UCS Manager network driver failed to create '
                              'Port Profile %s'), profile_name)
                return False
            handle.CompleteTransaction()

        except Exception as e:
            if const.DUPLICATE_EXCEPTION in str(e):
                LOG.debug("UCS Manager network driver found an entry that "
                          "already exists %s", profile_name)
            else:
                # Raise a Neutron exception. Include a description of
                # the original  exception.
                raise cexc.UcsmConfigFailed(config=profile_name,
                                            ucsm_ip=self.ucsm_ip, exc=e)

        finally:
            # Disconnect from UCS Manager
            self.ucs_manager_disconnect(handle)
            return True

    def _update_service_profile(self, handle, service_profile, vlan_id):
        service_profile_path = (const.SERVICE_PROFILE_PATH_PREFIX +
                                str(service_profile))
        eth0 = service_profile_path + const.ETH0
        eth1 = service_profile_path + const.ETH1
        eth_port_paths = [eth0, eth1]

        obj = handle.GetManagedObject(
            None,
            self.ucsmsdk.LsServer.ClassId(),
            {self.ucsmsdk.LsServer.DN: service_profile_path})

        if not obj:
            LOG.debug("UCS Manager network driver could not find Service "
                      "Profile %s", service_profile_path)
            return False

        for eth_port_path in eth_port_paths:
            eth = handle.GetManagedObject(
                obj, self.ucsmsdk.VnicEther.ClassId(),
                {self.ucsmsdk.VnicEther.DN: eth_port_path}, True)

            if eth:
                vlan_name = self.make_vlan_name(vlan_id)
                vlan_path = eth_port_path + const.VLAN_PATH_PREFIX + vlan_name

                eth_if = handle.AddManagedObject(eth,
                    self.ucsmsdk.VnicEtherIf.ClassId(),
                    {self.ucsmsdk.VnicEtherIf.DN: vlan_path,
                     self.ucsmsdk.VnicEtherIf.NAME: vlan_name,
                     self.ucsmsdk.VnicEtherIf.DEFAULT_NET: "no"}, True)

                if not eth_if:
                    LOG.debug("UCS Manager network driver could not update "
                              "Service Profile %s with %s", service_profile,
                              str(vlan_id))
                    return False
            else:
                LOG.debug("UCS Manager network driver did not find ethernet "
                          "port at %s", eth_port_path)
        return True

    def update_serviceprofile(self, host_id, vlan_id):
        service_profile = self.ucsm_host_dict[host_id]
        if service_profile:
            LOG.debug("UCS Manager network driver Service Profile : %s",
                service_profile)
        else:
            LOG.debug("UCS Manager network driver does not support Host_id %s",
                      str(host_id))
            return

        # Connect to UCS Manager
        handle = self.ucs_manager_connect()
        if not handle:
            LOG.error(_LE('UCS Manager network driver failed to connect '
                          'to UCS Manager.'))
            return False

        try:
            handle.StartTransaction()
            # Create Vlan Profile
            if not self._create_vlanprofile(handle, vlan_id):
                LOG.error(_LE('UCS Manager network driver failed to create '
                              'Vlan Profile for vlan %s'), str(vlan_id))
                return False

            # Update Service Profile
            if not self._update_service_profile(
                handle,
                service_profile,
                vlan_id):
                LOG.error(_LE('UCS Manager network driver failed to update '
                              'Service Profile %s'), service_profile)
                return False
            # Complete Transaction
            handle.CompleteTransaction()

        except Exception as e:
            if const.DUPLICATE_EXCEPTION in str(e):
                LOG.debug("UCS Manager network driver found an entry that "
                          "already exists %s", service_profile)
            else:
                # Raise a Neutron exception. Include a description of
                # the original  exception.
                raise cexc.UcsmConfigFailed(config=service_profile,
                                            ucsm_ip=self.ucsm_ip, exc=e)

        finally:
            # Disconnect from UCS Manager
            self.ucs_manager_disconnect(handle)

    def _delete_vlan_profile(self, handle, vlan_id):
        vlan_name = self.make_vlan_name(vlan_id)
        vlan_profile_dest = (const.VLAN_PATH + const.VLAN_PROFILE_PATH_PREFIX +
                             vlan_name)

        obj = handle.GetManagedObject(
            None,
            self.ucsmsdk.FabricVlan.ClassId(),
            {self.ucsmsdk.FabricVlan.DN: vlan_profile_dest})

        if obj:
            handle.RemoveManagedObject(obj)

        return True

    def _delete_port_profile(self, handle, port_profile):
        port_profile_dest = (const.PORT_PROFILESETDN + const.VNIC_PATH_PREFIX +
                             port_profile)

        # Find port profile on the UCS Manager
        p_profile = handle.GetManagedObject(
                None,
                self.ucsmsdk.VnicProfile.ClassId(),
                {self.ucsmsdk.VnicProfile.NAME: port_profile,
                 self.ucsmsdk.VnicProfile.DN: port_profile_dest})

        if not p_profile:
            LOG.debug("UCS Manager network driver did not find port profile "
                      "%s to delete", port_profile_dest)
            return

        handle.RemoveManagedObject(p_profile)
        return True

    def _remove_vlan_from_all_service_profiles(self, handle, vlan_id):
        service_profile_list = []
        for host_id, value in six.iteritems(self.ucsm_host_dict):
            if value:
                service_profile_list.append(value)

        if not service_profile_list:
            # Nothing to do
            return
        for service_profile in service_profile_list:
            service_profile_path = (const.SERVICE_PROFILE_PATH_PREFIX +
                                    service_profile)
            eth0 = service_profile_path + const.ETH0
            eth1 = service_profile_path + const.ETH1
            eth_port_paths = [eth0, eth1]

            # 1. From the Service Profile config, access the configuration for
            # its ports.
            # 2. Check if that Vlan has been configured on each of the ports
            # 3. If Vlan conifg found, remove it.
            obj = handle.GetManagedObject(
                    None,
                    self.ucsmsdk.LsServer.ClassId(),
                    {self.ucsmsdk.LsServer.DN: service_profile_path})

            if obj:
                # Check if this vlan_id has been configured on the ports
                # in this Service profile
                for eth_port_path in eth_port_paths:
                    eth = handle.GetManagedObject(
                        obj, self.ucsmsdk.VnicEther.ClassId(),
                        {self.ucsmsdk.VnicEther.DN: eth_port_path}, True)
                    if eth:
                        vlan_name = self.make_vlan_name(vlan_id)
                        vlan_path = eth_port_path + "/if-" + vlan_name
                        vlan = handle.GetManagedObject(eth,
                            self.ucsmsdk.VnicEtherIf.ClassId(),
                            {self.ucsmsdk.VnicEtherIf.DN: vlan_path})
                        if vlan:
                            # Found vlan config. Now remove it.
                            handle.RemoveManagedObject(vlan)
        return True

    def delete_all_config_for_vlan(self, vlan_id, port_profile):
        # Connect to UCS Manager
        handle = self.ucs_manager_connect()
        if not handle:
            LOG.error(_LE('UCS Manager network driver failed to connect '
                          'to UCS Manager.'))
            return False

        try:
            handle.StartTransaction()
            self._delete_port_profile(handle, port_profile)
            self._remove_vlan_from_all_service_profiles(handle, vlan_id)
            self._delete_vlan_profile(handle, vlan_id)

            # Complete Transaction
            handle.CompleteTransaction()

        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigFailed(config=vlan_id,
                                        ucsm_ip=self.ucsm_ip, exc=e)

        finally:
            # Disconnect from UCS Manager
            self.ucs_manager_disconnect(handle)

    def ucs_manager_disconnect(self, handle):
        """Disconnects from the UCS Manager.

        After the disconnect, the handle associated with this connection
        is no longer valid.
        """
        try:
            handle.Logout()
        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmDisconnectFailed(ucsm_ip=self.ucsm_ip, exc=e)

    @staticmethod
    def make_vlan_name(vlan_id):
        return const.VLAN_PROFILE_NAME_PREFIX + str(vlan_id)
