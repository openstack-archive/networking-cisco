===================================================
ASR1000 L3 Router Service Plugin Installation Guide
===================================================

This is an installation guide for enabling the ASR1000 L3 Router Service Plugin
(L3P) support on OpenStack.

Prerequisites
~~~~~~~~~~~~~

The prerequisites for installing the ASR1k L3P are as follows:

* Cisco IOS XE image version 16.03.04. Refer to `ASR1k docs <https://www.cisco.com/c/en/us/products/routers/asr-1000-series-aggregation-services-routers/index.html>`_
  for upgrade/downgrade instructions. From this link, select the 'Support'
  option in the middle of the page for information on upgrade/downgrade
  guides, configuration and technical references.

* The ASR1k L3P has been tested on these OSs.

  * Ubuntu 14.04 or above

* Your ASR1k router must be set-up as described in the next section
  `ASR1k Router Setup`_.

* As the ASR1k L3P uses ncclient the following must also be installed:

  * ``Paramiko`` library, the SSHv2 protocol library for python
  * The ``ncclient`` (minimum version v0.4.6) python library for NETCONF
    clients.  Install the ncclient library by using the pip package
    manager at your shell prompt: :command:`pip install ncclient >= 0.4.6`
  * Additionally, the following
    `patch <https://github.com/ncclient/ncclient/commit/85d78a563a4f137dbde3d2054fb58798a66db17c>`_
    to ``ncclient`` is needed

ASR1k Router Setup
~~~~~~~~~~~~~~~~~~

This section lists what is required to prepare the ASR1k router for operation
with the ASR1k L3P.

#.  Your ASR1k router must be connected to a management network separate from
    the OpenStack data network. The configuration agent (CFGA) *must* be able
    to access this network so it can communicate with the ASR1k router to set
    up tenant data flows.

    The following exemplifies this for a case where the management subnet is
    10.0.10.0/24 with upstream gateway 10.0.10.1/24. The management interface
    of the ASR1k is ``GigabitEthernet0`` and its IP address is 10.0.10.39/24.

    .. code-block:: ini

        vrf definition Mgmt-intf
         !
         address-family ipv4
         exit-address-family
         !
         address-family ipv6
         exit-address-family
         !
        !
        interface GigabitEthernet0
        vrf forwarding Mgmt-intf
        ip address 10.0.10.39 255.255.255.0
        negotiation auto
        no mop enabled
        !
        ip route vrf Mgmt-intf 0.0.0.0 0.0.0.0 10.0.10.1
        ip ssh source-interface GigabitEthernet0
        !

    .. end

#.  A CFGA uses Netconf to apply configurations in an ASR1k router. Netconf
    therefore has to be enabled by the router administrator along with user
    credentials for authentication. These credentials must match one of the
    ``hosting_device_credentials`` defined for CFGA (
    :ref:`see <cred_example>`).

    The following exemplifies this for a user ``stack`` and password ``cisco``:

    .. code-block:: ini

        username stack privilege 15 password 0 cisco
        netconf max-sessions 16
        netconf ssh

    .. end

#.  Some pre-configuration of ASR1k interfaces that will carry data traffic
    for Neutron routers must be performed by the router administrator.

    * All participating interfaces must be enabled with :command:`no shutdown`.

    * Any port-channels to be used must also be pre-configured.

    The following example defines port-channel 10 on interfaces
    ``TenGigabitEthernet0/1/0`` and ``TenGigabitEthernet0/2/0``:

    .. code-block:: ini

        interface Port-channel10
        no ip address
        !
        interface TenGigabitEthernet0/1/0
        no ip address
        cdp enable
        channel-group 10 mode active
        !
        interface TenGigabitEthernet0/2/0
        no ip address
        cdp enable
        channel-group 10 mode active
        !

    .. end

ASR1k L3P Installation
~~~~~~~~~~~~~~~~~~~~~~

#.  Install networking-cisco package as described in the section
    :doc:`howto`.

#.  Configure ASR1k L3 router service plugin, its dependencies, the device
    manager plugin and the configuration agent. Full details on how to do this
    are available in the :doc:`/admin/l3-asr1k`.
    For details on each configuration parameters, refer to
    :doc:`ASR1k Configuration Reference<../configuration/samples/l3-asr1k>`.

#.  Restart neutron to pick-up configuration changes. For example on Ubuntu
    14.04 use:

    .. code-block:: ini

        $ service neutron-server restart

    .. end
