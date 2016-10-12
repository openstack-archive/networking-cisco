# Copyright 2014 Cisco Systems, Inc.  All rights reserved.
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

import copy
from datetime import datetime

import mock
from novaclient import exceptions as nova_exc
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from oslo_utils import importutils
from oslo_utils import timeutils
from oslo_utils import uuidutils

from networking_cisco._i18n import _LE

from neutron.api.v2 import attributes
from neutron.common import constants as common_constants
from neutron.common import test_lib
from neutron import context as n_context
from neutron.db import agents_db
from neutron.extensions import agent
from neutron import manager
from neutron.tests.unit.extensions import test_l3
from neutron_lib import constants as lib_constants

import networking_cisco
from networking_cisco import plugins
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.db.device_manager import (
    hosting_device_manager_db)
from networking_cisco.plugins.cisco.db.scheduler import cfg_agentschedulers_db
from networking_cisco.plugins.cisco.device_manager.rpc import (
    devices_cfgagent_rpc_cb)
from networking_cisco.plugins.cisco.device_manager.rpc import (
    devmgr_rpc_cfgagent_api)
from networking_cisco.plugins.cisco.extensions import (
    ciscocfgagentscheduler as cfgagtscheduler)
from networking_cisco.plugins.cisco.extensions import (
    ciscohostingdevicemanager as ciscodevmgr)


LOG = logging.getLogger(__name__)


_uuid = uuidutils.generate_uuid
ISO8601_TIME_FORMAT = common_constants.ISO8601_TIME_FORMAT

CORE_PLUGIN_KLASS = (
    'networking_cisco.tests.unit.cisco.device_manager'
    '.device_manager_test_support.TestCorePlugin')
extensions_path = (':' + plugins.__path__[0] + '/cisco/extensions')

L3_CFG_HOST_A = 'host_a'
L3_CFG_HOST_B = 'host_b'
L3_CFG_HOST_C = 'host_c'


class DeviceManagerTestSupportMixin(object):

    @property
    def _core_plugin(self):
        return manager.NeutronManager.get_plugin()

    def _mock_l3_admin_tenant(self):
        # Mock l3 admin tenant
        self.tenant_id_fcn_p = mock.patch(
            'networking_cisco.plugins.cisco.db.device_manager.'
            'hosting_device_manager_db.HostingDeviceManagerMixin.l3_tenant_id')
        self.tenant_id_fcn = self.tenant_id_fcn_p.start()
        self.tenant_id_fcn.return_value = "L3AdminTenantId"

    def _create_mgmt_nw_for_tests(self, fmt):
        self._mgmt_nw = self._make_network(fmt,
                                           cfg.CONF.general.management_network,
                                           True, tenant_id="L3AdminTenantId",
                                           shared=False)
        self._mgmt_subnet = self._make_subnet(fmt, self._mgmt_nw,
                                              "10.0.100.1", "10.0.100.0/24",
                                              ip_version=4)

    def _remove_mgmt_nw_for_tests(self):
        q_p = "network_id=%s" % self._mgmt_nw['network']['id']
        subnets = self._list('subnets', query_params=q_p)
        if subnets:
            for p in self._list('ports', query_params=q_p).get('ports'):
                self._delete('ports', p['id'])
            self._delete('subnets', self._mgmt_subnet['subnet']['id'])
            self._delete('networks', self._mgmt_nw['network']['id'])
        hosting_device_manager_db.HostingDeviceManagerMixin._mgmt_nw_uuid = (
            None)
        hosting_device_manager_db.HostingDeviceManagerMixin._mgmt_subnet_uuid\
            = None

    # Function used to mock novaclient services list
    def _novaclient_services_list(self, all=True):
        services = set(['nova-conductor', 'nova-cert', 'nova-scheduler',
                        'nova-compute'])
        full_list = [FakeResource(binary=res) for res in services]
        _all = all

        def response():
            if _all:
                return full_list
            else:
                return full_list[2:]
        return response

    # Function used to mock novaclient servers create
    def _novaclient_servers_create(self, instance_name, image_id, flavor_id,
                                   nics, files, config_drive):
        fake_vm = FakeResource()
        for nic in nics:
            p_dict = {'port': {'device_id': fake_vm.id,
                               'device_owner': 'nova'}}
            self._core_plugin.update_port(n_context.get_admin_context(),
                                          nic['port-id'], p_dict)
        return fake_vm

    # Function used to mock novaclient servers delete
    def _novaclient_servers_delete(self, vm_id):
        q_p = "device_id=%s" % vm_id
        ports = self._list('ports', query_params=q_p)
        for port in ports.get('ports', []):
            try:
                self._delete('ports', port['id'])
            except Exception as e:
                with excutils.save_and_reraise_exception(reraise=False):
                    LOG.error(_LE('Failed to delete port %(p_id)s for vm '
                                  'instance %(v_id)s due to %(err)s'),
                              {'p_id': port['id'], 'v_id': vm_id, 'err': e})
                    raise nova_exc.InternalServerError()

    def _mock_svc_vm_create_delete(self, plugin):
        # Mock novaclient methods for creation/deletion of service VMs
        mock.patch(
            'networking_cisco.plugins.cisco.device_manager.service_vm_lib.'
            'n_utils.find_resource',
            lambda *args, **kw: FakeResource()).start()
        self._nclient_services_mock = mock.MagicMock()
        self._nclient_services_mock.list = self._novaclient_services_list()
        mock.patch.object(plugin._svc_vm_mgr_obj._nclient, 'services',
                          self._nclient_services_mock).start()
        nclient_servers_mock = mock.MagicMock()
        nclient_servers_mock.create = self._novaclient_servers_create
        nclient_servers_mock.delete = self._novaclient_servers_delete
        mock.patch.object(plugin._svc_vm_mgr_obj._nclient, 'servers',
                          nclient_servers_mock).start()

    def _mock_dispatch_pool_maintenance(self):
        # Mock creation/deletion of service VMs
        dispatch_pool_maintenance_job_fcn_p = mock.patch(
            'networking_cisco.plugins.cisco.db.device_manager.'
            'hosting_device_manager_db.HostingDeviceManagerMixin.'
            '_dispatch_pool_maintenance_job')
        dispatch_pool_maintenance_job_fcn_p .start()

    def _mock_eventlet_greenpool_spawn_n(self):
        # Mock GreenPool's spawn_n to execute the specified function directly
        self._greenpool_mock = mock.MagicMock()
        self._greenpool_mock.return_value.spawn_n = (
            lambda f, *args, **kwargs: f(*args, **kwargs))
        _eventlet_greenpool_fcn_p = mock.patch(
            'networking_cisco.plugins.cisco.db.device_manager.'
            'hosting_device_manager_db.eventlet.GreenPool',
            self._greenpool_mock)
        _eventlet_greenpool_fcn_p.start()

    def _mock_io_file_ops(self):
        # Mock library functions for config drive file operations
        cfg_template = '\n'.join(['interface GigabitEthernet1',
                                  'ip address <ip> <mask>',
                                  'no shutdown'])
        m = mock.mock_open(read_data=cfg_template)
        m.return_value.__iter__.return_value = cfg_template.splitlines()
        mock.patch('networking_cisco.plugins.cisco.device_manager.'
                   'hosting_device_drivers.csr1kv_hd_driver.open', m,
                   create=True).start()

    def _test_remove_all_hosting_devices(self):
        """Removes all hosting devices created during a test."""
        devmgr = manager.NeutronManager.get_service_plugins()[
            cisco_constants.DEVICE_MANAGER]
        context = n_context.get_admin_context()
        devmgr.delete_all_hosting_devices(context, True)

    def _get_fake_resource(self, tenant_id=None, id=None):
        return {'id': id or _uuid(),
                'tenant_id': tenant_id or _uuid()}

    def _get_test_context(self, user_id=None, tenant_id=None, is_admin=False):
        return n_context.Context(user_id, tenant_id, is_admin)

    def _mock_cfg_agent_notifier(self, plugin):
        # Mock notifications to l3 agent and Cisco config agent
        self._l3_agent_mock = mock.MagicMock()
        self._cfg_agent_mock = mock.MagicMock()
        self._l3_cfg_agent_mock = mock.MagicMock()
        plugin.agent_notifiers = {
            lib_constants.AGENT_TYPE_L3: self._l3_agent_mock,
            cisco_constants.AGENT_TYPE_CFG: self._cfg_agent_mock,
            cisco_constants.AGENT_TYPE_L3_CFG: self._l3_cfg_agent_mock}

    def _define_keystone_authtoken(self):
        test_opts = [
            cfg.StrOpt('auth_url', default='http://localhost:35357/v2.0/'),
            cfg.StrOpt('identity_uri', default='http://localhost:5000'),
            #cfg.StrOpt('admin_user', default='neutron'),
            cfg.StrOpt('username', default='neutron'),
            #cfg.StrOpt('admin_password', default='secrete'),
            cfg.StrOpt('password', default='secrete'),
            cfg.StrOpt('project_name', default='service'),
            cfg.StrOpt('project_domain_id', default='default'),
            cfg.StrOpt('user_domain_id', default='default')]
        cfg.CONF.register_opts(test_opts, 'keystone_authtoken')

    def _add_device_manager_plugin_ini_file(self):
        # includes config files for device manager service plugin
        cfg_file = (
            networking_cisco.__path__[0] +
            '/tests/unit/cisco/etc/cisco_device_manager_plugin.ini')
        if 'config_files' in test_lib.test_config:
            test_lib.test_config['config_files'].append(cfg_file)
        else:
            test_lib.test_config['config_files'] = [cfg_file]

    def _register_cfg_agent_states(self, host_a_active=True,
                                   host_b_active=False,
                                   host_c_active=False):
        """Register zero, one, two, or three L3 config agents."""
        l3_cfg_host_a = {
            'binary': 'neutron-cisco-cfg-agent',
            'host': L3_CFG_HOST_A,
            'topic': cisco_constants.CFG_AGENT,
            'configurations': {
                'service_agents': [cisco_constants.AGENT_TYPE_L3_CFG],
                'total routers': 0,
                'total ex_gw_ports': 0,
                'total interfaces': 0,
                'total floating_ips': 0,
                'hosting_devices': 0,
                'non_responding_hosting_devices': {}},
            'local_time': str(timeutils.utcnow()),
            'agent_type': cisco_constants.AGENT_TYPE_CFG}
        agent_callback = agents_db.AgentExtRpcCallback()
        dev_mgr_callback = devices_cfgagent_rpc_cb.DeviceMgrCfgRpcCallback(
            manager.NeutronManager.get_service_plugins()[
                cisco_constants.DEVICE_MANAGER])
        if host_a_active is True:
            agent_callback.report_state(
                self.adminContext,
                agent_state={'agent_state': l3_cfg_host_a},
                time=datetime.utcnow().strftime(ISO8601_TIME_FORMAT))
            dev_mgr_callback.register_for_duty(self.adminContext,
                                               L3_CFG_HOST_A)
        if host_b_active is True:
            l3_cfg_host_b = copy.deepcopy(l3_cfg_host_a)
            l3_cfg_host_b['host'] = L3_CFG_HOST_B
            l3_cfg_host_b['local_time'] = str(timeutils.utcnow()),
            agent_callback.report_state(
                self.adminContext, agent_state={'agent_state': l3_cfg_host_b},
                time=datetime.utcnow().strftime(ISO8601_TIME_FORMAT))
            dev_mgr_callback.register_for_duty(self.adminContext,
                                               L3_CFG_HOST_B)
        if host_c_active is True:
            l3_cfg_host_c = copy.deepcopy(l3_cfg_host_a)
            l3_cfg_host_c['host'] = L3_CFG_HOST_C
            l3_cfg_host_c['local_time'] = str(timeutils.utcnow()),
            agent_callback.report_state(
                self.adminContext, agent_state={'agent_state': l3_cfg_host_c},
                time=datetime.utcnow().strftime(ISO8601_TIME_FORMAT))
            dev_mgr_callback.register_for_duty(self.adminContext,
                                               L3_CFG_HOST_B)


class TestDeviceManagerExtensionManager(object):

    def get_resources(self):
        res = ciscodevmgr.Ciscohostingdevicemanager.get_resources()
        # add agent resource
        for item in agent.Agent.get_resources():
            res.append(item)
        # add hosting device to cfg agent scheduler resources
        for item in cfgagtscheduler.Ciscocfgagentscheduler.get_resources():
            res.append(item)
        # Add the resources to the global attribute map
        # This is done here as the setup process won't
        # initialize the main API router which extends
        # the global attribute map
        attributes.RESOURCE_ATTRIBUTE_MAP.update(
            ciscodevmgr.RESOURCE_ATTRIBUTE_MAP)
        return res

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []


# A core plugin supporting Cisco device manager and hosting device to cfg
# agent scheduling functionality
class TestCorePlugin(test_l3.TestNoL3NatPlugin,
                     cfg_agentschedulers_db.CfgAgentSchedulerDbMixin,
                     hosting_device_manager_db.HostingDeviceManagerMixin):

    supported_extension_aliases = [
        "agent", "external-net",
        cfgagtscheduler.CFG_AGENT_SCHEDULER_ALIAS,
        ciscodevmgr.HOSTING_DEVICE_MANAGER_ALIAS]

    def __init__(self):
        super(TestCorePlugin, self).__init__()
        self.cfg_agent_scheduler = importutils.import_object(
            cfg.CONF.general.configuration_agent_scheduler_driver)
        self.agent_notifiers[cisco_constants.AGENT_TYPE_CFG] = (
            devmgr_rpc_cfgagent_api.DeviceMgrCfgAgentNotifyAPI(self))

    def cleanup_after_test(self):
        """This function should be called in the TearDown() function of
        test classes that use the plugin.

        Reset all class variables to their default values.
        This is needed to avoid tests to pollute subsequent tests.
        """
        TestCorePlugin._l3_tenant_uuid = None
        TestCorePlugin._mgmt_nw_uuid = None
        TestCorePlugin._mgmt_subnet_uuid = None
        TestCorePlugin._mgmt_sec_grp_id = None
        TestCorePlugin._credentials = {}
        TestCorePlugin._plugging_drivers = {}
        TestCorePlugin._hosting_device_drivers = {}
        TestCorePlugin._hosting_device_locks = {}
        TestCorePlugin._cfgagent_scheduler = None
        TestCorePlugin._cfg_agent_statuses = {}
        TestCorePlugin._svc_vm_mgr_obj = None
        TestCorePlugin._nova_running = False


# Used to fake Glance images, Nova VMs and Nova services
class FakeResource(object):
    def __init__(self, id=None, enabled='enabled', state='up', binary=None):
        self.id = id or _uuid()
        self.status = enabled
        self.state = state
        self.binary = binary
