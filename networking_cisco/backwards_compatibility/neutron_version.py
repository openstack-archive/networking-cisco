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

from distutils.version import StrictVersion

from neutron import version

NEUTRON_VERSION = StrictVersion(str(version.version_info))
NEUTRON_NEWTON_VERSION = StrictVersion('9.0.0')
NEUTRON_OCATA_VERSION = StrictVersion('10.0.0')
NEUTRON_PIKE_VERSION = StrictVersion('11.0.0')
NEUTRON_QUEENS_VERSION = StrictVersion('12.0.0')
