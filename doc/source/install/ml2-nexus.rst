=========================================
Nexus Mechanism Driver Installation Guide
=========================================

This is an installation guide for enabling the Nexus Mechanism Driver (MD)
support on OpenStack.  This guide only covers details on the Nexus MD install
and does not cover OpenStack or Nexus 9K switch installation.
The `Prerequisites`_ section contains links for this.

Prerequisites
~~~~~~~~~~~~~

The prerequisites for installing the ML2 Nexus MD are as follows:

* Cisco Nexus 9K image version - NX-OS 7.0(3)I5 (minimum required for REST API
  Driver). Refer to `Nexus 9K docs <https://www.cisco.com/c/en/us/products/switches/nexus-9000-series-switches/index.html>`_
  for upgrade/downgrade instructions.  From this link, select the 'Support'
  option in the middle of the page for information on upgrade/downgrade
  guides, configuration and technical references.
* The ML2 Nexus MD have been tested on these OSs.

    * RHEL 6.1 or above
    * Ubuntu 14.04 or above

* Your Nexus switch must be set-up as described in the next section
  `Nexus Switch Setup`_.
* Requires neutron installation as described in
  `Neutron install <https://docs.openstack.org/neutron/latest/install/>`_
* If unable to upgrade your Nexus 9K Switch to a version that supports the
  REST API driver needed by the Nexus MD, the ncclient driver can be
  configured temporarily for use instead.  This is temporary
  since ncclient option is being deprecated for removal.  Refer
  to `nexus_driver` configuration variable in
  :doc:`Nexus Configuration Reference </configuration/ml2-nexus>` for details
  on changing this setting.  The ncclient driver requires the following
  to be installed:

    * ``Paramiko`` library, the SSHv2 protocol library for python
    * The ``ncclient`` (minimum version v0.4.2) python library for NETCONF
      clients.  Install the ncclient library by using the pip package
      manager at your shell prompt:
      :command:`pip install ncclient == 0.4.2`

Nexus Switch Setup
~~~~~~~~~~~~~~~~~~~

This section lists what is required to prepare the Nexus switch for operation
with the Nexus Driver.

#. Your Nexus switch must be connected to a management network separate from
   the OpenStack data network. The Nexus MD *must* be able to access this
   network so it can communicate with the switch to set up your data flows.
#. The ML2 Nexus Rest API Driver requires :command:`feature nxapi` to be
   enabled on the switch.
#. Each compute host on the cloud must be connected to the switch using an
   interface dedicated solely to OpenStack data traffic.
#. Some pre-configuration must be performed by the Nexus switch administrator.
   For instance:

   * All participating compute host interfaces must be enabled
     with :command:`no shutdown`.

   * Possible port-channels pre-configuration:

     * Peer-link configuration must always be pre-configured.
     * The port-channel configuration must be preconfigured for all
       non-baremetal cases. For baremetal cases, when administrator prefers
       to have port-channels learned versus automatically creating
       port-channels using ``vpc-pool`` Nexus driver config.
     * When port-channels are learned, the interfaces must also be configured
       as members of the port-channel.

   * For VXLAN Overlay Configurations, enable the feature using the following
     Nexus CLI:

     .. code-block:: ini

           feature nv overlay
           feature vn-segment-vlan-based
           interface nve1
               no shutdown
               source-interface loopback x
               # where x is same value as Nexus driver config 'nve_src_intf'

     .. end


ML2 Nexus MD Installation
~~~~~~~~~~~~~~~~~~~~~~~~~

#. Install networking-cisco repository as described in the section
   :doc:`How to install networking-cisco </install/howto>`.
#. Configure Nexus ML2 Driver.
   Once the networking-cisco code is installed, it needs to be configured and
   enabled in Neutron, the :doc:`admin guide </admin/ml2-nexus>` provides full
   details on how to create the neutron configs for various use cases.  For
   details on each configuration parameters, refer to
   :doc:`Nexus Configuration Reference</configuration/ml2-nexus>`.

   Below is a simple VLAN configuration which can be applied to
   ML2 neutron config files ``ml2_conf.ini`` and possibly
   ``ml2_conf_cisco.ini`` located in directory ``/etc/neutron/plugins/ml2``.
   The file ``ml2_conf_cisco.ini`` is optional if you'd like to isolate
   cisco specific parameters.

   .. code-block:: ini

       [ml2]
       #- This neutron config specifies to use vlan type driver and use
       #  cisco nexus mechanism driver.
       type_drivers = vlan
       tenant_network_types = vlan
       mechanism_drivers = openvswitch,cisco_nexus

       #- This neutron config specifies the vlan range to use.
       [ml2_type_vlan]
       network_vlan_ranges = physnet1:1400:3900

       #- Provide Nexus credentials, compute host, and nexus interface
       [ml2_mech_cisco_nexus:192.168.1.1]
       username=admin
       password=mySecretPasswordForNexus
       compute-1=1/2

   .. end
#. Restart neutron to pick-up configuration changes.

   .. code-block:: ini

       service neutron-service restart

   .. end

