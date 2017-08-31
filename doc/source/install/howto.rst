===============================
How to install networking-cisco
===============================

The following lists steps to install the networking-cisco repository:

#. Released versions of networking-cisco are available via either:

   .. code-block:: ini

       http://tarballs.openstack.org/networking-cisco
       https://pypi.python.org/pypi/networking-cisco

   .. end

   The neutron release is http://tarballs.openstack.org/neutron

#. To install the Nexus ML2 driver, do as follows:

     * When using pip for installs, do either:

       .. code-block:: ini

           pip install networking-cisco
           pip install <path to downloaded networking-cisco tarball>

       .. end

     * To install the Nexus ML2 mechanism driver without pip, do:

       .. code-block:: ini

           tar -zxfv <downloaded networking-cisco tarball>
           cd ./networking-cisco-<version>
           python setup.py install

       .. end

       If installing without pip, you should ensure that the python
       dependencies are all installed. They can be found in
       ``requirements.txt`` in the untarred directory.

     * To install the Nexus ML2 mechanism driver from system packages, do:

       .. code-block:: ini

           yum install python-networking-cisco
       .. end

#. Recent additions to Nexus ML2 data requires a data base migration to be
   performed.  This can be done by running:

   .. code-block:: ini

       su -s /bin/sh -c "neutron-db-manage --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini --config-file /etc/neutron/plugins/ml2/ml2_conf_cisco.ini upgrade head" neutron

   .. end
