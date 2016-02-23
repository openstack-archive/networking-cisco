#!/usr/bin/env bash

# Default values
# --------------
# osn is the name of OpenStack network service, i.e.,
# it should be 'neutron'.
osn=${1:-neutron}
plugin=${2:-n1kv}

osnExtNwName=test_extnet1
osnExtNwLen=24
hostportIP=10.0.21.3
portName=hostOnExtNw
n1kvPortPolicyProfileNames=(test-profile osn_t1_pp osn_t2_pp)
vethHostSideName=hostOnExtNw_hs
vethBridgeSideName=hostOnExtNw_bs


function get_port_profile_id() {
    name=$1
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
    nw=`$osn net-show $osnExtNwName`
    extNwVLAN=`echo "$nw" | awk '/provider:segmentation_id/ { print $4; }'`
    if [ -z ${extNwVLAN+x} ] || [ "$extNwVLAN" == "" ]; then
        echo "Failed to lookup VLAN of $osnExtNwName network, please check health of plugin and VSM then re-run this script."
        echo "Aborting!"
        exit 1
    fi
fi

echo -n "Checking if $portName port exists ..."
port=`$osn port-show $portName 2>&1`
hasPort=`echo $port | awk '/Unable to find|Value/ { if ($1 == "Unable") print "No"; else print "Yes"; }'`
if [ "$hasPort" == "No" ]; then
    echo " No, it does not. Creating it."
    port=`$osn port-create --name $portName --fixed-ip ip_address=$hostportIP $osnExtNwName $extra_port_params`
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
echo "Creating and plugging $vethHostSideName device into $osnExtNwName network"
sudo ip link add $vethHostSideName address $macAddr type veth peer name $vethBridgeSideName
sudo ip link set $vethHostSideName up
sudo ip link set $vethBridgeSideName up
sudo ip -4 addr add $hostportIP/$osnExtNwLen dev $vethHostSideName

if [ "$plugin" == "ovs" ]; then
    extra_ovs_params="tag=$extNwVLAN"
fi
sudo ovs-vsctl -- --may-exist add-port br-int $vethBridgeSideName $extra_ovs_params -- set interface $vethBridgeSideName external-ids:iface-id=$portId -- set interface $vethBridgeSideName external-ids:attached-mac=$macAddr -- set interface $vethBridgeSideName external-ids:iface-status=active
