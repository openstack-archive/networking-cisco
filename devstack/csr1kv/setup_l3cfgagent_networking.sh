#!/bin/bash

# Default values
# --------------
# osn is the name of Openstack network service, i.e.,
# it should be 'neutron'.
osn=${1:-neutron}
plugin=${2:-n1kv}

adminUser=$osn
l3AdminTenant=L3AdminTenant

osnMgmtNwName=osn_mgmt_nw
osnMgmtNwLen=24
l3CfgAgentMgmtIP=${3:-10.0.100.2}
portName=l3CfgAgent1
n1kvPortPolicyProfileNames=(osn_mgmt_pp osn_t1_pp osn_t2_pp)
vethHostSideName=l3cfgagent_hs
vethBridgeSideName=l3cfgagent_bs

tenantId=`keystone tenant-get $l3AdminTenant 2>&1 | awk '/No tenant|id/ { if ($1 == "No") print "No"; else print $4; }'`
if [ "$tenantId" == "No" ]; then
    echo "No $l3AdminTenant exists, please create one using the setup_keystone... script then re-run this script."
    echo "Aborting!"
    exit 1
fi


function get_port_profile_id() {
    local name=$1
    local c=0
    pProfileId=None
    while [ $c -le 15 ] && [ "$pProfileId" == "None" ]; do
        pProfileId=`$osn cisco-policy-profile-list | awk 'BEGIN { res="None"; } /'"$name"'/ { res=$2; } END { print res;}'`
        if [[ "$pProfileId" == "None" ]]; then
            let c+=1
            sleep 5
        fi
    done
}


if [ "$plugin" == "n1kv" ]; then
    get_port_profile_id ${n1kvPortPolicyProfileNames[0]}
    extra_port_params="--n1kv:profile_id $pProfileId"
elif [ "$plugin" == "ovs" ]; then
    nw=`$osn net-show $osnMgmtNwName`
    mgmtVLAN=`echo "$nw" | awk '/provider:segmentation_id/ { print $4; }'`
    if [ -z ${mgmtVLAN+x} ] || [ "$mgmtVLAN" == "" ]; then
        echo "Failed to lookup VLAN of $osnMgmtNwName network, please check health of plugin and VSM then re-run this script."
        echo "Aborting!"
        exit 1
    fi
fi

echo -n "Checking if $portName port exists ..."
port=`$osn port-show $portName 2>&1`
hasPort=`echo $port | awk '/Unable to find|Value/ { if ($1 == "Unable") print "No"; else print "Yes"; }'`
if [ "$hasPort" == "No" ]; then
    echo " No, it does not. Creating it."
    port=`$osn port-create --name $portName --tenant-id $tenantId --fixed-ip ip_address=$l3CfgAgentMgmtIP $osnMgmtNwName $extra_port_params`
else
    echo " Yes, it does."
fi

macAddr=`echo "$port" | awk '/mac_address/ { print $4; }'`
if [ -z ${macAddr+x} ] || [ "$macAddr" == "" ]; then
    echo "Failed to create $portName port, please check health of plugin and VSM then re-run this script."
    echo "Aborting!"
    exit 1
fi
portId=`echo "$port" | awk '/ id/ { print $4; }'`

hasVeth=`ip link show | awk '/'"$vethHostSideName"'/ { print $2; }'`
if [ "$hasVeth" != "" ]; then
    echo "Deleting existing $vethHostSideName device"
    sudo ip link del $vethHostSideName
    sudo ovs-vsctl -- --if-exists del-port $vethBridgeSideName
fi
echo "Creating and plugging $vethHostSideName device into $osnMgmtNwName network"
sudo ip link add $vethHostSideName address $macAddr type veth peer name $vethBridgeSideName
sudo ip link set $vethHostSideName up
sudo ip link set $vethBridgeSideName up
sudo ip -4 addr add $l3CfgAgentMgmtIP/$osnMgmtNwLen dev $vethHostSideName

if [ "$plugin" == "ovs" ]; then
    extra_ovs_params="tag=$mgmtVLAN"
fi
sudo ovs-vsctl -- --may-exist add-port br-int $vethBridgeSideName $extra_ovs_params -- set interface $vethBridgeSideName external-ids:iface-id=$portId -- set interface $vethBridgeSideName external-ids:attached-mac=$macAddr -- set interface $vethBridgeSideName external-ids:iface-status=active
