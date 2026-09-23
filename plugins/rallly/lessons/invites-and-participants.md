---
title: Invites and participants
region: polls
depth: working
mode: write
requires: [poll-data-model]
assumes: [prisma, react]
test: held
---

How a person gets into a poll, what an invite is before and after they
respond, and the one link that has to mean the same thing everywhere.
This is the newest part of the product (the Share dialog with email
invites landed in #3160 and has had a commit most days since), so it
is both the best example of the current conventions and the place a
new engineer is most likely to be asked to change.

Two ways in. The invite link (`/invite/<pollId>`) is open to anyone
who has it; a response made there is a `Participant` with an
app-minted `token`, the edit credential the `poll-data-model` lesson
covers. An email invite is a `PollInvite` row with its own token, sent
by `sendPollInvite` in `apps/web/src/features/poll/invite/mutations.ts`
(line 32: the poll must be open, the space's resolved tier pro, the
sender under `MAX_POLL_INVITES_PER_DAY` counted from the activity log,
the address not already a participant; then the row, the activity, and
the email, with a failed send deleting its event). The link in that
email is `getPollInvitePath` in `invite/utils.ts`, and the same helper
builds the personal link a host copies from the dialog, so the two can
never disagree; the invite page (`app/[locale]/invite/[urlId]/
page.tsx`, line 60) reads the token from `?token=` and records the
open through `recordPollInviteOpenAction`. When the invitee responds
through their link, `attachParticipantToInvite` (mutations line 252)
sets `participantId` and the response takes the invite's token, which
is why one link keeps editing one response. Deleting the response hard
deletes the participant and the `SetNull` foreign key reverts the
invite to pending (`af3d9273`, #3191, and the comment on `revokedAt` in
`poll.prisma`); revoking is explicit (`revokePollInvite`, line 327), and
re-inviting a revoked address reactivates the row with a fresh token
(`sendPollInvite`, lines 108 to 134, comments included).

The status a host sees is derived, not stored:
`derivePollInviteStatus` in `utils.ts` (sent, opened, responded, with
responded outranking opened) over rows `listPollInvites` in `data.ts`
selects; `loaders.ts` composes the list items for the dialog, and
`e481cf5b` (#3228) moved that read onto a tRPC query. The actions in
`invite/actions.ts` are the reference shape for the platform lesson:
`sendPollInviteAction` (line 22) with a rate limit and
`hasPollAdminAccess`, `revokePollInviteAction` (59),
`recordPollInviteOpenAction` (93) on the unauthenticated client. The
UI is `features/poll/components/invitee-list.tsx`,
`invite-by-email.tsx`, and `share-dialog.tsx`; locale strings go in
`apps/web/public/locales/en/app.json` through `pnpm i18n:scan`.

Task source for the tutor: `3011b1ad` (#3178) let hosts copy an
invitee's personal link. The pure part, `getPollInvitePath`, got the
unit test (`features/poll/invite/utils.test.ts`, one case); the list
item grew an `inviteUrl` (`types.ts`, `loaders.ts`, `data.ts` selecting
`token`); the email's inline path moved onto the helper; the dialog got
a menu and three strings; the spec grew a step. Hold the unit test; its
verifier line is `test-web src/features/poll/invite/utils.test.ts`.
Scope the task to `apps/web/src/features/poll` and
`apps/web/public/locales/en/app.json`; verify with `lint
apps/web/src/features/poll` and `structure`. The brief asks for
the feature (a host can copy each invitee's personal link, and it must
be the link the email carries) and names the helper the held test
imports; it does not say where the URL is composed or what the dialog
does. At the fix's parent the path's query key was `invite`, and the
held test expects that; `95e61636` (#3188) renamed it to `token` later,
which is what the pin has. The parent is five days behind the pin
and before the participant-token schema changes. The unit tests do
not mind (`apps/web/src/test/setup.ts` mocks the client), so the task
needs no `setup:` operation, but `typecheck-web` does not belong in
its verifier: against the pin's generated client it fails on seventy
errors in files the task never touches, and with the client
regenerated for this tree it still finds a handful (the private API's
schemas, the user mutations), which are the dependency upgrades
between this parent and the pin. Run it for the learner when they ask,
after `regenerate-client`, and read it with that in mind; they run
`pnpm db:generate` again when they are back on their own branch.
A seam for a fresh task: a bulk form of `revokePollInvite` beside the
single one, or a status the derivation does not yet distinguish.

## Rubric

- The link is composed in one helper used by both the email and the
  copy action, the loader composes the absolute URL, and `data.ts`
  selects the token only where it is needed.
- Every string is a locale key, the menu's action reports success and
  failure the way the dialog already does, and nothing reaches into
  `@rallly/database` outside `data.ts` and `mutations.ts`.

## Talk through

- What happens to an invite when its invitee responds, when the
  response is deleted, and when the host revokes it, and which of
  those rotates the token.
