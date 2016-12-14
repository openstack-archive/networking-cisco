# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
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

from types import ModuleType

from distutils.version import StrictVersion

from neutron import version


# Some constants and verifier functions have been deprecated but are still
# used by earlier releases of neutron. In order to maintain
# backwards-compatibility with stable/mitaka this will act as a translator
# that passes constants and functions according to version number.

NEUTRON_VERSION = StrictVersion(str(version.version_info))
NEUTRON_NEWTON_VERSION = StrictVersion('9.0.0')

n_c = __import__('neutron.common.constants', fromlist=['common.constants'])
constants = __import__('neutron_lib.constants', fromlist=['constants'])

# 9.0.0 is Newton
if NEUTRON_VERSION >= NEUTRON_NEWTON_VERSION:
    from neutron.conf import common as base_config
    from neutron import manager
    from neutron_lib.api import validators

    is_attr_set = validators.is_attr_set
    validators = validators.validators
    if NEUTRON_VERSION.version[0] == NEUTRON_NEWTON_VERSION.version[0]:
        from neutron.api import extensions  # noqa
        from neutron.db import model_base  # noqa

        def get_plugin(service=None):
            if service is None:
                return manager.NeutronManager.get_plugin()
            else:
                return manager.NeutronManager.get_service_plugins().get(
                    service)
        n_c_attr_names = n_c._mg__my_globals
    else:
        from neutron_lib.api import extensions
        from neutron_lib.db import model_base
        from neutron_lib.plugins import directory

        get_plugin = directory.get_plugin
        n_c_attr_names = dir(n_c)
# Pre Newton
elif NEUTRON_VERSION < NEUTRON_NEWTON_VERSION:
    from neutron.api import extensions  # noqa
    from neutron.api.v2 import attributes
    from neutron.common import config as base_config
    from neutron.db import model_base  # noqa
    from neutron import manager
    setattr(constants, 'ATTR_NOT_SPECIFIED', getattr(attributes,
                                                     'ATTR_NOT_SPECIFIED'))
    is_attr_set = attributes.is_attr_set
    validators = attributes.validators
    n_c_attr_names = n_c.my_globals

    def get_plugin(service=None):
        if service is None:
            return manager.NeutronManager.get_plugin()
        else:
            return manager.NeutronManager.get_service_plugins().get(service)
core_opts = base_config.core_opts
#extensions = extensions
#model_base = model_base

# Bring in the union of all constants in neutron.common.constants
# and neutron_lib.constants. Handle any duplicates by using the
# values in neutron_lib.
#
# In the plugin code, replace the following imports:
#     from neutron.common import constants
#     from neutron_lib import constants
# with (something like this):
#     from networking_cisco import backward_compatibility as bc
# Then constants are referenced as shown in this example:
#     port['devide_owner'] = bc.constants.DEVICE_OWNER_ROUTER_INTF

ignore = frozenset(['__builtins__', '__doc__', '__file__', '__name__',
                    '__package__', '__path__', '__version__'])
for attr_name in n_c_attr_names:
    attr = getattr(n_c, attr_name)
    if attr_name in ignore or isinstance(attr, ModuleType):
        continue
    else:
        setattr(constants, attr_name, attr)
del n_c, ignore, attr_name, attr
