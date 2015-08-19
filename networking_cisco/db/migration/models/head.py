# Copyright 2015 Cisco Systems, Inc
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

from neutron.db.migration.models import head

from networking_cisco.plugins.cisco.db.device_manager import (  # noqa
    hd_models)
from networking_cisco.plugins.cisco.db.l3 import (  # noqa
    ha_db)
from networking_cisco.plugins.cisco.db.l3 import (  # noqa
    l3_models)
from networking_cisco.plugins.ml2.drivers.cisco.apic import (  # noqa
    apic_model)
from networking_cisco.plugins.ml2.drivers.cisco.n1kv import (  # noqa
    n1kv_models)
from networking_cisco.plugins.ml2.drivers.cisco.nexus import (  # noqa
    nexus_models_v2)
from networking_cisco.plugins.ml2.drivers.cisco.ucsm import (  # noqa
    ucsm_model)


def get_metadata():
    return head.model_base.BASEV2.metadata
