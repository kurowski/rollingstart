"""Session identity: which session is the tutor's, and how the toolkit
learns where the learner's directory is.
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import List, Optional

from . import frontmatter as fm
from .model import Learner

_SESSION_ID = re.compile(r"^[A-Za-z0-9-]+$")


def is_session_id(s: str) -> bool:
    return _SESSION_ID.match(s or "") is not None


def claim(learner: Learner, session_id: str) -> str:
    """Record SESSION_ID as the tutor's: in the `session` file always,
    and in the open task's tutor-session line as well when a task is
    open (added if missing; the rewrite is a temporary file and a
    rename). Returns the line to print; never raises.

    The file is written even while a task is open, because a reader can
    need it with no task to read. Resuming a parked task learns the
    running session from the file and stamps it into the task it
    reopens; a file left naming an older session would stamp that,
    and the write guard fires only for a task stamped with the session
    that is running. Keeping the file current costs one write and keeps
    the guard aimed at the session the learner is talking to."""
    if not is_session_id(session_id):
        return "SESSION: not recorded (no session id, or one with characters outside [A-Za-z0-9-])"
    try:
        learner.dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return f"SESSION: not recorded (cannot create {learner.dir})"
    # The open task's line first, because that is the one the write
    # guard reads: a `session` file that cannot be written must not cost
    # the stamp. Then the file, in every case, for the readers that run
    # when no task is open.
    task = learner.task_file
    text: Optional[str] = None
    if task.is_file():
        try:
            text = task.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError:
            text = None
    open_task = text is not None and fm.has_block(text)
    problems: List[str] = []
    stamped_task = False
    if open_task:
        try:
            tmp = task.with_name(".task.md.tmp")
            tmp.write_text(stamped(text or "", session_id), encoding="utf-8", errors="surrogateescape")
            os.replace(tmp, task)
            stamped_task = True
        except OSError:
            problems.append(f"could not rewrite {task}")
    file_ok = True
    file_problem = ""
    try:
        learner.session.write_text(session_id + "\n", encoding="utf-8")
    except OSError:
        file_ok = False
        file_problem = f"could not write {learner.session}"
        problems.append(file_problem)
    # What counts as recorded is the open task's line when a task is
    # open, because that is the one the guard reads, and the file when
    # none is.
    if not (stamped_task if open_task else file_ok):
        return f"SESSION: not recorded ({'; '.join(problems)})"
    where = "recorded in the open task" if open_task else "no task open"
    # Not "a resume will refuse": the file keeps whatever it held, and a
    # resume stamps what it reads there. Say the truth, which the tutor
    # can act on, rather than a protection that is not there.
    note = "" if file_ok else (
        f"; {file_problem}, so it still names whatever it named before — a parked task resumed now would carry that, "
        "and the write guard would not fire for this session"
    )
    return f"SESSION: {session_id} is the tutor ({where}){note}"


def stamped(text: str, session_id: str) -> str:
    """TEXT with SESSION_ID as its tutor-session line: replacing the one
    it has, or added at the end of the frontmatter."""
    return fm.with_field(text, "tutor-session", session_id)


def recorded(learner: Learner) -> str:
    """The tutor's session as the learner's directory records it: the
    open task's line while a task is open (claim keeps that one fresh),
    else the `session` file. '' when neither holds a valid id. One
    reading for every caller, since a second would drift."""
    task = learner.task()
    candidate = task.tutor_session if task is not None and task.tutor_session else _session_file(learner)
    return candidate if is_session_id(candidate) else ""


def _session_file(learner: Learner) -> str:
    try:
        return learner.session.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


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

