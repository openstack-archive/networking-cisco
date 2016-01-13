# Copyright 2016 Cisco Systems, Inc.
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

"""Add support for UCSM Service Profile Templates.

Revision ID: 13bd9ebffbf5
Revises: 2e89171ea204
Create Date: 2016-01-27 13:12:12.805860

"""

# revision identifiers, used by Alembic.
revision = '13bd9ebffbf5'
down_revision = '2e89171ea204'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('ml2_ucsm_sp_templates',
        sa.Column('vlan_id', sa.Integer(), nullable=False),
        sa.Column('sp_template', sa.String(length=64), nullable=False),
        sa.Column('device_id', sa.String(length=64), nullable=False),
        sa.Column('updated_on_ucs', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('vlan_id', 'sp_template', 'device_id')
    )
