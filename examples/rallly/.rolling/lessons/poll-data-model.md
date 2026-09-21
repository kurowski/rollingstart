---
title: The poll data model
region: polls
depth: working
mode: write
requires: [how-a-change-ships]
assumes: [prisma, postgres]
test: held
---

The tables everything joins to, and the shape you have to hold in your
head before any change to voting is safe. The schema is split by model
under `packages/database/prisma/models/`; `poll.prisma` is the one to
read end to end, comments included, because the comments are where the
design decisions are.

`Poll` (lines 32 to 69): an app-minted nanoid id, `status` on
`PollStatus` (`open | closed | scheduled | canceled`) with
`closedReason`, a soft-delete pair `deleted` + `deletedAt`, the
visibility flags (note `disableComments` defaults to true), `timeZone`,
`deadline`, `spaceId`. `Option` (145 to 158): `startTime` and a
`duration` in minutes where 0 means all day. `Participant` (71 to 94):
a response, with a unique `token` that is its edit credential, minted
in the app and never defaulted by the database; the comment at line 76
says why. `Vote` (168 to 185): participant × option × `VoteType`, with
`pollId` denormalised on purpose. `PollInvite` (96 to 119): per-invitee
tokens, `openedAt`/`remindedAt`/`revokedAt`, and a one-to-one
`participantId` that flips an invite from pending to responded; the
comment on `revokedAt` is the whole invite lifecycle in one paragraph.
`PollActivity` (121 to 143): an append-only timeline whose `type` is a
Zod union in `apps/web/src/features/poll/activity/schema.ts`, not a
database enum, and whose references are soft.

Where the model is used: reads in `features/poll/data.ts` (`getPoll`,
`getPollResults`, `getPollParticipants`, `listPolls`), writes in
`features/poll/mutations.ts` (`createPoll` line 74, `closePoll` 133,
`setPollMuted` 183, `deletePoll` 208, and the three house-keeping
functions from 266), with `mutations.test.ts` beside them as the
pattern for testing a write against the mocked client. The legacy vote
path is `trpc/routers/polls/participants.ts` (`add` at line 288 mints
the token and attaches to a pending invite; `update` at 518 replaces
all votes in a transaction; `delete` at 214 hard-deletes so the invite
reverts to pending). The recent history of `Participant` is a worked
example of how schema changes ship here in stages: backfill
(`20260904150000_backfill_participant_token`), require
(`20260905170000_require_participant_token`), purge (`6d0ca33e`,
#3192), drop (`f79dde98`, #3194).

Task sources for the tutor. `af3d9273` (#3191) is the exemplary fix,
ten lines in `participants.ts` plus the assertion in
`tests/email-invites.spec.ts`; its test is Playwright, so it can be
held only where the map's `integration` command can run (a browser
and the stack), which this example's environment does not have.
`6b30747e` (#3193) removes the participant soft-delete filters from
reads and is a good "understand why this is now safe" reading, with no
test to hold. So in this environment the tutor builds along a seam
and writes the test itself, against the mocked client in
`mutations.test.ts`'s shape: a read in `data.ts` that must respect a
poll's soft-delete and an invite's `revokedAt`, or a write in
`mutations.ts` beside a sibling (`revokePollInvite` in `invite/
mutations.ts` next to a bulk form of it has worked). Any task that
changes a model needs the migration in its brief and
`regenerate-client` as a `setup:` operation, so the type check sees
the new client. Verify with `typecheck-web`, `lint` on the feature,
and `test-web` on the test the tutor wrote.

## Rubric

- The change is correct about the relations: which side owns the
  foreign key, what cascades, what is soft-deleted and what is hard.
- Any query respects the poll's soft-delete and the invite's
  `revokedAt` where they apply.
- The test that proves the change is the right kind (`.test.ts` with
  the database mocked, or `.spec.ts` against the stack) and asserts
  behaviour, not the mock.

## Talk through

- Which reads filter on the poll's soft-delete and which on the
  invite's `revokedAt`.
- The participant token, the invite-to-participant link, and why
  `PollActivity.type` is not an enum.
