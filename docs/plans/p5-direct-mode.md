# P5: `direct` mode (2.0)

> The plan's entry is [`docs/plan.md`](../plan.md) § 7, P5. This
> file is the tracker for the checkpoint. Each PR flips its own
> sub-scope from `[PENDING]` to `[COMPLETE]`. When the whole checkpoint
> ends, a retrospective is appended.

## Context

P1a delivered the learner loop as a plugin for `write` mode, against a
map committed in the target repository, and the first fresh learner's
four lessons then reshaped it (PRs #16 to #19, recorded in
[`p1a-write-mode.md`](p1a-write-mode.md) under "After closure"): the
learner drives, a lesson opens with a walkthrough and offers its
exercise, `task` builds on a yes, `cancel` stops, and the toolkit's git
undoes what it cannot finish. Every one of those is mode-agnostic, and
`direct` mode inherits them.

P5 delivers `direct` mode, the first checkpoint of 2.0: the lesson the
plan is aimed at, where the learner directs a coding agent in a second,
ordinary Claude Code session and the tutor watches how it goes, then
reads the whole of it. It was planned as P1b and moved behind the 1.0
release on 2026-09-22 (`docs/plan.md` § 10); the plan was written and
its mechanisms confirmed that day, so it starts from known ground.
Concretely: the session-identity contract that tells the tutor's
session from the coding session; three hook handlers that run in every
session where the plugin is enabled (the session log, the guard on the
learner's state directory, and ask-before-destructive); a `direct`
task, built from a situation rather than a brief and presented with the
instruction to open a second session; the watch, a Monitor the `lesson`
skill arms over the session logs, with the short list of things worth a
word; and a `direct` `done` that reads the session against the human's
ledger, in the register the learner drives.

End state: a learner with `poll-data-model` satisfied runs
`/rolling:next` on the Rallly clone, is walked through `poll-lifecycle`,
takes the offer, is handed a situation and told to open a second
session in the same directory, directs an agent there over as many
turns as it takes while the tutor watches and speaks only when there is
something worth saying, quits and restarts the tutor part-way and finds
it still the tutor, says done, and gets feedback on how they directed,
with the verifier's findings taken off their ledger first. Nothing the
tutor holds is readable from the coding session. The learner closes
the lesson.

P6, the upper rungs of `direct`, follows.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Only the learner-typed skills claim the session | `start`, `next`, `done`, and `cancel` run `rolling-claim-session` inline; `lesson` and `task` do not, and instead run `rolling-show whoami ${CLAUDE_SESSION_ID}`, which says whether this session is the tutor's; when it is not, they say so and point at `/rolling:start`, and build or present nothing | P1a's deferred hazard: `lesson` is model-invocable, and now so is `task`; a coding session with the plugin enabled could invoke either on a description match, and an inline claim there would move the guard off the tutor and turn the log off for the coding session. A restarted tutor reclaims through the skill it types first, which `start` and `next` both are. Nothing about the stamp becomes script-proof (P1a's decision stands, P2's eval measures); this closes the one route a model could take without meaning to. To confirm in 5.2 before building on. |
| The log is JSON lines, one event per line, whole | `sessions/<session id>.jsonl` in the learner's directory: `{"t": <ISO time>, "kind": "prompt" \| "edit" \| "command" \| "reply", …}` with the prompt text, the edited path and tool, the command, or the reply text; nothing truncated | A model reads it, and `done` reads all of it; a Monitor filters it. Truncating a reply to save bytes would lose exactly what `done` needs (what the agent said it did). The spike's line format needed a regex to filter; JSON lines need `json.loads`. |
| Which sessions are logged | Every session in the repository whose id is not the tutor's, while a `direct` task is open; nothing otherwise | The plan's rule (§ 5). A `write` task, or no task, logs nothing: the learner's other sessions in the same repository are theirs. The hook handler decides from the open task's `mode` and `tutor-session` and the event's `session_id`, and does nothing on anything it cannot make sense of. |
| The state guard denies by path and by name | PreToolUse on Read, Glob, Grep, Edit, Write, MultiEdit, NotebookEdit: deny a path under the learner's directory; on Bash: deny a command that names the learner's directory, `ROLLING_DATA`, or a `rolling-` executable; in a session that is not the tutor's, while a `direct` task is open | The reference and the held test are there, and a coding agent grepping the machine for the failing behaviour could land on them (the spike's motivation). Naming the executables closes the route through the toolkit itself (`rolling-show reference`), which a `Bash(rolling-*)` allow rule in the author's settings would otherwise pre-approve for the coding session too. The tutor's session is never guarded here (the write guard is its own). Everything else allows. |
| Destructive operations ask in every session | The ask-before-destructive hook is P2's (1.0), not this checkpoint's; it applies to the coding session as to any other, and this plan only checks that it does | Not specific to `direct`; the `ask` decision was confirmed below while this plan was P1b's, and the hook's shape (the head of a destructive operation, the map found from the command's working directory) is recorded in `docs/plan.md` § 7, P2. |
| The watch is a toolkit command under a Monitor | `rolling-watch` tails `sessions/*.jsonl` and prints one line per prompt, reply, and edit (commands stay in the file); `lesson` arms it with the Monitor tool for the maximum window and re-arms on expiry; where Monitor is unavailable, `lesson` says so and `done` reads the log | The Monitor's contract is a command whose stdout lines are events (confirmed below); a script keeps the filter out of the skill and testable. Thirty minutes is the ceiling, so a lesson longer than that re-arms, which is one tool call at the expiry notice. |
| The tutor speaks on a short list, and otherwise holds an empty turn | The agent editing outside the task's scope and the learner not noticing; a result accepted with no check run; the same ask rephrased a third time; a destructive operation about to run | § 5 and § 8: the risk is noise. Every intervention is an offer in a line or two and an **Intervention** entry in evidence, on the tutor's ledger. Whether a model holds an empty turn on a notification is measured in 5.7 and, properly, in P2. |
| A `direct` task is a situation, built the same way | `task` builds from a fix or a seam exactly as for `write`, held test and both-ways proof included; the body is `## Situation` (a symptom, a request, a report), never instructions; `lesson` presents it with "open a second Claude Code session in this directory and direct it" | § 4. The learner writes the brief for the agent; a task that arrives as a brief has done their work. The proof machinery is mode-agnostic. |
| The write guard covers the tutor in a `direct` task too | `rolling-guard` denies the tutor's Edit and Write inside the scope for any open task, not only `write` | The tutor never writes the change in either mode; in `direct` the learner's agent does. Same harm (the tutor doing the work), same hook; one condition removed. |
| `done` in `direct` reads the log with the ledger, and the learner closes | `rolling-show sessions` renders every log for the open task; the skill takes the verifier's findings off the learner's ledger first, then reads the session turn by turn and says what it noticed, once, as a colleague would; the learner closes, as in `write` | The plan's § 5 as rewritten before this checkpoint: the ledger is kept for what it is good for (not blaming the learner for what tests catch), the register is the one the learner drives. |
| The runner grows a second window on purpose | `runner/run.sh code <clone>`: a plain `claude` in the same container and directory, no plugin flag, nothing pinned | The coding session must be an ordinary session with the plugin enabled at user scope (which the container's is), so the same command a learner would type; the runner only saves the `shell` then `claude` dance. The output-style eval (exit criterion) runs against exactly this. |

A decision that would have to be re-derived if forgotten also goes to
`docs/plan.md` § 10, dated, when the checkpoint ends.

## Mechanisms to confirm first

Each is confirmed in a scratch setup (a throwaway plugin under the
session's scratchpad, a scratch repository, the runner's image), by
the sub-scope named, before that sub-scope builds on it.

| Mechanism | Sub-scope | Result |
|---|---|---|
| A plugin's hooks fire in a session that never invokes one of its skills: UserPromptSubmit, PostToolUse, and Stop, with the fields the log needs | 5.1 | **Yes** (2026-09-22, `--plugin-dir`, print mode, in the runner's image against a scratch repository). A plain `claude -p` that ran one Bash command fired all three: UserPromptSubmit carries `prompt`; PostToolUse carries `tool_name`, `tool_input`, and `tool_response` (for Bash a dict with `stdout`, `stderr`, `interrupted`); Stop carries `last_assistant_message` (the docs say to use it rather than the transcript, and it held the reply verbatim). Every event carries `session_id`, `cwd`, `permission_mode`, `transcript_path`, and `prompt_id`; the hook's environment has `CLAUDE_PLUGIN_DATA` and `CLAUDE_PLUGIN_ROOT`, and no `CLAUDE_ENV_FILE` outside SessionStart. `agent_id` is absent on the main thread, as the docs say; a subagent's events carry it, to be seen in 5.3. |
| A plugin skill can arm a Monitor and receive its events | 5.1 | **Yes** (same probe). A skill whose `allowed-tools` names `Monitor` (strict validation accepts it) armed `tail -F` on a file, slept, and reported both lines appended by another process, in one print-mode run. Interactive persistence across turns, the expiry notice, and re-arming are checked by hand in 5.4 in the runner's `tutor`. |
| A PreToolUse `ask` decision is honoured | 5.1 | **Yes** (same probe). A hook returning `permissionDecision: ask` for a Bash command: in print mode under `acceptEdits` the command did not run, the result reported one permission denial, and the model told the user the command needed confirmation. The interactive prompt is checked by hand in 5.3. |
| The same hooks fire under a marketplace install, in a second session started in the same directory with no plugin flag, with a different `session_id` from the tutor's | 5.2 | |
| Monitor is available in the runner's environment | 5.1 | **Yes**: the probe above ran there (OAuth login, no Bedrock or Vertex). Corporate targets on those providers degrade to reading the log at `done`, per § 8. |
| A Monitor re-armed at expiry keeps delivering, and an empty turn on a notification is possible | 5.4 | |
| `rolling-show whoami` from a skill's inline command can tell the tutor's session from another (the substituted `${CLAUDE_SESSION_ID}` differs between two sessions in one directory) | 5.2 | |
| A hook's `deny` on Read/Grep/Glob for a path outside the working directory is honoured, and a Bash deny by command text does not break the coding session's ordinary work | 5.3 | |

## Sub-scopes

A sub-scope is a paragraph: goal, branch, dependencies, and a
done-when a reviewer can check in a line or three. Detail lives in the
artifact it describes (a spec, a script's header comment, a skill),
and the sub-scope points at it once it exists.

### 5.1 — The plan [COMPLETE, written as P1b's]

This file, with the three mechanisms above confirmed in a scratch
setup and recorded. Written as the P1b plan on branch `p5.1/plan` and
retitled the same day when `direct` moved to 2.0. The mechanism rows it
owns are filled; the rest wait for the checkpoint to open.

---

### 5.2 — Session identity [PENDING]

The contract that tells the tutor's session from every other one, and
the toolkit's word on it. `rolling-show whoami <id>` says whether the
given session is the tutor's (the open task's `tutor-session`, else the
`session` file); `lesson` and `task` run it inline instead of claiming,
and say so and stop when the answer is no; `start`, `next`, `done`, and
`cancel` claim as before. `docs/profile.md` says which skills write the
stamp and why the other two read it. Branch `p5.2/session-identity`;
depends on 5.1. Done when the marketplace-install row and the
`whoami` row of the mechanism table are filled in from the runner (two
sessions in one directory, the second started with `runner/run.sh
code`), the tests cover both answers and a missing stamp, and a
`/rolling:lesson` typed in the second session says it is not the
tutor's and presents nothing.

---

### 5.3 — The hooks [PENDING]

Three handlers in `hooks.json`, all Python in `bin/`, all opening by
reading the open task and the event's `session_id`, all allowing on
anything they cannot make sense of. `rolling-log` on UserPromptSubmit,
PostToolUse (Edit, Write, MultiEdit, NotebookEdit, Bash), and Stop:
appends one JSON line to `sessions/<session id>.jsonl` for a session
that is not the tutor's while a `direct` task is open, and nothing
otherwise. `rolling-state-guard` on PreToolUse for the reading and
editing tools and Bash: denies a path under the learner's directory,
and a Bash command naming that directory, `ROLLING_DATA`, or a
`rolling-` executable, in a session that is not the tutor's while a
`direct` task is open, with a reason that says the directory is the
tutor's. The ask-before-destructive hook lands in P2 and is
already there when this opens. `rolling-guard` loses its `write`-only
condition. `docs/profile.md` gets the log's format. Branch
`p5.3/hooks`; depends on 5.2. Done when the handlers' tests drive
them with hand-built events (the tutor's session, a coding session,
subagent events with `agent_id`, a task in each mode and none, paths
spelled every way the write guard already handles), the two 5.3 rows
of the mechanism table are filled in from the runner (a Read of the
learner's directory from the coding session denied; an ordinary
`pnpm` command in the coding session unaffected), and a log written by a
real second session has a prompt, an edit, a command, and a reply.

---

### 5.4 — `direct` tasks and the watch [PENDING]

`task` builds a `direct` task: a `## Situation` body, the same
sources, the same proof; `next` stops skipping `direct` lessons.
`lesson` presents a `direct` task as the situation plus the
instruction to open a second session in this directory and direct it,
says up front that the tutor is watching and will speak only when
there is something worth a word, arms the Monitor over `rolling-watch`
for the maximum window and re-arms at the expiry notice, and holds the
short list of things worth saying; each said once, as an offer, and
noted as an **Intervention**. `rolling-show sessions` renders every log
for the open task for the tutor to read, and a restarted tutor reads it
before arming the watch again. Where Monitor is unavailable, `lesson`
says so and the watch is skipped. Branch `p5.4/direct-tasks`; depends
on 5.3. Done when `rolling-watch`'s filter has tests, the two 5.4
rows of the mechanism table are filled in from the runner, and one
`direct` task on the Rallly clone (`poll-lifecycle`, built from a
situation the lesson names) is presented with the watch armed and the
tutor holding an empty turn through an ordinary prompt-and-reply in the
second session.

---

### 5.5 — `direct` `done` [PENDING]

The human's ledger, in the register the learner drives. `done` with a
`direct` task open: the verifier first, as now; then its findings come
off the learner's ledger in so many words (a type error, a lint
failure, a failing test are the checks' job, and the only thing on the
ledger about them is whether the checks were asked for); then the
session, read from `rolling-show sessions` turn by turn, and what the
tutor noticed, once, located in the log and in the change: where the
direction was actionable and scoped, where the agent drifted and
whether they steered, what they sent back, what they accepted that a
maintainer here would have bounced, read against the map's list of
mistakes agents make here. A held test's failure against a valid
alternative is said to be the test's shape. Interventions the tutor
made stay on the tutor's ledger and are said so. The learner closes.
Branch `p5.5/direct-done`; depends on 5.4. Done when the evidence
entry shape for a `direct` lesson is in `docs/profile.md` and one
`done` on a real session log on the Rallly clone leads with the
verifier, separates the ledgers, cites the log, and closes on the
learner's word.

---

### 5.6 — The runner's second window, and the output-style check [PENDING]

`runner/run.sh code <clone>`: a plain `claude` in the running
container, no plugin flag, the way a learner would open a second
session. And the exit criterion's check, as a script in the handoff
harness's shape rather than a `claude plugin eval` (P2 brings those):
set an output style in the clone's project settings, start a second
session, ask it something plain, and record what it did with the style
and whether anything of the tutor's reached it. Branch `p5.6/runner`;
depends on 5.2. Done when `code` opens a session whose id differs
from the tutor's and whose hooks write a log while a `direct` task is
open, and the check's result is recorded here, whatever it says.

---

### 5.7 — The exit run, and closure [PENDING]

Run the checkpoint's exit criterion honestly and close it out. Branch
`p5.7/closure`; depends on 5.2 through 5.6. Done when one `direct`
lesson has run end to end on the Rallly clone with the maintainer as
the learner: walkthrough, offer, situation, a second session directed
over several turns with the watch armed, the tutor quit and restarted
part-way and still the tutor, `done` with the ledgers separated, the
learner closing; the coding session's log shows a Read of the
learner's directory denied and nothing of the tutor's readable; the
output-style check's result is recorded; the transcripts of both
sessions are read for the failure modes the plan names (the tutor as
noise, the tutor grading the learner on what tests catch, a catch the
tutor prompted credited to the learner, the fourth wall); the
retrospective is appended here in the register the P1a one set,
`CLAUDE.md` § Status and `docs/plan.md` § 7 are updated, and every
mechanism row above is filled in.

## Explicitly deferred

- **Anything on the 1.0 track**: done before this opens.
- **`escalate`, `second-opinion`, the citation check, detours with the
  depth cap, evals, and whether `ask` is needed**: P2. The output-style
  check in 5.6 is a script, and P2 turns it and the properties named
  here into `claude plugin eval` cases.
- **A guard for the walkthrough's write window.** The tutor holds Edit
  and Write while a lesson is open with no task, and the write guard
  keys on a task's scope. Denying all edits in that state would also
  deny the `task` skill the seam test it authors before a task exists,
  so the shape is not obvious; it is prose for now and P2's eval
  measures it alongside the Bash-level scope rule.
- **A script-proof session stamp.** P1a's decision stands: the stamp is
  script-written and a shell can rewrite it. 5.2 closes the one route
  a model could take by accident (a model-invocable skill claiming);
  P2 measures the rest.
- **Cancel versus pause** (#20).
- **`permissions.ask` rules and the toolkit's allow rules in the
  author's committed settings**: written by `rolling-author:init` in
  P3, described in `docs/plan.md` § 3 and the map spec now.
- **The runner this plan names** (`runner/run.sh code`, the container
  the mechanism rows were probed in) was retired in P1b (1b.4;
  `docs/plan.md` § 10, 2026-09-21). The coding session is an ordinary
  `claude` in the clone, however the maintainer runs Rallly, and 5.6
  is a script beside the maintainer's environment, not a runner
  command.
- **The review bot's silent patterns** are process, not product: the
  read-only template, the missing `Skill` grant, and a stacked PR whose
  workflow file lags `main`'s all end in a green check and no review.
  All three are fixed or known; `docs/workflow.md` should say to check
  that a review posted, which 5.7 does with the rest of the closure.

## Verification

- The plan's exit criterion for P1b: one `direct` lesson end to end on
  Rallly, walkthrough and offer included, the tutor restarted
  mid-lesson and reclaiming the role; nothing the tutor holds readable
  from the coding session; an eval that sets an odd output style in
  the directory and checks what the coding session does with it.
- The gate is green on `main`; every hook handler has tests that drive
  it with hand-built events for both sessions and every mode.
- Every mechanism in the table above has a recorded result, and none
  of them is "no" without a plan change that says how.
- The transcripts of the exit run's two sessions, read for the failure
  modes named in 5.7, are clean or their findings are fixed and
  recorded.
