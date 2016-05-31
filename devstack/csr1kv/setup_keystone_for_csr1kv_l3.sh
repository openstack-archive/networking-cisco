#!/usr/bin/env bash

## Users, roles, tenants ##
adminUser=${1:-neutron}
adminRole=admin
l3AdminTenant=L3AdminTenant
serviceTenant=service
# Below user is just for demos so that we don't see all logical instances.
regularUser=viewer
password=viewer


echo -n "Checking if $l3AdminTenant tenant exists ..."
tenantId=`openstack project show $l3AdminTenant 2>&1 | awk '/No|id/ { if ($1 == "No") print "No"; else if ($2 == "id") print $4; }'`
if [ "$tenantId" == "No" ]; then
   echo " No, it does not. Creating it."
   tenantId=$(openstack project create $l3AdminTenant --domain="default" --or-show -f value -c id)
   echo $tenantId
else
   echo " Yes, it does."
fi


echo -n "Checking if $regularUser user exists ..."
userId=`openstack user show $regularUser 2>&1 | awk '/No user|id/ { if ($1 == "No") print "No"; else print $4; }'`
if [ "$userId" == "No" ]; then
   echo " No, it does not. Creating it."
   userId=$(openstack user create $regularUser --password $password --domain="default" --or-show -f value -c id)
   echo $userId
else
   echo " Yes, it does."
fi

echo -n "Checking if $adminUser user has admin privileges in $l3AdminTenant tenant ..."
isAdmin=`openstack --os-username $adminUser --os-project-name $l3AdminTenant user role list 2>&1 | awk 'BEGIN { res="No" } { if ($4 == "admin") res="Yes"; } END { print res; }'`

if [ "$isAdmin" == "No" ]; then
   echo " No, it does not. Giving it admin rights."
   admUserId=`openstack user show $adminUser | awk '{ if ($2 == "id") print $4 }'`
   admRoleId=`openstack role show $adminRole | awk '{ if ($2 == "id") print $4 }'`
   openstack role add $admRoleId --user $admUserId  --project $tenantId
else
   echo " Yes, it has."
fi


# What follows can be removed once L3AdminTenant is used to lookup UUID of L3AdminTenant

echo -n "Determining UUID of $serviceTenant tenant ..."
tenantId=`openstack project show $serviceTenant 2>&1 | awk '/No tenant|id/ { if ($1 == "No") print "No"; else if ($2 == "id") print $4; }'`

if [ "$tenantId" == "No" ]; then
   echo "Error: $serviceTenant tenant does not seem to exist. Aborting!"
   exit 1
else
   echo " Done."
fi


echo -n "Checking if $adminUser user has admin privileges in $serviceTenant tenant ..."
isAdmin=`openstack --os-username $adminUser --os-project-name $serviceTenant user role list 2>&1 | awk 'BEGIN { res="No" } { if ($4 == "admin") res="Yes"; } END { print res; }'`

if [ "$isAdmin" == "No" ]; then
   echo " No, it does not. Giving it admin rights."
   admUserId=`openstack user show $adminUser | awk '{ if ($2 == "id") print $4 }'`
   admRoleId=`openstack role show $adminRole | awk '{ if ($2 == "id") print $4 }'`
   openstack role add $admRoleId --user $admUserId --project $tenantId
else
   echo " Yes, it has."
fi
