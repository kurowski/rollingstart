<p align="center"><img src="docs/rollingstart-logo-white.png" alt="Rolling Start" width="150"></p>

# Rolling Start

A Claude Code native codebase tutor. An author describes the landscape
of a codebase, a learner picks a destination, and the tutor, running as
a Claude Code plugin, points the way: one task at a time, with feedback
on real work in the learner's own working copy.

The learner's plugin, `rolling`, runs `write` lessons end to end: intake,
a route through the author's map, a walkthrough, an exercise built from
the repository's own history and proved before it is served, and
feedback against the lesson's rubric (P1a). A map lives in a project's
own tree, or ships as a map plugin for a repository its author does not
own, and the tutor finds either (P1b). Next is P2, enforcement and
evals; `direct` mode is 2.0. The plan is in
[`docs/plan.md`](docs/plan.md), and each checkpoint's record is in
[`docs/plans/`](docs/plans/).

Two public codebases have maps today. [Homie](https://github.com/kurowski/homie)
has built-in support: its map is committed in its own tree, so Claude Code can
run `/rolling:start` right out of the box on a fresh Homie clone.
We also support [Rallly](https://github.com/lukevella/rallly) as a demo of
external support: its map ships as the `rallly` plugin in this marketplace.
Clone Rallly then [install](https://rollingstart.dev/#install) Rolling Start's Rallly plugin.
