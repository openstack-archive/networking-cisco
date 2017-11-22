#!/usr/bin/env bash

# Many of neutron's repos suffer from the problem of depending on neutron,
# but it not existing on pypi. This ensures its installed into the test environment.
set -ex

# First parameter is requirements file but this script ignores it and
# checks out proper version itself. Leave the first parameter in so
# that the API for this script is the same for all of OpenStack
# projects.

# Ignore first parameter
shift

LATEST_SUPPORTED_STABLE="stable/pike"

ZUUL_CLONER=/usr/zuul-env/bin/zuul-cloner
NEUTRONCLIENT_BRANCH=${NEUTRONCLIENT_BRANCH:-${NEUTRON_BRANCH:-$LATEST_SUPPORTED_STABLE}}
REQUIREMENTS_BRANCH=${REQUIREMENTS_BRANCH:-${NEUTRON_BRANCH:-$LATEST_SUPPORTED_STABLE}}
NEUTRON_BRANCH=${NEUTRON_BRANCH:-$LATEST_SUPPORTED_STABLE}

if [ -d "/home/zuul/src/git.openstack.org/openstack/requirements" ]; then
    (cd /home/zuul/src/git.openstack.org/openstack/requirements && \
     git checkout $REQUIREMENTS_BRANCH)
    UPPER_CONSTRAINTS_FILE=/home/zuul/src/git.openstack.org/openstack/requirements/upper-constraints.txt
else
    UPPER_CONSTRAINTS_FILE=https://git.openstack.org/cgit/openstack/requirements/plain/upper-constraints.txt?h=${REQUIREMENTS_BRANCH}
fi
install_cmd="pip install -c$UPPER_CONSTRAINTS_FILE"


if $(python -c "import neutronclient" 2> /dev/null); then
    echo "Neutronclient already installed."
elif [ -d "/home/zuul/src/git.openstack.org/openstack/python-neutronclient" ]; then
    # We're in a ZuulV3 environment then we needs to setup the source locations
    # to the right branch the tox-install-siblings task will handle the rest
    (cd /home/zuul/src/git.openstack.org/openstack/python-neutronclient && \
     git checkout $NEUTRONCLIENT_BRANCH )
    pip install -e /home/zuul/src/git.openstack.org/openstack/python-neutronclient
else
    # Install neutron client from git.openstack.org
    # Dont use upper contraints here because python-neutronclient is in upperconstraints
    pip install -e git+https://git.openstack.org/openstack/python-neutronclient@$NEUTRONCLIENT_BRANCH#egg=python-neutronclient
fi

if $(python -c "import neutron" 2> /dev/null); then
    echo "Neutron already installed."
elif [ -d "/home/zuul/src/git.openstack.org/openstack/neutron" ]; then
    # We're in a ZuulV3 environment then we needs to setup the source locations
    # to the right branch the tox-install-siblings task will handle the rest
    (cd /home/zuul/src/git.openstack.org/openstack/neutron && \
     git checkout $NEUTRON_BRANCH)
    $install_cmd -e /home/zuul/src/git.openstack.org/openstack/neutron
else
    # Install neutron from git.openstack.org
    $install_cmd -e git+https://git.openstack.org/openstack/neutron@$NEUTRON_BRANCH#egg=neutron
fi

# Install the rest of the requirements as normal
$install_cmd -U $*

exit $?
