# Copyright (c) 2013-2016 Cisco Systems, Inc.
# All rights reserved.
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


"""
Cisco Nexus-OS XML-based configuration snippets.
"""


# The following are standard strings, messages used to communicate with Nexus.
EXEC_CONF_SNIPPET = """
      <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0">
        <configure>
          <__XML__MODE__exec_configure>%s
          </__XML__MODE__exec_configure>
        </configure>
      </config>
"""

EXEC_GET_INTF_SNIPPET = """
    <cmd>show running-config interface %s %s</cmd>
"""

EXEC_GET_VERSION_SNIPPET = """
    <cmd>show version</cmd>
"""

EXEC_GET_INVENTORY_SNIPPET = """
    <cmd>show inventory</cmd>
"""

EXEC_SAVE_CONF_SNIPPET = """
            <cmd>copy running-config startup-config</cmd>
"""

# 'show run vlan' was selected over 'show vlan' because the latter does not
# show vn-segment information
EXEC_GET_VLAN_SNIPPET = """
    <cmd>show run vlan</cmd>
"""

CMD_VLAN_CONF_SNIPPET = """
            <vlan>
              <vlan-id-create-delete>
                <__XML__PARAM_value>%s</__XML__PARAM_value>
                <__XML__MODE_vlan>
                  <name>
                    <vlan-name>%s</vlan-name>
                  </name>
                </__XML__MODE_vlan>
              </vlan-id-create-delete>
            </vlan>
"""

CMD_VLAN_CONF_VNSEGMENT_SNIPPET = """
            <vlan>
              <vlan-id-create-delete>
                <__XML__PARAM_value>%s</__XML__PARAM_value>
                <__XML__MODE_vlan>
                  <vn-segment>
                    <vlan-vnsegment>%s</vlan-vnsegment>
                  </vn-segment>
                </__XML__MODE_vlan>
              </vlan-id-create-delete>
            </vlan>
"""

CMD_VLAN_CREATE_SNIPPET = """
            <vlan>
              <vlan-id-create-delete>
                <__XML__PARAM_value>%s</__XML__PARAM_value>
              </vlan-id-create-delete>
            </vlan>
"""

CMD_VLAN_ACTIVE_SNIPPET = """
            <vlan>
              <vlan-id-create-delete>
                <__XML__PARAM_value>%s</__XML__PARAM_value>
                <__XML__MODE_vlan>
                  <state>
                    <vstate>active</vstate>
                  </state>
                </__XML__MODE_vlan>
              </vlan-id-create-delete>
            </vlan>
"""

CMD_VLAN_NO_SHUTDOWN_SNIPPET = """
            <vlan>
              <vlan-id-create-delete>
                <__XML__PARAM_value>%s</__XML__PARAM_value>
                <__XML__MODE_vlan>
                  <no>
                    <shutdown/>
                  </no>
                </__XML__MODE_vlan>
              </vlan-id-create-delete>
            </vlan>
"""

CMD_NO_VLAN_CONF_SNIPPET = """
          <no>
          <vlan>
            <vlan-id-create-delete>
              <__XML__PARAM_value>%s</__XML__PARAM_value>
            </vlan-id-create-delete>
          </vlan>
          </no>
"""

CMD_INT_VLAN_NATIVE_HEADER = """
                    <native>
                      <vlan>"""

CMD_INT_VLAN_NATIVE_TRAILER = """
                      </vlan>
                    </native>
"""

CMD_INT_VLAN_ALLOWED_HEADER = """
                    <allowed>
                      <vlan>"""

CMD_INT_VLAN_ALLOWED_TRAILER = """
                      </vlan>
                    </allowed>
"""

CMD_INT_VLAN_HEADER = """
          <interface>
            <%s>
              <interface>%s</interface>
              <__XML__MODE_if-ethernet-switch>
                <switchport>
                  <trunk>"""

CMD_VLAN_ID = """
                          <vlan_id>%s</vlan_id>"""

CMD_VLAN_ADD_ID = """
                        <add>%s
                        </add>""" % CMD_VLAN_ID

CMD_INT_VLAN_TRAILER = """
                  </trunk>
                </switchport>
              </__XML__MODE_if-ethernet-switch>
            </%s>
          </interface>
"""

CMD_INT_VLAN_SNIPPET = (CMD_INT_VLAN_HEADER +
                        CMD_INT_VLAN_ALLOWED_HEADER +
                        CMD_VLAN_ID +
                        CMD_INT_VLAN_ALLOWED_TRAILER +
                        CMD_INT_VLAN_TRAILER)

CMD_INT_VLAN_ADD_SNIPPET = (CMD_INT_VLAN_HEADER +
                            CMD_INT_VLAN_ALLOWED_HEADER +
                            CMD_VLAN_ADD_ID +
                            CMD_INT_VLAN_ALLOWED_TRAILER +
                            CMD_INT_VLAN_TRAILER)

CMD_INT_VLAN_NATIVE_SNIPPET = (CMD_INT_VLAN_HEADER +
                               CMD_INT_VLAN_NATIVE_HEADER +
                               CMD_VLAN_ID +
                               CMD_INT_VLAN_NATIVE_TRAILER +
                               CMD_INT_VLAN_TRAILER)


CMD_PORT_TRUNK = """
          <interface>
            <%s>
              <interface>%s</interface>
              <__XML__MODE_if-ethernet-switch>
                <switchport></switchport>
                <switchport>
                  <mode>
                    <trunk>
                    </trunk>
                  </mode>
                </switchport>
              </__XML__MODE_if-ethernet-switch>
            </%s>
          </interface>
"""

CMD_NO_SWITCHPORT = """
          <interface>
            <%s>
              <interface>%s</interface>
              <__XML__MODE_if-ethernet-switch>
                <no>
                  <switchport>
                  </switchport>
                </no>
              </__XML__MODE_if-ethernet-switch>
            </%s>
          </interface>
"""

CMD_NO_VLAN_INT_SNIPPET = """
          <interface>
            <%s>
              <interface>%s</interface>
              <__XML__MODE_if-ethernet-switch>
                <switchport></switchport>
                <switchport>
                  <trunk>
                    <allowed>
                      <vlan>
                        <remove>
                          <vlan>%s</vlan>
                        </remove>
                      </vlan>
                    </allowed>
                  </trunk>
                </switchport>
              </__XML__MODE_if-ethernet-switch>
            </%s>
          </interface>
"""

CMD_NO_VLAN_INT_NATIVE_SNIPPET = """
          <interface>
            <%s>
              <interface>%s</interface>
              <__XML__MODE_if-ethernet-switch>
                <switchport></switchport>
                <no>
                  <switchport>
                    <trunk>
                      <native>
                        <vlan>
                        </vlan>
                      </native>
                    </trunk>
                  </switchport>
                </no>
              </__XML__MODE_if-ethernet-switch>
            </%s>
          </interface>
"""
CMD_VLAN_SVI_SNIPPET = """
<interface>
    <vlan>
        <vlan>%s</vlan>
        <__XML__MODE_vlan>
            <no>
              <shutdown/>
            </no>
            <ip>
                <address>
                    <address>%s</address>
                </address>
            </ip>
        </__XML__MODE_vlan>
    </vlan>
</interface>
"""

CMD_NO_VLAN_SVI_SNIPPET = """
<no>
    <interface>
        <vlan>
            <vlan>%s</vlan>
        </vlan>
    </interface>
</no>
"""

CMD_INT_NVE_SNIPPET = """
<interface>
    <nve>nve%s</nve>
    <__XML__MODE_if-nve>
        <noshut>no shutdown</noshut>
        <srcint>source-interface loopback %s</srcint>
    </__XML__MODE_if-nve>
</interface>
"""

CMD_NO_INT_NVE_SNIPPET = """
<nonve>no interface nve %s</nonve>
"""

CMD_INT_NVE_MEMBER_SNIPPET = """
<interface>
    <nve>nve%s</nve>
    <__XML__MODE_if-nve>
        <member>member vni %s mcast-group %s</member>
    </__XML__MODE_if-nve>
</interface>
"""

CMD_INT_NVE_NO_MEMBER_SNIPPET = """
<interface>
    <nve>nve%s</nve>
    <__XML__MODE_if-nve>
        <member>no member vni %s</member>
    </__XML__MODE_if-nve>
</interface>
"""

CMD_FEATURE_VXLAN_SNIPPET = """
<feature>feature nv overlay</feature>
<feature>feature vn-segment-vlan-based</feature>
"""

# Removing the "feature nv overlay" configuration also removes the
# "interface nve" configuration.
CMD_NO_FEATURE_VXLAN_SNIPPET = """
<feature>no feature nv overlay</feature>
<feature>no feature vn-segment-vlan-based</feature>
"""

# REGEX SNIPPETS For extracting data from get calls

RE_GET_VLAN_ID = "vlanid-utf\>(\d+)\<"
RE_GET_VLAN_NAME = "vlanname\>([\x21-\x7e]+)\<"
RE_GET_VLAN_STATE = "vlanstate\>(\w+)\<"
RE_GET_VLAN_SHUT_STATE = "shutstate\>([a-z]+)\<"
