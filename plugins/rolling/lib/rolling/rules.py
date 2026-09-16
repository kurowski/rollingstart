"""The small rules the specs state and every module leans on: what a
slug is, what an argument may contain, what a path may look like, and
when a map command can safely have a task's arguments appended to it.
Pure functions over strings and paths; no I/O beyond a stat.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

DEPTHS = ("orientation", "working", "deep")
MODES = ("write", "direct")
TESTS = ("held", "shown")

_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_KEY = re.compile(r"^[a-z0-9-]+$")
_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_SHELL_META = frozenset("$`;&|<>(){}\\\"'*?[")
_TRAILING_OPERATORS = frozenset(";&|><\\")


def is_slug(s: str) -> bool:
    """Lowercase kebab-case: the one spelling that survives a
    case-folding filesystem."""
    return bool(_SLUG.match(s))


def is_key(s: str) -> bool:
    return bool(_KEY.match(s))


def is_sha(s: str) -> bool:
    return bool(_SHA.match(s))


def is_date(s: str) -> bool:
    return bool(_DATE.match(s))


def args_are_words(args: str) -> bool:
    """Arguments on a verify line are words separated by single spaces
    and nothing else: no shell metacharacter, glob, quote, or control
    character, and no run of spaces, since a path with a space in it
    cannot be expressed and an extra space would become an empty word.
    The model writes them, and they must not become a way to run shell."""
    if any(c in _SHELL_META or ord(c) < 32 or ord(c) == 127 for c in args):
        return False
    return args == " ".join(args.split(" ")) and not args.startswith(" ") and not args.endswith(" ") and "  " not in args


def words(args: str) -> List[str]:
    """The argv words of a line's arguments that passed args_are_words."""
    return args.split(" ") if args else []


def is_plain_relpath(p: str) -> bool:
    """A repository-relative path spelled one way: no leading slash, no
    `.` or `..` segment, no empty segment (so no `./`, no `//`)."""
    return p != "" and not p.startswith("/") and all(seg not in ("", ".", "..") for seg in p.split("/"))


def command_takes_args(cmd: str) -> bool:
    """A map command may have arguments appended after it only if it does
    not end in an operator (; & | > < \\) and contains no '#': either would
    turn the appended words into something other than arguments."""
    c = cmd.rstrip(" \t")
    return c != "" and "#" not in c and c[-1] not in _TRAILING_OPERATORS


def normalize_scope(scope: str) -> str:
    """A scope line as written by the model, made comparable: no leading
    `./`, no trailing `/`, no doubled `/`. Anything that is not a plain
    repository-relative path afterwards is '' and guards nothing; the
    validator reports it."""
    raw = scope.strip()
    if raw.startswith("/") or ".." in raw.split("/"):
        return ""
    s = "/".join(seg for seg in raw.split("/") if seg not in ("", "."))
    return s if s and is_plain_relpath(s) else ""


def inside_scope(path: str, scope: str, fold_case: bool = False) -> bool:
    """Is PATH (repository-relative) inside SCOPE: equal to it, beneath it
    as a directory, matching it as a glob, or beneath a directory the glob
    names. In a glob `*` and `?` stay within one path segment and a
    segment that is exactly `**` spans any number of segments, zero
    included (elsewhere `**` is `*`, as in gitignore). With fold_case the
    comparison ignores case, for a filesystem that does."""
    return _glob_match(scope, path, fold_case, prefix=True)


def names_path(path: str, glob: str, fold_case: bool = False) -> bool:
    """Does GLOB name PATH exactly: equal to it, or matching it as a glob.
    Nothing beneath a directory the glob names; that is inside_scope."""
    return _glob_match(glob, path, fold_case, prefix=False)


def _glob_match(glob: str, path: str, fold_case: bool, prefix: bool) -> bool:
    # Matched segment by segment with a table, never a regex: a glob is
    # the model's text, and `src/**a**a**a...` as a regex backtracks
    # until the hook times out. Every step here is bounded by the
    # lengths. With prefix, the glob may stop at any segment boundary of
    # the path and what follows is beneath it.
    if fold_case:   # casefold, not lower: it folds the letters a Mac's volume folds (ſ, ς)
        glob, path = glob.casefold(), path.casefold()
    pats, segs = glob.split("/"), path.split("/")
    # reach[j]: the glob so far can consume exactly the first j segments
    reach = [True] + [False] * len(segs)
    for pat in pats:
        if pat == "**":
            for j in range(1, len(segs) + 1):
                reach[j] = reach[j] or reach[j - 1]
        else:
            reach = [False] + [reach[j - 1] and _segment_match(pat, segs[j - 1]) for j in range(1, len(segs) + 1)]
    return any(reach) if prefix else reach[-1]


def _segment_match(pat: str, seg: str) -> bool:
    """One segment against a pattern of literals, `?` and `*`."""
    # reach[j]: the pattern so far can consume exactly the first j characters
    reach = [True] + [False] * len(seg)
    for c in pat:
        if c == "*":
            for j in range(1, len(seg) + 1):
                reach[j] = reach[j] or reach[j - 1]
        else:
            reach = [False] + [reach[j - 1] and (c == "?" or c == seg[j - 1]) for j in range(1, len(seg) + 1)]
    return reach[-1]


def has_symlink_component(top: Path, relpath: str) -> bool:
    """Is any component of RELPATH under TOP, the last included, a
    symbolic link? The held test is applied and reverted through this
    path; a link anywhere in it could write outside the repository or
    lose the file the link stood for."""
    cur = top
    for seg in relpath.split("/"):
        if seg:
            cur = cur / seg
            if cur.is_symlink():
                return True
    return False
