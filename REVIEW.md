# Review guidelines

What reviewers check, human or agent. Read this before opening a PR;
knowing the criteria up front is cheaper than learning them in review.

## Correctness first

- Does it do what the issue said? Check the acceptance criteria
  explicitly.
- Are the failure paths handled, or only the happy one? The scripts run
  other people's commands in repositories and environments they do not
  control; failure is the common case, not the edge.
- Are errors actionable? "verifier failed" tells a learner nothing.
  Name what ran, what it exited with, and what they can do.
- Does a script a skill runs inline always exit 0? A non-zero exit
  aborts the skill. Does it report absence in words rather than
  silence?

## Scope

- One issue, one PR. A diff spanning a spec, the toolkit, and the
  skills at once should have been a stack.
- Did in-flight additions pass the three tests in
  [`docs/workflow.md`](docs/workflow.md)? If not, they belong in a
  follow-up.
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

- POSIX `sh`, no bashisms: `[ ]` not `[[ ]]`, no arrays, no `local`
  relied on, no `pipefail`. `shellcheck` clean.
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

- User-visible behaviour changed → the docs describing it changed in
  the same PR. For the formats, that is `docs/map.md` or
  `docs/profile.md`; for a skill, its own description and the workflow
  it is part of.
- A decision meeting the ADR threshold got an ADR.
- Comments explain why, not what. Match the density of the surrounding
  code.
- Roles are Author, Tutor, Learner. No employer codebase, no character
  names.

## Commit history

- Bodies explain the reasoning, not just the change. This repository is
  meant to become an instance of its own tool.
- No `wip`, no `fix typo` chains that should have been squashed before
  pushing.
