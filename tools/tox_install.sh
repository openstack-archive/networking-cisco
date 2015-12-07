#!/bin/sh

# Many of neutron's repos suffer from the problem of depending on neutron,
# but it not existing on pypi. This ensures its installed into the test environment.
set -ex

ZUUL_CLONER=/usr/zuul-env/bin/zuul-cloner

mkdir -p .test-tars

if $(python -c "import neutron" 2> /dev/null); then
    echo "Neutron already installed."
elif [ -x $ZUUL_CLONER ]; then
    # Use zuul-cloner to clone openstack/neutron, this will ensure the Depends-On
    # references are retrieved from zuul and rebased into the repo, then installed.
    $ZUUL_CLONER --cache-dir /opt/git --workspace /tmp git://git.openstack.org openstack/neutron
    (cd /tmp/openstack/neutron && git checkout stable/liberty)
    pip install /tmp/openstack/neutron
else
    # Download or update neutron-master tarball and install
    ( cd .test-tars && wget -N http://tarballs.openstack.org/neutron/neutron-stable-liberty.tar.gz )
    pip install .test-tars/neutron-stable-liberty.tar.gz
fi

# Install the rest of the requirements as normal
pip install -U $*

exit $?
