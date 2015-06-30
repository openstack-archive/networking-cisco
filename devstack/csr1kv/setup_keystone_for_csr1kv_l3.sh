#!/bin/bash

# Make sure you that you have sourced openrc for a user
# with admin (privilege) rights before you run this script.
# See README.TXT for further details.

# Default values
# --------------
# adminUser is same as name of Openstack network service,
# it should be 'neutron'.
adminUser=${1:-neutron}
adminRole=admin
l3AdminTenant=L3AdminTenant
serviceTenant=service
# Below user is just for demos so that we don't see all logical instances.
regularUser=viewer
password=viewer


echo -n "Checking if $l3AdminTenant tenant exists ..."
tenantId=`keystone tenant-get $l3AdminTenant 2>&1 | awk '/No tenant|id/ { if ($1 == "No") print "No"; else print $4; }'`

if [ "$tenantId" == "No" ]; then
   echo " No, it does not. Creating it."
   tenantId=`keystone tenant-create --name $l3AdminTenant --description "Owner of CSR1kv VMs" | awk '/id/ { print $4; }'`
else
   echo " Yes, it does."
fi


echo -n "Checking if $regularUser user exists ..."
userId=`keystone user-get $regularUser 2>&1 | awk '/No user|id/ { if ($1 == "No") print "No"; else print $4; }'`
if [ "$userId" == "No" ]; then
   echo " No, it does not. Creating it."
   keystone user-create --name $regularUser --tenant $l3AdminTenant --pass $password --enabled true
else
   echo " Yes, it does."
fi

echo -n "Checking if $adminUser user has admin privileges in $l3AdminTenant tenant ..."
isAdmin=`keystone --os-username $adminUser --os-tenant-name $l3AdminTenant user-role-list 2>&1 | awk 'BEGIN { res="No" } { if ($4 == "admin") res="Yes"; } END { print res; }'`
if [ "$isAdmin" == "No" ]; then
   echo " No, it does not. Giving it admin rights."
   admUserId=`keystone user-get $adminUser | awk '{ if ($2 == "id") print $4 }'`
   admRoleId=`keystone role-get $adminRole | awk '{ if ($2 == "id") print $4 }'`
   keystone user-role-add --user-id $admUserId --role-id $admRoleId --tenant-id $tenantId
else
   echo " Yes, it has."
fi


# What follows can be removed once L3AdminTenant is used to lookup UUID of L3AdminTenant

echo -n "Determining UUID of $serviceTenant tenant ..."
tenantId=`keystone tenant-get $serviceTenant 2>&1 | awk '/No tenant|id/ { if ($1 == "No") print "No"; else print $4; }'`

if [ "$tenantId" == "No" ]; then
   echo "Error: $serviceTenant tenant does not seem to exist. Aborting!"
   exit 1
else
   echo " Done."
fi


echo -n "Checking if $adminUser user has admin privileges in $serviceTenant tenant ..."
isAdmin=`keystone --os-username $adminUser --os-tenant-name $serviceTenant user-role-list 2>&1 | awk 'BEGIN { res="No" } { if ($4 == "admin") res="Yes"; } END { print res; }'`

if [ "$isAdmin" == "No" ]; then
   echo " No, it does not. Giving it admin rights."
   admUserId=`keystone user-get $adminUser | awk '{ if ($2 == "id") print $4 }'`
   admRoleId=`keystone role-get $adminRole | awk '{ if ($2 == "id") print $4 }'`
   keystone user-role-add --user-id $admUserId --role-id $admRoleId --tenant-id $tenantId
else
   echo " Yes, it has."
fi
