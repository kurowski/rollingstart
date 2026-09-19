---
title: How a change ships here
region: platform
depth: orientation
mode: write
requires: [local-dev-setup]
assumes: [typescript, react, git]
test: shown
---

The rules a maintainer will hold your first pull request to, and where
each one is enforced. Most of them are in `CLAUDE.md`; this lesson has
you find the mechanism behind each so they stop being lore, by making
one small change that crosses the layers and running every check the
repository has on it.

The feature folder is the unit of organisation. `features/<domain>/`
holds a closed set of files (`data.ts`, `loaders.ts`, `mutations.ts`,
`actions.ts`, `schema.ts`, `types.ts`, `ability.ts`, `constants.ts`,
`utils.ts`, `client.tsx`, `service.ts`, `components/`) and nothing else;
`scripts/check-feature-structure.mjs` and `check-feature-cycles.mjs`
enforce it as `pnpm check:structure`. Reads go in `data.ts`, writes in
`mutations.ts`, and the only things allowed to touch `@rallly/database`
are those two. Layering (`app → features → components → lib`) is a lint
rule: `apps/web/biome.json` `noRestrictedImports`, one override per
directory, each with a message that explains itself. Above `apps/web`
sit the packages: `packages/ui` is where a component or constant goes
once it could ship in a different product (`CLAUDE.md`, "Directory
Structure"), exported by name from `packages/ui/src/index.ts` or as its
own subpath.

Writes are server actions, not tRPC. `apps/web/src/lib/safe-action/
server.ts` builds `actionClient` → `authActionClient` →
`adminActionClient`; `features/poll/invite/actions.ts` is the
reference. `apps/web/src/trpc/trpc.ts` still defines the procedure
ladder (`publicProcedure` … `proProcedure` … `spaceOwnerProcedure`) and
the poll router still has mutations in it, but `CLAUDE.md` freezes that
surface: reads only, no new mutations. `procedures-and-actions` is the
lesson on both.

Tests: `.test.ts` is Vitest and co-located; `.spec.ts` is Playwright
under `apps/web/tests/`. Lint and format are Biome only (`biome.json`,
2-space, 80 columns, double quotes) plus two GritQL plugins. Commits are
gitmoji with the PR number at the end. Strings go through `Trans` and
`apps/web/public/locales/en/app.json`; `pnpm i18n:scan` adds keys and
does not overwrite existing English, which is what `i18n:sync` is for.

This is a `write` lesson with the test shown: the tutor hands you a
failing unit test with the task, and the work is to make it pass in
the place the rules say the change belongs, then run the repository's
own checks (`pnpm check`, `pnpm type-check`, `pnpm check:structure`,
`pnpm test:unit`) before you say done. The point is the mechanics, not
the analysis; the tutor's review is about where you put things and
which check would have caught each alternative.

Task source for the tutor: `aab791da` (#3235). Password managers were
popping up on inputs that collect someone else's details (an invitee's
email, a confirmation phrase), and ten inputs had opted out of one
manager by hand with `data-1p-ignore`. The fix adds
`packages/ui/src/lib/password-manager-ignore.ts` (five vendor
attributes as one `as const` object), exports it from
`packages/ui/src/index.ts`, spreads it into the inputs, and tightens
the one unit test that already checked the attribute,
`apps/web/src/app/[locale]/(space)/settings/spaces/components/
leave-space-dialog.test.tsx`, to assert two of the new attributes. That
test is the one to bring forward with `--shown`; its verifier line is
`test-web leave-space-dialog.test.tsx` (vitest takes the file name as
a filter, since the full path holds brackets a verifier line cannot
carry). Scope the task to `apps/web/src` and `packages/ui/src`, and
verify with `typecheck-web`, `lint` on both, and `structure`. The brief
names the symptom and the two attributes the test wants; it does not
say where the constant lives, since deciding that is the lesson. The
fix's parent is one commit behind the map's pin.

## Rubric

- The test passes and every check on the map that the verifier runs is
  green; the learner ran `pnpm check`, `pnpm type-check`, and `pnpm
  check:structure` themselves before saying done.
- The constant lives where the admission test in `CLAUDE.md` puts it
  (`packages/ui`, since it could ship in another product), is exported
  the way that package exports things, and is spread rather than
  copied; the learner can name the file that would have failed had
  they put it in a feature folder or a `helpers.ts`.
- The learner can say why a new write here is a server action and
  where the old way still lives, and which of `.test.ts` and `.spec.ts`
  the test they were handed is and why.
