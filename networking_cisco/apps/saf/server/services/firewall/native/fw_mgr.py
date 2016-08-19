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

from functools import wraps

from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import utils as sys_utils
from networking_cisco.apps.saf.db import dfa_db_models as dfa_dbm
from networking_cisco.apps.saf.server import dfa_openstack_helper as OsHelper
from networking_cisco.apps.saf.server.services.firewall.native import (
    fabric_setup_base as fabric)
from networking_cisco.apps.saf.server.services.firewall.native import (
    fw_constants)
from networking_cisco.apps.saf.server.services.firewall.native.drivers import (
    dev_mgr)

from networking_cisco._i18n import _LE, _LI

LOG = logging.getLogger(__name__)


class FwTenant(object):

    """Class to hold Tenant specific attributes.

    This class maintains a mapping of rule, policies, FW IDs with its
    associated tenant ID.
    It's assumed that a Rule, policy or FW signified by their unique ID can
    only be associated with one Tenant.
    """

    def __init__(self):
        """Initialize. """
        self.rule_tenant_dict = {}
        self.policy_tenant_dict = {}
        self.fw_tenant_dict = {}

    def store_rule_tenant(self, rule_id, tenant_id):
        """Stores the tenant ID corresponding to the rule. """
        self.rule_tenant_dict[rule_id] = tenant_id

    def get_rule_tenant(self, rule_id):
        """Retrieves the tenant ID corresponding to the rule. """
        return self.rule_tenant_dict[rule_id]

    def store_policy_tenant(self, policy_id, tenant_id):
        """Stores the tenant ID corresponding to the policy. """
        self.policy_tenant_dict[policy_id] = tenant_id

    def get_policy_tenant(self, policy_id):
        """Retrieves the tenant ID corresponding to the policy. """
        return self.policy_tenant_dict[policy_id]

    def store_fw_tenant(self, fw_id, tenant_id):
        """Stores the tenant ID corresponding to the firewall. """
        self.fw_tenant_dict[fw_id] = tenant_id

    def get_fw_tenant(self, fw_id):
        """Retrieves the tenant ID corresponding to the firewall. """
        return self.fw_tenant_dict[fw_id]

    def del_fw_tenant(self, fw_id):
        """Deletes the FW Tenant mapping. """
        del self.fw_tenant_dict[fw_id]

    def del_policy_tenant(self, pol_id):
        """Deletes the Tenant policy mapping. """
        del self.policy_tenant_dict[pol_id]

    def del_rule_tenant(self, rule_id):
        """Deletes the Tenant policy mapping. """
        del self.rule_tenant_dict[rule_id]


class FwMapAttr(object):

    """Firewall Attributes. This class is instantiated per tenant. """

    def __init__(self, tenant_id):
        """Initialize. """
        self.rules = {}
        self.policies = {}
        self.tenant_id = tenant_id
        self.rule_cnt = 0
        self.policy_cnt = 0
        self.active_pol_id = None
        self.fw_created = False
        self.fw_drvr_status = False
        self.fw_id = None
        self.fw_type = None
        self.tenant_name = None
        self.fw_name = None
        self.mutex_lock = sys_utils.lock()

    def store_policy(self, pol_id, policy):
        """Store the policy.

        Policy is maintained as a dictionary of pol ID.
        """
        if pol_id not in self.policies:
            self.policies[pol_id] = policy
            self.policy_cnt += 1

    def store_rule(self, rule_id, rule):
        """Store the rules.

        Policy is maintained as a dictionary of Rule ID.
        """
        if rule_id not in self.rules:
            self.rules[rule_id] = rule
            self.rule_cnt += 1

    def delete_rule(self, rule_id):
        """Delete the specific Rule from dictionary indexed by rule id. """
        if rule_id not in self.rules:
            LOG.error(_LE("No Rule id present for deleting %s"), rule_id)
            return
        del self.rules[rule_id]
        self.rule_cnt -= 1
        # No need to navigate through self.policies to delete rules since
        # if a rule is a part of a policy, Openstack would not allow to delete
        # that rule

    def is_rule_present(self, rule_id):
        """Returns if rule specified by rule id is present in dictionary. """
        if rule_id not in self.rules:
            return False
        else:
            return True

    def rule_update(self, rule_id, rule):
        """Update the rule. """
        if rule_id not in self.rules:
            LOG.error(_LE("Rule ID not present %s"), rule_id)
            return
        self.rules[rule_id].update(rule)

    def is_policy_present(self, pol_id):
        """Returns if policy specified by ID is present in the dictionary. """
        return pol_id in self.policies

    def is_fw_present(self, fw_id):
        """Returns if firewall index by ID is present in dictionary. """
        if self.fw_id is None or self.fw_id != fw_id:
            return False
        else:
            return True

    def create_fw(self, proj_name, pol_id, fw_id, fw_name, fw_type, rtr_id):
        """Fills up the local attributes when FW is created. """
        self.tenant_name = proj_name
        self.fw_id = fw_id
        self.fw_name = fw_name
        self.fw_created = True
        self.active_pol_id = pol_id
        self.fw_type = fw_type
        self.router_id = rtr_id

    def delete_fw(self, fw_id):
        """Deletes the FW local attributes. """
        self.fw_id = None
        self.fw_name = None
        self.fw_created = False
        self.active_pol_id = None

    def delete_policy(self, pol_id):
        """Deletes the policy from the local dictionary. """
        if pol_id not in self.policies:
            LOG.error(_LE("Invalid policy %s"), pol_id)
            return
        del self.policies[pol_id]
        self.policy_cnt -= 1

    def is_fw_complete(self):
        """This API returns the completion status of FW.

        This returns True if a FW is created with a active policy that has
        more than one rule associated with it and if a driver init is done
        successfully.
        """
        LOG.info(_LI("In fw_complete needed %(fw_created)s "
                     "%(active_policy_id)s %(is_fw_drvr_created)s "
                     "%(pol_present)s %(fw_type)s"),
                 {'fw_created': self.fw_created,
                  'active_policy_id': self.active_pol_id,
                  'is_fw_drvr_created': self.is_fw_drvr_created(),
                  'pol_present': self.active_pol_id in self.policies,
                  'fw_type': self.fw_type})
        if self.active_pol_id is not None:
            LOG.info(_LI("In Drvr create needed %(len_policy)s %(one_rule)s"),
                     {'len_policy':
                      len(self.policies[self.active_pol_id]['rule_dict']),
                      'one_rule':
                      self.one_rule_present(self.active_pol_id)})
        return self.fw_created and self.active_pol_id and (
            self.is_fw_drvr_created()) and self.fw_type and (
            self.active_pol_id in self.policies) and (
            len(self.policies[self.active_pol_id]['rule_dict'])) > 0 and (
            self.one_rule_present(self.active_pol_id))

    def is_fw_drvr_create_needed(self):
        """This API returns True if a driver init needs to be performed.

        This returns True if a FW is created with a active policy that has
        more than one rule associated with it and if a driver init is NOT
        done.
        """
        LOG.info(_LI("In Drvr create needed %(fw_created)s "
                     "%(active_policy_id)s"
                     " %(is_fw_drvr_created)s %(pol_present)s %(fw_type)s"),
                 {'fw_created': self.fw_created,
                  'active_policy_id': self.active_pol_id,
                  'is_fw_drvr_created': self.is_fw_drvr_created(),
                  'pol_present': self.active_pol_id in self.policies,
                  'fw_type': self.fw_type})
        if self.active_pol_id is not None and (
           self.active_pol_id in self.policies):
            LOG.info(_LI("In Drvr create needed %(len_policy)s %(one_rule)s"),
                     {'len_policy':
                      len(self.policies[self.active_pol_id]['rule_dict']),
                      'one_rule':
                      self.one_rule_present(self.active_pol_id)})
        return self.fw_created and self.active_pol_id and (
            not self.is_fw_drvr_created()) and self.fw_type and (
            self.active_pol_id in self.policies) and (
            len(self.policies[self.active_pol_id]['rule_dict'])) > 0 and (
            self.one_rule_present(self.active_pol_id))

    def one_rule_present(self, pol_id):
        """Returns if atleast one rule is present in the policy. """
        pol_dict = self.policies[pol_id]
        for rule in pol_dict['rule_dict']:
            if self.is_rule_present(rule):
                return True
        return False

    def fw_drvr_created(self, status):
        """This stores the status of the driver init.

        This API assumes only one FW driver.
        """
        self.fw_drvr_status = status

    def is_fw_drvr_created(self):
        """This returns the status of the driver creation.

        This API assumes only one FW driver.
        """
        return self.fw_drvr_status

    def get_fw_dict(self):
        """This API creates a FW dictionary from the local attributes. """
        fw_dict = {}
        if self.fw_id is None:
            return fw_dict
        fw_dict = {'rules': {}, 'tenant_name': self.tenant_name,
                   'tenant_id': self.tenant_id, 'fw_id': self.fw_id,
                   'fw_name': self.fw_name,
                   'firewall_policy_id': self.active_pol_id,
                   'fw_type': self.fw_type, 'router_id': self.router_id}
        # When Firewall and Policy are both deleted and the SM is doing a
        # retry (maybe DCNM Out partition could not be deleted) during
        # which without this check, it throws an exception since
        # self.policies is empty. This is also an issue during restart.
        if self.active_pol_id not in self.policies:
            return fw_dict
        pol_dict = self.policies[self.active_pol_id]
        for rule in pol_dict['rule_dict']:
            fw_dict['rules'][rule] = self.rules[rule]
        return fw_dict

    def update_fw_params(self, rtr_id=-1, fw_type=-1):
        """Updates the FW parameters. """
        if rtr_id != -1:
            self.router_id = rtr_id
        if fw_type != -1:
            self.fw_type = fw_type


class FwMgr(dev_mgr.DeviceMgr):

    """Firewall Native Manager"""

    def __init__(self, cfg):
        """Initialization routine.

        It populates the local cache after reading the DB. It initializes the
        Fabric class and DeviceMgr class.
        """
        LOG.debug("Initializing Native FW Manager %s", cfg.firewall.device)
        self.fw_init = False
        if cfg.firewall.device is None or cfg.firewall.device is '':
            return
        super(FwMgr, self).__init__(cfg)
        self.events.update({
            'firewall_rule.create.end': self.fw_rule_create,
            'firewall_rule.delete.end': self.fw_rule_delete,
            'firewall_rule.update.end': self.fw_rule_update,
            'firewall_policy.create.end': self.fw_policy_create,
            'firewall_policy.delete.end': self.fw_policy_delete,
            'firewall.create.end': self.fw_create,
            'firewall.update.end': self.fw_update,
            'firewall.delete.end': self.fw_delete})
        self.fwid_attr = {}
        self.pid_dict = {}
        self.rules_id = {}
        self.fw_drvr_created = False
        self.fabric = fabric.FabricBase()
        self.tenant_db = FwTenant()
        self.os_helper = OsHelper.DfaNeutronHelper()
        fw_dict = self.populate_local_cache()
        self.populate_local_sch_cache(fw_dict)
        self.dcnm_obj = None
        self.fw_init = True

    def populate_cfg_dcnm(self, cfg, dcnm_obj):
        """This routine stores the DCNM object. """
        if not self.fw_init:
            return
        self.dcnm_obj = dcnm_obj
        self.fabric.store_dcnm(dcnm_obj)
        self.populate_dcnm_obj(dcnm_obj)

    def populate_event_queue(self, cfg, que_obj):
        """This routine is for storing the Event Queue obj. """
        if not self.fw_init:
            return
        self.que_obj = que_obj
        self.populate_event_que(que_obj)

    def network_sub_create_notif(self, tenant_id, tenant_name, cidr):
        """Network create notification. """
        if not self.fw_init:
            return
        self.network_create_notif(tenant_id, tenant_name, cidr)

    def network_del_notif(self, tenant_id, tenant_name, net_id):
        """Network delete notification. """
        if not self.fw_init:
            return
        self.network_delete_notif(tenant_id, tenant_name, net_id)

    def project_create_notif(self, tenant_id, tenant_name):
        """Tenant Create notification. """
        if not self.fw_init:
            return
        self.os_helper.create_router('_'.join([fw_constants.TENANT_EDGE_RTR,
                                               tenant_name]),
                                     tenant_id, [])

    def project_delete_notif(self, tenant_id, tenant_name):
        """Tenant Delete notification. """
        if not self.fw_init:
            return
        rtr_name = '_'.join([fw_constants.TENANT_EDGE_RTR, tenant_name])
        self.os_helper.delete_router_by_name(rtr_name, tenant_id)

    def _create_fw_fab_dev_te(self, tenant_id, drvr_name, fw_dict):
        """Prepares the Fabric and configures the device.

        This routine calls the fabric class to prepare the fabric when
        a firewall is created. It also calls the device manager to
        configure the device. It updates the database with the final
        result.
        """
        is_fw_virt = self.is_device_virtual()
        ret = self.fabric.prepare_fabric_fw(tenant_id, fw_dict, is_fw_virt,
                                            fw_constants.RESULT_FW_CREATE_INIT)

        if not ret:
            LOG.error(_LE("Prepare Fabric failed"))
            return
        else:
            self.update_fw_db_final_result(fw_dict.get('fw_id'), (
                fw_constants.RESULT_FW_CREATE_DONE))
        ret = self.create_fw_device(tenant_id, fw_dict.get('fw_id'),
                                    fw_dict)
        if ret:
            self.fwid_attr[tenant_id].fw_drvr_created(True)
            self.update_fw_db_dev_status(fw_dict.get('fw_id'), 'SUCCESS')
            LOG.info(_LI("FW device create returned success for tenant %s"),
                     tenant_id)
        else:
            LOG.error(_LE("FW device create returned failure for tenant %s"),
                      tenant_id)

    def _create_fw_fab_dev(self, tenant_id, drvr_name, fw_dict):
        """This routine calls the Tenant Edge routine if FW Type is TE. """
        if fw_dict.get('fw_type') == fw_constants.FW_TENANT_EDGE:
            self._create_fw_fab_dev_te(tenant_id, drvr_name, fw_dict)

    def _check_create_fw(self, tenant_id, drvr_name):
        """Creates the Firewall, if all conditions are met.

        This function first checks if all the configuration are done
        for a FW to be launched. After that it creates the FW entry in the
        DB. After that, it calls the routine to prepare the fabric and
        configure the device.
        """
        if self.fwid_attr[tenant_id].is_fw_drvr_create_needed():
            fw_dict = self.fwid_attr[tenant_id].get_fw_dict()
            try:
                with self.fwid_attr[tenant_id].mutex_lock:
                    ret = self.add_fw_db(fw_dict.get('fw_id'), fw_dict,
                                         fw_constants.RESULT_FW_CREATE_INIT)
                    if not ret:
                        LOG.error(_LE("Adding FW DB failed for tenant %s"),
                                  tenant_id)
                        return
                    self._create_fw_fab_dev(tenant_id, drvr_name, fw_dict)
            except Exception as exc:
                LOG.error(_LE("Exception raised in create fw %s"), str(exc))

    def _delete_fw_fab_dev(self, tenant_id, drvr_name, fw_dict):
        """Deletes the Firewall.

        This routine calls the fabric class to delete the fabric when
        a firewall is deleted. It also calls the device manager to
        unconfigure the device. It updates the database with the final
        result.
        """
        is_fw_virt = self.is_device_virtual()
        if self.fwid_attr[tenant_id].is_fw_drvr_created():
            ret = self.delete_fw_device(tenant_id, fw_dict.get('fw_id'),
                                        fw_dict)
            if not ret:
                LOG.error(_LE("Error in delete_fabric_fw device for tenant "
                          "%s"), tenant_id)
                return False
            else:
                self.fwid_attr[tenant_id].fw_drvr_created(False)
                self.update_fw_db_dev_status(fw_dict.get('fw_id'), '')
        ret = self.fabric.delete_fabric_fw(tenant_id, fw_dict, is_fw_virt,
                                           fw_constants.RESULT_FW_DELETE_INIT)
        if not ret:
            LOG.error(_LE("Error in delete_fabric_fw for tenant %s"),
                      tenant_id)
            return False
        self.update_fw_db_final_result(fw_dict.get('fw_id'), (
            fw_constants.RESULT_FW_DELETE_DONE))
        self.delete_fw(fw_dict.get('fw_id'))
        return True

    def _check_delete_fw(self, tenant_id, drvr_name):
        """Deletes the Firewall, if all conditioms are met.

        This function after modifying the DB with delete operation status,
        calls the routine to remove the fabric cfg from DB and unconfigure
        the device.
        """
        fw_dict = self.fwid_attr[tenant_id].get_fw_dict()
        ret = False
        try:
            with self.fwid_attr[tenant_id].mutex_lock:
                self.update_fw_db_final_result(fw_dict.get('fw_id'), (
                    fw_constants.RESULT_FW_DELETE_INIT))
                ret = self._delete_fw_fab_dev(tenant_id, drvr_name, fw_dict)
        except Exception as exc:
            LOG.error(_LE("Exception raised in delete fw %s"), str(exc))
        return ret

    def _check_update_fw(self, tenant_id, drvr_name):
        """Update the Firewall config by calling the driver.

        This function calls the device manager routine to update the device
        with modified FW cfg.
        """
        if self.fwid_attr[tenant_id].is_fw_complete():
            fw_dict = self.fwid_attr[tenant_id].get_fw_dict()
            self.modify_fw_device(tenant_id, fw_dict.get('fw_id'), fw_dict)

    def fw_handler_decorator(fw_func):
        @wraps(fw_func)
        def fw_handler_fn(*args):
            try:
                fn_name = fw_func.__name__
                fw_func(*args)
            except Exception as exc:
                LOG.error(_LE("Exception in %(name)s %(exc)s"),
                          {'name': fn_name, 'exc': str(exc)})

        return fw_handler_fn

    @fw_handler_decorator
    def _fw_create(self, drvr_name, data, cache):
        """Firewall create routine.

        This function updates its local cache with FW parameters.
        It checks if local cache has information about the Policy
        associated with the FW. If not, it means a restart has happened.
        It retrieves the policy associated with the FW by calling
        Openstack API's and calls t he policy create internal routine.
        """

        fw = data.get('firewall')
        tenant_id = fw.get('tenant_id')
        fw_name = fw.get('name')
        fw_id = fw.get('id')
        fw_pol_id = fw.get('firewall_policy_id')
        admin_state = fw.get('admin_state_up')
        rtr_id = None
        if 'router_ids' in fw and len(fw.get('router_ids')) != 0:
            rtr_id = fw.get('router_ids')[0]
        if not admin_state:
            LOG.debug("Admin state disabled")
            return

        name = dfa_dbm.DfaDBMixin.get_project_name(self, tenant_id)
        rtr_name = '_'.join([fw_constants.TENANT_EDGE_RTR, name])

        fw_rtr_name = self.os_helper.get_rtr_name(rtr_id)
        fw_type = None
        if fw_rtr_name == rtr_name:
            fw_type = fw_constants.FW_TENANT_EDGE
        if tenant_id not in self.fwid_attr:
            self.fwid_attr[tenant_id] = FwMapAttr(tenant_id)
        tenant_obj = self.fwid_attr[tenant_id]
        tenant_obj.create_fw(name, fw_pol_id, fw_id, fw_name, fw_type, rtr_id)
        self.tenant_db.store_fw_tenant(fw_id, tenant_id)
        if not cache:
            self._check_create_fw(tenant_id, drvr_name)
        if fw_pol_id is not None and not (
                tenant_obj.is_policy_present(fw_pol_id)):
            pol_data = self.os_helper.get_fw_policy(fw_pol_id)
            if pol_data is not None:
                self.fw_policy_create(pol_data, cache=cache)

    def fw_create(self, data, fw_name=None, cache=False):
        """Top level FW create function. """
        LOG.debug("FW create %s", data)
        try:
            self._fw_create(fw_name, data, cache)
        except Exception as exc:
            LOG.error(_LE("Exception in fw_create %s"), str(exc))

    @fw_handler_decorator
    def _fw_update(self, drvr_name, data):
        """Update routine for the Firewall.

        Check if FW is already cfgd using the below function
        if self.fwid_attr[tenant_id].is_fw_complete() or
        is_fw_drvr_create_needed():
        The above two functions will take care of whether FW is already
        cfgd or about to be cfgd in case of error.
        If yes, this may be a change in policies attached to FW.
        If no, do a check, create after storing the parameters like
        rtr_id.
        """
        fw = data.get('firewall')
        tenant_id = fw.get('tenant_id')
        if self.fwid_attr[tenant_id].is_fw_complete() or \
           self.fwid_attr[tenant_id].is_fw_drvr_create_needed():
            prev_info_complete = True
        else:
            prev_info_complete = False

        tenant_obj = self.fwid_attr[tenant_id]
        if 'router_ids' in fw and len(fw.get('router_ids')) != 0:
            rtr_id = fw.get('router_ids')[0]
            name = dfa_dbm.DfaDBMixin.get_project_name(self, tenant_id)
            rtr_name = '_'.join([fw_constants.TENANT_EDGE_RTR, name])

            fw_rtr_name = self.os_helper.get_rtr_name(rtr_id)
            fw_type = None
            if fw_rtr_name == rtr_name:
                fw_type = fw_constants.FW_TENANT_EDGE
            tenant_obj.update_fw_params(rtr_id, fw_type)

        if not prev_info_complete:
            self._check_create_fw(tenant_id, drvr_name)

    def fw_update(self, data, fw_name=None):
        """Top level FW update function. """
        LOG.debug("FW Update %s", data)
        self._fw_update(fw_name, data)

    @fw_handler_decorator
    def _fw_delete(self, drvr_name, data):
        """Firewall Delete routine.

        This function calls routines to remove FW from fabric and device.
        It also updates its local cache.
        """
        fw_id = data.get('firewall_id')
        tenant_id = self.tenant_db.get_fw_tenant(fw_id)

        if tenant_id not in self.fwid_attr:
            LOG.error(_LE("Invalid tenant id for FW delete %s"), tenant_id)
            return

        tenant_obj = self.fwid_attr[tenant_id]
        ret = self._check_delete_fw(tenant_id, drvr_name)
        if ret:
            tenant_obj.delete_fw(fw_id)
            self.tenant_db.del_fw_tenant(fw_id)

    def fw_delete(self, data, fw_name=None):
        """Top level FW delete function. """
        self._fw_delete(fw_name, data)

    def _fw_rule_decode_store(self, data):
        """Misc function to decode the firewall rule from Openstack. """
        fw_rule = data.get('firewall_rule')
        rule = {'protocol': fw_rule.get('protocol'),
                'source_ip_address': fw_rule.get('source_ip_address'),
                'destination_ip_address': fw_rule.get(
                    'destination_ip_address'),
                'source_port': fw_rule.get('source_port'),
                'destination_port': fw_rule.get('destination_port'),
                'action': fw_rule.get('action'),
                'enabled': fw_rule.get('enabled'),
                'name': fw_rule.get('name')}
        return rule

    @fw_handler_decorator
    def _fw_rule_create(self, drvr_name, data, cache):
        """Firewall Rule create routine.

        This function updates its local cache with rule parameters.
        It checks if local cache has information about the Policy
        associated with the rule. If not, it means a restart has happened.
        It retrieves the policy associated with the FW by calling
        Openstack API's and calls t he policy create internal routine.
        """
        tenant_id = data.get('firewall_rule').get('tenant_id')
        fw_rule = data.get('firewall_rule')
        rule = self._fw_rule_decode_store(data)
        fw_pol_id = fw_rule.get('firewall_policy_id')
        rule_id = fw_rule.get('id')
        if tenant_id not in self.fwid_attr:
            self.fwid_attr[tenant_id] = FwMapAttr(tenant_id)
        self.fwid_attr[tenant_id].store_rule(rule_id, rule)
        if not cache:
            self._check_create_fw(tenant_id, drvr_name)
        self.tenant_db.store_rule_tenant(rule_id, tenant_id)
        if fw_pol_id is not None and not (
                self.fwid_attr[tenant_id].is_policy_present(fw_pol_id)):
            pol_data = self.os_helper.get_fw_policy(fw_pol_id)
            if pol_data is not None:
                self.fw_policy_create(pol_data, cache=cache)

    def fw_rule_create(self, data, fw_name=None, cache=False):
        """Top level rule creation routine. """
        LOG.debug("FW Rule create %s", data)
        self._fw_rule_create(fw_name, data, cache)

    @fw_handler_decorator
    def _fw_rule_delete(self, drvr_name, data):
        """Function that updates its local cache after a rule is deleted. """
        rule_id = data.get('firewall_rule_id')
        tenant_id = self.tenant_db.get_rule_tenant(rule_id)

        if tenant_id not in self.fwid_attr:
            LOG.error(_LE("Invalid tenant id for FW delete %s"), tenant_id)
            return
        tenant_obj = self.fwid_attr[tenant_id]
        # Guess actual FW/policy need not be deleted if this is the active
        # rule, Openstack does not allow it to be deleted
        tenant_obj.delete_rule(rule_id)
        self.tenant_db.del_rule_tenant(rule_id)

    def fw_rule_delete(self, data, fw_name=None):
        """Top level rule delete function. """
        LOG.debug("FW Rule delete %s", data)
        self._fw_rule_delete(fw_name, data)

    @fw_handler_decorator
    def _fw_rule_update(self, drvr_name, data):
        """Firewall Rule update routine.

        Function to decode the updated rules and call routines that
        in turn calls the device routines to update rules.
        """
        LOG.debug("FW Update %s", data)
        tenant_id = data.get('firewall_rule').get('tenant_id')
        fw_rule = data.get('firewall_rule')
        rule = self._fw_rule_decode_store(data)
        rule_id = fw_rule.get('id')
        if tenant_id not in self.fwid_attr or not (
           self.fwid_attr[tenant_id].is_rule_present(rule_id)):
            LOG.error(_LE("Incorrect update info for tenant %s"), tenant_id)
            return
        self.fwid_attr[tenant_id].rule_update(rule_id, rule)
        self._check_update_fw(tenant_id, drvr_name)

    def fw_rule_update(self, data, fw_name=None):
        """Top level rule update routine. """
        LOG.debug("FW Update Debug")
        self._fw_rule_update(fw_name, data)

    @fw_handler_decorator
    def _fw_policy_delete(self, drvr_name, data):
        """Routine to delete the policy from local cache. """
        policy_id = data.get('firewall_policy_id')
        tenant_id = self.tenant_db.get_policy_tenant(policy_id)

        if tenant_id not in self.fwid_attr:
            LOG.error(_LE("Invalid tenant id for FW delete %s"), tenant_id)
            return
        tenant_obj = self.fwid_attr[tenant_id]
        # Guess actual FW need not be deleted since if this is the active
        # policy, Openstack does not allow it to be deleted
        tenant_obj.delete_policy(policy_id)
        self.tenant_db.del_policy_tenant(policy_id)

    def fw_policy_delete(self, data, fw_name=None):
        """Top level policy delete routine. """
        LOG.debug("FW Policy Debug")
        self._fw_policy_delete(fw_name, data)

    @fw_handler_decorator
    def _fw_policy_create(self, drvr_name, data, cache):
        """Firewall Policy create routine.

        This function updates its local cache with policy parameters.
        It checks if local cache has information about the rules
        associated with the policy. If not, it means a restart has
        happened. It retrieves the rules associated with the policy by
        calling Openstack API's and calls the rule create internal routine.
        """
        policy = {}
        fw_policy = data.get('firewall_policy')
        tenant_id = fw_policy.get('tenant_id')
        LOG.info(_LI("Creating policy for tenant %s"), tenant_id)
        policy_id = fw_policy.get('id')
        policy_name = fw_policy.get('name')
        pol_rule_dict = fw_policy.get('firewall_rules')
        if tenant_id not in self.fwid_attr:
            self.fwid_attr[tenant_id] = FwMapAttr(tenant_id)
        policy['name'] = policy_name
        policy['rule_dict'] = pol_rule_dict
        self.fwid_attr[tenant_id].store_policy(policy_id, policy)
        if not cache:
            self._check_create_fw(tenant_id, drvr_name)
        self.tenant_db.store_policy_tenant(policy_id, tenant_id)
        for rule in pol_rule_dict:
            rule_id = rule
            if not self.fwid_attr[tenant_id].is_rule_present(rule_id):
                rule_data = self.os_helper.get_fw_rule(rule_id)
                if rule_data is not None:
                    self.fw_rule_create(rule_data, cache=cache)

    def fw_policy_create(self, data, fw_name=None, cache=False):
        """Top level policy create routine. """
        LOG.debug("FW Policy Debug")
        self._fw_policy_create(fw_name, data, cache)

    def convert_fwdb_event_msg(self, rule, tenant_id, rule_id, policy_id):
        """Convert the Firewall DB to a event message format.

        From inputs from DB, this will create a FW rule dictionary that
        resembles the actual data from Openstack when a rule is created.
        This is usually called after restart, in order to populate local
        cache.
        """
        rule.update({'tenant_id': tenant_id, 'id': rule_id,
                     'firewall_policy_id': policy_id})
        fw_rule_data = {'firewall_rule': rule}
        return fw_rule_data

    def convert_fwdb(self, tenant_id, name, policy_id, fw_id):
        """Convert the Firewall DB to a query response.

        From FWDB inputs, this will create a FW message that resembles the
        actual data from Openstack, when a query for FW is done.
        """
        fw_dict = {'tenant_id': tenant_id, 'name': name, 'id': fw_id,
                   'firewall_policy_id': policy_id,
                   'admin_state_up': True}
        fw_data = {'firewall': fw_dict}
        return fw_data

    def populate_local_cache(self):
        """This populates the local cache after reading the Database.

        It calls the appropriate rule create, fw create routines.
        It doesn't actually call the routine to prepare the fabric or cfg the
        device since it will be handled by retry module.
        """
        fw_dict = self.get_all_fw_db()
        LOG.info(_LI("Populating FW Mgr Local Cache"))
        for fw_id in fw_dict:
            fw_data = fw_dict.get(fw_id)
            tenant_id = fw_data.get('tenant_id')
            rule_dict = fw_data.get('rules').get('rules')
            policy_id = fw_data.get('rules').get('firewall_policy_id')
            for rule in rule_dict:
                fw_evt_data = self.convert_fwdb_event_msg(rule_dict.get(rule),
                                                          tenant_id, rule,
                                                          policy_id)
                LOG.info(_LI("Populating Rules for tenant %s"), tenant_id)
                self.fw_rule_create(fw_evt_data, cache=True)
            fw_os_data = self.os_helper.get_fw(fw_id)
            # If enabler is stopped and FW is deleted, then the above routine
            # will fail.
            if fw_os_data is None:
                fw_os_data = self.convert_fwdb(tenant_id, fw_data.get('name'),
                                               policy_id, fw_id)
            LOG.info(_LI("Populating FW for tenant %s"), tenant_id)
            self.fw_create(fw_os_data, cache=True)
            if fw_data.get('device_status') == 'SUCCESS':
                self.fwid_attr[tenant_id].fw_drvr_created(True)
            else:
                self.fwid_attr[tenant_id].fw_drvr_created(False)
        return fw_dict

    def retry_failure_fab_dev_create(self, tenant_id, fw_data, fw_dict):
        """This module calls routine in fabric to retry the failure cases.

        If device is not successfully cfg/uncfg, it calls the device manager
        routine to cfg/uncfg the device.
        """
        result = fw_data.get('result').split('(')[0]
        is_fw_virt = self.is_device_virtual()
        # Fabric portion
        if result == fw_constants.RESULT_FW_CREATE_INIT:
            name = dfa_dbm.DfaDBMixin.get_project_name(self, tenant_id)
            ret = self.fabric.retry_failure(tenant_id, name, fw_dict,
                                            is_fw_virt, result)
            if not ret:
                LOG.error(_LE("Retry failure returned fail for tenant %s"),
                          tenant_id)
                return
            else:
                result = fw_constants.RESULT_FW_CREATE_DONE
                self.update_fw_db_final_result(fw_dict.get('fw_id'), result)
        # Device portion
        if result == fw_constants.RESULT_FW_CREATE_DONE:
            if fw_data.get('device_status') != 'SUCCESS':
                ret = self.create_fw_device(tenant_id, fw_dict.get('fw_id'),
                                            fw_dict)
                if ret:
                    self.fwid_attr[tenant_id].fw_drvr_created(True)
                    self.update_fw_db_dev_status(fw_dict.get('fw_id'),
                                                 'SUCCESS')
                    LOG.info(_LI("Retry failue return success for create"
                             " tenant %s"), tenant_id)

    def retry_failure_fab_dev_delete(self, tenant_id, fw_data, fw_dict):
        """Retry the failure cases for delete.

        This module calls routine in fabric to retry the failure cases for
        delete.
        If device is not successfully cfg/uncfg, it calls the device manager
        routine to cfg/uncfg the device.
        """
        result = fw_data.get('result').split('(')[0]
        name = dfa_dbm.DfaDBMixin.get_project_name(self, tenant_id)
        fw_dict['tenant_name'] = name
        is_fw_virt = self.is_device_virtual()
        if result == fw_constants.RESULT_FW_DELETE_INIT:
            if self.fwid_attr[tenant_id].is_fw_drvr_created():
                ret = self.delete_fw_device(tenant_id, fw_dict.get('fw_id'),
                                            fw_dict)
                if ret:
                    # Device portion
                    self.update_fw_db_dev_status(fw_dict.get('fw_id'),
                                                 '')
                    self.fwid_attr[tenant_id].fw_drvr_created(False)
                    LOG.info(_LI("Retry failue dev return success for delete"
                             " tenant %s"), tenant_id)
                else:
                    return
            name = dfa_dbm.DfaDBMixin.get_project_name(self, tenant_id)
            ret = self.fabric.retry_failure(tenant_id, name, fw_dict,
                                            is_fw_virt, result)
            if not ret:
                LOG.error(_LE("Retry failure returned fail for tenant %s"),
                          tenant_id)
                return
            result = fw_constants.RESULT_FW_DELETE_DONE
            self.update_fw_db_final_result(fw_dict.get('fw_id'), result)
            self.delete_fw(fw_dict.get('fw_id'))
            self.fwid_attr[tenant_id].delete_fw(fw_dict.get('fw_id'))
            self.tenant_db.del_fw_tenant(fw_dict.get('fw_id'))

    def fw_retry_failures_create(self):
        """This module is called for retrying the create cases. """
        for tenant_id in self.fwid_attr:
            try:
                with self.fwid_attr[tenant_id].mutex_lock:
                    if self.fwid_attr[tenant_id].is_fw_drvr_create_needed():
                        fw_dict = self.fwid_attr[tenant_id].get_fw_dict()
                        if fw_dict:
                            fw_obj, fw_data = self.get_fw(fw_dict.get('fw_id'))
                            self.retry_failure_fab_dev_create(tenant_id,
                                                              fw_data,
                                                              fw_dict)
                        else:
                            LOG.error(_LE("FW data not found for tenant %s"),
                                      tenant_id)
            except Exception as exc:
                LOG.error(_LE("Exception in retry failure create %s"),
                          str(exc))

    def fill_fw_dict_from_db(self, fw_data):
        """
        This routine is called to create a local fw_dict with data from DB.
        """
        rule_dict = fw_data.get('rules').get('rules')
        fw_dict = {'fw_id': fw_data.get('fw_id'),
                   'fw_name': fw_data.get('name'),
                   'firewall_policy_id': fw_data.get('firewall_policy_id'),
                   'fw_type': fw_data.get('fw_type'),
                   'router_id': fw_data.get('router_id'), 'rules': {}}
        for rule in rule_dict:
            fw_dict['rules'][rule] = rule_dict.get(rule)
        return fw_dict

    def fw_retry_failures_delete(self):
        """This routine is called for retrying the delete cases. """
        for tenant_id in self.fwid_attr:
            try:
                with self.fwid_attr[tenant_id].mutex_lock:
                    # For both create and delete case
                    fw_data = self.get_fw_by_tenant_id(tenant_id)
                    if fw_data is None:
                        LOG.info(_LI("No FW for tenant %s"), tenant_id)
                        continue
                    result = fw_data.get('result').split('(')[0]
                    if result == fw_constants.RESULT_FW_DELETE_INIT:
                        fw_dict = self.fwid_attr[tenant_id].get_fw_dict()
                        # This means a restart has happened before the FW is
                        # completely deleted
                        if not fw_dict:
                            # Need to fill fw_dict from fw_data
                            fw_dict = self.fill_fw_dict_from_db(fw_data)
                        self.retry_failure_fab_dev_delete(tenant_id, fw_data,
                                                          fw_dict)
            except Exception as exc:
                LOG.error(_LE("Exception in retry failure delete %s"),
                          str(exc))

    def fw_retry_failures(self):
        """Top level retry routine called. """
        if not self.fw_init:
            return
        try:
            self.fw_retry_failures_create()
            self.fw_retry_failures_delete()
        except Exception as exc:
            LOG.error(_LE("Exception in retry failures %s"), str(exc))
