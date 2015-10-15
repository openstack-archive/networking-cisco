# Copyright 2014 Cisco Systems, Inc.  All rights reserved.
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


# This class is used instead of the L3AgentNotifyAPI to effectively
# disable notifications from the l3 base class to the l3 agents.
class L3AgentNotifyAPINoOp(object):
    """API for plugin to notify L3 agent but without actions."""
    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, topic=None):
        pass

    def agent_updated(self, context, admin_state_up, host):
        pass

    def router_deleted(self, context, router_id):
        pass

    def routers_updated(self, context, routers, operation=None, data=None):
        pass

    def router_removed_from_agent(self, context, router_id, host):
        pass

    def router_added_to_agent(self, context, routers, host):
        pass

L3AgentNotifyNoOp = L3AgentNotifyAPINoOp()
