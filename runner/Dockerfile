# The runner's toolchain container: Node 24, pnpm via corepack, git,
# Python 3 (the toolkit's language; the base image ships 3.11), and Claude
# Code, running as the unprivileged `node` user. The Rallly clone is
# bind-mounted at /work, this repository's marketplace manifest and
# plugins read-only under /rolling as the plugin marketplace, and nothing
# else from the host; dependencies install and execute only in here.
#
# Build: docker build -t rolling-runner runner
# Run:   runner/run.sh (see runner/README.md)
FROM node:24-bookworm

ARG CLAUDE_CODE_VERSION=2.1.267
# Must match the clone's packageManager field at the pin; corepack fetches
# whatever the clone actually names, so this only decides what is baked in.
ARG PNPM_VERSION=10.28.0

# git for the repo, bubblewrap + socat so Claude Code's own /sandbox works
# inside the container too, and the small tools the skills' scripts and a
# working shell expect.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git ca-certificates curl openssl less procps bubblewrap socat ripgrep \
 && rm -rf /var/lib/apt/lists/*

# Claude Code, installed globally at build time so the launcher is on PATH
# for every user. The npm package installs a native binary that does not
# use Node at runtime. Auto-update is off: the image is the version.
# Python 3 is the toolkit's language. The base image ships it (3.11 at
# this tag), transitively; the check below is what fails the build if a
# base bump loses it, instead of a lesson.
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && claude --version \
 && python3 --version
ENV DISABLE_AUTOUPDATER=1

# In a container on a Docker bridge network, `localhost` resolves to ::1
# before 127.0.0.1, so a Node server bound by name lands on ::1 while a
# client connecting by name can end up at 127.0.0.1 (Rallly's
# outbound-proxy unit test does exactly that and fails with ECONNREFUSED).
# On the host the order is the other way round. Resolve IPv4 first, for
# every node process in here, so the container behaves like the host.
ENV NODE_OPTIONS=--dns-result-order=ipv4first

# pnpm comes from corepack, which the upstream node image ships, so the
# clone's packageManager field decides the version that runs. The pinned
# version is fetched now, at build time, into a shared corepack home the
# node user owns: no download and no confirmation prompt in the learner's
# first session, and a future pin bump can still be fetched at run time.
ENV COREPACK_HOME=/opt/corepack \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0
# pnpm keeps its store on the same filesystem as node_modules so it can hard
# link, and the clone (a bind mount) and the home volume are different
# filesystems, so left to itself it creates .pnpm-store inside the clone:
# untracked files in the working tree, and thousands of JSON files for
# biome to lint. Pin the store into the home volume; pnpm copies instead
# of linking across the boundary, which is slower once and correct always.
ENV npm_config_store_dir=/home/node/.pnpm-store
RUN corepack enable \
 && corepack install -g "pnpm@${PNPM_VERSION}" \
 && chown -R node:node "$COREPACK_HOME"

# The unprivileged user, uid 1000 to match the host user that owns the
# bind-mounted clone. Its home is a named volume at run time: Claude Code's
# config and login, the pnpm store, and the npm cache all persist there.
USER node
ENV HOME=/home/node
WORKDIR /work
CMD ["bash"]
