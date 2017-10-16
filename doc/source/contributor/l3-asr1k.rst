==================================================
ASR1000 L3 Router Service Plugin Contributor Guide
==================================================

Using DevStack
~~~~~~~~~~~~~~
DevStack is used by developers to install Openstack. It is not intended for
production use. For introductory details on DevStack, refer to
:doc:`/contributor/howto`.

To install the ASR1k L3 router service plugin along with OpenStack
using DevStack, do as follows:

#.  Clone DevStack and checkout the branch (ex: stable/ocata, stable/newton,
    etc) you want to install.

#.  Configure the ASR1k L3 router service plugin in ``local.conf`` file as
    shown in examples which follow.

#.  Run :command:`./stack.sh`  to install and :command:`./unstack.sh` to
    uninstall.

DevStack Configuration Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This section describes how to extend the ``local.conf`` file with
ASR1k-based L3 routing details for DevStack deployment. These details should
follow the section which installs networking-cisco repository as described
in :doc:`/contributor/howto`.

Append the following lines to ``local.conf`` to enable the L3P, DMP and CFGA:

.. code-block:: ini

    Q_CISCO_ASR1K_ENABLED=True

    enable_service ciscocfgagent
    enable_service q-ciscorouter
    enable_service q-ciscodevicemanager

    [[post-config|/etc/neutron/neutron.conf]]

    [DEFAULT]
    api_extensions_path = extensions:/opt/stack/networking-cisco/networking_cisco/plugins/cisco/extensions

.. end

Defining credentials, hosting device templates, hosting devices and router types
--------------------------------------------------------------------------------
DevStack can automatically include definitions of credentials, hosting device
templates, hosting devices and router types in configuration files that are
given as arguments to neutron server and the CFGA when they are started.

The actual definitions to be included has to be provided to DevStack. This is
done using two text files:

* ``cisco_device_manager_plugin.inject``
* ``cisco_router_plugin.inject``

If these files exist in the DevStack root directory when the
:command:`./stack.sh` command is executed, DevStack will append their contents
to configuration files that neutron server consumes when it starts.

A cisco_device_manager_plugin.inject sample file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The sample inject file below can be viewed as raw text
:download:`cisco_device_manager_plugin.inject <../../../devstack/inject_files/cisco_device_manager_plugin.inject>`
file.

.. literalinclude:: ../../../devstack/inject_files/cisco_device_manager_plugin.inject

A ``cisco_router_plugin.inject`` sample file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The sample inject file below can be viewed as raw text
:download:`cisco_router_plugin.inject <../../../devstack/inject_files/cisco_router_plugin.inject>`
file.

.. literalinclude:: ../../../devstack/inject_files/cisco_router_plugin.inject

Source Code Location
~~~~~~~~~~~~~~~~~~~~
Code locations for the ASR1k L3 router service plugin, the device manager
plugin and the configuration agent are found in the following directory:

:file:`{networking-cisco install directory}/networking_cisco/plugins/cisco`

Typically devstack clone the source code to ``/opt/stack/networking-cisco``.
