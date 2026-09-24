#!/usr/bin/env python3
"""Refuse a pull request that changes a plugin without bumping its version.

A plugin with a version is pinned to it: `/plugin update` offers an
installed learner a new copy only when the version in the plugin's
`.claude-plugin/plugin.json` differs from the one they have. A change
merged without a bump therefore never reaches anyone who installed
before it, and nothing says so. `rolling` sat at 0.1.0 through the whole
of P1b that way, and this check is how it cannot happen again.

For every plugin directory under `plugins/` that the pull request
changes, outside its `tests/` (which no learner runs), the version at
HEAD must differ from the version on the base branch. A plugin that
does not exist on the base branch is new and needs no bump. Run from
the repository root with the base ref as the argument:

    python3 .github/scripts/check-plugin-versions.py origin/main

Exits 1 and names each offending plugin, 0 otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Dict, List, Optional


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def version_at(ref: str, plugin: str) -> Optional[str]:
    """The plugin's version at REF, or None when the plugin is not there."""
    path = f"plugins/{plugin}/.claude-plugin/plugin.json"
    shown = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    if shown.returncode != 0:
        return None
    return json.loads(shown.stdout).get("version")


def changed_plugins(base: str) -> List[str]:
    """Plugins with a change outside tests/ between the merge base and HEAD.

    Renames are listed as a deletion and an addition, so a file moved
    into tests/ or into another plugin still counts against the plugin
    it left; with rename detection, git names only the new path."""
    names = git("diff", "--name-only", "--no-renames", f"{base}...HEAD", "--", "plugins/").split()
    touched: Dict[str, bool] = {}
    for name in names:
        parts = name.split("/")
        if len(parts) < 3 or parts[2] == "tests":
            continue
        touched[parts[1]] = True
    return sorted(touched)


def main(argv: List[str]) -> int:
    if len(argv) != 1:
        print("usage: check-plugin-versions.py <base-ref>", file=sys.stderr)
        return 2
    base = argv[0]
    merge_base = git("merge-base", base, "HEAD").strip()
    stale = []
    for plugin in changed_plugins(base):
        before = version_at(merge_base, plugin)
        if before is None:
            print(f"{plugin}: new plugin, no bump needed")
            continue
        after = version_at("HEAD", plugin)
        if after is None:
            print(f"{plugin}: removed")
        elif after == before:
            stale.append(plugin)
            print(f"{plugin}: changed, but its version is still {before}")
        else:
            print(f"{plugin}: {before} -> {after}")
    if stale:
        print(
            "Bump the version in plugins/<name>/.claude-plugin/plugin.json for: "
            + ", ".join(stale)
            + ". Without a bump, /plugin update never offers the change to a learner who"
            " already installed the plugin (CLAUDE.md, Conventions).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
