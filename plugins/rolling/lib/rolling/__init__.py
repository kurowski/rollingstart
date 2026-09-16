"""The rolling plugin's toolkit.

Python 3.9 or later, standard library only: that is what a Mac with the
command line tools and any desktop Linux already have, and the plugin
must not ask a learner to install a runtime first. Nothing here knows
about any particular codebase; the map knows everything about one.

Modules: rules (what a slug, an argument, a path may be), frontmatter
(the flat subset docs/map.md defines), model (the map, lessons, task,
and learner's directory as objects), validate (the three checkers,
returning faults), guard (the write-mode scope guard, a PreToolUse
hook handler), paths (where the map and the learner's directory
are), repo (git behind a small wrapper), heldtest (the held test's
apply and revert, with the record that survives a kill), verifier (a
structured report and its rendering), diff, tasks (begin, end, close,
and every refusal), session, and cli (the commands the bin/ executables
dispatch to).
"""

from __future__ import annotations

__all__ = ["rules", "frontmatter", "model", "validate", "guard", "paths", "repo", "heldtest", "verifier", "diff", "tasks", "session", "cli"]
