===============================================
UCSM Mechanism Driver Overview and Architecture
===============================================

Introduction
~~~~~~~~~~~~
The ML2 UCSM driver translates neutron ML2 port and network configuration
into configuration for Fabric Interconnects and vNICs on the UCS Servers.
This driver supports configuration of neutron virtual and SR-IOV ports
on VLAN networks. It communicates with the UCSM via the Cisco UCS Python
SDK (version 0.8.2).

Overview
~~~~~~~~
The UCSM driver runs as part of the neutron server process on the OpenStack
controller nodes and has no component running on any of the compute nodes.
In an OpenStack cloud consisting of a mixiture of servers from different
vendors, enabling the UCSM driver will result in configuration of only
the UCS servers controlled by UCS Managers. The other servers will not
be affected. Once the UCSM driver is initialized with its configuration,
any changes to the configuration will not take effect until the neutron
server process is restarted.

.. _ucsm_virtio_support:

Neutron virtual port support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The UCSM driver configures UCS servers and Fabric Interconnects (FIs) in
response to a neutron virtual port request during VM creation and
deletion. The UCSM driver when enabled, configures the FI's
outgoing trunk port to carry VLAN traffic for that VM. It also
configures the server's ethernet ports to allow the VM's VLAN traffic by
manipulating the server's Service Profile (or Template). The driver
is also responsible for removing this configuration during VM port
deletion.

.. _ucsm_sriov_support:

SR-IOV port support
~~~~~~~~~~~~~~~~~~~
The UCSM driver supports configuration of SR-IOV ports created on Cisco and
and Intel NICs available on UCS Servers. VMs with SR-IOV ports enjoy greater
network performance because these ports bypass the virtual switch on the
compute host's kernel and send packets directly to the Fabric Interconnect.

When the SR-IOV ports being configured are on Cisco NICs, the driver
creates Port Profiles (PPs) on the UCS Manager and associates it with
the next available VF. The driver is also responsible for deleting the
PPs when all VMs using it no longer exist.
