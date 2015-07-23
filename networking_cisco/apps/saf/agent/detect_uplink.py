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


import os
import subprocess
import sys
import time

from networking_cisco.apps.saf.common import dfa_logger as logging

LOG = logging.getLogger(__name__)

uplink_file_path = '/tmp/uplink'
detect_uplink_file_path = '/tmp/uplink_detected'


def run_cmd_line(cmd_str, stderr=None, shell=True,
                 echo_cmd=False, check_result=False):
    if echo_cmd:
        LOG.debug(cmd_str)
    if shell:
        cmd_args = cmd_str
    else:
        cmd_args = cmd_str.split()
    output = None
    returncode = 0
    try:
        output = subprocess.check_output(cmd_args, shell=shell, stderr=stderr)
    except subprocess.CalledProcessError as e:
        if check_result:
            LOG.debug(e)
            sys.exit(e.returncode)
        else:
            returncode = e.returncode
    return output, returncode


def read_file(file_name):
    file_content = None
    if os.path.isfile(file_name):
        filep = open(file_name, "r")
        file_content = filep.read()
        filep.close()
        file_content = file_content.replace("\n", "")
    return file_content


def find_uplink():
    intf_cmd_list = ("ip link |grep 'state UP' | awk '{print $2}' "
                     "| sed 's/://'|grep ^[epb]")
    intf_net_addr = "ifconfig %s | grep 'inet addr'"
    en_rxtx = ('sudo /usr/sbin/lldptool -i %s -g "ncb" -L adminStatus=rxtx')
    dis_rxtx = ('sudo /usr/sbin/lldptool -i %s -g "ncb" -L '
                'adminStatus=disabled')
    mod_brdg = ('sudo /usr/sbin/lldptool -i %s -g "ncb" -t -n -V evb | '
                'grep "mode:bridge"')

    intf_list, returncode = run_cmd_line(intf_cmd_list)
    for intf in intf_list.split():
        intf_out, retcode = run_cmd_line(intf_net_addr % intf)
        if intf_out is None:
            out, ret = run_cmd_line(en_rxtx % intf)
            time.sleep(40)
            out, ret = run_cmd_line(mod_brdg % intf)
            run_cmd_line(dis_rxtx % intf)
            if out:
                return intf


def detect_uplink_non_auto(input_string):
    file_str = "normal"
    if input_string is None:
        file_str = read_file(uplink_file_path)
    return file_str


def detect_uplink_auto(input_string):
    if input_string is None:
        return_str = find_uplink()
    else:
        cmd_str = ('sudo /usr/sbin/lldptool -i %s -g "ncb" -t -n -V evb | '
                   'grep "mode:bridge"') % input_string
        (output, returncode) = run_cmd_line(cmd_str,
                                            check_result=False)
        if returncode == 0:
            return_str = "normal"
        else:
            return_str = "down"

    LOG.debug('return_str=%s', return_str)
    return return_str


def detect_uplink(input_string=None):
    auto_detect = False
    if os.path.isfile(uplink_file_path):
        detected_uplink = detect_uplink_non_auto(input_string)
    else:
        detected_uplink = detect_uplink_auto(input_string)
        auto_detect = True
    log_str = "auto detect = %s, input string %s, detected uplink is %s." % (
        auto_detect, input_string, detected_uplink)
    LOG.debug(log_str)
    return detected_uplink
