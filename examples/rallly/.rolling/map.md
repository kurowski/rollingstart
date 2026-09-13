---
name: Rallly
mode: write
commands:
  build: pnpm build
  typecheck: pnpm type-check
  test: pnpm test:unit
  lint: pnpm check
  structure: pnpm check:structure
  test-web: pnpm --filter @rallly/web test:unit
  test-billing: pnpm --filter @rallly/billing test:unit
  test-emails: pnpm --filter @rallly/emails test:unit
  integration: pnpm --filter @rallly/web test:integration
operations:
  reset-db: pnpm db:reset --force
  seed-db: pnpm db:seed
  apply-migrations: pnpm db:deploy
  regenerate-client: pnpm db:generate
destructive:
  - reset-db
---

# Rallly

A scheduling app: someone creates a poll with candidate dates, invites
people, they vote, and the host books the winner. A pnpm/turbo monorepo:
Next.js 16 App Router in `apps/web`, Prisma in `packages/database`,
tRPC for reads, server actions for writes, React Email in
`packages/emails`, Stripe in `packages/billing`. Every claim on this map
is checked against the checkout at `aab791da` (main on 2026-09-09).

The commands above are what a task's verifier may select. `test` runs
every unit suite through turbo; the `test-*` commands scope to one
workspace and pass a file path straight to vitest (`test-web
src/features/poll/mutations.test.ts`), which is what a task should use.
`integration` runs Playwright and needs the stack from
`docker-compose.dev.yml` up; give it one spec, never the suite.
`apps/web` needs `regenerate-client` before `typecheck` or any `test-*`.

In this example's environment, the services Rallly needs
(`docker-compose.dev.yml`: postgres, redis, an S3 stand-in, a mail
catcher) are managed outside the toolchain: they are up before a lesson
starts, and `docker` is not available where the toolchain runs. So the
lessons here do not have the learner start, stop, or inspect them. A
team that develops on bare machines would write this differently, with
`pnpm docker:up` as a step in the setup lesson; that is the author's
call. What does not vary: the tutor never brings services up, and a
command that fails because one is unreachable is reported as an
environment fault, not fixed.

Read `CLAUDE.md` at the repo root before anything else: it is the
maintainers' own account of how work is done here, and the lessons
below assume you have.

## Regions

- **polls** — the product. The poll, its options, participants, votes,
  invites, and activity timeline; creating, voting, closing, booking,
  deleting. `apps/web/src/features/poll/`, the frozen legacy router
  `apps/web/src/trpc/routers/polls.ts` and `polls/participants.ts`, the
  schema in `packages/database/prisma/models/poll.prisma`, the pages
  under `apps/web/src/app/[locale]/invite/[urlId]/` and
  `(optional-space)/poll/[urlId]/`.
- **billing** — Stripe subscriptions, the hobby/pro tier on a space, the
  pay wall, the webhook. `apps/web/src/features/billing/`,
  `packages/billing/`, `packages/database/prisma/models/billing.prisma`,
  `apps/web/src/app/api/stripe/`.
- **platform** — everything the other two stand on: the feature-folder
  layout and its lint-enforced layering, the tRPC procedure ladder and
  the server-action clients, Better-Auth, email templates and their
  i18n, feature flags and instance policy, the house-keeping cron.
  `apps/web/src/lib/`, `apps/web/src/trpc/trpc.ts`,
  `apps/web/src/lib/safe-action/`, `packages/emails/`,
  `apps/web/src/lib/feature-flags/`.

## Suggested course

Everyone starts with the two platform lessons, in this order: without
them nothing else can be run or shipped.

1. platform, `orientation`: `local-dev-setup`, `how-a-change-ships`
2. polls, `working`: `poll-data-model`, `poll-lifecycle`
3. billing, `working`: `billing-and-tiers`

A learner here for billing can go 1 → 3 and skip polls entirely; the
billing lesson requires only the opening two. A learner here for the
product should take polls at `working` before billing, since the pay
wall gates poll features. Nobody needs `deep` in the first fortnight.

## Corpus

Exemplary, copy the shape of:

- `apps/web/src/features/poll/` — the feature folder as the maintainers
  want every feature to look: `data.ts` reads, `mutations.ts` writes,
  `actions.ts` the server actions that call them, `schema.ts`,
  `loaders.ts`, `components/`. The closed file set and the layering are
  enforced by `pnpm check:structure` and `apps/web/biome.json`.
- `apps/web/src/features/billing/actions.ts` — a server action built on
  `authActionClient` with `.metadata({ actionName })`, the write path
  new code uses.
- `packages/emails/src/templates/poll-invite.tsx` — an email template:
  props type with `locale` and `chrome`, `createEmailI18n`, the
  `send…Email` export.
- `apps/web/src/features/billing/utils.ts` — `resolveSpaceTier`, the one
  place the tier rule is derived.

Legacy, read but do not copy:

- `apps/web/src/trpc/routers/polls.ts` and `polls/participants.ts` —
  the frozen legacy transport. Reads still live here; new writes do
  not. The old `make`/`modify`/`book` mutations are how it used to be
  done.
- `apps/web/src/components/environment.tsx` (`IfSelfHosted`) — a
  shrinking set, per `CLAUDE.md`; use feature flags and instance policy.

Pull requests that show how work is done here:

- #3191 `af3d9273` — a ten-line fix with the integration test that
  proves it and a one-line schema comment.
- #3180 `f58b281b` — a small feature end to end: action, mutation,
  schema, component, locale string, spec.
- #3204 `dd4833d3` — a billing change with a clean unit-test seam in
  `packages/billing/src/pricing.test.ts`.

Definition of ready, before a pull request:
`pnpm check:fix && pnpm type-check && pnpm test:unit && pnpm check:structure`,
and a gitmoji subject ending in the PR number (`🐛 Fix … (#3191)`).

## Mistakes agents make here

The ways an agentic change to this repo goes wrong. What the learner is
taught to catch in `direct` lessons, and what the tutor reads an
agent's change against at the end of one.

- Adds a mutation to `apps/web/src/trpc/routers/` instead of a server
  action in `features/<x>/actions.ts` calling `features/<x>/mutations.ts`.
  `CLAUDE.md` freezes tRPC for writes; the old router makes it look
  normal.
- Imports `@rallly/database` outside `features/**/{data,mutations}.ts`,
  or a feature's `data.ts` from a page under `app/`. Biome's
  `noRestrictedImports` overrides in `apps/web/biome.json` catch it;
  the agent often does not run `pnpm check`.
- Creates `helpers.ts`, `hooks.ts`, `queries.ts`, or an `index.ts`
  barrel inside a feature folder. Banned names; `pnpm check:structure`
  fails.
- Hardcodes an English string in a component instead of `Trans`/`t`
  with a key in `apps/web/public/locales/en/app.json`; or edits an
  existing key's English and runs `i18n:scan`, which does not overwrite.
- Names a unit test `.spec.ts` (Playwright picks it up, Vitest ignores
  it) or an integration test `.test.ts`.
- Asserts against the `@rallly/database` mock instead of the behaviour
  (see `features/poll/mutations.test.ts` for the right shape).
- Writes timezone-naive date code. `apps/web/vitest.config.mts` pins
  `TZ` to `Asia/Kathmandu` on purpose, and `biome-plugins/
  no-raw-datetime-formatting.grit` bans raw formatting.
- Makes a status transition non-idempotent (`closePoll` guards with
  `status: { not: "closed" }`) or forgets `recordPollActivities`, so
  the timeline misses the event.
- Changes a Prisma model under `packages/database/prisma/models/`
  without a migration, or without `pnpm db:generate`, so the type check
  fails in ways that read as bugs in the code; or drops a column in the
  same release as the code that stops writing it (this repo splits
  those: see the participant-token migrations of 2026-09-04 to 09-06).
- Derives "is this space pro" anywhere but `resolveSpaceTier`, so
  self-hosted instances lose features.
- Rate-limits or gates a new procedure with the wrong rung of the ladder
  in `apps/web/src/trpc/trpc.ts` (`publicProcedure` where
  `privateProcedure` was meant), or skips
  `createRateLimitMiddleware` on a public write.
