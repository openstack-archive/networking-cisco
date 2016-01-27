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

"""Add baremetal channel-group and is_native

Revision ID: 2e89171ea204
Revises: 11ba2d65c8de
Create Date: 2016-01-27 13:12:12.805860

"""

# revision identifiers, used by Alembic.
revision = '2e89171ea204'
down_revision = '11ba2d65c8de'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('cisco_ml2_nexusport_bindings',
        sa.Column('channel_group', sa.Integer(), default=0))
    op.add_column('cisco_ml2_nexusport_bindings',
        sa.Column('is_native', sa.Boolean(), nullable=False,
                  server_default=sa.sql.false()))
