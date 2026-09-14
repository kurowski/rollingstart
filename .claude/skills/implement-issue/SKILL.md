---
name: implement-issue
description: Implement a refined GitHub issue following the docs-driven sequence — docs, failing test, implement, gate, refine docs, review, open PR.
---

Implement a refined issue, following the docs-driven sequence in
[`docs/workflow.md`](../../../docs/workflow.md).

## Inputs

An issue number or URL, and optionally a branch name. If no branch is
given, suggest one from the issue title in kebab-case, prefixed with
the sub-scope (`p1a.3/toolkit`).

**If no issue number was given**, suggest one rather than asking cold.
The likely answer is the next open sub-issue under whichever tracking
issue is In Progress on the active checkpoint's board:

```sh
gh project list --owner kurowski
gh project item-list <project-number> --owner kurowski --limit 100 --format json \
  --jq '.items[] | select(.content.type == "Issue") | select(.status == "In Progress" or .status == "Todo") | "\(.status)\t#\(.content.number)\t\(.content.title)"'
```

Read the candidate's body to confirm it has no undeclared dependency
on a sibling, then propose it.

## Process

### 1. Read the issue

```sh
gh issue view {number} --comments
gh api repos/kurowski/rollingstart/issues/{number}/sub_issues -q '.[] | "#\(.number) [\(.state)] \(.title)"'
```

`--comments` is load-bearing: refinement decisions and scope notes
often land as comments. Also read the **parent tracking issue's**
comments; fold-ins are supposed to live in bodies, but this is the
backstop for the ones that don't.

**Sweep for closeout debt before starting new work.** A parent's
closeout (step 7) waits on a merge that often happens with no session
running, so nothing fires it. The sweep makes the trigger
self-healing: any open issue whose sub-issues are all closed is a
pending closeout, and it comes before branching for anything new (with
the usual approvals).

```sh
for n in $(gh issue list --state open --json number --jq '.[].number'); do
  gh api "repos/kurowski/rollingstart/issues/$n/sub_issues" \
    --jq "select(length > 0) | select(all(.[]; .state == \"closed\")) | \"#$n closeout pending\"" 2>/dev/null
done
```

**If the issue has linked sub-issues it is a tracking issue.** Do not
implement it in one branch. Take the first open sub-issue that has its
dependencies satisfied, and confirm the choice with the user before
branching.

### 2. Read context

- [`CLAUDE.md`](../../../CLAUDE.md): conventions and the architectural
  seams
- [`REVIEW.md`](../../../REVIEW.md): know what review will check
  before starting
- The checkpoint's plan in [`docs/plans/`](../../../docs/plans/),
  including its "mechanisms to confirm first"
- Relevant ADRs in [`docs/decisions/`](../../../docs/decisions/)
- For a skill or a script the spike prototyped: the spike's version
  under [`spike/`](../../../spike/) and what
  [`spike/NOTES.md`](../../../spike/NOTES.md) says went wrong with it.
  The spike is a record to learn from, not code to copy; its scripts
  assumed the learner's state was in the tree

### 3. Verify board membership: a precondition, not a formality

Committing to implement an issue is committing to its checkpoint, and
the board must show it. This check is mechanical and runs regardless
of how the decision to implement was reached.

```sh
gh issue view {number} --json projectItems,milestone
```

- **`projectItems` non-empty**: already on a board, nothing to do.
- **Empty**: route by the issue's `P{N}{x}: …` milestone. List boards
  including closed ones (`gh project list --owner kurowski --closed`)
  and match the checkpoint to the board titled `… P{N}{x} …`.
  - Board open → `gh project item-add <num> --owner kurowski --url <issue-url>`
  - Board closed because the checkpoint shipped → this is tail
    follow-up work. The milestone alone is sufficient. **Proceed and
    say so; don't stop to ask.**
- **Stop and ask only when the checkpoint is genuinely ambiguous**: no
  milestone and no way to infer one, or a closed board that signals
  future work pulled forward.

### 4. Branch, and decide the PR shape first

```sh
git checkout main && git pull origin main && git checkout -b {branch}
```

**If one PR would be too large to review** (the diff crosses layers, or
runs past a few hundred reviewable lines) plan a **base-chained stack**
instead:

- Slice by dependency layer, each independently reviewable
- Build **serially**: open the first slice's PR and drive its review to
  settlement before writing the next, so upper layers are written
  against reviewed contracts
- Branch each slice off the one beneath it and open with
  `--base <branch-below>`. GitHub retargets to `main` automatically as
  bases merge, and it is the repository's delete-head-branch-on-merge
  setting doing that. Deleting a merged base by hand closes the PRs
  stacked on it instead, so leave the deletion to the setting
- Hand the whole stack over when every slice has settled; merge
  bottom-up, with merge commits, because a squash rewrites the history
  the layer above descends from and strands it

**Never use GitHub's native stacked PRs.** Do not run
`gh stack init/add/submit`. Base chaining keeps `gh pr merge` available
and is how this repo stacks.

### 5. Docs-driven implementation

**Confirm the mechanism first**, if the sub-issue names one. In a
scratch setup under the session's scratchpad, never a real checkout:
a throwaway git repository, a throwaway plugin directory, a `claude`
session started there. Record what happened in the checkpoint's plan
under "Mechanisms to confirm first". If the answer is no, stop and
ask; the plan may need to change shape.

**For user-visible behaviour:**

1. **Docs**: write or update the documentation describing the
   behaviour. That is the spec. Commit: `docs: describe {behaviour}`
2. **Failing test**: for a `bin/` script, a test under
   `plugins/rolling/tests/` that builds a scratch repository and
   encodes the expected behaviour. It must fail now. Commit:
   `test: add failing test for {behaviour}`. A skill has no unit test;
   its check is a run against the Rallly clone, written up in the
   plan, and an eval from P2 on
3. **Implement**: build until it passes, following existing patterns.
   POSIX `sh` for scripts; Node without dependencies only for hook
   handlers. Logical commits with real bodies
4. **The gate**: `shellcheck` over every shell script, the test
   runner, and `claude plugin validate` for each plugin and the
   marketplace, each by its own exit status
5. **Refine docs**: update with what implementation taught you

**For architecture and infrastructure:** the ADR (from `/refine-issue`
or written now) replaces step 1, and step 5 updates it with what was
learned.

### 6. Pre-push review, then open the PR

Before any push that changes behaviour, run the local review from
[`CLAUDE.md`](../../../CLAUDE.md) § Rules: spawn a code-review
sub-agent on the Opus model (`claude-opus-5`) over the outgoing diff
(`git diff main`, including anything uncommitted that will ship),
reviewing against [`REVIEW.md`](../../../REVIEW.md), the checkpoint
plan, and the relevant ADRs, and have it verify each finding before
reporting, with state-changing experiments confined to a scratch copy
under the session's scratchpad, per the rule. Verify the live tree
(status, log, local config) when the review returns. Fix the real
findings, re-run the gate, then push. A review-round fix is a push and
gets its own review.

One sub-issue → one branch → one PR. Never bundle.

```sh
git push -u origin {branch}
gh pr create --title "{title}" --body "Closes #{number}

## Summary
{what and why}

## Test plan
{how to verify}"
```

The PR closes the **sub-issue**, not the parent. Do not add the PR to
the board separately; the issue row already shows linked PRs.

**When this PR closes the parent's last open sub-issue, say so in the
body**: "Merging this completes the sub-issues of #{parent}; the parent
closeout (step 7) follows the merge." The merge often happens in the
GitHub UI with no session running; the marker makes the merge event
itself carry the reminder, and the sweep in step 1 is the backstop
when it doesn't.

Report the PR URL, then watch CI in the background and read the result
when it finishes. Never poll in a foreground loop.

```sh
gh run watch <run-id> --exit-status
```

### 7. Close out the parent, only if this was the last sub-issue

A sub-issue's PR closes only that sub-issue. After the PR **merges**
(not at open; the parent must not close while a sibling PR is
pending), check:

```sh
gh api repos/kurowski/rollingstart/issues/{parent}/sub_issues -q '.[] | "#\(.number) [\(.state)]"'
```

If all are closed:

1. **Verify the parent's end-to-end criteria** actually hold across
   the shipped sub-issues; they are distinct from any single
   sub-issue's
2. **Coherence sweep**: confirm deferred follow-ups were filed and
   linked rather than silently dropped, and that the plan and ADRs
   describe *shipped* reality. Grep for stale forward-references and
   fix them in the same closeout
3. **Tick the parent's verification checkboxes**
4. **Flip the plan's sub-scope heading** `[PENDING]` → `[COMPLETE]` in
   [`docs/plans/`](../../../docs/plans/). This is a small docs change:
   directly on `main`, its own PR, or folded into the next sub-scope's
   first PR. Ask which, and note it in the closeout
5. **Close the parent** with a summary: sub-issue → PR table,
   verification confirmation, and tracked deferrals

This is usually a separate turn, since it waits on the merge. Get
explicit approval before pushing the plan change and before closing.

## Important

- **Never commit or push without explicit approval.**
- **Before any push to GitHub, run the local pre-push code review.**
  The rule and its calibration live in
  [`CLAUDE.md`](../../../CLAUDE.md) § Rules. Read your own diff as a
  reviewer would first; it is cheaper than a CI round-trip and much
  cheaper than a review round.
- **Stop on surprises.** An unexpected incompatibility, a mechanism
  that does not behave as the docs say, or an uncovered design
  question means stop and ask; do not continue in a possibly wrong
  direction.
- **In-flight scope**: apply the three tests in
  [`docs/workflow.md`](../../../docs/workflow.md) (Small, Clearly
  related, Documented) before absorbing anything the issue didn't
  anticipate. When in doubt, file the follow-up.
- **Never write to `../rallly`.** It is the pinned reference. Tests
  build their own scratch repositories; the tutor runs in
  `../rallly-spike`.

## Output

- A branch with the implementation, or a base-chained stack for large
  scopes
- An open PR linked to the issue, CI green
- If this was the last sub-issue: the parent closed out and the plan
  marked complete
