# Review guidelines

What reviewers check, human or agent. Read this before opening a PR;
knowing the criteria up front is cheaper than learning them in review.

## Correctness first

- Does it do what the sub-scope in the checkpoint plan says? Check its
  "done when" explicitly.
- Are the failure paths handled, or only the happy one? The scripts run
  other people's commands in repositories and environments they do not
  control; failure is the common case, not the edge.
- Are errors actionable? "verifier failed" tells a learner nothing.
  Name what ran, what it exited with, and what they can do.
- Does a script a skill runs inline always exit 0? A non-zero exit
  aborts the skill. Does it report absence in words rather than
  silence?

## Scope

- One change, one PR. A diff spanning a spec, the toolkit, and the
  skills at once should have been a stack.
- Claims about a target's code (`examples/*`, the map plugins) are
  cited by path and pin against the checkout named in that example's
  README. If that checkout is on this machine, read it and check them;
  if it is not, review the shape and the reasoning, and do not report
  the missing checkout as a finding.

## The architectural seams

These are the ones worth blocking a PR over, because they are expensive
to recover once crossed. Each is a rule in [`CLAUDE.md`](CLAUDE.md) and
a row of the enforcement table in [`docs/plan.md`](docs/plan.md) § 5.

- **The plugin knows nothing about any codebase.** A package manager, a
  framework, a path, a domain in `plugins/rolling/` belongs in a map.
- **The tutor does not orchestrate environments.** No docker, no service
  lifecycle, no toolchain installation, no fixing the learner's setup.
- **Verifiers are structured, never shell.** Declared commands and held
  test files, resolved by `verify`; arguments are words.
- **Nothing the tutor writes goes in the learner's tree.**
- **Rules that must hold are held by hooks or scripts, in every
  permission mode.** Prose is the first line, never the only one. No
  wildcard grants; nothing that depends on `auto` or on manual mode.
- **No fourth wall.** A skill that has the tutor cite a script, a task
  file, or a profile file to the learner is wrong. The learner's checks
  are the map's commands, verbatim.
- **The learner picks the destination.** `next` never edits it and
  never serves outside it.
- **The human's ledger.** In a `direct` lesson the verifier's findings
  come off the table before the learner's direction and review are
  read, and a catch the tutor prompted is the tutor's.

## Shell and hook specifics

- Bash 3.2 or later, nothing newer: no associative arrays, no
  `mapfile`, no `${var,,}`; a stock Mac has to run it. `shellcheck
  --shell=bash` clean.
- A command line assembled from a task file is built as an array and
  expanded as `"${args[@]}"`, never re-parsed by `sh -c` or word-split
  from a string; that is the reason the scripts are bash.
- `set -u` everywhere; `set -e` only in scripts a skill runs as an
  action, never in one it runs inline.
- Every variable that reaches a command line is quoted, and every
  argument that came from a task file is checked against the
  metacharacter list before it goes anywhere near `sh -c`.
- Paths from the model (a task's `scope`, a `verify:` line's arguments)
  are treated as untrusted input, because the model wrote them.
- Git operations are explicit about which ref, which paths, and which
  tree. A script that switches branches checks the tree is clean first
  and says what it refused.
- A hook handler never blocks the session on its own failure: it exits
  0 with no output on anything it did not understand, and expresses a
  decision only in the documented JSON shape.
- A skill's `allowed-tools` grants exactly what its instructions call
  for, by name. A grant that would pre-approve a destructive command
  is a finding.

## Tests

- Does the test fail without the change? If not, it isn't testing the
  change.
- Are the assertions about behaviour, or about implementation detail
  that will break on the next refactor?
- Subprocess, filesystem, and git behaviour needs real coverage in a
  scratch repository. That is this tool's actual job, not an incidental
  detail.
- A test never touches a real checkout: not this repository, not
  `../rallly`, not `../rallly-spike`.

## Documentation

- A format changed → `docs/map.md` or `docs/profile.md` changed in the
  same PR. A skill's behaviour changed → its `SKILL.md` says so, and
  the run that checked it is in the checkpoint plan.
- A decision that would have to be re-derived if forgotten is in
  `docs/plan.md` § 10, dated, or in the commit body if it is smaller
  than that.
- Comments explain why, not what. Match the density of the surrounding
  code.
- Roles are Author, Tutor, Learner. No employer codebase, no character
  names.

## Commit history

- Bodies explain the reasoning, not just the change. This repository is
  meant to become an instance of its own tool.
- No `wip`, no `fix typo` chains that should have been squashed before
  pushing.
