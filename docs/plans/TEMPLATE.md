# P{N}{x}: {Title}

> Expanded plan for the `P{N}{x}: {Title}` checkpoint. The plan's entry
> is [`docs/plan.md`](../plan.md) § 7, P{N}{x}.
>
> This file is the drafting artifact. Its sub-scopes are copied
> verbatim into GitHub issues; its remaining content becomes the
> project board's README. After the checkpoint ships,
> `/milestone-endgame` appends a retrospective.

## Context

What the previous checkpoint delivered. What this one delivers. The
end state: what is true when this checkpoint is done that isn't true
now.

## Key decisions

| Decision | Choice | Why |
|---|---|---|

Anything meeting the ADR threshold gets a record in
[`docs/decisions/`](../decisions/) instead of a table row here.

## Mechanisms to confirm first

Claude Code behaviours this checkpoint rests on that the docs do not
confirm, each with the sub-scope that must confirm it before building
on it, and the result once known.

## Sub-scopes

### {N}{x}.1 — {Title} [PENDING]

**Goal.** One sentence.

**Branch.** `p{N}{x}.1/{slug}`

**Depends on.** Nothing, or `{N}{x}.y`.

**Acceptance criteria.**

- Stated as outcomes, not file lists; the implementor chooses the files
- Testable: someone else can confirm each one independently

**Verification.**

- [ ] What must be observed for this sub-scope to be done

---

### {N}{x}.2 — {Title} [PENDING]

...

## Explicitly deferred

What is out of scope for this checkpoint, and why. Naming it here
stops it being re-litigated mid-implementation.

## Verification

End-to-end criteria for the checkpoint as a whole, distinct from any
single sub-scope's. The closure sub-scope confirms these. The plan's
own exit criterion for the checkpoint is the floor.
