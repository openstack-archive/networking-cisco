========================================
Nexus Mechanism Driver Contributor Guide
========================================

DevStack Configuration Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For introductory details on DevStack, refer to :doc:`/contributor/howto`.
This section focuses on Nexus VLAN and VXLAN feature specific changes
to DevStack's configuration file ``local.conf``. These changes should
follow the section which installs networking-cisco repository as described
in :doc:`/contributor/howto`.

VLAN Configuration
------------------
The following sample configuration will provide you with Nexus VLAN
Configuration.  This configuration supports both normal VM as well as
Baremetal.  As you can see there is a lot of similarity between the neutron
config file and the ``local.conf`` file so details in the neutron start-up
config file sections :ref:`nexus_vlan_startup` apply here.

.. code-block:: ini

    [[local|localrc]]
    enable_plugin networking-cisco https://github.com/openstack/networking-cisco

    # Set openstack passwords here.  For example, ADMIN_PASSWORD=ItsASecret

    # disable_service/enable_service here. For example,
    # disable_service tempest
    # enable_service q-svc

    # bring in latest code from repo.  (RECLONE=yes; OFFLINE=False)

    Q_PLUGIN=ml2
    Q_ML2_PLUGIN_MECHANISM_DRIVERS=openvswitch,cisco_nexus
    Q_ML2_TENANT_NETWORK_TYPE=vlan
    ML2_VLAN_RANGES=physnet1:100:109
    ENABLE_TENANT_TUNNELS=False
    ENABLE_TENANT_VLANS=True
    PHYSICAL_NETWORK=physnet1
    OVS_PHYSICAL_BRIDGE=br-eth1

    [[post-config|/etc/neutron/plugins/ml2/ml2_conf.ini]]
    [ml2_cisco]
    switch_heartbeat_time = 30

    [ml2_mech_cisco_nexus:192.168.1.1]
    host_ports_mapping=ComputeHostA:[1/10]  # deprecates config `ComputeHostA=1/10`
    username=admin
    password=mySecretPasswordForNexus
    vpc_pool=1001-1025,1030
    intfcfg_portchannel=no lacp suspend-individual;spanning-tree port type edge trunk

    [ml2_mech_cisco_nexus:192.168.2.2]
    host_ports_mapping=ComputeHostB:[1/10]  # deprecates config `ComputeHostB=1/10`
    username=admin
    password=mySecretPasswordForNexus
    vpc_pool=1001-1025,1030
    intfcfg_portchannel=no lacp suspend-individual;spanning-tree port type edge trunk

.. end

VXLAN Configuration
-------------------

In addition to the standard OpenStack settings, follow the ``local.conf``
file example below to configure the Nexus switch for VXLAN Terminal End
Point (VTEP) support.  As you can see there is a lot of similarity between
the neutron config file and the ``local.conf`` file so details in the
neutron start-up config file sections :ref:`neutron_vxlan_startup` apply here.

.. code-block:: ini

        [[local|localrc]]
        enable_plugin networking-cisco https://github.com/openstack/networking-cisco

        Q_PLUGIN=ml2
        Q_ML2_PLUGIN_MECHANISM_DRIVERS=openvswitch,cisco_nexus
        Q_ML2_PLUGIN_TYPE_DRIVERS=nexus_vxlan,vlan
        Q_ML2_TENANT_NETWORK_TYPE=nexus_vxlan
        ML2_VLAN_RANGES=physnet1:100:109
        ENABLE_TENANT_TUNNELS=False
        ENABLE_TENANT_VLANS=True
        PHYSICAL_NETWORK=physnet1
        OVS_PHYSICAL_BRIDGE=br-eth1

        [[post-config|/etc/neutron/plugins/ml2/ml2_conf.ini]]
        [agent]
        minimize_polling=True
        tunnel_types=

        [ml2_cisco]
        switch_hearbeat_time = 30  # No longer required since 30 is now the default in this release.

        [ml2_mech_cisco_nexus:192.168.1.1]
        host_ports_mapping=ComputeHostA:[1/10]  # deprecates config `ComputeHostA=1/10`
        username=admin
        password=secretPassword
        physnet=physnet1

        [ml2_mech_cisco_nexus:192.168.1.2]
        host_ports_mapping=ComputeHostB:[1/10]  # deprecates config `ComputeHostB=1/10`
        NetworkNode=1/11
        username=admin
        password=secretPassword
        physnet=physnet1

        [ml2_type_nexus_vxlan]
        vni_ranges=50000:55000
        mcast_ranges=225.1.1.1:225.1.1.2

        [ml2_type_vlan]
        network_vlan_ranges = physnet1:100:109

.. end

Source Code Location
~~~~~~~~~~~~~~~~~~~~
Code location for the ML2 Nexus Mechanism Driver are found in the following directory:

``{networking-cisco install directory}/networking_cisco/ml2_drivers/nexus``

