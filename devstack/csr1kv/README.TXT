======================
 Enable CSR1kv script for CSR1kv plugins in Devstack
======================

1. Download DevStack

2. In file localrc or local.conf in the root DevStack directory, add
networking-cisco repo as an external repository and enable cisco-csr.

Refer to following example for the settings:
local.conf.csr1kv_and_n1kv
localrc.csr1kv_and_n1kv

3. run "stack.sh"
