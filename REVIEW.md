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

## Python and hook specifics

- Python 3.9, standard library only; nothing a 3.9 interpreter would
  refuse. `subprocess` gets an argument list, never a string and never
  `shell=True`; the one place a shell runs is the map's own declared
  command, with the task's arguments appended as separate argv words.
- Paths and arguments from the model (a task's `scope`, a `verify:`
  line's arguments, a `held:` path) are untrusted input: checked by
  `rules` before use, refused rather than sanitised.
- Anything that changes the learner's tree is written so that a kill
  at any point leaves either the original or a recorded copy: record
  the step, then take it; copy in full, then rename; `try`/`finally`
  around the apply and revert, with the record on disk for the kill
  no `finally` sees.
- Git operations are explicit about which ref, which paths, and which
  tree, through the `Repo` wrapper. Everything that can be refused is
  checked before anything is written, so a refusal never leaves the
  repository half-way.
- A hook handler never blocks the session on its own failure: it exits
  0 with no output on anything it did not understand, and expresses a
  decision only in the documented JSON shape.
- Logic returns structured results (faults, a report) and rendering is
  separate, so the tests assert on objects and only the skill-facing
  lines are string contracts.
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
  `../rallly`, not `../rallly-spike`. The scratch world in
  `tests/support.py` is the only fixture.

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
