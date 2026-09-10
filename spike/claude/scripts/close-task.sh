#!/bin/sh
# Close the open task: remove the task's files from the profile, and
# nothing else. Called by the `done` skill when a lesson is satisfied, so
# that the skill never needs a broad `rm` in its allowed tools.
set -u
root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "not a git repository"; exit 0; }
p="$root/.rolling/profile"
for f in task.md reference.md brief.md review.md planted.md; do
  [ -f "$p/$f" ] && rm -f "$p/$f" && echo "removed $f"
done
echo "task closed; profile.md and evidence/ kept"
exit 0
