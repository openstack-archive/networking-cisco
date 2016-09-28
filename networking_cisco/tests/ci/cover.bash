#!/bin/bash
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


ALLOWED_EXTRA_MISSING=4

show_diff () {
    head -1 $1
    diff -U 0 $1 $2 | sed 1,2d
}

run_coverage () {
    local which=$1 ; shift
    report=$(mktemp -t rally_coverageXXXXXXX)
    find . -type f -name "*.pyc" -delete && python setup.py test --coverage --coverage-package-name=networking_cisco --testr-args="$*"
    coverage report > $report
    echo "$which COVERAGE"
    cat $report
    missing=$(awk 'END { print $3 }' $report)
}

# Stash uncommitted changes, checkout master and save coverage report
uncommited=$(git status --porcelain | grep -v "^??")
[[ -n "$uncommited" ]] && git -c user.name=test -c user.email=test@test.com stash -u > /dev/null
git checkout HEAD^

run_coverage BASELINE $*
baseline_missing=$missing
baseline_report=$report

# Checkout back and unstash uncommitted changes (if any)
git checkout -
[[ -n $uncommited ]] && git stash pop > /dev/null

# Generate and save coverage report
run_coverage CURRENT $*
current_missing=$missing
current_report=$report

# Show coverage details
allowed_missing=$((baseline_missing+ALLOWED_EXTRA_MISSING))

echo "Allowed to introduce missing lines : ${ALLOWED_EXTRA_MISSING}"
echo "Missing lines in master            : ${baseline_missing}"
echo "Missing lines in proposed change   : ${current_missing}"

if [ $allowed_missing -gt $current_missing ];
then
    if [ $baseline_missing -lt $current_missing ];
    then
        show_diff $baseline_report $current_report
        echo "Coverage has declined some with this change - consider adding more tests, if possible."
    else
        if [ $baseline_missing -gt $current_missing ];
        then
            echo "Great job! Coverage has improved with this commit!"
        else
            echo "Coverage is the same with this change."
        fi
    fi
    exit_code=0
else
    show_diff $baseline_report $current_report
    echo "Please write more unit tests, we should maintain/improve our test coverage :( "
    exit_code=1
fi

rm $baseline_report $current_report
exit $exit_code
