==========================================
UCSM Mechanism Driver Administration Guide
==========================================
The configuration parameters for the ML2 UCSM Mechanism Driver can be
specified in a configuration file along with other neutron configuration
parameters. Another approach could be to use TripleO config for OpenStack
on OpenStack installations.

For a description of functionalities supported by the UCSM Driver
for VLAN and SR-IOV configuration, please refer to
:doc:`/reference/ml2-ucsm`.

.. _ucsm_driver_startup:

UCSM Driver configuration along with neutron parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Configuration for Cisco specific ML2 mechanism drivers can be added
   to the file containing neutron specific configuration, by specifying it
   under a driver specific section header. UCSM driver configuration needs
   to be under the section header ``[ml2_cisco_ucsm]``. This neutron
   configuration file is often called ``ml2_conf.ini`` and frequently
   resides under the directory ``/etc/neutron/plugins/ml2``.

   .. note::
      It is also possible to place this configuration into a separate
      file for example ``ml2_conf_cisco.ini`` to keep these
      configurations separate from existing configuration in file
      ``ml2_conf.ini``.

#. This configuration file needs to be provided on the command line when
   neutron-server process is started. For example:

   .. code-block:: console

       /usr/local/bin/neutron-server --config-file /etc/neutron/neutron.conf \
           --config-file /etc/neutron/plugins/ml2/ml2_conf.ini  \
           --config-file /etc/neutron/plugins/ml2/ml2_conf_cisco.ini

   .. end

#. In a OpenStack setup with a single UCSM, it may be sufficient to use
   the single-UCSM format to specify the UCSM driver config with the
   following parameters:

   * Management IP address of the UCSM
   * Admin username to login to the UCSM
   * Admin password
   * Hostname to Service Profile Mapping for all the servers that are
     controlled by this UCSM and are part of the OpenStack cloud.

     .. note::
        The Service Profile (SP) associated with a server can also be a
        Service Profile Template (SPT). If the SP or the SPT are not
        created at the root level on the UCSM, the path to the SP or
        SPT needs to be provided as part of the above configuration.

#. List of ethernet ports or vNICs on the UCS Servers that can be used
   for neutron virtual port configurations. Of all the ethernet ports
   or vNICs available on the UCS Servers, provide only the ones that
   are set aside for neutron virtual port use.

#. List of vNIC Templates that are associated with neutron physical
   networks. This is an optional config and needs to be specified
   only when vNICs spread across multiple UCS Servers are all
   connected to a common physical network and need to be configured
   identically by the UCSM driver.

#. List of supported SR-IOV devices specified as a list of vendor and
   product IDs. This is an optional parameter and will default to
   the vendor and product IDs for Cisco VICs and Intel NICs.

#. For use cases where a SR-IOV port attached to a nova VM can
   potentially carry a list of application specific VLANs. For this
   configuration, the UCSM driver expects a mapping between a
   neutron network and the list of application specific VLANs that
   can be expected on a SR-IOV port on this neutron network. This
   is also an optional config.

   .. note::
      The VLAN IDs associated with a neutron network should not be
      confused with the VLAN-id range of the neutron network itself.
      SR-IOV ports created on these neutron networks essentially
      act as trunk ports that can carry application specific
      traffic on VLANs specified in this config.

#. In a setup that utilizes multiple UCSMs, UCSM specific configuration
   parameters need to be repeated for each UCSM under a repeatable section
   starting with the UCSM IP specified in this format:
   ``[ml2_cisco_ucsm_ip:<UCSM IP address>]``

#. The UCSM driver connects to all the UCS Managers provided in its
   configuration via a HTTPS connection where the SSL certificate on
   the UCS Manager is checked for validity. If there is a need to opt
   out of this default behavior, the parameter ``ucsm_https_verify``
   needs to be explicity set to False. This is a global configuration
   and is applicable to all the UCS Manager configurations provided to
   the driver. Disabling SSL certificate checking makes the connection
   insecure and is not recommended.

Enabling SR-IOV support
~~~~~~~~~~~~~~~~~~~~~~~

The UCSM driver allows the Cisco VM-FEX capability available on UCS Managers
to be leveraged in the OpenStack context. OpenStack users that have UCS
servers with supported Cisco and Intel NICs can bring up VMs with SR-IOV
port to carry their tenant traffic at greater speeds. The following sections
provide more details about this feature.


Prerequisites for SR-IOV port support
-------------------------------------

Before the UCS Servers are purposed as compute hosts with SR-IOV ports, these
hosts need to be pre-configured to have SR-IOV VFs (Virtual Functions) enabled
and ready for OpenStack use and UCSM driver configuration. Here is the list of
pre-requisites for SR-IOV port support:

#. UCS Servers with any of the following VICs:

   *  Cisco UCS VIC 1240 (with vendor_id:product_id as 1137:0071)
   *  Cisco UCS VIC 1340 (with vendor_id:product_id as 1137:0071)
   *  Intel 92599 10 Gigabit Ethernet Controller (with vendor_id:product_id as 8086:10ed)

#. Cisco UCS Python SDK version 0.8.2 installed on the OpenStack
   controller nodes. More information about the UCS SDK can be found here:
   `Cisco UCS SDK information <https://communities.cisco.com/docs/DOC-37174>`_

#. A dynamic vNIC connection policy needs to be defined on the UCSM specifying the
   number of VFs the physical function (PF) should be split into. This profile
   also needs to specify if the VFs would be created in ``direct`` or ``macvtap``
   modes. Detailed instructions for creating a Dynamic vNIC connection policy and
   applying it on a UCS Server vNIC can be found in `UCS Manager VM-FEX configuration
   guide <https://www.cisco.com/c/en/us/td/docs/unified_computing/ucs/sw/vm_fex/kvm/gui/config_guide/2-1/b_GUI_KVM_VM-FEX_UCSM_Configuration_Guide_2_1/b_GUI_KVM_VM-FEX_UCSM_Configuration_Guide_2_1_chapter_011.html#topic_C6C37CF9F34D426EB0C8C5C5C636B7D0>`_

#. Associate the Dynamic vNIC connection policy with a PF by updating its Service
   Profile.

#. Intel VT-x and VT-d processor extensions for virtualization must be enabled
   in the host BIOS. This can be achieved by adding ``intel_iommu=on`` to
   ``GRUB_CMDLINE_LINUX`` in :file:`/etc/sysconfig/grub` [in RHEL] or
   :file:`/etc/default/grub` [in Ubuntu].

#. After this grub.conf files on the SR-IOV capable compute hosts need to be
   regenerated by running :command:`grub2-mkconfig -o /boot/grub2/grub.cfg`
   on BIOS systems or :command:`grub2-mkconfig -o /boot/efi/EFI/redhat/grub.cfg`
   on UEFI systems.

#. These SR-IOV capable compute hosts need to be rebooted. Due to this operation
   it is better to install OpenStack on these compute hosts after this list
   of pre-requisites have been completed.

#. Make sure that IOMMU is activated by running :command:`dmesg | grep -iE "dmar|iommu"`.
   The output should include the following lines::

   [ 0.000000] Kernel command line: BOOT_IMAGE=/vmlinuz-3.13.0-24-generic root=/dev/mapper/devstack--38--vg-root ro quiet intel_iommu=on
   [ 0.000000] Intel-IOMMU:enabled

#. Make sure the SR-IOV capable VFs are visible to kernel by running
   :command:`lspci –nn | grep Cisco`. The output should contain several lines that
   look like::

     0a:00.1 Ethernet controller [0200]: Cisco Systems Inc VIC SR-IOV VF [1137:0071] (rev a2)


Configuring nova for SR-IOV
~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. For nova to schedule VMs requesting SR-IOV ports, it needs to be made aware of
   compute hosts that have SR-IOV capable devices. This is achieved by adding the
   following configuration to ``nova.conf`` on each compute host capable of
   hosting SR-IOV based VMs.

   .. code-block:: ini

       [default]
       pci_passthrough_whitelist = { "vendor_id": "<id>", "product_id": "<id>",
           "physical_network": "physnet2"}

   .. end

#. Also, for nova to schedule VMs that request SR-IOV port(s) on a compute host,
   nova's scheduler should be able to filter compute hosts based on their SR-IOV
   capability. This is achieved by adding the following config to ``nova.conf``
   on the controller node(s).

   .. code-block:: ini

       [DEFAULT]
       scheduler_default_filters = RetryFilter, AvailabilityZoneFilter, RamFilter, ComputeFilter, ComputeCapabilitiesFilter, ImagePropertiesFilter, ServerGroupAntiAffinityFilter, ServerGroupAffinityFilter, PciPassthroughFilter

   .. end

Troubleshooting
~~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1

   ml2-ucsm-troubleshoot

