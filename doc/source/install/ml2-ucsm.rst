========================================
UCSM Mechanism Driver Installation Guide
========================================

This installation guide details enabling the Cisco Unified Computing
System Manager (UCSM) Mechanism Driver (MD) to configure UCS Servers
and Fabric Interconnects managed by one or more UCS Managers
in an OpenStack environment.

Prerequisites
~~~~~~~~~~~~~

The prerequisites for installing the ML2 UCSM mechanism driver are as follows:

* Cisco UCS B or C series servers connected to a Fabric Interconnect
  running UCS Manager version 2.1 or above. Please refer to
  `UCSM Install and Upgrade Guides <https://www.cisco.com/c/en/us/support/servers-unified-computing/ucs-manager/products-installation-guides-list.html>`_
  for information on UCSM installation.

* Associate UCS servers with a Service Profile or Service Profile Template
  on the UCS Manager. Instructions on how to do this via the UCSM GUI can be
  found in `UCS Manager Server Management Guide <https://www.cisco.com/c/en/us/td/docs/unified_computing/ucs/sw/gui/config/guide/2-2/b_UCSM_GUI_Configuration_Guide_2_2/configuring_service_profiles.html>`_

* Identify the vNICs for OpenStack use beforehand. If this configuration is
  not provided to the UCSM driver, it will configure vNICs eth0 and eth1 with
  OpenStack related configuration. If a subset of the vNICs on the UCS Servers
  need to be reserved for non-OpenStack workloads, the list of vNICs provided
  to the UCSM driver should not include those vNICs.

* OpenStack networking service neutron installed according to instructions in
  `neutron install guide <https://docs.openstack.org/neutron/latest/install/>`_

* OpenStack running on the OSs:

  * RHEL 6.1 or above OR
  * Ubuntu 14.04 or above

* UCS Manager version 2.2 running on the Fabric Interconnect. This software
  can be downloaded from `UCS Manager Software Download <https://software.cisco.com/download/release.html?mdfid=283612660&softwareid=283655658&release=2.2(6c)&flowid=22121>`_

.. _ucsm_ssl_certificate_setup:

* A valid SSL certificate can be set up on the UCS Manager by following
  instructions specified in `Cisco UCS Manager Administration Management Guide <https://www.cisco.com/c/en/us/td/docs/unified_computing/ucs/ucs-manager/GUI-User-Guides/Admin-Management/3-1/b_Cisco_UCS_Admin_Mgmt_Guide_3_1/b_Cisco_UCS_Admin_Mgmt_Guide_3_1_chapter_0110.html>`_

ML2 UCSM MD Installation
~~~~~~~~~~~~~~~~~~~~~~~~

#. Install networking-cisco repository as described in the section
   :doc:`/install/howto`.

#. Once the networking-cisco code is installed, configure and enable the
   Cisco UCSM ML2 driver in neutron. The :doc:`/admin/ml2-ucsm` provides full
   details on how to create the neutron configuration for various use cases.

   Below is a simple VLAN configuration along with UCSM driver configuration
   which can be applied to ML2 neutron config files ``ml2_conf.ini``.

   .. code-block:: ini

       [ml2]
       #- This neutron config specifies to use vlan type driver and use
       #  cisco ucsm mechanism driver.
       type_drivers = vlan
       tenant_network_types = vlan
       mechanism_drivers = openvswitch,cisco_ucsm

       #- This neutron config specifies the vlan range to use.
       [ml2_type_vlan]
       network_vlan_ranges = physnet1:1400:3900

       #- Provide UCSM IP and credentials
       #  This format can be used when there is 1 UCSM to be configured.
       [ml2_cisco_ucsm]
       ucsm_ip=10.10.10.10
       ucsm_username=admin
       ucsm_password=mysecretpassword

       # List of vNICs on every UCS Server that can be configured for
       # tenant VLAN configuration.
       ucsm_virtio_eth_ports=ucs-eth-0, ucs-eth-1

       # Hostname to Service Profile mapping for Compute hosts managed by
       # this UCS Manager. This config should be specified for hosts configured
       # with only Service Profiles and not Service Profile Templates.
       ucsm_host_list=controller-1:Controller-SP, compute-1:Compute-SP

       # Service Profile Template config for UCSM. This is a mapping of Service Profile
       # Template to the list of UCS Servers (shown as S# below) controlled by this template.
       sp_template_list = SP_Template1_path:SP_Template1:S1,S2 SP_Template2_path:SP_Template2:S3,S4,S5

       # vNIC Template config for UCSM. This is a mapping of vNIC Templates on the UCS
       # Manager that control vNICs that are connected to Neutron provider networks.
       vnic_template_list = physnet1:vnic_template_path1:vt1 physnet2:vnic_template_path2:vt2

   .. end

#. If the installation consists of multiple Fabric Interconnects with
   multiple UCS Managers running on them, the UCSM driver will talk
   to each one of them to configure the set of UCS Servers controlled
   by them. In that case, the neutron configuration file needs to contain
   configuration for all these UCS Managers and the UCS servers they
   control.

   Below is a snippet of configuration that depicts the multi-UCSM
   configuration format.

   .. code-block:: ini

       [ml2_cisco_ucsm]

       # This block of config has to repeat for each UCSM in the installation
       [ml2_cisco_ucsm_ip:1.1.1.1]
       ucsm_username = username
       ucsm_password = password

       # List of vNICs on every UCS Server that can be configured for
       # tenant VLAN configuration.
       ucsm_virtio_eth_ports = eth0, eth1

       # Hostname to Service Profile mapping for Compute hosts managed by
       # this UCS Manager. This config should be specified for hosts configured
       # with only Service Profiles and not Service Profile Templates.
       ucsm_host_list = Hostname1:Serviceprofile1, Hostname2:Serviceprofile2

       # Service Profile Template config per UCSM. This is a mapping of Service Profile
       # Template to the list of UCS Servers controlled by this template.
       sp_template_list = SP_Template1_path:SP_Template1:S1,S2 SP_Template2_path:SP_Template2:S3,S4

       # vNIC Template config per UCSM. This is a mapping of vNIC Templates on the UCS
       # Manager that control vNICs that are connected to Neutron provider networks.
       vnic_template_list = physnet1:vnic_template_path1:vt1 physnet2:vnic_template_path2:vt2

   .. end

#. Though not recommended, the UCSM SSL certificate checking can be disabled if
   necessary.

   .. code-block:: ini

       [ml2_cisco_ucsm]

       ucsm_https_verify = False

   .. end

#. Restart neutron to pick-up configuration changes.

   .. code-block:: console

       $ service neutron-server restart

   .. end

Configuring UCSM Driver via TripleO
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

VLAN Configuration
------------------
The Cisco specific implementation is deployed by modifying the tripleo
environment file
`Tripleo Nexus Ucsm Env File <https://github.com/openstack/tripleo-heat-templates/tree/master/environments/neutron-ml2-cisco-nexus-ucsm.yaml>`_
and updating the contents with the deployment specific content. Note that
with TripleO deployment, the server names are not known before deployment
so the MAC address of the server must be used in place of the server name.
Descriptions of the parameters can be found at
`Tripleo Nexus Ucsm Parm file <https://github.com/openstack/tripleo-heat-templates/tree/master/puppet/extraconfig/all_nodes/neutron-ml2-cisco-nexus-ucsm.j2.yaml>`_.

.. code-block:: yaml

        resource_registry:
          OS::TripleO::AllNodesExtraConfig: /usr/share/openstack-tripleo-heat-templates/puppet/extraconfig/all_nodes/neutron-ml2-cisco-nexus-ucsm.yaml
          OS::TripleO::Compute::Net::SoftwareConfig: /home/stack/templates/nic-configs/compute.yaml
          OS::TripleO::Controller::Net::SoftwareConfig: /home/stack/templates/nic-configs/controller.yaml

        parameter_defaults:

          NetworkUCSMIp: '10.86.1.10'
          NetworkUCSMUsername: 'neutron'
          NetworkUCSMPassword: 'cisco123'
          NetworkUCSMHostList: '06:00:C0:06:00:E0:bxb6-C6-compute-2,06:00:C0:05:00:E0:bxb6-C5-compute-1,06:00:C0:03:00:E0:bxb6-C3-control-2,06:00:C0:07:00:E0:bxb6-C7-compute-3,06:00:C0:04:00:E0:bxb6-C4-control-3,06:00:C0:02:00:E0:bxb6-C2-control-1'

          ControllerExtraConfig:
            neutron::plugins::ml2::mechanism_drivers: ['openvswitch', 'cisco_ucsm']

.. end

.. note::
   Multi-UCSM configuration is currently not supported via TripleO.
