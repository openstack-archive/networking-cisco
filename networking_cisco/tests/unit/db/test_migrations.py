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

from oslo_config import cfg
import six
import unittest2

# We don't need to run these test under Python 3 yet.
# TODO(HenryG): Figure out why they don't work with Python 3.
if six.PY3:
    raise unittest2.SkipTest("Disabled for Python 3.")

from neutron.db.migration.alembic_migrations import external
from neutron.db.migration import cli as migration
from neutron.tests.functional.db import test_migrations

from networking_cisco.db.migration import alembic_migrations
from networking_cisco.db.migration.models import head

from networking_cisco.tests import test_compatibility as tc

# EXTERNAL_TABLES should contain all names of tables that are not related to
# current repo.
EXTERNAL_TABLES = set(external.TABLES) - set(external.REPO_CISCO_TABLES)


class _TestModelsMigrationsCisco(test_migrations._TestModelsMigrations):

    def db_sync(self, engine):
        cfg.CONF.set_override('connection', engine.url, group='database')
        for conf in migration.get_alembic_configs():
            self.alembic_config = conf
            self.alembic_config.neutron_config = cfg.CONF
            migration.do_alembic_command(conf, 'upgrade', 'heads')

    def get_metadata(self):
        return head.get_metadata()

    def include_object(self, object_, name, type_, reflected, compare_to):
        if type_ == 'table' and (name == 'alembic' or
                                 name == alembic_migrations.VERSION_TABLE or
                                 name in EXTERNAL_TABLES):
            return False
        else:
            return True


class TestModelsMigrationsMysql(_TestModelsMigrationsCisco,
                                tc.MySQLTestCase):
    pass
