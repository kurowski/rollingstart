# P{N}{x}: {Title}

> The plan's entry is [`docs/plan.md`](../plan.md) § 7, P{N}{x}. This
> file is the tracker for the checkpoint: sub-scopes flip from
> `[PENDING]` to `[COMPLETE]` as their PRs merge, and a retrospective
> is appended when the checkpoint ends.

## Context

What the previous checkpoint delivered. What this one delivers. The
end state: what is true when this checkpoint is done that isn't true
now.

## Key decisions

| Decision | Choice | Why |
|---|---|---|

A decision that would have to be re-derived if forgotten also goes to
`docs/plan.md` § 10, dated, when the checkpoint ends.

## Mechanisms to confirm first

Claude Code behaviours this checkpoint rests on that the docs do not
confirm, each with the sub-scope that must confirm it before building
on it, and the result once known.

| Mechanism | Sub-scope | Result |
|---|---|---|

## Sub-scopes

### {N}{x}.1 — {Title} [PENDING]

**Goal.** One sentence.

**Branch.** `p{N}{x}.1/{slug}`

**Depends on.** Nothing, or `{N}{x}.y`.

**Done when.** Outcomes, not file lists; each one something a reviewer
can check.

---

### {N}{x}.2 — {Title} [PENDING]

...

## Explicitly deferred

What is out of scope for this checkpoint, and why, so it isn't
re-litigated mid-implementation.

## Verification

End-to-end criteria for the checkpoint as a whole. The plan's own exit
criterion is the floor.
