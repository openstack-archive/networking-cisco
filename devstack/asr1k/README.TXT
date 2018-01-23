=================================================
 Enable ASR1k script for ASR1k plugin in Devstack
=================================================

1. Download DevStack

2. To enable ASR1k Routing-aaS, in file localrc or local.conf in the root
DevStack directory, add networking-cisco repo as an external repository and
enable q-ciscorouter and ciscocfgagent.

Refer to following examples for the settings:
local.conf.asr1k
localrc.asr1k

4. run "stack.sh"
