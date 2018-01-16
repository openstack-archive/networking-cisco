#!/usr/bin/env bash

# Runs all install and demo scripts in the right order.

# osn is the name of OpenStack network service, i.e.,
# it should be 'neutron'.
osn=${1:-neutron}
plugin=${2:-ovs}
localrc=$3
TOP_DIR=$(cd $(dirname $localrc) && pwd)
mysql_user=$4
mysql_password=$5
mgmt_ip=$6
Q_CISCO_ASR1K_ENABLED=${7:-True}

# Adopted from Devstack scripts:
# Normalize config values to True or False
# Accepts as False: 0 no No NO false False FALSE
# Accepts as True: 1 yes Yes YES true True TRUE
# VAR=$(trueorfalse default-value test-value)
function pause(){
   read -p "Press [Enter] to continue ......"
}

if [[ ! -z $localrc && -f $localrc ]]; then
    eval $(grep ^Q_CISCO_CREATE_TEST_NETWORKS= $localrc)
fi
CREATE_TEST_NETWORKS=$(trueorfalse "False" $Q_CISCO_CREATE_TEST_NETWORKS)

if [[ "$Q_CISCO_ASR1K_ENABLED" == "True" ]]; then
    echo "***************** Setting up Keystone for ASR1k *****************"
    #pause
    ./setup_keystone_for_asr1k_l3.sh $osn
fi
echo 'Done!...'
