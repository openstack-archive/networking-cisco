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


from networking_cisco import backwards_compatibility as bc


if bc.NEUTRON_VERSION < bc.NEUTRON_NEWTON_VERSION:
    from neutron.tests.common import base

    class MySQLTestCase(base.MySQLTestCase):
        pass
else:
    from neutron.tests.unit import testlib_api

    class MySQLTestCase(testlib_api.MySQLTestCaseMixin,
                        testlib_api.SqlTestCaseLight):
        pass
