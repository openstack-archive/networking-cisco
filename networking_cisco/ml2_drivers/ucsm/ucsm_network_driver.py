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

from collections import defaultdict
import six
from threading import Timer

from contextlib import contextmanager
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils

from networking_cisco import backwards_compatibility as bc
from networking_cisco.ml2_drivers.ucsm import config
from networking_cisco.ml2_drivers.ucsm import constants as const
from networking_cisco.ml2_drivers.ucsm import exceptions as cexc
from networking_cisco.ml2_drivers.ucsm import ucsm_db


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class CiscoUcsmDriver(object):

    """UCS Manager Driver Main Class."""

    def __init__(self):
        LOG.debug("UCS Manager Network driver found")
        self.ucsmsdk = None
        self.supported_sriov_vnic_types = [bc.portbindings.VNIC_DIRECT,
                                           bc.portbindings.VNIC_MACVTAP]
        self.supported_pci_devs = CONF.ml2_cisco_ucsm.supported_pci_devs

        config.load_single_ucsm_config()

        self.ucsm_db = ucsm_db.UcsmDbModel()
        self.ucsm_host_dict = {}
        self.ucsm_sp_dict = {}
        self._create_host_and_sp_dicts_from_config()

        # Start timer to monitor Port Profiles that need to be deleted.
        Timer(const.DEFAULT_PP_DELETE_TIME,
            self._delayed_delete_port_profile, ()).start()
        LOG.debug('Starting periodic Port Profile delete timer for %d',
            const.DEFAULT_PP_DELETE_TIME)

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
            LOG.info('Non SR-IOV vnic_type: %s.', vnic_type)
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
        return profile and (profile.get('pci_vendor_info') ==
                const.PCI_INFO_CISCO_VIC_1240)

    def _import_ucsmsdk(self):
        """Imports the ucsmsdk module.

        This module is not installed as part of the normal Neutron
        distributions. It is imported dynamically in this module so that
        the import can be mocked, allowing unit testing without requiring
        the installation of ucsmsdk.

        """
        # Check if SSL certificate checking has been disabled.
        # If so, warn the user before proceeding.
        if not CONF.ml2_cisco_ucsm.ucsm_https_verify:
            LOG.warning(const.SSL_WARNING)

        # Monkey patch the ucsmsdk version of ssl to enable https_verify if
        # required
        from networking_cisco.ml2_drivers.ucsm import ucs_ssl
        ucs_driver = importutils.import_module('ucsmsdk.ucsdriver')
        ucs_driver.ssl = ucs_ssl

        class ucsmsdk(object):
            handle = importutils.import_class(
                    'ucsmsdk.ucshandle.UcsHandle')
            fabricVlan = importutils.import_class(
                    'ucsmsdk.mometa.fabric.FabricVlan.FabricVlan')
            vnicProfile = importutils.import_class(
                    'ucsmsdk.mometa.vnic.VnicProfile.VnicProfile')
            vnicEtherIf = importutils.import_class(
                    'ucsmsdk.mometa.vnic.VnicEtherIf.VnicEtherIf')
            vmVnicProfCl = importutils.import_class(
                    'ucsmsdk.mometa.vm.VmVnicProfCl.VmVnicProfCl')

        return ucsmsdk

    def _create_host_and_sp_dicts_from_config(self):
        # Pull Service Profile to Hostname mapping from config if it has been
        # provided
        for ip, ucsm in CONF.ml2_cisco_ucsm.ucsms.items():
            for host, sp in (ucsm.ucsm_host_list or {}).items():
                self.ucsm_host_dict[host] = ip
                if '/' not in sp:
                    self.ucsm_sp_dict[(ip, host)] = (
                        const.SERVICE_PROFILE_PATH_PREFIX + sp.strip())
                else:
                    self.ucsm_sp_dict[(ip, host)] = sp.strip()

        # Learn the mappings for the UCSMs which didn't have the host list in
        # the config.
        self._create_ucsm_host_to_service_profile_mapping()

        if not self.ucsm_sp_dict:
            LOG.error('UCS Manager network driver failed to get Service '
                      'Profile information for any of its nodes.')

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

        ucsm = CONF.ml2_cisco_ucsm.ucsms.get(ucsm_ip)

        if not ucsm or not ucsm.ucsm_username or not ucsm.ucsm_password:
            LOG.error('UCS Manager network driver failed to get login '
                      'credentials for UCSM %s', ucsm_ip)
            return None

        handle = self.ucsmsdk.handle(ucsm_ip, ucsm.ucsm_username,
                                     ucsm.ucsm_password)
        try:
            handle.login()
        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConnectFailed(ucsm_ip=ucsm_ip, exc=e)

        return handle

    def _create_ucsm_host_to_service_profile_mapping(self):
        """Reads list of Service profiles and finds associated Server."""
        # Get list of UCSMs without host list given in the config
        ucsm_ips = [ip for ip, ucsm in CONF.ml2_cisco_ucsm.ucsms.items()
                    if not ucsm.ucsm_host_list]
        for ucsm_ip in ucsm_ips:
            with self.ucsm_connect_disconnect(ucsm_ip) as handle:
                try:
                    sp_list = handle.query_classid('lsServer')
                    if sp_list is not None:
                        for sp in sp_list:
                            if sp.pn_dn:
                                server_name = handle.query_dn(sp.pn_dn).name
                                if (server_name and not
                                        sp.oper_src_templ_name):
                                    LOG.debug('Server %s info retrieved '
                                        'from UCSM %s', server_name, ucsm_ip)
                                    key = (ucsm_ip, server_name)
                                    self.ucsm_sp_dict[key] = str(sp.dn)
                                    self.ucsm_host_dict[server_name] = ucsm_ip
                except Exception as e:
                    # Raise a Neutron exception. Include a description of
                    # the original exception.
                    raise cexc.UcsmConfigReadFailed(ucsm_ip=ucsm_ip, exc=e)

    def _learn_sp_and_template_for_host(self, host_id):
        ucsm_ips = list(CONF.ml2_cisco_ucsm.ucsms)
        for ucsm_ip in ucsm_ips:
            with self.ucsm_connect_disconnect(ucsm_ip) as handle:
                try:
                    sp_list = handle.query_classid('lsServer')
                    if sp_list is not None:
                        for sp in sp_list:
                            if sp.pn_dn:
                                server_name = handle.query_dn(sp.pn_dn).name
                                LOG.debug('Server_name = %s', server_name)
                                if server_name == host_id:
                                    self.ucsm_host_dict[server_name] = ucsm_ip
                                    LOG.debug('Found host %s with SP %s '
                                              'at UCSM %s', server_name,
                                              str(sp.dn), ucsm_ip)
                                    LOG.debug('Server SP Template %s',
                                        sp.oper_src_templ_name)
                                    config.update_sp_template_config(
                                        host_id, ucsm_ip,
                                        sp.oper_src_templ_name)
                                    return ucsm_ip
                except Exception as e:
                    # Raise a Neutron exception. Include a description of
                    # the original  exception.
                    raise cexc.UcsmConfigReadFailed(ucsm_ip=ucsm_ip, exc=e)

    def get_ucsm_ip_for_host(self, host_id):
        ucsm_ip = self.ucsm_host_dict.get(host_id)
        if not ucsm_ip:
            # See if there is a UCSM in the configuration with this host_id
            ucsms = CONF.ml2_cisco_ucsm.ucsms
            ucsm_ip = next(iter([ip for ip, ucsm in ucsms.items()
                           if host_id in ucsm.sp_template_list]), None)
            if not ucsm_ip:
                # Try to discover the Service Proile or SP Template for the
                # host directly from UCS Manager
                LOG.debug('Did not find SP Template so reading from UCSM')
                ucsm_ip = self._learn_sp_and_template_for_host(host_id)

        return ucsm_ip

    def _create_vlanprofile(self, handle, vlan_id, ucsm_ip):
        """Creates VLAN profile to able associated with the Port Profile."""
        vlan_name = self.make_vlan_name(vlan_id)
        vlan_profile_dest = (const.VLAN_PATH + const.VLAN_PROFILE_PATH_PREFIX +
                             vlan_name)

        try:
            vp1 = handle.query_dn(const.VLAN_PATH)
            if not vp1:
                LOG.warning('UCS Manager network driver Vlan Profile '
                            'path at %s missing', const.VLAN_PATH)
                return False

            # Create a vlan profile with the given vlan_id
            vp2 = self.ucsmsdk.fabricVlan(
                parent_mo_or_dn=vp1,
                name=vlan_name,
                compression_type=const.VLAN_COMPRESSION_TYPE,
                sharing=const.NONE,
                pub_nw_name="",
                id=str(vlan_id),
                mcast_policy_name="",
                default_net="no")

            handle.add_mo(vp2)
            handle.commit()

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

        # Remove this Port Profile from the delete DB table if it was
        # addded there due to a previous delete.
        self.ucsm_db.remove_port_profile_to_delete(profile_name, ucsm_ip)

        # Check if direct or macvtap mode
        if vnic_type == bc.portbindings.VNIC_DIRECT:
            port_mode = const.HIGH_PERF
        else:
            port_mode = const.NONE

        try:
            port_profile = handle.query_dn(const.PORT_PROFILESETDN)

            if not port_profile:
                LOG.warning('UCS Manager network driver Port Profile '
                            'path at %s missing',
                    const.PORT_PROFILESETDN)
                return False

            # Create a port profile on the UCS Manager
            p_profile = self.ucsmsdk.vnicProfile(
                parent_mo_or_dn=port_profile,
                name=profile_name,
                policy_owner="local",
                nw_ctrl_policy_name="",
                pin_to_group_name="",
                descr=const.DESCR,
                qos_policy_name=qos_policy,
                host_nw_ioperf=port_mode,
                max_ports=const.MAX_PORTS)

            handle.add_mo(p_profile)

            if not p_profile:
                LOG.warning('UCS Manager network driver could not '
                            'create Port Profile %s.', profile_name)
                return False

            LOG.debug('UCS Manager network driver associating Vlan '
                      'Profile with Port Profile at %s',
                vlan_associate_path)
            # Associate port profile with vlan profile
            mo = self.ucsmsdk.vnicEtherIf(
                parent_mo_or_dn=p_profile,
                name=vlan_name,
                default_net="yes")

            handle.add_mo(mo)

            if not mo:
                LOG.warning('UCS Manager network driver cannot '
                            'associate Vlan Profile to Port '
                            'Profile %s', profile_name)
                return False
            LOG.debug('UCS Manager network driver created Port Profile %s '
                      'at %s', profile_name, port_profile_dest)

            # For Multi VLAN trunk support
            if trunk_vlans:
                for vlan in trunk_vlans:
                    vlan_name = self.make_vlan_name(vlan)
                    # Associate port profile with vlan profile
                    # for the trunk vlans
                    mo = self.ucsmsdk.vnicEtherIf(
                        parent_mo_or_dn=p_profile,
                        name=vlan_name,
                        default_net="no")

                    handle.add_mo(mo)

                    if not mo:
                        LOG.warning('UCS Manager network driver cannot '
                                    'associate Vlan %(vlan)d to Port '
                                    'Profile %(profile)s',
                                    {'vlan': vlan, 'profile': profile_name})

            cl_profile = self.ucsmsdk.vmVnicProfCl(
                parent_mo_or_dn=p_profile,
                org_path=".*",
                name=cl_profile_name,
                policy_owner="local",
                sw_name=".*",
                dc_name=".*",
                descr=const.DESCR)

            handle.add_mo(cl_profile)

            if not cl_profile:
                LOG.warning('UCS Manager network driver could not '
                            'create Client Profile %s.',
                            cl_profile_name)
                return False

            handle.commit()

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
            LOG.info('UCS Manager network driver does not have UCSM IP '
                     'for Host_id %s', str(host_id))
            return False

        with self.ucsm_connect_disconnect(ucsm_ip) as handle:
            # Create Vlan Profile
            if not self._create_vlanprofile(handle, vlan_id, ucsm_ip):
                LOG.error('UCS Manager network driver failed to create '
                          'Vlan Profile for vlan %s', str(vlan_id))
                return False
            if trunk_vlans:
                for vlan in trunk_vlans:
                    if not self._create_vlanprofile(handle, vlan, ucsm_ip):
                        LOG.error('UCS Manager network driver failed to '
                                  'create Vlan Profile for vlan %s', vlan)
                        return False

            qos_policy = CONF.ml2_cisco_ucsm.ucsms[ucsm_ip].sriov_qos_policy
            if qos_policy:
                LOG.debug('UCS Manager Network driver applying QoS Policy '
                          '%(qos)s to Port Profile %(port_profile)s',
                          {'qos': qos_policy, 'port_profile': profile_name})

            # Create Port Profile
            if not self._create_port_profile(handle, profile_name,
                                             vlan_id, vnic_type,
                                             ucsm_ip, trunk_vlans,
                                             qos_policy):
                LOG.error('UCS Manager network driver failed to create '
                          'Port Profile %s', profile_name)
                return False

        return True

    def _update_service_profile(self, handle, service_profile,
                                vlan_id, ucsm_ip):
        """Updates Service Profile on the UCS Manager.

        Each of the ethernet ports on the Service Profile representing
        the UCS Server, is updated with the VLAN profile corresponding
        to the vlan_id passed in.
        """
        virtio_port_list = (
            CONF.ml2_cisco_ucsm.ucsms[ucsm_ip].ucsm_virtio_eth_ports)

        eth_port_paths = ["%s%s" % (service_profile, ep)
            for ep in virtio_port_list]

        vlan_name = self.make_vlan_name(vlan_id)

        try:
            obj = handle.query_dn(service_profile)

            if not obj:
                LOG.debug('UCS Manager network driver could not find '
                          'Service Profile %s in UCSM %s',
                          service_profile, ucsm_ip)
                return False

            for eth_port_path in eth_port_paths:
                eth = handle.query_dn(eth_port_path)

                if eth:
                    eth_if = self.ucsmsdk.vnicEtherIf(
                        parent_mo_or_dn=eth,
                        name=vlan_name,
                        default_net="no")

                    handle.add_mo(eth_if)

                    if not eth_if:
                        LOG.debug('UCS Manager network driver could not '
                                  'update Service Profile %s with vlan %d',
                                  service_profile, vlan_id)
                        return False
                else:
                    LOG.debug('UCS Manager network driver did not find '
                              'ethernet port at %s', eth_port_path)

            handle.commit()
            return True

        except Exception as e:
            return self._handle_ucsm_exception(e, 'Service Profile',
                                               vlan_name, ucsm_ip)

    def update_service_profile_template(self, vlan_id,
                                        host_id, ucsm_ip):

        template_info = (
            CONF.ml2_cisco_ucsm.ucsms[ucsm_ip].sp_template_list[host_id])

        sp_template_path = (template_info.path + const.SP_TEMPLATE_PREFIX +
                            template_info.name)

        vlan_name = self.make_vlan_name(vlan_id)

        with self.ucsm_connect_disconnect(ucsm_ip) as handle:
            # Create Vlan Profile
            if not self._create_vlanprofile(handle, vlan_id, ucsm_ip):
                LOG.error('UCS Manager network driver failed to create '
                          'Vlan Profile for vlan %s', str(vlan_id))
                return False

            virtio_port_list = (
                CONF.ml2_cisco_ucsm.ucsms[ucsm_ip].ucsm_virtio_eth_ports)
            eth_port_paths = ["%s%s" % (sp_template_path, ep)
                for ep in virtio_port_list]

            try:
                obj = handle.query_dn(sp_template_path)
                if not obj:
                    LOG.error('UCS Manager network driver could not find '
                              'Service Profile template %s.',
                        sp_template_path)
                    return False

                for eth_port_path in eth_port_paths:
                    eth = handle.query_dn(eth_port_path)

                    if eth:
                        eth_if = self.ucsmsdk.vnicEtherIf(
                            parent_mo_or_dn=eth,
                            name=vlan_name,
                            default_net="no")

                        handle.add_mo(eth_if)

                        if not eth_if:
                            LOG.debug('UCS Manager network driver could not '
                                      'update Service Profile Template %s '
                                      'with vlan %d',
                                      template_info.name, vlan_id)
                            return False
                    else:
                        LOG.debug('UCS Manager network driver did not find '
                                  'ethernet port at %s', eth_port_path)
                handle.commit()
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
        if not ucsm_ip:
            LOG.info('UCS Manager network driver does not have UCSM IP '
                     'for Host_id %s', str(host_id))
            return False

        service_profile = self.ucsm_sp_dict.get((ucsm_ip, host_id))
        if service_profile:
            LOG.debug('UCS Manager network driver Service Profile : %s',
                      service_profile)
        else:
            LOG.info('UCS Manager network driver does not support '
                     'Host_id %s', host_id)
            return False

        with self.ucsm_connect_disconnect(ucsm_ip) as handle:
            # Create Vlan Profile
            if not self._create_vlanprofile(handle, vlan_id, ucsm_ip):
                LOG.error('UCS Manager network driver failed to create '
                          'Vlan Profile for vlan %s', str(vlan_id))
                return False

            # Update Service Profile
            if not self._update_service_profile(handle,
                                                service_profile,
                                                vlan_id,
                                                ucsm_ip):
                LOG.error('UCS Manager network driver failed to update '
                          'Service Profile %(service_profile)s in UCSM '
                          '%(ucsm_ip)s',
                    {'service_profile': service_profile, 'ucsm_ip': ucsm_ip})
                return False

        return True

    def update_vnic_template(self, host_id, vlan_id, physnet,
        vnic_template_path, vnic_template):
        """Updates VNIC Template with the vlan_id."""
        ucsm_ip = self.get_ucsm_ip_for_host(host_id)

        if not ucsm_ip:
            LOG.info('UCS Manager network driver does not have UCSM IP '
                     'for Host_id %s', str(host_id))
            return False

        vlan_name = self.make_vlan_name(vlan_id)

        with self.ucsm_connect_disconnect(ucsm_ip) as handle:
            # Create Vlan Profile
            if not self._create_vlanprofile(handle, vlan_id, ucsm_ip):
                LOG.error('UCS Manager network driver failed to create '
                          'Vlan Profile for vlan %s', vlan_id)
                return False

            try:
                LOG.debug('VNIC Template Path: %s', vnic_template_path)
                vnic_template_full_path = (vnic_template_path +
                   const.VNIC_TEMPLATE_PREFIX + str(vnic_template))
                LOG.debug('VNIC Template Path: %s for physnet %s',
                    vnic_template_full_path, physnet)

                mo = handle.query_dn(vnic_template_full_path)
                if not mo:
                    LOG.error('UCS Manager network driver could '
                              'not find VNIC template %s',
                        vnic_template_full_path)
                    return False

                vlan_dn = (vnic_template_full_path + const.VLAN_PATH_PREFIX +
                    vlan_name)
                LOG.debug('VNIC Template VLAN path: %s', vlan_dn)

                eth_if = self.ucsmsdk.vnicEtherIf(
                    parent_mo_or_dn=mo,
                    name=vlan_name,
                    default_net="no")
                handle.add_mo(eth_if)
                if not eth_if:
                    LOG.error('UCS Manager network driver could '
                              'not add VLAN %(vlan_name)s to VNIC '
                              'template %(vnic_template_full_path)s',
                        {'vlan_name': vlan_name,
                        'vnic_template_full_path': vnic_template_full_path})
                    return False

                handle.commit()
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
            obj = handle.query_dn(vlan_profile_dest)

            if obj:
                handle.remove_mo(obj)

            handle.commit()

        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigFailed(config=vlan_id,
                                        ucsm_ip=ucsm_ip, exc=e)

    def _delayed_delete_port_profile(self):
        pp_delete_dict = defaultdict(list)
        Timer(const.DEFAULT_PP_DELETE_TIME,
            self._delayed_delete_port_profile, ()).start()
        all_pps = self.ucsm_db.get_all_port_profiles_to_delete()
        for pp in all_pps:
            pp_delete_dict[pp.device_id].append(pp.profile_id)

        # Connect to each UCSM IP and try to delete Port profiles
        for ucsm_ip in pp_delete_dict.keys():
            with self.ucsm_connect_disconnect(ucsm_ip) as handle:
                for pp in pp_delete_dict.get(ucsm_ip):
                    LOG.debug('Deleting PP %s from UCSM %s', pp,
                        ucsm_ip)
                    try:
                        self._delete_port_profile_from_ucsm(handle,
                                                            pp, ucsm_ip)
                        # Remove this Port Profile from the delete DB table
                        # if it was addded there due to a previous delete.
                        LOG.debug('Removing PP %s from delete table after '
                                  'successful delete', pp)
                        self.ucsm_db.remove_port_profile_to_delete(pp, ucsm_ip)
                    except Exception:
                        #do nothing
                        LOG.debug('Could not delete PP %s from UCSM %s',
                            pp, ucsm_ip)

    def _delete_port_profile_from_ucsm(self, handle, port_profile, ucsm_ip):
        """Deletes Port Profile from UCS Manager."""
        port_profile_dest = (const.PORT_PROFILESETDN + const.VNIC_PATH_PREFIX +
                             port_profile)

        # Find port profile on the UCS Manager
        p_profile = handle.query_dn(port_profile_dest)

        if p_profile:
            handle.remove_mo(p_profile)
        else:
            LOG.warning('UCS Manager network driver did not find '
                        'Port Profile %s to delete.',
                        port_profile)

        handle.commit()

    def _delete_port_profile(self, handle, port_profile, ucsm_ip):
        """Calls method to delete Port Profile from UCS Manager.
           If exception is raised by UCSM, then the PP is added to
           a DB table. The delete timer thread, tried to delete all
           PPs added to this table when it wakes up.
           """
        try:
            self._delete_port_profile_from_ucsm(handle, port_profile, ucsm_ip)

        except Exception as e:
            # Add the Port Profile that we could not delete to the Port Profile
            # delete table. A periodic task will attempt to delete it.
            LOG.debug('Received Port Profile delete exception %s', e)
            self.ucsm_db.add_port_profile_to_delete_table(port_profile,
                                                          ucsm_ip)

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
            for service_profile in service_profile_list:
                virtio_port_list = (
                    CONF.ml2_cisco_ucsm.ucsms[ucsm_ip].ucsm_virtio_eth_ports)
                eth_port_paths = ["%s%s" % (service_profile, ep)
                    for ep in virtio_port_list]

                # 1. From the Service Profile config, access the
                # configuration for its ports.
                # 2. Check if that Vlan has been configured on each port
                # 3. If Vlan config found, remove it.
                obj = handle.query_dn(service_profile)

                if obj:
                    # Check if this vlan_id has been configured on the
                    # ports in this Service profile
                    for eth_port_path in eth_port_paths:
                        eth = handle.query_dn(eth_port_path)
                        if eth:
                            vlan_name = self.make_vlan_name(vlan_id)
                            vlan_path = eth_port_path + "/if-" + vlan_name
                            vlan = handle.query_dn(vlan_path)
                            if vlan:
                                # Found vlan config. Now remove it.
                                handle.remove_mo(vlan)
            handle.commit()

        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigDeleteFailed(config=vlan_id,
                                              ucsm_ip=ucsm_ip,
                                              exc=e)

    def _remove_vlan_from_all_sp_templates(self, handle, vlan_id, ucsm_ip):
        """Deletes VLAN config from all SP Templates that have it."""
        sp_template_info_list = (
            CONF.ml2_cisco_ucsm.ucsms[ucsm_ip].sp_template_list.values())

        vlan_name = self.make_vlan_name(vlan_id)
        virtio_port_list = (
            CONF.ml2_cisco_ucsm.ucsms[ucsm_ip].ucsm_virtio_eth_ports)

        try:
            # sp_template_info_list is a list of tuples.
            # Each tuple is of the form :
            # (ucsm_ip, sp_template_path, sp_template)
            for sp_template_info in sp_template_info_list:
                sp_template_path = sp_template_info.path
                sp_template = sp_template_info.name

                sp_template_full_path = (sp_template_path +
                    const.SP_TEMPLATE_PREFIX + sp_template)

                obj = handle.query_dn(sp_template_full_path)
                if not obj:
                    LOG.error('UCS Manager network driver could not '
                        'find Service Profile template %s',
                        sp_template_full_path)
                    continue

                eth_port_paths = ["%s%s" % (sp_template_full_path, ep)
                    for ep in virtio_port_list]
                for eth_port_path in eth_port_paths:
                    eth = handle.query_dn(eth_port_path)

                    if eth:
                        vlan_path = (eth_port_path +
                            const.VLAN_PATH_PREFIX + vlan_name)
                        vlan = handle.query_dn(vlan_path)
                        if vlan:
                            # Found vlan config. Now remove it.
                            handle.remove_mo(vlan)
                        else:
                            LOG.debug('UCS Manager network driver did not '
                            'find VLAN %s at %s', vlan_name, eth_port_path)
                    else:
                        LOG.debug('UCS Manager network driver did not '
                            'find ethernet port at %s', eth_port_path)
                handle.commit()
                return True
        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmConfigDeleteFailed(config=vlan_id,
                                              ucsm_ip=ucsm_ip,
                                              exc=e)

    def _remove_vlan_from_vnic_templates(self, handle, vlan_id, ucsm_ip):
        """Removes VLAN from all VNIC templates that have it enabled."""
        ucsm = CONF.ml2_cisco_ucsm.ucsms[ucsm_ip]
        vnic_template_info = ucsm.vnic_template_list.values()

        vlan_name = self.make_vlan_name(vlan_id)

        if not vnic_template_info:
            # Nothing to do
            return
        try:
            for temp_info in vnic_template_info:
                vnic_template = temp_info.template
                vnic_template_path = temp_info.path

                vnic_template_full_path = (vnic_template_path +
                    const.VNIC_TEMPLATE_PREFIX + str(vnic_template))
                LOG.debug('vnic_template_full_path: %s',
                    vnic_template_full_path)
                mo = handle.query_dn(vnic_template_full_path)
                if not mo:
                    LOG.error('UCS Manager network driver could '
                              'not find VNIC template %s at',
                        vnic_template_full_path)
                    continue

                vlan_dn = (vnic_template_full_path +
                    const.VLAN_PATH_PREFIX + vlan_name)
                LOG.debug('VNIC Template VLAN path; %s', vlan_dn)
                eth_if = handle.query_dn(vlan_dn)

                if not eth_if:
                    LOG.error('UCS Manager network driver could not '
                              'delete VLAN %(vlan_name)s from VNIC '
                              'template %(vnic_template_full_path)s',
                        {'vlan_name': vlan_name,
                        'vnic_template_full_path':
                        vnic_template_full_path})
                if eth_if:
                    handle.remove_mo(eth_if)
            handle.commit()
            return True
        except Exception as e:
            return self._handle_ucsm_exception(e, 'VNIC Template',
                                               vlan_id, ucsm_ip)

    def delete_all_config_for_vlan(self, vlan_id, port_profile,
                                   trunk_vlans):
        """Top level method to delete all config for vlan_id."""
        ucsm_ips = list(CONF.ml2_cisco_ucsm.ucsms)
        for ucsm_ip in ucsm_ips:

            with self.ucsm_connect_disconnect(ucsm_ip) as handle:
                LOG.debug('Deleting config for VLAN %d from UCSM %s', vlan_id,
                    ucsm_ip)
                if (port_profile):
                    self._delete_port_profile(handle, port_profile, ucsm_ip)

                ucsm = CONF.ml2_cisco_ucsm.ucsms[ucsm_ip]
                if ucsm.sp_template_list:
                    self._remove_vlan_from_all_sp_templates(handle,
                                                            vlan_id,
                                                            ucsm_ip)
                if ucsm.vnic_template_list:
                    self._remove_vlan_from_vnic_templates(handle,
                                                          vlan_id,
                                                          ucsm_ip)
                if not (ucsm.sp_template_list and
                        ucsm.vnic_template_list):
                    self._remove_vlan_from_all_service_profiles(handle,
                                                                vlan_id,
                                                                ucsm_ip)
                self._delete_vlan_profile(handle, vlan_id, ucsm_ip)
                if trunk_vlans:
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
            handle.logout()
        except Exception as e:
            # Raise a Neutron exception. Include a description of
            # the original  exception.
            raise cexc.UcsmDisconnectFailed(ucsm_ip=ucsm_ip, exc=e)

    @staticmethod
    def make_vlan_name(vlan_id):
        return const.VLAN_PROFILE_NAME_PREFIX + str(vlan_id)
