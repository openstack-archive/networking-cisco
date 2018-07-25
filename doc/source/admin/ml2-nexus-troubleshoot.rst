Introduction
------------
The details in this section identify common problems which can be
encountered, error messages that can be seen for each problem, and
the actions the user can take to resolve each problem.  A good place
to start triaging is to peruse the neutron log file for error messages by
searching for strings such as ``ERROR`` or ``Traceback``. If
you find a Nexus driver error in the log file, you can search this guide
for snippets from the log message.

All Nexus Mechanism Driver log messages appear in the same log file as
neutron.  To isolate Nexus log messages from other neutron log entries,
grep on 'nexus'.  The location of OpenStack log messages vary according
to each install implementation.

At times, the problems can not be resolved by the administrator and
requires intervention by Cisco Tech Support.  If this is the only
recourse left, then gather the following information to provide to
Tech Support so they can better assist you.

* If an installer is being used for deployment, identify what installer is
  being used and provide a copy of its log files.

* Provide compressed OpenStack log files::

      tar -xvfz openstack-log-files.tar.gz {OpenStack log directory}

* Provide a copy of the current configuration of all participating
  Nexus Switches in your network. This can be done with the Nexus command::

      copy run off-load-nexus-config-for-viewing

* Dump content of Nexus driver databases into files using commands
  defined in :ref:`db_show`.

* Provide a network diagram with connection details.

.. _db_show:

How to view Nexus Driver databases
----------------------------------
To help triage issues, it may be helpful to peruse the following database
tables:

#. To view the content of the Nexus Driver port binding database table:
   In addition to port entries, the switch state is also saved in here.
   These special entries can be identified with an instance_id of
   ``RESERVED_NEXUS_SWITCH_DEVICE_ID_R1``.

   .. code-block:: console

       mysql -e "use neutron; select * from cisco_ml2_nexusport_bindings;"

   .. end

#. To view the content of the Nexus Driver port mapping database table:

   .. code-block:: console

       mysql -e "use neutron; select * from cisco_ml2_nexus_host_interface_mapping;"

   .. end

#. To view the content of the Nexus Driver VPC ID port database table:

   .. code-block:: console

       mysql -e "use neutron; select * from cisco_ml2_nexus_vpc_alloc;"

   .. end

#. To view the content of the Nexus Driver VNI allocation port database table:

   .. code-block:: console

       mysql -e "use neutron; select * from ml2_nexus_vxlan_allocations;"

   .. end

#. To view the content of the Nexus Driver Mcast mapping database table:

   .. code-block:: console

       mysql -e "use neutron; select * from ml2_nexus_vxlan_mcast_groups;"
       mysql -e "use neutron; select * from cisco_ml2_nexus_nve;"

   .. end

Create Event Failures
---------------------
Description
^^^^^^^^^^^
As events for port creation are received, the Nexus Driver makes sure at
least one of the switches for each event are active.  If it fails to
reach a switch, Message 1 below will appear.  After checking all switches
and it is determined there are no active switches needed for this event,
then the exception (message 2 below) will appear and the event is rejected.

Message
^^^^^^^

::

    1. Failed to ping switch ip {switch_ip} error {exp_err}
    2. NexusConnectFailed: <snip> Create Failed: Port event can not be
       processed at this time.

Corrective Action
^^^^^^^^^^^^^^^^^
Refer to `corrective actions` defined in :ref:`connect_loss` for steps to
narrow down why switch(s) are not active.

Update/Delete Event Failures
----------------------------
Description
^^^^^^^^^^^
As Update or Delete configuration events are received, there are a couple
exceptions which can be raised by Nexus Driver.  When events are
sent to the configuration driver, they can fail during the authorization
phase with the exception ``NexusConnectFailed`` or during the actual
configuration with the exception ``NexusConfigFailed``.  The following
illustrates what appears for these exceptions:

#. ``NexusConnectFailed``: Unable to connect to Nexus {switch-ipaddr}.
   ``Reason``: {error returned from underlying REST API or the Nexus switch}
#. ``NexusConfigFailed``: Failed to configure Nexus switch: {switch-ipaddr}
   ``Config``: REST API path: REST API body
   ``Reason``: {error returned from underlying REST API or the Nexus switch}

Notice the ``NexusConfigFailed`` exception has a ``Config:`` parameter. This
provides information of what object the driver was trying to configure
(REST API path) and what value(s) the driver was trying to change (REST API
body).

The exception is accompanied by a ``Reason:`` parameter which returns the exact
error received by the Nexus REST API driver from one of two sources:

* The lower layer REST API code could return an error. See the section
  :ref:`connect_loss` for an example of an error from the lower layer
  REST API driver as well as Message 2 below.
* The error comes from the Nexus Switch itself.  See the section
  `Missing Nexus Switch VXLAN Prerequisite Config`_ for an example of
  an error generated by Nexus Switch.

The ``Reason`` clause provides the details needed to narrow down the error.
Since the ``Reason`` clause contains the specific details to the error message,
it will be reduced to the following for the remainder of the `Troubleshooting`
section.

Message
^^^^^^^

::

    1. NexusConnectFailed: <SNIP>, Reason: Update Port Failed: Nexus Switch is
       down or replay in progress.
    2. NexusConfigFailed: <SNIP>, Reason: HTTPConnectionPool(
       host={switch-ipaddr}, port=80): Read timed out. (
       read timeout=30)

Corrective Action
^^^^^^^^^^^^^^^^^
#. Check the section :ref:`connect_loss` for the most likely lower layer
   REST API error.  Message 2 above is an example of the output you
   would see.
#. Errors returned by the Nexus switch cannot be documented in this
   section.  You can determine what object failed to update by analyzing
   what's in the ``Config:`` clause of the exception and manually applying
   the same action using the Nexus switch CLI.
#. The ``NexusConnectFailed`` error (message 1 above) is a special case
   where the reason is generated by Nexus Driver.  In this case, the Nexus
   driver receives update events from neutron but configuration replay has
   not fully initialized or in process of reconfiguring the switch, or the
   switch is down.  This may be a temporary glitch.  Updates are resent to
   Nexus Driver and the switch is configured when the switch becomes active.

.. _connect_loss:

Connection loss with Nexus Switch
---------------------------------
Description
^^^^^^^^^^^
The most likely error to encounter is loss of connectivity to the Nexus
switch either due to Nexus switch rebooting or breakage in the network
itself.  One or either of the exceptions shown below can occur during
configuration events.   The first occurs if the driver was performing an
authorization request prior to configuration.  The latter occurs if the
driver was attempting a configuration request.  Either case will fail with a
timeout error as shown in the messages listed below.

Message
^^^^^^^

::

    1. NexusConnectFailed: <SNIP>, Reason: HTTPConnectionPool(
        host={switch-ipaddr}, port=80): Max retries exceeded with url:
        /api/aaaLogin.json (Caused by ConnectTimeoutError(
        Connection to {switch-ipaddr} timed out.  (connect timeout=60))
    2. NexusConfigFailed: <SNIP>, Reason: HTTPConnectionPool(
        host={switch-ipaddr}, port=80): Read timed out. (read timeout=30)

Corrective Action
^^^^^^^^^^^^^^^^^

* Check if the Nexus switch is accessible from the OpenStack
  Controller node by issuing a ping to the Nexus Switch ip address.
* If the switch is accessible, check the Nexus port binding database as
  described in section :ref:`db_show` and look for
  ``RESERVED_NEXUS_SWITCH_DEVICE_ID_R1``.  Check the following if the switch is
  shown as ``INACTIVE``.

  #. Check the credentials configured for this switch in the neutron start-up
     configuration file.  Make sure the switch IP address is correct and
     the credential information is correct. See the various configuration
     examples in the section
     :ref:`nexus_vlan_startup` for details.
  #. Check that ``feature nxapi`` is configured on the Nexus Switch since
     it is required for Nexus Mechanism driver to use the REST API Config
     driver.

* If the switch is not accessible, isolate where in the network a
  failure has occurred.

  #. Is Nexus Switch management interface down?
  #. Is there a failure in intermediary device between the OpenStack
     Controller and Nexus Switch?
  #. Can the next hop device be reached?

* Check if the switch is running by accessing the console.

Configuration Replay Messages
-----------------------------
Description
^^^^^^^^^^^
The Nexus driver periodically performs a get request to the Nexus switch
to make sure the communication path is open.  A log message (See Message 1
below) is generated the first time the get request fails.  The Nexus Driver
will indefinitely continue to send the get request until it is successful
as indicated by log message 2 below.  Once connectivity is established, the
configuration for this Nexus switch is replayed and successful completion of
the reconfiguration is show in the log message 3 below.  If there were
no port bindings found for a switch, message 4 will be seen. This may be
due to no port events received for this switch and the switch state has
toggled.  For failures during the replay of the switch configuration,
refer to the section `Replay of Configuration Data Failed`_.

Message
^^^^^^^

::

    1. Lost connection to switch ip {switch_ip}
    2. Re-established connection to switch  ip {switch_ip}
    3. Restore of Nexus switch ip {switch_ip} is complete
    4. No port entries found for switch ip {switch_ip} during replay

Corrective Action
^^^^^^^^^^^^^^^^^
1. To monitor the state of the target switch from the perspective of
   the Nexus Driver, database commands can be used.  Refer to section
   :ref:`db_show` and look for ``RESERVED_NEXUS_SWITCH_DEVICE_ID_R1``.
2. Fix any failed connectivity issues as described in
   :ref:`connect_loss`.

Replay of Configuration Data Failed
-----------------------------------
Description
^^^^^^^^^^^
The Nexus driver has detected the Nexus switch is up and it is attempting
to reconfigure.  Occasionally configurations will fail since the switch is
not fully ready to handle configurations.  Any number of the messages
listed below can be seen for this failure.

Message
^^^^^^^

::

    1. Unexpected exception while replaying entries for switch {switch_ip}
       Reason: {Contains error details from lower layers}
    2. Unable to initialize interfaces to switch {switch_ip}
    3. Replay config failed for ip {switch_ip}
    4. Error encountered restoring vlans for switch {switch_ip}
    5. Error encountered restoring vxlans for switch {switch_ip}

Corrective Action
^^^^^^^^^^^^^^^^^
This may be a temporary glitch and should recover on next replay retry.
If the problem persists, contact Tech Support for assistance.

Nexus Switch is not getting configured
--------------------------------------
Description
^^^^^^^^^^^
The only difference between this case and what is described in the section
:ref:`connect_loss` is the Nexus switch has never been successfully
configured after neutron start-up.  Refer to the connection loss section
for more details to triage this case.

Message
^^^^^^^
There's no specific error message for this other than some shown in
:ref:`connect_loss` section.

Corrective Action
^^^^^^^^^^^^^^^^^
There are a couple possible reasons for this issue:

* It may be due to a connection loss or never having a connection with the
  switch.  See the :ref:`connect_loss` for more triage hints
  details like how to check the state of the switch and configuration errors
  that can occur.
* It is possible the hostname is not correctly configured in the neutron
  start-up file beneath the nexus switch section named `ml2_mech_cisco_nexus`.
  Depending on the configuration of the OpenStack host, the hostname to
  configure is the long name `hostname.domainname` which can be derived by
  running `hostname -f` on the host itself. Additionally if you enable
  debug in neutron start-up config file and search for the log entry
  `Attempting to bind port {port} on host {hostname}`, the `hostname` in
  this message is the same name used in Nexus look-ups.  Configure this
  name in the neutron start-up file and restart neutron.

No Nexus Configuration in the neutron start-up file
---------------------------------------------------
Description
^^^^^^^^^^^
If there are no Nexus switches configured in the neutron start-up
configuration file, the error message below will be seen in the neutron
log file.

Message
^^^^^^^

::

    No switch bindings in the port database

Corrective Action
^^^^^^^^^^^^^^^^^
#. Check Sample configurations throughout this guide on configuring switch
   details.  Specifically look for the section header `ml2_mech_cisco_nexus`.
   Also refer to the
   :doc:`Nexus Configuration Reference </configuration/ml2-nexus>`.
#. When neutron is started, make sure the Nexus configuration is in
   the configuration file provided to neutron at start-up.

Nexus Switch not defined in the neutron start-up file
-----------------------------------------------------
Description
^^^^^^^^^^^
If there is Nexus configuration defined in the neutron start-up but
there is nothing found for a specific switch, these messages below
will be seen.  Message 1 is generated for baremetal port events while
message 2 is generated for non-baremetal events.

Message
^^^^^^^

::

    1. Skip switch {switch_ip}.  Not configured in ini file
    2. Host {switch_ip} not defined in switch configuration section.

Corrective Action
^^^^^^^^^^^^^^^^^
Check Sample configurations throughout this guide on configuring switch
details.  Specifically look for the section header `ml2_mech_cisco_nexus`.
Also refer to the
:doc:`Nexus Configuration Reference </configuration/ml2-nexus>`.

Missing Nexus Switch VXLAN Prerequisite Config
----------------------------------------------
Description
^^^^^^^^^^^
An attempt was made to configure
:command:`member vni <vni-id> mcast-group <mcast-ip>` beneath
:command:`int nve 1` but an error was returned by the REST API configuration
driver used by the Nexus Driver.  Possible reasons are:

1. Nexus switch can't find configured object. See message listed below
   for sample detail in reason space of exception.
2. loss of connectivity with switch. See :ref:`connect_loss`.

Message
^^^^^^^

::

    Failed to configure nve_member for switch {switch_ip}, vni {vni}
        Reason: NexusConfigFailed: <SNIP>, Reason:
        {"imdata":[{ "error": { "attributes": { "code": "102",
        "text": "configured object ((Dn0)) not found
        Dn0=sys\/epId-1\/nws\/vni-70037, "}

Corrective Action
^^^^^^^^^^^^^^^^^
Some general VXLAN configuration must be in place prior to Nexus Driver
driver attempting to configure vni and mcast-group configuration.  Refer
to the `Prerequisite` section of :ref:`neutron_vxlan_startup` and the
section :ref:`switch_setup` for more details.

Invalid ``vpc_pool`` config error
---------------------------------
Description
^^^^^^^^^^^
The ``vpc_pool`` configuration parameter is a pool used for automatically
creating port-channel ids for baremetal events.  As `vpc_pool` is parsed,
a number of errors can be detected and are reported in the messages below.
For a detail description of configuring ``vpc-pool`` parameter, refer to
:doc:`Nexus Configuration Reference </configuration/ml2-nexus>`.

Message
^^^^^^^

::

    1. Unexpected value {bad-one} configured in vpc-pool config
       {full-config} for switch {switchip}. Ignoring entire config.
    2. Incorrectly formatted range {bad-one} config in vpc-pool
       config {full-config} for switch {switchip}. Ignoring entire config.
    3. Invalid Port-channel range value {bad-one} received in vpc-pool
       config {full-config} for switch {switchip}. Ignoring entire config.

Corrective Action
^^^^^^^^^^^^^^^^^
In each message, the ``{bad-one}`` field is the portion of the
``{full-config}`` field which is failing the parsing.  The ``{full-config}``
is what the user configured for a given ``{switchip}`` in the ``vpc_pool``
configuration parameter.  Possible issues for each message can be:

1. Values in the range are not numeric. Ex: 2-abc
2. There should only be a min-max value provided. More than two
   values separated by '-' can not be processed. Ex: 3-5-7
3. Values in range must meet valid port-channel range on Nexus
   where smallest is 1 and largest is 4096. ex: 0-5 or 4090-4097

Learned Port-channel Configuration Failures for Baremetal Events
----------------------------------------------------------------
Description
^^^^^^^^^^^
If a baremetal event is received with multiple ethernet interfaces, the first
in the list indicates how the rest will be treated.  If it is determined the
first interface is preconfigured as a member of a port-channel, the
expectation is the remaining interfaces should also be preconfigured as
members of the same port-channel.  If this is not the case, the exception
below will be raised.

Message
^^^^^^^

::

    1. NexusVPCLearnedNotConsistent: Learned Nexus channel group
       not consistent on this interface set: first interface
       {first}, second interface {second}.  Check Nexus
       Config and make consistent.
    2. NexusVPCExpectedNoChgrp: Channel group state in baremetal
       interface set not consistent: first interface %(first)s,
       second interface %(second)s. Check Nexus Config and make consistent.

Corrective Action
^^^^^^^^^^^^^^^^^
The message fields ``{first}`` and ``{second}`` each contain the host,
interface and the channel-group learned.  The ``{first}`` is the basis
interface compared to and the ``{second}`` is the interface that does not
match the channel-group of the ``{first}``.

* Message 1 is seen when the ``{first}`` is a member of a channel group and
  ``{second}`` does not match channel group of the ``{first}``.
* Message 2 is seen when the ``{first}`` is not a member of a channel group
  while the ``{second}`` is.

Log into each switch identified in ``{first}`` and ``{second}`` fields and
make sure each interface is a member of the same port-channel if learning is
desired.  If automated port-channel creation is preferred, see
`Automated Port-channel Creation Failures for Baremetal Events`_.

Automated Port-channel Creation Failures for Baremetal Events
-------------------------------------------------------------
Description
^^^^^^^^^^^
Baremetal events received with multiple ethernet interfaces are treated as
port-channel interfaces.   The first interface in the list indicates
how the rest will be treated.  If all interfaces are currently not members of
a port-channel, then the Nexus Driver will try and create a port-channel
provided the Nexus Driver configuration parameter ``vpc-pool`` has been
defined for each switch.  For details on the activity the Nexus Driver
performs to configure the port-channel, refer to :ref:`nexus_vlan_create`.

Message
^^^^^^^

::

    1. NexusVPCAllocFailure: Unable to allocate vpcid for all switches
       {ip_list}
    2. NexusVPCExpectedNoChgrp: Channel group state in baremetal
       interface set not consistent: first interface {first},
       {second} interface %(second)s.  Check Nexus Config and make consistent.

Corrective Action
^^^^^^^^^^^^^^^^^
1. The first exception ``NexusVPCAllocFailure`` will be raised if the
   ``vpc-pool`` is not configured or the pool of one of the participating
   switches has been depleted.  The pools can be viewed using port mapping
   database query command as shown in :ref:`db_show`.  For details on
   configuring ``vpc-pool`` parameter, refer to
   :doc:`Nexus Configuration Reference </configuration/ml2-nexus>`.
2. Exception 2 is raised when the ``{first}`` is not a member of a channel
   group while the ``{second}`` is.  Log into each switch identified in
   ``{first}`` and ``{second}`` fields and make sure each interface is not a
   member of port-channel.  If learning the port-channel is preferred, make
   sure all interfaces are configured as members to the same port-channel.

Invalid Baremetal Event
-----------------------
Description
^^^^^^^^^^^
A baremetal event has been received but the Nexus Driver was unable to
decode the ``switch_info`` data in the port event. As a result, the event is
ignored by the Nexus driver.

Message
^^^^^^^

::

    switch_info can't be decoded {reason}

Corrective Action
^^^^^^^^^^^^^^^^^
This error should not occur and suggest looking for earlier errors in
the log file.  If unable to triage further from log messages, contact
Tech Support for assistance.

Trunk Configuration Conflict on Nexus Switch
--------------------------------------------
Description
^^^^^^^^^^^
During interface initialization, the Nexus driver collects trunking information
for interfaces from the Nexus switch. This occurs at start-up for statically
configured ports and on receipt of a port event for baremetal ports.  The
driver looks for trunking vlans configured using
:command:`switchport trunk allowed vlan <vlanid(s)>` and also checks if the
mode type in :command:`switchport mode <type>` is ``trunk``.

The Nexus driver logs a warning if there are trunking vlans configured but
the trunk mode is not ``trunk``.   The driver does not try to resolve the
conflict since the correction can be done in a number of ways which requires
attention from the administrator.  The driver does continue to add and
remove vlans to this interface.  However, since the trunk mode is missing,
the data traffic does not pass on this interface.

Message
^^^^^^^
Found trunk vlans but switchport mode is not trunk on Nexus switch {switch}
interface {interface}. Recheck config.

Corrective Action
^^^^^^^^^^^^^^^^^
Look at the interface on the Nexus Switch identified in the message and check
for the following possible errors.

* For VM deployments, ensure the OpenStack Nexus driver is configured with the
  correct interface for the intended OpenStack host.
* Ensure :command:`switchport mode trunk` is configured on the interface.
* Ensure only vlans required as provider vlans or within your tenant vlan
  range are configured as ``allowed`` on the interface, and any additional
  vlans are removed.

Insecure Communication Path with Nexus Switch
---------------------------------------------
Description
^^^^^^^^^^^
The configuration option `https_verify` is available in 5.4.0 and defaults
to ``False`` (insecure); however, from Cisco Release 6.0.0 it will change
to ``True`` causing certificates to be verified.  It is highly recommended
not to disable certificate verification in production since the communication
path is insecure leaving the path vunerable to man-in-the-middle attacks.
If a switch is insecure, the warning message below will be seen in the neutron
log file identifying the ip address of the Nexus switch.

Message
^^^^^^^
HTTPS Certificate verification is disabled. Your connection to Nexus Switch
{ip} is insecure.

Corrective Action
^^^^^^^^^^^^^^^^^
The {ip} in the error message targets which switch is insecure and needs
one or more of the following actions to secure it.

* If a publically known certificate is not currently available, apply for one
  from a public Certificate Authority (CA).
* If the certificate and key files have not been configured on the
  target Nexus switch, configure them using the Nexus Management CLI
  `nxapi certificate` and `enable` the certificate.  For Nexus details,
  refer to the section `NX-API Management Commands`  in the
  `Nexus NXAPI Programmability Guide <https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus9000/sw/6-x/programmability/guide/b_Cisco_Nexus_9000_Series_NX-OS_Programmability_Guide/b_Cisco_Nexus_9000_Series_NX-OS_Programmability_Guide_chapter_011.html>`_.
* Set `https_verify=True` in the neutron start-up configuration beneath the
  section header [ml2_mech_cisco_nexus:your-switch-ip] for the target switch.
  Changing it to `True` will cause verification of public certificate to occur.

.. _dupl_entry:

DBDuplicate Entry - Failed Insert into cisco_ml2_nexus_host_interface_mapping
-----------------------------------------------------------------------------
Description
^^^^^^^^^^^
When the same port-channel is configured for multiple hosts beneath the
same switch, a `DBDuplicateEntry` error is seen as shown in the Message
section below.  This type of configuration is seen with static configurations
only and not ironic.  An example of such a configuration is as follows:

::

    [ml2_mech_cisco_nexus:<snipped-switch-ip-addr>]
    host_ports_mapping=compute-host-1:[port-channel:300],
                       compute-host-2:[port-channel:300]

.. note::
    The above used to be represented by the now deprecated format::

      [ml2_mech_cisco_nexus:<snipped-switch-ip-addr>]
      compute-host-1 = port-channel:300
      compute-host-2 = port-channel:300

This anomaly can also occur when there are multiple controllers which
are attempting to initialize the cisco_ml2_nexus_host_interface_mapping
db table at the same time.

Message
^^^^^^^

::

    DBDuplicateEntry: (pymysql.err.IntegrityError)
    (1062, u"Duplicate entry '<your-switch-ip>-<your-port-channel-interface>'
    for key 'PRIMARY'")
    [SQL: u'INSERT INTO cisco_ml2_nexus_host_interface_mapping
    <SNIP>

Corrective Action
^^^^^^^^^^^^^^^^^
Both error cases described were introduced in Cisco Release 5.1.0.
To eliminate these errors, upgrade to a more recent release of the
networking-cisco package.

Neutron trunking feature not supported in Openstack Newton branches
-------------------------------------------------------------------
Description
^^^^^^^^^^^
Cisco Nexus ML2 Mechanism driver supports trunking from tag 5.3.0;
however, Openstack neutron in Newton branches and lower do not.
As a result, an error can occur if baremetal configurations
are attempted with these combined branches/tags.  The
error message which could be seen is shown below.

Message
^^^^^^^

::

    TypeError: get_object() got an unexpected keyword argument 'port_id'

Corrective Action
^^^^^^^^^^^^^^^^^
Upgrade networking-cisco package or apply the changes found in
https://review.openstack.org/#/c/542877/.

Exception NexusPortBindingNotFound seen in update_port_postcommit
-----------------------------------------------------------------
Description
^^^^^^^^^^^
An exception NexusPortBindingNotFound is seen in update_port_postcommit
when attempting to get port binding by calling get_nexusvlan_binding.
This is a result of a spurious update event received while deletes
are occurring for same event.  It is more likely to occur when there are
multiple threads and/or multiple controllers.

Message
^^^^^^^

::

    networking_cisco.ml2_drivers.nexus.exceptions.NexusPortBindingNotFound:
        Nexus Port Binding (switch_ip=1.1.1.1,vlan_id=265) is not present

Corrective Action
^^^^^^^^^^^^^^^^^
The solution is to log a warning instead of raising an exception to be
consistent with other ml2 drivers.  To eliminate this exception, upgrade
the networking-cisco package to pick-up latest fixes.
