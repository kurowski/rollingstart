# Workflow

How work happens here. One page, because the project is small: a
handful of shell scripts, two or three hook handlers, and a set of
skills, specs, and maps that are prose. The process the predecessor
carried, milestones with project boards, tracking issues with native
sub-issues, an ADR directory, and four skills to drive them, was built
for a team on a large system and is recorded in this file's first
version in git history; what follows is what survived contact with a
plugin.

Rolling Start is built primarily by AI agents with a human maintainer,
in public, on purpose: the process is part of what this project is
demonstrating.

## Where things live

| Path | What |
|---|---|
| [`docs/plan.md`](plan.md) | Design and decision record. Decisions made after it go in § 10, dated. |
| [`docs/map.md`](map.md), [`docs/profile.md`](profile.md) | The formats: what the author writes, what the tutor writes (P1a.2) |
| [`docs/plans/`](plans/) | One plan per checkpoint (P1a, P1b, …): its sub-scopes, a paragraph each, are the tracker; each PR flips its own to `[COMPLETE]`, and the plan ends with a retrospective. Detail lives in the artifact a sub-scope describes, not in the plan. |
| [`spike/NOTES.md`](../spike/NOTES.md) | What P0 found, as it happened; the register a retrospective is written in |

GitHub carries the PRs. Issues are a backlog, not a tracker: file one
for something found mid-run that outlives the session, or a deferral
worth remembering, and close it with `Closes #N` when a PR does.

## How a slice ships

A sub-scope of the checkpoint plan, on its own branch off `main`,
named for it (`p1a.3/toolkit`). Before branching, read `CLAUDE.md`,
`REVIEW.md`, the sub-scope, and, for anything the spike prototyped,
the spike's version and what `spike/NOTES.md` says went wrong with it.

1. **Confirm the mechanism**, if the sub-scope rests on a Claude Code
   behaviour the docs do not spell out. In a scratch setup under the
   session's scratchpad, never a real checkout; record the result in
   the plan's table. Stop and ask when the answer is no.
2. **Spec.** A format change lands in `docs/map.md` or
   `docs/profile.md` first. A script's contract is its header comment.
   A skill's is its own `SKILL.md` and the loop in `docs/plan.md` § 5.
3. **Test**, for a script: under `plugins/rolling/tests/`, against a
   scratch repository, failing first.
4. **Implement.** POSIX `sh`; Node without dependencies only for hook
   handlers. Logical commits with real bodies.
5. **The gate**, each by its own exit status: `shellcheck` over every
   shell script, the test runner, `claude plugin validate` for each
   plugin and the marketplace. CI runs the same on every PR and on
   `main`; the commands live in `.github/workflows/ci.yml` from P1a.3.
6. **Review.** Scripts and hooks: a code-review sub-agent on Opus over
   the outgoing diff, per `CLAUDE.md` § Rules, real findings fixed
   before the push. Prose: a run on the Rallly clone, transcript read,
   written up in the plan.
7. **PR.** Summary of what and why, a test plan, `Closes #N` if an
   issue exists. The maintainer merges, with a merge commit, never a
   squash; the branch's own commits are the history. The PR flips
   its own sub-scope to `[COMPLETE]` and records its number there:
   the merge is what makes that true.

A change that would be too large for one review (it crosses layers, or
runs past a few hundred lines) is a base-chained stack: each slice
branched off the one beneath it, opened with `--base <branch-below>`,
reviewed to settlement before the next is written. Never GitHub's
native stacked PRs.

Something the sub-scope did not anticipate goes into the same PR only
if it is small, clearly part of the sub-scope, and noted in the PR
body. Otherwise it is a backlog issue or a line in the plan's deferred
list.

## When a checkpoint ends

Run its exit criterion honestly, on the target, and append a
`## Retrospective` to the plan: planned against delivered, the exit
run as it went, decisions made on the way (the ones worth keeping go
to `docs/plan.md` § 10, dated), what went wrong and how it was fixed
with PR numbers, what was deferred and where, what to carry forward,
what to change. Specific and unflattering; a retrospective that reads
as a success report is not doing its job. Then tick the checkpoint in
`CLAUDE.md` § Status and mark it done in `docs/plan.md` § 7 the way P0
is, and read the next checkpoint's entry for what this one changed
about it.

## Commit messages

Write commit bodies you'd want a new hire to learn from: explain why,
not just what. Rolling Start builds tasks from git history, and this
repository is meant to become its own instance once it has something
to teach. A `wip` commit is a lesson we can't teach.
