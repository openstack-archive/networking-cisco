# Copyright 2017 Cisco Systems Inc.
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

from oslo_log import log as logging

from neutron.db import common_db_mixin
from neutron_lib.api import validators

from networking_cisco import backwards_compatibility as bc
from networking_cisco.backwards_compatibility import ml2_api as api

LOG = logging.getLogger(__name__)


class CiscoProviderNetDriver(api.ExtensionDriver,
                             common_db_mixin.CommonDbMixin):
    _supported_extension_alias = 'provider'

    def initialize(self):
        LOG.info("CiscoProviderNetDriver initialization complete")

    @property
    def extension_alias(self):
        return self._supported_extension_alias

    def process_create_network(self, context, data, result):
        if validators.is_attr_set(data.get(bc.providernet.SEGMENTATION_ID)):
            result['is_provider_network'] = True
