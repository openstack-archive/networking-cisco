#!/usr/bin/env bash

# osn is the name of OpenStack network service, i.e.,
# it should be 'neutron'.
osn=${1:-neutron}

function delete_service_resources_by_name() {
    service=$1
    resource=$2
    name=$3
    local list_command="list --field=id --field=name"
    local delete_command="delete"
    if [[ "$service" == "$osn" ]]; then
       list_command=$resource"-list --field=id --field=name"
       delete_command=$resource"-"$delete_command
    fi

    ids=($($service $list_command | awk -v n=$name '$4 ~ n { print $2; }'))

    if [[ ${#ids[@]} > 0 ]]; then
       echo "Deleting ${#ids[@]} $resource resources named $name"
       for id in "${ids[@]}"; do
          echo "    $service $delete_command $id"
          $service $delete_command $id
       done
       if [[ "$service" == "nova" ]]; then
          wait_time=7
          echo "Waiting $wait_time seconds to let Nova clean up"
          sleep $wait_time
       fi
    else
       echo "No $resource resources named $name to delete"
    fi
}

devstack_dir=$(find -L $HOME -name devstack -type d)

source $devstack_dir/openrc $osn L3AdminTenant

delete_service_resources_by_name nova server CSR1kv_nrouter

delete_service_resources_by_name $osn port mgmt
delete_service_resources_by_name $osn port t1_p:
delete_service_resources_by_name $osn port t2_p:

delete_service_resources_by_name $osn subnet t1_sn:
delete_service_resources_by_name $osn subnet t2_sn:

delete_service_resources_by_name $osn net t1_n:
delete_service_resources_by_name $osn net t2_n:


eval $(grep ^MYSQL_USER= $devstack_dir/lib/database)
eval $(grep ^MYSQL_USER= $devstack_dir/localrc)
eval $(grep ^MYSQL_PASSWORD= $devstack_dir/localrc)
eval $(grep ^Q_PLUGIN= $devstack_dir/localrc)
table="$Q_PLUGIN_$osn"

mysql -u$MYSQL_USER -p$MYSQL_PASSWORD -e "use $table; delete from hostingdevices;"

echo
echo "Now please RESTART $osn SERVER and CISCO CFG AGENT!"
