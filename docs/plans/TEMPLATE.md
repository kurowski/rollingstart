# P{N}{x}: {Title}

> The plan's entry is [`docs/plan.md`](../plan.md) § 7, P{N}{x}. This
> file is the tracker for the checkpoint. Each PR flips its own
> sub-scope from `[PENDING]` to `[COMPLETE]`. When the whole checkpoint
> ends, a retrospective is appended.

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

A sub-scope is a paragraph: goal, branch, dependencies, and a
done-when a reviewer can check in a line or three. Detail lives in the
artifact it describes (a spec, a script's header comment, a skill),
and the sub-scope points at it once it exists. A contract drafted
before its artifact may sit under the paragraph until the slice lands,
and that slice's PR replaces it with a pointer.

### {N}{x}.1 — {Title} [PENDING]

Goal in a sentence. Branch `p{N}{x}.1/{slug}`; depends on nothing, or
`{N}{x}.y`. Done when: outcomes, not file lists, each one something a
reviewer can check.

---

### {N}{x}.2 — {Title} [PENDING]

...

## Explicitly deferred

What is out of scope for this checkpoint, and why, so it isn't
re-litigated mid-implementation.

## Verification

End-to-end criteria for the checkpoint as a whole. The plan's own exit
criterion is the floor.
