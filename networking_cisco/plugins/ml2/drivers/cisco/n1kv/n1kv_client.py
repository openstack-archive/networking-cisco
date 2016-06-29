# Copyright 2015 Cisco Systems, Inc.
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

import base64
import eventlet
import netaddr
import requests
import six

from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_utils import excutils
from oslo_utils import netutils

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    constants as n1kv_const)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (
    exceptions as n1kv_exc)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import config  # noqa

from networking_cisco._i18n import _, _LE, _LI

from neutron.common import exceptions as n_exc
from neutron.extensions import providernet
from neutron.plugins.common import constants as p_const

LOG = logging.getLogger(__name__)

cfg.CONF.import_group(
    'ml2_cisco_n1kv',
    'networking_cisco.plugins.ml2.drivers.cisco.n1kv.config')


class Client(object):

    """
    Client for the Cisco Nexus1000V Neutron Plugin.

    This client implements functions to communicate with
    Cisco Nexus1000V VSM.

    For every Neutron object, Cisco Nexus1000V Neutron Plugin
    creates a corresponding object on the controller (Cisco
    Nexus1000V VSM).

    CONCEPTS:

    Following are few concepts used in Nexus1000V VSM:

    port-profiles:
    Policy profiles correspond to port profiles on Nexus1000V VSM.
    Port profiles are the primary mechanism by which network policy is
    defined and applied to switch interfaces in a Nexus 1000V system.

    network-segment:
    Each network-segment represents a broadcast domain.

    network-segment-pool:
    A network-segment-pool contains one or more network-segments.

    logical-network:
    A logical-network contains one or more network-segment-pools.

    bridge-domain:
    A bridge-domain is created when the network-segment is of type VXLAN.
    Each VXLAN <--> VLAN combination can be thought of as a bridge domain.

    ip-pool:
    Each ip-pool represents a subnet on the Nexus1000V VSM.


    WORK FLOW:

    For every network profile a corresponding logical-network and
    a network-segment-pool, under this logical-network, will be created.

    For every network created from a given network profile, a
    network-segment will be added to the network-segment-pool corresponding
    to that network profile.

    A port is created on a network and associated with a policy-profile.
    Hence for every unique combination of a network and a policy-profile, a
    unique vm-network will be created and a reference to the port will be
    added. If the same combination of network and policy-profile is used by
    another port, the references to that port will be added to the same
    vm-network.


    """

    # Define paths for the URI where the client connects for HTTP requests.
    port_profiles_path = "/virtual-port-profile"
    ports_path = "/kvm/vm-network/%s/ports"
    port_path = "/kvm/vm-network/%s/ports/%s"
    network_segment_path = "/network-segment/%s"
    network_segments_path = "/network-segment"
    network_segment_pool_path = "/network-segment-pool/%s"
    network_segment_pools_path = "/network-segment-pool"
    ip_pool_path = "/ip-pool-template/%s"
    ip_pools_path = "/ip-pool-template"
    vm_networks_path = "/kvm/vm-network"
    vm_network_path = "/kvm/vm-network/%s"
    bridge_domains_path = "/kvm/bridge-domain"
    bridge_domain_path = "/kvm/bridge-domain/%s"
    logical_network_path = "/logical-network/%s"
    md5_path = "/kvm/config-md5-hashes"
    sync_notification_path = "/sync-notification"

    pool = eventlet.GreenPool(cfg.CONF.ml2_cisco_n1kv.http_pool_size)

    def __init__(self, **kwargs):
        """Initialize a new client for the plugin."""
        self.format = 'json'

        # Extract configuration parameters from the configuration file.
        self.username = cfg.CONF.ml2_cisco_n1kv.username
        self.password = cfg.CONF.ml2_cisco_n1kv.password
        self.vsm_ips = config.get_vsm_hosts()
        self.action_prefix = 'http://%s/api/n1k'
        self.timeout = cfg.CONF.ml2_cisco_n1kv.http_timeout
        self.max_vsm_retries = cfg.CONF.ml2_cisco_n1kv.max_vsm_retries
        required_opts = ('vsm_ips', 'username', 'password')
        # Validate whether required options are configured
        for opt in required_opts:
            if not getattr(self, opt):
                raise cfg.RequiredOptError(opt, 'ml2_cisco_n1kv')
        # Validate the configured VSM IP addresses
        # Note: Currently only support IPv4
        for vsm_ip in self.vsm_ips:
            if not (netutils.is_valid_ipv4(vsm_ip) or
                    netutils.is_valid_ipv6(vsm_ip)):
                raise cfg.Error(_("Cisco Nexus1000V ML2 driver config: "
                                  "Invalid format for VSM IP address: %s") %
                                vsm_ip)

    def send_sync_notification(self, msg, vsm_ip):
        """Send a start/end/no-change sync notification to the VSM.

        :param vsm_ip: string representing the IP address of the VSM
        :param msg: message string, start, end or no-change
        """
        body = {'status': msg}
        self._post(self.sync_notification_path, body=body, vsm_ip=vsm_ip)

    def list_port_profiles(self, vsm_ip=None):
        """Fetch all policy profiles from the VSM.

        :param vsm_ip: string representing the IP address of the VSM
        :returns: JSON string
        """
        return self._get(self.port_profiles_path, vsm_ip=vsm_ip)

    def list_network_profiles(self, vsm_ip=None):
        """Fetch all network profiles from VSM.

        :param vsm_ip: string representing the IP address of the VSM
        :return: JSON string
        """
        return self._get(self.network_segment_pools_path, vsm_ip=vsm_ip)

    def list_networks(self, vsm_ip=None):
        """Fetch all networks from VSM.

        :param vsm_ip: string representing the IP address of the VSM
        :return: JSON string
        """
        return self._get(self.network_segments_path, vsm_ip=vsm_ip)

    def list_subnets(self, vsm_ip=None):
        """Fetch all subnets from VSM.

        :param vsm_ip: string representing the IP address of the VSM
        :return: JSON string
        """
        return self._get(self.ip_pools_path, vsm_ip=vsm_ip)

    def list_vmnetworks(self, vsm_ip=None):
        """Fetch all VM networks from VSM.

        :param vsm_ip: string representing the IP address of the VSM
        :return: JSON string
        """
        return self._get(self.vm_networks_path, vsm_ip=vsm_ip)

    def list_md5_hashes(self, vsm_ip=None):
        """Fetch MD5 hashes for all resources from VSM.

        Fetch MD5 hashes for network profiles, networks, subnets, ports and
        a consolidated hash of these hashes from the VSM

        :param vsm_ip: string representing the IP address of the VSM
        :return: JSON string
        """
        return self._get(self.md5_path, vsm_ip=vsm_ip)

    def list_bridge_domains(self, vsm_ip=None):
        """Fetch the list of all bridge domains on the VSM.

        :param vsm_ip: string representing the IP address of the VSM
        :return: JSON string
        """
        return self._get(self.bridge_domains_path, vsm_ip=vsm_ip)

    def show_network(self, network_id, vsm_ip=None):
        """Fetch details of a given network like segment type from the VSM.

        :param network_id: UUID of the network whose details are needed
        :param vsm_ip: string representing the IP address of the VSM
        :return: JSON string
        """
        return self._get(self.network_segment_path % network_id, vsm_ip=vsm_ip)

    def _create_logical_network(self, network_profile, vsm_ip=None):
        """Create a logical network on the VSM.

        :param network_profile: network profile dict
        :param vsm_ip: string representing the IP address of the VSM
        """
        body = {'description': network_profile['name']}
        logical_network_name = (network_profile['id'] +
                                n1kv_const.LOGICAL_NETWORK_SUFFIX)
        return self._post(self.logical_network_path % logical_network_name,
                          body=body, vsm_ip=vsm_ip)

    def delete_logical_network(self, logical_network_name, vsm_ip=None):
        """Delete a logical network on VSM.

        :param logical_network_name: string representing name of the logical
                                     network
        :param vsm_ip: string representing the IP address of the VSM
        """
        return self._delete(
            self.logical_network_path % logical_network_name, vsm_ip=vsm_ip)

    def create_network_segment_pool(self, network_profile, vsm_ip=None):
        """Create a network segment pool on the VSM.

        :param network_profile: network profile dict
        :param vsm_ip: string representing the IP address of the VSM
        """
        self._create_logical_network(network_profile, vsm_ip=vsm_ip)
        logical_network_name = (network_profile['id'] +
                                n1kv_const.LOGICAL_NETWORK_SUFFIX)
        body = {'name': network_profile['name'],
                'description': network_profile['name'],
                'id': network_profile['id'],
                'logicalNetwork': logical_network_name}
        return self._post(
            self.network_segment_pool_path % network_profile['id'],
            body=body, vsm_ip=vsm_ip)

    def delete_network_segment_pool(self, network_segment_pool_id,
                                    vsm_ip=None):
        """Delete a network segment pool on the VSM.

        :param network_segment_pool_id: UUID representing the network
                                        segment pool
        :param vsm_ip: string representing the IP address of the VSM
        """
        return self._delete(self.network_segment_pool_path %
                            network_segment_pool_id, vsm_ip=vsm_ip)

    def create_network_segment(self, network, network_profile, vsm_ip=None):
        """Create a network segment on the VSM.

        :param network: network dict
        :param network_profile: network profile object
        :param vsm_ip: string representing the IP address of the VSM
        """
        body = {'publishName': network['id'],
                'description': network['name'],
                'id': network['id'],
                'tenantId': network['tenant_id'],
                'mode': 'access',
                'segmentType': network_profile['segment_type'],
                'networkSegmentPool': network_profile['id']}
        # Override tenantId if network is shared
        if network['shared']:
            body['tenantId'] = '0'
        if network[providernet.NETWORK_TYPE] == p_const.TYPE_VLAN:
            body['vlan'] = network[providernet.SEGMENTATION_ID]
        elif network[providernet.NETWORK_TYPE] == p_const.TYPE_VXLAN:
            # Create a bridge domain on VSM
            bd_name = network['id'] + n1kv_const.BRIDGE_DOMAIN_SUFFIX
            self.create_bridge_domain(network, network_profile, vsm_ip=vsm_ip)
            body['bridgeDomain'] = bd_name
        try:
            return self._post(self.network_segment_path % network['id'],
                              body=body, vsm_ip=vsm_ip)
        except(n1kv_exc.VSMError, n1kv_exc.VSMConnectionFailed):
            with excutils.save_and_reraise_exception():
                # Clean up the bridge domain from the VSM for VXLAN networks.
                # Reraise the exception so that caller method executes further
                # clean up.
                if network[providernet.NETWORK_TYPE] == p_const.TYPE_VXLAN:
                    self.delete_bridge_domain(bd_name, vsm_ip=vsm_ip)

    def update_network_segment(self, updated_network):
        """Update a network segment on the VSM.

        :param updated_network: updated network dict
        """
        body = {'description': updated_network['name'],
                'tenantId': updated_network['tenant_id']}
        if updated_network['shared']:
            body['tenantId'] = '0'
        return self._post(self.network_segment_path % updated_network['id'],
                          body=body)

    def delete_network_segment(self, network_segment_id, network_type,
                               vsm_ip=None):
        """Delete a network segment on the VSM.

        :param network_segment_id: UUID representing the network segment
        :param network_type: type of network to be deleted
        :param vsm_ip: string representing the IP address of the VSM
        """
        if network_type == p_const.TYPE_VXLAN:
            bd_name = network_segment_id + n1kv_const.BRIDGE_DOMAIN_SUFFIX
            self.delete_bridge_domain(bd_name, vsm_ip=vsm_ip)
        return self._delete(self.network_segment_path % network_segment_id,
                            vsm_ip=vsm_ip)

    def create_bridge_domain(self, network, net_prof, vsm_ip=None):
        """Create a bridge domain on VSM.

        :param network: network dict
        :param net_prof: network profile dict
        :param vsm_ip: string representing the IP address of the VSM
        """
        if net_prof['sub_type'] == n1kv_const.CLI_VXLAN_MODE_ENHANCED:
            vxlan_subtype = n1kv_const.MODE_UNICAST
        else:
            vxlan_subtype = n1kv_const.MODE_NATIVE_VXLAN
        body = {'name': network['id'] + n1kv_const.BRIDGE_DOMAIN_SUFFIX,
                'segmentId': network[providernet.SEGMENTATION_ID],
                'subType': vxlan_subtype,
                'tenantId': network['tenant_id']}
        if vxlan_subtype == n1kv_const.MODE_NATIVE_VXLAN:
            start_ip, end_ip = net_prof['multicast_ip_range'].split('-', 1)
            body['groupIp'] = start_ip
        return self._post(self.bridge_domains_path,
                          body=body, vsm_ip=vsm_ip)

    def delete_bridge_domain(self, name, vsm_ip=None):
        """Delete a bridge domain on VSM.

        :param name: name of the bridge domain to be deleted
        :param vsm_ip: string representing the IP address of the VSM
        """
        return self._delete(self.bridge_domain_path % name, vsm_ip=vsm_ip)

    def create_ip_pool(self, subnet, vsm_ip=None):
        """Create a subnet on VSM.

        :param subnet: subnet dict
        :param vsm_ip: string representing the IP address of the VSM
        """
        if subnet['cidr']:
            try:
                ip = netaddr.IPNetwork(subnet['cidr'])
                netmask = str(ip.netmask)
                network_address = str(ip.network)
            except (ValueError, netaddr.AddrFormatError):
                msg = _("Invalid input for CIDR")
                raise n_exc.InvalidInput(error_message=msg)
        else:
            netmask = network_address = ""

        if subnet['allocation_pools']:
            address_range_start = subnet['allocation_pools'][0]['start']
            address_range_end = subnet['allocation_pools'][0]['end']
        else:
            address_range_start = None
            address_range_end = None

        body = {'addressRangeStart': address_range_start,
                'addressRangeEnd': address_range_end,
                'ipAddressSubnet': netmask,
                'description': subnet['name'],
                'gateway': subnet['gateway_ip'],
                'dhcp': subnet['enable_dhcp'],
                'dnsServersList': subnet['dns_nameservers'],
                'networkAddress': network_address,
                'netSegmentName': subnet['network_id'],
                'id': subnet['id'],
                'tenantId': subnet['tenant_id']}
        return self._post(self.ip_pool_path % subnet['id'],
                          body=body, vsm_ip=vsm_ip)

    def update_ip_pool(self, subnet):
        """Update an ip-pool on the VSM.

        :param subnet: subnet dictionary
        """
        body = {'description': subnet['name'],
                'dhcp': subnet['enable_dhcp'],
                'dnsServersList': subnet['dns_nameservers']}
        return self._post(self.ip_pool_path % subnet['id'],
                          body=body)

    def delete_ip_pool(self, subnet_id, vsm_ip=None):
        """Delete an ip-pool on the VSM.

        :param subnet_id: UUID representing the subnet
        :param vsm_ip: string representing the IP address of the VSM
        """
        return self._delete(self.ip_pool_path % subnet_id, vsm_ip=vsm_ip)

    def create_n1kv_port(self, port, vmnetwork_name, policy_profile,
                         vsm_ip=None):
        """Create a port on the VSM.

        :param port: port dict
        :param vmnetwork_name: name of the VM network
        :param policy_profile: policy profile object
        :param vsm_ip: string representing the IP address of the VSM
        """
        body = {'name': vmnetwork_name,
                'networkSegmentId': port['network_id'],
                'networkSegment': port['network_id'],
                'portProfile': policy_profile.name,
                'portProfileId': policy_profile.id,
                'tenantId': port['tenant_id'],
                'portId': port['id'],
                'macAddress': port['mac_address'],
                'portType': port['device_owner'],
                }
        if port.get('fixed_ips'):
            body['ipAddress'] = port['fixed_ips'][0]['ip_address']
            body['subnetId'] = port['fixed_ips'][0]['subnet_id']
        return self._post(self.vm_networks_path,
                          body=body, vsm_ip=vsm_ip)

    def delete_n1kv_port(self, vmnetwork_name, port_id, vsm_ip=None):
        """Delete a port on the VSM.

        :param vmnetwork_name: name of the VM network which imports this port
        :param port_id: UUID of the port
        :param vsm_ip: string representing the IP address of the VSM
        """
        return self._delete(self.port_path % (vmnetwork_name, port_id),
                            vsm_ip=vsm_ip)

    def _do_request(self, method, action, body=None,
                    headers=None, vsm_ip=None):
        """Perform the HTTP request.

        The response is in either JSON format or plain text. A GET method will
        invoke a JSON response while a PUT/POST/DELETE returns message from the
        VSM in plain text format.
        Exception is raised when VSM replies with an INTERNAL SERVER ERROR HTTP
        status code (500) i.e. an error has occurred on the VSM or SERVICE
        UNAVAILABLE (404) i.e. VSM is not reachable.

        :param method: type of the HTTP request. POST, GET, PUT or DELETE
        :param action: path to which the client makes request
        :param body: dict for arguments which are sent as part of the request
        :param headers: header for the HTTP request
        :param vsm_ip: vsm_ip for the HTTP request. If not provided then
                       request will be sent to all VSMs.
        :returns: JSON or plain text in HTTP response
        """

        action = self.action_prefix + action
        if body:
            body = jsonutils.dumps(body)
            LOG.debug("req: %s", body)
        hosts = []
        if vsm_ip:
            hosts.append(vsm_ip)
        else:
            hosts = self.vsm_ips
        if not headers:
            headers = self._get_auth_header()
            headers['Content-Type'] = headers['Accept'] = "application/json"
        for vsm_ip in hosts:
            if netutils.is_valid_ipv6(vsm_ip):
                # Enclose IPv6 address in [] in the URL
                vsm_action = action % ("[%s]" % vsm_ip)
            else:
                # IPv4 address
                vsm_action = action % vsm_ip
            for attempt in range(self.max_vsm_retries + 1):
                try:
                    LOG.debug("[VSM %(vsm)s attempt %(id)s]: Connecting.." %
                        {"vsm": vsm_ip, "id": attempt})
                    resp = self.pool.spawn(requests.request,
                                           method,
                                           url=vsm_action,
                                           data=body,
                                           headers=headers,
                                           timeout=self.timeout).wait()
                    break
                except Exception as e:
                    LOG.debug("[VSM %(vsm)s attempt %(id)s]: Conn timeout." %
                        {"vsm": vsm_ip, "id": attempt})
                    if attempt == self.max_vsm_retries:
                        LOG.error(_LE("VSM %s, Conn failed."), vsm_ip)
                        raise n1kv_exc.VSMConnectionFailed(reason=e)
            if resp.status_code != requests.codes.OK:
                LOG.error(_LE("VSM %(vsm)s, Got error: %(err)s"),
                    {"vsm": vsm_ip, "err": resp.text})
                raise n1kv_exc.VSMError(reason=resp.text)
        if 'application/json' in resp.headers['content-type']:
            try:
                return resp.json()
            except ValueError:
                return {}
        elif 'text/plain' in resp.headers['content-type']:
            LOG.info(_LI("VSM: %s"), resp.text)

    def _delete(self, action, body=None, headers=None, vsm_ip=None):
        return self._do_request("DELETE", action, body=body,
                                headers=headers, vsm_ip=vsm_ip)

    def _get(self, action, vsm_ip, body=None, headers=None):
        return self._do_request("GET", action, body=body,
                                headers=headers, vsm_ip=vsm_ip)

    def _post(self, action, body=None, headers=None, vsm_ip=None):
        return self._do_request("POST", action, body=body,
                                headers=headers, vsm_ip=vsm_ip)

    def _put(self, action, body=None, headers=None, vsm_ip=None):
        return self._do_request("PUT", action, body=body,
                                headers=headers, vsm_ip=vsm_ip)

    def _get_auth_header(self):
        """Retrieve header with auth info for the VSM.

        :return: authorization header dict
        """
        auth = base64.encodestring(six.b("%s:%s" %
                                   (self.username,
                                    self.password))).rstrip()
        return {"Authorization": "Basic %s" % auth}
