# P1a: `write` mode, in-repo map

> The plan's entry is [`docs/plan.md`](../plan.md) § 7, P1a. This
> file is the tracker for the checkpoint. Each PR flips its own
> sub-scope from `[PENDING]` to `[COMPLETE]`. When the whole checkpoint
> ends, a retrospective is appended.

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
| The process is a page, not a system | `docs/workflow.md`; the checkpoint plan is the tracker; issues are a backlog; decisions go to `docs/plan.md` § 10 | The predecessor's milestones, boards, sub-issues, ADRs, and workflow skills were built for a team on a large Go system. This is a few thousand lines of shell and Node and a body of prose whose test is a run. The first version of this branch carried the whole apparatus across; the second cut it, and the history shows both. |
| Toolkit executables are prefixed `rolling-` | `rolling-verify`, `rolling-diff`, `rolling-begin-task`, … | `bin/` is on the Bash tool's PATH for the whole session, shared with the target repo's own tools. A bare `verify` or `diff` collides with something eventually; the prefix also makes `allowed-tools` grants readable (`Bash(rolling-show *)`). |
| The state directory is resolved one way, everywhere | `$ROLLING_DATA` if set, else `${CLAUDE_PLUGIN_DATA}`, then `/repos/<encoded toplevel>/` under it; encoding is the one Claude Code uses for its own project directories (every non-alphanumeric byte → `-`) | One resolver in one place, used by scripts, hooks, and tests alike. `ROLLING_DATA` exists so tests run in a temporary directory and never touch a real data directory. Whether `CLAUDE_PLUGIN_DATA` reaches a `bin/` script as an environment variable is a mechanism to confirm (below). |
| Nothing is excluded from the diff | `rolling-diff` shows the working tree against `base`, every path | The spike excluded `.rolling/` and `.claude/` because the profile and the scripts lived there. Now the tree holds only the author's map and the learner's work; a learner who edits a lesson file has made a change the tutor should see. |
| Diff first, then verify; the held test is applied inside verify | `done` runs `rolling-diff`, then `rolling-verify`; verify applies held tests, runs, reverts, restoring a learner file at the same path | The diff must not contain the held test and the tree must not keep it (§ 4). Doing the apply/revert inside one script, with a trap, is the only way to make "never lingers" a property rather than a hope. |
| The skill writes `task.md`; scripts print what it needs and a validator checks the result | `rolling-begin-task` prints `branch:`, `base:`, `return-to:`, `held:` lines; the model writes the file in the documented shape; `rolling-check-task` rejects a malformed one before anything reads it | Mixed ownership of one file (script writes the top, model appends the rest) is how fields drift. One writer, one checker. `rolling-diff` and `rolling-verify` also fail safe on a bad file and say why. |
| `lesson` is the one skill the model may invoke | `disable-model-invocation: true` on `start`, `next`, `done`; not on `lesson` | `next` has to hand off to `lesson` (§ 5) and a skill reaches another only through the Skill tool. `lesson` only ever re-presents the open task, or says there is none, so an unprompted invocation is harmless; the other three do things. |
| The session stamp is written by a script, not by the model | Every learner-side skill runs `` !`rolling-claim-session ${CLAUDE_SESSION_ID}` `` inline | The stamp is what P1b's hooks use to tell the tutor from the coding session; a value the model might forget to copy is not a stamp. Inline substitution of the session id is documented; a script call is the deterministic way to persist it. |
| The spike's scripts are rewritten, not moved | `bin/` starts from the spike's contracts (`spike/README.md`) and the lessons in `spike/NOTES.md`, and reimplements them against the new layout | Every spike script hardcodes `.rolling/profile/`; the exclusions, the branch dance, and `show.sh`'s subcommands all follow from that. Porting line by line would carry the assumption along. |
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
| `claude plugin validate` accepts the marketplace root and each plugin directory, and its exit status is usable as a gate | 1a.3 | |
| `${CLAUDE_SESSION_ID}` is substituted inside a skill's inline `` !`…` `` command, and the same session's PreToolUse hook receives the same id in `session_id` | 1a.4 | |
| A plugin's `hooks.json` PreToolUse handler fires in the tutor's session for Edit and Write, receives `tool_input.file_path`, and its `deny` is honoured in `auto` mode | 1a.4 | |
| The `Skill` tool can invoke a plugin skill that does not disable model invocation, from inside another skill's turn | 1a.5 | |
| Inline commands in one skill run in document order (so `rolling-diff` completes before `rolling-verify` starts) | 1a.5 | |

## Sub-scopes

A sub-scope is a paragraph: goal, branch, dependencies, and a
done-when a reviewer can check in a line or three. Detail lives in the
artifact it describes (a spec, a script's header comment, a skill),
and the sub-scope points at it once it exists. The two exceptions
below, 1a.3 and 1a.4, carry their scripts' contracts because they were
drafted before the scripts; each slice's PR replaces its contract with
a pointer when it lands.

### 1a.1 — The repository learns how work happens here [COMPLETE]

`CLAUDE.md`, `REVIEW.md`, and `docs/workflow.md` for a plugin
repository, and this plan. Branch `p1a.1/process`; depends on
nothing. Done when an agent can read `CLAUDE.md` and know the rules,
`docs/workflow.md` fits on a page, and this plan has a paragraph per
sub-scope. PR #3.

---

### 1a.2 — The formats: `docs/map.md` and `docs/profile.md` [PENDING]

The two specs, from `docs/plan.md` § 4 and the spike's drafts, written
before any script parses either. Branch `p1a.2/specs`; depends on
1a.1. Done when `docs/map.md` specifies the map and lesson files
(carrying the slug and link rules from the old skills spec, and the
`test: held | shown` field), `docs/profile.md` specifies the learner's
directory and every file in it with the mutation rules of § 4, each
lists the validator's checks so 1a.3 implements a list, and the
spike's Rallly map conforms after at most the `test:` field is added.

---

### 1a.3 — The marketplace, the plugin skeleton, and the toolkit [PENDING]

The repository becomes a marketplace with one plugin, `rolling`, whose
`bin/` holds every script the skills and hooks call, each tested
against a scratch repository, with CI running the gate. Branch
`p1a.3/toolkit`; depends on 1a.2. Done when the gate is green in CI
and a scratch repository run through begin-task → edit → diff →
verify (with one held test) → end-task leaves the tree exactly as the
learner left it, the held test in no diff and no commit, and the
learner back on their branch.

Contracts drafted in advance (to become the scripts' header comments):

- `.claude-plugin/marketplace.json` lists `rolling`;
  `plugins/rolling/.claude-plugin/plugin.json` names it, versions it,
  and declares no dependencies. `claude plugin validate` passes on
  both.
- One resolver for the learner's directory, per the key decision
  above, shared by every script and by the hook handler; the
  mechanism rows for `CLAUDE_PLUGIN_DATA` and `bin/` on PATH are
  confirmed and recorded before anything depends on them.
- `rolling-show <what>` prints one piece of context for a skill's
  inline command and always exits 0, reporting absence in words:
  `map`; `lessons`, the index, one frontmatter block per slug, which
  is what `start` lays the course out from and `next` chooses from;
  `lesson <slug>`, one lesson in full, and `lesson` with no slug, the
  open task's; `profile`; `task`; `corpus`; `tree`; `state-dir`. Plural
  is the list, singular is the item, so no skill takes every lesson
  body into context to pick one.
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
- Every script is bash 3.2 or later, `shellcheck --shell=bash` clean,
  calls only `git` and a POSIX userland, builds any command line from
  a task file as an array, and has a test under `plugins/rolling/tests/`
  that builds a scratch repository in a temporary directory with
  `ROLLING_DATA` pointed at another one; `tests/run.sh` runs them all
  and exits non-zero on any failure.
- `.github/workflows/ci.yml` runs `shellcheck`, `tests/run.sh`, and
  `claude plugin validate` on every PR and on `main`, each as its own
  step.

---

### 1a.4 — The `write`-mode scope guard [PENDING]

The one rule that must hold when the learner asks nicely: while a
`write` task is open and this session is the tutor's, the tutor cannot
edit inside the task's scope, except scaffold paths. Branch
`p1a.4/write-guard`; depends on 1a.3. Done when, in a scratch
repository with a `write` task open, the tutor's session is denied an
Edit inside scope in `auto` mode and told why, allowed one outside it,
and a test drives the handler through every case below.

Contract drafted in advance (to become the handler's header comment):

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
- The test's cases: in-scope denied, scaffold allowed, out of scope
  allowed, no task allowed, wrong session allowed, `direct` mode
  allowed, garbage input allowed.

---

### 1a.5 — The four skills [PENDING]

`start`, `next`, `lesson`, and `done` as `rolling`'s skills, calling
the toolkit by name, holding the loop of `docs/plan.md` § 5 and the
coaching rules the spike settled (`spike/claude/skills/`, corrected
per `spike/NOTES.md`), with none of the spike's fourth-wall slips.
`lesson` is the one skill the model may invoke; `done` runs
`rolling-claim-session`, `rolling-diff`, `rolling-verify` inline, in
that order, before it speaks. Branch `p1a.5/skills`; depends on 1a.3
and 1a.4. Done when `claude plugin validate` is green, no skill grants
a map command or names a script, a task file, or a profile file to
the learner, the mechanism rows assigned to 1a.5 are recorded, and
one `write` lesson has run end to end on the Rallly clone with its
transcript read for fourth-wall slips and for the tutor writing inside
scope, written up here.

---

### 1a.6 — Running it, contained [PENDING]

A runner that puts the plugin, the map, and a Rallly clone together in
the spike's container, so a lesson runs on this machine without npm
touching the host: this repository mounted read-only and registered as
a local marketplace, `rolling` installed from it, the map copied into
the clone, the learner's directory in the home volume so it survives a
rebuild. Branch `p1a.6/runner`; depends on 1a.3. Done when, from a
fresh clone at the pin, `up`, `pnpm install` in `shell`, and `tutor`
lead to `/rolling:start` being offered and running, and
`spike/README.md` points at the new runner and calls its own frozen.

---

### 1a.7 — The Rallly map at eight to ten lessons [PENDING]

The map grows from the spike's five lessons to the set a first
fortnight needs, every lesson with a rubric, a region, a depth, a
mode, and `test: held` or `shown`; the five revised; three to five
added across the regions from the code at the pin (candidates to
confirm at the pin first: the tRPC procedure ladder and server-action
clients; email templates and their i18n; feature flags and instance
policy; invites and participants; the house-keeping cron; the Stripe
webhook as a `direct` lesson written now and served in P1b); at least
one early `write` lesson with `test: shown`; at least two suggested
courses. Branch `p1a.7/rallly-map`; depends on 1a.2. Done when
`rolling-check-map` is green, every path, line, sha, and PR number is
checked against `../rallly` at `aab791da`, and for each lesson with a
source fix `rolling-begin-task --fix` succeeds on the clone with
`rolling-verify` failing on the starting state and passing with the
reference applied.

---

### 1a.8 — The exit run, and closure [PENDING]

Run the checkpoint's exit criterion honestly and close it out. Branch
`p1a.8/closure`; depends on 1a.5, 1a.6, 1a.7. Done when three `write`
lessons have run end to end on the Rallly clone in three separate
sessions with the profile carrying the thread and the transcripts read
for the properties § 7 names; three seeded profiles (one region deep,
a different region deep, every region at working) get three different
first lessons and two seeded backgrounds with the same destination
still diverge, recorded as profile → route; `git status` in the clone
shows only the learner's own work and nothing of the learner's
directory is findable in the tree; the retrospective is appended here,
`CLAUDE.md` § Status and `docs/plan.md` § 7 are updated, the README
stops saying nothing is built, and every mechanism row above is filled
in.

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
- **Hook handlers on a host without `node`.** The plan (§ 8) has the
  handlers in Node because every Claude Code host had Node when Claude
  Code was only an npm package. The native installer bundles its own
  runtime, so a learner with a native install on a repo that does not
  need Node (Homie, in P1c) may have no `node` on PATH. Not a P1a
  problem, since Rallly requires Node; P1c meets it, and the likely
  answer is a bash handler that pulls the two or three fields it needs
  out of the hook's JSON by pattern rather than a parser.
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
