---
title: Billing and tiers
region: billing
depth: working
mode: direct
requires: [how-a-change-ships]
assumes: [stripe, react]
test: held
---

How a space becomes pro, how the code asks whether it is, and what the
pay wall does about it. A `direct` lesson.

The tier is on the space, not the user: `Space.tier` on `SpaceTier`
(`space.prisma` lines 6 and 56 to 61), and `Subscription` in
`billing.prisma` records what Stripe said. The one place the rule is
derived is `resolveSpaceTier` in `features/billing/utils.ts`: when
billing is off (`isBillingEnabled` in `constants.ts`, which is
`!isSelfHosted`), every space is pro. `CLAUDE.md` calls that out, and
`utils.test.ts` pins it; `features/space/utils.ts`
(`isSpaceBrandingActive`, `isSpaceAttributionHidden`) is how a stored
paid setting is read through it, and `flags-and-policy` is the lesson
on the other half of that rule. Server-side gating is `proProcedure` in
`trpc/trpc.ts` line 175 (`PAYMENT_REQUIRED`) and, on the action side,
a `resolveSpaceTier` check in the mutation (`sendPollInvite` in
`features/poll/invite/mutations.ts` returns `paymentRequired`);
client-side it is `components/pay-wall.tsx`, `pay-wall-dialog.tsx`,
`pro-badge.tsx`, and `upgrade-button.tsx`, opened from anywhere with
`showPayWall` in `client.tsx`. `CLAUDE.md` ("Permission-Gated UI")
says how a plan-gated control looks: enabled with a `ProBadge`, never
hidden or disabled.

The write paths are server actions: `upgradeToProAction` and
`openCustomerPortalAction` in `features/billing/actions.ts`, calling
`mutations.ts` (`createStripePortalSession`,
`stopUserSubscriptionRenewals`, and friends) and `service.ts`
(`getStripe`). Stripe talks back through
`app/api/stripe/webhook/route.ts` and `features/billing/webhook/
mutations.ts`, which `stripe-webhook` covers. Prices and currencies
come from `packages/billing/src/pricing.ts` (`displayedCurrencies`,
`getCountryCurrency`, `CURRENCY_COOKIE_NAME`) and `lib/stripe.ts`
(`mapProPrices`, `getProPricing`); `pricing.test.ts` and
`stripe.test.ts` are the unit seams.

Situations for the tutor to present: `2875e7e4` (#3211, seventeen
lines: the pay wall forgets the currency you picked) and `8ccb963f`
(#3209, one line: two cookies with the same name and the wrong one
wins) are small and real; `dd4833d3` (#3204) is the larger version with
a test seam, and `d374ed48` (#3157) is a tier bug outside the billing
folder. Mistakes worth watching for: deriving pro-ness from
`Space.tier` directly, gating with `privateProcedure` where
`proProcedure` was meant, hiding a plan-gated control instead of
badging it, a stored paid setting read without the resolved tier.

## Rubric

- The brief says which surface the change is on (pay wall, action,
  pricing package), what self-hosted instances should see, and how to
  prove it without a real Stripe account.
- The review catches a tier derived outside `resolveSpaceTier`, a gate
  on the wrong rung, or a plan gate presented the way `CLAUDE.md`
  forbids.
- The review says what it would merge as-is and what it would send
  back, and why.
