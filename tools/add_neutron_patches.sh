#!/bin/sh

echo "Adding neutron patches into the testing env"

NEUTRON_SRC="$1"
LIST_SRC="$2/test-patches.txt"

echo "Checking Directory Existence: $NEUTRON_SRC"

if [ ! -d "$NEUTRON_SRC" ]; then
  echo "Directory $NEUTRON_SRC does not exist, aborting..."
  exit 1
fi

cd $NEUTRON_SRC

# Ensure we're on toxBranch not master or other branches
git checkout -b toxBranch 2> /dev/null
git checkout toxBranch 2> /dev/null

# Fetch and rebase patches into neutron src
while read p; do
  git fetch https://review.openstack.org/openstack/neutron $p
  git checkout FETCH_HEAD
  git rebase master
  git rebase HEAD toxBranch

  if [ -d "$2/.git/rebase-merge" ]; then
    echo "Patch $p in confict and can not be added..."
    git rebase --abort
  fi
done <$LIST_SRC

# Ensure we're up to date with master even after rebases
git checkout toxBranch
git rebase master
