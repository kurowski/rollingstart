---
name: plan-milestone
description: Expand a checkpoint of the plan (P1a, P1b, …) into a plan document and set up GitHub tracking — project board, issues, milestone assignment. Use when starting a new checkpoint.
---

Expand a checkpoint of the plan into a working plan and set up its
GitHub tracking. "Milestone" is GitHub's word for the object that
carries the issues; the plan calls the same unit a checkpoint (P1a) or
a phase (P2). One milestone per checkpoint, titled `P{N}{x}: {Title}`.

## Inputs

Work out which checkpoint automatically:

1. Read [`CLAUDE.md`](../../../CLAUDE.md) § Status for the first
   unchecked checkpoint
2. Read [`docs/plan.md`](../../../docs/plan.md) § 7 for that
   checkpoint's scope and exit criterion
3. Confirm: "Next up is **P{N}{x}: {Title}**: {scope}. Exit criterion
   is {…}. Plan this one?"
4. Proceed only after the user confirms

The user may name a different checkpoint instead.

## Process

### 1. Read context

- [`docs/workflow.md`](../../../docs/workflow.md): how work happens
  here
- [`docs/plans/TEMPLATE.md`](../../../docs/plans/TEMPLATE.md): the
  required format
- [`docs/plan.md`](../../../docs/plan.md) §§ 3–5 and § 10: the layout,
  the formats, the loop and its enforcement table, and what has been
  decided; the plan must not contradict them
- [`docs/decisions/`](../../../docs/decisions/): anything decided since
  the plan
- The most recent plan in [`docs/plans/`](../../../docs/plans/), for
  style and depth
- The relevant risks in [`docs/plan.md`](../../../docs/plan.md) § 8: a
  plan that ignores a named risk is incomplete
- The mechanisms § 3 and § 7 say the docs do not confirm: each one the
  checkpoint rests on gets a "confirm first" step in the sub-scope that
  builds on it

### 2. Draft the plan

Write `docs/plans/p{N}{x}-{slug}.md` from the template:

- **Context**: what the previous checkpoint delivered, what this one
  delivers, the end state
- **Key decisions**, with rationale. Anything meeting the ADR threshold
  in [`docs/decisions/README.md`](../../../docs/decisions/README.md)
  gets an ADR instead of a table row
- **Mechanisms to confirm first**, each with the sub-scope that
  confirms it
- **Sub-scopes** under a `## Sub-scopes` H2, each an H3
  `### {N}{x}.{M} — Title [PENDING]` carrying a one-sentence goal,
  branch name, dependencies, acceptance criteria, and a verification
  checklist, separated by `---`
- **Explicitly deferred**, with reasons, so it isn't re-litigated
  mid-build
- **Verification**: end-to-end criteria for the checkpoint as a whole,
  with the plan's own exit criterion as the floor

Acceptance criteria are outcomes, not file lists. The implementor
picks the files.

Slice sub-scopes at natural dependency boundaries, each independently
reviewable: the gate passes, and it delivers something coherent. If
{N}{x}.2 needs {N}{x}.1 merged first, say so.

The plan file is the *drafting* artifact. Its content gets split across
the project board README and one issue per sub-scope, and
`/milestone-endgame` later rewrites this file into a retrospective, so
everything an implementor needs must reach the project and issues, not
just this file.

### 3. Present for review

Do **not** commit yet. Present the plan and iterate until the user is
satisfied.

### 4. Create the milestone and the project board

The milestone, if it does not exist yet (the repository does not
pre-create them):

```sh
gh api repos/kurowski/rollingstart/milestones -X POST -f title="P{N}{x}: {Title}" -f description="{one sentence}"
```

One board per checkpoint, under the maintainer's account:

```sh
gh project create --title "Rolling Start: P{N}{x} — {Title}" --owner kurowski
```

Note the project number.

### 5. Link the board to the repo

Without this it doesn't appear on the repo's Projects tab:

```sh
gh project link {project-num} --owner kurowski --repo kurowski/rollingstart
```

### 6. Set the board's description and README

Together these carry everything in the plan except the sub-scopes, so
the full plan is reflected in project + issues.

- **Description** (~255 chars): one sentence distilled from Context
- **README**: all plan content *except* `## Sub-scopes`, opening with a
  link back to the plan file

```sh
gh project edit {project-num} --owner kurowski \
  --description "..." \
  --readme "$(cat "$SCRATCH/p{N}{x}-readme.md")"
```

### 7. Create the sub-scope issues

```sh
.claude/skills/plan-milestone/scripts/create-issues.sh \
  docs/plans/p{N}{x}-{slug}.md \
  {N}{x} \
  {project-num}
```

The script resolves the `P{N}{x}: …` milestone (and errors if it is
missing), splits `## Sub-scopes` on `### {N}{x}.{M} —` headers, creates
one issue per sub-scope on the milestone, adds each to the board, and
prefixes each body with a link back to the plan section. On the way it
reflows hard-wrapped paragraphs into single lines: GitHub renders each
newline in an issue body as a hard break, so the plan file's wrapped
prose would otherwise render jagged.

**Full-fidelity rule**: sub-scope content is copied in full, reflowed
for issue rendering, never summarized or trimmed. An agent picking the
issue up in a future session must have everything it needs without
reading anything else.

Milestones carry no due dates. This is a side project; invented dates
rot in public.

### 8. Commit the plan

Get explicit approval, then commit.

## Output

- `docs/plans/p{N}{x}-{slug}.md`
- A linked project board with description and README
- One issue per sub-scope, all on the `P{N}{x}: …` milestone and the
  board

## Next step

The issues are verbatim plan copies; they have **not** been refined
into ready-to-build requirements. Point the user at
**`/refine-issue {first issue}`**, not `/implement-issue`. The order in
[`docs/workflow.md`](../../../docs/workflow.md) is `/plan-milestone` →
`/refine-issue` → `/implement-issue` → `/milestone-endgame`.
