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

from networking_cisco.backwards_compatibility import neutron_version as nv


if nv.NEUTRON_VERSION >= nv.NEUTRON_ROCKY_VERSION:
    from neutron_lib.api.attributes import *  # noqa
else:
    # NOTE(sambetts) Because of neutron _MovedGlobals we can not import * from
    # neutron.api.v2.attributes so instead we monkey patch the real one and
    # then make this module point at the real one
    from neutron.api.v2 import attributes as _attributes
    import sys

    _attributes.RESOURCES = _attributes.RESOURCE_ATTRIBUTE_MAP
    sys.modules[__name__] = _attributes
