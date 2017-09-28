If you would like to contribute to the development of OpenStack,
you must follow the steps in this page:

   http://docs.openstack.org/infra/manual/developers.html

Once those steps have been completed, changes to OpenStack
should be submitted for review via the Gerrit tool, following
the workflow documented at:

   http://docs.openstack.org/infra/manual/developers.html#development-workflow

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
* genconfig - Generate sample configuration files included in the documentation
