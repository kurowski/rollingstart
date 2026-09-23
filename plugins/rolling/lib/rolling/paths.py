"""Where things are.

The map is at <repo>/.rolling. The learner's directory is
$ROLLING_DATA/repos/<encoded top level>: the plugin's SessionStart hook
exports ROLLING_DATA from ${CLAUDE_PLUGIN_DATA}, which Claude Code
substitutes into hook commands but never puts in the Bash tool's
environment. Tests set ROLLING_DATA to a temporary directory. The
encoding is the one Claude Code uses for its own project directories:
every byte that is not an ASCII letter or digit becomes '-'.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

NO_DATA_MSG = (
    "the learner directory cannot be resolved: ROLLING_DATA is not set. "
    "The plugin sets it when a session starts, so a plugin installed or "
    "reloaded during this session has not had its session start yet: "
    "tell the learner to run /clear (or restart Claude Code) and try again. "
    "A script run outside a session needs it set by hand."
)


def toplevel(cwd: Optional[Path] = None) -> Optional[Path]:
    """The repository's top level as git reports it, or None outside one."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return Path(out.stdout.strip())


MAP_DIR = ".rolling"   # the one place the map's name in the tree is spelled


def map_dir(top: Path) -> Path:
    return top / MAP_DIR


def encode(path: str) -> str:
    return "".join(
        chr(b) if (48 <= b <= 57 or 65 <= b <= 90 or 97 <= b <= 122) else "-"
        for b in path.encode("utf-8", "surrogateescape")
    )


def learner_dir_in(data: Path, top: Path) -> Path:
    """The learner's directory for the repository at top, under the
    plugin's data directory: the one place this layout is spelled."""
    return data / "repos" / encode(str(top))


def learner_dir(top: Path) -> Optional[Path]:
    """The learner's directory for the repository at top, or None when
    ROLLING_DATA is unset; the caller says so in NO_DATA_MSG's words."""
    data = os.environ.get("ROLLING_DATA", "")
    return learner_dir_in(Path(data), top) if data else None
