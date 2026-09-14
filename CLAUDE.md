# Rolling Start — agent instructions

Read this before doing anything in this repository.

## What this is

A Claude Code native codebase tutor, shipped as a plugin marketplace. An
**author** who knows a codebase describes its landscape in a map; a
**learner** who does not picks a destination on it; the **tutor**, Claude
Code running the `rolling` plugin, points the way: one task at a time,
with feedback on real work in the learner's own working copy. The author
describes the landscape, the learner picks the destination, the tutor
points the way.

[`docs/plan.md`](docs/plan.md) is the design and the decision record:
what changed from the original conception, the three roles, the
repository layout, the formats, the loop and where each rule is
enforced, the phases, the risks, and what has been decided. Read it
before proposing anything structural.

## Status

- [x] **P0 — Spike.** `spike/`, merged as PR #1. The premise held.
- [x] **Plan, draft 2.** PR #2.
- [ ] P1a — `write` mode, in-repo map — [`docs/plans/p1a-write-mode.md`](docs/plans/p1a-write-mode.md)
- [ ] P1b — `direct` mode
- [ ] P1c — Distribution: map plugins, the resolver, `adopt`
- [ ] P2 — Enforced, and measured
- [ ] P3 — The author's plugin
- [ ] P4 — The upper rungs of `direct`
- [ ] P5 — Release

## Key locations

| Path | What |
|---|---|
| `.claude-plugin/marketplace.json` | The marketplace. Lists the plugins below. (P1a) |
| `plugins/rolling/` | The learner's plugin: skills, hooks, the `bin/` toolkit. (P1a) |
| `plugins/rolling-author/` | The author's plugin. `adopt` in P1c, the rest in P3. |
| `plugins/rallly/`, `plugins/homie/` | Map plugins. (P1c) |
| `examples/rallly/.rolling/` | The Rallly map's source until it becomes a map plugin |
| `docs/plan.md` | Design and decision record |
| `docs/map.md`, `docs/profile.md` | The formats: what the author writes, what the tutor writes. (P1a) |
| `docs/workflow.md` | How work happens here. The skills point at it. |
| `docs/plans/` | One expanded plan per phase checkpoint, plus its retrospective |
| `docs/decisions/` | ADRs, for decisions made after the plan |
| `spike/` | P0, kept as a record. None of it is the plugin. |
| `evals/` | `claude plugin eval` suites, the tests of a prompt product. (P2) |
| `.claude/skills/` | `/plan-milestone`, `/refine-issue`, `/implement-issue`, `/milestone-endgame` |
| `../rallly` | Rallly reference checkout, pinned at `aab791da`. Read-only. |
| `../rallly-spike` | A writable Rallly clone the tutor runs in, contained |
| `../homie` | The maintainer's Go CLI, the toolchain-diversity target (P1c) |
| `../rollingstop` | The archived predecessor, for anything § 9 of the plan says to carry over |

## Rules

**Never commit or push without explicit approval.** Not once, not for a
one-liner. "Proceed" on an edit means edit; committing, pushing, and
opening a PR each get their own word.

**The plugin knows nothing about any codebase; the map knows everything
about one.** If a skill or script in `plugins/rolling/` names a package
manager, a framework, a path in Rallly, or a domain, stop: that belongs
in a map. The generic example regions in documentation are `billing`,
`scheduling`, and `platform`. The maintainer's employer's codebase never
appears in this repository, in examples or otherwise.

**The tutor never orchestrates the environment.** No docker, no compose,
no health checks, no installing toolchains, no fixing a broken `.env`.
It runs where the learner's environment already runs; a command that
fails because a service is down is reported, with the setup lesson
offered. Whether the *learner* starts services in a setup lesson is the
map's call, per environment.

**Verifiers are structured, never shell.** A task names declared
commands and the test files the tutor holds; `verify` runs those and
only those, and rejects any argument with a shell metacharacter in it.
Operations are the author's shell, code-reviewed in the target repo.

**Nothing the tutor writes goes in the learner's tree.** Learner state
lives in the plugin's data directory, keyed by repository. The map is
the author's and is committed; everything else the tutor produces is
outside the working copy, so the repo's own checks never see it and a
coding agent cannot grep its way to a reference solution.

**A rule that must hold is held by a hook or a script, in every
permission mode.** Prose in a skill is the first line; the hook in
`hooks.json` is the one that holds when the learner asks nicely. Nothing
may depend on the permission mode: skills declare narrow grants or none,
never a wildcard over a package manager or git, and destructive
operations prompt through `permissions.ask` rules first and a hook's
`ask` second.

**No fourth wall.** The checks a learner runs during a lesson are the
repo's own commands, given verbatim as the map declares them. The tutor
names the lesson's mode up front and never cites a script, a task file,
or a profile file; those are its own.

**The learner picks the destination.** The `next` skill serves lessons
inside the destination and detours off them, never a region the learner
did not choose, and never edits the destination. A route that reads as
a fixed order across learners with different backgrounds is a bug.

**Skill inline commands always exit zero.** A non-zero exit from a
`` !`command` `` aborts the skill, and they run under the Bash tool's
two-minute timeout. Every script a skill runs inline reports in words
and exits 0; a script a skill runs as an action may exit non-zero.

**One issue → one branch → one PR.** For large scopes, base-chained
stacks. Never GitHub's native stacked PRs. Direct commits to `main` are
the exception, not a lane: for a change where a PR would be needless
ceremony, and only on the maintainer's say-so, asked each time. A new
spec, reference page, or ADR always goes through a PR.

**Every push that changes behaviour gets a local code review first.**
Spawn a code-review sub-agent on the Opus model (`claude-opus-5`) over
the outgoing diff, reviewing against [`REVIEW.md`](REVIEW.md), the
checkpoint plan in [`docs/plans/`](docs/plans/), and the relevant ADRs,
and fix the real findings before pushing. The gate is the push, not
finishing the work: a review-round fix is a push and gets its own
review, however small the fix felt. The reviewer's brief confines any
state-changing experiment (a hook, a script run under odd env, a git
operation) to a scratch copy of the repository under the session's
scratchpad, never the live checkout and never `../rallly`, and the tree
is verified (status, log, local config) when a review returns. Exempt
only pushes that change no behaviour at all: comment wording, doc prose.
Skills are behaviour.

**Code review lives on three surfaces; triage all of them.** Inline
per-file comments (`gh api repos/kurowski/rollingstart/pulls/<N>/comments`),
review summary bodies (`gh pr view <N> --json reviews`), and the
PR-level conversation
(`gh api repos/kurowski/rollingstart/issues/<N>/comments`). An empty
inline list plus green checks is not review-clean.

**Answer review findings where they were raised.** Reply to each inline
comment in its own thread
(`gh api repos/kurowski/rollingstart/pulls/<N>/comments -X POST -f body='…' -F in_reply_to=<id>`)
with the disposition and the fixing commit; reserve PR-level comments
for whole-PR feedback.

**Write commit bodies you'd want a new hire to learn from.** What and
why, each decision with its reason. This repository is meant to become
an instance of its own tool once it has something to teach, so its
history is teaching material.

**Stop on surprises.** An unexpected incompatibility, a Claude Code
mechanism that does not behave as the docs say, or an uncovered design
question means stop and ask, not guess and continue. The mechanisms the
plan rests on that the docs do *not* confirm are named in
[`docs/plan.md`](docs/plan.md) § 3 and § 7; confirm each before
building on it.

**Facts about Rallly come from the pinned checkout at `../rallly`.**
Not from memory, and not from an unpinned read. When a claim rests on
Rallly, cite the path and the pin. `../rallly` is a reference to read
and never written to; the tutor runs against `../rallly-spike`, a
writable clone at the same pin. If the checkout is not on this machine
(a reviewer's sandbox, say), leave the claim to whoever has it.

**Roles are Author, Tutor, Learner** in every document, commit, and
skill. The analogy the project started from stays in conversation.

## Conventions

- **Shell.** `plugins/*/bin/` scripts are POSIX `sh` (`#!/bin/sh`,
  `set -u`, no bashisms), clean under `shellcheck`. They assume `git`
  and a POSIX userland and nothing else: no `jq`, no Python, no Node
  beyond what the target repo already requires. Hook handlers are the
  one exception: Node (`.mjs`, no dependencies), because they read JSON
  on stdin and every Claude Code host has Node.
- **Tests.** Each script in `bin/` has a test that runs it against a
  scratch repository built in a temporary directory, never against a
  real checkout. A plain-`sh` runner, no framework.
- **The gate**, before any push: `shellcheck` over every shell script,
  the test runner, and the plugin manifest validator for each plugin,
  each checked by its own exit status and never through a pipe that
  masks it. CI runs the same.
- **Skills.** `disable-model-invocation: true` on every learner-facing
  skill except `lesson`, which only ever re-presents the open task and
  is how `next` hands off; `allowed-tools` grants narrow and named,
  never `Bash(pnpm *)` or `Bash(git *)`; inline commands are single
  invocations of a `bin/` script, never compound one-liners (their
  parts match no grant).
- **Docs** carry a light motorsport theme in prose. Never in
  identifiers.

## Workflow

[`docs/workflow.md`](docs/workflow.md) is the reference. The cycle is
`/plan-milestone` → `/refine-issue` → `/implement-issue` →
`/milestone-endgame`, where a milestone is one checkpoint of the plan's
phases (P1a, P1b, …).
