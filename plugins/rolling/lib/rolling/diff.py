"""What the learner changed: the working tree against the open task's
base commit, unstaged and untracked included, nothing excluded. Nothing
has to be committed or staged for the tutor to see the work, and the
tree holds only the author's map and the learner's work, so a change to
either is a change.

All of that holds while the task's branch is the one checked out. Off
it, the same subtraction answers a different question -- that branch
against the task's starting state, the author's fix included when the
task was cut from one -- so the capture says whose change it is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from . import rules
from .model import Task
from .repo import Repo


class NotCaptured(Exception):
    """The diff could not be taken; the message says why, in words."""


@dataclass
class Diff:
    base: str
    base_subject: str
    head_short: str
    head_moved: bool                       # HEAD is no longer the base commit
    off_branch: str = ""                   # the task's branch, when it is not the one checked out
    stat: List[str] = field(default_factory=list)
    untracked: List[str] = field(default_factory=list)
    patch: str = ""                        # tracked changes against the base
    new_files: List[str] = field(default_factory=list)   # one patch per untracked file

    def render(self, cap: int = 3000) -> List[str]:
        """The report, capped so a stray binary cannot swamp the transcript."""
        head = f"## HEAD: {self.head_short}"
        if self.head_moved:
            head += "  (HEAD has moved since the task began; the diff is still against base)"
        out = [f"## Base: {self.base} ({self.base_subject})", head, ""]
        if self.off_branch:
            # Against the base from another branch, the diff is that branch
            # against the task's starting state -- which, for a task cut
            # from a fix, is the author's fix itself, with a verifier that
            # passes on it. Silence here reads as the learner's work having
            # been seen and approved, so it is said before the diff.
            out += ["## Not the exercise's change",
                    f"The repository is not on {self.off_branch}, the task's branch. What follows is the",
                    "tree as it stands here against the task's base, so it carries whatever this branch",
                    "already had -- the lesson's own fix among it, if that is where the task was cut",
                    "from. The checks below ran against that same tree. None of this is the learner's",
                    "work on the exercise, and no feedback can rest on it.",
                    ""]
        out += ["## Changed files"]
        out += ["  " + l for l in self.stat]
        out += ["## New files (untracked)"] + ["  " + f for f in self.untracked]
        out += ["", "## Diff"] + self.patch.split("\n")
        for p in self.new_files:
            out += p.split("\n")
        if len(out) > cap:
            return out[:cap - 1] + [f"DIFF: truncated at {cap} of {len(out)} lines (set ROLLING_DIFF_MAX_LINES to raise)"]
        return out


def capture(repo: Repo, task: Task) -> Diff:
    base = task.base
    if not base:
        raise NotCaptured("the open task has no base: line")
    if not rules.is_sha(base):
        raise NotCaptured(f"base '{base}' is not a commit sha; use the full sha, not a ref")
    if not repo.is_commit(base):
        raise NotCaptured(f"base {base} is not a commit in this repository")
    untracked = repo.untracked()
    return Diff(
        base=base,
        base_subject=repo.subject(base),
        head_short=repo.short("HEAD"),
        head_moved=repo.rev_parse("HEAD") != repo.rev_parse(base),
        off_branch=task.branch if task.branch and repo.branch() != task.branch else "",
        stat=[l for l in repo.diff_stat(base).split("\n") if l],
        untracked=untracked,
        patch=repo.diff(base),
        new_files=[repo.diff_new_file(f).rstrip("\n") for f in untracked],
    )
