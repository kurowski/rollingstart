"""The task's lifecycle in the repository: begin (the throwaway branch
with the starting state committed), end (the learner's work committed
there, the learner returned), park and resume (the same leaving, with
the task's files set aside and brought back), close (the task's files
removed).

Every rule about what may be done to the tree is here as a check that
raises Refused with the message the tutor sees, and every check runs
before anything is written, so a refusal never leaves the repository
half-way.

**The exclude block.** A task's starting state is older than the branch
the learner came from, and ignore rules are added late: a repository
that started ignoring `test-results/` last month has a starting state
that does not, so the generated directory a learner's own test run left
turns from invisible into untracked the moment a task begins. It is
then dirt to the clean-tree check, which refuses the proof, and
`end-task`'s `git add -A` would commit it onto the task branch.

So begin writes the ignore patterns of the branch `return-to` names
into `.git/info/exclude`, between two marker lines, and the tree is
judged the way the learner's own branch judges it for the task's
lifetime. The patterns come from the `.gitignore` files of that branch,
read out of git rather than off disk, and a nested one is rewritten to
mean what it means where it lives (`node_modules` in
`apps/web/.gitignore` becomes `/apps/web/**/node_modules`), since
`info/exclude` is read from the top.

`.git/info/exclude` is not in the working tree, so nothing the tutor
writes lands where the repository's own checks or a coding agent can
see it. The rules cut both ways, though: a task whose `scope` sits
inside something the learner's branch ignores would have its work left
out of end's commit, so a scope inside ignored ground is a mistake in
the map that this makes visible rather than one this hides.

The block's lifecycle: begin writes it, replacing any block a crashed
run left rather than appending a second; end and park remove
it, because the learner is back on their own branch where their own
`.gitignore` applies; resume writes it again for whatever branch the
resumed task returns to, which a park across a branch change may have
moved; and close removes a block whose end never ran, so the rules
never outlive the task that wanted them.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from . import excludes, frontmatter as fm, paths, rules, session
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
        return Begun(branch, base, return_to, held, self._carry_excludes(return_to))

    def _carry_excludes(self, return_to: str) -> str:
        """The exclude block for the branch RETURN_TO names, written once
        the branch and its starting state exist, so a begin that failed
        part-way never leaves one. Never fatal: a task without it works,
        showing the dirt the learner's own branch would have hidden, and
        saying so is better than refusing a task that is otherwise
        begun. The catch is as wide as that promise: this runs after the
        branch and its starting state exist, so anything getting out of
        here lands past _undo_begin and leaves exactly the half-begun
        task the undo path exists to prevent."""
        words = return_to.split()
        if not words:
            return ""
        try:
            excludes.write(self.repo, words[0])
        except (OSError, UnicodeError) as e:
            return (f"note: the ignore rules of {words[0]} could not be carried into the repository's exclude file "
                    f"({e}); anything that branch ignores and this starting state does not will look like a change "
                    "of the learner's")
        return ""

    def _drop_excludes(self) -> List[str]:
        """The block out again, when the learner is back on their own
        branch and their own .gitignore applies. Never fatal either: what
        is left is extra ignore rules, which the next begin replaces."""
        try:
            excludes.remove(self.repo)
        except (OSError, UnicodeError) as e:
            return [f"note: the carried ignore rules could not be taken out of the repository's exclude file ({e}); "
                    "the block between the two 'rolling-start:' lines can go by hand"]
        return []

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
        carried = self._carry_excludes(return_to)
        return Begun(branch, base, return_to, [], "; ".join(n for n in (note, carried) if n))

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

    def _end_checks(self, task: Task) -> None:
        """What leaving a task refuses, whether it is ended or parked,
        before anything is written. Refuses unless HEAD is the task
        branch: a learner who switched branches by hand has a tree this
        code should not guess about."""
        if not task.branch or not task.return_to:
            raise Refused("task.md has no branch: or return-to: line; nothing to leave")
        cur = self.repo.branch()
        if cur != task.branch:
            raise Refused(f"not on {task.branch} (on {cur or 'a detached HEAD'}); leaving nothing")
        words = task.return_to.split()
        if len(words) > 2:
            raise Refused(f"task.md return-to has {len(words)} words; expected '<ref> <sha>' or a sha")

    def end(self, task: Task) -> List[str]:
        """Commit what the learner left on the task branch, keep the
        branch, return them to where they were."""
        repo = self.repo
        self._end_checks(task)
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
        # After the commit above, which the block kept from sweeping in
        # what the learner's branch ignores, and after the switch: they
        # are on their own branch now, where their own .gitignore says
        # what counts.
        return out + self._drop_excludes()

    # ---- close

    # ---- park and resume

    def _parked_pairs(self) -> List[Tuple[Path, Path]]:
        """Every file a parked task is made of, as (where it lives while
        the task is open, where it waits while it is parked). task.md
        leads, because it is what says a task is parked: a move that
        stops part-way then leaves something a second resume finishes,
        never an open task whose held test is somewhere else."""
        l = self.learner
        return [(p, l.parked / p.name) for p in (l.task_file, l.reference, l.patch, l.held, l.lesson_file)]

    def park(self, task: Task) -> List[str]:
        """Set the open task aside for a detour: what end does to the
        tree (the learner's work committed on the branch, which is kept,
        and the learner back where they were), and then the task's files
        moved into parked/ rather than removed.

        One task is parked at a time, so a second park is refused while
        the first can still be resumed. A parked task whose branch the
        learner has since deleted is not resumable and is replaced
        instead: what it holds is a pointer to work that is gone, and a
        pointer nobody can follow must not block every later detour."""
        self._end_checks(task)
        parked = self.learner.parked_task()
        if parked is not None and parked.branch and self.repo.branch_exists(parked.branch):
            raise Refused(
                f"a task is already parked ({parked.lesson or 'no lesson named'}, on {parked.branch}); one is parked at a "
                "time, so resume that one (rolling-resume-task) and end or finish it before parking this one"
            )
        out = self.end(task)
        if _present(self.learner.parked):
            if parked is not None:
                out.append(
                    f"the task parked before this one cannot be resumed: its branch {parked.branch or '(none named)'} is "
                    "gone, so it is cleared and this one takes its place"
                )
            else:
                out.append("what was parked could not be read as a task, so it is cleared and this one takes its place")
            self._clear_parked()
        return out + self._park_files(task)

    def _park_files(self, task: Task) -> List[str]:
        moved: List[str] = []
        try:
            self.learner.parked.mkdir(parents=True, exist_ok=True)
            for live, aside in self._parked_pairs():
                if not _present(live):
                    continue
                _replace(live, aside)
                moved.append(live.name)
        except OSError as e:
            raise Refused(
                f"their work is committed on {task.branch} and they are back where they were, but the task could not be "
                f"set aside ({e}); moved: {', '.join(moved) or 'nothing'}. Say so; rolling-resume-task puts back what moved"
            )
        return [f"parked {task.lesson or 'the task'}; its files are set aside until rolling-resume-task"]

    def resume(self, session_id: str) -> List[str]:
        """Pick the parked task up again: back onto its branch, its files
        back where they were, `return-to` rewritten to where the learner
        was when they resumed and `tutor-session` to the session reading
        it now. The write guard holds only for a task stamped with the
        running session, so a resumed task carrying the old stamp would
        leave the tutor free to write the learner's code; a resume with
        no session recorded refuses, as the pen does.

        A parked task whose branch is gone is cleared rather than
        refused: the branch was the learner's to delete, and a pointer
        nobody can follow would block every later detour. Running this
        twice finishes a restore that stopped part-way, which is why
        being on the parked task's own branch is not the refusal that
        being on another task's is."""
        repo, learner = self.repo, self.learner
        parked = learner.parked_task()
        if parked is None:
            raise Refused("nothing is parked; rolling-park-task is what sets an open task aside")
        open_task = learner.task()
        if open_task is not None and open_task.branch != parked.branch:
            raise Refused(
                f"a task is open ({open_task.lesson or 'no lesson named'}); end it (rolling-end-task) or park it before "
                "resuming the parked one"
            )
        if not parked.branch:
            self._clear_parked()
            return ["the parked task names no branch, so there is nothing to come back to; it is cleared"]
        if not repo.branch_exists(parked.branch):
            self._clear_parked()
            return [
                f"the branch {parked.branch} is gone, so {parked.lesson or 'the parked task'} cannot come back; it is cleared",
                "nothing of the learner's was touched and nothing is open: the branch was theirs to delete",
            ]
        if not session.is_session_id(session_id):
            raise Refused(
                "the tutor's session is not recorded, and a resumed task carries it (the write guard holds only for the "
                "session the task names); a skill's inline rolling-claim-session records it first"
            )
        cur = repo.branch()
        switching = cur != parked.branch
        if switching:
            if repo.status():
                raise Refused("the working tree is not clean; commit, stash, or discard first:\n" + "\n".join(repo.status()))
            if cur and rules.is_task_branch(cur):
                raise Refused(
                    f"the repository is on {cur}, another task's branch; a task resumes from the learner's own branch. "
                    f"Leave that one first (git switch <their branch>); say so and stop"
                )
            return_to = self._return_to()
        else:
            # A second run, finishing what the first could not. The first
            # run wrote where the learner was into the parked copy before
            # it switched, so that is still the answer; recomputing here
            # would name the task's own branch as the place to go back to.
            return_to = parked.return_to
        pairs = self._parked_pairs()
        task_live, task_aside = pairs[0]
        # The two lines that belong to this run, into the copy still in
        # parked/ and before any git write: a failure moves nothing, and
        # a kill after it leaves a parked task that already knows where
        # it returns to.
        stamped = self._restamp(task_aside, return_to, session_id)
        if switching:
            try:
                repo.switch(parked.branch)
            except GitError as e:
                raise Refused(f"could not switch to {parked.branch}: {e}\nnothing was moved and the task is still parked")
        restored: List[str] = []
        try:
            # Everything but task.md, and task.md last: while it is still
            # in parked/ a task is parked, so a run that stops here is
            # finished by the next one, and once it has moved the task is
            # open with everything it needs. The park moves the same list
            # the other way round, for the same reason.
            for live, aside in reversed(pairs[1:]):
                if not _present(aside):
                    continue
                _replace(aside, live)
                restored.append(live.name)
        except OSError as e:
            raise Refused(
                f"the repository is on {parked.branch}, but the task could not be put back ({e}); restored: "
                f"{', '.join(restored) or 'nothing'}. The task is still parked; say so — rolling-resume-task finishes "
                "it once whatever stopped the move is out of the way"
            )
        out = [f"back on {parked.branch}; {parked.lesson or 'the task'} is open again, with their work as they left it"]
        out += stamped
        try:
            _replace(task_aside, task_live)
        except OSError as e:
            raise Refused(
                f"the repository is on {parked.branch} and the task's files are back, but the task itself could not be "
                f"opened ({e}); it is still parked — say so, and rolling-resume-task finishes it once whatever is in the "
                "way is gone"
            )
        self._clear_parked()
        # The block for the branch this task returns to *now*: a park and
        # a resume from somewhere else rewrote return-to, and the rules
        # carried have to be that branch's.
        note = self._carry_excludes(return_to)
        return out + ([note] if note else [])

    def _restamp(self, task: Path, return_to: str, session_id: str) -> List[str]:
        """The resumed task's two lines that belong to this run: where it
        returns to now, and whose session it is. Written into the copy
        still in parked/, before the switch and before the moves, so a
        failure here leaves a parked task rather than an open one with
        the wrong stamp, and a kill afterwards leaves one that knows
        where it returns to without the next run having to guess.
        Written as claim writes its own, through a temporary file and a
        rename."""
        try:
            text = task.read_text(encoding="utf-8", errors="surrogateescape")
            text = fm.with_field(fm.with_field(text, "return-to", return_to), "tutor-session", session_id)
            tmp = task.with_name("." + task.name + ".tmp")
            tmp.write_text(text, encoding="utf-8", errors="surrogateescape")
            os.replace(tmp, task)
        except OSError as e:
            raise Refused(
                f"the task's return-to and tutor-session lines could not be rewritten ({e}); nothing was moved and it is "
                "still parked, so nothing is open and the write guard has nothing to be wrong about. Say so; a later "
                "rolling-resume-task tries again"
            )
        return [f"return-to: {return_to}", f"tutor-session: {session_id}"]

    def _clear_parked(self) -> None:
        """Remove parked/, whatever is left in it. Best effort: what it
        held has either been moved back or was unreachable, and a stale
        directory is cleared by the next park either way."""
        try:
            if self.learner.parked.is_dir() and not self.learner.parked.is_symlink():
                shutil.rmtree(self.learner.parked)
            elif _present(self.learner.parked):
                self.learner.parked.unlink()
        except OSError:
            pass

    def close(self) -> List[str]:
        """Remove task.md, reference.md, reference.patch, held/, and the
        open-lesson marker, and nothing else. Closing a lesson that never
        got an exercise is the same call with less to remove.

        The exclude block goes too, when one is still there: end removes
        it, but end refuses off the task's branch and close then runs
        alone, and ignore rules that outlive their task would hide the
        learner's own files on their own branch."""
        out: List[str] = []
        out += self._drop_excludes()
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




def _present(p: Path) -> bool:
    """Whether the path is there at all, a broken symbolic link included."""
    return p.exists() or p.is_symlink()


def _replace(src: Path, dst: Path) -> None:
    """Move SRC onto DST, whatever is in the way: os.replace will not put
    a file where a directory is, nor a directory where anything is."""
    if dst.is_dir() and not dst.is_symlink():
        shutil.rmtree(dst)
    elif _present(dst):
        dst.unlink()
    os.replace(str(src), str(dst))


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
