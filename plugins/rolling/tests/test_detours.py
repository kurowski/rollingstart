"""Detours: the pen that writes one, and the lifecycle that runs it.

A detour is a side-quest off the course, of one to three steps, each
step a lesson — one the tutor wrote for this learner or one borrowed
from the map outside their destination. The properties these tests hold
to are the ones the learner would notice: the task they were doing is
waiting for them when the detour ends, with their work; the destination
never moves; and nothing the toolkit refuses leaves either the detour
or the task stranded.
"""

from __future__ import annotations

import unittest

from support import WorldTest

PLAN = """---
gap: never sure when to quote a shell variable
returns-to: greet-politely
steps:
{steps}
---

Two steps: what the quotes do here, then the author's own setup lesson.
"""

STEP = """---
title: Quoting in this repository
region: greeting
depth: working
assumes: [sh]
---

Where the quotes matter here.

## Pointers

- src/greet.sh

## Rubric

- Can say what breaks without the quotes.
"""

PROFILE = """# Profile

## Background
Fluent in sh.

## Destination
greeting: working

## Why
Here to own the greeting.

## Satisfied
"""


class DetourTest(WorldTest):
    """Shared scaffolding: a learner with a destination, a session
    claimed, and the helpers that write a plan and a step."""

    def setUp(self) -> None:
        super().setUp()
        self.assertRuns("claim-session", "s1")
        self.w.learner.dir.mkdir(parents=True, exist_ok=True)
        self.w.learner.profile.write_text(PROFILE, encoding="utf-8")

    def plan(self, slug="quoting", steps=("quoting-basics", "setup"), status=0, body=None):
        text = body if body is not None else PLAN.format(steps="\n".join(f"  - {s}" for s in steps))
        return self.assertRuns("write", "detour", slug, status=status, stdin=text)

    def step(self, detour="quoting", slug="quoting-basics", status=0, body=None):
        return self.assertRuns("write", "step", detour, slug, status=status, stdin=body if body is not None else STEP)

    def take(self, slug="quoting", lesson="greet-politely"):
        """Open the lesson the detour returns to, then take the detour.
        A detour is a side trip off a lesson, so `begin-detour` refuses
        unless that lesson is the open one."""
        if self.w.learner.open_lesson() != lesson:
            self.assertRuns("begin-lesson", lesson)
        return self.assertRuns("begin-detour", slug)

    def open_task(self, lesson="greet-politely"):
        """A begun task with the learner's work in the tree, as the pen
        leaves it: begin-task cuts the branch, the task file follows."""
        w = self.w
        branch, base = w.begin(lesson, "--fix", w.fix, "--held", "tests/greet.test.sh")
        w.held_task(branch, base, lesson=lesson)
        w.write("src/greet.sh", w.read("src/greet.sh") + "# the learner was here\n")
        return branch, base

    def destination(self) -> str:
        return self.w.learner.profile.read_text(encoding="utf-8").split("## Destination")[1].split("##")[0].strip()


class ThePenTest(DetourTest):
    """What rolling-write detour and rolling-write step accept, and what
    they refuse before anything lands."""

    def test_a_plan_and_a_step_land(self):
        self.assertIn("wrote detours/quoting.md", self.plan())
        self.assertIn("wrote detours/quoting/quoting-basics.md", self.step())
        d = self.w.learner.detour_plan("quoting")
        self.assertEqual(d.steps, ["quoting-basics", "setup"])
        self.assertEqual(d.returns_to, "greet-politely")
        self.assertIn("never sure when to quote", d.gap)

    def test_a_fourth_step_is_refused(self):
        out = self.plan(steps=("a", "b", "c", "d"), status=1)
        self.assertIn("a detour is at most 3", out)
        self.assertIn("suggest a teammate", out)
        self.assertFalse((self.w.learner.detours / "quoting.md").exists(), "nothing landed")

    def test_the_same_step_twice_is_refused(self):
        self.assertIn("listed twice", self.plan(steps=("setup", "setup"), status=1))

    def test_a_step_that_is_the_lesson_returned_to_is_refused(self):
        self.assertIn("does not step through its own starting point", self.plan(steps=("greet-politely",), status=1))

    def test_the_plan_needs_a_gap_a_returns_to_and_a_body(self):
        out = self.plan(status=1, body="---\nsteps:\n  - setup\n---\n")
        for want in ("gap is missing", "returns-to is missing", "no body"):
            self.assertIn(want, out)

    def test_returns_to_must_be_a_lesson_in_the_map(self):
        out = self.plan(status=1, body=PLAN.format(steps="  - setup").replace("returns-to: greet-politely", "returns-to: no-such-lesson"))
        self.assertIn("is not a lesson in the map", out)

    def test_a_step_may_not_shadow_a_map_lesson(self):
        self.plan(steps=("setup",))
        out = self.step(slug="setup", status=1)
        self.assertIn("is a lesson in the map", out)
        self.assertIn("Borrow it instead", out)
        self.assertFalse(self.w.learner.step_file("quoting", "setup").exists())

    def test_a_step_the_plan_does_not_name_is_refused(self):
        self.plan()
        self.assertIn("is not a step of 'quoting'", self.step(slug="unplanned", status=1))

    def test_a_step_without_its_plan_is_refused(self):
        self.assertIn("no detour 'quoting'", self.step(status=1))

    def test_a_pointer_must_be_in_the_tree(self):
        self.plan()
        out = self.step(status=1, body=STEP.replace("- src/greet.sh", "- src/nowhere.sh"))
        self.assertIn("pointer 'src/nowhere.sh' is not in the tree", out)

    def test_a_step_needs_pointers_and_a_rubric(self):
        self.plan()
        out = self.step(status=1, body=STEP.replace("## Pointers\n\n- src/greet.sh\n\n", "").replace("## Rubric", "## Notes"))
        self.assertIn("no ## Pointers heading", out)
        self.assertIn("no ## Rubric heading", out)

    def test_requires_and_exercise_are_a_map_lessons_fields(self):
        self.plan()
        out = self.step(status=1, body=STEP.replace("depth: working", "depth: working\nrequires: [setup]\nexercise: none"))
        self.assertIn("requires is for a map lesson", out)
        self.assertIn("exercise is for a map lesson", out)
        self.assertNotIn("but it takes one value", out, "a field that does not belong gets no advice about its shape")

    def test_a_step_takes_the_region_and_depth_it_returns_to(self):
        self.plan()
        out = self.step(status=1, body=STEP.replace("region: greeting", "region: platform").replace("depth: working", "depth: deep"))
        self.assertIn("region is 'platform'", out)
        self.assertIn("whose region is 'greeting'", out)
        self.assertIn("depth is 'deep'", out)

    def test_the_open_detours_plan_cannot_be_rewritten(self):
        self.plan(steps=("setup",))
        self.assertRuns("begin-lesson", "greet-politely")
        self.assertRuns("begin-detour", "quoting")
        out = self.plan(steps=("setup",), status=1)
        self.assertIn("is open", out)
        self.assertIn("rolling-close-detour", out)


class BeginTest(DetourTest):
    def test_it_refuses_a_plan_that_is_not_there(self):
        self.assertIn("does not exist", self.assertRuns("begin-detour", "nope", status=1))

    def test_it_refuses_a_step_nothing_can_serve(self):
        self.plan(steps=("never-written",))
        self.assertRuns("begin-lesson", "greet-politely")
        out = self.assertRuns("begin-detour", "quoting", status=1)
        self.assertIn("neither written under detours/quoting/ nor a lesson in the map", out)
        self.assertIn("never-written", out)
        self.assertEqual(self.w.learner.open_detour(), "", "nothing was opened")

    def test_it_refuses_a_second_detour(self):
        self.plan(steps=("setup",))
        self.take()
        self.assertIn("one runs at a time", self.assertRuns("begin-detour", "quoting", status=1))

    def test_it_refuses_a_stray_task_branch(self):
        """begin-task ran and the exercise was never written: there is no
        task to park, and a step must not be opened standing here."""
        self.plan(steps=("setup",))
        self.assertRuns("begin-lesson", "greet-politely")
        self.w.begin("greet-politely", "--fix", self.w.fix)
        out = self.assertRuns("begin-detour", "quoting", status=1)
        self.assertIn("a task branch, with no task open", out)
        self.assertEqual(self.w.learner.open_detour(), "")

    def test_it_refuses_a_plan_that_returns_to_another_lesson(self):
        """The plan says where the detour goes back to, and that has to
        be where the learner is: otherwise the detour would end by
        opening a lesson they never picked, which is the tutor choosing
        their route."""
        self.plan(steps=("setup",))
        self.assertRuns("begin-lesson", "greet-politely")
        self.w.learner.lesson_file.write_text("setup\n", encoding="utf-8")
        out = self.assertRuns("begin-detour", "quoting", status=1)
        self.assertIn("returns to greet-politely, but the open lesson is setup", out)
        self.assertEqual(self.w.learner.open_detour(), "")

    def test_it_refuses_with_no_lesson_open(self):
        self.plan(steps=("setup",))
        out = self.assertRuns("begin-detour", "quoting", status=1)
        self.assertIn("no lesson is open", out)
        self.assertEqual(self.w.learner.open_detour(), "")

    def test_it_opens_the_first_step(self):
        self.plan()
        self.step()
        out = self.take()
        self.assertIn("STEP: quoting-basics is open", out)
        self.assertIn("returning to greet-politely", out)
        self.assertEqual(self.w.learner.open_detour(), "quoting")
        self.assertEqual(self.w.learner.open_lesson(), "quoting-basics")


class StepsAreLessonsTest(DetourTest):
    """A step is served by everything that already serves a lesson."""

    def setUp(self) -> None:
        super().setUp()
        self.plan()
        self.step()
        self.take()

    def test_show_lesson_finds_the_step(self):
        out = self.assertRuns("show", "lesson")
        self.assertIn("### quoting-basics (step of detour quoting)", out)
        self.assertIn("Where the quotes matter here", out)

    def test_show_detour_marks_the_open_step_and_names_its_kind(self):
        out = self.assertRuns("show", "detour")
        self.assertIn("step 1 of 2: quoting-basics (the tutor's)  <- open", out)
        self.assertIn("step 2 of 2: setup (borrowed from the map)", out)

    def test_begin_lesson_opens_a_step_by_name(self):
        self.assertRuns("close-task")                       # step 1 closes, step 2 opens
        self.assertIn("quoting-basics is open", self.assertRuns("begin-lesson", "quoting-basics"))

    def test_a_step_gets_its_own_exercise_and_the_task_validates(self):
        """The task validator knows a map's lessons; a step is not one,
        and a task for a step must still validate or no step could ever
        have an exercise."""
        branch, base = self.w.begin("quoting-basics", "--fix", self.w.fix, "--held", "tests/greet.test.sh")
        self.w.held_task(branch, base, lesson="quoting-basics")
        self.assertIn("task ok", self.assertRuns("check-task"))

    def test_an_unknown_lesson_says_so_without_inventing_a_step(self):
        self.assertIn("no lesson or step 'nope'", self.assertRuns("show", "lesson", "nope"))


class ThroughADetourTest(DetourTest):
    """The whole thing, as a learner meets it: stuck mid-task, a detour
    of two steps, and back in the task with their work."""

    def test_a_detour_mid_task_parks_runs_its_steps_and_comes_back(self):
        w = self.w
        self.assertRuns("begin-lesson", "greet-politely")
        branch, _ = self.open_task()
        before = self.destination()
        self.plan()
        self.step()

        out = self.take()
        self.assertIn("committed the learner's uncommitted work", out)
        self.assertIn("parked greet-politely", out)
        self.assertOnBranch("main")
        self.assertClean()
        self.assertTrue(w.learner.has_parked())
        self.assertFalse(w.learner.has_task())
        self.assertIn("parked: greet-politely", self.assertRuns("show", "detour"))

        # Step one, with an exercise of its own, then closed.
        sbranch, sbase = w.begin("quoting-basics", "--fix", w.fix, "--held", "tests/greet.test.sh")
        w.held_task(sbranch, sbase, lesson="quoting-basics")
        self.assertIn("task ok", self.assertRuns("check-task"))
        self.assertRuns("end-task")
        out = self.assertRuns("close-task")
        self.assertIn("STEP: setup is open", out)
        self.assertEqual(w.learner.open_lesson(), "setup", "the borrowed lesson is step two")
        self.assertTrue(w.learner.has_parked(), "still waiting")

        # Step two closes: the detour ends and the task comes back.
        self.assertRuns("claim-session", "s2")
        out = self.assertRuns("close-task")
        self.assertIn("the last step is done", out)
        self.assertIn("detour cleared", out)
        self.assertOnBranch(branch)
        self.assertTrue(w.learner.has_task())
        self.assertFalse(w.learner.has_parked())
        self.assertEqual(w.learner.open_detour(), "")
        self.assertIn("the learner was here", w.read("src/greet.sh"), "their work, as they left it")
        t = w.learner.task()
        self.assertEqual(t.lesson, "greet-politely")
        self.assertEqual(t.tutor_session, "s2", "restamped, or the write guard would not fire")
        self.assertEqual(self.destination(), before, "a detour is a side trip, not a reroute")

    def test_a_detour_before_any_exercise_reopens_the_lesson(self):
        """Nothing to park: the learner was in the walkthrough. The
        lesson they left is open again at the end."""
        self.assertRuns("begin-lesson", "greet-politely")
        self.plan(steps=("setup",))
        self.take()
        self.assertEqual(self.w.learner.open_lesson(), "setup")
        out = self.assertRuns("close-task")
        self.assertIn("LESSON: greet-politely is open again", out)
        self.assertEqual(self.w.learner.open_lesson(), "greet-politely")
        self.assertEqual(self.w.learner.open_detour(), "")

    def test_a_lesson_the_map_has_lost_is_said_not_opened(self):
        self.assertRuns("begin-lesson", "greet-politely")
        self.plan(steps=("setup",))
        self.take()
        (self.w.top / ".rolling/lessons/greet-politely.md").unlink()
        out = self.assertRuns("close-task")
        self.assertIn("is no longer in the map", out)
        self.assertEqual(self.w.learner.open_lesson(), "")
        self.assertEqual(self.w.learner.open_detour(), "", "the detour still ended")

    def test_a_plan_that_vanishes_still_gives_the_task_back(self):
        """The one path that clears the detour without a next step or a
        returns-to. It still has to end the detour the ordinary way,
        because ending is what brings a parked task back."""
        w = self.w
        self.assertRuns("begin-lesson", "greet-politely")
        branch, _ = self.open_task()
        self.plan(steps=("setup",))
        self.take()
        self.assertTrue(w.learner.has_parked())
        (w.learner.detours / "quoting.md").unlink()

        out = self.assertRuns("close-task")
        self.assertIn("cannot be read", out)
        self.assertEqual(w.learner.open_detour(), "")
        self.assertFalse(w.learner.has_parked(), "the parked task is not left behind")
        self.assertTrue(w.learner.has_task())
        self.assertOnBranch(branch)
        self.assertIn("the learner was here", w.read("src/greet.sh"))

    def test_git_failing_inside_the_resume_still_exits_zero(self):
        """close-task's promise is that the step is closed, so whatever
        the detour then cannot do is a note at exit 0 — a refusal and a
        git failure alike. An index git cannot map is the cheapest real
        git failure to stage."""
        w = self.w
        self.assertRuns("begin-lesson", "greet-politely")
        self.open_task()
        self.plan(steps=("setup",))
        self.take()
        index = w.top / ".git/index"
        index.unlink()
        index.mkdir()
        self.addCleanup(lambda: index.is_dir() and index.rmdir())

        out = self.assertRuns("close-task")          # status=0 is the assertion
        self.assertIn("removed lesson", out, "the step still closed")
        self.assertIn("rolling-close-detour", out, "and the detour is left to be ended")
        self.assertEqual(w.learner.open_detour(), "quoting")
        self.assertTrue(w.learner.has_parked(), "nothing of theirs was lost")

    def test_closing_a_lesson_that_is_not_a_step_leaves_the_detour(self):
        """Not a state the toolkit makes. Ending the detour on it would
        be a large guess about a small inconsistency."""
        self.plan(steps=("setup",))
        self.take()
        self.w.learner.lesson_file.write_text("greet-politely\n", encoding="utf-8")
        out = self.assertRuns("close-task")
        self.assertIn("is not one of its steps", out)
        self.assertEqual(self.w.learner.open_detour(), "quoting", "left for rolling-close-detour")


class CancelTest(DetourTest):
    """/rolling:cancel mid-detour ends the detour, not the step."""

    def test_it_refuses_while_the_learner_stands_on_the_task_branch(self):
        self.plan(steps=("setup",))
        self.assertRuns("begin-lesson", "greet-politely")
        self.assertRuns("begin-detour", "quoting")
        branch, base = self.w.begin("setup", "--fix", self.w.fix)
        self.w.held_task(branch, base, lesson="setup", held=[], held_verify=[], expect_fail_on_base=[])
        out = self.assertRuns("close-detour", status=1)
        self.assertIn("rolling-end-task first", out)
        self.assertEqual(self.w.learner.open_detour(), "quoting")
        self.assertTrue(self.w.learner.has_task(), "nothing was removed")

    def test_an_ended_task_on_the_step_is_closed_with_the_detour(self):
        """end-task leaves task.md in place — it only moves the tree —
        so the refusal above has to read the branch, not the file, or a
        learner who ended their step's exercise could never cancel."""
        w = self.w
        self.assertRuns("begin-lesson", "greet-politely")
        branch, _ = self.open_task()
        self.plan(steps=("setup",))
        self.take()
        sbranch, sbase = w.begin("setup", "--fix", w.fix)
        w.held_task(sbranch, sbase, lesson="setup", held=[], held_verify=[], expect_fail_on_base=[])
        self.assertRuns("end-task")
        self.assertTrue(w.learner.has_task(), "end-task leaves the file; close-task removes it")

        out = self.assertRuns("close-detour")
        self.assertIn("removed task.md", out, "the step's own files go")
        self.assertOnBranch(branch, )
        self.assertEqual(w.learner.task().lesson, "greet-politely", "and the parked task is back")
        self.assertEqual(w.learner.open_detour(), "")

    def test_it_resumes_the_parked_task_and_clears_the_detour(self):
        w = self.w
        self.assertRuns("begin-lesson", "greet-politely")
        branch, _ = self.open_task()
        self.plan(steps=("setup",))
        self.take()
        out = self.assertRuns("close-detour")
        self.assertIn("ended before it finished", out)
        self.assertOnBranch(branch)
        self.assertTrue(w.learner.has_task())
        self.assertEqual(w.learner.open_detour(), "")
        self.assertIn("the learner was here", w.read("src/greet.sh"))

    def test_a_refused_resume_leaves_both_and_a_second_run_finishes(self):
        """The order is resume, then clear: a tree the resume refuses
        leaves the detour open and the task parked, both still there."""
        w = self.w
        self.assertRuns("begin-lesson", "greet-politely")
        branch, _ = self.open_task()
        self.plan(steps=("setup",))
        self.take()
        w.write("their-own-file.txt", "not the tutor's business\n")

        out = self.assertRuns("close-detour", status=1)
        self.assertIn("the working tree is not clean", out)
        self.assertIn("neither is lost", out)
        self.assertEqual(w.learner.open_detour(), "quoting", "still open")
        self.assertTrue(w.learner.has_parked(), "still parked")
        self.assertOnBranch("main")

        (w.top / "their-own-file.txt").unlink()
        self.assertRuns("close-detour")
        self.assertOnBranch(branch)
        self.assertTrue(w.learner.has_task())
        self.assertEqual(w.learner.open_detour(), "")

    def test_it_refuses_when_no_detour_is_open(self):
        self.assertIn("no detour is open", self.assertRuns("close-detour", status=1))


if __name__ == "__main__":
    unittest.main()
