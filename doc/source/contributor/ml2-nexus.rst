========================================
Nexus Mechanism Driver Contributor Guide
========================================

Using Devstack
~~~~~~~~~~~~~~
Devstack is used by developers to install Openstack.  It is not intended for
production use.

To install the ML2 Nexus driver along with OpenStack using devstack do as
follows:

#. Clone devstack and checkout the branch (ex: Ocata, Newton, etc) you want
   to install.

#. Configure the ML2 Nexus driver in ``local.conf`` file as shown in examples
   which follow.

#. Run :command:`./stack.sh`  to install and :command:`./unstack.sh` to
   uninstall.

Devstack configuration examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section describes how to configure the ``local.conf`` file with Nexus VLAN
details for devstack deployment.  General devstack install details are found
at other documentation links such as:

* For general devstack information, refer to
  `Devstack <https://docs.openstack.org/devstack/>`_
* For general ML2 devstack details, refer to
  `ML2_devstack <https://wiki.openstack.org/wiki/Neutron/ML2#ML2_Configuration/>`_

To configure ML2 Nexus driver in devstack, the first step required
in the ``local.conf`` file is to pull in the networking-cisco repository.
The following will cause the nexus code base to get installed.

.. code-block:: ini

    [[local|localrc]]
    enable_plugin networking-cisco https://github.com/openstack/networking-cisco
    enable_service net-cisco

.. end

Following this configuration, apply VLAN and VXLAN feature specific changes
to ``local.conf`` file as described in sections below.

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
    enable_service net-cisco

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
    ComputeHostA=1/10
    username=admin
    password=mySecretPasswordForNexus
    vpc_pool=1001-1025,1030
    intfcfg.portchannel=no lacp suspend-individual;spanning-tree port type edge trunk

    [ml2_mech_cisco_nexus:192.168.2.2]
    ComputeHostB=1/10
    username=admin
    password=mySecretPasswordForNexus
    vpc_pool=1001-1025,1030
    intfcfg.portchannel=no lacp suspend-individual;spanning-tree port type edge trunk

.. end

VXLAN Configuration
-------------------

In addition to the standard Openstack settings, follow the ``local.conf``
file example below to configure the Nexus switch for VXLAN Terminal End
Point (VTEP) support.  As you can see there is a lot of similarity between
the neutron config file and the ``local.conf`` file so details in the
neutron start-up config file sections :ref:`neutron_vxlan_startup` apply here.

.. code-block:: ini

        [[local|localrc]]
        enable_plugin networking-cisco https://github.com/openstack/networking-cisco
        enable_service net-cisco

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
        nexus_driver = restapi     # No longer required since restapi is now the default in this release.

        [ml2_mech_cisco_nexus:192.168.1.1]
        ComputeHostA=1/10
        username=admin
        password=secretPassword
        ssh_port=22
        physnet=physnet1

        [ml2_mech_cisco_nexus:192.168.1.2]
        ComputeHostB=1/10
        NetworkNode=1/11
        username=admin
        password=secretPassword
        ssh_port=22
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

``{networking-cisco install directory}/networking_cisco/plugins/ml2/drivers/cisco/nexus``

