==========================================================
ASR1000 L3 Router Service Plugin Overview and Architecture
==========================================================

The ASR1k L3 router service plugin (L3P) represents each Neutron router as a
virtual routing and forwarding table (VRF) to ensure isolation. Each neutron
router port maps to a VLAN sub-interface in the ASR1k. These sub-interfaces
can either reside on ethernet interfaces or port-channel interfaces.

When a neutron router is attached to a subnet on an internal network the
corresponding VLAN sub-interface that is created is placed in the VRF of the
router. Hence the VRF effectively monopolizes that sub-interface. This is the
reason why a particular neutron network can only be attached to a single
neutron router.

The gateway port of a neutron router is handled differently as external
networks typically need to be shared among many tenant routers. For this
reason VLAN sub-interfaces for external networks are placed in the *global*
VRF. The default gateway inside the VRF of the tenant routers point to the
IP address of the *upstream* router on the external network *via* the VLAN
sub-interface for the external network in the global VRF.

For the dynamic source NAT that is normally performed by tenant neutron
routers with gateway set, the IP address of the tenant router's *gateway
port* is used. If a floating ip has been created and associated with a
neutron port on an internal network/subnet, the static source NAT for that
floating ip takes precedence of the dynamic source NAT.
