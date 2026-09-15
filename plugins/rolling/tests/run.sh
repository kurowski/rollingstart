#!/usr/bin/env bash
# Run every test-*.sh beside this file, each in its own process, and exit
# non-zero if any failed. A test builds its own scratch world and never
# touches a real checkout or data directory.
set -u
here=$(cd "$(dirname "$0")" && pwd)
failed=0; ran=0
for t in "$here"/test-*.sh; do
  [ -f "$t" ] || continue
  ran=$((ran + 1))
  name=$(basename "$t" .sh)
  if out=$(bash "$t" 2>&1); then
    echo "PASS $name: $(printf '%s\n' "$out" | tail -n 1)"
  else
    echo "FAIL $name"; printf '%s\n' "$out" | sed 's/^/     /'
    failed=$((failed + 1))
  fi
done
echo "$ran test files, $failed failed"
[ "$failed" -eq 0 ]
