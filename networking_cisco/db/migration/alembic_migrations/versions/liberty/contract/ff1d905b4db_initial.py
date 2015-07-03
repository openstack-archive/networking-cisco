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

"""Initial Liberty no-op contract revision.

Revision ID: ff1d905b4db
Revises: None
Create Date: 2015-07-28 17:38:34.209525

"""

# revision identifiers, used by Alembic.
revision = 'ff1d905b4db'
down_revision = None
branch_labels = ('liberty_contract',)
depends_on = ('kilo',)


def upgrade():
    pass
