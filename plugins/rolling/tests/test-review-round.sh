#!/usr/bin/env bash
# What the first review of the toolkit found (PR for 1a.3): the composed
# loop's own property, recovery from a kill mid-verify, a failed restore
# that must not lose the learner's file, the proof that must not say ok
# for lines that never ran, a map command ending in a control operator,
# a stale held/ from a previous task, --here sweeping the learner's own
# work, a CRLF map, and a profile heading with a trailing space.
. "$(dirname "$0")/lib.sh"
scratch_world

task_for() {
  # task_for BRANCH BASE: a held-test task on the fix.
  write_task "lesson: greet-politely
mode: write
branch: $1
base: $2
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
fix: $FIX
scope: src
scope: tests
verify: check
held: tests/greet.test.sh
held-verify: test tests/greet.test.sh
expect-fail-on-base: held-verify test tests/greet.test.sh"
}

# --- The composed loop: begin (held) → edit → report → end. The held test
# is in no diff and no commit, the tree is as the learner left it, and the
# learner is back on their branch.
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
task_for "$branch" "$base"
sedi 's/HELLO/Hello/' src/greet.sh
mkdir -p tests && printf '#!/bin/sh\necho "learner test"\n' > tests/greet.test.sh
rep=$(rolling-report)
assert_not_contains "loop: held test not in diff" "Hello pat" "$rep"
assert_contains "loop: held passes" "HELD PASS" "$rep"
assert_eq "loop: learner's test intact after report" "learner test" "$(sh tests/greet.test.sh)"
assert_no_file "loop: no pending marker" "$LEARNER/held-aside.pending"
out=$(rolling-end-task); assert_status "loop: end-task" 0 $?
assert_eq "loop: back on main" "main" "$(git symbolic-ref --short HEAD)"
assert_eq "loop: held test in no commit on the branch" "" "$(git log "$branch" --format=%H -S 'Hello pat' -- tests/greet.test.sh)"
assert_contains "loop: learner's test committed on the branch" "learner test" "$(git show "$branch:tests/greet.test.sh")"
assert_eq "loop: tree clean after" "" "$(git status --porcelain)"
rolling-close-task >/dev/null

# --- Recovery after a kill mid-verify: a pending record and a set-aside
# file left behind are finished by the next script that touches the tree.
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
task_for "$branch" "$base"
mkdir -p tests && printf '#!/bin/sh\necho "learner test 2"\n' > tests/greet.test.sh
# Simulate the state SIGKILL leaves: learner's file set aside, held copy applied, record present.
mkdir -p "$LEARNER/held-aside/tests" && mv tests/greet.test.sh "$LEARNER/held-aside/tests/greet.test.sh"
cp "$LEARNER/held/tests/greet.test.sh" tests/greet.test.sh
printf 'aside tests/greet.test.sh\napplied tests/greet.test.sh\n' > "$LEARNER/held-aside.pending"
assert_contains "kill: the held test is in the tree before recovery" "Hello pat" "$(cat tests/greet.test.sh)"
out=$(rolling-diff)
assert_contains "kill: diff reports the repair" "HELD reverted: restored your file at tests/greet.test.sh" "$out"
assert_not_contains "kill: diff does not show the held test" "Hello pat" "$out"
assert_contains "kill: diff shows the learner's file" "learner test 2" "$out"
assert_eq "kill: learner's file back" "learner test 2" "$(sh tests/greet.test.sh)"
assert_no_file "kill: record gone" "$LEARNER/held-aside.pending"
assert_no_file "kill: aside gone" "$LEARNER/held-aside"
# The same, finished by end-task instead.
mkdir -p "$LEARNER/held-aside/tests" && mv tests/greet.test.sh "$LEARNER/held-aside/tests/greet.test.sh"
cp "$LEARNER/held/tests/greet.test.sh" tests/greet.test.sh
printf 'aside tests/greet.test.sh\napplied tests/greet.test.sh\n' > "$LEARNER/held-aside.pending"
out=$(rolling-end-task); assert_status "kill: end-task after a pending revert" 0 $?
assert_contains "kill: end-task repaired first" "HELD reverted" "$out"
assert_eq "kill: held test in no commit" "" "$(git log "$branch" --format=%H -S 'Hello pat' -- tests/greet.test.sh)"
assert_contains "kill: learner's file committed" "learner test 2" "$(git show "$branch:tests/greet.test.sh")"
rolling-close-task >/dev/null

# --- A restore that fails keeps the learner's file and says so. (Root
# cannot be locked out of a directory, so this section is skipped as root.)
if [ "$(id -u)" -ne 0 ]; then
  out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
  branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
  write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
held: tests/greet.test.sh
held-verify: lockdir
held-verify: test tests/greet.test.sh"
  # A map command that makes tests/ unwritable while the held test is applied.
  awk '{ print } /^  args: sh args.sh$/ { print "  lockdir: chmod a-w tests" }' .rolling/map.md > .rolling/map.md.new && mv .rolling/map.md.new .rolling/map.md
  mkdir -p tests && printf '#!/bin/sh\necho "precious"\n' > tests/greet.test.sh
  out=$(rolling-verify); rc=$?
  chmod u+w tests
  assert_status "restore-fail: still exit 0" 0 $rc
  assert_contains "restore-fail: reported" "HELD REVERT FAILED" "$out"
  assert_contains "restore-fail: summary says so" "REVERT FAILED" "$out"
  assert_file "restore-fail: learner's file kept aside" "$LEARNER/held-aside/tests/greet.test.sh"
  assert_eq "restore-fail: learner's content intact" "precious" "$(sh "$LEARNER/held-aside/tests/greet.test.sh")"
  assert_file "restore-fail: record kept" "$LEARNER/held-aside.pending"
  # Now the directory is writable again: the next script finishes the revert.
  out=$(rolling-diff)
  assert_contains "restore-fail: repaired later" "HELD reverted: restored your file" "$out"
  assert_eq "restore-fail: learner's file back" "precious" "$(sh tests/greet.test.sh)"
  assert_no_file "restore-fail: record gone" "$LEARNER/held-aside.pending"
  git checkout -q -- .rolling/map.md 2>/dev/null || true
  rolling-end-task >/dev/null; rolling-close-task >/dev/null
  git switch -q main
else
  echo "  (skipped the failed-restore section: running as root)"
fi

# --- The proof is not ok for lines that never ran.
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
verify: nope
held: tests/greet.test.sh
held-verify: test tests/greet.test.sh
expect-fail-on-base: held-verify test tests/greet.test.sh"
out=$(rolling-verify --on-base)
assert_contains "proof: unknown line" "UNKNOWN  nope" "$out"
assert_contains "proof: not ok on an unknown line" "PROOF: not ok" "$out"
write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
held: ../escape.sh
held-verify: test tests/greet.test.sh
expect-fail-on-base: held-verify test tests/greet.test.sh"
out=$(rolling-verify --on-base)
assert_contains "proof: rejected held path" "HELD REJECTED ../escape.sh" "$out"
assert_contains "proof: gap named" "PROOF GAP: expected to fail but never ran" "$out"
assert_contains "proof: not ok when the held test never ran" "PROOF: not ok" "$out"
task_for "$branch" "$base"
out=$(rolling-verify --on-base)
assert_contains "proof: ok when everything ran" "PROOF: ok" "$out"
assert_contains "proof: expected failures counted" "expected failures: 1" "$out"
rolling-end-task >/dev/null; rolling-close-task >/dev/null

# --- A map command ending in a control operator: rejected by the checker
# and never run by the verifier.
M="$WORLD/m2"; rm -rf "$M"; cp -R .rolling "$M"
awk '{ print } /^  args: sh args.sh$/ { print "  evil: echo ran;" }' "$M/map.md" > "$M/map.md.new" && mv "$M/map.md.new" "$M/map.md"
out=$(rolling-check-map "$M" 2>&1); assert_status "control operator: check-map fails" 1 $?
assert_contains "control operator: named" "commands.evil ends in an operator" "$out"
cp "$M/map.md" .rolling/map.md
write_task "lesson: setup
mode: write
branch: b
base: $FIX
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: evil touch $WORLD/PWNED"
out=$(rolling-verify)
assert_contains "control operator: verifier rejects" "REJECTED evil touch" "$out"
assert_no_file "control operator: nothing ran" "$WORLD/PWNED"
git checkout -q -- .rolling/map.md
rm -f "$LEARNER/task.md"

# --- A task already open is refused; a previous held/ is cleared.
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
task_for "$branch" "$base"
out=$(rolling-begin-task setup --fix "$FIX" --shown tests/greet.test.sh 2>&1); assert_status "open task refused" 1 $?
assert_contains "open task named" "a task is already open (greet-politely)" "$out"
assert_eq "open task: still on the first branch" "$branch" "$(git symbolic-ref --short HEAD)"
rolling-end-task >/dev/null; rolling-close-task >/dev/null
assert_no_file "close cleared held/" "$LEARNER/held"
# A held/ left over by hand (no task open) is cleared by the next begin.
mkdir -p "$LEARNER/held/tests" && echo stale > "$LEARNER/held/tests/stale.sh"
out=$(rolling-begin-task setup --fix "$FIX" --shown tests/greet.test.sh); assert_status "begin after stale held" 0 $?
assert_no_file "stale held cleared" "$LEARNER/held/tests/stale.sh"
git switch -q main

# --- --here refuses to sweep the learner's own changes.
echo "learner's own edit" >> src/greet.sh
echo "seam" > tests/seam.test.sh
out=$(rolling-begin-task setup --here tests/seam.test.sh 2>&1); assert_status "--here refuses other changes" 1 $?
assert_contains "--here names them" "src/greet.sh" "$out"
assert_eq "--here left HEAD alone" "main" "$(git symbolic-ref --short HEAD)"
git checkout -q -- src/greet.sh
out=$(rolling-begin-task setup --here tests/seam.test.sh); assert_status "--here with only the named path" 0 $?
assert_contains "--here committed only the named path" "tests/seam.test.sh" "$(git show --stat --format= HEAD)"
git switch -q main

# --- A CRLF map still parses; a trailing space on a profile heading still checks.
M="$WORLD/m3"; rm -rf "$M"; cp -R .rolling "$M"
sed 's/$/\r/' "$M/map.md" > "$M/map.md.crlf" && mv "$M/map.md.crlf" "$M/map.md"
out=$(rolling-check-map "$M"); assert_status "CRLF map checks clean" 0 $?
mkdir -p "$LEARNER"
printf '# Profile\n\n## Background\nx\n\n## Destination \ngreeting: expert\n\n## Why\ny\n\n## Satisfied \n- setup (nope)\n' > "$LEARNER/profile.md"
out=$(rolling-check-profile 2>&1); assert_status "trailing-space headings still checked" 1 $?
assert_contains "trailing-space: destination fault" "destination line is not" "$out"
assert_contains "trailing-space: satisfied fault" "satisfied line is not" "$out"
# ---------------------------------------------------------------- round two

# A held path listed twice, or spelled two ways, is refused everywhere.
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
held: tests/greet.test.sh
held: tests/greet.test.sh
held-verify: test tests/greet.test.sh"
out=$(rolling-check-task 2>&1); assert_status "dup held: check-task fails" 1 $?
assert_contains "dup held: named" "held 'tests/greet.test.sh' is listed twice" "$out"
mkdir -p tests && printf '#!/bin/sh\necho "mine"\n' > tests/greet.test.sh
out=$(rolling-verify)
assert_contains "dup held: verifier refuses" "HELD REJECTED tests/greet.test.sh   (listed twice)" "$out"
assert_eq "dup held: learner's file intact" "mine" "$(sh tests/greet.test.sh)"
write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
held: ./tests/greet.test.sh
held-verify: test tests/greet.test.sh"
out=$(rolling-check-task 2>&1); assert_contains "dot-slash held path refused" "not a plain repository-relative path" "$out"
out=$(rolling-verify); assert_contains "dot-slash: verifier refuses" "HELD REJECTED ./tests/greet.test.sh" "$out"
assert_eq "dot-slash: learner's file intact" "mine" "$(sh tests/greet.test.sh)"

# SIGTERM during a held line reverts and stops: no later held line runs
# against the reverted tree.
awk '{ print } /^  args: sh args.sh$/ { print "  slow: sleep 5" }' .rolling/map.md > .rolling/map.md.new && mv .rolling/map.md.new .rolling/map.md
write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
held: tests/greet.test.sh
held-verify: slow
held-verify: test tests/greet.test.sh"
rolling-verify > "$WORLD/term.out" 2>&1 &
vpid=$!
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40; do
  grep -q "^applied " "$LEARNER/held-aside.pending" 2>/dev/null && break
  sleep 0.1
done
sleep 0.2   # let the held line start
kill -TERM "$vpid" 2>/dev/null
wait "$vpid" 2>/dev/null
out=$(cat "$WORLD/term.out")
assert_contains "sigterm: says interrupted" "VERIFIER: interrupted" "$out"
assert_not_contains "sigterm: no later held line ran" "HELD PASS     test" "$out"
assert_eq "sigterm: learner's file back" "mine" "$(sh tests/greet.test.sh)"
assert_no_file "sigterm: no record left" "$LEARNER/held-aside.pending"
git checkout -q -- .rolling/map.md

# A failed revert fails the proof (non-root only).
if [ "$(id -u)" -ne 0 ]; then
  awk '{ print } /^  args: sh args.sh$/ { print "  lockdir: chmod a-w tests" }' .rolling/map.md > .rolling/map.md.new && mv .rolling/map.md.new .rolling/map.md
  write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
held: tests/greet.test.sh
held-verify: lockdir
held-verify: test tests/greet.test.sh
expect-fail-on-base: held-verify test tests/greet.test.sh"
  out=$(rolling-verify --on-base); chmod u+w tests
  assert_contains "revert-fail: proof not ok" "PROOF: not ok" "$out"
  rolling-diff >/dev/null   # finishes the revert
  assert_eq "revert-fail: learner's file back" "mine" "$(sh tests/greet.test.sh)"
  git checkout -q -- .rolling/map.md
fi

# Redirections and comments in a map command are refused, consistently.
M="$WORLD/m4"; rm -rf "$M"; cp -R .rolling "$M"
awk '{ print } /^  args: sh args.sh$/ { print "  redir: sh args.sh >"; print "  hash: sh args.sh;#x"; print "  spaced: sh args.sh # note" }' "$M/map.md" > "$M/map.md.new" && mv "$M/map.md.new" "$M/map.md"
out=$(rolling-check-map "$M" 2>&1); assert_status "redir/hash: check-map fails" 1 $?
assert_contains "redir named" "commands.redir ends in an operator" "$out"
assert_contains "hash named" "commands.hash ends in an operator" "$out"
assert_contains "spaced comment named" "commands.spaced ends in an operator" "$out"
cp "$M/map.md" .rolling/map.md
echo "PRECIOUS" > src/victim.txt
write_task "lesson: setup
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: redir src/victim.txt
verify: hash one two
verify: spaced one"
out=$(rolling-check-task 2>&1); assert_status "redir/hash: check-task fails" 1 $?
assert_contains "check-task names the command" "whose command in the map ends in an operator or contains '#'" "$out"
out=$(rolling-verify)
assert_contains "redir: verifier refuses" "REJECTED redir src/victim.txt" "$out"
assert_contains "hash: verifier refuses" "REJECTED hash one two" "$out"
assert_contains "spaced: verifier refuses" "REJECTED spaced one" "$out"
assert_eq "redir: victim untouched" "PRECIOUS" "$(cat src/victim.txt)"
rm -f src/victim.txt; git checkout -q -- .rolling/map.md
task_for "$branch" "$base"; rolling-end-task >/dev/null; rolling-close-task >/dev/null

# --shown may not name a directory holding a held file; held must be a file.
git switch -q main
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh --shown tests 2>&1); assert_status "shown dir over held file refused" 1 $?
assert_contains "shown dir named" "is not a regular file at" "$out"
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests 2>&1); assert_status "held directory refused" 1 $?
assert_contains "held directory named" "is not a regular file at" "$out"
assert_eq "refusals leave HEAD on main" "main" "$(git symbolic-ref --short HEAD)"

# --here takes files, not directories, and copes with a non-ASCII name in the tree.
mkdir -p newdir && echo t > newdir/t.sh && echo notes > newdir/learner-notes.txt
out=$(rolling-begin-task setup --here newdir 2>&1); assert_status "--here directory refused" 1 $?
assert_contains "--here directory named" "never a directory" "$out"
out=$(rolling-begin-task setup --here newdir/t.sh 2>&1); assert_status "--here refuses the sibling note" 1 $?
assert_contains "--here names the sibling" "newdir/learner-notes.txt" "$out"
rm -rf newdir
printf 'x\n' > "src/café.sh"
out=$(rolling-begin-task setup --here "src/café.sh"); assert_status "--here with a non-ASCII name" 0 $?
assert_contains "--here committed it" "café" "$(git -c core.quotePath=false show --stat --format= HEAD)"
git switch -q main; rm -f "src/café.sh"

# --on-base with nothing to run still ends with PROOF: not ok.
rm -f "$LEARNER/task.md"
out=$(rolling-verify --on-base)
assert_contains "on-base without a task: not ok" "PROOF: not ok" "$out"

# A CRLF task.md still takes the session stamp.
write_task "lesson: setup
mode: write
scope: src"
sed 's/$/\r/' "$LEARNER/task.md" > "$LEARNER/task.md.crlf" && mv "$LEARNER/task.md.crlf" "$LEARNER/task.md"
rolling-claim-session crlf-1 >/dev/null
assert_eq "crlf task: stamp recorded" "crlf-1" "$(fm_scalar "$LEARNER/task.md" tutor-session)"
rm -f "$LEARNER/task.md"

# Directories created only for a held file are removed again, innermost first.
git switch -q main
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
mkdir -p "$LEARNER/held/deep/a/b" && cp "$LEARNER/held/tests/greet.test.sh" "$LEARNER/held/deep/a/b/t.sh"
write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
held: deep/a/b/t.sh
held-verify: test deep/a/b/t.sh"
out=$(rolling-verify)
assert_contains "deep held ran" "HELD FAIL(1) test deep/a/b/t.sh" "$out"
assert_no_file "deep dirs removed" deep
rolling-end-task >/dev/null; rolling-close-task >/dev/null

# A record whose set-aside copy is gone says so, and does not block.
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
printf 'aside tests/gone.sh\n' > "$LEARNER/held-aside.pending"
out=$(rolling-diff)
assert_contains "missing aside: reported" "HELD REVERT INCOMPLETE: no set-aside copy of tests/gone.sh" "$out"
assert_no_file "missing aside: record cleared" "$LEARNER/held-aside.pending"
rolling-close-task >/dev/null; git switch -q main

# -------------------------------------------------------------- round three

held_task() {
  # held_task BRANCH BASE HELD-LINES: a task with the given held:/held-verify: lines.
  write_task "lesson: greet-politely
mode: write
branch: $1
base: $2
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
$3"
}

# A symbolic link at the held path, or in its parents, is refused and kept.
git switch -q main
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
mkdir -p tests && printf '#!/bin/sh\necho real\n' > tests/real.sh && ln -s real.sh tests/greet.test.sh
held_task "$branch" "$base" "held: tests/greet.test.sh
held-verify: test tests/greet.test.sh"
out=$(rolling-verify)
assert_contains "symlink held path refused" "HELD REJECTED tests/greet.test.sh   (a symbolic link is in the way" "$out"
assert_eq "symlink kept" "real.sh" "$(readlink tests/greet.test.sh)"
assert_no_file "symlink: no record" "$LEARNER/held-aside.pending"
rm -f tests/greet.test.sh tests/real.sh
mkdir -p "$WORLD/elsewhere" && printf 'outside\n' > "$WORLD/elsewhere/t.sh" && ln -s ../elsewhere linked
mkdir -p "$LEARNER/held/linked" && cp "$LEARNER/held/tests/greet.test.sh" "$LEARNER/held/linked/t.sh"
held_task "$branch" "$base" "held: linked/t.sh
held-verify: test linked/t.sh"
out=$(rolling-verify)
assert_contains "symlinked parent refused" "HELD REJECTED linked/t.sh   (a symbolic link is in the way" "$out"
assert_eq "symlinked parent: nothing written through it" "outside" "$(cat "$WORLD/elsewhere/t.sh")"
rm -rf linked "$WORLD/elsewhere" "$LEARNER/held/linked"

# Two held entries that are one file are refused, whichever way they alias.
mkdir -p tests && printf '#!/bin/sh\necho mine\n' > tests/greet.test.sh
mkdir -p "$LEARNER/held/Tests" && cp "$LEARNER/held/tests/greet.test.sh" "$LEARNER/held/Tests/greet.test.sh"
held_task "$branch" "$base" "held: tests/greet.test.sh
held: Tests/greet.test.sh
held-verify: test tests/greet.test.sh"
out=$(rolling-verify)
if [ -e Tests ] && [ tests -ef Tests ]; then
  assert_contains "case-folded alias refused" "the same file as another held path" "$out"
fi
assert_eq "alias: learner's file intact" "mine" "$(sh tests/greet.test.sh)"
assert_no_file "alias: no record" "$LEARNER/held-aside.pending"
[ "$LEARNER/held/tests" -ef "$LEARNER/held/Tests" ] || rm -rf "$LEARNER/held/Tests"

# Directories created for several held paths all go, deepest first.
mkdir -p "$LEARNER/held/newtop/sub" && cp "$LEARNER/held/tests/greet.test.sh" "$LEARNER/held/newtop/shallow.sh" && cp "$LEARNER/held/tests/greet.test.sh" "$LEARNER/held/newtop/sub/deep.sh"
held_task "$branch" "$base" "held: newtop/shallow.sh
held: newtop/sub/deep.sh
held-verify: test newtop/shallow.sh"
out=$(rolling-verify)
assert_contains "multi-dir: ran" "HELD FAIL(1) test newtop/shallow.sh" "$out"
assert_no_file "multi-dir: all created dirs removed" newtop
rm -rf "$LEARNER/held/newtop"

# SIGTERM during a verify: line still ends with the report lines.
awk '{ print } /^  args: sh args.sh$/ { print "  slow: sleep 5" }' .rolling/map.md > .rolling/map.md.new && mv .rolling/map.md.new .rolling/map.md
write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
verify: slow"
rolling-verify --on-base > "$WORLD/term2.out" 2>&1 &
vpid=$!
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40; do
  grep -q "^PASS     check" "$WORLD/term2.out" 2>/dev/null && break
  sleep 0.1
done
sleep 0.2   # let the slow line start
kill -TERM "$vpid" 2>/dev/null
wait "$vpid" 2>/dev/null
out=$(cat "$WORLD/term2.out")
assert_contains "sigterm in verify: report line" "VERIFIER: interrupted" "$out"
assert_not_contains "sigterm in verify: no held wording without a held test" "HELD interrupted" "$out"
assert_contains "sigterm in verify: proof line" "PROOF: not ok (interrupted)" "$out"
git checkout -q -- .rolling/map.md
task_for "$branch" "$base"; rolling-end-task >/dev/null; rolling-close-task >/dev/null

# A symbolic link in the fix cannot be held or shown.
git switch -q main
ln -s ../src/greet.sh tests/link.test.sh && git add tests/link.test.sh && git commit -q -m "link"
LINKFIX=$(git rev-parse HEAD)
out=$(rolling-begin-task greet-politely --fix "$LINKFIX" --held tests/link.test.sh 2>&1); assert_status "symlink in fix refused" 1 $?
assert_contains "symlink in fix named" "is not a regular file at" "$out"
git reset -q --hard "$FIX"

# --------------------------------------------------------------- round five

# begin-task refuses the same path twice, whichever flags carry it.
git switch -q main
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh --shown tests/greet.test.sh 2>&1); assert_status "held+shown same path refused" 1 $?
assert_contains "held+shown named" "is listed twice" "$out"
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh --held tests/greet.test.sh 2>&1); assert_status "held twice refused" 1 $?
assert_eq "dup refusals leave HEAD on main" "main" "$(git symbolic-ref --short HEAD)"

# A held path that begins with a dash is handled, not passed to dirname as a flag.
printf 'x\n' > -dash.sh && git add -- -dash.sh && git commit -q -m "dash"
mkdir -p -- -dashdir && printf 'y\n' > -dashdir/t.sh && git add -- -dashdir && git commit -q -m "dashdir"
DASHFIX=$(git rev-parse HEAD)
out=$(rolling-begin-task greet-politely --fix "$DASHFIX" --held -dashdir/t.sh); assert_status "dash-leading held path" 0 $?
assert_file "dash: held copy written" "$LEARNER/held/-dashdir/t.sh"
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
held_task "$branch" "$base" "held: -dashdir/t.sh
held-verify: test -dashdir/t.sh"
out=$(rolling-verify)
assert_not_contains "dash: no raw dirname error" "dirname: invalid option" "$out"
assert_contains "dash: held line ran" "HELD FAIL" "$out"
rolling-end-task >/dev/null; rolling-close-task >/dev/null
git reset -q --hard "$FIX"

# Two held paths that are one file through a hard link are refused.
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
mkdir -p tests && printf '#!/bin/sh\necho mine\n' > tests/greet.test.sh && ln tests/greet.test.sh tests/hard.test.sh
mkdir -p "$LEARNER/held/tests" && cp "$LEARNER/held/tests/greet.test.sh" "$LEARNER/held/tests/hard.test.sh"
held_task "$branch" "$base" "held: tests/greet.test.sh
held: tests/hard.test.sh
held-verify: test tests/greet.test.sh"
# The first apply replaces greet.test.sh with a new file, so the hard link
# no longer aliases it; what matters is that both of the learner's files
# come back and the held test is nowhere.
out=$(rolling-verify)
assert_eq "hard link: learner's file intact" "mine" "$(sh tests/greet.test.sh)"
assert_eq "hard link: the linked file intact" "mine" "$(sh tests/hard.test.sh)"
assert_no_file "hard link: no record left" "$LEARNER/held-aside.pending"
rm -f tests/hard.test.sh
task_for "$branch" "$base"; rolling-end-task >/dev/null; rolling-close-task >/dev/null

# A set-aside copy that vanished mid-run is an incomplete revert: reported,
# not claimed as clean, and it fails the proof.
git switch -q main
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
awk -v d="$LEARNER/held-aside" '{ print } /^  args: sh args.sh$/ { print "  vanish: rm -rf " d }' .rolling/map.md > .rolling/map.md.new && mv .rolling/map.md.new .rolling/map.md
mkdir -p tests && printf '#!/bin/sh\necho mine\n' > tests/greet.test.sh
held_task "$branch" "$base" "held: tests/greet.test.sh
held-verify: vanish
held-verify: test tests/greet.test.sh
expect-fail-on-base: held-verify test tests/greet.test.sh"
out=$(rolling-verify --on-base)
assert_contains "vanished aside: reported" "HELD REVERT INCOMPLETE" "$out"
assert_contains "vanished aside: summary" "REVERT INCOMPLETE" "$out"
assert_not_contains "vanished aside: not claimed clean" ", reverted" "$out"
assert_contains "vanished aside: proof not ok" "PROOF: not ok" "$out"
assert_no_file "vanished aside: record cleared (nothing to retry)" "$LEARNER/held-aside.pending"
git checkout -q -- .rolling/map.md
task_for "$branch" "$base"; rolling-end-task >/dev/null; rolling-close-task >/dev/null

finish
