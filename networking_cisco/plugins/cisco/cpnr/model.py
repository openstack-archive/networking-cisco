# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
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

from itertools import groupby
import netaddr
from operator import itemgetter
import time
import uuid

from oslo_config import cfg
from oslo_log import log as logging

from networking_cisco.plugins.cisco.cpnr import cpnr_client
from networking_cisco.plugins.cisco.cpnr import dhcpopts
from networking_cisco._i18n import _LE, _LW
from neutron.agent.linux import dhcp
from neutron_lib import constants

LOG = logging.getLogger(__name__)
RELOAD_TIMEOUT = 120


class Network(object):

    def __init__(self):
        self.vpn = Vpn()
        self.view = View()
        self.forward_zones = {}
        self.scopes = {}
        self.client_entries = {}
        self.reverse_zones = {}
        self.hosts = {}

    @classmethod
    def from_neutron(cls, network):
        net = Network()
        net.vpn = Vpn.from_neutron(network)
        net.view = View.from_neutron(network)
        fz = ForwardZone.from_neutron(network)
        net.forward_zones[fz.data['origin']] = fz
        # Ignore DHCP-disabled and IPv6 subnets
        ipv4_subnet_ids = cls.filter_ipv4_subnets(network.subnets)
        for subnet in network.subnets:
            if subnet.id not in ipv4_subnet_ids:
                continue
            net.scopes[subnet.id] = Scope.from_neutron(network, subnet)
            net.reverse_zones[subnet.id] = ReverseZone.from_neutron(network,
                                                                    subnet)
        for port in network.ports:
            ipv4_port = False
            for ip in port.fixed_ips:
                if ip.subnet_id in ipv4_subnet_ids:
                    ipv4_port = True
                    # Update hosts with only IPv4 fixed IPs
                    hostname = Host.addr_to_hostname(ip.ip_address)
                    net.hosts[hostname] = Host.from_neutron(network,
                                                            ip.ip_address)
            if ipv4_port:
                net.client_entries[port.id] = ClientEntry.from_neutron(
                    network, port)
        return net

    def create(self):
        self.vpn.create()
        self.view.create()
        for fz in self.forward_zones.values():
            fz.create()
        for scope in self.scopes.values():
            scope.create()
        for ce in self.client_entries.values():
            ce.create()
        for rz in self.reverse_zones.values():
            rz.create()
        for host in self.hosts.values():
            host.create()

    def update(self, new):
        self.vpn.update(new.vpn)
        self.view.update(new.view)
        self._update_all(self.forward_zones, new.forward_zones)
        self._update_all(self.scopes, new.scopes)
        self._update_all(self.client_entries, new.client_entries)
        self._update_all(self.reverse_zones, new.reverse_zones)
        self._update_all(self.hosts, new.hosts)

    def _update_all(self, old, new):
        deleted_keys = set(old.keys()) - set(new.keys())
        deleted = (old[key] for key in deleted_keys)
        for d in deleted:
            d.delete()
        created_keys = set(new.keys()) - set(old.keys())
        created = (new[key] for key in created_keys)
        for c in created:
            c.create()
        updated_keys = set(old.keys()) & set(new.keys())
        updated = ((old[key], new[key]) for key in updated_keys)
        for o, n in updated:
            o.update(n)

    def delete(self):
        for host in self.hosts.values():
            host.delete()
        for rz in self.reverse_zones.values():
            rz.delete()
        for ce in self.client_entries.values():
            ce.delete()
        for scope in self.scopes.values():
            scope.delete()
        for fz in self.forward_zones.values():
            fz.delete()
        self.view.delete()
        self.vpn.delete()

    @staticmethod
    def filter_ipv4_subnets(subnets):
        return [subnet.id for subnet in subnets
                if subnet.enable_dhcp and subnet.ip_version == 4]


class Vpn(object):

    def __init__(self, data=None):
        self.data = data or {}

    @classmethod
    def from_neutron(cls, network):
        vpnid = cls.net_to_vpn_id(network.id)
        vpnrfc = cls.net_to_vpn_rfc(network.id)
        data = {'name': network.id,
                'description': network.id,
                'id': vpnid,
                'vpnId': vpnrfc}
        return cls(data)

    @classmethod
    def from_pnr(cls, vpn):
        attrs = ['name', 'description', 'id', 'vpnId']
        vpn = {k: vpn[k] for k in attrs if k in vpn}
        return cls(vpn)

    @staticmethod
    def net_to_vpn_id(netid):
        netid = uuid.UUID(netid)
        return str(netid.int & 0x7fffffff)

    @staticmethod
    def net_to_vpn_rfc(netid):
        netid = uuid.UUID(netid)
        return (netid.hex[-14:-8].lstrip('0') + ':' +
            netid.hex[-8:].lstrip('0'))

    def create(self):
        pnr = _get_client()
        pnr.update_vpn(self.data['name'], self.data)

    def update(self, new):
        pnr = _get_client()
        if self.data != new.data:
            pnr.update_vpn(new.data['name'], new.data)
            self.data = new.data

    def delete(self):
        pnr = _get_client()
        pnr.delete_vpn(self.data['name'])


class Scope(object):

    def __init__(self, data=None):
        self.data = data or {}

    @classmethod
    def from_neutron(cls, network, subnet):
        vpnid = Vpn.net_to_vpn_id(network.id)
        range_list = cls._from_port_list_to_range(network.ports, subnet.id)
        policy = Policy.from_neutron_subnet(network, subnet)
        ipv4_subnets = [sub for sub in network.subnets
                        if sub.enable_dhcp and sub.ip_version == 4]
        primary_subnet = ipv4_subnets[0].cidr
        if (subnet.cidr == primary_subnet):
            data = {'name': subnet.id,
                    'vpnId': vpnid,
                    'subnet': subnet.cidr,
                    'rangeList': range_list,
                    'restrictToReservations': 'enabled',
                    'embeddedPolicy': policy.data}
        else:
            data = {'name': subnet.id,
                    'vpnId': vpnid,
                    'subnet': subnet.cidr,
                    'rangeList': range_list,
                    'restrictToReservations': 'enabled',
                    'embeddedPolicy': policy.data,
                    'primarySubnet': primary_subnet}
        return cls(data)

    @classmethod
    def from_pnr(cls, scope):
        attrs = ['name', 'vpnId', 'subnet', 'rangeList',
                 'restrictToReservations', 'embeddedPolicy',
                 'primarySubnet']
        scope = {k: scope[k] for k in attrs if k in scope}
        return cls(scope)

    @staticmethod
    def _from_port_list_to_range(ports, subnet_id):
        # List of IP addresses as integers
        ip_addrs_int = []
        for port in ports:
            for ip in port.fixed_ips:
                if ip.subnet_id != subnet_id:
                    continue
                ip_addrs_int.append(int(netaddr.IPAddress(ip.ip_address)))
        # Group all consecutive addresses and create ranges
        ip_ranges = []
        for key, group in groupby(enumerate(sorted(ip_addrs_int)),
                                  lambda item: item[0] - item[1]):
            ip_range = list(map(itemgetter(1), group))
            min_range = str(netaddr.IPAddress(ip_range[0]))
            max_range = str(netaddr.IPAddress(ip_range[-1]))
            ip_ranges.append((min_range, max_range))
        range_item = [{'start': start, 'end': end}
                      for (start, end) in ip_ranges]
        range_list = {'RangeItem': range_item}
        return range_list

    def create(self):
        pnr = _get_client()
        pnr.update_scope(self.data['name'], self.data)

    def update(self, new):
        pnr = _get_client()
        if self.data != new.data:
            pnr.update_scope(new.data['name'], new.data)
            self.data = new.data

    def delete(self):
        pnr = _get_client()
        pnr.delete_scope(self.data['name'])


class ClientEntry(object):

    def __init__(self, data=None, vpnid='0'):
        self.data = data or {}
        self.vpnid = vpnid

    @classmethod
    def from_neutron(cls, network, port):
        vpnid = Vpn.net_to_vpn_id(network.id)
        name = cls._gen_client_entry_name(network.id, port.mac_address)

        # Retain only IPv4 fixed IPs
        ipv4_subnet_ids = Network.filter_ipv4_subnets(network.subnets)
        fixed_ips_v4 = [fixed_ip for fixed_ip in port.fixed_ips
                        if fixed_ip.subnet_id in ipv4_subnet_ids]

        hostname = ('host-%s' %
                   (fixed_ips_v4[0].ip_address.replace('.', '-'),))
        addrs = {'stringItem': [alloc.ip_address for alloc in fixed_ips_v4]}
        policy = Policy.from_neutron_port(network, port)
        netportid = "%s+%s" % (network.id, port.id)
        data = {'clientClassName': 'openstack-client-class',
                'name': name,
                'hostName': hostname,
                'domainName': cfg.CONF.dhcp_domain,
                'reservedAddresses': addrs,
                'embeddedPolicy': policy.data,
                'userDefined': netportid}
        return cls(data, vpnid)

    @classmethod
    def from_pnr(cls, ce):
        attrs = ['clientClassName', 'name', 'hostName', 'domainName',
                 'reservedAddresses', 'embeddedPolicy', 'userDefined']
        ce = {k: ce[k] for k in attrs if k in ce}
        (netid, _, _) = ce['userDefined'].partition('+')
        vpnid = Vpn.net_to_vpn_id(netid)
        return cls(ce, vpnid)

    @staticmethod
    def _gen_client_entry_name(netid, macaddr):
        netid = uuid.UUID(netid)
        vpnid = netid.hex[-14:-8] + ':' + netid.hex[-8:]
        vpnid = vpnid.replace(':', '')
        vpnid = ':'.join(vpnid[i:i + 2] for i in range(0, len(vpnid), 2))
        return '01:' + vpnid + ":" + macaddr

    def create(self):
        pnr = _get_client()
        pnr.update_client_entry(self.data['name'], self.data)

    def update(self, new):
        pnr = _get_client()
        if self.data != new.data:
            pnr.update_client_entry(new.data['name'], new.data)
            self.data = new.data

    def delete(self):
        pnr = _get_client()
        pnr.delete_client_entry(self.data['name'])
        for addr in self.data['reservedAddresses']['stringItem']:
            pnr.release_address(addr, self.vpnid)


class Policy(object):

    def __init__(self, data=None):
        self.data = data or {}

    @classmethod
    def from_neutron_subnet(cls, network, subnet):
        options = []
        if subnet.gateway_ip:
            options.append(('routers', subnet.gateway_ip))
        dns_servers = cls._normalize_dns_nameservers(network, subnet)
        if dns_servers:
            options.append(('domain-name-servers', dns_servers))
        static_routes_str = cls._normalize_host_routes(network, subnet)
        static_routes = ""
        if static_routes_str:
            static_routes = dhcpopts.format_for_options(
                            'classless-static-routes', static_routes_str)
        if static_routes:
            options.append(('classless-static-routes', static_routes))
        extra_options = {'dhcp-lease-time': str(cfg.CONF.dhcp_lease_duration),
                         'domain-name': cfg.CONF.dhcp_domain}
        for option in extra_options.items():
            options.append(option)

        opt_list = []
        for name, val in options:
            opt = dhcpopts.format_for_pnr(name, val)
            if opt:
                opt_list.append(opt)

        if opt_list:
            data = {'optionList': {'OptionItem': opt_list}}
        else:
            data = {'optionList': {'list': []}}
        return cls(data)

    @classmethod
    def from_neutron_port(cls, network, port):
        opt_list = []
        if hasattr(port, 'extra_dhcp_opts'):
            for opt in port.extra_dhcp_opts:
                opt = dhcpopts.format_for_pnr(opt.opt_name, opt.opt_value)
                if opt:
                    opt_list.append(opt)

        if opt_list:
            data = {'optionList': {'OptionItem': opt_list}}
        else:
            data = {'optionList': {'list': []}}
        return cls(data)

    @classmethod
    def _normalize_dns_nameservers(cls, network, subnet):
        if not subnet.dns_nameservers:
            for ip in cls._iter_dhcp_ips(network, subnet):
                subnet.dns_nameservers.append(ip)
        return ','.join(subnet.dns_nameservers)

    @classmethod
    def _normalize_host_routes(cls, network, subnet):
        host_routes = []
        isolated_subnets = dhcp.Dnsmasq.get_isolated_subnets(network)
        if (isolated_subnets[subnet.id] and
           cfg.CONF.enable_isolated_metadata and
           subnet.ip_version == 4):
            class HostRoute(object):
                pass
            for ip in cls._iter_dhcp_ips(network, subnet):
                hr = HostRoute()
                hr.nexthop = ip
                hr.destination = '%s/32' % (dhcp.METADATA_DEFAULT_IP,)
                host_routes.append(hr)
        host_routes.extend(subnet.host_routes)
        encoded_routes = []
        for hr in host_routes:
            (subnet, _, mask) = hr.destination.partition("/")
            sigbytes = ((int(mask) - 1) / 8) + 1
            prefix = '.'.join(subnet.split('.')[:int(sigbytes)])
            destination = mask + '.' + prefix
            encoded_routes.append(destination + ' ' + hr.nexthop)
        return ','.join(encoded_routes)

    @staticmethod
    def _iter_dhcp_ips(net, subnet):
        for port in net.ports:
            if port.device_owner != constants.DEVICE_OWNER_DHCP:
                continue
            for ip in port.fixed_ips:
                if ip.subnet_id != subnet.id:
                    continue
                yield ip.ip_address


class View(object):

    def __init__(self, data=None):
        self.data = data or {}

    @classmethod
    def from_neutron(cls, network):
        viewid = cls.net_to_view_id(network.id)
        data = {'name': network.id,
                'viewId': viewid,
                'priority': viewid}
        return cls(data)

    @classmethod
    def from_pnr(cls, view):
        attrs = ['name', 'viewId', 'priority']
        view = {k: view[k] for k in attrs if k in view}
        return cls(view)

    @staticmethod
    def net_to_view_id(netid):
        netid = uuid.UUID(netid)
        return str(netid.int & 0x7fffffff)

    def create(self):
        pnr = _get_client()
        pnr.update_dns_view(self.data['name'], self.data)

    def update(self, new):
        pnr = _get_client()
        if self.data != new.data:
            pnr.update_dns_view(new.data['name'], new.data)
            self.data = new.data

    def delete(self):
        pnr = _get_client()
        pnr.delete_dns_view(self.data['name'])


class ForwardZone(object):

    def __init__(self, data=None):
        self.data = data or {}

    @classmethod
    def from_neutron(cls, network):
        email = cfg.CONF.cisco_pnr.admin_email.replace('@', '.') + '.'
        viewid = View.net_to_view_id(network.id)
        data = {'origin': cfg.CONF.dhcp_domain + '.',
                'nameservers': {'stringItem': ['localhost.']},
                'ns': 'localhost.',
                'person': email,
                'serial': '1',
                'viewId': viewid}
        return cls(data)

    @classmethod
    def from_pnr(cls, zone):
        attrs = ['origin', 'nameservers', 'ns', 'person', 'serial', 'viewId']
        zone = {k: zone[k] for k in attrs if k in zone}
        return cls(zone)

    def create(self, retry_count=10):
        pnr = _get_client()
        # When many CCMZone objects are created at the same time,
        # HTTP error code 500 is returned (AX_CCM_DB_UNAVAIL) sometimes.
        # Hence, need to retry updating failed CCMZone object.
        for i in range(retry_count):
            try:
                pnr.update_ccm_zone(self.data['origin'], self.data,
                                    viewid=self.data['viewId'])
                break
            except Exception:
                time.sleep(1)

    def update(self, new):
        pnr = _get_client()
        if self.data != new.data:
            pnr.update_ccm_zone(new.data['origin'], new.data,
                                viewid=self.data['viewId'])
            self.data = new.data

    def delete(self):
        pnr = _get_client()
        pnr.delete_ccm_zone(self.data['origin'], viewid=self.data['viewId'])


class ReverseZone(object):

    def __init__(self, data=None):
        self.data = data or {}

    @classmethod
    def from_neutron(cls, network, subnet):
        octets = subnet.cidr.partition('/')[0].split('.')
        rzone = '%s.%s.%s.in-addr.arpa.' % (octets[2], octets[1], octets[0])
        email = cfg.CONF.cisco_pnr.admin_email.replace('@', '.') + '.'
        viewid = View.net_to_view_id(network.id)
        data = {'origin': rzone,
                'nameservers': {'stringItem': ['localhost.']},
                'ns': 'localhost.',
                'person': email,
                'serial': '1',
                'viewId': viewid,
                'description': subnet.id}
        return cls(data)

    @classmethod
    def from_pnr(cls, rzone):
        attrs = ['origin', 'nameservers', 'ns', 'person',
                 'serial', 'viewId', 'description']
        rzone = {k: rzone[k] for k in attrs if k in rzone}
        return cls(rzone)

    def create(self):
        pnr = _get_client()
        pnr.update_ccm_reverse_zone(self.data['origin'], self.data,
                                    viewid=self.data['viewId'])

    def update(self, new):
        pnr = _get_client()
        if self.data != new.data:
            pnr.update_ccm_reverse_zone(new.data['origin'], new.data,
                                        viewid=self.data['viewId'])
            self.data = new.data

    def delete(self):
        pnr = _get_client()
        pnr.delete_ccm_reverse_zone(self.data['origin'],
                                    viewid=self.data['viewId'])


class Host(object):

    def __init__(self, data=None, viewid=0):
        self.data = data or {}
        self.viewid = viewid

    @classmethod
    def from_neutron(cls, network, addr):
        viewid = View.net_to_view_id(network.id)
        data = {'name': cls.addr_to_hostname(addr),
                'zoneOrigin': cfg.CONF.dhcp_domain + '.',
                'addrs': {'stringItem': [addr]}}
        return cls(data, viewid)

    @classmethod
    def from_pnr(cls, host, viewid):
        attrs = ['name', 'zoneOrigin', 'addrs']
        host = {k: host[k] for k in attrs if k in host}
        return cls(host, viewid)

    @staticmethod
    def addr_to_hostname(addr):
        return 'host-%s' % addr.replace('.', '-')

    def create(self):
        pnr = _get_client()
        pnr.update_ccm_host(self.data['name'], self.data,
                            viewid=self.viewid,
                            zoneid=self.data['zoneOrigin'])

    def update(self, new):
        pnr = _get_client()
        if self.data != new.data:
            pnr.update_ccm_host(new.data['name'], new.data,
                                viewid=self.viewid,
                                zoneid=self.data['zoneOrigin'])
            self.data = new.data

    def delete(self):
        pnr = _get_client()
        pnr.delete_ccm_host(self.data['name'], viewid=self.viewid,
                            zoneid=self.data['zoneOrigin'])


def _get_client():
    global _pnr_client
    if '_pnr_client' not in globals():
        (addr, _, port) = cfg.CONF.cisco_pnr.http_server.rpartition(":")
        (scheme, _, addr) = addr.rpartition('://')
        if not scheme:
            scheme = 'http'
        user = cfg.CONF.cisco_pnr.http_username
        pswd = cfg.CONF.cisco_pnr.http_password
        insecure = cfg.CONF.cisco_pnr.insecure
        _pnr_client = cpnr_client.CpnrClient(scheme, addr, port, user,
                                             pswd, insecure)
    return _pnr_client


def configure_pnr():
    dhcp_log_settings = ','.join(cfg.CONF.cisco_pnr.dhcp_log_settings)
    dhcp_server_config = {'clientClass': 'enabled',
                          'clientClassLookupId': '"openstack-client-class"',
                          'deleteOrphanedLeases': 'true',
                          'name': 'DHCP',
                          'logSettings': dhcp_log_settings}
    client_class = {'clientLookupId':
                    '(concat (request option 82 151) (request chaddr))',
                    'name': 'openstack-client-class'}
    dns_log_settings = ','.join(cfg.CONF.cisco_pnr.dns_log_settings)
    dns_server_config = {'localPortNum': '5353',
                         'hybridMode': 'true',
                         'hybridOverride': 'exceptions-override-zones',
                         'logSettings': dns_log_settings}
    dns_addrs = [{'addr': a} for a in cfg.CONF.cisco_pnr.upstream_dns_servers]
    dns_forwarder = {'addr': {'DnsIPnPortItem': dns_addrs},
                     'name': '.'}
    email = cfg.CONF.cisco_pnr.admin_email.replace('@', '.')
    dns_zone = {'origin': '.',
                'nameservers': {'stringItem': ['localhost.']},
                'ns': 'localhost.',
                'person': email,
                'serial': '1'}
    try:
        pnr = _get_client()
        pnr.update_dhcp_server(dhcp_server_config)
        pnr.update_client_class(client_class['name'], client_class)
        pnr.update_dns_server(dns_server_config)
        pnr.update_dns_forwarder('%%32%45', dns_forwarder)
        pnr.update_ccm_zone('%%32%45', dns_zone)
    except cpnr_client.CpnrException:
        LOG.error(_LE("Failed to configure CPNR DHCP Server and Client Class"))


def recover_networks():
    networks = {}
    try:
        networks = _unsafe_recover_networks()
    except Exception:
        LOG.exception(_LE("Failed to recover networks. "
                          "CPNR may be unreachable"))
    return networks


def _unsafe_recover_networks():
    pnr = _get_client()
    networks = {}
    try:
        for vpn in pnr.get_vpns():
            net = Network()
            netid = vpn['name']
            net.vpn = Vpn.from_pnr(vpn)
            networks[netid] = net
            try:
                for scope in pnr.get_scopes(vpn['id']):
                    net.scopes[scope['name']] = Scope.from_pnr(scope)
            except Exception:
                LOG.exception(_LE('Failed to read back scopes for '
                                'network %s'), netid)
        for ce in pnr.get_client_entries():
            (netid, _, portid) = ce['userDefined'].partition('+')
            if netid not in networks:
                continue
            net = networks[netid]
            net.client_entries[portid] = ClientEntry.from_pnr(ce)
        for view in pnr.get_dns_views():
            netid = view['name']
            if netid not in networks:
                continue
            net = networks[netid]
            net.view = View.from_pnr(view)
            viewid = view['viewId']
            try:
                for fzone in pnr.get_ccm_zones(viewid=viewid):
                    domain = fzone['origin']
                    net.forward_zones[domain] = ForwardZone.from_pnr(fzone)
                for rz in pnr.get_ccm_reverse_zones(viewid=viewid):
                    subid = rz['description']
                    net.reverse_zones[subid] = ReverseZone.from_pnr(rz)
                for host in pnr.get_ccm_hosts(viewid=viewid, zoneid=domain):
                    net.hosts[host['name']] = Host.from_pnr(host, viewid)
            except Exception:
                LOG.exception(_LE('Failed to read back PNR data for '
                              'network %(network)s view %(view)s'),
                              {'network': netid, 'view': viewid})
    except Exception:
        LOG.exception(_LE('Failed to recover networks from PNR'))
    return networks


def get_version():
    version = 0
    try:
        pnr = _get_client()
        verstr = pnr.get_version()
        version = verstr.split()[2]
    except cpnr_client.CpnrException:
        LOG.warning(_LW("Failed to obtain CPNR version number"))
    except StandardError:
        LOG.warning(_LW("Failed to parse CPNR version number"))
    LOG.debug("CPNR version: %s", version)
    return version


def reload_needed():
    pnr = _get_client()
    return pnr.reload_needed()


def reload_server(timeout=RELOAD_TIMEOUT):
    pnr = _get_client()
    pnr.reload_server()
    reloaded_time = time.time()
    while time.time() - reloaded_time < timeout:
        try:
            if (pnr.get_version() != '' and
               'name' in pnr.get_dhcp_server() and
               'name' in pnr.get_dns_server()):
                return
        except Exception:
            time.sleep(1)
            continue
    LOG.warning(_LW("PNR timed out after reload, "
                  "timeout: %s seconds"), timeout)
