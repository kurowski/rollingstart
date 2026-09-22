# The runner

Rolling Start on a Rallly clone, contained: Rallly's toolchain and
Claude Code in a container, Rallly's services from its own compose
file, this repository's marketplace manifest and plugins mounted
read-only as the plugin marketplace, and nothing from npm executing on
the host. It is how a lesson is run on this machine during P1, and the
shape a `.devcontainer/` would take if P4 decides the Rallly example
ships one.

What the host needs: git 2.23 or later (for `git switch`), Docker with
the compose plugin, and a POSIX shell with `od` and `mktemp` (for the
secret `env.sh` generates and the files it writes); Linux or macOS. No
Node, no pnpm, no npm, no Python on the host; the toolkit's Python is
the base image's.

```sh
git clone https://github.com/lukevella/rallly ~/Projects/rallly-spike
git -C ~/Projects/rallly-spike checkout --detach aab791da5177f4a7653c8904e754808d9b4968ef   # the pin ../rallly is on
runner/run.sh up ~/Projects/rallly-spike
```

If the P0 spike's stack is still up (`docker compose ls` shows
`rolling-spike`), stop it first with `spike/container/run.sh down
~/Projects/rallly-spike`: both stacks are Rallly's compose file and
publish the same host ports.

`up` builds the image (Node 24, the pnpm Rallly's `packageManager`
pins, git, Python 3, Claude Code, as the unprivileged `node` user, uid
1000 to match yours), brings the stack up under the compose project
`rolling-runner`, writes both `.env` files from Rallly's samples with
the service names in place of `localhost` (`env.sh`, which fills
`SECRET_PASSWORD` too and never overwrites an existing `.env`), puts
the map from `examples/rallly/.rolling/` into the clone, and registers
the mounted marketplace inside the container and installs `rolling`
from it. Anything the P0 spike's installer left in the clone (its
skills, scripts, and settings under `.claude/`, its `.rolling/profile`)
is removed first, by name and only where git does not track it; a
tracked file of one of those names is the clone's own and stays, with
a note.

The map goes in committed. A task begins only from a clean tree, and a
task branch carries the map from the commit it began on, so an
uncommitted `.rolling/` would stop the first lesson. The first `up`
cuts a local branch `rolling/map` from the commit the clone is on and
commits the map there; a later `up` returns the clone to that branch
(saying so) and recommits the map if it changed. The branch is never
pushed. `up` refuses, touching nothing, when the clone has
uncommitted changes, when its `.rolling/` holds edits that are not the
example map, or when the clone is on a task's branch with a task
open. A map edit already committed on `rolling/map` is not protected:
the example is the source, and `up` recommits it over the edit, which
git still has. This is the shape a map has in a repository whose author
committed it, which is what the plugin expects in P1a; the map-plugin
route arrives in P1b.

Two more things `up` puts in the home volume, both found by the first
fresh learner's run. The host's git identity, copied in, so the
learner's commits inside are theirs; without one git refuses to commit
at all, and the toolkit falls back to committing as Rolling Start.
And allow rules for the toolkit's own commands in the container's user
settings, since a skill's grants hold only for the turn it ran in and
auto mode's classifier denied `rolling-begin-task` the moment `next`
had to ask the learner something first. The rules are the commands the
skills grant, plus `rolling-export`, which only ever creates a
directory the learner names. Unlike a skill's grants they hold in
every turn and in every session that shares the home volume, and
`rolling-verify` and `rolling-report` run the map's declared commands
through them; no map operation is among them, so a destructive one
still prompts. An author inside a project would commit the same rules
in its `.claude/settings.json`.

Then, inside the container, the steps from Rallly's `CONTRIBUTING.md`
that the `local-dev-setup` lesson is about:

```sh
runner/run.sh shell ~/Projects/rallly-spike
pnpm install                       # the pinned pnpm is baked into the image
exit
```

Stop there. Generating the Prisma client, migrating and seeding the
database, and getting the map's commands green is lesson one; doing it
here would leave that lesson nothing to do. `pnpm install` is enough to
prove the toolchain works.

Then the tutor, in the same container:

```sh
runner/run.sh tutor ~/Projects/rallly-spike
```

The first run asks you to log in: it prints a URL, you open it on the
host, and you paste the code back. The login lives in the home volume
`rolling-runner-home`, so it happens once, and so does everything the
plugin keeps about you: its data directory is under that home, so the
learner's state survives a rebuild of the image and a `down` of the
stack, and goes only with the volume. `/rolling:start` is the first
thing to run. A second window joins the same container with `shell`;
the container lives as long as the first window's process, so closing
that one cuts the others off. `down` stops the toolchain container,
open windows included, and the stack, and keeps the stack's data;
`destroy` removes the stack's data and the home volume, login and
learner state included.

What the tutor's session can see: the clone, its home, and under
`/rolling` the marketplace manifest and the plugins directory, since
Claude Code resolves an installed plugin through its marketplace
source at load time and reports `cache-miss` without it. The plugin's
own sources are in the installed copy in the home volume anyway; what
the mount leaves out is the rest of this repository, the plan, the map
sources, and the spike, which are not the learner's to read over the
tutor's shoulder.

Two differences between the container and a host, both handled in the
image. pnpm wants its store on the same filesystem as `node_modules`,
and the clone (a bind mount) and the home volume are not, so on its
own it would create `.pnpm-store/` inside the clone; the image pins
the store into the home volume. And on a Docker bridge network
`localhost` resolves to `::1` before `127.0.0.1`, which makes Rallly's
`outbound-proxy` unit test fail; the image sets Node to resolve IPv4
first. Both are explained in the `Dockerfile`.

What the container does not have: browsers, so Playwright integration
specs (`integration` on the map) cannot run; unit tests, type check,
lint, and structure checks all can. Port 3000 is published, so `pnpm
dev` inside the container serves the app at `http://localhost:3000`.

What this isolates and what it does not: a dependency's install script
runs as uid 1000 inside the container, sees the clone, the mounted
marketplace read-only, and the home volume, and nothing else of yours. It has
outbound network. Docker here is the rootful daemon, so a kernel
escape would be root; rootless Podman is the stronger runtime if that
matters, and the runner's `docker` calls are the only thing that would
change.

The plugin is installed from the marketplace, not loaded with
`--plugin-dir`, so this is also where the mechanisms the plan lists
for that route are checked: the plugin's `bin/` on the session's PATH,
the data directory the hooks are handed, and the source staying
reachable, all under a marketplace install; the checkpoint plan
records what was seen.
