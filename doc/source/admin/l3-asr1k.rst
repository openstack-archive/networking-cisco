=====================================================
ASR1000 L3 Router Service Plugin Administration Guide
=====================================================

The ASR1000 (ASR1k) L3 Router Service Plugin (L3P) implements neutron's L3
routing service API on the Cisco ASR1000 family of routers.

Specifically it provides the following features:

* L3 forwarding between subnets on the tenants' neutron L2 networks
* Support for overlapping IP address ranges between different tenants so
  each tenant could use the same IPv4 address space, :rfc:`1918`
* P-NAT overload for connections originating on private subnets behind a
  tenant's neutron gateway routers connected to external neutron networks
* Floating IP, i.e., static NAT of a private IP address on a internal neutron
  subnet to a public IP address on an external neutron subnet/network
* Static routes on neutron routers
* HSRP-based high availability (HA) whereby a neutron router is supported by
  two (or more) ASR1k routers, one actively doing L3 forwarding, the others
  ready to take over in case of disruptions

Component Overview
~~~~~~~~~~~~~~~~~~

To implement neutron routers in ASR1000 routers the ASR1k L3P relies on two
additional Cisco components: a device manager plugin (DMP) for neutron server
and a configuration agent (CFGA).

The DMP manages a device repository in which ASR1k routers are registered. An
ASR1k router in the DMP repository is referred to as a *hosting device*.
neutron server should be configured so that it loads both the DMP and the
L3P when it starts, covered in section :ref:`conf_neutron_section`.

The CFGA is a standalone component that needs to be separately started as
neutron server cannot be configured to take care of that. The CFGA monitors
hosting devices as well as performs configurations in them upon instruction
from the L3P or the DMP. That communication is done using the regular AMQP
message bus that is used by Openstack services.

.. warning:: The ASR1k L3P and CFGA assume that nobody else manipulates the
    configurations the CFGA makes in the ASR1k routers used in the Openstack
    neutron deployment. If router administrators do not honor this
    assumption the CFGA may be unable to perform its configuration tasks.

Limitations
-----------

* The neutron deployment must use VLAN-based network segmentation. That is, the
  L2 substrate must be controlled by ML2's VLAN technology driver.
* Access to nova's Metadata service via neutron routers is not supported.
  The deployment can instead provide access via neutron's DHCP namespaces when
  IPAM is implemented using neutron DHCP agents. Alternatively, metadata can
  be provided to nova virtual machines using nova's config drive feature.
* Only one router can be attached to a particular internal neutron network.
  If a user attempts to attach a router to an internal network that already has
  another router attached to it the L3P will reject the request.

.. _conf_neutron_section:

Configuring Neutron directly for ASR1000
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The subsections that follows details the steps to be performed to properly
configure and start neutron so that ASR1k devices can host neutron routers.

Configure enabled service plugins in neutron
--------------------------------------------

Update the neutron configuration file commonly named ``neutron.conf`` so
the neutron server will load the device manager and L3 service plugins.

This file is most commonly found in the directory ``/etc/neutron``. The
``service_plugins`` configuration option should contain the following two
items:

* ``networking_cisco.plugins.cisco.service_plugins.cisco_device_manager_plugin.CiscoDeviceManagerPlugin``
* ``networking_cisco.plugins.cisco.service_plugins.cisco_router_plugin.CiscoRouterPlugin``

in addition to any other service plugins.

.. code-block:: ini

    [DEFAULT]
    service_plugins = networking_cisco.plugins.cisco.service_plugins.cisco_device_manager_plugin.CiscoDeviceManagerPlugin,networking_cisco.plugins.cisco.service_plugins.cisco_router_plugin.CiscoRouterPlugin

.. end

.. _cred_def_section:

Specify ASR credentials
-----------------------

Add credential information to the configuration file under the section
``[hosting_device_credentials]``. The format is as follows:

* :samp:`[cisco_hosting_device_credential:{UUID}]` of hosting device credentials
* :samp:`name={NAME}` of credentials
* :samp:`description={description}` of credentials
* :samp:`user_name={USERNAME}`, username of credentials
* :samp:`password={PASSWORD}`, password of credentials
* :samp:`type={TYPE}`, *not required for ASR1k, can be left empty*


The credentials are used by a CFGA when configuring ASR1k routers. For
that reason the router administrator needs to pre-configure those
credentials in the ASR1k devices.

The following is an example of credentials defined in a configuration file
that neutron server reads:

.. _cred_example:

.. code-block:: ini

    [hosting_device_credentials]
    [cisco_hosting_device_credential:1]
    name="Universal credential"
    description="Credential used for all hosting devices"
    user_name=stack
    password=cisco
    type=

.. end

.. note::
  As the credential definitions are tightly coupled to Cisco device
  management they may be placed in the file
  ``cisco_device_manager_plugin.ini``.

Define hosting device templates
-------------------------------

Define hosting device templates for ASR1k devices and devices supporting
Linux network namespace-based routers.  The hosting device template
definition should be placed in the ``[hosting_device_templates]`` section
with the following format:

* :samp:`[cisco_hosting_device_template:{UUID}]` of hosting device template
* :samp:`name={NAME}` given to hosting devices created using this template
* :samp:`enabled={True|False}`, ``True`` if template enabled, ``False`` otherwise
* :samp:`host_category={VM|Hardware|Network_Node}`
* :samp:`service_types={SERVICE_TYPES}`, *not required for ASR1k, can be left empty*
* :samp:`image={IMAGE}`, name or UUID of Glance image, *not used for ASR1k*
* :samp:`flavor={UUID}` of nova VM flavor, *not used for ASR1k*
* :samp:`default_credentials_id={UUID}` of default credentials
* :samp:`configuration_mechanism={MECHANISM}`, *not required for ASR1k, can be left empty*
* :samp:`protocol_port={PORT}` udp/tcp port for management
* :samp:`booting_time={SECONDS}`, typical booting time of devices based on this template
* :samp:`slot_capacity={INTEGER}`, abstract metric specifying capacity to host logical resources like neutron routers
* :samp:`desired_slots_free={INTEGER}`, desired number of slots to keep available at all times
* :samp:`tenant_bound={TENANT_SPEC}`, list of tenant UUIDs to which template is available, if empty available to all tenants
* :samp:`device_driver={MODULE}` to be used as hosting device driver
* :samp:`plugging_driver={MODULE}` to be used as plugging driver


The hosting device template stores information that is common for a
certain type of devices (like the ASR1k). The information is used by the DMP
and the CFGA to tailor how to they manage devices of the type in question.

The following is an example with template 1 for devices using namespaces
and template 2 for ASR1k devices):

.. _hdt_example:

.. code-block:: ini

    [hosting_devices_templates]
    [cisco_hosting_device_template:1]
    name=NetworkNode
    enabled=True
    host_category=Network_Node
    service_types=router:FW:VPN
    image=
    flavor=
    default_credentials_id=1
    configuration_mechanism=
    protocol_port=22
    booting_time=360
    slot_capacity=2000
    desired_slots_free=0
    tenant_bound=
    device_driver=networking_cisco.plugins.cisco.device_manager.hosting_device_drivers.noop_hd_driver.NoopHostingDeviceDriver
    plugging_driver=networking_cisco.plugins.cisco.device_manager.plugging_drivers.noop_plugging_driver.NoopPluggingDriver

    [cisco_hosting_device_template:3]
    name="ASR1k template"
    enabled=True
    host_category=Hardware
    service_types=router
    image=
    flavor=
    default_credentials_id=1
    configuration_mechanism=
    protocol_port=22
    booting_time=360
    slot_capacity=2000
    desired_slots_free=0
    tenant_bound=
    device_driver=networking_cisco.plugins.cisco.device_manager.hosting_device_drivers.noop_hd_driver.NoopHostingDeviceDriver
    plugging_driver=networking_cisco.plugins.cisco.device_manager.plugging_drivers.hw_vlan_trunking_driver.HwVLANTrunkingPlugDriver

.. end

A normal deployment need not modify any of the values in the example above.

.. note::
  As the hosting device template definitions are tightly coupled to Cisco
  device management, they may be placed in the file
  ``cisco_device_manager_plugin.ini``.

Add ASR1k devices to device repository
--------------------------------------

Register ASR1k devices in the device repository. The information that
needs to be provided should be placed in the ``[hosting_devices]``
section and should be formatted as:

* :samp:`[cisco_hosting_device:{UUID}]` of hosting device
* :samp:`template_id={UUID}` of hosting device template for this hosting device
* :samp:`credentials_id={UUID}` of credentials for this hosting device
* :samp:`name={NAME}` of device, e.g., its name in DNS
* :samp:`description={DESCRIPTION}` arbitrary description of the device
* :samp:`device_id={MANUFACTURER_ID}` of the device, e.g., its serial number
* :samp:`admin_state_up=True|False`, ``True`` if device is active, ``False`` otherwise
* :samp:`management_ip_address={IP ADDRESS}` of device's management network interface
* :samp:`protocol_port={PORT}` udp/tcp port of hosting device's management process
* :samp:`tenant_bound={UUID}` of tenant allowed to have neutron routers on the hosting device, if empty any tenant can have neutron routers on it
* :samp:`auto_delete={True|False}`, only relevant for VM-based hosting devices, so value is ignored for ASR1k devices


If any of the ``UUID`` values are given as an integer, they will
automatically be converted into a proper UUID when the hosting device is
added to the database. Hence, ``1`` becomes
``00000000-0000-0000-0000-000000000001``.

Once registered, the L3P starts scheduling neutron routers to those devices
that have ``admin_state_up`` set to True. Neutron routers already scheduled
to a disabled hosting device continue to operate as normal.

In the example below, two ASR1k routers are registered as hosting devices
based on hosting device template 3 and to use credentials 1 as defined in
the earlier :ref:`credentials <cred_example>` and :ref:`hosting device template <hdt_example>`
examples:

.. code-block:: ini

    [hosting_devices]
    [cisco_hosting_device:3]
    template_id=3
    credentials_id=1
    name="ASR1k device 1"
    description="ASR1k in rack 2"
    device_id=SN:abcd1234efgh
    admin_state_up=True
    management_ip_address=10.0.100.5
    protocol_port=22
    tenant_bound=
    auto_delete=False

    [cisco_hosting_device:5]
    template_id=3
    credentials_id=1
    name="ASR1k device 2"
    description="ASR1k in rack 5"
    device_id=SN:efgh5678ijkl
    admin_state_up=True
    management_ip_address=10.0.100.6
    protocol_port=22
    tenant_bound=
    auto_delete=False

.. end

The ASR1k routers have to be configured by the router administrator to
accept the credentials specified in the hosting device database record.

The plugging driver for VLAN trunking needs to be configured with the
ASR1k interfaces to use for tenant data traffic. This information is
placed in the section ``[plugging_drivers]`` and  should be structured as
follows:

* :samp:`[HwVLANTrunkingPlugDriver:{UUID}]` of hosting device
* :samp:`internal_net_interface_{NUMBER}={NETWORK_SPEC}:{INTERFACE_NAME}`
* :samp:`external_net_interface_{NUMBER}={NETWORK_SPEC}:{INTERFACE_NAME}`

The ``NETWORK_SPEC`` can be ``*``, which matches any network UUID, or a
specific network UUID, or a comma separated list of network UUIDs.

The example below illustrates how to specify that ``Port-channel 10``
in for hosting devices 3 and 4 will carry all tenant network traffic:

.. code-block:: ini

    [plugging_drivers]
    [HwVLANTrunkingPlugDriver:3]
    internal_net_interface_1=*:Port-channel10
    external_net_interface_1=*:Port-channel10

    [HwVLANTrunkingPlugDriver:5]
    internal_net_interface_1=*:Port-channel10
    external_net_interface_1=*:Port-channel10

.. end

.. note::
  As the hosting device definitions and plugging driver configurations
  are tightly coupled to Cisco device management, they may be placed in
  the file ``cisco_device_manager_plugin.ini``.

Define router types
-------------------

Define router types for neutron routers to be hosted in devices supporting
Linux network namespaces and in ASR1k devices.  The information that
needs to be provided should be placed in the ``[router_types]`` section.
The following is the format:

* :samp:`[cisco_router_type:{UUID}]` of router type
* :samp:`name={NAME}` of router type, should preferably be unique
* :samp:`description={DESCRIPTION}` of router type
* :samp:`template_id={UUID}` of hosting device template for this router type
* :samp:`ha_enabled_by_default={True|False}`, ``True`` if HA should be enabled by default, False otherwise
* :samp:`shared={True|False}`, ``True`` if routertype is available to all tenants, ``False`` otherwise
* :samp:`slot_need={NUMBER}` of slots this router type consumes in hosting devices
* :samp:`scheduler={MODULE}` to be used as scheduler for router of this type
* :samp:`driver={MODULE}` to be used by router plugin as router type driver
* :samp:`cfg_agent_service_helper={MODULE}` to be used by CFGA as service helper driver
* :samp:`cfg_agent_driver={MODULE}` to be used by CFGA agent for device configurations


A router type is associated with a hosting device template. Neutron routers
based on a particular router type will only be scheduled to hosting devices
based on the same hosting device template.

In the example below a router type is defined for neutron routers
implemented as Linux network namespaces and for neutron routers implemented
in ASR1k devices. The hosting device templates refers to the ones defined
in the earlier :ref:`hosting device template example <hdt_example>`:

.. code-block:: ini

    [router_types]
    [cisco_router_type:1]
    name=Namespace_Neutron_router
    description="Neutron router implemented in Linux network namespace"
    template_id=1
    ha_enabled_by_default=False
    shared=True
    slot_need=0
    scheduler=
    driver=
    cfg_agent_service_helper=
    cfg_agent_driver=

    [cisco_router_type:3]
    name=ASR1k_router
    description="Neutron router implemented in Cisco ASR1k device"
    template_id=3
    ha_enabled_by_default=True
    shared=True
    slot_need=2
    scheduler=networking_cisco.plugins.cisco.l3.schedulers.l3_router_hosting_device_scheduler.L3RouterHostingDeviceHARandomScheduler
    driver=networking_cisco.plugins.cisco.l3.drivers.asr1k.asr1k_routertype_driver.ASR1kL3RouterDriver
    cfg_agent_service_helper=networking_cisco.plugins.cisco.cfg_agent.service_helpers.routing_svc_helper.RoutingServiceHelper
    cfg_agent_driver=networking_cisco.plugins.cisco.cfg_agent.device_drivers.asr1k.asr1k_routing_driver.ASR1kRoutingDriver

.. end

A normal deployment need not modify any of the values in the example above
as long as the templates referred to are correct.

To ensure all neutron routers created by users are scheduled onto the ASR1k
devices, the ``default_router_type`` configuration option in the
``[routing]`` section should be set to the name of the router type
defined for ASR1k devices. For the example above, this would be done by:

.. code-block:: ini

    [routing]
    default_router_type = ASR1k_router

.. end

.. note::
  As the router type definitions are tightly coupled to Cisco ASR1000 L3
  router service plugin, they may be placed in the file
  ``cisco_router_plugin.ini``.

Make services use correct configuration files
---------------------------------------------

Include the configuration files on the command line when the neutron-server
and configuration agent is started. For example:

.. code-block:: console

   $ /usr/local/bin/neutron-server --config-file /etc/neutron/neutron
     .conf \
     --config-file /etc/neutron/plugins/ml2/ml2_conf.ini \
     --config-file /etc/neutron/plugins/ml2/ml2_conf_cisco.ini \
     --config-file /etc/neutron/plugins/cisco/cisco_router_plugin.ini \
     --config-file /etc/neutron/plugins/cisco/cisco_device_manager_plugin.ini

.. end

It looks similarly for the configuration agent:

.. code-block:: console

   $ /usr/local/bin/neutron-cisco-cfg-agent \
     --config-file /etc/neutron/neutron.conf \
     --config-file /etc/neutron/plugins/cisco/cisco_cfg_agent.ini \
     --config-file /etc/neutron/plugins/cisco/cisco_router_plugin.ini \
     --config-file /etc/neutron/plugins/cisco/cisco_device_manager_plugin.ini

.. end

High-Availability for Neutron Routers in ASR1k devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The HA is implemented using the HSRP feature of IOS XE.

When a user creates a neutron router that has HA enabled, the L3P will
automatically create a second neutron router with the same name but with
``_HA_backup_1`` added to the name. This second router is referred to as a
*redundancy router* and it is hidden from non-admin users. The HA-enabled
router the user created is referred to as the *user-visible router*.

The router-list command issued by a neutron *admin* user returns both the
user-visible and redundancy HA routers (list below has been truncated for
clarity):

.. code-block:: console

    (keystone_admin)$ neutron router-list
    +--------------------------------------+---------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------+
    | id                                   | name                            | external_gateway_info                                                                                                                       |
    +--------------------------------------+---------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------+
    | 0924ad2f-9858-4f2c-b4ea-f2aff15da682 | router1_HA_backup_1             | {"network_id": "09ec988a-948e-42da-b5d1-b15c341f653c", "external_fixed_ips": [{"subnet_id": "e732b00d-027c-45d4-a68a-10f1535000f4",         |
    |                                      |                                 | "ip_address": "172.16.6.35"}]}                                                                                                              |
    | 2c8265be-6df1-49eb-b8e9-e8c0aea19f44 | router1                         | {"network_id": "09ec988a-948e-42da-b5d1-b15c341f653c", "external_fixed_ips": [{"subnet_id": "e732b00d-027c-45d4-a68a-10f1535000f4",         |
    |                                      |                                 | "ip_address": "172.16.6.34"}]}                                                                                                              |
                     ...                                  ...                                                                           ...
    +--------------------------------------+---------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------+

.. end

The same router-list command issued by a *non-admin* user returns only the
user-visible HA router:

.. code-block:: console

    (keystone_regular)$ neutron router-list
    +--------------------------------------+---------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    | id                                   | name    | external_gateway_info                                                                                                                                              |
    +--------------------------------------+---------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    | 2c8265be-6df1-49eb-b8e9-e8c0aea19f44 | router1 | {"network_id": "09ec988a-948e-42da-b5d1-b15c341f653c", "external_fixed_ips": [{"subnet_id": "e732b00d-027c-45d4-a68a-10f1535000f4", "ip_address": "172.16.6.34"}]} |
    +--------------------------------------+---------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------+

.. end

The L3P uses a HA aware scheduler that will schedule the user-visible router
and its redundancy router on different ASR1k devices. The CFGAs managing those
ASR1k devices apply configurations for the user-visible router and its
redundancy router so that they form a HSRP-based HA pair.

External Network Connectivity and Global Routers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Connectivity to external networks for neutron routers in the ASR1k is provided
using interfaces in the global VRF of the ASR1k. The L3P represents an ASR1k's
global VRF with a special neutron router referred to as a *global* neutron
router. Global routers are only visible to admin users.

When a neutron gateway router has been scheduled to an ASR1k device, the L3P
automatically creates a global router that is scheduled to that ASR1k. This
global router will have regular router ports on every subnet of an external
neutron network. Furthermore, the global router can be connected to several
external networks if there are neutron gateway routers on the same ASR1k device
that are attached to those networks.

Continuing the example above where the HA routers were discussed, the full
list of routers are shown below:

.. code-block:: console

    (keystone_admin)$ neutron router-list
    +--------------------------------------+---------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------+
    | id                                   | name                            | external_gateway_info                                                                                                                                |
    +--------------------------------------+---------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------+
    | 0924ad2f-9858-4f2c-b4ea-f2aff15da682 | router1_HA_backup_1             | {"network_id": "09ec988a-948e-42da-b5d1-b15c341f653c", "external_fixed_ips": [{"subnet_id": "e732b00d-027c-45d4-a68a-10f1535000f4", "ip_address":    |
    |                                      |                                 | "172.16.6.35"}]}                                                                                                                                     |
    | 2c8265be-6df1-49eb-b8e9-e8c0aea19f44 | router1                         | {"network_id": "09ec988a-948e-42da-b5d1-b15c341f653c", "external_fixed_ips": [{"subnet_id": "e732b00d-027c-45d4-a68a-10f1535000f4", "ip_address":    |
    |                                      |                                 | "172.16.6.34"}]}                                                                                                                                     |
    | 5826d408-1fa3-4e01-b98a-8990060a8902 | Global-router-0000-000000000003 | null                                                                                                                                                 |
    | 66dba329-468c-4b15-8626-97a86afeaf79 | Global-router-0000-000000000005 | null                                                                                                                                                 |
    | 71336018-6390-4142-951a-f18d2f028a77 | Logical-Global-router           | null                                                                                                                                                 |
    +--------------------------------------+---------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------+

.. end

It shows two global routers: ``Global-router-0000-000000000003`` and
``Global-router-0000-000000000005``.  The table also contains a router named
``Logical-Global-router``. HSRP-based HA is also used for the global routers.
The logical global router stores HA information for the global routers, most
importantly the HSRP VIP addresses. It only exists in the neutron database and
is never explicitly seen by the CFGA.

The reason why there are two global routers in this example is the two HA
routers (the user-visible one and its redundancy) have the gateway set and are
scheduled to different ASR1k devices.

The details of router1 (see below) reveal that it has external gateway set to
subnet ``e732b00d-027c-45d4-a68a-10f1535000f4``. The
``routerhost:hosting_device`` field shows that it has been scheduled to hosting
device ``00000000-0000-0000-0000-000000000003``.

.. code-block:: console

    (keystone_admin)$ neutron router-show router1
    +-------------------------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    | Field                                           | Value                                                                                                                                                                       |
    +-------------------------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    | admin_state_up                                  | True                                                                                                                                                                        |
    | cisco_ha:details                                | {"redundancy_routers": [{"priority": 97, "state": "STANDBY", "id": "0924ad2f-9858-4f2c-b4ea-f2aff15da682"}], "probe_connectivity": false, "priority": 100, "state":         |
    |                                                 | "ACTIVE", "redundancy_level": 1, "type": "HSRP"}                                                                                                                            |
    | cisco_ha:enabled                                | True                                                                                                                                                                        |
    | description                                     |                                                                                                                                                                             |
    | external_gateway_info                           | {"network_id": "09ec988a-948e-42da-b5d1-b15c341f653c", "external_fixed_ips": [{"subnet_id": "e732b00d-027c-45d4-a68a-10f1535000f4", "ip_address": "172.16.6.34"}]}          |
    | id                                              | 2c8265be-6df1-49eb-b8e9-e8c0aea19f44                                                                                                                                        |
    | name                                            | router1                                                                                                                                                                     |
    | routerhost:hosting_device                       | 00000000-0000-0000-0000-000000000003                                                                                                                                        |
    | routerrole:role                                 |                                                                                                                                                                             |
    | routertype-aware-scheduler:auto_schedule        | True                                                                                                                                                                        |
    | routertype-aware-scheduler:share_hosting_device | True                                                                                                                                                                        |
    | routertype:id                                   | 00000000-0000-0000-0000-000000000003                                                                                                                                        |
    | routes                                          |                                                                                                                                                                             |
    | status                                          | ACTIVE                                                                                                                                                                      |
    | tenant_id                                       | fb99eb6f915342e399894a35f911b515                                                                                                                                            |
    +-------------------------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

.. end

The details of ``Global-router-0000-000000000003`` (see below) show that it is
also scheduled to hosting device ``00000000-0000-0000-0000-000000000003``.

.. code-block:: console

    (keystone_admin)$ neutron router-show Global-router-0000-000000000003
    +-------------------------------------------------+--------------------------------------+
    | Field                                           | Value                                |
    +-------------------------------------------------+--------------------------------------+
    | admin_state_up                                  | True                                 |
    | cisco_ha:enabled                                | False                                |
    | description                                     |                                      |
    | external_gateway_info                           |                                      |
    | id                                              | 5826d408-1fa3-4e01-b98a-8990060a8902 |
    | name                                            | Global-router-0000-000000000003      |
    | routerhost:hosting_device                       | 00000000-0000-0000-0000-000000000003 |
    | routerrole:role                                 | Global                               |
    | routertype-aware-scheduler:auto_schedule        | False                                |
    | routertype-aware-scheduler:share_hosting_device | True                                 |
    | routertype:id                                   | 00000000-0000-0000-0000-000000000003 |
    | routes                                          |                                      |
    | status                                          | ACTIVE                               |
    | tenant_id                                       |                                      |
    +-------------------------------------------------+--------------------------------------+

.. end

The ``external_gateway_info`` of ``Global-router-0000-000000000003`` is empty
which is expected since global routers are attached to the external networks
using regular router ports.

By listing the router ports of ``Global-router-0000-000000000003`` (see below),
it can be seen that it indeed has a router port on the same subnet as the
gateway of ``router1``.

.. code-block:: console

    (keystone_admin)$ neutron router-port-list Global-router-0000-000000000003
    +--------------------------------------+------+-------------------+------------------------------------------------------------------------------------+
    | id                                   | name | mac_address       | fixed_ips                                                                          |
    +--------------------------------------+------+-------------------+------------------------------------------------------------------------------------+
    | 9f57e5a7-bfda-4ae4-80e1-80528f7c9e1e |      | fa:16:3e:b5:0b:2a | {"subnet_id": "e732b00d-027c-45d4-a68a-10f1535000f4", "ip_address": "172.16.6.38"} |
    +--------------------------------------+------+-------------------+------------------------------------------------------------------------------------+

.. end

Although not shown, here the situation is analogous for ``router1_HA_backup_1``
and ``Global-router-0000-000000000005``. They are both scheduled to hosting
device ``00000000-0000-0000-0000-000000000005``.

Configuration Replay onto ASR1k Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The CFGA performs a keep-alive against each ASR1k router that it manages.
If communication is lost due to router reboot or loss of network connectivity,
it continues to check for a sign of life. Once the router recovers, the
CFGA will replay all neutron specific configurations for this router.
Similarly, if a CFGA is restarted, the neutron specific configuration for all
ASR1k routers it manages are replayed. Other configurations in the router
are not touched by the replay mechanism.

The time period to perform keep-alives for each router can be altered by the
configuration variable ``heartbeat_interval`` defined under the section
header ``[cfg_agent]``.  If this feature is not wanted, the configuration
variable ``enable_heartbeat`` should be set to ``False`` which disables it.
Refer to the :doc:`ASR1000 Configuration Sample<../configuration/samples/l3-asr1k>`
for more details on these settings.

High-Availability for Configuration Agents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Since no configurations can be made to an ASR1k router if the CFGA managing
that router is dead, a high-availability mechanism is implemented for CFGA. The
CFGA HA requires that at least two CFGA are deployed. If a CFGA dies, the
DMP will select another CFGA to take over management of the hosting devices
(the ASR1k routers) that were managed by the dead CFGA. The detailed
activities are described in the remainder of this section.

Whenever a neutron REST API update operation is performed on a neutron
router, a notification will be sent to the CFGA managing the ASR1k that
hosts the neutron router. At that point, the status of the CFGA is checked.
If the CFGA has not sent a status report recently, it is considered dead and
the hosting device will be un-assigned from that CFGA. The time interval
after which a device is considered dead can be modified using the
``cfg_agent_down_time`` configuration option.

After that, an attempt to reschedule the hosting devices to another CFGA will
be performed. If it succeeds, the hosting device will be assigned to that CFGA
and then the notification will be sent. If not, the hosting device will not be
assigned to any config agent but new re-scheduling attempts will be performed
periodically.

Every 20 seconds (configurable through the configuration option
``cfg_agent_monitoring_interval``), any CFGA that has not been checked in the
last 20 seconds (because of a notification) will be checked. If the CFGA is
determined to be dead, all hosting devices handled by that CFGA will be
unassigned from that CFGA.

An attempt to reschedule each of those hosting devices to other CFGA will be
performed. Those attempts that succeed will result in the corresponding ASR1k
router being assigned to the CFGA returned by the scheduler. Those attempts
that fail will result in the ASR1k remaining unassigned.

Hence, an ASR1k will either be rescheduled as a consequence of a neutron
router notification or by the periodic CFGA status check.

Scheduling of hosting devices to configuration agents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Two hosting device-to-CFGA schedulers are available. The
``configuration_agent_scheduler_driver`` configuration option in the
``[general]`` section determines which scheduler the L3P uses.

Random
------
* Hosting device is randomly assigned to the first available CFGA
* Two hosting devices can end up being assigned to the same CFGA
* ``configuration_agent_scheduler_driver = networking_cisco.plugins.cisco.device_manager.scheduler.hosting_device_cfg_agent_scheduler.HostingDeviceCfgAgentScheduler``

Load-balanced
-------------
* Attempts to load-balance hosting devices across available CFGA
* A hosting device is assigned to the CFGA managing the least number of
  hosting devices
* ``configuration_agent_scheduler_driver = networking_cisco.plugins.cisco.device_manager.scheduler.hosting_device_cfg_agent_scheduler.StingyHostingDeviceCfgAgentScheduler``

Troubleshooting
~~~~~~~~~~~~~~~
* To triage issues and verify that the L3P, DMP, CFGA, and the ASR1k
  routers are operating correctly, the following steps can be performed:

  #. Use the ``neutron agent-list`` command to make sure that at least one
     CFGA (i.e., ``neutron-cisco-cfg-agent``) is running with alive state
     showing ``:-)``. Also ensure that any deployed L3 agent (i.e.,
     ``neutron-l3-agent``) is disabled, indicated by alive state of ``xxx``:

     .. code-block:: console

        (keystone_admin)$ neutron agent-list
        +--------------------------------------+--------------------+------------------+-------+----------------+---------------------------+
        | id                                   | agent_type         | host             | alive | admin_state_up | binary                    |
        +--------------------------------------+--------------------+------------------+-------+----------------+---------------------------+
        | 019fdca0-6310-43f6-ae57-005fbbd1f672 | L3 agent           | tme166.cisco.com | xxx   | True           | neutron-l3-agent          |
        | 1595c8ce-3ec5-4a01-a1d8-c53cd0cd4970 | DHCP agent         | tme166.cisco.com | :-)   | True           | neutron-dhcp-agent        |
        | 61971f98-75f0-4d03-a130-88f7228c51a1 | Open vSwitch agent | tme167.cisco.com | :-)   | True           | neutron-openvswitch-agent |
        | 8d0de547-a7b8-4c33-849b-b0a7e38198b0 | Metadata agent     | tme166.cisco.com | :-)   | True           | neutron-metadata-agent    |
        | cdfc51b4-88b6-4d84-bfa3-2900914375cc | Open vSwitch agent | tme166.cisco.com | :-)   | True           | neutron-openvswitch-agent |
        | fbc8f44b-64cd-4ab1-91d8-32dbdf10d281 | Cisco cfg agent    | tme166.cisco.com | :-)   | True           | neutron-cisco-cfg-agent   |
        +--------------------------------------+--------------------+------------------+-------+----------------+---------------------------+

     .. end

  #. If cisco-cfg-agent is not running [xxx] then check the output of
     :command:`systemctl status neutron-cisco-cfg-agent.service` to make
     sure that its loaded and active or any errors that it shows.

  #. Check the logs for config-agent at
     ``/var/log/neutron/cisco-cfg-agent.log`` and see if there are any errors
     or tracebacks.

  #. Verify that a hosting-device-template for ASR1k routers is defined:

     .. code-block:: console

        (keystone_admin)$ neutron cisco-hosting-device-template-list
        +--------------------------------------+-----------------+---------------+---------------+---------+
        | id                                   | name            | host_category | service_types | enabled |
        +--------------------------------------+-----------------+---------------+---------------+---------+
        | 00000000-0000-0000-0000-000000000001 | NetworkNode     | Network_Node  | router:FW:VPN | True    |
        | 00000000-0000-0000-0000-000000000003 | ASR1k template  | Hardware      | router        | True    |
        +--------------------------------------+-----------------+---------------+---------------+---------+

     .. end

     .. note::
         The above command must be performed as administrator.

     If the Cisco extensions to neutronclient are not installed a query
     to the neutron ``cisco_hosting_device_templates`` DB table can instead
     be performed. The following shows how this is done when MySQL is used:

     .. code-block:: console

        $ mysql -e "use neutron; select * from cisco_hosting_device_templates;"

     .. end

  #. Verify that the ASR1k routers are registered in the device repository:

     .. code-block:: console

        (keystone_admin)$ neutron cisco-hosting-device-list
        +--------------------------------------+----------------+--------------------------------------+----------------+--------+
        | id                                   | name           | template_id                          | admin_state_up | status |
        +--------------------------------------+----------------+--------------------------------------+----------------+--------+
        | 00000000-0000-0000-0000-000000000003 | ASR1k device 1 | 00000000-0000-0000-0000-000000000003 | True           | ACTIVE |
        | 00000000-0000-0000-0000-000000000004 | ASR1k device 2 | 00000000-0000-0000-0000-000000000003 | True           | ACTIVE |
        +--------------------------------------+----------------+--------------------------------------+----------------+--------+

     .. end

     .. note::
         The above command must be performed as administrator.

     Alternatively, as a DB query:

     .. code-block:: console

        $ mysql -e "use neutron; select * from cisco_hosting_devices;"

     .. end

  #. Verify that a router type for ASR1k routers is defined:

     .. code-block:: console

        (keystone_admin)$ neutron cisco-router-type-list
        +--------------------------------------+--------------------------+-------------------------------------------------------+--------------------------------------+
        | id                                   | name                     | description                                           | template_id                          |
        +--------------------------------------+--------------------------+-------------------------------------------------------+--------------------------------------+
        | 00000000-0000-0000-0000-000000000001 | Namespace_Neutron_router | Neutron router implemented in Linux network namespace | 00000000-0000-0000-0000-000000000001 |
        | 00000000-0000-0000-0000-000000000003 | ASR1k_router             | Neutron router implemented in Cisco ASR1k device      | 00000000-0000-0000-0000-000000000003 |
        +--------------------------------------+--------------------------+-------------------------------------------------------+--------------------------------------+

     .. end

     Alternatively, do:

     .. code-block:: console

        $ mysql -e "use neutron; select * from cisco_router_types;"

     .. end

  #. Verify that there is ip connectivity between the controllers and the
     ASR1K routers.

  #. Check the netconf sessions on the ASR1K using the
     ``show netconf session`` command.

  #. Collect logs from ``/var/log/neutron/server.log`` and
     ``/var/log/neutron/cisco-cfg-agent.log``.

  #. If new code is being pulled for bug fixes, run the steps in the section
     :doc:`/install/howto` and restart neutron and configuration agent
     services.

* The hosting-device states reported by the CFGA and their meaning are as
  follows:

  `ACTIVE`
    Active means the hosting device is up, responds to pings and is
    configurable.

  `NOT RESPONDING`
    Not responding means the hosting device does not respond
    to pings but has not yet been determined to be dead or faulty.

  `ERROR`
    Error means the hosting device has been determined to be faulty;
    meaning it may respond to pings but other symptoms indicate it is faulty.

  `DEAD`
    Dead means the hosting device has been determined to be dead in
    that it does not respond to pings even given multiple, repeated attempts.
