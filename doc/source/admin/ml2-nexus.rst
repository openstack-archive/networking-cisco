===========================================
Nexus Mechanism Driver Administration Guide
===========================================

There are two ways to configure the Nexus ML2 Mechanism driver either directly
in the neutron configuration files or via TripleO config for OpenStack on
OpenStack configurations.

This guide focuses on the neutron start-up files then follows up with
samples of Tripleo configuration files.  You will find similarities
between the neutron start-up files and Tripleo sample configurations
since tripleo config files ultimately cause the generation of neutron
start-up configuration files.  These neutron start-up files are most often
placed beneath the directory ``/etc/neutron/plugins/ml2`` on the controller
node.

For a description of what activites are performed by the Nexus Driver
for VLAN and VXLAN configuration, refer to
:doc:`/reference/ml2-nexus` documentation.

.. _nexus_vlan_startup:

Configuring neutron directly for Nexus
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
VLAN Configuration
------------------
To configure the Nexus ML2 Mechanism Driver for use with neutron VLAN networks,
do the following:

#. Update the neutron configuration file commonly named ``ml2_conf.ini`` with
   sample configuration described in this document. This file is most
   commonly found in the directory ``/etc/neutron/plugins/ml2``.

   .. note::
      Cisco specific ML2 configuration may be isolated in the file
      ``ml2_conf_cisco.ini`` file while keeping neutron specific
      configuration parameters in file ``ml2_conf.ini``.

#. Add the Nexus switch information to the configuration file. Multiple switches
   can be configured in this file as well as multiple OpenStack hosts for each
   switch.  This information includes:

   * The IP address of the switch
   * The Nexus switch credential username and password
   * The OpenStack hostname and Nexus port of the node that is connected to the
     switch (For non-baremetal only)
   * vpc ids pool (baremetal only).  It is required when automated port-channel
     creation is desired.
   * intfcfg_portchannel (baremetal only).  This is an optional config
     which allows the user to custom configure port-channel as they are
     getting created.
     The custom config will substitute the default config
     :command:`spanning-tree port type edge trunk;no lacp suspend-individual`.
     See :ref:`nexus_vlan_create` for more details on
     what gets configured during port-channel creation.

   For detail description of the Nexus mechanism driver options in the neutron
   configuration files, refer to
   :doc:`Nexus Configuration Reference </configuration/ml2-nexus>`.

#. Include the configuration file on the command line when the neutron-server
   is started. For example:

   .. code-block:: console

       /usr/local/bin/neutron-server --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini  --config-file /etc/neutron/plugins/ml2/ml2_conf_cisco.ini

   .. end

Sample configuration with ethernet interfaces
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The sample configuration which follows contains configuration for both
Baremetal and standard configuration as they can co-exist at the same time.
If baremetal is not deployed, then those baremetal configuration variables
identified below can be omitted.  Host to interface mapping configurations can
also be omitted if only baremetal deployments exist. For configuration
activities performed during VLAN creation and removal, refer to
:ref:`nexus_vlan_create` and :ref:`nexus_vlan_remove` sections.

.. code-block:: ini

    [ml2]
    #- This neutron config specifies to use vlan type driver and uses
    #  Cisco nexus mechanism driver.
    type_drivers = vlan
    tenant_network_types = vlan
    mechanism_drivers = openvswitch,cisco_nexus

    #- This extension driver must be enabled when the mechanism
    #  driver includes nexus.
    extension_drivers = cisco_providernet_ext

    #- This neutron config specifies the vlan range to use.
    [ml2_type_vlan]
    network_vlan_ranges = physnet1:1400:3900

    [ml2_cisco]
    #- switch_heartbeat_time is optional since it now defaults to 30 seconds
    #  where previously it defaulted to 0 for disabled.  This causes a
    #  keep-alive event to be sent to each Nexus switch for the amount of
    #  seconds configured. If a failure is detected, the configuration will be
    #  replayed once the switch is restored.
    switch_heartbeat_time = 30

    #- Beneath this section header 'ml2_mech_cisco_nexus:' followed by the IP
    #  address of the Nexus switch are configuration which only applies to
    #  this switch.
    [ml2_mech_cisco_nexus:192.168.1.1]

    #- Provide the Nexus login credentials
    username=admin
    password=mySecretPasswordForNexus

    #- Non-baremetal config only - Hostname and port used on the switch for
    #  this OpenStack host.  Where 1/2 indicates the "interface ethernet 1/2"
    #  port on the switch and host-1 is the OpenStack host name.
    host_ports_mapping=host-1:[1/2]  # deprecates config `host-1=1/2`

    #- Baremetal config only - Provide pool of vpc ids for use when creating
    #  port-channels.  The following allows for a pool of ids 1001 thru 1025
    #  and also 1030.
    vpc_pool=1001-1025,1030

    #- Baremetal config only - Provide custom port-channel Nexus 9K commands
    #  for use when creating port-channels for baremetal events.
    intfcfg_portchannel=no lacp suspend-individual;spanning-tree port type edge trunk

    #- Setting the https_verify option below to True is highly encouraged
    #  for use in a production setting. This secures the communication
    #  path preventing man-in-the-middle attacks.  The default is
    #  currently False but will change to True from Cisco release 6.0.0.
    https_verify=True

.. end

Sample configuration with vPC interfaces
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In addition to supporting ethernet interfaces, multi-homed hosts using
vPC configurations are supported.  To configure this for non-baremetal
case, the administrator must do some pre-configuration on the Nexus
switch and the OpenStack host.  These prerequisites are as follows:

#. The vPC must already be configured on the Nexus 9K device as described in
   `Nexus9K NXOS vPC Cfg Guide <https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus9000/sw/7-x/interfaces/configuration/guide/b_Cisco_Nexus_9000_Series_NX-OS_Interfaces_Configuration_Guide_7x/b_Cisco_Nexus_9000_Series_NX-OS_Interfaces_Configuration_Guide_7x_chapter_01000.html>`_.
#. The data interfaces on the OpenStack host must be bonded. This bonded
   interface must be attached to the external bridge.

For baremetal case, Nexus driver will only configure the bonding on the TOR.
The bonding on the baremetal server can be done one of two ways:

#. The network config is passed into the instance using config-drive from
   nova/ironic.  Therefore, if the instance has something like cloud-init
   or glean which can read the config-drive it’ll set up the bond.
#. If the instance image doesn’t have one of those tools then it is down to
   the tenant/owner of the instance to set it up manually.

The only variance from the ethernet configuration shown previously is the host
to interface mapping so this is the only change shown below for non-baremetal
configuration:

.. code-block:: ini

    [ml2_mech_cisco_nexus:192.168.1.1]
    host_ports_mapping=host-1:[port-channel2]  # deprecates config `host-1=port-channel:2`

    [ml2_mech_cisco_nexus:192.168.2.2]
    host_ports_mapping=host-1:[port-channel2]  # deprecates config `host-1=port-channel:2`

.. end

Sample configuration with multiple ethernet interfaces
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
There are some L2 topologies in which traffic from a physical server can come
into multiple interfaces on the ToR switch configured by the Nexus Driver.
In the case of server directly attached to ToR, this is easily taken care of by
port-channel/bonding.  However, if an intermediary device (e.g. Cisco UCS
Fabric Interconnect) is placed between the server and the Top of Rack switch,
then server traffic has the possibility of coming into multiple interfaces on
the same switch.  So the user needs to be able to specify multiple interfaces
per host.

The following shows how to configure multiple interfaces per host.
Since only the host to interface mapping is the only variance to the
ethernet configuration, only the change to host to interface mapping is shown.

.. code-block:: ini

    [ml2_mech_cisco_nexus:192.168.1.1]
    host_ports_mapping=host-1:[1/11,1/12]  # deprecates config `host-1=1/11,1/12`

.. end

.. _neutron_vxlan_startup:

VXLAN Overlay Configuration
---------------------------

Limitations
^^^^^^^^^^^
VXLAN Overlay Configuration is supported on normal VM configurations and not
baremetal.  Because of this, host to interface mapping in the ML2 Nexus
configuration section is always required.

Prerequisites
^^^^^^^^^^^^^
The Cisco Nexus ML2 driver does not configure the features described in the
“Considerations for the Transport Network” section of
`Nexus9K NXOS VXLAN Cfg Guide <http://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus9000/sw/6-x/vxlan/configuration/guide/b_Cisco_Nexus_9000_Series_NX-OS_VXLAN_Configuration_Guide.pdf>`_.
The administrator must perform such configuration before configuring the
Nexus driver for VXLAN. Do all of the following that are relevant to your
installation:

* Configure a loopback IP address
* Configure IP multicast, PIM, and rendezvous point (RP) in the core
* Configure the default gateway for VXLAN VLANs on external routing devices
* Configure VXLAN related feature commands: :command:`feature nv overlay`
  and :command:`feature vn-segment-vlan-based`
* Configure NVE interface and assign loopback address

Nexus Driver VXLAN Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
To support VXLAN configuration on a top-of-rack Nexus switch, add the following
additional Nexus Driver configuration settings:

#. Configure an additional setting named ``physnet`` under the
   ``ml2_mech_cisco_nexus`` section header.
#. Configure the VLAN range in the ``ml2_type_vlan`` section as shown in the
   Sample which follows. The ``ml2_type_vlan`` section header format is
   defined in the ``/etc/neutron/plugins/ml2/ml2_conf.ini``.
#. Configure the network VNI ranges and multicast ranges in the
   ``ml2_type_nexus_vxlan`` section.  These variables are described in
   more detail in :doc:`Nexus Configuration Reference </configuration/ml2-nexus>`.

Sample VXLAN configuration with Ethernet interfaces
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: ini

        [ml2]
        #- This neutron config specifies to use nexus_vxlan,vlan type driver
        #  and use cisco nexus mechanism driver.
        type_drivers = nexus_vxlan,vlan
        tenant_network_types = nexus_vxlan
        mechanism_drivers = openvswitch,cisco_nexus

        #- This extension driver must be enabled when the mechanism
        #  driver includes nexus.
        extension_drivers = cisco_providernet_ext

        [ml2_type_vlan]
        network_vlan_ranges = physnet1:100:109

        [ml2_mech_cisco_nexus:192.168.1.1]
        # Provide the Nexus log in information
        username=admin
        password=mySecretPasswordForNexus

        # Hostname and port used on the switch for this OpenStack host.
        # Where 1/2 indicates the "interface ethernet 1/2" port on the switch.
        host_ports_mapping=host-1:[1/2]  # deprecates config `host-1=1/2`

        # Where physnet1 is a physical network name listed in the ML2 VLAN
        # section header [ml2_type_vlan].
        physnet=physnet1

        # Setting the https_verify option below to True is highly encouraged
        # for use in a production setting. This secures the communication
        # path preventing man-in-the-middle attacks.  The default is
        # currently False but will change to True from Cisco release 6.0.0.
        https_verify=True

        [ml2_type_nexus_vxlan]
        # Comma-separated list of <vni_min>:<vni_max> tuples enumerating
        # ranges of VXLAN VNI IDs that are available for tenant network allocation.
        vni_ranges=50000:55000

        # Multicast groups for the VXLAN interface. When configured, will
        # enable sending all broadcast traffic to this multicast group.
        # Comma separated list of min:max ranges of multicast IP's
        # NOTE: must be a valid multicast IP, invalid IP's will be discarded
        mcast_ranges=225.1.1.1:225.1.1.2

.. end

.. _nexus_nodhcp_startup:

Additional configuration when the DHCP agent is not running on the Network Node
--------------------------------------------------------------------------------
If a DHCP Agent is not running on the network node then the network node
physical connection to the Nexus switch must be added to all OpenStack hosts
that require access to the network node. As an example, if the network node
is physically connected to Nexus switch 192.168.1.1 port 1/10 then the
following configuration is required.

.. code-block:: ini

        <SKIPPED Other Config defined in VLAN/VXLAN sections>
        [ml2_mech_cisco_nexus:192.168.1.1]
        ComputeHostA=1/8,1/10
        ComputeHostB=1/9,1/10
        username=admin
        password=secretPassword
        ssh_port=22
        physnet=physnet1
        https_verify=True  # for secure path if certificate available

        [ml2_mech_cisco_nexus:192.168.1.2]
        ComputeHostC=1/10
        username=admin
        password=secretPassword
        ssh_port=22
        physnet=physnet1
        https_verify=True  # for secure path if certificate available

.. end


Configuring neutron via OpenStack on OpenStack (TripleO) for Nexus
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
In this file, you can see how the parameters below are mapped to neutron
variables.  More details on these neutron variable names can be found in
:doc:`Nexus Configuration Reference </configuration/ml2-nexus>`.

.. code-block:: yaml

    resource_registry:
      OS::TripleO::AllNodesExtraConfig: /usr/share/openstack-tripleo-heat-templates/puppet/extraconfig/all_nodes/neutron-ml2-cisco-nexus-ucsm.yaml

    parameter_defaults:
      NeutronMechanismDrivers: 'openvswitch,cisco_nexus'
      NetworkNexusConfig: {
        "N9K-9372PX-1": {
            "ip_address": "192.168.1.1",
            "nve_src_intf": 0,
            "password": "mySecretPasswordForNexus",
            "physnet": "datacentre",
            "servers": {
                "54:A2:74:CC:73:51": {
                    "ports": "1/2"
                }
            },
            "ssh_port": 22,
            "username": "admin",
            "vpc_pool": "1001-1025,1030",
            "intfcfg_portchannel": "no lacp suspend-individual;spanning-tree port type edge trunk",
            "https_verify":=True
        }
      }
      NetworkNexusManagedPhysicalNetwork: datacentre
      NetworkNexusPersistentSwitchConfig: 'false'
      NetworkNexusNeverCacheSshConnection: 'false'
      NetworkNexusSwitchHeartbeatTime: 30
      NetworkNexusSwitchReplayCount: 3
      NetworkNexusCfgDriver: 'restapi'
      NetworkNexusProviderVlanAutoCreate: 'true'
      NetworkNexusProviderVlanAutoTrunk: 'true'
      NetworkNexusVxlanGlobalConfig: 'false'
      NetworkNexusHostKeyChecks: 'false'
      NeutronNetworkVLANRanges: 'datacentre:2000:2500'
      NetworkNexusVxlanVniRanges: '0:0'
      NetworkNexusVxlanMcastRanges: '0.0.0.0:0.0.0.0'
      NeutronPluginExtensions: 'cisco_providernet_ext'

.. end


VXLAN Configuration
-------------------
The Cisco specific implementation is deployed by modifying the tripleO
environment file `Tripleo Nexus Ucsm Env File <https://github.com/openstack/tripleo-heat-templates/tree/master/environments/neutron-ml2-cisco-nexus-ucsm.yaml>`_
and updating the contents with the deployment specific content. Note that with
TripleO deployment, the server names are not known before deployment. Instead,
the MAC address of the server must be used in place of the server name.
Descriptions of the parameters can be found at `Tripleo Nexus Ucsm Parm file <https://github.com/openstack/tripleo-heat-templates/tree/master/puppet/extraconfig/all_nodes/neutron-ml2-cisco-nexus-ucsm.j2.yaml>`_.
In this file, you can see how the parameters below are mapped to neutron
variables.  With these neutron variable names, more details can be
found in :doc:`Nexus Configuration Reference </configuration/ml2-nexus>`.

.. code-block:: yaml

        resource_registry:
          OS::TripleO::AllNodesExtraConfig: /usr/share/openstack-tripleo-heat-templates/puppet/extraconfig/all_nodes/neutron-ml2-cisco-nexus-ucsm.yaml

        parameter_defaults:
          NeutronMechanismDrivers: 'openvswitch,cisco_nexus'
          NetworkNexusConfig: {
            "N9K-9372PX-1": {
                "ip_address": "192.168.1.1",
                "nve_src_intf": 0,
                "password": "secretPassword",
                "physnet": "datacentre",
                "servers": {
                    "54:A2:74:CC:73:51": {
                        "ports": "1/10"
                    }
                },
                "ssh_port": 22,
                "username": "admin"
                "https_verify":=True
            }
           "N9K-9372PX-2": {
                "ip_address": "192.168.1.2",
                "nve_src_intf": 0,
                "password": "secretPassword",
                "physnet": "datacentre",
                "servers": {
                    "54:A2:74:CC:73:AB": {
                        "ports": "1/10"
                    }
                   "54:A2:74:CC:73:CD": {
                        "ports": "1/11"
                    }
                },
                "ssh_port": 22,
                "username": "admin"
                "https_verify":=True
            }
          }

          NetworkNexusManagedPhysicalNetwork: datacentre
          NetworkNexusPersistentSwitchConfig: 'false'
          NetworkNexusNeverCacheSshConnection: 'false'
          NetworkNexusSwitchHeartbeatTime: 30
          NetworkNexusSwitchReplayCount: 3
          NetworkNexusCfgDriver: 'restapi'
          NetworkNexusProviderVlanAutoCreate: 'true'
          NetworkNexusProviderVlanAutoTrunk: 'true'
          NetworkNexusVxlanGlobalConfig: 'false'
          NetworkNexusHostKeyChecks: 'false'
          NeutronNetworkVLANRanges: 'datacentre:2000:2500'
          NetworkNexusVxlanVniRanges: '50000:55000'
          NetworkNexusVxlanMcastRanges: '225.1.1.1:225.1.1.2'
          NeutronPluginExtensions: 'cisco_providernet_ext'

.. end

.. note::
    If setting ``NetworkNexusManagedPhysicalNetwork``, the per-port
    ``physnet`` value needs to be the same as
    ``NetworkNexusManagedPhysicalNetwork``.

Additional configuration when the DHCP agent is not running on the Network Node
--------------------------------------------------------------------------------
The following is the Tripleo version of configuring what was described in
the section :ref:`nexus_nodhcp_startup`.

.. code-block:: yaml

        <Skipped other config details defined in VLAN/VXLAN sections>

        parameter_defaults:
          NeutronMechanismDrivers: 'openvswitch,cisco_nexus'
          NetworkNexusConfig: {
            "N9K-9372PX-1": {
                "ip_address": "192.168.1.1",
                "nve_src_intf": 0,
                "password": "secretPassword",
                "physnet": "datacentre",
                "servers": {
                    "54:A2:74:CC:73:51": {
                        "ports": "1/10"
                    }
                },
                "ssh_port": 22,
                "username": "admin"
                "https_verify":=True
            }
            "N9K-9372PX-2": {
                "ip_address": "192.168.1.2",
                "nve_src_intf": 0,
                "password": "secretPassword",
                "physnet": "datacentre",
                "servers": {
                    "54:A2:74:CC:73:AB": {
                        "ports": "1/10"
                   }
                   "54:A2:74:CC:73:CD": {
                        "ports": "1/11"
                    }
                },
                "ssh_port": 22,
                "username": "admin"
                "https_verify":=True
            }
          }
        <Skipped other config details defined in VLAN/VXLAN sections>

.. end

Configuration Replay applied to the Nexus Switch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The Nexus mechanism driver performs a keep-alive against each known Nexus
switch every 30 seconds. If communication is lost due to switch reboot
or loss of network connectivity, it continues to check for a sign of life.
Once the switch recovers, the Nexus driver will replay all known configuration
for this switch. If neutron restarts, configuration for all known Nexus
switches is replayed. The time period to perform keep-alives for each switch
can be altered by the configuration variable ``switch_heartbeat_time``
defined under the section header ``[ml2_cisco]``.  If this feature is not
wanted, the variable should be set to 0 which disables it.  Refer to the
:doc:`Nexus Configuration Reference </configuration/ml2-nexus>` for more
details on this setting.

Provider Network Limited Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The OpenStack/network administrator may want to control how the OpenStack
create, update and delete port events program the Nexus switch for provider
networks. Two configuration variables are available to address limiting the
actions taken for provider networks during port events. The variables are
defined under the ``[ml2_cisco]`` section header.  These variables depend
on the `extension_drivers` being set to `cisco_providernet_ext` beneath
the ``[ml2]`` section header.

.. code-block:: ini

   [ml2_cisco]
   # Provider VLANs are automatically created as needed on the Nexus switch.
   provider_vlan_auto_create=[True|False]

   # Provider VLANs are automatically trunked as needed on the ports of the
   # Nexus switch.
   provider_vlan_auto_trunk=[True|False]

.. end

For more information on provider networks, refer to the
`Provider Networks <https://docs.openstack.org/ocata/networking-guide/intro-os-networking.html#provider-networks>`_
OpenStack documentation.

Neutron Trunk Support
~~~~~~~~~~~~~~~~~~~~~
Nexus driver support for the neutron trunk feature consists of the driver
programming the trunk parent port's and all subport's network segmentation ID(s)
on the switch. (See :ref:`nexus_vlan_create` for VLAN programming details.)

The VLAN IDs described in this section are the same IDs used for all Layer-2
configuration. The segmentation ID assigned to a VLAN network segment is used
to program the switch on neutron port events. These port events are triggered
when Nova instances are created, updated or deleted.

Note that the segmentation IDs assigned from the ``openstack network trunk set``
command are not used to configure the nexus top-of-rack switch. Example:

.. code-block:: console

   $ openstack network trunk set --subport port=<port ID>, segmentation-type=vlan,
     segmentation-id=<vlan ID> <trunk ID>

.. end

These VLAN IDs are used by instances attached to a virtual switch (ex. OVS).

In baremetal deployments, the trunk parent port's network segmentation ID will be
programmed on the nexus switch as both ``switchport trunk native`` and ``switchport
trunk allowed``. For trunk subports, only ``switchport trunk allowed`` is programmed.
For VM deployments, ``switchport trunk allowed`` is programmed on the switch for
both the parent and subports of the trunk.

There are no specific nexus configuration variables required for trunk support.
To enable neutron trunking, the neutron ``service_plugin`` configuration variable
must include the ``trunk`` plugin.

For more configuration and usage information on the neutron trunk feature refer
to the `Neutron/TrunkPort <https://wiki.openstack.org/wiki/Neutron/TrunkPort>`_
and neutron `Trunking <https://docs.openstack.org/ocata/networking-guide/config-trunking.html>`_
OpenStack documentation.


Troubleshooting
~~~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1

   ml2-nexus-troubleshoot
