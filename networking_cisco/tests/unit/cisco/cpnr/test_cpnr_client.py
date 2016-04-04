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
#

from mock import patch
import unittest

from networking_cisco.plugins.cisco.cpnr.cpnr_client import CpnrClient


class TestCpnrClient(unittest.TestCase):

    def setUp(self):
        super(TestCpnrClient, self).setUp()
        self.mock_do_request = patch.object(CpnrClient, '_do_request').start()

    def test_buildurl(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        expected_url = ('http://cpnr.com:8080/web-services/rest/'
                        'resource/t?vpnId=vpn1234?viewId=view123&'
                        'zoneOrigin=test.com')
        return_url = mock_client._build_url('t', 'vpn1234', 'view123',
                        'test.com')
        self.assertEqual(expected_url, return_url)

    def test_get_dhcp_server(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)

        mock_client.get_dhcp_server()
        self.mock_do_request.assert_called_once_with('GET',
                    'http://cpnr.com:8080/web-services/rest/'
                    'resource/DHCPServer')

    def test_get_client_classes(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_client_classes()
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/ClientClass')

    def test_get_client_class(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_client_class('myclientclass')
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'ClientClass/myclientclass')

    def test_get_vpns(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_vpns()
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/VPN')

    def test_get_scopes(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_scopes()
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/Scope?vpnId=.*')

    def test_get_scope(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_scope('myscope')
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/Scope/myscope')

    def test_get_client_entries(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_client_entries()
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/ClientEntry')

    def test_get_client_entry(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_client_entry('myclinetentry')
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'ClientEntry/myclinetentry')

    def test_get_leases(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_leases('vpn123')
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'Lease?vpnId=vpn123')

    def test_get_dns_server(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_dns_server()
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/DNSServer')

    def test_get_dns_forwarders(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_dns_forwarders()
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/DnsForwarder')

    def test_get_dns_forwarder(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_dns_forwarder('myforwarder')
        self.mock_do_request.assert_called_once_with('GET',
                    'http://cpnr.com:8080/web-services/rest/'
                    'resource/DnsForwarder/myforwarder')

    def test_get_dns_views(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.get_dns_views()
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/DnsView')

    def test_get_dns_view(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_dns_view('mydnsview')
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'DnsView/mydnsview')

    def test_get_ccm_zones(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_ccm_zones()
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMZone?viewId=.*')

    def test_get_ccm_zone(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_ccm_zone('myzone')
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMZone/myzone?viewId=.*')

    def test_get_ccm_reverse_zones(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_ccm_reverse_zones()
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMReverseZone?viewId=.*')

    def test_get_ccm_reverse_zone(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_ccm_reverse_zone('myreversezone')
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMReverseZone/myreversezone?viewId=.*')

    def test_get_ccm_hosts(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_ccm_hosts()
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMHost?viewId=.*&zoneOrigin=.*')

    def test_get_ccm_host(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.get_ccm_host('myhost')
        self.mock_do_request.assert_called_once_with('GET',
            'http://cpnr.com:8080/web-services/rest/resource/CCMHost'
            '/myhost?viewId=.*&zoneOrigin=.*')

    def test_create_scope(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.create_scope('myscope')
        self.mock_do_request.assert_called_once_with('POST',
            'http://cpnr.com:8080/web-services/rest/resource/Scope',
            'myscope')

    def test_create_client_class(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.create_client_class('myclientclass')
        self.mock_do_request.assert_called_once_with('POST',
            'http://cpnr.com:8080/web-services/rest/resource/ClientClass',
            'myclientclass')

    def test_create_vpn(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.create_vpn('myvpn')
        self.mock_do_request.assert_called_once_with('POST',
            'http://cpnr.com:8080/web-services/rest/resource/VPN',
            'myvpn')

    def test_create_client_entry(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.create_client_entry('mycliententry')
        self.mock_do_request.assert_called_once_with('POST',
            'http://cpnr.com:8080/web-services/rest/resource/ClientEntry',
            'mycliententry')

    def test_create_dns_forwarder(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                'admin', 0)
        mock_client.create_dns_forwarder('mydnsforwarder')
        self.mock_do_request.assert_called_once_with('POST',
            'http://cpnr.com:8080/web-services/rest/resource/DnsForwarder',
            'mydnsforwarder')

    def test_create_dns_view(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.create_dns_view('mydnsview')
        self.mock_do_request.assert_called_once_with('POST',
            'http://cpnr.com:8080/web-services/rest/resource/DnsView',
            'mydnsview')

    def test_create_ccm_zone(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.create_ccm_zone('myccmzone')
        self.mock_do_request.assert_called_once_with('POST',
            'http://cpnr.com:8080/web-services/rest/resource/CCMZone',
            'myccmzone')

    def test_create_ccm_reverse_zone(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.create_ccm_reverse_zone('myccmreversezone')
        self.mock_do_request.assert_called_once_with('POST',
            'http://cpnr.com:8080/web-services/rest/resource/CCMReverseZone',
            'myccmreversezone')

    def test_create_ccm_host(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.create_ccm_host('myccmhost')
        self.mock_do_request.assert_called_once_with('POST',
            'http://cpnr.com:8080/web-services/rest/resource/CCMHost',
            'myccmhost')

    def test_update_dhcp_server(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_dhcp_server('updatedhcpserver')
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource/DHCPServer',
            'updatedhcpserver')

    def test_update_client_class(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_client_class('updateclientclass',
                                        'newclientclass')
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'ClientClass/updateclientclass',
            'newclientclass')

    def test_update_vpn(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_vpn('updatevpn', 'newvpn')
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource/VPN/updatevpn',
            'newvpn')

    def test_update_scope(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_scope('updatescope', 'newscope')
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'Scope/updatescope',
            'newscope')

    def test_update_client_entry(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_client_entry('updatecliententry',
                                        'newcliententry')
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource'
            '/ClientEntry/updatecliententry',
            'newcliententry')

    def test_update_dns_server(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_dns_server('updatednsserver')
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource/DNSServer',
            'updatednsserver')

    def test_update_dns_forwarder(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_dns_forwarder('updatednsforwarder',
                                         'newforwarder')
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'DnsForwarder/updatednsforwarder',
            'newforwarder')

    def test_update_dns_view(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_dns_view('updatednsview', 'newdnsview')
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource'
            '/DnsView/updatednsview',
            'newdnsview')

    def test_update_ccm_zone(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_ccm_zone('updateccmzone', 'newzone',
                                    None)
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMZone/updateccmzone',
            'newzone')

    def test_update_ccm_reverse_zone(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_ccm_reverse_zone(
                                        'updateccmreversezone',
                                        'newreversezone',
                                        None)
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMReverseZone/updateccmreversezone',
            'newreversezone')

    def test_update_ccm_host(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.update_ccm_host('updateccmhost', 'newccmhost',
                                    None)
        self.mock_do_request.assert_called_once_with('PUT',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMHost/updateccmhost',
            'newccmhost')

    def test_delete_client_class(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.delete_client_class('deleteclientclass')
        self.mock_do_request.assert_called_once_with('DELETE',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'ClientClass/deleteclientclass')

    def test_delete_vpn(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.delete_vpn('deletevpn')
        self.mock_do_request.assert_called_once_with('DELETE',
            'http://cpnr.com:8080/web-services/rest/resource/VPN/deletevpn')

    def test_delete_scope(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.delete_scope('deletescope')
        self.mock_do_request.assert_called_once_with('DELETE',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'Scope/deletescope')

    def test_delete_client_entry(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.delete_client_entry('deletecliententry')
        self.mock_do_request.assert_called_once_with('DELETE',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'ClientEntry/deletecliententry')

    def test_delete_dns_forwarder(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.delete_dns_forwarder('deletednsforwarder')
        self.mock_do_request.assert_called_once_with('DELETE',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'DnsForwarder/deletednsforwarder')

    def test_delete_dns_view(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.delete_dns_view('deletednsview')
        self.mock_do_request.assert_called_once_with('DELETE',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'DnsView/deletednsview')

    def test_delete_ccm_zone(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.delete_ccm_zone('deleteccmzone')
        self.mock_do_request.assert_called_once_with('DELETE',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMZone/deleteccmzone')

    def test_delete_ccm_reverse_zone(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.delete_ccm_reverse_zone('delccmreversezone')
        self.mock_do_request.assert_called_once_with('DELETE',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMReverseZone/delccmreversezone')

    def test_delete_ccm_host(self):
        mock_client = CpnrClient('http', 'cpnr.com', '8080', 'admin',
                                 'admin', 0)
        mock_client.delete_ccm_host('deleteccmhost')
        self.mock_do_request.assert_called_once_with('DELETE',
            'http://cpnr.com:8080/web-services/rest/resource/'
            'CCMHost/deleteccmhost')
