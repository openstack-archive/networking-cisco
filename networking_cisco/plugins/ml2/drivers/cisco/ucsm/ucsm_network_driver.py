# Copyright 2015-2016 Cisco Systems, Inc.
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

from contextlib import contextmanager
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils

from networking_cisco._i18n import _LE, _LI, _LW

from neutron.extensions import portbindings

from networking_cisco.plugins.ml2.drivers.cisco.ucsm import config
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import constants as const
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import exceptions as cexc

LOG = logging.getLogger(__name__)


class CiscoUcsmDriver(object):

    """UCS Manager Driver Main Class."""

    def __init__(self):
        LOG.debug("UCS Manager Network driver found")
        self.ucsmsdk = None
        self.supported_sriov_vnic_types = [portbindings.VNIC_DIRECT,
                                           portbindings.VNIC_MACVTAP]
        self.supported_pci_devs = config.parse_pci_vendor_config()
        self.ucsm_conf = config.UcsmConfig()
        self.ucsm_host_dict = {}
        self.ucsm_sp_dict = {}
        self._create_host_and_sp_dicts_from_config()

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
            return False

        # Check for vendor_info
        return self._check_for_supported_vendor(profile)

    def _check_for_supported_vendor(self, profile):
        """Checks if the port belongs to a supported vendor.

        Returns True for supported_pci_devs.
        """
        vendor_info = profile.get('pci_vendor_info')
        if not vendor_info:
            return False
        if vendor_info not in self.supported_pci_devs:
            return False
        return True

    def is_vmfex_port(self, profile):
        """Checks if the port is a VMFEX port.

        Returns True only for port that support VM-FEX.
        It is important to distinguish between the two since Port Profiles
        on the UCS Manager are created only for the VM-FEX ports.
        """
        return profile and (profile.get('pci_vendor_info')
            == const.PCI_INFO_CISCO_VIC_1240)

    def _import_ucsmsdk(self):
        """Imports the Ucsm SDK module.

        This module is not installed as part of the normal Neutron
        distributions. It is imported dynamically in this module so that
        the import can be mocked, allowing unit testing without requiring
        the installation of UcsSdk.

        """
        return importutils.import_module('UcsSdk')

    def _create_host_and_sp_dicts_from_config(self):
        # Check if Service Profile to Hostname mapping config has been provided
        if cfg.CONF.ml2_cisco_ucsm.ucsm_host_list:
            self.ucsm_sp_dict, self.ucsm_host_dict = (
                config.parse_ucsm_host_config())
        else:
            self._create_ucsm_host_to_service_profile_mapping()

    @contextmanager
    def ucsm_connect_disconnect(self, ucsm_ip):
        handle = self.ucs_manager_connect(ucsm_ip)
        try:
            yield handle
        finally:
            self.ucs_manager_disconnect(handle, ucsm_ip)

    def ucs_manager_connect(self, ucsm_ip):
        """Connects to a UCS Manager."""
        if not self.ucsmsdk:
            self.ucsmsdk = self._import_ucsmsdk()

        username, password = self.ucsm_conf.get_credentials_for_ucsm_ip(
            ucsm_ip)
        if not username:
            LOG.error(_LE('UCS Manager network driver failed to get login '
                          'credentials for UCSM %s'), ucsm_ip)
            return None

        handle = self.ucsmsdk.UcsHandle()
        try:
            handle.Login(ucsm_ip, username, password)
        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConnectFailed(ucsm_ip=ucsm_ip, exc=e)

        return handle

    def _get_server_name(self, handle, service_profile_mo, ucsm_ip):
        """Get the contents of the 'Name' field associated with UCS Server.

        When a valid connection hande to UCS Manager is handed in, the Name
        field associated with a UCS Server is returned.
        """
        try:
            resolved_dest = handle.ConfigResolveDn(service_profile_mo.PnDn)
            server_list = resolved_dest.OutConfig.GetChild()
            if not server_list:
                return ""
            return server_list[0].Name
        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigReadFailed(ucsm_ip=ucsm_ip, exc=e)

    def _create_ucsm_host_to_service_profile_mapping(self):
        """Reads list of Service profiles and finds associated Server."""
        ucsm_ips = self.ucsm_conf.get_all_ucsm_ips()
        for ucsm_ip in ucsm_ips:
            with self.ucsm_connect_disconnect(ucsm_ip) as handle:
                try:
                    sp_list_temp = handle.ConfigResolveClass('lsServer', None,
                        inHierarchical=False)
                    if sp_list_temp and sp_list_temp.OutConfigs is not None:
                        sp_list = sp_list_temp.OutConfigs.GetChild() or []
                        for sp in sp_list:
                            if sp.PnDn != "":
                                server_name = self._get_server_name(handle, sp,
                                    ucsm_ip)
                                if server_name != "":
                                    key = (ucsm_ip, server_name)
                                    self.ucsm_sp_dict[key] = str(sp.Dn)
                                    self.ucsm_host_dict[server_name] = ucsm_ip
                except Exception as e:
                    # Raise a Neutron exception. Include a description of
                    # the original  exception.
                    raise cexc.UcsmConfigReadFailed(ucsm_ip=ucsm_ip, exc=e)

    def get_ucsm_ip_for_host(self, host_id):
        ucsm_ip = self.ucsm_host_dict.get(host_id)
        if not ucsm_ip:
            ucsm_ip = self.ucsm_conf.get_ucsm_ip_for_sp_template_host(host_id)
        return ucsm_ip

    def _create_vlanprofile(self, handle, vlan_id, ucsm_ip):
        """Creates VLAN profile to be assosiated with the Port Profile."""
        vlan_name = self.make_vlan_name(vlan_id)
        vlan_profile_dest = (const.VLAN_PATH + const.VLAN_PROFILE_PATH_PREFIX +
                             vlan_name)

        try:
            handle.StartTransaction()
            vp1 = handle.GetManagedObject(
                None,
                self.ucsmsdk.FabricLanCloud.ClassId(),
                {self.ucsmsdk.FabricLanCloud.DN: const.VLAN_PATH})
            if not vp1:
                LOG.warning(_LW('UCS Manager network driver Vlan Profile '
                                'path at %s missing'), const.VLAN_PATH)
                return False

            # Create a vlan profile with the given vlan_id
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

            handle.CompleteTransaction()
            if vp2:
                LOG.debug('UCS Manager network driver Created Vlan '
                          'Profile %s at %s', vlan_name, vlan_profile_dest)
                return True

        except Exception as e:
            return self._handle_ucsm_exception(e, 'Vlan Profile',
                                               vlan_name, ucsm_ip)

    def _create_port_profile(self, handle, profile_name, vlan_id,
                             vnic_type, ucsm_ip, trunk_vlans, qos_policy):
        """Creates a Port Profile on the UCS Manager.

        Significant parameters set in the port profile are:
        1. Port profile name - Should match what was set in vif_details
        2. High performance mode - For VM-FEX to be enabled/configured on
        the port using this port profile, this mode should be enabled.
        3. Vlan id - Vlan id used by traffic to and from the port.
        """
        port_profile_dest = (const.PORT_PROFILESETDN + const.VNIC_PATH_PREFIX +
                             profile_name)

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
            handle.StartTransaction()
            port_profile = handle.GetManagedObject(
                None,
                self.ucsmsdk.VnicProfileSet.ClassId(),
                {self.ucsmsdk.VnicProfileSet.DN: const.PORT_PROFILESETDN})

            if not port_profile:
                LOG.warning(_LW('UCS Manager network driver Port Profile '
                                'path at %s missing'),
                    const.PORT_PROFILESETDN)
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
                 self.ucsmsdk.VnicProfile.QOS_POLICY_NAME: qos_policy,
                 self.ucsmsdk.VnicProfile.HOST_NW_IOPERF: port_mode,
                 self.ucsmsdk.VnicProfile.MAX_PORTS: const.MAX_PORTS})
            if not p_profile:
                LOG.warning(_LW('UCS Manager network driver could not '
                                'create Port Profile %s.'), profile_name)
                return False

            LOG.debug('UCS Manager network driver associating Vlan '
                      'Profile with Port Profile at %s',
                vlan_associate_path)
            # Associate port profile with vlan profile
            mo = handle.AddManagedObject(
                p_profile,
                self.ucsmsdk.VnicEtherIf.ClassId(),
                {self.ucsmsdk.VnicEtherIf.DN: vlan_associate_path,
                 self.ucsmsdk.VnicEtherIf.NAME: vlan_name,
                 self.ucsmsdk.VnicEtherIf.DEFAULT_NET: "yes"}, True)
            if not mo:
                LOG.warning(_LW('UCS Manager network driver cannot '
                                'associate Vlan Profile to Port '
                                'Profile %s'), profile_name)
                return False
            LOG.debug('UCS Manager network driver created Port Profile %s '
                      'at %s', profile_name, port_profile_dest)

            # For Multi VLAN trunk support
            if trunk_vlans:
                for vlan in trunk_vlans:
                    vlan_name = self.make_vlan_name(vlan)
                    vlan_associate_path = (const.PORT_PROFILESETDN +
                        const.VNIC_PATH_PREFIX + profile_name +
                        const.VLAN_PATH_PREFIX + vlan_name)
                    # Associate port profile with vlan profile
                    # for the trunk vlans
                    mo = handle.AddManagedObject(
                        p_profile,
                        self.ucsmsdk.VnicEtherIf.ClassId(),
                        {self.ucsmsdk.VnicEtherIf.DN: vlan_associate_path,
                        self.ucsmsdk.VnicEtherIf.NAME: vlan_name,
                        self.ucsmsdk.VnicEtherIf.DEFAULT_NET: "no"}, True)
                    if not mo:
                        LOG.warning(_LW('UCS Manager network driver cannot '
                                        'associate Vlan %(vlan)d to Port '
                                        'Profile %(profile)s'),
                                    {'vlan': vlan, 'profile': profile_name})

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
            handle.CompleteTransaction()

            if not cl_profile:
                LOG.warning(_LW('UCS Manager network driver could not '
                                'create Client Profile %s.'),
                            cl_profile_name)
                return False

            LOG.debug('UCS Manager network driver created Client Profile '
                      '%s at %s', cl_profile_name, cl_profile_dest)
            return True

        except Exception as e:
            return self._handle_ucsm_exception(e, 'Port Profile',
                                               profile_name, ucsm_ip)

    def create_portprofile(self, profile_name, vlan_id, vnic_type, host_id,
        trunk_vlans):
        """Top level method to create Port Profiles on the UCS Manager.

        Calls all the methods responsible for the individual tasks that
        ultimately result in the creation of the Port Profile on the UCS
        Manager.
        """
        ucsm_ip = self.get_ucsm_ip_for_host(host_id)
        if not ucsm_ip:
            LOG.info(_LI('UCS Manager network driver does not support Host_id '
                         '%s'), str(host_id))
            return False

        with self.ucsm_connect_disconnect(ucsm_ip) as handle:
            # Create Vlan Profile
            if not self._create_vlanprofile(handle, vlan_id, ucsm_ip):
                LOG.error(_LE('UCS Manager network driver failed to create '
                              'Vlan Profile for vlan %s'), str(vlan_id))
                return False
            if trunk_vlans:
                for vlan in trunk_vlans:
                    if not self._create_vlanprofile(handle, vlan, ucsm_ip):
                        LOG.error(_LE('UCS Manager network driver failed to '
                            'create Vlan Profile for vlan %s'), vlan)
                        return False

            qos_policy = self.ucsm_conf.get_sriov_qos_policy(ucsm_ip)
            if not qos_policy:
                qos_policy = ""
            else:
                LOG.debug('UCS Manager Network driver applying QoS Policy '
                          '%(qos)s to Port Profile %(port_profile)s',
                          {'qos': qos_policy, 'port_profile': profile_name})

            # Create Port Profile
            if not self._create_port_profile(handle, profile_name,
                                             vlan_id, vnic_type,
                                             ucsm_ip, trunk_vlans,
                                             qos_policy):
                LOG.error(_LE('UCS Manager network driver failed to create '
                              'Port Profile %s'), profile_name)
                return False

        return True

    def _update_service_profile(self, handle, service_profile,
                                vlan_id, ucsm_ip):
        """Updates Service Profile on the UCS Manager.

        Each of the ethernet ports on the Service Profile representing
        the UCS Server, is updated with the VLAN profile corresponding
        to the vlan_id passed in.
        """
        virtio_port_list = self.ucsm_conf.get_ucsm_eth_port_list(ucsm_ip)
        eth_port_paths = ["%s%s" % (service_profile, ep)
            for ep in virtio_port_list]

        vlan_name = self.make_vlan_name(vlan_id)

        try:
            handle.StartTransaction()
            obj = handle.GetManagedObject(
                None,
                self.ucsmsdk.LsServer.ClassId(),
                {self.ucsmsdk.LsServer.DN: service_profile})

            if not obj:
                LOG.debug('UCS Manager network driver could not find '
                          'Service Profile %s in UCSM %s',
                          service_profile, ucsm_ip)
                return False

            for eth_port_path in eth_port_paths:
                eth = handle.GetManagedObject(
                    obj, self.ucsmsdk.VnicEther.ClassId(),
                    {self.ucsmsdk.VnicEther.DN: eth_port_path}, True)

                if eth:
                    vlan_path = (eth_port_path + const.VLAN_PATH_PREFIX +
                                 vlan_name)

                    eth_if = handle.AddManagedObject(eth,
                        self.ucsmsdk.VnicEtherIf.ClassId(),
                        {self.ucsmsdk.VnicEtherIf.DN: vlan_path,
                        self.ucsmsdk.VnicEtherIf.NAME: vlan_name,
                        self.ucsmsdk.VnicEtherIf.DEFAULT_NET: "no"}, True)

                    if not eth_if:
                        LOG.debug('UCS Manager network driver could not '
                                  'update Service Profile %s with vlan %d',
                                  service_profile, vlan_id)
                        return False
                else:
                    LOG.debug('UCS Manager network driver did not find '
                              'ethernet port at %s', eth_port_path)

            handle.CompleteTransaction()
            return True

        except Exception as e:
            return self._handle_ucsm_exception(e, 'Service Profile',
                                               vlan_name, ucsm_ip)

    def update_service_profile_template(self, vlan_id,
                                        host_id, ucsm_ip):
        sp_template = self.ucsm_conf.get_sp_template_for_host(
            host_id)

        sp_template_path = (
            self.ucsm_conf.get_sp_template_path_for_host(host_id) +
            const.SP_TEMPLATE_PREFIX + sp_template)

        vlan_name = self.make_vlan_name(vlan_id)

        with self.ucsm_connect_disconnect(ucsm_ip) as handle:
            # Create Vlan Profile
            if not self._create_vlanprofile(handle, vlan_id, ucsm_ip):
                LOG.error(_LE('UCS Manager network driver failed to create '
                              'Vlan Profile for vlan %s'), str(vlan_id))
                return False

            virtio_port_list = self.ucsm_conf.get_ucsm_eth_port_list(ucsm_ip)
            eth_port_paths = ["%s%s" % (sp_template_path, ep)
                for ep in virtio_port_list]

            try:
                handle.StartTransaction()
                obj = handle.GetManagedObject(
                    None,
                    self.ucsmsdk.LsServer.ClassId(),
                    {self.ucsmsdk.LsServer.DN: sp_template_path})
                if not obj:
                    LOG.error(_LE('UCS Manager network driver could not find '
                                  'Service Profile template %s.'),
                        sp_template_path)
                    return False

                for eth_port_path in eth_port_paths:
                    eth = handle.GetManagedObject(
                        obj, self.ucsmsdk.VnicEther.ClassId(),
                        {self.ucsmsdk.VnicEther.DN: eth_port_path}, True)

                    if eth:
                        vlan_path = (eth_port_path + const.VLAN_PATH_PREFIX +
                                     vlan_name)

                        eth_if = handle.AddManagedObject(eth,
                            self.ucsmsdk.VnicEtherIf.ClassId(),
                            {self.ucsmsdk.VnicEtherIf.DN: vlan_path,
                            self.ucsmsdk.VnicEtherIf.NAME: vlan_name,
                            self.ucsmsdk.VnicEtherIf.DEFAULT_NET: "no"}, True)

                        if not eth_if:
                            LOG.debug('UCS Manager network driver could not '
                                      'update Service Profile Template %s '
                                      'with vlan %d',
                                      sp_template, vlan_id)
                            return False
                    else:
                        LOG.debug('UCS Manager network driver did not find '
                                  'ethernet port at %s', eth_port_path)
                handle.CompleteTransaction()
                return True
            except Exception as e:
                return self._handle_ucsm_exception(e,
                                                   'Service Profile Template',
                                                   vlan_id, ucsm_ip)

    def update_serviceprofile(self, host_id, vlan_id):
        """Top level method to update Service Profiles on UCS Manager.

        Calls all the methods responsible for the individual tasks that
        ultimately result in a vlan_id getting programed on a server's
        ethernet ports and the Fabric Interconnect's network ports.
        """
        ucsm_ip = self.get_ucsm_ip_for_host(host_id)

        service_profile = self.ucsm_sp_dict.get((ucsm_ip, host_id))
        if service_profile:
            LOG.debug('UCS Manager network driver Service Profile : %s',
                      service_profile)
        else:
            LOG.info(_LI('UCS Manager network driver does not support '
                         'Host_id %s'), host_id)
            return False

        with self.ucsm_connect_disconnect(ucsm_ip) as handle:
            # Create Vlan Profile
            if not self._create_vlanprofile(handle, vlan_id, ucsm_ip):
                LOG.error(_LE('UCS Manager network driver failed to create '
                              'Vlan Profile for vlan %s'), str(vlan_id))
                return False

            # Update Service Profile
            if not self._update_service_profile(handle,
                                                service_profile,
                                                vlan_id,
                                                ucsm_ip):
                LOG.error(_LE('UCS Manager network driver failed to update '
                              'Service Profile %(service_profile)s in UCSM '
                              '%(ucsm_ip)s'),
                    {'service_profile': service_profile, 'ucsm_ip': ucsm_ip})
                return False

        return True

    def update_vnic_template(self, host_id, vlan_id, physnet,
        vnic_template_path, vnic_template):
        """Updates VNIC Template with the vlan_id."""
        ucsm_ip = self.get_ucsm_ip_for_host(host_id)
        vlan_name = self.make_vlan_name(vlan_id)

        with self.ucsm_connect_disconnect(ucsm_ip) as handle:
            # Create Vlan Profile
            if not self._create_vlanprofile(handle, vlan_id, ucsm_ip):
                LOG.error(_LE('UCS Manager network driver failed to create '
                          'Vlan Profile for vlan %s'), vlan_id)
                return False

            try:
                LOG.debug('VNIC Template Path: %s', vnic_template_path)
                vnic_template_full_path = (vnic_template_path +
                   const.VNIC_TEMPLATE_PREFIX + str(vnic_template))
                LOG.debug('VNIC Template Path: %s for physnet %s',
                    vnic_template_full_path, physnet)

                handle.StartTransaction()
                mo = handle.GetManagedObject(
                    None,
                    self.ucsmsdk.VnicLanConnTempl.ClassId(),
                    {self.ucsmsdk.VnicLanConnTempl.DN:
                    vnic_template_full_path}, True)
                if not mo:
                    LOG.error(_LE('UCS Manager network driver could '
                                  'not find VNIC template %s'),
                        vnic_template_full_path)
                    return False

                vlan_dn = (vnic_template_full_path + const.VLAN_PATH_PREFIX +
                    vlan_name)
                LOG.debug('VNIC Template VLAN path: %s', vlan_dn)
                eth_if = handle.AddManagedObject(mo,
                    self.ucsmsdk.VnicEtherIf.ClassId(),
                    {self.ucsmsdk.VnicEtherIf.DN: vlan_dn,
                    self.ucsmsdk.VnicEtherIf.NAME: vlan_name,
                    self.ucsmsdk.VnicEtherIf.DEFAULT_NET: "no"}, True)
                if not eth_if:
                    LOG.error(_LE('UCS Manager network driver could '
                                  'not add VLAN %(vlan_name)s to VNIC '
                                  'template %(vnic_template_full_path)s'),
                        {'vlan_name': vlan_name,
                        'vnic_template_full_path': vnic_template_full_path})
                    return False

                handle.CompleteTransaction()
                return True
            except Exception as e:
                return self._handle_ucsm_exception(e, 'VNIC Template',
                    vlan_id, ucsm_ip)

    def _delete_vlan_profile(self, handle, vlan_id, ucsm_ip):
        """Deletes VLAN Profile from UCS Manager."""
        vlan_name = self.make_vlan_name(vlan_id)
        vlan_profile_dest = (const.VLAN_PATH + const.VLAN_PROFILE_PATH_PREFIX +
                             vlan_name)
        try:
            handle.StartTransaction()
            obj = handle.GetManagedObject(
                None,
                self.ucsmsdk.FabricVlan.ClassId(),
                {self.ucsmsdk.FabricVlan.DN: vlan_profile_dest})

            if obj:
                handle.RemoveManagedObject(obj)

            handle.CompleteTransaction()

        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigFailed(config=vlan_id,
                                        ucsm_ip=ucsm_ip, exc=e)

    def _delete_port_profile(self, handle, port_profile, ucsm_ip):
        """Deletes Port Profile from UCS Manager."""
        port_profile_dest = (const.PORT_PROFILESETDN + const.VNIC_PATH_PREFIX +
                             port_profile)

        try:
            handle.StartTransaction()

            # Find port profile on the UCS Manager
            p_profile = handle.GetManagedObject(
                None,
                self.ucsmsdk.VnicProfile.ClassId(),
                {self.ucsmsdk.VnicProfile.NAME: port_profile,
                self.ucsmsdk.VnicProfile.DN: port_profile_dest})

            if not p_profile:
                LOG.warning(_LW('UCS Manager network driver did not find '
                                'Port Profile %s to delete.'),
                            port_profile)
                return

            handle.RemoveManagedObject(p_profile)
            handle.CompleteTransaction()

        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigDeleteFailed(config=port_profile,
                                              ucsm_ip=ucsm_ip,
                                              exc=e)

    def _remove_vlan_from_all_service_profiles(self, handle, vlan_id, ucsm_ip):
        """Deletes VLAN Profile config from server's ethernet ports."""
        service_profile_list = []
        for key, value in six.iteritems(self.ucsm_sp_dict):
            if (ucsm_ip in key) and value:
                service_profile_list.append(value)

        if not service_profile_list:
            # Nothing to do
            return

        try:
            handle.StartTransaction()
            for service_profile in service_profile_list:
                virtio_port_list = self.ucsm_conf.get_ucsm_eth_port_list(
                    ucsm_ip)
                eth_port_paths = ["%s%s" % (service_profile, ep)
                    for ep in virtio_port_list]

                # 1. From the Service Profile config, access the
                # configuration for its ports.
                # 2. Check if that Vlan has been configured on each port
                # 3. If Vlan conifg found, remove it.
                obj = handle.GetManagedObject(
                        None,
                        self.ucsmsdk.LsServer.ClassId(),
                        {self.ucsmsdk.LsServer.DN: service_profile})

                if obj:
                    # Check if this vlan_id has been configured on the
                    # ports in this Service profile
                    for eth_port_path in eth_port_paths:
                        eth = handle.GetManagedObject(
                            obj, self.ucsmsdk.VnicEther.ClassId(),
                            {self.ucsmsdk.VnicEther.DN: eth_port_path},
                            True)
                        if eth:
                            vlan_name = self.make_vlan_name(vlan_id)
                            vlan_path = eth_port_path + "/if-" + vlan_name
                            vlan = handle.GetManagedObject(eth,
                                self.ucsmsdk.VnicEtherIf.ClassId(),
                                {self.ucsmsdk.VnicEtherIf.DN: vlan_path})
                            if vlan:
                                # Found vlan config. Now remove it.
                                handle.RemoveManagedObject(vlan)
            handle.CompleteTransaction()

        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigDeleteFailed(config=vlan_id,
                                              ucsm_ip=ucsm_ip,
                                              exc=e)

    def _remove_vlan_from_all_sp_templates(self, handle, vlan_id, ucsm_ip):
        """Deletes VLAN config from all SP Templates that have it."""
        sp_template_info_list = (
            self.ucsm_conf.get_sp_template_list_for_ucsm(ucsm_ip))

        vlan_name = self.make_vlan_name(vlan_id)
        virtio_port_list = self.ucsm_conf.get_ucsm_eth_port_list(ucsm_ip)

        try:
            handle.StartTransaction()
            # sp_template_info_list is a list of tuples.
            # Each tuple is of the form :
            # (ucsm_ip, sp_template_path, sp_template)
            for sp_template_info in sp_template_info_list:
                sp_template_path = sp_template_info[1]
                sp_template = sp_template_info[2]

                sp_template_full_path = (sp_template_path +
                    const.SP_TEMPLATE_PREFIX + sp_template)

                obj = handle.GetManagedObject(
                    None,
                    self.ucsmsdk.LsServer.ClassId(),
                    {self.ucsmsdk.LsServer.DN: sp_template_full_path})
                if not obj:
                    LOG.error(_LE('UCS Manager network driver could not '
                        'find Service Profile template %s'),
                        sp_template_full_path)
                    continue

                eth_port_paths = ["%s%s" % (sp_template_full_path, ep)
                    for ep in virtio_port_list]
                for eth_port_path in eth_port_paths:
                    eth = handle.GetManagedObject(
                        obj, self.ucsmsdk.VnicEther.ClassId(),
                        {self.ucsmsdk.VnicEther.DN: eth_port_path}, True)

                    if eth:
                        vlan_path = (eth_port_path +
                            const.VLAN_PATH_PREFIX + vlan_name)
                        vlan = handle.GetManagedObject(eth,
                            self.ucsmsdk.VnicEtherIf.ClassId(),
                            {self.ucsmsdk.VnicEtherIf.DN: vlan_path})
                        if vlan:
                            # Found vlan config. Now remove it.
                            handle.RemoveManagedObject(vlan)
                        else:
                            LOG.debug('UCS Manager network driver did not '
                            'find VLAN %s at %s', vlan_name, eth_port_path)
                    else:
                        LOG.debug('UCS Manager network driver did not '
                            'find ethernet port at %s', eth_port_path)
                handle.CompleteTransaction()
                return True
        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigDeleteFailed(config=vlan_id,
                                              ucsm_ip=ucsm_ip,
                                              exc=e)

    def _remove_vlan_from_vnic_templates(self, handle, vlan_id, ucsm_ip):
        """Removes VLAN from all VNIC templates that have it enabled."""
        vnic_template_info = self.ucsm_conf.get_vnic_templates_for_ucsm_ip(
            ucsm_ip)
        vlan_name = self.make_vlan_name(vlan_id)

        if not vnic_template_info:
            # Nothing to do
            return
        try:
            handle.StartTransaction()
            for temp_info in vnic_template_info:
                vnic_template_list = temp_info[1].split(',')
                vnic_template_path = temp_info[0]

                for vnic_template in vnic_template_list:
                    vnic_template_full_path = (vnic_template_path +
                        const.VNIC_TEMPLATE_PREFIX + str(vnic_template))
                    LOG.debug('vnic_template_full_path: %s',
                        vnic_template_full_path)
                    mo = handle.GetManagedObject(
                        None,
                        self.ucsmsdk.VnicLanConnTempl.ClassId(),
                        {self.ucsmsdk.VnicLanConnTempl.DN: (
                            vnic_template_full_path)},
                        True)
                    if not mo:
                        LOG.error(_LE('UCS Manager network driver could '
                                      'not find VNIC template %s at'),
                            vnic_template_full_path)
                        continue

                    vlan_dn = (vnic_template_full_path +
                        const.VLAN_PATH_PREFIX + vlan_name)
                    LOG.debug('VNIC Template VLAN path; %s', vlan_dn)
                    eth_if = handle.GetManagedObject(mo,
                        self.ucsmsdk.VnicEtherIf.ClassId(),
                        {self.ucsmsdk.VnicEtherIf.DN: vlan_dn})

                    if not eth_if:
                        LOG.error(_LE('UCS Manager network driver could not '
                                      'delete VLAN %(vlan_name)s from VNIC '
                                      'template %(vnic_template_full_path)s'),
                            {'vlan_name': vlan_name,
                            'vnic_template_full_path':
                            vnic_template_full_path})
                    if eth_if:
                        handle.RemoveManagedObject(eth_if)
            handle.CompleteTransaction()
            return True
        except Exception as e:
            return self._handle_ucsm_exception(e, 'VNIC Template',
                                               vlan_id, ucsm_ip)

    def delete_all_config_for_vlan(self, vlan_id, port_profile,
                                   trunk_vlans):
        """Top level method to delete all config for vlan_id."""
        ucsm_ips = self.ucsm_conf.get_all_ucsm_ips()
        for ucsm_ip in ucsm_ips:

            with self.ucsm_connect_disconnect(ucsm_ip) as handle:
                LOG.debug('Deleting config for VLAN %d from UCSM %s', vlan_id,
                    ucsm_ip)
                if (port_profile):
                    self._delete_port_profile(handle, port_profile, ucsm_ip)
                if self.ucsm_conf.is_service_profile_template_configured():
                    self._remove_vlan_from_all_sp_templates(handle,
                                                            vlan_id,
                                                            ucsm_ip)
                if self.ucsm_conf.is_vnic_template_configured():
                    self._remove_vlan_from_vnic_templates(handle,
                                                          vlan_id,
                                                          ucsm_ip)
                if not (self.ucsm_conf.is_service_profile_template_configured()
                    and self.ucsm_conf.is_vnic_template_configured()):
                    self._remove_vlan_from_all_service_profiles(handle,
                                                                vlan_id,
                                                                ucsm_ip)
                self._delete_vlan_profile(handle, vlan_id, ucsm_ip)
                for vlan_id in trunk_vlans:
                    self._delete_vlan_profile(handle, vlan_id, ucsm_ip)

    def _handle_ucsm_exception(self, exception_type, profile_type,
                               profile_name, ucsm_ip):
        if const.DUPLICATE_EXCEPTION in str(exception_type):
            LOG.debug('UCS Manager network driver ignoring duplicate '
                      'create/update of %s with %s',
                profile_type, profile_name)
            return True
        else:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigFailed(config=profile_name,
                                        ucsm_ip=ucsm_ip,
                                        exc=exception_type)

    def ucs_manager_disconnect(self, handle, ucsm_ip):
        """Disconnects from the UCS Manager.

        After the disconnect, the handle associated with this connection
        is no longer valid.
        """
        try:
            handle.Logout()
        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmDisconnectFailed(ucsm_ip=ucsm_ip, exc=e)

    @staticmethod
    def make_vlan_name(vlan_id):
        return const.VLAN_PROFILE_NAME_PREFIX + str(vlan_id)
