# The map

What an author writes. A map is a directory of Markdown that describes
the landscape of one codebase: its regions, the course the author
suggests through them, the commands and operations the repository
runs, where the good code is and where the old code is, and the ways
an agentic change here goes wrong. It says nothing about any learner.
The learner's side is [`profile.md`](profile.md).

A map lives at `.rolling/` in the repository root, committed and
reviewed in the repository's own pull requests, when the author is
inside the project. When the author is outside it, the same directory
ships as a map plugin, installed beside `rolling`; the format is
identical and this page covers both. The design is in
[`plan.md`](plan.md) § 3 and § 4.

```
.rolling/
  map.md                        # the landscape
  lessons/<slug>.md             # one file per lesson
  lessons/<slug>/<task-slug>.md # optional: tasks the author wrote by hand for that lesson
```

## Where the map lives, and how the tutor finds it

**In the tree.** `.rolling/` at the top level of the working tree, as
above. A project that carries its map also carries, in
`.claude/settings.json`, what a learner needs so that cloning and
trusting the folder is the whole install: the marketplace, the plugin
enabled, and standing allow rules for the toolkit's own commands (a
skill's grants hold only for the turn it ran in, and the moment a
skill needs the learner's reply the next turn's command is a fresh
permission decision, which auto mode denies rather than asks). The
rules are every toolkit command a skill runs, none of which touches
the tree except through a task's branch, plus `rolling-export`, which
only ever
creates a directory the learner names; no map operation is among them,
so a destructive one still prompts, and git's read-only commands are
not among them either, since a standing grant on `git diff *` would
also pre-approve its `--output` write.

```json
{
  "extraKnownMarketplaces": {
    "rollingstart": { "source": { "source": "github", "repo": "kurowski/rollingstart" } }
  },
  "enabledPlugins": { "rolling@rollingstart": true },
  "permissions": {
    "allow": [
      "Bash(rolling-show *)", "Bash(rolling-claim-session *)", "Bash(rolling-write *)",
      "Bash(rolling-note *)", "Bash(rolling-begin-lesson *)", "Bash(rolling-begin-task *)",
      "Bash(rolling-verify)", "Bash(rolling-verify *)", "Bash(rolling-report)",
      "Bash(rolling-keep-task)", "Bash(rolling-end-task)", "Bash(rolling-close-task)",
      "Bash(rolling-export *)", "Skill(rolling:lesson)", "Skill(rolling:task)"
    ]
  }
}
```

**As a map plugin.** The same directory, with a manifest and one hook
beside it, published in any marketplace and installed with `/plugin
install <name>@<marketplace>`. The plugin root *is* the map directory:

```
<plugin>/
  .claude-plugin/plugin.json    # name, version, and the declaration below
  hooks/hooks.json              # one SessionStart command: the registration
  README.md                     # install notes: the settings block above, minus the map's own registration
  map.md                        # the landscape, exactly as in .rolling/
  lessons/<slug>.md
```

The manifest declares which repository the map is for, under
`metadata`, which Claude Code ignores and its strict validator
accepts:

```json
{
  "name": "rallly",
  "version": "4.14.0",
  "description": "The Rolling Start map for Rallly.",
  "metadata": { "rolling": { "repo": "github.com/lukevella/rallly", "ref": "v4.14.0" } }
}
```

`repo` is a pattern the repository's `origin` URL must match once
normalised to `host/owner/name`, lower-cased throughout: scheme,
credentials, a trailing slash, and `.git` stripped, an scp-style
`git@github.com:owner/name` read as `github.com/owner/name`; a local
path, or a `file://` URL with no host, matches nothing.
`github.com/lukevella/rallly` matches the upstream clone only;
`*/rallly` matches forks too, which is the author's call. `ref` is
the release the map was last checked against, as a git ref: a tag
(`v4.14.0`) nearly always, since "validated against version 4.14.0"
is a thing a learner can be told, and a sha only for a project with no
releases. A map by an outsider is always behind a living repository,
and that is fine; what the resolver watches for is the reverse, a
checkout behind the map. An in-tree map declares nothing, since the
tree it is in is its pin.

`version` is the target's release, by convention: the map for Rallly
4.14.0 is `rallly` 4.14.0, so a learner reading the plugin's version
knows what it describes without opening the manifest. Nothing checks
this; it is what a reader will assume, so the examples here keep it.
A change to the map that does not revalidate it against a new release
(a lesson fixed, a pointer corrected) bumps the patch number, since
every change to a map needs a new version: a plugin with a version is
pinned to it, so a learner keeps the map they installed until they
update, and a lesson in progress does not have its map change under
it. When the map is revalidated against a new release, the version
becomes that release. If the target's own patch releases and the map's
patch bumps ever collide, `ref` is the exact truth and the version is
the convention.

The hook is one line of shell, and it is the plugin's only code:

```json
{ "hooks": { "SessionStart": [ { "hooks": [ { "type": "command",
  "command": "mkdir -p \"${CLAUDE_PLUGIN_DATA}\" && printf '%s\\n' \"${CLAUDE_PLUGIN_ROOT}\" > \"${CLAUDE_PLUGIN_DATA}/root\"" } ] } ] } }
```

Every session start, it writes where the plugin's copy is into the
plugin's own data directory, which is the one place a plugin can write
without knowing anyone else's paths, and the one thing nothing else
can say (the copy's path carries its version and moves on update). A
map plugin ships no `bin/`, no skills, and no agents; an author who
copies the `rallly` plugin's shape maintains prose and a manifest.

**The resolver.** Every toolkit command finds the map the same way,
once, through one function (`lib/rolling/mapsource.py`):

1. `.rolling/` in the tree, when it exists. It wins whenever it
   exists, which is what lets a project take an outsider's map into
   its tree by copying the directory in: commit it, and the plugin is
   simply no longer consulted.
2. Else the installed map plugin declared for this repository: the
   `root` files in the sibling directories of `rolling`'s own data
   directory (Claude Code keeps every plugin's data under one root),
   each read for its manifest's declaration, the one whose `repo`
   matches the repository's remote. A registration whose root is
   gone (an uninstall with `--keep-data`, a cache purge), or whose
   root has no manifest, no declaration, or no `map.md`, is skipped.
   Two matches is a refusal naming both.
3. Else no map, and the message says which map plugins are installed
   and which repository each declares, so a learner in the wrong
   clone can tell.

`rolling-show map` opens with where the map came from (`in tree`, or
`plugin rallly@rollingstart 4.14.0`) and `rolling-show map-check` says
it beside its verdict. A plugin map adds one warning when its declared
`ref` is not in the checkout (a shallow clone or one made without tags
may lack it: fetch) or is not an ancestor of HEAD: a checkout behind
the release the map describes gets pointers to code it has not
fetched, and the tutor should say so rather than hunt for what is not
there. HEAD past the release, the common case, says nothing. A task
branch carries the tree's map as of the
commit the task began on, and none when there is none: a map an older
commit carried (a project that moved its map into a plugin) is removed
from the branch's starting state rather than revived, so the plugin's
map stays the one in use for the task.

Two audiences read these files. The **tutor** reads all of it, as
prose, every time a skill runs. The **scripts** read only the parts
this page marks as parsed: the frontmatter of `map.md` and of each
lesson, and three body conventions named below. Everything else is
prose for a model and a reviewer, and the scripts never look at it.
The line is there so that nothing in the toolkit knows what a lesson
teaches; a map can say anything, as long as the parsed parts are
well-formed.

## Frontmatter, as the scripts read it

YAML between a `---` line that opens the file and the next line that
is exactly `---`. The scripts do not have a YAML parser and do not
want one: the subset is flat. A field is `key: value` at the start of a
line. A map is a key on its own line followed by two-space-indented
`key: value` lines. A list is either `[a, b, c]` on the key's line or
`- a` lines indented two spaces beneath it. Nothing nests deeper, no
value is quoted unless it has to be, and no line carries a trailing
`# comment`: in a command it would swallow the arguments the toolkit
appends, so the validator rejects it there, and elsewhere it is simply
not parsed. Anything the subset cannot express belongs in the body.

## `map.md`

```markdown
---
name: Rallly
mode: write
commands:
  build: pnpm build
  typecheck: pnpm type-check
  test: pnpm test:unit
  lint: pnpm check
  test-web: pnpm --filter @rallly/web test:unit
operations:
  reset-db: pnpm db:reset --force
  seed-db: pnpm db:seed
  regenerate-client: pnpm db:generate
destructive:
  - reset-db
---

# Rallly

One paragraph on what the software is and how the repository is put
together …

## Environment
## Regions
## Suggested courses
### Generalist
### Billing engineer
## Corpus
## Mistakes agents make here
```

### Frontmatter fields

- **`name`** (required). The codebase's name as the tutor says it.
- **`mode`** (required). `write` or `direct`: the default for lessons
  that do not say. `write` means the learner writes and the tutor
  reviews; `direct` means the learner directs a coding agent and the
  tutor reviews how it went.
- **`commands`** (required, a map). The checks a task's verifier may
  select, keyed by a short name (`[a-z0-9-]+`). Each value is a
  command line the repository's own developers run, verbatim. A
  verifier line names a key and may add arguments; the toolkit runs
  the declared command with the arguments appended as separate words,
  never re-parsed. So a command that takes a file path (`test-web
  src/x.test.ts`) is the one a task should use, and the whole-suite
  commands are for the learner's own hands.
- **`operations`** (optional, a map). Things a task may need done
  first (regenerate a client, seed a database), keyed the same way,
  values verbatim. A task names one on a `setup:` line and the tutor
  runs it when the task starts. Operations are the author's shell and
  are reviewed in the repository like any script.
- **`destructive`** (optional, a list of operation keys). The ones
  that drop or overwrite something of the learner's. The tutor asks
  before each run of one, in every permission mode, and the author's
  `permissions.ask` rules (P3) make the tool itself ask too.

### Body sections

The body is prose for the tutor. Five headings are conventional, and
the toolkit checks for the presence of two of them, `## Regions` and
`## Suggested courses`, and reads the region names out of the first.

- **A one-paragraph summary** under the title: what the software is,
  how the repository is put together, and the release the map was
  checked against (a map plugin's manifest `ref`; a tree's map names
  the tag or commit it was last read at). The tutor introduces the
  codebase from it.
- **`## Environment`** (optional). The shape of the environment the
  lessons assume, as a description, not a rule: whether services are
  a precondition provided from outside or a step the learner takes,
  what is not available where the toolchain runs, what a failing
  command usually means. The tutor never orchestrates the
  environment; what the learner does about it is whatever this
  section says.
- **`## Regions`** (required). The parts of the codebase a learner can
  choose to learn, one bullet each, opening with the region's slug in
  bold: `- **billing** — Stripe subscriptions, the tier on a space,
  the pay wall …` followed by where it lives. The slug is `[a-z0-9-]+`
  and is what a lesson's `region` field and a profile's destination
  name. This is the one body convention the scripts parse: the bold
  slug at the start of each bullet under this heading, nothing else.
- **`## Suggested courses`** (required; the singular heading is
  accepted). The author's default itineraries, one per kind of
  learner the author expects, each under a `### <course name>`
  heading: the opening lessons everyone takes, then regions in a
  sensible order with a depth for each, and a sentence on who this
  course is for. A map with one course still writes it under a
  `###`. At intake the tutor lays out the course that fits what the
  learner said they are here for, names the others, and the learner
  bends it: drops a region, deepens one, says why. A course is a
  suggestion the learner edits, not a requirement the tutor enforces;
  there is no destination in the map.

  ```markdown
  ## Suggested courses

  Everyone starts with the two platform lessons, in this order;
  nothing else can be run or shipped without them.

  ### Generalist

  1. platform, orientation: local-dev-setup, how-a-change-ships
  2. polls, working
  3. billing, working

  For someone who will work across the product. Nobody needs deep in
  the first fortnight.

  ### Billing engineer

  1. platform, orientation: local-dev-setup, how-a-change-ships
  2. billing, deep

  Skips polls entirely; the billing lessons require only the opening
  two. Take polls at orientation later if the pay wall's gating of
  poll features starts to matter.
  ```
- **`## Corpus`** (recommended). Pointers: the paths whose shape new
  code should copy; the paths that are legacy, to read and not copy;
  a few merged pull requests that show how work is done here; the
  definition of ready before a pull request. The tutor reads a
  learner's change against these.
- **`## Mistakes agents make here`** (recommended; required for
  `direct` lessons to mean anything). The ways an agentic change to
  this repository goes wrong, one bullet each with where the rule is
  enforced: a mutation on a frozen surface, a barrel file the
  structure check bans, a string that skipped i18n, a test that
  asserts the mock. This is what a learner is taught to catch in a
  `direct` lesson and what the tutor reads an agent's change against.

## `lessons/<slug>.md`

```markdown
---
title: The poll data model
region: polls
depth: working
mode: write
requires: [how-a-change-ships]
assumes: [prisma, postgres]
test: held
---

What the lesson is, why it matters here, and where to look …

Task sources for the tutor: `af3d9273` (#3191) is a ten-line fix with
the test that proves it …

## Rubric

- The change is correct about the relations …
- The test asserts behaviour, not the mock …

## Talk through

- The participant token, the invite-to-participant link, …
```

### The slug

A lesson's identity is its file name without `.md`: `poll-data-model.md`
is the lesson `poll-data-model`, and that slug is what `requires`, a
task, and a learner's profile use to name it. Slugs are lowercase
kebab-case, one or more runs of `a`–`z` and `0`–`9` joined by single
hyphens, and nothing else. Case-insensitive filesystems fold
`Poll-Model` and `poll-model` together and Linux does not, so a map
that loads on the author's laptop would break on a learner's machine;
the validator rejects the file name rather than the link.

Every `.md` file in the directory is a lesson, so a `README.md` is a
lesson whose slug fails the rule. Every directory in it is a lesson's
task directory and must match a lesson's slug (below); a `drafts/`
directory is an error. Entries beginning with a dot are ignored, so
the directory can be opened as an Obsidian vault.

### Frontmatter fields

- **`title`** (required). The lesson's name as the learner sees it.
- **`region`** (required). A region slug from the map's `## Regions`.
- **`depth`** (required). `orientation`, `working`, or `deep`.
  Orientation is enough to read the code and follow a conversation
  about it; working is enough to make changes safely; deep is enough
  to own it. A learner who chooses a region at `working` gets its
  orientation and working lessons; at `deep`, all of them.
- **`mode`** (optional). `write` or `direct`. Overrides the map's
  default for this lesson.
- **`requires`** (optional, a list of slugs). The lessons that must be
  satisfied before this one is offered. Each must name a lesson in the
  directory; a lesson may not require itself, and the graph may not
  have a cycle, because there would be no order to serve it in. Bare
  slugs, not `[[links]]`: a link is Markdown's idiom for prose, and
  this is a declaration.
- **`assumes`** (optional, a list of words). General knowledge from
  outside the repository the lesson leans on: `prisma`, `trpc`,
  `postgres`. Not checked against anything; the tutor reads it against
  the learner's background to go faster where it is covered and to
  offer a detour where it is not. A lesson is never skipped for it.
- **`exercise`** (optional). `none`, for a lesson that is its
  walkthrough: a look around a region with nothing worth changing for
  its own sake. Left out, the tutor offers an exercise at the end of
  the walkthrough, built from the lesson's task sources when the
  learner takes it.
- **`test`** (optional). `held`, the default, or `shown`. When the
  tutor builds a task from a fix in history, the fix's test is
  normally held back: the learner writes their own, and the original
  runs as a hidden acceptance check when they say they are done. An
  author marks a lesson `shown` to have the test handed over with the
  task instead, the Exercism shape, for an early lesson where the
  point is the mechanics of the repository rather than the analysis.

Unknown fields are reported, so a misspelled `requries` cannot
silently declare a lesson with no prerequisites.

### The body

Prose for the learner, walked through by the tutor: what the lesson
is, why it matters in this repository, and where to look, as pointers
into the code (paths and, where they help, line numbers and shas, each
checked against the release the map names). This is the lecture: the
tutor opens every lesson by reading it with the learner in the code,
before any exercise is offered, so write it the way you would show a
new colleague around. Notes for the tutor alone (the fixes and seams
in history a task can be built from, situations to present, mistakes
to watch for) go in the body too, addressed to the tutor, and the
tutor leaves them out of the walkthrough. It closes with
**`## Rubric`** (required), followed only
by `## Talk through` when there is one: the rubric is what a
maintainer here would look for in the change, the reviewer's checklist
for this lesson, as prose the tutor reads the learner's change against
and shows the learner. It is written about the change, never about the
learner: "the constant lives in `packages/ui` and is spread, not
copied", not "the learner can name the file that would have failed".
A rubric is never a set of questions; the tutor reads it against what
was done and says what it saw, and the learner decides when the lesson
is done. The rubric is the author's; the tutor does not add to it. The
heading's presence is the second body convention the scripts check.

After the rubric, optionally, **`## Talk through`**: the things a
colleague would make sure you know before you leave this lesson, the
"can you say why" items that used to sit in rubrics. The tutor raises
them once, normally during the walkthrough, else at `done`, as a
conversation; the learner takes them up or not, and nothing about the
lesson's close depends on it.

## `lessons/<slug>/<task-slug>.md` (optional)

A lesson and a task are different layers. The lesson is the node on
the map: what to learn, why it matters here, where to look, the
rubric; it is what a course is made of and what a profile marks
satisfied. A task is one concrete piece of work that demonstrates a
lesson: a brief or a situation, a starting state, a verifier, a held
reference. Normally the `task` skill builds a task just in time from
the lesson's pointers and the repository's history. An author who
would rather choose the exercise by hand writes it here, in a
directory beside the lesson file that shares the lesson's slug, one
file per task with its own slug (same rule as a lesson's). A lesson
may have several; `next` picks among them, or generates when there
are none. The tutor still proves a hand-written task both ways before
serving it.

A task file carries the author's half of a task's fields, in the same
frontmatter subset: `mode`, `scope`, `scaffold`, `setup`, `verify`,
`held`, `held-verify`, `expect-fail-on-base`, and `fix` (the sha the
task is built from), then a `## Brief` or `## Situation` body and a
`## Source`. The fields are defined in [`profile.md`](profile.md) §
`task.md`, since that is where the tutor's copy of them lives; the
lesson is the parent directory, so there is no `lesson` field.

## What `rolling-check-map` checks

Shape, never content. Every fault is reported, one per line, with the
file and the field, so a map is fixed in one pass.

`map.md`:

- The file exists and has a frontmatter block.
- `name` and `mode` are present; `mode` is `write` or `direct`.
- `commands` is present and non-empty; every key matches `[a-z0-9-]+`
  and every value is non-empty, contains no `#`, and does not end in
  an operator (`;`, `&`, `|`, `>`, `<`, `\`), since the toolkit appends
  a task's arguments after it and they must stay arguments.
- Every key under `operations` matches the same rule, with a non-empty
  value.
- Every entry under `destructive` names an operation key.
- No unknown top-level field.
- The body has `## Regions` with at least one bullet opening with a
  bold slug, and `## Suggested courses` (or `## Suggested course`)
  with at least one `###` heading under it.

`lessons/`:

- The directory exists; every non-dot entry is either a regular file
  ending in `.md` whose stem is a valid slug, or a directory whose
  name is the slug of a lesson file beside it.
- Each file has a frontmatter block with `title`, `region`, and
  `depth`; `region` names a region from `map.md`; `depth` is one of
  the three; `mode`, if present, is one of the two; `test`, if
  present, is `held` or `shown`; no unknown field.
- `exercise`, if present, is `none`.
- Every `requires` entry names a lesson in the directory and is not
  the lesson itself, no lesson is listed twice, and the graph has no
  cycle (reported once, naming the lessons on it).
- The body contains a `## Rubric` heading.

`lessons/<slug>/`, for each that exists:

- Every non-dot entry is a regular file ending in `.md` whose stem is
  a valid slug; the frontmatter's fields are from the task list above;
  `verify` and `held-verify` lines name command keys, and a
  `held-verify` line has a `held` path to go with it; `setup` lines
  name operation keys; `fix`, if present, is a hex string of 7 to 40
  characters; the body has `## Brief` or `## Situation`, and
  `## Source`.

Not checked, on purpose: whether a path in the prose exists, whether
a sha is in history, whether the rubric is any good. Those are the
author's, and `rolling-author:verify` (P3) is where a map's claims
against the repository get tested.
