"""What the learner changed: the working tree against the open task's
base commit, unstaged and untracked included, nothing excluded. Nothing
has to be committed or staged for the tutor to see the work, and the
tree holds only the author's map and the learner's work, so a change to
either is a change.
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
    stat: List[str] = field(default_factory=list)
    untracked: List[str] = field(default_factory=list)
    patch: str = ""                        # tracked changes against the base
    new_files: List[str] = field(default_factory=list)   # one patch per untracked file

    def render(self, cap: int = 3000) -> List[str]:
        """The report, capped so a stray binary cannot swamp the transcript."""
        head = f"## HEAD: {self.head_short}"
        if self.head_moved:
            head += "  (HEAD has moved since the task began; the diff is still against base)"
        out = [f"## Base: {self.base} ({self.base_subject})", head, "", "## Changed files"]
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
        stat=[l for l in repo.diff_stat(base).split("\n") if l],
        untracked=untracked,
        patch=repo.diff(base),
        new_files=[repo.diff_new_file(f).rstrip("\n") for f in untracked],
    )
