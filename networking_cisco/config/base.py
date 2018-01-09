# Copyright (c) 2016 Cisco Systems
# All Rights Reserved.
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

from oslo_config import cfg
from oslo_config import types


class RemainderOpt(cfg.DictOpt):

    """A greedy dictionary option

    This option will greedily parse any unparsed options in the config section
    this option is included in storing them in a dictionary structure. For
    example:

    A config file like this::

        [section_a]
        host1=value1
        host2=value2

    with a RemainderOpt option defined like::

        opts = [
            RemainderOpt('hosts')
        ]
        cfg.CONF.register_opts(opts, "section_a")

    Results in a dictionary like::

        hosts: {
           host1: value1,
           host2: value2
        }

    which is accessed using the oslo config object being used, for example::

        cfg.CONF['hosts']['host1']
    """

    def __init__(self, name, item_type=None, **kwargs):
        super(RemainderOpt, self).__init__(name, **kwargs)
        if not item_type:
            item_type = types.String()
        self.item_type = item_type

    def _get_opts_including_deprecated(self, namespace, group_name):
        opts = namespace._conf._get_group(group_name)._opts
        opt_names = list(opts)
        for name, opt in opts.items():
            opt_names.extend([x.name for x in opt['opt'].deprecated_opts])
        return opt_names

    def _get_from_namespace(self, namespace, group_name):
        opt_names = self._get_opts_including_deprecated(namespace,
                                                        group_name)
        result = {}
        for section in namespace._parsed:
            gk = section.get(group_name)
            if not gk:
                continue
            for key in gk:
                if key not in opt_names:
                    names = [(group_name, key)]
                    value = namespace._get_value(
                        names, positional=self.positional)
                    result[key] = self.item_type(value)
        return result


class SubsectionOpt(cfg.DictOpt):

    """An option for parsing multiple sections with sub-IDs

    This option allows to parse multiple defintions of the same config section
    which have unique IDs. For example::

        [switch:switch1]
        address=1.1.1.1
        password=p1

        [switch:switch2]
        address=2.2.2.2
        password=p2

    Both sections are type "switch" and will provide the same configuration
    options, but one is switch1 and the other is for switch2.

    Using this option this can be represented like::

        SubsectionOpt("switch",
                      dest="switches",
                      subopts=[StrOpt('address')
                               StrOpt('password')])

    When parsed the above config file example will result in a dictionary in
    the form::

        switches: {
            switch1: {
                address: 1.1.1.1,
                password: p1
            },
            switch2: {
                address: 2.2.2.2,
                password: p2
            }
        }
    """

    def __init__(self, name, subopts=None, **kwargs):
        super(SubsectionOpt, self).__init__(name, **kwargs)
        self.subopts = subopts or []

    def _get_from_namespace(self, namespace, group_name):
        identities = {}
        sections = cfg.CONF.list_all_sections()
        for section in sections:
            subsection, sep, ident = section.partition(':')
            if subsection.lower() != self.name.lower():
                continue
            cfg.CONF.register_opts(self.subopts, group=section)
            identities[ident] = cfg.CONF.get(section)
        return identities
