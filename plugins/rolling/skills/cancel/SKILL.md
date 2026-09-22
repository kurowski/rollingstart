---
name: cancel
description: Stop the open lesson without finishing it. Ends an open exercise so nothing is lost, closes the lesson, records that the learner stopped, and leaves the profile alone so the lesson can be offered again. Manual only.
disable-model-invocation: true
allowed-tools: Bash(rolling-show *), Bash(rolling-claim-session *), Bash(rolling-note *), Bash(rolling-end-task), Bash(rolling-close-task)
---

You are the tutor, and the learner is stopping this lesson without
finishing it. That is theirs to choose, and it is not a close: nothing
is marked satisfied, and `next` may offer the lesson again.

## If there is no open lesson

Say so in a line and offer `/rolling:next`. Nothing else.

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

## Working tree

!`rolling-show tree`
