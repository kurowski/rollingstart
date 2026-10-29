# P3: The author's plugin

> The plan's entry is [`docs/plan.md`](../plan.md) § 7, P3. This
> file is the tracker for the checkpoint. Each PR flips its own
> sub-scope from `[PENDING]` to `[COMPLETE]`. When the whole checkpoint
> ends, a retrospective is appended.

## Context

P1a delivered the `write` loop as a plugin, P1b the two homes a map can
have, and P2 the first instrument: 24 cases on a harness of our own,
which tells us whether the tutor follows its own rules. Three maps
exist — Rallly's in this repository, Homie's in its own tree, and a
third privately — each drafted with an agent's help and then edited by
hand. Nothing has ever measured whether a map *teaches*. A lesson whose
brief is ambiguous, whose pointers do not carry their weight, or whose
exercise proves nothing is invisible to every check this project has:
`rolling-check-map` reads structure, the both-ways proof reads a task's
commands, and P2's suite reads the tutor. None of them reads the
lesson.

That gap reshapes what § 7 said this checkpoint was. It listed four
skills — `init`, `mine`, `verify`, `proposals` — and two of them go:

- **`proposals` is dropped.** It reads escalations and the detours
  several learners needed. `escalate` is not a feature this tool
  should have: a learner who wants to ask a human has a dozen easier
  ways, and the store-and-forward machinery to carry a trace to one is
  well outside what Rolling Start does (the maintainer, 2026-10-21).
  With that input gone, `proposals` has one left, and it needs a
  learner population that does not exist.
- **`verify` as § 7 described it is a second copy of something that
  already runs.** "Proves tasks solvable both ways" is what
  `rolling-verify` does per task when a learner begins it, hardened
  through #14, #31, #32, #33 and 2.9–2.10. An author-side batch prover
  adds a driver over code that already fires at the only moment the
  answer matters.

So `verify` becomes the **shakedown**: the map is run with a learner
persona, and the author is told what a learner would hit — where the
brief was ambiguous, which pointers led nowhere useful, what the
persona's background left them stuck on, which exercise could be
satisfied without learning anything. A report the author rules on,
never a verdict. The deterministic reading stays where it already is,
in `rolling-check-map`; what is new is the subjective one, which is
the only kind that can judge teaching.

Two of P2's lessons set the register for the rest. The first is the
maintainer's at its close: the framework is about ten times as
complicated as it should be, because coding agents over-specify. So
#60's simplification pass opens this checkpoint rather than trailing
it, and P3 adds the least shipped surface of any checkpoint so far —
two prose skills, and an instrument that ships to nobody. The second
corrects the first where they look alike: what #60 is about is surface
the learner's loop carries, and what the shakedown removes is the
author's labour. An author who has written a map's lessons will not
hand-run them, and paying an agent to is far cheaper than a human
doing it slowly. Mechanism that serves a rule is suspect; mechanism
that removes human toil is the product.

End state: an author points `init` at a repository and gets a draft map
to edit rather than a blank page, `mine` turns its history into task
candidates and the list of mistakes agents make in it, and a shakedown
tells them which of their lessons would actually teach somebody — on
evidence from a learner who never saw the answer. A map's weak lesson
is found before a learner finds it.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| P3 is `init`, `mine`, and the shakedown | Three pieces of work, not four. `proposals` dropped; `escalate` (#37) closed, not deferred | § 7's list was written before P2 ran. Two of its four rested on a learner population and an escalation record that do not exist, and the maintainer's ruling on 2026-10-21 retires the feature they depended on. A closed issue carrying the reason stops the next reader reviving it from the backlog. |
| `verify` becomes `shakedown`, and it is a reading rather than a proof | The author's instrument runs a map's lessons with a learner persona and reports; no batch both-ways driver is built | The proof already runs per task at the moment it matters. The name `verify` carries exactly the deterministic connotation that caused the most re-litigation in this project's history: Rolling Start is a flexible tutor, not a quiz, and verification here is a light-touch operation. `shakedown` is the run you do before the race, which is what this is. |
| The shakedown is batched, not driven by hand | A run covers a map's lessons across several personas, unattended, and hands back a report | The author has already done the expensive work in writing the lessons; asking them to sit through each one is the worst job in the project. An agent's turns are cheaper than a human's hours, and the comparison is not close. |
| The learner persona is its own `claude -p` process | A second process per conversation, with its own throwaway config, no `--plugin-dir`, no `ROLLING_DATA`, no map, no clone of the reference. The harness passes it only what the tutor said | Isolation becomes structural instead of instructional. A subagent inside the tutor's session could be told not to look at the reference patch and the held tests; a process that never had them in context cannot. The alternative — the author scripting the learner's lines — is tedious and error-prone, and it was the slowest part of P2's cases to get right. |
| The persona runs on a weaker model than the tutor | Tutor on the strong model, persona on a cheap one, and the pairing is a parameter of the run | A learner who is confused is the point, so a less capable persona is the more faithful one, not a compromise. It also keeps a conversation's cost near the tutor's turns alone, since a persona turn carries no plugin, no skill files and a short context. |
| P2's scripted cases stay scripted | The persona driver is the author's instrument; the 24 cases keep fixed learner lines | A persona that improvises makes a run non-reproducible. For a report a human rules on that is fine; for grading the tutor it would destroy the thing that makes the suite a regression test. Two uses of one harness, with different determinism requirements, said out loud so neither is "upgraded" into the other. |
| The shakedown's report has no verdict | Prose per lesson, ordered by what looks worst, with the transcript behind each claim. No pass, no fail, no score, no threshold | P2 learned that a judge asked to police a list of negatives keeps finding new members of it, and that the same transcripts read as evidence for a design question were the cheapest instrument the checkpoint had. The author owns the map; the report's job is to hand them what a learner hit, not to grade their judgment. The first threshold anyone adds turns this back into the quiz we are avoiding. |
| The shakedown lives in `evals/`; `rolling-author` ships `init` and `mine` | No skill in the plugin fronting the harness | The harness is already portable: nothing in `evals/` hardcodes this repository, this machine, or a target, and it needs only `claude` on PATH, Python 3.9's standard library, and a token from `claude setup-token`. Its one coupling is `runner.py:77`, which finds the plugin by walking up from its own path, so it must sit beside `plugins/rolling`. A third-party author can clone a public repository and run it. A thin skill over a harness would be surface in the shipped plugin buying nothing. |
| `init`'s test is a discarded map, regenerated — both of them | Throw away Homie's map and Rallly's in turn, draft each again with `init`, and diff the draft against the hand-written one. Homie's is the measurement; Rallly's is the coverage | A discarded map gives the test a ground truth no fresh target can, and says exactly how much an author would have had to edit. The two answer different questions. The maintainer owns Homie, so a draft's accuracy there is judged exactly; they do not own Rallly, and read it to write that map. And Homie declares four `go` commands with no operations and no destructive list, so it reaches neither the operations half of a draft nor the `permissions.ask` rules — only Rallly, with six operations and three destructive, tests those. |
| The simplification pass opens the checkpoint | #60 is 3.2, before any new surface lands; #56 rides along as 3.3 | P2's retrospective put #59 and #60 before P3 starts, and #59 is closed. The four candidates on #60 are all in `plugins/rolling/`, which the new plugin shares by calling its `bin/`: simplifying before adding is cheaper than after, and a removal that lands after the thing built on it has to be unpicked twice. |

A decision that would have to be re-derived if forgotten also goes to
`docs/plan.md` § 10, dated, when the checkpoint ends.

## Mechanisms to confirm first

Each is confirmed in a scratch setup under the session's scratchpad by
the sub-scope named, before it builds on it, and the result recorded
here.

| Mechanism | Sub-scope | Result |
|---|---|---|
| A `claude -p` process with no tools at all answers in a learner's voice from a persona brief and a transcript, rather than refusing, asking to use a tool, or narrating that it is role-playing | 3.5 | *pending* |
| `claude -p` takes two `--plugin-dir` flags, so a case can load `rolling` and a map plugin together | 3.4 | *pending* |
| A target clone can be stood up cheaply enough to be worth doing per run: Homie's Go tree against a warm module cache, against the few seconds the synthetic fixture takes. Rallly's checks want a 2.6 GB `node_modules` and a database, so its cases point at a prepared clone rather than a fresh one | 3.4 | *pending* |
| A map plugin's SessionStart registration hook fires in a throwaway `CLAUDE_CONFIG_DIR` and writes its root where `rolling`'s resolver scans, so a plugin map resolves inside a harness run at all | 3.4 | *pending* |
| A second plugin's skills (`rolling-author`'s) run in print mode under `--plugin-dir`, as `rolling`'s do (2.2, 2.3) | 3.6 | *pending* |

## Sub-scopes

A sub-scope is a paragraph: goal, branch, dependencies, and a
done-when a reviewer can check in a line or three. Detail lives in the
artifact it describes (a spec, a script's header comment, a skill,
an eval case), and the sub-scope points at it once it exists.

### 3.1 — The plan [COMPLETE]

This file. Branch `p3.1/plan`; depends on nothing. Done when: the
checkpoint's shape is decided and written, the two dropped skills have
their reasons recorded, #37 is closed with the maintainer's ruling
quoted, and `docs/plan.md` § 7's P3 entry is rewritten to match what
this plan says rather than what was drafted before P2 ran.
Done: this file, § 7's entry rewritten, the `escalate` surface
retired across § 1, § 2, § 3 and `docs/profile.md`, and two
decisions in § 10 under *Planning P3*. PR #63.

---

### 3.2 — The simplification pass [COMPLETE]

Close #60's four candidates. Branch `p3.2/simplify`; depends on
nothing. Done when: the shared skill rules live in one place or the
duplication is ruled to stay, with the reason; the `cat -n` cause
reads in `reply.py`'s block message rather than only in `done`'s
prose; the detour and step shapes are stated once or the three copies
are ruled necessary; `only_markers` and its four tests are gone from
`evals/harness/graders.py`; and the suite's affected cases pass
afterwards. Removing mechanism needs no justifying defect here; adding
any needs one.
Done: `only_markers` is gone with its test and its row in the wiring
table — one method and one row, where the done-when above says four
tests; the `cat -n` cause now reads in `reply.py`'s block message,
with `done`'s clause down to one line and a test pinning the cause
into the message; and both placement questions are ruled to stay,
with the reasons in `docs/plan.md` § 10 under *P3.2*. The run behind
the shortened clause: `evals/run --case citations-land`, 2026-10-29,
3/3 on `claude-opus-5-5`, six sessions for $0.94, every grader of the
case green in every run — "every citation lands" among them, so the
hook never had to fire and the tutor's numbers came from readings of
single files, which is the behaviour the clause P2 bought was there
to hold. PR #64.

---

### 3.3 — The held copy keeps its mode [PENDING]

Close #56. Branch `p3.3/held-mode`; depends on nothing. Done when: the
held copy is written with the mode git recorded (`tasks.py:100`, the
mode from `git ls-tree`), a test covers a `100755` held file with a
`held-verify` line whose declared command *is* the file, and the
prose that misattributed it — `task`'s "fix the line or pick another
source", `done`'s reading of it as the environment's — no longer
describes a state the toolkit causes.

---

### 3.4 — A real clone and a real map as the subject [PENDING]

Let a case name a target repository and a map instead of the synthetic
fixture. Branch `p3.4/real-subject`; depends on 3.2. The mechanisms
above marked 3.4 are confirmed first. Done when: the harness's subject
is pluggable, with the synthetic fixture one implementation and "this
clone at this pin, with this map" the other; the per-task facts a seed
needs (the fix's sha, the held test's path) come from the map's own
task files rather than from the builder; one existing case runs
unchanged against the synthetic fixture, so P2's suite is untouched;
both homes a map can have are proved, since the subject is where
they differ: one lesson of the Rallly map served from a clone at
`f61c09708` whose origin is set to the URL the plugin declares —
`mapsource.py` matches `metadata.rolling.repo` against the
repository's origin normalised to host/owner/name, and a local clone
matches nothing — and one lesson of Homie's in-tree map served from a
clone of its `origin/main`, where `.rolling/` wins and nothing is
resolved at all; each transcript read; and the runner's header comment
carries the subject's contract. `could-not-run-is-theirs` gains the
second learner line P2 deferred here, so the `COULD-NOT-RUN` path's
**Feedback** entry is graded rather than ending the conversation
before it is due.

---

### 3.5 — The persona, and the shakedown's report [PENDING]

The instrument. Branch `p3.5/shakedown`; depends on 3.4. Done when: a
persona is a brief (a background, a destination, what they have done
before) and a model, and the harness drives a conversation between the
tutor's session and a persona process that has no plugin, no map, no
learner directory and no reference; the conversation ends on the
lesson closing, the persona giving up, or a turn cap, and says which;
the report names, per lesson and per persona, what the learner hit,
with the transcript kept behind each claim and no verdict anywhere in
it; the driver's own logic has unit tests the gate runs, with the two
`claude -p` calls stubbed; and the persona's isolation is shown from
the run's record rather than asserted — its process's environment and
arguments are in the kept evidence, and they carry neither
`--plugin-dir` nor `ROLLING_DATA`. One lesson against one persona is
measured for cost and quoted here before any full-map run is
authorised: P2's exit criterion was a $25 line item written without
anyone pricing it, and a shakedown of six lessons across three
personas is the same shape of bill. The full-map runs are on Homie,
whose four `go` commands need no services and no install, so a
lesson's checks actually run; Rallly gets single-lesson spot checks
instead, because its checks want the 2.6 GB install and a database
and a distorted run teaches nothing about the map.

---

### 3.6 — `init`, and the author's plugin [PENDING]

`rolling-author` exists and drafts a map. Branch `p3.6/init`; depends
on 3.5, which is how the draft is judged. The mechanism above marked
3.6 is confirmed first. Done when: `plugins/rolling-author/` validates
`--strict` and declares its dependency on `rolling`; `init` drafts
`map.md` and a lesson file per candidate lesson — regions from the
module structure and the history, candidate lessons at each depth,
corpus pointers, operations from the repository's own scripts and
contributing guide, the environment's shape — and the draft passes
`rolling-check-map`; `init` writes the `permissions.ask` rules for the
map's destructive operations into the project's `.claude/settings.json`
(P2's deferred list, the first layer of § 5's destructive row); the
skill is invoked by the author and never model-invoked; and both maps
are discarded, redrafted and diffed against the hand-written ones,
with the diffs read and written up here — what `init` got, what it
missed, and what an author would still have to write. Homie's diff is
the measurement, because the maintainer owns that codebase and can
judge a draft's accuracy exactly. Rallly's is the coverage Homie
cannot give: Homie declares no operations and no destructive list, so
the `permissions.ask` rules above are unreachable there.

---

### 3.7 — `mine`, history into task candidates [PENDING]

Branch `p3.7/mine`; depends on 3.6. Done when: `mine` turns bugfix
commits and merged pull requests into task candidates for an existing
map's lessons — each with the commit it came from, so the author can
read the real fix — and grows the map's "Mistakes agents make here"
from the repository's own review history; a candidate is a draft the
author edits or discards, never written into the map unasked; and the
candidates it drafts for Rallly are checked against that repository at
its pin, with any task it proposes that no starting state could run
reported here rather than quietly dropped.

---

### 3.8 — The exit run, and closure [PENDING]

Branch `p3.8/closure`; depends on everything above. Done when: the
Verification section below is run honestly and its results are written
into this file; a retrospective is appended per `docs/workflow.md`
(planned against delivered, the exit run as it went, decisions made on
the way, what went wrong with PR numbers, what was deferred and
where); the decisions worth keeping are in `docs/plan.md` § 10, dated;
P3 is ticked in `CLAUDE.md` § Status and marked done in § 7 the way P2
is; and P4's entry is read for what this checkpoint changed about it.
The minor bump is asked about once, here.

## Explicitly deferred

- **`proposals`**: dropped, not deferred. Its inputs do not exist and
  one of them never will.
- **`escalate`** (#37): closed in 3.1, with the reason. The surface
  planned for it goes with it: § 1's bullet making escalation a
  feature, § 2's `/rolling:escalate`, § 3's `escalate/SKILL.md` and
  `escalations/`, and `docs/profile.md`'s `escalations/<stamp>.md`.
  The closed checkpoints' records keep it where they deferred it:
  P2 did defer it, and rewriting that to agree with a later ruling
  would erase when the decision was actually made.
- **`adopt`**: 2.0, as decided (`docs/plan.md` § 10, 2026-09-21).
  Nothing here changes the argument.
- **A route to a lesson the learner names** (#57): still open. It is
  spec, and the cheapest shape is probably a slug argument to `lesson`
  rather than a skill of its own, but that is the maintainer's call
  and nothing in P3 is blocked on it.
- **An eval harness an author installs rather than clones**: not a
  capability gap. Once 3.4 lands, an author clones a public repository
  and runs it; what is missing is ergonomics, and "clone the tutor's
  source and run its test suite" is a packaging and documentation
  question for P4's release, not a design hole.
- **The shakedown as a gate**: never. It has no verdict by
  construction, and a threshold added later is the change that would
  turn this tool into the quiz it is not.
- **A batched shakedown of the private map**: the maintainer's to run
  locally if they want it; its results are not this repository's.
- **A new target**: Rallly and Homie carry P3. Oxide's `dropshot`,
  `v-api` or `omicron` would be the first Rust target and the third
  toolchain after Node and Go, and are of interest for later rather
  than needed here — a discarded map beats a fresh repository as a
  test of `init`, because it comes with the answer.
- **`second-opinion`** (#38), **cancel versus pause** (#20), **voices**
  (#17): backlog, untouched.
- **Everything in `direct` mode**: P5.

## Verification

- The plan's exit criterion for P3: an author gets from clone to a
  reviewable draft map in an afternoon, and edits rather than writes.
  Measured by 3.6's diff against the hand-written Homie map, with the
  editing that remained described rather than scored, and Rallly's
  diff read beside it for what Homie cannot reach.
- A shakedown of Homie's map surfaces at least one thing the
  maintainer then changed in it, with one lesson of Rallly's spot
  checked beside it. Both maps have been served to real learners
  since P1b, so an instrument that finds nothing in one of them has
  not earned its place, and the honest place to learn that is here.
- The persona never had the answer: for every conversation in the exit
  run, the kept evidence shows the persona's process carried no
  `--plugin-dir`, no `ROLLING_DATA`, and no path into the map or the
  reference.
- P2's 24 cases still pass on the synthetic fixture, unchanged by
  3.4's pluggable subject, on one model at `--runs 1` as a regression
  check rather than a full exit suite.
- The gate is green on `main`: byte-compile, both test suites,
  `claude plugin validate --strict` for the marketplace and all three
  plugins, `rolling-check-map`, and CI's `versions` job with
  `rolling-author` in the tree.
- `grep` finds nothing of any target's under `plugins/rolling/` or
  `plugins/rolling-author/`: no path, no domain, no framework or tool
  a target is built on. A command or a framework named as a generic
  example is not that (`CLAUDE.md` § Rules, `docs/plan.md` § 10,
  2026-10-21).
- Every mechanism above has a recorded result, and none of them is
  "no" without a plan change that says how.
- The cost of the exit run is estimated from a measured one-lesson
  pass before it is authorised, and both numbers are recorded in the
  retrospective.
- Issues #56 and #60 are closed by the PRs named above; #37 is closed
  by 3.1.
