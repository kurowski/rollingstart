# Rolling Start — a Claude Code native codebase tutor

*Reboot plan, draft 2: revised after the P0 spike. Same name, same
goals, new runtime. What the spike changed is marked in § 10 and
recorded as it happened in `spike/NOTES.md`.*

## 1. What changes, what doesn't

**Same goals.** Get an experienced engineer productive in a codebase they
had no hand in building. An author supplies what a model can't infer
(the lay of the land, what is exemplary and what is legacy, the local
rituals, a few PRs that show how work is done here). Each learner takes a
different route, shaped by what they already know (languages,
frameworks, tooling) and by where they are going: one new hire needs
the billing side of the app and does not care about scheduling, another
the reverse, a third wants all of it at working depth today and will go
deep later. Real work, with feedback on the diff from the same tutor who
was there while it was written.

**The principle, restated.** The [original conception of Rolling
Start](https://github.com/kurowski/rollingstop) (hereafter "Rolling
Stop") said "the author owns the
destination; the tutor owns the route," and that over-prescribes the
experience. Now: **the author describes the landscape, the learner picks
the destination, the tutor points the way.** Not entirely self-directed,
though: the author also lays out a suggested course of study, and that
course is what the learner pushes on. The learner is not picking a book
off the shelf; they are opening a choose-your-own-adventure book the
author wrote, and the first page is already turned.

**Two kinds of lesson, because two kinds of codebase.** In a repo with a
long history of humans writing the code, and the intent to continue, a
lesson is: the learner writes the change, the tutor reviews it. In a
repo that is largely agentically authored, what matters is different:
can the learner articulate a bug fix or a feature request well enough
for an agent to act on, steer it over as many turns as it takes, review
what comes back and spot the mistakes agents make, and suggest an
architectural improvement when one is warranted. There a lesson is: the
learner directs a coding agent, in their own session, the way they do
at work; the tutor watches how it goes and, at the end, reads the whole
of it. The author chooses per lesson. The first kind is table stakes and is what most orgs expect
today; the second is where this project is aimed, and is expected to be
the majority of lessons before long.

**Different premise.** Rolling Stop's founding claim was that state,
verification, and repeatability are "the parts an LLM does unreliably
alone," so a deterministic Go runtime should own them and the model
should only generate and judge. Two things have moved since:

1. The deterministic loop was never going to be *capable* enough. ADR
   0001 is the tell: the honest form of "has this learner demonstrated
   competence at this node" is a rubric a judge reads against evidence,
   and it lost only because M3 had to settle satisfaction with no model
   call. Every format decision downstream (count-based bars, kinds as
   load-bearing enums, verifiers as command selections) was shaped by
   that constraint, not by what teaching needs.
2. The learners already run Claude Code alongside whatever editor they
   use, so a second long-running process with its own TUI, IPC, and
   watcher is a tool they have to learn *in order to* learn the
   codebase. The editor was never the thing to replace; the bespoke
   runtime was.

**What survives, unchanged in spirit:**

- The author's map is authoritative about what is *there*; the tutor
  never invents regions, only detours.
- Feedback is grounded: it cites real code and is labelled by
  provenance (local convention vs. language norm).
- Content comes from the repo and its history, not from hand-writing
  exercises. Generated exercises are proven solvable before a learner
  sees them.
- Lifecycle rituals are first-class content, and destructive ones prompt.
- The tutor never orchestrates the environment.
- On-ramp, not residence: no decay model, no drilling. Explanation only
  in service of a task.
- Escalation to a human is a feature: repeated failure, a
  piece of feedback the learner disputes, a gap many learners share.

**What is dropped, deliberately:**

- The Go binary, the TUI, the IPC, the filesystem watcher, the strict
  loaders, `rolling doctor` as a product. Claude Code is the runtime.
- A runtime of our own. The tutor runs in Claude Code. Learners keep
  editing in VS Code, Vim, or whatever they use, in concert with it,
  exactly as before: the working copy is the shared surface, and the
  tutor reads it straight off the filesystem, uncommitted and unstaged,
  whenever it looks. The learner never has to commit for the tutor to
  see their work.
- "Runs without an API key." Everyone here has Claude Code.
- Deterministic satisfaction, and the examiner. Rolling Stop split the
  coach from a grader that ran in fresh context on the diff alone,
  because only an examiner's verdict could move the skill graph. That
  is an assessment tool's seam, and this is a tutor. Feedback is
  **formative and in the loop**: the same tutor that was there while
  the change was written reads the diff against the rubric, says what
  is good and what is missing, and a lesson is satisfied when tutor and
  learner agree it is, with the reasons written to evidence. Nobody is
  being ranked. A too-generous "you've got it" costs a gap that shows
  up later as a detour, which is the normal course of tutoring.
- Author-time pooling of generated tasks as the primary source. The
  learner has a capable agent in the loop, so tasks can be generated
  just in time, against the repo as it is now, which also retires the
  pool-staleness risk. A pool remains possible for expensive tasks.

**Where determinism still earns its keep** (and how it is provided
without a runtime): see § 5. The short version is: files for state,
shell scripts for the few operations that must be exact (diff capture,
profile validation, both-ways verification), hooks for the few rules
that must hold even when the model is persuaded otherwise.

## 2. The three roles, mapped onto Claude Code

| Role | Who | Claude Code mechanism |
|---|---|---|
| **Author** | A staff engineer who knows the codebase | Author-side skills (`/rolling:init`, `/rolling:mine`, `/rolling:verify`, `/rolling:review-proposals`) that draft a **map** of the codebase from the repo and its history for the author to edit, and keep it honest afterwards. Output is committed files in the target repo. The author describes; the author does not decide where any learner ends up. |
| **Tutor** | Claude Code running the learner-side plugin | Learner-side skills (`/rolling:start`, `/rolling:next`, `/rolling:done`, `/rolling:ask`, `/rolling:escalate`), a small set of hooks, and a profile on disk. One conversation: the coaching and the feedback are the same voice. In a `direct` lesson it also watches the learner's coding session as it happens, from a log the plugin's hooks write. |
| **Learner** | The engineer being onboarded | Starts from the author's suggested course at intake and bends it: drops a region, adds one, changes a depth, says why. Works in Claude Code as usual; in a `direct` lesson that means a second, ordinary Claude Code session they direct themselves. The plugin changes how the tutor's session behaves *during a lesson*, and nothing else. |

The tutor is one voice. What keeps it honest is not a second examiner
but three habits held by mechanism: the verifier runs deterministically
before it speaks, its feedback must cite the code it is about, and the
rubric it reads against is the author's, in the lesson file, not its own.

## 3. Repository and distribution

One new repo, which is a **plugin marketplace** containing two plugins,
one per side:

```
rollingstart/                        # the new repo
  .claude-plugin/marketplace.json    # lists the plugins below
  plugins/
    rolling/                         # the learner's plugin: what a target repo enables for everyone
      .claude-plugin/plugin.json
      skills/
        start/SKILL.md               # intake: background, the author's course, the learner's changes → profile
        next/SKILL.md                # route: choose the next lesson/task for this learner
        lesson/SKILL.md              # serve a task; coach behaviour rules
        done/SKILL.md                # run verifiers, capture diff, feedback against the rubric, update profile
        ask/SKILL.md                 # grounded Q&A that never solves the open task
        escalate/SKILL.md            # write an escalation with the trace attached
      agents/
        second-opinion.md            # optional, learner-invoked: fresh eyes on a diff, never a gate
      hooks/hooks.json               # SessionStart (profile summary); PreToolUse (write-mode scope guard;
                                     #   profile guard); UserPromptSubmit/PostToolUse/Stop (the session log,
                                     #   written only while a direct task is open and this is not the tutor)
      bin/                           # on PATH while enabled; the shared toolkit both plugins call:
                                     #   verify, diff, begin-task/end-task (the throwaway branch),
                                     #   watch-session, the hook handlers, map and profile checks
    rolling-author/                  # the author's plugin: enabled by the author alone; requires rolling
      .claude-plugin/plugin.json
      skills/
        init/SKILL.md                # draft the map from the repo
        mine/SKILL.md                # turn history into candidate tasks
        verify/SKILL.md              # prove tasks solvable both ways (calls rolling's bin/)
        proposals/SKILL.md           # review detours learners needed → promote
  docs/
    design.md                        # rewritten from Rolling Stop's, shorter
    map.md                           # the format the author writes (the spec)
    profile.md                       # the format the tutor writes
    decisions/                       # ADRs, same discipline as before
  examples/
    rallly/                          # a complete map for Rallly, copyable
  evals/                             # claude plugin eval suites: the tests of a prompt product
```

**Public plugin, private maps.** The plugin is open source, Apache-2.0
as before, in a public GitHub repo, meant to be used by many orgs. What
is private is each org's map, which lives in that org's own codebase
and never leaves it. The plugin knows nothing about any codebase; the
map knows everything about one.

**Why a marketplace and not a bare plugin.** A marketplace is the unit a
project's settings can point at and pin (`extraKnownMarketplaces`,
`enabledPlugins`), and it holds both plugins in one clone with one CI
and one docs tree.

**Why two plugins.** The learner should never see `/rolling-author:init`
in a menu, never have to be told which skills are not for them, and
never have the tutor auto-invoke `mine` or `verify` mid-lesson because a
description matched. Two plugins make all three true by omission rather
than by guard. The author side can also churn while the learner side
stays boring. The shared code is small (both-ways verification, map and
profile checks) and lives in `rolling`'s `bin/`, which is on PATH while
the plugin is enabled, so `rolling-author` calls it by name; the author
has `rolling` installed regardless, since they must run their own map.
Two things P1 confirms, since the spike ran from a clone's `.claude/`
and never exercised them: that one plugin's `bin/` is callable from
another's skill, and whether a plugin can declare that it requires
another so a missing `rolling` fails at install rather than at runtime.

**The install story, and it is the whole onboarding pitch.** the author
commits two things to the target repo: the map, and a
`.claude/settings.json` that registers the public marketplace and
enables `rolling`. The learner clones the repo, opens Claude Code, and is
offered the tutor. No binary, no PATH, no second process. The author
enables `rolling-author` in their own user settings; nobody else sees it.

**Why the map lives in the target repo, not in a plugin.** The map is
about *this* codebase and changes with it; it is reviewed in the same
PRs. The plugin looks for `.rolling/` in the repo root; a map-as-plugin
variant for codebases that cannot be modified is a later option, not the
default.

**Why the learner's state does not live in the repo.** Draft 1 kept the
profile in the working copy, gitignored by its own `.gitignore`, so it
would survive a container rebuild. The spike showed what that costs:
the coding agent in a `direct` lesson can grep its way to the reference
solution, the repo's own linters find whatever the tutor writes, and
every tree check has to exclude the directory. So the learner's state
moves out of the tree, into the plugin's data directory keyed by the
repository the way Claude Code keys its own session state
(`~/.claude/projects/<encoded path>`). It is per user, never committed,
invisible to the repo's tooling, and in a devcontainer it sits in the
same home volume as Claude Code's login, which is the answer to the
rebuild worry. The map stays in the repo; it is the author's and
committed.

## 4. Formats: much lighter, written for a model to read

Rolling Stop's formats were designed for a strict loader. These are
designed for a model with a validator, so they carry prose where the old
ones carried enums.

```
<repo>/.rolling/                       # the author's, committed
  map.md                               # the landscape: regions, the suggested course(s), corpus pointers,
                                       #   operations, commands, the mistakes agents make here
  lessons/<slug>.md                    # one per node: frontmatter + body
  tasks/<slug>.md                      # optional pre-authored tasks; generated ones can be pooled here

${CLAUDE_PLUGIN_DATA}/repos/<encoded repo path>/   # the learner's, never in the tree
  profile.md                           # who this learner is, and where they are going
  task.md                              # the open task: lesson, mode, branch, base, return-to, verifier
  reference.md                         # the held reference solution for the open task
  session.log                          # a direct lesson's coding session, written by hooks
  evidence/<lesson>.md                 # feedback, observations, the tutor's own interventions, appended
  detours/<slug>.md                    # lessons the tutor created for this learner
  escalations/                         # what went to a human, with the trace
```

**`map.md`** — the author's description of the landscape, and the
author's advice about crossing it, with nothing in it about any
particular learner. The **regions** of the codebase (`billing`,
`scheduling`, `platform` …), each with a sentence on what
lives there and where. The **suggested course**: the author's default
itinerary, regions in a sensible order with a depth for each, opening
with the lessons everyone needs (local-dev setup, how a change ships
here). An author who knows their teams can write more than one
(`billing engineer`, `scheduling engineer`, `generalist`), and intake
offers the closest fit. The commands (build, typecheck, test, lint); the
operations with destructive marking; the corpus pointers (exemplary
paths, legacy paths, exemplar PRs, definition of ready); the default
lesson `mode`; and, for `direct` lessons, the **mistakes agents make
here**: the author's list of the ways agentic changes in this repo go
wrong (a hand-rolled helper where a shared one exists, a migration
without a rollback, tests that assert the mock), which is what the
learner is taught to catch and what the tutor reads an agent's change
against at the end of a `direct` lesson.
There is no destination set: a course is a suggestion the learner
edits, not a requirement the tutor enforces.

**`lessons/<slug>.md`** — one per node. Frontmatter: `title`, `region`,
`depth` (one of `orientation`, `working`, `deep`), `mode` (`write` or
`direct`, see below; the map sets the default and a lesson overrides it),
`requires` (links), and `assumes` (general knowledge outside the repo the
lesson leans on: `prisma`, `trpc`, `postgres-jsonb`) so that routing can
skip or detour on the learner's background. Body: what the node is, why it matters *here*,
pointers into the code, and a **rubric**: what a good demonstration
shows. The rubric is prose the tutor reads the diff against, and shows
the learner. It replaces the count-based bar. Depth is how the map answers "just enough to be proficient today":
a region at `working` depth is its orientation and working lessons; at
`deep`, all of them.

**The destination is in the profile, not the map.** Intake writes it,
starting from the suggested course: the tutor lays the course out, the learner
pushes on it (drop scheduling, take billing to `deep`, keep the opening
lessons), and the result is recorded in the learner's words about why.
The billing hire ends up with the course minus scheduling and with
billing deepened; the one who wants all of it today keeps every region
and sets them to `working`, and can come back later and raise one to
`deep` without starting over. A learner who changes nothing has a
perfectly good destination: the author's. The tutor routes toward
whatever is written, and only that. Changing the destination is an
ordinary edit to the profile, offered whenever evidence suggests the
learner is somewhere they did not mean to be.

**Tasks** are generated just in time by the lesson skill from the node's
pointers and the repo's history (revert a fix and hand over the issue;
review a merged PR; extend a feature along an existing seam), and
self-verified before being served. A task carries: the brief, the
starting state (a branch and base commit, operations to run first), the
**verifier** (structured: which declared commands, which test files the
task adds), and a reference solution held back from the learner.

**Every task starts on a throwaway branch with its starting state
committed.** For a reverted fix, the branch is cut from the fix's
*parent* with only the fix's test brought forward, so the learner begins
from a clean tree, `git diff` and the editor gutter show nothing, and
the fix is not in the branch's history; reading it on the original
branch is a choice, not something shown. When the lesson ends the
learner's work is committed on the branch, the branch is kept, and they
are returned to where they were. The spike's first `write` task left the
"before" state as uncommitted changes on top of the fix, and every diff
was the answer; this is the fix.

The two modes use the same task differently. In a **`write`** lesson the
learner is handed the brief and writes the change; the ladder (use →
modify → debug → create → compare) is the vocabulary the route uses to
escalate difficulty. In a **`direct`** lesson the learner is handed the
*situation* (a failing behaviour, a user's request, a symptom) and
directs a coding agent in a second, ordinary Claude Code session: they
brief it, look at what came back, steer, ask for the checks and tests,
accept or send back, over as many turns as it takes, until they would
merge. Nothing passes through the tutor. The plugin's hooks on that
session log every prompt, file edit, command, and reply; the tutor
watches the log as it is written and reads all of it at `/done`. The
ladder here is articulate → steer → review → architect, and steering is
the baseline, not an upper rung. Nothing is planted: the spike showed
that a coding agent given a hidden instruction to do wrong and hide it
refuses and discloses, which is right of it; what the learner has to
catch is whatever the agent really did.

**Profile** — Markdown, appended by the tutor, validated by a script
(shape, not content). The mutation rules, rewritten for a tutor rather
than an examiner: a lesson is satisfied when the tutor, having seen the
verifier pass and read the diff against the rubric, says so and the learner
agrees, the reasons and any disagreement written to evidence;
observations made along the way go to evidence and never satisfy
anything on their own; in a `direct` lesson, a catch the tutor prompted
while watching is written to evidence and stays on the tutor's ledger,
never credited to the learner; detours are created by the tutor and
promoted by the author; and the destination is changed only by the
learner, in conversation, never by the tutor on its own.

## 5. The loop, and where each rule is enforced

```
/rolling:start  → intake: background, then the author's suggested course laid out region by region,
                  then the learner's changes to it (or none) → destination written to the profile
                → first lesson is usually the course's opener, local-dev setup: done when the commands run green
/rolling:next   → read map + profile → choose a reachable lesson inside the destination, skipping what
                  the background already covers → build a task from the map and history → throwaway branch,
                  starting state committed → prove it both ways → present it, mode first
    write:  the learner works, in their own editor; the tutor explains, points, asks; never writes
            inside the task's scope; runs the repo's checks when asked
    direct: the learner directs a coding agent in a second session; hooks log it; the tutor watches
            the log and speaks only on an event worth a word, as an offer, in its own window
/rolling:done   → run the verifier (deterministic tier: the repo's own commands), before the tutor speaks
                → capture what changed: the working tree against the task's base commit, nothing committed
                → write:  the tutor reads the diff against the rubric and the corpus pointers: what is good,
                          what is missing, what a maintainer here would say, with a line and a rule each
                → direct: the verifier's findings come off the learner's ledger first; then the session,
                          turn by turn: was the direction actionable and scoped, did they steer when the
                          agent drifted, did they ask for the checks, what did they send back, what did
                          they accept that a maintainer here would have bounced
                → satisfied when the tutor says so and the learner agrees; reasons to evidence either way
                → the branch is closed out and the learner returned; offer the next
```

| Rule | Enforcement |
|---|---|
| Feedback is formative and in the loop | The `done` skill is a step in the same conversation. Its inline commands run the verifier and capture the diff before the model's turn begins, so the deterministic result is on the table before any opinion is. Those inline commands always exit zero and report in text: a non-zero exit aborts the skill, which is the opposite of what a failing verifier needs. |
| Feedback is grounded | Every point of feedback carries a file, a line, a rule, and a provenance label (this repo's convention, or the language's norm). The skill has the tutor write the feedback to evidence in that shape; a script checks each cited path exists at the cited line and flags the ones that do not. Structure, not a second reader, is what stops hand-waving. |
| The human's ledger (`direct`) | Before the learner's direction or review is read, the verifier's findings are taken off the table: a type error, a lint failure, a failing test are the checks' job, and the only thing on the learner's ledger about them is whether they asked for the checks before saying done. What is judged is what a person directing an agent is responsible for: placement, convention, scope, a missing test, a design that will not age, and the steering that got there. The spike's first `direct` run graded the learner on things the tests catch; that was wrong and this is the correction. |
| A second opinion is available, never required | An optional `second-opinion` subagent with fresh context and read-only tools, invoked by the learner when they want fresh eyes on a diff (or by the tutor when the two disagree). It advises; it does not satisfy or block anything. |
| Don't do the task for the learner (`write`) | The `lesson` skill declares a `hooks:` block, so a **PreToolUse** hook exists only while a `write` lesson is open. It reads the open task's scope from the profile and returns `permissionDecision: deny` for Edit/Write inside it, except files the task marks as scaffold, where the tutor may leave `TODO(human)` markers the way the built-in Learning output style does. The hook is the one rule that must hold even when the learner asks nicely. |
| The coding session is a real session (`direct`) | The learner's coding agent is an ordinary Claude Code session in the same repo, not a subagent of the tutor and not primed by it. The plugin's hooks (`UserPromptSubmit`, `PostToolUse`, `Stop`) apply to every session where the plugin is enabled; the handler writes to the session log only while a `direct` task is open and the session is not the tutor's own, whose id the lesson skill records in the task when it starts. A `PreToolUse` hook denies that session any read or write of the learner's state directory. Whatever the learner sets for their tutor session (an output style, say) must not reach the coding session by way of shared per-directory settings; the skills say what they need, and the evals check it. |
| The tutor watches, sparingly (`direct`) | The lesson skill starts a Monitor on the session log, filtered to prompts, replies, and file edits, for the life of the session. The tutor speaks only on an event worth a word: the agent editing outside the task's scope and the learner not noticing, a result accepted without the repo's checks, the same ask rephrased a third time. One or two lines, as an offer, in its own window, written to evidence as its own intervention. Otherwise an empty turn. Triggers it cannot observe from the log are not triggers. |
| No fourth wall | The checks a learner runs during a lesson are the same tools a developer here uses in the normal course of work: the map's declared commands, given verbatim. The tutor names the lesson's mode up front and never cites a script, a task file, or a profile file; those are its own. Nothing the tutor puts in the repo shows up in the repo's own checks, which the storage layout now guarantees rather than a gitignore. |
| Every task on a throwaway branch | `begin-task` cuts the branch and commits the starting state before anything is presented; `end-task` commits what the learner left, keeps the branch, and returns them. The tutor does no free-form git while a task is open beyond applying and undoing the reference to prove the task, and those commands prompt on purpose. |
| Verifiers are structured, never shell | A task's verifier names declared commands and test files; the `done` skill's inline steps run those and only those, before the model's turn begins. Arguments are words, never shell: anything with a metacharacter is rejected. Operations are the author's shell, code-reviewed in the repo. |
| Destructive operations prompt | Operations marked destructive are run only after an explicit confirmation in the conversation, on top of Claude Code's own permission prompt. Skills pre-approve only the exact commands they use; `Bash(pnpm *)` would have pre-approved the destructive reset, and the spike caught that in review. |
| Never orchestrates the environment | The tutor never brings services up, installs toolchains, or fixes the environment; a failing command is reported with the local-dev-setup lesson offered. Whether the *learner* starts services in a setup lesson is the author's call, per environment, said in the map: a bare-metal team's map has `pnpm docker:up` as a step, a contained one has the services as a precondition. |
| Tasks are solvable | The both-ways check applies the reference on the starting branch, runs the verifier, restores the committed starting state, then runs it on that state; a task that fails either way is discarded and the failure logged for the author. |
| The tutor points the way, and only the way | The `next` skill serves lessons inside the learner's destination and detours off them; it never serves a region the learner did not choose, and never edits the destination. It justifies each choice against the profile in one line written to evidence. A route that reads as a fixed order across learners with the same destination and different backgrounds is a failing eval. |
| Any editor | The learner's edits in their own editor are the normal case, not an exception. The tutor reads the working copy directly with Read and Grep, so a file saved in Vim is as visible as one Claude wrote. At `done`, the change is the working tree against the task's base commit, taken by script; nothing has to be committed or staged. The write-mode hook governs only what Claude writes; what the learner writes is theirs. |
| Detours are bounded | Detour depth capped in the next skill; at the cap, escalate rather than route. |
| Profile survives | In the plugin's data directory, keyed by repo, per user, never in the tree (§ 3). A **SessionStart** hook injects a profile summary as `additionalContext`, so every session opens knowing where the learner is. |

## 6. What the harness gave that a plugin has to earn back

Being honest about the trade:

- **Repeatability.** Two runs of the Go loop were identical; two runs of
  a skill are not. Mitigation: evals with fixed fixtures (a repo at a
  pin, a seeded profile) asserting *properties* (feedback cites code;
  the tutor refused to write the solution; a failing verifier was never
  waved through; two profiles diverge), not transcripts.
- **State integrity.** A loader rejected a broken profile; here the model
  writes it. Mitigation: append-only evidence, a validating script run by
  the done skill before and after it writes, and a profile format simple
  enough that a diff is reviewable.
- **An examiner.** Dropped on purpose (§ 1). What is kept from the
  non-sycophancy argument is the part that applies to a tutor: the
  verifier speaks first, feedback cites code, and the rubric is the
  author's. `claude -p --bare` with a JSON schema remains the right tool
  if a clean-room reader is ever wanted for something (a cohort-level
  audit, say), and is what `second-opinion` would use.
- **A watcher.** Claude sees the edits it makes, and the working copy
  is read directly whenever the tutor looks. In a `direct` lesson the
  tier-1 event coach is back as a native thing: the plugin's hooks on
  the coding session write a log, and a Monitor in the tutor's session
  turns each line into a notification. Fired on events, offering rather
  than asserting, exactly as Rolling Stop specified it and never built.
- **A tool of our own to test.** Go had `go test`. The tests of this
  product are `claude plugin eval` suites (fresh `claude -p` sandbox per
  case, graders of type `regex`, `tool_used`, `tool_order`, `file_exists`,
  `llm`, and a with/without-plugin baseline) plus script unit tests.
  Plugin eval is early access and enabled per organization; if it is not
  on for yours, the same cases run under a small script around
  `claude -p --bare` until it is.

## 7. Phases

Each phase ends with something a person can use. No phase depends on a
format that has not survived contact with Rallly.

**P0 — Spike. Done** (2026-09-11 to 09-13; `spike/`, merged as PR #1).
Three skills, a handful of scripts, a five-lesson Rallly map, and a
contained runner, dropped into a Rallly clone and driven by hand. The
premise held; the maintainer called it during the first lesson. `direct`
mode needed a redesign mid-spike and got one. Everything it changed is
in § 10 and in `spike/NOTES.md`; the spike's code is scaffolding and
none of it is the plugin.

**P1 — The learner loop as a plugin, both modes.** Marketplace +
`rolling` skeleton; `start`, `next`, `lesson`, `done`; the storage layout
of § 3 and § 4 (state out of the tree); the throwaway-branch scripts,
the verifier, the diff, the session-log and profile-guard hook handlers,
and the watch, all in `bin/`; the plugin's `hooks.json` with the
tutor-or-not test; a profile validator; a SessionStart hook. `docs/map.md`
and `docs/profile.md` written as the specs. The Rallly map grows to 8–10
lessons with rubrics, regions, depths, and modes, and its list of agent
mistakes grows from the spike's. The old repo's `CLAUDE.md`, workflow
skills, and ADR discipline come across, since this is the first real
branch. *Exit:* three lessons end to end across three sessions, at least
one `direct`, with the profile reflecting it; three seeded profiles (one
region deep, a different region deep, every region at working depth)
get three different routes, and two seeded backgrounds with the *same*
destination still diverge; nothing the tutor writes is visible to the
repo's linters or to the coding session.

**P2 — Enforced, and measured.** PreToolUse hook for `write` lessons;
feedback shape enforced by the citation check; `second-opinion`;
escalation skill; detours with the depth cap. First eval suite, on the
properties the spike showed matter: did the tutor write the solution in
a `write` lesson; did it cite code; did a failing verifier ever get
waved through; in a `direct` lesson, did the verifier's findings stay
off the learner's ledger, was a tutor-prompted catch credited to the
learner, did the tutor speak at the right moments and stay quiet
otherwise, did any of the tutor's plumbing reach the learner. *Exit:*
evals pass on two model versions; a planted *gap in the learner's
background* (not a planted mistake) earns a correctly named detour
grounded in Rallly's own code.

**P3 — The author's plugin.** `rolling-author`: `init` drafts the map
from a bare repo (regions from the module structure and history,
candidate lessons at each depth, corpus pointers, operations from the
package scripts and CONTRIBUTING, the environment's shape); `mine` turns
bugfix commits and merged PRs into task candidates and grows the list of
agent mistakes from the repo's own review history; `verify` proves
tasks; `proposals` reviews detours that several learners needed. *Exit:*
an author gets from clone to a reviewable draft map in an afternoon, and
edits rather than writes.

**P4 — The upper rungs of `direct`.** Architecture (the learner is asked
what should change about how a region is built, and the tutor compares
it with the author's corpus pointers and the repo's own history) and
review of real history (the learner reviews a merged PR and the tutor
compares that review with what actually shipped and what the
maintainers said). Steering is no longer a rung here; the spike made it
the baseline of every `direct` lesson. *Exit:* a `direct` lesson on
Rallly at each rung that a strong engineer finds fair.

**P5 — Second target and release.** A Go repo (this plugin's own repo is
a candidate: it should be an instance of itself, as Rolling Stop meant
to be), a colleague onboarding onto something real, the authoring guide,
managed-settings install notes, and the question of whether the Rallly
example ships a `.devcontainer/` so anyone can run it contained the
standard way. *Exit:* a colleague who has never seen the target completes
a real task in it.

## 8. Risks particular to this approach

- **The tutor solves the task in a `write` lesson.** The default
  behaviour of a coding agent is to write the code, and `write` mode
  fights the grain of the tool. The hook is the backstop and the evals
  measure it. If it cannot be held, `write` lessons get narrower (more
  scaffold, smaller owned hunks) while `direct` lessons, which go with
  the grain, carry more of the course. In the spike, prose held.
- **The tutor is noise while watching.** A `direct` lesson's coding
  session wakes the tutor on every prompt, reply, and edit. If it
  comments on most of them, the learner stops looking at its window and
  the coaching is lost. The rule is a short list of triggers and an
  empty turn otherwise; whether a model holds an empty turn on a
  notification is measured, not assumed. If it cannot, the watch narrows
  to replies only, or moves to a summary at `/done`.
- **Two sessions, one directory.** The tutor and the coding session
  share the repo's `CLAUDE.md`, skills, MCP servers, and per-directory
  settings. Most of that is wanted or harmless; the spike's one bad
  instance was an output style set for the tutor reaching the coder. The
  plugin has no launcher to pin settings per session, so the mitigation
  is the skills stating what they need and an eval that sets something
  odd in the directory and checks the coding session is unaffected.
- **Context contamination.** The target repo's own `CLAUDE.md`, hooks,
  and MCP servers are all live in the tutor's session too; the plugin's
  instructions compete with them, and a plugin cannot ship a CLAUDE.md
  of its own. Rallly ships a `CLAUDE.md`, fourteen skills, and an MCP
  server, and the spike's tutor sat in the same menu as all of them.
  Mitigation: the lesson skill states precedence explicitly; evals run
  against a repo with a busy `CLAUDE.md`.
- **The tutor is too kind.** With no examiner, the pressure toward
  "looks great, moving on" is the model's default and the learner's
  wish. The mitigations are structural (verifier first, citations
  required, the author's rubric on screen, the human's ledger) and
  measured by the eval that plants a diff missing something the rubric
  names. If that eval cannot be held, `second-opinion` becomes a default
  step rather than an option, and that is the point at which to revisit,
  not before.
- **Prompt drift.** A model update changes the tutor's behaviour without
  a code change. Mitigation: the eval suite is the regression test, run
  on each model the audience uses.
- **Author effort.** Still the risk most likely to kill it. Now cheaper
  twice over: the author's draft is the default and the author edits,
  and describing what is there is less work than deciding what
  competence means.
- **The tightrope moves, it does not vanish.** A learner who trims the
  course to `billing: orientation` and stops has not been failed by the
  tutor; one who sets everything to `deep` and never arrives has. The
  suggested course is the author's guard against both: a reasonable
  default that most learners will bend rather than replace. The tutor
  should say when a destination looks unreachable in the time the
  learner has, and offer the course's shape back, without ever choosing
  for them.
- **Inline command limits.** Skill inline commands abort the skill on a
  non-zero exit and run under a timeout the docs do not state. Every
  script the skills run inline exits zero and reports in words, and
  verifiers are scoped to a workspace and a file rather than a whole
  suite. The spike never hit the timeout; P1's evals should.
- **AGPL.** Rallly is AGPL; a public example map with reference
  solutions is the same derivative-work question as before. Decide before
  the example ships publicly; a private target has no such problem.
- **Script dependencies.** Scripts must not assume `jq`, Python, or Node
  beyond what the target repo already requires. The spike's hook
  handlers are Node, which every Claude Code host has; the rest is
  POSIX sh and git.

## 9. Carried over from Rolling Stop

Worth copying, not rewriting: `docs/design.md` (principles, though its
"Who it's for" shrinks to teams onboarding engineers onto a codebase
they didn't build, who already use Claude Code; the locked-down-laptop
and source-can't-leave-the-building material goes), the
landscape survey, the Rallly example's command and operations tables and
the reasoning under each, the `[[slug]]` link and optional-node rules
from the skills spec, the ADR discipline, and the workflow skills
(`plan-milestone`, `refine-issue`, `implement-issue`, `milestone-endgame`),
which are about how work happens and are not tied to Go.

Leave behind: the Go tree, the loaders, `rolling doctor`, ADR 0001, the
TOML profile decision, and the strict-frontmatter posture.

## 10. Decided

**During drafting** (2026-09-09):

- **Two lesson modes, the author's choice per lesson.** `write`: the
  learner writes, the tutor reviews. `direct`: the learner directs a
  coding agent, the tutor watches and then reviews how it went. `write`
  is offered because orgs with a history of hand-written code expect it
  and will not take the project seriously without it; `direct` is the
  point of the project and is expected to become the majority of
  lessons.
- **Map in the target repo.** `.rolling/` at the root, reviewed in the
  codebase's own PRs, because that is the easiest thing to adopt. A
  per-codebase plugin in the marketplace would suit open source projects
  and is out of scope for now.
- **Two plugins.** `rolling` for learners, `rolling-author` for authors,
  one marketplace repo, shared scripts in `rolling`'s `bin/`.
- **Names.** Repo and domain `rollingstart`; plugin and map directory
  `rolling`; roles are Author, Tutor, Learner in every document.

**By the spike** (2026-09-11 to 09-13; each with its moment in
`spike/NOTES.md`):

- **No planting.** A coding agent given a hidden instruction to make a
  mistake and hide it refused and disclosed the instruction. That is the
  model behaving well and it kills the mechanism. The list of agent
  mistakes stays as what the learner is taught to catch.
- **`direct` mode is the learner's own session.** Not a subagent the
  tutor dispatches with a pasted brief, and not one shot: a second,
  ordinary Claude Code session the learner directs over as many turns
  as it takes, logged by the plugin's hooks, watched by the tutor as it
  happens, read whole at `/done`. Steering is the baseline.
- **The human's ledger.** The verifier's findings come off the table
  before the learner's direction and review are read; a person
  directing an agent is not responsible for what the tests catch, only
  for having asked for them. A catch the tutor prompted stays on the
  tutor's ledger.
- **A throwaway branch per task**, cut from the fix's parent with only
  its test brought forward, so nothing about the answer is in the diff
  or the branch's history.
- **No fourth wall.** The learner's checks are the repo's own commands;
  the tutor names the mode up front and never cites its scripts or
  files.
- **The environment's shape is the author's to describe.** The tutor
  never orchestrates it; whether the learner starts services in the
  setup lesson depends on the environment, and the map says which.
- **Learner state out of the tree.** In the plugin's data directory,
  keyed by repo, so the coding session cannot reach the reference, the
  repo's tooling never sees the tutor's files, and nothing has to be
  excluded from anything.
- **The tutor watches live.** Longer lessons need coaching before they
  are over; a Monitor on the session log gives the tutor each prompt,
  reply, and edit as it happens, and a short list of triggers says when
  to speak.
