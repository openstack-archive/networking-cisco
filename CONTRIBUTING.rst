If you would like to contribute to the development of networking-cisco,
you must follow the steps as outlined by the OpenStack page:

   https://docs.openstack.org/infra/manual/developers.html

Once those steps have been completed, changes to networking-cisco
should be submitted for review via the Gerrit tool, following
the workflow documented at:

   https://docs.openstack.org/infra/manual/developers.html#development-workflow

Pull requests submitted through GitHub will be ignored.

Bugs should be filed on Launchpad, not GitHub:

   https://bugs.launchpad.net/networking-cisco

Tox environments provided in networking-cisco:

* py27, py34 - Unit tests run against Mitaka neutron, on different python2.7 and python3.4
* newton - Unit tests run against Newton neutron with python2.7
* master - Unit tests run against master neutron with python2.7
* coverage - provides a report on the test coverage
* compare-coverage - compares coverage reports from before and after the current changes
* pep8 - Checks code against the pep8 and OpenStack hacking rules
* bandit - Performs static analysis on selected python source code
* genconfig - Generate sample configuration files included in the documentation
* docs - Generates documentation for viewing (hint: Run `genconfig` first)

DevStack is used by developers to install OpenStack and is not intended
for production use.  To get details on using DevStack, refer to other
documentation links such as:

* For general DevStack information, refer to
  `DevStack <https://docs.openstack.org/devstack/>`_
* For general ML2 DevStack details, refer to
  `ML2_DevStack <https://wiki.openstack.org/wiki/Neutron/ML2#Using_ML2_in_Devstack/>`_

As discussed in these links, ``local.conf`` is DevStack's configuration file
for defining OpenStack installations.  To include installing the
networking-cisco repository, add the following configuration.

.. code-block:: ini

    [[local|localrc]]
    enable_plugin networking-cisco https://github.com/openstack/networking-cisco

.. end

For further Cisco feature configuration details using DevStack, look for other
plugin/driver subsections in the Cisco contributor guide for sample DevStack
configurations.
