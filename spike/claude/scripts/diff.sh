#!/bin/sh
# Show what the learner changed: the working tree against the open task's
# base commit, uncommitted and unstaged included. Nothing has to be
# committed or staged for the tutor to see the work.
#
# `base:` comes from .rolling/profile/task.md and must be a commit sha (7
# to 40 hex characters), not a ref: a moving base like HEAD would make the
# diff empty the moment anything is committed. Untracked files are listed
# and shown too, since a new test file is exactly the kind of change a
# task asks for. The .rolling/ and .claude/ directories are excluded: the
# first is the profile, the second is the tutor's own installed files.
#
# Output is capped so a stray binary or a huge file cannot swamp the
# transcript. Always exits 0: it runs as an inline command in the `done`
# skill, and a non-zero exit there aborts the skill. Problems are reported
# in the text.
set -u
cap=${ROLLING_DIFF_MAX_LINES:-3000}
root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "DIFF: not captured (not a git repository)"; exit 0; }
task="$root/.rolling/profile/task.md"
[ -f "$task" ] || { echo "DIFF: not captured (no open task: $task is missing)"; exit 0; }
base=$(sed -n 's/^base: *//p' "$task" | head -n 1 | sed 's/[[:space:]].*$//')
case "$base" in
  "") echo "DIFF: not captured (the open task has no base: line)"; exit 0 ;;
  *[!0-9a-f]*) echo "DIFF: not captured (base '$base' is not a commit sha; use the full sha, not a ref)"; exit 0 ;;
esac
[ ${#base} -ge 7 ] || { echo "DIFF: not captured (base '$base' is too short to be a sha)"; exit 0; }
git -C "$root" cat-file -e "$base^{commit}" 2>/dev/null || { echo "DIFF: not captured (base $base is not a commit here)"; exit 0; }

cd "$root" || { echo "DIFF: not captured (cannot enter $root)"; exit 0; }
g() { git --no-pager -c color.ui=false -c core.quotePath=false "$@"; }
ex='.rolling'; ex2='.claude'

{
  echo "## Base: $base ($(g log -1 --format=%s "$base"))"
  head=$(git rev-parse HEAD)
  if [ "$head" = "$(git rev-parse "$base")" ]; then echo "## HEAD: $(git rev-parse --short HEAD)"
  else echo "## HEAD: $(git rev-parse --short HEAD)  (note: HEAD has moved since the task began)"; fi
  echo
  echo "## Changed files"
  g diff --stat "$base" -- . ":(exclude)$ex" ":(exclude)$ex2" | sed 's/^/  /'
  echo "## New files (untracked)"
  g ls-files --others --exclude-standard -- . ":(exclude)$ex" ":(exclude)$ex2" | sed 's/^/  /'
  echo
  echo "## Diff"
  g diff "$base" -- . ":(exclude)$ex" ":(exclude)$ex2"
  g ls-files -z --others --exclude-standard -- . ":(exclude)$ex" ":(exclude)$ex2" |
    tr '\0' '\n' | while IFS= read -r f; do
      [ -n "$f" ] || continue
      # --no-index exits 1 when the files differ, which they always do here.
      g diff --no-index --no-prefix -- /dev/null "$f" 2>&1 || true
    done
} > "$root/.rolling/profile/.diff.tmp" 2>&1

lines=$(wc -l < "$root/.rolling/profile/.diff.tmp")
if [ "$lines" -gt "$cap" ]; then
  head -n "$cap" "$root/.rolling/profile/.diff.tmp"
  echo
  echo "DIFF: truncated at $cap of $lines lines (set ROLLING_DIFF_MAX_LINES to raise)"
else
  cat "$root/.rolling/profile/.diff.tmp"
fi
rm -f "$root/.rolling/profile/.diff.tmp"
exit 0
