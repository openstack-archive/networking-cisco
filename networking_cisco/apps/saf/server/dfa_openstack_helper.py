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

from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import dfa_sys_lib as utils
from networking_cisco.apps.saf.server import dfa_events_handler as deh

from networking_cisco._i18n import _LE

LOG = logging.getLogger(__name__)


class DfaNeutronHelper(object):

    """Helper Routines for Neutron. """

    def __init__(self):
        """Initialization. """
        self.neutron_help = deh.EventsHandler('neutron', None, 20, 25)
        cfg = config.CiscoDFAConfig('neutron').cfg
        self.root_helper = cfg.sys.root_helper

    @property
    def neutronclient(self):
        """Returns client object. """
        return self.neutron_help.nclient

    def create_network(self, name, tenant_id, subnet, gw=None):
        """Create the openstack network, including the subnet. """

        try:
            body = {'network': {'name': name, 'tenant_id': tenant_id,
                                'admin_state_up': True}}
            netw = self.neutronclient.create_network(body=body)
            net_dict = netw.get('network')
            net_id = net_dict.get('id')
        except Exception as exc:
            LOG.error(_LE("Failed to create network %(name)s, Exc %(exc)s"),
                      {'name': name, 'exc': str(exc)})
            return None, None

        try:
            if gw is None:
                body = {'subnet': {'cidr': subnet,
                                   'ip_version': 4,
                                   'network_id': net_id,
                                   'tenant_id': tenant_id,
                                   'enable_dhcp': False}}
            else:
                body = {'subnet': {'cidr': subnet,
                                   'ip_version': 4,
                                   'network_id': net_id,
                                   'tenant_id': tenant_id,
                                   'enable_dhcp': False,
                                   'gateway_ip': gw}}
            subnet_ret = self.neutronclient.create_subnet(body=body)
            subnet_dict = subnet_ret.get('subnet')
            subnet_id = subnet_dict.get('id')
        except Exception as exc:
            LOG.error(_LE("Failed to create subnet %(sub)s, exc %(exc)s"),
                      {'sub': subnet, 'exc': str(exc)})
            try:
                self.neutronclient.delete_network(net_id)
            except Exception as exc:
                LOG.error(_LE("Failed to delete network %(net)s, exc %(exc)s"),
                          {'net': net_id, 'exc': str(exc)})
            return None, None
        return net_id, subnet_id

    def delete_network(self, name, tenant_id, subnet_id, net_id):
        """Delete the openstack subnet and network. """
        try:
            self.neutronclient.delete_subnet(subnet_id)
        except Exception as exc:
            LOG.error(_LE("Failed to delete subnet %(sub)s exc %(exc)s"),
                      {'sub': subnet_id, 'exc': str(exc)})
            return
        try:
            self.neutronclient.delete_network(net_id)
        except Exception as exc:
            LOG.error(_LE("Failed to delete network %(name)s exc %(exc)s"),
                      {'name': name, 'exc': str(exc)})

    # Pass
    def delete_network_all_subnets(self, net_id):
        """Delete the openstack network including all its subnets. """
        try:
            body = {'network_id': net_id}
            subnet_list = self.neutronclient.list_subnets(body=body)
            subnet_list = subnet_list.get('subnets')
            for subnet in subnet_list:
                if subnet.get('network_id') == net_id:
                    subnet_id = subnet.get('id')
                    self.neutronclient.delete_subnet(subnet_id)
        except Exception as exc:
            LOG.error(_LE("Failed to delete subnet for net %(net)s "
                      "Exc %(exc)s"), {'net': net_id, 'exc': str(exc)})
            return False
        try:
            self.neutronclient.delete_network(net_id)
        except Exception as exc:
            LOG.error(_LE("Failed to delete network %(net)s Exc %(exc)s"),
                      {'net': net_id, 'exc': str(exc)})
            return False
        return True

    def is_subnet_present(self, subnet_addr):
        """Returns if a subnet is present. """
        try:
            subnet_list = self.neutronclient.list_subnets(body={})
            subnet_dat = subnet_list.get('subnets')
            for sub in subnet_dat:
                if sub.get('cidr') == subnet_addr:
                    return True
            return False
        except Exception as exc:
            LOG.error(_LE("Failed to list subnet %(sub)s, Exc %(exc)s"),
                      {'sub': subnet_addr, 'exc': str(exc)})
            return False

    def get_all_subnets_cidr(self, no_mask=False):
        """Returns all the subnets. """
        body = {}
        subnet_cidrs = []
        try:
            subnet_list = self.neutronclient.list_subnets(body=body)
            subnet_dat = subnet_list.get('subnets')
            for sub in subnet_dat:
                if no_mask:
                    subnet_cidrs.append(sub.get('cidr').split('/')[0])
                else:
                    subnet_cidrs.append(sub.get('cidr'))
        except Exception as exc:
            LOG.error(_LE("Failed to list subnet Exc %s"), str(exc))
        return subnet_cidrs

    def get_subnets_for_net(self, net):
        """Returns the subnets in a network. """
        try:
            subnet_list = self.neutronclient.list_subnets(network_id=net)
            subnet_dat = subnet_list.get('subnets')
            return subnet_dat
        except Exception as exc:
            LOG.error(_LE("Failed to list subnet net %(net)s, Exc: %(exc)s"),
                      {'net': net, 'exc': str(exc)})
            return None

    def get_subnet_cidr(self, subnet_id):
        """retrieve the CIDR associated with a subnet, given its ID. """
        try:
            subnet_list = self.neutronclient.list_subnets(id=subnet_id)
            subnet_dat = subnet_list.get('subnets')[0]
            return subnet_dat.get('cidr')
        except Exception as exc:
            LOG.error(_LE("Failed to list subnet for ID %(subnet)s, "
                          "exc %(exc)s"), {'subnet': subnet_id, 'exc': exc})
            return None

    def delete_network_subname(self, sub_name):
        """Delete the network by part of its name, use with caution. """
        try:
            body = {}
            net_list = self.neutronclient.list_networks(body=body)
            for net in net_list:
                if net.get('name').find(sub_name) != -1:
                    self.delete_network_all_subnets(net.get('net_id'))
        except Exception as exc:
            LOG.error(_LE("Failed to get network by subname %(name)s, "
                          "Exc %(exc)s"),
                      {'name': sub_name, 'exc': str(exc)})

    def get_network_by_name(self, nwk_name):
        """Search for a openstack network by name. """
        ret_net_lst = []
        try:
            body = {}
            net_list = self.neutronclient.list_networks(body=body)
            net_list = net_list.get('networks')
            for net in net_list:
                if net.get('name') == nwk_name:
                    ret_net_lst.append(net)
        except Exception as exc:
            LOG.error(_LE("Failed to get network by name %(name)s, "
                          "Exc %(exc)s"),
                      {'name': nwk_name, 'exc': str(exc)})
        return ret_net_lst

    def get_network_by_tenant(self, tenant_id):
        """Returns the network of a given tenant. """
        ret_net_lst = []
        try:
            net_list = self.neutronclient.list_networks(body={})
            for net in net_list.get('networks'):
                if net.get('tenant_id') == tenant_id:
                    ret_net_lst.append(net)
        except Exception as exc:
            LOG.error(_LE("Failed to get network by tenant %(tenant)s, "
                          "Exc %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
        return ret_net_lst

    # Tested
    def get_rtr_by_name(self, rtr_name):
        """Search a router by its name. """
        upd_rtr_list = []
        try:
            rtr_list = self.neutronclient.list_routers()
            for rtr in rtr_list.get('routers'):
                if rtr_name == rtr['name']:
                    upd_rtr_list.append(rtr)
        except Exception as exc:
            LOG.error(_LE("Failed to get router by name %(name)s, "
                          "Exc %(exc)s"),
                      {'name': rtr_name, 'exc': str(exc)})
        return upd_rtr_list

    def create_router(self, name, tenant_id, subnet_lst):
        """Create a openstack router and add the interfaces. """
        try:
            body = {'router': {'name': name, 'tenant_id': tenant_id,
                               'admin_state_up': True}}
            router = self.neutronclient.create_router(body=body)
            rout_dict = router.get('router')
            rout_id = rout_dict.get('id')
        except Exception as exc:
            LOG.error(_LE("Failed to create router with name %(name)s"
                          " Exc %(exc)s"), {'name': name, 'exc': str(exc)})
            return None

        ret = self.add_intf_router(rout_id, tenant_id, subnet_lst)
        if not ret:
            try:
                ret = self.neutronclient.delete_router(rout_id)
            except Exception as exc:
                LOG.error(_LE("Failed to delete router %(name)s, Exc %(exc)s"),
                          {'name': name, 'exc': str(exc)})
            return None
        return rout_id

    def add_intf_router(self, rout_id, tenant_id, subnet_lst):
        """Add the interfaces to a router. """
        try:
            for subnet_id in subnet_lst:
                body = {'subnet_id': subnet_id}
                intf = self.neutronclient.add_interface_router(rout_id,
                                                               body=body)
                intf.get('port_id')
        except Exception as exc:
            LOG.error(_LE("Failed to create router intf ID %(id)s,"
                      " Exc %(exc)s"), {'id': rout_id, 'exc': str(exc)})
            return False
        return True

    # Passed
    def delete_router(self, name, tenant_id, rout_id, subnet_lst):
        """Delete the openstack router.

        Delete the router and remove the interfaces attached to it.
        """
        ret = self.delete_intf_router(name, tenant_id, rout_id, subnet_lst)
        if not ret:
            return False

        try:
            ret = self.neutronclient.delete_router(rout_id)
        except Exception as exc:
            LOG.error(_LE("Failed to delete router %(name)s ret %(ret)s "
                          "Exc %(exc)s"),
                      {'name': name, 'ret': str(ret), 'exc': str(exc)})
            return False
        return True

    def delete_intf_router(self, name, tenant_id, rout_id, subnet_lst):
        """Delete the openstack router and remove the interfaces attached. """
        try:
            for subnet_id in subnet_lst:
                body = {'subnet_id': subnet_id}
                intf = self.neutronclient.remove_interface_router(rout_id,
                                                                  body=body)
                intf.get('id')
        except Exception as exc:
            LOG.error(_LE("Failed to delete router interface %(name)s, "
                          " Exc %(exc)s"), {'name': name, 'exc': str(exc)})
            return False
        return True

    def delete_router_by_name(self, rtr_name, tenant_id):
        """Delete the openstack router and its interfaces given its name.

        The interfaces should be already removed prior to calling this
        function.
        """
        try:
            routers = self.neutronclient.list_routers()
            rtr_list = routers.get('routers')
            for rtr in rtr_list:
                if rtr_name == rtr['name']:
                    self.neutronclient.delete_router(rtr['id'])
        except Exception as exc:
            LOG.error(_LE("Failed to get and delete router by name %(name)s, "
                          "Exc %(exc)s"),
                      {'name': rtr_name, 'exc': str(exc)})
            return False
        return True

    def get_router_intf(self, router_id):
        """Retrieve the router interfaces. Incomplete, TODO(padkrish). """
        try:
            body = {}
            self.neutronclient.show_router(router_id, body=body)
        except Exception as exc:
            LOG.error(_LE("Failed to show router interface %(id)s "
                          "Exc %(exc)s"), {'id': router_id, 'exc': str(exc)})
            return
        # Complete fixme(padkrish)

    def get_router_port_subnet(self, subnet_id):
        try:
            body = 'network:router_interface'
            port_data = self.neutronclient.list_ports(device_owner=body)
            port_list = port_data.get('ports')
            for port in port_list:
                sub = port.get('fixed_ips')[0].get('subnet_id')
                if sub == subnet_id:
                    return port
            return None
        except Exception as exc:
            LOG.error(_LE("Failed to get router port subnet %(net)s, "
                          "Exc: %(exc)s"), {'net': subnet_id, 'exc': str(exc)})
            return None

    def get_rtr_name(self, router_id):
        """Retrieve the router name. Incomplete. """
        try:
            body = {}
            router = self.neutronclient.show_router(router_id, body=body)
            return router.get('router').get('name')
        except Exception as exc:
            LOG.error(_LE("Failed to show router interface %(id)s "
                          "Exc %(exc)s"), {'id': router_id, 'exc': str(exc)})

    def find_rtr_namespace(self, rout_id):
        """Find the namespace associated with the router. """
        if rout_id is None:
            return None
        args = ['ip', 'netns', 'list']
        try:
            ns_list = utils.execute(args, root_helper=self.root_helper)
        except Exception as exc:
            LOG.error(_LE("Unable to find the namespace list Exception %s"),
                      exc)
            return None
        for ns in ns_list.split():
            if 'router' in ns and rout_id in ns:
                return ns

    def program_rtr(self, args, rout_id, namespace=None):
        """Execute the command against the namespace. """
        if namespace is None:
            namespace = self.find_rtr_namespace(rout_id)
        if namespace is None:
            LOG.error(_LE("Unable to find namespace for router %s"), rout_id)
            return False
        final_args = ['ip', 'netns', 'exec', namespace] + args
        try:
            utils.execute(final_args, root_helper=self.root_helper)
        except Exception as e:
            LOG.error(_LE("Unable to execute %(cmd)s. "
                      "Exception: %(exception)s"),
                      {'cmd': final_args, 'exception': e})
            return False
        return True

    def program_rtr_return(self, args, rout_id, namespace=None):
        """Execute the command against the namespace and return the result. """
        if namespace is None:
            namespace = self.find_rtr_namespace(rout_id)
        if namespace is None:
            LOG.error(_LE("Unable to find namespace for router %s"), rout_id)
            return False
        final_args = ['ip', 'netns', 'exec', namespace] + args
        try:
            return utils.execute(final_args, root_helper=self.root_helper)
        except Exception as e:
            LOG.error(_LE("Unable to execute %(cmd)s. "
                      "Exception: %(exception)s"),
                      {'cmd': final_args, 'exception': e})
            return None

    def program_rtr_default_gw(self, tenant_id, rout_id, gw):
        """Program the default gateway of a router. """
        args = ['route', 'add', 'default', 'gw', gw]
        ret = self.program_rtr(args, rout_id)
        if not ret:
            LOG.error(_LE("Program router returned error for %s"), rout_id)
            return False
        return True

    def get_subnet_nwk_excl(self, tenant_id, excl_list, excl_part=False):
        """Retrieve the subnets of a network.

        Get the subnets inside a network after applying the exclusion
        list.
        """
        net_list = self.get_network_by_tenant(tenant_id)
        ret_subnet_list = []
        for net in net_list:
            if excl_part:
                name = net.get('name')
                part = name.partition('::')[2]
                if part:
                    continue
            subnet_lst = self.get_subnets_for_net(net.get('id'))
            for subnet_elem in subnet_lst:
                subnet = subnet_elem.get('cidr').split('/')[0]
                subnet_and_mask = subnet_elem.get('cidr')
                if subnet not in excl_list:
                    ret_subnet_list.append(subnet_and_mask)
        return ret_subnet_list

    def program_rtr_all_nwk_next_hop(self, tenant_id, rout_id, next_hop,
                                     excl_list):
        """Program the next hop for all networks of a tenant. """
        namespace = self.find_rtr_namespace(rout_id)
        if namespace is None:
            LOG.error(_LE("Unable to find namespace for router %s"), rout_id)
            return False

        net_list = self.get_network_by_tenant(tenant_id)
        for net in net_list:
            subnet_lst = self.get_subnets_for_net(net.get('id'))
            for subnet_elem in subnet_lst:
                subnet = subnet_elem.get('cidr').split('/')[0]
                subnet_and_mask = subnet_elem.get('cidr')
                if subnet not in excl_list:
                    args = ['route', 'add', '-net', subnet_and_mask, 'gw',
                            next_hop]
                    ret = self.program_rtr(args, rout_id, namespace=namespace)
                    if not ret:
                        LOG.error(_LE("Program router returned error for %s"),
                                  rout_id)
                        return False
        return True

    def program_rtr_nwk_next_hop(self, rout_id, next_hop, cidr):
        """Program the next hop for all networks of a tenant. """
        namespace = self.find_rtr_namespace(rout_id)
        if namespace is None:
            LOG.error(_LE("Unable to find namespace for router %s"), rout_id)
            return False

        args = ['route', 'add', '-net', cidr, 'gw', next_hop]
        ret = self.program_rtr(args, rout_id, namespace=namespace)
        if not ret:
            LOG.error(_LE("Program router returned error for %s"), rout_id)
            return False
        return True

    def remove_rtr_nwk_next_hop(self, rout_id, next_hop, subnet_lst,
                                excl_list):
        """Remove the next hop for all networks of a tenant. """
        namespace = self.find_rtr_namespace(rout_id)
        if namespace is None:
            LOG.error(_LE("Unable to find namespace for router %s"), rout_id)
            return False

        args = ['ip', 'route']
        ret = self.program_rtr_return(args, rout_id, namespace=namespace)
        if ret is None:
            LOG.error(_LE("Get routes return None %s"), rout_id)
            return False
        routes = ret.split('\n')
        concat_lst = subnet_lst + excl_list
        for rout in routes:
            if len(rout) == 0:
                continue
            nwk = rout.split()[0]
            if nwk == 'default':
                continue
            nwk_no_mask = nwk.split('/')[0]
            if nwk_no_mask not in concat_lst and nwk not in concat_lst:
                args = ['route', 'del', '-net', nwk, 'gw', next_hop]
                ret = self.program_rtr(args, rout_id, namespace=namespace)
                if not ret:
                    LOG.error(_LE("Program router returned error for %s"),
                              rout_id)
                    return False
        return True

    def get_fw(self, fw_id):
        """Return the Firewall given its ID. """
        fw = None
        try:
            fw = self.neutronclient.show_firewall(fw_id)
        except Exception as exc:
            LOG.error(_LE("Failed to get firewall list for id %(id)s, "
                          "Exc %(exc)s"), {'id': fw_id, 'exc': str(exc)})
        return fw

    # Tested
    def get_fw_rule(self, rule_id):
        """Return the firewall rule, given its ID. """
        rule = None
        try:
            rule = self.neutronclient.show_firewall_rule(rule_id)
        except Exception as exc:
            LOG.error(_LE("Failed to get firewall rule for id %(id)s "
                          "Exc %(exc)s"), {'id': rule_id, 'exc': str(exc)})
        return rule

    # Tested
    def get_fw_policy(self, policy_id):
        """Return the firewall policy, given its ID. """
        policy = None
        try:
            policy = self.neutronclient.show_firewall_policy(policy_id)
        except Exception as exc:
            LOG.error(_LE("Failed to get firewall plcy for id %(id)s "
                          "Exc %(exc)s"),
                      {'id': policy_id, 'exc': str(exc)})
        return policy
