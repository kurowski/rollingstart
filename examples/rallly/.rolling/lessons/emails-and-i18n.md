---
title: Emails and their i18n
region: platform
depth: working
mode: write
requires: [how-a-change-ships]
assumes: [react, i18next]
test: held
---

How an email leaves this system, why every template builds its own
i18n instance, and what the app has to pass in for branding and
headers. Most product work touches mail eventually (invites,
responses, bookings, billing), and the rules are easy to break in ways
only a production fan-out reveals.

The package is `packages/emails`. A template is a file under
`src/templates/` exporting a React Email component and a
`send…Email(args: SendArgs<Props>)`; `poll-invite.tsx` is the shape
to copy. `src/send.tsx` defines `SendArgs` (`to`, `locale`, `branding`,
`props`, and the optional `from`, `replyTo`, `attachments`,
`icalEvent`, `listUnsubscribeUrl`, each with a comment on when it
applies) and `sendRenderedEmail`, which renders, builds the
`List-Unsubscribe` headers, and hands off to nodemailer through
`transport.ts`. `src/chrome.ts` turns the caller's `EmailBranding` into
the `chrome` a template renders with (logo, colour, app name, base
URL, support address); `apps/web/src/emails/branding.ts` is where the
app decides between instance branding and a space's own
(`getSpaceBranding`, which asks instance policy and the resolved tier
before applying a space's colour).

The i18n rule is the one to get right. `src/i18n.ts`,
`createEmailI18n(locale)`, builds a fresh i18next instance per render
and returns `{ t, i18n }`; a template calls it once, uses `t(key, {
defaultValue })` for plain strings and `Trans` from
`react-i18next/TransWithoutContext` with both `t` and `i18n` for
strings with markup. `CLAUDE.md` ("i18n & Localization") says why: the
package's default export is a process-wide singleton, emails are sent
from server components where React context is unavailable, and a
concurrent fan-out through a shared instance would cross languages.
Keys live in `locales/en/emails.json`, written by `pnpm i18n:scan`
(config in `packages/emails/i18next.config.ts`: `removeUnusedKeys` is
on, so a key nothing references is deleted on the next scan). Tests
render to HTML with `@react-email/render` and assert on the default
copy, since the ICU backend does not interpolate under vitest; see
`src/templates/new-participant.test.tsx`, comment included.

Task source for the tutor: `e84e55da` (#3167) made the invite email
reply to the host: `replyTo` threaded from `sendPollInvite` in
`apps/web/src/features/poll/invite/mutations.ts` (which had to select
the sender's email), one new `Text` in `poll-invite.tsx` with a
`pollInvite_reply` key, the key in `emails.json`, and a new unit test
`packages/emails/src/templates/poll-invite.test.tsx` that renders the
template and looks for the copy. Hold that test; its verifier line is
`test-emails src/templates/poll-invite.test.tsx`. Scope the task to
`packages/emails` and `apps/web/src/features/poll/invite/mutations.ts`;
verify with `typecheck-emails` and `lint` on both. The brief gives the
copy the email should carry ("Reply to this email to reach
{hostName}") and says replies should reach the host; it does not say
how a reply address travels or how a string is localised in a
template. The later commit `0c3aad5c` (#3169) removed that line again,
so the template at the pin does not have it; the task branch starts
from before either. A seam for a fresh task: any template still
missing a line the product copy wants, or a header `SendArgs` supports
that a sender does not yet pass.

## Rubric

- The string goes through the template's own `t` with a `defaultValue`
  and a key in `emails.json` produced by the scan, never a literal in
  JSX; any markup goes through `TransWithoutContext` with `t` and
  `i18n` both passed.
- The reply address reaches nodemailer through `SendArgs.replyTo` from
  the caller that knows the host, not through a template prop or an
  environment variable, and the mutation selects only what it needs.
- The learner's own test renders the template and asserts on the copy.

## Talk through

- Why `createEmailI18n` is called per render and what would go wrong
  under load if it were not.
