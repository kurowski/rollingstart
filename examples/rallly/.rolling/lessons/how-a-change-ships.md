---
title: How a change ships here
region: platform
depth: orientation
mode: write
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

Task sources for the tutor: `f58b281b` (#3180) is a complete small
feature that touches every layer in order; `aab791da` (#3235) applies a
convention across twelve files and is a good "find every place" task;
a task that introduces a banned file name or a layering violation and
has the learner make `structure` and `lint` pass is also fair.

## Rubric

- The change respects the feature-folder set and the layering rules,
  and `lint` and `structure` pass, without the tutor naming the rule
  first.
- The learner can point at the file that enforces each rule they were
  held to.
- The learner can say why a new write is a server action and where the
  old way still lives.
