---
title: The Stripe webhook
region: billing
depth: deep
mode: direct
requires: [billing-and-tiers]
assumes: [stripe]
test: held
---

The one place Stripe writes into this system, and the properties every
handler in it has to keep: verified, idempotent on redelivery,
tolerant of rows that are already gone. A `direct` lesson, for someone
who will own billing.

The route is `apps/web/src/app/api/stripe/webhook/route.ts`: a 410 on
self-hosted (`isSelfHosted`, one of the infrastructure uses `CLAUDE.md`
sanctions), the raw body and the `stripe-signature` header into
`constructEvent` with `STRIPE_SIGNING_SECRET`, a 400 on a bad
signature, then `handleStripeWebhookEvent`; an unhandled type is
reported to Sentry and acknowledged, a thrown error is a 400, which is
what makes Stripe retry. The business logic is `features/billing/
webhook/mutations.ts`: `handleStripeWebhookEvent` (line 591) is a
`switch` over the event types, one function each
(`onCheckoutSessionCompleted` 85, `onCustomerSubscriptionCreated` 218,
`onCustomerSubscriptionDeleted` 355, `onCustomerSubscriptionUpdated`
423, the customer and payment-method handlers between). The tier is
never set from a single event: `syncSpaceTier` (line 39) recomputes it
from whether any subscription row is active, inside the same
transaction that wrote the triggering row, and clears the paid
settings and pending member invites on the way down. `webhook/utils.ts`
parses the metadata each event carries; `service.ts` (`getStripe`)
is the client; `packages/billing/src/lib/stripe.ts` maps prices.

What a maintainer checks in any change here: the handler survives the
same event twice (Stripe redelivers, and `updateMany` where a row may
already be gone is the house style, with a comment saying so); it does
not throw for a space or user that was cascade-deleted, since a throw
is a retry forever (`c2229e14`, #3001, added the `spaceExists` guard
to three handlers for exactly that); the tier is synced, not assumed;
and nothing here reads the session, since there is none. The
unit-test seams are in `packages/billing`; the handlers themselves are
exercised through Stripe's CLI against a dev server, which this
example's environment does not run.

Situations for the tutor to present: `c2229e14` (#3001) as a symptom
(Stripe retrying a subscription event for a space that no longer
exists); a new event type the product wants to react to; a request to
record a billing activity somewhere the timeline could show it.
Mistakes worth watching for: a handler that sets `tier` directly
instead of through `syncSpaceTier`, one that uses `update` where the
row may be gone, one that returns 200 on a failure it should retry
(or 400 on one it should not), a signature check moved or skipped, a
new `isSelfHosted` fork in product code.

## Rubric

- The brief names the event, what the handler must leave true in the
  database, what redelivery must not double-apply, and what happens
  when the space is already gone; and it says how to prove it without
  production Stripe.
- The review catches a non-idempotent write, a tier set outside
  `syncSpaceTier`, a throw where a no-op was wanted (or the reverse),
  and says which line and which retry semantics it would break.
- The review says what would block a merge and what is taste, and the
  learner can say what a 400 from this route makes Stripe do.
