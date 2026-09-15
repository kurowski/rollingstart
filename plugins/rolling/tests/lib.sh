# shellcheck shell=bash
# Sourced by every test. Builds a scratch repository with a small map and
# a fix in its history, points ROLLING_DATA at a scratch data directory,
# and offers a few assertions. Nothing here touches a real checkout or a
# real data directory: every path is under one temporary directory that
# is removed when the test exits.

set -u
TESTS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BIN="$TESTS_DIR/../bin"
export PATH="$BIN:$PATH"
# shellcheck source=../lib/common.sh
. "$TESTS_DIR/../lib/common.sh"

failures=0
checks=0

# assert_eq WHAT EXPECTED ACTUAL
assert_eq() {
  checks=$((checks + 1))
  if [ "$2" = "$3" ]; then return 0; fi
  echo "  FAIL: $1"; echo "    expected: $2"; echo "    actual:   $3"; failures=$((failures + 1))
}

# assert_contains WHAT NEEDLE HAYSTACK
assert_contains() {
  checks=$((checks + 1))
  case $3 in *"$2"*) return 0 ;; esac
  echo "  FAIL: $1"; echo "    expected to contain: $2"; echo "    in:"; printf '%s\n' "$3" | sed 's/^/      /'; failures=$((failures + 1))
}

# assert_not_contains WHAT NEEDLE HAYSTACK
assert_not_contains() {
  checks=$((checks + 1))
  case $3 in *"$2"*) echo "  FAIL: $1"; echo "    expected NOT to contain: $2"; failures=$((failures + 1)); return 0 ;; esac
}

# assert_status WHAT EXPECTED ACTUAL
assert_status() { assert_eq "$1 (exit status)" "$2" "$3"; }

# assert_file WHAT PATH   /  assert_no_file WHAT PATH
assert_file() { checks=$((checks + 1)); [ -e "$2" ] || { echo "  FAIL: $1: $2 does not exist"; failures=$((failures + 1)); }; }
assert_no_file() { checks=$((checks + 1)); [ ! -e "$2" ] || { echo "  FAIL: $1: $2 exists"; failures=$((failures + 1)); }; }

# The scratch world. After scratch_world: $WORLD (temp root), $REPO (a git
# repository with a map), $ROLLING_DATA, $LEARNER (the learner's
# directory for $REPO), $FIX (the sha of the fix commit), $PRE (its parent).
scratch_world() {
  WORLD=$(mktemp -d "${TMPDIR:-/tmp}/rolling-test.XXXXXX") || exit 1
  [ -n "$WORLD" ] && [ -d "$WORLD" ] || { echo "no scratch world"; exit 1; }
  trap 'chmod -R u+w "$WORLD" 2>/dev/null; rm -rf "$WORLD"' EXIT
  export ROLLING_DATA="$WORLD/data"
  REPO="$WORLD/repo"
  mkdir -p "$REPO" && cd "$REPO" || exit 1
  git init -q -b main
  # git reports the physical path (on macOS the temp dir is under a
  # symlink, /var -> /private/var); use the same spelling everywhere.
  REPO=$(git rev-parse --show-toplevel) && cd "$REPO" || exit 1
  git config user.email test@example.com
  git config user.name Test
  git config commit.gpgsign false

  # The "code": a script with a bug, and a test runner the map declares.
  mkdir -p src tests
  cat > src/greet.sh <<'EOF'
#!/bin/sh
# greet NAME: prints a greeting. Bug: shouts.
printf 'HELLO %s\n' "$1"
EOF
  cat > run-test.sh <<'EOF'
#!/bin/sh
# run-test.sh <test file>: runs one test file with sh. The map's `test`.
[ -n "$1" ] || { echo "usage: run-test.sh <file>"; exit 2; }
sh "$1"
EOF
  cat > check.sh <<'EOF'
#!/bin/sh
# The map's `check`: passes when every src file starts with a shebang.
for f in src/*; do head -n 1 "$f" | grep -q '^#!' || { echo "$f: no shebang"; exit 1; }; done
echo ok
EOF
  cat > args.sh <<'EOF'
#!/bin/sh
# The map's `args`: prints its arguments one per line, for argument tests.
for a in "$@"; do printf '[%s]\n' "$a"; done
EOF
  mkdir -p .rolling/lessons
  cat > .rolling/map.md <<'EOF'
---
name: Scratch
mode: write
commands:
  check: sh check.sh
  test: sh run-test.sh
  args: sh args.sh
  fails: sh -c 'exit 3'
operations:
  seed: sh -c 'echo seeded'
  reset: sh -c 'echo reset'
destructive:
  - reset
---

# Scratch

A scratch repository for the toolkit's tests.

## Regions

- **greeting** — the greeting script in `src/`.
- **platform** — the test runner and the checks.

## Suggested courses

### Generalist

1. platform, orientation: setup
2. greeting, working: greet-politely

## Corpus

- `src/greet.sh` is the whole product.

## Mistakes agents make here

- Shouting.
EOF
  cat > .rolling/lessons/setup.md <<'EOF'
---
title: Setup
region: platform
depth: orientation
requires: []
assumes: [sh]
test: shown
---

Get the checks green.

## Rubric

- `check` passes.
EOF
  cat > .rolling/lessons/greet-politely.md <<'EOF'
---
title: Greet politely
region: greeting
depth: working
requires: [setup]
assumes: [sh]
---

Make the greeting polite.

## Rubric

- The greeting is not shouted.
- A test proves it.
EOF
  git add -A && git commit -q -m "initial"
  PRE=$(git rev-parse HEAD)

  # The fix: lower the greeting, with the test that proves it.
  cat > src/greet.sh <<'EOF'
#!/bin/sh
# greet NAME: prints a greeting.
printf 'Hello %s\n' "$1"
EOF
  cat > tests/greet.test.sh <<'EOF'
#!/bin/sh
out=$(sh src/greet.sh pat)
[ "$out" = "Hello pat" ] || { echo "expected 'Hello pat', got '$out'"; exit 1; }
echo "greet: ok"
EOF
  git add -A && git commit -q -m "fix: greet politely"
  FIX=$(git rev-parse HEAD)
  LEARNER=$(rolling-show state-dir)
  export WORLD REPO LEARNER FIX PRE
}

# write_task: a task.md in the learner's directory with the given extra
# frontmatter lines ($1) and body ($2, defaults to a brief and a source).
write_task() {
  mkdir -p "$LEARNER"
  {
    echo "---"
    printf '%s\n' "$1"
    echo "---"
    echo
    if [ -n "${2:-}" ]; then printf '%s\n' "$2"; else printf '## Brief\n\nDo the thing.\n\n## Source\n\nThe fix.\n'; fi
  } > "$LEARNER/task.md"
}

finish() {
  if [ "$failures" -eq 0 ]; then echo "ok: $checks checks"; exit 0; fi
  echo "FAILED: $failures of $checks checks"; exit 1
}

# sedi EXPR FILE: in-place sed without -i, which differs between GNU and
# BSD sed and leaves backup files behind on one of them.
sedi() { sed "$1" "$2" > "$2.sedi" && mv "$2.sedi" "$2"; }
