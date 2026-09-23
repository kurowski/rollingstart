---
title: Procedures and actions
region: platform
depth: working
mode: write
requires: [how-a-change-ships]
assumes: [trpc, zod]
test: held
---

The two transports a request can arrive on, which one a new endpoint
goes on, and how each decides who is allowed to do what. Reads are
tRPC; writes are server actions; the rule is in `CLAUDE.md` ("`trpc/`
is frozen legacy transport") and this lesson has you move one write
across.

The tRPC side is a ladder of procedures in `apps/web/src/trpc/trpc.ts`,
each built on the one before by `.use()`: `publicProcedure` (line 79;
carries the maintenance guard, line 32, and a mutation-only session
guard that re-reads the user from the database, line 47),
`possiblyPublicProcedure` (83; public only while Quick Create is on),
`privateProcedure` (121; a non-guest user in the context),
`adminProcedure` (136; role checked against the database, not the
cookie cache, and the comment says why), `spaceProcedure` (154; an
active space and the content scope for this member), `proProcedure`
(175; `PAYMENT_REQUIRED` unless the resolved tier is pro), and
`spaceOwnerProcedure` (188). `createRateLimitMiddleware(name,
requests, duration)` (line 199) is what a public procedure wears
(`polls/participants.ts` line 288, `add`, is the shape). The routers
in `trpc/routers/` call `features/*/data.ts`; the poll router still
holds mutations (`make` at `polls.ts` line 95, `book` at 827, `close`
at 1275), and they are the frozen set: read to understand, never
extend.

The server-action side is `apps/web/src/lib/safe-action/server.ts`:
`actionClient` (metadata schema with `actionName`, the error handler
that maps `AppError` and Better-Auth's `APIError` to codes, a PostHog
flush in a `finally`, the maintenance check), `authActionClient` (a
`getCurrentUser()` read from the database, the CASL ability in the
context), `adminActionClient`, and its own `createRateLimitMiddleware`
keyed on `actionName` and user id. An action file is `"use server"`,
one `authActionClient.metadata({ actionName }).inputSchema(…).action(…)`
per export, authorization in the action (an access check like
`hasPollAdminAccess` or a CASL `ability.cannot(...)`, against database
state), and the work in a mutation that takes explicit parameters and
returns a result object. `features/poll/invite/actions.ts` and
`features/space/member/actions.ts` are the references; `features/poll/
actions.ts` (`setPollMutedAction`, line 8) with `mutations.ts`
(`setPollMuted`, line 183) is the smallest complete example, and it is
where this lesson's task comes from.

Two things a maintainer will check: that the authorization is on the
right rung (a mutation that only the owner may run is scoped by
`userId` in the mutation's `where`, not trusted from the client), and
that the mutation is testable without the request: `mutations.test.ts`
mocks `@rallly/database` and asserts what was updated under which
scope, not that a function was called.

Task source for the tutor: `9f52dbe7` (#2808) moved `toggleMuted` off
the poll router into `setPollMutedAction` and `setPollMuted`, with the
mutation's two cases added to `features/poll/mutations.test.ts`
(scoped to the owner and excluding deleted polls; `notFound` when no
row matches). Hold that test; its verifier line is `test-web
src/features/poll/mutations.test.ts`. Scope the task to
`apps/web/src/features/poll` and `apps/web/src/trpc/routers/polls.ts`;
verify with `lint` on those and `structure`. The brief says which
router entry is being retired and what the mutation is called and
returns, since the held test pins that; it does not say how the
action is built. The fix's parent is from July 2026, some way behind
the map's pin, so the type check does not belong in this task's
verifier (the unit tests, against the mocked client, need no setup
operation): run `typecheck-web` for the learner when they ask, after
`regenerate-client`, and read its output knowing the tree is older
than the toolchain. A seam that
fits the same lesson when a fresh task is wanted: any remaining
mutation in `trpc/routers/polls.ts` that a single owner-scoped
`updateMany` can express, moved the same way.

## Rubric

- The write is a server action on `authActionClient` with a metadata
  `actionName`, a Zod input schema in `schema.ts`, and the work in
  `mutations.ts`; the router entry is gone, not left beside it.
- The mutation takes the user id as a parameter, scopes the update by
  it (and by not-deleted), returns a result object rather than
  throwing for a missing row, and the learner's own test asserts that
  scope.

## Talk through

- For each rung of the procedure ladder, what it adds and where the
  same check lives on the action side; why the admin checks read the
  database rather than the session.
