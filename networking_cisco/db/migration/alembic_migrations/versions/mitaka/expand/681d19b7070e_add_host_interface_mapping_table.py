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


"""Add host/interface mapping table

Revision ID: 681d19b7070e
Revises: 203b495958cf
Create Date: 2017-05-16 13:47:24.649856

"""

# revision identifiers, used by Alembic.
revision = '681d19b7070e'
down_revision = '203b495958cf'


def upgrade():
    op.create_table('cisco_ml2_nexus_host_interface_mapping',
        sa.Column('host_id', sa.String(length=255), nullable=False,
                  index=True),
        sa.Column('switch_ip', sa.String(length=64), nullable=False,
                  index=True),
        sa.Column('if_id', sa.String(length=255), nullable=False),
        sa.Column('ch_grp', sa.Integer(), nullable=False),
        sa.Column('is_static', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('switch_ip', 'if_id')
    )
