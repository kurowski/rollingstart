# rolling

The learner's plugin. Enable it, and Claude Code becomes the tutor for
whichever repository you are in that has a Rolling Start map: a
description of the codebase written by someone who knows it, in the
format [`docs/map.md`](../../docs/map.md) defines. A map can come from
one of two places: an author inside the project commits it at
`.rolling/` in the repository root, or an author outside it publishes
the same directory as a map plugin, which the learner installs beside
this one. In P1a only the first is wired up; the map-plugin route, and
the resolver that prefers a committed map over an installed one when
both are present, arrive in P1c.

The skills are `/rolling:start` for intake, `/rolling:next` for the
next task, `/rolling:lesson` to be re-briefed, and `/rolling:done` when
you think you are done. `start`, `next`, and `done` are yours to type;
`lesson` is the one the tutor may invoke itself, since it only ever
re-presents the open task. Each skill declares the toolkit commands
it needs and nothing wider: no map command, no package manager, no
git that changes the tree; `next` alone also has the Edit and Write
tools, for the test it prepares before a task exists. The checks a
lesson asks of you are the repository's own commands, exactly as the
map declares them, and when the tutor runs one itself it asks. Those
grants hold for the turn a skill runs in; in a later turn of the same
conversation the tutor's own record-keeping commands ask you once
each, and the tutor says so.

Everything the tutor knows about you lives outside the repository, in
this plugin's data directory, keyed by the repository
([`docs/profile.md`](../../docs/profile.md)). Uninstalling the plugin
deletes it; `rolling-export` copies it out first.

## The toolkit (`bin/`)

On the Bash tool's PATH for the whole session while the plugin is
enabled. Each executable is a few lines that import
[`lib/rolling/`](lib/rolling/), Python 3.9 or later with no
dependencies beyond `git` (2.23 or later, for `git switch`). The
library's modules carry the contracts: `rules` (what a slug, an
argument, a path may be), `frontmatter` (the flat subset), `paths`
(where the map and the learner's directory are), `model`
(the map, lessons, task, and learner's directory as objects),
`validate` (the three checkers, returning faults), `repo` (git behind
a small wrapper), `heldtest` (the held test's apply and revert, with
the record that survives a kill), `verifier` (a structured report and
its rendering), `diff`, `tasks` (begin, end, close, and every
refusal), `session`, and `cli`. Every command that touches the tree
first finishes any held-test revert a killed run left behind.

| Script | Run by | What |
|---|---|---|
| `rolling-session-start` | the SessionStart hook | Exports `ROLLING_DATA` (this plugin's data directory) into the session's environment, so every later command can find the learner's directory. |
| `rolling-guard` | the PreToolUse hook | The `write`-mode scope guard: denies the tutor an edit inside the open task's scope. |
| `rolling-show <what>` | skills, inline | One piece of context: `map`, `map-check` (the map's faults in words, or `MAP: ok`), `lessons` (the index), `lesson [slug]`, `profile`, `task`, `corpus`, `tree`, `state-dir`. Always exits 0. |
| `rolling-claim-session <id>` | skills, inline | Records the session as the tutor's, in the open task or the `session` file. |
| `rolling-report` | `done`, inline | The diff, then the verifier, in that order, from one command. |
| `rolling-diff` | `rolling-report` | The working tree against the task's `base`, untracked included, nothing excluded, capped. |
| `rolling-verify [--on-base \| --on-reference]` | `rolling-report`, `next` | The task's `verify:` lines against the map's commands, then the held test applied, run, and reverted, with the learner's own file set aside in the learner's directory and a record that survives a kill. `--on-base` is the proof's first half (the expected failures fail on the starting state; a line that did not run fails it); `--on-reference` the second (the reference applied as a patch, everything passes, the patch reversed in a `finally`). The reference is the fix's own change, or for a seam task the patch the tutor wrote with `rolling-write patch`. |
| `rolling-begin-task <lesson> --fix <sha> [--held p]… [--shown p]… \| --here <path>…` | `next` | The throwaway branch with the starting state committed; held tests copied aside, shown tests brought forward, the map carried across as it is now; `--here` commits only the paths named. Refuses while a task is open. |
| `rolling-end-task` | `done` | Commits what the learner left on the task branch, keeps it, returns them to where they were. |
| `rolling-check-map [dir]` | authors, CI | The map's shape against the spec, exit 1 on a fault; `next` reads the same faults inline through `rolling-show map-check`. |
| `rolling-check-profile`, `rolling-check-task` | authors, by hand; the pen runs the same checks as it writes | The learner's files' shape against the spec. |
| `rolling-close-task` | `done` | Removes `task.md`, `reference.md`, `reference.patch`, `held/`, nothing else. |
| `rolling-write task\|profile\|reference\|patch` | `start`, `next`, `done` | The tutor's pen: the file on standard input, checked (a task or profile with faults is refused and nothing lands), written. A task gets the tutor's session id stamped in, from the open task or the `session` file, whatever the text said. The data directory is a path Claude Code protects from Edit and Write, and a granted script is not prompted. `rolling-write patch --from-tree <path>…` takes the patch as the diff of those files against HEAD (a new file included) and restores them, since a heredoc carrying code trips the Bash tool's obfuscation check; each path names one file, no glob or pathspec magic. |
| `rolling-note <lesson>` | every skill | Appends an evidence entry, under today's date; the entry must open with its kind (`**Route.**`, `**Observation.**`, `**Intervention.**`, `**Feedback.**`). |
| `rolling-keep-task` | `next` | Copies the open task, minus the five lines that belong to one run (`branch`, `base`, `return-to`, `started`, `tutor-session`), to `tasks/<lesson>/<stamp>.md` for a later session. |
| `rolling-export <dir>` | the learner | Copies the learner's directory somewhere safe. |

Scripts a skill runs inline always exit 0 and report in words, because
a non-zero inline exit aborts the skill. Scripts a skill runs as an
action (`begin-task`, `end-task`, the checks, `export`, `write`,
`note`, `keep-task`) exit non-zero
on refusal.

## Tests

```sh
cd plugins/rolling/tests && python3 -m unittest discover -s . -p 'test_*.py'
```

Each test builds a scratch repository with a small map and a fix in
its history under a temporary directory, points `ROLLING_DATA` at
another, and runs the commands against that (`support.py`). Nothing
touches a real checkout or a real data directory. To run one command
by hand outside a session, set `ROLLING_DATA` yourself.

The floor is Python 3.9, the one a Mac's command line tools ship. CI
runs the suite on 3.9 and on a Mac; to check the floor on a Linux
host, the `python:3.9-alpine` image does it:

```sh
docker run --rm -v "$PWD/plugins:/w/plugins:ro" -w /w python:3.9-alpine sh -c '
  apk add --no-cache -q git; cp -R /w/plugins /tmp/plugins; export HOME=/tmp
  git config --global user.email t@x; git config --global user.name t
  cd /tmp/plugins/rolling/tests && python3 -m unittest discover -s . -p "test_*.py"'
```

## Hooks

`hooks/hooks.json` registers two handlers, both Python in `bin/`:

- **SessionStart** runs `rolling-session-start`, which exports the
  plugin's data directory into the session's environment (above).
- **PreToolUse** on Edit, Write, MultiEdit, and NotebookEdit runs
  `rolling-guard`, the `write`-mode scope guard: while a `write` task
  is open and the session is the tutor's, an edit inside the task's
  `scope:` is denied with a reason, unless the path is one the task
  marks `scaffold:`. The repository is found from the edited path,
  never from the session's working directory, which follows every
  `cd`; the path is judged as written and with every symbolic link
  resolved, so a checkout reached through a link (on a Mac, anything
  under the temporary directory) and a link pointing into the scope
  are both caught. Any other session, mode, path, or
  state is allowed, including anything the handler cannot make sense of; the
  rule that must hold when the learner asks nicely is held by this
  hook, not by prose, and it holds in every permission mode.
