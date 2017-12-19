================================================
Nexus Mechanism Driver Overview and Architecture
================================================

Introduction
~~~~~~~~~~~~
The ML2 Nexus driver adds and removes trunk vlans on the Cisco Nexus switch
for both ethernet interfaces and port-channel interfaces.  It also supports
configuration of VXLAN Overlay, baremetal deployments (VLAN configurations
only), and performs configuration replay on switch recovery.

This user guide describes the activities the Nexus driver performs to create
and remove VLANS on receipt of OpenStack ML2 baremetal and non-baremetal port
events.

.. _nexus_vlan_create:

VLAN Creation
~~~~~~~~~~~~~
When VMs are created or when subnets are created with dhcp is enabled, port
events are received by the Nexus driver.  If there are switch credentials
defined by the administrator for the event, then the Nexus driver will
process the event.

The basic Nexus configuration actions taken by the Nexus driver are
as follows:

#. Configure the provided VLAN on the Nexus device,
#. Configure the interface as :command:`switchport mode trunk` and
   :command:`switchport trunk allowed vlan none` if no trunk vlans
   have been configured manually by the user.
#. Add a trunk vlan onto the specified interface using the interface
   CLI :command:`switchport trunk allowed vlan add <vlanid>`.
#. For baremetal port events, if the port is the `parent` port to an
   OpenStack trunking configuration or not a participant of an OpenStack
   trunking configuration, the VLAN is also configured as `native`
   using the CLI :command:`switchport trunk native vlan <vlanid>`.

Both normal VM port events and baremetal port events are supported by
the Nexus Driver for VLAN creation.  They can co-exist at the same
time.

In the case of non-baremetal port events, the Nexus driver uses the
host name from the port event to identify a switch and interface(s)
to configure.  The vlan used to configure the interface also comes
from the port event.  The administrator configures the host to
interface mapping as well as switch credentials in the ML2 Nexus
Driver switch configuration section of the neutron config file.
(ref: section header ``ml2_mech_cisco_nexus`` of config file shown
in the :doc:`/admin/ml2-nexus`.)

In the case of baremetal port events, the switch and interface mapping
are contained in the event itself.  The Nexus driver learns the
host to interface mapping by using dns name as the host name.  If
dns is not enabled, then the host name defaults to ``reserved_port``.
Even though the administrator does not configure this mapping,
the switch credentials must be configured for baremetal events.
This configuration aides in determining whether the baremetal
event is for the Nexus Driver.

If there are multiple ethernet interfaces defined in the baremetal event,
this implies it is a port-channel.  When the Nexus driver detects
multiple interfaces, it next determines whether the interfaces are
already configured as members of a port-channel. If not, it creates
a new port-channel interface and adds the ethernet interfaces as
members.  In more detail, it will do the following:

#. Allocate a port-channel id from ``vpc_pool`` configured by administrator
   ref: ``vpc_pool`` variable in admin and config guides).
#. Create the port-channel which includes :command:`switchport mode trunk`,
   :command:`switchport trunk allowed vlan none`,  and :command:`vpc-id x`.
#. Apply either user customized port-channel config provided by
   administrator OR the default config :command:`spanning-tree port type edge
   trunk` and :command:`no lacp suspend-individual`
   (refer to ``intfcfg_portchannel`` variable in the Nexus
   :doc:`administration </admin/ml2-nexus>`
   and :doc:`configuration </configuration/ml2-nexus>` guides).
#. Apply :command:`channel-group <vpcid> force mode-active` to the
   ethernet interfaces to make each interface a member of the port-channel.

Regardless whether the port-channel is learned or created, the
trunk vlans are applied to the port-channel and inherited by
ethernet interfaces.

.. _nexus_vlan_remove:

VLAN Removal
~~~~~~~~~~~~
When a VM is removed or a subnet is removed and dhcp is enabled, a delete
port-event is received by the Nexus driver.  If the port exists in the
Nexus driver's port data base, the driver will remove it from the data base
as well as remove the trunk vlan on the Nexus device.

To remove the trunk vlan from interface on the Nexus switch, it
sends :command:`switchport trunk allowed vlan remove <vlanid>` and possibly
:command:`no switchport trunk native vlan <vlanid>` if it was sent during
vlan creation.  The driver then checks if the vlan is used on any other
interfaces.  If not, it will remove the vlan from the Nexus switch as well
by issuing :command:`no vlan <vlanid>`.

If a port-channel was previously created for baremetal port events as
described in :ref:`nexus_vlan_create` and if there are no more port-bindings
referencing the created port-channel, the Nexus Driver will do as follows:

* The ethernet interfaces will be removed as members to the port-channel by
  issuing :command:' no channel-group ' on each participating Nexus
  Switch interface,
* The port-channel will be completely removed from the Nexus Switch(s) by
  issuing :command:`no port-channel <id>` on each participating switch,
* And the port-channel/vpc id released back into the Nexus driver vpc-id pool.

VXLAN Overlay Creation
~~~~~~~~~~~~~~~~~~~~~~
VXLAN Overlay creation does similar basic vlan trunk config as described
in the `VLAN Creation`_ section.  Prior to doing vlan trunk config, the VLAN
is mapped to a VXLAN Network Identifier (VNI) and applied to the
NVE (network virtualization edge) interface.  Specifically, the
steps done for the user is as follows:

* Create a one-to-one mapping by creating a mulitcast IP address and
  associating it with a VXLAN Network ID. Apply this configuration to the
  NVE interface:

  .. code-block:: console

      int nve1
          member vni <vni-id> mcast-group <mcast-addr>

  .. end

* Associate the VNI segment to the VLAN segment. The configuration applied is
  as follows:

  .. code-block:: console

      vlan <vlanid>
        vn-segment <vni-id>

  .. end

Configuration VXLAN VNI ranges and multicast groups is done beneath
the section header ``ml2_type_nexus_vxlan`` of the configuration file.
See the :doc:`/admin/ml2-nexus` for more details.

VXLAN Overlay Removal
~~~~~~~~~~~~~~~~~~~~~
VXLAN Overlay removal does vlan trunk removal as described in `VLAN Removal`_
section.  Additionally, it removes the vni member from the nve interface as
well as vlan segment if there are no other ports referencing it.

Configuration Replay
~~~~~~~~~~~~~~~~~~~~
If the Nexus MD discovers the Nexus switch is no longer reachable,
all known configuration for this switch is replayed once communication
is restored.  The order of the events are performed differently than described
in `VLAN Creation`_ for efficiency reasons.  This order is as follows:

#. All known interfaces are initialized with :command:`switchport mode trunk`
   and :command:`switchport trunk allowed vlan none` if there are no
   trunking vlans already configured.
#. For VXLAN, set :command:`member vni <vni-id> mcast-group <mcast-addr>`
   beneath the nve interface.
#. For each interface, a lists of VLANS are sent to the Nexus switch as a
   single request using the configuration
   :command:`switchport trunk allowed vlan add <multiple-vlanids>`.
#. Following this, batches of vlans made active. For VXLAN, this will
   also include the :command:`vn-segment <vni>` configuration.
