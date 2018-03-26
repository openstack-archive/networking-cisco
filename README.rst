The networking-cisco project's goal is to provide support for Cisco networking
hardware and software in OpenStack deployments. This includes ML2 drivers and
agents for neutron, as well as other pieces of software which interact with
neutron to best utilise your Cisco products with OpenStack.

* Free software: Apache license
* Documentation: http://networking-cisco.readthedocs.io/en/latest
* Source: http://git.openstack.org/cgit/openstack/networking-cisco
* Bugs: http://bugs.launchpad.net/networking-cisco

Drivers for Cisco Products
==========================

* Nexus 9000 Series Switches

  * ML2 Mechanism driver - cisco_nexus
  * ML2 VXLAN Type driver - nexus_vxlan

* UCS Manager

  * ML2 Mechanism driver - cisco_ucsm

* ASR 1000 Series

  * Neutron Service Plugins - cisco_l3_routing

* Service Advertisement Framework (SAF)

  * Firewall drivers - native, phy_asa
  * Applications - fabric-enabler-server, fabric-enabler-agent, fabric-enabler-cli

* Prime Network Registrar (CPNR)

  * Applications - cpnr-rootwrap, cpnr-dns-relay-agent, cpnr-dns-relay, cpnr-dhcp-relay-agent, cpnr-dhcp-relay

* Application Policy Infrastructure Controller (APIC)

  * *No longer supported.* Removed in release 5.0.0
  * Code removed by commit 10b124d39fde4085a695d5c6652c8fb6e0620ece
  * Driver now hosted in repo https://github.com/noironetworks/apic-ml2-driver

* Network Convergence System (NCS)

  * *No longer supported.* Removed in release 6.0.0
  * Code removed by commit 31e4880299d04ceb399aa38097fc5f2b26e30ab1

* Nexus 1000v

  * *No longer supported.* Removed in release 6.0.0
  * Code removed by commit 0730ec9e6b76b3c1e75082e9dd1af55c9faeb34c

* CSR 1000v series

  * *No longer supported.* Removed in release 6.0.0
  * Code removed by commit 917480566afa2b40dc382bc4f535d173bad7736d

Releases and Version Support
============================

We have a goal to maintain compatibility with each version of OpenStack for as
long as possible, so starting with version 4.0.0, networking-cisco was
compatible with both the Mitaka and Newton OpenStack releases. As such
networking-cisco is branchless and stable releases that are compatible with
multiple OpenStack versions will be cut from our master branch.

The latest (6.x) release of networking-cisco is compatible with the Mitaka,
Newton, Ocata, Pike and Queens releases of OpenStack.
