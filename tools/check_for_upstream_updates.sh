if [[ -e commit_msg ]]; then
  git status -s > git_status
  empty=true
  while read l; do
    split=( $l )
    if [[ "${split[0]}" != "??" ]]; then
      empty=false
      break
    fi
  done < git_status
  rm git_status 2> /dev/null

  if [[ $empty == false ]]; then
    git commit -F commit_msg
    if [[ $? > 0 ]]; then
      echo "Commit still failing, conflict may not be completely resolved. You can try running:"
      echo "git commit -F commit_msg"
      echo "manually to see the problem that needs resolving." 
      echo "If you complete the cherry-pick manually, please delete commit_msg."
    fi
  else
    echo "Nothing to do, all files now deleted!"
  fi
fi

git fetch https://git.openstack.org/openstack/neutron

echo "-------------------------------------------------------------"

git ls-files | grep py | sed -e "s/networking_cisco/neutron/g" > files

rm actual_files 2> /dev/null
while read l; do
  stuff="`git log -- $l`"
  if [[ $stuff != "" ]]; then
    echo "$l" >> actual_files
  fi
done< files
rm files

cat actual_files | xargs git log FETCH_HEAD --since="Thu, 29 Jan 2015 13:04:38 +0000" -- | grep "Change-Id" | sed -e "s/.*Change-Id:\ \(.*\).*/\1/g" > neutron_changes

git ls-files | xargs git log --since="Thu, 29 Jan 2015 13:04:38 +0000" -- | grep "Change-Id" | sed -e "s/.*Change-Id:\ \(.*\).*/\1/g" > networking_cisco_changes

rm actual_files

sort neutron_changes > neutron_changes.temp
mv neutron_changes.temp neutron_changes

sort networking_cisco_changes > net_cisco_changes.temp
mv net_cisco_changes.temp networking_cisco_changes

sort tools/shim-change-ids > shim-change-ids.temp

comm -23 neutron_changes shim-change-ids.temp > neutron_changes.temp
mv neutron_changes.temp neutron_changes

rm shim-change-ids.temp

comm -23 neutron_changes networking_cisco_changes > not_cherry_picked_changes

rm networking_cisco_changes
rm neutron_changes

echo "Change Id's affecting files in networking-cisco that aren't in our history"
echo "(WARNING: THESE ARE NOT IN CHRONOLOGICAL ORDER):"
cat not_cherry_picked_changes

greps=""
while read c; do
  greps+="--grep=$c "
done < not_cherry_picked_changes

rm not_cherry_picked_changes

echo "Commits in reverse date order from Change Id's:"
git log FETCH_HEAD --reverse --pretty=oneline $greps > not_cherry_picked_commits
cat not_cherry_picked_commits

#cat not_cherry_picked_commits | sed -e "s/\([^\ ]*\).*/\1/g" > not_cherry_picked_commits.temp
#mv not_cherry_picked_commits.temp not_cherry_picked_commits
#
#echo "Now attempting to cherry-pick missing changes in networking-cisco tree:"
#
#while read c; do
#  echo "Cherry picking $c"
#  git cherry-pick $c 2> /dev/null
#
#  git status -s > git_status
#  while read l; do
#    split=( $l )
#    if [[ "${split[0]}" == "DU" ]]; then
#      git rm "${split[1]}" > /dev/null
#    fi
#  done < git_status
#  rm git_status 2> /dev/null
#  
#  rm commit_msg 2> /dev/null
#  while read l; do
#    if [[ "$l" == "Conflicts:" ]]; then
#      echo "Cherry-picked from openstack/neutron" >> commit_msg
#      break
#    fi
#    echo "$l" >> commit_msg
#  done < .git/MERGE_MSG
#
#  git status -s > git_status
#  empty=true
#  while read l; do
#    split=( $l )
#    if [[ "${split[0]}" != "??" ]]; then
#      empty=false
#      break
#    fi
#  done < git_status
#  rm git_status 2> /dev/null
#
#  if [[ $empty == false ]]; then
#    git commit --quiet -F commit_msg 2> /dev/null
#
#    if [[ $? > 0 ]]; then
#      echo "Unabled to resolve cherry-pick successfully, there is a conflict that needs manual resolution. Please resolve these conflicts, then rerun this script to continue the automation."
#      break
#    else
#      echo "Cherry-pick complete!!!"
#    fi
#  else
#    echo "Nothing to do, all files now deleted!"
#  fi
#  rm commit_msg
#done < not_cherry_picked_commits

rm not_cherry_picked_commits
