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

Two public codebases have maps today. [Homie](https://github.com/kurowski/homie)
has built-in support: its map is committed in its own tree, so Claude Code can
run `/rolling:start` right out of the box on a fresh Homie clone.
We also support [Rallly](https://github.com/lukevella/rallly) as a demo of
external support: its map ships as the `rallly` plugin in this marketplace.
Clone Rallly then [install](https://rollingstart.dev/#install) Rolling Start's Rallly plugin.
