#!/usr/bin/env bash

# Default values
# --------------
# osn is the name of OpenStack network service, i.e.,
# it should be 'neutron'.
osn=${1:-neutron}
plugin=${2:-n1kv}
localrc=$3
TOP_DIR=$(cd $(dirname $localrc) && pwd)
net_cisco=${4:-networking-cisco}


if [[ ! -z $localrc && -f $localrc ]]; then
    eval $(grep ^Q_CISCO_PLUGIN_VSM_IP= $localrc)
    eval $(grep Q_CISCO_PLUGIN_VSM_USERNAME= $localrc)
    eval $(grep ^Q_CISCO_PLUGIN_VSM_PASSWORD= $localrc)

    eval $(grep ^Q_CISCO_MGMT_SUBNET= $localrc)
    eval $(grep ^Q_CISCO_MGMT_SUBNET_LENGTH= $localrc)
    eval $(grep ^Q_CISCO_MGMT_SUBNET_USAGE_RANGE_START= $localrc)
    eval $(grep ^Q_CISCO_MGMT_SUBNET_USAGE_RANGE_END= $localrc)
fi

adminUser=$osn
l3AdminTenant=L3AdminTenant

vsmIP=${Q_CISCO_PLUGIN_VSM_IP:-192.168.168.2}
vsmUsername=${Q_CISCO_PLUGIN_VSM_USERNAME:-admin}
vsmPassword=${Q_CISCO_PLUGIN_VSM_PASSWORD:-Sfish123}

base_dir=/opt/stack/data/$net_cisco/cisco
DIR_CISCO=/opt/stack/networking-cisco
templates_dir=$base_dir/templates
template_name=csr1kv_cfg_template
template_file=$templates_dir/$template_name
template_file_src=$DIR_CISCO/networking_cisco/plugins/cisco/device_manager/configdrive_templates/$template_name
osnMgmtNwName=osn_mgmt_nw
mgmtSecGrp=mgmt_sec_grp
mgmtProviderNwName=mgmt_net
mgmtProviderVlanId=100
osnMgmtSubnetName=osn_mgmt_subnet
# note that the size of this network sets the limit on number of CSR instances
osnMgmtNw=${Q_CISCO_MGMT_SUBNET:-10.0.100.0}
osnMgmtNwLen=${Q_CISCO_MGMT_SUBNET_LENGTH:-24}
osnMgmtSubnet=$osnMgmtNw/$osnMgmtNwLen
# the first 9 addresses are set aside for L3CfgAgents and similar
osnMgmtRangeStart=${Q_CISCO_MGMT_SUBNET_USAGE_RANGE_START:-10.0.100.10}
osnMgmtRangeEnd=${Q_CISCO_MGMT_SUBNET_USAGE_RANGE_END:-10.0.100.254}

# Items in the arrays below correspond to settings for
# the Mgmt, T1 (i.e., VLAN) and T2 (i.e., VXLAN) networks/ports.
# the N1kv only supports one physical network so far
n1kvPhyNwNames=(osn_phy_network osn_phy_network osn_phy_network)
n1kvNwProfileNames=(osn_mgmt_np osn_t1_np osn_t2_np)
n1kvNwProfileTypes=(vlan trunk trunk)
n1kvNwSubprofileTypes=(None vlan vlan)
n1kvNwProfileSegRange=($mgmtProviderVlanId-$mgmtProviderVlanId None None)
n1kvPortPolicyProfileNames=(osn_mgmt_pp osn_t1_pp osn_t2_pp sys-uplink)
n1kvPortPolicyProfileTypes=(vethernet vethernet vethernet ethernet)

function _configure_vsm_port_profiles() {
    # Package 'expect' must be installed for this function to work
    vsm_ip_addr=$1 user=$2 passwd=$3 profile_name=$4 ptype=$5 expect -c '
	spawn /usr/bin/telnet $env(vsm_ip_addr)
	expect {
	    -re "Trying.*Connected.*Escape.*Nexus .*login: " {
	        send "$env(user)\n"
	        exp_continue
	        #look for the password prompt
	    }

	    "*?assword:*" {
	        send "$env(passwd)\n"
	    }
        }
        expect -re ".*# "

	send "config te\n"
	expect -re ".*# "

	send "feature network-segmentation-manager\n"
	expect -re ".*# "

    send "port-profile type $env(ptype) $env(profile_name)\n"
	expect -re ".*# "

    if {$env(ptype) == "ethernet"} {
        send "switchport mode trunk\n"
        expect -re ".*# "
    }

    send "no shut\n"
	expect -re ".*# "

    send "state enabled\n"
	expect -re ".*# "

    send "publish port-profile\n"
	expect -re ".*# "

    send "end\n"
    expect -re ".*# "

    send "exit\n"
    '
}


function get_network_profile_id() {
    local name=$1
    local phyNet=$2
    local type=$3
    local subType=$4
    local segRange=$5
    local c=0
    local opt_param=
    nProfileId=`$osn cisco-network-profile-list | awk 'BEGIN { res="None"; } /'"$name"'/ { res=$2; } END { print res;}'`
    if [ "$nProfileId" == "None" ]; then
        echo "   Network profile $name does not exist. Creating it."
        if [ "$subType" != "None" ]; then
            opt_param="--sub_type $subType"
        fi
        if [ "$segRange" != "None" ]; then
            opt_param=$opt_param" --segment_range $segRange"
        fi
        echo $tenantId
	echo $phyNet
	echo $opt_param
	echo $name
	echo $type
        $osn cisco-network-profile-create --tenant-id $tenantId --physical_network $phyNet $opt_param $name $type
    fi
    while [ $c -le 15 ] && [ "$nProfileId" == "None" ]; do
        nProfileId=`$osn cisco-network-profile-list | awk 'BEGIN { res="None"; } /'"$name"'/ { res=$2; } END { print res;}'`
        let c+=1
        sleep 5
    done
}


function get_port_profile_id() {
    local name=$1
    local porttype=$2
    local c=0
    pProfileId=`$osn cisco-policy-profile-list | awk 'BEGIN { res="None"; } /'"$name"'/ { res=$2; } END { print res;}'`
    if [ "$pProfileId" == "None" ]; then
        echo "   Port policy profile $name does not exist. Creating it."
        _configure_vsm_port_profiles $vsmIP $vsmUsername $vsmPassword $name $porttype
    fi
    if [ "${n1kvPortPolicyProfileNames[$i]}" == "sys-uplink" ]; then
        # The n1kv plugin does not list the above policies so we cannot verify them
        return
    fi
    while [ $c -le 15 ] && [ "$pProfileId" == "None" ]; do
        pProfileId=`$osn cisco-policy-profile-list | awk 'BEGIN { res="None"; } /'"$name"'/ { res=$2; } END { print res;}'`
        let c+=1
        sleep 5
    done
}


tenantId=`keystone tenant-get $l3AdminTenant 2>&1 | awk '/No tenant|id/ { if ($1 == "No") print "No"; else if ($2 == "id") print $4; }'`
if [ "$tenantId" == "No" ]; then
    echo "No $l3AdminTenant exists, please create one using the setup_keystone... script then re-run this script."
    echo "Aborting!"
    exit 1
fi


source $TOP_DIR/openrc $adminUser $L3adminTenant


echo -n "Checking if $templates_dir exists..."
if [ -d $templates_dir ]; then
    echo "Yes, it does."
else
    echo "No, it does not. Creating it."
    mkdir -p $templates_dir
fi


#Hareesh - Copying of template file everytime to cater for template file changes
echo "Copying base template in $template_file_src to $template_file ..."
    cp $template_file_src $template_file

if [ "$plugin" == "n1kv" ]; then
    echo "Verifying that required N1kv network profiles exist:"
    for (( i=0; i<${#n1kvNwProfileNames[@]}; i++ )); do
        echo "   Checking ${n1kvNwProfileNames[$i]} ..."
        get_network_profile_id ${n1kvNwProfileNames[$i]} ${n1kvPhyNwNames[$i]} ${n1kvNwProfileTypes[$i]} ${n1kvNwSubprofileTypes[$i]} ${n1kvNwProfileSegRange[$i]}
        if [ $nProfileId == "None" ]; then
            echo "   Failed to verify network profile ${n1kvNwProfileNames[$i]}, please check health of the N1kv plugin and the VSM."
            echo "   Aborting!"
            exit 1
        else
            echo "   Done"
        fi
    done

    echo "Verifying that required N1kv port policy profiles exist:"
    for (( i=0; i<${#n1kvPortPolicyProfileNames[@]}; i++ )); do
        echo "   Checking ${n1kvPortPolicyProfileNames[$i]} ..."
        get_port_profile_id ${n1kvPortPolicyProfileNames[$i]} ${n1kvPortPolicyProfileTypes[$i]}
        if [ $pProfileId == "None" ] && [ "${n1kvPortPolicyProfileNames[$i]}" != "sys-uplink" ]; then
            echo "   Failed to verify port profile ${n1kvPortPolicyProfileNames[$i]}, please check health of the VSM then re-run this script."
            echo "   Aborting!"
            exit 1
        else
            echo "   Done"
        fi
    done
fi

echo -n ""
echo -n "Checking if $osnMgmtNwName network exists ..."
hasMgmtNetwork=`$osn net-show $osnMgmtNwName 2>&1 | awk '/Unable to find|enabled/ { if ($1 == "Unable") print "No"; else print "Yes"; }'`

if [ "$hasMgmtNetwork" == "No" ]; then
    echo " No, it does not. Creating it."
    if [ "$plugin" == "n1kv" ]; then
        get_network_profile_id ${n1kvNwProfileNames[0]} ${n1kvPhyNwNames[0]} ${n1kvNwProfileTypes[0]} ${n1kvNwSubprofileTypes[0]} ${n1kvNwProfileSegRange[0]}
        $osn net-create --tenant-id $tenantId $osnMgmtNwName --n1kv:profile_id $nProfileId
    else
        $osn net-create --tenant-id $tenantId $osnMgmtNwName --provider:network_type vlan --provider:physical_network pvnet1 --provider:segmentation_id $mgmtProviderVlanId
    fi
else
    echo " Yes, it does."
fi


echo -n "Checking if $osnMgmtSubnetName subnet exists ..."
hasMgmtSubnet=`$osn subnet-show $osnMgmtSubnetName 2>&1 | awk '/Unable to find|Value/ { if ($1 == "Unable") print "No"; else print "Yes"; }'`

if [ "$hasMgmtSubnet" == "No" ]; then
    echo " No, it does not. Creating it."
    # Disabling DHCP on mgmt subnet due to Nova bug #1220856 (https://bugs.launchpad.net/nova/+bug/1220856)
    $osn subnet-create --name $osnMgmtSubnetName --tenant-id $tenantId --allocation-pool start=$osnMgmtRangeStart,end=$osnMgmtRangeEnd $osnMgmtNwName $osnMgmtSubnet --disable-dhcp
else
    echo " Yes, it does."
fi


if [ "$plugin" == "n1kv" ]; then
    # security groups are not implemented by N1kv plugin so we stop here
    exit 0
fi


echo -n "Checking if $mgmtSecGrp security group exists ..."
hasMgmtSecGrp=`$osn security-group-show $mgmtSecGrp 2>&1 | awk '/Unable to find|Value/ { if ($1 == "Unable") print "No"; else print "Yes"; }'`

if [ "$hasMgmtSecGrp" == "No" ]; then
    echo " No, it does not. Creating it."
    $osn security-group-create --description "For CSR1kv management network" --tenant-id $tenantId $mgmtSecGrp
else
    echo " Yes, it does."
fi


proto="icmp"
echo -n "Checking if $mgmtSecGrp security group has $proto rule ..."
def=`$osn security-group-rule-list | awk -v grp=$mgmtSecGrp -v p=$proto  '/'"$proto"'|protocol/ { if ($4 == grp && $8 == p && $10 == "0.0.0.0/0") n++; } END { if (n > 0) print "Yes"; else print "No"; }'`
if [ "$def" == "No" ]; then
    echo " No, it does not. Creating it."
    $osn security-group-rule-create --tenant-id $tenantId --protocol icmp --remote-ip-prefix 0.0.0.0/0 $mgmtSecGrp
else
    echo " Yes, it does."
fi


proto="tcp"
echo -n "Checking if $mgmtSecGrp security group has $proto rule ..."
def=`$osn security-group-rule-list | awk -v grp=$mgmtSecGrp -v p=$proto '/'"$proto"'|protocol/ { if ($4 == grp && $8 == p && $10 == "0.0.0.0/0") n++; } END { if (n > 0) print "Yes"; else print "No"; }'`
if [ "$def" == "No" ]; then
    echo " No, it does not. Creating it."
    $osn security-group-rule-create --tenant-id $tenantId --protocol tcp --port-range-min 22 --port-range-max 22 --remote-ip-prefix 0.0.0.0/0 $mgmtSecGrp
else
    echo " Yes, it does."
fi
