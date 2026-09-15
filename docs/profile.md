# The learner's directory

What the tutor writes. Everything the plugin knows about one learner
in one repository lives in a directory outside that repository's
working tree, in the plugin's data directory, keyed by the repository.
The map is the author's and is committed ([`map.md`](map.md)); this is
the learner's and never is. The design is in [`plan.md`](plan.md) § 3
(why it is out of the tree) and § 4 (what it holds).

## Where it is

```
${CLAUDE_PLUGIN_DATA}/repos/<encoded repository path>/
```

`CLAUDE_PLUGIN_DATA` is the directory Claude Code gives the `rolling`
plugin for its own data: per plugin, per user, persistent across
sessions and updates, and deleted when the plugin is uninstalled from
its last scope (which is why `rolling-export` exists). The repository
path is the working tree's top level as `git rev-parse --show-toplevel`
prints it, encoded the way Claude Code encodes its own project
directories: every byte that is not a letter or a digit becomes `-`.
`/home/pat/rallly` is `-home-pat-rallly`.

Every script and hook handler resolves the directory through one
rule: `ROLLING_DATA`, if set, replaces `${CLAUDE_PLUGIN_DATA}`. Tests
set it to a temporary directory so nothing they do touches a real
one. Nothing in the repository points at this directory, and no file
in it is ever needed by the repository's tooling; that is the point
of its location.

```
<learner's directory>/
  profile.md               # who this learner is and where they are going
  session                  # the tutor's session id, when no task is open
  task.md                  # the open task, if any
  reference.md             # the held reference solution for the open task
  held/<path>              # the held test files for the open task
  sessions/<session id>.log  # a direct lesson's coding sessions (P1b)
  tasks/<lesson>-<stamp>.md  # tasks the tutor built and kept for reuse
  evidence/<lesson>.md     # feedback, observations, interventions, appended
  detours/<slug>.md        # lessons the tutor created for this learner (P2)
  escalations/<stamp>.md   # what went to a human, with the trace (P2)
```

## `profile.md`

Written once by `/rolling:start` after intake, appended to by
`/rolling:done`, edited otherwise only by the learner in conversation.

```markdown
# Profile

## Background
Fluent in TypeScript, React, Postgres; never used tRPC or Prisma;
here to own billing.

## Destination
platform: orientation
billing: deep

## Why
Joining the payments team; polls can wait.

## Satisfied
- local-dev-setup (2026-09-12)
- how-a-change-ships (2026-09-13)
```

- **`## Background`**: the learner's words, lightly tidied: fluent in,
  never used, here to do. The `next` skill reads a lesson's `assumes`
  against it.
- **`## Destination`**: one `<region>: <depth>` line per region the
  learner chose, region slugs from the map, depths from the three. A
  region not listed is not on the route. The opening lessons of the
  suggested course are on every route regardless, because everything
  requires them. This section is the learner's: intake writes it from
  the author's suggested course as the learner bent it, and only the
  learner changes it afterwards, in conversation, never the tutor on
  its own.
- **`## Why`**: the learner's reason, in their words, so a later
  session (or a later learner reading over their shoulder) knows what
  the destination was for.
- **`## Satisfied`**: `- <lesson slug> (<YYYY-MM-DD>)`, one per lesson,
  appended by `done` and only by `done`, only when the tutor has seen
  the verifier and read the change against the rubric and said the
  rubric is met and the learner has agreed.

## `session`

One line, the session id of the tutor's most recent session, written
by `rolling-claim-session` from every learner-side skill when no task
is open. While a task is open the same id lives in the task instead.
It is how P1b's hooks tell the tutor's session from the learner's
coding session; in P1a it is written and never read.

## `task.md`

The open task. Written by the `next` skill after `rolling-begin-task`
has put the repository on the task's branch, checked by
`rolling-check-task` before anything reads it, removed by
`rolling-close-task` when the lesson is satisfied. At most one exists.

```markdown
---
lesson: poll-data-model
mode: write
branch: rolling/poll-data-model-20260914-1530
base: 4f1c2e9d8b7a6c5e4d3f2a1b0c9d8e7f6a5b4c3d
return-to: main 0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d
started: 2026-09-14
tutor-session: 8b1f0c2e-…
fix: af3d9273
scope: apps/web/src/trpc/routers/polls/participants.ts
scope: apps/web/tests/email-invites.spec.ts
setup: regenerate-client
verify: typecheck
verify: test-web src/features/poll/mutations.test.ts
held: apps/web/tests/email-invites.spec.ts
held-verify: integration tests/email-invites.spec.ts
expect-fail-on-base: held-verify integration tests/email-invites.spec.ts
---

## Brief

What is wrong or wanted, where to look, what done means …

## Source

Built from af3d9273 (#3191), a ten-line fix in participants.ts with
the assertion in email-invites.spec.ts held back.
```

Fields, all in the frontmatter subset `map.md` defines:

- **`lesson`** (required). The lesson's slug.
- **`mode`** (required). `write` or `direct`, resolved from the lesson
  and the map. The write-mode guard reads it.
- **`branch`** (required). The throwaway branch `rolling-begin-task`
  cut, `rolling/<lesson>-<stamp>`. `rolling-end-task` refuses to run
  unless HEAD is this branch.
- **`base`** (required). The full sha of the starting-state commit on
  that branch, as `rolling-begin-task` printed it. `rolling-diff`
  takes the learner's change against it. A sha, never a ref: a moving
  base would make the diff empty the moment anything was committed.
- **`return-to`** (required). Where the learner was: a symbolic ref
  and its resolved sha, space-separated (`main 0e9d…`), or a sha
  alone if they were detached. `rolling-end-task` returns to the ref
  if it still resolves, else to the sha with a note.
- **`started`** (required). `YYYY-MM-DD`.
- **`tutor-session`** (required). The session id of the tutor's
  session, written by `rolling-claim-session` each time a learner-side
  skill runs, so whichever session last ran one is the tutor and a
  restarted tutor reclaims the role. The write-mode guard acts only in
  this session.
- **`fix`** (optional). The commit the task was built from, when it
  was built from one.
- **`scope`** (one or more). Paths or globs the change is expected to
  touch. In a `write` task the tutor is denied Edit and Write inside
  them by the hook in `hooks.json`; the learner's own edits are theirs.
  Globs are `*`, `**`, `?`; a bare directory matches everything
  beneath it. Paths from the model are untrusted input everywhere the
  toolkit reads them.
- **`scaffold`** (optional, one or more). Paths inside the scope where
  the tutor may write, leaving `TODO(human)` markers the way the
  built-in Learning output style does.
- **`setup`** (optional, one or more). Operation keys from the map,
  run by the tutor when the task starts, a destructive one only after
  the learner says yes to that run. Nothing runs them again at `done`;
  if the learner's own work will need one (they touch the schema), the
  brief says so.
- **`verify`** (one or more). A command key from the map's `commands`
  followed by arguments as plain words: no shell metacharacters, no
  globs, no path with a space in it. `rolling-verify` runs each in
  order and reports each.
- **`held`** (optional, one or more). Repository-relative paths of the
  test files held back from the learner, stored under `held/` with
  the same relative path. Present when the lesson's `test` is `held`
  and the task was built from a fix with a test.
- **`held-verify`** (optional, one or more). The verifier lines that
  need the held files in place: same shape as `verify`. `rolling-verify`
  runs them after the `verify` lines, with the held files applied, and
  reverts afterwards.
- **`expect-fail-on-base`** (optional, one or more). Which `verify` or
  `held-verify` lines must fail on the starting state, for the
  both-ways proof: `verify <line>` or `held-verify <line>`, the line
  verbatim.

Then the body: **`## Brief`** for a `write` task or **`## Situation`**
for a `direct` one (what is wrong or wanted, where to look, what done
means; a situation is a symptom or a request, not instructions), and
**`## Source`**: the commit or seam the task was built from, so `done`
can compare.

A task's frontmatter is the one place the model writes something the
scripts run. Every value is validated before it is used, and
`rolling-verify` and `rolling-diff` fail safe, in words, on anything
malformed rather than guessing.

## `reference.md`

The tutor's copy of the answer, held back. For a task built from a
fix: the sha, the paths it touched, and the tutor's note on what it
did and why, so `done` can compare what the learner did with what the
original did without confusing the two. For a task the tutor built
from a seam: the tutor's own solution, as a description or a diff.
Named to the learner as "a reference exists and I am holding it",
never by path; a coding session in a `direct` lesson is denied the
whole directory (P1b).

## `held/`

The held test files, at their repository-relative paths, copied from
the fix by `rolling-begin-task`. They are applied to the tree only
while `rolling-verify` runs the `held-verify` lines, after the diff
has been captured, and reverted before it returns, with any learner
file at the same path set aside for the run and restored. Removed with
the task.

## `sessions/<session id>.log` (P1b)

One file per coding session in a `direct` lesson, written by the
plugin's hooks from that session: every prompt, every file edited,
every command run, each reply, one line each, in order. The tutor
watches the directory while the learner works and reads all of it at
`done`. P1a writes none.

## `tasks/<lesson>-<stamp>.md`

A task the tutor built and kept, in `task.md`'s shape minus the
branch, base, return-to, started, and tutor-session fields, so a later
session (or another learner on this machine) can reuse it. Optional;
the `next` skill keeps a task here when it proved cleanly.

## `evidence/<lesson>.md`

Appended, never rewritten. One entry per event, opening with a date
line, and the entry's kind on the next line:

```markdown
## 2026-09-14

**Route.** Chose this lesson: billing at deep is the destination,
how-a-change-ships is satisfied, nothing else in billing is reachable
yet.

## 2026-09-14

**Observation.** Edited participants.ts before reading the schema
comment at poll.prisma:76; ran the same failing test three times.

## 2026-09-15

**Feedback.** VERIFIER: 2 passed, 0 failed, 0 unknown or rejected;
held: 1 passed.
- apps/web/src/trpc/routers/polls/participants.ts:291 — the token is
  minted in the app, never defaulted by the database; this repo's
  convention, see the comment at poll.prisma:76. Met.
- … Outcome: satisfied. The learner agreed.
```

Kinds: **Route** (why `next` chose this lesson, one line), **Observation**
(what the tutor noticed while the learner worked; never satisfies
anything), **Intervention** (what the tutor said unprompted while
watching a `direct` session, and why; on the tutor's ledger, not the
learner's), **Feedback** (the verifier summary lines, every point with
its location, rule, and provenance, and the outcome: `satisfied`, or
`open` and what would close it, with both positions when the tutor and
the learner disagree).

## `detours/<slug>.md` and `escalations/<stamp>.md` (P2)

A detour is a lesson the tutor wrote for this learner, in the lesson
format, off the map; the author promotes the ones several learners
needed. An escalation is what went to a human, with the trace. Neither
is written in P1.

## Who writes what

The rules the tutor holds, rewritten for a tutor rather than an
examiner:

- A lesson is **satisfied** when the tutor, having seen the verifier
  pass and read the change against the rubric, says so and the learner
  agrees. `done` writes the line to `## Satisfied` then, and only then.
  Disagreement is recorded in evidence with both positions and the
  lesson stays open; the learner may ask for a second opinion (P2).
- **Observations** go to evidence and never satisfy anything on their
  own.
- In a `direct` lesson, a **catch the tutor prompted** while watching
  is an Intervention in evidence and stays on the tutor's ledger; it
  is never credited to the learner.
- **The destination** is changed only by the learner, in conversation.
  The tutor may say when evidence suggests they are somewhere they did
  not mean to be, and offer the course's shape back, and never edits
  the section itself.
- **Detours** are created by the tutor and promoted by the author.
- Nothing here is ever written into the repository's working tree.

## What `rolling-check-profile` and `rolling-check-task` check

Shape, never content. Every fault on its own line with the file and
the field.

`profile.md`:

- The four headings `## Background`, `## Destination`, `## Why`,
  `## Satisfied` are present, in that order, under a `# Profile`
  title.
- Every non-blank line under `## Destination` is `<slug>: <depth>`
  with a valid slug and one of the three depths; no region twice.
  Whether the slug names a region in the map is checked when a map is
  at hand and reported as a warning otherwise.
- Every non-blank line under `## Satisfied` is `- <slug> (<YYYY-MM-DD>)`.

`task.md`:

- A frontmatter block with `lesson`, `mode`, `branch`, `base`,
  `return-to`, `started`, `tutor-session`, and at least one `scope`
  and one `verify`; no unknown field.
- `mode` is `write` or `direct`; `base` is 7 to 40 hex characters;
  `return-to` is a ref and a sha or a sha alone; `started` is a date;
  `fix`, if present, is hex.
- Every `verify` and `held-verify` line's first word is a command key
  in the map and the rest carries no shell metacharacter or glob;
  every `setup` line names an operation key; every
  `expect-fail-on-base` line repeats a `verify` or `held-verify` line
  verbatim.
- Every `held` path is repository-relative, contains no `..` segment,
  and has a file under `held/`; every `scaffold` path is inside some
  `scope`.
- The body has `## Brief` or `## Situation`, matching the mode, and
  `## Source`.
