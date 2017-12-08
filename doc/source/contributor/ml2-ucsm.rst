=======================================
UCSM Mechanism Driver Contributor Guide
=======================================

DevStack Configuration Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For introductory details on DevStack, refer to :doc:`/contributor/howto`.
This section focuses on how to set the UCSM driver related configuration
within DevStack's configuration file ``local.conf``. These changes should
follow the section which installs networking-cisco repository.

Configuration required for neutron virtual port support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The following parameters need to be provided to DevStack so that the
UCSM driver can be initialized with its configuration. The parameters provided
to ``local.conf`` are similar to the configuration options provided to neutron
and described in section :ref:`ucsm_driver_startup`.

Common configuration
--------------------

The following snippet refers to configuration that is common to all VLAN based
mechanism drivers.

.. code-block:: ini

    [[local|localrc]]
    enable_plugin networking-cisco https://github.com/openstack/networking-cisco

    # Set openstack passwords here.  For example, ADMIN_PASSWORD=ItsASecret

    # disable_service/enable_service here. For example,
    # disable_service tempest
    # enable_service q-svc

    # bring in latest code from repo.  (RECLONE=yes; OFFLINE=False)

    Q_PLUGIN=ml2
    Q_ML2_PLUGIN_MECHANISM_DRIVERS=openvswitch,cisco_ucsm
    Q_ML2_TENANT_NETWORK_TYPE=vlan
    ML2_VLAN_RANGES=physnet1:100:109
    ENABLE_TENANT_TUNNELS=False
    ENABLE_TENANT_VLANS=True
    PHYSICAL_NETWORK=physnet1
    OVS_PHYSICAL_BRIDGE=br-eth1

    Q_PLUGIN_CONF_FILE=/path/to/driver/config/file/ml2_conf.ini

    NOVA_CONF=/etc/nova/nova.conf
.. end

Driver configuration for a single UCSM
--------------------------------------

When the UCSM driver config needs to be specified in the single UCSM
format, the following configuration options need to be specified.

.. code-block:: ini

    [[post-config|/$Q_PLUGIN_CONF_FILE]]
    [ml2_cisco_ucsm]

    # Single UCSM Config format
    ucsm_ip=1.1.1.1
    ucsm_username=user
    ucsm_password=password

    # Hostname to Service profile mapping for UCS Manager
    # controlled compute hosts
    ucsm_host_list=Hostname1:/serviceprofilepath1/Serviceprofile1, Hostname2:Serviceprofile2

    # Service Profile Template config per UCSM. This is a mapping of Service Profile
    # Template to the list of UCS Servers controlled by this template.
    sp_template_list = SP_Template1_path:SP_Template1:S1,S2 SP_Template2_path:SP_Template2:S3,S4

    # Ethernet port names to be used for virtio ports
    ucsm_virtio_eth_ports = neutron-eth0, neutron-eth1

.. end

Driver configuration in multi-UCSM format
-----------------------------------------

When the UCSM driver config needs to be specified in the multi-UCSM format,
the following configuration options need to be specified.

.. code-block:: ini

    [[post-config|/$Q_PLUGIN_CONF_FILE]]
    [ml2_cisco_ucsm]

    # If there are multiple UCSMs in the setup, then the below
    # config needs to be specified in the multi-UCSM format
    # for each UCSM
    [ml2_cisco_ucsm_ip:1.1.1.1]
    ucsm_username = username
    ucsm_password = password
    ucsm_virtio_eth_ports = eth0, eth1
    ucsm_host_list=Hostname1:Serviceprofile1, Hostname2:Serviceprofile2
    sp_template_list = SP_Template1_path:SP_Template1:S1,S2 SP_Template2_path:SP_Template2:S3,S4
    vnic_template_list = physnet1:vnic_template_path1:vt11,vt12 physnet2:vnic_template_path2:vt21,vt22

.. end

Driver configuration to turn off SSL certificate checking
---------------------------------------------------------

When the UCSM driver is attempting to connect to UCS Manager(s) that do not have a valid SSL
certificate, this configuration can be used to simultaneously disable checking of SSL
certificates on all UCS Manager(s). However, this is not recommended in production since
it leaves the communication path insecure and vulnerable to man-in-the-middle attacks. To setup
a valid SSL certificate, use information provided in section :ref:`UCSM SSL Certificate Setup <ucsm_ssl_certificate_setup>`.

.. code-block:: ini

    [[post-config|/$Q_PLUGIN_CONF_FILE]]
    [ml2_cisco_ucsm]

    ucsm_https_verify = False

.. end

SR-IOV specific configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. On the controller nodes, update the list of available scheduler filters to
   include the ``PciPassthroughFilter``.

   .. code-block:: ini

       [[post-config|/$NOVA_CONF]]
       [DEFAULT]
       scheduler_default_filters = RetryFilter, AvailabilityZoneFilter, RamFilter, ComputeFilter, ComputeCapabilitiesFilter, ImagePropertiesFilter, ServerGroupAffinityFilter, PciPassthroughFilter
   .. end

#. On each of the compute nodes, additional configuration should be specified to allow
   a list of PCI devices. This whitelist is consumed by nova-compute to determine which
   PCI devices can used as SR-IOV devices. The following snippet shows how this
   configuration can be specified within the ``local.conf`` files of compute nodes.
   The vendor and product IDs for Cisco VICs are ``1137`` and ``0071`` respectively.

   .. code-block:: ini

       [[post-config|/$NOVA_CONF]]
       [DEFAULT]
       pci_passthrough_whitelist = {"vendor_id":"1111","product_id":"aaaa","physical_network":"physnet1"}

   .. end

#. To specify the list of PCI devices that need to be configured by the UCSM driver, use the
   following configuration options. The UCSM driver supports SR-IOV configuration on Cisco
   VICs and Intel NICs by default. This parameter can be omitted if the SR-IOV NICs to
   be supported are one of the defaults. In the multi-UCSM format this configuration
   needs to be specified per UCSM.

   .. code-block:: ini

       # SR-IOV and VM-FEX vendors supported by this driver
       # xxxx:yyyy represents vendor_id:product_id
       # This config is optional.
       supported_pci_devs=['2222:3333', '4444:5555']

   .. end

#. The configuration option to specify the list of application specific VLANs per physical network
   carrying SR-IOV traffic is as follows.

   .. code-block:: ini

       # SR-IOV Multi-VLAN trunk config section
       [sriov_multivlan_trunk]
       test_network1=5,7-9
       test_network2=500,701 - 709

   .. end
