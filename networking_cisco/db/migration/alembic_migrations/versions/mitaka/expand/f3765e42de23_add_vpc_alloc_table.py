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


"""Add VPC alloc table

Revision ID: f3765e42de23
Revises: 9148d96f9b39
Create Date: 2017-06-07 17:10:09.597016

"""

# revision identifiers, used by Alembic.
revision = 'f3765e42de23'
down_revision = '9148d96f9b39'


def upgrade():
    op.create_table('cisco_ml2_nexus_vpc_alloc',
        sa.Column('switch_ip', sa.String(length=64), nullable=False,
                  index=True),
        sa.Column('vpc_id', sa.Integer(), nullable=False),
        sa.Column('learned', sa.Boolean(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('switch_ip', 'vpc_id')
    )
