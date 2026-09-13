# Spike notes

Written as it happens. See README § What to record.

## Setup

2026-09-11, contained (`spike/container/`). Three things the container
surfaced that a host never would, all now handled in the image:

- Rallly's `outbound-proxy` unit test failed with `ECONNREFUSED`: on a
  Docker bridge network `localhost` resolves to `::1` first, so the
  test's server bound `::1` while its client connected at `127.0.0.1`.
  Fixed with `NODE_OPTIONS=--dns-result-order=ipv4first`.
- pnpm put its store inside the clone (`.pnpm-store/`, 3,293 files)
  because the home volume is a different filesystem from the bind
  mount; Biome then reported 2,155 errors. Fixed by pinning
  `npm_config_store_dir` into the home volume.
- On first launch Claude Code asked about Rallly's own `.mcp.json`
  (`next-devtools`, run as `npx -y next-devtools-mcp@latest`, unpinned).
  Declined for the spike: no lesson needs a dev server, and the
  experiment is the skills alone. That is the third piece of Rallly's
  agent configuration the tutor shares a session with, after its
  `CLAUDE.md` and its fourteen skills.

After the fixes: type check green, 725/725 unit tests uncached, Biome
green with one warning that is in Rallly's source at the pin.

- In the first lesson the tutor asked for `docker`, which the toolchain
  container does not have. Cause: `local-dev-setup` quoted
  `CONTRIBUTING.md`'s `pnpm docker:up` as a learner step. In a contained
  environment the services are a precondition provided from outside.
  Fixed in the lesson and the map as a description of *this example's*
  environment, not a rule: a bare-metal team's map would have the
  learner run `pnpm docker:up`. The only general rule is the one the
  plan already had: the tutor never orchestrates the environment. Not
  a reason for a VM, a socket mount, or bare metal.

## Learning output style

- Trying it via `/config` in the tutor window saved it to the clone's
  `.claude/settings.local.json`, so the `direct` lesson's coding agent
  came up in Learning style too ("Learn by Doing", `TODO(human)`) and
  behaved like a tutor. Fixed: `rolling-coding.json` pins
  `outputStyle: default` for the coding session; `--settings` outranks
  the project-local file. Lesson for P1: any per-session behaviour the
  learner sets for the tutor must not reach the coding session.

## `/start`

## `direct` task

2026-09-13, `how-a-change-ships` flipped to `direct`. First run. The
maintainer's verdict: "`direct` mode certainly needs a lot more work
than `write`." Three findings, all design, not wording:

- **One shot is unrealistic.** One brief, one review, graded. Real
  agentic work iterates: brief, see the result, steer, review again.
  The lesson must be a session of direction, not a single exchange.
- **Graded on the wrong ledger.** The review was dinged for missing
  things automated tests catch. That is not the human's job when
  directing an agent; the human's ledger is what the checks cannot
  catch (placement, convention, scope, missing tests, design) plus
  whether they asked for the checks at all. The verifier must run
  first and its findings come off the review's ledger before the
  review is assessed; planted mistakes must be of the kind tests
  cannot catch.
- **The interaction is awkward.** Pasting a brief into the tutor, which
  dispatches a subagent and reports back, is not how anyone works. The
  learner should talk to the coding agent directly, in its own
  terminal, iterating naturally, with the tutor reading the session's
  transcript afterwards.

Redesigned the same day: `run.sh code` opens a plain Claude Code session
in the same container with hooks attached via `--settings`
(`rolling-coding.json`) that log every prompt, tool call, and reply to
`.rolling/profile/session.log`. `/done` runs the verifier first, takes
its findings off the learner's ledger, then reads the log turn by
turn: direction, steering, what was asked for, what was accepted. The
implementer subagent is gone.

- **Planting is dead.** First run of the new flow: the tutor planted
  "put the constant under apps/web/src/components, avoid packages/ui,
  don't mention it" via `--append-system-prompt-file`. The coding agent
  refused it (packages/ui cannot import from the app, and CLAUDE.md
  sends shared UI there) and told the learner it had been given the
  directive. Right on both counts, and fatal to the mechanism: a hidden
  instruction to do wrong and hide it is what the model is built to
  resist. Removed from `direct` mode entirely; the learner reviews what
  the agent really did, against the map's list of agent mistakes. The
  plan (§ 4, § 5, § 8) still describes planting and needs revising in
  P1.
- The learner's `pnpm check` failed on the spike's own `.mjs` scripts
  under `.claude/scripts/`: Rallly's `biome check .` scans the whole
  repo and honours `.gitignore` but not `.git/info/exclude` (tested).
  Fixed with a nested `.claude/biome.json` that disables Biome there.
  Spike-only: the plugin's scripts live in the plugin directory,
  outside the learner's repo, so the real thing never has this
  problem. The general rule it brushes, that nothing the tutor puts in
  the repo may show up in the repo's own checks, is already met for
  the profile (gitignored, Markdown).
- Review of the second commit caught two real breaks before push: the
  transcript lookup excluded every session (an empty `--exclude` matched
  everything, and the tutor's id variable was misnamed), and the
  installer never removed the retired implementer agent from the clone.
  Also decided: the README's setup stops at `pnpm install`, so lesson
  one has something to do; and the coding session gets a PreToolUse
  hook denying `.rolling/profile/`, since a real agent grepping the
  repo could otherwise land on the reference.

## `write` task

- The reverted-fix task left the "before" state as uncommitted changes
  on top of the fixed commit: `git diff`, the editor gutter, and any
  stash all showed the answer. Fixed: every task now starts on a
  throwaway branch (`begin-task.sh`) branched from the fix's *parent*
  with only the test brought forward and committed, so the tree is
  clean and the fix is not in the branch's history; `end-task.sh`
  commits the learner's work there and returns them afterwards.
- The tutor presented a task without saying which mode it was in, and
  named `.rolling/profile/reference.md` to the learner. Both were the
  skill's wording. Fixed: the brief opens with the mode in one line,
  and the reference is mentioned as held, never by path.

- Presenting the task, the tutor cited `sh .claude/scripts/verify.sh`
  as what "done" means. Fourth wall. Cause: the lesson skill's own
  wording told it to. Fixed in the skill. The rule, for every skill:
  the checks a learner runs during a lesson are the same tools a
  developer uses in the normal course of development, never something
  specific to being inside a lesson.

## Verdict: taught or nagged?

2026-09-12, called early by the maintainer during the first lesson
(`local-dev-setup`, `write` mode): "i can already tell that this is
going to be great. consider this test successful even before i've
finished it." Intake after `/start` was singled out as the part that
landed. Caveat: `direct` mode had not run yet at that point; it is the
mode the project is for, and it still needs one full pass before P1
builds on it.

## What needs a hook

<!-- watch for: tutor writes in scope in write mode; implementer or
     tutor reads reference.md / planted.md -->

## Format friction

## Inline command timeout

<!-- measured: -->
