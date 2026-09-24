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
map was checked against a release the checkout does not have; the
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
| The declaration is manifest metadata, and the hook writes one line | `plugin.json` carries `"metadata": {"rolling": {"repo": "<pattern>", "ref": "<tag, or a sha>"}}`; `hooks.json` has one SessionStart command that writes `${CLAUDE_PLUGIN_ROOT}` to `${CLAUDE_PLUGIN_DATA}/root`, in shell, creating the directory first | Claude Code ignores `metadata` and `--strict` accepts it, so the declaration is reviewed where the manifest is and is never parsed by a hook. The hook's only job is to say where the plugin's copy is, which nothing else can (a plugin's cache path carries its version and moves on update); a line of shell that writes a path needs no Python and no review beyond reading it. The declaration's `repo` is a pattern the repository's `origin` URL must match after normalising (scheme, `.git`, credentials stripped): `github.com/lukevella/rallly`, or `*/rallly` for an author who expects forks. `ref` is the release the map was last checked against, a tag nearly always ("validated against 4.14.0" is a thing a learner can be told, "check out this old sha" is not; the maintainer's point on reading the first draft), a sha only for a project with no releases; an outsider's map is always behind a living repository, and the resolver watches only for the reverse. An in-tree map declares nothing: the tree it is in is its pin. |
| The resolver is one function with three answers | `paths.resolve_map(top, data)`: the tree's `.rolling/` when it exists; else the registered map plugin whose `repo` matches this repository's remote and whose registered root still exists; else no map, with the registered plugins and their declared repositories listed in the message. Two matches is a refusal naming both. Registrations are the `root` files in the sibling directories of `ROLLING_DATA`, the plugin data root Claude Code keeps at `~/.claude/plugins/data/` | One resolver in one place, as the learner directory has (P1a). `Where.map_dir` is the only thing that changes, so every command, the pen's validators, and the task carry-over see the same answer. A registration whose root is gone (an uninstall with `--keep-data`, a cache purge) is skipped, not an error. Tests build the data root in a temporary directory with the registrations they need. |
| The tree wins, and the resolver says which it chose | `rolling-show map` and `map-check` say where the map came from (`in tree`, or `plugin rallly@rollingstart 4.14.0`) and add a line when a plugin map's declared `ref` (the release it was checked against) is not in the checkout or not an ancestor of HEAD | § 3: the tree's map wins, so a project can take an outsider's map into its tree by copying the directory in, and the plugin is simply no longer consulted; that is all adoption needs in 1.0, and the `adopt` skill that would do the copy and stamp its source waits for 2.0 (below). The ancestor check is what "the checkout does not contain the declared release" means in git; a checkout behind the map's pin gets pointers that describe a future it has not fetched, which is the stale-pointer wart 1a.8 found from the other side. |
| Map plugins carry a version, the target's release by convention, bumped on every change | `plugin.json` `version`, semver: the release the map was validated against (`rallly` 4.15.2 for Rallly 4.15.2), the patch bumped for a map change between releases, and the version becoming the new release when the map is revalidated; the marketplace entry carries none | A plugin with a version is pinned to it: the learner keeps the map they installed until `plugin update`, and a lesson in progress does not have its map change under it. A git-sourced plugin without a version would update on every commit of this repository, which is the wrong cadence for content. Matching the target's version is not enforced, but it is what a reader assumes a map's version means (the maintainer, reading the first draft), so the examples keep it and `ref` stays the exact truth. Docs: set the version in one place only; `plugin.json` is that place. |
| The Rallly map's source moves to the plugin | `examples/rallly/.rolling/` becomes `plugins/rallly/`; `examples/` goes | One source, and it is the thing that ships. A Rallly clone gets the map by `plugin install`; nothing else copies it anywhere. |
| `runner/` is retired | Deleted in 1b.4 with its README, its rows in `CLAUDE.md`, and `spike/README.md`'s pointer to it; the maintainer's harness beside this repository is theirs | It existed to keep Node off the host, which meant orchestrating Rallly's toolchain and services around the plugin from inside this repository. Once the map is a plugin, installing Rolling Start into a Rallly clone is the same `plugin install` as anywhere, and how the maintainer runs Rallly (contained, or on the host after all) is as external to this repository as the environment is to the tutor. What the runner did that still matters is documented where it belongs: a git identity and the toolkit's allow rules are the learner's environment and the install notes say so; the proof of a task is the toolkit's `rolling-verify` by hand until P3's `verify`. |
| Homie's map is in Homie's tree from day one | `.rolling/` committed to `github.com/kurowski/homie` in that repository's own PR, with the `.claude/settings.json` § 3 says an author inside a project commits; nothing of the map in this repository | The maintainer owns Homie, so the lifecycle the plan sketched for it (a plugin here, adopted later) was ceremony: an author inside a project commits the map. Homie is now the internal-author route in public, the same route the work codebase walks in private. Homie assumes no orchestration: a Go toolchain and git, and the map says so. |
| `adopt` and `rolling-author` wait | No `rolling-author` plugin in P1b; it first appears in P3 with `init`. `adopt` (the copy of a plugin map into `.rolling/`, a stamp saying where it came from, a note when the plugin is newer than what the tree adopted) is 2.0, if a project ever asks for it | Adoption in 1.0 is a copy any author can do by hand, because the tree wins. A skill, a stamp, and a staleness note on the stamp are machinery for a lifecycle nobody has started yet, and P1b is simpler without them. The design keeps the skill (`docs/plan.md` § 2, § 3); the plan moves it. |
| The toolkit allows its own commands through a hook, not through settings | `rolling-allow`, a PreToolUse handler on Bash and Skill: `allow` for a single invocation of a toolkit executable with word arguments (heredoc and `2>&1` included) and for the two hand-off skills; silence otherwise | The allow rules existed because a skill's grants expire with its turn and auto mode denies a fresh decision; they were a JSON block a learner pasted into user settings, the roughest edge of the install (the maintainer, walking the Rallly path as a user). A plugin cannot ship permission rules, but its hooks run in every mode and an `allow` skips the prompt for that one call: the same mechanism the write guard uses for `deny`. Considered: a `rolling-setup` script that edits `~/.claude/settings.json`; a plugin editing the user's permissions is what permission systems exist to stop, and it would still be a step to know about. The hook matches only the toolkit's own executables, so nothing of the map's is allowed by it, and P5's state guard, which denies the same executables in a coding session, is its mirror (a deny from one hook beats an allow from another on the same call, probed below). The hook handlers themselves (`rolling-allow`, `rolling-guard`, `rolling-session-start`) are left out of the list: they exist to be run by `hooks.json`, and `rolling-session-start` would repoint the learner's directory for the rest of the session. |
| The work codebase's map leaves one paragraph here | What the format or the toolkit lacked, generically, and nothing else | `CLAUDE.md`: the maintainer's employer's codebase never appears in this repository. The internal-author route still has to be walked in P1b, since it is the corporate case, and the plugin should learn from it without the record saying what was learned about. |

One decision is the maintainer's, before 1b.8 runs: `/plugin
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
| A `dependencies: ["rolling"]` entry: what `plugin install rallly@rollingstart` does when `rolling` is not installed (installs it, refuses naming it, or installs `rallly` alone), and what it does when it is | 1b.4 | **Installs it** (2026-09-23, 2.1.278, on the host, this repository as a local marketplace): with `rolling` absent, `plugin install rallly@rollingstart` reported `+ 1 dependency: rolling` and both were installed and enabled; with it present, `rallly` installed alone; `plugin uninstall rolling` succeeded with the warning `required by rallly`. One more fact: a plugin installed from a local-directory marketplace loads in place from the checkout (Claude Code says so at install), so on the maintainer's host an edit under `plugins/` is live at the next session start. |
| A plugin's PreToolUse hook answering `allow` for a Bash command lets it run where the session's permissions would otherwise deny it, in print mode and under auto mode's classifier, and a command the hook does not allow is still refused | 1b.5 | **Yes** (2026-09-23, 2.1.278, a scratch plugin under `--plugin-dir`): its hook allowed `probe-cmd one two` and the command's output is in the transcript, in print mode under default permissions (where a prompt is a denial) and again under `--permission-mode auto`; a `touch` the hook was silent about was denied in default mode (auto mode's classifier allowed that one on its own, which says nothing about the hook). |
| The Skill tool is hookable the same way: a PreToolUse `allow` on `tool_input.skill` lets a skill invoke another with no `allowed-tools` grant for it | 1b.5 | **Yes** (same probes): the event carries `tool_name: Skill` and `tool_input.skill`; an outer skill granting only Read invoked the inner one through the hook's allow, in both modes. |
| When two hooks decide the same call, a `deny` from one beats an `allow` from the other | 1b.5 | **Yes** (2026-09-23, same scratch plugin, under `--permission-mode auto`): the allow hook and a second hook denying `probe-cmd` both fired; the command did not run, the result listed it as denied, and the model reported the deny hook's reason. So P5's state guard can deny in a coding session what this hook allows everywhere. |
| A bumped `version` in a map plugin's `plugin.json` reaches an installed learner on `plugin update` and not before, under a marketplace added from GitHub | 1b.8 | **Yes, and it had never been exercised** (2026-09-24, 2.1.281, the exit-run container below). The container installed `rallly` 4.15.2 and `rolling` 0.1.0 from `main` at `06ca4be`; PR #35 bumped them to 4.15.3 and 0.2.0 and merged; a new session still showed the old versions; `/plugin marketplace update` then `/plugin update` brought both to the merge commit `ece1e674`. Preparing it found that `rolling` had been 0.1.0 through 31 commits, so no installed learner had ever been offered an update; the fix is #35's CI check. One more fact: after an update the map plugin's registration still names the old copy until a session starts (its hook writes it), so a learner sees the new map after a `/clear` or a restart, as after an install; the old copy stays in the cache, so nothing breaks in between. |
| `/plugin marketplace add kurowski/rollingstart` then `/plugin install rolling@rollingstart` and `rallly@rollingstart` in a fresh Rallly clone on a machine that has never seen this repository: the plugin's `bin/` on PATH, the map resolved, a lesson served | 1b.8 | **Yes** (2026-09-24, 2.1.281): a `node:24-trixie` container with Claude Code installed by its own installer, no configuration, and Rallly cloned at `v4.15.2` from GitHub. `/plugin install rallly@rollingstart` brought `rolling` as its dependency; after `/clear` the map plugin had registered, `/rolling:start` found the map through it with no `.rolling/` in the clone, and `/rolling:next` served `local-dev-setup`. With the map copied into a clone's tree and committed, the same install's `rolling-show map-check` reported `in tree` and read the tree's copy. |
| A held `_test.go` that does not compile on the starting state (it calls what the fix adds) is the expected failure `--on-base` wants | 1b.6 | **Yes** (2026-09-22, in a scratch clone of Homie at `v0.7.0`): the `tool-owned-files` task, held `clonetarget_test.go` from `f3ba646`, which takes two results from a function that returns one on the parent; `--on-base` reported the held line `EXPECTED-FAIL` with the compiler's `assignment mismatch`, and `PROOF: ok`. The same holds for a shown test: `vet` compiles a package's tests, so a shown test calling a function the task adds fails `vet` on its package on the starting state too, and the tutor in the lesson run marked both lines expected. The converse is the author's to know, and the Homie map now says it: when a fix changes a function a held test calls, `vet` on that package fails *with the reference in place*, because the learner's own copy of the test still calls the old form; the task vets the callers' package instead. |
| `go test`'s and `go vet`'s arguments (`./internal/runner/`, `./cmd/hm/`, `-run`, `TestName`) are words the verifier's argument rule accepts | 1b.6 | **Yes** (same proofs): every Homie task's lines, `test ./internal/packages/ -run TestPacman`, `vet ./internal/render/ ./cmd/hm/`, and the rest, ran as written. A `-run` pattern with `|` in it would not, which the map says: a task needing two tests names their common prefix. |
| An in-tree map's `.claude/settings.json` (the marketplace and `enabledPlugins`) offers to install `rolling` when a learner trusts the folder | 1b.6 | **Yes, silently, and it needs a `/clear`** (2026-09-23, 2.1.280, a fresh clone of Homie at `22a7e2d` opened under a throwaway `CLAUDE_CONFIG_DIR` with no marketplaces, no plugins, and no trusted folders). The trust dialog asked only to trust the directory, and nothing offered the marketplace or the plugin, but afterwards the `rollingstart` marketplace was known and `rolling` 0.1.0 was in the plugin cache and loaded, from the project's `enabledPlugins` (`installed_plugins.json` stayed empty). The first `/rolling:start` refused with the unset-`ROLLING_DATA` message: the plugin arrived after that session began, so its SessionStart hook had not run. After `/clear`, `/rolling:start` ran intake. So the in-tree install is clone, trust, `/clear`, `/rolling:start`; `docs/map.md` says so. On the maintainer's own host the first attempt showed nothing, because Homie had been trusted before the settings file existed. One more fact: the plugin data root stayed at `~/.claude/plugins/data/` under the throwaway config dir. |

Two assumptions of the toolkit that have only ever been checked under
pnpm, to confirm on Homie in 1b.6 and record in the same table: a held
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
does when both homes are present and when the declared release is
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
`(map: in tree)` or `(map: plugin rallly@rollingstart 4.15.2)` and the
notes, `map-check` says the source beside its verdict and `MAP: none`
with the registrations listed when nothing resolves, and
`rolling-check-map` with no argument exits 1 then. Fifteen tests in
`test_resolver.py`: the URL normaliser across every spelling of one
remote (and paths, Windows drives included, refused), the tree winning
over an installed plugin, a plugin alone read by every command, two
matches refused naming both, a registration whose root is gone or
whose manifest lacks the declaration or whose root has no map, no
remote, a local remote, `ROLLING_DATA` unset, nothing installed, a
declared sha the checkout lacks, a release tag behind HEAD (annotated
and lightweight, no note), one ahead of HEAD, one that is no ref, and a
task branch cut from a commit that still carried a map.
The pre-push review found the matching case-sensitive where GitHub is
not, the two-plugins refusal followed by a verdict line contradicting
it, and the revived map; all fixed with tests. The three
mechanism rows above are filled from a scratch plugin on the host. The
Rallly map still lives in the tree until 1b.4, so the plugin route has
run only against the scratch plugin. PR #24.

---

### 1b.4 — The Rallly map as a map plugin, and the runner retired [COMPLETE]

`plugins/rallly/`: the map from `examples/rallly/.rolling/` at the
plugin root, `plugin.json` with the declaration (`*/rallly` or the
upstream URL, the maintainer's call, and the release the map was
checked against) and a version,
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
filled. Done: `plugins/rallly/` is the map at the plugin root with
`plugin.json` (`dependencies: ["rolling"]`, the declaration
`github.com/lukevella/rallly`, the upstream only, and `ref: v4.15.2`,
with the version 4.15.2 by the convention), the one-line hook, and a README with the install
steps, the allow rules, the git identity, what the lessons expect
running, and how updates arrive; the marketplace lists it and CI
validates it strictly and runs the map check on it; `examples/` and
`runner/` are gone, and `CLAUDE.md`, `REVIEW.md`, `spike/README.md`,
and `docs/plan.md` § 3 no longer point at them. Checked in the Rallly
clone on the host: on a detached HEAD at the pin with no `.rolling/`,
one session start wrote the plugin's registration, `rolling-show map`
opened with `plugin rallly@rollingstart 4.15.2`, `map-check` was ok
from the plugin's directory, and `/rolling:next` with the polls
orientation seed opened `poll-surfaces` from the plugin's map and
began the walkthrough; back on the clone's map branch the same
commands said `in tree`. The pin moved for this: the map had been
checked at `aab791da`, seventy-eight commits past 4.14.0 and thirteen
before 4.15.0, so no release described it; it was revalidated at
`v4.15.2`, the latest release, from the clone's object store (every
cited path exists there; three router procedures moved by fifteen
lines, one participants procedure by twenty-three, four sample-env
lines by five; two facts changed and each lesson concerned says so:
participant writes refused once a poll leaves `open`, and
`registration` decoupled from email login), and `CLAUDE.md`'s pin
follows. The pre-push review found the map still explaining its
choices as facts about the retired container ("this example's
environment has no browser"); every such sentence is the map's own
declaration now, and the README's link to the format is absolute,
since the README ships alone into the plugin cache. `grep runner` finds the P1a record, this
plan, P5's plan (which assumed it; its deferred note says so), the
spike's frozen notes, and CI's comment about GitHub's runner. PR #25.

---

### 1b.5 — The toolkit allows its own commands [COMPLETE]

The install is the two `/plugin` lines and nothing else. A PreToolUse
hook in `rolling`, `rolling-allow`, answers `allow` for a Bash call
that is a single invocation of one of the toolkit's own executables
with plain-word arguments (the pen's heredoc form included, a
trailing `2>&1` tolerated, nothing chained, no other redirection or
substitution), and for the Skill tool when the skill is
`rolling:lesson` or `rolling:task`; everything else says nothing and
falls through to the session's own permissions, so a map's command
and a destructive operation still ask. The settings block a project
commits shrinks to the marketplace and the plugin; the `rallly`
README loses its allow rules and keeps the git identity and the
restart after install. Branch `p1b.5/allow-hook`; depends on 1b.4.
Done when the handler's tests drive it with hand-built events (each
toolkit executable, quoted arguments, a heredoc, `2>&1`, a chained
command, a substitution, a redirection to a file, a Skill event for
each of the two skills and for another, a malformed event); the two
mechanism rows above are filled; `docs/map.md`, `docs/plan.md` § 3,
and the README say the hook and not the rules; and in the Rallly
clone on the host with the rules removed from every settings file, a
lesson runs past a turn that needed the learner's reply with no
denial and no prompt for a toolkit command. Done: `rolling-allow`
(`lib/rolling/allow.py`, its contract the module docstring) on
PreToolUse for Bash and Skill; the command rule is quote-aware, since
a Next.js route path travels quoted with its brackets and
parentheses, and inside double quotes `$`, backtick, and backslash
stay forbidden because the shell still expands them there; an
unquoted heredoc is not allowed for the same reason. Thirteen tests
drive the rule with strings (every executable bare, quoted paths, the
pen's heredoc quoted and unquoted, `2>&1`, chains, substitutions,
groupings, redirections, a leading path or variable or `sudo`, quoted
expansions, unterminated quotes) and the handler through its
executable with hand-built events, malformed ones included. The
settings block in `docs/map.md` is the marketplace and the plugin;
the `rallly` README keeps the git identity and the restart; the two
skills and the plugin README no longer say a later turn asks; `docs/plan.md`
§ 3 and § 10 say the hook. Checked in a scratch clone of Rallly at
`v4.15.2` with both plugins loaded from this branch, no allow rule in
any settings file, and only the map's `pnpm` commands pre-approved
for the print-mode run: `/rolling:next` opened `billing-and-tiers`
and walked it through, and the resumed "yes, let's do the exercise"
had `task` cut the branch, write the task and the reference through
the pen, prove both ways, keep the task, and hand off to present it,
with zero permission denials in either turn. The pre-push review,
briefed as an attacker reviewing an allow-list, found a real bypass:
after an allowed pen heredoc, anything following the terminator line
ran as a second command, unprompted, in every mode (`rolling-write
task <<'EOF'`, a body, `EOF`, then `rm -rf …`); the body is now
checked to end at the terminator with nothing but blank lines after,
with the three strings that got through as tests. From the same
round: the hook handlers are out of the allow-list, since
`rolling-session-start` from the model would repoint the learner's
directory; and one note for P5 to inherit knowingly: the Skill allow
for `lesson` and `task` is unconditional now, in every session and
repository, where a per-project rule used to be, so the `whoami`
check 5.2 adds is the only barrier left between a description match
in a coding session and a claimed stamp. PR #26.

---

### 1b.6 — The Homie map, in Homie's tree [COMPLETE]

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
Done: the map is in Homie's tree (`kurowski/homie` `6d3f2af`, pushed
to `main` at the maintainer's word, with `05a4498` moving the
contributing pointer to homie.sh's page and leading it with the
tutor), read at `v0.7.0` (`d09af90`). Four commands (`build: go build
./...`; `test: go test` and `vet: go vet`, which take a package path;
`e2e`, never a verifier), no operations. Five regions (`cli`,
`config`, `packages`, `scripts` with externals, `scaffold`; doctor and
status in `cli`), three courses, six lessons: the two openers, the
second from `1349c31` (#30) with its test shown, and four `working`
lessons, each a reverted fix with its test held: `a051c28` (pacman's
cached `-Qq`), `d9a9c24` (#29, `$USER` in scripts), `f352881`
(render's skip when in sync), `f3ba646` (`CloneTarget` derives only
under `$HOME`). Each tells the tutor to keep the walkthrough off the
function that is the answer, since at the pin it is in the learner's
tree. All five fix-backed tasks proved both ways with the toolkit in a
scratch clone, the map committed there (begin, `--on-base`,
`--on-reference`, end, close, branch deleted), under three seconds a
direction. The first proof of `tool-owned-files` was not ok: `vet` on
the scaffold package failed with the reference in place, for the
reason the Go row above records, and the task now vets `./cmd/hm/`;
the map says the rule for any author. The lesson run, on the host
with `rolling` installed by hand (the trust-prompt row above, probed afterwards):
`/rolling:start` laid out the five regions and three courses from the
map and wrote a Generalist profile for a Go newcomer fluent in bash
and rpm; `/rolling:next` opened `local-dev-setup`; the walkthrough
paced the Go (modules, `internal/`, `-X main.version`, same-package
tests, table tests) at the lesson's pointers, confirmed each setup
step from the learner's pasted output, and raised both talk-through
items; the exercise was a seam the tutor chose (`repoName` beside
`normalizeURL` in `internal/externals`, test shown, `--here`), proved
both ways after the tutor found `vet` failing on base and marked it
expected (now in the lesson); `done` gave located feedback against
the rubric (a hand-rolled loop where `strings.LastIndexAny` does it,
a fragment of a doc comment) and the learner closed. Read for P1a's
failure modes: no fourth wall broken, no quiz, the verifier the
lesson's three lines and nothing added at `done`. Nothing in the
tutor's prose or the toolkit's messages leaned on pnpm. Three small
things, none a toolkit fix: the tutor never said the lesson was a
`write` lesson, which `CLAUDE.md` asks for; it dropped the lesson's
`$HOMIE_REPO` caveat on `homie status`; and it cited `f3ba646`, a later
exercise's source, as the example of what e2e catches, since the map's
corpus lists it. And one toolkit wording nit for the backlog: a
task with only a shown test gets `PROOF: ok (… and the held test was
reverted)` on base, where there is none. PR #28.

---

### 1b.7 — The work codebase's map, privately [COMPLETE]

The in-tree route walked where it matters: a map in the work
codebase's own tree, its `.claude/settings.json` carrying what
`docs/map.md` says an author inside a project commits, and a lesson
run by a colleague or the maintainer. No branch here. Depends on
1b.3. Done when one paragraph in this file's retrospective says what
the format or the toolkit lacked and which PR fixed it, with nothing
about the codebase in it, and the fixes are in this repository under
their own sub-scope or as backlog issues.
Done: the map is in the work codebase's tree with its settings, in
that repository's own pull request; ten exercises built from real fixes
were proved both ways, one lesson ran end to end with the maintainer
as the learner, and its transcript was read. What it taught, for the
retrospective at closure. It was the first map for a codebase with
services, persistent test databases, and a monorepo whose apps import
built packages, and every hard part was the repository around a task's
starting state rather than the task. A verifier that reads state outside
the tree (a database's schema) needs a reset before a task from an older
commit can be proved; a package manager leaves links from another
commit behind, which breaks a build; a file ignored today but not on
the starting state makes the tree look dirty (#33); and a command a map
declares must exist on every starting state a task uses, or its absence
passes as the expected failure (#31). The first two were answered in the
map, by operations whose scripts live in `.rolling/`, since an operation
runs on the starting state and a script younger than it would not be
there: `docs/map.md` now says a map in the tree may carry them. A
reference that adds a dependency cannot be proved, since nothing
installs between applying it and checking (#32); that task was dropped.
Two more lessons for authors, now in the map rather than the toolkit: a
fix whose commit did not type-check alone (the team fixed the types a
commit later) cannot carry a type check, and a verifier ends with a
formatting check on the files it touches, since the learner's change
passed every check and would have failed CI on a semicolon. The run
itself held the P1a properties, and the tutor bent a suggested course to
the learner's stated goal unprompted; its one serious failure was
reporting a check it had not run, two lines of shell output of which its
tool call returned one (#30), which is P2's citation check. PR #34.

---

### 1b.8 — The exit run, and closure [COMPLETE]

Run the checkpoint's exit criterion honestly and close it out. Branch
`p1b.8/closure`; depends on 1b.4, 1b.5, and 1b.6. Done when: on a machine or
container that has never seen this repository, the marketplace is
added from GitHub, `rolling` and `rallly` are installed, and
`/rolling:next` in a fresh Rallly clone serves a lesson with no map in
the tree, the session's transcript read for the properties P1a's exit
run checked; a `write` lesson has run on Homie from the map in its
tree under `go test` (1b.6's run, or a second if the map changed
since); the last two mechanism rows are filled; the retrospective is
appended here in the register the P1a one set; `CLAUDE.md` § Status,
`docs/plan.md` § 7, and the README are updated; `docs/workflow.md`
says to check that the automatic review posted (from P5's deferred
list, since P1b closes first); and the decisions worth keeping are in
`docs/plan.md` § 10, dated.
Done: the exit run is written up in the retrospective below. A container
that had never seen this repository installed both plugins from GitHub
and served a lesson from the plugin map to a learner who said they
were a total beginner; the same install taught from the tree when a
map was committed there; the version row was tested across PR #35,
merged mid-run. 1b.6's Homie run stands for the `go test` lesson: the
map changed since only in the setup lesson's prose, and that change
came from the run itself. `CLAUDE.md` § Status, `docs/plan.md` § 3,
§ 7 and § 10, the README, and `docs/workflow.md` (check that the
automatic review posted, not only that its job is green) are updated.
PR #36.

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
- **The plan's § 3 tree** listed `docs/decisions/`, `agents/`, `ask`, and
  `escalate` as if built; corrected at closure (PR #36): what is not
  built yet is marked with the phase that builds it, and `docs/` is
  shown as it is.

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

## Retrospective

**Planned against delivered.** Eight sub-scopes, delivered as PRs #22
to #26, #28, #34, #35 and this one, #36, between 2026-09-22 and 09-24,
with the website (#27) and two fixes pushed straight to `main` beside
them (an unset `ROLLING_DATA` now names its cause; inline code in the
site's prose no longer wraps). The resolver, the map-plugin format,
the Rallly map as a plugin, and the allow hook landed as planned, and
the runner went. Two maps were written into their own projects' trees,
Homie's publicly and the work codebase's privately, which the plan had
as one public adoption and one private map; the Homie decision of
2026-09-21 made the first. Two things were not planned: the discovery
at the exit run that no update had ever reached an installed learner,
and the operations that an in-tree map now carries in `.rolling/`.

**The exit run, as it went.** A fresh container, Claude Code from its
own installer, Rallly cloned at `v4.15.2`: the marketplace from
GitHub, `rallly` with `rolling` pulled in as its dependency, `/clear`,
`/rolling:start`. The learner said "total noob", then "BASIC on an
Atari, an intern whose boss is keeping me busy". Intake asked two
questions instead of pushing a course, proposed a route gentler than
any the map suggests (platform and polls, both at orientation), and
wrote the profile only after "yes, the gentle route". `next` opened
the only reachable lesson; the walkthrough checked the machine,
reported accurately that nothing was set up, explained the terminal
and a database in the learner's own terms, took the recipe from
`CONTRIBUTING.md` with the lesson's line references, and said the
services were someone else's to start, which is what the map says.
`/rolling:cancel` recorded the stop as unfinished and marked nothing.
No `.rolling/` was ever in the clone; the clone's tree was untouched.
Two small misses: intake said the learner starts the services and the
walkthrough said a teammate does, the map's two phrasings of one idea;
and the cancel ran the pen and the close as one chained command, which
the allow hook refuses by design, so it will have asked.

**The two in-tree maps.** Homie (1b.6) was the first map for a codebase
that is not Node, and it held: `go test` arguments pass the verifier's
rule, a held test that does not compile on the starting state is the
expected failure, and the one thing Go taught is for authors (vet
compiles a package's tests, so it sees a test before the code it
calls). The work codebase (1b.7) was the first with services,
persistent test databases, and a monorepo whose apps import built
packages, and every hard part was the repository around a task's
starting state rather than the task; its paragraph above is the record.
Both lesson runs were read; the work codebase's found the tutor quoting
shell output its tool call never returned (#30), the worst thing any
run in P1b found.

**Decisions made on the way**, the ones kept in `docs/plan.md` § 10: a
map plugin declares its repository and the release it was checked
against, and the tree wins (1b.3); the toolkit allows its own commands
through a hook (1b.5); a map in the tree may carry the scripts its
operations run (1b.7); every plugin change bumps the plugin's version,
enforced in CI (1b.8); and the in-tree install is trusting the folder,
then `/clear` (1b.6's probe).

**What went wrong, and the fix.** No update had ever reached an
installed learner: `rolling` sat at 0.1.0 through 31 commits, and
nothing in the gate or the workflow looked at versions, though
`docs/map.md` required bumps of maps; found preparing the exit run,
fixed by #35's bumps and its CI check, whose own automatic review found
the check's one real gap (a plugin with no version passed as new). The
allow hook's first version let anything after a heredoc's terminator
run unprompted, found by its pre-push review (#26). In the Homie proofs,
a `vet` line failed with the reference in place because the learner's
copy of the held test still called the old form; in the work codebase's,
a missing command passed as the expected failure (#31), which was
caught only by reading the reference run. A plugin that arrives
mid-session was a repeated trap: `/reload-plugins` does not fire
SessionStart, so a plugin installed mid-session has no `ROLLING_DATA`
until `/clear` (fixed on `main` with a message that names the cause),
the in-tree install needs the same `/clear` after trusting the folder,
and the update row found the same for a map plugin's registration. The automatic review's second pass on #35
reported its job green and posted nothing; the workflow now says to
check.

**Deferred, and where.** Toolkit gaps, as backlog: a missing command
passing as the expected failure (#31), a reference that adds a
dependency (#32), and a file ignored today but not on the starting
state (#33). The tutor reporting a check it did not run (#30), for
P2's citation check. `done` returning the learner to their branch
without a second question (#29). Cancel versus pause (#20) and a task
with `held:` paths and no `held-verify:` line (#14), still. `adopt`
and `rolling-author`, as planned.

**Carry forward.** A container from a stock image with Claude Code
installed by its own installer is the fresh machine the plan asked for,
and it cost minutes; keep it as the exit-run recipe. Proving every task
both ways before a map ships, in the environment the learner will use,
found more in the work codebase than any run did. A throwaway
`CLAUDE_CONFIG_DIR` answers questions about install and trust without
touching the maintainer's setup, though the plugin data root does not
move with it.

**What to change.** Test the release mechanics before the release:
the version row sat in the table from 1b.1 to 1b.8, and one install
from GitHub at the start of the checkpoint would have shown that
nothing updated. Read a green review job's output, not its status.
And when a script's guard is a guess about what a tool prints, run the
tool: two of this checkpoint's findings (`--no-renames`, the missing
command) were outputs nobody had looked at.
