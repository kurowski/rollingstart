---
title: The poll lifecycle
region: polls
depth: working
mode: direct
requires: [poll-data-model]
assumes: [trpc, zod, next-app-router]
test: held
---

What happens to a poll between creation and deletion, where each
transition lives, and what has to be true on the far side of it. This
is a `direct` lesson: you will write the brief, an agent will
implement, and you will review.

The transitions, and the two surfaces they are spread across.
Creation is still the legacy router's `make` (`trpc/routers/polls.ts`
line 95) and the new `createPoll` in `features/poll/mutations.ts` line
74. Closing is `closePoll` (mutations line 133): an idempotent
`updateMany` guarded by `status: { not: "closed" }`, then
`recordPollActivities` with `poll_closed` and a reason; the legacy
`close` at router line 1275 does the same by hand. Booking is `book`
(router line 827, `proProcedure`): it creates a `ScheduledEvent`
(`event.prisma`) and sends the `finalized-host` and
`finalized-participant` emails. Reopen is at 1208, soft delete is
`deletePoll` (mutations 208) and `markAsDeleted` (router 672). The
house-keeping cron runs the rest of the lifecycle from
`app/api/house-keeping/[...method]/route.ts` (Hono, bearer-authed with
`CRON_SECRET`, one route per task, each logging a summary) on the
schedule in `apps/web/vercel.json`: `autoClosePolls` (mutations 322,
reason `auto`, 05:30 daily), `deleteInactivePolls` (266, 06:00),
`removeDeletedPolls` (364, 06:30), then the account reaper and the
hourly orphaned-guest sweep, which `57afeb77` (#3060) capped so a
backlog spills to the next run instead of timing the function out.
`tests/house-keeping.spec.ts` covers the poll ones.

Two things a maintainer will check in any change here: that a
transition is idempotent (a poll closed twice records one activity),
and that it writes the activity the timeline page reads
(`features/poll/activity/`). A third, since 4.15.0: a participant
write to a poll that is no longer open is refused on the server
(`trpc/routers/polls/utils.ts`, `d818a5fe`, #3246), the same rule
`canEditParticipant` applies on the client, and the lifecycle check
comes before the permission check. The pages that show state:
`app/[locale]/invite/[urlId]/page.tsx` for voters,
`(optional-space)/poll/[urlId]/` for hosts, and the flag-gated new admin
under `(space)/(dashboard)/polls/[pollId]/` (`pollAdmin` in
`lib/feature-flags/config.ts`, development only).

Situations for the tutor to present: `6b30747e` (#3193) and `f58b281b`
(#3180) as symptoms rather than fixes; a request to record an activity
a transition currently does not; a request to make a cron job's batch
behaviour visible, the way `57afeb77` did for the guest sweep. Mistakes
worth watching for: a non-idempotent guard, a missing
`recordPollActivities`, a mutation added to the frozen router, a cron
task that does unbounded work in one invocation.

## Rubric

- The brief names the transition, the surface it lives on, what must
  be true afterwards (idempotency, the activity written, who gets an
  email), and how to prove it.
- The review catches a missing or duplicated activity, a
  non-idempotent transition, or a write placed on the frozen tRPC
  surface, and says which file it would have gone in.
- The review distinguishes what would block a merge from what is
  taste.
