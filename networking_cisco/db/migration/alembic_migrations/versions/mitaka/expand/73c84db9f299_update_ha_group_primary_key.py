# Copyright 2017 Cisco Systems, Inc.
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

from alembic import op
from neutron.db import migration
from sqlalchemy.engine import reflection


"""update_ha_group_primary_key

Revision ID: 73c84db9f299
Revises: 972479e0e629
Create Date: 2017-10-05 05:31:54.243849

"""

# revision identifiers, used by Alembic.
revision = '73c84db9f299'
down_revision = '972479e0e629'


def upgrade():
    if migration.schema_has_table('cisco_router_ha_groups'):
        inspector = reflection.Inspector.from_engine(op.get_bind())
        foreign_keys = inspector.get_foreign_keys('cisco_router_ha_groups')
        migration.remove_foreign_keys('cisco_router_ha_groups', foreign_keys)
        primary_key = inspector.get_pk_constraint('cisco_router_ha_groups')
        op.drop_constraint(constraint_name=primary_key['name'],
                           table_name='cisco_router_ha_groups',
                           type_='primary')

        op.create_foreign_key('cisco_router_ha_groups_ibfk_1',
                              source_table='cisco_router_ha_groups',
                              referent_table='ports',
                              local_cols=['ha_port_id'],
                              remote_cols=['id'],
                              ondelete='CASCADE'),
        op.create_foreign_key('cisco_router_ha_groups_ibfk_2',
                              source_table='cisco_router_ha_groups',
                              referent_table='ports',
                              local_cols=['extra_port_id'],
                              remote_cols=['id'],
                              ondelete='SET NULL'),
        op.create_foreign_key('cisco_router_ha_groups_ibfk_3',
                              source_table='cisco_router_ha_groups',
                              referent_table='subnets',
                              local_cols=['subnet_id'],
                              remote_cols=['id'])
        op.create_foreign_key('cisco_router_ha_groups_ibfk_4',
                              source_table='cisco_router_ha_groups',
                              referent_table='routers',
                              local_cols=['user_router_id'],
                              remote_cols=['id'])

        op.create_primary_key(
            constraint_name='pk_cisco_router_ha_groups',
            table_name='cisco_router_ha_groups',
            columns=['ha_port_id', 'subnet_id'])
