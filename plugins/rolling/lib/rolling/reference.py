"""The reference, applied to the tree for the forward half of the proof
and reversed on the way out.

A task is proven both ways before the learner sees it: on the starting
state the expected failures fail (`rolling-verify --on-base`), and with
the reference applied everything passes (`rolling-verify
--on-reference`). The second half needs the reference in the tree,
inside the task's scope, and the write guard denies the tutor's editing
tools there the moment the task exists, as it should. So the reference
goes in and comes out through this module, as a patch:

- For a task built from a fix, the patch is the fix's own change to
  every path it touched except the held ones, taken against HEAD: a
  shown test is already at HEAD, so it diffs to nothing and is left
  alone, and the map (carried onto the branch as of now) is excluded
  by name.
- For a task built along a seam, the patch is the one the tutor wrote
  with the pen (`rolling-write patch`), kept in the learner's
  directory as `reference.patch`.

`git apply` puts it in, `git apply -R` takes it out, in a `finally`,
with SIGINT and SIGTERM turned into an exception by the verifier's
interruptible block so the reverse runs on the way out. The tree must
be clean before, which is what makes the reverse exact.

A kill the `finally` cannot survive (SIGKILL, which is how the Bash
tool ends a command past its timeout) leaves the patch applied. The
copy that was applied stays beside the task as the record, and every
command that touches the tree finishes the job first, through
`repair`, the way a held-test revert is finished: the reverse when it
still applies cleanly and HEAD is still the commit it was applied on,
a refusal in words naming the file when either is not so. Without
that, the tutor's answer would sit in the tree as the learner's work,
and `done` would read it and `end-task` commit it; and a reverse on
some other commit would be the tutor editing the learner's tree
uninvited.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, List, Tuple

from . import paths
from .model import Learner, Task
from .repo import GitError, Repo, literal


class NoReference(Exception):
    """Nothing to apply; the message says what the task lacks."""


class CannotApply(Exception):
    """The patch could not go in, or the tree was not ready for it."""


@dataclass
class Applied:
    """What the block reports: the reverse's outcome, and what the tree
    looked like afterwards."""
    notes: List[str] = field(default_factory=list)
    reverse_ok: bool = False
    dirty: List[str] = field(default_factory=list)   # status lines after the reverse

    @property
    def clean_exit(self) -> bool:
        return self.reverse_ok and not self.dirty


def patch_for(repo: Repo, learner: Learner, task: Task) -> bytes:
    if task.fix:
        if not repo.is_commit(task.fix):
            raise NoReference(f"fix {task.fix} is not a commit in this repository")
        fix = repo.rev_parse(f"{task.fix}^{{commit}}")
        if not repo.has_parent(fix):
            raise NoReference(f"fix {task.fix} is a root commit; there is no change to apply")
        touched = repo.changed_paths(f"{fix}^", fix)   # real names, so a quoted one is compared as itself
        keep = [p for p in touched if p not in task.held and p.split("/", 1)[0] != paths.MAP_DIR]
        if not keep:
            raise NoReference(f"fix {task.fix} touches nothing but held paths and the map; there is no reference to apply")
        patch = repo.run_bytes("diff", "--binary", "HEAD", fix, "--", *literal(keep))
        if not patch.strip():
            raise NoReference(f"fix {task.fix} is already in the tree at HEAD; nothing to apply")
        return patch
    if learner.patch.is_file():
        patch = learner.patch.read_bytes()
        if not patch.strip():
            raise NoReference("reference.patch is empty")
        return patch
    raise NoReference("the task has no fix: line and no reference patch; for a seam task, write the solution as a patch with rolling-write patch")


@contextmanager
def applied(repo: Repo, learner: Learner, patch: bytes) -> Iterator[Applied]:
    """PATCH in the tree for the block, reversed afterwards, whatever
    happens inside. The yielded Applied is filled in on the way out."""
    if repo.status():
        raise CannotApply("the working tree is not clean; the reference is applied only to the committed starting state")
    copy, at = learner.applied_patch, learner.applied_at
    result = Applied()
    try:
        copy.write_bytes(patch)
        at.write_text(repo.rev_parse("HEAD") + "\n", encoding="utf-8")
        repo.run("apply", "--check", "--", str(copy))
        repo.run("apply", "--", str(copy))
    except (GitError, OSError) as e:
        try:
            _forget(learner)
        except OSError:
            pass   # repair clears the record when the patch never went in
        raise CannotApply(f"the reference patch does not apply to the starting state: {e}")
    try:
        yield result
    finally:
        _reverse(repo, learner, result)


def _forget(learner: Learner) -> None:
    for f in (learner.applied_patch, learner.applied_at):
        if f.exists():
            f.unlink()


def _reverse(repo: Repo, learner: Learner, result: Applied) -> None:
    """Runs in a finally, so it raises nothing: every outcome is a note."""
    copy = learner.applied_patch
    try:
        repo.run("apply", "-R", "--", str(copy))
    except (GitError, OSError) as e:
        result.notes.append(f"REFERENCE REVERSE FAILED: {e}; the patch is still in the tree; `git apply -R {copy}` by hand")
        return
    result.reverse_ok = True
    try:
        _forget(learner)
    except OSError as e:
        result.notes.append(f"REFERENCE reversed, but its record could not be removed ({e}); remove {copy} and {learner.applied_at.name} by hand")
    try:
        result.dirty = repo.status()
    except (GitError, OSError) as e:
        result.dirty = [f"(git status failed: {e})"]
        result.notes.append(f"REFERENCE reversed, but the tree could not be checked afterwards: {e}")
        return
    if result.dirty:
        result.notes.append("REFERENCE reversed, but the tree is not clean afterwards; something the checks ran left these behind:")
        result.notes += ["  " + l for l in result.dirty]
    else:
        result.notes.append("REFERENCE reversed")


def repair(repo: Repo, learner: Learner) -> Tuple[List[str], bool]:
    """Finish what a killed run left: the applied copy reversed when HEAD
    is still the commit it went in on and it still comes out cleanly.
    Returns the lines to print and whether nothing is left to finish."""
    copy, at_file = learner.applied_patch, learner.applied_at
    if not copy.is_file():
        return [], True
    records = f"{copy} and {at_file.name} beside it, whichever exist"
    try:
        at = at_file.read_text(encoding="utf-8").strip()
    except OSError:
        at = ""
    # Out already? A record can outlive its reverse (a kill between the
    # reverse and the unlink, a directory that was read-only for the
    # unlink). Applies forward and does not reverse: not in the tree. A
    # mode-only patch does both in either state, so the reverse check
    # is what keeps it on the applied path below.
    if repo.ok("apply", "--check", "--", str(copy)) and not repo.ok("apply", "-R", "--check", "--", str(copy)):
        try:
            _forget(learner)
        except OSError as e:
            return [f"REFERENCE record stale: the reference is not in the tree, but its record could not be removed ({e}); remove {records}"], False
        return ["REFERENCE record cleared: a proof's record outlived its reverse; the reference is not in the tree"], True
    head = repo.head() or ""
    if not at or at != head:
        where = f"on {at[:12]}" if at else "on a commit it did not record"
        return [f"REFERENCE STILL APPLIED: a killed proof left the reference in the tree {where}, and HEAD is now {head[:12]}; `git apply -R {copy}` by hand on that commit, then remove {records}"], False
    try:
        repo.run("apply", "-R", "--check", "--", str(copy))
        repo.run("apply", "-R", "--", str(copy))
    except (GitError, OSError) as e:
        return [f"REFERENCE STILL APPLIED: a killed proof left the reference in the tree and it does not reverse cleanly now ({e}); `git apply -R {copy}` by hand, then remove {records}"], False
    try:
        _forget(learner)
    except OSError as e:
        return [f"REFERENCE repaired, but its record could not be removed ({e}); remove {records}"], False
    return ["REFERENCE repaired: reversed the reference a killed proof left in the tree"], True
