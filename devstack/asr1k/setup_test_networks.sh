#!/usr/bin/env bash

# Default values
# --------------
# osn is the name of OpenStack network service, i.e.,
# it should be 'neutron'.
osn=${1:-neutron}
plugin=${2:-ml2}

testNetworks=(test_net1 test_net2 test_net3 test_net4 test_net5 test_net6 test_extnet1)
testNetworkOpts=('' '' '' '' '' '' '--router:external=True')
testSubnetNames=(test_subnet1 test_subnet2 test_subnet3 test_subnet4 test_subnet5 test_subnet6 test_extsubnet1)
testSubnetCIDRs=('10.0.11.0/24' '10.0.12.0/24' '10.0.13.0/24' '10.0.14.0/24' '10.0.15.0/24' '10.0.16.0/24' '10.0.21.0/24')
testSubnetOpts=('' '' '' '' '' '' '--disable-dhcp --allocation-pool start=10.0.21.10,end=10.0.21.254')

function get_network_profile_id() {
    index=$1
    name=$2
    phyNet=$3
    type=$4
    subType=$5
    segRange=$6
    local c=0
    local opt_param=

    nProfileId[$index]=`$osn cisco-network-profile-list | awk 'BEGIN { res="None"; } /'"$name"'/ { res=$2; } END { print res;}'`
    if [ "${nProfileId[$index]}" == "None" ]; then
        echo "   Network profile $name does not exist. Creating it."
        if [ "$subType" != "None" ]; then
            opt_param="--sub_type $subType"
        fi
        if [ "$segRange" != "None" ]; then
            opt_param=$opt_param" --segment_range $segRange"
        fi
        $osn cisco-network-profile-create --physical_network $phyNet $opt_param $name $type
    fi
    while [ $c -le 5 ] && [ "$nProfileId" == "None" ]; do
        nProfileId=`$osn cisco-network-profile-list | awk 'BEGIN { res="None"; } /'"$name"'/ { res=$2; } END { print res;}'`
        let c+=1
    done
}

for (( i=0; i<${#testNetworks[@]}; i++)); do
    echo -n "Checking if ${testNetworks[$i]} network exists ..."
    hasNw=`$osn net-show ${testNetworks[$i]} 2>&1 | awk '/Unable to find|enabled/ { if ($1 == "Unable") print "No"; else print "Yes"; }'`
    if [ "$hasNw" == "No" ]; then
        echo " No it does not. Creating it."
        $osn net-create $profile_opt ${testNetworkOpts[$i]} ${testNetworks[$i]}
    else
        echo " Yes, it does."
    fi
done


for (( i=0; i<${#testSubnetNames[@]}; i++)); do
    echo -n "Checking if ${testSubnetNames[$i]} subnet exists ..."
    hasSubNw=`$osn subnet-show ${testSubnetNames[$i]} 2>&1 | awk '/Unable to find|Value/ { if ($1 == "Unable") print "No"; else print "Yes"; }'`
    if [ "$hasSubNw" == "No" ]; then
        echo " No it does not. Creating it."
        $osn subnet-create --name ${testSubnetNames[$i]} ${testSubnetOpts[$i]} ${testNetworks[$i]} ${testSubnetCIDRs[$i]}
    else
        echo " Yes, it does."
    fi
done
