---
title: Local dev setup
region: platform
depth: orientation
mode: write
requires: []
assumes: [pnpm, postgres]
---

Get Rallly's toolchain working against its services, the way
`CONTRIBUTING.md` says to, and prove it by making the map's commands
go green. This is the one lesson where the task is the environment:
there is no fix to revert and no test to hold or show, so the lesson
declares neither, and the tutor builds the task from this page.

In this environment the services (postgres, redis, an S3 stand-in, a
mail catcher, all declared in `docker-compose.dev.yml`) are a
precondition of this lesson, not a step in it: they are brought up from
outside the toolchain before the lesson starts. The tutor will not ask
you to start them. If a command fails because a service is
unreachable, that is reported as such, and the environment's owner
fixes it.

What you will have at the end: the dependencies installed, both `.env`
files filled in and pointing at the services wherever they are, the
Prisma client generated, the database migrated and seeded, and the
map's commands green.

Pointers:

- `CONTRIBUTING.md`, steps 1 to 7, skipping the one that starts the
  services and the portless proxy (the proxy is for the dev server's
  stable URL, not for any check on the map).
- `package.json` at the root: `packageManager` pins pnpm, `engines` pins
  Node 24 and `.npmrc` makes that strict. The root `scripts` block is
  the vocabulary every lesson uses: `db:generate`, `db:reset`, `check`,
  `check:structure`, `type-check`, `test:unit`.
- `apps/web/.env.sample` ships `SECRET_PASSWORD` empty (line 3) and the
  build's env validation rejects that; fill it in. `DATABASE_URL`
  (line 10), `SMTP_HOST` (17), `S3_ENDPOINT` (26), and `KV_REST_API_URL`
  (35) name where the services are; the samples say `localhost`, and a
  contained toolchain reaches them by service name instead.
  `packages/database/.env.sample` carries `DATABASE_URL` again (line
  2), for Prisma's own commands.
- `pnpm db:generate` must run before `pnpm type-check` or `pnpm
  test:unit` in `apps/web`, because the generated Prisma client
  (`packages/database/generated/prisma/`, per `schema.prisma`'s
  `output` on line 7) is what the types import. CI does the same
  (`.github/workflows/ci.yml`).
- Unit tests do not need postgres: `apps/web/src/test/setup.ts` mocks
  `@rallly/database`. `pnpm db:reset` and `pnpm db:seed` do, and so do
  integration tests (`apps/web/.env.test`).
- `pnpm check` lints the whole tree and will fail on a file your editor
  or agent left in it (`.claude/settings.local.json` is the usual one);
  that is not a problem with your setup. Scope it with a path when
  that happens.

## Confirming the state, step by step

An environment that is already set up is confirmed, not performed and
not quizzed about. Each step has a command or a file that shows it is
done; the learner runs the command or shows the file, and the tutor
reads the result. Nothing here is asked as a question.

- **Dependencies installed.** `pnpm install --frozen-lockfile` reports
  `Already up to date` (or `Done`) and `node_modules/` exists at the
  root and in each workspace.
- **Both `.env` files present and pointing at the services.** The four
  service lines and `SECRET_PASSWORD` in `apps/web/.env`, and
  `DATABASE_URL` in `packages/database/.env`, shown with their values:
  the learner reads them out, or greps for the five names. The values
  say where the services are; `localhost` with the compose ports, or a
  service name in a contained toolchain.
- **Prisma client generated.** `packages/database/generated/prisma/`
  exists and is newer than `packages/database/prisma/models/`. If in
  doubt, `pnpm db:generate` is idempotent and takes a second.
- **Database migrated.** `pnpm --filter @rallly/database exec prisma
  migrate status` reports the database schema is up to date. This
  needs postgres reachable at `DATABASE_URL`.
- **Database seeded.** The seed (`packages/database/prisma/seed.ts`)
  inserts a fixed set of users with `createMany`, `dev@rallly.co` first
  (`seed/data.ts` line 28), so a seed that has already run refuses a
  second time with a unique-constraint error. When the seed is run in
  this lesson, its own output (`✓ 5 users`, and so on down the list)
  is the confirmation.
- **The map's commands green.** `pnpm test:unit` and `pnpm build` at
  the root, run by the learner, with the tail of each shown; the
  verifier below covers the scoped ones.

## The task, and its verifier

A task is provable only with a check that fails before the work is
done, and in an environment that is already set up there is nothing
left to fail. So the exercise here is a smoke test along a small seam
beside the setup steps: a pure function of a few lines next to an
existing one, with its unit test shown, so that the learner's first
change in this repository is small and the whole pipeline (type check,
lint, test, structure) runs on something real. The seam is the
tutor's to choose; `apps/web/src/lib/` has several such functions with
tests beside them.

The verifier is these four lines and no others: `typecheck-web`;
`lint` on the seam's folder; `structure`; and `test-web` with the
seam's test, its path relative to `apps/web`. The tutor does not add a
check at `done` that the verifier did not run, and does not leave one
of these out.

Notes for the tutor: the task is built from this page, with the test
shown and committed into the starting state (`--here`); it is never a
reverted fix from history, however tempting one looks. The lesson's
own operations (`db:generate`, `db:reset`, `db:seed`) are the learner's
to run and are never a task's `setup:` line, and the tutor never runs
them for the learner. The tutor may not fix the environment; it may
say what a failure means.

## Rubric

- `typecheck-web`, `lint`, and `structure` pass in the verifier, and
  `test` and `build` pass in the learner's environment.
- The dependencies are installed, both `.env` files point at the
  services, the Prisma client is generated, and the database is
  migrated and seeded, whether performed in this lesson or confirmed
  the way the list above says.
- The seam's function is small, typed, and beside its test, and the
  test asserts behaviour, not implementation.

## Talk through

- What `pnpm db:generate` does and why it comes before the type check.
- What each service provides, which of the map's commands and
  operations need them, and how the app is told where they are.
