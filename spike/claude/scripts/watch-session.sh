#!/bin/sh
# Follow the coding session's log for the tutor's Monitor: one line per
# learner prompt, agent reply, and file edit; the rest of the log (other
# tool calls, the header) stays in the file. Waits for the log to appear,
# follows it from its start once it does, and survives it being replaced.
# grep must be line-buffered or nothing reaches the Monitor until its
# buffer fills. Runs until stopped.
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
tail -n 0 -F "$root/.rolling/profile/session.log" 2>/dev/null \
  | grep --line-buffered -E '^\[[0-9:]+\] (LEARNER|AGENT):|^\[[0-9:]+\]   (Edit|Write|NotebookEdit):'
