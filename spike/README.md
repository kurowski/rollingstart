# P0: the spike

The cheapest possible test of the premise, before any structure. No
plugin: three skills and eight scripts dropped into a Rallly
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
| `claude/scripts/verify.sh` | Runs the open task's `verify:` lines, resolved against the map's declared commands. Structured, never shell. |
| `claude/scripts/diff.sh` | The working tree against the task's base commit, untracked files included. Nothing has to be committed. |
| `claude/scripts/show.sh` | Prints one piece of context (map, lessons, profile, task…) for a skill's inline command; always exits 0, because an inline command that fails aborts the skill. |
| `claude/scripts/close-task.sh` | Removes the open task's files and nothing else, so the `done` skill never needs a broad `rm`. |
| `claude/scripts/begin-task.sh` | Puts the repo into a task's starting state on a throwaway branch, committed: for a reverted fix, branched from the fix's parent with only its test brought forward, so the answer is not in the diff or the branch's history. |
| `claude/scripts/end-task.sh` | Commits whatever the learner left on the task branch, keeps the branch, and returns them to where they were. |
| `claude/rolling-coding.json` | Hooks and a pinned default output style for the learner's coding session in a `direct` lesson, attached with `--settings` by `run.sh code`. |
| `claude/biome.json` | A nested Biome config that switches linting off under `.claude/`, so Rallly's `pnpm check` does not lint the spike's own scripts. Spike-only: the real plugin keeps its scripts outside the learner's repo. |
| `claude/scripts/session-log.mjs` | The hook handler: appends every prompt, tool call, and reply of the coding session to `.rolling/profile/session.log` for the tutor. |
| `claude/scripts/guard-profile.mjs` | PreToolUse hook for the coding session: denies reads and writes under `.rolling/profile/`, where the reference lives. |
| `claude/scripts/transcript.mjs` | Best-effort reader of a Claude Code session transcript (internal format), for detail beyond the log. |
| `../examples/rallly/.rolling/` | The map and lessons for Rallly. |
| `install.sh` | Copies all of the above into a Rallly clone. |
| `container/Dockerfile` | The toolchain image: Node 24, pnpm, git, Claude Code, unprivileged `node` user. |
| `container/run.sh` | `up`, `shell`, `tutor`, `code`, `down`, `destroy`: the stack from Rallly's compose file and the toolchain container on its network. |
| `container/env.sh` | Writes Rallly's `.env` files with the compose service names in place of `localhost`. |

## Setting up the Rallly copy, contained

Nothing from npm runs on the host. Rallly's toolchain and Claude Code
run in a container built from `container/Dockerfile` (Node 24, the pnpm
that Rallly's `packageManager` pins, fetched by corepack at build time,
git, Claude Code, as the unprivileged `node` user, uid 1000 to match
yours); Rallly's services run from its own `docker-compose.dev.yml`;
the toolchain container joins that stack's network and reaches the
services by name. The only thing mounted from the host is the clone. The
container's home is a named volume, `rolling-spike-home`, which is where
Claude Code's login, the pnpm store, and the npm cache persist.

What the host needs: git, Docker with the compose plugin, and a POSIX
shell with `od` (for the secret `env.sh` generates). No Node, no pnpm,
no npm on the host.

```sh
git clone https://github.com/lukevella/rallly ~/Projects/rallly-spike
git -C ~/Projects/rallly-spike checkout --detach aab791da5177f4a7653c8904e754808d9b4968ef   # the pin ../rallly is on
spike/container/run.sh up ~/Projects/rallly-spike
```

`up` copies the spike into the clone (`install.sh`), builds the image,
brings the stack up under the compose project `rolling-spike`, and
writes both `.env` files from Rallly's samples with the service names in
place of `localhost` (`container/env.sh`; it fills `SECRET_PASSWORD`
too, and never overwrites an existing `.env`). Then, inside the
container, the steps from Rallly's `CONTRIBUTING.md` that the
`local-dev-setup` lesson is about:

```sh
spike/container/run.sh shell ~/Projects/rallly-spike
pnpm install                       # the pinned pnpm is baked into the image
exit
```

Stop there. Generating the Prisma client, migrating and seeding the
database, and getting the map's commands green is lesson one
(`local-dev-setup`); doing it here would leave that lesson nothing to
do. `pnpm install` is enough to prove the toolchain works.

Then Claude Code, in the same container:

```sh
spike/container/run.sh tutor ~/Projects/rallly-spike
```

The first run asks you to log in: it prints a URL, you open it on the
host, and you paste the code it gives you back into the terminal. The
login lives in the home volume, so it happens once. Re-run `up` after
editing the skills or the map (it re-copies; the image and stack are
reused). `down` stops the stack and keeps its data; `destroy` removes
the stack's data and the home volume, login included.

Two differences between the container and a host, both handled in the
image. pnpm wants its store on the same filesystem as `node_modules`,
and the clone (a bind mount) and the home volume are not, so on its own
it would create `.pnpm-store/` inside the clone: untracked files in the
tree and thousands of JSON files for Biome to lint. The image pins the
store into the home volume with `npm_config_store_dir`; pnpm copies
across the boundary instead of linking. If a clone already has a
`.pnpm-store/`, delete it and every `node_modules` and run `pnpm
install` again in a fresh shell.

The other:
on a Docker bridge network `localhost` resolves to `::1` before
`127.0.0.1`, which makes Rallly's `outbound-proxy` unit test fail with
`ECONNREFUSED` (its server binds by name and lands on `::1`, its client
connects at `127.0.0.1`). The image sets
`NODE_OPTIONS=--dns-result-order=ipv4first` so every Node process in
the container resolves the way the host does. If a learner's first
`pnpm test:unit` shows that failure, the image is stale: re-run `up`.

What the container does not have: browsers, so Playwright integration
specs (`integration` on the map) cannot run in P0; unit tests, type
check, lint, and structure checks all can. Port 3000 is published, so
`pnpm dev` inside the container serves the app at `http://localhost:3000`
on the host if you want to see a change running.

What this isolates and what it does not: a dependency's install script
runs as uid 1000 inside the container, sees the clone and the home
volume, and nothing else of yours. It has outbound network. Docker here
is the rootful daemon, so a kernel escape would be root; rootless
Podman is the stronger runtime if that matters, and the runner's
`docker` calls are the only thing that would change. An egress
allowlist like the one in Anthropic's reference devcontainer is a later
addition, not a P0 one.

## Running it

With Claude Code running in the container (`run.sh tutor`):

1. Before writing a lesson mode of our own, try the built-in one: `/config` →
   Output style → **Learning**. Note whether its `TODO(human)` habit is
   the right shape for `write` lessons.
2. `/start`. Answer as yourself. Push on the course.
3. `/lesson`. Take a `direct` task first: it is the one this project is
   for, and the one with the least prior art. When the tutor hands you
   the situation, open a second window and run
   `spike/container/run.sh code ~/Projects/rallly-spike`: a plain
   Claude Code session in the same container, with hooks that log your
   prompts and its actions for the tutor. Direct it the way you would
   at work, as many turns as it takes, asking for the checks and tests,
   until you would merge. Then, in the tutor's window, `/done`.
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
- `direct` mode: did the tutor read the session as a session (steering
  counted), keep the checks' findings off your ledger, and cite your
  actual prompts? Did the coding agent behave like a normal session
  with the hooks attached?
- Did the profile survive a fresh session, and did `/start` pick up
  where you left off?
- Which of the rules in the skills held on their own, and which will
  need a hook (P2)? Two to watch: the tutor writing inside a `write`
  task's scope, which only prose protects in P0, and the coding
  session reaching into `.rolling/profile/`, which a PreToolUse hook
  in `rolling-coding.json` now denies.
- How long the inline verifier could run before Claude Code cut it off,
  if it ever did, and how long `/done` took to start speaking.
- Anything about the map format that was awkward to write, and anything
  the tutor needed that the map did not carry.
- Rallly ships its own `CLAUDE.md` and fourteen skills under
  `.claude/skills/` (Prisma, Better-Auth, Crowdin), so `/start`,
  `/lesson`, and `/done` share the menu with them and the tutor shares
  its context with Rallly's instructions. Did any of that leak into how
  the tutor behaved, and did the tutor ever invoke one of Rallly's
  skills unasked?

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
the `lesson` skill), `reference.md`, `session.log` (a `direct`
lesson's coding session, written by hooks), and `evidence/<lesson>.md`.
