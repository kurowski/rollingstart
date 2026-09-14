# Workflow

How work happens here. The Claude Code skills in
[`.claude/skills/`](../.claude/skills/) encode this; this document is
the reference they point at.

Rolling Start is built primarily by AI agents with a human maintainer.
The workflow is deliberately identical for both: same branches, same
PRs, same review. It also runs entirely in public, on purpose: the
process is part of what this project is demonstrating.

## The cycle

```
/plan-milestone  →  /refine-issue  →  /implement-issue  →  /milestone-endgame
```

Run in that order. `/refine-issue` is the per-issue planning step and
comes before any code is written; `/implement-issue` runs only on a
refined issue.

A **milestone** here is one checkpoint of the plan's phases: P1a, P1b,
P1c, P2, and so on ([`docs/plan.md`](plan.md) § 7). The word is
GitHub's, for the object that carries the issues; the plan calls them
checkpoints and phases, and both names mean the same unit of work.

## Where things live

**Durable artifacts live in the repo.** They survive the work that
produced them.

| Path | What |
|---|---|
| [`docs/plan.md`](plan.md) | Design and decision record: roles, layout, formats, the loop, phases, risks, decisions |
| [`docs/map.md`](map.md), [`docs/profile.md`](profile.md) | The formats: what the author writes, what the tutor writes (P1a.2) |
| [`docs/plans/`](plans/) | One expanded plan per checkpoint, plus its retrospective |
| [`docs/decisions/`](decisions/) | ADRs, for decisions made after the plan |
| [`spike/NOTES.md`](../spike/NOTES.md) | What P0 found, as it happened |

**Working state lives in GitHub.** It's disposable and it moves.

- **Milestones** (`P1a: write mode`) carry membership. No due dates;
  this is a side project and invented dates rot in public.
- **Project boards**, one per milestone, are the working surface:
  status columns and sub-issue progress.
- **Issues** carry the work. **PRs** carry the change and the
  discussion.

## Branches

Trunk-based. Feature branches off `main`, PRs back to `main`, no
long-lived branches. Descriptive kebab-case names, prefixed with the
sub-scope (`p1a.3/toolkit`). No issue numbers in branch names; link
with `Closes #N` in the PR body.

Direct commits to `main` are a narrow exception, not a lane: a change
where a PR would be needless ceremony (a plan status flip at closeout,
a one-line guidance fix) and only on the maintainer's say-so, asked
each time. Anything that deserves a reviewer's eyes goes through a PR
attached to its issue. A new spec, reference page, or ADR always does,
including one drafted during `/refine-issue`: writing it is work
product, not housekeeping.

## Issues

### Ready criteria

An issue is ready to implement when it has testable acceptance
criteria, its documentation exists (see below), and its dependencies
are resolved or named.

### Board membership is a precondition

Committing to implement an issue is committing to the milestone it
belongs to, and the board has to reflect that. `/implement-issue`
verifies this mechanically before branching.

Native sub-issues inherit board membership through their parent.
Standalone follow-ups filed mid-milestone need explicit membership,
routed by their milestone, never by whichever board feels current.

### Fold-in decisions go in issue bodies, never only in comments

When triage folds one issue's work into another, record it as a
checklist item in the *receiving* issue's body.

Both `/refine-issue` and `/implement-issue` read comments, so this
isn't about what gets read. It's about what gets **found**. A fold-in
sitting in comment 34 of 40 is technically read and practically
missed; a closed issue's comments are invisible to everyone in
practice; and whoever implements a sub-issue reads *that* sub-issue,
so a note on the parent's thread still isn't where the work happens.
The comment reads catch violations of this rule. They don't replace it.

### In-flight scope additions

Implementation surfaces gaps the issue didn't anticipate. Absorb one
into the current PR only if all three hold:

1. **Small**: roughly one commit, no new dependencies, no extra docs
2. **Clearly related**: the issue wouldn't feel done without it
3. **Documented**: noted on the issue and in the PR description

Fail any one and it becomes a follow-up issue. When in doubt, file the
follow-up.

## Documentation-driven development

Documentation comes before implementation. Which documentation depends
on the work.

**User-facing behaviour** (a format, a skill's behaviour, a script's
contract): write or update the docs describing the behaviour first.
That's the spec. Then a failing test that encodes it, where the
behaviour is a script's. Then implement until it passes. Then refine
the docs with what you learned. A skill's behaviour has no unit test;
its spec is the loop in [`docs/plan.md`](plan.md) § 5 and its own
`SKILL.md`, and its test is an eval (P2) or, until then, a run against
the Rallly clone written up in the checkpoint's plan.

**Architecture and infrastructure**: write the ADR
([`docs/decisions/`](decisions/)) before implementing. Then implement.
Then update the ADR with what implementation taught you.

**Write an ADR only when all three hold:** it affects more than the
file you're editing, you'd have to re-derive it if you forgot, and a
reasonable person could have chosen differently. Everything else
belongs in a commit body.

**Confirm the mechanism first.** The plan rests on a handful of Claude
Code behaviours the docs do not spell out (§ 3 and § 7 name them:
plugin hooks firing in every session in a directory, a skill starting
a Monitor, the data-directory variable's reach). A sub-scope that
builds on one of these starts by confirming it in a scratch setup and
recording the result in the checkpoint's plan, before any code depends
on it. Stop and ask when the answer is no.

## Pull requests

One issue → one branch → one PR. Focused PRs are a hard requirement; a
PR spanning a spec, the toolkit, and the skills at once cannot be
reviewed properly.

If a single PR would be too large (the diff crosses layers, or runs
past a few hundred reviewable lines) build a **base-chained stack**:
slice by dependency layer, branch each slice off the one beneath it,
open with `--base <branch-below>`, and drive each slice's review to
settlement before writing the next. Upper layers get written against
reviewed contracts.

**Never use GitHub's native stacked PRs.** Base chaining is how this
repo stacks.

PR bodies carry `Closes #N`, a summary of what and why, and a test
plan.

Every push that changes behaviour gets a local code review first: a
sub-agent on the Opus model over the outgoing diff, against
[`REVIEW.md`](../REVIEW.md), the plan, and the ADRs, and the review's
real findings are fixed before the push. The rule and its calibration
are in [`CLAUDE.md`](../CLAUDE.md) § Rules.

### The gate

Before any push, each checked by its own exit status, never through a
pipe that masks it:

- `shellcheck` over every shell script in the repository (`bin/`,
  tests, the workflow skill's script).
- The test runner under `plugins/rolling/tests/`, which builds scratch
  repositories in a temporary directory and runs each `bin/` script
  against them.
- `claude plugin validate <path>` for each plugin directory and for
  the marketplace root.

CI runs the same three on every PR and on `main`. The exact commands
live in [`ci.yml`](../.github/workflows/ci.yml) once P1a's toolkit
sub-scope lands them; copy from there rather than from memory. Evals
(`claude plugin eval`) join the gate in P2.

### Merging

Merge commits to `main`, never squash. A squash rewrites the history
every upper layer of a stack descends from, so each layer above it
conflicts and needs a rebase before it can merge. Stacks are common
here, so the repository should allow only merge commits; the branch's
own commits, with the bodies this repository asks for, are the history.
GitHub deleting the head branch on merge is what retargets the next
layer of a stack to `main`, so that setting stays on.

## Commit messages

Write commit bodies you'd want a new hire to learn from: explain why,
not just what. This isn't only style: Rolling Start builds tasks from
git history, and this repository is meant to become its own instance
once it has something to teach. A `wip` commit is a lesson we can't
teach.
