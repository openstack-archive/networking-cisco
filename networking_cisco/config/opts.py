# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from networking_cisco.ml2_drivers.nexus import (
    config as nexus_config)
from networking_cisco.ml2_drivers.nexus import (
    type_nexus_vxlan as nexus_vxlan_config)
from networking_cisco.ml2_drivers.ucsm import (
    config as ucsm_config)
from networking_cisco.plugins.cisco.device_manager import (
    config as asrcfg)


def list_nexus_conf_opts():
    return [
        ('ml2_cisco', nexus_config.ml2_cisco_opts),
        ('ml2_mech_cisco_nexus:<ip_address>', nexus_config.nexus_sub_opts)
    ]


def list_nexus_vxlan_type_driver_conf_opts():
    return [
        ('ml2_type_nexus_vxlan', nexus_vxlan_config.nexus_vxlan_opts),
    ]


def list_ucsm_conf_opts():
    main_group = list(ucsm_config.ml2_cisco_ucsm_opts)
    main_group.extend(ucsm_config.ml2_cisco_ucsm_common)
    return [
        ('ml2_cisco_ucsm', main_group),
        ('ml2_cisco_ucsm_ip:<ip_address>', ucsm_config.ml2_cisco_ucsm_common),
        ('sriov_multivlan_trunk', ucsm_config.sriov_opts)
    ]


def list_asr_conf_opts():
    return [
        ('cisco_hosting_device_credential:<uuid>', asrcfg.credentials_subopts),
        ('cisco_hosting_device_template:<uuid>', asrcfg.template_subopts),
        ('cisco_hosting_device:<uuid>', asrcfg.hosting_device_subopts),
        ('cisco_router_type:<uuid>', asrcfg.router_type_subopts),
        ('HwVLANTrunkingPlugDriver', asrcfg.hwvlantrunkingdrivers_subopts)
    ]
