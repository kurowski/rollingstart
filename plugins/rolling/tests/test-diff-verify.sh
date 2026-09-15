#!/usr/bin/env bash
# rolling-diff, rolling-verify, rolling-report: the change, the verifier,
# the held test applied and reverted, the both-ways proof, argument
# safety, and the whole loop leaving the tree as the learner left it.
. "$(dirname "$0")/lib.sh"
scratch_world

assert_contains "diff without task" "no open task" "$(rolling-diff)"
assert_contains "verify without task" "no open task" "$(rolling-verify)"

# A task from the fix, test held. begin-task also writes task.md's inputs.
out=$(rolling-begin-task greet-politely --fix "$FIX" --held tests/greet.test.sh)
branch=$(printf '%s\n' "$out" | sed -n 's/^branch: //p'); base=$(printf '%s\n' "$out" | sed -n 's/^base: //p')
write_task "lesson: greet-politely
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
fix: $FIX
scope: src/greet.sh
scope: tests
verify: check
held: tests/greet.test.sh
held-verify: test tests/greet.test.sh
expect-fail-on-base: held-verify test tests/greet.test.sh"

# The proof on the starting state: check passes, the held test must fail.
out=$(rolling-verify --on-base); assert_status "verify --on-base" 0 $?
assert_contains "on-base: check passes" "PASS     check" "$out"
assert_contains "on-base: held expected to fail" "HELD EXPECTED-FAIL(1) test tests/greet.test.sh" "$out"
assert_contains "on-base: proof ok" "PROOF: ok" "$out"
assert_no_file "held test reverted after proof" tests/greet.test.sh
assert_eq "tree clean after proof" "" "$(git status --porcelain)"

# Before any work: plain verify shows the held test failing.
out=$(rolling-verify)
assert_contains "held fails before the work" "HELD FAIL(1) test tests/greet.test.sh" "$out"
assert_contains "held failure shows output" "| expected 'Hello pat', got 'HELLO pat'" "$out"
assert_contains "summary with held" "VERIFIER: 1 passed, 0 failed, 0 unknown or rejected; held: 0 passed, 1 failed" "$out"

# The learner's work: the fix by a different route, plus their own test at
# the held path (which must be set aside and restored, never lost).
sedi 's/HELLO/Hello/' src/greet.sh
mkdir -p tests && printf '#!/bin/sh\necho "my own test"\n' > tests/greet.test.sh
echo "note" > tests/notes.txt
out=$(rolling-report); assert_status "report" 0 $?
assert_contains "report: diff heading first" "## The change" "$out"
assert_contains "report: diff shows the change" "-printf 'HELLO %s\\n' \"\$1\"" "$out"
assert_contains "report: diff shows the learner's own test" "+echo \"my own test\"" "$out"
assert_contains "report: diff lists untracked" "tests/notes.txt" "$out"
assert_not_contains "report: held test not in diff" "expected 'Hello pat'" "$out"
assert_contains "report: verifier after diff" "## Verifier" "$out"
assert_contains "report: held passes now" "HELD PASS     test tests/greet.test.sh" "$out"
assert_contains "report: summary" "held: 1 passed, 0 failed" "$out"
assert_eq "learner's own test restored" "my own test" "$(sh tests/greet.test.sh)"
assert_eq "no stray files" "" "$(git status --porcelain -uall | grep -v 'src/greet.sh\|tests/greet.test.sh\|tests/notes.txt' || true)"
d=$(printf '%s\n' "$out" | awk '/^## The change/{a=1} /^## Verifier/{a=0} a' )
v=$(printf '%s\n' "$out" | awk '/^## Verifier/{a=1} a')
assert_contains "diff section precedes verifier" "## Base:" "$d"
assert_contains "verifier section has the summary" "VERIFIER:" "$v"

# Argument handling: words, never shell.
write_task "lesson: setup
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: args one two
verify: args a;b
verify: args *.sh
verify: nope x
verify: fails"
out=$(rolling-verify)
assert_contains "args passed as words" "PASS     args one two" "$out"
assert_contains "metachar rejected" "REJECTED args a;b" "$out"
assert_contains "glob rejected" "REJECTED args *.sh" "$out"
assert_contains "unknown key" "UNKNOWN  nope x" "$out"
assert_contains "failure status" "FAIL(3) fails" "$out"
assert_contains "summary counts" "VERIFIER: 1 passed, 1 failed, 3 unknown or rejected" "$out"
# The words really arrive as separate arguments.
write_task "lesson: setup
mode: write
branch: $branch
base: $base
return-to: main $FIX
started: 2026-09-15
tutor-session: s1
scope: src
verify: args one two"
out=$(cd "$REPO" && bash -c 'sh args.sh "$@"' x one two)
assert_eq "args.sh sanity" "[one]
[two]" "$out"

# Diff fails safe on a bad base.
write_task "lesson: setup
mode: write
base: main
scope: src
verify: check"
assert_contains "diff: base must be a sha" "not a commit sha" "$(rolling-diff)"
write_task "lesson: setup
mode: write
base: 0123456789abcdef0123456789abcdef01234567
scope: src
verify: check"
assert_contains "diff: base must exist" "not a commit in this repository" "$(rolling-diff)"

# Diff is capped.
write_task "lesson: setup
mode: write
base: $base
scope: src
verify: check"
seq 1 500 > src/big.txt
out=$(ROLLING_DIFF_MAX_LINES=50 rolling-diff)
assert_contains "diff capped" "DIFF: truncated at 50 of" "$out"
rm -f src/big.txt

# Held: a missing held copy is reported, nothing applied, nothing lost.
write_task "lesson: setup
mode: write
base: $base
scope: src
verify: check
held: tests/absent.test.sh
held-verify: test tests/absent.test.sh"
out=$(rolling-verify)
assert_contains "missing held copy" "HELD MISSING tests/absent.test.sh" "$out"
assert_contains "held not run" "HELD not run" "$out"
assert_no_file "nothing applied" tests/absent.test.sh
finish
