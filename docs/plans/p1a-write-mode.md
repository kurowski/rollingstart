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
| The model writes its files through a script, not the Write tool | `rolling-write task\|profile\|reference` and `rolling-note <lesson>` read the text on standard input (a heredoc), check it, and write it; `rolling-write task` rewrites every `tutor-session` line the text carries with the recorded one (the open task's, else the `session` file the inline claim wrote), refusing when none is recorded; `rolling-keep-task` copies a proved task to `tasks/`; `rolling-write patch --from-tree <path>…` takes a seam task's reference from the tree where the tutor tried it (a new file removed afterwards; its content is in the patch), since the Bash tool refuses a heredoc carrying code | Found by 1a.5's first end-to-end turn: the data directory is under `~/.claude`, a documented protected path, so Edit and Write there prompt on every call in every mode short of bypassing permissions, and no allow rule pre-approves it. A granted `bin/` script is not prompted, and Claude Code hands a plugin its data directory precisely for its scripts. The model still authors every byte, so the decision above stands; the pen names files by role, never by path, so the grant writes nothing else. |
| The forward proof is a toolkit command | `rolling-verify --on-reference` applies the reference as a patch (the fix's own change against HEAD, or `reference.patch` written with the pen for a seam task), runs every line with the held test, and reverses the patch in a `finally`; `next` runs no free-form git | Found by 1a.5's second end-to-end turn: the guard denied the tutor's own reference edit, as it should, and the tutor served the task with only half a proof. The plan's "applying and undoing the reference" as free-form git prompted for approval and needed a write inside scope; a script needs neither. |
| The tutor's session stamp is script-written, not script-proof | `rolling-claim-session` takes the id on its command line (the skills pass `${CLAUDE_SESSION_ID}`), the pen rewrites any `tutor-session` line the model types, and nothing checks the id against Claude Code | The guard keys on that stamp. A model that ran `rolling-claim-session <made-up>` in its own session, or rewrote the task file through a shell, would turn the guard off for itself. A check against `CLAUDE_CODE_SESSION_ID` was tried in 1a.5's review and dropped: the variable is the model's own environment, and a nested `claude -p` inherits the outer session's, so the check refused the right id where the plan drives its end-to-end runs. The hook payload's `session_id` is the one value the model cannot forge, but every file it could be recorded in is one the model's shell can rewrite, so no script-side check is hook-grade while Bash is unrestricted. In P1a this is prose in the skills; P2's eval measures whether it holds, and P2 decides whether a Bash rule on the data directory is worth its false positives, the same call as the scope rule two rows up. |
| The task branch carries the map as of now | `rolling-begin-task --fix` puts `.rolling` from the commit the task began on into the starting-state commit, replacing whatever the branch point had | Found by the same turn: the branch is cut from the fix's parent, and every fix on the Rallly map predates the map's commit, so the task branch had no map at all. In `base`, so never in the learner's diff. |
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
| A plugin's `bin/` is on the Bash tool's PATH in a session where the plugin is enabled through a local marketplace, and stays so across `/clear` | 1a.3 | **Yes for both routes, and across `/clear`** (the clear checked by hand, 2026-09-19, in the runner's `tutor` session: after `/rolling:start` and `/clear`, `rolling-show map-check` ran from the Bash tool and reported the map's one fault). For `--plugin-dir`: a bare name resolved to the plugin's `bin/`, from an inline command and from a model-run one. For a marketplace install (2026-09-19, 1a.6's runner, in the container): with this repository added as a local marketplace (`source: directory`, path `/rolling`) and `rolling` installed from it, `/rolling:start`'s inline `rolling-claim-session` ran and wrote `session` under the data directory `~/.claude/plugins/data/rolling-rollingstart/repos/-work/`, before the model turn. So `bin/` resolves and the data directory is the plugin id with the marketplace name, in the home volume. Three more facts: an install copies the plugin into `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, stamped with the repository's commit, and neither `install` nor `update` refreshes that copy while the version stands; `plugin uninstall` deletes the data directory unless `--keep-data` is given, so the runner's `up` uninstalls with `--keep-data` and reinstalls to pick up an edit; the copy is taken from the working tree, uncommitted edits included; and the marketplace source must stay reachable in every session, since Claude Code resolves an installed plugin through it at load time and reports `cache-miss` (no skills, no hooks) when the directory is gone, so the runner mounts the manifest and the plugins directory in the tutor's session too. `/clear` is checked by hand in an interactive session (the runner's `tutor`), not here. |
| `claude plugin validate` accepts the marketplace root and each plugin directory, and its exit status is usable as a gate | 1a.3 | **Yes.** Exit 0 with warnings printed; `--strict` turns warnings into exit 1 for CI; `--json` available. Warns on a missing marketplace description and plugin author. |
| `${CLAUDE_SESSION_ID}` is substituted inside a skill's inline `` !`…` `` command, and the same session's PreToolUse hook receives the same id in `session_id` | 1a.4 | **Yes** (seen while confirming 1a.3's rows; confirmed again by the 1a.4 probe): the substituted value, the hook's `session_id`, the Bash tool's `CLAUDE_CODE_SESSION_ID`, and the print-mode result's `session_id` were one string. One caveat: a Claude session started from inside another's Bash tool once inherited the outer `CLAUDE_CODE_SESSION_ID`, so the skills use the substitution, never the variable. |
| A plugin's `hooks.json` PreToolUse handler fires in the tutor's session for Edit and Write, receives `tool_input.file_path`, and its `deny` is honoured in `auto` mode | 1a.4 | **Yes** (2026-09-15, `--plugin-dir`, print mode). Fires for Write with an absolute `file_path`; the input also carries `cwd`, `session_id`, `permission_mode`, `tool_use_id`, `transcript_path`. Under `--permission-mode acceptEdits`, where edits are auto-approved, the hook's `deny` held: the write outside the guarded path landed, the one inside did not, and the model reported the reason verbatim. A second probe under `--permission-mode auto` reported `permission_mode: auto` in the hook input and the deny held there too. |
| The `Skill` tool can invoke a plugin skill that does not disable model invocation, from inside another skill's turn | 1a.5 | **Yes** (2026-09-16, `--plugin-dir`, print mode): a manual-only outer skill invoked an inner one through the Skill tool and the inner's instructions ran in the same turn; the outer skill's own `allowed-tools: Skill(plugin:inner)` covered the call with no session grant, and the narrow form validates strictly. Also seen: a skill's inline command goes through permissions like any Bash call, so an inline `sh -c …` with no matching grant is refused and the skill fails; every inline command must be a single `bin/` invocation the skill's `allowed-tools` names. **Three more facts from the same probes.** A slash command in print mode (`claude -p "/rolling:next"`) does run the skill and a model turn, so end-to-end runs drive skills directly; a session is continued with `--resume`, never a reused `--session-id`. A skill's `allowed-tools` hold only for the turn the skill was invoked in: in the learner's next plain turn the same `rolling-*` commands prompt, once each, so a skill that finishes in a later turn says so and carries on. And the plugin's data directory is a protected path (see the pen decision above). |
| A non-zero exit from a skill's inline command aborts the skill | 1a.5 | **Yes, entirely** (2026-09-19, probe): the run had zero model turns and an empty result, and the command's output arrived as a `local-command-stderr` block. So anything a skill must be able to talk about runs inline through a command that always exits 0 and reports in words (`rolling-show map-check`); the exit-1 variants are for actions and CI. Found by the GitHub review of PR #9, which read `next`'s inline `rolling-check-map` against the dispatch table. |
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
record of what the reviews found. PR #6.

---

### 1a.4 — The `write`-mode scope guard [COMPLETE]

The one rule that must hold when the learner asks nicely: while a
`write` task is open and this session is the tutor's, the tutor cannot
edit inside the task's scope, except scaffold paths. Branch
`p1a.4/write-guard`; depends on 1a.3. Done: `hooks.json` registers a
PreToolUse handler for Edit, Write, MultiEdit, and NotebookEdit,
`rolling-guard`, which finds the repository from the edited path (the
hook's cwd follows every `cd`, so a guard keyed on it is off after
one), reads the open task from the data directory the hook is handed,
denies an edit inside `scope:` unless the path is a `scaffold:` path,
with a reason that says what the tutor may do instead, and allows
everything else, including everything it cannot make sense of, since
a hook that blocks a session on its own failure is worse than none.
The path is judged as spelled and with every link resolved, and on a
case-folding filesystem the comparison folds. Both mechanism rows
assigned here are confirmed (table above). The tests drive the handler
with hand-built events, the bypasses two review rounds found among
them; an end-to-end run with the real plugin, a task open and the
session id pinned, was denied inside the scope and allowed outside it.
The contract is the module's docstring, `lib/rolling/guard.py`. PR #7.

---

### 1a.5 — The four skills [COMPLETE]

`start`, `next`, `lesson`, and `done` as `rolling`'s skills, calling
the toolkit by name, holding the loop of `docs/plan.md` § 5 and the
coaching rules the spike settled (`spike/claude/skills/`, corrected
per `spike/NOTES.md`), with none of the spike's fourth-wall slips.
`lesson` is the one skill the model may invoke; `done` runs
`rolling-claim-session` and `rolling-report` (diff, then verifier)
inline, before it speaks. Branch `p1a.5/skills`, on top of
`p1a.5a/toolkit-writes`; depends on 1a.3 and 1a.4. Done: `claude
plugin validate --strict` is green; no skill grants a map command, a
package manager, or git that changes the tree, and none names a
script, a task file, or a profile file to the learner; the mechanism
rows above are recorded. The first end-to-end turns found three
mechanisms the toolkit lacked, which became the base PR of this stack
(the pen, since the data directory is a protected path; the forward
proof as a command, since the guard rightly denied the tutor its own
reference; the map carried onto a task branch cut from before it
existed). Then one `write` lesson ran end to end on the Rallly clone
twice, in print mode with the session resumed turn by turn and the
map's `pnpm` commands pre-approved for the run, since in print mode a
prompt is a denial and interactively each would have asked:
`/rolling:next` chose `poll-data-model` for a returning learner with
polls at `working`, built a seam task (a bulk-revoke mutation beside
its single-invite sibling), wrote the test, the task, the reference,
and the patch through the pen (the task file refused twice for a
malformed `expect-fail-on-base` line and the tutor corrected it),
proved it both ways (`PROOF: ok` twice), kept the task, and handed
off to `lesson`, whose brief opened with the mode, gave the map's
command verbatim as what "done" means, and said a reference was held
without naming a file. `/rolling:done` put the passing check on the
table first, read the diff against the rubric with a path, a line,
and a provenance per point, noticed the change was byte-identical to
its own reference and said so, left the rubric's explain-it bullets
to the learner, and when the learner said "I agree" without
answering, recorded a disagreement and kept the lesson open rather
than leaving the branch. In the first run the learner did answer and
the tutor marked the lesson satisfied, rewrote the profile, ended
the task (the work committed on the kept branch, the tree back where
it was, clean) and closed it. Transcripts read for the failure modes
the plan names: no fourth-wall slip in either (the tutor named the
branch and the map's commands, never a file of its own); the tutor
wrote inside the scope only before the task existed, to prepare the
test and try its solution, which the design allows, and the guard
denied its one attempt after. Warts recorded for the next slices: a
`direct` opening lesson (`how-a-change-ships`) blocks a fresh Rallly
learner until P1b, so the runs used a profile with it satisfied; the
map's `lint` is `biome check .`, which the tutor rightly dropped from
a verifier when the environment's ignored settings file failed it
(1a.7's map fixes that); and the transcript of a seam task shows the
solution, since the tutor tries it in the tree, so a learner reading
the tutor's tool calls has the answer (named as an exposure, not
solved). PR #9, on top of PR #8. **Review round, 2026-09-19.** The
automatic review never ran on #8 or #9 (the workflow was the
installer's no-op until PR #12's run), so each got a local Opus review
after the fact, in a scratch clone. Seven real findings, fixed in PR
#13 with tests: a `git apply` that failed part-way through writing
the reference deleted its own record, so a half-applied answer read
as the learner's work (the record now stays, and every command
refuses until the tree is put right); `rolling-write patch
--from-tree` reset any named path to HEAD with a task open, a hole in
the write guard (refused while a task is open); `next` prescribed the
seam-task order `--here` then `--from-tree`, which `begin` always
refuses (swapped, and the pen refuses to take from the tree once a
task file exists);
`--on-base` said ok for a task with no `expect-fail-on-base` line
(a proof gap now); `done` and `start` granted the whole pen where
they use `rolling-write profile` (narrowed to `Bash(rolling-write
profile *)`, after a probe showed a prefix grant matches a heredoc
invocation with nothing after the prefix: `Bash(cat profile *)` ran
`cat profile <<'EOF'` with no denial); `next`'s task shape
spelled the `expect-fail-on-base` line so that the pen refused it,
twice per task in every run so far (spelled out); `done` could close a
task without ending it and strand the learner on the branch (close
follows end, and "no" runs neither). Smaller: the pen no longer
removes a new file's directory, which may be the learner's; two keeps
in one second get two files; a refused write reports its own reason;
`lesson` is granted Edit and Write for the scaffold markers it
allows; the plugin's prose names no framework. Still open, by
choice: `git diff`, `git show`, and `git log` all take
`--output=<file>`, a write the guard cannot see, and `next` grants
all three and `done` the last two while the learner's task is open;
a prefix grant cannot exclude a flag, so prose covers it. The second
review round found that `reference.repair` cleared a record when the
patch re-applied forward and did not reverse, which a mode-change
entry that landed alone satisfies (a mode entry re-applies whatever
the mode is), so it now refuses to clear while any path the patch
names is dirty; and that its reverse-failed message advised a
`git apply -R` that cannot work on a half-applied tree, which now says
what to put back.

---

### 1a.6 — Running it, contained [COMPLETE]

A runner that puts the plugin, the map, and a Rallly clone together in
the spike's container, so a lesson runs on this machine without npm
touching the host: this repository's marketplace manifest and plugins
mounted read-only and registered as a local marketplace, `rolling`
installed from it, the map copied into the clone, the learner's
directory in the home volume so it survives a rebuild. Branch
`p1a.6/runner`; depends on 1a.3. Done: `runner/` at the repository
root (`Dockerfile`, `run.sh`, `env.sh`, `README.md`), the spike's
image plus that read-only mount under `/rolling`, narrowed so the
plan, the map sources, and the spike stay out of the tutor's session;
Python needs no adding, the base image ships 3.11. `up` builds the
image, starts Rallly's stack, writes the `.env` files, removes what
the spike's installer left in the clone, puts the map in committed on
a local branch `rolling/map` (a task begins only from a clean tree,
found in 1a.5), and installs the plugin from the marketplace,
uninstalling with `--keep-data` first when it is already there, since
the install is a copy keyed by version that nothing else refreshes and
a plain uninstall deletes the learner's state (mechanism row above).
`spike/README.md` calls its own runner frozen and points here.
Verified in the container: the plugin listed and enabled at user
scope; `/rolling:start`'s inline commands ran under the marketplace
install and wrote the session under
`~/.claude/plugins/data/rolling-rollingstart/`, in the home volume; a
second `up` after an edit refreshed the copy and kept that directory.
What the container could not do on its own: the model turn, since the
login the spike left in its volume had expired and a login is
interactive, and `/clear`. The maintainer did both from `runner/run.sh
tutor` the same day: logged in, ran `/rolling:start`, ran `/clear`,
and had the tutor run `rolling-show map-check`, which resolved and
reported the example map's one fault, the missing course heading that
1a.7 fixes. PR #11.

---

### 1a.7 — The Rallly map at eight to ten lessons [COMPLETE]

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
reference applied. Done: ten lessons in `examples/rallly/.rolling/`,
three courses (`Generalist`, `Product engineer`, `Billing engineer`)
under `## Suggested courses` with a `###` each, the map check green.
The five added are `procedures-and-actions` (the ladder in `trpc.ts`
and the clients in `safe-action/server.ts`), `emails-and-i18n`,
`flags-and-policy`, `invites-and-participants`, and `stripe-webhook`
(`direct`, `deep`, for P1b); the house-keeping cron is a paragraph of
`poll-lifecycle`, which already covered its three poll tasks, rather
than a lesson of its own. One mode changed: `how-a-change-ships` is
now `write` with `test: shown`, built from `aab791da` (#3235) with the
one unit test the fix tightened brought forward, because as a `direct`
opener it blocked every fresh learner until P1b (1a.5's wart) and
because the plan wanted an early `shown` lesson where the point is the
mechanics; `poll-lifecycle` and `billing-and-tiers` stay `direct`.
Every path, line, sha, and PR number was read at the pin; two facts
had moved since the spike (`vercel.json` is `apps/web/vercel.json`; the
invite link's query key is `token`, not `invite`, since #3188) and are
fixed, and the line numbers the old lessons cite all still hold. The
map's commands changed from what the runs found: `lint` is `pnpm exec
biome check` with a path appended, since `pnpm check` (`biome check
.`) fails on the container's `.claude/settings.local.json`, which git
ignores through the global excludes file that Biome's `useIgnoreFile`
does not read; `typecheck-web` and `typecheck-emails` are added as the
scoped type checks (fifteen seconds and two, in the container) so a
verifier fits the two-minute limit; and the environment is a
`## Environment` section. Five lessons name a fix with a unit test the
container can run, and each was proved on the clone the way `next`
would: a throwaway container from the runner's image with scratch
state, `rolling-begin-task <lesson> --fix <sha>` with the test held or
shown, a task file written through the pen, `rolling-verify --on-base`
and `--on-reference`, then end, close, and the branch deleted, the
clone back on `rolling/map` and clean. All five prove `PROOF: ok` both
ways: `how-a-change-ships` (`aab791da`, shown, with `typecheck-web`,
`lint`, `structure`), `emails-and-i18n` (`e84e55da`, held, with
`typecheck-emails` and `lint`), `procedures-and-actions` (`9f52dbe7`,
held), `invites-and-participants` (`3011b1ad`, held), and
`flags-and-policy` (`d374ed48`, held), the last three with `lint` and
`structure` only. The proofs found three things the map now says.
A task cut from before a schema change (the participant-token
migrations of 2026-09-04 to 09-06 sit between three of these parents
and the pin) fails `typecheck-web` on seventy errors in files it never
touches until the Prisma client is regenerated for that tree, so such
a task names `regenerate-client` as its `setup:` operation when its
checks load the real client, and its brief tells the learner to run
it again on return, since nothing runs it at `done`; the unit tests
run against the mocked client and passed under the stale one, which
the automatic review on the PR was the first to point out (the three
lessons had said otherwise, and `local-dev-setup` carried a `test:`
field with no test to apply it to; both fixed in the review round). Even then, the pin's `node_modules` finds a handful of
errors at a parent six lockfile commits behind (an implicit `any` in
the private API's schemas, two in the user mutations), so
`typecheck-web` is in a verifier only for the task cut from the pin's
own parent; the three older tasks say so in their lessons and have the
tutor run it on request. And a verifier line cannot carry the
bracketed path of a Next.js route test (`[locale]`, `(space)` are
shell metacharacters), while `--shown` can, since git is handed a
literal pathspec: the shown test's line is `test-web
leave-space-dialog.test.tsx`, vitest's name filter. `poll-data-model`
keeps no fix of its own: its exemplary one (`af3d9273`) is proved by a
Playwright spec, which this environment has no browser for, so the
lesson tells the tutor to build along a seam, which is what 1a.5's
runs did. The prose was reviewed by running it: a profile seeded
in the runner's container (TypeScript and React, never tRPC, platform
and polls at `working`, the setup lesson satisfied) and `/rolling:next`
in print mode. The tutor chose `how-a-change-ships` as the only
reachable lesson and said why in a route note, read the lesson, checked
`git log` for schema changes between the fix's parent and the pin as
the map now says to and found none, cut the branch with the test
shown, had the task refused twice by the pen for the
`expect-fail-on-base` line (the same stumble as 1a.5: it wrote the
line without the `verify` prefix, then with a colon), proved it both
ways, kept it, and handed off; the brief opened with the mode, gave the
map's commands verbatim, said a reference was held, and named no file
of the tutor's. One thing to watch: the brief listed the inputs the fix
touches, read off its diff, which a learner would otherwise find with
a grep; not the answer, but a step of it. For 1a.8: the `next` skill's
`task.md` shape could spell the `expect-fail-on-base` form out
(`verify <the line's text>`) so the pen stops refusing it; a task cut
from before a schema change leaves the learner's generated client
stale on return, and only the brief says so; and the clone carries two
of the maintainer's own task branches from the spike's runs
(`rolling/how-a-change-ships-20260913-*`), which are theirs to delete.
PR #12.
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
  stamp is the only piece of it written here. One hazard for P1b's
  design, from the review round: `lesson` is model-invocable and its
  inline `rolling-claim-session` rewrites the stamp, so once the
  learner's coding session has the plugin enabled it can claim the
  tutor's role on its own initiative and move the guard off the
  tutor. P1b decides whether `lesson` claims at all.
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
