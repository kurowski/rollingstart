"""A detour's lifecycle: begun (the open task parked, the first step
opened), advanced (the next step, when one closes), and ended (the
learner put back where they left the course).

The bookkeeping is deliberately thin. `open-detour` names the detour;
the `lesson` marker names the open step, exactly as it names any open
lesson. So everything that already reads that marker — the walkthrough,
`rolling-begin-task`, evidence, `done` — serves a step without being
told it is one, and the step's place in the detour is its slug found in
the plan's `steps` list. That is why the pen refuses the same slug
twice: position is read from the slug, and two of them would leave no
answer to which step is open.

Every check runs before anything is written, as in tasks.py. The one
write that touches the repository is the park a begin does, and it is
last of the refusable things and first of the writes, so a refusal
never leaves the tree moved and the detour half-open.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from . import rules, session, validate
from .model import Detour, Learner
from .repo import Repo
from .tasks import Refused, Tasks


class Detours:
    def __init__(self, repo: Repo, learner: Learner, map_dir: Path):
        self.repo = repo
        self.learner = learner
        self.map_dir = map_dir

    # ---- resolving a step

    def step_path(self, detour: str, slug: str) -> Optional[Path]:
        """Where a step's lesson lives: the detour's own file if the
        tutor wrote one, else the map's lesson if it is borrowing one,
        else None. The tutor's own comes first, and the pen refuses a
        step that would shadow a map lesson, so the order never decides
        anything it should not."""
        own = self.learner.step_file(detour, slug)
        if own.is_file():
            return own
        lesson = self.map_dir / "lessons" / f"{slug}.md"
        return lesson if lesson.is_file() else None

    def lesson_path(self, slug: str) -> Path:
        """Where a lesson's text is for a skill to read: the open
        detour's own step by that slug, else the map's lesson. Always a
        path, which may not exist — the caller says so in its own words.
        `step_path` is the same lookup for the question "can this be
        served", which wants None instead."""
        if rules.is_slug(slug):
            open_detour = self.learner.open_detour()
            if open_detour:
                own = self.learner.step_file(open_detour, slug)
                if own.is_file():
                    return own
        return self.map_dir / "lessons" / f"{slug}.md"

    def is_step(self, slug: str) -> bool:
        """Whether that slug is a step the tutor wrote for the open
        detour, rather than a lesson of the map's."""
        open_detour = self.learner.open_detour()
        return bool(open_detour and rules.is_slug(slug) and self.learner.step_file(open_detour, slug).is_file())

    # ---- begin

    def begin(self, slug: str) -> List[str]:
        """Open detour SLUG: park the open task if there is one, record
        the detour, and open its first step.

        A detour is offered on a gap and taken on the learner's yes; by
        the time this runs, the plan is written and agreed. What it
        refuses is the states that would strand something: a detour
        already open (one at a time, and no detour inside a detour), a
        plan that does not validate, and a step that nothing could
        serve."""
        if not rules.is_slug(slug):
            raise Refused(f"'{slug}' is not a detour slug (lowercase kebab-case)")
        open_slug = self.learner.open_detour()
        if open_slug:
            raise Refused(
                f"the detour '{open_slug}' is open; one runs at a time, and there is no detour inside a detour. Finish it, "
                "or end it with rolling-close-detour, first"
            )
        plan_path = self.learner.detours / f"{slug}.md"
        faults = validate.validate_detour(plan_path, self.map_dir)
        if faults:
            raise Refused("\n".join(str(f) for f in faults) + f"\n{len(faults)} fault(s) in the plan; nothing was begun")
        plan = Detour.load(plan_path)
        # The plan says which lesson the detour returns to, and that has
        # to be the one the learner is actually on. Both skills say so in
        # prose; nothing held it, so a plan naming another lesson would
        # end the detour by opening a lesson the learner never picked —
        # the tutor choosing their route, which is theirs to choose.
        here = self.learner.open_lesson()
        if not here:
            raise Refused(
                f"no lesson is open, so there is nothing for a detour to return to; '{slug}' says it returns to "
                f"{plan.returns_to or '(nothing)'}. A detour is a side trip off a lesson: open the lesson first"
            )
        if plan.returns_to != here:
            raise Refused(
                f"'{slug}' returns to {plan.returns_to or '(nothing)'}, but the open lesson is {here}. A detour returns "
                f"to the lesson it was taken from; write the plan with returns-to: {here}, or open {plan.returns_to} first "
                "if that is where the learner actually is"
            )
        missing = [s for s in plan.steps if self.step_path(slug, s) is None]
        if missing:
            raise Refused(
                f"{'this step is' if len(missing) == 1 else 'these steps are'} neither written under detours/{slug}/ nor a "
                f"lesson in the map: {', '.join(missing)}. Write each one the tutor is authoring (rolling-write step {slug} "
                "<step>), and check the spelling of each one being borrowed"
            )
        marker = self.learner.lesson_file
        self._writable(marker, "the open-lesson marker")
        self._writable(self.learner.open_detour_file, "the open-detour marker")
        out: List[str] = []
        if self.learner.has_task():
            task = self.learner.task()
            if task is None:
                raise Refused("a task.md is there but cannot be read as a task; nothing was begun. Ending it by hand is the learner's call")
            out += Tasks(self.repo, self.learner).park(task)
        else:
            # No task to park, but the learner is standing on a task
            # branch: rolling-begin-task ran and the exercise was never
            # written, or something was left behind. Parking needs the
            # task file, so there is nothing to set aside, and opening a
            # step here would put the step's own task on this branch.
            cur = self.repo.branch()
            if cur and rules.is_task_branch(cur):
                raise Refused(
                    f"the repository is on {cur}, a task branch, with no task open. A detour starts from the learner's own "
                    f"branch, never from a task's. Leaving it is theirs to do (git switch <their branch>, then git branch -D "
                    f"{cur} if nothing on it is wanted); say so and stop"
                )
        try:
            self.learner.dir.mkdir(parents=True, exist_ok=True)
            self.learner.open_detour_file.write_text(slug + "\n", encoding="utf-8")
        except OSError as e:
            raise Refused(
                f"the detour could not be recorded ({e})" + (
                    "; the task is parked, so rolling-resume-task puts the learner back and nothing is lost"
                    if out else "; nothing was moved"
                )
            )
        first = plan.steps[0]
        out += self._open_step(first)
        return out + [f"DETOUR: {slug} is open, {len(plan.steps)} step(s), returning to {plan.returns_to}"]

    def _writable(self, p: Path, what: str) -> None:
        if p.is_symlink():
            raise Refused(f"{p} is a symbolic link; {what} is a plain file the toolkit writes, so remove the link first")
        if p.exists() and not p.is_file():
            raise Refused(f"{p} is not a plain file; remove it and try again ({what})")

    def _open_step(self, slug: str) -> List[str]:
        """Write the open-lesson marker for a step. Best effort in the
        same sense as _mark_lesson: a marker that cannot be written is
        said, and the detour is still open, so a later close or a
        rolling-begin-lesson opens the step."""
        try:
            self.learner.lesson_file.write_text(slug + "\n", encoding="utf-8")
        except OSError as e:
            return [f"note: the open-lesson marker could not be written ({e}); the detour is open, and rolling-begin-lesson {slug} opens the step"]
        return [f"STEP: {slug} is open (no exercise built yet)"]

    # ---- advance, and end

    def advance(self, closed: str) -> List[str]:
        """The step CLOSED is done: open the next one, or end the detour
        after the last. Called by rolling-close-task, which has just
        removed the step's own files."""
        plan = self.learner.detour()
        if plan is None:
            # No plan, so no next step to open and no returns-to to go
            # back to. End it the ordinary way regardless: ending is
            # what brings a parked task back, and clearing the marker
            # on its own would leave one with nothing that resumes it.
            slug = self.learner.open_detour()
            return [f"the detour '{slug}' is open but its plan cannot be read, so it ends here"] + self.end(None)
        if not closed or not plan.has_step(closed):
            # Not a state the toolkit makes: the marker names the step
            # while a detour is open. Ending the detour on it would be a
            # large guess about a small inconsistency, so it is said and
            # the detour is left for rolling-close-detour.
            return [
                f"note: the detour {plan.slug} is open, but the lesson that just closed "
                f"({closed or 'none named'}) is not one of its steps ({', '.join(plan.steps)}); "
                "the detour is left open, and rolling-close-detour ends it"
            ]
        nxt = plan.step_after(closed)
        if nxt is not None:
            return [f"step {plan.steps.index(nxt) + 1} of {len(plan.steps)} in detour {plan.slug}:"] + self._open_step(nxt)
        return self.end(plan, last=True)

    def end(self, plan: Optional[Detour] = None, last: bool = False) -> List[str]:
        """End the detour: resume the parked task, then clear the marker,
        in that order. A resume the tree refuses leaves both — the detour
        open and the task parked — so the learner can deal with the tree
        and a later run finishes it, rather than either being orphaned.

        With nothing parked (the detour was taken before an exercise
        existed), the lesson it returns to is opened instead, which is
        where the learner left the course."""
        if plan is None:
            plan = self.learner.detour()
        out = [f"detour {plan.slug if plan else self.learner.open_detour() or '(unnamed)'}: " + ("the last step is done" if last else "ended before it finished")]
        if self.learner.has_parked():
            try:
                out += Tasks(self.repo, self.learner).resume(session.recorded(self.learner))
            except Refused as e:
                return out + [
                    str(e),
                    "the detour is still open and the task is still parked, so neither is lost; "
                    "rolling-close-detour finishes this once the tree allows it",
                ]
        elif plan is not None and plan.returns_to:
            out += self._reopen(plan.returns_to)
        self._clear()
        return out + ["detour cleared"]

    def _reopen(self, lesson: str) -> List[str]:
        """The lesson the detour returns to, open again. A lesson the map
        no longer has is said rather than opened: the slug would name
        nothing, and a marker pointing at nothing is worse than none."""
        if not (self.map_dir / "lessons" / f"{lesson}.md").is_file():
            return [f"note: the lesson this detour returned to, {lesson}, is no longer in the map; no lesson is open"]
        try:
            self.learner.lesson_file.write_text(lesson + "\n", encoding="utf-8")
        except OSError as e:
            return [f"note: {lesson} could not be opened again ({e}); rolling-begin-lesson {lesson} does it"]
        return [f"LESSON: {lesson} is open again, where the detour was taken from"]

    def _clear(self) -> None:
        """Remove the open-detour marker. Best effort: what it names has
        been dealt with by the time this runs, and a marker that cannot
        be removed is reported by the next begin, which refuses on it."""
        try:
            p = self.learner.open_detour_file
            if p.is_symlink() or p.is_file():
                p.unlink()
        except OSError:
            pass
