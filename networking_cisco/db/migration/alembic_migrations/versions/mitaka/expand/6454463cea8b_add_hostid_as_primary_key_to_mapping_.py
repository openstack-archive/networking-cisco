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
from sqlalchemy.engine.reflection import Inspector as insp


"""Add hostid as primary key to mapping table

Revision ID: 6454463cea8b
Revises: 73c84db9f299
Create Date: 2017-12-01 18:48:03.531425

"""

# revision identifiers, used by Alembic.
revision = '6454463cea8b'
down_revision = '73c84db9f299'

ML2_NEXUS_MAPPING_TABLE = 'cisco_ml2_nexus_host_interface_mapping'


def upgrade():

    bind = op.get_bind()

    inspector = insp.from_engine(bind)
    pk_constraint = inspector.get_pk_constraint(ML2_NEXUS_MAPPING_TABLE)
    op.drop_constraint(pk_constraint.get('name'), ML2_NEXUS_MAPPING_TABLE,
                       type_='primary')
    op.create_primary_key(op.f('pk_cisco_ml2_nexus_host_interface_mapping'),
                          ML2_NEXUS_MAPPING_TABLE,
                          ['host_id', 'switch_ip', 'if_id'])
