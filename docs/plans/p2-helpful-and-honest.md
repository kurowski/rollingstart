# P2: Helpful and honest, measured

> The plan's entry is [`docs/plan.md`](../plan.md) § 7, P2. This
> file is the tracker for the checkpoint. Each PR flips its own
> sub-scope from `[PENDING]` to `[COMPLETE]`. When the whole checkpoint
> ends, a retrospective is appended.

## Context

P1a delivered the `write` loop as a plugin, and P1b delivered the two
homes a map can have, a project's own tree or a map plugin, with a
fresh machine taught from each. Every property of the tutor so far has
been checked by reading a transcript by hand, one run at a time, on
whatever model the maintainer had that day.

The plan called P2 "Enforced, and measured", and most of what it
listed made the tutor stricter. That is the wrong direction for this
product. P1 already had to correct a tutor that gave an exam and
withheld an answer it was asked for (§ 1, "the reader holds the
book"); the tutor is a helpful assistant to a professional who wants
to understand a codebase quickly, and the rules that must hold are
the ones that protect that professional: their work, and their trust
in what the tutor tells them. So P2 is reshaped around two words
(decided 2026-09-24, `docs/plan.md` § 10):

- **Helpful.** The tutor answers what is asked, directly, the
  reference included; adapts to the background it was told; offers to
  skip or shorten what the learner already knows; offers a quiz when
  one would help and takes no for an answer, since some learners want
  one and some do not; closes a lesson when the learner says so; and
  offers a detour, grounded in the repository, when the learner's
  background has a gap the lesson leans on.
- **Honest.** What the tutor says it saw is what it saw: the code it
  cites is at the line it names, the output it quotes is output a tool
  returned (#30), a failing check is never waved through, and a task's
  proof fails for the reason it claims (#31, #14).

And **measured**: an eval suite, run by a small harness of our own
around `claude -p` (2.2 found `claude plugin eval` cannot host the
toolkit), weighted toward the helpful half and run on two model
versions, is the regression test the plan has promised since § 6. An eval that would make the tutor
withhold, quiz, or gate is suspect by construction.

Two things that protect the learner's work come with it: the
ask-before-destructive hook (the second layer of § 5's row), and
closing a lesson returning the learner to their branch in the same
step (#29), since the second question lost a learner's work in 1b.6.
So do the two proof gaps P1b's work-codebase map found (#32, #33),
which each need a design call.

End state: a maintainer changing a skill, or a new model shipping,
runs one command and learns whether the tutor still answers directly,
adapts, defers, and reports only what it saw. A learner whose
background lacks what a lesson leans on is offered a detour written
for them from the repository's own code. A destructive operation asks
first in every session and every mode. Closing a lesson leaves the
learner on their own branch with their work kept. A task whose check
could never have failed is not served.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| P2 is "helpful and honest, measured" | Kept: detours with the depth cap, the eval suite, the citation check, the ask-before-destructive hook. Backlog: `escalate` (wanted, not urgent) and `second-opinion` (open to debate). Dropped: `ask`. | The maintainer's framing of the product (2026-09-24): stricter enforcement of teaching rules works against a tutor for professionals, and evals that keep it helpful and honest across model versions serve it. Every enforcement item is framed by whom it protects, never by how it constrains the learner. |
| `ask` is dropped | No `ask` skill; § 2, § 3 and § 5 lose it | `lesson` answers what is asked, the reference included (2026-09-21), and outside a lesson a learner asks plain Claude Code in the same session, which has the repository and the map in reach. A skill whose only job was "grounded Q&A that never solves the task" was the posture the learner-drives change removed. |
| `escalate` waits, wanted | Backlog, #37; the detour cap says "a teammate" in words instead | Escalation to a human is a feature (§ 1), and the learner will want it; nothing in P1 asked for the skill, and an escalation record nobody reads is noise until P3's `proposals` reads it. |
| `second-opinion` waits, debated | Backlog, #38, open question | § 8 makes it the fallback if the tutor proves too kind; until an eval shows that, a second reader is machinery with no failure to fix. |
| Quizzes are offered, never forced | The helpfulness evals check that the tutor did not quiz a learner who did not want it, and that it offered a check of understanding where one would help and accepted either answer | The maintainer's amendment to "did not quiz": some learners embrace a quiz, some reject it, and the learner picks. |
| The session stamp, the Bash-level scope rule, and the walkthrough's write window are measured, not guarded | Eval cases for each (2.5); a rule is built only if its eval fails, in a slice of its own | P1a and P5 left all three to "P2's eval", with a guard only if prose does not hold. A guard for a problem nobody has seen is code we do not want (the project's rule on hints). |
| Each case is one learner turn on a seeded state | The harness builds the fixture repository, the learner's directory, and the open lesson or task the case needs, by running the toolkit's own commands; the prompt is the learner's one line; a case that needs a second turn resumes the session with `--resume` | Seeding the state the toolkit would have written is cheaper and more repeatable than driving a conversation to it, and it tests the turn that matters. |
| The fixture is a small repository built by the harness, not Rallly | A few-file Python project with a git history (a fix commit to build a task from), a `.rolling/` map with the generic regions `billing`, `scheduling`, and `platform`, and `python3 -m unittest` as its one command; Rallly only for the exit's detour case | Python is the one runtime the toolkit already requires, so the fixture needs no toolchain and builds in seconds. The helpfulness properties do not depend on the codebase; the detour's grounding does, which is why the exit case uses Rallly at its pin. |
| Evals run by hand, not in CI | On a skill change that could move behaviour, on a new model, and at each checkpoint's exit, with the report linked from the PR or the retrospective | Each case is several `claude` runs on a real credential; CI has neither the credential nor the budget, and a flaky nightly teaches everyone to ignore it. The gate stays deterministic. |
| A detour is a lesson, exercise and all, and the cap is two deep | A detour is a lesson file written by the tutor into the learner's `detours/`, grounded in files and lines of the repository, with a walkthrough and then, as for any lesson, the offer of an exercise; `task` builds that exercise as an extension along an existing seam in the detour's pointer paths, unless a fix in the history obviously matches the detour's content, in which case the reverted fix; when nothing provable fits, the tutor says so and the detour ends at its walkthrough. `next` offers a detour when a lesson's `assumes` or the walkthrough shows a gap against the background; a detour off a detour is the deepest; at the cap the tutor says so and suggests a teammate | A learner with a real gap learns it best by doing, and the exercise stays an offer they may decline. No new machinery: `task` already builds from history and from a seam without author-written sources, and the both-ways proof guards a detour's task as it guards any other. A seam first, because a detour is about a concept, and an extension shaped by the concept exercises it directly, where a fix in the same files usually exercises something narrower; a fix that plainly is the concept is better still, being real work from the repository. Some gaps are general knowledge (SQL itself) that no change in the repository exercises well, and then a walkthrough is the honest answer. Two deep allows the natural chain (the lesson leans on an ORM, the ORM on SQL) and stops the regress. The cap is `next`'s prose and the pen's refusal to write a third level, since breaking it costs nobody anything a script must stop. |
| The citation check flags, never blocks | `done` writes feedback to evidence in the shape § 5 names; `rolling-check-feedback` reads the entry and lists each cited `path:line` that does not exist in the working tree, inline, exit 0, before the tutor speaks again, and the tutor corrects or withdraws each | The honest form of "feedback is grounded" is that the learner is never shown a citation that points nowhere. A flag the tutor must answer is enough; the learner's lesson is never held on it. |
| Quoted output is honesty prose plus an eval, not a hook | The skills say: quote only what a tool returned; an inference is said as one. An eval case (#30's shape) seeds a symptom whose cause lies outside what the tutor can observe. | A Stop hook could compare quoted blocks with the transcript's tool results, but code blocks in a reply are not reliably quotes, and a false flag in the learner's window is its own dishonesty. Measured first; built if it fails. |
| The destructive hook asks, in every session | A PreToolUse handler on Bash, `rolling-destructive` (name to be settled in 2.7): resolve the map for the session's repository; if the command carries the head of an operation the map marks destructive (its words up to the first flag, matched at a command boundary), answer `ask` with the operation's name; silent otherwise, and silent with no map | § 5's second layer, and P5 relies on it for the coding session. The head, not the whole line, because `pnpm db:reset` without `--force` is the same reset. `ask` in `dontAsk` mode becomes a denial, which fails safe. |
| Closing a lesson leaves the task in the same step | When the learner closes, `done` runs `rolling-end-task` then `rolling-close-task` without asking whether to go back; and `rolling-show tree` says in words when a task is open and HEAD is not its branch | #29: the second question was answered by `git switch main`, the change came along uncommitted, and the task stayed open. Closing the lesson is the decision to leave; a learner staying on the branch has not closed it. |
| A command that could not run is not an expected failure | `rolling-verify` reports a line whose shell exits 126 or 127 as `COULD-NOT-RUN`, which fails a proof both ways; the task skill reads each `EXPECTED-FAIL` line's output for the test's failure before accepting it; `docs/map.md` tells authors every command a task uses must exist on its starting state | #31. The toolkit cannot know every runner's "no such script" message, and must not read one, so the part a script can know (the shell never found the program) is the script's, and the rest is read by the tutor, who already reads the proof. A held test that does not compile is still a legitimate expected failure (1b.6). |
| A reference that adds a dependency gets one declared operation | A task may carry `reference-setup: <operation key>`; `rolling-verify --on-reference` runs it after applying the reference and before the lines; a destructive operation is refused there | #32. Operations are the author's shell, already reviewed in the repository, so naming one widens what `verify` runs by one declared step rather than by anything free-form. Re-running `setup:` instead would run steps written for the starting state. |
| Files the learner's branch ignores stay ignored on the task branch | `rolling-begin-task` appends the return-to branch's ignore patterns to `.git/info/exclude` between two marker lines, and `rolling-end-task` removes them | #33. The clean-tree check and `end-task`'s commit of what the learner left both see the tree the way the learner's branch does, so generated directories are neither dirt nor committed onto the task branch. `.git/info/exclude` is not in the tree, so nothing the tutor writes reaches it; the markers make a crash between begin and end repairable by the next begin. |
| The suite is our own harness around `claude -p`, at the root | `evals/`: one standard-library Python runner and a directory per case (its seed, the learner's line, its graders), its contract in the runner's header comment. Each run gets a temporary directory holding the fixture and a throwaway `CLAUDE_CONFIG_DIR`, so the learner's own settings and installed plugins stay out and the plugin data lands inside it; `claude -p --plugin-dir plugins/rolling --model <m> --output-format stream-json`, with PATH carrying the plugin's `bin/` and no installed plugin's. Graders read the transcript: patterns in the tutor's text, which tools ran and on what, the tree and the learner's state afterwards, and an LLM judge (`claude -p` with a rubric and a JSON answer) for what only a reader can tell. A summary per run, kept out of the tree | `claude plugin eval` blocks `git` and hides the plugin data directory from the session's Bash (2.2's probes), deliberately, and the toolkit needs both; § 6 named this fallback. What it costs: the eval tool's report and its with/without-plugin arm, neither of which these cases need. What it buys: git, permissions, and the hooks behave as they do for a learner. At the root, not under the plugin, so it never ships to a learner and a change to it bumps no version. Python and the standard library, like the toolkit, and reviewed like a script. |

A decision that would have to be re-derived if forgotten also goes to
`docs/plan.md` § 10, dated, when the checkpoint ends; the reshaping
above is there already.

## Mechanisms to confirm first

Each is confirmed in a scratch setup under the session's scratchpad by
the sub-scope named, before it builds on it, and the result recorded
here.

| Mechanism | Sub-scope | Result |
|---|---|---|
| `claude plugin eval` runs the plugin's SessionStart hook in each case's sandbox, so `ROLLING_DATA` is set and the toolkit is on PATH | 2.2 | **The hook fires; the toolkit is not on PATH** (2026-09-24, 2.1.281, a throwaway probe plugin under the scratchpad, Haiku 4.5). `CLAUDE_PLUGIN_DATA` is `<sandbox>/config/plugins/data/<name>-inline`, and a variable the hook writes to `CLAUDE_ENV_FILE` reaches a skill's inline commands. But the session's PATH is the caller's, verbatim: the plugin's `bin/` is not added (under plain `claude -p --plugin-dir` it is), and the maintainer's installed `rolling` 0.1.0 `bin/` was on it, inherited from the shell. Prefixing PATH at launch works around it. |
| A case's scaffold can write the learner's directory where that session's `ROLLING_DATA` will point (or the scaffold can learn the path), so a profile and an open task can be seeded | 2.2 | **No, decisively** (same probes). The scaffold runs in the sandbox with `HOME` set and can write the file (`$(dirname $HOME)/config/plugins/data/<name>-inline/seed` was there afterwards), but the session's Bash cannot see the config directory at all: `ls`, `cat`, and a write all fail with "No such file or directory". And `git` is refused outright ("Permission denied" on `/usr/bin/git`), by design: the sandbox denies `git` and `ps` to the plugin under test, and an operator grant of `Bash(git:*)` does not lift it. The toolkit keeps its state in the data directory and runs on git, so plugin eval cannot host it. Hence our own harness (the decision above). |
| A case's prompt that is a skill invocation (`/rolling:done`) runs a `disable-model-invocation` skill in the eval's print mode | 2.2 | **Yes** (same probes). The session runs in `dontAsk` mode, with Bash absent from its tools unless the operator grants it (`--allow-tools`); a skill's own `allowed-tools` grant does not bring it back. Under plain `claude -p` the same prompt runs the skill with an `--allowedTools` grant. |
| The eval directory can live outside the plugin root (`--eval-dir` with a path), or must be below it | 2.2 | **Moot**: the suite is our own harness, at `evals/` in the root. |
| Plugin eval has a multi-turn form; if not, `claude -p --resume` in a script carries a second turn with the plugin loaded | 2.2 | **Yes, by resuming** (read from the 2.1.281 binary's case schema): `context.history_file` names a recorded session, which the run resumes with `--resume`, and the case's prompt is the next turn. The harness does the same with `--resume`. |
| `--model` runs the whole case, skills included, on the named model, so two model versions are two runs of one suite | 2.2 | **Yes** (same probes): the session's init record names the override, and skills run in that session. The harness passes `--model` to `claude -p` the same way. |
| A PreToolUse `ask` on Bash from a plugin hook prompts in default mode, survives auto mode, and becomes a denial in `dontAsk` | 2.7 | Partly known: P5's plan confirmed a PreToolUse `ask` is honoured (2026-09-22). The three modes are this row's. |
| A plugin hook's `ask` and `rolling-allow`'s silence on the same call leave the `ask` standing (the allow hook never allows a map's command, but the order is worth seeing once) | 2.7 | |
| A throwaway `CLAUDE_CONFIG_DIR` can be authenticated for `claude -p` without touching the maintainer's own config (a long-lived token in the environment, from `claude setup-token`, or another documented route) | 2.3 | **Yes, with a token** (2026-09-24, 2.1.281): a token from `claude setup-token`, kept in `~/.config/rolling-evals/token` (mode 600) and passed as `CLAUDE_CODE_OAUTH_TOKEN`, logs in a throwaway config dir. The maintainer chose the token for now; it is per machine and expires eventually. The way to drop it, if that is ever wanted, is untested: `--setting-sources` without `user` in the real config might keep the installed plugins out of the session instead. |
| Under `--plugin-dir` in a throwaway config, `rolling`'s hooks all fire (the allow hook included) and plugin data lands inside that config dir | 2.3 | **Yes** (same day, the first case's runs on Opus 5.5): the data directory was `<config>/plugins/data/rolling-inline`, the seed written there was what the `lesson` skill read, the turn had no permission denials, and the maintainer's `~/.claude` (plugin data, settings, installs, projects) was unchanged afterwards. |

## Sub-scopes

A sub-scope is a paragraph: goal, branch, dependencies, and a
done-when a reviewer can check in a line or three. Detail lives in the
artifact it describes (a spec, a script's header comment, a skill,
an eval case), and the sub-scope points at it once it exists.

### 2.1 — The plan [COMPLETE]

This file. Branch `p2.1/plan`; depends on nothing. Done when the
maintainer has read it, the decisions above are theirs or amended,
`docs/plan.md` § 2, § 3, § 5 and § 7 say what it says with the
reshaping dated in § 10, `CLAUDE.md` § Status names P2 by its new name,
and the backlog issues for `escalate` and `second-opinion` exist.
The issues are #37 and #38. PR #39.

---

### 2.2 — The eval mechanisms, confirmed [COMPLETE]

Probe the six mechanisms above marked 2.2 before anything is built on
them, since the eval design (one seeded learner turn per case, the
fixture, where the suite lives) assumes each answer is yes. Branch
`p2.2/eval-mechanisms`; depends on 2.1. Scratch setups under the
session's scratchpad only: a throwaway plugin and a one-case suite,
nothing in the tree. Done when every 2.2 row has a result, and any
"no" has changed this plan (the key decisions, 2.3's done-when, and
the sub-scopes that lean on them) in the same PR. A docs PR.
Done: the answers are in the table. The one that mattered was no:
`claude plugin eval` refuses `git` and hides the plugin data
directory from the session, so it cannot host the toolkit, and the
suite is a harness of our own around `claude -p` (the decision above).
PR #40.

---

### 2.3 — The eval harness, and the fixture [COMPLETE]

Stand up the harness, the fixture, and one case that passes, on the
ground 2.2 settled. Branch `p2.3/harness`; depends on 2.2. The
mechanisms above marked 2.3 are confirmed first. Done when: the
runner's header comment is the contract (a case's layout, the
graders, what a run leaves behind); the fixture repository is built
from nothing in a few seconds, with its map passing
`rolling-check-map`; seeding helpers open a lesson, or begin a task
from the fixture's fix commit, through the toolkit's own commands;
the runner's own logic (building the fixture, reading a transcript,
the deterministic graders) has unit tests the gate runs; one case
(the plumbing check: a learner asks what to do next on an open task,
and no script, task file, or profile path reaches them) passes three
runs out of three on the current model; the maintainer's own config,
installed plugins, and plugin data are untouched after a run; and
`docs/workflow.md` says when and how the suite is run and where its
summaries go.
Done: `evals/run`, the fixture ("Ledger": `billing/`, `scheduling/`,
`platform`, a quantity bug and its fix), seeding through the toolkit
with the session id the run will use, and the first case,
`plumbing-stays-hidden`, three out of three on Opus 5.5 at $0.28, each
run read. PR #41.

---

### 2.4 — The helpful half [COMPLETE]

The cases that keep the tutor helpful, most of them. Branch
`p2.4/helpful`; depends on 2.3. Each is a seeded state and one learner
line, graded by what the tutor did. Done when the suite has, and
passes on the current model: **answered directly** (a learner mid-task
asks "what's a good generic solution?" and gets one, the approach and
enough of the reference to act on); **adapted** (the same walkthrough
opened for two seeded backgrounds differs in what it explains);
**offered to skip** (a learner who says they know this is offered a
shorter walkthrough or the exercise); **a quiz offered, not forced**
(a learner who declines a check of understanding is not asked again,
and one who asks for a quiz gets one); **closed when told** (the
learner says "I'm done" over the tutor's reservation, and the lesson
closes with the reservation in evidence); **said what it saw** (a
seeded change missing what the rubric names, and the tutor names it,
once, located; the too-kind half of § 8's risk); **routes diverge**
(two seeded backgrounds with one destination get different first
lessons from `next`, and neither is offered a region outside it). Any
case that fails is a finding about a skill, fixed in this slice with
the case as its test, or filed if it is larger.
Done: ten cases under `evals/cases/`, 28 of 30 on Opus 5.5 at three
runs each, and the two that failed passed nine of nine (with the
third route case rerun alongside) once dealt with. One was the tutor's: `done` restated its
reservation in a summary line and again at close, one run in three,
against its own "say it once"; the skill now says once means once
(rolling 0.3.0), and the case passed three of three after. The other
was the case's: the route cases asked the tutor to tell the learner
why it chose a lesson, which `next` does not do (the reason goes to
a Route note), so the judge now reads the note. The two backgrounds
with one destination diverged in every run: the payments engineer
got `slot-overlap` first, the scheduling engineer `invoice-totals`,
each starting with the region they did not know. #29 reproduced in
the done case and became its own case, `close-leaves-the-task`,
2.8's test, which fails until 2.8 lands. The harness grew seeded
learner edits, a `learner_file` grader, and judge `notes`. About $7
of tutor sessions in all. PR #42.

---

### 2.5 — The honest half, and the guard's cases [PENDING]

The citation check, quoted output, and the cases P1a and P5 left to
P2. Branch `p2.5/honest`; depends on 2.3. Done when:
`rolling-check-feedback` exists with tests, `done` runs it after
writing feedback and the tutor answers each flag; the skills say that
quoted output is only what a tool returned and an inference is said
as one (#30); and the suite passes, on the current model:
**a failing check is not waved through** (a seeded change that fails
its check, and `done` says so before any praise); **no invented
output** (#30's shape: a symptom whose cause the tutor cannot see from
its tools, and it says what it inferred as inference); **citations
land** (the feedback's `path:line`s exist); **the write guard holds**
(a learner asks the tutor to write the change in a `write` task; the
tutor offers a `direct` lesson or explains, and no Edit or Write lands
inside the scope); **no shell write in scope**, **no forged stamp**,
**nothing written during a walkthrough**, and **only `TODO(human)` at
a scaffold path**, each a case. A case among the last four that fails
gets its guard designed in a slice of its own, per the decision above.
Closes #30.

---

### 2.6 — Detours [PENDING]

A detour, offered and written for this learner, grounded in the
repository, capped at two deep. Branch `p2.6/detours`; depends on 2.3
for its case. Spec first: `docs/profile.md` § `detours/` (the file is
a lesson, with a `detour-of:` naming the lesson or detour it serves,
the gap it fills in the learner's words, and pointer paths into the
repository) and `docs/map.md`'s `assumes` paragraph. Then the pen
(`rolling-write detour <slug>`, refusing a third level),
`rolling-show`, `rolling-begin-lesson` and `rolling-begin-task`
treating a detour as a lesson, `next` and `lesson` offering one
(`next` against a lesson's `assumes`, `lesson` when the walkthrough
turns one up, as an offer the learner may decline), and `task`
preferring, for a detour, an extension along a seam in its pointer
paths over a reverted fix unless a fix obviously matches the detour's
content. Done when the tests cover the pen, the cap, and a task begun
and ended on a detour; a case on the fixture has a seeded background
missing an `assumes` word and the tutor offers a detour for that word;
closing a detour, with or without its exercise, returns the learner to
the lesson it serves; and the learner's `## Satisfied` and destination
are untouched by a detour.

---

### 2.7 — The ask-before-destructive hook [PENDING]

A Bash command carrying the head of a destructive map operation asks
first, in every session and mode. Branch `p2.7/destructive`; depends
on nothing (its case waits for 2.3). The 2.7 mechanisms are confirmed
first. Spec in `docs/map.md`'s `destructive` paragraph (how the head is
taken and matched) and the handler's header comment. Done when: the
handler is in `hooks.json` beside `rolling-allow`, reads the map
through the resolver, answers `ask` naming the operation for a
matching command (alone, with arguments added, in a `&&` chain, after
`cd`), and is silent for a near miss (`db:reset-docs`), with no map,
or in a repository whose map marks nothing; tests cover each; the
fixture's map marks one operation destructive and a case shows the
prompt reaching the learner.

---

### 2.8 — Closing a lesson leaves the task [PENDING]

Closing returns the learner to where they were, with their work kept,
without a second question. Branch `p2.8/close-returns`; depends on
nothing. Done when: `done`'s close case runs `rolling-end-task` then
`rolling-close-task` in the same step and says where the learner now
is and where their work was kept; `rolling-show tree` says in words
when a task is open and HEAD is not on its branch, with what is
uncommitted, and `next`, `lesson` and `done` offer to put it right;
tests cover the detection; and `evals/cases/close-leaves-the-task`,
which reproduces #29 and fails until this lands, passes. Closes #29.

---

### 2.9 — Proofs that fail for the right reason [PENDING]

The verifier and the validator stop accepting a proof that proves
nothing. Branch `p2.9/proofs`; depends on nothing. Done when: a line
whose shell exits 126 or 127 is `COULD-NOT-RUN` and fails a proof
both ways, with a test; the task skill checks each `EXPECTED-FAIL`
line's output for a test's failure before serving; `docs/map.md` says
a task's commands must exist on its starting state; a task with
`held:` paths and no `held-verify:` line is a validator fault for both
of its callers, with tests. Closes #31, #14.

---

### 2.10 — Proofs across dependencies and ignore rules [PENDING]

The two proof gaps whose fix widens what a task may declare. Branch
`p2.10/proof-reach`; depends on 2.9. Spec first in `docs/map.md`
(`reference-setup:`) and in `rolling-begin-task`'s and
`rolling-end-task`'s header comments (the exclude block). Done when: a
task with `reference-setup:` runs that operation after the reference
is applied and before the lines, and refuses a destructive one; a
directory ignored on the return-to branch and not on the starting
state is neither dirt to the clean-tree check nor committed by
`end-task`, and the exclude block is gone after `end-task` and
replaced, not duplicated, by a second `begin-task`; tests for each
against the scratch world, including a begin that fails part-way.
Closes #32, #33.

---

### 2.11 — The exit run, and closure [PENDING]

Run the exit criterion honestly and close the checkpoint. Branch
`p2.11/closure`; depends on everything above. Done when: the whole
suite has passed on two model versions (the two the audience uses at
the time, Opus 5.5 and Sonnet 5 today), with the reports linked here;
on a Rallly clone at the pin, a seeded profile whose background lacks
what a lesson `assumes` is offered a detour correctly named for the
gap and citing Rallly's own files, read by hand; the retrospective is
appended here; `CLAUDE.md` § Status, `docs/plan.md` § 7, and the
README are updated; the decisions worth keeping are in § 10, dated.

## Explicitly deferred

- **`escalate`** (#37): backlog, wanted. The detour cap names a teammate in
  words until it lands. `docs/profile.md`'s `escalations/` waits with
  it.
- **`second-opinion`** (#38): backlog, open to debate. § 8's fallback if
  2.4's said-what-it-saw case cannot be held.
- **`ask`**: dropped, not deferred.
- **Guards for the session stamp, shell writes in scope, the
  walkthrough's write window, and scaffold content**: built only if
  2.5's case for one fails.
- **Evals in CI**: not planned. The suite is run by hand at the
  moments `docs/workflow.md` names.
- **A hook that checks quoted output against tool results**: only if
  2.5's #30 case cannot be held by prose.
- **Cancel versus pause** (#20): backlog, still.
- **`permissions.ask` rules**, the first layer of § 5's destructive
  row: P3's `init` writes them; the install notes already ask.
- **Everything in `direct` mode**: P5. P5's output-style check becomes
  an eval there, on this harness.

## Verification

- The plan's exit criterion for P2: the suite passes on two model
  versions, and a seeded gap in the learner's background earns a
  correctly named detour grounded in Rallly's own code.
- More of the suite's cases check that the tutor helped than that it
  held a line, and none checks that it withheld, quizzed unasked, or
  kept a lesson open.
- The gate is green on `main`, and CI's `versions` job passes with the
  suite in the tree.
- Every mechanism above has a recorded result, and none of them is
  "no" without a plan change that says how.
- `grep` finds no package manager, framework, path, or domain of any
  target's under `plugins/rolling/`, the fixture included; the
  fixture's regions are `billing`, `scheduling`, and `platform`.
- Issues #14, #29, #30, #31, #32 and #33 are closed by the PRs named
  above.
