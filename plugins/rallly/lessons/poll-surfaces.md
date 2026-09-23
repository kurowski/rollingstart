---
title: Where a poll lives
region: polls
depth: orientation
mode: write
requires: [how-a-change-ships]
assumes: [react, next-app-router]
exercise: none
---

The poll as a user meets it, and where each of those screens lives in
the code. This is a look around, not a change: after it you can take a
bug report that says "on the invite page" or "in the host's view" and
open the right file. The data underneath is the next lesson,
`poll-data-model`; this one stays on the surface.

Four surfaces, one feature folder. Everything below is under
`apps/web/src/`, and the components under
`features/poll/components/`.

**Creating one: `/new`.** `app/[locale]/(optional-space)/new/page.tsx`
renders `CreatePoll` (`components/create-poll.tsx` line 129), the
multi-step form for title, options, and settings, after loading the
signed-in user's space and the instance policy (lines 22 to 27). A
guest can create a poll too, which is why the route sits under
`(optional-space)`. The write still goes through the legacy router's
`make` (`trpc/routers/polls.ts` line 95); the newer `createPoll` in
`features/poll/mutations.ts` line 74 is the shape writes are moving
to, and `poll-lifecycle` covers the transitions.

**The host's view: `/poll/<id>`.** The route is
`(optional-space)/poll/[urlId]/`. Its `layout.tsx` fetches the poll
and prefetches the participant and comment lists on the server
(`trpc.polls.get` at line 19, `polls.participants.list` and
`polls.comments.list` at 33 and 34), then wraps everything in
`PollLayout` (`components/poll-layout.tsx`): the breadcrumb back to
`/polls`, and the admin controls, `ManagePoll` (the menu: edit
details, options, and settings; close or reopen; schedule; export to
CSV; duplicate; delete) and `ShareDialog` (lines 21 to 27). The page
itself, `admin-page.tsx`, composes `EventCard` (the title and the
host), `VotingForm` around
`ResponsiveResults`, `CommentsSheet`, and `PollFooter`. The
`edit-details`, `edit-options`, and `edit-settings` routes beside it
are the three edit forms, one per step of the create flow.

**The voter's view: `/invite/<id>`.** `app/[locale]/invite/[urlId]/page.tsx`
(line 43) is open to anyone with the link. It reads `?token=` from the
URL, resolves which responses that token may edit
(`loadParticipantIdsByToken`, `features/poll/loaders.ts` line 32), and
prefetches the same three queries the host's layout does (lines 76 to
78), then renders `InvitePage` (`invite-page.tsx` line 69): the same
`EventCard`, `VotingForm`, `ResponsiveResults`, and `CommentsSheet`,
with no admin controls, plus `InviteOpenRecorder`, which marks an
email invite as opened. `invites-and-participants` is the lesson on
how someone arrives here.

**The dashboard: `/polls`.** `app/[locale]/(space)/(dashboard)/polls/page.tsx`
lists a space's polls through `PollsInfiniteList`
(`components/polls-infinite-list.tsx`), with the status counts from
`loadPollStatusCounts` (`loaders.ts` line 12) for the filter tabs.
Beside it, `polls/[pollId]/` is a new admin view behind the
`pollAdmin` feature flag (`lib/feature-flags/config.ts`), loading
through `loadPoll` (`loaders.ts` line 17); read it as where the host's
view is heading, not where it is.

**Admin or participant is a matter of the URL.** `useRole` in
`features/poll/client.tsx` line 18 answers `admin` when the path
contains `/poll` and `participant` otherwise; `usePermissions` (line
47) turns that, the poll's status, and the token's participant ids
into "can add a response" and "can edit this one". The same
components render both views and consult these hooks, which is why
the host's page and the invite page look alike and behave
differently.

**What feeds the screens.** `usePoll` (`client.tsx` line 9) is
`trpc.polls.get` (`routers/polls.ts` line 703, a `publicProcedure`
selecting the poll and its options). `useParticipants`
(`components/participants-provider.tsx` line 17) is
`polls.participants.list`, and it renames hidden participants to
"Participant #n" on the client. The grid is `desktop-poll.tsx` or
`mobile-poll.tsx`, chosen by `responsive-results.tsx`; a vote is one of
`VOTE_TYPES` (`features/poll/constants.ts` line 4: yes, ifNeedBe, no).
`VotingForm` (`components/voting-form.tsx`) holds the form in one of
three modes, `new`, `edit`, or `view` (the schema at line 15), and
submits through `components/mutations.ts`. Reads stay on the frozen
router; writes are moving to `features/poll/actions.ts`
(`setPollMutedAction`, line 8) and `mutations.ts`, per `CLAUDE.md`.

## Rubric

There is no exercise in this lesson. A change on any of these
surfaces is read against the feature-folder shape in `CLAUDE.md` (a
page composes components from `features/poll/components/`; data
through `data.ts`, writes through `actions.ts` and `mutations.ts`) and
against the role rule: a control that only the host may use is gated
by `usePermissions` or the role, never by which page it happens to
be on.

## Talk through

- Given a URL a bug report names, which page file renders it and which
  components it composes.
- Why the host's page and the invite page share components, and what
  decides which controls appear.
- Which query each screen depends on, and where the participant list
  comes from.
