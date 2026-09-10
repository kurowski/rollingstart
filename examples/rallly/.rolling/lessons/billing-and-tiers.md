---
title: Billing and tiers
region: billing
depth: working
mode: direct
requires: [how-a-change-ships]
assumes: [stripe, react]
---

How a space becomes pro, how the code asks whether it is, and what the
pay wall does about it. A `direct` lesson.

The tier is on the space, not the user: `Space.tier` on `SpaceTier`
(`space.prisma` lines 6 and 56 to 61), and `Subscription` in
`billing.prisma` records what Stripe said. The one place the rule is
derived is `resolveSpaceTier` in `features/billing/utils.ts`: when
billing is off (`isBillingEnabled` in `constants.ts`, which is
`!isSelfHosted`), every space is pro. `CLAUDE.md` calls that out, and
`utils.test.ts` pins it. Server-side gating is `proProcedure` in
`trpc/trpc.ts` line 175 (`PAYMENT_REQUIRED`); client-side it is
`components/pay-wall.tsx`, `pay-wall-dialog.tsx`, `pro-badge.tsx`, and
`upgrade-button.tsx`.

The write paths are server actions: `upgradeToProAction` and
`openCustomerPortalAction` in `features/billing/actions.ts`, calling
`mutations.ts` (`createStripePortalSession`,
`stopUserSubscriptionRenewals`, and friends). Stripe talks back through
`app/api/stripe/webhook/route.ts`, which verifies the signature and
hands off to `handleStripeWebhookEvent` in
`features/billing/webhook/mutations.ts` line 591, one case per event
type. Prices and currencies come from `packages/billing/src/pricing.ts`
(`displayedCurrencies`, `getCountryCurrency`, the cookie name) and
`lib/stripe.ts`; `pricing.test.ts` is the unit seam.

Situations for the tutor to present: `2875e7e4` (#3211, seventeen
lines: the pay wall forgets the currency you picked) and `8ccb963f`
(#3209, one line: two cookies with the same name and the wrong one
wins) are small and real; `dd4833d3` (#3204) is the larger version with
a test seam. Mistakes worth planting: deriving pro-ness from
`Space.tier` directly, gating with `privateProcedure` where
`proProcedure` was meant, a webhook case that is not idempotent on
redelivery.

## Rubric

- The brief says which surface the change is on (pay wall, action,
  webhook, pricing package), what self-hosted instances should see, and
  how to prove it without a real Stripe account.
- The review catches a tier derived outside `resolveSpaceTier`, a gate
  on the wrong rung, or a webhook handler that would double-apply on
  redelivery.
- The review says what it would merge as-is and what it would send
  back, and why.
