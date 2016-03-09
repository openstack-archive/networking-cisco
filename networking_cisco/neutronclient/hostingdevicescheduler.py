# Copyright 2015 Cisco Systems, Inc.
# All Rights Reserved
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
#

from __future__ import print_function

from networking_cisco._i18n import _

from neutronclient.common import extension
from neutronclient.neutron import v2_0 as neutronV20


HOSTING_DEVICE = 'hosting_device'
CFG_AGENT_HOSTING_DEVICES = '/cfg-agent-hosting-devices'


class HostingDeviceHandledByConfigAgent(extension.NeutronClientExtension):
    resource = HOSTING_DEVICE
    resource_plural = '%ss' % resource
    object_path = '/dev_mgr/%s' % resource_plural
    resource_path = '/dev_mgr/%s/%%s' % resource_plural
    versions = ['2.0']
    allow_names = True


class HostingDeviceAssociateWithConfigAgent(extension.ClientExtensionCreate,
                                            HostingDeviceHandledByConfigAgent):

    shell_command = 'cisco-config-agent-associate-hosting-device'

    def get_parser(self, prog_name):
        parser = super(HostingDeviceAssociateWithConfigAgent, self).get_parser(
            prog_name)
        parser.add_argument(
            'config_agent_id',
            help=_('Id of the Cisco configuration agent.'))
        parser.add_argument(
            'hosting_device',
            help=_('Name or id of hosting device to associate.'))
        return parser

    def execute(self, parsed_args):
        self.log.debug('run(%s)' % parsed_args)
        neutron_client = self.get_client()
        neutron_client.format = parsed_args.request_format
        _id_hd = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, 'hosting_device', parsed_args.hosting_device)
        self.associate_hosting_device_with_config_agent(
            neutron_client, parsed_args.config_agent_id,
            {'hosting_device_id': _id_hd})
        print(_('Associated hosting device \'%(hd)s\' with Cisco '
                'configuration agent \'%(agent)s\'') % {
            'hd': parsed_args.hosting_device,
            'agent': parsed_args.config_agent_id}, file=self.app.stdout,
            end='')
        return [], []

    def associate_hosting_device_with_config_agent(
            self, client, config_agent_id, body):
        """Associates a hosting_device with a config agent."""
        return client.post((ConfigAgentHandlingHostingDevice.resource_path +
                            CFG_AGENT_HOSTING_DEVICES) % config_agent_id,
                           body=body)


class HostingDeviceDisassociateFromConfigAgent(
        extension.ClientExtensionCreate, HostingDeviceHandledByConfigAgent):

    shell_command = 'cisco-config-agent-disassociate-hosting-device'

    def get_parser(self, prog_name):
        parser = super(HostingDeviceDisassociateFromConfigAgent,
                       self).get_parser(prog_name)
        parser.add_argument(
            'config_agent_id',
            help=_('Id of the Cisco configuration agent.'))
        parser.add_argument(
            'hosting_device',
            help=_('Name or id of hosting device to disassociate.'))
        return parser

    def execute(self, parsed_args):
        self.log.debug('run(%s)' % parsed_args)
        neutron_client = self.get_client()
        neutron_client.format = parsed_args.request_format
        _id_hd = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, 'hosting_device', parsed_args.hosting_device)
        self.disassociate_hosting_device_with_config_agent(
            neutron_client, parsed_args.config_agent_id, _id_hd)
        print(_('Disassociated hosting device \'%(hd)s\' from Cisco '
                'configuration agent \'%(agent)s\'') % {
            'hd': parsed_args.hosting_device,
            'agent': parsed_args.config_agent_id}, file=self.app.stdout,
            end='')
        return [], []

    def disassociate_hosting_device_with_config_agent(
            self, client, config_agent_id, hosting_device_id):
        """Disassociates a hosting_device with a config agent."""
        return client.delete((ConfigAgentHandlingHostingDevice.resource_path +
                              CFG_AGENT_HOSTING_DEVICES + "/%s") % (
            config_agent_id, hosting_device_id))


class HostingDeviceHandledByConfigAgentList(extension.ClientExtensionList,
                                            HostingDeviceHandledByConfigAgent):
    shell_command = 'cisco-config-agent-list-hosting-devices'
    list_columns = ['id', 'name', 'admin_state_up', 'template_id']

    def get_parser(self, prog_name):
        parser = super(HostingDeviceHandledByConfigAgentList,
                       self).get_parser(prog_name)
        parser.add_argument(
            'config_agent_id',
            help=_('Id of the Cisco configuration agent to query.'))
        return parser

    def call_server(self, neutron_client, search_opts, parsed_args):
        data = self.list_hosting_device_handled_by_config_agent(
            neutron_client, parsed_args.config_agent_id, **search_opts)
        return data

    def list_hosting_device_handled_by_config_agent(
            self, client, cfg_agent_id, **_params):
        """Fetches a list of hosting devices handled by a config agent."""
        return client.get((ConfigAgentHandlingHostingDevice.resource_path +
                           CFG_AGENT_HOSTING_DEVICES) % cfg_agent_id,
                          params=_params)


AGENT = 'agent'
HOSTING_DEVICE_CFG_AGENTS = '/hosting-device-cfg-agents'


class ConfigAgentHandlingHostingDevice(extension.NeutronClientExtension):
    resource = AGENT
    resource_plural = '%ss' % resource
    object_path = '/%s' % resource_plural
    resource_path = '/%s/%%s' % resource_plural
    versions = ['2.0']
    allow_names = True


class ConfigAgentHandlingHostingDeviceList(extension.ClientExtensionList,
                                           ConfigAgentHandlingHostingDevice):

    shell_command = 'cisco-hosting-device-list-config-agents'
    list_columns = ['id', 'alive', 'agent_type', 'admin_state_up', 'host']

    def extend_list(self, data, parsed_args):
        for agent in data:
            agent['alive'] = ":-)" if agent.get('alive') else 'xxx'

    def get_parser(self, prog_name):
        parser = super(ConfigAgentHandlingHostingDeviceList, self).get_parser(
            prog_name)
        parser.add_argument('hosting_device',
                            help=_('Name or id of hosting device to query.'))
        return parser

    def call_server(self, neutron_client, search_opts, parsed_args):
        _id = neutronV20.find_resourceid_by_name_or_id(
            neutron_client, 'hosting_device', parsed_args.hosting_device)
        data = self.list_config_agents_handling_hosting_device(
            neutron_client, _id, **search_opts)
        return data

    def list_config_agents_handling_hosting_device(
            self, client, hosting_device_id, **_params):
        """Fetches a list of config agents handling a hosting device."""
        resource_path = '/dev_mgr/hosting_devices/%s'
        return client.get((resource_path + HOSTING_DEVICE_CFG_AGENTS) %
                          hosting_device_id, params=_params)
