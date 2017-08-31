================================================
Nexus Mechanism Driver Overview and Architecture
================================================

Introduction
~~~~~~~~~~~~
The ML2 Nexus driver adds and removes trunk vlans on the Cisco Nexus 9K switch
for both ethernet interfaces and port-channel interfaces.  It also supports
configuration of VXLAN Overlay, baremetal deployments (VLAN configurations
only), and performs configuration replay on switch recovery.

This user guide describes the activities the Nexus driver performs to create
and remove VLANS on receipt of Openstack ML2 baremetal and non-baremetal port
events.

.. _nexus_vlan_create:

VLAN Creation
~~~~~~~~~~~~~
When VMs are created or when subnets are created with dhcp is enabled, port
events are received by the nexus driver.  If there are switch credentials
defined by the administrator for the event, then the nexus driver will
process the event.

The basic Nexus configuration actions taken by the nexus driver are
as follows:

#. Configure the provided VLAN on the Nexus device,
#. Configure the interface as :command:`switchport mode trunk` if needed.
#. Initialize the interface with :command:`switchport trunk allowed vlan none`
   (only if no trunk vlan have been configured manually by the user)
#. Add a trunk vlan onto the specified interface using the interface
   CLI :command:`switchport trunk allowed vlan add <vlanid>`.

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
in the :doc:`admin guide </admin/ml2-nexus>`.)

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
   (refer to ``intfcfg.portchannel`` config in :doc:`admin </admin/ml2-nexus>`
   and :doc:`config guide </configuration/ml2-nexus>`).
#. Apply :command:`channel-group <vpcid> force mode-active` to the
   ethernet interfaces to make each interface a member of the port-channel.

Regardless whether the port-channel is learned or created, the
trunk vlans are applied to the port-channel and inherited by
ethernet interfaces.

.. _nexus_vlan_remove:

VLAN Removal
~~~~~~~~~~~~
When a VM is removed or a subnet is removed and dhcp is enabled, a delete
port-event is received by the nexus driver.  If the port exists in the
nexus driver's port data base, the driver will remove it from the data base
as well as remove the trunk vlan on the Nexus 9K device.

To remove the trunk vlan from interface on the Nexus switch, it
sends :command:`switchport trunk allowed vlan remove <vlanid>`.  The driver
then checks if the vlan is used on any other interfaces.  If not,
it will remove the vlan from the Nexus switch as well by issuing
:command:`no vlan <vlanid>`.

VXLAN Overlay Creation
~~~~~~~~~~~~~~~~~~~~~~
VXLAN Overlay creation does similar basic vlan trunk config as described
in `VLAN Creation`_ section.  Prior to doing vlan trunk config, the VLAN
is mapped to a VXLAN Network Identifier (VNI) and applied to
nve (network virtualization edge) interface.  Specifically, the
steps done for the user is as follows:

* Create nve interface, assign an mcast group to a vni which is
  associated to the nve interface.  So the configuration applied is as
  follows:

  .. code-block:: console

      int nve1
          member vni <vni-id> mcast-group <mcast-addr>

  .. end

* Associate the vni to a vlan.  The configuration applied is as follows:

  .. code-block:: console

      vlan <vlanid>
        vn-segment <vni-id>

  .. end

Configuration VXLAN vni ranges and multicast groups is done beneath
the section header ``ml2_type_nexus_vxlan`` of the configuration file.
See the :doc:`admin guide </admin/ml2-nexus>` for more details.

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
   and :command:`switchport trunk allowed vlan none` if needed.
#. For VXLAN, set :command:`member vni <vni-id> mcast-group <mcast-addr>`
   beneath the nve interface.
#. For each interface, a lists of VLANS are sent to the Nexus switch as a
   single request using the configuration
   :command:`switchport trunk allowed vlan add <multiple-vlanids>`.
#. Following this, batches of vlans made active. For VXLAN, this will
   also include the :command:`vn-segment <vni>` configuration.
