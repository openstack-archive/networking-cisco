======================
 Enabling in Devstack
======================

1. Download DevStack

2. Add this repo as an external repository::

     > cat local.conf
     [[local|localrc]]
     enable_plugin networking-cisco https://git.openstack.org/openstack/networking-cisco.git
     enable_service net-cisco


3. run ``stack.sh``
