# P1b: Distribution

> The plan's entry is [`docs/plan.md`](../plan.md) § 7, P1b. This
> file is the tracker for the checkpoint. Each PR flips its own
> sub-scope from `[PENDING]` to `[COMPLETE]`. When the whole checkpoint
> ends, a retrospective is appended.

## Context

P1a delivered the learner loop as a plugin for `write` mode against a
map committed in the target repository, and the first fresh learner's
four lessons then reshaped it (PRs #16 to #19, recorded in
[`p1a-write-mode.md`](p1a-write-mode.md) under "After closure"). In
P1a the map is found at `.rolling/` in the repository root and nowhere
else; the Rallly map's source is `examples/rallly/.rolling/`, put into
the clone by `runner/`, a contained harness that exists because the
maintainer kept Node off the host and so had to orchestrate Rallly's
toolchain around the plugin; and the plugin has been installed only
from this repository mounted as a local marketplace.

P1b delivers the second home a map can have. Concretely: the map
plugin, a directory that is the map with a manifest naming the
repository it is for and a one-line hook that registers itself; the
resolver in `rolling` that finds the map for the repository the
session is in, prefers the one in the tree, and warns when a plugin
map was written against a commit the checkout does not have; the
Rallly map repackaged as the `rallly` map plugin, which is the demo and
the external-author route; the Homie map, written straight into
Homie's own tree, which is the internal-author route in public and the
first map for a repository that is not Node; and, before any of that,
the Rallly map's three fixes the first fresh learner's lessons asked
for. The maintainer's work codebase gets its map the same way,
privately; only what it taught the plugin is recorded here. And
`runner/` is retired: once the map is a plugin, installing Rolling
Start into a Rallly clone is `plugin install` like anywhere else, and
how the maintainer runs Rallly's toolchain (in a container, or on the
host after all) is outside this repository's concerns, as the
environment is outside the tutor's.

End state: a learner on a machine that has never seen this repository
clones Rallly, adds the marketplace from GitHub, installs `rolling` and
`rallly`, opens Claude Code, and is taught a lesson with no map in the
tree. A learner on a Homie clone is taught a `write` lesson from the
map in Homie's tree, with `go test` as the verifier. A Rallly clone
that has the plugin installed and a `.rolling/` committed is taught
from the tree, and the plugin is not consulted.

P2 (enforced, and measured) follows. Nothing here assumes it.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| A map plugin is the map directory with a manifest | The plugin root holds `map.md` and `lessons/`, exactly as `.rolling/` does, beside `.claude-plugin/plugin.json`, `hooks/hooks.json`, and a `README.md` with the install notes; no `bin/`, no skills, no agents | Same format, one loader (`Map.load` takes a directory and does not care which). A plugin may have no skills or commands (docs: hooks-only is a valid plugin). A map plugin ships no code, so an author who copies the `rallly` plugin's shape maintains prose and a manifest, nothing else. |
| The declaration is manifest metadata, and the hook writes one line | `plugin.json` carries `"metadata": {"rolling": {"repo": "<pattern>", "commit": "<sha>"}}`; `hooks.json` has one SessionStart command that writes `${CLAUDE_PLUGIN_ROOT}` to `${CLAUDE_PLUGIN_DATA}/root`, in shell, creating the directory first | Claude Code ignores `metadata` and `--strict` accepts it, so the declaration is reviewed where the manifest is and is never parsed by a hook. The hook's only job is to say where the plugin's copy is, which nothing else can (a plugin's cache path carries its version and moves on update); a line of shell that writes a path needs no Python and no review beyond reading it. The declaration's `repo` is a pattern the repository's `origin` URL must match after normalising (scheme, `.git`, credentials stripped): `github.com/lukevella/rallly`, or `*/rallly` for an author who expects forks. `commit` is the sha the map's claims were checked against, the same sha the map's own prose names. An in-tree map declares nothing: the tree it is in is its pin. |
| The resolver is one function with three answers | `paths.resolve_map(top, data)`: the tree's `.rolling/` when it exists; else the registered map plugin whose `repo` matches this repository's remote and whose registered root still exists; else no map, with the registered plugins and their declared repositories listed in the message. Two matches is a refusal naming both. Registrations are the `root` files in the sibling directories of `ROLLING_DATA`, the plugin data root Claude Code keeps at `~/.claude/plugins/data/` | One resolver in one place, as the learner directory has (P1a). `Where.map_dir` is the only thing that changes, so every command, the pen's validators, and the task carry-over see the same answer. A registration whose root is gone (an uninstall with `--keep-data`, a cache purge) is skipped, not an error. Tests build the data root in a temporary directory with the registrations they need. |
| The tree wins, and the resolver says which it chose | `rolling-show map` and `map-check` say where the map came from (`in tree`, or `plugin rallly@rollingstart 0.3.0`) and add a line when a plugin map's declared `commit` is not an ancestor of HEAD | § 3: the tree's map wins, so a project can take an outsider's map into its tree by copying the directory in, and the plugin is simply no longer consulted; that is all adoption needs in 1.0, and the `adopt` skill that would do the copy and stamp its source waits for 2.0 (below). The ancestor check is what "the checkout does not contain the declared commit" means in git; a checkout behind the map's pin gets pointers that describe a future it has not fetched, which is the stale-pointer wart 1a.8 found from the other side. |
| Map plugins carry a version, bumped on every change | `plugin.json` `version`, semver, and a map change is a bump; the marketplace entry carries none | A plugin with a version is pinned to it: the learner keeps the map they installed until `plugin update`, and a lesson in progress does not have its map change under it. A git-sourced plugin without a version would update on every commit of this repository, which is the wrong cadence for content. Docs: set the version in one place only; `plugin.json` is that place. |
| The Rallly map's source moves to the plugin | `examples/rallly/.rolling/` becomes `plugins/rallly/`; `examples/` goes | One source, and it is the thing that ships. A Rallly clone gets the map by `plugin install`; nothing else copies it anywhere. |
| `runner/` is retired | Deleted in 1b.4 with its README, its rows in `CLAUDE.md`, and `spike/README.md`'s pointer to it; the maintainer's harness beside this repository is theirs | It existed to keep Node off the host, which meant orchestrating Rallly's toolchain and services around the plugin from inside this repository. Once the map is a plugin, installing Rolling Start into a Rallly clone is the same `plugin install` as anywhere, and how the maintainer runs Rallly (contained, or on the host after all) is as external to this repository as the environment is to the tutor. What the runner did that still matters is documented where it belongs: a git identity and the toolkit's allow rules are the learner's environment and the install notes say so; the proof of a task is the toolkit's `rolling-verify` by hand until P3's `verify`. |
| Homie's map is in Homie's tree from day one | `.rolling/` committed to `github.com/kurowski/homie` in that repository's own PR, with the `.claude/settings.json` § 3 says an author inside a project commits; nothing of the map in this repository | The maintainer owns Homie, so the lifecycle the plan sketched for it (a plugin here, adopted later) was ceremony: an author inside a project commits the map. Homie is now the internal-author route in public, the same route the work codebase walks in private. Homie assumes no orchestration: a Go toolchain and git, and the map says so. |
| `adopt` and `rolling-author` wait | No `rolling-author` plugin in P1b; it first appears in P3 with `init`. `adopt` (the copy of a plugin map into `.rolling/`, a stamp saying where it came from, a note when the plugin is newer than what the tree adopted) is 2.0, if a project ever asks for it | Adoption in 1.0 is a copy any author can do by hand, because the tree wins. A skill, a stamp, and a staleness note on the stamp are machinery for a lifecycle nobody has started yet, and P1b is simpler without them. The design keeps the skill (`docs/plan.md` § 2, § 3); the plan moves it. |
| The work codebase's map leaves one paragraph here | What the format or the toolkit lacked, generically, and nothing else | `CLAUDE.md`: the maintainer's employer's codebase never appears in this repository. The internal-author route still has to be walked in P1b, since it is the corporate case, and the plugin should learn from it without the record saying what was learned about. |

One decision is the maintainer's, before 1b.7 runs: `/plugin
marketplace add kurowski/rollingstart` needs the repository public and
reachable from a learner's machine at the moment of the exit run; a
private repository can be added with a token, but the demo's point is
that nothing is needed.

A decision that would have to be re-derived if forgotten also goes to
`docs/plan.md` § 10, dated, when the checkpoint ends; the three above
that reshape the plan (the runner retired, Homie in its tree, `adopt`
deferred) are there already, dated 2026-09-21.

## Mechanisms to confirm first

Each is confirmed in a scratch setup (a throwaway plugin directory
registered as a local marketplace under the session's scratchpad, and
a scratch repository), by the sub-scope named, before that sub-scope
builds on it. The result is recorded here.

| Mechanism | Sub-scope | Result |
|---|---|---|
| A plugin with `hooks.json` and no skills installs from a marketplace, its SessionStart hook fires with `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` for its own id, alongside `rolling`'s hook in the same session, and its data directory is a sibling of `rolling`'s under one plugin data root | 1b.3 | **Yes** (2026-09-22, 2.1.278, on the host). A scratch marketplace under the scratchpad with one hooks-only plugin, `scratchmap`, added and installed at user scope beside the installed `rolling`; one `claude -p` in a scratch repository created `~/.claude/plugins/data/scratchmap-scratchmarket/root` holding the plugin's cache path, next to `rolling-rollingstart/`. Under `--plugin-dir` the same plugin registered as `scratchmap-inline`. Uninstalled and the marketplace removed afterwards. |
| The hook's shell command can create `${CLAUDE_PLUGIN_DATA}` (the directory may not exist at the first session start) and the `root` it writes is readable from the Bash tool afterwards | 1b.3 | **Yes** (same probes). The data directory did not exist before the first session; `mkdir -p` in the hook's one line made it, and the `root` file was there for the toolkit to read. In the probe the model's own Bash was refused by the sandbox for expanding a variable, which says nothing about the hook and is why the tests drive the resolver directly. |
| `plugin.json` `metadata` with a nested object passes `claude plugin validate --strict` without a warning | 1b.3 | **Yes** (same probe): `metadata.rolling` with `repo` and `commit`, validated strictly as a plugin and through its marketplace, no warning. |
| A `dependencies: ["rolling"]` entry: what `plugin install rallly@rollingstart` does when `rolling` is not installed (installs it, refuses naming it, or installs `rallly` alone), and what it does when it is | 1b.4 | |
| A bumped `version` in a map plugin's `plugin.json` reaches an installed learner on `plugin update` and not before, under a marketplace added from GitHub | 1b.7 | |
| `/plugin marketplace add kurowski/rollingstart` then `/plugin install rolling@rollingstart` and `rallly@rollingstart` in a fresh Rallly clone on a machine that has never seen this repository: the plugin's `bin/` on PATH, the map resolved, a lesson served | 1b.7 | |

Two assumptions of the toolkit that have only ever been checked under
pnpm, to confirm on Homie in 1b.5 and record in the same table: a held
`_test.go` that does not compile on the starting state (it calls what
the fix adds) is the expected failure `--on-base` wants, since the
exit is non-zero either way; and `go test`'s arguments (`./internal/config/...`,
`-run`, `TestName`) are words the verifier's argument rule accepts.

## Sub-scopes

A sub-scope is a paragraph: goal, branch, dependencies, and a
done-when a reviewer can check in a line or three. Detail lives in the
artifact it describes (a spec, a script's header comment, a skill),
and the sub-scope points at it once it exists.

### 1b.1 — The plan [COMPLETE]

This file. Branch `p1b.1/plan`; depends on nothing. Done when the
maintainer has read it, the decisions above are theirs or amended, and
`docs/plan.md` § 7 and § 10 and `CLAUDE.md` § Status say what it
says. The maintainer's reading moved three things before it opened:
the runner out, Homie's map into Homie's tree, and `adopt` to 2.0.
PR #22.

---

### 1b.2 — The Rallly map after the first fresh learner [COMPLETE]

The three things the plan's P1b entry opens with, all in
`examples/rallly/.rolling/` where the map still lives. The setup
lesson confirms the environment's state rather than asking about it
(each step with the command or file that shows it is done) and its
task's verifier is the subset the lesson names, not the tutor's
choice. `polls` gets an `orientation` lesson, so a destination of
`polls: orientation` reaches something; the poll's shape as a user
sees it and where each part lives, built from the pin, with an
exercise small enough for orientation or `exercise: none` if the
walkthrough is the lesson. `billing-and-tiers` is rewritten as a
`write` lesson with its test held, from the fixes it already names as
situations (`2875e7e4` #3211, `8ccb963f` #3209, `dd4833d3` #3204 with
its `pricing.test.ts` seam), so the Billing engineer course serves a
lesson in 1.0; `stripe-webhook` stays `direct`. The courses say so.
Branch `p1b.2/rallly-map`; depends on nothing. Done when
`rolling-check-map` is green, every new path, line, and sha is read at
`aab791da`, each fix-backed task is proved both ways with the toolkit
in a Rallly clone at the pin (begin from the fix, `--on-base`,
`--on-reference`, end, close, branch deleted; wherever the maintainer
runs Rallly), and a seeded profile with `billing: deep` gets
`billing-and-tiers` from `/rolling:next` rather than the refusal
1a.8's seed 4 got. Done: the setup lesson has a step-by-step list of
what shows each setup step done (the seed's fixed users make a second
`db:seed` refuse, which is the check for "seeded"), names its four
verifier lines as the only ones, and tells the tutor the task is a
shown-test seam beside the setup steps and never a reverted fix; the
first fresh learner's transcript had the tutor choosing its own
verifier, running lint and structure by hand at `done`, and quizzing
on the services. `poll-surfaces` is the polls orientation lesson: the
four screens (`/new`, `/poll/<id>`, `/invite/<id>`, `/polls`), what
each composes, the role rule in `client.tsx`, and what feeds them,
with `exercise: none`. `billing-and-tiers` is `write` with
`pricing.test.ts` held from `dd4833d3`, the brief scoped to the rule in
the pricing package, and the four-PR currency arc as reading;
`typecheck-billing` joins the map's commands for it; the courses say
which lessons are which. Everything was read at `aab791da`, and two
claims written from memory were wrong at the pin and fixed before
the run (the manage menu's items, the event card's contents). Proved
and run on the host, not in the runner: the maintainer put Node 24
and pnpm on the host and installed `rolling` at user scope from this
repository as a local marketplace, so the proof is four toolkit
commands in the clone with scratch state (`--on-base`: the held test
fails on the parent since `getCountryCurrency` does not exist,
`typecheck-billing` and `lint` pass; `--on-reference`: all pass and
the tree comes back clean; under three seconds each). Two seeds
through `/rolling:next` in print mode: billing at `deep` with both
openers satisfied opened `billing-and-tiers` with the route note
saying it is the only reachable billing lesson and the walkthrough
should lean on Stripe; the first fresh learner's destination (polls at
`orientation`) opened `poll-surfaces`, walked it through pacing the
App Router parts for a learner new to them, named nothing of the
tutor's, and ended by saying the lesson has no exercise. PR #23.

---

### 1b.3 — The map-plugin format and the resolver [COMPLETE]

The spec first, then the toolkit. `docs/map.md` gains the map
plugin's shape (the map at the plugin root, the manifest's `metadata.rolling`
declaration, the one-line registration hook, the README's install
notes with the toolkit's allow rules), what a project that commits
its map puts in `.claude/settings.json` (the marketplace, `rolling`
enabled, the same allow rules; § 3's install story, written down once
so Homie and the work codebase can paste it), and what the resolver
does when both homes are present and when the declared commit is
missing. Then `paths.resolve_map`, `Where.map_dir` resolved through
it, `rolling-show map` and `map-check` saying the source and the
warning, and the message for no map naming what is registered.
`_carry_map` removes the branch point's `.rolling/` before carrying the
origin's, when there is one: a project that moved its map into a
plugin still has the old map in its history, and a task cut from
before the move would otherwise revive it, where the tree wins (found
in review). Branch `p1b.3/resolver`, a stack if the spec and the toolkit
run past one review; depends on 1b.1. Done when the tests cover the
tree alone, a plugin alone, both with the tree winning, two matching
plugins refused, a registration whose root is gone, and a declared
commit outside HEAD's history, all against a scratch data root; the
three 1b.3 rows of the mechanism table are filled from a scratch
plugin; and a reader of `docs/map.md` could publish a map plugin for a
repository of their own, or commit one to it, without reading a skill.
Done: `docs/map.md` has the section (the settings block a project
commits, the plugin's shape with the manifest's declaration and the
one-line hook, the resolver's three answers and its one warning);
`lib/rolling/mapsource.py` is the resolver, with its contract as the
module docstring, and `Where` in `cli.py` carries what it found, so
every command reads the same map; `rolling-show map` opens with
`(map: in tree)` or `(map: plugin rallly@rollingstart 0.3.0)` and the
notes, `map-check` says the source beside its verdict and `MAP: none`
with the registrations listed when nothing resolves, and
`rolling-check-map` with no argument exits 1 then. Fifteen tests in
`test_resolver.py`: the URL normaliser across every spelling of one
remote (and paths, Windows drives included, refused), the tree winning
over an installed plugin, a plugin alone read by every command, two
matches refused naming both, a registration whose root is gone or
whose manifest lacks the declaration or whose root has no map, no
remote, a local remote, `ROLLING_DATA` unset, nothing installed, a
declared commit the checkout lacks, one ahead of HEAD, one that is not
a sha, and a task branch cut from a commit that still carried a map.
The pre-push review found the matching case-sensitive where GitHub is
not, the two-plugins refusal followed by a verdict line contradicting
it, and the revived map; all fixed with tests. The three
mechanism rows above are filled from a scratch plugin on the host. The
Rallly map still lives in the tree until 1b.4, so the plugin route has
run only against the scratch plugin. PR #24.

---

### 1b.4 — The Rallly map as a map plugin, and the runner retired [PENDING]

`plugins/rallly/`: the map from `examples/rallly/.rolling/` at the
plugin root, `plugin.json` with the declaration (`*/rallly` or the
upstream URL, the maintainer's call, and `aab791da`) and a version,
the registration hook, a README that says how to install it, what to
add to settings (the toolkit's allow rules, a git identity for the
learner's checkpoints), and which of Rallly's services a lesson
expects to find running; the marketplace lists it; `examples/` is
gone. `runner/` is deleted with its README, and everything that
pointed at it (`CLAUDE.md`'s key locations and its Rallly rules,
`spike/README.md`, `docs/plan.md` § 3's note on the runner's allow
rules) now points at the plugin's install notes or says nothing.
Branch `p1b.4/rallly-plugin`; depends on 1b.2 and 1b.3. Done when the
gate validates three things strictly (the marketplace, `rolling`,
`rallly`); in a Rallly clone with no `.rolling/`, the plugin installed
from this repository as a local marketplace, `/rolling:start` says the
map is the `rallly` plugin and `/rolling:next` serves a lesson; with
the plugin's map copied into the clone's `.rolling/` and committed on
a local branch, the same session says the map is in the tree; `grep
runner` over the repository finds only history (the P1a plan and the
spike's notes); and the `dependencies` row of the mechanism table is
filled.

---

### 1b.5 — The Homie map, in Homie's tree [PENDING]

A map for Homie, committed to `github.com/kurowski/homie` as
`.rolling/` in that repository's own PR, with the `.claude/settings.json`
the in-tree route carries, as `docs/map.md` now spells it. Written
from the code, the history, and `CLAUDE.md`: commands from the
`Makefile` and the module (`build`, `test` with a package path
appended, `vet`, and `e2e`, which is the repository's own
container-based suite, declared like Rallly's `integration` with what
it needs said on the map: Docker on the learner's machine, four image
builds, minutes rather than seconds, so it is never in a task's
verifier and is in the definition of ready, as Homie's own brief says
to run it before tagging); no operations unless the repository has
one worth declaring; regions from the package layout (the command layer in
`cmd/homie`, config and templating, the package backends, externals,
doctor and status; the maintainer's count, not this plan's); the two
openers, `local-dev-setup` (a Go toolchain and git, `go build`, `go
test ./...` green, and nothing to start) and `how-a-change-ships` (a
merged PR from the history, the test it carried shown), three or four
`working` lessons with fixes to revert, and one suggested course. The
map is reviewed in Homie's PR; what lands here is the record. No
branch in this repository unless the run finds a toolkit fix, which
gets its own. Depends on 1b.3. Done when `rolling-check-map` is green
in Homie's tree, every path, line, sha, and PR number is read at the
commit the map went in on, each fix-backed task is proved both ways
with the toolkit in a Homie clone with the Go rows of the mechanism
table recorded, and one `write` lesson runs end to end there with the
maintainer as the learner, its transcript read for the failure modes
P1a named and for one more: anything in the plugin's prose or the
toolkit's messages that only made sense under pnpm.

---

### 1b.6 — The work codebase's map, privately [PENDING]

The in-tree route walked where it matters: a map in the work
codebase's own tree, its `.claude/settings.json` carrying what
`docs/map.md` says an author inside a project commits, and a lesson
run by a colleague or the maintainer. No branch here. Depends on
1b.3. Done when one paragraph in this file's retrospective says what
the format or the toolkit lacked and which PR fixed it, with nothing
about the codebase in it, and the fixes are in this repository under
their own sub-scope or as backlog issues.

---

### 1b.7 — The exit run, and closure [PENDING]

Run the checkpoint's exit criterion honestly and close it out. Branch
`p1b.7/closure`; depends on 1b.4 and 1b.5. Done when: on a machine or
container that has never seen this repository, the marketplace is
added from GitHub, `rolling` and `rallly` are installed, and
`/rolling:next` in a fresh Rallly clone serves a lesson with no map in
the tree, the session's transcript read for the properties P1a's exit
run checked; a `write` lesson has run on Homie from the map in its
tree under `go test` (1b.5's run, or a second if the map changed
since); the last two mechanism rows are filled; the retrospective is
appended here in the register the P1a one set; `CLAUDE.md` § Status,
`docs/plan.md` § 7, and the README are updated; `docs/workflow.md`
says to check that the automatic review posted (from P5's deferred
list, since P1b closes first); and the decisions worth keeping are in
`docs/plan.md` § 10, dated.

## Explicitly deferred

- **`adopt`, and with it any stamp of a map's provenance and any
  notice that a plugin is newer than what a tree adopted**: 2.0, if a
  project asks. Adoption in 1.0 is copying the plugin's map into
  `.rolling/`, because the tree wins.
- **`rolling-author`** as a plugin: P3, where `init` is its first
  skill and the writing of `.claude/settings.json` and the
  `permissions.ask` rules is `init`'s job. In P1b the settings block
  is written down in `docs/map.md` and pasted.
- **A proof harness in this repository.** P1a's retrospective
  suggested keeping one; the maintainer's lives beside the repository
  and was built around the runner. The product form is
  `rolling-author:verify` in P3; until then a task is proved by hand
  with `rolling-verify` in a scratch clone, which is four commands.
- **The managed-plugin route** (organisation settings, where a plugin
  may not ship `bin/`): P4's question, as § 3 says.
- **A second unfamiliar Node app** as a target: P3, where `init`'s
  question is whether a map can be drafted for a repository the author
  does not know.
- **`escalate`, `second-opinion`, the citation check, detours with the
  depth cap, evals, the ask-before-destructive hook, and whether `ask`
  is needed**: P2. The runs here are read by hand.
- **A guard for the walkthrough's write window** and **a script-proof
  session stamp**: P2's eval decides, as P5's plan records.
- **Everything in `direct` mode**: P5. The Rallly map's `direct`
  lessons stay as written and are skipped, except `billing-and-tiers`
  (1b.2). P5's plan has the runner growing a second window for the
  coding session; with the runner gone, that is a second terminal.
- **Cancel versus pause** (#20) and **a task with `held:` paths and no
  `held-verify:` line** (#14): backlog, taken if a run here trips on
  them.
- **The plan's § 3 tree** still lists `docs/decisions/`, `agents/`,
  `ask`, and `escalate`; it is the design's shape and is corrected at
  closure with the rest of § 7, not slice by slice.

## Verification

- The plan's exit criterion for P1b: `/plugin install
  rallly@rollingstart` in a fresh Rallly clone serves a lesson; a
  `write` lesson runs on Homie from the map in its tree under `go
  test`; a Rallly clone with the plugin installed and the map
  committed in its tree is taught from the tree.
- The gate is green on `main`, with two plugins and the marketplace
  validated strictly.
- Every mechanism in the table above has a recorded result, and none
  of them is "no" without a plan change that says how.
- `grep` finds no package manager, framework, path, or domain of
  Rallly's or Homie's under `plugins/rolling/`, and nothing in this
  repository starts, stops, or configures an environment.
- A reader of `docs/map.md` can publish a map plugin for a repository
  of their own, or commit one to it, without reading the skills.
