======================
 Enable CSR1kv script for CSR1kv plugins in Devstack
======================

1. Download DevStack

2. To enable CSR1kv Routing-aaS, in file localrc or local.conf in the root
DevStack directory, add networking-cisco repo as an external repository and
enable q-ciscorouter and ciscocfgagent.

Refer to following examples for the settings:
local.conf.csr1kv_and_n1kv
localrc.csr1kv_and_n1kv

3. To enable CSR1kv FWaaS, in file localrc or local.conf in the root DevStack
directory, include the following line:
enable_service cisco-fwaas

4. run "stack.sh"
