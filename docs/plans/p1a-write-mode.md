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
| The state directory is resolved one way, everywhere | `$ROLLING_DATA/repos/<encoded toplevel>/`, and nothing else; the plugin's SessionStart hook exports `ROLLING_DATA` from `${CLAUDE_PLUGIN_DATA}` through Claude Code's session environment file; encoding is the one Claude Code uses for its own project directories (every non-alphanumeric byte → `-`) | One resolver in one place, used by scripts, hooks, and tests alike. The Bash tool never sees `CLAUDE_PLUGIN_DATA` (mechanism table), so a fallback to it would never fire; the hook is the only route. Tests set `ROLLING_DATA` to a temporary directory and never touch a real one. |
| Nothing is excluded from the diff | `rolling-diff` shows the working tree against `base`, every path | The spike excluded `.rolling/` and `.claude/` because the profile and the scripts lived there. Now the tree holds only the author's map and the learner's work; a learner who edits a lesson file has made a change the tutor should see. |
| Diff first, then verify; the held test is applied inside verify, and both run from one script | `done` runs one inline command, `rolling-report`, which captures the diff and then runs `rolling-verify`; verify applies held tests, runs, reverts, restoring a learner file at the same path | The diff must not contain the held test and the tree must not keep it (§ 4). A skill's inline commands start in parallel (mechanism table), so the sequence has to live inside one script; doing the apply/revert under a trap is the only way to make "never lingers" a property rather than a hope. |
| The skill writes `task.md`; scripts print what it needs and a validator checks the result | `rolling-begin-task` prints `branch:`, `base:`, `return-to:`, `held:` lines; the model writes the file in the documented shape; `rolling-check-task` rejects a malformed one before anything reads it | Mixed ownership of one file (script writes the top, model appends the rest) is how fields drift. One writer, one checker. `rolling-diff` and `rolling-verify` also fail safe on a bad file and say why. |
| `lesson` is the one skill the model may invoke | `disable-model-invocation: true` on `start`, `next`, `done`; not on `lesson` | `next` has to hand off to `lesson` (§ 5) and a skill reaches another only through the Skill tool. `lesson` only ever re-presents the open task, or says there is none, so an unprompted invocation is harmless; the other three do things. |
| The session stamp is written by a script, not by the model | Every learner-side skill runs `` !`rolling-claim-session ${CLAUDE_SESSION_ID}` `` inline | The stamp is what P1b's hooks use to tell the tutor from the coding session; a value the model might forget to copy is not a stamp. Inline substitution of the session id is documented; a script call is the deterministic way to persist it. |
| The spike's scripts are rewritten, not moved | `bin/` starts from the spike's contracts (`spike/README.md`) and the lessons in `spike/NOTES.md`, and reimplements them against the new layout | Every spike script hardcodes `.rolling/profile/`; the exclusions, the branch dance, and `show.sh`'s subcommands all follow from that. Porting line by line would carry the assumption along. |
| The Rallly map's source stays in this repository | `examples/rallly/.rolling/`, installed into the clone by the runner; the clone's copy is never pushed anywhere | The map has to live somewhere reviewable, and P1c repackages exactly this directory as the `rallly` map plugin. What "hand-written into a local clone's `.rolling/` and never pushed" (§ 7) rules out is a fork of Rallly carrying it, not a source here. |
| The toolkit is Python 3.9, standard library only, not bash | `plugins/rolling/lib/rolling/` as a package; `bin/` executables of a few lines; `unittest` | Bash was the first choice, on a misreading of "assume nothing beyond git and a POSIX userland" as a rule about the scripts' language rather than the tools they call. Six review rounds on the bash toolkit were mostly paying for bash: quoting, word splitting, no `try`/`finally` around the one destructive path. Node was the obvious second choice and wrong for the same audience reason: Claude Code's native installer no longer brings Node, and a learner on a Go repository may not have it. Python 3 is on every Mac that has git (both come with the command line tools) and on every desktop Linux; 3.9 is the floor a Mac's tools ship. Perl is more present still, and unreadable for the same reason bash was. |
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
| `CLAUDE_PLUGIN_DATA` reaches a `bin/` script as an environment variable when the Bash tool runs it, and `${CLAUDE_PLUGIN_DATA}` is substituted in a skill's inline command and in a `hooks.json` command | 1a.3 | **Partly** (2026-09-15, 2.1.270, `--plugin-dir`). Not in the Bash tool's environment, for inline or model-run commands. Substituted in a skill's inline command and in a `hooks.json` command; a hook's process also has it in its environment, with `CLAUDE_PLUGIN_ROOT`. Path observed: `~/.claude/plugins/data/<plugin>-<marketplace>/`, `inline` as the marketplace for `--plugin-dir`; created on first session. **And confirmed:** a SessionStart hook can append `export VAR=…` to the file named by `CLAUDE_ENV_FILE`, and every later Bash command in the session sees it, inline commands included. That is the resolver: the hook exports `ROLLING_DATA`. |
| A plugin's `bin/` is on the Bash tool's PATH in a session where the plugin is enabled through a local marketplace, and stays so across `/clear` | 1a.3 | **Yes** for `--plugin-dir` (a bare name resolved to the plugin's `bin/`, from an inline command and from a model-run one). A marketplace install and `/clear` are checked when 1a.6's runner exists. |
| `claude plugin validate` accepts the marketplace root and each plugin directory, and its exit status is usable as a gate | 1a.3 | **Yes.** Exit 0 with warnings printed; `--strict` turns warnings into exit 1 for CI; `--json` available. Warns on a missing marketplace description and plugin author. |
| `${CLAUDE_SESSION_ID}` is substituted inside a skill's inline `` !`…` `` command, and the same session's PreToolUse hook receives the same id in `session_id` | 1a.4 | **Yes** (seen while confirming 1a.3's rows): the substituted value, the hook's `session_id`, the Bash tool's `CLAUDE_CODE_SESSION_ID`, and the print-mode result's `session_id` were one string. One caveat: a Claude session started from inside another's Bash tool once inherited the outer `CLAUDE_CODE_SESSION_ID`, so the skills use the substitution, never the variable. |
| A plugin's `hooks.json` PreToolUse handler fires in the tutor's session for Edit and Write, receives `tool_input.file_path`, and its `deny` is honoured in `auto` mode | 1a.4 | Fires for Bash under `--plugin-dir` (seen). Edit and Write, `file_path`, and `deny` under `auto`: 1a.4. |
| The `Skill` tool can invoke a plugin skill that does not disable model invocation, from inside another skill's turn | 1a.5 | From a prompt, yes (seen). From inside another skill's turn: 1a.5. Also seen: a skill's inline command goes through permissions like any Bash call, so an inline `sh -c …` with no matching grant is refused and the skill fails; every inline command must be a single `bin/` invocation the skill's `allowed-tools` names. |
| Inline commands in one skill run in document order (so `rolling-diff` completes before `rolling-verify` starts) | 1a.5 | **No.** They start together: three inline commands, one sleeping two seconds, all began within a millisecond. Anything that must be sequenced runs inside one script; `done` gets a single inline `rolling-report` that captures the diff and then runs the verifier. |

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

### 1a.2 — The formats: `docs/map.md` and `docs/profile.md` [COMPLETE]

The two specs, from `docs/plan.md` § 4 and the spike's drafts, written
before any script parses either. Branch `p1a.2/specs`; depends on
1a.1. Done when `docs/map.md` specifies the map and lesson files
(carrying the slug and link rules from the old skills spec, and the
`test: held | shown` field), `docs/profile.md` specifies the learner's
directory and every file in it with the mutation rules of § 4, each
lists the validator's checks so 1a.3 implements a list, and the
spike's Rallly map conforms after `test:` and a `###` course heading are added.
PR #4.

---

### 1a.3 — The marketplace, the plugin skeleton, and the toolkit [COMPLETE]

The repository is a marketplace with one plugin, `rolling`, whose
`bin/` holds every command the skills and hooks call, each tested
against a scratch repository, with CI running the gate on Python 3.9
and on a Mac. Branch `p1a.3/toolkit`; depends on 1a.2. Done: the
gate is green, and the scratch-repository loop (begin-task → edit →
diff → verify with a held test → end-task) is a test that leaves the
tree as the learner left it, the held test in no diff and no commit,
and the learner back on their branch. The contracts drafted here
became the scripts' header comments; the table in
[`plugins/rolling/README.md`](../../plugins/rolling/README.md) is the
index. Two things the slice added to the plan's list: a SessionStart
hook handler, because the Bash tool never sees `CLAUDE_PLUGIN_DATA`
and the session environment file is the way to hand it on; and
`rolling-report`, because inline commands start in parallel. The
spike's Rallly map passes `rolling-check-map` but for the one `###`
course heading 1a.7 adds. The pre-push review found that the held
test's revert could lose the learner's own file on a failed restore
and could not survive a kill the trap cannot catch (the Bash tool's
timeout); the fix keeps the set-aside copy and a step-by-step record
in the learner's directory, and every script that touches the tree
finishes a pending revert before doing anything else. The both-ways
proof now counts a line that did not run as a failure, a map command
ending in a control operator is refused, and `--here` takes the paths
it may commit and refuses the rest. A second round found the holes in
those fixes (a repeated held path, a catchable signal, a failed revert
still proving ok, redirections) and closed them; a third found the
symbolic-link cases, and the toolkit now refuses a link anywhere in a
held path rather than reason about it. The test file for the review
rounds is the largest in the suite, which is the right way round.
PR #5. Then the maintainer read the map checker, asked whether bash
was the right language, and it was not: the toolkit was rewritten in
Python from the contract (the lines a skill reads, the specs' check
lists, the exit conventions) rather than translated, with the same
scenarios as tests (1a.3b). The bash version is in the history as the
record of what the reviews found.

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
  for Edit, Write, MultiEdit, and NotebookEdit that runs a handler in
  `bin/` (Python, like the rest) and passes it the data directory.
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
`rolling-claim-session` and `rolling-report` (diff, then verifier) inline,
before it speaks. Branch `p1a.5/skills`; depends on 1a.3
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
