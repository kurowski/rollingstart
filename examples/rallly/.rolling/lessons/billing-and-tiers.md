---
title: Billing and tiers
region: billing
depth: working
mode: write
requires: [how-a-change-ships]
assumes: [stripe, react]
test: held
---

How a space becomes pro, how the code asks whether it is, and what the
pay wall does about it.

The tier is on the space, not the user: `Space.tier` on `SpaceTier`
(`packages/database/prisma/models/space.prisma` line 6, the enum at
56), and `Subscription` in `billing.prisma` records what Stripe said.
The one place the rule is derived is `resolveSpaceTier` in
`apps/web/src/features/billing/utils.ts` (line 9): when billing is off
(`isBillingEnabled` in `constants.ts` line 4, which is
`!isSelfHosted`), every space is pro. `CLAUDE.md` calls that out, and
`utils.test.ts` pins it; `features/space/utils.ts`
(`isSpaceBrandingActive`, `isSpaceAttributionHidden`) is how a stored
paid setting is read through it, and `flags-and-policy` is the lesson
on the other half of that rule. Server-side gating is `proProcedure` in
`trpc/trpc.ts` line 175 (`PAYMENT_REQUIRED`) and, on the action side,
a `resolveSpaceTier` check in the mutation (`sendPollInvite` in
`features/poll/invite/mutations.ts` returns `paymentRequired`);
client-side it is `TierProvider` and `useTier` (`features/billing/client.tsx`
lines 13 and 23), the pay wall (`components/pay-wall.tsx`,
`pay-wall-dialog.tsx`, `pro-badge.tsx`, `upgrade-button.tsx`), opened
from anywhere with `showPayWall` (`client.tsx` line 75). `CLAUDE.md`
("Permission-Gated UI") says how a plan-gated control looks: enabled
with a `ProBadge`, never hidden or disabled.

The write paths are server actions: `upgradeToProAction`
(`features/billing/actions.ts` line 27), which opens a Stripe checkout
session, and `openCustomerPortalAction` (line 178), calling
`mutations.ts` (`createStripePortalSession`,
`stopUserSubscriptionRenewals`, and friends) and `service.ts`
(`getStripe`). Stripe talks back through
`app/api/stripe/webhook/route.ts` and `features/billing/webhook/
mutations.ts`, which `stripe-webhook` covers.

Prices and currencies are the part of billing with a clean unit seam,
and this lesson's exercise lives there. `packages/billing/src/pricing.ts`
is the pricing package's rulebook: the built-in `pricingData`,
`displayedCurrencies` (line 22, the three currencies Stripe prices
carry), `CURRENCY_COOKIE_NAME` (27), `isDisplayedCurrency` (31), and
`getCountryCurrency` (79), the rule for which currency to show a buyer
from a given country; `pricing.test.ts` beside it is the pattern for
testing a rule. `packages/billing/src/lib/stripe.ts` (`getProPricing`)
is where the live prices come from, with `stripe.test.ts`. On the app
side, `features/billing/data.ts` caches those prices for an hour
(`getProPrices`, line 47), `loaders.ts` (`loadPayWallPricing`, line 16)
picks the buyer's currency from the request country and hands the pay
wall its prices, `pay-wall-dialog.tsx` keeps the selected currency
(lines 232 to 238) and writes it to the cookie (`setCurrencyCookie`,
`client.tsx` line 85), and `upgradeToProAction` passes it to checkout.

That flow arrived in four pull requests over a week, worth reading in
order for how a feature grows here: `dd4833d3` (#3204) built it, the
rule and its test in the package and the wiring in the app;
`2410a32d` (#3208) carried the currency picked on the pricing page
into the pay wall through the cookie; `8ccb963f` (#3209) renamed the
cookie, one line, so the domain-scoped one wins; `2875e7e4` (#3211)
made the pay wall remember the pick across close and reopen.

Task source for the tutor: build from `dd4833d3` with
`packages/billing/src/pricing.test.ts` held; on the starting state the
held test imports `getCountryCurrency`, which does not exist yet, so
it fails there as it should. Scope the task to `packages/billing/src`
and brief only the rule: buyers everywhere see USD today; the app
needs one function that says which currency to show a buyer from a
country (ISO 3166-1 alpha-2, any case), limited to what Stripe
actually offers on the price, falling back to USD and then to whatever
is available; the United Kingdom and the crown dependencies get GBP,
the euro area with the EFTA and EU countries that price in euros get
EUR. Say that wiring it into the pay wall and checkout is the
follow-up the original PR also did, not this task. Verify with
`typecheck-billing` and `lint packages/billing/src`; the held line is
`test-billing src/pricing.test.ts`, the path relative to
`packages/billing`. The parent is thirty-one commits behind the pin
with no schema change between, so the generated client fits it and
there is no `setup:` line. `8ccb963f` and `2875e7e4` are too
small or too UI-bound for a held test and are for the talk-through.

## Rubric

- The rule lives in `packages/billing` beside the other pricing
  rules and is exported for the app to consult, the way
  `resolveSpaceTier` is the one place the tier is derived; nothing in
  `apps/web` decides a currency on its own.
- The country sets are data, not a chain of conditions per country,
  and the code is upper-cased before the lookup.
- A currency is returned only if the price carries it; the fallback is
  USD when available, else the first currency there is; an unknown or
  missing country is USD.
- The unit test is `.test.ts` beside the rule and asserts the
  behaviour: the mapped countries, the fallbacks, and the "only what
  Stripe offers" case.
- Nothing forks on `isSelfHosted`; billing-off behaviour goes through
  `isBillingEnabled` and `resolveSpaceTier`.

## Talk through

- How a space becomes pro and the one place the rule is derived; what
  a self-hosted instance sees, and why.
- The two rungs of server-side gating (`proProcedure` and a
  `resolveSpaceTier` check in a mutation) and when each is the right
  one; how a plan-gated control is presented.
- The cookie arc (#3208, #3209, #3211): why a currency preference is a
  cookie shared across subdomains, and why renaming it fixed a bug.
