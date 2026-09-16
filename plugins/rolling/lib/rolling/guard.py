"""The write-mode scope guard: the one rule that must hold when the
learner asks nicely.

A PreToolUse hook on Edit, Write, MultiEdit, and NotebookEdit. While a
`write` task is open and the session is the tutor's, an edit inside the
task's scope is denied, except at a scaffold path, where the tutor may
leave TODO(human) markers the way the built-in Learning output style
does. Everything else is allowed: another tool, another session, a
`direct` task, no task, a path outside every scope, and anything the
handler cannot make sense of. A hook that blocks the session on its
own failure would be worse than no hook, so the answer to any doubt is
to allow.

The repository is found from the edited path, never from the session's
working directory: the hook's cwd follows every `cd` the tutor runs,
and a guard keyed on it is off after one. Each ancestor of the path is
tried as a repository top; the one with an open write task for this
session is the one. The learner's directory is keyed by the top as git
spells it, so that lookup needs no git at all.

Two spellings of the edited path are judged, and either inside the
scope denies: the path as the tool was given it, and the path with
every symbolic link resolved. The first catches a link inside the
scope pointing out (the scope names paths, whatever the inode); the
second catches a checkout reached through a link, which on a Mac is
anything under the temporary directory, and a link outside the scope
pointing in. On a case-folding filesystem, judged at the repository
top, the lookup and the comparison both fold case. Unicode
normalisation is not folded: a scope spelled with non-ASCII letters
matches only its own spelling, and a Mac's default volume would accept
the other one.

What the hook does not hold: a write through Bash (`sed -i`, a
redirection) and an edit of the task file the tutor itself keeps in
the data directory. Those are the skills' prose to forbid and the
evals' to measure (P2); this hook is the four editing tools.

Claude Code hands the handler the event as JSON on stdin (session_id,
cwd, tool_name, tool_input with file_path or notebook_path) and the
plugin's data directory as an argument, substituted from
${CLAUDE_PLUGIN_DATA} in hooks.json. A decision is the documented JSON
on stdout; allowing is silence.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional

from . import paths, rules
from .model import Learner, Task

GUARDED_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


@dataclass
class Event:
    session_id: str
    cwd: Path
    tool: str
    path: str   # as the tool was given it; absolute or relative to cwd


@dataclass
class Placement:
    """The edited path seen from one repository that has a task for this
    session: the top as the path spelled it, the path beneath it."""
    top: Path
    rel: str
    task: Task
    fold: bool


def parse_event(text: str) -> Optional[Event]:
    try:
        ev = json.loads(text)
    except ValueError:
        return None
    if not isinstance(ev, dict):
        return None
    ti = ev.get("tool_input")
    if not isinstance(ti, dict):
        return None
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    if not isinstance(path, str) or not path:
        return None
    return Event(
        session_id=str(ev.get("session_id") or ""),
        cwd=Path(str(ev.get("cwd") or os.getcwd())),
        tool=str(ev.get("tool_name") or ""),
        path=path,
    )


def spellings(path: str, cwd: Path) -> List[Path]:
    """The edited path, absolute, as given and with every link resolved."""
    given = Path(path) if os.path.isabs(path) else cwd / path
    # normpath keeps a leading `//` (POSIX lets it mean something), and
    # nothing here does; one slash, so the ancestors are the real ones.
    lexical = "/" + os.path.normpath(given).lstrip("/")
    return list(dict.fromkeys([Path(lexical), Path(os.path.realpath(given))]))


def folds_case(top: Path) -> bool:
    """Does the filesystem at a repository top fold case? Every repository
    has a .git entry; if the upper-cased name is the same entry, it folds.
    (A decoy directory named .GIT is another entry and does not count.)"""
    try:
        return os.path.samefile(top / ".git", top / ".GIT")
    except (OSError, ValueError):   # missing, or a NUL in the path
        return False


def learner_name(top: Path, names: List[str], fold: bool) -> Optional[str]:
    """The learner directory keyed by this top, among those that exist.
    On a case-folding filesystem the tool may spell the top in any case
    and git spelled it in one, so there the match folds too."""
    enc = paths.encode(str(top))
    if enc in names:
        return enc
    if fold:
        return next((n for n in names if n.lower() == enc.lower()), None)
    return None


def placements(ev: Event, data: Path) -> Iterator[Placement]:
    """Every (repository, relative path) the edit could be, for a
    repository with an open write task belonging to this session."""
    try:
        names = os.listdir(data / "repos")
    except OSError:
        return
    for spelled in spellings(ev.path, ev.cwd):
        for top in spelled.parents:
            fold = folds_case(top)
            name = learner_name(top, names, fold)
            if name is None:
                continue
            task = Learner(data / "repos" / name).task()
            if task is None or task.mode != "write" or task.tutor_session != ev.session_id:
                continue
            yield Placement(top, spelled.relative_to(top).as_posix(), task, fold)


def judge(p: Placement) -> Optional[str]:
    """The reason to deny this placement, or None. A scaffold names files
    exactly (a directory scaffold would exempt the whole scope beneath
    it); a scope covers everything beneath what it names."""
    scaffolds = [s for s in map(rules.normalize_scope, p.task.scaffold) if s]
    if any(rules.names_path(p.rel, s, p.fold) for s in scaffolds):
        return None
    scopes = [s for s in map(rules.normalize_scope, p.task.scope) if s]
    matched = [s for s in scopes if rules.inside_scope(p.rel, s, p.fold)]
    if not matched:
        return None
    return (
        f"{p.rel} is the learner's to write in this lesson (it is under {', '.join(matched)}). "
        "Point at the file and line, explain the convention and where the repo follows it, or "
        "ask a question. The only place you may write is a file the task lets you scaffold, "
        "and only TODO(human) markers there."
    )


def decide(ev: Event, data_dir: str) -> Optional[str]:
    """The reason to deny, or None to allow. A scaffold match on one
    spelling does not excuse a scope match on another, so every
    placement is judged."""
    if ev.tool not in GUARDED_TOOLS or not data_dir or not ev.session_id:
        return None
    for p in placements(ev, Path(data_dir)):
        reason = judge(p)
        if reason:
            return reason
    return None


def main(argv: List[str]) -> int:
    """Read the event, decide, print a denial if any. Never fails: any
    surprise is an allow."""
    try:
        ev = parse_event(sys.stdin.read())
        if ev is None:
            return 0
        reason = decide(ev, argv[0] if argv else "")
        if reason:
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }))
    except Exception:  # noqa: BLE001  a hook must not block the session on its own failure
        pass
    return 0
