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

function trueorfalse {
    local xtrace=$(set +o | grep xtrace)
    set +o xtrace
    local default=$1
    local testval=$2

    [[ -z "$testval" ]] && { echo "$default"; return; }
    [[ "0 no No NO false False FALSE" =~ "$testval" ]] && { echo "False"; return; }
    [[ "1 yes Yes YES true True TRUE" =~ "$testval" ]] && { echo "True"; return; }
    echo "$default"
    $xtrace
}


if [[ ! -z $localrc && -f $localrc ]]; then
    eval $(grep ^Q_CISCO_CREATE_TEST_NETWORKS= $localrc)
fi
CREATE_TEST_NETWORKS=$(trueorfalse "False" $Q_CISCO_CREATE_TEST_NETWORKS)

if [[ "$Q_CISCO_ASR1K_ENABLED" == "True" ]]; then
    echo "***************** Setting up Keystone for ASR1k *****************"
    #pause
    ./setup_keystone_for_csr1kv_l3.sh $osn
else
    source ${TOP_DIR}/openrc admin demo
    echo "***************** Setting up Keystone for CSR1kv *****************"
    ./setup_keystone_for_csr1kv_l3.sh $osn
#    pause
    source ${TOP_DIR}/openrc $osn L3AdminTenant
    echo "***************** Setting up Nova & Glance for CSR1kv *****************"
    ./setup_nova_and_glance_for_csr1kv_l3.sh $osn $plugin $localrc $mysql_user $mysql_password
#    pause
    echo "***************** Setting up Neutron for CSR1kv *****************"
    ./setup_neutron_for_csr1kv_l3.sh $osn $plugin $localrc
#    pause
    echo "***************** Setting up CfgAgent connectivity *****************"
    ./setup_l3cfgagent_networking.sh $osn $plugin $localrc $mgmt_ip

    if [[ "$CREATE_TEST_NETWORKS" == "True" ]]; then
        source ${TOP_DIR}/openrc admin demo
        echo "***************** Setting up test networks *****************"
       ./setup_test_networks.sh $osn $plugin
       ./setup_interface_on_extnet1_for_demo.sh $osn $plugin
    fi

fi
echo 'Done!...'
