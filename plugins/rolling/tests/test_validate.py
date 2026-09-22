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

    def test_command_rules_apply_to_the_task(self):
        self.w.add_command("evil", "echo ran;")
        faults = self.faults(**self.full(verify=["evil x"], held=[], held_verify=[], expect_fail_on_base=[]))
        self.assertIn("verify names 'evil', whose command in the map ends in an operator or contains '#'", faults)


if __name__ == "__main__":
    unittest.main()
