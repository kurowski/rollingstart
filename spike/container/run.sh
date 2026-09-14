#!/bin/sh
# Run the spike contained: Rallly's toolchain and Claude Code in a container,
# Rallly's services from its own compose file, nothing from npm executing on
# the host.
#
#   spike/container/run.sh up      <clone>   install spike files, build image, start stack, write .env
#   spike/container/run.sh shell   <clone>   a shell in the toolchain container
#   spike/container/run.sh tutor   <clone>   the tutor: Claude Code in the toolchain container
#   spike/container/run.sh code    <clone>   the coding agent for a direct lesson, in a second window
#   spike/container/run.sh down    <clone>   stop the stack (keeps its data)
#   spike/container/run.sh destroy <clone>   stop the stack and delete its data and the home volume
#
# There is one toolchain container per clone, named rolling-spike. The
# first `shell`, `tutor`, or `code` starts it; any later one, from another
# window, joins it with `docker exec`, so a shell, the tutor, and the
# coding agent all share one container. `code` is a plain Claude Code
# session for the learner to direct, with the spike's hooks attached via
# --settings (they log prompts and tool calls for the tutor to read). It exits when its last
# process does. It joins the compose project's network, so services are
# reachable by name (rallly_db, mailpit, ...); env.sh writes .env files
# that say so. Port 3000 is published for the dev server. It runs as uid
# 1000 (`node`), matching the host user, so files it writes into the clone
# are yours. Its home is the named volume rolling-spike-home.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cmd=${1:-}; clone=${2:-}
[ -n "$cmd" ] && [ -n "$clone" ] || { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
clone=$(cd "$clone" && pwd)
[ -f "$clone/docker-compose.dev.yml" ] || { echo "$clone does not look like a Rallly clone"; exit 1; }

project=rolling-spike
image=rolling-spike
container=rolling-spike
network="${project}_default"
homevol=rolling-spike-home
compose="docker compose -p $project -f $clone/docker-compose.dev.yml"

running() { [ "$(docker container inspect -f '{{.State.Running}}' "$container" 2>/dev/null)" = "true" ]; }

# enter command...: exec into the running container, or start it with this
# command as its first process. `--rm` removes it once that process ends;
# exec'd processes ride along and are cut off if the first one exits first.
enter() {
  if running; then
    docker exec -it -w /work "$container" "$@"
  else
    docker run -it --rm --name "$container" \
      --user 1000:1000 \
      --network "$network" \
      -p 3000:3000 \
      -v "$clone:/work" \
      -v "$homevol:/home/node" \
      -w /work \
      "$image" "$@"
  fi
}

case "$cmd" in
  up)
    sh "$here/../install.sh" "$clone"
    docker build -t "$image" "$here"
    $compose up -d --wait
    (cd "$clone" && sh "$here/env.sh")
    echo
    echo "stack is up on network $network. Next, inside the container:"
    echo "  spike/container/run.sh shell $clone"
    echo "  pnpm install"
    echo "and stop there: the Prisma client, the database, and the map's commands going green are lesson one."
    echo "then: spike/container/run.sh tutor $clone   (log in once; the login persists in $homevol)"
    echo "a second window joins the same container: spike/container/run.sh shell $clone"
    ;;
  shell)  enter bash ;;
  tutor)  enter claude ;;
  code)   enter claude --settings /work/.claude/rolling-coding.json ;;
  down)   $compose down ;;
  destroy)
    docker rm -f "$container" >/dev/null 2>&1 || true
    $compose down --volumes --remove-orphans
    docker volume rm -f "$homevol" >/dev/null && echo "removed $homevol"
    ;;
  *) echo "unknown command: $cmd"; exit 1 ;;
esac
