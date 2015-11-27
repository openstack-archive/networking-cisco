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

"""Add missing tenant_id index

Revision ID: 11ba2d65c8de
Revises: 414ff6eb123a
Create Date: 2015-11-26 23:33:41.877280

"""

# revision identifiers, used by Alembic.
revision = '11ba2d65c8de'
down_revision = '414ff6eb123a'

from alembic import op


def upgrade():
    op.create_index(op.f('ix_cisco_router_ha_groups_tenant_id'),
                    'cisco_router_ha_groups', ['tenant_id'], unique=False)
