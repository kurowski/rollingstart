---
title: Feature flags and instance policy
region: platform
depth: working
mode: write
requires: [how-a-change-ships]
assumes: [typescript]
test: held
---

Where a cloud-versus-self-hosted difference is allowed to live, the
two kinds there are, and the one rule that keeps paid features from
leaking or vanishing. `CLAUDE.md` ("Deployment Modes") is the
statement; this lesson is the mechanism.

Capabilities answer "can this instance do X?" and live in one file,
`apps/web/src/lib/feature-flags/config.ts`: `featureFlagConfig`, one
line per field with its reason (`billing`, `captcha`, `registration`,
`pollAdmin`, `inProcessRateLimit`, …), typed by `types.ts`. Server code
asks `isFeatureEnabled(feature)` from `server.ts`; client code asks
`useFeatureFlag(feature)` from `client.tsx`, fed by a provider mounted
in the root layout. Policies answer "what does this instance's
organisation decide for its spaces?" and live in
`apps/web/src/features/instance-policy/`: `deriveInstancePolicy` in
`utils.ts` is the inventory (`spacesAlwaysShared`,
`spaceBrandingAllowed`, `spaceAttributionConfigurable`, each with a
reason), `getInstancePolicy` in `data.ts` derives it for server code
from `isSelfHosted` and the license (skipping the license read in
maintenance mode, and the comment says why), `loadInstancePolicy` in
`loaders.ts` is the page-facing read, `useInstancePolicy` in
`client.tsx` the hook; `utils.test.ts` pins every field both ways.

`isSelfHosted` itself (`lib/constants.ts`) is for infrastructure
wiring: the Stripe webhook route, licensing, storage. A handful of
legacy product forks still key on it (`components/environment.tsx`,
`IfSelfHosted`, is one), and `CLAUDE.md` calls a new one a review
blocker: add a capability or a policy field instead. The rule that
joins policy to billing is `resolveSpaceTier` in
`features/billing/utils.ts`: without billing every space is pro, and
that is derived once. A stored paid setting on a space
(`showBranding`, `hideAttribution`) is only honoured through the
resolved tier and the policy that allows it; `features/space/utils.ts`
(`isSpaceBrandingActive`, `isSpaceAttributionHidden`) is where that is
written down, and `apps/web/src/emails/branding.ts` and
`features/space/data.ts` are two of the five places that call it.

Task source for the tutor: `d374ed48` (#3157). A space that had turned
custom branding on and then dropped to hobby kept rendering its colour
and hiding the credit, because every call site read the stored
settings against the policy alone. The fix adds the two helpers to
`features/space/utils.ts`, uses them from `emails/branding.ts`,
`space/data.ts`, `scheduled-event/data.ts`, `trpc/routers/polls.ts`,
and the new-poll page, and adds eight cases to
`features/space/utils.test.ts` (tier, switch, policy, each way). Hold
that test file; its verifier line is `test-web
src/features/space/utils.test.ts`. Scope the task to `apps/web/src`;
verify with `lint apps/web/src/features/space
apps/web/src/emails` and `structure`. The brief describes the symptom
(a downgraded space keeps its branding) and names the two helpers and
their inputs, since the held test pins them; it does not say where the
tier rule is derived or which call sites are affected. The fix's parent
is six days behind the map's pin and before the participant-token
schema changes, so the task needs `regenerate-client` as a `setup:`
operation for the tests to load the client, and the brief tells the
learner to run `pnpm db:generate` again when they are back on their
own branch. `typecheck-web` does not belong in the verifier at this
parent for the same reason as in `procedures-and-actions`: the pin's
toolchain finds a few errors in files the task never touches. `95979adf` (#3147) is the refactor
that created all of this, and its `CLAUDE.md` hunk is the shortest
statement of the rule; `1c6f5da3` (#3125) added the white-label policy
that `spaceBrandingAllowed` reflects. A seam for a fresh task: a new
policy field, derived in `utils.ts` with a test, read through the
loader and the hook.

## Rubric

- The rule is derived in one helper per setting and every call site
  uses it; no call site reads `Space.tier` or `isSelfHosted` to decide.
- The helpers take the stored tier and resolve it through
  `resolveSpaceTier`, so a self-hosted instance (no billing) keeps its
  branding, and the learner's own test covers the hobby, switch-off,
  and policy-off cases.
- The learner can say the difference between a capability and a
  policy, name the file each lives in, and say what `CLAUDE.md` makes a
  review blocker.
