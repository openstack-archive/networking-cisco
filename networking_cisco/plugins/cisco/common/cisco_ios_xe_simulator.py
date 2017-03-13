# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
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

# A tiny and simple Cisco IOS XE running config simulator.
# The intended use is to allow a developer to observe how the running config
# of an IOS XE device evolves as CLI commands are issued.
#
# Simple implies here that no CLI syntax or semantical checks are made so it
# is entirely up to the command issuer to ensure the correctness of the
# commands and their arguments.
#
# Bob Melander (bob.melander@gmail.com)

import re
import six

from oslo_utils import timeutils


class CiscoIOSXESimulator(object):

    # set of commands to be logged only
    log_only_commands = set()
    # set of commands bound to immediately preceding line
    parent_bound_commands = {'exit-address-family'}
    exclamation = {'vrf definition', ' exit-address-family'}

    def __init__(self, path, host_ip, netmask, port, username, password,
                 device_params, mgmt_interface, timeout):
        self.host_ip = host_ip
        self.netmask = netmask
        self.port = port
        self.username = username
        self.password = password
        self.device_params = device_params
        self.mgmt_interface = mgmt_interface
        self.timeout = timeout
        self.last_update = timeutils.utcnow()
        self.rc = self._get_dict()
        self._set_default_config()

    def get_config(self):
        change_date = timeutils.strtime(self.last_update, '%a %b %d %Y')
        change_time = timeutils.strtime(self.last_update, '%H:%M:%S')
        intro_lines = ("! Last configuration change at " + change_time + " " +
                       "UTC " + change_date + " by " + self.username + "\n!\n")
        intro_lines += ("hostname ASR-1002X-" +
                        self.host_ip.replace('.', '_') + "\n!\n")
        intro_lines += ("boot-start-marker\nboot system flash "
                        "bootflash:/asr1002x-simulated.03.16.00.S-ext."
                        "SPA.bin\nboot-end-marker\n!\n")
        rc_data = {'rc_str': intro_lines}
        cmds = sorted(self.rc.keys())
        if 'vrf' in cmds:
            cmds.remove('vrf')
            cmds.insert(0, 'vrf')
        #for cmd, args in sorted(six.iteritems(self.rc)):
        for cmd in cmds:
            args = self.rc[cmd]
            line = cmd
            self._build_line(rc_data, args, line, 0)
        print(rc_data['rc_str'])
        return rc_data['rc_str']

    def edit_config(self, snippet):
        command_lines = self._get_command_lines(snippet)
        if not command_lines:
            return
        self._process_next_level(self.rc, self.rc, command_lines, None, True)
        self.last_update = timeutils.utcnow()
        return True

    def _set_default_config(self):
        mgmt_gw_ip = '.'.join((self.host_ip.split('.')[:-1]) + ['1'])
        command_chunks = [
            ["vrf definition Mgmt-intf",
             "address-family ipv4",
             "exit-address-family",
             "address-family ipv6",
             "exit-address-family"],
            ["interface " + self.mgmt_interface,
             "vrf forwarding Mgmt-intf",
             "ip address " + self.host_ip + " " + self.netmask,
             "negotiation auto"],
            ["ip tftp source - interface " + self.mgmt_interface],
            ["ip route vrf Mgmt - intf 0.0.0.0 0.0.0.0 " + mgmt_gw_ip],
            ["ip ssh source - interface " + self.mgmt_interface],
            ["ip ssh version 2"]
        ]
        for commands in command_chunks:
            self._process_next_level(self.rc, self.rc, commands, None, True)

    def _build_line(self, rc_data, current, baseline, level):
        for string, the_rest in sorted(six.iteritems(current)):
            if string == 'EOL':
                continue
            #line = baseline
            line = " " if baseline == "" and level >= 1 else baseline
            #line += ' ' + string if line != "" else string
            line += ' ' + string if line != "" and line != " " else string
            if 'EOL' in the_rest:
                #termination = "\n!\n" if self._to_exclamate(line) else "\n"
                if self._to_exclamate(line):
                    termination = "\n !\n" if level >= 1 else "\n!\n"
                else:
                    #termination = " \n" if level == 1 else "\n"
                    termination = "\n"
                rc_data['rc_str'] += line + termination
                line = ""
            self._build_line(rc_data, the_rest, line, level + 1)
            if level == 0:
                rc_data['rc_str'] += "!\n"

    def _to_exclamate(self, line):
        for statement in self.exclamation:
            if line.startswith(statement):
                return True
        return False

    def _process_next_level(self, parent, current, remaining_lines,
                            last_processed, is_root=False):
        if not remaining_lines:
            return
        pre, cmd_line = self._get_command_prepending(remaining_lines[0])
        if pre is None:
            self._process_set(cmd_line, parent, current,
                              remaining_lines, last_processed, is_root)
        elif pre.lower() == "no":
            self._process_unset(cmd_line.split(" "), current)

    def _process_set(self, cmd_line, parent, current, remaining_lines,
                     last_processed, is_root):
        cmd, args = self._get_command_and_args(cmd_line)
        if cmd in self.log_only_commands:
            self._process_next_level(parent, current,
                                     remaining_lines[1:], last_processed)
            return
        if cmd in self.parent_bound_commands:
            this_one = last_processed.get(cmd)
            start = last_processed
        else:
            this_one = parent.get(cmd)
            start = current
        if this_one is None:
            this_one, current_parent = self._get_successor_and_its_parent(
                parent, cmd, start, is_root)
        else:
            current_parent = start
        for arg in args:
            next_one, current_parent = self._get_successor_and_its_parent(
                current_parent, arg, this_one, is_root)
            this_one = next_one
        this_one['EOL'] = True
        if is_root is True:
            current = this_one
        self._process_next_level(current_parent, current, remaining_lines[1:],
                                 this_one)

    def _process_unset(self, remaining, current):
        if not remaining:
            return
        arg = remaining[0]
        rest = remaining[1:]
        if arg in current:
            if not rest:
                del current[arg]
            else:
                self._process_unset(rest, current[arg])
                num_items = len(current[arg])
                if num_items == 0:
                    del current[arg]

    def _get_successor_and_its_parent(self, parent, string, current, is_root):
        successor = current.get(string)
        if successor is None:
            successor = self._get_dict()
            current[string] = successor
            current_parent = parent if is_root is False else successor
        else:
            current_parent = current
        return successor, current_parent

    def _get_command_lines(self, snippet):
        if not snippet:
            return []
        lines = snippet.split('\n')
        commands = []
        for line in lines:
            if self._should_skip_line(line):
                continue
            cmd = self._get_embedded_command_string(line)
            if cmd is not None:
                commands.append(cmd)
        return commands

    def _should_skip_line(self, line):
        if line == "":
            return True
        if line.find("config>") != -1:
            return True
        elif line.find("cli-config-data>") != -1:
            return True
        return False

    def _get_embedded_command_string(self, line):
        match_obj = re.match(r'\s*<cmd>(.*)</cmd>\s*', line)
        if match_obj:
            return match_obj.group(1)
        return None

    def _get_command_prepending(self, cmd):
        match_obj = re.match(r'\s*(no|do) (.*)\s*', cmd)
        if match_obj:
            return match_obj.group(1), match_obj.group(2)
        return None, cmd

    def _get_command_and_args(self, cmd_line):
        str_list = cmd_line.split(" ")
        return str_list[0], str_list[1:]

    def _get_dict(self):
        return {}


# A simple Cisco IOS XE CLI simulator
class FakeRunningConfig(object):
    def __init__(self, rc):
        self._raw = rc
