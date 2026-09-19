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
declares neither, the tutor builds the task from this page, and the
verifier is the map's own commands. A task is provable only with a
check that fails before the work is done, so in an environment that is
already set up the tutor adds a smoke test along a small seam (a
one-line fix with its unit test, shown), and the setup steps are
confirmed rather than performed.

In this environment the services (postgres, redis, an S3 stand-in, a
mail catcher, all declared in `docker-compose.dev.yml`) are a
precondition of this lesson, not a step in it: they are brought up from
outside the toolchain before the lesson starts, and `docker` is not
available inside. The tutor will not ask you to start them. If a
command fails because a service is unreachable, that is reported as
such, and the environment's owner fixes it.

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
- `apps/web/.env.sample` ships `SECRET_PASSWORD` empty and the build's
  env validation rejects that; fill it in. `DATABASE_URL`, `SMTP_HOST`,
  `S3_ENDPOINT`, and `KV_REST_API_URL` name where the services are;
  the samples say `localhost`, and a contained toolchain reaches them
  by service name instead.
- `pnpm db:generate` must run before `pnpm type-check` or `pnpm
  test:unit` in `apps/web`, because the generated Prisma client
  (`packages/database/generated/prisma/`, per `schema.prisma`'s
  `output`) is what the types import. CI does the same
  (`.github/workflows/ci.yml`).
- Unit tests do not need postgres: `apps/web/src/test/setup.ts` mocks
  `@rallly/database`. `pnpm db:reset` and `pnpm db:seed` do, and so do
  integration tests (`apps/web/.env.test`).
- `pnpm check` lints the whole tree and will fail on a file your editor
  or agent left in it (`.claude/settings.local.json` is the usual one);
  that is not a problem with your setup. Scope it with a path when
  that happens.

The task's verifier is a fast subset of the map's commands
(`typecheck-web`, `lint` on a folder, `structure`, and one scoped
`test-*`); you run the full `test` and `build` yourself and show the
tutor the tail of each. The tutor may not run any of the setup for you
and may not fix your environment; it may tell you what a failure means.

## Rubric

- `typecheck-web`, `lint`, and `structure` pass in the verifier, and
  the learner has shown `test` and `build` passing.
- The learner can say, without looking, what `pnpm db:generate` does and
  why it comes before the type check.
- The learner can name what the services provide, which of the map's
  commands and operations need them, and how the app is told where
  they are.
