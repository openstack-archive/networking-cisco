# Copyright 2016 Cisco Systems, Inc.
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

from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.server.services.firewall.native import (
    fw_constants as fw_const)
from networking_cisco.apps.saf.server.services.firewall.native.drivers import (
    dev_mgr_plug)

from networking_cisco._i18n import _LI

LOG = logging.getLogger(__name__)


# Not sure of the exact name. But, this implements a case when all requests
# goto first device until it exhausts
class MaxSched(object):

    """Max Sched class.

    This scheduler will return the first firewall until it reaches its quota.
    """

    def __init__(self, obj_dict):
        """Initialization. """
        self.num_res = len(obj_dict)
        self.obj_dict = obj_dict
        self.res = dict()
        cnt = 0
        for ip in self.obj_dict:
            obj_elem_dict = self.obj_dict.get(ip)
            drvr_obj = obj_elem_dict.get('drvr_obj')
            self.res[cnt] = {'mgmt_ip': ip,
                             'quota': drvr_obj.get_max_quota(),
                             'obj_dict': obj_elem_dict,
                             'used': 0,
                             'fw_id_lst': []}
            cnt += 1

    def allocate_fw_dev(self, fw_id):
        """Allocate firewall device.

        Allocate the first Firewall device which has resources available.
        """
        for cnt in self.res:
            used = self.res.get(cnt).get('used')
            if used < self.res.get(cnt).get('quota'):
                self.res[cnt]['used'] = used + 1
                self.res[cnt]['fw_id_lst'].append(fw_id)
                return self.res[cnt].get('obj_dict'), (
                    self.res[cnt].get('mgmt_ip'))
        return None, None

    def populate_fw_dev(self, fw_id, mgmt_ip, new):
        """Populate the class after a restart. """
        for cnt in self.res:
            used = self.res.get(cnt).get('used')
            if mgmt_ip == self.res[cnt].get('mgmt_ip'):
                if new:
                    self.res[cnt]['used'] = used + 1
                self.res[cnt]['fw_id_lst'].append(fw_id)
                return self.res[cnt].get('obj_dict'), (
                    self.res[cnt].get('mgmt_ip'))
        return None, None

    def get_fw_dev_map(self, fw_id):
        """Return the object dict and mgmt ip for a firewall. """
        for cnt in self.res:
            if fw_id in self.res.get(cnt).get('fw_id_lst'):
                return self.res[cnt].get('obj_dict'), (
                    self.res[cnt].get('mgmt_ip'))
        return None, None

    def deallocate_fw_dev(self, fw_id):
        """Release the firewall resource. """
        for cnt in self.res:
            if fw_id in self.res.get(cnt).get('fw_id_lst'):
                self.res[cnt]['used'] = self.res[cnt]['used'] - 1
                self.res.get(cnt).get('fw_id_lst').remove(fw_id)
                return


class DeviceMgr(object):

    """Device Manager. """

    def __init__(self, cfg):
        """Initialization. """
        self.drvr_obj = {}
        self.mgmt_ip_list = cfg.firewall.fw_mgmt_ip
        self.mgmt_ip_list = self.mgmt_ip_list.strip('[').rstrip(']').split(',')
        self.user_list = cfg.firewall.fw_username
        if self.user_list:
            self.user_list = self.user_list.strip('[').rstrip(']').split(',')
        self.pwd_list = cfg.firewall.fw_password
        if self.pwd_list:
            self.pwd_list = self.pwd_list.strip('[').rstrip(']').split(',')
        self.interface_in_list = cfg.firewall.fw_interface_in
        if self.interface_in_list:
            self.interface_in_list = self.interface_in_list.strip('[').\
                rstrip(']').split(',')
        self.interface_out_list = cfg.firewall.fw_interface_out
        if self.interface_out_list:
            self.interface_out_list = self.interface_out_list.strip('[').\
                rstrip(']').split(',')
        self.obj_dict = dict()
        cnt = 0
        dev = cfg.firewall.device
        # Modify enabler_conf.ini in source path for IP list
        for ip in self.mgmt_ip_list:
            ip = ip.strip()
            obj = dev_mgr_plug.DeviceMgr(cfg, dev)
            self.obj_dict[ip] = dict()
            self.obj_dict[ip]['drvr_obj'] = obj.get_drvr_obj()
            self.obj_dict[ip]['dev_name'] = cfg.firewall.device.split(',')[cnt]
            cnt = cnt + 1
        self.drvr_initialize(cfg)
        if cfg.firewall.sched_policy == fw_const.SCHED_POLICY:
            self.sched_obj = MaxSched(self.obj_dict)

    def populate_local_sch_cache(self, fw_dict):
        """Populate the local cache from FW DB after restart. """
        for fw_id in fw_dict:
            fw_data = fw_dict.get(fw_id)
            mgmt_ip = fw_data.get('fw_mgmt_ip')
            dev_status = fw_data.get('device_status')
            if dev_status == 'SUCCESS':
                new = True
            else:
                new = False
            if mgmt_ip is not None:
                drvr_dict, mgmt_ip = self.sched_obj.populate_fw_dev(fw_id,
                                                                    mgmt_ip,
                                                                    new)
                if drvr_dict is None or mgmt_ip is None:
                    LOG.info(_LI("Pop cache for FW sch: drvr_dict or mgmt_ip "
                             "is None"))

    def drvr_initialize(self, cfg):
        """Initialize the driver routines. """
        cnt = 0
        for ip in self.obj_dict:
            cfg_dict = {}
            drvr_obj = self.obj_dict.get(ip).get('drvr_obj')
            cfg_dict['mgmt_ip_addr'] = ip
            if self.user_list is not None:
                cfg_dict['user'] = self.user_list[cnt]
            if self.pwd_list is not None:
                cfg_dict['pwd'] = self.pwd_list[cnt]
            if self.interface_in_list is not None:
                cfg_dict['interface_in'] = self.interface_in_list[cnt]
            if self.interface_out_list is not None:
                cfg_dict['interface_out'] = self.interface_out_list[cnt]
            drvr_obj.initialize(cfg_dict)
            cnt = cnt + 1

    def populate_event_que(self, que_obj):
        """Populates the event queue object.

        This is for sending router events to event handler.
        """
        for ip in self.obj_dict:
            drvr_obj = self.obj_dict.get(ip).get('drvr_obj')
            drvr_obj.populate_event_que(que_obj)

    def populate_dcnm_obj(self, dcnm_obj):
        """Populates the DCNM object. """
        for ip in self.obj_dict:
            drvr_obj = self.obj_dict.get(ip).get('drvr_obj')
            drvr_obj.populate_dcnm_obj(dcnm_obj)

    def is_device_virtual(self):
        """Returns if the device is physical or virtual. """
        for ip in self.obj_dict:
            drvr_obj = self.obj_dict.get(ip).get('drvr_obj')
            ret = drvr_obj.is_device_virtual()
            # No way to pin a device as of now, so return the first
            # TODO(padkrish)
            return ret

    def create_fw_device(self, tenant_id, fw_id, data):
        """Creates the Firewall. """
        drvr_dict, mgmt_ip = self.sched_obj.allocate_fw_dev(fw_id)
        if drvr_dict is not None and mgmt_ip is not None:
            self.update_fw_db_mgmt_ip(fw_id, mgmt_ip)
            ret = drvr_dict.get('drvr_obj').create_fw(tenant_id, data)
            if not ret:
                self.sched_obj.deallocate_fw_dev(fw_id)
            return ret
        else:
            return False

    def delete_fw_device(self, tenant_id, fw_id, data):
        """Deletes the Firewall. """
        drvr_dict, mgmt_ip = self.sched_obj.get_fw_dev_map(fw_id)
        ret = drvr_dict.get('drvr_obj').delete_fw(tenant_id, data)
        # FW DB gets deleted, so no need to remove the MGMT IP
        if ret:
            self.sched_obj.deallocate_fw_dev(fw_id)
        return ret

    def modify_fw_device(self, tenant_id, fw_id, data):
        """Modifies the firewall cfg. """
        drvr_dict, mgmt_ip = self.sched_obj.get_fw_dev_map(fw_id)
        return drvr_dict.get('drvr_obj').modify_fw(tenant_id, data)

    def network_create_notif(self, tenant_id, tenant_name, cidr):
        """Notification for Network create.

        Since FW ID not present, it's not possible to know which FW instance
        to call. So, calling everyone, each instance will figure out if it
        applies to them.
        """
        for ip in self.obj_dict:
            drvr_obj = self.obj_dict.get(ip).get('drvr_obj')
            ret = drvr_obj.network_create_notif(tenant_id, tenant_name, cidr)
            LOG.info(_LI("Driver with IP %(ip)s return %(ret)s"),
                     {'ip': ip, 'ret': ret})

    def network_delete_notif(self, tenant_id, tenant_name, net_id):
        """Notification for Network delete.

        Since FW ID not present, it's not possible to know which FW instance
        to call. So, calling everyone, each instance will figure out if it
        applies to them.
        """
        for ip in self.obj_dict:
            drvr_obj = self.obj_dict.get(ip).get('drvr_obj')
            ret = drvr_obj.network_delete_notif(tenant_id, tenant_name,
                                                net_id)
            LOG.info(_LI("Driver with IP %(ip)s return %(ret)s for network "
                         "delete notification"), {'ip': ip, 'ret': ret})
