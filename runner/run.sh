#!/bin/sh
# Run Rolling Start contained: Rallly's toolchain and Claude Code in a
# container, Rallly's services from its own compose file, this
# repository's marketplace manifest and plugins mounted read-only as the
# plugin marketplace, nothing from npm executing on the host.
#
#   runner/run.sh up      <clone>   build the image, start the stack, write .env, install the map, install the plugin
#   runner/run.sh shell   <clone>   a shell in the toolchain container
#   runner/run.sh tutor   <clone>   the tutor: Claude Code in the toolchain container, the plugin enabled
#   runner/run.sh down    <clone>   stop the toolchain container and the stack (keeps the stack's data)
#   runner/run.sh destroy <clone>   stop the stack and delete its data and the home volume
#
# One toolchain container per clone, named rolling-runner. The first
# `shell` or `tutor` starts it; a later one, from another window, joins it
# with `docker exec`, and is cut off when the first one exits. It joins
# the compose project's network, so services are reachable by name
# (rallly_db, mailpit, ...); env.sh writes .env files that say so. Port
# 3000 is published for the dev server. It runs as uid 1000 (`node`),
# matching the host user, so files it writes into the clone are yours.
# Its home is the named volume rolling-runner-home: Claude Code's login,
# the plugin's data directory (the learner's state), the pnpm store, and
# the npm cache all persist there across rebuilds; `destroy` removes it.
#
# The map goes into the clone committed, on a local branch `rolling/map`,
# never pushed: a task begins only from a clean tree, and a task branch
# carries the map from the commit it began on. The first `up` cuts the
# branch from the commit the clone is on; a later `up` returns to it and
# recommits the map there if it changed.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/.." && pwd)
cmd=${1:-}; clone=${2:-}
usage() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; }
[ -n "$cmd" ] && [ -n "$clone" ] || { usage; exit 1; }
clone=$(cd "$clone" && pwd)
[ -f "$clone/docker-compose.dev.yml" ] || { echo "$clone does not look like a Rallly clone"; exit 1; }
[ "$(id -u)" = 1000 ] || echo "warning: you are uid $(id -u); the container writes into the clone as uid 1000" >&2

project=rolling-runner
image=rolling-runner
container=rolling-runner
network="${project}_default"
homevol=rolling-runner-home
mapbranch=rolling/map

compose() { docker compose -p "$project" -f "$clone/docker-compose.dev.yml" "$@"; }
state() { docker container inspect -f '{{.State.Running}}' "$container" 2>/dev/null || echo absent; }
stack_up() { docker network inspect "$network" >/dev/null 2>&1; }

# The marketplace, mounted read-only at /rolling in every container: Claude
# Code resolves an installed plugin through its marketplace source at load
# time (a missing source is "cache-miss" and no plugin), so the mount is
# not only for the install. Only the manifest and the plugins directory
# go in; the rest of this repository (the plan, the map sources, the
# spike) is not the tutor's session's to read. The installed copy in the
# home volume holds the plugin's own sources regardless.

# enter command...: exec into the running container, or start it with this
# command as its first process. `--rm` removes it once that process ends;
# exec'd processes ride along and are cut off if the first one exits first.
enter() {
  stack_up || { echo "the stack is down; run: runner/run.sh up $clone"; exit 1; }
  case "$(state)" in
    true)  docker exec -it -w /work "$container" "$@" ;;
    false) docker rm -f "$container" >/dev/null; enter "$@" ;;
    *)
      docker run -it --rm --name "$container" \
        --user 1000:1000 \
        --network "$network" \
        -p 3000:3000 \
        -v "$clone:/work" \
        -v "$repo/.claude-plugin:/rolling/.claude-plugin:ro" \
        -v "$repo/plugins:/rolling/plugins:ro" \
        -v "$homevol:/home/node" \
        -w /work \
        "$image" "$@"
      ;;
  esac
}

# once command...: non-interactive and unnamed, for the setup steps.
once() {
  docker run --rm \
    --user 1000:1000 \
    -v "$clone:/work" \
    -v "$repo/.claude-plugin:/rolling/.claude-plugin:ro" \
    -v "$repo/plugins:/rolling/plugins:ro" \
    -v "$homevol:/home/node" \
    -w /work \
    "$image" "$@"
}

# install_map: the example map into the clone, committed on the local map
# branch. What the spike's installer left in the clone goes first, by
# name and only if git does not track it (the installer never committed;
# a tracked file of those names is the clone's own and stays), along
# with a half-made copy of the map a killed run left. Then the guards,
# touching nothing: a dirty clone, a map in the clone that is neither
# committed nor the example (someone's edits), an open task's branch.
install_map() {
  for f in .claude/skills/start .claude/skills/lesson .claude/skills/done .claude/scripts \
           .claude/agents/implementer.md .claude/rolling-coding.json .claude/biome.json .rolling/profile; do
    [ -e "$clone/$f" ] || continue
    if git -C "$clone" ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
      echo "note: $f is tracked in the clone, so it is the clone's own and stays"
    else
      rm -rf "${clone:?}/$f" && echo "removed the spike's $f"
    fi
  done
  rm -rf "${clone:?}/.rolling.new"
  if [ -n "$(git -C "$clone" status --porcelain --untracked-files=all -- . ':!.rolling')" ]; then
    echo "the clone has uncommitted changes outside .rolling/; commit or stash them before up"; exit 1
  fi
  if [ -n "$(git -C "$clone" status --porcelain --untracked-files=all -- .rolling)" ] \
     && ! diff -rq "$repo/examples/rallly/.rolling" "$clone/.rolling" >/dev/null 2>&1; then
    echo "the clone's .rolling/ has uncommitted changes that are not the example map:"
    diff -rq "$repo/examples/rallly/.rolling" "$clone/.rolling" 2>&1 | sed 's/^/  /' || true
    echo "move them aside (or into examples/rallly/.rolling/) before up; nothing was touched"; exit 1
  fi
  current=$(git -C "$clone" symbolic-ref -q --short HEAD || echo "")
  case "$current" in
    "$mapbranch") ;;
    rolling/*) echo "the clone is on $current, a task's branch; finish the task (/rolling:done) before up"; exit 1 ;;
    "") ;;
    *) echo "leaving $current for $mapbranch" ;;
  esac
  if git -C "$clone" show-ref --verify --quiet "refs/heads/$mapbranch"; then
    git -C "$clone" switch -q "$mapbranch"
  else
    echo "cutting $mapbranch from the commit the clone is on"
    git -C "$clone" switch -q -c "$mapbranch"
  fi
  # The copy lands beside the old map and swaps in, so a failed copy
  # leaves the old one in place.
  cp -R "$repo/examples/rallly/.rolling" "$clone/.rolling.new"
  rm -rf "${clone:?}/.rolling"
  mv "$clone/.rolling.new" "$clone/.rolling"
  git -C "$clone" add -A -- .rolling
  if git -C "$clone" diff --cached --quiet; then
    echo "map unchanged on $mapbranch"
  else
    git -C "$clone" -c user.name="Rolling Start" -c user.email="rolling@localhost" commit -q -m "Rolling Start map (local branch, never pushed)"
    echo "map committed on $mapbranch"
  fi
}

# install_plugin: this repository as a local marketplace in the container's
# home, and the plugin installed from it. An install copies the plugin
# into a cache keyed by its version, and neither `install` nor `update`
# refreshes that copy while the version stands, so a plugin already
# installed is uninstalled first, keeping its data: a plain uninstall
# deletes the plugin's data directory, which is the learner's state.
install_plugin() {
  once claude plugin marketplace add /rolling >/dev/null 2>&1 || true   # already added is fine
  once claude plugin marketplace update rollingstart
  if ! installed=$(once claude plugin list 2>&1); then
    echo "could not list the container's plugins:"; echo "$installed"; exit 1
  fi
  case "$installed" in
    *rolling@rollingstart*) echo "refreshing the installed plugin, keeping its data"; once claude plugin uninstall --keep-data rolling@rollingstart ;;
    *) echo "installing the plugin" ;;
  esac
  once claude plugin install rolling@rollingstart
}

case "$cmd" in
  up)
    docker build -t "$image" "$here"
    compose up -d --wait
    (cd "$clone" && sh "$here/env.sh")
    install_map
    install_plugin
    echo
    echo "stack is up on network $network; the clone is on branch $mapbranch with the map committed."
    echo "Next, inside the container:"
    echo "  runner/run.sh shell $clone"
    echo "  pnpm install"
    echo "and stop there: the Prisma client, the database, and the map's commands going green are lesson one."
    echo "then: runner/run.sh tutor $clone   (log in once; the login persists in $homevol) and /rolling:start"
    echo "a second window joins the same container: runner/run.sh shell $clone"
    ;;
  shell)  enter bash ;;
  tutor)  enter claude ;;
  down)
    docker rm -f "$container" >/dev/null 2>&1 || true
    compose down
    ;;
  destroy)
    docker rm -f "$container" >/dev/null 2>&1 || true
    compose down --volumes --remove-orphans
    if docker volume inspect "$homevol" >/dev/null 2>&1; then
      docker volume rm "$homevol" >/dev/null
      echo "removed $homevol (login and learner state included)"
    else
      echo "$homevol was not there"
    fi
    ;;
  *) echo "unknown command: $cmd"; usage; exit 1 ;;
esac
