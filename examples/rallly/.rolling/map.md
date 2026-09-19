---
name: Rallly
mode: write
commands:
  build: pnpm build
  typecheck: pnpm type-check
  typecheck-web: pnpm --filter @rallly/web type-check
  typecheck-emails: pnpm --filter @rallly/emails type-check
  test: pnpm test:unit
  lint: pnpm exec biome check
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

The commands above are what a task's verifier may select, and the
scoped ones are what a task should use. `test` runs every unit suite
through turbo; the `test-*` commands scope to one workspace and pass a
file path, or a fragment of one, straight to vitest (`test-web
src/features/poll/invite/utils.test.ts`). `typecheck` runs every
workspace's `tsc`; `typecheck-web` and `typecheck-emails` run one, in
about fifteen seconds and two. `lint` is Biome with a path appended
(`lint apps/web/src/features/poll`); the whole-tree form developers
run by hand is `pnpm check`, and it is not on the list because it also
checks whatever an editor or an agent has dropped in the tree
(`.claude/settings.local.json`, say, which Biome does not know is
ignored). `structure` is the feature-folder check, whole tree, under a
second. `integration` runs Playwright, needs the stack from
`docker-compose.dev.yml` and a browser, and takes one spec, never the
suite; in this example's environment there is no browser, so a task
proved here uses a unit test. `apps/web` needs `regenerate-client`
before `typecheck-web` or any `test-*` after a schema change, and a
task cut from before one (`packages/database/prisma/` in `git log`
between the fix and the pin) names it as its `setup:` operation, with
the reverse run when the learner returns.

Read `CLAUDE.md` at the repo root before anything else: it is the
maintainers' own account of how work is done here, and the lessons
below assume you have.

## Environment

The services Rallly needs (`docker-compose.dev.yml`: postgres, redis,
an S3 stand-in, a mail catcher) are managed outside the toolchain in
this example's environment: they are up before a lesson starts, and
`docker` is not available where the toolchain runs. So the lessons
here do not have the learner start, stop, or inspect them. A team that
develops on bare machines would write this differently, with `pnpm
docker:up` as a step in the setup lesson; that is the author's call.
What does not vary: the tutor never brings services up, and a command
that fails because one is unreachable is reported as an environment
fault, not fixed.

Unit tests need no service: `apps/web/src/test/setup.ts` mocks
`@rallly/database`, and `packages/emails` renders to a string. The
database operations, the integration specs, and `pnpm dev` need
postgres; a failure in any of those that reads as a connection refused
is the environment, not the code.

## Regions

- **polls** — the product. The poll, its options, participants, votes,
  invites, and activity timeline; creating, voting, closing, booking,
  deleting. `apps/web/src/features/poll/` (with `invite/` and
  `activity/` beneath it), the frozen legacy router
  `apps/web/src/trpc/routers/polls.ts` and `polls/participants.ts`, the
  schema in `packages/database/prisma/models/poll.prisma`, the pages
  under `apps/web/src/app/[locale]/invite/[urlId]/` and
  `(optional-space)/poll/[urlId]/`, and the house-keeping cron that
  runs the lifecycle's tail.
- **billing** — Stripe subscriptions, the hobby/pro tier on a space, the
  pay wall, the webhook. `apps/web/src/features/billing/` (with
  `webhook/` beneath it), `packages/billing/`,
  `packages/database/prisma/models/billing.prisma`,
  `apps/web/src/app/api/stripe/`.
- **platform** — everything the other two stand on: the feature-folder
  layout and its lint-enforced layering, the tRPC procedure ladder and
  the server-action clients, Better-Auth, email templates and their
  i18n, feature flags and instance policy. `apps/web/src/lib/`,
  `apps/web/src/trpc/trpc.ts`, `apps/web/src/lib/safe-action/`,
  `packages/emails/`, `apps/web/src/lib/feature-flags/`,
  `apps/web/src/features/instance-policy/`.

## Suggested courses

Everyone starts with the two platform lessons, in this order: without
`local-dev-setup` nothing runs, and without `how-a-change-ships`
nothing ships. Both are `write` lessons, and the second hands you its
test. Everything else requires them.

### Generalist

1. platform, `working`: `local-dev-setup`, `how-a-change-ships`, then
   `procedures-and-actions`, `emails-and-i18n`, and `flags-and-policy`
   in whatever order the work brings them up
2. polls, `working`
3. billing, `working`

For someone who will work across the product. The three platform
`working` lessons are each a single change with a held test; take
`procedures-and-actions` before any poll lesson if tRPC and server
actions are new to you. Nobody needs `deep` in the first fortnight.

### Product engineer

1. platform, `orientation`: `local-dev-setup`, `how-a-change-ships`
2. polls, `working`: `poll-data-model`, then
   `invites-and-participants` and `poll-lifecycle`

For someone joining to work on polls. The poll lessons lean on
`procedures-and-actions` (the frozen router and the action clients) and
`emails-and-i18n` (invites and notifications send mail); take platform
at `working` later if either keeps coming up, or ask for a detour when
it does.

### Billing engineer

1. platform, `orientation`: `local-dev-setup`, `how-a-change-ships`
2. billing, `deep`: `billing-and-tiers`, then `stripe-webhook`

Skips polls entirely; the billing lessons require only the opening
two. The tier rule (`resolveSpaceTier`) sits where billing meets
instance policy, so `flags-and-policy` at platform `working` is worth
adding if self-hosted behaviour is part of the job. Take polls at
`orientation` later if the pay wall's gating of poll features starts to
matter.

## Corpus

Exemplary, copy the shape of:

- `apps/web/src/features/poll/` — the feature folder as the maintainers
  want every feature to look: `data.ts` reads, `mutations.ts` writes,
  `actions.ts` the server actions that call them, `schema.ts`,
  `loaders.ts`, `components/`, and sub-concerns as subdirectories
  (`invite/`, `activity/`) with the same vocabulary. The closed file
  set and the layering are enforced by `pnpm check:structure` and
  `apps/web/biome.json`.
- `apps/web/src/features/poll/invite/actions.ts` — a server action built
  on `authActionClient` with `.metadata({ actionName })`, a rate-limit
  middleware, an access check against the database, and a mutation
  call; `features/billing/actions.ts` is the same shape with CASL.
- `apps/web/src/features/poll/mutations.ts` and `mutations.test.ts` — a
  mutation that takes explicit parameters and returns a result object,
  and a unit test against the mocked database that asserts the
  behaviour (what was updated, under which scope), not the mock.
- `packages/emails/src/templates/poll-invite.tsx` — an email template:
  a props type with `locale` and `chrome`, `createEmailI18n`, `t` with a
  `defaultValue`, `TransWithoutContext` with both `t` and `i18n`, and
  the `send…Email` export built on `sendRenderedEmail`.
- `apps/web/src/features/billing/utils.ts` — `resolveSpaceTier`, the one
  place the tier rule is derived; `features/instance-policy/utils.ts`,
  `deriveInstancePolicy`, is the same idea for policy.
- `packages/ui/src/lib/password-manager-ignore.ts` — a cross-app
  constant in its right home, exported from `packages/ui/src/index.ts`.

Legacy, read but do not copy:

- `apps/web/src/trpc/routers/polls.ts` and `polls/participants.ts` —
  the frozen legacy transport. Reads still live here; new writes do
  not. The old `make`/`modify`/`book` mutations and the participant
  `add`/`update`/`delete` are how it used to be done.
- `apps/web/src/components/environment.tsx` (`IfSelfHosted`) — a
  shrinking set, per `CLAUDE.md`; use feature flags and instance policy.
- `apps/web/src/lib/dayjs.ts` — calendar arithmetic only; every
  user-facing date goes through `lib/datetime/`.

Pull requests that show how work is done here:

- #3235 `aab791da` — a cross-layer fix: a constant in `packages/ui`,
  exported, spread into eleven inputs, one unit test tightened, one
  paragraph added to `CLAUDE.md`.
- #3191 `af3d9273` — a ten-line fix with the integration test that
  proves it and a one-line schema comment.
- #3180 `f58b281b` — a small feature end to end: action, mutation,
  schema, component, locale string, spec.
- #3178 `3011b1ad` — a feature whose one pure helper got the unit test
  and whose UI got the spec.
- #2808 `9f52dbe7` — a write moved off the frozen router: action,
  mutation with a unit test, schema, the router entry deleted.
- #3157 `d374ed48` — a rule derived in one place (`isSpaceBrandingActive`)
  and used from five, with the unit test on the rule.
- #3204 `dd4833d3` — a billing change with a clean unit-test seam in
  `packages/billing/src/pricing.test.ts`.
- #3147 `95979adf` — the refactor that created `instance-policy/` and
  `resolveSpaceTier`; read its `CLAUDE.md` hunk for the rule it set.

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
- Puts a cross-app constant or component under `apps/web/src/components/`
  (or a feature) when `packages/ui` is its home, or the reverse; the
  admission test in `CLAUDE.md` is "could this ship in a different
  product?".
- Hardcodes an English string in a component instead of `Trans`/`t`
  with a key in `apps/web/public/locales/en/app.json`; or edits an
  existing key's English and runs `i18n:scan`, which does not overwrite.
  In an email, uses the client `Trans` or a shared i18next instance
  instead of `createEmailI18n` and `TransWithoutContext` with `t` and
  `i18n` both passed.
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
  self-hosted instances lose features; or reads a stored paid setting
  (`showBranding`, `hideAttribution`) without the resolved tier, so a
  downgraded space keeps what it stopped paying for (#3157).
- Forks on `isSelfHosted` in product code instead of adding a
  capability to `lib/feature-flags/config.ts` or a policy field to
  `features/instance-policy/utils.ts`. `CLAUDE.md` calls a new fork a
  review blocker.
- Rate-limits or gates a new procedure with the wrong rung of the ladder
  in `apps/web/src/trpc/trpc.ts` (`publicProcedure` where
  `privateProcedure` was meant), skips `createRateLimitMiddleware` on a
  public write, or authorizes an action against the session snapshot
  instead of the database.
- Writes `data-1p-ignore` inline on an input instead of spreading
  `passwordManagerIgnoreProps` from `@rallly/ui` (#3235).
- Makes a webhook handler that is not idempotent on redelivery, or
  that throws on a row that was cascade-deleted, so Stripe retries the
  event forever (#3001).
