# Copyright 2015 Cisco Systems, Inc.
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
#

import netaddr

from networking_cisco.apps.saf.common import config
from networking_cisco.apps.saf.common import constants as const
from networking_cisco.apps.saf.common import dfa_exceptions as dexc
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import utils
from networking_cisco.apps.saf.db import dfa_db_models as dfa_dbm
from networking_cisco.apps.saf.server import (
    dfa_openstack_helper as OsHelper)
import networking_cisco.apps.saf.server.services.firewall.native.fw_constants \
    as fw_const

from networking_cisco._i18n import _LE, _LI

LOG = logging.getLogger(__name__)


class ServiceIpSegTenantMap(dfa_dbm.DfaDBMixin):
    """Tenant Specific Service Attributes.

    Class for storing/retrieving the tenant specific service attributes
    locally as well as from the FW DB
    """
    def __init__(self):
        """Initialization. """
        self.fabric_status = False
        self.in_dcnm_net_dict = self.out_dcnm_net_dict = {}
        self.in_dcnm_subnet_dict = self.out_dcnm_subnet_dict = {}
        self.state = fw_const.INIT_STATE
        self.result = fw_const.RESULT_FW_CREATE_INIT
        self.fw_dict = {}
        self.in_subnet_dict = self.out_subnet_dict = {}
        self.dummy_net_id = self.dummy_subnet_id = self.dummy_router_id = None

    def update_fw_dict(self, fw_dict):
        """updating the fw dict. """
        self.fw_dict.update(fw_dict)

    def get_fw_dict(self):
        """retrieving the fw dict. """
        return self.fw_dict

    def store_dummy_router_net(self, net_id, subnet_id, rtr_id):
        """Storing the router attributes. """
        self.dummy_net_id = net_id
        self.dummy_subnet_id = subnet_id
        self.dummy_router_id = rtr_id

    def get_dcnm_net_dict(self, direc):
        """Retrieve the DCNM net dict. """
        if direc == 'in':
            return self.in_dcnm_net_dict
        else:
            return self.out_dcnm_net_dict

    def store_dcnm_net_dict(self, net_dict, direc):
        """Storing the DCNM net dict. """
        if direc == 'in':
            self.in_dcnm_net_dict = net_dict
        else:
            self.out_dcnm_net_dict = net_dict

    def get_dcnm_subnet_dict(self, direc):
        """Retrieve the DCNM subnet dict. """
        if direc == 'in':
            return self.in_dcnm_subnet_dict
        else:
            return self.out_dcnm_subnet_dict

    def _parse_subnet(self, subnet_dict):
        """Return the subnet, start, end, gateway of a subnet. """
        if not subnet_dict:
            return
        alloc_pool = subnet_dict.get('allocation_pools')
        cidr = subnet_dict.get('cidr')
        subnet = cidr.split('/')[0]
        start = alloc_pool[0].get('start')
        end = alloc_pool[0].get('end')
        gateway = subnet_dict.get('gateway_ip')
        sec_gateway = subnet_dict.get('secondary_gw')
        return {'subnet': subnet, 'start': start, 'end': end,
                'gateway': gateway, 'sec_gateway': sec_gateway}

    def store_dcnm_subnet_dict(self, subnet_dict, direc):
        """Store the subnet attributes and dict. """
        if direc == 'in':
            self.in_dcnm_subnet_dict = subnet_dict
            self.in_subnet_dict = self._parse_subnet(subnet_dict)
        else:
            self.out_dcnm_subnet_dict = subnet_dict
            self.out_subnet_dict = self._parse_subnet(subnet_dict)

    def get_in_seg_vlan(self):
        """Retrieve the seg, vlan, mod domain for IN network. """
        return self.in_dcnm_net_dict.get('segmentation_id'), (
            self.in_dcnm_net_dict.get('vlan_id'))

    def get_out_seg_vlan(self):
        """Retrieve the seg, vlan, mod domain for OUT network. """
        return self.out_dcnm_net_dict.get('segmentation_id'), (
            self.out_dcnm_net_dict.get('vlan_id'))

    def get_in_ip_addr(self):
        """Retrieve 'in' service subnet attributes. """
        return self.in_subnet_dict

    def get_out_ip_addr(self):
        """Retrieve 'out' service subnet attributes. """
        return self.out_subnet_dict

    def get_dummy_router_net(self):
        """Retrieve the dummy router attributes. """
        return {'net_id': self.dummy_net_id,
                'subnet_id': self.dummy_subnet_id,
                'router_id': self.dummy_router_id}

    def set_fabric_create(self, status):
        """Store the fabric create status. """
        self.fabric_status = status

    def is_fabric_create(self):
        """Retrieve the fabric create status. """
        return self.fabric_status

    def create_fw_db(self, fw_id, fw_name, tenant_id):
        """Create FW dict. """
        fw_dict = {'fw_id': fw_id, 'name': fw_name, 'tenant_id': tenant_id}
        # FW DB is already created by FW Mgr
        # self.add_fw_db(fw_id, fw_dict)
        self.update_fw_dict(fw_dict)

    def destroy_local_fw_db(self):
        """Delete the FW dict and its attributes. """
        del self.fw_dict
        del self.in_dcnm_net_dict
        del self.in_dcnm_subnet_dict
        del self.out_dcnm_net_dict
        del self.out_dcnm_subnet_dict

    def update_fw_local_cache(self, net, direc, start):
        """Update the fw dict with Net ID and service IP. """
        fw_dict = self.get_fw_dict()
        if direc == 'in':
            fw_dict.update({'in_network_id': net, 'in_service_ip': start})
        else:
            fw_dict.update({'out_network_id': net, 'out_service_ip': start})
        self.update_fw_dict(fw_dict)

    def update_fw_local_result_str(self, os_result=None, dcnm_result=None,
                                   dev_result=None):
        """Update the FW result in the dict. """
        fw_dict = self.get_fw_dict()
        if os_result is not None:
            fw_dict['os_status'] = os_result
        if dcnm_result is not None:
            fw_dict['dcnm_status'] = dcnm_result
        if dev_result is not None:
            fw_dict['dev_status'] = dev_result
        self.update_fw_dict(fw_dict)

    def update_fw_local_result(self, os_result=None, dcnm_result=None,
                               dev_result=None):
        """Retrieve and update the FW result in the dict. """
        self.update_fw_local_result_str(os_result=os_result,
                                        dcnm_result=dcnm_result,
                                        dev_result=dev_result)

    def update_fw_local_router(self, net_id, subnet_id, router_id, os_result):
        """Update the FW with router attributes. """
        fw_dict = self.get_fw_dict()
        fw_dict.update({'router_id': router_id, 'router_net_id': net_id,
                        'router_subnet_id': subnet_id})
        self.store_dummy_router_net(net_id, subnet_id, router_id)
        self.update_fw_local_result(os_result=os_result)

    def commit_fw_db(self):
        """Calls routine to update the FW DB. """
        fw_dict = self.get_fw_dict()
        self.update_fw_db(fw_dict.get('fw_id'), fw_dict)

    def commit_fw_db_result(self):
        """Calls routine to update the FW create/delete result in DB. """
        fw_dict = self.get_fw_dict()
        self.update_fw_db_result(fw_dict.get('fw_id'), fw_dict)

    def store_local_final_result(self, final_res):
        """Store the final reult for FW create/delete. """
        self.result = final_res

    def get_store_local_final_result(self):
        """Store/Retrieve the final result.

        Retrieve the final result for FW create/delete from DB and store it
        locally.
        """
        fw_dict = self.get_fw_dict()
        fw_data, fw_data_dict = self.get_fw(fw_dict.get('fw_id'))
        res = fw_data.result
        self.store_local_final_result(res)

    def get_local_final_result(self):
        """Retrieve the final reult for FW create/delete. """
        return self.result

    def store_state(self, state, popl_db=True):
        """Store the state of FW create/del operation. """
        self.state = state
        if popl_db:
            fw_dict = self.get_fw_dict()
            self.append_state_final_result(fw_dict.get('fw_id'),
                                           self.get_local_final_result(),
                                           state)

    def fixup_state(self, from_str, state):
        """Fixup state after retart.

        Fixup the state, if Delete is called when create SM is half-way
        through.
        """
        result = self.get_local_final_result()
        if from_str == fw_const.FW_CR_OP:
            if result == fw_const.RESULT_FW_DELETE_INIT:
                return state + 1
        if from_str == fw_const.FW_DEL_OP:
            if result == fw_const.RESULT_FW_CREATE_INIT:
                return state - 1
        return state

    def get_state(self):
        """Return the current state. """
        return self.state


class FabricApi(object):
    """Class for retrieving FW attributes, available to external modules. """
    serv_obj_dict = {}
    ip_db_obj = {}

    @classmethod
    def store_tenant_obj(cls, tenant_id, obj):
        """Store the tenant obj. """
        cls.serv_obj_dict[tenant_id] = obj

    @classmethod
    def del_obj(cls, tenant_id, obj):
        """Delete the tenant obj. """
        del cls.serv_obj_dict[tenant_id]

    @classmethod
    def store_db_obj(cls, in_obj, out_obj):
        """Store the IP DB object. """
        cls.ip_db_obj['in'] = in_obj
        cls.ip_db_obj['out'] = out_obj

    @classmethod
    def get_in_ip_addr(cls, tenant_id):
        """Retrieves the 'in' service subnet attributes. """
        if tenant_id not in cls.serv_obj_dict:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return
        tenant_obj = cls.serv_obj_dict.get(tenant_id)
        return tenant_obj.get_in_ip_addr()

    @classmethod
    def get_out_ip_addr(cls, tenant_id):
        """Retrieves the 'out' service subnet attributes. """
        if tenant_id not in cls.serv_obj_dict:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return
        tenant_obj = cls.serv_obj_dict.get(tenant_id)
        return tenant_obj.get_out_ip_addr()

    @classmethod
    def get_in_srvc_node_ip_addr(cls, tenant_id):
        """Retrieves the IN service node IP address. """
        if tenant_id not in cls.serv_obj_dict:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return
        tenant_obj = cls.serv_obj_dict.get(tenant_id)
        in_subnet_dict = tenant_obj.get_in_ip_addr()
        next_hop = str(netaddr.IPAddress(in_subnet_dict.get('subnet')) + 2)
        return next_hop

    @classmethod
    def get_out_srvc_node_ip_addr(cls, tenant_id):
        """Retrieves the OUT service node IP address. """
        if tenant_id not in cls.serv_obj_dict:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return
        tenant_obj = cls.serv_obj_dict.get(tenant_id)
        out_subnet_dict = tenant_obj.get_out_ip_addr()
        next_hop = str(netaddr.IPAddress(out_subnet_dict.get('subnet')) + 2)
        return next_hop

    @classmethod
    def get_dummy_router_net(cls, tenant_id):
        """Retrieves the dummy router network info. """
        if tenant_id not in cls.serv_obj_dict:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return
        tenant_obj = cls.serv_obj_dict.get(tenant_id)
        return tenant_obj.get_dummy_router_net()

    @classmethod
    def get_in_seg_vlan(cls, tenant_id):
        """Retrieves the IN Seg, VLAN, mob domain. """
        if tenant_id not in cls.serv_obj_dict:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return None, None
        tenant_obj = cls.serv_obj_dict.get(tenant_id)
        return tenant_obj.get_in_seg_vlan()

    @classmethod
    def get_out_seg_vlan(cls, tenant_id):
        """Retrieves the OUT Seg, VLAN, mob domain. """
        if tenant_id not in cls.serv_obj_dict:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return None, None
        tenant_obj = cls.serv_obj_dict.get(tenant_id)
        return tenant_obj.get_out_seg_vlan()

    @classmethod
    def get_in_subnet_id(cls, tenant_id):
        """Retrieve the subnet ID of IN network. """
        if 'in' not in cls.ip_db_obj:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return None
        db_obj = cls.ip_db_obj.get('in')
        in_subnet_dict = cls.get_in_ip_addr(tenant_id)
        sub = db_obj.get_subnet(in_subnet_dict.get('subnet'))
        return sub.subnet_id

    @classmethod
    def get_out_subnet_id(cls, tenant_id):
        """Retrieve the subnet ID of OUT network. """
        if 'out' not in cls.ip_db_obj:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return None
        db_obj = cls.ip_db_obj.get('out')
        out_subnet_dict = cls.get_out_ip_addr(tenant_id)
        sub = db_obj.get_subnet(out_subnet_dict.get('subnet'))
        return sub.subnet_id

    @classmethod
    def get_in_net_id(cls, tenant_id):
        """Retrieve the network ID of IN network. """
        if 'in' not in cls.ip_db_obj:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return None
        db_obj = cls.ip_db_obj.get('in')
        in_subnet_dict = cls.get_in_ip_addr(tenant_id)
        sub = db_obj.get_subnet(in_subnet_dict.get('subnet'))
        return sub.network_id

    @classmethod
    def get_out_net_id(cls, tenant_id):
        """Retrieve the network ID of OUT network. """
        if 'out' not in cls.ip_db_obj:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return None
        db_obj = cls.ip_db_obj.get('out')
        out_subnet_dict = cls.get_out_ip_addr(tenant_id)
        sub = db_obj.get_subnet(out_subnet_dict.get('subnet'))
        return sub.network_id

    @classmethod
    def is_network_source_fw(cls, nwk, nwk_name):
        """Check if SOURCE is FIREWALL, if yes return TRUE.

        If source is None or entry not in NWK DB, check from Name.
        Name should have constant AND length should match.
        """
        if nwk is not None:
            if nwk.source == fw_const.FW_CONST:
                return True
            return False
        if nwk_name in fw_const.DUMMY_SERVICE_NWK and (
           len(nwk_name) == len(fw_const.DUMMY_SERVICE_NWK) +
           fw_const.SERVICE_NAME_EXTRA_LEN):
            return True
        if nwk_name in fw_const.IN_SERVICE_NWK and (
           len(nwk_name) == len(fw_const.IN_SERVICE_NWK) +
           fw_const.SERVICE_NAME_EXTRA_LEN):
            return True
        if nwk_name in fw_const.OUT_SERVICE_NWK and (
           len(nwk_name) == len(fw_const.OUT_SERVICE_NWK) +
           fw_const.SERVICE_NAME_EXTRA_LEN):
            return True
        return False

    def is_subnet_source_fw(cls, tenant_id, subnet):
        """Check if the subnet is created as a result of any FW operation. """
        cfg = config.CiscoDFAConfig().cfg
        subnet = subnet.split('/')[0]
        in_sub_dict = cls.get_in_ip_addr(tenant_id)
        if not in_sub_dict:
            return False
        if in_sub_dict.get('subnet') == subnet:
            return True
        out_sub_dict = cls.get_out_ip_addr(tenant_id)
        if not out_sub_dict:
            return False
        if out_sub_dict.get('subnet') == subnet:
            return True
        dummy_sub = cfg.firewall.fw_service_dummy_ip_subnet
        dummy_sub = dummy_sub.split('/')[0]
        return subnet == dummy_sub


class FabricBase(dfa_dbm.DfaDBMixin, FabricApi):

    """Class to implement Fabric configuration for Physical FW. """

    def __init__(self):
        """Init Routine for FabricBase class.

        Init routine that parses the arguments and fills in
        the local cache. It also tries to recover the DB
        in case of mis-match caused to ungraceful enabler crash.
        """
        LOG.debug("Entered FabricPhys")
        cfg = config.CiscoDFAConfig().cfg
        # TODO(padkrish) Add simple validation of config file input.
        self.auto_nwk_create = cfg.firewall.fw_auto_serv_nwk_create
        self.serv_vlan_min = int(cfg.dcnm.vlan_id_min)
        self.serv_vlan_max = int(cfg.dcnm.vlan_id_max)
        self.serv_seg_min = int(cfg.dcnm.segmentation_id_min)
        self.serv_seg_max = int(cfg.dcnm.segmentation_id_max)
        seg_to = int(cfg.dcnm.segmentation_reuse_timeout)
        self.serv_host_prof = cfg.firewall.fw_service_host_profile
        self.serv_host_mode = cfg.firewall.fw_service_host_fwd_mode
        self.serv_ext_prof = cfg.firewall.fw_service_ext_profile
        self.serv_ext_mode = cfg.firewall.fw_service_ext_fwd_mode
        self.serv_part_vrf_prof = cfg.firewall.fw_service_part_vrf_profile
        self.serv_mgmt_ip = cfg.firewall.fw_mgmt_ip
        self.state = fw_const.INIT_STATE
        self.service_vlans = dfa_dbm.DfaSegmentTypeDriver(self.serv_vlan_min,
                                                          self.serv_vlan_max,
                                                          const.RES_VLAN,
                                                          cfg)
        self.service_segs = dfa_dbm.DfaSegmentTypeDriver(self.serv_seg_min,
                                                         self.serv_seg_max,
                                                         const.RES_SEGMENT,
                                                         cfg,
                                                         reuse_timeout=seg_to)
        self.service_in_ip_start = cfg.firewall.fw_service_in_ip_start
        self.service_in_ip_end = cfg.firewall.fw_service_in_ip_end
        self.mask = int(self.service_in_ip_start.split('/')[1])
        self.service_in_ip = dfa_dbm.DfasubnetDriver(self.service_in_ip_start,
                                                     self.service_in_ip_end,
                                                     const.RES_IN_SUBNET)
        self.service_out_ip_start = cfg.firewall.fw_service_out_ip_start
        self.service_out_ip_end = cfg.firewall.fw_service_out_ip_end
        self.service_out_ip = dfa_dbm.DfasubnetDriver(
            self.service_out_ip_start, self.service_out_ip_end,
            const.RES_OUT_SUBNET)
        self.servicedummy_ip_subnet = cfg.firewall.fw_service_dummy_ip_subnet
        self.service_attr = {}
        self.os_helper = OsHelper.DfaNeutronHelper()
        self.fabric_fsm = dict()
        self.dcnm_obj = None
        self.initialize_create_state_map()
        self.initialize_delete_state_map()
        self.initialize_fsm()
        self.mutex_lock = utils.lock()
        self.correct_db_restart()
        self.populate_local_cache()
        self.store_db_obj(self.service_in_ip, self.service_out_ip)

    def initialize_create_state_map(self):
        """This is a mapping of create result message string to state. """
        self.fabric_state_map = {
            fw_const.INIT_STATE_STR: fw_const.OS_IN_NETWORK_STATE,
            fw_const.OS_IN_NETWORK_CREATE_FAIL:
                fw_const.OS_IN_NETWORK_STATE,
            fw_const.OS_IN_NETWORK_CREATE_SUCCESS:
                fw_const.OS_OUT_NETWORK_STATE,
            fw_const.OS_OUT_NETWORK_CREATE_FAIL:
                fw_const.OS_OUT_NETWORK_STATE,
            fw_const.OS_OUT_NETWORK_CREATE_SUCCESS:
                fw_const.OS_DUMMY_RTR_STATE,
            fw_const.OS_DUMMY_RTR_CREATE_FAIL:
                fw_const.OS_DUMMY_RTR_STATE,
            fw_const.OS_DUMMY_RTR_CREATE_SUCCESS:
                fw_const.DCNM_IN_NETWORK_STATE,
            fw_const.DCNM_IN_NETWORK_CREATE_FAIL:
                fw_const.DCNM_IN_NETWORK_STATE,
            fw_const.DCNM_IN_NETWORK_CREATE_SUCCESS:
                fw_const.DCNM_IN_PART_UPDATE_STATE,
            fw_const.DCNM_IN_PART_UPDATE_FAIL:
                fw_const.DCNM_IN_PART_UPDATE_STATE,
            fw_const.DCNM_IN_PART_UPDATE_SUCCESS:
                fw_const.DCNM_OUT_PART_STATE,
            fw_const.DCNM_OUT_PART_CREATE_FAIL:
                fw_const.DCNM_OUT_PART_STATE,
            fw_const.DCNM_OUT_PART_CREATE_SUCCESS:
                fw_const.DCNM_OUT_NETWORK_STATE,
            fw_const.DCNM_OUT_NETWORK_CREATE_FAIL:
                fw_const.DCNM_OUT_NETWORK_STATE,
            fw_const.DCNM_OUT_NETWORK_CREATE_SUCCESS:
                fw_const.DCNM_OUT_PART_UPDATE_STATE,
            fw_const.DCNM_OUT_PART_UPDATE_FAIL:
                fw_const.DCNM_OUT_PART_UPDATE_STATE,
            fw_const.DCNM_OUT_PART_UPDATE_SUCCESS:
                fw_const.FABRIC_PREPARE_DONE_STATE}

    def initialize_delete_state_map(self):
        """This is a mapping of delete result message string to state. """
        self.fabric_state_del_map = {
            fw_const.INIT_STATE_STR: fw_const.OS_IN_NETWORK_STATE,
            fw_const.OS_IN_NETWORK_DEL_FAIL:
                fw_const.OS_IN_NETWORK_STATE,
            fw_const.OS_IN_NETWORK_DEL_SUCCESS:
                fw_const.INIT_STATE,
            fw_const.OS_OUT_NETWORK_DEL_FAIL:
                fw_const.OS_OUT_NETWORK_STATE,
            fw_const.OS_OUT_NETWORK_DEL_SUCCESS:
                fw_const.OS_IN_NETWORK_STATE,
            fw_const.OS_DUMMY_RTR_DEL_FAIL:
                fw_const.OS_DUMMY_RTR_STATE,
            fw_const.OS_DUMMY_RTR_DEL_SUCCESS:
                fw_const.OS_OUT_NETWORK_STATE,
            fw_const.DCNM_IN_NETWORK_DEL_FAIL:
                fw_const.DCNM_IN_NETWORK_STATE,
            fw_const.DCNM_IN_NETWORK_DEL_SUCCESS:
                fw_const.OS_DUMMY_RTR_STATE,
            fw_const.DCNM_IN_PART_UPDDEL_FAIL:
                fw_const.DCNM_IN_PART_UPDATE_STATE,
            fw_const.DCNM_IN_PART_UPDDEL_SUCCESS:
                fw_const.DCNM_IN_NETWORK_STATE,
            fw_const.DCNM_OUT_PART_DEL_FAIL:
                fw_const.DCNM_OUT_PART_STATE,
            fw_const.DCNM_OUT_PART_DEL_SUCCESS:
                fw_const.DCNM_IN_PART_UPDATE_STATE,
            fw_const.DCNM_OUT_NETWORK_DEL_FAIL:
                fw_const.DCNM_OUT_NETWORK_STATE,
            fw_const.DCNM_OUT_NETWORK_DEL_SUCCESS:
                fw_const.DCNM_OUT_PART_STATE,
            fw_const.DCNM_OUT_PART_UPDDEL_FAIL:
                fw_const.DCNM_OUT_PART_UPDATE_STATE,
            fw_const.DCNM_OUT_PART_UPDDEL_SUCCESS:
                fw_const.DCNM_OUT_NETWORK_STATE}

    def initialize_fsm(self):
        """Initializing the Finite State Machine.

        This is a mapping of state to a dict of appropriate create and delete
        functions.
        """
        self.fabric_fsm = {
            fw_const.INIT_STATE:
                [self.init_state, self.init_state],
            fw_const.OS_IN_NETWORK_STATE:
                [self.create_os_in_nwk, self.delete_os_in_nwk],
            fw_const.OS_OUT_NETWORK_STATE:
                [self.create_os_out_nwk, self.delete_os_out_nwk],
            fw_const.OS_DUMMY_RTR_STATE:
                [self.create_os_dummy_rtr, self.delete_os_dummy_rtr],
            fw_const.DCNM_IN_NETWORK_STATE:
                [self.create_dcnm_in_nwk, self.delete_dcnm_in_nwk],
            fw_const.DCNM_IN_PART_UPDATE_STATE:
                [self.update_dcnm_in_part, self.clear_dcnm_in_part],
            fw_const.DCNM_OUT_PART_STATE:
                [self.create_dcnm_out_part, self.delete_dcnm_out_part],
            fw_const.DCNM_OUT_NETWORK_STATE:
                [self.create_dcnm_out_nwk, self.delete_dcnm_out_nwk],
            fw_const.DCNM_OUT_PART_UPDATE_STATE:
                [self.update_dcnm_out_part, self.clear_dcnm_out_part],
            fw_const.FABRIC_PREPARE_DONE_STATE:
                [self.prepare_fabric_done, self.prepare_fabric_done]}

    def store_dcnm(self, dcnm_obj):
        """Stores the DCNM object. """
        self.dcnm_obj = dcnm_obj

    def get_service_obj(self, tenant_id):
        """Retrieves the service object associated with a tenant. """
        return self.service_attr[tenant_id]

    def create_serv_obj(self, tenant_id):
        """Creates and stores the service object associated with a tenant. """
        self.service_attr[tenant_id] = ServiceIpSegTenantMap()
        self.store_tenant_obj(tenant_id, self.service_attr[tenant_id])

    def delete_serv_obj(self, tenant_id):
        """Creates and stores the service object associated with a tenant. """
        self.del_obj(tenant_id, self.service_attr[tenant_id])
        del self.service_attr[tenant_id]

    def store_net_db(self, tenant_id, net, net_dict, result):
        """Store service network in DB. """
        network_dict = {'name': net_dict.get('name'),
                        'config_profile': net_dict.get('config_profile'),
                        'segmentation_id': net_dict.get('segmentation_id'),
                        'tenant_id': tenant_id,
                        'fwd_mode': net_dict.get('fwd_mode'),
                        'vlan': net_dict.get('vlan_id')}
        self.add_network_db(net, network_dict, fw_const.FW_CONST, result)

    def store_fw_db(self, tenant_id, net, subnet_dict, direc):
        """Calls the service object routine to commit the FW entry to DB. """
        serv_obj = self.get_service_obj(tenant_id)
        sub = subnet_dict.get('allocation_pools')[0].get('start')
        serv_obj.update_fw_local_cache(net, direc, sub)
        serv_obj.commit_fw_db()

    def update_fw_db_result(self, tenant_id, os_status=None, dcnm_status=None,
                            dev_status=None):
        """Update the FW DB Result and commit it in DB.

        Calls the service object routine to commit the result of a FW
        operation in to DB
        """
        serv_obj = self.get_service_obj(tenant_id)
        serv_obj.update_fw_local_result(os_status, dcnm_status, dev_status)
        serv_obj.commit_fw_db_result()

    def store_fw_db_router(self, tenant_id, net_id, subnet_id, router_id,
                           os_status):
        """Store the result of FW router operation in DB.

        Calls the service object routine to commit the result of router
        operation in to DB, after updating the local cache.
        """
        serv_obj = self.get_service_obj(tenant_id)
        serv_obj.update_fw_local_router(net_id, subnet_id, router_id,
                                        os_status)
        serv_obj.commit_fw_db()
        serv_obj.commit_fw_db_result()

    def store_net_fw_db(self, tenant_id, net, net_dict, subnet_dict,
                        direc, result, os_status=None, dcnm_status=None,
                        dev_status=None):
        """Save the entries in Network and Firewall DB.

        Stores the entries into Network DB and Firewall DB as well as update
        the result of operation into FWDB. Generally called by OS operations
        that wants to modify both the Net DB and FW DB.
        """
        self.store_net_db(tenant_id, net, net_dict, result)
        self.store_fw_db(tenant_id, net, subnet_dict, direc)
        self.update_fw_db_result(tenant_id, os_status=os_status,
                                 dcnm_status=dcnm_status,
                                 dev_status=dev_status)

    def get_gateway(self, subnet):
        """Retrieve the Gateway associated with the subnet.

        Returns the Gateway associated with a subnet. This is also the Gateway
        address configured in the leaf switch or ToR. This value is subnet + 1.
        The Gateway created in Openstack is + 2, which is also the FW's IN
        interface address and DCNM's service node IP address.
        """
        # TODO(padkrish) No error checking is done below for the size of CIDR.
        return str(netaddr.IPAddress(subnet) + 1)

    def get_secondary_gateway(self, subnet):
        """Returns the Secondary Gateway associated with a subnet.

        This is the end IP address. The secondary GW IP address reuses the
        end IP address.
        """
        return self.get_end_ip(subnet)

    def get_start_ip(self, subnet):
        """Returns the starting IP associated with a subnet.

        This value is start IP address is + 3.
        """
        return str(netaddr.IPAddress(subnet) + 3)

    def get_end_ip(self, subnet):
        """Returns the end IP associated with a subnet.

        It's value is the second last address of the CIDR.
        i.e.. end IP address is -2 (from the end of the subnet)
        """
        return str(netaddr.IPAddress(subnet) + (1 << (32 - self.mask)) - 2)

    def check_allocate_ip(self, obj, direc):
        """This function allocates a subnet from the pool.

        It first checks to see if Openstack is already using the subnet.
        If yes, it retries until it finds a free subnet not used by
        Openstack.
        """
        subnet_lst = self.os_helper.get_all_subnets_cidr(no_mask=True)
        ip_next = obj.allocate_subnet(subnet_lst)
        if ip_next is None:
            LOG.error(_LE("Unable to allocate a subnet for direction %s"),
                      direc)
        return ip_next

    def get_next_ip(self, tenant_id, direc):
        """Retrieve the next available subnet.

        Given a tenant, it returns the service subnet values assigned
        to it based on direction.
        """
        # TODO(padkrish) Put in a common functionality for services.
        if direc == 'in':
            subnet_dict = self.get_in_ip_addr(tenant_id)
        else:
            subnet_dict = self.get_out_ip_addr(tenant_id)
        if subnet_dict:
            return subnet_dict
        if direc == 'in':
            # ip_next = self.service_in_ip.allocate_subnet()
            ip_next = self.check_allocate_ip(self.service_in_ip, "in")
        else:
            # ip_next = self.service_out_ip.allocate_subnet()
            ip_next = self.check_allocate_ip(self.service_out_ip, "out")
        return {'subnet': ip_next, 'start': self.get_start_ip(ip_next),
                'end': self.get_end_ip(ip_next),
                'gateway': self.get_gateway(ip_next),
                'sec_gateway': self.get_secondary_gateway(ip_next)}

    def release_subnet(self, cidr, direc):
        """Routine to release a subnet from the DB. """
        if direc == 'in':
            self.service_in_ip.release_subnet(cidr)
        else:
            self.service_out_ip.release_subnet(cidr)

    def fill_dcnm_subnet_info(self, tenant_id, subnet, start, end, gateway,
                              sec_gateway, direc):
        """Fills the DCNM subnet parameters.

        Function that fills the subnet parameters for a tenant required by
        DCNM.
        """
        serv_obj = self.get_service_obj(tenant_id)
        fw_dict = serv_obj.get_fw_dict()
        fw_id = fw_dict.get('fw_id')
        if direc == 'in':
            name = fw_id[0:4] + fw_const.IN_SERVICE_SUBNET + (
                fw_id[len(fw_id) - 4:])
        else:
            name = fw_id[0:4] + fw_const.OUT_SERVICE_SUBNET + (
                fw_id[len(fw_id) - 4:])
        subnet_dict = {'enable_dhcp': False,
                       'tenant_id': tenant_id,
                       'name': name,
                       'cidr': subnet + '/24',
                       'gateway_ip': gateway,
                       'secondary_gw': sec_gateway,
                       'ip_version': 4}
        subnet_dict['allocation_pools'] = [{'start': start, 'end': end}]
        # TODO(padkrish) Network ID and subnet ID are not filled.
        return subnet_dict

    def retrieve_dcnm_subnet_info(self, tenant_id, direc):
        """Retrieves the DCNM subnet info for a tenant. """
        serv_obj = self.get_service_obj(tenant_id)
        subnet_dict = serv_obj.get_dcnm_subnet_dict(direc)
        return subnet_dict

    def alloc_retrieve_subnet_info(self, tenant_id, direc):
        """Allocate and store Subnet.

        This function initially checks if subnet is allocated for a tenant
        for the in/out direction. If not, it calls routine to allocate a subnet
        and stores it on tenant object.
        """
        serv_obj = self.get_service_obj(tenant_id)
        subnet_dict = self.retrieve_dcnm_subnet_info(tenant_id, direc)
        if subnet_dict:
            return subnet_dict
        ip_subnet_dict = self.get_next_ip(tenant_id, direc)
        subnet_dict = self.fill_dcnm_subnet_info(
            tenant_id, ip_subnet_dict.get('subnet'),
            ip_subnet_dict.get('start'), ip_subnet_dict.get('end'),
            ip_subnet_dict.get('gateway'), ip_subnet_dict.get('sec_gateway'),
            direc)
        serv_obj.store_dcnm_subnet_dict(subnet_dict, direc)
        return subnet_dict

    def retrieve_dcnm_net_info(self, tenant_id, direc):
        """Retrieves the DCNM network info for a tenant. """
        serv_obj = self.get_service_obj(tenant_id)
        net_dict = serv_obj.get_dcnm_net_dict(direc)
        return net_dict

    def update_dcnm_net_info(self, tenant_id, direc, vlan_id,
                             segmentation_id):
        """Update the DCNM net info with allocated values of seg/vlan. """
        net_dict = self.retrieve_dcnm_net_info(tenant_id, direc)
        if not net_dict:
            return None
        net_dict['vlan_id'] = vlan_id
        if vlan_id != 0:
            net_dict['mob_domain'] = True
        net_dict['segmentation_id'] = segmentation_id
        return net_dict

    def fill_dcnm_net_info(self, tenant_id, direc, vlan_id=0,
                           segmentation_id=0):
        """Fill DCNM network parameters.

        Function that fills the network parameters for a tenant required by
        DCNM.
        """
        serv_obj = self.get_service_obj(tenant_id)
        fw_dict = serv_obj.get_fw_dict()
        fw_id = fw_dict.get('fw_id')
        net_dict = {'status': 'ACTIVE', 'admin_state_up': True,
                    'tenant_id': tenant_id, 'provider:network_type': 'local',
                    'vlan_id': vlan_id, 'segmentation_id': segmentation_id}
        if vlan_id == 0:
            net_dict.update({'mob_domain': False, 'mob_domain_name': None})
        else:
            net_dict.update({'mob_domain': True})
        # TODO(padkrish) NWK ID are not filled.
        if direc == 'in':
            name = fw_id[0:4] + fw_const.IN_SERVICE_NWK + (
                fw_id[len(fw_id) - 4:])
            net_dict.update({'name': name, 'part_name': None,
                             'config_profile': self.serv_host_prof,
                             'fwd_mode': self.serv_host_mode})
        else:
            name = fw_id[0:4] + fw_const.OUT_SERVICE_NWK + (
                fw_id[len(fw_id) - 4:])
            net_dict.update({'name': name,
                             'part_name': fw_const.SERV_PART_NAME,
                             'config_profile': self.serv_ext_prof,
                             'fwd_mode': self.serv_ext_mode})
        return net_dict

    def retrieve_network_info(self, tenant_id, direc):
        """Retrieve the DCNM Network information.

        Retrieves DCNM net dict if already filled, else, it calls
        routines to fill the net info and store it in tenant obj.
        """
        serv_obj = self.get_service_obj(tenant_id)
        net_dict = self.retrieve_dcnm_net_info(tenant_id, direc)
        if net_dict:
            return net_dict
        net_dict = self.fill_dcnm_net_info(tenant_id, direc)
        serv_obj.store_dcnm_net_dict(net_dict, direc)
        return net_dict

    def alloc_seg(self, net_id):
        """Allocates the segmentation ID. """
        segmentation_id = self.service_segs.allocate_segmentation_id(
            net_id, source=fw_const.FW_CONST)
        return segmentation_id

    def alloc_vlan(self, net_id):
        """Allocates the vlan ID. """
        vlan_id = self.service_vlans.allocate_segmentation_id(
            net_id, source=fw_const.FW_CONST)
        return vlan_id

    def update_subnet_db_info(self, tenant_id, direc, net_id, subnet_id):
        """Update the subnet DB with Net and Subnet ID, given the subnet. """
        subnet_dict = self.retrieve_dcnm_subnet_info(tenant_id, direc)
        if not subnet_dict:
            LOG.error(_LE("Subnet dict not found for tenant %s"), tenant_id)
            return
        subnet = subnet_dict['cidr'].split('/')[0]
        if direc == 'in':
            self.service_in_ip.update_subnet(subnet, net_id, subnet_id)
        else:
            self.service_out_ip.update_subnet(subnet, net_id, subnet_id)

    def update_net_info(self, tenant_id, direc, vlan_id, segmentation_id):
        """Update the DCNM netinfo with vlan and segmentation ID. """
        serv_obj = self.get_service_obj(tenant_id)
        net_dict = self.update_dcnm_net_info(tenant_id, direc, vlan_id,
                                             segmentation_id)
        serv_obj.store_dcnm_net_dict(net_dict, direc)
        return net_dict

    def _create_service_nwk(self, tenant_id, tenant_name, direc):
        """Function to create the service in network in DCNM. """
        net_dict = self.retrieve_dcnm_net_info(tenant_id, direc)
        net = utils.Dict2Obj(net_dict)
        subnet_dict = self.retrieve_dcnm_subnet_info(tenant_id, direc)
        subnet = utils.Dict2Obj(subnet_dict)
        try:
            self.dcnm_obj.create_service_network(tenant_name, net, subnet)
        except dexc.DfaClientRequestFailed:
            LOG.error(_LE("Failed to create network in DCNM %s"), direc)
            return False
        return True

    def _delete_service_nwk(self, tenant_id, tenant_name, direc):
        """Function to delete the service in network in DCNM. """
        net_dict = {}
        if direc == 'in':
            seg, vlan = self.get_in_seg_vlan(tenant_id)
            net_dict['part_name'] = None
        else:
            seg, vlan = self.get_out_seg_vlan(tenant_id)
            net_dict['part_name'] = fw_const.SERV_PART_NAME
        net_dict['segmentation_id'] = seg
        net_dict['vlan'] = vlan
        net = utils.Dict2Obj(net_dict)
        ret = True
        try:
            self.dcnm_obj.delete_service_network(tenant_name, net)
        except dexc.DfaClientRequestFailed:
            LOG.error(_LE("Failed to delete network in DCNM %s"), direc)
            ret = False
        return ret

    def get_dummy_router_net(self, tenant_id):
        """Retrieves the dummy router information from service object. """
        if tenant_id not in self.service_attr:
            LOG.error(_LE("Fabric not prepared for tenant %s"), tenant_id)
            return
        tenant_obj = self.get_service_obj(tenant_id)
        return tenant_obj.get_dummy_router_net()

    def _create_out_partition(self, tenant_id, tenant_name):
        """Function to create a service partition. """
        vrf_prof_str = self.serv_part_vrf_prof
        self.dcnm_obj.create_partition(tenant_name, fw_const.SERV_PART_NAME,
                                       None, vrf_prof_str,
                                       desc="Service Partition")

    def _update_partition_srvc_node_ip(self, tenant_name, srvc_ip,
                                       vrf_prof=None, part_name=None):
        """Function to update srvc_node address of partition. """
        self.dcnm_obj.update_project(tenant_name, part_name,
                                     service_node_ip=srvc_ip,
                                     vrf_prof=vrf_prof,
                                     desc="Service Partition")

    def _update_partition_dci_id(self, tenant_name, dci_id,
                                 vrf_prof=None, part_name=None):
        """Function to update DCI ID of partition. """
        self.dcnm_obj.update_project(tenant_name, part_name, dci_id=dci_id,
                                     vrf_prof=vrf_prof)

    def _update_partition_in_create(self, tenant_id, tenant_name):
        """Function to update a  partition. """
        in_subnet_dict = self.get_in_ip_addr(tenant_id)
        # self._update_partition(tenant_name, in_ip)
        # Need more generic thinking on this one TODO(padkrish)
        next_hop = str(netaddr.IPAddress(in_subnet_dict.get('subnet')) + 2)
        self._update_partition_srvc_node_ip(tenant_name, next_hop)

    def _update_partition_in_delete(self, tenant_name):
        """Function to update a  partition. """
        self._update_partition_srvc_node_ip(tenant_name, None)

    def _update_partition_out_create(self, tenant_id, tenant_name):
        """Function to update a  partition. """
        vrf_prof = self.serv_part_vrf_prof
        seg = self.dcnm_obj.get_partition_segmentId(tenant_name,
                                                    fw_const.SERV_PART_NAME)
        if seg is None:
            return False
        else:
            self._update_partition_dci_id(tenant_name, seg,
                                          vrf_prof=vrf_prof,
                                          part_name=fw_const.SERV_PART_NAME)
            return True

    def _delete_partition(self, tenant_id, tenant_name):
        """Function to delete a service partition. """
        self.dcnm_obj.delete_partition(tenant_name, fw_const.SERV_PART_NAME)

    def allocate_seg_vlan(self, net_id, is_fw_virt, direc, tenant_id):
        """allocate segmentation ID and VLAN ID.

        Allocate vlan, seg thereby storing NetID atomically.
        This saves an extra step to update DB with NetID after allocation.
        Also may save an extra step after restart, if process crashed
        after allocation but before updating DB with NetID. Now, since
        both steps are combined, Vlan/Seg won't be allocated w/o NetID.
        """
        seg = self.alloc_seg(net_id)
        vlan = 0
        # VLAN allocation is only needed for physical firewall case
        if not is_fw_virt:
            vlan = self.alloc_vlan(net_id)
        # Updating the local cache
        self.update_net_info(tenant_id, direc, vlan, seg)

    def create_openstack_network(self, subnet, network, tenant_id,
                                 tenant_name, direction):
        """Helper function to create openstack network.

        The net_id and subnet_id is returned. Upon failure, the subnet is
        deallocated.
        """
        try:
            gw = str(netaddr.IPAddress(subnet['cidr'].split('/')[0]) + 2)
            net_id, subnet_id = self.os_helper.create_network(
                network['name'], tenant_id, subnet['cidr'], gw=gw)
            if net_id is None or subnet_id is None:
                self.release_subnet(subnet['cidr'], direction)
            return net_id, subnet_id
        except Exception as exc:
            self.release_subnet(subnet['cidr'], direction)
            LOG.error(_LE("Create network for tenant %(tenant)s "
                          "network %(name)s direction %(dir)s failed "
                          "exc %(exc)s "),
                      {'tenant': tenant_name, 'name': network['name'],
                       'dir': direction, 'exc': str(exc)})
            return None, None

    def _create_os_nwk(self, tenant_id, tenant_name, direc, is_fw_virt=False):
        """Function to create Openstack network.

        This function does the following:
        1. Allocate an IP address with the net_id/subnet_id not filled in the
           DB.
        2. Fill network parameters w/o vlan, segmentation_id, because we don't
           have net_id to store in DB.
        3. Create a Openstack network, using the network parameters created in
           the previous step. At this point we will have a net_id.
        4. Allocate segmentation_id, vlan and along with net_id store it in the
           DB.
        5. Update IP DB with net_id created in step 3. So, after restart
           deallocate any IP DB entries that does not have a net_id/subnet_id.
        """
        subnet = self.alloc_retrieve_subnet_info(tenant_id, direc)
        network = self.retrieve_network_info(tenant_id, direc)
        net_id, subnet_id = self.create_openstack_network(subnet, network,
                                                          tenant_id,
                                                          tenant_name, direc)
        if not net_id or not subnet_id:
            return net_id, subnet_id
        self.allocate_seg_vlan(net_id, is_fw_virt, direc, tenant_id)
        self.update_subnet_db_info(tenant_id, direc, net_id, subnet_id)
        return net_id, subnet_id

    def _attach_dummy_intf_rtr(self, tenant_id, tenant_name, rtr_id):
        """Function to create a dummy router and interface. """
        serv_obj = self.get_service_obj(tenant_id)
        fw_dict = serv_obj.get_fw_dict()
        fw_id = fw_dict.get('fw_id')
        rtr_nwk = fw_id[0:4] + fw_const.DUMMY_SERVICE_NWK + (
            fw_id[len(fw_id) - 4:])
        net_id, subnet_id = self.os_helper.create_network(
            rtr_nwk, tenant_id, self.servicedummy_ip_subnet)
        if net_id is None or subnet_id is None:
            return None, None
        net_dict = {}
        net_dict['name'] = rtr_nwk
        self.store_net_db(tenant_id, net_id, net_dict, 'SUCCESS')
        subnet_lst = set()
        subnet_lst.add(subnet_id)
        if rtr_id is None:
            self.os_helper.delete_network(rtr_nwk, tenant_id, subnet_id,
                                          net_id)
            return None, None
        ret = self.os_helper.add_intf_router(rtr_id, tenant_id, subnet_lst)
        if not ret:
            self.os_helper.delete_network(rtr_nwk, tenant_id, subnet_id,
                                          net_id)
            return None, None
        return net_id, subnet_id

    def _delete_dummy_intf_rtr(self, tenant_id, tenant_name, rtr_id):
        """Function to delete a dummy interface of a router. """
        dummy_router_dict = self.get_dummy_router_net(tenant_id)
        ret = self.delete_os_dummy_rtr_nwk(dummy_router_dict.get('router_id'),
                                           dummy_router_dict.get('net_id'),
                                           dummy_router_dict.get('subnet_id'))
        # Release the network DB entry
        self.delete_network_db(dummy_router_dict.get('net_id'))
        return ret

    def create_os_in_nwk(self, tenant_id, fw_dict, is_fw_virt=False):
        """Create the Openstack IN network and stores the values in DB. """
        tenant_name = fw_dict.get('tenant_name')
        try:
            net, subnet = self._create_os_nwk(tenant_id, tenant_name, "in",
                                              is_fw_virt=is_fw_virt)
            if net is None or subnet is None:
                return False
        except Exception as exc:
            # If Openstack network creation fails, IP address is released.
            # Seg, VLAN creation happens only after network creation in
            # Openstack is successful.
            LOG.error(_LE("Creation of In Openstack Network failed tenant "
                      "%(tenant)s, Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            return False
        ret = fw_const.OS_IN_NETWORK_CREATE_SUCCESS
        net_dict = self.retrieve_dcnm_net_info(tenant_id, "in")
        subnet_dict = self.retrieve_dcnm_subnet_info(tenant_id, "in")
        # Very unlikely case, so nothing released.
        if not net_dict or not subnet_dict:
            LOG.error(_LE("Allocation of net,subnet failed Len net %(len_net)s"
                      "sub %(len_sub)s"),
                      {'len_net': len(net_dict), 'len_sub': len(subnet_dict)})
            ret = fw_const.OS_IN_NETWORK_CREATE_FAIL
        # Updating the FW and Nwk DB
        self.store_net_fw_db(tenant_id, net, net_dict, subnet_dict,
                             "in", 'SUCCESS', os_status=ret)
        return True

    def create_os_out_nwk(self, tenant_id, fw_dict, is_fw_virt=False):
        """Create the Openstack OUT network and stores the values in DB. """
        tenant_name = fw_dict.get('tenant_name')
        try:
            net, subnet = self._create_os_nwk(tenant_id, tenant_name, "out",
                                              is_fw_virt=is_fw_virt)
            if net is None or subnet is None:
                return False
        except Exception as exc:
            # If Openstack network creation fails, IP address is released.
            # Seg, VLAN creation happens only after network creation in
            # Openstack is successful.
            LOG.error(_LE("Creation of Out Openstack Network failed tenant "
                      "%(tenant)s, Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            return False
        ret = fw_const.OS_OUT_NETWORK_CREATE_SUCCESS
        net_dict = self.retrieve_dcnm_net_info(tenant_id, "out")
        subnet_dict = self.retrieve_dcnm_subnet_info(tenant_id, "out")
        # Very unlikely case, so nothing released.
        if not net_dict or not subnet_dict:
            LOG.error(_LE("Allocation of net,subnet failed len net %(len_net)s"
                      " %(len_sub)s"),
                      {'len_net': len(net_dict), 'len_sub': len(subnet_dict)})
            ret = fw_const.OS_OUT_NETWORK_CREATE_FAIL
        # Updating the FW and Nwk DB
        self.store_net_fw_db(tenant_id, net, net_dict, subnet_dict,
                             "out", 'SUCCESS', os_status=ret)
        return True

    def _delete_os_nwk(self, tenant_id, tenant_name, direc, is_fw_virt=False):
        """Delete the network created in Openstack.

        Function to delete Openstack network, It also releases the associated
        segmentation, VLAN and subnets.
        """
        serv_obj = self.get_service_obj(tenant_id)
        fw_dict = serv_obj.get_fw_dict()
        fw_id = fw_dict.get('fw_id')
        fw_data, fw_data_dict = self.get_fw(fw_id)
        if fw_data is None:
            LOG.error(_LE("Unable to get fw_data for tenant %s"), tenant_name)
            return False
        if direc == 'in':
            net_id = fw_data.in_network_id
            seg, vlan = self.get_in_seg_vlan(tenant_id)
            subnet_dict = self.get_in_ip_addr(tenant_id)
        else:
            net_id = fw_data.out_network_id
            seg, vlan = self.get_out_seg_vlan(tenant_id)
            subnet_dict = self.get_out_ip_addr(tenant_id)
        # Delete the Openstack Network
        sub = subnet_dict.get('subnet')
        try:
            ret = self.os_helper.delete_network_all_subnets(net_id)
            if not ret:
                LOG.error(_LE("Delete network for ID %(net)s direct %(dir)s "
                          "failed"), {'net': net_id, 'dir': direc})
                return False
        except Exception as exc:
            LOG.error(_LE("Delete network for ID %(net)s direct %(dir)s failed"
                      " Exc %(exc)s"),
                      {'net': net_id, 'dir': direc, 'exc': exc})
            return False

        # Release the segment, VLAN and subnet allocated
        if not is_fw_virt:
            self.service_vlans.release_segmentation_id(vlan)
        self.service_segs.release_segmentation_id(seg)
        self.release_subnet(sub, direc)
        # Release the network DB entry
        self.delete_network_db(net_id)
        return True

    def delete_os_in_nwk(self, tenant_id, fw_dict, is_fw_virt=False):
        """Deletes the Openstack In network and update the DB. """
        ret = True
        tenant_name = fw_dict.get('tenant_name')
        try:
            ret = self._delete_os_nwk(tenant_id, tenant_name, "in",
                                      is_fw_virt=is_fw_virt)
        except Exception as exc:
            LOG.error(_LE("Deletion of In Openstack Network failed tenant "
                      "%(tenant)s Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            ret = False
        # Updating the FW DB
        if ret:
            res = fw_const.OS_IN_NETWORK_DEL_SUCCESS
        else:
            res = fw_const.OS_IN_NETWORK_DEL_FAIL
        self.update_fw_db_result(tenant_id, os_status=res)
        return ret

    def delete_os_out_nwk(self, tenant_id, fw_dict, is_fw_virt=False):
        """Deletes the Openstack Out network and update the DB. """
        ret = True
        tenant_name = fw_dict.get('tenant_name')
        try:
            ret = self._delete_os_nwk(tenant_id, tenant_name, "out",
                                      is_fw_virt=is_fw_virt)
        except Exception as exc:
            LOG.error(_LE("Deletion of Out Openstack Network failed tenant "
                      "%(tenant)s, Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            ret = False
        # Updating the FW DB
        if ret:
            res = fw_const.OS_OUT_NETWORK_DEL_SUCCESS
        else:
            res = fw_const.OS_OUT_NETWORK_DEL_FAIL
        self.update_fw_db_result(tenant_id, os_status=res)
        return ret

    def create_os_dummy_rtr(self, tenant_id, fw_dict, is_fw_virt=False):
        """Create the dummy interface and attach it to router.

        Attach the dummy interface to the Openstack router and store the
        info in DB.
        """
        res = fw_const.OS_DUMMY_RTR_CREATE_SUCCESS
        tenant_name = fw_dict.get('tenant_name')
        try:
            rtr_id = fw_dict.get('router_id')
            if rtr_id is None:
                LOG.error(_LE("Invalid router id, attaching dummy interface"
                          " failed"))
                return False
            if is_fw_virt:
                net_id = subnet_id = None
            else:
                net_id, subnet_id = (
                    self._attach_dummy_intf_rtr(tenant_id, tenant_name,
                                                rtr_id))
                if net_id is None or subnet_id is None:
                    LOG.error(_LE("Invalid net_id or subnet_id, creating dummy"
                              " interface failed"))
                    return False
        except Exception as exc:
            # Function _attach_dummy_intf_rtr already took care of
            # cleanup for error cases.
            LOG.error(_LE("Creation of Openstack Router failed "
                      "tenant %(tenant)s, Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            res = fw_const.OS_DUMMY_RTR_CREATE_FAIL
        self.store_fw_db_router(tenant_id, net_id, subnet_id, rtr_id, res)
        return True

    def delete_os_dummy_rtr(self, tenant_id, fw_dict, is_fw_virt=False):
        """Delete the Openstack Dummy router and store the info in DB. """
        ret = True
        tenant_name = fw_dict.get('tenant_name')
        try:
            rtr_id = fw_dict.get('router_id')
            if not rtr_id:
                LOG.error(_LE("Invalid router id, deleting dummy interface"
                          " failed"))
                return False
            if not is_fw_virt:
                ret = self._delete_dummy_intf_rtr(tenant_id, tenant_name,
                                                  rtr_id)
        except Exception as exc:
            # Function _attach_dummy_intf_rtr already took care of
            # cleanup for error cases.
            LOG.error(_LE("Deletion of Openstack Router failed tenant "
                      "%(tenant)s, Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            ret = False
        if ret:
            res = fw_const.OS_DUMMY_RTR_DEL_SUCCESS
        else:
            res = fw_const.OS_DUMMY_RTR_DEL_FAIL
        self.update_fw_db_result(tenant_id, os_status=res)
        return ret

    def create_dcnm_in_nwk(self, tenant_id, fw_dict, is_fw_virt=False):
        """Create the DCNM In Network and store the result in DB. """
        tenant_name = fw_dict.get('tenant_name')
        ret = self._create_service_nwk(tenant_id, tenant_name, 'in')
        if ret:
            res = fw_const.DCNM_IN_NETWORK_CREATE_SUCCESS
            LOG.info(_LI("In Service network created for tenant %s"),
                     tenant_id)
        else:
            res = fw_const.DCNM_IN_NETWORK_CREATE_FAIL
            LOG.info(_LI("In Service network create failed for tenant %s"),
                     tenant_id)
        self.update_fw_db_result(tenant_id, dcnm_status=res)
        return ret

    def delete_dcnm_in_nwk(self, tenant_id, fw_dict, is_fw_virt=False):
        """Delete the DCNM In Network and store the result in DB. """
        tenant_name = fw_dict.get('tenant_name')
        ret = self._delete_service_nwk(tenant_id, tenant_name, 'in')
        if ret:
            res = fw_const.DCNM_IN_NETWORK_DEL_SUCCESS
            LOG.info(_LI("In Service network deleted for tenant %s"),
                     tenant_id)
        else:
            res = fw_const.DCNM_IN_NETWORK_DEL_FAIL
            LOG.info(_LI("In Service network deleted failed for tenant %s"),
                     tenant_id)
        self.update_fw_db_result(tenant_id, dcnm_status=res)
        return ret

    def update_dcnm_in_part(self, tenant_id, fw_dict, is_fw_virt=False):
        """Update DCNM's in partition information.

        Update the In partition service node IP address in DCNM and
        update the result
        """
        res = fw_const.DCNM_IN_PART_UPDATE_SUCCESS
        tenant_name = fw_dict.get('tenant_name')
        ret = True
        try:
            self._update_partition_in_create(tenant_id, tenant_name)
        except Exception as exc:
            LOG.error(_LE("Update of In Partition failed for tenant %(tenant)s"
                      " Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            res = fw_const.DCNM_IN_PART_UPDATE_FAIL
            ret = False
        self.update_fw_db_result(tenant_id, dcnm_status=res)
        LOG.info(_LI("In partition updated with service ip addr"))
        return ret

    def clear_dcnm_in_part(self, tenant_id, fw_dict, is_fw_virt=False):
        """Clear the DCNM in partition service information.

        Clear the In partition service node IP address in DCNM and update the
        result.
        """
        res = fw_const.DCNM_IN_PART_UPDDEL_SUCCESS
        tenant_name = fw_dict.get('tenant_name')
        ret = True
        try:
            self._update_partition_in_delete(tenant_name)
        except Exception as exc:
            LOG.error(_LE("Clear of In Partition failed for tenant %(tenant)s"
                      " , Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            res = fw_const.DCNM_IN_PART_UPDDEL_FAIL
            ret = False
        self.update_fw_db_result(tenant_id, dcnm_status=res)
        LOG.info(_LI("In partition cleared off service ip addr"))
        return ret

    def create_dcnm_out_part(self, tenant_id, fw_dict, is_fw_virt=False):
        """Create the DCNM OUT partition and update the result. """
        res = fw_const.DCNM_OUT_PART_CREATE_SUCCESS
        tenant_name = fw_dict.get('tenant_name')
        ret = True
        try:
            self._create_out_partition(tenant_id, tenant_name)
        except Exception as exc:
            LOG.error(_LE("Create of Out Partition failed for tenant "
                      "%(tenant)s ,Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            res = fw_const.DCNM_OUT_PART_CREATE_FAIL
            ret = False
        self.update_fw_db_result(tenant_id, dcnm_status=res)
        LOG.info(_LI("Out partition created"))
        return ret

    def delete_dcnm_out_part(self, tenant_id, fw_dict, is_fw_virt=False):
        """Delete the DCNM OUT partition and update the result. """
        res = fw_const.DCNM_OUT_PART_DEL_SUCCESS
        tenant_name = fw_dict.get('tenant_name')
        ret = True
        try:
            self._delete_partition(tenant_id, tenant_name)
        except Exception as exc:
            LOG.error(_LE("deletion of Out Partition failed for tenant "
                      "%(tenant)s, Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            res = fw_const.DCNM_OUT_PART_DEL_FAIL
            ret = False
        self.update_fw_db_result(tenant_id, dcnm_status=res)
        LOG.info(_LI("Out partition deleted"))
        return ret

    def create_dcnm_out_nwk(self, tenant_id, fw_dict, is_fw_virt=False):
        """Create the DCNM OUT Network and update the result. """
        tenant_name = fw_dict.get('tenant_name')
        ret = self._create_service_nwk(tenant_id, tenant_name, 'out')
        if ret:
            res = fw_const.DCNM_OUT_NETWORK_CREATE_SUCCESS
            LOG.info(_LI("out Service network created for tenant %s"),
                     tenant_id)
        else:
            res = fw_const.DCNM_OUT_NETWORK_CREATE_FAIL
            LOG.info(_LI("out Service network create failed for tenant %s"),
                     tenant_id)
        self.update_fw_db_result(tenant_id, dcnm_status=res)
        return ret

    def delete_dcnm_out_nwk(self, tenant_id, fw_dict, is_fw_virt=False):
        """Delete the DCNM OUT network and update the result. """
        tenant_name = fw_dict.get('tenant_name')
        ret = self._delete_service_nwk(tenant_id, tenant_name, 'out')
        if ret:
            res = fw_const.DCNM_OUT_NETWORK_DEL_SUCCESS
            LOG.info(_LI("out Service network deleted for tenant %s"),
                     tenant_id)
        else:
            res = fw_const.DCNM_OUT_NETWORK_DEL_FAIL
            LOG.info(_LI("out Service network deleted failed for tenant %s"),
                     tenant_id)
        self.update_fw_db_result(tenant_id, dcnm_status=res)
        return ret

    def update_dcnm_out_part(self, tenant_id, fw_dict, is_fw_virt=False):
        """Update DCNM OUT partition service node IP address and result. """
        res = fw_const.DCNM_OUT_PART_UPDATE_SUCCESS
        tenant_name = fw_dict.get('tenant_name')
        ret = True
        try:
            ret = self._update_partition_out_create(tenant_id, tenant_name)
            if not ret:
                res = fw_const.DCNM_OUT_PART_UPDATE_FAIL
        except Exception as exc:
            LOG.error(_LE("Update of Out Partition failed for tenant "
                      "%(tenant)s Exception %(exc)s"),
                      {'tenant': tenant_id, 'exc': str(exc)})
            res = fw_const.DCNM_OUT_PART_UPDATE_FAIL
            ret = False
        self.update_fw_db_result(tenant_id, dcnm_status=res)
        LOG.info(_LI("Out partition updated with service ip addr"))
        return ret

    def clear_dcnm_out_part(self, tenant_id, fw_dict, is_fw_virt=False):
        """Clear DCNM out partition information.

        Clear the DCNM OUT partition service node IP address and update
        the result
        """
        res = fw_const.DCNM_OUT_PART_UPDDEL_SUCCESS
        self.update_fw_db_result(tenant_id, dcnm_status=res)
        LOG.info(_LI("Out partition cleared -noop- with service ip addr"))
        return True

    def init_state(self, tenant_id, fw_dict, is_fw_virt=False):
        """Dummy function called at the init stage. """
        return True

    def prepare_fabric_done(self, tenant_id, tenant_name, is_fw_virt=False):
        """Dummy function called at the final stage. """
        return True

    def get_next_create_state(self, state, ret):
        """Return the next create state from previous state. """
        if ret:
            if state == fw_const.FABRIC_PREPARE_DONE_STATE:
                return state
            else:
                return state + 1
        else:
            return state

    def get_next_del_state(self, state, ret):
        """Return the next delete state from previous state. """
        if ret:
            if state == fw_const.INIT_STATE:
                return state
            else:
                return state - 1
        else:
            return state

    def get_next_state(self, state, ret, oper):
        """Returns the next state for a create or delete operation. """
        if oper == fw_const.FW_CR_OP:
            return self.get_next_create_state(state, ret)
        else:
            return self.get_next_del_state(state, ret)

    def run_create_sm(self, tenant_id, fw_dict, is_fw_virt):
        """Runs the create State Machine.

        Goes through every state function until the end or when one state
        returns failure.
        """
        ret = True
        serv_obj = self.get_service_obj(tenant_id)
        state = serv_obj.get_state()
        # Preserve the ordering of the next lines till while
        new_state = serv_obj.fixup_state(fw_const.FW_CR_OP, state)
        serv_obj.store_local_final_result(fw_const.RESULT_FW_CREATE_INIT)
        if state != new_state:
            state = new_state
            serv_obj.store_state(state)
        while ret:
            try:
                ret = self.fabric_fsm[state][0](tenant_id, fw_dict,
                                                is_fw_virt=is_fw_virt)
            except Exception as exc:
                LOG.error(_LE("Exception %(exc)s for state %(state)s"),
                          {'exc': str(exc), 'state':
                           fw_const.fw_state_fn_dict.get(state)})
                ret = False
            if ret:
                LOG.info(_LI("State %s return successfully"),
                         fw_const.fw_state_fn_dict.get(state))
            state = self.get_next_state(state, ret, fw_const.FW_CR_OP)
            serv_obj.store_state(state)
            if state == fw_const.FABRIC_PREPARE_DONE_STATE:
                break
        if ret:
            serv_obj.store_local_final_result(fw_const.RESULT_FW_CREATE_DONE)
        return ret

    def run_delete_sm(self, tenant_id, fw_dict, is_fw_virt):
        """Runs the delete State Machine.

        Goes through every state function until the end or when one state
        returns failure.
        """
        # Read the current state from the DB
        ret = True
        serv_obj = self.get_service_obj(tenant_id)
        state = serv_obj.get_state()
        # Preserve the ordering of the next lines till while
        new_state = serv_obj.fixup_state(fw_const.FW_DEL_OP, state)
        serv_obj.store_local_final_result(fw_const.RESULT_FW_DELETE_INIT)
        if state != new_state:
            state = new_state
            serv_obj.store_state(state)
        while ret:
            try:
                ret = self.fabric_fsm[state][1](tenant_id, fw_dict,
                                                is_fw_virt=is_fw_virt)
            except Exception as exc:
                LOG.error(_LE("Exception %(exc)s for state %(state)s"),
                          {'exc': str(exc), 'state':
                           fw_const.fw_state_fn_del_dict.get(state)})
                ret = False
            if ret:
                LOG.info(_LI("State %s return successfully"),
                         fw_const.fw_state_fn_del_dict.get(state))
            if state == fw_const.INIT_STATE:
                break
            state = self.get_next_state(state, ret, fw_const.FW_DEL_OP)
            serv_obj.store_state(state)
        return ret

    def get_key_state(self, status, state_dict):
        """Returns the key associated with the dict. """
        for key, val in state_dict.items():
            if val == status:
                return key

    def pop_fw_state(self, compl_result, os_status, dcnm_status):
        """Populate the state information in the cache.

        Check if state information is embedded in result
        If not:
        a. It's still in Init state and no SM is called yet
        b. The SM has completely run
        c. Delete has started and before any SM is run, it restarted.
        """
        res_list = compl_result.split('(')
        state_num = None
        if len(res_list) > 1:
            state_num = int(res_list[1].split(')')[0])
        else:
            if res_list[0] == fw_const.RESULT_FW_CREATE_INIT:
                if os_status is None:
                    state_num = fw_const.INIT_STATE
            elif res_list[0] == fw_const.RESULT_FW_CREATE_DONE:
                state_num = fw_const.FABRIC_PREPARE_DONE_STATE
            elif res_list[0] == fw_const.RESULT_FW_DELETE_INIT:
                if os_status == fw_const.OS_CREATE_SUCCESS and (
                   dcnm_status == fw_const.DCNM_CREATE_SUCCESS):
                    state_num = fw_const.FABRIC_PREPARE_DONE_STATE
        return state_num

    def pop_fw_local(self, tenant_id, net_id, direc, node_ip):
        """Populate the local cache.

        Read the Network DB and populate the local cache.
        Read the subnet from the Subnet DB, given the net_id and populate the
        cache.
        """
        net = self.get_network(net_id)
        serv_obj = self.get_service_obj(tenant_id)
        serv_obj.update_fw_local_cache(net_id, direc, node_ip)
        if net is not None:
            net_dict = self.fill_dcnm_net_info(tenant_id, direc, net.vlan,
                                               net.segmentation_id)
            serv_obj.store_dcnm_net_dict(net_dict, direc)
        if direc == "in":
            subnet = self.service_in_ip.get_subnet_by_netid(net_id)
        else:
            subnet = self.service_out_ip.get_subnet_by_netid(net_id)
        if subnet is not None:
            subnet_dict = self.fill_dcnm_subnet_info(
                tenant_id, subnet,
                self.get_start_ip(subnet), self.get_end_ip(subnet),
                self.get_gateway(subnet), self.get_secondary_gateway(subnet),
                direc)
            serv_obj.store_dcnm_subnet_dict(subnet_dict, direc)

    # Tested for 1 FW
    def populate_local_cache_tenant(self, fw_id, fw_data):
        """Populate the cache for a given tenant.

        Calls routines to Populate the in and out information.
        Update the result information.
        Populate the state information.
        Populate the router information.
        """
        tenant_id = fw_data.get('tenant_id')
        self.create_serv_obj(tenant_id)
        serv_obj = self.get_service_obj(tenant_id)
        serv_obj.create_fw_db(fw_id, fw_data.get('name'), tenant_id)
        self.pop_fw_local(tenant_id, fw_data.get('in_network_id'), "in",
                          fw_data.get('in_service_node_ip'))
        self.pop_fw_local(tenant_id, fw_data.get('out_network_id'), "out",
                          fw_data.get('out_service_node_ip'))
        serv_obj.update_fw_local_result_str(fw_data.get('os_status'),
                                            fw_data.get('dcnm_status'),
                                            fw_data.get('device_status'))
        compl_res = fw_data.get('result')
        result = compl_res.split('(')[0]
        serv_obj.store_local_final_result(result)
        state = self.pop_fw_state(compl_res, fw_data.get('os_status'),
                                  fw_data.get('dcnm_status'))
        if state is None:
            LOG.error(_LE("Unable to get state complete result %(res)s"
                      " OS status %(os)s, dcnm status %(dcnm)s"),
                      {'res': compl_res, 'os': fw_data.get('os_status'),
                       'dcnm': fw_data.get('dcnm_status')})
        serv_obj.store_state(state, popl_db=False)
        if state == fw_const.FABRIC_PREPARE_DONE_STATE:
            serv_obj.set_fabric_create(True)
        router_id = fw_data.get('router_id')
        rout_net_id = fw_data.get('router_net_id')
        rout_subnet_id = fw_data.get('router_subnet_id')
        # Result is already populated above, so pass None below.
        # And, the result passed should be a string
        serv_obj.update_fw_local_router(rout_net_id, rout_subnet_id, router_id,
                                        None)

    def populate_local_cache(self):
        """Populate the local cache from DB.

        Read the entries from FW DB and Calls routines to populate the cache.
        """
        fw_dict = self.get_all_fw_db()
        for fw_id in fw_dict:
            LOG.info(_LI("Populating cache for FW %s"), fw_id)
            fw_data = fw_dict[fw_id]
            self.populate_local_cache_tenant(fw_id, fw_data)

    def delete_os_dummy_rtr_nwk(self, rtr_id, net_id, subnet_id):
        """Delete the dummy interface to the router.  """
        subnet_lst = set()
        subnet_lst.add(subnet_id)
        ret = self.os_helper.delete_intf_router(None, None, rtr_id, subnet_lst)
        if not ret:
            return ret
        return self.os_helper.delete_network_all_subnets(net_id)

    def delete_os_nwk_db(self, net_id, seg, vlan):
        """Delete the Openstack Network from the database.

        Release the segmentation ID, VLAN associated with the net.
        Delete the network given the partial name.
        Delete the entry from Network DB, given the net ID.
        Delete the entry from Firewall DB, given the net ID.
        Release the IN/OUT sug=bnets associated with the net.
        """
        if seg is not None:
            self.service_segs.release_segmentation_id(seg)
        if vlan is not None:
            self.service_vlans.release_segmentation_id(vlan)
        self.os_helper.delete_network_all_subnets(net_id)
        # There's a chance that OS network got created but it's ID
        # was not put in DB
        # So, deleting networks in os that has part of the special
        # name
        self.os_helper.delete_network_subname(fw_const.IN_SERVICE_NWK)
        self.delete_network_db(net_id)
        self.clear_fw_entry_by_netid(net_id)
        self.service_in_ip.release_subnet_by_netid(net_id)
        self.service_out_ip.release_subnet_by_netid(net_id)

    # Tested for positive case, no delete happened
    def correct_db_restart(self):
        """Ensure DB is consistent after unexpected restarts. """
        LOG.info(_LI("Checking consistency of DB"))
        # Any Segments allocated that's not in Network or FW DB, release it
        seg_netid_dict = self.service_segs.get_seg_netid_src(fw_const.FW_CONST)
        vlan_netid_dict = self.service_vlans.get_seg_netid_src(
            fw_const.FW_CONST)
        for netid in seg_netid_dict:
            net = self.get_network(netid)
            fw_net = self.get_fw_by_netid(netid)
            if not net or not fw_net:
                if netid in vlan_netid_dict:
                    vlan_net = vlan_netid_dict[netid]
                else:
                    vlan_net = None
                self.delete_os_nwk_db(netid, seg_netid_dict[netid], vlan_net)
                LOG.info(_LI("Allocated segment for net %s not in DB "
                         "returning"), net)
                return
        # Any VLANs allocated that's not in Network or FW DB, release it
        # For Virtual case, this list will be empty
        for netid in vlan_netid_dict:
            net = self.get_network(netid)
            fw_net = self.get_fw_by_netid(netid)
            if not net or not fw_net:
                if netid in seg_netid_dict:
                    vlan_net = seg_netid_dict[netid]
                else:
                    vlan_net = None
                self.delete_os_nwk_db(netid, vlan_net, vlan_netid_dict[netid])
                LOG.info(_LI("Allocated vlan for net %s not in DB returning"),
                         net)
                return
        # Release all IP's from DB that has no NetID or SubnetID
        self.service_in_ip.release_subnet_no_netid()
        self.service_out_ip.release_subnet_no_netid()
        # It leaves out following possibilities not covered by above.
        # 1. Crash can happen just after creating FWID in DB (for init state)
        # 2. Crash can happen after 1 + IP address allocation
        # 3. Crash can happen after 2 + create OS network
        # IP address allocated will be freed as above.
        # Only OS network will remain for case 3.
        # Also, create that FW DB entry only if that FWID didn't exist.

        # Delete all dummy networks created for dummy router from OS if it's
        # ID is not in NetDB
        # Delete all dummy routers and its associated networks/subnetfrom OS
        # if it's ID is not in FWDB
        fw_dict = self.get_all_fw_db()
        for fw_id in fw_dict:
            rtr_nwk = fw_id[0:4] + fw_const.DUMMY_SERVICE_NWK + (
                fw_id[len(fw_id) - 4:])
            net_list = self.os_helper.get_network_by_name(rtr_nwk)
            # TODO(padkrish) Come back to finish this. Not sure of this.
            # The router interface should be deleted first and then the network
            # Try using show_router
            for net in net_list:
                # Check for if it's there in NetDB
                net_db_item = self.get_network(net.get('id'))
                if not net_db_item:
                    self.os_helper.delete_network_all_subnets(net.get('id'))
                    LOG.info(_LI("Router Network %s not in DB, returning"),
                             net.get('id'))
                    return
            rtr_name = fw_id[0:4] + fw_const.DUMMY_SERVICE_RTR + (
                fw_id[len(fw_id) - 4:])
            rtr_list = self.os_helper.get_rtr_by_name(rtr_name)
            for rtr in rtr_list:
                fw_db_item = self.get_fw_by_rtrid(rtr.get('id'))
                if not fw_db_item:
                    # There should be only one
                    if not net_list:
                        LOG.error(_LE("net_list len is 0, router net not "
                                  "found"))
                        return
                    fw_type = fw_dict[fw_id].get('fw_type')
                    if fw_type == fw_const.FW_TENANT_EDGE:
                        rtr_net = net_list[0]
                        rtr_subnet_lt = (
                            self.os_helper.get_subnets_for_net(rtr_net))
                        if rtr_subnet_lt is None:
                            LOG.error(_LE("router subnet not found for "
                                      "net %s"), rtr_net)
                            return
                        rtr_subnet_id = rtr_subnet_lt[0].get('id')
                        LOG.info(_LI("Deleted dummy router network %s"),
                                 rtr.get('id'))
                        ret = self.delete_os_dummy_rtr_nwk(rtr.get('id'),
                                                           rtr_net.get('id'),
                                                           rtr_subnet_id)
                        return ret
        LOG.info(_LI("Done Checking consistency of DB, no issues"))
        # TODO(padkrish) Read the Service NWK creation status in DCNM.
        # If it does not match with FW DB DCNM status, update it
        # Do the same for partition as well.
        # TODO(padkrish)  go through the algo for delete SM as well.

    def _prepare_fabric_fw_internal(self, tenant_id, fw_dict, is_fw_virt,
                                    result):
        """Internal routine to prepare the fabric.

        This creates an entry in FW DB and runs the SM.
        """
        if not self.auto_nwk_create:
            LOG.info(_LI("Auto network creation disabled"))
            return False
        try:
            tenant_name = fw_dict.get('tenant_name')
            fw_id = fw_dict.get('fw_id')
            fw_name = fw_dict.get('fw_name')
            # TODO(padkrish) More than 1 FW per tenant not supported.
            if tenant_id in self.service_attr and (
               result == fw_const.RESULT_FW_CREATE_DONE):
                LOG.error(_LE("Fabric already prepared for tenant %(tenant)s,"
                          " %(name)s"),
                          {'tenant': tenant_id, 'name': tenant_name})
                return True
            if tenant_id not in self.service_attr:
                self.create_serv_obj(tenant_id)
            self.service_attr[tenant_id].create_fw_db(fw_id, fw_name,
                                                      tenant_id)
            ret = self.run_create_sm(tenant_id, fw_dict, is_fw_virt)
            if ret:
                LOG.info(_LI("SM create returned True for Tenant Name "
                         "%(tenant)s FW %(fw)s"),
                         {'tenant': tenant_name, 'fw': fw_name})
                self.service_attr[tenant_id].set_fabric_create(True)
            else:
                LOG.error(_LE("SM create returned False for Tenant Name "
                          "%(tenant)s FW %(fw)s"),
                          {'tenant': tenant_name, 'fw': fw_name})
        except Exception as exc:
            LOG.error(_LE("Exception raised in create fabric int %s"),
                      str(exc))
            return False
        return ret

    def prepare_fabric_fw(self, tenant_id, fw_dict, is_fw_virt, result):
        """Top level routine to prepare the fabric. """
        try:
            with self.mutex_lock:
                ret = self._prepare_fabric_fw_internal(tenant_id, fw_dict,
                                                       is_fw_virt, result)
        except Exception as exc:
            LOG.error(_LE("Exception raised in create fabric %s"), str(exc))
            return False
        return ret

    def delete_fabric_fw_internal(self, tenant_id, fw_dict, is_fw_virt,
                                  result):
        """Internal routine to delete the fabric configuration.

        This runs the SM and deletes the entries from DB and local cache.
        """
        if not self.auto_nwk_create:
            LOG.info(_LI("Auto network creation disabled"))
            return False
        try:
            tenant_name = fw_dict.get('tenant_name')
            fw_name = fw_dict.get('fw_name')
            if tenant_id not in self.service_attr:
                LOG.error(_LE("Service obj not created for tenant %s"),
                          tenant_name)
                return False
            # A check for is_fabric_create is not needed since a delete
            # may be issued even when create is not completely done.
            # For example, some state such as create stuff in DCNM failed and
            # SM for create is in the process of retrying. A delete can be
            # issue at that time. If we have a check for is_fabric_create
            # then delete operation will not go through.
            if result == fw_const.RESULT_FW_DELETE_DONE:
                LOG.error(_LE("Fabric for tenant %s already deleted"),
                          tenant_id)
                return True
            ret = self.run_delete_sm(tenant_id, fw_dict, is_fw_virt)
            self.service_attr[tenant_id].set_fabric_create(False)
            if ret:
                LOG.info(_LI("Delete SM completed successfully for tenant"
                         "%(tenant)s FW %(fw)s"),
                         {'tenant': tenant_name, 'fw': fw_name})
                self.service_attr[tenant_id].destroy_local_fw_db()
                self.delete_serv_obj(tenant_id)
            else:
                LOG.error(_LE("Delete SM failed for tenant"
                          "%(tenant)s FW %(fw)s"),
                          {'tenant': tenant_name, 'fw': fw_name})
            # TODO(padkrish) Equivalent of create_fw_db for delete.
        except Exception as exc:
            LOG.error(_LE("Exception raised in delete fabric int %s"),
                      str(exc))
            return False
        return ret

    def delete_fabric_fw(self, tenant_id, fw_dict, is_fw_virt, result):
        """Top level routine to unconfigure the fabric. """
        try:
            with self.mutex_lock:
                ret = self.delete_fabric_fw_internal(tenant_id, fw_dict,
                                                     is_fw_virt, result)
        except Exception as exc:
            LOG.error(_LE("Exception raised in delete fabric %s"), str(exc))
            return False
        return ret

    def retry_failure_internal(self, tenant_id, tenant_name, fw_data,
                               is_fw_virt, result):
        """Internal routine to retry the failed cases. """
        if not self.auto_nwk_create:
            LOG.info(_LI("Auto network creation disabled"))
            return False
        try:
            # TODO(padkrish) More than 1 FW per tenant not supported
            if tenant_id not in self.service_attr:
                LOG.error(_LE("Tenant Obj not created"))
                return False
            if result == fw_const.RESULT_FW_CREATE_INIT:
                # A check for is_fabric_create is not done here.
                ret = self.run_create_sm(tenant_id, fw_data, is_fw_virt)
            else:
                if result == fw_const.RESULT_FW_DELETE_INIT:
                    # A check for is_fabric_create is not done here.
                    # Pls check the comment given in function
                    # delete_fabric_fw_int
                    ret = self.run_delete_sm(tenant_id, fw_data, is_fw_virt)
                else:
                    LOG.error(_LE("Unknown state in retry"))
                    return False
            self.service_attr[tenant_id].set_fabric_create(ret)
        except Exception as exc:
            LOG.error(_LE("Exception raised in create fabric int %s"),
                      str(exc))
            return False
        return ret

    def retry_failure(self, tenant_id, tenant_name, fw_data, is_fw_virt,
                      result):
        """Top level retry failure routine. """
        try:
            with self.mutex_lock:
                ret = self.retry_failure_internal(tenant_id, tenant_name,
                                                  fw_data, is_fw_virt, result)
        except Exception as exc:
            LOG.error(_LE("Exception raised in create fabric %s"), str(exc))
            return False
        return ret
