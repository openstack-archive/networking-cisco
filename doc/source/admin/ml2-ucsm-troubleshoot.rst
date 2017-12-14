Introduction
------------

This section lists some issues that could be encountered during the
installation and operation of the UCS Manager driver. For each of these
scenarios, there is an attempt to identify the probable root cause for that
issue and a way to return to a successful state.

The UCS Manager driver logs important information regarding its operation in
the neutron server log file. Please refer to this log file while trying to
troubleshoot your driver installation.

The UCS Manager driver prefixes any configuration it adds to the UCS Manager
with ``OS-``. This driver creates VLAN Profiles, Port-Profiles and updates
Service Profiles and Service Profile Templates in addition to updating vNIC
Templates.  For this to be successful, the UCS Manager driver should be able to
connect to the UCS Manager and push down the configuration. Listed below are
some common reasons why the configuration might be missing on the UCS Manager.
Please refer to the neutron server log file for error messages reported by the
UCS Manager driver to root cause the issue.

Connection to UCS Manager Failed: Certificate verify failed
-----------------------------------------------------------

Description
^^^^^^^^^^^

If you see that the driver is reporting a UCS Manager connection failure with
the following error message, then the SSL Certificate verification on the UCS
Manager has failed and this would prevent the driver from connecting to the UCS
Manager.

Error Message
^^^^^^^^^^^^^

::

  UcsmConnectFailed: Unable to connect to UCS Manager <IP address>. Reason: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:590)>.

Corrective Action
^^^^^^^^^^^^^^^^^

If you want the SSL certificate check to proceed, please make sure UCS Manager
has a valid SSL certificate associated with it. Instructions can be found at:

`Cisco UCS Manager Administration Management Guide 3.1 <http://www.cisco.com/c/en/us/td/docs/unified_computing/ucs/ucs-manager/GUI-User-Guides/Admin-Management/3-1/b_Cisco_UCS_Admin_Mgmt_Guide_3_1/b_Cisco_UCS_Admin_Mgmt_Guide_3_1_chapter_0110.html>`_


SSL certificate checking can be disabled by setting the configuration variable
``ucsm_https_verify`` to False. This will be available starting from release
5.4.

UCS Manager network driver failed to get login credentials for UCSM
-------------------------------------------------------------------

Description
^^^^^^^^^^^

The UCSM driver needs IP address and login credentials for all the UCS Managers
that it needs to configure. Any issues with providing this configuration would
result in connectivity issues to the UCS Manager(s).

Error Message
^^^^^^^^^^^^^

::

  UCS Manager network driver failed to get login credentials for UCSM <IP address>

Corrective Action
^^^^^^^^^^^^^^^^^

Please check if the UCS Manager IP address, username and password are provided
in the configuration file passed to neutron server process and that they are
accurate. Ping the UCS Manager(s) IP address(s) from the OpenStack controller
to check if you have network connectivity.

VLAN Profile with the id ``OS-<VLAN-id>`` not configured on the UCS Manager
---------------------------------------------------------------------------

Description
^^^^^^^^^^^

If the connection to the UCS Manager is successful, when a neutron network is
created with DHCP service enabled, a VLAN Profile should be created on the UCS
Manager. This configuration will program the Fabric Interconnect to send
traffic on the VLAN associated with the neutron network to the TOR switch.

Corrective Action
^^^^^^^^^^^^^^^^^

Make sure that the neutron Network created is of type VLAN and neutron is
configured to use the VLAN type driver. This configuration can be provided as
follows:

.. code-block:: ini

    [ml2]
    type_drivers = vlan
    tenant_network_types = vlan

.. end

VLAN configuration missing on the vNICs on either the Controller or Compute nodes
---------------------------------------------------------------------------------

Description
^^^^^^^^^^^

Once the VLAN profiles are created, vNICs on the UCS Servers acting as
OpenStack Controllers would also be updated with VLAN configuration. The vNICs
on UCS Servers acting as compute hosts will be updated with VLAN configuration
when VMs are created on those compute hosts.

Corrective Action
^^^^^^^^^^^^^^^^^

#. Check if the hostname to Service Profile mapping provided to the UCSM driver
   via the ``ucsm_host_list`` are accurate.

#. Check if the Service Profile on the UCS Manager is at the root or in a sub
   directory.  If it is in a subdirectory, please provide the full path in the
   ``ucsm_host_list`` config.

#. Check if the Service Profile is still attached to a Service Profile
   Template. In that case, for the UCSM driver to be able to modify this SP, it
   should be unbound from the Template.

#. If the UCSM driver is required to modify the Service Profile Template, then
   the driver needs to be provided with the ``sp_template_list`` configuration.

#. The next configuration parameter to check would be the
   ``ucsm_virtio_eth_ports``. This configuration should contain the list of
   vNICS on the Service Profile or the Service Profile Template that is
   available for the UCSM driver to configure tenant VLANs on.

VLAN configuration not deleted on the UCS Manager
-------------------------------------------------

Description
^^^^^^^^^^^

Just like VLAN configuration was added to the UCS Manager at different stages
of Network and VM configuration, the deletion process also follows its own
state machine.

Issue
^^^^^

Deleting a VM did not result in the removal of VLAN configuration on the UCS
Manager.

Corrective Action
^^^^^^^^^^^^^^^^^

#. If there are other VMs still active on the compute host on the same network
   (hence these VMs are on the same VLAN as the one being deleted), the VLAN-id
   configured on vNICs on the compute hosts will not be deleted. In other
   words, VLAN configuration on the compute hosts will not be deleted until all
   the VMs on the compute host on the VLAN are deleted.

#. The global VLAN profile will be deleted only when the neutron Network
   associated with that VLAN-id is deleted.

Port Profiles not created on the UCS Manager
--------------------------------------------

Description
^^^^^^^^^^^

When a VM is launched with an SR-IOV port, the UCSM driver responds to that
request by creating Port Profiles (PP) on the UCS Manager. The PPs created by
the driver are always named ``OS-PP-<Vlan-id>``.

Issue
^^^^^

Port profile is not created on the UCS Manager.

Corrective Action
^^^^^^^^^^^^^^^^^

#. Run the command ``lspci -nn | grep -i Cisco`` on the compute nodes containing the
   SR-IOV capable Cisco NICs. The output should contain lines that look as follows::

     0a:00.1 Ethernet controller [0200]: Cisco Systems Inc VIC SR-IOV VF [1137:0071] (rev a2)

#. If there are no rows for Virtual Functions with vendor and product ids 1137
   and 0071, it is an indication that the Dynamic vNIC Profile for that
   Physical Function has not been setup properly on the UCS Manager.

#. The ethernet port a.k.a as the Physical Function needs to be split into
   SR-IOV Virtual Functions that can be consumed by the UCSM driver. This can
   be achieved by attaching a Dynamic vNIC Profile where the ``direct`` or
   ``macvtap`` values are set. In addition, the parameter to specify the number
   of Virtual Functions to split the Physical Function into also needs to be
   provided.

   .. note::
      Attaching a Dynamic vNIC Profile to a ethernet port on a UCS Server would
      result in a server reboot.

#. Check that the ``intel_iommu`` kernel parameter is set to ``on`` in the grub
   files on the compute node with the SR-IOV ports by running the following
   command::

     dmesg | grep -e DMAR -e IOMMU

   The output of the command should contain a line that says ``Intel-IOMMU:
   enabled``.

#. Lastly, make sure that a Port Profile for that VLAN-id does not exist prior
   to OpenStack use. If so, OpenStack will not be able to create one for the
   same VLAN-id or re-use the pre-existing Port Profile.

Port Profiles not deleted on the UCS Manager
--------------------------------------------

Description
^^^^^^^^^^^

The Port Profile created on the UCS Manager in response to a SR-IOV based VM,
is aware of all the VMs that are currently using that Port Profile. UCS Manager
learns this information by polling the UCS Servers that are attached to it.
This polling interval is approximately 15 mins and is not user configurable.
The Port Profile can be deleted only when they are no longer in use by any VM.

Issue
^^^^^

Port Profile still exists on the UCS Manager when all VMs using that Port
Profile have been deleted.

Corrective Action
^^^^^^^^^^^^^^^^^

No manual intervention required.

Even when all the VMs using a specific Port Profile are deleted, it takes some
time for the UCS Manager to learn this information because of the polling
interval. The UCS Manager will not allow the UCSM driver to delete the Port
Profile before this.

The UCSM driver maintains a list of Port Profiles to delete from the various
UCS Managers that it is connected to. The driver also has a timer thread that
wakes up every 10 minutes and attempts to delete the Port Profiles in this
list.  So, although the Port Profile might not get deleted right away, the UCS
driver will take care of eventually deleting Port Profiles that it created when
they are not in use.
