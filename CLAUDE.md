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
before proposing anything structural. Decisions made after it go in its
§ 10, dated, not in a separate record.

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
| `docs/workflow.md` | How work happens here |
| `docs/plans/` | One plan per checkpoint, the tracker for its work, with a retrospective at the end |
| `spike/` | P0, kept as a record. None of it is the plugin. |
| `evals/` | `claude plugin eval` suites, the tests of a prompt product. (P2) |
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

**One change → one branch → one PR.** The maintainer merges, with a
merge commit. A change that crosses layers is a base-chained stack,
never GitHub's native one.

**Scripts and hooks get a local code review before they are pushed.**
Spawn a code-review sub-agent on the Opus model (`claude-opus-5`) over
the outgoing diff, against [`REVIEW.md`](REVIEW.md) and the checkpoint
plan, and fix the real findings first. A review-round fix is a push and
gets its own review. The reviewer's brief confines any state-changing
experiment (a hook, a script under odd env, a git operation) to a
scratch copy under the session's scratchpad, never the live checkout
and never `../rallly`, and the tree is verified (status, log, local
config) when a review returns. Prose (a skill, a spec, a map, a doc) is
reviewed by running it: a lesson on the Rallly clone, its transcript
read for the failure modes the plan names, and from P2 an eval.

**Write commit bodies you'd want a new hire to learn from.** What and
why, each decision with its reason. This repository is meant to become
an instance of its own tool once it has something to teach, so its
history is teaching material.

**Stop on surprises.** An unexpected incompatibility, a Claude Code
mechanism that does not behave as the docs say, or an uncovered design
question means stop and ask, not guess and continue. The mechanisms the
plan rests on that the docs do *not* confirm are named in
[`docs/plan.md`](docs/plan.md) § 3 and § 7 and tabled in the checkpoint
plan; confirm each in a scratch setup before building on it.

**Facts about Rallly come from the pinned checkout at `../rallly`.**
Not from memory, and not from an unpinned read. When a claim rests on
Rallly, cite the path and the pin. `../rallly` is a reference to read
and never written to; the tutor runs against `../rallly-spike`, a
writable clone at the same pin. If the checkout is not on this machine
(a reviewer's sandbox, say), leave the claim to whoever has it.

**Roles are Author, Tutor, Learner** in every document, commit, and
skill. The analogy the project started from stays in conversation.

## Conventions

- **Python 3.9 or later, standard library only.** That is what a Mac
  with the command line tools and any desktop Linux already have, and
  the plugin must not ask a learner to install a runtime first (the
  native Claude Code installer no longer brings Node). So nothing
  newer than 3.9 (no `match`, no `X | Y` in annotations at runtime, no
  `tomllib`), no third-party packages, and `subprocess` always with an
  argument list, never a shell. Every module starts with
  `from __future__ import annotations`: 3.14 evaluates annotations
  lazily and 3.9 does not, and the difference has bitten once. The
  executables in `plugins/*/bin/`
  are a few lines each and import `lib/rolling/`; the library is
  where the code is. Hook handlers are the same Python. The first
  toolkit was bash; it was replaced (PR for 1a.3b) because bash made
  the one destructive path, applying and reverting the held test,
  need six review rounds to get right, and a map validator in bash
  was unreadable.
- **Tests.** `unittest`, under `plugins/rolling/tests/`, against a
  scratch repository built in a temporary directory, never a real
  checkout. Assert on the structured result where the library returns
  one (a fault list, a report), on the rendered text only where the
  text is the contract a skill reads.
- **The gate**, before any push: byte-compile with warnings as
  errors, the test suite, and `claude plugin validate --strict` for
  each plugin and the marketplace, each checked by its own exit
  status. CI runs the same on Python 3.9, a current Python, and a
  Mac's system Python.
- **Skills.** `disable-model-invocation: true` on every learner-facing
  skill except `lesson`, which only ever re-presents the open task and
  is how `next` hands off; `allowed-tools` grants narrow and named,
  never `Bash(pnpm *)` or `Bash(git *)`; inline commands are single
  invocations of a `bin/` script, never compound one-liners (their
  parts match no grant).
- **Docs** carry a light motorsport theme in prose. Never in
  identifiers.

## Workflow

[`docs/workflow.md`](docs/workflow.md): the checkpoint plan is the
tracker, a slice ships as spec, test, code, gate, review, PR, and a
checkpoint ends with a retrospective.
