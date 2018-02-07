# Copyright 2015 Cisco Systems, Inc.  All rights reserved.
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
import mock

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import uuidutils
from sqlalchemy.orm import exc as db_exc
from webob import exc

from networking_cisco import backwards_compatibility as bc
from networking_cisco.backwards_compatibility import l3_const
from networking_cisco.backwards_compatibility import l3_exceptions
from networking_cisco.plugins.cisco.common import cisco_constants
from networking_cisco.plugins.cisco.db.l3.l3_router_appliance_db import (
    L3RouterApplianceDBMixin)
from networking_cisco.plugins.cisco.extensions import ha
from networking_cisco.plugins.cisco.extensions import routerhostingdevice
from networking_cisco.plugins.cisco.extensions import routerrole
from networking_cisco.plugins.cisco.extensions import routertype
from networking_cisco.plugins.cisco.extensions import routertypeawarescheduler
from networking_cisco.plugins.cisco.l3.drivers.asr1k import (
    asr1k_routertype_driver as drv)
from networking_cisco.tests.unit.cisco.l3 import (
    test_ha_l3_router_appliance_plugin as cisco_ha_test)
from networking_cisco.tests.unit.cisco.l3 import (
    test_l3_routertype_aware_schedulers as cisco_test_case)

LOG = logging.getLogger(__name__)


_uuid = uuidutils.generate_uuid

DEVICE_OWNER_ROUTER_INTF = bc.constants.DEVICE_OWNER_ROUTER_INTF
EXTERNAL_GW_INFO = l3_const.EXTERNAL_GW_INFO
AGENT_TYPE_L3_CFG = cisco_constants.AGENT_TYPE_L3_CFG

ROUTER_ROLE_GLOBAL = cisco_constants.ROUTER_ROLE_GLOBAL
ROUTER_ROLE_LOGICAL_GLOBAL = cisco_constants.ROUTER_ROLE_LOGICAL_GLOBAL
ROUTER_ROLE_HA_REDUNDANCY = cisco_constants.ROUTER_ROLE_HA_REDUNDANCY
LOGICAL_ROUTER_ROLE_NAME = cisco_constants.LOGICAL_ROUTER_ROLE_NAME
ROUTER_INFO_INCOMPLETE = cisco_constants.ROUTER_INFO_INCOMPLETE

DEVICE_OWNER_GLOBAL_ROUTER_GW = cisco_constants.DEVICE_OWNER_GLOBAL_ROUTER_GW
AUXILIARY_GATEWAY_KEY = cisco_constants.AUXILIARY_GATEWAY_KEY

ROUTER_ROLE_ATTR = routerrole.ROUTER_ROLE_ATTR
HOSTING_DEVICE_ATTR = routerhostingdevice.HOSTING_DEVICE_ATTR
AUTO_SCHEDULE_ATTR = routertypeawarescheduler.AUTO_SCHEDULE_ATTR

TestSchedulingL3RouterApplianceExtensionManager = (
    cisco_test_case.TestSchedulingL3RouterApplianceExtensionManager)


class Asr1kRouterTypeDriverTestCase(
        cisco_test_case.L3RoutertypeAwareHostingDeviceSchedulerTestCaseBase):

    # Nexus router type for ASR1k driver tests, why?
    #   - Yes(!), it does not matter and there is only one hosting device for
    #  that router type in the test setup which makes scheduling deterministic
    router_type = 'Nexus_ToR_Neutron_router'

    def _update(self, resource, id, new_data,
                expected_code=exc.HTTPOk.code,
                neutron_context=None,
                check_return_code=True):
        req = self.new_update_request(resource, new_data, id)
        if neutron_context:
            # create a specific auth context for this request
            req.environ['neutron.context'] = neutron_context
        res = req.get_response(self._api_for_resource(resource))
        if check_return_code is True:
            self.assertEqual(expected_code, res.status_int)
        elif res.status_int != expected_code:
            LOG.debug('Returned code (%(ret)s) != expected code (%(exp)s)',
                      {'ret': res.status_int, 'exp': expected_code})
        return self.deserialize(self.fmt, res)

    def _delete(self, collection, id,
                expected_code=exc.HTTPNoContent.code,
                neutron_context=None, check_return_code=True):
        req = self.new_delete_request(collection, id)
        if neutron_context:
            # create a specific auth context for this request
            req.environ['neutron.context'] = neutron_context
        res = req.get_response(self._api_for_resource(collection))
        if check_return_code is True:
            self.assertEqual(expected_code, res.status_int)
        elif res.status_int != expected_code:
            LOG.debug('Returned code (%(ret)s) != expected code (%(exp)s)',
                      {'ret': res.status_int, 'exp': expected_code})

    def _verify_global_router(self, role, hd_id, ext_net_ids):
        # The 'ext_net_ids' argument is a dict where key is ext_net_id and
        # value is a list of subnet_ids that the global router should be
        # connected to
        if role == ROUTER_ROLE_LOGICAL_GLOBAL or hd_id is None:
            q_p = '%s=%s' % (ROUTER_ROLE_ATTR, role)
        else:
            q_p = '%s=%s&%s=%s' % (ROUTER_ROLE_ATTR, role,
                                   HOSTING_DEVICE_ATTR, hd_id)
        routers = self._list('routers', query_params=q_p)['routers']
        if hd_id is None:
            self.assertEqual(0, len(routers))
        else:
            self.assertEqual(1, len(routers))
            router = routers[0]
            if role == ROUTER_ROLE_GLOBAL:
                self.assertTrue(router['name'].endswith(
                    hd_id[-cisco_constants.ROLE_ID_LEN:]))
            else:
                self.assertEqual(router['name'], LOGICAL_ROUTER_ROLE_NAME)
                self.assertFalse(router[AUTO_SCHEDULE_ATTR])
            self.assertIsNone(router[l3_const.EXTERNAL_GW_INFO])
            q_p = '%s=%s&%s=%s' % ('device_id', router['id'], 'device_owner',
                                   DEVICE_OWNER_GLOBAL_ROUTER_GW)
            aux_gw_ports = self._list('ports', query_params=q_p)['ports']
            self.assertEqual(len(ext_net_ids), len(aux_gw_ports))
            ids = copy.deepcopy(ext_net_ids)
            # check that there are ports on each external network
            for aux_gw_port in aux_gw_ports:
                self.assertIn(aux_gw_port['network_id'], ids)
                self.assertEqual(len(aux_gw_port['fixed_ips']),
                                 len(ids[aux_gw_port['network_id']]))
                # check that port has ip on correct subnets
                for ips in aux_gw_port['fixed_ips']:
                    self.assertIn(ips['subnet_id'],
                                  ids[aux_gw_port['network_id']])
                    ids[aux_gw_port['network_id']].remove(ips['subnet_id'])
                ids.pop(aux_gw_port['network_id'])
            return router['id']

    def _verify_routers(self, router_ids, ext_net_ids, hd_id=None,
                        call_indices=None):
        if call_indices is None:
            call_indices = [0]
        # tenant routers
        q_p = '%s=None' % ROUTER_ROLE_ATTR
        r_ids = {r['id'] for r in self._list(
            'routers', query_params=q_p)['routers']}
        self.assertEqual(len(r_ids), len(router_ids))
        for r_id in r_ids:
            self.assertIn(r_id, router_ids)
        # global router on hosting device
        g_rtr_id = self._verify_global_router(ROUTER_ROLE_GLOBAL, hd_id,
                                              ext_net_ids)
        # logical global router for global routers HA
        self._verify_global_router(ROUTER_ROLE_LOGICAL_GLOBAL, hd_id,
                                   ext_net_ids)
        notifier = self.l3_plugin.agent_notifiers[AGENT_TYPE_L3_CFG]
        if hd_id:
            for call_index in call_indices:
                # routers_updated notification call_index is for global router
                notify_call = notifier.method_calls[call_index]
                self.assertEqual(notify_call[0], 'routers_updated')
                updated_routers = notify_call[1][1]
                self.assertEqual(len(updated_routers), 1)
                self.assertEqual(updated_routers[0]['id'], g_rtr_id)
        # ensure *no* update notifications where sent for logical global router
        for call in notifier.method_calls:
            if call[0] == 'routers_updated':
                self.assertNotIn(call[1][1][0][ROUTER_ROLE_ATTR],
                                 [ROUTER_ROLE_LOGICAL_GLOBAL])
            elif call[0] == 'router_deleted':
                self.assertNotIn(call[1][1][ROUTER_ROLE_ATTR],
                                 [ROUTER_ROLE_LOGICAL_GLOBAL])

    def _test_create_gateway_router(self, set_context=False,
                                    same_tenant=True, same_ext_net=True):
        tenant_id_1 = _uuid()
        tenant_id_2 = tenant_id_1 if same_tenant is True else _uuid()
        with self.network(tenant_id=tenant_id_1) as n_external_1,\
                self.network(tenant_id=tenant_id_2) as n_external_2:
            ext_net_1_id = n_external_1['network']['id']
            self._set_net_external(ext_net_1_id)
            sn_1 = self._make_subnet(
                self.fmt, n_external_1, '10.0.1.1', cidr='10.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            ext_net_ids = {ext_net_1_id: [sn_1['id']]}
            ext_gw_1 = {'network_id': ext_net_1_id}
            if same_ext_net is False:
                ext_net_2_id = n_external_2['network']['id']
                self._set_net_external(ext_net_2_id)
                sn_2 = self._make_subnet(
                    self.fmt, n_external_2, '10.0.2.1', cidr='10.0.2.0/24',
                    tenant_id=tenant_id_2)['subnet']
                ext_gw_2_subnets = [sn_2['id']]
            else:
                ext_net_2_id = ext_net_1_id
                ext_gw_2_subnets = [sn_1['id']]
            ext_gw_2 = {'network_id': ext_net_2_id}
            with self.router(
                    tenant_id=tenant_id_1, external_gateway_info=ext_gw_1,
                    set_context=set_context) as router1:
                r1 = router1['router']
                self.l3_plugin._process_backlogged_routers()
                r1_after = self._show('routers', r1['id'])['router']
                hd_id = r1_after[HOSTING_DEVICE_ATTR]
                # should have one global router now
                self._verify_routers({r1['id']}, ext_net_ids, hd_id)
                with self.router(
                        tenant_id=tenant_id_2, external_gateway_info=ext_gw_1,
                        set_context=set_context) as router2:
                    r2 = router2['router']
                    self.l3_plugin._process_backlogged_routers()
                    # should still have only one global router
                    self._verify_routers({r1['id'], r2['id']}, ext_net_ids,
                                         hd_id)
                    with self.router(name='router2', tenant_id=tenant_id_2,
                                     external_gateway_info=ext_gw_2,
                                     set_context=set_context) as router3:
                        r3 = router3['router']
                        self.l3_plugin._process_backlogged_routers()
                        # should still have only one global router but now with
                        # one extra auxiliary gateway port
                        ext_net_ids[ext_net_2_id] = ext_gw_2_subnets
                        self._verify_routers(
                            {r1['id'], r2['id'], r3['id']}, ext_net_ids, hd_id)

    # single tenant and single external network
    def test_create_gateway_router(self):
        self._test_create_gateway_router()

    # _dt means two different tenants
    def test_create_gateway_router_dt(self):
        self._test_create_gateway_router(same_tenant=False)

    # _den means two different external networks
    def test_create_gateway_router_den(self):
        self._test_create_gateway_router(same_ext_net=False)

    # _dt means both two different tenants and two different external networks
    def test_create_gateway_router_dt_den(self):
        self._test_create_gateway_router(same_tenant=False, same_ext_net=False)

    def test_create_gateway_router_non_admin(self):
        self._test_create_gateway_router(True)

    def test_create_gateway_router_non_admin_dt(self):
        self._test_create_gateway_router(True, same_tenant=False)

    def test_create_gateway_router_non_admin_den(self):
        self._test_create_gateway_router(True, same_ext_net=False)

    def test_create_gateway_router_non_admin_dt_den(self):
        self._test_create_gateway_router(True, same_tenant=False,
                                         same_ext_net=False)

    # msn - multiple subnets (on a single neutron external network)
    def _test_create_msn_gateway_router(self, set_context=False,
                                        same_tenant=True, same_ext_net=True):
        tenant_id_1 = _uuid()
        tenant_id_2 = tenant_id_1 if same_tenant is True else _uuid()
        with self.network(tenant_id=tenant_id_1) as msn_n_external_1,\
                self.network(tenant_id=tenant_id_2) as n_external_2:
            msn_ext_net_1_id = msn_n_external_1['network']['id']
            self._set_net_external(msn_ext_net_1_id)
            sn_1 = self._make_subnet(
                self.fmt, msn_n_external_1, '10.0.1.1', cidr='10.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            sn_2 = self._make_subnet(
                self.fmt, msn_n_external_1, '20.0.1.1', cidr='20.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            ext_gw_1_subnets = [sn_1['id'], sn_2['id']]
            ext_net_ids = {msn_ext_net_1_id: ext_gw_1_subnets}
            ext_gw_1 = {
                'network_id': msn_ext_net_1_id,
                'external_fixed_ips': [{'subnet_id': sid}
                                       for sid in ext_gw_1_subnets]}
            if same_ext_net is False:
                ext_net_2_id = n_external_2['network']['id']
                self._set_net_external(ext_net_2_id)
                sn_3 = self._make_subnet(
                    self.fmt, n_external_2, '10.0.2.1', cidr='10.0.2.0/24',
                    tenant_id=tenant_id_2)['subnet']
                ext_gw_2_subnets = [sn_3['id']]
                ext_gw_2 = {'network_id': ext_net_2_id,
                            'external_fixed_ips': [{'subnet_id': sn_3['id']}]}
            else:
                ext_net_2_id = msn_ext_net_1_id
                ext_gw_2_subnets = ext_gw_1_subnets
                ext_gw_2 = ext_gw_1
            with self.router(
                    tenant_id=tenant_id_1, external_gateway_info=ext_gw_1,
                    set_context=set_context) as router1:
                r1 = router1['router']
                self.l3_plugin._process_backlogged_routers()
                r1_after = self._show('routers', r1['id'])['router']
                hd_id = r1_after[HOSTING_DEVICE_ATTR]
                # should have one global router now
                self._verify_routers({r1['id']}, ext_net_ids, hd_id)
                with self.router(
                        tenant_id=tenant_id_2, external_gateway_info=ext_gw_1,
                        set_context=set_context) as router2:
                    r2 = router2['router']
                    self.l3_plugin._process_backlogged_routers()
                    # should still have only one global router
                    self._verify_routers({r1['id'], r2['id']}, ext_net_ids,
                                         hd_id)
                    with self.router(name='router2', tenant_id=tenant_id_2,
                                     external_gateway_info=ext_gw_2,
                                     set_context=set_context) as router3:
                        r3 = router3['router']
                        self.l3_plugin._process_backlogged_routers()
                        # should still have only one global router but now with
                        # one extra auxiliary gateway port
                        ext_net_ids[ext_net_2_id] = ext_gw_2_subnets
                        self._verify_routers(
                            {r1['id'], r2['id'], r3['id']},
                            ext_net_ids, hd_id)

    # single tenant and single external network with two subnets
    def test_create_msn_gateway_router(self):
        self._test_create_msn_gateway_router()

    def test_create_msn_gateway_router_dt(self):
        self._test_create_msn_gateway_router(same_tenant=False)

    def test_create_msn_gateway_router_den(self):
        self._test_create_msn_gateway_router(same_ext_net=False)

    def test_create_msn_gateway_router_dt_den(self):
        self._test_create_msn_gateway_router(same_tenant=False,
                                             same_ext_net=False)

    def _test_create_router_adds_no_global_router(self, set_context=False):
        with self.router(set_context=set_context) as router:
            r = router['router']
            self.l3_plugin._process_backlogged_routers()
            # should have no global routers
            self._verify_routers({r['id']}, {}, None)

    def test_create_router_adds_no_global_router(self):
        self._test_create_router_adds_no_global_router()

    def test_create_router_adds_no_global_router_non_admin(self):
        self._test_create_router_adds_no_global_router(True)

    def _test_create_router_adds_no_aux_gw_port_to_global_router(
            self, set_context=False, same_tenant=True):
        tenant_id_1 = _uuid()
        tenant_id_2 = tenant_id_1 if same_tenant is True else _uuid()
        with self.network(tenant_id=tenant_id_1) as n_external_1:
            ext_net_1_id = n_external_1['network']['id']
            self._set_net_external(ext_net_1_id)
            sn_1 = self._make_subnet(
                self.fmt, n_external_1, '10.0.1.1', cidr='10.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            ext_net_ids = {ext_net_1_id: [sn_1['id']]}
            ext_gw_1 = {'network_id': ext_net_1_id}
            with self.router(
                    tenant_id=tenant_id_1, external_gateway_info=ext_gw_1,
                    set_context=set_context) as router1:
                r1 = router1['router']
                self.l3_plugin._process_backlogged_routers()
                r1_after = self._show('routers', r1['id'])['router']
                hd_id = r1_after[HOSTING_DEVICE_ATTR]
            with self.router(tenant_id=tenant_id_2,
                             set_context=set_context) as router2:
                r2 = router2['router']
                # backlog processing will trigger one routers_updated
                # notification containing r1 and r2
                self.l3_plugin._process_backlogged_routers()
                self._verify_routers({r1['id'], r2['id']}, ext_net_ids, hd_id)

    def test_create_router_adds_no_aux_gw_port_to_global_router(self):
        self._test_create_router_adds_no_aux_gw_port_to_global_router()

    def test_create_router_adds_no_aux_gw_port_to_global_router_dt(self):
        self._test_create_router_adds_no_aux_gw_port_to_global_router(
            same_tenant=False)

    def test_create_router_adds_no_aux_gw_port_to_global_router_non_admin(
            self):
        self._test_create_router_adds_no_aux_gw_port_to_global_router(True)

    def test_create_router_adds_no_aux_gw_port_to_global_router_non_admin_dt(
            self):
        self._test_create_router_adds_no_aux_gw_port_to_global_router(
            True, same_tenant=False)

    def _test_update_router_set_gateway(
            self, set_context=False, same_tenant=True, same_ext_net=True):
        tenant_id_1 = _uuid()
        tenant_id_2 = tenant_id_1 if same_tenant is True else _uuid()
        with self.network(tenant_id=tenant_id_1) as n_external_1, \
                self.network(tenant_id=tenant_id_2) as n_external_2:
            ext_net_1_id = n_external_1['network']['id']
        self._set_net_external(ext_net_1_id)
        sn_1 = self._make_subnet(
            self.fmt, n_external_1, '10.0.1.1', cidr='10.0.1.0/24',
            tenant_id=tenant_id_1)['subnet']
        ext_net_ids = {ext_net_1_id: [sn_1['id']]}
        ext_gw_1 = {'network_id': ext_net_1_id}
        if same_ext_net is False:
            ext_net_2_id = n_external_2['network']['id']
            self._set_net_external(ext_net_2_id)
            sn_2 = self._make_subnet(
                self.fmt, n_external_2, '10.0.2.1', cidr='10.0.2.0/24',
                tenant_id=tenant_id_2)['subnet']
            ext_gw_2_subnets = [sn_2['id']]
        else:
            ext_net_2_id = ext_net_1_id
            ext_gw_2_subnets = [sn_1['id']]
        ext_gw_2 = {'network_id': ext_net_2_id}
        with self.router(tenant_id=tenant_id_1,
                         set_context=set_context) as router1, \
                self.router(name='router2', tenant_id=tenant_id_2,
                            set_context=set_context) as router2:
            r1 = router1['router']
            r2 = router2['router']
            # backlog processing will trigger one routers_updated
            # notification containing r1 and r2
            self.l3_plugin._process_backlogged_routers()
            # should have no global router yet
            r_ids = {r1['id'], r2['id']}
            self._verify_routers(r_ids, ext_net_ids)
            r_spec = {'router': {l3_const.EXTERNAL_GW_INFO: ext_gw_1}}
            r1_after = self._update('routers', r1['id'], r_spec)['router']
            hd_id = r1_after[HOSTING_DEVICE_ATTR]
            # should now have one global router
            self._verify_routers(r_ids, ext_net_ids, hd_id, [1])
            r_spec = {'router': {l3_const.EXTERNAL_GW_INFO: ext_gw_2}}
            self._update('routers', r2['id'], r_spec)['router']
            # should still have only one global router but now with
            # one extra auxiliary gateway port
            ext_net_ids[ext_net_2_id] = ext_gw_2_subnets
            self._verify_routers(r_ids, ext_net_ids, hd_id, [1, 3])

    def test_update_router_set_gateway(self):
        self._test_update_router_set_gateway()

    def test_update_router_set_gateway_dt(self):
        self._test_update_router_set_gateway(same_tenant=False)

    def test_update_router_set_gateway_den(self):
        self._test_update_router_set_gateway(same_ext_net=False)

    def test_update_router_set_gateway_dt_den(self):
        self._test_update_router_set_gateway(same_tenant=False,
                                             same_ext_net=False)

    def test_update_router_set_gateway_non_admin(self):
        self._test_update_router_set_gateway(True)

    def test_update_router_set_gateway_non_admin_dt(self):
        self._test_update_router_set_gateway(True, same_tenant=False)

    def test_update_router_set_gateway_non_admin_den(self):
        self._test_update_router_set_gateway(True, same_ext_net=False)

    def test_update_router_set_gateway_non_admin_dt_den(self):
        self._test_update_router_set_gateway(True, same_tenant=False,
                                             same_ext_net=False)

    def _test_update_router_set_msn_gateway(
            self, set_context=False, same_tenant=True, same_ext_net=True):
        tenant_id_1 = _uuid()
        tenant_id_2 = tenant_id_1 if same_tenant is True else _uuid()
        with self.network(tenant_id=tenant_id_1) as msn_n_external_1, \
                self.network(tenant_id=tenant_id_2) as n_external_2:
            msn_ext_net_1_id = msn_n_external_1['network']['id']
        self._set_net_external(msn_ext_net_1_id)
        sn_1 = self._make_subnet(
            self.fmt, msn_n_external_1, '10.0.1.1', cidr='10.0.1.0/24',
            tenant_id=tenant_id_1)['subnet']
        sn_2 = self._make_subnet(
            self.fmt, msn_n_external_1, '20.0.1.1', cidr='20.0.1.0/24',
            tenant_id=tenant_id_1)['subnet']
        ext_net_ids = {msn_ext_net_1_id: [sn_1['id'], sn_2['id']]}
        ext_gw_1 = {
            'network_id': msn_ext_net_1_id,
            'external_fixed_ips': [{'subnet_id': sn_1['id']}]}
        if same_ext_net is False:
            ext_net_2_id = n_external_2['network']['id']
            self._set_net_external(ext_net_2_id)
            sn_3 = self._make_subnet(
                self.fmt, n_external_2, '10.0.2.1', cidr='10.0.2.0/24',
                tenant_id=tenant_id_2)['subnet']
            ext_gw_2_subnets = [sn_3['id']]
            ext_gw_2 = {'network_id': ext_net_2_id,
                        'external_fixed_ips': [{'subnet_id': sn_3['id']}]}
        else:
            ext_net_2_id = msn_ext_net_1_id
            ext_gw_2_subnets = ext_net_ids[msn_ext_net_1_id]
            ext_gw_2 = ext_gw_1
        with self.router(tenant_id=tenant_id_1,
                         set_context=set_context) as router1, \
                self.router(name='router2', tenant_id=tenant_id_2,
                            set_context=set_context) as router2:
            r1 = router1['router']
            r2 = router2['router']
            # backlog processing will trigger one routers_updated
            # notification containing r1 and r2
            self.l3_plugin._process_backlogged_routers()
            # should have no global router yet
            r_ids = {r1['id'], r2['id']}
            self._verify_routers(r_ids, ext_net_ids)
            r_spec = {'router': {l3_const.EXTERNAL_GW_INFO: ext_gw_1}}
            r1_after = self._update('routers', r1['id'], r_spec)['router']
            res_ips = r1_after[l3_const.EXTERNAL_GW_INFO][
                    'external_fixed_ips']
            self.assertEqual(1, len(res_ips))
            self.assertEqual(sn_1['id'], res_ips[0]['subnet_id'])
            hd_id = r1_after[HOSTING_DEVICE_ATTR]
            # should now have one global router
            self._verify_routers(r_ids, ext_net_ids, hd_id, [1])
            ext_gw_1_2 = {'network_id': msn_ext_net_1_id,
                          'external_fixed_ips': [{'subnet_id': sn_1['id']},
                                                 {'subnet_id': sn_2['id']}]}
            r_spec = {'router': {l3_const.EXTERNAL_GW_INFO: ext_gw_1_2}}
            r1_final = self._update('routers', r1['id'], r_spec)['router']
            res_ips = r1_final[l3_const.EXTERNAL_GW_INFO][
                    'external_fixed_ips']
            self.assertEqual(2, len(res_ips))
            self.assertIn(res_ips[0]['subnet_id'],
                          ext_net_ids[msn_ext_net_1_id])
            self.assertIn(res_ips[1]['subnet_id'],
                          ext_net_ids[msn_ext_net_1_id])
            # should now have one global router
            self._verify_routers(r_ids, ext_net_ids, hd_id, [1])
            r_spec = {'router': {l3_const.EXTERNAL_GW_INFO: ext_gw_2}}
            self._update('routers', r2['id'], r_spec)['router']
            # should still have only one global router but now with
            # one extra auxiliary gateway port
            ext_net_ids[ext_net_2_id] = ext_gw_2_subnets
            self._verify_routers(r_ids, ext_net_ids, hd_id, [1, 3])

    def test_update_router_set_msn_gateway(self):
        self._test_update_router_set_msn_gateway()

    def test_update_router_set_msn_gateway_dt(self):
        self._test_update_router_set_msn_gateway(same_tenant=False)

    def test_update_router_set_msn_gateway_den(self):
        self._test_update_router_set_msn_gateway(same_ext_net=False)

    def test_update_router_set_msn_gateway_dt_den(self):
        self._test_update_router_set_msn_gateway(same_tenant=False,
                                                 same_ext_net=False)

    def _test_router_update_unset_gw_or_delete(
            self, set_context=False, same_tenant=True, same_ext_net=True,
            update_operation=True):
        tenant_id_1 = _uuid()
        tenant_id_2 = tenant_id_1 if same_tenant is True else _uuid()
        with self.network(tenant_id=tenant_id_1) as n_external_1, \
                self.network(tenant_id=tenant_id_1) as n_external_2:
            ext_net_1_id = n_external_1['network']['id']
            self._set_net_external(ext_net_1_id)
            sn_1 = self._make_subnet(
                self.fmt, n_external_1, '10.0.1.1', cidr='10.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            ext_net_ids = {ext_net_1_id: [sn_1['id']]}
            ext_gw_1 = {'network_id': ext_net_1_id}
            if same_ext_net is False:
                ext_net_2_id = n_external_2['network']['id']
                self._set_net_external(ext_net_2_id)
                sn_2 = self._make_subnet(
                    self.fmt, n_external_2, '10.0.2.1', cidr='10.0.2.0/24',
                    tenant_id=tenant_id_2)['subnet']
                ext_gw_2_subnets = [sn_2['id']]
            else:
                ext_net_2_id = ext_net_1_id
                ext_gw_2_subnets = [sn_1['id']]
            ext_net_ids[ext_net_2_id] = ext_gw_2_subnets
            ext_gw_2 = {'network_id': ext_net_2_id}
            with self.router(tenant_id=tenant_id_1,
                             external_gateway_info=ext_gw_1,
                             set_context=set_context) as router1,\
                    self.router(name='router2', tenant_id=tenant_id_2,
                                external_gateway_info=ext_gw_2,
                                set_context=set_context) as router2:
                r1 = router1['router']
                r2 = router2['router']
                # backlog processing will trigger one routers_updated
                # notification containing r1 and r2
                self.l3_plugin._process_backlogged_routers()
                r1_after = self._show('routers', r1['id'])['router']
                hd_id = r1_after[HOSTING_DEVICE_ATTR]
                r_ids = {r1['id'], r2['id']}
                # should have one global router now
                self._verify_routers(r_ids, ext_net_ids, hd_id, [0, 1])
                if update_operation is True:
                    r_spec = {'router': {l3_const.EXTERNAL_GW_INFO: None}}
                    self._update('routers', r1['id'], r_spec)
                else:
                    self._delete('routers', r1['id'])
                    r_ids = {r2['id']}
                # should still have one global router
                if same_ext_net is False:
                    ext_net_ids.pop(ext_net_1_id)
                self._verify_routers(r_ids, ext_net_ids, hd_id, [0, 1])
                if update_operation is True:
                    LOG.debug('Update router %s to remove gateway', r2['id'])
                    self._update('routers', r2['id'], r_spec,
                                 check_return_code=False)
                else:
                    LOG.debug('Delete router %s', r2['id'])
                    self._delete('routers', r2['id'], check_return_code=False)
                    r_ids = {}
                # should have no global router now
                ext_net_ids.pop(ext_net_2_id, None)
                self._verify_routers(r_ids, ext_net_ids)

    def test_router_update_unset_gw(self):
        self._test_router_update_unset_gw_or_delete()

    def test_router_update_unset_gw_dt(self):
        self._test_router_update_unset_gw_or_delete(same_tenant=False)

    def test_router_update_unset_gw_den(self):
        self._test_router_update_unset_gw_or_delete(same_ext_net=False)

    def test_router_update_unset_gw_dt_den(self):
        self._test_router_update_unset_gw_or_delete(same_tenant=False,
                                                    same_ext_net=False)

    def test_router_update_unset_gw_non_admin(self):
        self._test_router_update_unset_gw_or_delete(True)

    def test_router_update_unset_gw_non_admin_dt(self):
        self._test_router_update_unset_gw_or_delete(True, same_tenant=False)

    def test_router_update_unset_gw_non_admin_den(self):
        self._test_router_update_unset_gw_or_delete(True, same_ext_net=False)

    def test_router_update_unset_gw_non_admin_dt_den(self):
        self._test_router_update_unset_gw_or_delete(True, same_tenant=False,
                                                    same_ext_net=False)

    def _test_router_update_unset_msn_gw(
            self, set_context=False, same_tenant=True, same_ext_net=True):
        tenant_id_1 = _uuid()
        tenant_id_2 = tenant_id_1 if same_tenant is True else _uuid()
        with self.network(tenant_id=tenant_id_1) as msn_n_external_1, \
                self.network(tenant_id=tenant_id_1) as n_external_2:
            msn_ext_net_1_id = msn_n_external_1['network']['id']
            self._set_net_external(msn_ext_net_1_id)
            sn_1 = self._make_subnet(
                self.fmt, msn_n_external_1, '10.0.1.1', cidr='10.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            sn_2 = self._make_subnet(
                self.fmt, msn_n_external_1, '20.0.1.1', cidr='20.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            ext_gw_1_subnets = [sn_1['id'], sn_2['id']]
            ext_net_ids = {msn_ext_net_1_id: ext_gw_1_subnets}
            ext_gw_1 = {
                'network_id': msn_ext_net_1_id,
                'external_fixed_ips': [{'subnet_id': sid}
                                       for sid in ext_gw_1_subnets]}
            if same_ext_net is False:
                ext_net_2_id = n_external_2['network']['id']
                self._set_net_external(ext_net_2_id)
                sn_3 = self._make_subnet(
                    self.fmt, n_external_2, '10.0.2.1', cidr='10.0.2.0/24',
                    tenant_id=tenant_id_2)['subnet']
                ext_gw_2_subnets = [sn_3['id']]
                ext_gw_2 = {'network_id': ext_net_2_id,
                            'external_fixed_ips': [{'subnet_id': sn_3['id']}]}
            else:
                ext_net_2_id = msn_ext_net_1_id
                ext_gw_2_subnets = ext_gw_1_subnets
                ext_gw_2 = ext_gw_1
            ext_net_ids[ext_net_2_id] = ext_gw_2_subnets
            with self.router(tenant_id=tenant_id_1,
                             external_gateway_info=ext_gw_1,
                             set_context=set_context) as router1,\
                    self.router(name='router2', tenant_id=tenant_id_2,
                                external_gateway_info=ext_gw_2,
                                set_context=set_context) as router2:
                r1 = router1['router']
                r2 = router2['router']
                # backlog processing will trigger one routers_updated
                # notification containing r1 and r2
                self.l3_plugin._process_backlogged_routers()
                r1_after = self._show('routers', r1['id'])['router']
                hd_id = r1_after[HOSTING_DEVICE_ATTR]
                r_ids = {r1['id'], r2['id']}
                # should have one global router now
                self._verify_routers(r_ids, ext_net_ids, hd_id, [0, 1])
                ext_gw_1['external_fixed_ips'] = [{'subnet_id': sn_1['id']}]
                r_spec = {'router': {l3_const.EXTERNAL_GW_INFO: ext_gw_1}}
                r1_after_2 = self._update('routers', r1['id'],
                                          r_spec)['router']
                res_ips = r1_after_2[l3_const.EXTERNAL_GW_INFO][
                        'external_fixed_ips']
                self.assertEqual(1, len(res_ips))
                self.assertEqual(sn_1['id'], res_ips[0]['subnet_id'])
                # should still have one global router
                self._verify_routers(r_ids, ext_net_ids, hd_id, [0, 1])
                r_spec = {'router': {l3_const.EXTERNAL_GW_INFO: None}}
                self._update('routers', r1['id'], r_spec)
                # should still have one global router
                if same_ext_net is False:
                    ext_net_ids.pop(msn_ext_net_1_id)
                self._verify_routers(r_ids, ext_net_ids, hd_id, [0, 1])
                LOG.debug('Update router %s to remove gateway', r2['id'])
                self._update('routers', r2['id'], r_spec,
                             check_return_code=False)
                # should have no global router now
                self._verify_routers(r_ids, ext_net_ids)

    def test_router_update_unset_msn_gw(self):
        self._test_router_update_unset_msn_gw()

    def test_router_update_unset_msn_gw_dt(self):
        self._test_router_update_unset_msn_gw(same_tenant=False)

    def test_router_update_unset_msn_gw_den(self):
        self._test_router_update_unset_msn_gw(same_ext_net=False)

    def test_router_update_unset_msn_gw_dt_den(self):
        self._test_router_update_unset_msn_gw(same_tenant=False,
                                              same_ext_net=False)

    def _test_router_update_unset_msn_gw_concurrent(
            self, delete_global=True, delete_ports=False,
            delete_logical=False):

        def _concurrent_delete_global_router(local_self, context,
                                             global_router_id, logical=False):
            if delete_ports is True:
                delete_p_fcn(local_self, context, global_router_id)
            try:
                if logical is True:
                    if delete_logical is True:
                        super(L3RouterApplianceDBMixin,
                              self.l3_plugin).delete_router(context,
                                                            global_router_id)
                else:
                    if delete_global is True:
                        self.l3_plugin.delete_router(
                            context, global_router_id, unschedule=False)
            except (db_exc.ObjectDeletedError,
                    l3_exceptions.RouterNotFound) as e:
                LOG.warning(e)
            delete_gr_fcn(local_self, context, global_router_id, logical)

        set_context = False
        tenant_id = _uuid()
        with self.network(tenant_id=tenant_id) as msn_n_external:
            msn_ext_net_id = msn_n_external['network']['id']
            self._set_net_external(msn_ext_net_id)
            sn_1 = self._make_subnet(
                self.fmt, msn_n_external, '10.0.1.1', cidr='10.0.1.0/24',
                tenant_id=tenant_id)['subnet']
            sn_2 = self._make_subnet(
                self.fmt, msn_n_external, '20.0.1.1', cidr='20.0.1.0/24',
                tenant_id=tenant_id)['subnet']
            ext_gw_subnets = [sn_1['id'], sn_2['id']]
            ext_net_ids = {msn_ext_net_id: ext_gw_subnets}
            ext_gw = {
                'network_id': msn_ext_net_id,
                'external_fixed_ips': [{'subnet_id': sid}
                                       for sid in ext_gw_subnets]}
            with self.router(tenant_id=tenant_id,
                             external_gateway_info=ext_gw,
                             set_context=set_context) as router:
                r = router['router']
                # backlog processing will trigger one routers_updated
                # notification containing r1 and r2
                self.l3_plugin._process_backlogged_routers()
                r_after = self._show('routers', r['id'])['router']
                hd_id = r_after[HOSTING_DEVICE_ATTR]
                r_ids = {r['id']}
                # should have one global router now
                self._verify_routers(r_ids, ext_net_ids, hd_id)
                ext_gw['external_fixed_ips'] = [{'subnet_id': sn_1['id']}]
                r_spec = {'router': {l3_const.EXTERNAL_GW_INFO: ext_gw}}
                r_after_2 = self._update('routers', r['id'], r_spec)['router']
                res_ips = r_after_2[l3_const.EXTERNAL_GW_INFO][
                        'external_fixed_ips']
                self.assertEqual(1, len(res_ips))
                self.assertEqual(sn_1['id'], res_ips[0]['subnet_id'])
                # should still have one global router
                self._verify_routers(r_ids, ext_net_ids, hd_id)
                # now we simulate that there is another router with similar
                # gateway that is unset concurrently and that its REST API
                # thread manages to delete the global router
                r_spec = {'router': {l3_const.EXTERNAL_GW_INFO: None}}

                delete_gr_fcn = drv.ASR1kL3RouterDriver._delete_global_router
                delete_p_fcn = (
                    drv.ASR1kL3RouterDriver._delete_auxiliary_gateway_ports)
                with mock.patch(
                        'networking_cisco.plugins.cisco.l3.drivers.asr1k'
                        '.asr1k_routertype_driver.ASR1kL3RouterDriver'
                        '._delete_global_router',
                        new=_concurrent_delete_global_router):
                    LOG.debug('Update router %s to remove gateway', r['id'])
                    self._update('routers', r['id'], r_spec,
                                 check_return_code=False)
                    # should have no global router now
                    self._verify_routers(r_ids, ext_net_ids)

    def test_router_update_unset_msn_gw_concurrent_global_delete(self):
        self._test_router_update_unset_msn_gw_concurrent()

    def test_router_update_unset_msn_gw_concurrent_global_port_delete(self):
        self._test_router_update_unset_msn_gw_concurrent(delete_ports=True)

    def test_router_update_unset_msn_gw_concurrent_port_delete(self):
        self._test_router_update_unset_msn_gw_concurrent(delete_global=False,
                                                         delete_ports=True)

    def _test_delete_gateway_router(self, set_context=False, same_tenant=True,
                                    same_ext_net=True):
        self._test_router_update_unset_gw_or_delete(
            set_context, same_tenant, same_ext_net, update_operation=False)

    def test_delete_gateway_router(self):
        self._test_delete_gateway_router()

    def test_delete_gateway_router_dt(self):
        self._test_delete_gateway_router(same_tenant=False)

    def test_delete_gateway_router_den(self):
        self._test_delete_gateway_router(same_ext_net=False)

    def test_delete_gateway_router_dt_den(self):
        self._test_delete_gateway_router(same_tenant=False, same_ext_net=False)

    def test_delete_gateway_router_non_admin(self):
        self._test_delete_gateway_router(True)

    def test_delete_gateway_router_non_admin_dt(self):
        self._test_delete_gateway_router(True, same_tenant=False)

    def test_delete_gateway_router_non_admin_den(self):
        self._test_delete_gateway_router(True, same_ext_net=False)

    def test_delete_gateway_router_non_admin_dt_den(self):
        self._test_delete_gateway_router(True, same_tenant=False,
                                         same_ext_net=False)

    def _test_delete_msn_gateway_router(self, set_context=False,
                                        same_tenant=True, same_ext_net=True):
        tenant_id_1 = _uuid()
        tenant_id_2 = tenant_id_1 if same_tenant is True else _uuid()
        with self.network(tenant_id=tenant_id_1) as msn_n_external_1, \
                self.network(tenant_id=tenant_id_1) as n_external_2:
            msn_ext_net_1_id = msn_n_external_1['network']['id']
            self._set_net_external(msn_ext_net_1_id)
            sn_1 = self._make_subnet(
                self.fmt, msn_n_external_1, '10.0.1.1', cidr='10.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            sn_2 = self._make_subnet(
                self.fmt, msn_n_external_1, '20.0.1.1', cidr='20.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            ext_gw_1_subnets = [sn_1['id'], sn_2['id']]
            ext_net_ids = {msn_ext_net_1_id: ext_gw_1_subnets}
            ext_gw_1 = {
                'network_id': msn_ext_net_1_id,
                'external_fixed_ips': [{'subnet_id': sid}
                                       for sid in ext_gw_1_subnets]}
            if same_ext_net is False:
                ext_net_2_id = n_external_2['network']['id']
                self._set_net_external(ext_net_2_id)
                sn_3 = self._make_subnet(
                    self.fmt, n_external_2, '10.0.2.1', cidr='10.0.2.0/24',
                    tenant_id=tenant_id_2)['subnet']
                ext_gw_2_subnets = [sn_3['id']]
                ext_gw_2 = {'network_id': ext_net_2_id,
                            'external_fixed_ips': [{'subnet_id': sn_3['id']}]}
            else:
                ext_net_2_id = msn_ext_net_1_id
                ext_gw_2_subnets = ext_gw_1_subnets
                ext_gw_2 = ext_gw_1
            ext_net_ids[ext_net_2_id] = ext_gw_2_subnets
            with self.router(tenant_id=tenant_id_1,
                             external_gateway_info=ext_gw_1,
                             set_context=set_context) as router1,\
                    self.router(name='router2', tenant_id=tenant_id_2,
                                external_gateway_info=ext_gw_2,
                                set_context=set_context) as router2:
                r1 = router1['router']
                r2 = router2['router']
                # backlog processing will trigger one routers_updated
                # notification containing r1 and r2
                self.l3_plugin._process_backlogged_routers()
                r1_after = self._show('routers', r1['id'])['router']
                hd_id = r1_after[HOSTING_DEVICE_ATTR]
                r_ids = {r1['id'], r2['id']}
                # should have one global router now
                self._verify_routers(r_ids, ext_net_ids, hd_id, [0, 1])
                self._delete('routers', r1['id'])
                r_ids = {r2['id']}
                # should still have one global router
                if same_ext_net is False:
                    ext_net_ids.pop(msn_ext_net_1_id)
                self._verify_routers(r_ids, ext_net_ids, hd_id, [0, 1])
                self._delete('routers', r2['id'], check_return_code=False)
                r_ids = {}
                # should have no global router now
                self._verify_routers(r_ids, ext_net_ids)

    def test_delete_msn_gateway_router(self):
        self._test_delete_msn_gateway_router()

    def test_delete_msn_gateway_router_dt(self):
        self._test_delete_msn_gateway_router(same_tenant=False)

    def test_delete_msn_gateway_router_den(self):
        self._test_delete_msn_gateway_router(same_ext_net=False)

    def test_delete_msn_gateway_router_dt_den(self):
        self._test_delete_msn_gateway_router(same_tenant=False,
                                             same_ext_net=False)

    def _test_router_interface_add_refused_for_unsupported_topology(
            self, num_expected_ports=2, set_context=False, same_tenant=True):
        tenant_id_1 = _uuid()
        tenant_id_2 = tenant_id_1 if same_tenant is True else _uuid()
        with self.network(tenant_id=tenant_id_1,
                          set_context=set_context) as n1, \
                self.network(tenant_id=tenant_id_1,
                             set_context=set_context) as n2, \
                self.subnet(
                    network=n1, cidr='10.0.0.0/24', tenant_id=tenant_id_1,
                    set_context=set_context) as subnet1, \
                self.subnet(
                    network=n2, cidr='10.0.1.0/24', tenant_id=tenant_id_2,
                    set_context=set_context) as subnet2, \
                self.port(subnet=subnet2, tenant_id=tenant_id_1,
                          set_context=set_context) as port1, \
                self.port(subnet=subnet1, tenant_id=tenant_id_2,
                          set_context=set_context) as port2, \
                self.router(tenant_id=tenant_id_1,
                            set_context=set_context) as router1, \
                self.router(name='router2', tenant_id=tenant_id_1,
                            set_context=set_context) as router2:
            sn1 = subnet1['subnet']
            sn2 = subnet2['subnet']
            p1 = port1['port']
            p2 = port2['port']
            r1 = router1['router']
            r2 = router2['router']
            self._router_interface_action('add', r1['id'], sn1['id'], None)
            # Add r2 to sn1 by subnet id
            # Two routers on same network == non-supported topology so
            # should fail
            self._router_interface_action('add', r2['id'], sn1['id'], None,
                                          expected_code=exc.HTTPConflict.code)
            # Add r2 to sn1 by port id
            # Two routers on same network == non-supported topology so
            # should fail
            self._router_interface_action('add', r2['id'], None, p2['id'],
                                          expected_code=exc.HTTPConflict.code)
            # Add r2 to sn2 by subnet id
            # One router per network is ok
            self._router_interface_action('add', r2['id'], sn2['id'], None)
            # Add r1 to sn2 by port id
            # Two routers on same network == non-supported topology so
            # should fail
            self._router_interface_action('add', r1['id'], None, p1['id'],
                                          expected_code=exc.HTTPConflict.code)
            q_p = 'device_owner=%s' % DEVICE_OWNER_ROUTER_INTF
            r_ports = self._list('ports', query_params=q_p)['ports']
            self.assertEqual(num_expected_ports, len(r_ports))

    def test_router_interface_add_refused_for_unsupported_topology(self):
        self._test_router_interface_add_refused_for_unsupported_topology()

    def test_router_interface_add_refused_for_unsupported_topology_dt(self):
        self._test_router_interface_add_refused_for_unsupported_topology(
            same_tenant=False)


class Asr1kHARouterTypeDriverTestCase(
        Asr1kRouterTypeDriverTestCase,
        cisco_ha_test.HAL3RouterTestsMixin):

    # For the HA tests we need more than one hosting device
    router_type = 'ASR1k_Neutron_router'
    _is_ha_tests = True

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        if l3_plugin is None:
            l3_plugin = cisco_test_case.HA_L3_PLUGIN_KLASS
        if ext_mgr is None:
            ext_mgr = (cisco_test_case.
                       TestHASchedulingL3RouterApplianceExtensionManager())
        cfg.CONF.set_override('default_ha_redundancy_level', 1, group='ha')

        super(Asr1kHARouterTypeDriverTestCase, self).setUp(
            l3_plugin=l3_plugin, ext_mgr=ext_mgr)

    def _verify_routers(self, router_ids, ext_net_ids, hd_id=None,
                        call_indices=None):
        # The 'ext_net_ids' argument is a dict where key is ext_net_id and
        # value is a list of subnet_ids that the global router should be
        # connected to
        # tenant routers
        q_p = '%s=None' % ROUTER_ROLE_ATTR
        r_ids = {r['id'] for r in self._list(
            'routers', query_params=q_p)['routers']}
        self.assertEqual(len(r_ids), len(router_ids))
        for r_id in r_ids:
            self.assertIn(r_id, router_ids)
        # global router on hosting device
        self._verify_global_router(ROUTER_ROLE_GLOBAL, hd_id, ext_net_ids)
        # logical global router for global routers HA
        self._verify_global_router(ROUTER_ROLE_LOGICAL_GLOBAL, hd_id,
                                   ext_net_ids)
        notifier = self.l3_plugin.agent_notifiers[AGENT_TYPE_L3_CFG]
        # ensure *no* update notifications where sent for logical global router
        for call in notifier.method_calls:
            if call[0] == 'routers_updated':
                self.assertNotIn(call[1][1][0][ROUTER_ROLE_ATTR],
                                 [ROUTER_ROLE_LOGICAL_GLOBAL])
            elif call[0] == 'router_deleted':
                self.assertNotIn(call[1][1][ROUTER_ROLE_ATTR],
                                 [ROUTER_ROLE_LOGICAL_GLOBAL])

    def test_router_interface_add_refused_for_unsupported_topology(self):
        self._test_router_interface_add_refused_for_unsupported_topology(
            num_expected_ports=6)

    def test_router_interface_add_refused_for_unsupported_topology_dt(self):
        self._test_router_interface_add_refused_for_unsupported_topology(
            num_expected_ports=6, same_tenant=False)


class L3CfgAgentAsr1kRouterTypeDriverTestCase(
        cisco_test_case.L3RoutertypeAwareHostingDeviceSchedulerTestCaseBase,
        cisco_ha_test.HAL3RouterTestsMixin):

    _is_ha_tests = True

    def setUp(self, core_plugin=None, l3_plugin=None, dm_plugin=None,
              ext_mgr=None):
        if l3_plugin is None:
            l3_plugin = cisco_test_case.HA_L3_PLUGIN_KLASS
        if ext_mgr is None:
            ext_mgr = (cisco_test_case.
                       TestHASchedulingL3RouterApplianceExtensionManager())
        cfg.CONF.set_override('default_ha_redundancy_level', 1, group='ha')

        super(L3CfgAgentAsr1kRouterTypeDriverTestCase, self).setUp(
            l3_plugin=l3_plugin, ext_mgr=ext_mgr)
        self.orig_get_sync_data = self.l3_plugin.get_sync_data
        self.l3_plugin.get_sync_data = self.l3_plugin.get_sync_data_ext

    def tearDown(self):
        self.l3_plugin.get_sync_data = self.orig_get_sync_data
        super(L3CfgAgentAsr1kRouterTypeDriverTestCase, self).tearDown()

    def _verify_global_router(self, role, hd_id, ext_net_ids):
        # The 'ext_net_ids' argument is a dict where key is ext_net_id and
        # value is a list of subnet_ids that the global router should be
        # connected to
        if hd_id is None:
            q_p = '%s=%s' % (ROUTER_ROLE_ATTR, role)
        else:
            q_p = '%s=%s&%s=%s' % (ROUTER_ROLE_ATTR, role, HOSTING_DEVICE_ATTR,
                                   hd_id)
        routers = self._list('routers', query_params=q_p)['routers']
        self.assertEqual(1, len(routers))
        router = routers[0]
        if role == ROUTER_ROLE_GLOBAL:
            self.assertTrue(router['name'].endswith(
                hd_id[-cisco_constants.ROLE_ID_LEN:]))
        else:
            self.assertEqual(router['name'], LOGICAL_ROUTER_ROLE_NAME)
            self.assertEqual(router[AUTO_SCHEDULE_ATTR], False)
        self.assertIsNone(router[l3_const.EXTERNAL_GW_INFO])
        q_p = '%s=%s&%s=%s' % ('device_id', router['id'], 'device_owner',
                               DEVICE_OWNER_GLOBAL_ROUTER_GW)
        aux_gw_ports = self._list('ports', query_params=q_p)['ports']
        self.assertEqual(len(ext_net_ids), len(aux_gw_ports))
        ids = copy.deepcopy(ext_net_ids)
        for aux_gw_port in aux_gw_ports:
            self.assertIn(aux_gw_port['network_id'], ids)
            self.assertEqual(len(aux_gw_port['fixed_ips']),
                             len(ids[aux_gw_port['network_id']]))
            # check that port has ip on correct subnets
            for ips in aux_gw_port['fixed_ips']:
                self.assertIn(ips['subnet_id'],
                              ids[aux_gw_port['network_id']])
                ids[aux_gw_port['network_id']].remove(ips['subnet_id'])
            ids.pop(aux_gw_port['network_id'])
        return router

    def _verify_ha_settings(self, router, expected_ha):
        self.assertEqual(router[ha.ENABLED], expected_ha[ha.ENABLED])
        if expected_ha[ha.ENABLED]:
            if ha.DETAILS in expected_ha:
                self.assertDictEqual(router[ha.DETAILS],
                                     expected_ha[ha.DETAILS])
            else:
                self.assertTrue(ha.DETAILS not in router)
        else:
            self.assertIsNone(router.get(ha.DETAILS))

    def _verify_global_router_ha(self, global_router, ha_settings,
                                 net_id_to_port, g_l_rtr_rr_ids):
        # global routers should here have HA setup information from
        # the logical global router
        self._verify_ha_settings(global_router, ha_settings)
        rr_info_list = global_router[ha.DETAILS][ha.REDUNDANCY_ROUTERS]
        self.assertEqual(len(rr_info_list), len(g_l_rtr_rr_ids))
        for rr_info in rr_info_list:
            self.assertIn(rr_info['id'], g_l_rtr_rr_ids)
        # the VIP address for the global router's auxiliary gateway ports
        # comes from the auxiliary gateway ports of the logical global router
        for aux_gw_port in global_router[AUXILIARY_GATEWAY_KEY]:
            ha_port = aux_gw_port['ha_info']['ha_port']
            l_g_port = net_id_to_port[ha_port['network_id']]
            self.assertEqual(l_g_port['fixed_ips'][0]['ip_address'],
                             ha_port['fixed_ips'][0]['ip_address'])

    def _verify_sync_data(self, router, router_ids, ext_net_ids):
        # The 'ext_net_ids' argument is a dict where key is ext_net_id and
        # value is a list of subnet_ids that the global router should be
        # connected to
        hd_id = router[HOSTING_DEVICE_ATTR]
        id_r_ha_backup = router[ha.DETAILS][ha.REDUNDANCY_ROUTERS][0]['id']
        router_ha_backup = self._show('routers', id_r_ha_backup)['router']
        hd_id_ha_backup = router_ha_backup[HOSTING_DEVICE_ATTR]
        # logical global router for global routers HA
        logical_global_router = self._verify_global_router(
            ROUTER_ROLE_LOGICAL_GLOBAL, None, ext_net_ids)
        self.assertTrue(logical_global_router[ha.ENABLED])
        self.assertEqual(router[routertype.TYPE_ATTR],
                         logical_global_router[routertype.TYPE_ATTR])
        ha_settings = {ha.ENABLED: logical_global_router[ha.ENABLED]}
        ha_settings[ha.DETAILS] = copy.copy(logical_global_router[ha.DETAILS])
        g_l_rtr_rr_ids = {r_info['id'] for r_info in
                          ha_settings[ha.DETAILS][ha.REDUNDANCY_ROUTERS]}
        self.assertEqual(len(g_l_rtr_rr_ids), 2)
        # global routers on hosting devices
        g_rtr_1 = self._verify_global_router(ROUTER_ROLE_GLOBAL, hd_id,
                                             ext_net_ids)
        self.assertIn(g_rtr_1['id'], g_l_rtr_rr_ids)
        self.assertFalse(g_rtr_1[ha.ENABLED])
        g_rtr_2 = self._verify_global_router(ROUTER_ROLE_GLOBAL,
                                             hd_id_ha_backup, ext_net_ids)
        self.assertIn(g_rtr_2['id'], g_l_rtr_rr_ids)
        self.assertFalse(g_rtr_1[ha.ENABLED])
        e_context = bc.context.get_admin_context()
        ids_incomplete_router_dicts = copy.copy(g_l_rtr_rr_ids)
        sync_routers = []
        attempt = 0
        while ids_incomplete_router_dicts and attempt < 10:
            new_sync_routers = self.l3_plugin.get_sync_data_ext(
                e_context, ids_incomplete_router_dicts)
            ids_incomplete_router_dicts = []
            for s_r in new_sync_routers:
                if s_r['status'] != cisco_constants.ROUTER_INFO_INCOMPLETE:
                    sync_routers.append(s_r)
                else:
                    LOG.debug('Received incomplete router dict for router '
                              '%(r_id)s in attempt %(att)d',
                              {'r_id': s_r['id'], 'att': attempt})
                    ids_incomplete_router_dicts.append(s_r['id'])
            attempt += 1
        self.assertEqual(2, len(sync_routers))
        q_p = '%s=%s&%s=%s' % ('device_id', logical_global_router['id'],
                               'device_owner', DEVICE_OWNER_GLOBAL_ROUTER_GW)
        net_id_to_port = {itfc['network_id']: itfc for itfc in
                          self._list('ports', query_params=q_p)['ports']}
        for global_router in sync_routers:
            self._verify_global_router_ha(global_router, ha_settings,
                                          net_id_to_port, g_l_rtr_rr_ids)

    def _test_l3_cfg_agent_query_global_router_info(
            self, set_context=False, same_tenant=True, same_ext_net=True):
        with mock.patch(
            'networking_cisco.plugins.cisco.device_manager.plugging_drivers.'
            'hw_vlan_trunking_driver.HwVLANTrunkingPlugDriver.'
                'allocate_hosting_port') as m:
            m.side_effect = lambda ctx, r_id, p_db, n_t, hd_i: (
                {'allocated_port_id': p_db.id,
                 'allocated_vlan': 5})
            tenant_id_1 = _uuid()
            tenant_id_2 = tenant_id_1 if same_tenant is True else _uuid()
            with self.network(tenant_id=tenant_id_1) as msn_n_external_1, \
                    self.network(tenant_id=tenant_id_1) as n_external_2:
                msn_ext_net_1_id = msn_n_external_1['network']['id']
            self._set_net_external(msn_ext_net_1_id)
            sn_1 = self._make_subnet(
                self.fmt, msn_n_external_1, '10.0.1.1', cidr='10.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            sn_2 = self._make_subnet(
                self.fmt, msn_n_external_1, '20.0.1.1', cidr='20.0.1.0/24',
                tenant_id=tenant_id_1)['subnet']
            ext_net_ids = {msn_ext_net_1_id: [sn_1['id'], sn_2['id']]}
            ext_gw_1 = {
                'network_id': msn_ext_net_1_id,
                'external_fixed_ips': [{'subnet_id': sn_1['id']}]}
            if same_ext_net is False:
                ext_net_2_id = n_external_2['network']['id']
                self._set_net_external(ext_net_2_id)
                sn_3 = self._make_subnet(
                    self.fmt, n_external_2, '10.0.2.1', cidr='10.0.2.0/24',
                    tenant_id=tenant_id_2)['subnet']
                ext_gw_2_subnets = [sn_3['id']]
                ext_gw_2 = {'network_id': ext_net_2_id,
                            'external_fixed_ips': [{'subnet_id': sn_3['id']}]}
            else:
                ext_net_2_id = msn_ext_net_1_id
                ext_gw_2_subnets = ext_net_ids[msn_ext_net_1_id]
                ext_gw_2 = ext_gw_1
            ext_net_ids[ext_net_2_id] = ext_gw_2_subnets
            with self.router(tenant_id=tenant_id_1,
                             external_gateway_info=ext_gw_1,
                             set_context=set_context) as router1, \
                    self.router(name='router2', tenant_id=tenant_id_2,
                                external_gateway_info=ext_gw_2,
                                set_context=set_context) as router2, \
                    self.router(tenant_id=tenant_id_2,
                                external_gateway_info=ext_gw_1,
                                set_context=set_context) as router3:
                r1 = router1['router']
                r2 = router2['router']
                r3 = router3['router']
                self.l3_plugin._process_backlogged_routers()
                attempt = 0
                complete_router_dict = False
                while complete_router_dict is False and attempt < 10:
                    r1_after = self._show('routers', r1['id'])['router']
                    if (ha.ENABLED in r1_after and
                        ha.DETAILS in r1_after and
                            r1_after['status'] != ROUTER_INFO_INCOMPLETE):
                        complete_router_dict = True
                    attempt += 1
                r_ids = [r1['id'], r2['id'], r3['id']]
                self._verify_sync_data(r1_after, r_ids, ext_net_ids)

    def test_l3_cfg_agent_query_global_router_info(self):
        self._test_l3_cfg_agent_query_global_router_info()

    def test_l3_cfg_agent_query_global_router_info_dt(self):
        self._test_l3_cfg_agent_query_global_router_info(same_tenant=False)

    def test_l3_cfg_agent_query_global_router_info_den(self):
        self._test_l3_cfg_agent_query_global_router_info(same_ext_net=False)

    def test_l3_cfg_agent_query_global_router_info_dt_den(self):
        self._test_l3_cfg_agent_query_global_router_info(same_tenant=False,
                                                         same_ext_net=False)
