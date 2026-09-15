#!/usr/bin/env bash
# rolling-begin-task and rolling-end-task: the throwaway branch, held and
# shown tests, refusals, and the way back.
. "$(dirname "$0")/lib.sh"
scratch_world

# --fix with the test held: branch from the fix's parent, test not in tree.
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh); rc=$?
assert_status "begin --fix --held" 0 $rc
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p')
base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
rt=$(printf '%s\n' "$out" | sed -n 's/^return-to: //p')
assert_contains "branch name" "rolling/greet-politely-" "$branch"
assert_eq "on the branch" "$branch" "$(git symbolic-ref --short HEAD)"
assert_eq "base is HEAD" "$(git rev-parse HEAD)" "$base"
assert_eq "return-to is ref and sha" "main $FIX" "$rt"
assert_contains "held line" "held: tests/greet.test.sh" "$out"
assert_no_file "held test not in tree" tests/greet.test.sh
assert_file "held test copied" "$LEARNER/held/tests/greet.test.sh"
assert_contains "code is pre-fix" "HELLO" "$(cat src/greet.sh)"
assert_eq "tree clean" "" "$(git status --porcelain)"
assert_eq "fix not in history" "" "$(git log --format=%H | grep -x "$FIX" || true)"
assert_eq "one commit on top of the parent" "$PRE" "$(git rev-parse HEAD^)"
write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: $rt
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
held: tests/greet.test.sh
held-verify: test tests/greet.test.sh"

# end-task: commits leftovers, returns to main, keeps the branch.
echo "edit" >> src/greet.sh
echo "new" > src/other.sh
out=$(rolling-end-task); rc=$?
assert_status "end-task" 0 $rc
assert_contains "end says committed" "committed the learner's uncommitted work" "$out"
assert_contains "end says back" "back on main" "$out"
assert_eq "back on main" "main" "$(git symbolic-ref --short HEAD)"
assert_eq "main untouched" "$FIX" "$(git rev-parse HEAD)"
assert_eq "branch kept" "1" "$(git branch --list "$branch" | wc -l | tr -d ' ')"
assert_contains "work committed on branch" "src/other.sh" "$(git show --stat --format= "$branch" | tr -d ' ')"
assert_eq "tree clean after return" "" "$(git status --porcelain)"

# end-task refuses when not on the task branch.
out=$(rolling-end-task 2>&1); rc=$?
assert_status "end refuses off-branch" 1 $rc
assert_contains "end names where it is" "not on $branch" "$out"

# --fix with the test shown: test present and failing on the branch.
rm -rf "$LEARNER"
out=$(rolling-begin-task setup --fix "$FIX" --shown tests/greet.test.sh); assert_status "begin --shown" 0 $?
assert_file "shown test in tree" tests/greet.test.sh
assert_eq "shown: tree clean (committed)" "" "$(git status --porcelain)"
assert_status "shown test fails on the starting state" 1 "$(sh run-test.sh tests/greet.test.sh >/dev/null 2>&1; echo $?)"
assert_not_contains "no held line for shown" "held:" "$out"
git switch -q main

# --here: branches at HEAD and commits what the tutor added.
echo 'echo seam' > tests/seam.test.sh
out=$(rolling-begin-task setup --here tests/seam.test.sh); assert_status "begin --here" 0 $?
assert_eq "here: tree clean" "" "$(git status --porcelain)"
assert_contains "here: committed the file" "tests/seam.test.sh" "$(git show --stat --format= HEAD)"
assert_contains "here: return-to" "return-to: main $FIX" "$out"
git switch -q main

# Refusals.
echo dirty >> src/greet.sh
out=$(rolling-begin-task setup --fix "$FIX" --held tests/greet.test.sh 2>&1); assert_status "dirty tree refused" 1 $?
assert_contains "dirty tree named" "not clean" "$out"
git checkout -q -- src/greet.sh
out=$(rolling-begin-task setup --fix "$PRE" --held tests/greet.test.sh 2>&1); assert_status "root commit refused" 1 $?
assert_contains "root commit named" "root commit" "$out"
out=$(rolling-begin-task setup --fix "$FIX" --held src/nope.sh 2>&1); assert_status "untouched path refused" 1 $?
assert_contains "untouched path named" "not changed by" "$out"
out=$(rolling-begin-task 'Bad Slug' --fix "$FIX" 2>&1); assert_status "bad slug refused" 2 $?
out=$(rolling-begin-task setup --fix "$FIX" --held /etc/passwd 2>&1); assert_status "absolute path refused" 1 $?
out=$(rolling-begin-task setup --fix "$FIX" --held ../x 2>&1); assert_status "dotdot refused" 1 $?
git switch -q main && git checkout -q -b side && git commit -q --allow-empty -m "merge me" && git switch -q main && git merge -q --no-ff -m merge side 2>/dev/null
MERGE=$(git rev-parse HEAD)
out=$(rolling-begin-task setup --fix "$MERGE" --held tests/greet.test.sh 2>&1); assert_status "merge commit refused" 1 $?
assert_contains "merge commit named" "merge commit" "$out"
assert_eq "refusals leave HEAD on main" "main" "$(git symbolic-ref --short HEAD)"
out=$(ROLLING_DATA='' rolling-begin-task setup --fix "$FIX" --held tests/greet.test.sh 2>&1); assert_status "held without data refused" 1 $?
assert_eq "still on main" "main" "$(git symbolic-ref --short HEAD)"

# end-task returns to the sha when the ref is gone.
rolling-begin-task setup --fix "$FIX" --shown tests/greet.test.sh >/dev/null
b2=$(git symbolic-ref --short HEAD)
write_task "lesson: setup
mode: write
branch: $b2
base: $(git rev-parse HEAD)
return-to: gone-branch $MERGE
scope: src"
out=$(rolling-end-task); assert_status "end with a gone ref" 0 $?
assert_contains "end says detached" "detached" "$out"
assert_eq "at the sha" "$MERGE" "$(git rev-parse HEAD)"
finish
