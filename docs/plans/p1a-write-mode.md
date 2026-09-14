# P1a: `write` mode, in-repo map

> Expanded plan for the `P1a: write mode` checkpoint. The plan's entry
> is [`docs/plan.md`](../plan.md) § 7, P1a.
>
> This file is the drafting artifact. Its sub-scopes are copied
> verbatim into GitHub issues; its remaining content becomes the
> project board's README. After the checkpoint ships,
> `/milestone-endgame` appends a retrospective.

## Context

P0 (the spike, `spike/`, PR #1) proved the premise by hand: three
skills and eight scripts dropped into a Rallly clone's `.claude/`, a
five-lesson map in its `.rolling/`, and the maintainer as the learner.
`write` mode held on prose alone; `direct` mode was redesigned
mid-spike into the learner's own coding session. None of the spike's
code is the plugin: its scripts assumed the learner's state lived in
the tree, which the plan has since moved out (§ 3), and its skills
were installed by copying, which the plan replaces with a marketplace.

P1a delivers the learner loop as a real plugin, for `write` mode only,
against a map committed in the target repo. Concretely: a marketplace
at the repository root with one plugin in it, `rolling`; four skills
(`start`, `next`, `lesson`, `done`); a toolkit in `bin/` that every
skill calls by name and that keeps every learner file in the plugin's
data directory; the one hook that must hold in `write` mode, the scope
guard; the two format specs; and the Rallly map grown from five
lessons to eight or ten, with tests marked held or shown.

End state: a learner opens Claude Code in a Rallly clone that has the
map committed and the plugin enabled, runs `/rolling:start`, and is
taught three `write` lessons across three separate sessions, with the
profile carrying the thread and nothing of the tutor's in the tree.
Three seeded profiles get three different routes.

P1b (`direct` mode) and P1c (map plugins, the resolver, `adopt`)
follow. Nothing here assumes them, but the session-identity stamp
(`tutor-session`) that P1b needs is written now, while the tutor's is
the only session, so P1b adds handlers rather than reshaping the task
file.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Toolkit executables are prefixed `rolling-` | `rolling-verify`, `rolling-diff`, `rolling-begin-task`, … | `bin/` is on the Bash tool's PATH for the whole session, shared with the target repo's own tools. A bare `verify` or `diff` collides with something eventually; the prefix also makes `allowed-tools` grants readable (`Bash(rolling-show *)`). |
| The state directory is resolved one way, everywhere | `$ROLLING_DATA` if set, else `${CLAUDE_PLUGIN_DATA}`, then `/repos/<encoded toplevel>/` under it; encoding is the one Claude Code uses for its own project directories (every non-alphanumeric byte → `-`) | One resolver in one place, used by scripts, hooks, and tests alike. `ROLLING_DATA` exists so tests run in a temporary directory and never touch a real data directory. Whether `CLAUDE_PLUGIN_DATA` reaches a `bin/` script as an environment variable is a mechanism to confirm (below). |
| Nothing is excluded from the diff | `rolling-diff` shows the working tree against `base`, every path | The spike excluded `.rolling/` and `.claude/` because the profile and the scripts lived there. Now the tree holds only the author's map and the learner's work; a learner who edits a lesson file has made a change the tutor should see. |
| Diff first, then verify; the held test is applied inside verify | `done` runs `rolling-diff`, then `rolling-verify`; verify applies held tests, runs, reverts, restoring a learner file at the same path | The diff must not contain the held test and the tree must not keep it (§ 4). Doing the apply/revert inside one script, with a trap, is the only way to make "never lingers" a property rather than a hope. |
| The skill writes `task.md`; scripts print what it needs and a validator checks the result | `rolling-begin-task` prints `branch:`, `base:`, `return-to:`, `held:` lines; the model writes the file in the documented shape; `rolling-check-task` rejects a malformed one before anything reads it | Mixed ownership of one file (script writes the top, model appends the rest) is how fields drift. One writer, one checker. `rolling-diff` and `rolling-verify` also fail safe on a bad file and say why. |
| `lesson` is the one skill the model may invoke | `disable-model-invocation: true` on `start`, `next`, `done`; not on `lesson` | `next` has to hand off to `lesson` (§ 5) and a skill reaches another only through the Skill tool. `lesson` only ever re-presents the open task, or says there is none, so an unprompted invocation is harmless; the other three do things. |
| The session stamp is written by a script, not by the model | Every learner-side skill runs `` !`rolling-claim-session ${CLAUDE_SESSION_ID}` `` inline | The stamp is what P1b's hooks use to tell the tutor from the coding session; a value the model might forget to copy is not a stamp. Inline substitution of the session id is documented; a script call is the deterministic way to persist it. |
| The spike's scripts are rewritten, not moved | `bin/` starts from the spike's contracts (§ Spike, `spike/README.md`) and the lessons in `spike/NOTES.md`, and reimplements them against the new layout | Every spike script hardcodes `.rolling/profile/`; the exclusions, the branch dance, and `show.sh`'s subcommands all follow from that. Porting line by line would carry the assumption along. |
| The Rallly map's source stays in this repository | `examples/rallly/.rolling/`, installed into the clone by the runner; the clone's copy is never pushed anywhere | The map has to live somewhere reviewable, and P1c repackages exactly this directory as the `rallly` map plugin. What "hand-written into a local clone's `.rolling/` and never pushed" (§ 7) rules out is a fork of Rallly carrying it, not a source here. |
| The tutor's Bash writes inside scope are not hook-denied in P1a | The guard covers Edit, Write, NotebookEdit, MultiEdit | A Bash rule that denies any command naming a scope path would also deny `pnpm --filter … test <that path>`, which the tutor is supposed to run. Prose covers the `sed -i` case for now; P2's eval measures whether it holds, and P2 decides whether a narrower Bash rule is worth its false positives. |
| CI arrives with the toolkit | `.github/workflows/ci.yml` lands in 1a.3 with the first scripts it can check | A gate with nothing to check is ceremony; a toolkit without one is how a red branch reaches `main`. |

## Mechanisms to confirm first

Each is confirmed in a scratch setup under the session's scratchpad
(a throwaway git repository, a throwaway plugin directory registered
as a local marketplace, a `claude` session started there), by the
sub-scope named, before that sub-scope builds on it. The result is
recorded here.

| Mechanism | Sub-scope | Result |
|---|---|---|
| `CLAUDE_PLUGIN_DATA` reaches a `bin/` script as an environment variable when the Bash tool runs it, and `${CLAUDE_PLUGIN_DATA}` is substituted in a skill's inline command and in a `hooks.json` command | 1a.3 | |
| A plugin's `bin/` is on the Bash tool's PATH in a session where the plugin is enabled through a local marketplace, and stays so across `/clear` | 1a.3 | |
| `${CLAUDE_SESSION_ID}` is substituted inside a skill's inline `` !`…` `` command, and the same session's PreToolUse hook receives the same id in `session_id` | 1a.4 | |
| A plugin's `hooks.json` PreToolUse handler fires in the tutor's session for Edit and Write, receives `tool_input.file_path`, and its `deny` is honoured in `auto` mode | 1a.4 | |
| The `Skill` tool can invoke a plugin skill that does not disable model invocation, from inside another skill's turn | 1a.5 | |
| `claude plugin validate` accepts the marketplace root and each plugin directory, and its exit status is usable as a gate | 1a.3 | |
| Inline commands in one skill run in document order (so `rolling-diff` completes before `rolling-verify` starts) | 1a.5 | |

## Sub-scopes

### 1a.1 — The repository learns how work happens here [PENDING]

**Goal.** Carry the old repository's process (`CLAUDE.md`,
`REVIEW.md`, `docs/workflow.md`, the ADR discipline, the four workflow
skills) across, rewritten for a plugin repository, and slice P1a into
the sub-scopes on this page.

**Branch.** `p1a.1/process`

**Depends on.** Nothing.

**Acceptance criteria.**

- `CLAUDE.md` states the rules an agent must follow here, with the
  plan's architectural seams (§ 5) as rules and the working agreements
  the maintainer has enforced since P0 written down; nothing Go-shaped
  survives.
- `REVIEW.md` names the seams a reviewer blocks on, and the shell and
  hook specifics that replace the old Go section.
- `docs/workflow.md` describes the cycle with checkpoints (P1a, P1b,
  …) as GitHub milestones, the gate (`shellcheck`, the test runner,
  `claude plugin validate`), and merge-commits-only.
- `docs/decisions/` holds the README and the template; `docs/plans/`
  holds the template and this plan.
- The four skills under `.claude/skills/` refer to `kurowski`, the
  plan, and checkpoints; `create-issues.sh` resolves `P1a: …`
  milestones and `### 1a.N —` headings.
- This plan exists with every sub-scope below carrying a goal, a
  branch, dependencies, acceptance criteria, and a verification list.

**Verification.**

- [ ] `bash -n` on `create-issues.sh`; `shellcheck` once it is
      installed on the host
- [ ] Every path `CLAUDE.md` § Key locations names either exists or is
      marked with the sub-scope that creates it
- [ ] The maintainer has read `CLAUDE.md` and the plan and agreed the
      slicing

---

### 1a.2 — The formats: `docs/map.md` and `docs/profile.md` [PENDING]

**Goal.** Write the two specs the plugin reads and writes against,
from the plan's § 4 and the spike's drafts, before any script parses
either.

**Branch.** `p1a.2/specs`

**Depends on.** 1a.1.

**Acceptance criteria.**

- `docs/map.md` specifies `.rolling/map.md` (frontmatter: `name`,
  default `mode`, `commands`, `operations`, `destructive`; body:
  regions, one or more suggested courses, corpus, mistakes agents make
  here, the environment's shape) and `.rolling/lessons/<slug>.md`
  (frontmatter: `title`, `region`, `depth`, `mode`, `requires`,
  `assumes`, `test: held | shown`; body ending in `## Rubric`), with
  the slug and link rules carried from the old skills spec (lowercase
  kebab-case; `requires` entries are slugs; a flat directory), and the
  optional `tasks/<slug>.md` for pre-authored tasks. It says what the
  scripts parse (the frontmatter, flat, two-space indented) and what
  only the tutor reads (the body), and why the line is there.
- `docs/profile.md` specifies the learner's directory in the plugin's
  data directory: its location and encoding, `profile.md` (background,
  destination as `<region>: <depth>` lines, why, satisfied), `task.md`
  (`lesson`, `mode`, `branch`, `base`, `return-to` as ref and sha,
  `started`, `scope`, `scaffold`, `setup`, `verify`,
  `expect-fail-on-base`, `held`, `tutor-session`; then brief or
  situation, then source), `reference.md`, `held/`, `sessions/`,
  `tasks/`, `evidence/<lesson>.md`, `detours/`, `escalations/`, and
  the mutation rules of § 4 (who may write what, when a lesson is
  satisfied, what never satisfies anything).
- Both specs state the validator's checks (shape, not content) so
  `rolling-check-map`, `rolling-check-profile`, and
  `rolling-check-task` in 1a.3 implement a list rather than invent one.
- Both use `billing`, `scheduling`, `platform` as example regions and
  never name the maintainer's employer's codebase.

**Verification.**

- [ ] The spike's Rallly map and five lessons conform to
      `docs/map.md` after at most the `test:` field is added, or the
      spec says why they had to change
- [ ] Every field the spike's `task.md` shape carried is either in
      `docs/profile.md` or listed there as dropped, with a reason

---

### 1a.3 — The marketplace, the plugin skeleton, and the toolkit [PENDING]

**Goal.** The repository becomes a marketplace with one plugin,
`rolling`, whose `bin/` holds every script the skills and hooks will
call, each tested against a scratch repository, with CI running the
gate.

**Branch.** `p1a.3/toolkit`

**Depends on.** 1a.2.

**Acceptance criteria.**

- `.claude-plugin/marketplace.json` lists `rolling`;
  `plugins/rolling/.claude-plugin/plugin.json` names it, versions it,
  and declares no dependencies. `claude plugin validate` passes on
  both.
- One resolver for the learner's directory, per the key decision
  above, shared by every script and by the hook handler; the
  mechanism rows for `CLAUDE_PLUGIN_DATA` and `bin/` on PATH are
  confirmed and recorded before anything depends on them.
- `rolling-show <what>` prints one piece of context for a skill's
  inline command (`map`, `lessons`, `lesson-heads`, `profile`, `task`,
  `lesson-for-task`, `corpus`, `tree`, `state-dir`) and always exits 0,
  reporting absence in words.
- `rolling-claim-session <id>` records the id as `tutor-session` in
  the open task, or in the learner's directory when no task is open;
  always exits 0.
- `rolling-begin-task <lesson> --fix <sha> [--held <path>…] [--shown <path>…] | --here`
  cuts `rolling/<lesson>-<stamp>` from the fix's parent (or here),
  brings `--shown` paths forward and commits, copies `--held` paths
  from the fix into the learner's directory under `held/` and does
  not put them in the tree, refuses a dirty tree, a root commit, a
  merge commit, or a path the fix did not touch, and prints `branch:`,
  `base:`, `return-to:` (ref and sha), and `held:` lines. Exits
  non-zero on refusal (it is run as an action, not inline).
- `rolling-end-task` refuses unless HEAD is the task branch, commits
  whatever is uncommitted with the documented message, keeps the
  branch, and returns to the ref if it still resolves, else to the sha
  with a note.
- `rolling-diff` prints the working tree against `base`, untracked
  files included, nothing excluded, capped, always exit 0, and fails
  safe in words on a missing or malformed task.
- `rolling-verify` runs the task's `verify:` lines against the map's
  `commands:` with the spike's argument rules (words only; any
  metacharacter or glob rejected; `</dev/null`), then for each `held`
  path sets aside any learner file at that path, applies the held
  copy, runs the task's held-test command, reverts, restores the
  learner's file, under a trap so an interrupt restores too; prints
  one line per command and a `VERIFIER:` summary with the held
  results labelled as held; always exits 0.
- `rolling-check-map [dir]`, `rolling-check-profile`, and
  `rolling-check-task` implement exactly the checks the specs list and
  report every fault, one per line, with the file and field; exit
  non-zero on faults, since they are run as actions.
- `rolling-close-task` removes `task.md`, `reference.md`, and `held/`
  and nothing else.
- `rolling-export <dir>` copies the learner's directory for this
  repository to `<dir>`, refusing to overwrite, and prints what it
  wrote; because uninstalling the plugin deletes the data directory
  (§ 8).
- Every script is POSIX `sh`, `shellcheck` clean, assumes only `git`
  and a POSIX userland, and has a test under `plugins/rolling/tests/`
  that builds a scratch repository in a temporary directory with
  `ROLLING_DATA` pointed at another one; `tests/run.sh` runs them all
  and exits non-zero on any failure.
- `.github/workflows/ci.yml` runs `shellcheck`, `tests/run.sh`, and
  `claude plugin validate` on every PR and on `main`, each as its own
  step.

**Verification.**

- [ ] The gate is green locally and in CI
- [ ] A scratch repository run through begin-task → edit → diff →
      verify (with one held test) → end-task leaves the tree exactly
      as the learner left it, the held test in no diff and no commit,
      and the learner back on their branch
- [ ] The mechanism rows assigned to 1a.3 are filled in

---

### 1a.4 — The `write`-mode scope guard [PENDING]

**Goal.** The one rule that must hold when the learner asks nicely:
while a `write` task is open and this session is the tutor's, the
tutor cannot edit inside the task's scope, except scaffold paths.

**Branch.** `p1a.4/write-guard`

**Depends on.** 1a.3.

**Acceptance criteria.**

- `plugins/rolling/hooks/hooks.json` registers a PreToolUse handler
  for Edit, Write, MultiEdit, and NotebookEdit that runs a Node
  handler in `bin/` (no dependencies) and passes it the data directory.
- The handler reads the open task; if there is none, or its mode is
  not `write`, or the event's `session_id` differs from
  `tutor-session`, it exits 0 with no output. Otherwise it resolves
  the event's path against the project directory, matches it against
  the task's `scope:` lines (globs: `*`, `**`, `?`; a bare directory
  matches everything beneath it), exempts `scaffold:` paths, and
  denies with a reason that names the scope and says what the tutor
  may do instead (point, explain, scaffold with `TODO(human)`).
- The handler never blocks the session on its own failure: malformed
  input, an unreadable task file, or a missing data directory all
  exit 0 silently.
- The mechanism rows assigned to 1a.4 are confirmed and recorded
  before the handler is written against them.
- A test drives the handler with hand-built JSON events against a
  scratch data directory: in-scope denied, scaffold allowed, out of
  scope allowed, no task allowed, wrong session allowed, `direct` mode
  allowed, garbage input allowed.

**Verification.**

- [ ] In a scratch repository with a `write` task open, the tutor's
      session is denied an Edit inside scope in `auto` mode and told
      why, and allowed one outside it
- [ ] Gate green

---

### 1a.5 — The four skills [PENDING]

**Goal.** `start`, `next`, `lesson`, and `done` as `rolling`'s
skills, calling the toolkit by name, with the coaching rules the spike
settled and none of the spike's fourth-wall slips.

**Branch.** `p1a.5/skills`

**Depends on.** 1a.3, 1a.4.

**Acceptance criteria.**

- `/rolling:start`: the intake as the spike's `start` skill had it
  (the author's course laid out, the learner bends it, the destination
  written in the learner's words), writing `profile.md` to the
  learner's directory through the toolkit, never to the tree; for a
  returning learner, where they are and what comes next; says once
  that uninstalling the plugin deletes the profile and that
  `rolling-export` exists, in words a learner can act on without a
  script path being the instruction.
- `/rolling:next`: reads map and profile; chooses a reachable lesson
  inside the destination with the spike's rule (region listed, depth
  at or below, `requires` satisfied, background covering `assumes`
  speeds rather than skips); writes the one-line justification to
  evidence; builds the task (a reverted fix with its test held, or
  shown when the lesson says so; else an extension along a seam);
  runs `rolling-begin-task`; writes `task.md` and `reference.md`;
  proves the task both ways with `rolling-verify` and restores the
  committed starting state; refuses to serve an unproven task; then
  hands off to `lesson`.
- `/rolling:lesson`: presents the open task, mode first, brief, where
  to look, what done means, and the checks as the map's own commands
  verbatim; holds the `write` coaching rules (explain, point, ask;
  never write inside scope; observations to evidence); re-presents
  when invoked on an open task in a new session; says there is
  nothing open otherwise. The only skill without
  `disable-model-invocation: true`.
- `/rolling:done`: inline, in this order, `rolling-claim-session`,
  `rolling-diff`, `rolling-verify`, then the task, the lesson, and the
  corpus; the verifier speaks first; every point of feedback carries
  `path:line`, the rule, and its provenance; the held test's result is
  read as a signal, and a fail against a valid alternative is said to
  be that; satisfied when the tutor says so and the learner agrees,
  both positions recorded when they do not; appends evidence; on
  satisfied, appends to the profile, offers `rolling-end-task`, runs
  `rolling-close-task`, and offers `/rolling:next`.
- Every skill's `allowed-tools` grants exactly the `rolling-*`
  invocations and read tools it uses, and the map's commands are not
  pre-approved (the learner is asked, or the tutor's action prompts).
- No skill names a script, a task file, or a profile file in anything
  the learner is shown; the mode is named in the first line of every
  brief.
- The mechanism rows assigned to 1a.5 are confirmed and recorded.

**Verification.**

- [ ] `claude plugin validate plugins/rolling` green; gate green
- [ ] One `write` lesson end to end on the Rallly clone (with 1a.6's
      runner and 1a.7's map, or the spike's five lessons before 1a.7
      lands), transcript read for fourth-wall slips and for the tutor
      writing inside scope

---

### 1a.6 — Running it, contained [PENDING]

**Goal.** A runner that puts the plugin, the map, and a Rallly clone
together in the spike's container so a lesson can be run on this
machine without npm touching the host.

**Branch.** `p1a.6/runner`

**Depends on.** 1a.3 (the marketplace exists to register).

**Acceptance criteria.**

- `dev/contained/` (or the spike's `container/` moved and renamed;
  the implementer decides and the commit says why) builds the same
  image, brings up Rallly's compose stack, and starts a named
  toolchain container with the Rallly clone mounted at the workspace
  and this repository mounted read-only.
- On `up`, the runner registers this repository as a local
  marketplace in the container, installs `rolling` from it, and copies
  `examples/rallly/.rolling/` into the clone; on re-run it refreshes
  both. The learner's directory lands in the home volume with Claude
  Code's login, so it survives a rebuild.
- `tutor` opens Claude Code in the clone; `shell` opens a shell;
  `down` and `destroy` as the spike had them.
- `spike/README.md` gains one line pointing at the new runner and
  saying the spike's own is frozen.

**Verification.**

- [ ] From a fresh clone at the pin: `up`, `pnpm install` in `shell`,
      `tutor`, `/rolling:start` is offered and runs

---

### 1a.7 — The Rallly map at eight to ten lessons [PENDING]

**Goal.** The map grows from the spike's five lessons to the set a
first fortnight needs, every lesson with a rubric, a region, a depth,
a mode, and `test: held` or `shown`, every claim checked at the pin.

**Branch.** `p1a.7/rallly-map`

**Depends on.** 1a.2.

**Acceptance criteria.**

- `examples/rallly/.rolling/` conforms to `docs/map.md`
  (`rolling-check-map` green once 1a.3 lands; by hand before).
- The five spike lessons are revised: `test:` added; the setup lesson
  states the environment's shape as a description of this example's
  environment; nothing names a script.
- Three to five lessons added across the regions, chosen from the
  code at the pin, each with a source fix or seam the tutor can build
  a task from (a sha and the paths it touched, checked against
  `../rallly`). Candidates, to be confirmed at the pin before any is
  written: the tRPC procedure ladder and server-action clients
  (platform, working); email templates and their i18n (platform,
  working); feature flags and instance policy (platform, working);
  invites and participants (polls, working); the house-keeping cron
  (polls, deep); the Stripe webhook (billing, deep, `direct`, so it
  waits for P1b to be served but is written now).
- At least one early `write` lesson marks `test: shown`, so the
  Exercism shape is exercised.
- The map's suggested course covers the added lessons, and at least
  two courses exist (a generalist and a billing engineer) so intake
  has a fit to offer.
- Every path, line, sha, and PR number cited is checked against
  `../rallly` at `aab791da`, and the map says so.

**Verification.**

- [ ] `rolling-check-map examples/rallly/.rolling` green
- [ ] For each lesson with a source fix, `rolling-begin-task --fix`
      succeeds on the clone and `rolling-verify` fails on the starting
      state and passes with the reference applied

---

### 1a.8 — The exit run, and closure [PENDING]

**Goal.** Run the checkpoint's exit criterion honestly and close it
out.

**Branch.** `p1a.8/closure`

**Depends on.** 1a.5, 1a.6, 1a.7.

**Acceptance criteria.**

- Three `write` lessons end to end on the Rallly clone, each in its
  own session (`/clear` or a new terminal between), the profile
  carrying the thread; the transcripts read for the properties § 7
  names: did the tutor write inside scope, cite code, wave a failing
  verifier through, name a script.
- Three seeded profiles (one region deep; a different region deep;
  every region at working) each get a different first lesson from
  `/rolling:next`, and two seeded backgrounds with the same
  destination still diverge, recorded as profile → route.
- After all of it, `git status` in the clone shows only the learner's
  own work, and a search of the tree for the learner's directory
  contents finds nothing.
- The retrospective is written per `/milestone-endgame`; `CLAUDE.md`
  § Status and `docs/plan.md` § 7 are updated; the README stops saying
  nothing is built.

**Verification.**

- [ ] The exit criterion in `docs/plan.md` § 7 P1a holds, with the
      evidence in the retrospective
- [ ] Every mechanism row above is filled in

## Explicitly deferred

- **`direct` mode**, the session log, the state-directory guard, the
  ask-before-destructive hook, the watch: P1b. The `tutor-session`
  stamp is the only piece of it written here.
- **Map plugins, the resolver, `adopt`, the Homie map**: P1c. In P1a
  the map is found at `.rolling/` in the repo root and nowhere else.
- **`ask`, `escalate`, `second-opinion`, the citation check, detours
  with the depth cap, evals**: P2. The feedback shape is asked for by
  the skill in P1a and measured in P2.
- **`permissions.ask` rules for destructive operations**: written by
  `rolling-author:init` in P3. In P1a the map marks them, the skill
  asks in conversation, and the tutor's grants never cover them.
- **`docs/design.md` and the landscape survey**, carried from the old
  repository shortened (§ 9): after P1 has shipped something for them
  to describe. The README and the plan are the design until then.
- **The AGPL question** on a public Rallly map with reference
  solutions (§ 8): the references here are shas into Rallly's own
  history, not copies, and the map's source has been public since P0.
  Decide before P1c publishes it as a plugin.
- **A Bash-level scope guard** for the tutor: P2, if the eval shows
  prose does not hold.
- **The review bot workflow** (`review.yml`) from the old repository:
  needs an API key in the repository's secrets, which is the
  maintainer's to add; the local Opus review is the gate until then.

## Verification

- The plan's exit criterion for P1a: three `write` lessons end to end
  across three sessions on Rallly with the profile reflecting it;
  three seeded profiles get three different routes, and two seeded
  backgrounds with the same destination still diverge; nothing the
  tutor writes is in the tree.
- The gate is green on `main`.
- Every mechanism in the table above has a recorded result, and none
  of them is "no" without a plan change that says how.
- A reader of `CLAUDE.md`, `docs/map.md`, and `docs/profile.md` can
  write a map for a repository of their own without reading the
  skills.
