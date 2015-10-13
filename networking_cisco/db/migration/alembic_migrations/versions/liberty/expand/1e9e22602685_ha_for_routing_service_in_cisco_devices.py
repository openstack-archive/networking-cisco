# Copyright 2015 OpenStack Foundation
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
#

"""ha_for_routing_service_in_cisco_devices

Revision ID: 1e9e22602685
Revises: 53f08de0523f
Create Date: 2015-09-28 09:33:27.294138

"""

# revision identifiers, used by Alembic.
revision = '1e9e22602685'
down_revision = '2921fe565328'

from alembic import op
import sqlalchemy as sa

from networking_cisco.plugins.cisco.extensions import ha


ha_states = sa.Enum('ACTIVE', 'STANDBY', name='ha_states')


def upgrade():
    op.create_table('cisco_router_ha_settings',
        sa.Column('router_id', sa.String(36), nullable=True),
        sa.Column('ha_type', sa.String(255), nullable=True),
        sa.Column('redundancy_level', sa.Integer,
                  server_default=str(ha.MIN_REDUNDANCY_LEVEL)),
        sa.Column('priority', sa.Integer, nullable=True),
        sa.Column('probe_connectivity', sa.Boolean, nullable=True),
        sa.Column('probe_target', sa.String(64), nullable=True),
        sa.Column('probe_interval', sa.Integer, nullable=True),
        sa.Column('state', ha_states, server_default='ACTIVE'),
        sa.ForeignKeyConstraint(['router_id'], ['routers.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('router_id')
    )
    op.create_table('cisco_router_ha_groups',
        sa.Column('tenant_id', sa.String(length=255), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('ha_type', sa.String(255), nullable=True),
        sa.Column('group_identity', sa.String(255), nullable=True),
        sa.Column('ha_port_id', sa.String(36), nullable=False),
        sa.Column('extra_port_id', sa.String(36), nullable=True),
        sa.Column('subnet_id', sa.String(36), nullable=True),
        sa.Column('user_router_id', sa.String(36), nullable=True),
        sa.Column('timers_config', sa.String(255), nullable=True),
        sa.Column('tracking_config', sa.String(255), nullable=True),
        sa.Column('other_config', sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['ha_port_id'], ['ports.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['extra_port_id'], ['ports.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['subnet_id'], ['subnets.id']),
        sa.ForeignKeyConstraint(['user_router_id'], ['routers.id']),
        sa.PrimaryKeyConstraint('ha_port_id')
    )
    op.create_table('cisco_router_redundancy_bindings',
        sa.Column('redundancy_router_id', sa.String(36)),
        sa.Column('priority', sa.Integer),
        sa.Column('state', ha_states, server_default='STANDBY'),
        sa.Column('user_router_id', sa.String(36)),
        sa.ForeignKeyConstraint(['redundancy_router_id'], ['routers.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_router_id'], ['routers.id']),
        sa.PrimaryKeyConstraint('redundancy_router_id')
    )
