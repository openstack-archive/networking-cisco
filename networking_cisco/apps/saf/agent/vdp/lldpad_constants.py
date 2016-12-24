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

"""Service VDP 2.2 constants."""

MINIMUM_VDP22_VERSION = "0.9.45"
VDP_MGRID = 0
VDP_TYPEID = 0
VDP_TYPEID_VER = 0
VDP_VSIFRMT_UUID = 5
VDP_FILTER_VID = 1
VDP_FILTER_MACVID = 2
VDP_FILTER_GIDVID = 3
VDP_FILTER_GIDMACVID = 4
VDP_SYNC_TIMEOUT = 15
CALLBACK_THRESHOLD = 5

verify_failure_reason = "vsi_id mismatch, queried %s, returned %s"
retrieve_failure_reason = "Unable to retrieve failure, reply %s"
mode_failure_reason = "Incorrect Reply,no mode information found: %s"
filter_failure_reason = "Incorrect Reply,no filter information found: %s"
multiple_filter_failure_reason = \
    "Incorrect Reply,multiple filter information found: %s"
format_failure_reason = "Reply not formatted correctly: %s"
hints_failure_reason = "Incorrect Reply,no hints information found: %s"
multiple_hints_failure_reason = \
    "Incorrect Reply,multiple hints information found: %s"
nonzero_hints_failure = "Non-zero hints, value %d"
vsi_mismatch_failure_reason = "VSIID Reply mis-match req vsi %s reply vsi %s"
mac_mismatch_failure_reason = \
    "VSIID MAC Reply mis-match req mac %s reply mac %s"
