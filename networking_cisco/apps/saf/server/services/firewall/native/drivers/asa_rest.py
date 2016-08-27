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

#
# Openstack driver for cisco ASA firewall
#

import base64
import netaddr
from networking_cisco.apps.saf.common import dfa_logger as logging
from oslo_serialization import jsonutils
try:
    import urllib2
except ImportError:
    import urllib.request as urllib2

from networking_cisco._i18n import _LE, _LI

LOG = logging.getLogger(__name__)


class Asa5585(object):
    """ASA 5585 Driver. """

    def __init__(self, mgmt_ip, username, password):
        self.server = "https://" + mgmt_ip
        self.username = username
        self.password = password
        self.tenant_rule = dict()
        self.rule_tbl = dict()

    def rest_send_cli(self, data):
        headers = {'Content-Type': 'application/json'}
        api_path = "/api/cli"    # param
        url = self.server + api_path

        # Use request library instead of urllib2. Also for status codes,
        # use the literals provided by request library, instead of hardcoding.
        # TODO(padkrish)
        req = urllib2.Request(url, jsonutils.dumps(data), headers)
        byte_str = ('%s:%s' % ('user', 'user')).encode()
        base64string = base64.encodestring(byte_str).decode().replace('\n', '')

        req.add_header("Authorization", "Basic %s" % base64string)
        f = None
        status_code = 400
        try:
            f = urllib2.urlopen(req)
            status_code = f.getcode()
            LOG.info(_LI("Status code is %d"), status_code)

        except (urllib2.HTTPError, netaddr.err):
            LOG.error(_LE("Error received from server. HTTP status code "
                      "is %d"), netaddr.err.code)
            try:
                json_error = jsonutils.loads(netaddr.err.read())
                if json_error:
                    LOG.error(_LE("Error in Json Loads"),
                              jsonutils.dumps(json_error, sort_keys=True,
                                              indent=4,
                                              separators=(',', ': ')))
            except ValueError:
                pass
        finally:
            if f:
                f.close()
        return (status_code in range(200, 300))

    def setup(self, **kwargs):
        """setup ASA context for an edge tenant pair. """
        params = kwargs.get('params')
        LOG.info(_LI("asa_setup: tenant %(tenant)s %(in_vlan)d %(out_vlan)d"
                     " %(in_ip)s %(in_mask)s %(out_ip)s %(out_mask)s"),
                 {'tenant': params.get('tenant_name'),
                  'in_vlan': params.get('in_vlan'),
                  'out_vlan': params.get('out_vlan'),
                  'in_ip': params.get('in_ip'),
                  'in_mask': params.get('in_mask'),
                  'out_ip': params.get('out_ip'),
                  'out_mask': params.get('out_mask')})
        inside_vlan = str(params.get('in_vlan'))
        outside_vlan = str(params.get('out_vlan'))
        context = params.get('tenant_name')
        cmds = ["conf t", "changeto system"]
        inside_int = params.get('intf_in') + '.' + inside_vlan
        cmds.append("int " + inside_int)
        cmds.append("vlan " + inside_vlan)
        outside_int = params.get('intf_out') + '.' + outside_vlan
        cmds.append("int " + outside_int)
        cmds.append("vlan " + outside_vlan)
        cmds.append("context " + context)
        cmds.append("allocate-interface " + inside_int)
        cmds.append("allocate-interface " + outside_int)
        cmds.append("config-url disk0:/" + context + ".cfg")
        cmds.append("write memory")
        cmds.append("changeto context " + context)
        cmds.append("int " + inside_int)
        cmds.append("nameif Inside")
        cmds.append("security-level 100")
        cmds.append(
            "ip address " + params.get('in_ip') + " " + params.get('in_mask'))
        cmds.append("int " + outside_int)
        cmds.append("nameif Outside")
        cmds.append("security-level 0")
        cmds.append("ip address " + params.get('out_ip') + " " +
                    params.get('out_mask'))

        cmds.append("router ospf 1")
        cmds.append("network " + params.get('in_ip') + " " +
                    params.get('in_mask') + " area 0")
        cmds.append("network " + params.get('out_ip') + " " +
                    params.get('out_mask') + " area 0")
        cmds.append("area 0")
        cmds.append("route Outside 0.0.0.0 0.0.0.0 " + params.get('out_gw') +
                    " 1")
        cmds.append("route Outside 0.0.0.0 0.0.0.0 " +
                    params.get('out_sec_gw') + " 1")
        cmds.append("end")
        cmds.append("write memory")

        if context not in self.tenant_rule:
            self.tenant_rule[context] = dict()
            self.tenant_rule[context]['rule_lst'] = []

        data = {"commands": cmds}
        return self.rest_send_cli(data)

    def cleanup(self, **kwargs):
        """cleanup ASA context for an edge tenant pair. """
        params = kwargs.get('params')
        LOG.info(_LI("asa_cleanup: tenant %(tenant)s %(in_vlan)d %(out_vlan)d"
                     " %(in_ip)s %(in_mask)s %(out_ip)s %(out_mask)s"),
                 {'tenant': params.get('tenant_name'),
                  'in_vlan': params.get('in_vlan'),
                  'out_vlan': params.get('out_vlan'),
                  'in_ip': params.get('in_ip'),
                  'in_mask': params.get('in_mask'),
                  'out_ip': params.get('out_ip'),
                  'out_mask': params.get('out_mask')})
        inside_vlan = str(params.get('in_vlan'))
        outside_vlan = str(params.get('out_vlan'))
        context = params.get('tenant_name')
        cmds = ["conf t", "changeto system"]
        cmds.append("no context " + context + " noconfirm")
        inside_int = params.get('intf_in') + '.' + inside_vlan
        outside_int = params.get('intf_out') + '.' + outside_vlan
        cmds.append("no interface " + inside_int)
        cmds.append("no interface " + outside_int)
        cmds.append("write memory")
        cmds.append("del /noconfirm disk0:/" + context + ".cfg")

        if context in self.tenant_rule:
            for rule in self.tenant_rule[context].get('rule_lst'):
                del self.rule_tbl[rule]
            del self.tenant_rule[context]
        data = {"commands": cmds}
        return self.rest_send_cli(data)

    def get_quota(self):
        cmds = ["conf t", "changeto system"]
        cmds.append("show ver | grep Contexts")
        data = {"commands": cmds}
        headers = {'Content-Type': 'application/json'}
        api_path = "/api/cli"    # param
        url = self.server + api_path

        req = urllib2.Request(url, jsonutils.dumps(data), headers)
        byte_str = ('%s:%s' % ('user', 'user')).encode()
        base64string = base64.encodestring(byte_str).decode().replace('\n', '')
        req.add_header("Authorization", "Basic %s" % base64string)
        max_ctx_count = 0
        f = None
        try:
            f = urllib2.urlopen(req)
            status_code = f.getcode()
            LOG.info(_LI("Status code is %d"), status_code)
            if status_code in range(200, 300):
                resp = jsonutils.loads(f.read())
                try:
                    max_ctx_count = int(resp.get('response')[-1].split()[3])
                except ValueError:
                    max_ctx_count = 0
                LOG.info(_LI("Max Context Count is %d"), max_ctx_count)

        except (urllib2.HTTPError, netaddr.err):
            LOG.info(_LI("Error received from server. HTTP status code is %d"),
                     netaddr.err.code)
            try:
                json_error = jsonutils.loads(netaddr.err.read())
                if json_error:
                    LOG.info(_LI("Error in Json loads"),
                             jsonutils.dumps(json_error, sort_keys=True,
                                             indent=4,
                                             separators=(',', ': ')))
            except ValueError:
                pass
        finally:
            if f:
                f.close()
        return max_ctx_count

    def get_ip_address(self, ip_address):
        """Decode the IP address. """
        if ip_address is None:
            ip_address = '0.0.0.0/0'
        return netaddr.IPNetwork(ip_address)

    def build_acl_ip(self, network_obj):
        "Build the acl for IP address. "

        if str(network_obj) == '0.0.0.0/0':
            acl = "any "
        else:
            acl = "%(ip)s %(mask)s " % {'ip': network_obj.network,
                                        'mask': network_obj.netmask}
        return acl

    def build_acl_port(self, port, enabled=True):
        "Build the acl for L4 Ports. "
        if port is not None:
            if ':' in port:
                range = port.replace(':', ' ')
                acl = "range %(range)s " % {'range': range}
            else:
                acl = "eq %(port)s " % {'port': port}
                if not enabled:
                    acl += "inactive"
            return acl

    def build_acl(self, tenant_name, rule):
        """Build the ACL. """
        # TODO(padkrish) actions that is not deny or allow, throw error
        if rule['action'] == 'allow':
            action = 'permit'
        else:
            action = 'deny'
        acl_str = "access-list %(tenant)s extended %(action)s %(prot)s "
        acl = acl_str % {'tenant': tenant_name, 'action': action,
                         'prot': rule.get('protocol')}
        src_ip = self.get_ip_address(rule.get('source_ip_address'))
        ip_acl = self.build_acl_ip(src_ip)
        acl += ip_acl

        acl += self.build_acl_port(rule.get('source_port'))

        dst_ip = self.get_ip_address(rule.get('destination_ip_address'))
        ip_acl = self.build_acl_ip(dst_ip)
        acl += ip_acl

        acl += self.build_acl_port(rule.get('destination_port'),
                                   enabled=rule.get('enabled'))
        return acl

    def apply_policy(self, policy):
        """Apply a firewall policy. """
        tenant_name = policy['tenant_name']
        fw_id = policy['fw_id']
        fw_name = policy['fw_name']
        LOG.info(_LI("asa_apply_policy: tenant=%(tenant)s fw_id=%(fw_id)s "
                     "fw_name=%(fw_name)s"),
                 {'tenant': tenant_name, 'fw_id': fw_id, 'fw_name': fw_name})
        cmds = ["conf t", "changeto context " + tenant_name]

        for rule_id, rule in policy['rules'].items():
            acl = self.build_acl(tenant_name, rule)

            LOG.info(_LI("rule[%(rule_id)s]: name=%(name)s enabled=%(enabled)s"
                         " protocol=%(protocol)s dport=%(dport)s "
                         "sport=%(sport)s dip=%(dport)s "
                         "sip=%(sip)s action=%(dip)s"),
                     {'rule_id': rule_id, 'name': rule.get('name'),
                      'enabled': rule.get('enabled'),
                      'protocol': rule.get('protocol'),
                      'dport': rule.get('dst_port'),
                      'sport': rule.get('src_port'),
                      'dip': rule.get('destination_ip_address'),
                      'sip': rule.get('source_ip_address'),
                      'action': rule.get('action')})

            # remove the old ace for this rule
            if rule_id in self.rule_tbl:
                cmds.append('no ' + self.rule_tbl[rule_id])

            self.rule_tbl[rule_id] = acl
            if tenant_name in self.tenant_rule:
                if rule_id not in self.tenant_rule[tenant_name]['rule_lst']:
                    self.tenant_rule[tenant_name]['rule_lst'].append(rule_id)
            cmds.append(acl)
        cmds.append("access-group " + tenant_name + " global")
        cmds.append("write memory")

        LOG.info(_LI("cmds sent is %s"), cmds)
        data = {"commands": cmds}
        return self.rest_send_cli(data)
