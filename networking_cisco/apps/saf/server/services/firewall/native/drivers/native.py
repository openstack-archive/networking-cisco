# Copyright 2016 Cisco Systems, Inc.
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
#

import time

from networking_cisco._i18n import _LE, _LI
from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.server import dfa_openstack_helper as OsHelper
from networking_cisco.apps.saf.server.services.firewall.native import (
    fabric_setup_base as FP)
from networking_cisco.apps.saf.server.services.firewall.native import (
    fw_constants as fw_const)
from networking_cisco.apps.saf.server.services.firewall.native.drivers import (
    base)


LOG = logging.getLogger(__name__)
Q_PRIORITY = 30 + 4


class NativeFirewall(base.BaseDriver, FP.FabricApi):

    """Native Firewall Driver. """

    def __init__(self):
        """Class init. """
        LOG.debug("Initializing Native Firewall")
        super(NativeFirewall, self).__init__()
        self.tenant_dict = {}
        self.os_helper = OsHelper.DfaNeutronHelper()
        self.cfg = config.CiscoDFAConfig().cfg
        self.mgmt_ip_addr = None
        self.dcnm_obj = None
        self.que_obj = None

    def initialize(self, cfg_dict):
        """Initialization routine. """
        LOG.debug("Initialize for NativeFirewall")
        self.mgmt_ip_addr = cfg_dict.get('mgmt_ip_addr')

    def populate_event_que(self, que_obj):
        """Populate the event queue object. """
        LOG.debug("Pop Event for NativeFirewall")
        self.que_obj = que_obj

    def populate_dcnm_obj(self, dcnm_obj):
        """Populate the DCNM object. """
        LOG.debug("Pop DCNM for NativeFirewall")
        self.dcnm_obj = dcnm_obj

    def is_device_virtual(self):
        """Returns if device is virtual. """
        return True

    def get_name(self):
        """Returns the name of the FW appliance. """
        # Put it in a constant fixme(padkrish)
        return 'native'

    def get_max_quota(self):
        """Returns the number of Firewall instances.

        Returns the maximum number of Firewall instance that a single Firewall
        can support.
        """
        # TODO(padkrish) Return the right value
        return 50

    def attach_intf_router(self, tenant_id, tenant_name, router_id):
        """Routine to attach the interface to the router. """
        in_sub = self.get_in_subnet_id(tenant_id)
        out_sub = self.get_out_subnet_id(tenant_id)
        # Modify Hard coded Name fixme
        subnet_lst = set()
        subnet_lst.add(in_sub)
        subnet_lst.add(out_sub)
        ret = self.os_helper.add_intf_router(router_id, tenant_id, subnet_lst)
        return ret, in_sub, out_sub

    def get_router_id(self, tenant_id, tenant_name):
        """Retrieve the router ID. """
        router_id = None
        if tenant_id in self.tenant_dict:
            router_id = self.tenant_dict.get(tenant_id).get('router_id')
        if not router_id:
            router_list = self.os_helper.get_rtr_by_name(
                'FW_RTR_' + tenant_name)
            if len(router_list) > 0:
                router_id = router_list[0].get('id')
        return router_id

    def delete_intf_router(self, tenant_id, tenant_name, router_id):
        """Routine to delete the router. """
        in_sub = self.get_in_subnet_id(tenant_id)
        out_sub = self.get_out_subnet_id(tenant_id)
        subnet_lst = set()
        subnet_lst.add(in_sub)
        subnet_lst.add(out_sub)
        router_id = self.get_router_id(tenant_id, tenant_name)
        if router_id:
            ret = self.os_helper.delete_intf_router(tenant_name, tenant_id,
                                                    router_id, subnet_lst)
            if not ret:
                LOG.error(_LE("Failed to delete router intf id %(rtr)s, "
                              "tenant %(tenant)s"),
                          {'rtr': router_id, 'tenant': tenant_id})
            return ret
        LOG.error(_LE("Invalid router ID, can't delete interface from "
                      "router"))

    def prepare_router_vm_msg(self, tenant_id, tenant_name, router_id, net_id,
                              subnet_id, seg, status):
        """Prepare the message to be sent to Event queue for VDP trigger.

        This is actually called for a subnet add to a router. This function
        prepares a VM's VNIC create/delete message.
        """
        max_get_router_info_retry = True
        attempt = 0
        while max_get_router_info_retry:
            port_data = self.os_helper.get_router_port_subnet(subnet_id)
            if port_data is None:
                LOG.error(_LE("Unable to get router port data"))
                return None
            if port_data.get('binding:host_id') == '':
                time.sleep(3)
                attempt += 1
                if attempt > 3:
                    max_get_router_info_retry = False
                    LOG.error(_LE("Unable to get router binding host data, "
                                  "Max attempts reached"))
            else:
                max_get_router_info_retry = False
        if status is 'up':
            event_type = 'service.vnic.create'
        else:
            event_type = 'service.vnic.delete'
        vnic_data = {'status': status, 'mac': port_data.get('mac_address'),
                     'segid': seg, 'host': port_data.get('binding:host_id')}
        if vnic_data['host'] == '':
            LOG.error(_LE("Null host for seg %(seg)s subnet %(subnet)s"),
                      {'seg': seg, 'subnet': subnet_id})
            if self.tenant_dict.get(tenant_id).get('host') is None:
                LOG.error(_LE("Null host for tenant %(tenant)s seg %(seg)s "
                              "subnet %(subnet)s"),
                          {'tenant': tenant_id, 'seg': seg,
                           'subnet': subnet_id})
                return None
            else:
                vnic_data['host'] = self.tenant_dict.get(tenant_id).get('host')
        else:
            self.tenant_dict[tenant_id]['host'] = vnic_data['host']
        vm_ip = port_data.get('fixed_ips')[0].get('ip_address')
        vnic_data.update({'port_id': port_data.get('id'), 'network_id': net_id,
                          'vm_name': 'FW_SRVC_RTR_' + tenant_name,
                          'vm_ip': vm_ip, 'vm_uuid': router_id, 'gw_mac': None,
                          'fwd_mod': 'anycast_gateway'})
        payload = {'service': vnic_data}
        data = (event_type, payload)
        return data

    def send_router_port_msg(self, tenant_id, tenant_name, router_id, net_id,
                             subnet_id, seg, status):
        """Sends the router port message to the queue. """
        data = self.prepare_router_vm_msg(tenant_id, tenant_name, router_id,
                                          net_id, subnet_id, seg, status)
        if data is None:
            return False
        timestamp = time.ctime()
        pri = Q_PRIORITY
        LOG.info(_LI("Sending native FW data into queue %(data)s"),
                 {'data': data})
        self.que_obj.put((pri, timestamp, data))
        return True

    def create_tenant_dict(self, tenant_id, router_id=None):
        """Tenant dict creation. """
        self.tenant_dict[tenant_id] = {'host': None, 'router_id': router_id}

    def send_in_router_port_msg(self, tenant_id, arg_dict, status):
        "Call routine to send vNic create notification for 'in' interface. """
        in_net = self.get_in_net_id(tenant_id)
        ret = self.send_router_port_msg(tenant_id,
                                        arg_dict.get('tenant_name') + '_in',
                                        arg_dict.get('router_id'), in_net,
                                        arg_dict.get('in_sub'),
                                        arg_dict.get('in_seg'), status)
        if not ret:
            LOG.error(_LE("Sending router port message failed for in network "
                          "tenant %(tenant)s subnet %(seg)s"),
                      {'tenant': tenant_id, 'seg': arg_dict.get('in_seg')})
            if status == 'up':
                self.delete_intf_router(tenant_id, arg_dict.get('tenant_name'),
                                        arg_dict.get('router_id'))
            return False
        return True

    def send_out_router_port_msg(self, tenant_id, arg_dict, status):
        "Call routine to send vNic create notification for 'out' interface. """
        out_net = self.get_out_net_id(tenant_id)
        router_id = arg_dict.get('router_id')
        in_seg = arg_dict.get('in_seg')
        out_seg = arg_dict.get('out_seg')
        in_sub = arg_dict.get('in_sub')
        out_sub = arg_dict.get('out_sub')
        ret = self.send_router_port_msg(tenant_id,
                                        arg_dict.get('tenant_name') + '_out',
                                        router_id, out_net, out_sub, out_seg,
                                        status)
        if not ret:
            LOG.error(_LE("Sending router port message failed for out network "
                          "tenant %(tenant)s subnet %(seg)s"),
                      {'tenant': tenant_id, 'seg': out_seg})
            in_net = self.get_in_net_id(tenant_id)
            if status == 'up':
                ret = self.send_router_port_msg(
                    tenant_id, arg_dict.get('tenant_name') + '_in', router_id,
                    in_net, in_sub, in_seg, 'down')
                if not ret:
                    LOG.error(_LE("Error case, Sending router port message "
                                  "failed for in network tenant %(tenant)s "
                                  "subnet %(seg)s"),
                              {'tenant': tenant_id, 'seg': in_seg})
                self.delete_intf_router(tenant_id, arg_dict.get('tenant_name'),
                                        router_id)
            return False
        return True

    def program_next_hop(self, tenant_id, arg_dict):
        "Program the next hop for all host subnets to the 'in' gateway. """
        if arg_dict.get('in_gw') != 0:
            ret = self.os_helper.program_rtr_all_nwk_next_hop(
                tenant_id, arg_dict.get('router_id'), arg_dict.get('in_gw'),
                arg_dict.get('excl_list'))
            if not ret:
                LOG.error(_LE("Unable to program default router next hop %s"),
                          arg_dict.get('router_id'))
                self.delete_intf_router(tenant_id, arg_dict.get('tenant_name'),
                                        arg_dict.get('router_id'))
                return False
        return True

    def program_default_gw(self, tenant_id, arg_dict):
        "Program the default gateway to the 'out' interface. """
        ret = False
        attempt = 0
        if arg_dict.get('out_gw') != 0:
            while not ret and attempt <= 3:
                time.sleep(5)
                ret = self.os_helper.program_rtr_default_gw(
                    tenant_id, arg_dict.get('router_id'),
                    arg_dict.get('out_gw'))
                attempt += 1
        if not ret:
            LOG.error(_LE("Unable to program default GW in router %s"),
                      arg_dict.get('router_id'))
            self.delete_intf_router(tenant_id, arg_dict.get('tenant_name'),
                                    arg_dict.get('router_id'))
            return False
        return True

    def update_dcnm_partition_static_route(self, tenant_id, arg_dict):
        """Add static route in DCNM's partition.

        This gets pushed to the relevant leaf switches.
        """
        ip_list = self.os_helper.get_subnet_nwk_excl(tenant_id,
                                                     arg_dict.get('excl_list'))
        srvc_node_ip = self.get_out_srvc_node_ip_addr(tenant_id)
        ret = self.dcnm_obj.update_partition_static_route(
            arg_dict.get('tenant_name'), fw_const.SERV_PART_NAME, ip_list,
            vrf_prof=self.cfg.firewall.fw_service_part_vrf_profile,
            service_node_ip=srvc_node_ip)
        if not ret:
            LOG.error(_LE("Unable to update DCNM ext profile with static "
                          "route %s"), arg_dict.get('router_id'))
            self.delete_intf_router(tenant_id, arg_dict.get('tenant_name'),
                                    arg_dict.get('router_id'))
            return False
        return True

    def _create_arg_dict(self, tenant_id, data, in_sub, out_sub):
        """Create the argument dictionary. """
        in_seg, in_vlan = self.get_in_seg_vlan(tenant_id)
        out_seg, out_vlan = self.get_out_seg_vlan(tenant_id)
        in_ip_dict = self.get_in_ip_addr(tenant_id)
        out_ip_dict = self.get_out_ip_addr(tenant_id)
        excl_list = [in_ip_dict.get('subnet'), out_ip_dict.get('subnet')]

        arg_dict = {'tenant_id': tenant_id,
                    'tenant_name': data.get('tenant_name'),
                    'in_seg': in_seg, 'in_vlan': in_vlan,
                    'out_seg': out_seg, 'out_vlan': out_vlan,
                    'router_id': data.get('router_id'),
                    'in_sub': in_sub, 'out_sub': out_sub,
                    'in_gw': in_ip_dict.get('gateway'),
                    'out_gw': out_ip_dict.get('gateway'),
                    'excl_list': excl_list}
        return arg_dict

    def _create_fw(self, tenant_id, data):
        """Internal routine that gets called when a FW is created. """
        LOG.debug("In creating Native FW data is %s", data)
        # TODO(padkrish):
        # Check if router is already added and only then add, needed for
        # restart cases since native doesn't have a special DB
        ret, in_sub, out_sub = self.attach_intf_router(tenant_id,
                                                       data.get('tenant_name'),
                                                       data.get('router_id'))
        if not ret:
            LOG.error(_LE("Native FW: Attach intf router failed for tenant "
                          "%s"), tenant_id)
            return False

        self.create_tenant_dict(tenant_id, data.get('router_id'))
        arg_dict = self._create_arg_dict(tenant_id, data, in_sub, out_sub)

        # Program DCNM to update profile's static IP address on OUT part
        ret = self.update_dcnm_partition_static_route(tenant_id, arg_dict)
        if not ret:
            return False
        # Program the default GW in router namespace
        ret = self.program_default_gw(tenant_id, arg_dict)
        if not ret:
            return False

        # Program router namespace to have all tenant networks to be routed
        # to IN service network
        ret = self.program_next_hop(tenant_id, arg_dict)
        if not ret:
            return False

        # Send message for router port auto config for in service nwk
        ret = self.send_in_router_port_msg(tenant_id, arg_dict, 'up')
        if not ret:
            return False

        # Send message for router port auto config for out service nwk
        return self.send_out_router_port_msg(tenant_id, arg_dict, 'up')

    def create_fw(self, tenant_id, data):
        """Top level routine called when a FW is created. """
        try:
            return self._create_fw(tenant_id, data)
        except Exception as exc:
            LOG.error(_LE("Failed to create FW for device native, tenant "
                          "%(tenant)s data %(data)s Exc %(exc)s"),
                      {'tenant': tenant_id, 'data': data, 'exc': exc})
            return False

    def _delete_fw(self, tenant_id, data):
        """Internal routine called when a FW is deleted. """
        LOG.debug("In Delete fw data is %s", data)
        in_sub = self.get_in_subnet_id(tenant_id)
        out_sub = self.get_out_subnet_id(tenant_id)
        arg_dict = self._create_arg_dict(tenant_id, data, in_sub, out_sub)

        if arg_dict.get('router_id') is None:
            LOG.error(_LE("Router ID unknown for tenant %s"), tenant_id)
            return False

        if tenant_id not in self.tenant_dict:
            self.create_tenant_dict(tenant_id, arg_dict.get('router_id'))
        ret = self.send_in_router_port_msg(tenant_id, arg_dict, 'down')
        if not ret:
            return False
        ret = self.send_out_router_port_msg(tenant_id, arg_dict, 'down')
        if not ret:
            return False
        # Usually sending message to queue doesn't fail!!!

        router_ret = self.delete_intf_router(tenant_id,
                                             arg_dict.get('tenant_name'),
                                             arg_dict.get('router_id'))
        if not router_ret:
            LOG.error(_LE("Unable to delete router for tenant %s, error case"),
                      tenant_id)
            return router_ret
        del self.tenant_dict[tenant_id]
        return router_ret

    def delete_fw(self, tenant_id, data):
        """Top level routine called when a FW is deleted. """
        try:
            ret = self._delete_fw(tenant_id, data)
            return ret
        except Exception as exc:
            LOG.error(_LE("Failed to delete FW for device native, tenant "
                          "%(tenant)s data %(data)s Exc %(exc)s"),
                      {'tenant': tenant_id, 'data': data, 'exc': exc})
            return False

    def modify_fw(self, tenant_id, data):
        """Modify Firewall attributes.

        Routine called when Firewall attributes gets modified. Nothing to be
        done for native FW.
        """
        LOG.debug("In Modify fw data is %s", data)

    def _program_dcnm_static_route(self, tenant_id, tenant_name):
        """Program DCNM Static Route. """
        in_ip_dict = self.get_in_ip_addr(tenant_id)
        in_gw = in_ip_dict.get('gateway')
        in_ip = in_ip_dict.get('subnet')
        if in_gw is None:
            LOG.error(_LE("No FW service GW present"))
            return False
        out_ip_dict = self.get_out_ip_addr(tenant_id)
        out_ip = out_ip_dict.get('subnet')

        # Program DCNM to update profile's static IP address on OUT part
        excl_list = []
        excl_list.append(in_ip)
        excl_list.append(out_ip)
        subnet_lst = self.os_helper.get_subnet_nwk_excl(tenant_id, excl_list,
                                                        excl_part=True)
        # This count is for telling DCNM to insert the static route in a
        # particular position. Total networks created - exclusive list as
        # above - the network that just got created.
        srvc_node_ip = self.get_out_srvc_node_ip_addr(tenant_id)
        ret = self.dcnm_obj.update_partition_static_route(
            tenant_name, fw_const.SERV_PART_NAME, subnet_lst,
            vrf_prof=self.cfg.firewall.fw_service_part_vrf_profile,
            service_node_ip=srvc_node_ip)
        if not ret:
            LOG.error(_LE("Unable to update DCNM ext profile with static "
                          "route"))
            return False
        return True

    def network_create_notif(self, tenant_id, tenant_name, cidr):
        """Tenant Network create Notification.

        Restart is not supported currently for this. fixme(padkrish).
        """
        router_id = self.get_router_id(tenant_id, tenant_name)
        if not router_id:
            LOG.error(_LE("Rout ID not present for tenant"))
            return False
        ret = self._program_dcnm_static_route(tenant_id, tenant_name)
        if not ret:
            LOG.error(_LE("Program DCNM with static routes failed "
                          "for router %s"), router_id)
            return False

        # Program router namespace to have this network to be routed
        # to IN service network
        in_ip_dict = self.get_in_ip_addr(tenant_id)
        in_gw = in_ip_dict.get('gateway')
        if in_gw is None:
            LOG.error(_LE("No FW service GW present"))
            return False
        ret = self.os_helper.program_rtr_nwk_next_hop(router_id, in_gw, cidr)
        if not ret:
            LOG.error(_LE("Unable to program default router next hop %s"),
                      router_id)
            return False
        return True

    def network_delete_notif(self, tenant_id, tenant_name, network_id):
        """Tenant Network delete Notification.

        Restart is not supported currently for this. fixme(padkrish).
        """
        router_id = self.get_router_id(tenant_id, tenant_name)
        if router_id is None:
            LOG.error(_LE("Rout ID not present for tenant"))
            return False
        ret = self._program_dcnm_static_route(tenant_id, tenant_name)
        if not ret:
            LOG.error(_LE("Program DCNM with static routes failed for "
                          "router %s"), router_id)
            return False

        # Program router namespace to have this network to be routed
        # to IN service network
        in_ip_dict = self.get_in_ip_addr(tenant_id)
        in_gw = in_ip_dict.get('gateway')
        in_ip = in_ip_dict.get('subnet')
        if in_gw is None:
            LOG.error(_LE("No FW service GW present"))
            return False
        out_ip_dict = self.get_out_ip_addr(tenant_id)
        out_ip = out_ip_dict.get('subnet')
        excl_list = []
        excl_list.append(in_ip)
        excl_list.append(out_ip)
        subnet_lst = self.os_helper.get_subnet_nwk_excl(tenant_id, excl_list,
                                                        excl_part=True)
        ret = self.os_helper.remove_rtr_nwk_next_hop(router_id, in_gw,
                                                     subnet_lst, excl_list)
        if not ret:
            LOG.error(_LE("Unable to program default router next hop %s"),
                      router_id)
            return False
        return True
