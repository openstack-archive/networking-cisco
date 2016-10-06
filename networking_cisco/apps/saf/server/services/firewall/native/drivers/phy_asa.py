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
    fabric_setup_base as FP)
from networking_cisco.apps.saf.server.services.firewall.native.drivers import (
    asa_rest as asa)
from networking_cisco.apps.saf.server.services.firewall.native.drivers import (
    base)

from networking_cisco._i18n import _LE, _LI

LOG = logging.getLogger(__name__)


class PhyAsa(base.BaseDriver, FP.FabricApi):

    """Physical ASA Driver. """

    def __init__(self):
        LOG.info(_LI("Initializing physical ASA"))
        super(PhyAsa, self).__init__()

    def initialize(self, cfg_dict):
        self.mgmt_ip_addr = cfg_dict.get('mgmt_ip_addr').strip()
        self.user = cfg_dict.get('user').strip()
        self.pwd = cfg_dict.get('pwd').strip()
        self.interface_in = cfg_dict.get('interface_in').strip()
        self.interface_out = cfg_dict.get('interface_out').strip()
        LOG.info(_LI("ASA with mgmt %s getting initialized"),
                 self.mgmt_ip_addr)
        self.asa5585 = asa.Asa5585(self.mgmt_ip_addr, self.user, self.pwd)

    def populate_event_que(self, que_obj):
        LOG.info(_LI("Populate Event for PhyAsa"))

    def populate_dcnm_obj(self, dcnm_obj):
        LOG.info(_LI("Populate Event for DCNM obj"))

    def network_create_notif(self, tenant_id, tenant_name, cidr):
        """Network Create Notification. """
        LOG.info(_LI("Nwk Create Notif PhyAsa"))

    def network_delete_notif(self, tenant_id, tenant_name, network_id):
        """Network Delete Notification. """
        LOG.info(_LI("Nwk Delete Notif PhyAsa"))

    def is_device_virtual(self):
        return False

    def get_name(self):
        return 'phy_asa'

    def get_max_quota(self):
        return self.asa5585.get_quota()

    def create_fw(self, tenant_id, data):
        LOG.info(_LI("In creating phy ASA FW data is %s"), data)
        tenant_name = data.get('tenant_name')
        in_ip_dict = self.get_in_ip_addr(tenant_id)
        in_gw = in_ip_dict.get('gateway')
        in_sec_gw = in_ip_dict.get('sec_gateway')
        in_serv_node = self.get_in_srvc_node_ip_addr(tenant_id)
        out_ip_dict = self.get_out_ip_addr(tenant_id)
        out_ip_gw = out_ip_dict.get('gateway')
        out_sec_gw = out_ip_dict.get('sec_gateway')
        out_serv_node = self.get_out_srvc_node_ip_addr(tenant_id)
        in_seg, in_vlan = self.get_in_seg_vlan(tenant_id)
        out_seg, out_vlan = self.get_out_seg_vlan(tenant_id)

        kw = {'params': {'tenant_name': tenant_name,
                         'in_vlan': in_vlan, 'out_vlan': out_vlan,
                         'in_ip': in_serv_node, 'in_mask': '255.255.255.0',
                         'in_gw': in_gw, 'in_sec_gw': in_sec_gw,
                         'out_ip': out_serv_node, 'out_mask': '255.255.255.0',
                         'out_gw': out_ip_gw, 'out_sec_gw': out_sec_gw,
                         'intf_in': self.interface_in,
                         'intf_out': self.interface_out}}
        status = self.asa5585.setup(**kw)
        if status is False:
            LOG.error(_LE("Physical FW instance creation failure for "
                      "tenant %s"), tenant_name)
            return False

        status = self.asa5585.apply_policy(data)
        if status is False:
            LOG.error(_LE("Applying FW policy failure for tenant %s"),
                      tenant_name)

        return status

    def delete_fw(self, tenant_id, data):
        LOG.info(_LI("In Delete fw data is %s"), data)
        tenant_name = data.get('tenant_name')
        in_serv_node = self.get_in_srvc_node_ip_addr(tenant_id)
        out_serv_node = self.get_out_srvc_node_ip_addr(tenant_id)
        in_seg, in_vlan = self.get_in_seg_vlan(tenant_id)
        out_seg, out_vlan = self.get_out_seg_vlan(tenant_id)

        kw = dict(params=dict(tenant_name=tenant_name,
                              in_vlan=in_vlan, out_vlan=out_vlan,
                              in_ip=in_serv_node, in_mask='255.255.255.0',
                              out_ip=out_serv_node, out_mask='255.255.255.0',
                              intf_in=self.interface_in,
                              intf_out=self.interface_out))
        status = self.asa5585.cleanup(**kw)
        return status

    def modify_fw(self, tenant_id, data):
        LOG.info(_LI("In Modify fw data is %s"), data)
        return self.asa5585.apply_policy(data)
