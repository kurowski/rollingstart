"""The three validators, against the lists in docs/map.md and
docs/profile.md: the scratch map is clean, each listed fault is caught,
warnings are warnings."""

from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from support import WorldTest

from rolling import validate
from rolling.model import Map


def whats(faults):
    return [f.what for f in faults]


class ExerciseFieldTest(WorldTest):
    def test_exercise_none_is_allowed_and_anything_else_is_not(self):
        w = self.w
        w.write(".rolling/lessons/tour.md", "---\ntitle: Tour\nregion: platform\ndepth: orientation\nexercise: none\n---\n\nA look around.\n\n## Rubric\n\n- Nothing to change.\n")
        self.assertIn("MAP: ok", self.assertRuns("show", "map-check"))
        w.write(".rolling/lessons/tour.md", "---\ntitle: Tour\nregion: platform\ndepth: orientation\nexercise: optional\n---\n\nA look around.\n\n## Rubric\n\n- Nothing to change.\n")
        self.assertIn("exercise 'optional' is not 'none'", self.assertRuns("show", "map-check"))
        w.write(".rolling/lessons/tour.md", "---\ntitle: Tour\nregion: platform\ndepth: orientation\nexercise: none\n---\n\nA look around.\n\n## Rubric\n\n- Nothing to change.\n")
        w.write(".rolling/lessons/tour/one.md", "---\nfix: " + w.fix + "\nscope: src\nverify: check\n---\n\n## Brief\n\nx\n\n## Source\n\ny\n")
        self.assertIn("would never be served", self.assertRuns("show", "map-check"))


class MapValidationTest(WorldTest):
    def setUp(self):
        super().setUp()
        self.m = self.w.root / "m"

    def copy_map(self):
        shutil.rmtree(self.m, ignore_errors=True)
        shutil.copytree(self.w.top / ".rolling", self.m)
        return self.m

    def edit(self, rel, old, new):
        p = self.m / rel
        p.write_text(p.read_text().replace(old, new, 1))

    def faults_after(self, rel, old, new):
        self.copy_map()
        self.edit(rel, old, new)
        return whats(validate.validate_map(self.m))

    def test_scratch_map_is_clean(self):
        self.assertEqual(validate.validate_map(self.w.top / ".rolling"), [])
        m = Map.load(self.w.top / ".rolling")
        self.assertEqual((m.name, m.mode, m.regions, m.courses), ("Scratch", "write", ["greeting", "platform"], ["Generalist"]))
        self.assertEqual([p.name for p in m.lesson_files()], ["greet-politely.md", "setup.md"])

    def test_map_frontmatter_faults(self):
        self.assertIn("mode 'maybe' is not write or direct", self.faults_after("map.md", "mode: write", "mode: maybe"))
        self.assertIn("name is missing", self.faults_after("map.md", "name: Scratch\n", ""))
        self.assertIn("unknown field 'commandz'", self.faults_after("map.md", "commands:", "commandz:"))
        self.assertIn("destructive names 'drop', which is not an operation", self.faults_after("map.md", "  - reset", "  - drop"))
        self.assertIn("commands.evil ends in an operator (; & | > < \\) or contains '#', so arguments could not be appended safely",
                      self.faults_after("map.md", "  args: sh args.sh\n", "  args: sh args.sh\n  evil: echo ran;\n"))
        for bad in ("sh args.sh >", "sh args.sh;#x", "sh args.sh # note"):
            self.assertTrue(any("commands.bad ends in an operator" in f for f in self.faults_after("map.md", "  args: sh args.sh\n", f"  args: sh args.sh\n  bad: {bad}\n")), bad)

    def test_a_field_in_the_wrong_shape_is_a_fault(self):
        self.assertIn("destructive is a scalar, but it must be a list ([a, b])", self.faults_after("map.md", "destructive:\n  - reset", "destructive: reset"))
        self.assertIn("requires is a scalar, but it must be a list ([a, b])", self.faults_after("lessons/greet-politely.md", "requires: [setup]", "requires: setup"))
        self.assertIn("name is a list, but it takes one value", self.faults_after("map.md", "name: Scratch", "name: [Scratch]"))

    def test_map_body_faults(self):
        self.assertIn("no ## Regions heading", self.faults_after("map.md", "## Regions", "## Places"))
        self.assertIn("## Suggested courses has no ### course heading under it", self.faults_after("map.md", "### Generalist", "#### Generalist"))

    def test_missing_map_or_frontmatter(self):
        self.copy_map()
        (self.m / "map.md").unlink()
        self.assertIn("does not exist", whats(validate.validate_map(self.m)))
        (self.m / "map.md").write_text("no fence\n")
        self.assertIn("no frontmatter block (a --- line first, another closing it)", whats(validate.validate_map(self.m)))

    def test_lesson_faults(self):
        L = "lessons/greet-politely.md"
        self.assertIn("region 'greetings' is not in the map's ## Regions", self.faults_after(L, "region: greeting", "region: greetings"))
        self.assertIn("depth 'expert' is not orientation, working, or deep", self.faults_after(L, "depth: working", "depth: expert"))
        self.assertIn("requires 'ghost', which is not a lesson", self.faults_after(L, "requires: [setup]", "requires: [setup, ghost]"))
        self.assertIn("requires 'setup' twice", self.faults_after(L, "requires: [setup]", "requires: [setup, setup]"))
        self.assertIn("requires itself", self.faults_after(L, "requires: [setup]", "requires: [greet-politely]"))
        self.assertIn("no ## Rubric heading", self.faults_after("lessons/setup.md", "## Rubric", "## Rubrik"))
        self.assertIn("test 'given' is not held or shown", self.faults_after("lessons/setup.md", "test: shown", "test: given"))
        faults = self.faults_after("lessons/setup.md", "title:", "titel:")
        self.assertIn("unknown field 'titel'", faults)
        self.assertIn("title is missing", faults)

    def test_cycle(self):
        faults = self.faults_after("lessons/setup.md", "requires: []", "requires: [greet-politely]")
        self.assertTrue(any(f.startswith("requires has a cycle through") for f in faults), faults)

    def test_directory_shape(self):
        self.copy_map()
        shutil.copy(self.m / "lessons/setup.md", self.m / "lessons/Setup-Two.md")
        (self.m / "lessons/drafts").mkdir()
        (self.m / "lessons/notes.txt").write_text("x")
        faults = whats(validate.validate_map(self.m))
        self.assertIn("'Setup-Two' is not a slug (lowercase kebab-case)", faults)
        self.assertIn("a directory in lessons/ must match a lesson file beside it (drafts.md)", faults)
        self.assertIn("not a lesson file (every file in lessons/ ends in .md)", faults)

    def test_crlf_map_is_clean(self):
        self.copy_map()
        p = self.m / "map.md"
        p.write_bytes(p.read_text().replace("\n", "\r\n").encode())
        self.assertEqual(validate.validate_map(self.m), [])

    def test_author_tasks(self):
        self.copy_map()
        tdir = self.m / "lessons/greet-politely"
        tdir.mkdir()
        (tdir / "be-polite.md").write_text("---\nmode: write\nscope: src/greet.sh\nverify: check\nheld: tests/greet.test.sh\nheld-verify: test tests/greet.test.sh\nfix: 0123456\n---\n\n## Brief\n\nBe polite.\n\n## Source\n\nThe fix.\n")
        self.assertEqual(validate.validate_map(self.m), [])
        held_only = "---\nmode: write\nscope: src/greet.sh\nverify: check\nheld: tests/greet.test.sh\n---\n\n## Brief\n\nBe polite.\n\n## Source\n\nThe fix.\n"
        (tdir / "held-only.md").write_text(held_only)
        self.assertIn("held: paths need a held-verify: line to run them; a held test nothing runs is never applied and never checked",
                      whats(validate.validate_map(self.m)), "the author's task file gets the fault too (#14)")
        (tdir / "held-only.md").unlink()
        destructive_setup = "---\nmode: write\nscope: src/greet.sh\nverify: check\nreference-setup: reset\n---\n\n## Brief\n\nBe polite.\n\n## Source\n\nThe fix.\n"
        (tdir / "wipes.md").write_text(destructive_setup)
        self.assertIn("reference-setup names 'reset', which the map lists as destructive; the proof runs unattended, and a destructive operation waits for the learner's yes",
                      whats(validate.validate_map(self.m)), "the author's task file gets this fault too (#32)")
        (tdir / "wipes.md").unlink()
        (tdir / "bad.md").write_text("---\nverify: nope\nfix: xyz\nbogus: 1\n---\n## Source\n")
        faults = whats(validate.validate_map(self.m))
        self.assertIn("verify names 'nope', which is not a command in the map", faults)
        self.assertIn("fix 'xyz' is not 7 to 40 hex characters", faults)
        self.assertIn("unknown field 'bogus'", faults)
        self.assertIn("no ## Brief or ## Situation heading", faults)
        self.assertEqual(len(faults), 4)


PROFILE = "# Profile\n\n## Background\nKnows sh.\n\n## Destination\ngreeting: working\nplatform: orientation\n\n## Why\nBecause.\n\n## Satisfied\n- setup (2026-09-15)\n"


class ProfileValidationTest(WorldTest):
    def check(self, text):
        p = self.w.learner.profile
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return validate.validate_profile(p, ["greeting", "platform"])

    def test_clean(self):
        self.assertEqual(self.check(PROFILE), [])

    def test_missing(self):
        self.assertIn("does not exist", validate.validate_profile(self.w.learner.profile, None)[0].what)

    def test_faults(self):
        self.assertIn("destination line is not '<region>: <orientation|working|deep>': greeting: expert", whats(self.check(PROFILE.replace("greeting: working", "greeting: expert"))))
        self.assertIn("destination lists 'greeting' twice", whats(self.check(PROFILE.replace("platform: orientation", "greeting: deep"))))
        self.assertIn("satisfied line is not '- <slug> (<YYYY-MM-DD>)': - setup (yesterday)", whats(self.check(PROFILE.replace("(2026-09-15)", "(yesterday)"))))
        self.assertTrue(any(f.startswith("the headings ## Background") for f in whats(self.check(PROFILE.replace("## Why", "## Reasons")))))
        self.assertEqual(self.check(PROFILE + "\n## Notes\nwhatever\n"), [], "an extra heading is allowed")

    def test_unknown_region_is_a_warning(self):
        results = self.check(PROFILE.replace("greeting: working", "nowhere: working"))
        self.assertEqual([r.warning for r in results], [True])
        self.assertIn("destination region 'nowhere' is not in the map's ## Regions", results[0].what)
        self.assertEqual(self.check.__self__.w.run("check-profile")[0], 0, "a warning is not a fault")

    def test_trailing_space_on_a_heading_still_checks(self):
        text = PROFILE.replace("## Destination\n", "## Destination \n").replace("greeting: working", "greeting: expert").replace("## Satisfied\n", "## Satisfied \n").replace("(2026-09-15)", "(nope)")
        faults = whats(self.check(text))
        self.assertTrue(any("destination line is not" in f for f in faults))
        self.assertTrue(any("satisfied line is not" in f for f in faults))


class DetourValidationTest(WorldTest):
    """validate_detour and validate_step on the fault list, rather than
    on the pen's rendering of it (test_detours.py has that)."""

    PLAN = "---\ngap: never used dataclasses\nreturns-to: greet-politely\nsteps:\n  - one\n---\n\nWhy this step.\n"
    STEP = "---\ntitle: T\nregion: greeting\ndepth: working\n---\n\nBody.\n\n## Pointers\n\n- src/greet.sh\n\n## Rubric\n\n- Can say so.\n"

    def plan_faults(self, text):
        p = self.w.root / "plan.md"
        p.write_text(text, encoding="utf-8")
        return whats(validate.validate_detour(p, self.w.top / ".rolling"))

    def step_faults(self, text):
        p = self.w.root / "step.md"
        p.write_text(text, encoding="utf-8")
        return whats(validate.validate_step(p, self.w.top))

    def test_a_clean_plan_and_step_have_no_faults(self):
        self.assertEqual(self.plan_faults(self.PLAN), [])
        self.assertEqual(self.step_faults(self.STEP), [])

    def test_a_missing_plan_says_so(self):
        self.assertEqual(whats(validate.validate_detour(self.w.root / "nope.md", self.w.top / ".rolling")),
                         ["does not exist (no such detour)"])

    def test_steps_must_be_a_list_of_one_to_three_unique_slugs(self):
        self.assertIn("steps is missing: one to three, in order", self.plan_faults(self.PLAN.replace("steps:\n  - one\n", "")))
        self.assertIn("4 steps; a detour is at most 3", " ".join(self.plan_faults(self.PLAN.replace("  - one", "  - a\n  - b\n  - c\n  - d"))))
        self.assertIn("step 'a' is listed twice", " ".join(self.plan_faults(self.PLAN.replace("  - one", "  - a\n  - a"))))
        self.assertIn("is not a slug", " ".join(self.plan_faults(self.PLAN.replace("  - one", "  - Not A Slug"))))
        self.assertIn("but it must be a list", " ".join(self.plan_faults(self.PLAN.replace("steps:\n  - one", "steps: one"))))

    def test_an_unknown_field_is_reported_once_and_not_advised_on(self):
        """A misspelled field gets the unknown-field fault and nothing
        about its shape: advice towards a field that does not exist. The
        misspelling here is list-shaped, which is what makes the shape
        check skip load-bearing."""
        faults = self.plan_faults(self.PLAN.replace("gap: never used dataclasses", "gaps: [a, b]"))
        self.assertEqual([f for f in faults if "gaps" in f], ["unknown field 'gaps'"])
        self.assertIn("gap is missing: what the learner is missing, in their words", faults)

    def test_a_steps_pointers_must_be_in_the_tree(self):
        self.assertIn("pointer 'src/nowhere.sh' is not in the tree",
                      self.step_faults(self.STEP.replace("- src/greet.sh", "- src/nowhere.sh")))
        self.assertIn("pointer '../outside' is not a plain repository-relative path",
                      self.step_faults(self.STEP.replace("- src/greet.sh", "- ../outside")))
        self.assertIn("pointer 'src/greet.sh' is listed twice",
                      self.step_faults(self.STEP.replace("- src/greet.sh", "- src/greet.sh\n- src/greet.sh")))
        self.assertIn("## Pointers has no `- <path>` lines",
                      self.step_faults(self.STEP.replace("- src/greet.sh\n", "")))

    def test_a_step_is_a_lesson_minus_requires_and_exercise(self):
        self.assertIn("requires is for a map lesson: a step's order is the detour's steps: list, and nothing serves a step but the detour",
                      self.step_faults(self.STEP.replace("depth: working", "depth: working\nrequires: [setup]")))
        self.assertIn("exercise is for a map lesson: a step the tutor wrote offers one, since a gap worth a detour is worth doing something about",
                      self.step_faults(self.STEP.replace("depth: working", "depth: working\nexercise: none")))
        for want in ("title is missing", "region is missing", "depth is missing"):
            self.assertIn(want, " ".join(self.step_faults("---\nassumes: [x]\n---\n\nB.\n\n## Pointers\n\n- src/greet.sh\n\n## Rubric\n\n- x\n")))

    def test_a_pointer_may_name_a_directory(self):
        self.assertEqual(self.step_faults(self.STEP.replace("- src/greet.sh", "- src")), [])

    def test_a_pointer_may_be_written_as_prose(self):
        """The two spellings every run of the detour eval produced, and
        the first write was refused every time: the path formatted as
        code, and a note on why it matters after a dash or a colon."""
        for dressed in ("- `src/greet.sh`",
                        "- `src/greet.sh` — the greeting, and where it reads its argument",
                        "- **src/greet.sh**",
                        "- **`src/greet.sh`**",
                        "- *`src/greet.sh`* — bold and code, which this repository's own prose mixes",
                        "- src/greet.sh: the greeting itself",
                        "- `src/greet.sh`.",
                        "- src/greet.sh - the one to follow"):
            with self.subTest(dressed):
                self.assertEqual(self.step_faults(self.STEP.replace("- src/greet.sh", dressed)), [])

    def test_a_pointer_that_parses_to_nothing_is_quoted_as_written(self):
        """The dressing comes off before the path is checked, so a
        pointer that is all dressing parses to ''. The fault is the
        whole point of the change, so it quotes the line instead."""
        self.assertIn("pointer '..' is not a plain repository-relative path",
                      self.step_faults(self.STEP.replace("- src/greet.sh", "- ..")))
        self.assertIn("pointer '`  `' is not a plain repository-relative path",
                      self.step_faults(self.STEP.replace("- src/greet.sh", "- `  `")))

    def test_a_dressed_pointer_that_is_not_there_still_faults_on_the_path(self):
        """The accommodation is to the dressing, not to the check: a
        path that is absent is still absent, and the fault quotes the
        path rather than the line, so the writer sees what was read."""
        self.assertIn("pointer 'src/nowhere.sh' is not in the tree",
                      self.step_faults(self.STEP.replace("- src/greet.sh", "- `src/nowhere.sh` — a note")))
        self.assertIn("pointer 'src/greet.sh' is listed twice",
                      self.step_faults(self.STEP.replace("- src/greet.sh", "- src/greet.sh\n- `src/greet.sh`: again")))


class TaskValidationTest(WorldTest):
    def faults(self, **fields):
        p = self.w.task(**fields)
        return whats(validate.validate_task(p, self.w.top, self.w.top / ".rolling", self.w.learner.held))

    def full(self, **extra):
        f = dict(lesson="greet-politely", mode="write", branch="rolling/x", base=self.w.fix, return_to=f"main {self.w.pre}",
                 started="2026-09-15", tutor_session="s1", fix=self.w.fix, scope=["src/greet.sh", "tests"],
                 scaffold=["tests/greet.test.sh"], setup=["seed"], verify=["check"], held=["tests/greet.test.sh"],
                 held_verify=["test tests/greet.test.sh"], expect_fail_on_base=["held-verify test tests/greet.test.sh"])
        f.update(extra)
        return f

    def test_clean(self):
        (self.w.learner.held / "tests").mkdir(parents=True)
        (self.w.learner.held / "tests/greet.test.sh").write_text("x")
        self.assertEqual(self.faults(**self.full()), [])

    def test_missing_task(self):
        faults = validate.validate_task(self.w.learner.task_file, self.w.top, self.w.top / ".rolling", self.w.learner.held)
        self.assertIn("no open task", faults[0].what)

    def test_each_fault(self):
        (self.w.learner.held / "tests").mkdir(parents=True)
        (self.w.learner.held / "tests/greet.test.sh").write_text("x")
        self.assertIn("scaffold 'docs/x.md' is not inside any scope", self.faults(**self.full(scaffold=["docs/x.md"])))
        self.assertNotIn("scaffold 'packages/web/src/x.ts' is not inside any scope", self.faults(**self.full(scope=["packages/*/src"], scaffold=["packages/web/src/x.ts"])))
        self.assertIn("scaffold 'packages/a/b/src/x.ts' is not inside any scope", self.faults(**self.full(scope=["packages/*/src"], scaffold=["packages/a/b/src/x.ts"])), "a single * stays within one segment")
        self.assertNotIn("scaffold 'packages/a/b/src/x.ts' is not inside any scope", self.faults(**self.full(scope=["packages/**/src"], scaffold=["packages/a/b/src/x.ts"])))
        self.assertTrue(any("carries a shell metacharacter" in f for f in self.faults(**self.full(verify=["check  two"]))), "a double space is not a word")
        self.assertIn("expect-fail-on-base 'verify test x' does not repeat a verify: line verbatim", self.faults(**self.full(expect_fail_on_base=["verify test x"])))
        self.assertIn("held 'tests/other.sh' has no file under held/", self.faults(**self.full(held=["tests/other.sh"], held_verify=[], expect_fail_on_base=[])))
        self.assertIn("held 'tests/greet.test.sh' is listed twice", self.faults(**self.full(held=["tests/greet.test.sh", "tests/greet.test.sh"])))
        self.assertIn("held './tests/greet.test.sh' is not a plain repository-relative path", self.faults(**self.full(held=["./tests/greet.test.sh"])))
        self.assertIn("a direct task needs a ## Situation heading", self.faults(**self.full(mode="direct")))
        self.assertIn("task 'nothing' is not a task of lesson 'greet-politely'", " ".join(self.faults(**self.full(task="nothing"))))
        faults = self.faults(**self.full(branch="", tutor_session="", verify=["check $(rm -rf /)"], bogus="1"))
        self.assertIn("branch is missing", faults)
        self.assertIn("tutor-session is missing", faults)
        self.assertIn("verify line 'check $(rm -rf /)' carries a shell metacharacter, quote, or glob", faults)
        self.assertIn("unknown field 'bogus'", faults)
        faults = self.faults(**self.full(base="notasha", started="15/09/2026", return_to="a b c"))
        self.assertIn("base 'notasha' is not 7 to 40 hex characters", faults)
        self.assertIn("started '15/09/2026' is not YYYY-MM-DD", faults)
        self.assertIn("return-to has 3 words; expected '<ref> <sha>' or a sha", faults)

    def test_held_paths_need_a_line_that_runs_them(self):
        """The mirror of the fault above it: with no held-verify: line the
        held test is never applied and never checked, so holding it back
        from the learner is all it does (#14)."""
        (self.w.learner.held / "tests").mkdir(parents=True)
        (self.w.learner.held / "tests/greet.test.sh").write_text("x")
        faults = self.faults(**self.full(held_verify=[], expect_fail_on_base=["verify check"]))
        self.assertIn("held: paths need a held-verify: line to run them; a held test nothing runs is never applied and never checked", faults)
        self.assertEqual(self.faults(**self.full()), [], "both together are clean")

    def test_reference_setup_names_one_operation_that_is_not_destructive(self):
        """The proof runs it with nobody to ask, and the hook that asks
        watches the tutor's commands rather than the verifier's (#32)."""
        def check(value):
            return self.faults(**self.full(reference_setup=value, held=[], held_verify=[],
                                           expect_fail_on_base=["verify check"]))

        self.assertEqual(check("seed"), [], "an operation of the map's is fine")
        self.assertIn("reference-setup names 'nope', which is not an operation in the map", check("nope"))
        self.assertIn("reference-setup names 'reset', which the map lists as destructive; the proof runs unattended, and a destructive operation waits for the learner's yes",
                      check("reset"))
        self.assertIn("reference-setup has 2 lines; it names one operation", check(["seed", "seed"]))

    def test_command_rules_apply_to_the_task(self):
        self.w.add_command("evil", "echo ran;")
        faults = self.faults(**self.full(verify=["evil x"], held=[], held_verify=[], expect_fail_on_base=[]))
        self.assertIn("verify names 'evil', whose command in the map ends in an operator or contains '#'", faults)


if __name__ == "__main__":
    unittest.main()
