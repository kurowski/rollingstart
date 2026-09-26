"""Citations in the tutor's words, checked against the working tree.

The tutor cites code as `path:line` (or `path:12-20`), and the learner
is never to be left with one that points nowhere. The Stop hook
(reply.py) runs this on each of the tutor's replies before the learner
can answer, and when something is flagged has the tutor correct or
withdraw it in the same turn. It flags and never refuses.

What counts as a citation: a path followed by a colon and a line
number, where the path has a directory separator or ends in an
extension, contains a letter, and starts at a word boundary (so the
port in `http://localhost:3000` and a time like `12:30` are not ones).
A column after the line (`path:12:5`) is ignored; a range is checked
at its end.

What counts as pointing somewhere: a file in the working tree, inside
the repository, with at least that many lines. A bare file name
(`invoice.py:14`) is found if any file of that name in the repository,
at the top or below it, tracked or untracked and not ignored, has the
line; a path the tree does not have as written is looked for below a
directory it may have left out (`src/x.ts:9` for `apps/web/src/x.ts`).
And a path is only called missing when it could have been one: a path
whose first directory the tree does not have
(`docker.io/library/python:3`) and a bare name no file carries
(`self.total:5`, `db.example.com:5432`) are taken for something other
than a file and pass silently. That is looser than it could be, on
purpose: a false flag the tutor then "corrects" is its own dishonesty,
so when in doubt this says nothing, and a citation invented whole is
left to the eval.

What it cannot tell is whether the line says what the tutor claims.
That is the eval's to measure, not a script's.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .repo import Repo

_CITE = re.compile(
    r"(?<![\w./:@+-])"
    r"((?:[\w.@+-]+/)*[\w@+-][\w.@+-]*\.\w+|(?:[\w.@+-]+/)+[\w@+-][\w.@+-]*)"
    r":(\d+)(?:[-–](\d+))?"
)


@dataclass(frozen=True)
class Citation:
    path: str
    first: int
    last: int

    def __str__(self) -> str:
        return f"{self.path}:{self.first}" + (f"-{self.last}" if self.last != self.first else "")


def find(text: str) -> List[Citation]:
    """The citations in TEXT, in order, each once."""
    seen: List[Citation] = []
    for m in _CITE.finditer(text):
        path = m.group(1)
        if not re.search(r"[A-Za-z]", path):
            continue
        first = int(m.group(2))
        c = Citation(path, first, max(first, int(m.group(3))) if m.group(3) else first)
        if c not in seen:
            seen.append(c)
    return seen


def check(text: str, repo: Repo, away: Sequence[str] = ()) -> List[str]:
    """One line per citation in TEXT that points nowhere, saying why.
    AWAY names files that are rightly out of the tree just now (a held
    test between its runs); a citation of one is not judged."""
    return [f"{c} — {why}" for c, why in _verdicts(text, repo, away) if why]


def _verdicts(text: str, repo: Repo, away: Sequence[str] = ()) -> List[Tuple[Citation, Optional[str]]]:
    """Each citation in TEXT that could be a file, with why it points
    nowhere, or None when it lands. What is taken for something other
    than a file is left out."""
    top = repo.top
    files: Optional[List[str]] = None
    out: List[Tuple[Citation, Optional[str]]] = []
    for c in find(text):
        rel = posixpath.normpath(c.path)
        if rel == ".." or rel.startswith("../"):
            out.append((c, "outside the repository"))
            continue
        if any(a == rel or a.endswith("/" + rel) for a in away):
            continue
        if files is None:
            files = repo.files()
        # A bare name anywhere in the tree, the top included; a path
        # with a directory as written, or below a package directory it
        # left out (src/x.ts for apps/web/src/x.ts). A tracked file the
        # change deleted is a candidate, and is then not there.
        here = (top / rel).exists() or rel in files
        candidates = sorted({p for p in files if p.endswith("/" + rel)} | ({rel} if here else set()))
        if "/" in rel and (top / rel).exists():
            candidates = [rel]
        # Under a directory the tree has, a missing file is missing;
        # otherwise it is more likely a host, an image, or an attribute
        # (a counter at zero among them) than a file.
        could_be = bool(candidates) or ("/" in rel and (top / rel.split("/", 1)[0]).is_dir())
        if not could_be:
            continue
        if c.first == 0:
            out.append((c, "there is no line 0"))
        elif not candidates:
            out.append((c, "no such file in the working tree"))
        else:
            out.append((c, _short_of(top, candidates, c.last)))
    return out


def _short_of(top: Path, candidates: List[str], line: int) -> Optional[str]:
    """None when some candidate is a file with LINE; otherwise why not."""
    if len(candidates) == 1 and (top / candidates[0]).is_dir():
        return "a directory, not a file"
    counts = [_lines(top / p) for p in candidates if (top / p).is_file()]
    if not counts:
        return "no such file in the working tree"
    if any(line <= n for n in counts):
        return None
    if len(counts) == 1:
        return f"the file has {counts[0]} line{'' if counts[0] == 1 else 's'}"
    return f"no file of that name has that many lines (the longest of {len(counts)} has {max(counts)})"


def _lines(p: Path) -> int:
    data = p.read_bytes()
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
