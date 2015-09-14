# Copyright (c) 2015 Cisco Systems, Inc.
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

from networking_cisco.plugins.ml2.drivers.cisco.n1kv import exceptions as c_exc
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import n1kv_client

_resource_metadata = {'network-segment': ['publishName', 'description', 'id',
                                          'tenantId', 'mode', 'segmentType',
                                          'networkSegmentPool', 'vlan',
                                          'vxlan', 'bridgeDomain'],
                      'port': ['id', 'macAddress', 'ipAddress', 'subnetId'],
                      'vmnetwork': ['name', 'networkSegmentId',
                                    'networkSegment', 'portProfile',
                                    'portProfileId', 'tenantId',
                                    'portId', 'macAddress',
                                    'portType', 'ipAddress', 'subnetId'],
                      'subnet': ['addressRangeStart', 'addressRangeEnd',
                                 'ipAddressSubnet', 'description', 'gateway',
                                 'dhcp', 'dnsServersList', 'networkAddress',
                                 'netSegmentName', 'id', 'tenantId']}


class TestClient(n1kv_client.Client):
    """Base class for test client"""
    def __init__(self, **kwargs):
        self.broken = False
        self.inject_params = False
        self.total_profiles = 2
        self.shared_net = False
        self.upd_shared_net = False
        super(TestClient, self).__init__()

    def _get_total_profiles(self):
        """Return total number of profiles"""
        return self.total_profiles

    def _do_request(self, method, action, body=None, headers=None,
                    vsm_ip=None):
        """Handle outgoing requestes based on type"""
        if self.broken:
            raise c_exc.VSMError(reason='VSM:Internal Server Error')
        if self.inject_params and body:
            body['invalidKey'] = 'catchMeIfYouCan'
        if method == 'POST' and self.shared_net:
            return _validate_shared_net_resource(action, body)
        # For update to shared network cases, set to shared after net create
        elif (method == 'POST' and self.upd_shared_net and
              '/network-segment/' in action):
            ret = _validate_resource(action, body)
            self.shared_net = True
            return ret
        elif method == 'POST':
            return _validate_resource(action, body)
        elif method == 'GET':
            if 'virtual-port-profile' in action:
                return _policy_profile_generator(
                    self._get_total_profiles())
            else:
                raise c_exc.VSMError(reason='VSM:Internal Server Error')


class TestClientInvalidRequest(TestClient):
    """Test invalid request cases"""
    def __init__(self, **kwargs):
        super(TestClientInvalidRequest, self).__init__()
        self.inject_params = True


class TestClientInvalidResponse(TestClient):
    """Test invalid response cases"""
    def __init__(self, **kwargs):
        super(TestClientInvalidResponse, self).__init__()
        self.broken = True


class TestClientSharedNetwork(TestClient):
    """Test shared network cases"""
    def __init__(self, **kwargs):
        super(TestClientSharedNetwork, self).__init__()
        self.shared_net = True


class TestClientUpdateSharedNetwork(TestClient):
    """Test cases where network is updated to be shared"""
    def __init__(self, **kwargs):
        super(TestClientUpdateSharedNetwork, self).__init__()
        self.upd_shared_net = True


class TestClientVSMRetry(n1kv_client.Client):
    """Base class for test client"""
    def __init__(self, **kwargs):
        super(TestClientVSMRetry, self).__init__()
        self.pool.spawn = self._fake_pool_spawn

    def _fake_pool_spawn(self):
        pass


def _validate_resource(action, body=None):
    """Validate expected keys are present in outgoing request"""
    if body:
        body_set = set(body.keys())
    else:
        return
    if 'vm-network' in action and 'port' not in action:
        vmnetwork_set = set(_resource_metadata['vmnetwork'])
        if body_set - vmnetwork_set:
            raise c_exc.VSMError(reason='Invalid Request')
    elif '/network-segment/' in action:
        network_set = set(_resource_metadata['network-segment'])
        if body_set - network_set:
            raise c_exc.VSMError(reason='Invalid Request')
    elif 'port' in action:
        port_set = set(_resource_metadata['port'])
        if body_set - port_set:
            raise c_exc.VSMError(reason='Invalid Request')
    elif 'subnet' in action:
        subnet_set = set(_resource_metadata['subnet'])
        if body_set - subnet_set:
            raise c_exc.VSMError(reason='Invalid Request')
    else:
        return


def _validate_shared_net_resource(action, body=None):
    """Validate keys in outgoing shared network request"""
    if body:
        body_set = set(body.keys())
    else:
        return
    if 'vm-network' in action and 'port' not in action:
        vmnetwork_set = set(_resource_metadata['vmnetwork'])
        if body_set - vmnetwork_set:
            raise c_exc.VSMError(reason='Invalid Request')
    elif 'port' in action:
        port_set = set(_resource_metadata['port'])
        if body_set - port_set:
            raise c_exc.VSMError(reason='Invalid Request')
    elif 'subnet' in action:
        subnet_set = set(_resource_metadata['subnet'])
        if body_set - subnet_set:
            raise c_exc.VSMError(reason='Invalid Request')
    elif '/network-segment/' in action:
        network_set = set(_resource_metadata['network-segment'])
        if body_set - network_set:
            raise c_exc.VSMError(reason='Invalid Request')
        if body['tenantId'] != '0':
            raise c_exc.VSMError(reason='Invalid Shared Network Handling')
    else:
        return


def _policy_profile_generator(total_profiles):
    """
    Generate policy profile response and return a dictionary.

    :param total_profiles: integer representing total number of profiles to
                           return
    """
    profiles = {}
    for num in range(1, total_profiles + 1):
        name = "pp-%s" % num
        profile_id = "00000000-0000-0000-0000-00000000000%s" % num
        profiles[name] = {"properties": {"name": name, "id": profile_id}}
    return profiles


def _policy_profile_generator_xml(total_profiles):
    """
    Generate policy profile response in XML format.

    :param total_profiles: integer representing total number of profiles to
                           return
    """
    xml = ["""<?xml version="1.0" encoding="utf-8"?>
           <set name="virtual_port_profile_set">"""]
    template = (
        '<instance name="%(num)d"'
        ' url="/api/n1k/virtual-port-profile/%(num)s">'
        '<properties>'
        '<id>00000000-0000-0000-0000-00000000000%(num)s</id>'
        '<name>pp-%(num)s</name>'
        '</properties>'
        '</instance>'
    )
    xml.extend(template % {'num': n} for n in range(1, total_profiles + 1))
    xml.append("</set>")
    return ''.join(xml)
