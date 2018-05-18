# Copyright 2018 Cisco Systems, Inc.
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


"""Remove the N1kv mechanism driver

Revision ID: c52284b920fd
Revises: 53f08de0523f
Create Date: 2018-01-16 16:48:18.526764

"""

# revision identifiers, used by Alembic.
revision = 'c52284b920fd'
down_revision = '53f08de0523f'


def upgrade():
    op.drop_table('cisco_ml2_n1kv_policy_profiles')
    op.drop_table('cisco_ml2_n1kv_port_bindings')
    op.drop_table('cisco_ml2_n1kv_network_bindings')
    op.drop_table('cisco_ml2_n1kv_vlan_allocations')
    op.drop_table('cisco_ml2_n1kv_vxlan_allocations')
    op.drop_table('cisco_ml2_n1kv_profile_bindings')
    op.drop_table('cisco_ml2_n1kv_network_profiles')
