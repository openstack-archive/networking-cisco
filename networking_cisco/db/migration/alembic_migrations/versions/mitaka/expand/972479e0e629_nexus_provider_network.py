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
import sqlalchemy as sa


"""nexus_provider_network

Revision ID: 972479e0e629
Revises: f3765e42de23
Create Date: 2017-05-02 15:11:15.280677

"""

# revision identifiers, used by Alembic.
revision = '972479e0e629'
down_revision = 'f3765e42de23'


def upgrade():
    op.create_table('cisco_ml2_nexus_provider_networks',
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('vlan_id', sa.Integer, nullable=False, index=True),
        sa.PrimaryKeyConstraint('network_id'),
    )

    op.drop_column('cisco_ml2_nexusport_bindings', 'is_provider_vlan')
