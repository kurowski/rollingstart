#!/bin/sh
# Install the P0 spike into a writable Rallly clone.
#
#   spike/install.sh /path/to/rallly
#
# Copies the spike's skills, agent, and scripts into the clone's .claude/
# and the example map into .rolling/, and makes sure the profile directory
# is self-protecting (its .gitignore contains "*"). Existing files with the
# same names are overwritten; anything else in the clone's .claude/ is left
# alone. Run it again to pick up edits.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/.." && pwd)
target=${1:?usage: spike/install.sh /path/to/rallly}
target=$(cd "$target" && pwd)
git -C "$target" rev-parse --show-toplevel >/dev/null 2>&1 || { echo "$target is not a git repository"; exit 1; }

mkdir -p "$target/.claude" "$target/.rolling/profile"
cp -R "$here/claude/." "$target/.claude/"
cp -R "$repo/examples/rallly/.rolling/." "$target/.rolling/"
printf '*\n' > "$target/.rolling/profile/.gitignore"
chmod +x "$target"/.claude/scripts/*.sh

echo "installed into $target:"
echo "  .claude/skills/{start,lesson,done}  .claude/scripts/{verify,diff,show,close-task,begin-task,end-task}.sh"
echo "  .claude/scripts/{session-log,transcript}.mjs  .claude/rolling-coding.json (hooks for the coding session)"
echo "  .rolling/map.md  .rolling/lessons/  .rolling/profile/ (gitignored)"
echo "next: open Claude Code in $target and run /start"
