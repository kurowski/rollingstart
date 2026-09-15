"""The held test: applied to the tree only while its lines run, then
reverted, with the learner's own file at the same path set aside and
restored.

The record of every step lives in the learner's directory, written
before the step is taken: held-aside/ holds the set-aside copies and
held-aside.pending lists the steps. A kill nothing can catch (SIGKILL,
which is how the Bash tool ends a command past its timeout) leaves the
record behind, and the next script that touches the tree finishes it
through revert(). The verifier's own run ends through revert() too:
one routine for the normal path and the repair path, so they cannot
drift.

    ht = HeldTest(learner, top)
    with ht.applied(paths):        # raises Refused before anything is applied
        ...run the held lines...
    ht.result                      # the RevertResult, whatever happened

No two commands run the apply at once by design: `done` reaches the
verifier through one inline command, `rolling-report`, because a
skill's inline commands start in parallel. There is no lock; two
tree-touching commands started by hand at the same moment would race
the record.
"""

from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator, List, Optional

from . import rules
from .model import Learner


class Step(Enum):
    ASIDE = "aside"        # the learner's file at <path> is now a complete copy under held-aside/
    DIR = "dir"            # a directory created for the apply
    APPLIED = "applied"    # the held copy is, or is about to be, at <path>


@dataclass(frozen=True)
class Entry:
    step: Step
    path: str


class Record:
    """held-aside.pending: one entry per line, appended before the step."""

    def __init__(self, path: Path):
        self.path = path

    def exists(self) -> bool:
        return self.path.is_file()

    def is_empty(self) -> bool:
        return not self.exists() or self.path.stat().st_size == 0

    def start(self) -> None:
        self.path.write_text("", encoding="utf-8")

    def append(self, step: Step, path: str) -> None:
        with open(self.path, "a", encoding="utf-8", errors="surrogateescape") as f:
            f.write(f"{step.value} {path}\n")

    def entries(self) -> List[Entry]:
        try:
            text = self.path.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError:
            return []
        out = []
        for line in text.split("\n"):
            kind, _, p = line.partition(" ")
            if p and kind in (s.value for s in Step):
                out.append(Entry(Step(kind), p))
        return out

    def clear(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass


@dataclass
class RevertResult:
    ok: bool = True             # every retryable step succeeded (the record is cleared)
    incomplete: bool = False    # a set-aside copy was missing; nothing to retry, that file is gone
    had_record: bool = False    # the record was non-empty
    lines: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        """The word for a summary line, or '' when nothing happened."""
        if not self.ok:
            return "REVERT FAILED (record kept)"
        if self.incomplete:
            return "REVERT INCOMPLETE (a set-aside copy was missing; see above)"
        return "reverted" if self.had_record else ""


def revert(learner: Learner, top: Path, quiet: bool = False) -> RevertResult:
    """Undo whatever the record describes: removals, then restores, then
    directories deepest first, whatever order the record has. Success
    lines are omitted when quiet (the verifier's own run, where a revert
    is the normal ending); failures are always reported. On success the
    record and the aside directory go; a failed step keeps both."""
    res = RevertResult()
    record = Record(learner.pending)
    if not record.exists():
        return res
    entries = record.entries()
    res.had_record = bool(entries)

    for e in entries:
        if e.step is not Step.APPLIED:
            continue
        target = top / e.path
        if not _present(target):
            continue
        try:
            _remove(target)
            if not quiet:
                res.lines.append(f"HELD reverted: removed the held copy left at {e.path}")
        except OSError:
            res.lines.append(f"HELD REVERT FAILED: could not remove the held copy at {e.path}")
            res.ok = False

    for e in entries:
        if e.step is not Step.ASIDE:
            continue
        src = learner.aside / e.path
        if not _present(src):
            res.lines.append(f"HELD REVERT INCOMPLETE: no set-aside copy of {e.path} was found; if you had a file there before the last run, it is gone")
            res.incomplete = True
            continue
        try:
            (top / e.path).parent.mkdir(parents=True, exist_ok=True)
            _move(src, top / e.path)
            if not quiet:
                res.lines.append(f"HELD reverted: restored your file at {e.path}")
        except OSError:
            res.lines.append(f"HELD REVERT FAILED: your file is still at {src}; put it back at {e.path} by hand")
            res.ok = False

    # Deepest first: an ancestor is a strict prefix of its descendants, so shorter.
    for p in sorted((e.path for e in entries if e.step is Step.DIR), key=len, reverse=True):
        try:
            (top / p).rmdir()
        except OSError:
            pass

    if res.ok:
        record.clear()
        shutil.rmtree(learner.aside, ignore_errors=True)
    return res


class CannotApply(Exception):
    """A held path could not be applied; the lines say which and why."""

    def __init__(self, lines: List[str]):
        super().__init__("\n".join(lines))
        self.lines = lines


class HeldTest:
    def __init__(self, learner: Learner, top: Path):
        self.learner = learner
        self.top = top
        self.record = Record(learner.pending)
        self.applied_paths: List[str] = []
        self.result: Optional[RevertResult] = None

    @contextmanager
    def applied(self, paths: List[str]) -> Iterator["HeldTest"]:
        """The held test applied for the block's duration and reverted on
        the way out, whatever happened. Raises CannotApply, with nothing
        left applied, when any path cannot be applied."""
        self._apply(paths)
        try:
            yield self
        except BaseException:
            self.result = revert(self.learner, self.top, quiet=False)   # an interrupt: the learner is watching
            raise
        else:
            self.result = revert(self.learner, self.top, quiet=True)    # the normal ending

    # ---- apply

    def _apply(self, paths: List[str]) -> None:
        shutil.rmtree(self.learner.aside, ignore_errors=True)
        self.learner.aside.mkdir(parents=True, exist_ok=True)
        self.record.start()
        problems: List[str] = []
        try:
            for p in paths:
                problem = self._check(p)
                if problem:
                    problems.append(problem)
                    continue
                self._apply_one(p)
        except OSError as e:
            problems.append(f"HELD not applied: {e}")
        if problems:
            self.result = revert(self.learner, self.top, quiet=True)
            raise CannotApply(problems)

    def _check(self, p: str) -> str:
        if not rules.is_plain_relpath(p):
            return f"HELD REJECTED {p}   (not a plain repository-relative path: no leading ./, no .., no //)"
        if p in self.applied_paths:
            return f"HELD REJECTED {p}   (listed twice)"
        if not (self.learner.held / p).is_file():
            return f"HELD MISSING {p}   (no copy under held/)"
        if rules.has_symlink_component(self.top, p):
            return f"HELD REJECTED {p}   (a symbolic link is in the way; the held test is applied only through plain files and directories)"
        target = self.top / p
        if target.exists() and any(_same(target, self.top / q) for q in self.applied_paths):
            return f"HELD REJECTED {p}   (the same file as another held path)"
        return ""

    def _apply_one(self, p: str) -> None:
        target = self.top / p
        if _present(target):
            # Copy in full to a temporary name, rename into place, record,
            # then remove the original: the record never names a partial copy.
            aside = self.learner.aside / p
            aside.parent.mkdir(parents=True, exist_ok=True)
            tmp = aside.with_name(aside.name + ".rolling-tmp")
            _copy(target, tmp)
            os.replace(tmp, aside)
            self.record.append(Step.ASIDE, p)
            _remove(target)
        for d in _dirs_to_create(self.top, p):
            self.record.append(Step.DIR, d)
        self.record.append(Step.APPLIED, p)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.learner.held / p, target)
        self.applied_paths.append(p)


# ---- file helpers, all symlink-aware


def _present(p: Path) -> bool:
    return p.exists() or p.is_symlink()


def _remove(p: Path) -> None:
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p)
    else:
        p.unlink()


def _copy(src: Path, dst: Path) -> None:
    if src.is_dir() and not src.is_symlink():
        shutil.copytree(src, dst, symlinks=True)
    else:
        shutil.copy2(src, dst, follow_symlinks=False)


def _move(src: Path, dst: Path) -> None:
    """Rename when on one filesystem; otherwise copy in full, replace,
    then remove the source, so a kill mid-way never leaves half a file
    at the destination."""
    try:
        os.replace(src, dst)
        return
    except OSError:
        pass
    tmp = dst.with_name(dst.name + ".rolling-tmp")
    _copy(src, tmp)
    os.replace(tmp, dst)
    _remove(src)


def _same(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _dirs_to_create(top: Path, p: str) -> Iterator[str]:
    """The directories an apply of P would create, innermost first."""
    d = os.path.dirname(p)
    while d and not (top / d).is_dir():
        yield d
        d = os.path.dirname(d)
