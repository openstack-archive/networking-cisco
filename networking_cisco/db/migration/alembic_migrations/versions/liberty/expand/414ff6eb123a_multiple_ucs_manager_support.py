# Copyright 2015 Cisco Systems, Inc.
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

"""Multiple UCS Manager support

Revision ID: 414ff6eb123a
Revises: 1e9e22602685
Create Date: 2015-10-19 15:21:10.806609

"""

# revision identifiers, used by Alembic.
revision = '414ff6eb123a'
down_revision = '1e9e22602685'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'ml2_ucsm_port_profiles',
        sa.Column('device_id', sa.String(length=64), nullable=False)
    )
