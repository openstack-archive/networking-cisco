=======================================
Installing the networking-cisco Package
=======================================

The following lists steps to install the networking-cisco repository:

#. Released versions of networking-cisco are available via either:

   .. code-block:: ini

       http://tarballs.openstack.org/networking-cisco
       https://pypi.org/project/networking-cisco

   .. end

   The neutron release is http://tarballs.openstack.org/neutron

#. To install networking-cisco, do as follows:

   * When using pip for installs, do either:

     .. code-block:: console

        $ pip install networking-cisco
        $ pip install <path to downloaded networking-cisco tarball>

     .. end

   * To install networking-cisco without pip, do:

     .. code-block:: console

        $ tar -zxfv <downloaded networking-cisco tarball>
        $ cd ./networking-cisco-<version>
        $ python setup.py install

     .. end

       If installing without pip, you should ensure that the python
       dependencies are all installed. They can be found in
       ``requirements.txt`` in the untarred directory.

   * To install networking-cisco package from system packages, do:

     .. code-block:: console

        $ yum install python-networking-cisco

     .. end

#. Recent additions to networking-cisco package data requires a data base
   migration to be performed.  This can be done by running:

   .. code-block:: console

       $ su -s /bin/sh -c "neutron-db-manage --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini upgrade head" neutron

   .. end

   .. note::
      If a separate file for cisco configuration exists (ex: ml2_conf_cisco.ini),
      that file also should be included by following other config files in the
      command with::

        --config-file /etc/neutron/plugins/ml2/ml2_conf_cisco.ini
