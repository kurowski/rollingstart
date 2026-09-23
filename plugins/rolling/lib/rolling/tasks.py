"""The task's lifecycle in the repository: begin (the throwaway branch
with the starting state committed), end (the learner's work committed
there, the learner returned), close (the task's files removed).

Every rule about what may be done to the tree is here as a check that
raises Refused with the message the tutor sees, and every check runs
before anything is written, so a refusal never leaves the repository
half-way.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from typing import List, Optional

from . import paths, rules
from .model import Learner, Task
from .repo import GitError, Repo, literal


class Refused(Exception):
    """A refusal, with the message the tutor sees."""


@dataclass
class Begun:
    branch: str
    base: str
    return_to: str
    held: List[str] = field(default_factory=list)
    note: str = ""

    def lines(self) -> List[str]:
        out = ([self.note] if self.note else []) + [f"branch: {self.branch}", f"base: {self.base}", f"return-to: {self.return_to}"]
        return out + [f"held: {p}" for p in self.held]


class Tasks:
    def __init__(self, repo: Repo, learner: Learner):
        self.repo = repo
        self.learner = learner

    # ---- begin

    def begin_from_fix(self, lesson: str, fix: str, held: List[str], shown: List[str]) -> Begun:
        """The task is a real fix, reverted: branch from the fix's parent;
        shown paths (its tests) brought forward and committed, present and
        failing; held paths copied into the learner's held/ and never put
        in the tree. The fix commit is not in the branch's history."""
        repo = self.repo
        self._common_checks(lesson)
        if repo.status():
            raise Refused("the working tree is not clean; commit, stash, or discard first:\n" + "\n".join(repo.status()))
        if not repo.is_commit(fix):
            raise Refused(f"{fix} is not a commit")
        fix = repo.rev_parse(f"{fix}^{{commit}}")
        if not repo.has_parent(fix):
            raise Refused(f"{fix} is a root commit; pick another fix")
        if repo.is_merge(fix):
            raise Refused(f"{fix} is a merge commit; pick another fix")
        seen: List[str] = []
        for p in held + shown:
            if not rules.is_literal_path(p):
                raise Refused(f"{p} is not a plain repository-relative path naming one file (no leading ./, no .., no //, no glob, no pathspec magic)")
            if p in seen:
                raise Refused(f"{p} is listed twice")
            seen.append(p)
            if not repo.touched(fix, p):
                raise Refused(f"{p} is not changed by {fix}; held and shown paths must be files the fix touched")
            if repo.mode_at(fix, p) not in ("100644", "100755"):
                raise Refused(f"{p} is not a regular file at {fix} (a directory, a symbolic link, or a file the fix deleted cannot be held or shown)")
        branch, return_to = self._branch_for(lesson), self._return_to()
        origin, origin_branch = repo.rev_parse("HEAD"), repo.branch()
        self._empty_held()
        try:
            repo.switch_new(branch, f"{fix}^")
            if shown:
                repo.checkout_paths(fix, shown)
            # The map as it is now, not as it was (or was not) before the fix:
            # a task cut from before the map was committed would otherwise
            # lose it. In the starting-state commit, so never in the diff.
            carried = self._carry_map(origin)
            note = ", with that commit's test brought forward so it is present and failing" if shown else ""
            note += ", and the map as of the commit the task began from" if carried else ""
            repo.commit(f"rolling: starting state for {lesson}\n\nThe code as it was before {repo.short(fix)}{note}. A Rolling\nStart task; the branch is throwaway.", allow_empty=True, as_tool=True)
            # The held copies, written only once the branch exists into the
            # directory _empty_held just emptied; still inside the undo, since
            # a branch with its starting state and no held test is a task
            # that cannot be proved and, being on a task branch, cannot be
            # begun again.
            for p in held:
                dest = self.learner.held / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(repo.show(fix, p))
            base = repo.rev_parse("HEAD")
        except (GitError, OSError) as e:
            # The tree was clean when this began and everything in it since
            # is the toolkit's, so switching back discards nothing of the
            # learner's.
            raise Refused(self._undo_begin(branch, origin_branch, origin, str(e), discard=True, before=[]))
        self._mark_lesson(lesson)
        return Begun(branch, base, return_to, held)

    def _mark_lesson(self, lesson: str) -> None:
        """The open-lesson marker, so the lesson a task belongs to is
        recorded the same way whether next chose it first or a task was
        begun directly (a proof harness, a test). Best effort: the task
        file carries the lesson too."""
        marker = self.learner.lesson_file
        try:
            if marker.is_symlink() or (marker.exists() and not marker.is_file()):
                return   # not a marker the toolkit wrote; never write through it, and close-task clears it
            marker.write_text(lesson + "\n", encoding="utf-8")
        except OSError:
            pass

    def begin_here(self, lesson: str, files: List[str]) -> Begun:
        """The task starts from the current commit plus the files the
        tutor has already put in the tree, named one by one. Anything
        else changed in the tree is the learner's and is refused rather
        than swept into a commit they did not ask for."""
        repo = self.repo
        self._common_checks(lesson)
        if not files:
            raise Refused("--here needs the paths the task adds")
        for p in files:
            if not rules.is_literal_path(p):
                raise Refused(f"{p} is not a plain repository-relative path naming one file (no leading ./, no .., no //, no glob, no pathspec magic)")
            fp = repo.top / p
            if fp.is_symlink() or not fp.is_file():
                raise Refused(f"{p} is not a regular file in the working tree (--here takes the files the task adds, one by one, never a directory or a link)")
        status = repo.status()
        changed = {_unquote(line[3:]): line for line in status}
        for p in files:
            if p in changed and changed[p][3:] != p:
                raise Refused(f"git quotes the path {p}; a task cannot start from a file git has to quote (a quote, a backslash, or a control character in the name)")
        other = [line for name, line in changed.items() if name not in files]
        if other:
            raise Refused("the working tree has changes outside the paths named; commit, stash, or discard them first:\n" + "\n".join(other))
        branch, return_to = self._branch_for(lesson), self._return_to()
        origin, origin_branch = repo.rev_parse("HEAD"), repo.branch()
        self._empty_held()
        note = ""
        try:
            repo.switch_new(branch)
            repo.add(files)
            if repo.staged_nonempty():
                repo.commit(f"rolling: starting state for {lesson}\n\nThe current commit plus the files the task adds. A Rolling Start task; the\nbranch is throwaway.", as_tool=True)
            else:
                note = "note: nothing to commit; the starting state is the current commit"
            base = repo.rev_parse("HEAD")
        except GitError as e:
            # HEAD never moved, so unstaging is enough: the files the tutor
            # prepared stay in the tree, untracked, as they were.
            raise Refused(self._undo_begin(branch, origin_branch, origin, str(e), discard=False, before=status))
        self._mark_lesson(lesson)
        return Begun(branch, base, return_to, [], note)

    def _undo_begin(self, branch: str, origin_branch: Optional[str], origin: str, why: str, discard: bool, before: List[str]) -> str:
        """Put the repository back as it was before a begin whose git
        write failed part-way, and say where it is. Each step is its own
        attempt, so one that fails does not stop the next, and the message
        reports what is actually true afterwards rather than what was
        meant: a half-made branch the tutor then "tidies" by hand is how
        the first fresh learner lost the map from the tree (2026-09-21)."""
        repo = self.repo
        problems: List[str] = []
        if discard:
            # Whether or not HEAD moved: a switch that was refused at the
            # ref update has already rewritten the index and tree.
            try:
                repo.switch_discarding(origin_branch or origin, detach=not origin_branch)
            except GitError as e:
                problems.append(f"could not put the tree back: {e}")
        else:
            try:
                repo.unstage_all()
            except GitError as e:
                problems.append(f"could not unstage: {e}")
            try:
                if repo.branch() == branch:
                    if origin_branch:
                        repo.switch(origin_branch)
                    else:
                        repo.switch_detach(origin)
            except GitError as e:
                problems.append(f"could not switch back: {e}")
        try:
            if repo.branch_exists(branch) and repo.branch() != branch:
                repo.delete_branch(branch)
        except GitError as e:
            problems.append(f"could not remove {branch}: {e}")
        try:
            if self.learner.held.is_dir():
                shutil.rmtree(self.learner.held)
        except OSError:
            pass
        where = repo.branch() or f"detached at {repo.head()}"
        left = repo.status()
        if left != before:   # for --here, the files the tutor prepared were there before and should still be
            problems.append("the tree is not as it was:\n" + "\n".join(left))
        if not problems:
            return f"could not begin the task: {why}\nnothing was begun; the repository is on {where}, as it was"
        return (
            f"could not begin the task: {why}\nthe task was not begun, and the repository could not be put back: "
            + "; ".join(problems) + f"\nit is on {where}. Say so to the learner; putting it right is theirs to do, never yours"
        )

    def _carry_map(self, origin: str) -> bool:
        """Put .rolling as of ORIGIN into the tree and index, replacing
        whatever the branch point had there; when ORIGIN has none, the
        branch point's is removed all the same, since a map an older
        commit carried is not the map now (a project that moved its map
        into a plugin, say), and the tree's map wins wherever it exists.
        False when ORIGIN has none."""
        repo = self.repo
        repo.run("rm", "-r", "-q", "--ignore-unmatch", "--", *literal([paths.MAP_DIR]), check=False)
        if not repo.ok("cat-file", "-e", f"{origin}:{paths.MAP_DIR}"):
            return False
        repo.checkout_paths(origin, [paths.MAP_DIR])
        return True

    def _common_checks(self, lesson: str) -> None:
        if not rules.is_slug(lesson):
            raise Refused(f"'{lesson}' is not a lesson slug (lowercase kebab-case)")
        if self.repo.head() is None:
            raise Refused("the repository has no commits")
        if self.learner.has_task():
            t = self.learner.task()
            raise Refused(f"a task is already open ({t.lesson if t else '?'}); run rolling-end-task and rolling-close-task first")
        # A lesson next opened is the one a task may begin for: a task for
        # another lesson would split the learner's record (the route note
        # under one lesson, the exercise and its feedback under another) and
        # mark the wrong lesson satisfied. No marker is fine: a proof
        # harness begins tasks without next.
        open_lesson = self.learner.open_lesson()
        if open_lesson and open_lesson != lesson:
            raise Refused(f"the open lesson is {open_lesson}, not {lesson}; a task begins for the open lesson. Close it first (rolling-close-task) if the learner is changing lessons")
        # An open task's own branch is the case above; this is a branch a
        # failed or abandoned run left, with no task to end.
        cur = self.repo.branch()
        if cur and rules.is_task_branch(cur):
            raise Refused(
                f"the repository is on {cur}, a task branch from an earlier run; a task begins from the learner's own branch, "
                f"never from another task's. Leaving it is the learner's to do (git switch <their branch>, then git branch -D {cur} "
                "if nothing on it is wanted); say so and stop"
            )

    def _empty_held(self) -> None:
        """Empty and recreate held/: the first write of a begin, after every
        check has passed and before any git write, so a directory that
        cannot be written refuses here and not after the branch exists.
        (os.access would be advisory; doing the write is the check.)"""
        try:
            self.learner.dir.mkdir(parents=True, exist_ok=True)
            if self.learner.held.is_dir() and not self.learner.held.is_symlink():
                shutil.rmtree(self.learner.held)
            elif self.learner.held.exists() or self.learner.held.is_symlink():
                self.learner.held.unlink()
            self.learner.held.mkdir()
        except OSError as e:
            raise Refused(f"the learner directory cannot be written: {e}")

    def _branch_for(self, lesson: str) -> str:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        branch = f"rolling/{lesson}-{stamp}"
        if not self.repo.valid_branch_name(branch):
            raise Refused(f"'{lesson}' does not make a valid branch name")
        n = 1
        while self.repo.branch_exists(branch):   # two tasks in one second (tests do this)
            n += 1
            branch = f"rolling/{lesson}-{stamp}-{n}"
        return branch

    def _return_to(self) -> str:
        cur = self.repo.branch()
        head = self.repo.rev_parse("HEAD")
        return f"{cur} {head}" if cur else head

    # ---- end

    def end(self, task: Task) -> List[str]:
        """Commit what the learner left on the task branch, keep the
        branch, return them to where they were. Refuses unless HEAD is
        the task branch: a learner who switched branches by hand has a
        tree this code should not guess about."""
        repo = self.repo
        if not task.branch or not task.return_to:
            raise Refused("task.md has no branch: or return-to: line; nothing to leave")
        cur = repo.branch()
        if cur != task.branch:
            raise Refused(f"not on {task.branch} (on {cur or 'a detached HEAD'}); leaving nothing")
        words = task.return_to.split()
        if len(words) > 2:
            raise Refused(f"task.md return-to has {len(words)} words; expected '<ref> <sha>' or a sha")
        out: List[str] = []
        index = repo.index_tree()   # how they had things staged, to put back if the commit fails
        try:
            repo.add(None)
            if repo.staged_nonempty():
                as_tool = repo.commit("rolling: the learner's work, as left\n\nCommitted on the throwaway branch when the task ended, so nothing is\nlost. Not for merging.")
                out.append(f"committed the learner's uncommitted work on {task.branch}")
                if as_tool:
                    out.append("note: no git identity is configured for the learner here, so that commit is under the toolkit's name (Rolling Start); their work is on the branch either way")
        except GitError as e:
            # Their work stays in the tree, staged as they had it; the
            # branch is not left, since leaving would need the commit.
            try:
                if index:
                    repo.restore_index(index)
                else:
                    repo.unstage_all()
            except GitError:
                pass
            raise Refused(f"could not commit the learner's work: {e}\nnothing was left: the repository is still on {task.branch} with their work in the tree, uncommitted. Say so; fixing what stopped the commit is theirs, and rolling-end-task can be run again")
        ref, sha = task.return_ref_and_sha()
        if sha and repo.branch_exists(ref):
            repo.switch(ref)
            out.append(f"back on {ref}; {task.branch} kept")
        elif sha:
            repo.switch_detach(sha)
            out.append(f"back at {sha}, detached: the branch '{ref}' no longer exists; {task.branch} kept")
        else:
            repo.switch_detach(ref)
            out.append(f"back at {ref}, detached; {task.branch} kept")
        return out

    # ---- close

    def close(self) -> List[str]:
        """Remove task.md, reference.md, reference.patch, held/, and the
        open-lesson marker, and nothing else. Closing a lesson that never
        got an exercise is the same call with less to remove."""
        out: List[str] = []
        for f in (self.learner.task_file, self.learner.reference, self.learner.patch):
            if f.is_file():
                f.unlink()
                out.append(f"removed {f.name}")
        marker = self.learner.lesson_file
        if marker.is_symlink() or marker.is_file():
            marker.unlink()
            out.append("removed lesson")
        elif marker.exists():   # not a file the toolkit wrote; gone anyway, so the next lesson can open
            shutil.rmtree(marker)
            out.append("removed lesson (it was a directory, which nothing of the toolkit's writes)")
        if self.learner.held.is_dir():
            shutil.rmtree(self.learner.held)
            out.append("removed held/")
        out.append("closed; profile.md, evidence/, tasks/, sessions/ kept")
        return out




def _unquote(name: str) -> str:
    r"""A path as git's porcelain prints it, unquoted: with quotePath off,
    git still C-quotes a name holding a quote, a backslash, or a control
    character, as "..." with \\, \", \t, \n, and \ooo escapes."""
    if not (name.startswith('"') and name.endswith('"')):
        return name
    body = name[1:-1]
    escapes = {"a": "\a", "b": "\b", "t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r", '"': '"', "\\": "\\"}
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            octal = body[i + 1:i + 4]
            if nxt in escapes:
                out.append(escapes[nxt])
                i += 2
                continue
            if len(octal) == 3 and all(c in "01234567" for c in octal):
                out.append(chr(int(octal, 8)))
                i += 4
                continue
        out.append(c)
        i += 1
    return "".join(out)
