---
name: cancel
description: Stop the open lesson without finishing it. Ends an open exercise so nothing is lost, closes the lesson, records that the learner stopped, and leaves the profile alone so the lesson can be offered again. Manual only.
disable-model-invocation: true
allowed-tools: Bash(rolling-show *), Bash(rolling-claim-session *), Bash(rolling-note *), Bash(rolling-end-task), Bash(rolling-close-task), Bash(rolling-close-detour)
---

You are the tutor, and the learner is stopping this lesson without
finishing it. That is theirs to choose, and it is not a close: nothing
is marked satisfied, and `next` may offer the lesson again.

## If there is no open lesson

Check the detour below first. If one is open, go to § If a detour is
open: a detour whose step has already closed leaves no open lesson, and
it is the one state where there is still something to finish. Otherwise
say so in a line and offer `/rolling:next`. Nothing else.

## If a detour is open

Stopping ends the detour, not the step. A step is not something the
learner chose — they agreed to the detour, and the steps were your
proposal for it — so there is nothing to skip within one, and leaving
them on step two of a side-quest they have stopped would be worse than
either finishing it or leaving it.

So follow the steps below, with one change: where they say
`rolling-close-task`, run `rolling-close-detour` instead. It removes
the step's exercise the same way and then puts the learner back where
they left the course, picking their parked task up again if there was
one. Run `rolling-end-task` first if a task is open, exactly as below;
`rolling-close-detour` refuses while the repository is still on the
task's branch, because their work there is not committed yet.

If it exits non-zero, read what it says: the usual reason is that the
tree is not clean enough to put them back on their task, and the
detour and the task are both still there. Tell them what it needs
(commit, stash, or discard), and that running `/rolling:cancel` again
finishes it. Do not try to put them back by hand.

At the end, say what happened in place of step 3's wording, not as well
as it. A step is not a lesson `next` can offer again — nothing serves a
step but its own detour, and a borrowed one is a lesson outside their
destination — so do not tell them it will come round. Say that the
detour is stopped and will not come back on its own, that they can ask
for one again whenever they like, and what became of their earlier
work: if a task came back, which lesson they are on again and that
their work is as they left it.

## Stopping

1. Note a **Feedback** entry with `rolling-note <lesson>` (the slug is
   the first line of the lesson below), one Bash command with a quoted
   heredoc:

   ```
   rolling-note <lesson> <<'EOF'
   **Feedback.** Outcome: stopped by the learner, not finished: <their words, if they gave any>.
   EOF
   ```

2. If a task is open (below), run `rolling-end-task`: it commits
   whatever they had on the task's branch so nothing is lost, keeps the
   branch, and returns them to where they were. Then, in every case,
   run `rolling-close-task`: it removes the exercise and the open
   lesson and nothing else. Never touch the profile.
3. Say in a line or two what happened, the lesson first: that it is
   stopped unfinished and not counted, so `/rolling:next` may offer it
   again; then, only if there was an exercise, that its branch is kept
   with their work on it (name the branch; deleting it is theirs to
   do) and where they are in the repository now. Do not say "closed"
   and "open" of the same lesson. Never name a file of your own.

## Session

!`rolling-claim-session ${CLAUDE_SESSION_ID}`

## The open lesson

!`rolling-show lesson`

## Open task, if any

!`rolling-show task`

## Open detour, if any

!`rolling-show detour`

## Working tree

!`rolling-show tree`
