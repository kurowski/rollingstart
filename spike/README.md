# P0: the spike

The cheapest possible test of the premise, before any structure. No
plugin: three skills, one agent, and four scripts dropped into a Rallly
clone's `.claude/`, plus a five-lesson map in its `.rolling/`. Run it on
yourself through two tasks, one of each mode, and answer honestly
whether the loop feels like being taught or like being nagged.

Plan: [`docs/plan.md`](../docs/plan.md) § 7, P0.

## What is in here

| Path | What |
|---|---|
| `claude/skills/start` | Intake: background, the author's suggested course, the learner's changes. Writes the profile. |
| `claude/skills/lesson` | Chooses the next lesson, builds a task from the map and git history, proves it both ways, coaches. Both modes. |
| `claude/skills/done` | Runs the verifier and captures the diff *before* the model's turn, then feedback against the rubric. |
| `claude/agents/implementer.md` | `direct` mode: works from the learner's brief alone, may plant a mistake. |
| `claude/scripts/verify.sh` | Runs the open task's `verify:` lines, resolved against the map's declared commands. Structured, never shell. |
| `claude/scripts/diff.sh` | The working tree against the task's base commit, untracked files included. Nothing has to be committed. |
| `claude/scripts/show.sh` | Prints one piece of context (map, lessons, profile, task…) for a skill's inline command; always exits 0, because an inline command that fails aborts the skill. |
| `claude/scripts/close-task.sh` | Removes the open task's files and nothing else, so the `done` skill never needs a broad `rm`. |
| `../examples/rallly/.rolling/` | The map and lessons for Rallly. |
| `install.sh` | Copies all of the above into a Rallly clone. |

## Setting up the Rallly copy

The spike runs in a writable Rallly clone with its stack up; the
reference checkout at `../rallly` is pinned and read-only, so make a
second one. Rolling Start never brings the stack up, so this is the one
time you do it by hand, following Rallly's own `CONTRIBUTING.md`. Rallly
declares Node 24 and pnpm via `packageManager`, so `corepack enable`
gives you the right pnpm.

```sh
git clone https://github.com/lukevella/rallly ~/Projects/rallly-spike
cd ~/Projects/rallly-spike
git checkout --detach aab791da5177f4a7653c8904e754808d9b4968ef   # the pin ../rallly is on
corepack enable && pnpm install
cp apps/web/.env.sample apps/web/.env && cp packages/database/.env.sample packages/database/.env
sed -i "s/^SECRET_PASSWORD=$/SECRET_PASSWORD=$(openssl rand -hex 32)/" apps/web/.env
pnpm docker:up            # postgres, redis, garage, mailpit, via Rallly's compose file
pnpm db:generate && pnpm db:reset --force && pnpm db:seed
pnpm type-check && pnpm test:unit && pnpm check   # the map's commands, green before you start
```

Then, from this repository:

```sh
spike/install.sh ~/Projects/rallly-spike
```

Re-run it whenever you edit the skills or the map.

## Running it

In the Rallly copy, open Claude Code and:

1. Before writing a lesson mode of our own, try the built-in one: `/config` →
   Output style → **Learning**. Note whether its `TODO(human)` habit is
   the right shape for `write` lessons.
2. `/start`. Answer as yourself. Push on the course.
3. `/lesson`. Take the `direct` task first: it is the one this project is
   for, and the one with the least prior art. Write the brief the way
   you would for an agent at work. Review what comes back the way you
   would at work.
4. `/done`.
5. `/lesson` again, for a `write` task. Try, at least once, to get the
   tutor to write the code for you.
6. `/done`.

Keep the sessions separate if you can (`/clear` or a new terminal
between lessons) so the profile is doing the remembering, not the
context window.

## What to record

Write it in [`NOTES.md`](NOTES.md) as it happens, not afterwards. The
exit criterion is an honest answer, and memory flatters.

- Taught or nagged? Where did it feel like a colleague, and where like
  a form?
- What did the model get wrong *unprompted*: did it write the solution
  in `write` mode; did it wave a failing verifier or an unmet rubric
  through; did it tour the codebase instead of serving the task; did it
  invent a task it had not proven?
- `direct` mode: did the implementer see anything but the brief? Was the
  planted mistake findable, and fair? Was the tutor's review of your
  review useful, or did it just grade you?
- Did the profile survive a fresh session, and did `/start` pick up
  where you left off?
- Which of the rules in the skills held on their own, and which will
  need a hook (P2)? Two to watch: the tutor writing inside a `write`
  task's scope, and the implementer or the tutor reading
  `.rolling/profile/reference.md` or `planted.md`, which only prose
  protects in P0.
- How long the inline verifier could run before Claude Code cut it off,
  if it ever did, and how long `/done` took to start speaking.
- Anything about the map format that was awkward to write, and anything
  the tutor needed that the map did not carry.

## Formats used by the spike

These are drafts. The plan's § 4 is the intent; the spike is where they
meet a real repo, and P1 writes them up properly.

**`.rolling/map.md`** has YAML frontmatter (`name`, default `mode`,
`commands`, `operations`, and `destructive`, the list of operation keys
that prompt) that the scripts read, and a Markdown body the
tutor reads: `## Regions`, `## Suggested course`, `## Corpus`,
`## Mistakes agents make here`. The frontmatter is parsed by `verify.sh`
with awk, so keep it flat: `commands:` followed by two-space-indented
`key: command` lines.

**`.rolling/lessons/<slug>.md`** has frontmatter `title`, `region`,
`depth` (`orientation` | `working` | `deep`), `mode` (`write` |
`direct`, optional), `requires` (list of slugs), `assumes` (list of
general knowledge the lesson leans on), and a body ending in
`## Rubric`.

A task's `verify:` lines run as one inline command in the `done` skill,
before the model's turn, under whatever timeout inline commands have.
That number is not documented; measuring it is one of the spike's jobs
(see NOTES.md). Keep verifiers short regardless: the map's `test-*`
commands take a file path for exactly this reason. `setup:` lines name
operations the task needs first and are run by the `lesson` skill when
the task starts, not by the verifier.

**`.rolling/profile/`** is the learner's and is gitignored by its own
`.gitignore`: `profile.md`, `task.md` (the open task; its shape is in
the `lesson` skill), `reference.md`, `brief.md`, `review.md`,
`planted.md`, and `evidence/<lesson>.md`.
