#!/usr/bin/env bash

# Default values
# --------------
# adminUser is same as name of OpenStack network service,
# it should be 'neutron'.
adminUser=${1:-neutron}
osn=$adminUser
plugin=${2:-n1kv}
localrc=$3
TOP_DIR=$(cd $(dirname $localrc) && pwd)
mysql_user=$4
mysql_password=$5

if [[ -n $mysql_user && -n $mysql_password ]]; then
   mysql_auth="-u $mysql_user -p$mysql_password"
fi

if [[ ! -z $localrc && -f $localrc ]]; then
    eval $(grep ^Q_CISCO_CSR1KV_QCOW2_IMAGE= $localrc)
fi

l3AdminTenant="L3AdminTenant"
csr1kvFlavorName="csr1kv_router"
csr1kvFlavorId=621
networkHostsAggregateName="compute_network_hosts"
aggregateMetadataKey="aggregate_instance_extra_specs:network_host"
aggregateMetadataValue="True"
aggregateMetadata="$aggregateMetadataKey=$aggregateMetadataValue"
max_attempts=200
computeNetworkNodes=( $(hostname) )
csr1kvImageSrc=$Q_CISCO_CSR1KV_QCOW2_IMAGE
csr1kvImageName="csr1kv_openstack_img"
csr1kvDiskFormat="qcow2"
csr1kvContainerFormat="bare"
#csr1kvGlanceExtraParams="--property hw_vif_model=e1000 --property hw_disk_bus=ide --property hw_cdrom_bus=ide"


# We need to add hosts to aggregates in a separate process
# that can wait for nova compute to start as this script
# may run before nova compute has started
function add_host_to_aggregate {
    local host_array_name=$1[@]
    local hosts=("${!host_array_name}")
    local attempt=1
    echo "Configuring compute nodes to act as network hosts ..."
    while [ ${#hosts[@]} -gt 0  -a  $attempt -le $max_attempts ]; do
        for host in "${hosts[@]}"; do
            host_exists=`nova host-describe $host 2>&1 | awk 'BEGIN { res = "Yes" } /ERROR/ { if ($1 == "ERROR") res = "No"; } END { print res; } '`
            if [ "$host_exists" == "Yes" ]; then
                host_added=`nova aggregate-details $aggregateId 2>&1 | awk -v host=$host 'BEGIN { res = "No" } { if (index($8, host) > 0) res = "Yes"; } END { print res }'`
                if [ "$host_added" == "No" ]; then
                    echo "    Adding host '$host' to '$networkHostsAggregateName' aggregate"
                    nova aggregate-add-host $aggregateId $host > /dev/null 2>&1
                fi
            else
                remaining[${#remaining[@]}]=$host
            fi
        done
        hosts=(${remaining[@]})
        remaining=( )
        attempt=$(($attempt+1))
        sleep 1
    done
    exit 0
}


tenantId=`keystone tenant-get $l3AdminTenant 2>&1 | awk '/No tenant|id/ { if ($1 == "No") print "No"; else if ($2 == "id") print $4; }'`
if [ "$tenantId" == "No" ]; then
   echo "No $l3AdminTenant exists, please create one using the setup_keystone... script then re-run this script."
   echo "Aborting!"
   exit 1
fi


source $TOP_DIR/openrc $adminUser $L3AdminTenant

echo -n "Checking if flavor '$csr1kvFlavorName' exists ..."
flavorId=`nova flavor-show $csr1kvFlavorId 2>&1 | awk '/No flavor|id|endpoint/ {
   if (index($0, "endpoint") > 0) {
      print "NO SERVER"; nextfile;
   }
   else if (index($0, "No flavor") > 0)
      print "No";
   else
      print $4;
}'`

if [ "$flavorId" == "No" ]; then
   echo " No, it does not. Creating it."
   flavorId=`nova flavor-create $csr1kvFlavorName $csr1kvFlavorId 4096 0 4 --is-public False | awk -v r=$csr1kvFlavorName '$0 ~ r { print $2 }'`
elif [ "$flavorId" == "NO SERVER" ]; then
   echo " Nova does not seem to be running. Skipping!"
else
   echo " Yes, it does."
fi

# We disable scheduling by aggregate metadata for now.
if false; then
    echo -n "Checking if flavor '$csr1kvFlavorName' has metadata '$aggregateMetadata' ..."
    hasMetadata=`nova flavor-show 621 2>&1 | awk -v key=$aggregateMetadataKey -v value=$aggregateMetadataValue '
    BEGIN { res = "No" }
    {
       if ($2 == "extra_specs" && index($4, key) > 0  && index($5, value) > 0)
         res = "Yes"
    }
    END { print res }'`

    if [ "$hasMetadata" == "No" ]; then
       echo " No, it does not. Adding it."
       nova flavor-key $csr1kvFlavorId set $aggregateMetadata > /dev/null 2>&1
    else
       echo " Yes, it does."
    fi

    echo -n "Checking if aggregate '$networkHostsAggregateName' exists ..."
    aggregateId=`nova aggregate-list 2>&1 | awk -v name=$networkHostsAggregateName -v r=$networkHostsAggregateName"|Id" '
    BEGIN { res = "No" }
    $0 ~ r {
      if ($2 != "Id" && $4 == name)
        res = $2;
    }
    END { print res; }'`

    if [ "$aggregateId" == "No" ]; then
       echo " No, it does not. Creating it."
       aggregateId=`nova aggregate-create $networkHostsAggregateName 2>&1 | awk -v name=$networkHostsAggregateName -v r=$networkHostsAggregateName"|Id" 'BEGIN { res = "No" } $0 ~ r { if ($2 != "Id" && $4 == name) res = $2; } END { print res; }'`
    else
       echo " Yes, it does."
    fi

    echo "Setting metadata for aggregate '$networkHostsAggregateName'"
    nova aggregate-set-metadata $aggregateId $aggregateMetadata > /dev/null 2>&1

    # Add nodes to the aggregate in a separate process that can run until
    # the nova compute has started on the hosts.
    ( add_host_to_aggregate computeNetworkNodes ) &
fi

if [ "$flavorId" != "NO SERVER" ]; then
    echo "Removing relevant quota limits ..."
    nova quota-update --cores -1 --instances -1 --ram -1 $tenantId > /dev/null 2>&1
fi

echo -n "Checking if image '$csr1kvImageName' exists ..."
hasImage=`glance image-show $csr1kvImageName 2>&1 | awk '
/Property|No|endpoint/ {
   if (index($0, "endpoint") > 0) {
      print "NO SERVER"; nextfile;
   }
   else if (index($0, "No image") > 0)
      print "No";
   else
      print "Yes";
}'`

if [ "$hasImage" == "No" ]; then
   echo " No, it does not. Creating it."
   glance image-create --name $csr1kvImageName --disk-format $csr1kvDiskFormat --container-format $csr1kvContainerFormat --file $csr1kvImageSrc $csr1kvGlanceExtraParams
elif [ "$hasImage" == "NO SERVER" ]; then
   echo " Glance does not seem to be running. Skipping!"
else
   echo " Yes, it does."
fi
