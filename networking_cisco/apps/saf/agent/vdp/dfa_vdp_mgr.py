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


from six.moves import queue
import time

from oslo_serialization import jsonutils

from networking_cisco._i18n import _LE, _LI

from networking_cisco.apps.saf.agent import detect_uplink as uplink_det
from networking_cisco.apps.saf.agent.topo_disc import topo_disc
from networking_cisco.apps.saf.agent.vdp import ovs_vdp
from networking_cisco.apps.saf.common import constants
from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.common import dfa_sys_lib as sys_utils
from networking_cisco.apps.saf.common import rpc
from networking_cisco.apps.saf.common import utils

LOG = logging.getLogger(__name__)


class VdpMsgPriQue(object):

    """VDP Message Queue. """

    def __init__(self):
        self._queue = queue.PriorityQueue()

    def enqueue(self, priority, msg):
        msg_tupl = (priority, msg)
        self._queue.put(msg_tupl)

    def dequeue(self):
        msg_tupl = self._queue.get()
        return msg_tupl[0], msg_tupl[1]

    def dequeue_nonblock(self):
        msg_tupl = self._queue.get_nowait()
        return msg_tupl[0], msg_tupl[1]

    def is_not_empty(self):
        return not self._queue.empty()


class VdpQueMsg(object):

    """Construct VDP Message. """

    def __init__(self, msg_type, port_uuid=None, vm_mac=None, oui=None,
                 net_uuid=None, segmentation_id=None, status=None,
                 vm_bulk_list=None, phy_uplink=None, br_int=None, br_ex=None,
                 root_helper=None):
        self.msg_dict = {}
        self.msg_type = msg_type
        if msg_type == constants.VM_MSG_TYPE:
            self.construct_vm_msg(port_uuid, vm_mac, net_uuid,
                                  segmentation_id, status, oui, phy_uplink)
        elif msg_type == constants.UPLINK_MSG_TYPE:
            self.construct_uplink_msg(status, phy_uplink, br_int, br_ex,
                                      root_helper)
        elif msg_type == constants.VM_BULK_SYNC_MSG_TYPE:
            self.construct_vm_bulk_sync_msg(vm_bulk_list, phy_uplink)

    def construct_vm_msg(self, port_uuid, vm_mac, net_uuid,
                         segmentation_id, status, oui, phy_uplink):
        self.msg_dict['port_uuid'] = port_uuid
        self.msg_dict['vm_mac'] = vm_mac
        self.msg_dict['net_uuid'] = net_uuid
        self.msg_dict['segmentation_id'] = segmentation_id
        self.msg_dict['status'] = status
        self.msg_dict['oui'] = oui
        self.msg_dict['phy_uplink'] = phy_uplink

    def construct_vm_bulk_sync_msg(self, vm_bulk_list, phy_uplink):
        self.msg_dict['phy_uplink'] = phy_uplink
        self.msg_dict['vm_bulk_list'] = vm_bulk_list

    def construct_uplink_msg(self, status, phy_uplink, br_int, br_ex,
                             root_helper):
        self.msg_dict['status'] = status
        self.msg_dict['phy_uplink'] = phy_uplink
        self.msg_dict['br_int'] = br_int
        self.msg_dict['br_ex'] = br_ex
        self.msg_dict['root_helper'] = root_helper

    def get_oui(self):
        return self.msg_dict['oui']

    def get_uplink(self):
        return self.msg_dict['phy_uplink']

    def get_mac(self):
        return self.msg_dict['vm_mac']

    def get_status(self):
        return self.msg_dict['status']

    def get_segmentation_id(self):
        return self.msg_dict['segmentation_id']

    def get_net_uuid(self):
        return self.msg_dict['net_uuid']

    def get_port_uuid(self):
        return self.msg_dict['port_uuid']

    def get_integ_br(self):
        return self.msg_dict['br_int']

    def get_ext_br(self):
        return self.msg_dict['br_ex']

    def get_root_helper(self):
        return self.msg_dict['root_helper']

    def set_uplink(self, uplink):
        self.msg_dict['phy_uplink'] = uplink


class VdpMgr(object):

    """Responsible for Handling VM/Uplink requests. """

    def __init__(self, config_dict, rpc_client, hostname):
        self.br_integ = config_dict.get('integration_bridge')
        self.br_ex = config_dict.get('external_bridge')
        self.root_helper = config_dict.get('root_helper')
        self.host_id = config_dict.get('host_id')
        self.node_list = config_dict['node_list']
        self.node_uplink_list = config_dict['node_uplink_list']
        # Check for error?? fixme(padkrish)
        self.que = VdpMsgPriQue()
        self.err_que = VdpMsgPriQue()
        self.phy_uplink = None
        self.veth_intf = None
        self.restart_uplink_called = False
        self.ovs_vdp_obj_dict = {}
        self.rpc_clnt = rpc_client
        self.host_name = hostname
        self.uplink_det_compl = False
        self.process_uplink_ongoing = False
        self.uplink_down_cnt = 0
        self.is_os_run = False
        self.static_uplink = False
        self.static_uplink_port = None
        self.static_uplink_first = True
        self.bulk_vm_rcvd_flag = False
        self.bulk_vm_check_cnt = 0
        self.vdp_mgr_lock = utils.lock()
        self.read_static_uplink()
        self.start()
        self.topo_disc = topo_disc.TopoDisc(self.topo_disc_cb,
                                            self.root_helper)

    def read_static_uplink(self):
        """Read the static uplink from file, if given."""
        if self.node_list is None or self.node_uplink_list is None:
            return
        for node, port in zip(self.node_list.split(','),
                              self.node_uplink_list.split(',')):
            if node.strip() == self.host_name:
                self.static_uplink = True
                self.static_uplink_port = port.strip()
                return

    def topo_disc_cb(self, intf, topo_disc_obj):
        return self.save_topo_disc_params(intf, topo_disc_obj)

    def update_vm_result(self, port_uuid, result, lvid=None,
                         vdp_vlan=None, fail_reason=None):
        context = {'agent': self.host_id}
        if lvid is None or vdp_vlan is None:
            args = jsonutils.dumps({'port_uuid': port_uuid, 'result': result,
                                    'fail_reason': fail_reason})
        else:
            args = jsonutils.dumps({'port_uuid': port_uuid, 'local_vlan': lvid,
                                    'vdp_vlan': vdp_vlan, 'result': result,
                                    'fail_reason': fail_reason})
        msg = self.rpc_clnt.make_msg('update_vm_result', context, msg=args)
        try:
            resp = self.rpc_clnt.call(msg)
            return resp
        except rpc.MessagingTimeout:
            LOG.error(_LE("RPC timeout: Failed to update VM result on the"
                          " server"))

    def vdp_vlan_change_cb(self, port_uuid, lvid, vdp_vlan, fail_reason):
        """Callback function for updating the VDP VLAN in DB. """
        LOG.info(_LI("Vlan change CB lvid %(lvid)s VDP %(vdp)s"),
                 {'lvid': lvid, 'vdp': vdp_vlan})
        self.update_vm_result(port_uuid, constants.RESULT_SUCCESS,
                              lvid=lvid, vdp_vlan=vdp_vlan,
                              fail_reason=fail_reason)

    def process_vm_event(self, msg, phy_uplink):
        LOG.info(_LI("In processing VM Event status %(status)s for MAC "
                     "%(mac)s UUID %(uuid)s oui %(oui)s"),
                 {'status': msg.get_status(), 'mac': msg.get_mac(),
                  'uuid': msg.get_port_uuid(), 'oui': msg.get_oui()})
        time.sleep(10)
        if msg.get_status() == 'up':
            res_fail = constants.CREATE_FAIL
        else:
            res_fail = constants.DELETE_FAIL
        if (not self.uplink_det_compl or
                phy_uplink not in self.ovs_vdp_obj_dict):
            LOG.error(_LE("Uplink Port Event not received yet"))
            self.update_vm_result(msg.get_port_uuid(), res_fail)
            return
        ovs_vdp_obj = self.ovs_vdp_obj_dict[phy_uplink]
        port_event_reply = ovs_vdp_obj.send_vdp_port_event(
            msg.get_port_uuid(), msg.get_mac(), msg.get_net_uuid(),
            msg.get_segmentation_id(), msg.get_status(), msg.get_oui())
        if not port_event_reply.get('result'):
            LOG.error(_LE("Error in VDP port event, Err Queue enq"))
            self.update_vm_result(
                msg.get_port_uuid(), res_fail,
                fail_reason=port_event_reply.get('fail_reason'))
        else:
            LOG.info(_LI("Success in VDP port event"))
            lvid, vdp_vlan = ovs_vdp_obj.get_lvid_vdp_vlan(msg.get_net_uuid(),
                                                           msg.get_port_uuid())
            self.update_vm_result(
                msg.get_port_uuid(), constants.RESULT_SUCCESS,
                lvid=lvid, vdp_vlan=vdp_vlan,
                fail_reason=port_event_reply.get('fail_reason'))

    def process_bulk_vm_event(self, msg, phy_uplink):
        """Process the VM bulk event usually after a restart. """
        LOG.info("In processing Bulk VM Event status %s", msg)
        time.sleep(3)
        if (not self.uplink_det_compl or
                phy_uplink not in self.ovs_vdp_obj_dict):
            # This condition shouldn't be hit as only when uplink is obtained,
            # save_uplink is called and that in turns calls this process_bulk.
            LOG.error(_LE("Uplink Port Event not received,"
                          "yet in bulk process"))
            return
        ovs_vdp_obj = self.ovs_vdp_obj_dict[phy_uplink]
        for vm_dict in msg.msg_dict.get('vm_bulk_list'):
            if vm_dict['status'] == 'down':
                ovs_vdp_obj.pop_local_cache(vm_dict['port_uuid'],
                                            vm_dict['vm_mac'],
                                            vm_dict['net_uuid'],
                                            vm_dict['local_vlan'],
                                            vm_dict['vdp_vlan'],
                                            vm_dict['segmentation_id'])
            vm_msg = VdpQueMsg(constants.VM_MSG_TYPE,
                               port_uuid=vm_dict['port_uuid'],
                               vm_mac=vm_dict['vm_mac'],
                               net_uuid=vm_dict['net_uuid'],
                               segmentation_id=vm_dict['segmentation_id'],
                               status=vm_dict['status'],
                               oui=vm_dict['oui'],
                               phy_uplink=phy_uplink)
            self.process_vm_event(vm_msg, phy_uplink)

    def process_uplink_event(self, msg, phy_uplink):
        LOG.info(_LI("Received New uplink Msg %(msg)s for uplink %(uplink)s"),
                 {'msg': msg.get_status(), 'uplink': phy_uplink})
        if msg.get_status() == 'up':
            ovs_exc_raised = False
            ovs_exc_reason = ""
            try:
                self.ovs_vdp_obj_dict[phy_uplink] = ovs_vdp.OVSNeutronVdp(
                    phy_uplink, msg.get_integ_br(), msg.get_ext_br(),
                    msg.get_root_helper(), self.vdp_vlan_change_cb)
            except Exception as exc:
                ovs_exc_reason = str(exc)
                LOG.error(_LE("OVS VDP Object creation failed %s"),
                          str(ovs_exc_reason))
                ovs_exc_raised = True
            if (ovs_exc_raised or not self.ovs_vdp_obj_dict[phy_uplink].
                    is_lldpad_setup_done()):
                # Is there a way to delete the object??
                if not ovs_exc_reason:
                    uplink_fail_reason = (self.ovs_vdp_obj_dict[phy_uplink].
                                          get_uplink_fail_reason())
                else:
                    uplink_fail_reason = ovs_exc_reason
                LOG.error(_LE("UP Event Processing NOT Complete"))
                self.err_que.enqueue(constants.Q_UPL_PRIO, msg)
                self.save_uplink(uplink=self.phy_uplink,
                                 fail_reason=uplink_fail_reason)
            else:
                self.uplink_det_compl = True
                veth_intf = (self.ovs_vdp_obj_dict[self.phy_uplink].
                             get_lldp_local_bridge_port())
                LOG.info(_LI("UP Event Processing Complete Saving uplink "
                             "%(ul)s and veth %(veth)s"),
                         {'ul': self.phy_uplink, 'veth': veth_intf})
                self.save_uplink(uplink=self.phy_uplink, veth_intf=veth_intf)
                self.topo_disc.uncfg_intf(self.phy_uplink)
                self.topo_disc.cfg_intf(veth_intf,
                                        phy_interface=self.phy_uplink)
        elif msg.get_status() == 'down':
            # Free the object fixme(padkrish)
            if phy_uplink in self.ovs_vdp_obj_dict:
                self.ovs_vdp_obj_dict[phy_uplink].clear_obj_params()
            else:
                ovs_vdp.delete_uplink_and_flows(self.root_helper, self.br_ex,
                                                phy_uplink)
            self.save_uplink()
            self.topo_disc.uncfg_intf(self.veth_intf)
            self.topo_disc.cfg_intf(phy_uplink)

    def process_queue(self):
        LOG.info(_LI("Entered process_q"))
        while True:
            prio, msg = self.que.dequeue()
            msg_type = msg.msg_type
            phy_uplink = msg.get_uplink()
            LOG.info(_LI("Msg dequeued type is %d"), msg_type)
            try:
                if msg_type == constants.VM_MSG_TYPE:
                    self.process_vm_event(msg, phy_uplink)
                elif msg_type == constants.VM_BULK_SYNC_MSG_TYPE:
                    self.process_bulk_vm_event(msg, phy_uplink)
                elif msg_type == constants.UPLINK_MSG_TYPE:
                    try:
                        self.process_uplink_event(msg, phy_uplink)
                    except Exception as eu:
                        LOG.exception(_LE("Exception caught in process_uplink"
                                          " %s"), str(eu))
                    self.process_uplink_ongoing = False
            except Exception as e:
                LOG.exceptin(_LE("Exception caught in process_q %s"), str(e))

    def process_err_queue(self):
        LOG.info(_LI("Entered Err process_q"))
        try:
            while self.err_que.is_not_empty():
                prio, msg = self.err_que.dequeue_nonblock()
                msg_type = msg.msg_type
                LOG.info(_LI("Msg dequeued from err queue type is %d"),
                         msg_type)
                if msg_type == constants.UPLINK_MSG_TYPE:
                    self.que.enqueue(constants.Q_UPL_PRIO, msg)
        except Exception as e:
            LOG.exceptin(_LE("Exception caught in proc_err_que %s "), str(e))

    def start(self):
        # Spawn the thread
        # Pass the Que as last argument so that in case of exception, the
        # daemon can exit gracefully. fixme(padkrish)
        thr_q = utils.EventProcessingThread("VDP_Mgr", self, 'process_queue')
        thr_q.start()
        task_err_proc = utils.PeriodicTask(constants.ERR_PROC_INTERVAL,
                                           self.process_err_queue)
        task_err_proc.run()
        task_uplink = utils.PeriodicTask(constants.UPLINK_DET_INTERVAL,
                                         self.vdp_uplink_proc_top)
        task_uplink.run()

    def is_openstack_running(self):
        """Currently it just checks for the presence of both the bridges. """
        try:
            if (ovs_vdp.is_bridge_present(self.br_ex, self.root_helper) and
                    ovs_vdp.is_bridge_present(self.br_integ,
                                              self.root_helper)):
                return True
            else:
                return False
        except Exception as e:
            LOG.error(_LE("Exception in is_openstack_running %s"), str(e))
            return False

    def vdp_uplink_proc_top(self):
        try:
            self.vdp_uplink_proc()
        except Exception as e:
            LOG.error(_LE("VDP uplink proc exception %s"), e)

    def save_uplink(self, uplink="", veth_intf="", fail_reason=""):
        context = {}
        # If uplink physical interface is a part of bond, then this function
        # will be called with uplink=bond0, as an example
        memb_port_list = sys_utils.get_member_ports(uplink)
        args = jsonutils.dumps({'agent': self.host_id, 'uplink': uplink,
                                'veth_intf': veth_intf,
                                'memb_port_list': memb_port_list,
                                'fail_reason': fail_reason})
        msg = self.rpc_clnt.make_msg('save_uplink', context, msg=args)
        try:
            resp = self.rpc_clnt.call(msg)
            return resp
        except rpc.MessagingTimeout:
            LOG.error(_LE("RPC timeout: Failed to save link name on the "
                          "server"))

    def _fill_topology_cfg(self, topo_dict):
        """Fills the extra configurations in the topology. """
        cfg_dict = {}
        if topo_dict.bond_member_ports is not None:
            cfg_dict.update({'bond_member_ports':
                             topo_dict.bond_member_ports})
        if topo_dict.bond_interface is not None:
            cfg_dict.update({'bond_interface':
                             topo_dict.bond_interface})
        return cfg_dict

    def save_topo_disc_params(self, intf, topo_disc_obj):
        context = {}
        topo_cfg = self._fill_topology_cfg(topo_disc_obj)
        args = jsonutils.dumps(
            {'host': self.host_id, 'protocol_interface': intf,
             'heartbeat': time.ctime(),
             'phy_interface': topo_disc_obj.phy_interface,
             'remote_evb_cfgd': topo_disc_obj.remote_evb_cfgd,
             'remote_evb_mode': topo_disc_obj.remote_evb_mode,
             'remote_mgmt_addr': topo_disc_obj.remote_mgmt_addr,
             'remote_system_desc': topo_disc_obj.remote_system_desc,
             'remote_system_name': topo_disc_obj.remote_system_name,
             'remote_port': topo_disc_obj.remote_port,
             'remote_chassis_id_mac': topo_disc_obj.remote_chassis_id_mac,
             'remote_port_id_mac': topo_disc_obj.remote_port_id_mac,
             'configurations': jsonutils.dumps(topo_cfg)})
        msg = self.rpc_clnt.make_msg('save_topo_disc_params', context,
                                     msg=args)
        try:
            resp = self.rpc_clnt.call(msg)
            return resp
        except rpc.MessagingTimeout:
            LOG.error("RPC timeout: Failed to send topo disc on the server")

    def uplink_bond_intf_process(self):
        """Process the case when uplink interface becomes part of a bond.

        This is called to check if the phy interface became a part of the
        bond. If the below condition is True, this means, a physical
        interface that was not a part of a bond was earlier discovered as
        uplink and now that interface became part of the bond.
        Usually, this doesn't happen as LLDP and in turn this function will
        first detect a 'down' followed by an 'up'. When regular interface
        becomes part of bond, it's rare for it to hit this 'normal' case.
        But, still providing the functionality if it happens.
        The following is done :
        a. Bring down the physical interface by sending a 'down' event
        b. Add the bond interface by sending an 'up' event
        Consquently, when bond is added that will be assigned to
        self.phy_uplink. Then, the below condition will be False. i.e..
        'get_bond_intf' will return False, when the argument is 'bond0'.
        """
        bond_intf = sys_utils.get_bond_intf(self.phy_uplink)
        if bond_intf is None:
            return False
        self.save_uplink(
            fail_reason=constants.port_transition_bond_down_reason)
        self.process_uplink_ongoing = True
        upl_msg = VdpQueMsg(constants.UPLINK_MSG_TYPE, status='down',
                            phy_uplink=self.phy_uplink,
                            br_int=self.br_integ, br_ex=self.br_ex,
                            root_helper=self.root_helper)
        self.que.enqueue(constants.Q_UPL_PRIO, upl_msg)
        self.phy_uplink = None
        self.veth_intf = None
        self.uplink_det_compl = False

        # No veth interface
        self.save_uplink(
            uplink=bond_intf,
            fail_reason=constants.port_transition_bond_up_reason)
        self.phy_uplink = bond_intf
        self.process_uplink_ongoing = True
        upl_msg = VdpQueMsg(constants.UPLINK_MSG_TYPE, status='up',
                            phy_uplink=self.phy_uplink,
                            br_int=self.br_integ, br_ex=self.br_ex,
                            root_helper=self.root_helper)
        self.que.enqueue(constants.Q_UPL_PRIO, upl_msg)
        return True

    def check_periodic_bulk_vm_notif_rcvd(self):
        """Bulk VM check handler called from periodic uplink detection.

        This gets called by the 'normal' stage of uplink detection.
        The bulk VM event sends all the VM's running in this agent.
        Sometimes during upgrades, it was found that due to some race
        condition, the server does not send the Bulk VM event.
        Whenever, a save_uplink is done by the agent, the server sends
        the Bulk VM event.
        If Bulk VM event is not received after few attempts, save_uplink is
        done to request the Bulk VM list.
        It's not protected with a mutex, since worst case,
        Bulk VM event will be sent twice, which is not that bad. When
        uplink is detected for the first time, it will hit the below
        else case and there a save_uplink is anyways done.
        """
        if not self.bulk_vm_rcvd_flag:
            if self.bulk_vm_check_cnt >= 1:
                self.bulk_vm_check_cnt = 0
                self.save_uplink(uplink=self.phy_uplink,
                                 veth_intf=self.veth_intf)
                LOG.info(_LI("Doing save_uplink again to request "
                             "Bulk VM's"))
            else:
                LOG.info(_LI("Bulk VM not received, incrementing count"))
                self.bulk_vm_check_cnt += 1

    def static_uplink_detect(self, veth):
        """Return the static uplink based on argument passed.

        The very first time, this function is called, it returns the uplink
        port read from a file.
        After restart, when this function is called the first time, it
        returns 'normal' assuming a veth is passed to this function which will
        be the case if uplink processing is successfully done.
        If user modified the uplink configuration and restarted, a 'down'
        will be returned to clear the old uplink.
        """
        LOG.info(_LI("In static_uplink_detect %(veth)s"), {'veth': veth})
        if self.static_uplink_first:
            self.static_uplink_first = False
            if self.phy_uplink is not None and (
               self.phy_uplink != self.static_uplink_port):
                return 'down'
        if veth is None:
            return self.static_uplink_port
        else:
            return 'normal'

    def vdp_uplink_proc(self):
        """Periodic handler to detect the uplink interface to the switch.

        -> restart_uplink_called: should be called by agent initially to set
           the stored uplink and veth from DB
        -> process_uplink_ongoing: Will be set when uplink message is enqueue
           and reset when dequeued and processed completely
        -> uplink_det_compl: Will be set to True when a valid uplink is
           detected and object created. Will be reset when uplink is down
        -> phy_uplink: Is the uplink interface
        -> veth_intf : Signifies the veth interface.
        """
        LOG.info(_LI("In Periodic Uplink Task"))
        if not self.is_os_run:
            if not self.is_openstack_running():
                LOG.info(_LI("OpenStack is not running"))
                return
            else:
                self.is_os_run = True
        if not self.restart_uplink_called or self.process_uplink_ongoing:
            LOG.info(_LI("Uplink before restart not refreshed yet..states "
                         "%(ruc)d %(puo)d"),
                     {'ruc': self.restart_uplink_called,
                      'puo': self.process_uplink_ongoing})
            return
        if self.phy_uplink is not None:
            if (self.uplink_det_compl and (
               self.phy_uplink not in self.ovs_vdp_obj_dict)):
                LOG.error(_LE("Not Initialized for phy %s"), self.phy_uplink)
                return
            if self.phy_uplink in self.ovs_vdp_obj_dict:
                self.veth_intf = (self.ovs_vdp_obj_dict[self.phy_uplink].
                                  get_lldp_local_bridge_port())
            # The below logic has a bug when agent is started
            # and openstack is not running fixme(padkrish)
            else:
                if self.veth_intf is None:
                    LOG.error(_LE("Incorrect state, Bug"))
                    return
        if self.static_uplink:
            ret = self.static_uplink_detect(self.veth_intf)
        else:
            ret = uplink_det.detect_uplink(self.veth_intf)
        if ret is 'down':
            if self.phy_uplink is None:
                LOG.error(_LE("Wrong status down"))
                return
            # Call API to set the uplink as "" DOWN event
            self.uplink_down_cnt = self.uplink_down_cnt + 1
            if not self.static_uplink and (
               self.uplink_down_cnt < constants.UPLINK_DOWN_THRES):
                return
            self.process_uplink_ongoing = True
            upl_msg = VdpQueMsg(constants.UPLINK_MSG_TYPE,
                                status='down',
                                phy_uplink=self.phy_uplink,
                                br_int=self.br_integ, br_ex=self.br_ex,
                                root_helper=self.root_helper)
            self.que.enqueue(constants.Q_UPL_PRIO, upl_msg)
            self.phy_uplink = None
            self.veth_intf = None
            self.uplink_det_compl = False
            self.uplink_down_cnt = 0
        elif ret is None:
            if self.veth_intf is not None:
                LOG.error(_LE("Wrong status None"))
                return
            # Call API to set the uplink as "" Uplink not discovered yet
            self.save_uplink(fail_reason=constants.uplink_undiscovered_reason)
        elif ret is 'normal':
            if self.veth_intf is None:
                LOG.error(_LE("Wrong status Normal"))
                return
            # Uplink already discovered, nothing to be done here
            # Resetting it back, happens when uplink was down for a very short
            # time and no need to remove flows
            self.uplink_down_cnt = 0
            bond_det = self.uplink_bond_intf_process()
            # Revisit this logic.
            # If uplink detection fails, it will be put in Error queue, which
            # will dequeue and put it back in the main queue
            # At the same time this periodic task will also hit this normal
            # state and will put the message in main queue. fixme(padkrish)
            # The below lines are put here because after restart when
            # eth/veth are passed to uplink script, it will return normal
            # But OVS object would not have been created for the first time,
            # so the below lines ensures it's done.
            if not self.uplink_det_compl and not bond_det:
                if self.phy_uplink is None:
                    LOG.error(_LE("Incorrect state, bug"))
                    return
                self.process_uplink_ongoing = True
                upl_msg = VdpQueMsg(constants.UPLINK_MSG_TYPE,
                                    status='up',
                                    phy_uplink=self.phy_uplink,
                                    br_int=self.br_integ, br_ex=self.br_ex,
                                    root_helper=self.root_helper)
                self.que.enqueue(constants.Q_UPL_PRIO, upl_msg)
                # yield
                LOG.info(_LI("Enqueued Uplink Msg from normal"))
            self.check_periodic_bulk_vm_notif_rcvd()
        else:
            LOG.info(_LI("In Periodic Uplink Task uplink found %s"), ret)
            bond_intf = sys_utils.get_bond_intf(ret)
            if bond_intf is not None:
                ret = bond_intf
                LOG.info(_LI("Interface %(memb)s part of bond %(bond)s") %
                         {'memb': ret, 'bond': bond_intf})
            # Call API to set the uplink as ret
            self.save_uplink(uplink=ret, veth_intf=self.veth_intf)
            self.phy_uplink = ret
            self.process_uplink_ongoing = True
            upl_msg = VdpQueMsg(constants.UPLINK_MSG_TYPE,
                                status='up',
                                phy_uplink=self.phy_uplink,
                                br_int=self.br_integ, br_ex=self.br_ex,
                                root_helper=self.root_helper)
            self.que.enqueue(constants.Q_UPL_PRIO, upl_msg)
            # yield
            LOG.info(_LI("Enqueued Uplink Msg"))

    def vdp_vm_event(self, vm_dict_list):
        if isinstance(vm_dict_list, list):
            vm_msg = VdpQueMsg(constants.VM_BULK_SYNC_MSG_TYPE,
                               vm_bulk_list=vm_dict_list,
                               phy_uplink=self.phy_uplink)
            self.bulk_vm_rcvd_flag = True
        else:
            vm_dict = vm_dict_list
            LOG.info(_LI("Obtained VM event Enqueueing Status %(status)s "
                         "MAC %(mac)s uuid %(uuid)s oui %(oui)s"),
                     {'status': vm_dict['status'], 'mac': vm_dict['vm_mac'],
                      'uuid': vm_dict['net_uuid'], 'oui': vm_dict['oui']})
            vm_msg = VdpQueMsg(constants.VM_MSG_TYPE,
                               port_uuid=vm_dict['port_uuid'],
                               vm_mac=vm_dict['vm_mac'],
                               net_uuid=vm_dict['net_uuid'],
                               segmentation_id=vm_dict['segmentation_id'],
                               status=vm_dict['status'],
                               oui=vm_dict['oui'],
                               phy_uplink=self.phy_uplink)
        self.que.enqueue(constants.Q_VM_PRIO, vm_msg)

    def is_uplink_received(self):
        """Returns whether uplink information is received after restart.

        Not protecting this with a mutex, since this gets called inside the
        loop from dfa_agent and having a mutex is a overkill. Worst case,
        during multiple restarts on server and when the corner case is hit,
        this may return an incorrect value of False when _dfa_uplink_restart
        is at the middle of execution. Returning an incorrect value of False,
        may trigger an RPC to the server to retrieve the uplink one extra time.
        _dfa_uplink_restart will not get executed twice, since that is anyway
        protected with a mutex.
        """
        return self.restart_uplink_called

    def dfa_uplink_restart(self, uplink_dict):
        try:
            with self.vdp_mgr_lock:
                if not self.restart_uplink_called:
                    self._dfa_uplink_restart(uplink_dict)
        except Exception as exc:
            LOG.error(_LE("Exception in dfa_uplink_restart %s") % str(exc))

    def _dfa_uplink_restart(self, uplink_dict):
        LOG.info(_LI("Obtained uplink after restart %s "), uplink_dict)
        # This shouldn't happen
        if self.phy_uplink is not None:
            LOG.error(_LE("Uplink detection already done %s"), self.phy_uplink)
            return
        uplink = uplink_dict.get('uplink')
        veth_intf = uplink_dict.get('veth_intf')
        # Logic is as follows:
        # If DB didn't have any uplink it means it's not yet detected or down
        # if DB has uplink and veth, then no need to scan all ports we can
        # start with this veth.
        # If uplink has been removed or modified during restart, then a
        # down will be returned by uplink detection code and it will be
        # removed then.
        # If DB has uplink, but no veth, it's an error condition and in
        # which case remove the uplink port from bridge and start fresh
        if uplink is None or len(uplink) == 0:
            LOG.info(_LI("uplink not discovered yet"))
            self.restart_uplink_called = True
            return
        if veth_intf is not None and len(veth_intf) != 0:
            LOG.info(_LI("veth interface is already added, %(ul)s %(veth)s"),
                     {'ul': uplink, 'veth': veth_intf})
            self.phy_uplink = uplink
            self.veth_intf = veth_intf
            self.restart_uplink_called = True
            return
        LOG.info(_LI("Error case removing the uplink %s from bridge"), uplink)
        ovs_vdp.delete_uplink_and_flows(self.root_helper, self.br_ex, uplink)
        self.restart_uplink_called = True
