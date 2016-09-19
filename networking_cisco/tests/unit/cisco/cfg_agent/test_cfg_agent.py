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

import mock
from oslo_config import cfg
from oslo_utils import uuidutils
import testtools

from neutron.agent.common import config
from neutron.common import constants as l3_constants
from neutron.tests import base

from networking_cisco import backwards_compatibility as bc_attr
from networking_cisco.plugins.cisco.cfg_agent import cfg_agent


_uuid = uuidutils.generate_uuid
HOSTNAME = 'myhost'
FAKE_ID = _uuid()


def prepare_router_data(enable_snat=None, num_internal_ports=1):
    router_id = _uuid()
    ex_gw_port = {'id': _uuid(),
                  'network_id': _uuid(),
                  'fixed_ips': [{'ip_address': '19.4.4.4',
                                 'subnet_id': _uuid()}],
                  'subnet': {'cidr': '19.4.4.0/24',
                             'gateway_ip': '19.4.4.1'}}
    int_ports = []
    for i in range(num_internal_ports):
        int_ports.append({'id': _uuid(),
                          'network_id': _uuid(),
                          'admin_state_up': True,
                          'fixed_ips': [{'ip_address': '35.4.%s.4' % i,
                                         'subnet_id': _uuid()}],
                          'mac_address': 'ca:fe:de:ad:be:ef',
                          'subnet': {'cidr': '35.4.%s.0/24' % i,
                                     'gateway_ip': '35.4.%s.1' % i}})
    hosting_device = {'id': _uuid(),
                      'host_type': 'CSR1kv',
                      'ip_address': '20.0.0.5',
                      'port': '23'}

    router = {
        'id': router_id,
        l3_constants.INTERFACE_KEY: int_ports,
        'routes': [],
        'gw_port': ex_gw_port,
        'hosting_device': hosting_device}
    if enable_snat is not None:
        router['enable_snat'] = enable_snat
    return router, int_ports


class TestCiscoCfgAgentWithStateReporting(base.BaseTestCase):

    def setUp(self):
        self.conf = cfg.ConfigOpts()
        config.register_agent_state_opts_helper(cfg.CONF)
        self.conf.register_opts(bc_attr.core_opts)
        self.conf.register_opts(cfg_agent.OPTS, "cfg_agent")
        cfg.CONF.set_override('report_interval', 0, 'AGENT')
        super(TestCiscoCfgAgentWithStateReporting, self).setUp()
        self.devmgr_plugin_api_cls_p = mock.patch(
            'networking_cisco.plugins.cisco.cfg_agent.cfg_agent.'
            'CiscoDeviceManagementApi')
        devmgr_plugin_api_cls = self.devmgr_plugin_api_cls_p.start()
        self.devmgr_plugin_api = mock.Mock()
        devmgr_plugin_api_cls.return_value = self.devmgr_plugin_api
        self.devmgr_plugin_api.register_for_duty.return_value = True

        self.plugin_reportstate_api_cls_p = mock.patch(
            'neutron.agent.rpc.PluginReportStateAPI')
        plugin_reportstate_api_cls = self.plugin_reportstate_api_cls_p.start()
        self.plugin_reportstate_api = mock.Mock()
        plugin_reportstate_api_cls.return_value = self.plugin_reportstate_api

        self.looping_call_p = mock.patch(
            'oslo_service.loopingcall.FixedIntervalLoopingCall')
        self.looping_call_p.start()

        mock.patch('neutron.common.rpc.create_connection').start()

    def test_agent_registration_success(self):
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        self.assertTrue(agent.devmgr_rpc.register_for_duty(agent.context))

    def test_agent_registration_success_after_2_tries(self):
        self.devmgr_plugin_api.register_for_duty = mock.Mock(
            side_effect=[False, False, True])
        cfg_agent.REGISTRATION_RETRY_DELAY = 0.01
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        self.assertEqual(3, agent.devmgr_rpc.register_for_duty.call_count)

    def test_agent_registration_fail_always(self):
        self.devmgr_plugin_api.register_for_duty = mock.Mock(
            return_value=False)
        cfg_agent.REGISTRATION_RETRY_DELAY = 0.01
        cfg_agent.MAX_REGISTRATION_ATTEMPTS = 3
        with testtools.ExpectedException(SystemExit):
            cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)

    def test_agent_registration_no_device_mgr(self):
        self.devmgr_plugin_api.register_for_duty = mock.Mock(
            return_value=None)
        cfg_agent.REGISTRATION_RETRY_DELAY = 0.01
        cfg_agent.MAX_REGISTRATION_ATTEMPTS = 3
        with testtools.ExpectedException(SystemExit):
            cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)

    def test_report_state(self):
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        # Set keepalive iteration to just before the reporting iteration
        agent.keepalive_iteration = self.conf.cfg_agent.report_iteration - 1
        agent._report_state()
        self.assertIn('total routers', agent.agent_state['configurations'])
        self.assertEqual(0,
                         agent.agent_state['configurations']['total routers'])

    def test_report_state_report_iteration_check_full_report(self):
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        # Set keepalive iteration to just before the reporting iteration
        agent.keepalive_iteration = self.conf.cfg_agent.report_iteration - 1
        agent._report_state()
        self.assertIn('total routers', agent.agent_state['configurations'])
        self.assertEqual(0, agent.agent_state[
            'configurations']['total routers'])
        self.assertEqual(0, agent.keepalive_iteration)

    def test_report_state_report_iteration_check_partial_report(self):
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        # Retain original keepalive iteration
        agent.keepalive_iteration = self.conf.cfg_agent.report_iteration
        agent._report_state()
        self.assertNotIn('configurations', agent.agent_state)
        self.assertEqual((self.conf.cfg_agent.report_iteration + 1),
                         agent.keepalive_iteration)

    @mock.patch('networking_cisco.plugins.cisco.cfg_agent.'
                'cfg_agent.CiscoCfgAgentWithStateReport._agent_registration')
    def test_report_state_attribute_error(self, agent_registration):
        cfg.CONF.set_override('report_interval', 1, 'AGENT')
        self.plugin_reportstate_api.report_state.side_effect = AttributeError
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        agent.heartbeat = mock.Mock()
        agent.send_agent_report(None, None)
        self.assertTrue(agent.heartbeat.stop.called)

    def test_get_hosting_device_configuration(self):
        routing_service_helper_mock = mock.MagicMock()
        routing_service_helper_mock.driver_manager = mock.MagicMock()
        drv_mgr = routing_service_helper_mock.driver_manager
        drv = drv_mgr.get_driver_for_hosting_device.return_value
        fake_running_config = 'a fake running config'
        drv.get_configuration = mock.MagicMock(
            return_value=fake_running_config)
        hd_id = 'a_hd_id'
        payload = {'hosting_device_id': hd_id}
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        agent.routing_service_helper = routing_service_helper_mock
        res = agent.get_hosting_device_configuration(mock.MagicMock(), payload)
        self.assertEqual(fake_running_config, res)
        drv.get_configuration.assert_called_once_with()

    def test_get_hosting_device_configuration_no_hosting_device(self):
        routing_service_helper_mock = mock.MagicMock()
        routing_service_helper_mock.driver_manager = mock.MagicMock()
        drv_mgr = routing_service_helper_mock.driver_manager
        drv = drv_mgr.get_driver_for_hosting_device.return_value
        fake_running_config = 'a fake running config'
        drv.get_configuration = mock.MagicMock(
            return_value=fake_running_config)
        hd_id = None
        payload = {'hosting_device_id': hd_id}
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        agent.routing_service_helper = routing_service_helper_mock
        res = agent.get_hosting_device_configuration(mock.MagicMock(), payload)
        self.assertIsNone(res)
        drv.get_configuration.assert_not_called()

    def test_get_hosting_device_configuration_no_svc_helper(self):
        routing_service_helper_mock = mock.MagicMock()
        routing_service_helper_mock.driver_manager = mock.MagicMock()
        drv_mgr = routing_service_helper_mock.driver_manager
        drv = drv_mgr.get_driver_for_hosting_device.return_value
        fake_running_config = 'a fake running config'
        drv.get_configuration = mock.MagicMock(
            return_value=fake_running_config)
        hd_id = 'a_hd_id'
        payload = {'hosting_device_id': hd_id}
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        agent.routing_service_helper = None
        res = agent.get_hosting_device_configuration(mock.MagicMock(), payload)
        self.assertIsNone(res)
        drv.get_configuration.assert_not_called()

    def test_plugin_notified_about_revived_hosting_devices_heartbeat_on(self):
        self.conf.set_override('enable_heartbeat', True, 'cfg_agent')
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        _dev_status_mock = mock.MagicMock()
        ids_revived_hds = ['fake_hd_id1', 'fake_hd_id2']
        _dev_status_mock.check_backlogged_hosting_devices.return_value = {
            'reachable': [], 'dead': [], 'revived': ids_revived_hds}
        with mock.patch.object(agent, '_dev_status', _dev_status_mock),\
                mock.patch.object(agent, 'process_services') as p_s_mock,\
                mock.patch.object(agent, 'devmgr_rpc') as d_r_mock:
            ctx = mock.MagicMock()
            agent._process_backlogged_hosting_devices(ctx)
        p_s_mock.assert_called_with(device_ids=ids_revived_hds)
        d_r_mock.report_revived_hosting_devices.assert_called_with(
            ctx, hd_ids=ids_revived_hds)

    def test_plugin_not_notified_about_revived_hosting_devices_heartbeat_off(
            self):
        self.conf.set_override('enable_heartbeat', False, 'cfg_agent')
        agent = cfg_agent.CiscoCfgAgentWithStateReport(HOSTNAME, self.conf)
        _dev_status_mock = mock.MagicMock()
        ids_revived_hds = ['fake_hd_id1', 'fake_hd_id2']
        _dev_status_mock.check_backlogged_hosting_devices.return_value = {
            'reachable': [], 'dead': [], 'revived': ids_revived_hds}
        with mock.patch.object(agent, '_dev_status', _dev_status_mock),\
                mock.patch.object(agent, 'process_services') as p_s_mock,\
                mock.patch.object(agent, 'devmgr_rpc') as d_r_mock:
            ctx = mock.MagicMock()
            agent._process_backlogged_hosting_devices(ctx)
        self.assertEqual(0, p_s_mock.call_count)
        self.assertEqual(0, d_r_mock.report_revived_hosting_devices.call_count)
