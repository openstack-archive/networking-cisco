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

import mock

from neutron.agent import dhcp_agent
from neutron.tests import base

from oslo_config import cfg

from networking_cisco.plugins.cisco.cpnr.dhcp_driver import OPTS
from networking_cisco.plugins.cisco.cpnr import dhcpopts
from networking_cisco.plugins.cisco.cpnr import model
from networking_cisco.tests.unit.cisco.cpnr import fake_networks

dhcp_agent.register_options(cfg.CONF)
cfg.CONF.register_opts(OPTS, 'cisco_pnr')


class TestModel(base.BaseTestCase):

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_network_init(self, mock_client):
        net = model.Network.from_neutron(fake_networks.fake_net1)
        self.assertIsInstance(net, model.Network)
        self.assertFalse(mock_client.called)

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_network_create(self, mock_client):
        net = model.Network.from_neutron(fake_networks.fake_net1)
        net.create()

        # Validate call to CpnrClient.update_vpn
        netid = fake_networks.fake_net1.id
        expected = {'name': netid,
                    'description': netid,
                    'id': model.Vpn.net_to_vpn_id(netid),
                    'vpnId': model.Vpn.net_to_vpn_rfc(netid)}
        mock_client.return_value.update_vpn.assert_called_once_with(
            netid, expected)

        # Validate call to CpnrClient.update_view
        viewid = model.View.net_to_view_id(netid)
        expected = {'name': netid,
                    'viewId': viewid,
                    'priority': viewid}
        mock_client.return_value.update_dns_view.assert_called_once_with(
            netid, expected)

        # Validate call to CpnrClient.update_ccm_zone
        expected = {'origin': 'openstacklocal.',
                    'nameservers': {'stringItem': ['localhost.']},
                    'ns': 'localhost.',
                    'person': 'test.example.com.',
                    'serial': '1',
                    'viewId': viewid}
        mock_client.return_value.update_ccm_zone.assert_called_once_with(
            expected['origin'], expected, viewid=viewid)

        # Validate call to CpnrClient.update_ccm_reverse_zone (reuse fw zone)
        expected['origin'] = '9.9.172.in-addr.arpa.'
        expected['description'] = fake_networks.fake_subnet1.id
        mock_client.return_value.\
            update_ccm_reverse_zone.assert_called_once_with(
                expected['origin'], expected, viewid=viewid)

        # Validate call to CpnrClient.update_scope
        range_list = {'RangeItem': [{'start': '172.9.9.9',
                                     'end': '172.9.9.9'}]}
        policy = model.Policy.from_neutron_subnet(
            fake_networks.fake_net1, fake_networks.fake_subnet1)
        expected = {'name': fake_networks.fake_subnet1.id,
                    'vpnId': model.Vpn.net_to_vpn_id(netid),
                    'subnet': '172.9.9.0/24',
                    'rangeList': range_list,
                    'restrictToReservations': 'enabled',
                    'embeddedPolicy': policy.data}
        mock_client.return_value.update_scope.assert_called_once_with(
            expected['name'], expected)

        # Validate call to CpnrClient.update_client_entry
        policy = model.Policy.from_neutron_port(
            fake_networks.fake_net1, fake_networks.fake_port1)
        netportid = "%s+%s" % (netid, fake_networks.fake_port1.id)
        expected = {'clientClassName': 'openstack-client-class',
                    'name': '01:ab:12:34:56:78:90:ab:aa:bb:cc:dd:ee:ff',
                    'hostName': 'host-172-9-9-9',
                    'domainName': 'openstacklocal',
                    'reservedAddresses': {'stringItem': ['172.9.9.9']},
                    'embeddedPolicy': policy.data,
                    'userDefined': netportid}
        mock_client.return_value.update_client_entry.assert_called_once_with(
            expected['name'], expected)

        # Validate call to CpnrClient.update_ccm_host
        expected = {'name': 'host-172-9-9-9',
                    'zoneOrigin': 'openstacklocal.',
                    'addrs': {'stringItem': ['172.9.9.9']}}
        mock_client.return_value.update_ccm_host.assert_called_once_with(
            expected['name'], expected,
            viewid=viewid, zoneid=expected['zoneOrigin'])

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_port_add(self, mock_client):
        old = model.Network.from_neutron(fake_networks.fake_net1)
        new = model.Network.from_neutron(fake_networks.fake_net2)
        old.update(new)

        # Validate that only port-related objects updated
        self.assertFalse(mock_client.return_value.update_vpn.called)
        self.assertFalse(mock_client.return_value.update_dns_view.called)
        self.assertFalse(mock_client.return_value.update_ccm_zone.called)
        self.assertFalse(mock_client.return_value.
            update_ccm_reverse_zone.called)

        # Validate call to CpnrClient.update_scope
        range_list = {'RangeItem': [{'start': '172.9.9.9',
                                     'end': '172.9.9.10'}]}
        policy = model.Policy.from_neutron_subnet(
            fake_networks.fake_net2, fake_networks.fake_subnet1)
        expected = {'name': fake_networks.fake_subnet1.id,
                    'vpnId': model.Vpn.net_to_vpn_id(
                        fake_networks.fake_net2.id),
                    'subnet': '172.9.9.0/24',
                    'rangeList': range_list,
                    'restrictToReservations': 'enabled',
                    'embeddedPolicy': policy.data}
        mock_client.return_value.update_scope.assert_called_once_with(
            expected['name'], expected)

        # Validate call to CpnrClient.update_client_entry
        netid = fake_networks.fake_net2.id
        policy = model.Policy.from_neutron_port(
            fake_networks.fake_net2, fake_networks.fake_port2)
        netportid = "%s+%s" % (netid, fake_networks.fake_port2.id)
        expected = {'clientClassName': 'openstack-client-class',
                    'name': '01:ab:12:34:56:78:90:ab:aa:bb:cc:dd:ee:99',
                    'hostName': 'host-172-9-9-10',
                    'domainName': 'openstacklocal',
                    'reservedAddresses': {'stringItem': ['172.9.9.10']},
                    'embeddedPolicy': policy.data,
                    'userDefined': netportid}
        mock_client.return_value.update_client_entry.assert_called_once_with(
            expected['name'], expected)

        # Validate call to CpnrClient.update_ccm_host
        viewid = model.View.net_to_view_id(netid)
        expected = {'name': 'host-172-9-9-10',
                    'zoneOrigin': 'openstacklocal.',
                    'addrs': {'stringItem': ['172.9.9.10']}}
        mock_client.return_value.update_ccm_host.assert_called_once_with(
            expected['name'], expected,
            viewid=viewid, zoneid=expected['zoneOrigin'])

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_port_remove(self, mock_client):
        old = model.Network.from_neutron(fake_networks.fake_net2)
        new = model.Network.from_neutron(fake_networks.fake_net1)
        old.update(new)

        # Validate that only port-related objects updated
        self.assertFalse(mock_client.return_value.delete_vpn.called)
        self.assertFalse(mock_client.return_value.delete_dns_view.called)
        self.assertFalse(mock_client.return_value.delete_ccm_zone.called)
        self.assertFalse(
            mock_client.return_value.delete_ccm_reverse_zone.called)

        # Validate call to CpnrClient.update_scope
        range_list = {'RangeItem': [{'start': '172.9.9.9',
                                     'end': '172.9.9.9'}]}
        policy = model.Policy.from_neutron_subnet(
            fake_networks.fake_net1, fake_networks.fake_subnet1)
        expected = {'name': fake_networks.fake_subnet1.id,
                    'vpnId': model.Vpn.net_to_vpn_id(
                        fake_networks.fake_net1.id),
                    'subnet': '172.9.9.0/24',
                    'rangeList': range_list,
                    'restrictToReservations': 'enabled',
                    'embeddedPolicy': policy.data}
        mock_client.return_value.update_scope.assert_called_once_with(
            expected['name'], expected)

        # Validate call to CpnrClient.delete_client_entry
        mock_client.return_value.delete_client_entry.assert_called_once_with(
            '01:ab:12:34:56:78:90:ab:aa:bb:cc:dd:ee:99')

        # Validate call to CpnrClient.release_address
        netid = fake_networks.fake_net2.id
        vpnid = model.Vpn.net_to_vpn_id(netid)
        mock_client.return_value.release_address('172.9.9.10', vpnid)

        # Validate call to CpnrClient.delete_ccm_host
        viewid = model.View.net_to_view_id(netid)
        mock_client.return_value.delete_ccm_host.assert_called_once_with(
            'host-172-9-9-10', viewid=viewid, zoneid='openstacklocal.')

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_network_delete(self, mock_client):
        net = model.Network.from_neutron(fake_networks.fake_net1)
        net.delete()

        # Validate call to CpnrClient.delete_vpn
        netid = fake_networks.fake_net1.id
        mock_client.return_value.delete_vpn.assert_called_once_with(netid)

        # Validate call to CpnrClient.delete_view
        viewid = model.View.net_to_view_id(netid)
        mock_client.return_value.delete_dns_view.assert_called_once_with(netid)

        # Validate call to CpnrClient.delete_ccm_zone
        mock_client.return_value.delete_ccm_zone.assert_called_once_with(
            'openstacklocal.', viewid=viewid)

        # Validate call to CpnrClient.delete_ccm_reverse_zone
        mock_client.return_value.\
            delete_ccm_reverse_zone.assert_called_once_with(
                '9.9.172.in-addr.arpa.', viewid=viewid)

        # Validate call to CpnrClient.delete_scope
        mock_client.return_value.delete_scope.assert_called_once_with(
            fake_networks.fake_subnet1.id)

        # Validate call to CpnrClient.delete_client_entry
        mock_client.return_value.delete_client_entry.assert_called_once_with(
            '01:ab:12:34:56:78:90:ab:aa:bb:cc:dd:ee:ff')

        # Validate call to CpnrClient.release_address
        vpnid = model.Vpn.net_to_vpn_id(netid)
        mock_client.return_value.release_address('172.9.9.9', vpnid)

        # Validate call to CpnrClient.delete_ccm_host
        mock_client.return_value.delete_ccm_host.assert_called_once_with(
            'host-172-9-9-9', viewid=viewid, zoneid='openstacklocal.')

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_reload(self, mock_client):
        mock_client.return_value.reload_needed.return_value = False
        self.assertFalse(model.reload_needed())
        mock_client.return_value.reload_needed.return_value = True
        self.assertTrue(model.reload_needed())

        mock_client.return_value.get_version.return_value = "1"
        mock_client.return_value.get_dhcp_server.return_value = {
            'name': 'fake'}
        mock_client.return_value.get_dns_server.return_value = {
            'name': 'fake'}
        model.reload_server()
        self.assertTrue(mock_client.return_value.reload_server.called)

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_get_version(self, mock_client):
        (mock_client.return_value.get_version.
            return_value) = "CPNR Version 8.3.3"
        ver = model.get_version()
        self.assertEqual('8.3.3', ver)

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_recover_networks(self, mock_client):
        # Setup return values for get functions
        net = model.Network.from_neutron(fake_networks.fake_net2)
        mock_client.return_value.get_vpns.return_value = [net.vpn.data]
        mock_client.return_value.get_scopes.return_value = \
            [s.data for s in net.scopes.values()]
        mock_client.return_value.get_client_entries.return_value = \
            [ce.data for ce in net.client_entries.values()]
        mock_client.return_value.get_dns_views.return_value = [net.view.data]
        mock_client.return_value.get_ccm_zones.return_value = \
            [fz.data for fz in net.forward_zones.values()]
        mock_client.return_value.get_ccm_reverse_zones.return_value = \
            [rz.data for rz in net.reverse_zones.values()]
        mock_client.return_value.get_ccm_hosts.return_value = \
            [h.data for h in net.hosts.values()]

        # Extract key identifiers
        netid = fake_networks.fake_net2.id
        vpnid = net.vpn.data['id']
        viewid = net.view.data['viewId']
        zoneid = 'openstacklocal.'

        # Invoke recover_networks function
        networks = model.recover_networks()
        self.assertIn(netid, networks)
        rec = networks[netid]

        # Validate get functions are called as expected
        mock_client.return_value.get_vpns.assert_called_once_with()
        mock_client.return_value.get_scopes.assert_called_once_with(vpnid)
        mock_client.return_value.get_client_entries.assert_called_once_with()
        mock_client.return_value.get_dns_views.assert_called_once_with()
        mock_client.return_value.\
            get_ccm_zones.assert_called_once_with(viewid=viewid)
        mock_client.return_value.get_ccm_reverse_zones.assert_called_once_with(
            viewid=viewid)
        mock_client.return_value.get_ccm_hosts(viewid=viewid, zoneid=zoneid)

        # Validate that recover_networks returned correct data
        self.assertEqual(net.vpn.data, rec.vpn.data)
        self.assertEqual(net.view.data, rec.view.data)
        for scopeid in net.scopes:
            self.assertIn(scopeid, rec.scopes)
            self.assertEqual(net.scopes[scopeid].data,
                             rec.scopes[scopeid].data)
        for clientid in net.client_entries:
            self.assertIn(clientid, rec.client_entries)
            self.assertEqual(net.client_entries[clientid].data,
                             rec.client_entries[clientid].data)
        for fzid in net.forward_zones:
            self.assertIn(fzid, rec.forward_zones)
            self.assertEqual(net.forward_zones[fzid].data,
                             rec.forward_zones[fzid].data)
        for rzid in net.reverse_zones:
            self.assertIn(rzid, rec.reverse_zones)
            self.assertEqual(net.reverse_zones[rzid].data,
                             rec.reverse_zones[rzid].data)
        for hostid in net.hosts:
            self.assertIn(hostid, rec.hosts)
            self.assertEqual(net.hosts[hostid].data,
                             rec.hosts[hostid].data)

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_policy_from_port(self, mock_client):
        policy = model.Policy.from_neutron_port(fake_networks.fake_net1,
                                                fake_networks.fake_port1)
        opts_list = fake_networks.fake_port1.extra_dhcp_opts
        opt_list_pnr_format = [dhcpopts.format_for_pnr(opts_list[i].opt_name,
                                                       opts_list[i].opt_value)
                               for i in range(len(opts_list))]
        expected = {'OptionItem': opt_list_pnr_format}
        self.assertEqual(expected, policy.data['optionList'])

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_policy_from_subnet(self, mock_client):
        fake_network = fake_networks.fake_net1
        fake_subnet = fake_networks.fake_subnet1
        policy = model.Policy.from_neutron_subnet(fake_network, fake_subnet)
        # DNS servers and static routes should correspond to values in
        # fake_networks.fake_subnet1
        fake_policy_opts = [('routers', fake_subnet.gateway_ip),
                            ('domain-name-servers', '8.8.8.8'),
                            ('classless-static-routes',
                                '18:28:00:01:28:00:00:02'),
                            ('dhcp-lease-time',
                             str(cfg.CONF.dhcp_lease_duration)),
                            ('domain-name', cfg.CONF.dhcp_domain)]
        policy_list_pnr_format = [dhcpopts.format_for_pnr(name, val)
                                  for name, val in fake_policy_opts]
        expected = {'OptionItem': policy_list_pnr_format}
        self.assertEqual(expected, policy.data['optionList'])

    @mock.patch.object(model, "_get_client", autospec=True)
    def test_scope_from_subnet(self, mock_client):
        policy = model.Policy.from_neutron_subnet(
            fake_networks.fake_net3, fake_networks.fake_subnet1)
        range_list = {'RangeItem': [{'start': '172.9.9.11',
                                     'end': '172.9.9.13'},
                                    {'start': '172.9.9.18',
                                     'end': '172.9.9.18'}]}
        expected = {'name': fake_networks.fake_subnet1.id,
                    'vpnId': model.Vpn.net_to_vpn_id(
                        fake_networks.fake_net3.id),
                    'subnet': '172.9.9.0/24',
                    'rangeList': range_list,
                    'restrictToReservations': 'enabled',
                    'embeddedPolicy': policy.data}
        scope = model.Scope.from_neutron(fake_networks.fake_net3,
                                         fake_networks.fake_subnet1)
        self.assertEqual(expected, scope.data)
