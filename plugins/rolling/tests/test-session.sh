#!/usr/bin/env bash
# rolling-claim-session and rolling-session-start.
. "$(dirname "$0")/lib.sh"
scratch_world

out=$(rolling-claim-session abc-123); assert_status "claim without task" 0 $?
assert_contains "no task: says so" "no task open" "$out"
assert_eq "no task: session file" "abc-123" "$(cat "$LEARNER/session")"

write_task "lesson: setup
mode: write
scope: src"
out=$(rolling-claim-session def-456); assert_status "claim with task" 0 $?
assert_contains "task: says so" "recorded in the open task" "$out"
assert_eq "task: line added before the closing fence" "def-456" "$(fm_scalar "$LEARNER/task.md" tutor-session)"
assert_eq "task: other fields intact" "setup" "$(fm_scalar "$LEARNER/task.md" lesson)"
assert_contains "task: body intact" "## Brief" "$(cat "$LEARNER/task.md")"
rolling-claim-session ghi-789 >/dev/null
assert_eq "task: line replaced, not duplicated" "1" "$(grep -c '^tutor-session:' "$LEARNER/task.md")"
assert_eq "task: new value" "ghi-789" "$(fm_scalar "$LEARNER/task.md" tutor-session)"
assert_contains "bad id rejected" "not recorded" "$(rolling-claim-session 'x; rm')"
assert_contains "empty id rejected" "not recorded" "$(rolling-claim-session '')"
out=$(ROLLING_DATA='' rolling-claim-session abc); assert_status "unset data exits 0" 0 $?
assert_contains "unset data says so" "ROLLING_DATA" "$out"

# session-start: appends an export to CLAUDE_ENV_FILE, exits 0 always.
envf="$WORLD/env.sh"; : > "$envf"
CLAUDE_ENV_FILE="$envf" rolling-session-start "/some/data dir" </dev/null; assert_status "session-start" 0 $?
assert_eq "session-start wrote an export" "export ROLLING_DATA=/some/data\\ dir" "$(cat "$envf")"
# shellcheck disable=SC1090
( . "$envf"; assert_eq "the export sources back" "/some/data dir" "$ROLLING_DATA" )
CLAUDE_ENV_FILE='' rolling-session-start /x </dev/null; assert_status "session-start without env file" 0 $?
CLAUDE_ENV_FILE="$envf" rolling-session-start "" </dev/null; assert_status "session-start without data" 0 $?
assert_eq "nothing written for empty data" 1 "$(wc -l < "$envf" | tr -d ' ')"
finish
