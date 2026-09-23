<p align="center"><img src="docs/rollingstart-logo-white.png" alt="Rolling Start" width="150"></p>

# Rolling Start

A Claude Code native codebase tutor. An author describes the landscape
of a codebase, a learner picks a destination, and the tutor, running as
a Claude Code plugin, points the way: one task at a time, with feedback
on real work in the learner's own working copy.

The learner's plugin, `rolling`, runs `write` lessons end to end on a
Rallly clone: the marketplace at the repository root, the four skills,
the toolkit, the write-mode guard, and a ten-lesson map (P1a, done).
`direct` mode and distribution as map plugins are next. The plan is in
[`docs/plan.md`](docs/plan.md); the checkpoint's record is in
[`docs/plans/p1a-write-mode.md`](docs/plans/p1a-write-mode.md).

Two codebases have maps today. [Rallly](https://github.com/lukevella/rallly)
is the demo: its map ships as the `rallly` plugin in this marketplace,
for any Rallly clone. [Homie](https://github.com/kurowski/homie) has
built-in support: its map is committed in its own tree, so a Homie
clone needs only `rolling`.

The [original conception](https://github.com/kurowski/rollingstop), a
deterministic Go harness, is archived; the plan says what it got wrong
and what carries over.

Apache-2.0.
