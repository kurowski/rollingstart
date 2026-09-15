#!/usr/bin/env bash
# rolling-check-map, rolling-check-profile, rolling-check-task: the
# scratch map is clean; each listed fault is caught; faults are counted.
. "$(dirname "$0")/lib.sh"
scratch_world

out=$(rolling-check-map); assert_status "scratch map is clean" 0 $?
assert_contains "check-map summary" "map ok" "$out"
assert_contains "check-map counts" "2 lessons, 2 regions, 1 courses" "$out"
out=$(rolling-check-map "$REPO/.rolling"); assert_status "explicit directory" 0 $?

# Map faults, one at a time on a copy.
M="$WORLD/m"; reset_map() { rm -rf "$M"; cp -R "$REPO/.rolling" "$M"; }
faulty() { reset_map; eval "$1"; out=$(rolling-check-map "$M" 2>&1); rc=$?; assert_status "$2 (fails)" 1 $rc; assert_contains "$2" "$3" "$out"; }
faulty "sedi 's/^mode: write/mode: maybe/' \"\$M/map.md\"" "bad mode" "mode 'maybe' is not write or direct"
faulty "sedi '/^name:/d' \"\$M/map.md\"" "missing name" "name is missing"
faulty "sedi 's/^commands:/commandz:/' \"\$M/map.md\"" "unknown field" "unknown field 'commandz'"
faulty "sedi 's/^  - reset/  - drop/' \"\$M/map.md\"" "destructive names a non-operation" "destructive names 'drop'"
faulty "sedi 's/^## Regions/## Places/' \"\$M/map.md\"" "no regions" "no ## Regions heading"
faulty "sedi 's/^### Generalist/#### Generalist/' \"\$M/map.md\"" "no course heading" "no ### course heading"
faulty "sedi 's/^region: greeting/region: greetings/' \"\$M/lessons/greet-politely.md\"" "lesson region unknown" "region 'greetings' is not in the map"
faulty "sedi 's/^depth: working/depth: expert/' \"\$M/lessons/greet-politely.md\"" "lesson depth" "depth 'expert' is not"
faulty "sedi 's/^requires: \[setup\]/requires: [setup, ghost]/' \"\$M/lessons/greet-politely.md\"" "requires unknown" "requires 'ghost', which is not a lesson"
faulty "sedi 's/^requires: \[\]/requires: [greet-politely]/' \"\$M/lessons/setup.md\"" "cycle" "requires has a cycle"
faulty "sedi 's/^## Rubric/## Rubrik/' \"\$M/lessons/setup.md\"" "no rubric" "no ## Rubric heading"
faulty "cp \"\$M/lessons/setup.md\" \"\$M/lessons/Setup-Two.md\"" "bad slug" "'Setup-Two' is not a slug"
faulty "mkdir -p \"\$M/lessons/drafts\"" "stray directory" "must match a lesson file beside it"
faulty "sedi 's/^test: shown/test: given/' \"\$M/lessons/setup.md\"" "bad test" "test 'given' is not held or shown"
faulty "sedi 's/^title:/titel:/' \"\$M/lessons/setup.md\"" "lesson unknown field and missing title" "unknown field 'titel'"

# A hand-written task under a lesson.
reset_map; mkdir -p "$M/lessons/greet-politely"
cat > "$M/lessons/greet-politely/be-polite.md" <<'EOF'
---
mode: write
scope: src/greet.sh
verify: check
held: tests/greet.test.sh
held-verify: test tests/greet.test.sh
fix: 0123456
---

## Brief

Be polite.

## Source

The fix.
EOF
out=$(rolling-check-map "$M"); assert_status "task file clean" 0 $?
reset_map; mkdir -p "$M/lessons/greet-politely"; printf -- '---\nverify: nope\n---\n## Brief\n## Source\n' > "$M/lessons/greet-politely/bad.md"
out=$(rolling-check-map "$M" 2>&1); assert_status "task names unknown command (fails)" 1 $?
assert_contains "task names unknown command" "names 'nope', which is not a command" "$out"
reset_map; mkdir -p "$M/lessons/greet-politely"; printf -- '---\nverify: check\nfix: xyz\n---\n## Source\n' > "$M/lessons/greet-politely/t.md"
out=$(rolling-check-map "$M" 2>&1); assert_status "task file faults" 1 $?
assert_contains "task fix hex" "fix 'xyz' is not 7 to 40 hex" "$out"
assert_contains "task brief" "no ## Brief or ## Situation" "$out"
assert_contains "fault count" "2 fault(s)" "$out"

# check-profile
out=$(rolling-check-profile 2>&1); assert_status "no profile" 1 $?
mkdir -p "$LEARNER"
cat > "$LEARNER/profile.md" <<'EOF'
# Profile

## Background
Knows sh.

## Destination
greeting: working
platform: orientation

## Why
Because.

## Satisfied
- setup (2026-09-15)
EOF
out=$(rolling-check-profile); assert_status "profile clean" 0 $?
sedi 's/^greeting: working/greeting: expert/' "$LEARNER/profile.md"
out=$(rolling-check-profile 2>&1); assert_status "bad depth" 1 $?; assert_contains "bad depth named" "destination line is not" "$out"
sedi 's/^greeting: expert/nowhere: working/' "$LEARNER/profile.md"
out=$(rolling-check-profile 2>&1); assert_status "unknown region is a warning" 0 $?; assert_contains "warning text" "warning: destination region 'nowhere'" "$out"
sedi 's/^- setup (2026-09-15)/- setup (yesterday)/' "$LEARNER/profile.md"
out=$(rolling-check-profile 2>&1); assert_status "bad satisfied" 1 $?; assert_contains "bad satisfied named" "satisfied line is not" "$out"
sedi 's/^## Why/## Reasons/' "$LEARNER/profile.md"
out=$(rolling-check-profile 2>&1); assert_contains "heading order" "headings must be exactly" "$out"

# check-task
rm -f "$LEARNER/task.md"
out=$(rolling-check-task 2>&1); assert_status "no task" 1 $?
mkdir -p "$LEARNER/held/tests" && cp "$REPO/tests/greet.test.sh" "$LEARNER/held/tests/"
write_task "lesson: greet-politely
mode: write
branch: rolling/x
base: $FIX
return-to: main $PRE
started: 2026-09-15
tutor-session: s1
fix: $FIX
scope: src/greet.sh
scope: tests
scaffold: tests/greet.test.sh
setup: seed
verify: check
held: tests/greet.test.sh
held-verify: test tests/greet.test.sh
expect-fail-on-base: held-verify test tests/greet.test.sh"
out=$(rolling-check-task 2>&1); assert_status "task clean" 0 $?
assert_contains "task ok" "task ok" "$out"
t() { write_task "$1" "${2:-}"; out=$(rolling-check-task 2>&1); rc=$?; assert_status "$3 (fails)" 1 $rc; assert_contains "$3" "$4" "$out"; }
t "lesson: greet-politely
mode: write
branch: b
base: $FIX
return-to: main $PRE
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
scaffold: docs/x.md" "" "scaffold outside scope" "scaffold 'docs/x.md' is not inside any scope"
t "lesson: greet-politely
mode: write
branch: b
base: $FIX
return-to: main $PRE
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
expect-fail-on-base: verify test x" "" "expect-fail must repeat a line" "does not repeat a verify: line verbatim"
t "lesson: greet-politely
mode: write
branch: b
base: $FIX
return-to: main $PRE
started: 2026-09-15
tutor-session: s1
scope: src
verify: check
held: tests/other.sh" "" "held without a copy" "held 'tests/other.sh' has no file under held/"
t "lesson: greet-politely
mode: direct
branch: b
base: $FIX
return-to: main $PRE
started: 2026-09-15
tutor-session: s1
scope: src
verify: check" "" "direct needs a situation" "a direct task needs a ## Situation heading"
t "lesson: greet-politely
mode: write
branch: b
base: $FIX
return-to: main $PRE
started: 2026-09-15
tutor-session: s1
task: nothing
scope: src
verify: check" "" "task names a missing author task" "task 'nothing' is not a task of lesson"
t "lesson: greet-politely
mode: write
base: $FIX
return-to: main $PRE
started: 2026-09-15
scope: src
verify: check \$(rm -rf /)
bogus: 1" "" "missing fields, bad args, unknown field" "verify line 'check \$(rm -rf /)' carries a shell metacharacter"
assert_contains "missing branch named" "branch is missing" "$out"
assert_contains "unknown field named" "unknown field 'bogus'" "$out"
t "lesson: greet-politely
mode: write
branch: b
base: notasha
return-to: main $PRE
started: 15/09/2026
tutor-session: s1
scope: src
verify: check" "" "bad base and date" "base 'notasha' is not 7 to 40 hex"
assert_contains "bad date named" "started '15/09/2026' is not YYYY-MM-DD" "$out"

# close-task removes exactly the task's files.
mkdir -p "$LEARNER/evidence" && echo e > "$LEARNER/evidence/setup.md" && echo r > "$LEARNER/reference.md"
out=$(rolling-close-task); assert_status "close" 0 $?
assert_no_file "task removed" "$LEARNER/task.md"
assert_no_file "reference removed" "$LEARNER/reference.md"
assert_no_file "held removed" "$LEARNER/held"
assert_file "profile kept" "$LEARNER/profile.md"
assert_file "evidence kept" "$LEARNER/evidence/setup.md"
assert_contains "close reports" "task closed" "$out"

# export copies the directory and refuses to overwrite.
out=$(rolling-export "$WORLD/out"); assert_status "export" 0 $?
assert_file "exported profile" "$WORLD/out/profile.md"
assert_contains "export lists files" "profile.md" "$out"
out=$(rolling-export "$WORLD/out" 2>&1); assert_status "export refuses overwrite" 1 $?
assert_contains "export refusal named" "refusing to overwrite" "$out"
out=$(rolling-export 2>&1); assert_status "export usage" 2 $?
finish
