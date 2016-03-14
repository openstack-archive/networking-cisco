#!/usr/bin/env bash

# Many of neutron's repos suffer from the problem of depending on neutron,
# but it not existing on pypi. This ensures its installed into the test environment.
set -ex

ZUUL_CLONER=/usr/zuul-env/bin/zuul-cloner

mkdir -p .test-tars

install_cmd="pip install"

CONSTRAINTS_FILE=$1
shift

if [ "$CONSTRAINTS_FILE" != "unconstrained" ]; then
    install_cmd="$install_cmd -c$CONSTRAINTS_FILE"
fi

if $(python -c "import neutronclient" 2> /dev/null); then
    echo "Neutronclient already installed."
elif [ -x $ZUUL_CLONER ]; then
    # Use zuul-cloner to clone openstack/neutronclient, this will ensure the Depends-On
    # references are retrieved from zuul and rebased into the repo, then installed.
    $ZUUL_CLONER --cache-dir /opt/git --workspace /tmp git://git.openstack.org openstack/python-neutronclient
    pip install /tmp/openstack/python-neutronclient
else
    # Download or update neutronclient-master tarball and install
    ( cd .test-tars && curl -R -O http://tarballs.openstack.org/python-neutronclient/python-neutronclient-master.tar.gz )
    pip install .test-tars/python-neutronclient-master.tar.gz
fi

if $(python -c "import neutron" 2> /dev/null); then
    echo "Neutron already installed."
elif [ -x $ZUUL_CLONER ]; then
    # Use zuul-cloner to clone openstack/neutron, this will ensure the Depends-On
    # references are retrieved from zuul and rebased into the repo, then installed.
    $ZUUL_CLONER --cache-dir /opt/git --workspace /tmp git://git.openstack.org openstack/neutron
    $install_cmd /tmp/openstack/neutron
else
    # Download or update neutron-master tarball and install
    ( cd .test-tars && curl -R -O http://tarballs.openstack.org/neutron/neutron-master.tar.gz )
    $install_cmd .test-tars/neutron-master.tar.gz
fi

# Install the rest of the requirements as normal
$install_cmd -U $*

exit $?
