# Copyright 2015 Cisco Systems Inc.
# All Rights Reserved
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

import sys

import mock

from networking_cisco.neutronclient import policyprofile as pp
from neutronclient import shell
from neutronclient.tests.unit import test_cli20


class CLITestV20PolicyProfile(test_cli20.CLITestV20Base):

    def setUp(self):
        self._mock_extension_loading()
        super(CLITestV20PolicyProfile, self).setUp()

    def _mock_extension_loading(self):
        ext_pkg = 'neutronclient.common.extension'
        ext = mock.patch(ext_pkg + '._discover_via_entry_points').start()
        ext.return_value = [("policy_profile", pp)]
        return ext

    def test_ext_cmd_loaded(self):
        shell.NeutronShell('2.0')
        ext_cmd = {'cisco-policy-profile-list': pp.PolicyProfileList,
                   'cisco-policy-profile-show': pp.PolicyProfileShow}
        self.assertDictContainsSubset(ext_cmd, shell.COMMANDS['2.0'])

    def test_list_policyprofile_detail(self):
        """List policyprofile: -D."""
        resources = 'policy_profiles'
        cmd = pp.PolicyProfileList(test_cli20.MyApp(sys.stdout), None)
        contents = [{'name': 'myname', 'segment_type': 'vlan'}]
        self._test_list_resources(resources, cmd, True,
                                  response_contents=contents)

    def test_list_policyprofile_known_option_after_unknown(self):
        """List policyprofile: -- --tags a b --request-format xml."""
        resources = 'policy_profiles'
        cmd = pp.PolicyProfileList(test_cli20.MyApp(sys.stdout), None)
        contents = [{'name': 'myname', 'segment_type': 'vlan'}]
        self._test_list_resources(resources, cmd, tags=['a', 'b'],
                                  response_contents=contents)

    def test_list_policyprofile_fields(self):
        """List policyprofile: --fields a --fields b -- --fields c d."""
        resources = 'policy_profiles'
        cmd = pp.PolicyProfileList(test_cli20.MyApp(sys.stdout), None)
        contents = [{'name': 'myname', 'segment_type': 'vlan'}]
        self._test_list_resources(resources, cmd,
                                  fields_1=['a', 'b'], fields_2=['c', 'd'],
                                  response_contents=contents)

    def test_show_policyprofile(self):
        """Show policyprofile: --fields id --fields name myid."""
        resource = 'policy_profile'
        cmd = pp.PolicyProfileShow(test_cli20.MyApp(sys.stdout), None)
        args = ['--fields', 'id', '--fields', 'name', self.test_id]
        self._test_show_resource(resource, cmd, self.test_id, args,
                                 ['id', 'name'])
