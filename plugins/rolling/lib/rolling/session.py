"""Session identity: which session is the tutor's, and how the toolkit
learns where the learner's directory is.
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Optional

from . import frontmatter as fm
from .model import Learner

_SESSION_ID = re.compile(r"^[A-Za-z0-9-]+$")


def is_session_id(s: str) -> bool:
    return _SESSION_ID.match(s or "") is not None


def claim(learner: Learner, session_id: str) -> str:
    """Record SESSION_ID as the tutor's: in the open task's tutor-session
    line when a task is open (added if missing; the rewrite is a
    temporary file and a rename), else in the `session` file. Returns
    the line to print; never raises."""
    if not is_session_id(session_id):
        return "SESSION: not recorded (no session id, or one with characters outside [A-Za-z0-9-])"
    try:
        learner.dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return f"SESSION: not recorded (cannot create {learner.dir})"
    task = learner.task_file
    text: Optional[str] = None
    if task.is_file():
        try:
            text = task.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError:
            text = None
    if text is not None and fm.has_block(text):
        try:
            tmp = task.with_name(".task.md.tmp")
            tmp.write_text(stamped(text, session_id), encoding="utf-8", errors="surrogateescape")
            os.replace(tmp, task)
        except OSError:
            return f"SESSION: not recorded (could not rewrite {task})"
        return f"SESSION: {session_id} is the tutor (recorded in the open task)"
    try:
        learner.session.write_text(session_id + "\n", encoding="utf-8")
    except OSError:
        return f"SESSION: not recorded (could not write {learner.session})"
    return f"SESSION: {session_id} is the tutor (no task open)"


def stamped(text: str, session_id: str) -> str:
    """TEXT with SESSION_ID as its tutor-session line: replacing the one
    it has, or added at the end of the frontmatter."""
    lines = text.split("\n")
    out = [lines[0]]
    seen = closed = False
    for line in lines[1:]:
        bare = line.rstrip("\r")
        if not closed and bare.startswith("tutor-session:"):
            out.append(f"tutor-session: {session_id}")
            seen = True
            continue
        if not closed and bare == "---":
            if not seen:
                out.append(f"tutor-session: {session_id}")
            closed = True
        out.append(line)
    return "\n".join(out)


def export_data_dir(data_dir: str, env_file: Optional[str]) -> None:
    """The SessionStart hook's work: hand ${CLAUDE_PLUGIN_DATA}, which
    Claude Code substitutes into the hook command but never puts in the
    Bash tool's environment, to every later Bash command through the
    session environment file it sources first. Written once; the hook
    also fires on resume, clear, and compact."""
    if not data_dir or not env_file:
        return
    line = "export ROLLING_DATA=" + shlex.quote(data_dir)
    p = Path(env_file)
    try:
        existing = p.read_text(encoding="utf-8").split("\n") if p.is_file() else []
        if line not in existing:
            with open(p, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        pass

