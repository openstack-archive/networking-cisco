===================================
Cisco Prime Network Registrar (PNR)
===================================

1. General
----------

This is an installation guide for enabling
Cisco Prime Network Registrar (PNR) support on OpenStack.

Please refer to PNR installation guide
(http://www.cisco.com/c/en/us/support/cloud-systems-management/prime-network-registrar/tsd-products-support-series-home.html)
for how to install and bring up the PNR.

The Neutron DHCP agent in the OpenStack environment needs to be setup
to communicate with the PNR DHCP server and with the PNR DNS server.
The PNR DHCP server performs leasing operations and PNR DNS server
resolves DNS queries, these two servers replace dnsmasq.

This guide does not cover OpenStack installation.

2. Prerequisites
----------------

The prerequisites for installing the PNR OpenStack enabler are the
following:

    - Install PNR with required DNS and DHCP licenses.
    - Disable dnsmasq or other DNS/DHCP services.

3. PNR plugin Installation
--------------------------

:3.1 Using devstack:

In this scenario, the PNR plugin will be installed along with OpenStack
using devstack.

1. Clone devstack.

2. Add this repo as an external repository:

   ::

    > cat local.conf
    [[local|localrc]]
    enable_plugin networking-cisco https://git.openstack.org/openstack/networking-cisco.git
    enable_service net-cisco

3. :command:`./stack.sh`

:3.2 On a setup with OpenStack already installed:

In this scenario, the PNR plugin will be installed on a setup which has
OpenStack installed already:

1. Clone networking-cisco_.

    .. _networking-cisco: https://github.com/openstack/networking-cisco

2. :command:`cd networking-cisco`

3. :command:`sudo python networking_cisco/setup.py install`

4. The following modifications are needed in the ``dhcp_agent.ini``
   file.

    Change the DHCP driver from dnsmasq to PNR.

    .. code-block:: ini

        [DEFAULT]
        #dhcp_driver = neutron.agent.linux.dhcp.Dnsmasq
        dhcp_driver = networking_cisco.plugins.cisco.cpnr.dhcp_driver.CpnrDriver

    Add the following new section to the ``dhcp_agent.ini`` file
    with the details for contacting the PNR local server.

    .. code-block:: ini

        [cisco_pnr]
        http_server = http://<pnr_localcluster_ipaddress>:8080
        http_username = <pnr_localcluster_username>
        http_password = <pnr_localcluster_password>
        external_interface = eth0
        dhcp_server_addr = <pnr_localcluster_ipaddress>
        dhcp_server_port = 67
        dns_server_addr = <pnr_localcluster_ipaddress>
        dns_server_port = 53

    Change the <pnr_localcluster_ipaddress> to the IP
    address of the local PNR VM.

    Change the <pnr_localcluster_username> and
    <pnr_localcluster_password> to the same username
    and password provided during PNR installation.

    If you are using HTTPS with a valid SSL certificate,
    change the scheme in http_server config variable to
    'https' and the port number in the address to the
    appropriate port (default 8443).

    If you do not want to verify SSL certificates, add a
    config variable to ``dhcp_agent.ini`` file.

    .. code-block:: ini

        [cisco_pnr]
        insecure = True

    Note that using the ``insecure`` variable is NOT recommended in
    production.


5. After changing ``dhcp_agent.ini``, restart the DHCP agent.

   On Red Hat based server:

   :command:`systemctl restart neutron-dhcp-agent`

   On Ubuntu based server:

   :command:`service restart neutron-dhcp-agent`


6. Start the dhcp and dns relay from command line as a detached
   background process. The relay files exist in
   networking_cisco/plugins/cisco/cpnr.

   :command:`nohup python dhcp_relay.py --config-file /etc/neutron/dhcp_agent.ini --log-file /var/log/neutron/dhcp-relay.log &`

   :command:`nohup python dns_relay.py --config-file /etc/neutron/dhcp_agent.ini --log-file /var/log/neutron/dns-relay.log &`

