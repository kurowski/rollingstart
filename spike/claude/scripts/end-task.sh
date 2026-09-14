#!/bin/sh
# Leave a task's throwaway branch and return to where the learner was.
# Anything uncommitted on the branch is committed there first, so nothing
# of the learner's is lost; the branch is kept, not deleted. Reads
# `branch:` and `return-to:` from .rolling/profile/task.md. Run by the
# tutor from the done skill, after the learner agrees. Exits non-zero on
# refusal.
set -eu
root=$(git rev-parse --show-toplevel)
cd "$root"
task=.rolling/profile/task.md
[ -f "$task" ] || { echo "no open task"; exit 1; }
branch=$(sed -n 's/^branch: *//p' "$task" | head -n 1 | sed 's/[[:space:]].*$//')
return_to=$(sed -n 's/^return-to: *//p' "$task" | head -n 1 | sed 's/[[:space:]].*$//')
[ -n "$branch" ] && [ -n "$return_to" ] || { echo "task.md has no branch:/return-to: lines; nothing to leave"; exit 1; }
current=$(git symbolic-ref -q --short HEAD || echo "")
[ "$current" = "$branch" ] || { echo "not on $branch (on ${current:-a detached HEAD}); leaving nothing"; exit 1; }

excl='. :(exclude).rolling :(exclude).claude'
# shellcheck disable=SC2086
git add -A -- $excl
if ! git diff --cached --quiet; then
  git commit -q -m "rolling: the learner's work, as left

Committed on the throwaway branch when the task ended, so nothing is
lost. Not for merging."
  echo "committed the learner's uncommitted work on $branch"
fi
git switch -q "$return_to" 2>/dev/null || git switch -q --detach "$return_to"
echo "back on $return_to; $branch kept"
