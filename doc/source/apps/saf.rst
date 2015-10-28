===================================
Cisco Nexus StandAlone Fabric (SAF)
===================================

1. General
----------

This is an installation guide for enabling nexus fabric support on OpenStack

Please refer to nexus fabric system configuration for how to bring up
the fabric using a spine and leaf topology with DCNM as the fabric manager.
The compute node in an OpenStack setup should be connected to the nexus
fabric leaf switch. This link on the compute node/server is often
referred as uplink in this note.

This guide does not cover OpenStack installation.


2. Prerequisites
----------------
The prerequisites for installing Nexus fabric OpenStack enabler are the
following:

    - Install LLDPad
    - Install OVS (version 2.3.x)

3. Fabric Enabler Installation
------------------------------

:3.1 Using devstack:

In this scenario, SAF will be installed along with openstack using devstack

    1. Clone devstack.

    2. Use ``networking-cisco/devstack/saf/local.conf.compute.saf`` and ``networking-cisco/devstack/saf/local.conf.control.saf`` as and example to create local.conf for control and compute nodes and set the required parameters in the local.conf based on the your setup.

    3. Run ./stack.sh
        

:3.2 On a setup with OpenStack already installed:

In this scenario, SAF will be installed on a setup which has already OpenStack installed:

1. Clone networking-cisco_.

   .. _networking-cisco: https://github.com/openstack/networking-cisco

2. The following modifications are needed in:

  ::

    2.1 /etc/neutron/plugins/ml2/ml2_conf.ini

    [ml2]
    type_drivers = local
    mechanism_drivers = openvswitch

    [ovs]
    bridge_mappings = ethd:br-ethd

    [agent]
    tunnel_types = 

    Following sections should remain empty:
    [ml2_type_flat]
    [ml2_type_vlan]
    [ml2_type_gre]
    [ml2_type_vxlan]


    L3 agent  - must be disabled
    DHCP service - must be disabled


    2.2 neutron.conf:

    [DEFAULT]
    notification_driver = messaging
    notification_topics = cisco_dfa_neutron_notify
    rpc_backend = rabbit

    [keystone_authtoken]
    ...
    auth_host = <ip address of controller>
    auth_port = 35357
    admin_tenant_name = service
    admin_user = neutron
    admin_password = <admin password>
    ...

    2.3 nova.conf:
    
    [keystone_authtoken]
    ...
    admin_password = <admin password>
    admin_user = nova
    admin_tenant_name = service
    auth_uri = http://<ip address of controller>:5000/v2.0
    auth_host = <ip address of controller>
    ...


    3.3 keystone.conf:
    [DEFAULT]
    notification_driver = messaging
    notification_topics = cisco_dfa_keystone_notify
    admin_endpoint = http://<services ip address>:%(admin_port)s/
    rpc_backend = rabbit


4. ``cd networking-cisco``

5. Edit ``networking-cisco/etc/saf/enabler_conf.ini``

   Set the parameters in each section of the enabler_conf.ini based on your setup

6. Run ``python tools/saf_prepare_setup.py``

7. Run ``sudo python setup.py install``

8. On controller node run:

   - On ubuntu based server:

    ``sudo start fabric-enabler-server``

   - On Red Hat based server:
    
    ``sudo systemctl start fabric-enabler-server``

9. On compute node run:

   - On ubuntu based server:

    ``sudo start fabric-enabler-agent``

   - On Red Hat based server:
    
    ``sudo systemctl start fabric-enabler-agent``
