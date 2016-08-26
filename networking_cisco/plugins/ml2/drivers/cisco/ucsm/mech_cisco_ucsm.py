# Copyright 2015-2016 Cisco Systems, Inc.
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


from oslo_log import log as logging

from networking_cisco._i18n import _LE, _LI, _LW

from neutron.extensions import portbindings
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import driver_api as api

from neutron_lib import constants

from networking_cisco.plugins.ml2.drivers.cisco.ucsm import config
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import constants as const
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import ucsm_db
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import ucsm_network_driver

LOG = logging.getLogger(__name__)


class CiscoUcsmMechanismDriver(api.MechanismDriver):

    """ML2 Mechanism Driver for Cisco UCS Manager."""

    def initialize(self):
        self.vif_type = const.VIF_TYPE_802_QBH
        self.vif_details = {portbindings.CAP_PORT_FILTER: False}
        self.ucsm_db = ucsm_db.UcsmDbModel()
        self.driver = ucsm_network_driver.CiscoUcsmDriver()
        self.ucsm_conf = config.UcsmConfig()

    def _get_vlanid(self, context):
        """Returns vlan_id associated with a bound VLAN segment."""
        segment = context.bottom_bound_segment
        if segment and self.check_segment(segment):
            return segment.get(api.SEGMENTATION_ID)

    def _is_supported_deviceowner(self, port):
        return (port['device_owner'].startswith('compute') or
                port['device_owner'] == constants.DEVICE_OWNER_DHCP or
                port['device_owner'] == constants.DEVICE_OWNER_ROUTER_HA_INTF)

    def _is_status_active(self, port):
        return port['status'] == constants.PORT_STATUS_ACTIVE

    def _get_physnet(self, context):
        """Returns physnet associated with a bound VLAN segment."""
        segment = context.bottom_bound_segment
        if segment and self.check_segment(segment):
            return segment.get(api.PHYSICAL_NETWORK)

    def update_port_precommit(self, context):
        """Adds port profile and vlan information to the DB.

        Assign a port profile to this port. To do that:
        1. Get the vlan_id associated with the bound segment
        2. Check if a port profile already exists for this vlan_id
        3. If yes, associate that port profile with this port.
        4. If no, create a new port profile with this vlan_id and
        associate with this port
        """
        vnic_type = context.current.get(portbindings.VNIC_TYPE,
                                        portbindings.VNIC_NORMAL)

        profile = context.current.get(portbindings.PROFILE, {})
        host_id = self._get_host_id(
            context.current.get(portbindings.HOST_ID))
        if not host_id:
            LOG.warning(_LW('Host id from port context is None. '
                'Ignoring this port'))
            return

        vlan_id = self._get_vlanid(context)
        if not vlan_id:
            LOG.warning(_LW('Vlan_id is None. Ignoring this port'))
            return

        ucsm_ip = self.driver.get_ucsm_ip_for_host(host_id)
        if not ucsm_ip:
            LOG.info(_LI('Host %s is not controlled by any known '
                         'UCS Manager.'), host_id)
            return

        LOG.debug('UCSM IP: %s', str(ucsm_ip))
        if not self.driver.check_vnic_type_and_vendor_info(vnic_type,
                                                           profile):
            # This is a neutron virtio port.
            # If VNIC templates are configured, that config would
            # take precedence and the VLAN is added to the VNIC template.
            physnet = self._get_physnet(context)
            if not physnet:
                LOG.debug('physnet is None. Not modifying VNIC '
                          'Template config')
            if self.ucsm_conf.vnic_template_mode and physnet:
                # Check if VNIC template is configured for this physnet
                vnic_template_path, vnic_template = (
                    self.ucsm_conf.get_vnic_template_for_physnet(ucsm_ip,
                    physnet))

                if vnic_template:
                    LOG.debug('vnic_template %s', vnic_template)
                    self.ucsm_db.add_vnic_template(vlan_id, ucsm_ip,
                        vnic_template, physnet)
                else:
                    LOG.debug('VNIC Template not configured for '
                              'physnet %s', physnet)
                    return
            # In the absence of VNIC Templates, VLAN is directly added
            # to vNIC(s) on the SP Template.
            # Check if SP Template config has been provided. If so, find
            # the UCSM that controls this host and the Service Profile
            # Template for this host.

            if self.ucsm_conf.is_service_profile_template_configured():
                sp_template = self.ucsm_conf.get_sp_template_for_host(host_id)
                LOG.debug('SP Template: %s, VLAN_id: %d', sp_template,
                          vlan_id)
                self.ucsm_db.add_service_profile_template(vlan_id,
                                                          sp_template,
                                                          ucsm_ip)
                return

        # If this is an Intel SR-IOV vnic, then no need to create port
        # profile on the UCS manager. So no need to update the DB.
        if not self.driver.is_vmfex_port(profile):
            LOG.debug('This is a SR-IOV port and hence not updating DB.')
            return

        # This is a Cisco VM-FEX port
        p_profile_name = self.make_profile_name(vlan_id)
        LOG.debug('Port Profile: %s for VLAN_id: %d', p_profile_name, vlan_id)

        # Create a new port profile entry in the db
        self.ucsm_db.add_port_profile(p_profile_name, vlan_id, ucsm_ip)

    def update_port_postcommit(self, context):
        """Creates a port profile on UCS Manager.

        Creates a Port Profile for this VLAN if it does not already
        exist.
        """
        vlan_id = self._get_vlanid(context)

        if not vlan_id:
            LOG.warning(_LW('Vlan_id is None. Ignoring this port.'))
            return

        if (not self._is_supported_deviceowner(context.current) or
            not self._is_status_active(context.current)):
            LOG.debug("Unsupported device_owner '%(owner)s' or port not"
                      " active (vlan_id '%(vlan)d', status %(status)s)."
                      "   Nothing to do.",
                      {'owner': context.current['device_owner'],
                       'vlan': vlan_id,
                       'status': context.current['status']})
            return

        # Checks to perform before UCS Manager can create a Port Profile.
        # 1. Make sure this host is on a known UCS Manager.
        host_id = self._get_host_id(
            context.current.get(portbindings.HOST_ID))
        if not host_id:
            LOG.warning(_LW('Host id from port context is None. '
                'Ignoring this port'))
            return

        ucsm_ip = self.driver.get_ucsm_ip_for_host(host_id)
        if not ucsm_ip:
            LOG.info(_LI('Host_id %s is not controlled by any known UCS '
                'Manager'), str(host_id))
            return

        profile = context.current.get(portbindings.PROFILE, {})
        vnic_type = context.current.get(portbindings.VNIC_TYPE,
                                        portbindings.VNIC_NORMAL)

        # 2. Make sure this is a vm_fex_port.(Port profiles are created
        # only for VM-FEX ports.)
        if (self.driver.check_vnic_type_and_vendor_info(vnic_type, profile) and
            self.driver.is_vmfex_port(profile)):

            # 3. Make sure update_port_precommit added an entry in the DB
            # for this port profile
            profile_name = self.ucsm_db.get_port_profile_for_vlan(vlan_id,
                ucsm_ip)

            # 4. Make sure that the Port Profile hasn't already been created
            # on the UCS Manager
            if profile_name and self.ucsm_db.is_port_profile_created(vlan_id,
                ucsm_ip):
                LOG.debug('Port Profile %s for vlan_id %d already exists '
                          'on UCSM %s.', profile_name, vlan_id, ucsm_ip)
                return

            # Multi VLAN trunk support
            # Check if this network is a trunk network. If so pass the
            # additional VLAN ids to the UCSM driver.
            network = context.network.current['name']
            trunk_vlans = self.ucsm_conf.get_sriov_multivlan_trunk_config(
                network)

            # All checks are done. Ask the UCS Manager driver to create the
            # above Port Profile.
            if self.driver.create_portprofile(profile_name, vlan_id,
                                              vnic_type, host_id, trunk_vlans):
                # Port profile created on UCS, record that in the DB.
                self.ucsm_db.set_port_profile_created(vlan_id, profile_name,
                    ucsm_ip)
            return
        else:
            # Enable vlan-id for this Neutron virtual port.
            LOG.debug('Host_id is %s', host_id)
            physnet = self._get_physnet(context)
            if self.ucsm_conf.is_vnic_template_configured() and physnet:
                LOG.debug('Update VNIC Template for physnet: %s', physnet)
                vnic_template_path, vnic_template = (
                    self.ucsm_conf.get_vnic_template_for_physnet(ucsm_ip,
                    physnet))

                if vnic_template:
                    LOG.debug('vnic_template %s', vnic_template)
                    if (self.driver.update_vnic_template(host_id,
                                                         vlan_id,
                                                         physnet,
                                                         vnic_template_path,
                                                         vnic_template)):
                        LOG.debug('Setting ucsm_updated flag for '
                                  'vlan : %(vlan)d, '
                                  'vnic_template : %(vnic_template)s '
                                  'on ucsm_ip: %(ucsm_ip)s',
                                  {'vlan': vlan_id,
                                  'vnic_template': vnic_template,
                                  'ucsm_ip': ucsm_ip})
                        self.ucsm_db.set_vnic_template_updated(
                            vlan_id, ucsm_ip, vnic_template, physnet)
                    return

            if (self.ucsm_conf.is_service_profile_template_configured()
                and self.driver.update_service_profile_template(
                    vlan_id, host_id, ucsm_ip)):
                sp_template = self.ucsm_conf.get_sp_template_for_host(
                        host_id)
                LOG.debug('Setting ucsm_updated flag for vlan : %(vlan)d, '
                          'sp_template : %(sp_template)s on ucsm_ip: '
                          '%(ucsm_ip)s', {'vlan': vlan_id,
                          'sp_template': sp_template, 'ucsm_ip': ucsm_ip})
                self.ucsm_db.set_sp_template_updated(vlan_id, sp_template,
                                                     ucsm_ip)
            else:
                self.driver.update_serviceprofile(host_id, vlan_id)

    def delete_network_precommit(self, context):
        """Delete entry corresponding to Network's VLAN in the DB."""
        segments = context.network_segments
        vlan_id = segments[0]['segmentation_id']

        if vlan_id:
            # For VM-FEX ports
            self.ucsm_db.delete_vlan_entry(vlan_id)
            # For Neutron virtio ports
            if self.ucsm_conf.is_service_profile_template_configured():
                self.ucsm_db.delete_sp_template_for_vlan(vlan_id)
            if self.ucsm_conf.is_vnic_template_configured():
                self.ucsm_db.delete_vnic_template_for_vlan(vlan_id)

    def delete_network_postcommit(self, context):
        """Delete all configuration added to UCS Manager for the vlan_id."""

        segments = context.network_segments
        vlan_id = segments[0]['segmentation_id']
        port_profile = self.make_profile_name(vlan_id)
        network_name = context.current['name']
        trunk_vlans = self.ucsm_conf.get_sriov_multivlan_trunk_config(
            network_name)
        if vlan_id:
            self.driver.delete_all_config_for_vlan(vlan_id, port_profile,
                trunk_vlans)

    def bind_port(self, context):
        """Binds port to current network segment.

        Binds port only if the vnic_type is direct or macvtap and
        the port is from a supported vendor. While binding port set it
        in ACTIVE state and provide the Port Profile or Vlan Id as part
        vif_details.
        """
        vnic_type = context.current.get(portbindings.VNIC_TYPE,
                                        portbindings.VNIC_NORMAL)

        LOG.debug('Attempting to bind port %(port)s with vnic_type '
                  '%(vnic_type)s on network %(network)s ',
                  {'port': context.current['id'],
                   'vnic_type': vnic_type,
                   'network': context.network.current['id']})

        profile = context.current.get(portbindings.PROFILE, {})

        if not self.driver.check_vnic_type_and_vendor_info(vnic_type,
                                                           profile):
            return

        for segment in context.network.network_segments:
            if self.check_segment(segment):
                vlan_id = segment[api.SEGMENTATION_ID]

                if not vlan_id:
                    LOG.warning(_LW('Cannot bind port: vlan_id is None.'))
                    return

                LOG.debug("Port binding to Vlan_id: %s", str(vlan_id))

                # Check if this is a Cisco VM-FEX port or Intel SR_IOV port
                if self.driver.is_vmfex_port(profile):
                    profile_name = self.make_profile_name(vlan_id)
                    self.vif_details[
                        const.VIF_DETAILS_PROFILEID] = profile_name
                else:
                    self.vif_details[
                        portbindings.VIF_DETAILS_VLAN] = str(vlan_id)

                context.set_binding(segment[api.ID],
                                    self.vif_type,
                                    self.vif_details,
                                    constants.PORT_STATUS_ACTIVE)
                return

        LOG.error(_LE('UCS Mech Driver: Failed binding port ID %(id)s '
                      'on any segment of network %(network)s'),
                  {'id': context.current['id'],
                   'network': context.network.current['id']})

    @staticmethod
    def check_segment(segment):
        network_type = segment[api.NETWORK_TYPE]
        return network_type == p_const.TYPE_VLAN

    @staticmethod
    def make_profile_name(vlan_id):
        return const.PORT_PROFILE_NAME_PREFIX + str(vlan_id)

    def _get_host_id(self, host_id):
        """Strips the host_id of any domain name extensions."""
        return host_id.split('.')[0] if host_id else None
