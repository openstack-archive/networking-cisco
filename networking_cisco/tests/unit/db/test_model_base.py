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

import sqlalchemy as sa

from networking_cisco import backwards_compatibility as bc
from neutron.tests.unit import testlib_api


class TestTable(bc.model_base.BASEV2, bc.HasProject,
                bc.model_base.HasId, bc.model_base.HasStatusDescription):

    name = sa.Column(sa.String(8), primary_key=True)


class TestModelBase(testlib_api.SqlTestCase):

    def setUp(self):
        super(TestModelBase, self).setUp()
        self.ctx = bc.context.Context('user', 'project')
        self.session = self.ctx.session

    def test_model_base(self):
        foo = TestTable(name='meh')
        self.assertEqual('meh', foo.name)
        self.assertIn('meh', str(foo))  # test foo.__repr__
        cols = [k for k, _v in foo]  # test foo.__iter__ and foo.next
        self.assertIn('name', cols)

    def test_get_set_tenant_id_tenant(self):
        foo = TestTable(tenant_id='tenant')
        self.assertEqual('tenant', foo.get_tenant_id())
        foo.set_tenant_id('project')
        self.assertEqual('project', foo.get_tenant_id())

    def test_get_set_tenant_id_project(self):
        foo = TestTable(project_id='project')
        self.assertEqual('project', foo.get_tenant_id())
        foo.set_tenant_id('tenant')
        self.assertEqual('tenant', foo.get_tenant_id())

    def test_project_id_attribute(self):
        foo = TestTable(project_id='project')
        self.assertEqual('project', foo.project_id)
        self.assertEqual('project', foo.tenant_id)

    def test_tenant_id_attribute(self):
        foo = TestTable(tenant_id='tenant')
        self.assertEqual('tenant', foo.project_id)
        self.assertEqual('tenant', foo.tenant_id)
