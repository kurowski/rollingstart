---
title: Local dev setup
region: platform
depth: orientation
mode: write
requires: []
assumes: [pnpm, docker-compose]
---

Get Rallly running on your machine, the way `CONTRIBUTING.md` says to,
and prove it by making every command on the map go green. This is the
one lesson where the task is the environment. Rolling Start never brings
a stack up for you; a contributor here does it by hand, once.

What you will have at the end: pnpm via corepack, the dependencies
installed, both `.env` files filled in, the dev stack from
`docker-compose.dev.yml` up (postgres on 5450, redis, garage, mailpit),
the Prisma client generated, the database migrated and seeded.

Pointers:

- `CONTRIBUTING.md`, steps 1 to 7. Follow them literally.
- `package.json` at the root: `packageManager` pins pnpm, `engines` pins
  Node 24. `corepack enable` is enough for pnpm.
- `apps/web/.env.sample` ships `SECRET_PASSWORD` empty and the build's
  env validation rejects that; fill it in.
- `pnpm db:generate` must run before `pnpm type-check` or `pnpm
  test:unit` in `apps/web`, because the generated Prisma client is what
  the types import. CI does the same (`.github/workflows/ci.yml`).
- Unit tests do not need postgres: `apps/web/src/test/setup.ts` mocks
  `@rallly/database`. Integration tests do (`apps/web/.env.test` points
  at the compose stack).

The task's verifier is a fast subset of the map's commands
(`typecheck`, `lint`, `structure`, and one scoped `test-*`); you run the
full `test` and `build` yourself and show the tutor the tail of each.
The tutor may not run any of the setup for you and may not fix your
environment; it may tell you what a failure means.

## Rubric

- `typecheck`, `lint`, and `structure` pass in the verifier, and the
  learner has shown `test` and `build` passing.
- The learner can say, without looking, what `pnpm db:generate` does and
  why it comes before the type check.
- The learner can name what the compose stack provides and which of the
  map's commands need it.
