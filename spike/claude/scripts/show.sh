#!/bin/sh
# Print one piece of Rolling Start context for a skill's inline command.
#
#   sh .claude/scripts/show.sh <what>
#
# Every skill's inline `!`…`` block calls this rather than a compound
# one-liner, for two reasons: an inline command that exits non-zero aborts
# the skill, and a compound command has parts that no allowed-tools pattern
# matches. This script always exits 0 and reports absence in words.
set -u
root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "(not a git repository)"; exit 0; }
r="$root/.rolling"
what=${1:-}

case "$what" in
  map)
    [ -f "$r/map.md" ] && cat "$r/map.md" || echo "(no map: $r/map.md is missing)" ;;
  corpus)
    [ -f "$r/map.md" ] && sed -n '/^## Corpus/,$p' "$r/map.md" || echo "(no map)" ;;
  lessons)
    found=0
    for f in "$r"/lessons/*.md; do
      [ -e "$f" ] || continue
      found=1; echo; echo "=== $(basename "$f" .md) ==="; cat "$f"
    done
    [ "$found" -eq 1 ] || echo "(no lessons under $r/lessons/)" ;;
  lesson-heads)
    found=0
    for f in "$r"/lessons/*.md; do
      [ -e "$f" ] || continue
      found=1; echo "### $(basename "$f" .md)"
      sed -n '/^---$/,/^---$/p' "$f" | sed '1d;$d'
    done
    [ "$found" -eq 1 ] || echo "(no lessons under $r/lessons/)" ;;
  profile)
    [ -f "$r/profile/profile.md" ] && cat "$r/profile/profile.md" || echo "(no profile: this is a new learner, or /start has not run)" ;;
  task)
    [ -f "$r/profile/task.md" ] && cat "$r/profile/task.md" || echo "(no open task)" ;;
  lesson-for-task)
    if [ -f "$r/profile/task.md" ]; then
      slug=$(sed -n 's/^lesson: *//p' "$r/profile/task.md" | head -n 1 | sed 's/[[:space:]].*$//')
      if [ -z "$slug" ]; then echo "(the open task names no lesson)"
      elif [ -f "$r/lessons/$slug.md" ]; then cat "$r/lessons/$slug.md"
      else echo "(the open task names lesson '$slug', but $r/lessons/$slug.md does not exist)"; fi
    else echo "(no open task)"; fi ;;
  session-log)
    [ -f "$r/profile/session.log" ] && cat "$r/profile/session.log" || echo "(no coding session log: not a direct lesson, or the coding agent was not launched with run.sh code)" ;;
  transcript)
    if [ -f "$r/profile/task.md" ] && command -v node >/dev/null 2>&1; then
      started=$(sed -n 's/^started: *//p' "$r/profile/task.md" | head -n 1 | sed 's/[[:space:]].*$//')
      cd "$root" && node .claude/scripts/transcript.mjs --latest ${started:+--since "$started"} --exclude "${CLAUDE_CODE_SESSION_ID:-${CLAUDE_SESSION_ID:-}}" 2>/dev/null || echo "(transcript not readable)"
    else echo "(no open task, or no node)"; fi ;;
  tree)
    cd "$root" || exit 0
    dirty=$(git --no-pager -c color.ui=false -c core.quotePath=false status --porcelain -- . ':(exclude).rolling' ':(exclude).claude')
    if [ -n "$dirty" ]; then
      n=$(printf '%s\n' "$dirty" | wc -l | tr -d ' ')
      printf '%s\n' "$dirty" | head -n 20
      [ "$n" -gt 20 ] && echo "(... and $((n - 20)) more)"
    else echo "(clean)"; fi
    if h=$(git rev-parse --verify -q HEAD); then echo "HEAD $h"; else echo "HEAD (no commits yet)"; fi ;;
  *)
    echo "usage: show.sh map|corpus|lessons|lesson-heads|profile|task|lesson-for-task|session-log|transcript|tree" ;;
esac
exit 0
