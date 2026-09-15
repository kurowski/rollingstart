# rolling

The learner's plugin. Enable it, and Claude Code becomes the tutor for
whichever repository you are in that has a Rolling Start map: a
description of the codebase written by someone who knows it, in the
format [`docs/map.md`](../../docs/map.md) defines. A map has two homes.
An author inside the project commits it at `.rolling/` in the
repository root; an author outside it publishes the same directory as
a map plugin, and the learner installs both plugins. In P1a only the
first is wired up; the map-plugin route and the resolver that prefers
a committed map over an installed one arrive in P1c.

The skills are `/rolling:start` for intake, `/rolling:next` for the
next task, `/rolling:lesson` to be re-briefed, and `/rolling:done` when
you think you are done. They arrive in P1a.5; what is here now is the
toolkit they call and the one hook they need.

Everything the tutor knows about you lives outside the repository, in
this plugin's data directory, keyed by the repository
([`docs/profile.md`](../../docs/profile.md)). Uninstalling the plugin
deletes it; `rolling-export` copies it out first.

## The toolkit (`bin/`)

On the Bash tool's PATH for the whole session while the plugin is
enabled. Every script is bash 3.2 or later, calls only `git` (2.23 or
later, for `git switch`) and a POSIX userland, and carries its
contract in its header comment. Every script that touches the tree
first finishes any held-test revert a killed run left behind.

| Script | Run by | What |
|---|---|---|
| `rolling-session-start` | the SessionStart hook | Exports `ROLLING_DATA` (this plugin's data directory) into the session's environment, so every later command can find the learner's directory. |
| `rolling-show <what>` | skills, inline | One piece of context: `map`, `lessons` (the index), `lesson [slug]`, `profile`, `task`, `corpus`, `tree`, `state-dir`. Always exits 0. |
| `rolling-claim-session <id>` | skills, inline | Records the session as the tutor's, in the open task or the `session` file. |
| `rolling-report` | `done`, inline | The diff, then the verifier, in that order, from one command. |
| `rolling-diff` | `rolling-report` | The working tree against the task's `base`, untracked included, nothing excluded, capped. |
| `rolling-verify [--on-base]` | `rolling-report`, `next` | The task's `verify:` lines against the map's commands, then the held test applied, run, and reverted, with the learner's own file set aside in the learner's directory and a record that survives a kill. `--on-base` is the both-ways proof, and a line that did not run fails it. |
| `rolling-begin-task <lesson> --fix <sha> [--held p]… [--shown p]… \| --here <path>…` | `next` | The throwaway branch with the starting state committed; held tests copied aside, shown tests brought forward; `--here` commits only the paths named. Refuses while a task is open. |
| `rolling-end-task` | `done` | Commits what the learner left on the task branch, keeps it, returns them to where they were. |
| `rolling-check-map [dir]` | authors, `next` | The map's shape against the spec. |
| `rolling-check-profile`, `rolling-check-task` | `start`, `next` | The learner's files' shape against the spec. |
| `rolling-close-task` | `done` | Removes `task.md`, `reference.md`, `held/`, nothing else. |
| `rolling-export <dir>` | the learner | Copies the learner's directory somewhere safe. |

Scripts a skill runs inline always exit 0 and report in words, because
a non-zero inline exit aborts the skill. Scripts a skill runs as an
action (`begin-task`, `end-task`, the checks, `export`) exit non-zero
on refusal.

## Tests

```sh
plugins/rolling/tests/run.sh
```

Each test builds a scratch repository with a small map and a fix in
its history under a temporary directory, points `ROLLING_DATA` at
another, and runs the scripts against that. Nothing touches a real
checkout or a real data directory. To run one script by hand outside
a session, set `ROLLING_DATA` yourself.

The scripts target bash 3.2, the one a stock Mac ships. CI runs the
tests on macOS under `/bin/bash`; to check on a Linux host, the
official `bash:3.2` image does it with a busybox userland, which is
stricter than macOS's:

```sh
docker run --rm -v "$PWD/plugins:/w/plugins:ro" -w /w bash:3.2 bash -c '
  apk add --no-cache -q git; cp -R /w/plugins /tmp/plugins; export HOME=/tmp
  git config --global user.email t@x; git config --global user.name t
  bash /tmp/plugins/rolling/tests/run.sh'
```

## Hooks

`hooks/hooks.json` registers the SessionStart handler above. The
`write`-mode scope guard joins it in P1a.4.
