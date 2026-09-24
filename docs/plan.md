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

**And the reader holds the book.** Rolling Start is a README with a
coach in it, for professional engineers getting up to speed at work;
it is not a course that withholds a grade until a student has
performed. The tutor offers, explains, answers what is asked, and says
what it sees; the learner decides what to do, how much help to take,
and when a lesson is done. A rubric is what a maintainer would look
for in the change, never a set of questions the learner must answer.
The first fresh learner's second lesson found the tutor holding a
lesson open on questions nobody had asked, and this is the correction
(2026-09-21, § 10).

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
- Escalation to a human is a feature: the learner asking for one, a
  piece of feedback the learner disputes, a gap many learners share,
  the tutor stuck.

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
  is good and what is missing, and a lesson is done when the learner
  says it is, with the tutor's view written to evidence, reservations
  included. Nobody is being ranked, and nobody is being graded. A gap
  the tutor saw and the learner closed over shows up later as a
  detour, which is the normal course of tutoring; that is what the
  evidence is for.
- Author-time pooling of generated tasks as the primary source. The
  learner has a capable agent in the loop, so tasks can be generated
  just in time, against the repo as it is now, which also retires the
  pool-staleness risk. A pool remains possible for expensive tasks.

**Where determinism still earns its keep** (and how it is provided
without a runtime): see § 5. The short version is: files for state,
shell scripts for the few operations that must be exact (diff capture,
profile validation, both-ways verification), hooks for the few rules
that must hold even when the model is persuaded otherwise. A rule must
hold when breaking it costs someone something; everything else the map
or a skill says is a hint, and no script enforces a hint.

## 2. The three roles, mapped onto Claude Code

| Role | Who | Claude Code mechanism |
|---|---|---|
| **Author** | A staff engineer who knows the codebase | Author-side skills (`/rolling-author:init`, `/rolling-author:mine`, `/rolling-author:verify`, `/rolling-author:proposals`, `/rolling-author:adopt`) that draft a **map** of the codebase from the repo and its history for the author to edit, and keep it honest afterwards. Output is committed files in the target repo, or a map plugin. The author describes; the author does not decide where any learner ends up. |
| **Tutor** | Claude Code running the learner-side plugin | Learner-side skills: `/rolling:start` (intake), `/rolling:next` (chooses the lesson and hands off to) `/rolling:lesson` (the walkthrough, the offer of an exercise, and the coaching rules once one is open), `/rolling:task` (builds the exercise when the learner takes the offer), `/rolling:done`, `/rolling:cancel` (stops a lesson without finishing it), and later `/rolling:escalate`; a small set of hooks; and a profile on disk. One conversation: the coaching and the feedback are the same voice. In a `direct` lesson it also watches the learner's coding session as it happens, from a log the plugin's hooks write. |
| **Learner** | The engineer being onboarded | Starts from the author's suggested course at intake and bends it: drops a region, adds one, changes a depth, says why. Works in Claude Code as usual; in a `direct` lesson that means a second, ordinary Claude Code session they direct themselves. The plugin changes how the tutor's session behaves *during a lesson*, logs the coding session in a `direct` one, and does nothing else. |

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
        next/SKILL.md                # route: choose the next lesson for this learner and open it
        lesson/SKILL.md              # the walkthrough, the offer of an exercise; coach behaviour rules
        task/SKILL.md                # build and prove the exercise, when the learner takes the offer
        cancel/SKILL.md              # stop the open lesson without finishing it; nothing marked, nothing lost
        done/SKILL.md                # run verifiers, capture diff, feedback against the rubric, update profile
        escalate/SKILL.md            # (backlog, wanted) write an escalation with the trace attached
      agents/
        second-opinion.md            # (backlog, debated) optional, learner-invoked: fresh eyes on a diff, never a gate
      hooks/hooks.json               # every handler opens by reading the open task, if any, and this
                                     #   session's id, then acts on the answer: PreToolUse (write-mode scope
                                     #   guard, tutor only; state-directory guard, every session;
                                     #   ask-before-destructive, every session, task or no task);
                                     #   UserPromptSubmit/PostToolUse/Stop (the session log, for sessions
                                     #   that are not the tutor's while a direct task is open)
      bin/                           # on PATH while enabled; the shared toolkit both plugins call:
                                     #   verify, diff, begin-task/end-task (the throwaway branch),
                                     #   watch-sessions, export, the hook handlers, map and profile checks
      lib/rolling/                   # the toolkit's library; bin/ executables are a few lines each over it
      tests/                         # unittest against scratch repositories
    rolling-author/                  # (P3) the author's plugin: enabled by the author alone; requires rolling
      .claude-plugin/plugin.json
      skills/
        init/SKILL.md                # draft the map from the repo
        mine/SKILL.md                # turn history into candidate tasks
        verify/SKILL.md              # prove tasks solvable both ways (calls rolling's bin/)
        proposals/SKILL.md           # review detours learners needed → promote
        adopt/SKILL.md               # (2.0) move a map plugin into a repo's .rolling/, stamping where it came from
    rallly/                          # a map plugin: the Rallly map (below), installable in any Rallly clone
  docs/
    plan.md                          # this file: the design, and § 10, the dated decision record
    map.md                           # the format the author writes (the spec)
    profile.md                       # the format the tutor writes
    workflow.md                      # how work happens here
    plans/                           # one plan per checkpoint: the tracker, then the retrospective
  site/                              # rollingstart.dev, static, deployed by .github/workflows/pages.yml
  evals/                             # (P2) claude plugin eval suites: the tests of a prompt product
```

**Public plugin, private maps.** The plugin is open source, Apache-2.0
as before, in a public GitHub repo, meant to be used by many orgs. What
can be private is a map: an org's map lives wherever the org keeps it,
in its codebase or in a private marketplace, and never has to leave the
building. The plugin knows nothing about any codebase; the map knows
everything about one.

**Why a marketplace and not a bare plugin.** A marketplace is the unit a
project's settings can point at (`extraKnownMarketplaces`,
`enabledPlugins`), and it holds every plugin, the two example maps
included, in one clone with one CI and one docs tree.

**Why two plugins.** The learner should never see `/rolling-author:init`
in a menu, never have to be told which skills are not for them, and
never have the tutor auto-invoke `mine` or `verify` mid-lesson because a
description matched. Two plugins make all three true by omission rather
than by guard. The author side can also churn while the learner side
stays boring. The shared code is small (both-ways verification, map and
profile checks) and lives in `rolling`'s `bin/`, which is on PATH while
the plugin is enabled, so `rolling-author` calls it by name; the author
has `rolling` installed regardless, since they must run their own map.
Both halves of that are documented: a plugin's `bin/` executables are
on the Bash tool's PATH for the whole session while the plugin is
enabled, and `plugin.json` has a `dependencies` list whose failure mode
is that enabling fails and names the missing install. What the docs do
not say, and P1 must confirm first because the whole of `direct` mode
rests on it, is that a plugin's hooks fire in every session started in
a directory where the plugin is enabled, not only in sessions that
invoke one of its skills; and, second, that a skill can start a
Monitor. One more limit the docs do state: a plugin distributed through
claude.ai organisation settings may not include `bin/`, so an org that
installs that way needs the toolkit shipped another way, a P4 question.

**The install story, and it is the whole onboarding pitch.** An author
inside the project commits two things to the target repo: the map, and
a `.claude/settings.json` that registers the public marketplace and
enables `rolling`. Nothing about permissions: a skill's grants hold
only for the turn it ran in, and auto mode denies rather than prompts
when a lesson needs the learner's reply mid-way (found by the first
fresh learner's run), so the plugin's own PreToolUse hook allows the
toolkit's commands and the two hand-off skills, in every mode, and
nothing else (2026-09-23, § 10). The learner clones the repo, opens
Claude Code,
trusts the folder (a project's marketplace registration applies only
after that), and is offered the tutor. No binary, no PATH, no second
process. An author outside the project publishes the map as a plugin
instead, and the learner installs two things: `rolling` and the map.
The author enables `rolling-author` in their own user settings; nobody
else sees it.

**Where the map lives: with its author.** A map is a directory of
Markdown, and it can live in two places. Inside the target repo, at
`.rolling/`, committed and reviewed in the repo's own PRs: the natural
home when the author is inside the project. Or as a **map plugin**, a
directory with a manifest, published in any marketplace: the natural
home when the author is outside the project, or when a project would
rather not carry it. The distinction is who the author is, not what
kind of project it is; a company may keep its map out of the source
tree and an open source project may commit one. The format is identical
either way, and `rolling` resolves it with one question: is there a
`.rolling/` in the repo root, and if not, is there an installed map
plugin for this repo? A map plugin's manifest names the repo it is for
(a remote URL pattern and the release it was last checked against,
as a tag nearly always), and on
`SessionStart` its own hook writes its root and that declaration to a
fixed file in its own data directory, the one place a plugin can write
without knowing anyone else's paths; `rolling`'s resolver scans the
plugin data directories for those files and takes the one whose
declaration matches the current repo's remote, warning when the
checkout does not contain the declared release. When both a committed
map and a plugin map are present the repo's own wins, which is what
lets a project adopt an outsider's map without a flag day: commit it,
and the plugin is simply no longer consulted. `adopt` stamps the source
marketplace and version into the committed map, and the resolver says
so, without switching, when it can see a newer plugin map than the one
committed. The Rallly example is a map
plugin, because Rallly is not ours to commit to, and that is the demo:
`/plugin install rallly@rollingstart` in any Rallly clone.

**Why the learner's state does not live in the repo.** Draft 1 kept the
profile in the working copy, gitignored by its own `.gitignore`, so it
would survive a container rebuild. The spike showed what that costs:
the coding agent in a `direct` lesson can grep its way to the reference
solution, anything the tutor puts in the tree is one linter config away
from being checked, and every tree check has to exclude the directory. So the learner's state
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
  tasks/<slug>.md                      # optional, the author's pre-authored tasks

${CLAUDE_PLUGIN_DATA}/repos/<encoded repo path>/   # the learner's, never in the tree
  profile.md                           # who this learner is, and where they are going
  task.md                              # the open task: lesson, mode, branch, base (the starting-state
                                       #   commit), return-to (ref and sha), scope, scaffold, verify lines,
                                       #   held test paths, tutor-session
  reference.md                         # the held reference solution for the open task
  held/                                # the held test files, applied only while verify runs
  sessions/<session id>.log            # a direct lesson's coding sessions, one file each, written by hooks
  tasks/                               # tasks the tutor generated and kept for reuse
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
`requires` (links), `assumes` (general knowledge outside the repo the
lesson leans on: `prisma`, `trpc`, `postgres-jsonb`) so that routing can
skip or detour on the learner's background, and `test` (`held`, the
default, or `shown`; see tasks below). Body: what the node is, why it matters *here*,
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

**Tasks** are generated just in time by the `task` skill from the node's
pointers and the repo's history (revert a fix and hand over the issue;
review a merged PR; extend a feature along an existing seam), and
self-verified before being served; `lesson` presents them. A task
carries: the brief, the starting state (a throwaway branch, its `base`,
which is the starting-state commit the diff is taken against, and
operations to run first), the scope the change is expected to touch and
any scaffold paths, the **verifier** (structured: which declared
commands, and which test files the tutor holds), and a reference
solution held back from the learner.

**The fix's test is held back, not handed over.** Nobody at work is
given a failing test with an issue; writing one is part of the work,
and asking an agent for one is part of directing it. So the learner
gets the situation, as an issue, and writes their own test or has their
agent write it; held means not handed over unasked, and a learner who
asks to see it, or the reference, is shown it, with a note in evidence.
The test that shipped with the original fix stays with
the tutor as the verifier: at `/done`, after the learner's diff has
been captured, `verify` applies it, runs it, and reverts it, setting a
learner's own test at the same path aside for the run and restoring it,
so it is never in the diff and never lingers in the tree: a hidden
acceptance check, the way CI has expectations nobody sees verbatim.
Whether the learner wrote a test, and whether it tests the right thing,
is then on their ledger rather than given away. A held test written too
close to the original fix can fail a valid implementation that took a
different shape; that is a signal for the tutor to read, not a verdict,
and the tutor says so rather than marking the task open. The spike's
lesson showed the test, and it named half the answer. An author can
still mark a lesson's test as shown, the Exercism shape, for early
`write` lessons where the point is the mechanics of the repo rather
than the analysis; held is the default.

**Every task starts on a throwaway branch with its starting state
committed.** For a reverted fix, the branch is cut from the fix's
*parent*, so the learner begins from a clean tree, `git diff` and the
editor gutter show nothing, and the fix is not in the branch's history;
reading it on the original branch is a choice, not something shown.
When the lesson ends the learner's work is committed on the branch, the
branch is kept, and they are returned to where they were. The spike's
first `write` task left the "before" state as uncommitted changes on
top of the fix, and every diff was the answer; this is the fix.

The two modes use the same task differently. In a **`write`** lesson the
learner is handed the brief and writes the change; the ladder (use →
modify → debug → create → compare) is the vocabulary the route uses to
escalate difficulty. In a **`direct`** lesson the learner is handed the
*situation* (a failing behaviour, a user's request, a symptom) and
directs a coding agent in a second, ordinary Claude Code session: they
brief it, look at what came back, steer, ask for the checks and tests,
accept or send back, over as many turns as it takes, until they would
merge. Nothing passes through the tutor. The plugin's hooks on that
session's log every prompt, file edit, command, and reply; the tutor
watches the logs as they are written and reads all of them at `/done`. The
ladder here is articulate → steer → review → architect, and steering is
the baseline, not an upper rung. Nothing is planted: the spike showed
that a coding agent given a hidden instruction to do wrong and hide it
refuses and discloses, which is right of it; what the learner has to
catch is whatever the agent really did.

**Profile** — Markdown, appended by the tutor, validated by a script
(shape, not content). The mutation rules, rewritten for a tutor rather
than an examiner: a lesson is satisfied when the learner says so,
after the tutor has put the verifier's result and its reading of the
diff against the rubric on the table; the tutor's view, including what
it did not see, is written to evidence and never blocks the close;
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
                  the background already covers → open it → hand off to
/rolling:lesson → the walkthrough: the author's account of the lesson, read in the code with the learner,
                  questions answered, paced by what they already know → then, always, the offer of an
                  exercise, which they take or decline (a lesson marked exercise: none has none)
                → taken: hand off to
/rolling:task   → build a task from the map and history, fitting what the walkthrough turned up →
                  throwaway branch, starting state committed → prove it both ways → hand back to
/rolling:lesson → present it, mode first
    write:  the learner works, in their own editor; the tutor explains, points, asks; never writes
            inside the task's scope; runs the repo's checks when asked
    direct: the learner directs a coding agent in a second session; hooks log it; the tutor starts the
            watch and speaks only on an event worth a word, as an offer, in its own window
                → declined: the lesson ends at the walkthrough, and /rolling:done records it
/rolling:cancel → at any point: the exercise's branch is kept with whatever is on it, the lesson closes
                  unmarked, and next may offer it again
/rolling:done   → run the verifier (deterministic tier: the repo's own commands), before the tutor speaks
                → capture what changed: the working tree against the task's base commit, nothing committed
                → the held test, if any: applied, run, reverted, now that the diff is captured; its result
                  joins the verifier's
                → write:  the tutor reads the diff against the rubric and the corpus pointers: what is good,
                          what is missing, what a maintainer here would say, with a line and a rule each
                → direct: the verifier's findings come off the learner's ledger first; then the session,
                          turn by turn, as what the tutor noticed and offers: where the direction was
                          actionable and scoped, where the agent drifted and whether they steered, whether
                          they asked for the checks, what they sent back, what they accepted that a
                          maintainer here would have bounced
                → done when the learner says so; the tutor's view to evidence either way, what it did not see
                  included, so a later route can come back to it
                → the learner's work is committed on the task branch, which is kept; the learner is returned;
                  offer the next
```

| Rule | Enforcement |
|---|---|
| Feedback is formative and in the loop | The `done` skill is a step in the same conversation. Its inline commands run the verifier and capture the diff before the model's turn begins, so the deterministic result is on the table before any opinion is. Those inline commands always exit zero and report in text: a non-zero exit aborts the skill, which is the opposite of what a failing verifier needs. They also run under the Bash tool's two-minute timeout, so a task's verifier is scoped to a workspace and a file, never a whole suite; a verifier that cannot fit runs as the skill's first action instead, still before any opinion. |
| Feedback is grounded | Every point of feedback carries a file, a line, a rule, and a provenance label (this repo's convention, or the language's norm). The skill has the tutor write the feedback to evidence in that shape; a script checks each cited path exists at the cited line and flags the ones that do not. Structure, not a second reader, is what stops hand-waving. |
| The human's ledger (`direct`) | Before the learner's direction or review is read, the verifier's findings are taken off the table: a type error, a lint failure, a failing test are the checks' job, and the only thing on the learner's ledger about them is whether they asked for the checks before saying done. What the tutor reads and says something about is what a person directing an agent is responsible for: placement, convention, scope, whether a test was written and tests the right thing, a design that will not age, and the steering that got there; said once, as a colleague would, with the learner closing the lesson as in a `write` one. The held test's own result is read the same way: a fail against a valid alternative is the test's shape, not the learner's fault, and is said so. The spike's first `direct` run graded the learner on things the tests catch; that was wrong and this is the correction. |
| A second opinion is available, never required | In the backlog since planning P2, open to debate (§ 10). An optional `second-opinion` subagent with fresh context and read-only tools, invoked by the learner when they want fresh eyes on a diff (or by the tutor when the two disagree). It advises; it does not satisfy or block anything. |
| The learner drives | The tutor answers what is asked, the approach and the reference included, and notes what it gave so `done` reads the change with that in mind; a rubric is read against the change and never turned into questions, and a lesson's `## Talk through` items are offered once and dropped; the learner closes a lesson, and the tutor's reservations go to evidence rather than holding it open. Prose in P1; P2's eval measures whether the tutor said what it saw and then deferred. The one hard line is the write guard, which defines the mode rather than polices the learner: a learner who wants the change written for them is asking for a `direct` lesson, and the tutor offers one. |
| Don't do the task for the learner (`write`) | A **PreToolUse** hook in the plugin's `hooks.json` denies Edit and Write inside the open task's `scope` while a `write` task is open and the session is the tutor's, except paths the task marks `scaffold`, where the tutor may leave `TODO(human)` markers the way the built-in Learning output style does. It lives in `hooks.json` and reads the open task, not in a skill's `hooks:` block: hooks a skill registers persist for the rest of the session, which is the wrong lifetime. The hook is the one rule that must hold even when the learner asks nicely. |
| The coding session is a real session (`direct`) | The learner's coding agent is an ordinary Claude Code session in the same repo, not a subagent of the tutor and not primed by it. The plugin's hooks apply to every session where the plugin is enabled, so every hook handler begins by reading the open task, if any, and this session's id. The tutor's session id is the `tutor-session` field of the open task, written from `${CLAUDE_SESSION_ID}` by every learner-side skill each time one runs, so whichever session last ran a skill is the tutor and a restarted tutor reclaims the role. While a `direct` task is open, a session that is not the tutor's is logged, one file per session id under `sessions/`, and denied any read or write of the learner's state directory; the tutor's session is neither logged nor guarded. Nothing is injected into any session at start. Whatever the learner sets for their tutor session (an output style, say) can still reach the coding session through the directory's shared settings; the plugin has no launcher to pin it, so that is a named exposure (§ 8) checked by an eval, not a solved problem. |
| The tutor watches, sparingly (`direct`) | The lesson skill starts a Monitor that follows the `sessions/` directory, filtered to prompts, replies, and file edits, for the life of the tutor's session; a new tutor session on an open `direct` task reads the logs so far and starts it again. Replies arrive once per turn, from the Stop hook's last message. The tutor speaks only on an event worth a word: the agent editing outside the task's scope and the learner not noticing, a result accepted without the repo's checks, the same ask rephrased a third time. One or two lines, as an offer, in its own window, written to evidence as its own intervention. Otherwise an empty turn. Triggers it cannot observe from the log are not triggers. Where Monitor is unavailable (Bedrock, Vertex, Foundry, or non-essential traffic disabled) the tutor says up front that it is not watching and reads the logs at `/done`. |
| No fourth wall | The checks a learner runs during a lesson are the same tools a developer here uses in the normal course of work: the map's declared commands, given verbatim. The tutor names the lesson's mode up front and never cites a script, a task file, or a profile file; those are its own. Nothing the tutor puts in the repo shows up in the repo's own checks, which the storage layout now guarantees rather than a gitignore. |
| Every task on a throwaway branch | `begin-task` cuts the branch from the fix's parent, carries the map across as it is now (the fix may predate it), commits the starting state, and records in the task both `base` (that commit) and `return-to` as a symbolic ref with its resolved sha. `end-task` refuses, with a message, unless HEAD is still the task branch; otherwise it commits what the learner left, keeps the branch, and returns to the ref if it still resolves, else to the sha with a note. The tutor does no free-form git while a task is open; the reference is applied and undone by `verify --on-reference`, as a patch, in a `finally`. |
| Verifiers are structured, never shell | A task's verifier names declared commands and the test files the tutor holds; `verify` runs those and only those. Arguments are words, never shell: anything with a metacharacter is rejected. The held test is applied, run, and reverted by `verify` itself, after the diff has been captured, so it never appears in the learner's diff or lingers in the tree; a learner's own test at the same path is set aside for the run and restored. Operations are the author's shell, code-reviewed in the repo. |
| Destructive operations prompt, in every permission mode | The author marks an operation destructive in the map, once. Two layers make it prompt. First, `permissions.ask` rules, which the docs guarantee no mode auto-approves: an author inside the project has `rolling-author` write them into the `.claude/settings.json` they already commit, and a map plugin's install notes ask the learner to add them, because a plugin cannot ship permission rules of its own. Second, the plugin's **PreToolUse** hook returns `ask` for any command matching the map's list; on its own that survives auto mode's classifier but in `dontAsk` mode becomes a denial, which fails safe. The tutor's own confirmation in conversation sits on top. Nothing here depends on a grant a skill declares. |
| Never orchestrates the environment | The tutor never brings services up, installs toolchains, or fixes the environment; a failing command is reported with the local-dev-setup lesson offered. Whether the *learner* starts services in a setup lesson is the author's call, per environment, said in the map: a bare-metal team's map has `pnpm docker:up` as a step, a contained one has the services as a precondition. |
| Tasks are solvable | The both-ways check applies the reference and the held test on the starting branch, runs the verifier, restores the committed starting state, applies the held test alone, and runs it again; a task whose held test does not fail on the starting state or pass on the reference is discarded and the failure logged for the author. |
| The tutor points the way, and only the way | The `next` skill serves lessons inside the learner's destination and detours off them; it never serves a region the learner did not choose, and never edits the destination. It justifies each choice against the profile in one line written to evidence. A route that reads as a fixed order across learners with the same destination and different backgrounds is a failing eval. |
| Any editor | The learner's edits in their own editor are the normal case, not an exception. The tutor reads the working copy directly with Read and Grep, so a file saved in Vim is as visible as one Claude wrote. At `done`, the change is the working tree against the task's base commit, taken by script; nothing has to be committed or staged. The write-mode hook governs only what Claude writes; what the learner writes is theirs. |
| Detours are bounded | A detour is a walkthrough written for this learner, and a detour off a detour is the deepest: `next` says so and the pen refuses a third level; at the cap, the tutor suggests a teammate rather than another detour. |
| Profile survives | In the plugin's data directory, keyed by repo, per user, never in the tree (§ 3). Skills load it themselves through their inline commands; no hook injects it, since a hook cannot know at session start whether a session will be the tutor's. One hazard, named: the data directory is deleted when the plugin is uninstalled from its last scope, profile and evidence with it, so `rolling` gets an `export` that writes the learner's state somewhere they choose, and `/rolling:start` says so once. |

Two notes on permissions, since Claude Code's default mode moved to
`auto` while this was being written. Nothing in the table depends on the
mode: the rules that must hold are held by hooks, which apply in every
mode, or by scripts the skills run. And skills declare narrow grants or
none, never a wildcard over a package manager or git: narrow grants
still apply in auto mode and matter to the manual-mode users
(enterprise and API-key sessions default there, and an organisation can
force it), while a broad one is either dropped by auto mode or, in
manual mode, a pre-approval of whatever the wildcard covers.

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
  Plugin eval is generally available now; a small script around
  `claude -p --bare` covers any case it cannot express.

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

**Targets, from P1 on.** Three, each for a different reason, none of
them a codebase to learn from scratch. **Rallly**, public, as a map
plugin: the demo, and the external-author path, since it is not ours to
commit to. **The maintainer's own codebase at work**, private, with
`.rolling/` committed in its own tree: the internal-author path and the
actual corporate case, with nothing about it ever appearing in this
repository. **Homie**, the maintainer's own Go CLI, public: the
toolchain check, because the plugin's scripts have only ever seen pnpm
and a compose stack, and generalising from one ecosystem produces the
wrong interface; a single binary with `go test` and no services is as
different an environment as we have to hand. Homie's map is committed
in Homie's own tree from the first day (decided 2026-09-21, § 10): the
maintainer owns the project, and an author inside a project commits
the map. The handoff most open source maps would go through, an
outsider's plugin adopted by the project, needs only the resolver's
precedence in 1.0: the in-repo map wins when both are present, so
adopting is copying the directory in. The `adopt` step that does the
copy and stamps where it came from waits for 2.0 and a project that
wants it (2026-09-21, § 10). Same stack
twice over (Rallly and the work codebase are both Next.js, Prisma, pnpm)
diversifies nothing the plugin touches, which is why the third is Go. A second unfamiliar Node app (Papermark
was the candidate) would test only whether `rolling-author:init` can
draft a map for a repo the author does not know, which is P3's question.

**Two releases.** 1.0 is `write` mode end to end: the learner loop,
distribution, enforcement and evals, the author's plugin, and a
release a colleague can be onboarded with (P1 to P4). 2.0 adds
`direct` mode and its upper rungs (P5 and P6). `direct` is where the
project is aimed and was planned second in P1; it moved to 2.0 on
2026-09-22 (§ 10) because every part of it is additive to the `write`
loop, it is the most uncertain part of the plan, and the author's
plugin is the risk most likely to kill the project and should come
first. Its plan is written and its mechanisms are confirmed, so 2.0
starts from known ground.

**P1 — The learner loop as a plugin.** Two checkpoints, each usable on
its own.

*P1a, `write` mode, in-repo map. Done* (2026-09-15 to 09-19, then
extended by the first fresh learner's runs to 09-22; PRs #3 to #19;
the record and the retrospective are in
[`docs/plans/p1a-write-mode.md`](plans/p1a-write-mode.md)). Marketplace +
`rolling` skeleton;
`start`, `next`, `lesson`, `done`; the storage layout of § 3 and § 4
(state out of the tree); `begin-task`, `end-task`, `verify` with the
held test, `diff`, and `export` in `bin/`; the profile validator; the
write-mode scope guard in `hooks.json`, with the `tutor-session` stamp
it reads (trivial while the tutor's is the only session, real in P5);
`docs/map.md` and `docs/profile.md` as the specs. The Rallly map,
hand-written into a local clone's `.rolling/` and never pushed, grows to
8–10 lessons with rubrics, regions, depths, modes, and tests marked held
or shown. The old repo's `CLAUDE.md`, workflow skills, and ADR
discipline come across, since this is the first real branch. *Exit:*
three `write` lessons end to end across three sessions on Rallly with
the profile reflecting it; three seeded profiles (one region deep, a
different region deep, every region at working depth) get three
different routes, and two seeded backgrounds with the *same* destination
still diverge; nothing the tutor writes is in the tree.

*P1b, distribution. Done* (2026-09-22 to 09-24; PRs #22 to #36; the
record and the retrospective are in
[`docs/plans/p1b-distribution.md`](plans/p1b-distribution.md)). Opened
with the map and the skills after the
first fresh learner's four lessons: the setup lesson confirming the
environment's state rather than quizzing about it and using the
verifier subset it names, `polls` getting an `orientation` lesson
since `polls: orientation` reaches nothing today, and
`billing-and-tiers` rewritten as a `write` lesson so the Billing
engineer course is not empty until 2.0. Then the map-plugin manifest
and registration hook, the resolver with its precedence and staleness
warning, the Rallly map repackaged as a map plugin, and the Homie map
committed in Homie's own tree. The work codebase's map is written in
its own tree, privately. `runner/` is retired: with the map a plugin,
Rolling Start is installed into a Rallly clone like anywhere else, and
how the maintainer runs Rallly's toolchain is outside this repository.
`adopt`, and `rolling-author` with it, wait: P3 for the plugin, 2.0
for the skill. *Exit:* `/plugin install rallly@rollingstart` in a
fresh Rallly clone serves a lesson; a `write` lesson runs on Homie
from the map in its tree under `go test`; a Rallly clone with the
plugin installed and the map committed in its tree is taught from the
tree.

**P2 — Helpful and honest, measured.** Reshaped while planning it
(2026-09-24, § 10); the plan is
[`docs/plans/p2-helpful-and-honest.md`](plans/p2-helpful-and-honest.md).
The first eval suite, weighted toward helpfulness: did the tutor answer
a direct question directly, adapt to the background, offer to skip what
the learner knows, offer a quiz without forcing one, close a lesson when
told, say what it saw in the change, and keep its plumbing to itself;
and toward honesty: did it cite code that is there, quote only output
it received (#30), and never wave a failing check through. The citation
check; detours with the depth cap; the ask-before-destructive hook (the
second layer of § 5's row, a hook on Bash that asks for a command
carrying the head of a destructive map operation, in every session and
mode); closing a lesson returning the learner to their branch in the
same step (#29); and proofs that fail for the right reason (#14, #31,
#32, #33). `escalate` and `second-opinion` wait in the backlog, and
`ask` is dropped. *Exit:* evals pass on two model versions; a seeded
*gap in the learner's background* (a seeded profile, not a planted
mistake) earns a correctly named detour grounded in Rallly's own code.

**P3 — The author's plugin.** `rolling-author`: `init` drafts the map
from a bare repo (regions from the module structure and history,
candidate lessons at each depth, corpus pointers, operations from the
package scripts and CONTRIBUTING, the environment's shape); `mine` turns
bugfix commits and merged PRs into task candidates and grows the list of
agent mistakes from the repo's own review history; `verify` proves
tasks; `proposals` reviews detours that several learners needed;
`init` also writes the `permissions.ask` rules for the map's
destructive operations into the project's settings. *Exit:* an author
gets from clone to a reviewable draft map in an afternoon, and edits
rather than writes.

**P4 — Release 1.0.** A colleague onboarding onto something real, the
authoring guide covering both places a map can come from, managed-settings install
notes, and the question of whether the Rallly example ships a
`.devcontainer/` so anyone can run it contained the standard way. The
three targets above have been in use since P1, in `write` mode; whether this repository
should be an instance of itself is a question for when it has something
to teach. *Exit:* a colleague who has never seen the target completes a
real task in it.

**P5 — `direct` mode (2.0).** The plan is
[`docs/plans/p5-direct-mode.md`](plans/p5-direct-mode.md), written
2026-09-22 with its three mechanisms confirmed (a plugin's hooks fire in
a session that invokes none of its skills, a skill can arm a Monitor,
a PreToolUse `ask` is honoured). The session-identity contract
(`tutor-session`, claimed only by the skills the learner types, since
`lesson` and `task` are model-invocable and a coding session could
invoke either); the session-log and state-guard hook handlers; the
watch; `direct` tasks built as situations; the human's-ledger `done`,
in the register the learner drives. *Exit:* one `direct` lesson end to
end on Rallly, walkthrough and offer included, the tutor restarted
mid-lesson and reclaiming the role; nothing the tutor holds is readable
from the coding session; an eval that sets an odd output style in the
directory and checks what the coding session does with it.

**P6 — The upper rungs of `direct` (2.0).** Architecture (the learner is asked
what should change about how a region is built, and the tutor compares
it with the author's corpus pointers and the repo's own history) and
review of real history (the learner reviews a merged PR and the tutor
compares that review with what actually shipped and what the
maintainers said). Steering is no longer a rung here; the spike made it
the baseline of every `direct` lesson. *Exit:* a `direct` lesson on
Rallly at each rung that a strong engineer finds fair.

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
- **The tutor is too kind, or too strict.** Two ways to fail the
  same rule. Too kind: with no examiner, "looks great, moving on" is
  the model's default and the learner's wish, and a gap goes unsaid.
  Too strict: the model's other default is the classroom, and the
  first fresh learner's second lesson found the tutor withholding an
  answer to make them work for it and holding the lesson open on
  rubric questions nobody had asked. The rule is the same for both:
  the tutor says what it sees, located, honestly, once, and then the
  learner decides. The mitigations are structural (verifier first,
  citations required, the author's rubric on screen, the human's
  ledger, the learner's word closing the lesson) and measured by two
  evals: one seeds a diff missing something the rubric names and
  checks the tutor said so; the other has the learner say "I'm done"
  over the tutor's reservation and checks the lesson closed with the
  reservation in evidence. If the first cannot be held,
  `second-opinion` becomes a default step rather than an option, and
  that is the point at which to revisit, not before.
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
- **The tutor's session stamp is script-written, not script-proof.**
  The write guard keys on the `tutor-session` line of the open task,
  which `rolling-claim-session` writes from its command line and the
  pen rewrites from the recorded value; a model that typed another id
  into that command, or rewrote the file through a shell, would turn
  the guard off for its own session. No script-side check is
  hook-grade while Bash is unrestricted (every file it could compare
  against is one a shell can rewrite, and the only unforgeable value,
  the hook payload's `session_id`, has nowhere safe to live). Prose in
  P1a; P2's eval measures whether it holds, and decides with the scope
  rule whether a Bash rule on the data directory is worth its false
  positives.
- **Inline command limits.** Skill inline commands abort the skill on a
  non-zero exit and run under the Bash tool's two-minute timeout. Every
  script the skills run inline exits zero and reports in words, and
  verifiers are scoped to a workspace and a file rather than a whole
  suite; one that cannot fit runs as the skill's first action instead.
  The spike did not measure the timeout; P1's evals do.
- **Monitor is not everywhere.** The docs list it as unavailable on
  Bedrock, Vertex, and Foundry, and disabled when non-essential traffic
  is off, which describes a good share of the corporate targets. Where
  it is missing the tutor says so and `direct` mode degrades to reading
  the session logs at `/done`, which is the spike's original shape and
  still works.
- **Uninstall deletes the profile.** The plugin's data directory goes
  with the plugin when it is removed from its last scope. `export`
  exists for this, and `start` mentions it once; a learner who ignores
  both loses their evidence, not their code.
- **Script dependencies.** The toolkit assumes Python 3.9 and git and
  nothing else (decided 2026-09-15, § 10): Python 3 comes with a Mac's
  command line tools and every desktop Linux, and the native Claude
  Code installer no longer brings Node, so Node is not a runtime a
  learner can be assumed to have.

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
- **Map in the target repo** (draft 1; revised below).
- **Two plugins.** `rolling` for learners, `rolling-author` for authors,
  one marketplace repo, shared scripts in `rolling`'s `bin/`.
- **Names.** Repo and domain `rollingstart`; plugin and map directory
  `rolling`; roles are Author, Tutor, Learner in every document.

**By the spike** (2026-09-11 to 09-13; each with its moment in
`spike/NOTES.md`, except where dated otherwise):

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
- **A throwaway branch per task**, cut from the fix's parent, so
  nothing about the answer is in the diff or the branch's history.
- **The fix's test is held back** (2026-09-14, on the maintainer's
  point that nobody is handed a failing test with an issue). The
  learner writes their own; the original's test is the tutor's hidden
  acceptance check at `/done`, read as a signal, since a valid
  alternative can fail a test shaped to the original fix. An author may
  mark a lesson's test shown for early mechanics lessons.
- **No fourth wall.** The learner's checks are the repo's own commands;
  the tutor names the mode up front and never cites its scripts or
  files.
- **The environment's shape is the author's to describe.** The tutor
  never orchestrates it; whether the learner starts services in the
  setup lesson depends on the environment, and the map says which.
- **Learner state out of the tree.** In the plugin's data directory,
  keyed by repo, so nothing in the repo points at the reference and a
  hook denies the path, the repo's tooling never sees the tutor's
  files, and nothing has to be excluded from anything.
- **The tutor watches live.** Longer lessons need coaching before they
  are over; a Monitor on the session logs gives the tutor each prompt,
  reply, and edit as it happens, and a short list of triggers says when
  to speak.

**While reviewing draft 2** (2026-09-14):

- **The map lives with its author, and can move.** In the target repo
  at `.rolling/` when the author is inside the project; as a map plugin
  when the author is outside it or the project would rather not carry
  it; and adoptable from the second home into the first once it earns
  it, with the in-repo map winning whenever both exist. Same format, one
  resolver, both in the first release, replacing draft 1's "in the repo,
  plugin later": the spike spent real effort pretending Rallly carried a
  map it does not, and the distinction was never corporate versus open
  source.
- **Destructive operations prompt through `ask` rules first**, the
  hook second, because the docs attach the no-mode-auto-approves
  guarantee to the rule and not to a hook's decision.
- **Three targets from P1**: Rallly public as a map plugin, the work
  codebase private in its own tree, Homie public as a map plugin to be
  adopted.

**While building P1a** (2026-09-15):

- **The toolkit is Python 3.9, standard library only.** The first
  version was bash, chosen on a misreading of "assume nothing beyond
  git and a POSIX userland" as a rule about the scripts' language
  rather than the tools they call; six review rounds on it were mostly
  paying for bash. Node was the obvious second choice and wrong for
  the audience: the native Claude Code installer bundles its own
  runtime, so a learner on a repository that does not need Node may not
  have it. Python 3 is on every Mac that has git and on every desktop
  Linux; 3.9 is the floor a Mac's tools ship. Rewritten from the
  contract, not translated, with the same scenarios as tests.


**During P1a's exit run** (2026-09-19):

- **A task is provable only with an expected failure.** `rolling-verify
  --on-base` reports a proof gap for a task with no
  `expect-fail-on-base` line, since checks that pass before the work is
  done prove nothing (PR #13). So an environment lesson in an
  environment that is already set up has nothing to prove on its own;
  the tutor builds a smoke test along a small seam beside the setup
  steps, which is what it did unprompted in the exit run, and the
  Rallly map's setup lesson now says so.
- **The route follows the background, not the course's order.** Two
  seeded learners with the same destination and opposite backgrounds
  got the same first lesson because the tutor read the course's listing
  order as a sequence. The `next` skill now prefers, among reachable
  lessons, the one whose `assumes` the background lacks, and a map's
  course text says when its lessons are independent. A route that
  reads as a fixed order across backgrounds is the bug `CLAUDE.md`
  names.

**During the first fresh learner's run** (2026-09-21, the hotfix
before the next checkpoint; the run is written up in its PR):

- **The toolkit's git runs none of the repository's hooks and signs
  nothing.** The starting state and the learner's checkpoint are
  bookkeeping on a throwaway branch, not changes up for review; a hook
  that fails after a switch or wants a key would strand the learner
  half-way, and `--no-verify` alone leaves three hooks live. The
  starting state is committed as Rolling Start; the checkpoint under
  the learner's identity, or the toolkit's with a note when git has
  none for them, which a fresh container has not.
- **A begin that fails part-way is undone, and a task never begins
  from another task's branch.** The container had no git identity, the
  starting-state commit failed after the branch was cut and the map
  staged, and the tutor "tidied" the map out of the tree and began
  again from the half-made branch. Now every git write in a begin is
  under an undo that reports where the repository actually is, and
  `begin-task` refuses on a `rolling/<lesson>-<stamp>` branch.
- **The lesson's page comes before the skill's build order, and a
  brief names nothing the tutor holds.** The setup lesson says its
  task is the environment with a smoke test; the tutor hunted a
  reverted fix instead, told the learner a held test "already exists"
  at its path, named the reference's library, and ran the lesson's own
  setup operation for them.
- **The runner pre-approves the toolkit's commands for every turn.** A
  skill's grants hold only for the turn it ran in, so once `next`
  needed a reply, auto mode's classifier denied the granted command.
  The rules are the skills' own, in the container's user settings; an
  author inside a project would commit the same (P1b).

**After the first fresh learner's second lesson** (2026-09-21):

- **The lesson before the exercise, and the exercise on offer.** Every
  task had opened as a challenge: `next` built and proved a task, and
  the learner's first contact with a lesson was its homework, though
  the author had written the lecture into the lesson body and the
  tutor read it only as raw material for a brief. Now `next` chooses
  and opens the lesson and hands off; `lesson` gives the walkthrough
  (the body, read in the code, paced by the profile, questions
  answered) and always offers the exercise once, as a colleague would;
  the learner takes it, and a new `task` skill builds and proves it
  then, knowing what the walkthrough turned up, or declines, and
  `done` records a lesson closed at the walkthrough. Not a third
  lesson mode: mode says what shape the exercise takes, and a lecture
  is what comes before it in every lesson; an author whose lesson has
  nothing worth exercising marks it `exercise: none`. The saving in
  the tutor's time is real only when the offer is declined (the proof
  and, for a seam task, the tutor's own test and solution never
  happen); otherwise the work moves later, and the gain is that the
  walkthrough starts within seconds and the task fits what the
  learner said. `task` joins `lesson` as a skill the model may invoke,
  since the yes comes in conversation; it builds nothing unless a
  lesson is open.

**Reordering the releases** (2026-09-22):

- **`direct` mode moves to 2.0.** 1.0 is `write` mode through
  distribution, enforcement, the author's plugin, and a release; `direct`
  and its upper rungs follow as P5 and P6. Everything the first week
  built is mode-agnostic and `direct` is additive to it (a second
  session, three hooks, the watch, a second `done`), so nothing on the
  `write` track waits on it; it was the most uncertain part of the plan,
  the part most likely to iterate; and the author's plugin, named in
  § 8 as the risk most likely to kill the project, comes sooner this
  way. The ask-before-destructive hook, planned with `direct`, is not
  specific to it and moves to P2. The `direct` plan is kept, retitled
  P5, with its three mechanisms confirmed on the day of the decision.
  The Rallly map's `direct` lessons stay as written and are skipped
  until 2.0, except `billing-and-tiers`, which P1b rewrites as `write`
  so the Billing engineer course serves something in 1.0. `direct`
  remains where the project is aimed; only the order changed.

**Before the direct-mode plan** (2026-09-22):

- **`ask` may not be needed.** It was "grounded Q&A that never solves
  the open task", which is the posture the learner-drives change
  removed; `lesson` now answers what is asked, the reference included.
  P2 decides whether anything is left for a separate skill (questions
  outside any lesson, perhaps) or whether the entry goes.
- **The install story carries the toolkit's allow rules.** § 3 now says
  the author's committed settings pre-approve the `rolling-*` commands
  and the two hand-off skills, as the runner does in its home volume,
  since a skill's grants expire with its turn and auto mode denies.

**During the first fresh learner's second lesson** (2026-09-21):

- **The learner drives.** The tutor refused a direct question ("what's
  a good generic solution then?") to make the learner work for it,
  set them a larger exercise they had not asked for, and at `done`
  held the lesson open on three rubric items they had not asked about,
  one unrelated to the change. That is a classroom, and the product is
  a README with a coach in it for professionals at work. Now: the
  tutor answers what is asked, the reference included, and notes what
  it gave; a rubric is what a maintainer looks for in the change,
  written about the change and never about the learner, and a lesson's
  `## Talk through` items are offered once; the learner closes a
  lesson, and the tutor's view goes to evidence, reservations
  included, so a later route can come back to a gap. The satisfaction
  rule in § 1, § 4, and § 5 and the "too kind" risk in § 8 are
  rewritten. Considered and not built: an author-level `posture:` on
  the map that would make the strict shape available to a classroom.
  Every target is a workplace, and the strict shape changes the
  satisfaction rule, the rubric, and the evidence at once; if a
  classroom ever asks, a map field is where it goes.

**Planning P1b** (2026-09-21):

- **Homie's map is in Homie's tree from day one.** The plan had Homie
  start as a map plugin here and be adopted later, to play out the
  open source lifecycle; but the maintainer owns Homie, and an author
  inside a project commits the map, so the plugin stage was ceremony.
  Homie is the internal-author route in public; the work codebase is
  the same route in private.
- **`adopt` waits for 2.0, and `rolling-author` for P3.** Adoption in
  1.0 is copying a plugin's map into `.rolling/`, because the tree
  wins; a skill that does the copy, stamps where the map came from,
  and notices when the plugin is newer than the stamp is machinery for
  a lifecycle nobody has started, and P1b is simpler without it. The
  design keeps the skill (§ 2, § 3); it is built if a project asks.
  With it out, the author's plugin has no reason to exist before
  `init`, so it first appears in P3.
- **`runner/` is retired.** It existed because the maintainer kept
  Node off the host, which meant orchestrating Rallly's toolchain and
  services around the plugin from inside this repository. Once the map
  is a plugin, installing Rolling Start into a Rallly clone is `plugin
  install` like anywhere, and how the maintainer runs Rallly
  (contained, or on the host after all) is as external to this
  repository as the environment is to the tutor. No map, Homie's
  included, assumes any orchestration; what a lesson expects to find
  running is the map's to say. The runner's leftover duties go where
  they belong: a git identity and the toolkit's allow rules are the
  learner's environment, said in the map plugin's install notes; a
  task's proof is `rolling-verify` by hand until P3's `verify`.

**While building P1b** (2026-09-23):

- **A map plugin declares the release it was checked against, not a
  sha, and its version is that release by convention.** The first
  draft of the format pinned a plugin map to a commit. A target
  repository moves faster than a map an outsider writes for it, so the
  map is always behind HEAD, and "check out this old sha" is an awkward
  thing to tell a learner while "validated against version 4.15.2" is
  not. The declaration is `ref`, any git ref, a tag nearly always; the
  resolver resolves it and warns only when the checkout lacks it or is
  behind it, and HEAD past the release, the common case, says nothing.
  The plugin's own version is the target's release (`rallly` 4.15.2 for
  Rallly 4.15.2), with the patch bumped for a map change between
  releases; not enforced, but what a reader assumes a map's version
  means, so the examples keep it. The Rallly map was revalidated at
  `v4.15.2`, the latest release, to declare one, and the reference
  checkout's pin moved with it.

- **The toolkit allows its own commands through a hook, not through
  settings** (2026-09-23). The allow rules a learner pasted into user
  settings were the roughest edge of the install, and the maintainer
  hit it first when walking the Rallly path as a user. A plugin cannot
  ship permission rules, but its hooks run in every mode and an `allow`
  skips the prompt for that one call, the mechanism the write guard
  already uses for `deny`. `rolling-allow` allows one plain invocation
  of a toolkit executable (word arguments, the pen's quoted heredoc, a
  trailing `2>&1`, nothing chained or redirected) and the two hand-off
  skills, and is silent about everything else, so a map's command and
  a destructive operation ask as before. Considered and not built: a
  `rolling-setup` script that edits `~/.claude/settings.json`, which is
  what permission systems exist to stop, and still a step to know
  about. The install is the two `/plugin` lines and a restart, on
  either route.

**Closing P1b** (2026-09-24):

- **The in-tree install is trusting the folder, then `/clear`**
  (probed 2026-09-23). A project's `.claude/settings.json` naming the
  marketplace and enabling `rolling` installs both silently when a
  learner trusts the folder: no offer, no `/plugin` line. The plugin
  arrives after that first session has started, so its hooks have not
  run and `/rolling:start` asks for a `/clear` first. A folder trusted
  before the settings existed gets nothing, and needs the two
  `/plugin` lines; a project's onboarding notes should say both.
- **A map in the tree may carry the scripts its operations run**
  (2026-09-23). An operation runs on the task's starting state, which
  is often older than any script the project would add for it, so a
  script kept elsewhere in the repository is absent there. The toolkit
  carries `.rolling/` onto every task branch, so a script in it exists
  on every starting state. A map plugin's directory is not in the
  learner's tree, so a plugin map cannot do this; `docs/map.md` says
  both. The work codebase's map carries two: a reset of the test
  databases, and a reinstall that clears the links a package manager
  leaves behind across commits.
- **Every change to a plugin bumps its version, and CI enforces it**
  (2026-09-24). A plugin with a version is pinned to it, and `/plugin
  update` offers a new copy only when the version differs; `rolling`
  sat at 0.1.0 through 31 commits, so no installed learner had ever
  been offered an update, and nothing in the gate looked. Considered:
  dropping `rolling`'s version so it follows `main`, which is simpler
  but lets code change under a lesson in progress, which P1b decided
  against for maps. So `rolling` takes a minor bump per change until
  1.0, a map follows `docs/map.md`, the version lives in `plugin.json`
  and not in `marketplace.json`, and CI's `versions` job refuses a pull
  request that changes a plugin, outside its `tests/`, without a new
  version, or leaves a plugin with none (PR #35).

**Planning P2** (2026-09-24):

- **P2 is "helpful and honest, measured", not "enforced".** Most of
  what the entry listed made the tutor stricter, and P1 had already
  corrected a tutor that withheld an answer and held a lesson open on
  questions nobody asked (2026-09-21). The tutor is a helpful
  assistant to a professional, so a rule that must hold is framed by
  whom it protects: the learner's work (the destructive hook, closing a
  lesson returning them to their branch) or the learner's trust in what
  the tutor says it saw (citations, quoted output, proofs). The eval
  suite is weighted toward helpfulness, and an eval that would make the
  tutor withhold, quiz, or gate is suspect by construction. A quiz is
  offered where it would help and never forced: some learners want
  one and some do not, and the learner picks.
- **`ask` is dropped; `escalate` and `second-opinion` go to the
  backlog.** `lesson` answers what is asked, and outside a lesson the
  learner asks plain Claude Code in the same session. `escalate` is
  wanted and not urgent: until it lands the detour cap names a
  teammate in words. `second-opinion` is open to debate: § 8 makes it
  the fallback if the tutor proves too kind, and no eval has shown
  that yet.
- **The session stamp, the Bash-level scope rule, and the
  walkthrough's write window are measured, not guarded.** P1a and P5
  left each to P2's eval with a guard only if prose fails; P2 keeps
  that order, and a guard for one is a slice of its own if its case
  fails.
