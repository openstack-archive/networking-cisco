# Copyright 2018 Cisco Systems, Inc.  All rights reserved.
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

# NOTE(sambetts) F401 is the flake8 code for the "X imported but not used"
# error we only ignore that so that other errors like import order still get
# caught.

from networking_cisco.backwards_compatibility import neutron_version as nv

# Pull in all the neutron_lib constants
from neutron_lib.constants import *  # noqa

if nv.NEUTRON_VERSION >= nv.NEUTRON_PIKE_VERSION:
    from neutron_lib.plugins.constants import *  # noqa

# Compatibility additions for releases before Newton
if nv.NEUTRON_VERSION < nv.NEUTRON_NEWTON_VERSION:
    from neutron.api.v2.attributes import ATTR_NOT_SPECIFIED  # noqa: F401

# Compatibility additions for releases before Ocata
if nv.NEUTRON_VERSION < nv.NEUTRON_OCATA_VERSION:
    from neutron.plugins.common.constants import L3_ROUTER_NAT as L3  # noqa: F401

# Compatibility additions for all releases before Pike
if nv.NEUTRON_VERSION < nv.NEUTRON_PIKE_VERSION:
    from neutron.plugins.common.constants import MAX_VLAN_TAG  # noqa: F401
    from neutron.plugins.common.constants import MAX_VXLAN_VNI  # noqa: F401
    from neutron.plugins.common.constants import TYPE_FLAT  # noqa: F401
    from neutron.plugins.common.constants import TYPE_VLAN  # noqa: F401
    from neutron.plugins.common.constants import TYPE_VXLAN  # noqa: F401

# Additional things that haven't moved to neutron_lib yet
from neutron.plugins.common.constants import EXT_TO_SERVICE_MAPPING  # noqa: F401
