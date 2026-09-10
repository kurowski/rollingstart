#!/bin/sh
# Run the open task's verifier and report, one line per command.
#
# The verifier is structured, never shell: each `verify:` line in the
# frontmatter of .rolling/profile/task.md names a command key declared
# under `commands:` in .rolling/map.md, optionally followed by arguments.
# This script resolves the key and runs the declared command with the
# arguments as separate words. A key the map does not declare is reported,
# not run. Arguments are plain words: anything that would mean something
# to a shell ($ ` ; & | < > ( ) { } \ quotes, and the globs * ? [) is
# rejected, because task.md is written by the model and the arguments
# must not become a way to run shell after all. A map command line may
# not carry a trailing `# comment`; it is stripped here, so it cannot
# swallow the arguments, but keep the map clean anyway.
#
# Output: PASS/FAIL per command, the tail of each failure, and a summary
# line. The exit status is always 0 once the report is printed: this runs
# as an inline command inside the `done` skill, and a non-zero exit there
# aborts the skill, which is the opposite of what a failing verifier needs.
# The result is the VERIFIER: line, not the status.
#
# Keep a task's verifier short: it runs inline, before the model's turn,
# under whatever timeout inline commands have (measure it; see NOTES.md).
# Scope test commands to a workspace and a file rather than a whole suite.
set -u
root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "VERIFIER: not run (not a git repository)"; exit 0; }
task="$root/.rolling/profile/task.md"
map="$root/.rolling/map.md"
[ -f "$task" ] || { echo "VERIFIER: not run (no open task: $task is missing)"; exit 0; }
[ -f "$map" ]  || { echo "VERIFIER: not run (no map: $map is missing)"; exit 0; }

# command_for KEY: the command declared for KEY in the map's frontmatter.
command_for() {
  awk -v want="$1" '
    /^---$/ { fence++; next }
    fence != 1 { next }
    /^commands:/ { inblock = 1; next }
    inblock && /^[^ ]/ { inblock = 0 }
    inblock && /^  [A-Za-z0-9_-]+:/ {
      key = $1; sub(/:$/, "", key)
      if (key == want) { sub(/^  [A-Za-z0-9_-]+: */, ""); sub(/[ \t]+#.*$/, ""); print; exit }
    }' "$map"
}

# verify_lines: the `verify:` lines from the task's frontmatter only.
# A trailing `# comment` on the line is dropped, and a line left empty
# by that is dropped too, so a commented-out verifier is not a verifier.
verify_lines() {
  awk '/^---$/ { fence++; next }
       fence == 1 && /^verify:/ { sub(/^verify: */, ""); sub(/[ \t]+#.*$/, ""); sub(/^#.*$/, ""); if ($0 != "") print }' "$task"
}

tmp=$(mktemp -d) || { echo "VERIFIER: not run (mktemp failed)"; exit 0; }
trap 'rm -rf "$tmp"' EXIT INT TERM
verify_lines > "$tmp/lines"
[ -s "$tmp/lines" ] || { echo "VERIFIER: not run (the open task declares no verify: lines in its frontmatter)"; exit 0; }
: > "$tmp/results"

while IFS= read -r line; do
  key=${line%% *}
  args=""; [ "$line" != "$key" ] && args=${line#* }
  label="$key"; [ -n "$args" ] && label="$key $args"
  cmd=$(command_for "$key")
  if [ -z "$cmd" ]; then
    echo "UNKNOWN  $label   (no such command in .rolling/map.md)"
    echo u >> "$tmp/results"; continue
  fi
  case "$args" in
    *[\$\`\;\&\|\<\>\(\)\{\}\\\"\'\*\?\[]*)
      echo "REJECTED $label   (arguments may not contain shell metacharacters)"
      echo u >> "$tmp/results"; continue ;;
  esac
  # $args is split on whitespace into words, deliberately; the map's own
  # command string is the one thing here that is trusted as shell.
  # shellcheck disable=SC2086
  out=$(cd "$root" && sh -c "$cmd \"\$@\"" verifier $args </dev/null 2>&1); rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "PASS     $label   ($cmd)"
    echo p >> "$tmp/results"
  else
    echo "FAIL($rc) $label   ($cmd)"
    if [ -n "$out" ]; then printf '%s\n' "$out" | tail -n 40 | sed 's/^/    | /'; else echo "    | (no output)"; fi
    echo f >> "$tmp/results"
  fi
done < "$tmp/lines"

pass=$(grep -c '^p$' "$tmp/results"); fail=$(grep -c '^f$' "$tmp/results"); unknown=$(grep -c '^u$' "$tmp/results")
echo "VERIFIER: $pass passed, $fail failed, $unknown unknown or rejected"
exit 0
