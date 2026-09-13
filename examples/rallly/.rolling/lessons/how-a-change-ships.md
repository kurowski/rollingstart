---
title: How a change ships here
region: platform
depth: orientation
mode: direct
requires: [local-dev-setup]
assumes: [typescript, react, git]
---

The rules a maintainer will hold your first pull request to, and where
each one is enforced. Most of them are in `CLAUDE.md`; this lesson has
you find the mechanism behind each so they stop being lore.

The feature folder is the unit of organisation. `features/<domain>/`
holds a closed set of files (`data.ts`, `loaders.ts`, `mutations.ts`,
`actions.ts`, `schema.ts`, `types.ts`, `ability.ts`, `constants.ts`,
`utils.ts`, `client.tsx`, `service.ts`, `components/`) and nothing else;
`scripts/check-feature-structure.mjs` and `check-feature-cycles.mjs`
enforce it as `pnpm check:structure`. Reads go in `data.ts`, writes in
`mutations.ts`, and the only things allowed to touch `@rallly/database`
are those two. Layering (`app → features → components → lib`) is a lint
rule: `apps/web/biome.json` `noRestrictedImports`, one override per
directory, each with a message that explains itself.

Writes are server actions, not tRPC. `apps/web/src/lib/safe-action/
server.ts` builds `actionClient` → `authActionClient` →
`adminActionClient`; `features/billing/actions.ts` is the reference.
`apps/web/src/trpc/trpc.ts` still defines the procedure ladder
(`publicProcedure` … `proProcedure` … `spaceOwnerProcedure`) and the
poll router still has mutations in it, but `CLAUDE.md` freezes that
surface: reads only, no new mutations.

Tests: `.test.ts` is Vitest and co-located; `.spec.ts` is Playwright
under `apps/web/tests/`. Lint and format are Biome only (`biome.json`,
2-space, 80 columns, double quotes) plus two GritQL plugins. Commits are
gitmoji with the PR number at the end. Strings go through `Trans` and
`apps/web/public/locales/en/app.json`; `pnpm i18n:scan` adds keys and
does not overwrite existing English, which is what `i18n:sync` is for.

This is a `direct` lesson: the learner directs a coding agent over as
many turns as it takes, briefing, steering, asking for the checks, and
reviewing what comes back until they would merge. The rules above are
what a good brief names up front, what good steering catches when the
agent drifts, and what a good review sends back.

Situations for the tutor to present: `aab791da` (#3235) as a symptom, a
password manager popping up on a field that collects someone else's
details, with ten inputs already opted out of one manager by hand; or
`f58b281b` (#3180) as a user's request for a small feature that has to
touch every layer. Mistakes worth watching for: a shared helper placed in
the wrong layer (in `components/` when `packages/ui` was the home, or
the reverse), a `helpers.ts` or `index.ts` barrel in a feature folder,
a hardcoded English string, a write added to the frozen tRPC router
instead of a server action.

## Rubric

- The opening brief, or the steering that followed it, says where the
  change belongs (which layer, which feature folder) and which checks
  must pass, so the agent could not plausibly put it in the wrong
  place and call it done; and the learner asked for the repo's checks
  before accepting.
- The review catches a placement or layering mistake, a banned file
  name, or a write on the wrong surface, and names the file that
  enforces the rule it broke.
- The review says what would block a merge and what is taste, and the
  learner can say why a new write is a server action and where the old
  way still lives.
