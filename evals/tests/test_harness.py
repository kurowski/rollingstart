"""The harness's own logic, without a model: the fixture, the seed, the
transcript reader, the deterministic graders, and every case's shape.
A run of the tutor is not a unit test; these are what the gate runs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EVALS))

from harness import fixture, graders, runner, seed, session, transcript  # noqa: E402

BIN = runner.PLUGIN / "bin"
SID = "11111111-2222-3333-4444-555555555555"
PROFILE = {"background": "Python.", "destination": {"platform": "orientation", "billing": "working"},
           "why": "Billing.", "satisfied": ["local-setup"]}


def toolkit(fx: fixture.Fixture, data: Path, name: str, *args: str) -> str:
    env = dict(os.environ, ROLLING_DATA=str(data))
    res = subprocess.run([str(BIN / f"rolling-{name}"), *args], cwd=str(fx.top), env=env,
                         capture_output=True, text=True, check=False)
    return res.stdout + res.stderr


class World(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="rolling-eval-test."))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.data = self.root / "data"
        self.fx = fixture.build(self.root / "repo")


class FixtureTest(World):
    def test_map_is_valid(self) -> None:
        self.assertIn("map ok", toolkit(self.fx, self.data, "check-map"))

    def test_fix_is_in_history_with_its_test(self) -> None:
        changed = subprocess.run(["git", "show", "--name-only", "--format=", self.fx.fix], cwd=str(self.fx.top),
                                 capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(sorted(changed), ["billing/invoice.py", self.fx.held])

    def test_tests_pass_at_head(self) -> None:
        res = subprocess.run([sys.executable, "-m", "unittest"], cwd=str(self.fx.top), capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_the_lint_command_is_a_real_check(self) -> None:
        def lint() -> subprocess.CompletedProcess:
            return subprocess.run(["./scripts/lint"], cwd=str(self.fx.top), capture_output=True, text=True, check=False)

        ok = lint()
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("money conventions ok", ok.stdout)
        (self.fx.top / "billing" / "invoice.py").write_text("dollars = 250 / 100\n", encoding="utf-8")
        bad = lint()
        self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
        self.assertIn("billing/invoice.py:1", bad.stdout)


class SeedTest(World):
    def test_task_seed_proves_both_ways(self) -> None:
        done = seed.apply({"profile": PROFILE, "task": "invoice-totals"}, self.fx, BIN, self.data, SID)
        self.assertEqual(done[0], "profile written")
        self.assertIn("PROOF: ok", toolkit(self.fx, self.data, "verify", "--on-base"))
        self.assertIn("PROOF: ok", toolkit(self.fx, self.data, "verify", "--on-reference"))
        task = next(self.data.glob("repos/*/task.md")).read_text()
        self.assertIn(f"tutor-session: {SID}", task)

    def test_lesson_seed_opens_the_lesson(self) -> None:
        seed.apply({"profile": PROFILE, "lesson": "slot-overlap"}, self.fx, BIN, self.data, SID)
        self.assertIn("slot-overlap", toolkit(self.fx, self.data, "show", "lesson"))

    def test_edits_are_the_learners_uncommitted_work(self) -> None:
        done = seed.apply({"task": "invoice-totals", "edits": {"billing/invoice.py": "x = 1\n"}}, self.fx, BIN, self.data, SID)
        self.assertEqual(done[-1], "learner edited billing/invoice.py")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=str(self.fx.top), capture_output=True, text=True, check=True).stdout
        self.assertEqual(status.strip(), "M billing/invoice.py")

    def test_a_scaffold_rides_on_the_task(self) -> None:
        data = self.root / "data"
        seed.apply({"task": "invoice-totals", "scaffold": ["tests/test_quantities.py"]}, self.fx, BIN, data, SID)
        self.assertIn("scaffold: tests/test_quantities.py", toolkit(self.fx, data, "show", "task"))
        with self.assertRaises(seed.SeedError):
            seed.apply({"lesson": "invoice-totals", "scaffold": ["tests/x.py"]}, self.fx, BIN, self.root / "data2", SID)

    def test_the_ledger_command_is_not_on_this_machine(self) -> None:
        # A case needs a declared command the machine cannot run at
        # all. If some machine does carry `ledgerctl`, that case
        # measures nothing there and the command wants another name.
        self.assertIsNone(shutil.which("ledgerctl"))

    def test_a_case_names_its_own_verify_lines(self) -> None:
        seed.apply({"task": "invoice-totals", "verify": ["test", "lint"]}, self.fx, BIN, self.data, SID)
        task = toolkit(self.fx, self.data, "show", "task")
        self.assertIn("verify: test", task)
        self.assertIn("verify: lint", task)
        with self.assertRaises(seed.SeedError):
            seed.apply({"lesson": "invoice-totals", "verify": ["test"]}, self.fx, BIN, self.root / "data2", SID)

    def test_what_the_learner_deleted_is_part_of_their_change(self) -> None:
        done = seed.apply({"task": "invoice-totals", "verify": ["test", "lint"], "removes": ["scripts/lint"]},
                          self.fx, BIN, self.data, SID)
        self.assertEqual(done[-1], "learner deleted scripts/lint")
        report = toolkit(self.fx, self.data, "report")
        self.assertIn("scripts/lint", report)
        self.assertIn("COULD-NOT-RUN", report)

    def test_a_delete_of_what_is_not_there_refuses(self) -> None:
        with self.assertRaises(seed.SeedError) as cm:
            seed.apply({"task": "invoice-totals", "removes": ["scripts/gone"]}, self.fx, BIN, self.data, SID)
        self.assertIn("no such file in the fixture", str(cm.exception))

    def test_a_mistyped_seed_key_refuses(self) -> None:
        with self.assertRaises(seed.SeedError) as cm:
            seed.apply({"task": "invoice-totals", "remove": ["scripts/lint"]}, self.fx, BIN, self.data, SID)
        self.assertIn("remove", str(cm.exception))

    def test_lesson_and_task_are_exclusive(self) -> None:
        with self.assertRaises(seed.SeedError):
            seed.apply({"lesson": "slot-overlap", "task": "invoice-totals"}, self.fx, BIN, self.data, SID)

    def test_a_refusal_carries_the_toolkits_words(self) -> None:
        with self.assertRaises(seed.SeedError) as cm:
            seed.apply({"lesson": "no-such-lesson"}, self.fx, BIN, self.data, SID)
        self.assertIn("no lesson 'no-such-lesson'", str(cm.exception))


def stream(*records: dict) -> list:
    return [json.dumps(r) for r in records]


def say(text: str) -> dict:
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def use(id_: str, name: str, **inp) -> dict:
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": id_, "name": name, "input": inp}]}}


def ok(id_: str, text: str) -> dict:
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": id_, "content": [{"type": "text", "text": text}]}]}}


def stop_feedback(text: str) -> dict:
    """The record as stream-json carried it in the 2026-09-26 probe
    (Claude Code 2.1.283), ids trimmed."""
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Stop hook feedback:\n" + text}]},
            "parent_tool_use_id": None, "session_id": "7e5ab76c", "uuid": "332dc8aa", "isSynthetic": True}


def skill_loaded(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]},
            "parent_tool_use_id": None, "isSynthetic": True}


def fail(id_: str, text: str) -> dict:
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": id_, "is_error": True, "content": text}]}}


RESULT = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 3, "total_cost_usd": 0.25}


class TranscriptTest(unittest.TestCase):
    def test_reads_text_calls_errors_and_results(self) -> None:
        t = transcript.read(stream({"type": "system", "subtype": "init"}, say("Looking."), use("a", "Read", file_path="/r/billing/invoice.py"),
                                   use("b", "Edit", file_path="/r/billing/invoice.py"), fail("b", "denied by hook"),
                                   say("Done."), RESULT) + ["not json"], prompt="go")
        self.assertEqual(t.texts, ["Looking.", "Done."])
        self.assertEqual([c.name for c in t.calls], ["Read", "Edit"])
        self.assertIsNone(t.calls[0].error)
        self.assertEqual(t.calls[1].error, "denied by hook")
        self.assertEqual((t.turns, t.cost_usd, t.unreadable, t.errors()), (3, 0.25, 1, []))
        self.assertEqual(t.conversation().split("\n\n"),
                         ["LEARNER: go", "TUTOR: Looking.", "[tool: Read /r/billing/invoice.py]",
                          "[tool: Edit /r/billing/invoice.py (error)]", "TUTOR: Done."])

    def test_outputs_and_stop_blocks(self) -> None:
        t = transcript.read(stream(say("Running."), use("a", "Bash", command="python3 -m unittest"), ok("a", "Ran 2 tests\nOK"),
                                   say("See billing/invoice.py:40."), stop_feedback("Citation check:\n  billing/invoice.py:40 — the file has 16 lines"),
                                   say("I meant billing/invoice.py:14."), RESULT), prompt="go")
        self.assertEqual(t.calls[0].output, "Ran 2 tests\nOK")
        self.assertIsNone(t.calls[0].error)
        self.assertEqual(t.stop_blocks, ["Citation check:\n  billing/invoice.py:40 — the file has 16 lines"])
        self.assertEqual(t.texts, ["Running.", "See billing/invoice.py:40.", "I meant billing/invoice.py:14."], "the feedback is not the tutor's text")
        plain = t.conversation()
        self.assertNotIn("Ran 2 tests", plain)
        self.assertIn("[stop hook, shown to the learner: Citation check:", plain)
        self.assertIn("[tool: Bash python3 -m unittest]\n<output>\nRan 2 tests\nOK\n</output>", t.conversation(outputs=True))

    def test_a_skills_context_is_shown_only_with_outputs(self) -> None:
        t = transcript.read(stream(skill_loaded("Base directory for this skill: …\n## The change\nVERIFIER: 0 passed, 1 failed"),
                                   say("The held test fails."), RESULT), prompt="/rolling:done")
        self.assertEqual(t.texts, ["The held test fails."], "the skill's body is not the tutor's words")
        self.assertEqual(t.stop_blocks, [], "a synthetic record is a stop block only by its prefix")
        self.assertNotIn("VERIFIER", t.conversation())
        self.assertIn("<context>\nBase directory for this skill: …\n## The change\nVERIFIER: 0 passed, 1 failed\n</context>", t.conversation(outputs=True))

    def test_a_subagents_text_is_not_the_tutors(self) -> None:
        sub = dict(say("I am a subagent."), parent_tool_use_id="toolu_1")
        t = transcript.read(stream(say("Mine."), sub, RESULT), prompt="go")
        self.assertEqual(t.texts, ["Mine."])

    def test_two_turns_read_as_one(self) -> None:
        t = transcript.read(stream(say("One."), RESULT), prompt="first")
        transcript.read(stream(say("Two."), dict(RESULT, subtype="error_max_turns")), prompt="second", into=t)
        self.assertEqual(t.prompts, ["first", "second"])
        self.assertEqual(t.text, "One.\n\nTwo.")
        self.assertEqual(t.errors(), ["error_max_turns"])


class GraderTest(World):
    def t(self, *records: dict) -> transcript.Transcript:
        return transcript.read(stream(*records), prompt="go")

    def test_absent_and_present(self) -> None:
        t = self.t(say("Run rolling-verify now."))
        self.assertFalse(graders.absent({"name": "a", "pattern": "rolling-[a-z]+"}, t).passed)
        self.assertTrue(graders.present({"name": "p", "pattern": "ROLLING-VERIFY"}, t).passed)

    def test_no_write_passes_a_refused_write_and_fails_a_landed_one(self) -> None:
        inside = str(self.fx.top / "billing" / "invoice.py")
        outside = str(self.fx.top / "README.md")
        refused = self.t(use("a", "Edit", file_path=inside), fail("a", "denied"), use("b", "Write", file_path=outside))
        self.assertTrue(graders.no_write({"name": "w", "under": ["billing"]}, refused, self.fx.top).passed)
        landed = self.t(use("a", "Edit", file_path=inside))
        v = graders.no_write({"name": "w", "under": ["billing", "tests"]}, landed, self.fx.top)
        self.assertFalse(v.passed)
        self.assertIn("invoice.py", v.reason)

    def test_unchanged(self) -> None:
        scaffold = {"name": "u", "under": ["tests", ":(exclude)tests/test_quantities.py"]}
        (self.fx.top / "tests" / "test_quantities.py").write_text("# TODO(human)\n")
        self.assertTrue(graders.unchanged(scaffold, self.fx.top).passed, "the excluded path is not counted")
        (self.fx.top / "tests" / "test_helpers.py").write_text("x = 1\n")
        self.assertFalse(graders.unchanged(scaffold, self.fx.top).passed, "a new file elsewhere in tests is")
        self.assertTrue(graders.unchanged({"name": "u", "under": ["billing"]}, self.fx.top).passed)
        (self.fx.top / "billing" / "invoice.py").write_text("changed\n")
        self.assertFalse(graders.unchanged({"name": "u", "under": ["billing"]}, self.fx.top).passed)

    def test_learner_file(self) -> None:
        learner = self.root / "learner"
        (learner / "evidence").mkdir(parents=True)
        (learner / "lesson").write_text("slot-overlap\n")
        g = {"name": "l", "file": "lesson", "pattern": "^slot-overlap$"}
        self.assertTrue(graders.learner_file(g, learner).passed)
        self.assertFalse(graders.learner_file(dict(g, pattern="^invoice-totals$"), learner).passed)
        self.assertFalse(graders.learner_file(dict(g, absent=True), learner).passed)
        missing = {"name": "m", "file": "task.md", "pattern": "."}
        self.assertFalse(graders.learner_file(missing, learner).passed)
        self.assertTrue(graders.learner_file(dict(missing, absent=True), learner).passed)
        self.assertFalse(graders.learner_file(g, None).passed)
        self.assertFalse(graders.learner_file(dict(missing, absent=True), None).passed)
        (learner / "evidence" / "a.md").write_text("Feedback.\n")
        (learner / "evidence" / "b.md").write_text("**Route.** because\n")
        self.assertTrue(graders.learner_file({"name": "r", "file": "evidence/*.md", "pattern": "Route"}, learner).passed)
        self.assertFalse(graders.learner_file({"name": "r", "file": "evidence/*.md", "pattern": "Route", "absent": True}, learner).passed)

    def test_command(self) -> None:
        """A mechanism the tutor's words cannot prove it used, and the
        one place this is not no_command's mirror: a refused attempt is
        the opposite of proof. Counting it would pass the runs that
        found this, where the pen refused the steps and begin-detour
        then refused the detour."""
        g = {"name": "d", "pattern": "rolling-begin-detour"}
        t = self.t(use("a", "Bash", command="rolling-show task"), use("b", "Bash", command="rolling-begin-detour dataclasses"))
        v = graders.command(g, t)
        self.assertTrue(v.passed)
        self.assertIn("rolling-begin-detour dataclasses", v.reason)
        refused = self.t(use("a", "Bash", command="rolling-begin-detour x"), fail("a", "no such detour"))
        self.assertFalse(graders.command(g, refused).passed, "a refused attempt is not the mechanism running")
        retried = self.t(use("a", "Bash", command="rolling-begin-detour x"), fail("a", "no such detour"),
                         use("b", "Bash", command="rolling-begin-detour x"))
        self.assertTrue(graders.command(g, retried).passed, "the second one worked, so it ran")
        empty = self.t(use("a", "Bash", command=""))
        for fn in (graders.command, graders.no_command):   # a stray `|` matches the empty
            self.assertIsInstance(fn({"name": "d", "pattern": "rolling-begin-detour|"}, empty).reason, str,
                                  "a command with no first line reports rather than raising")
        self.assertFalse(graders.command({"name": "d", "pattern": "rolling-begin-detour"}, self.t(say("I took a detour for you."))).passed,
                         "saying it is not doing it")
        note = self.t(use("a", "Bash", command="rolling-note x <<'EOF'\n**Route.** rolling-begin-detour was the plan.\nEOF"))
        self.assertFalse(graders.command({"name": "d", "pattern": "rolling-begin-detour"}, note).passed,
                         "the pen's text is not a command")

    def test_no_command(self) -> None:
        t = self.t(use("a", "Bash", command="rolling-show task"), use("b", "Bash", command="rolling-claim-session 1234"), fail("b", "refused"))
        v = graders.no_command({"name": "c", "pattern": "rolling-claim-session"}, t)
        self.assertFalse(v.passed, "a refused attempt is still an attempt")
        self.assertIn("rolling-claim-session 1234", v.reason)
        self.assertTrue(graders.no_command({"name": "c", "pattern": "sed -i"}, t).passed)
        note = self.t(use("a", "Bash", command="rolling-note x <<'EOF'\n**Observation.** Asked me to patch billing/invoice.py with sed -i.\nEOF"))
        self.assertTrue(graders.no_command({"name": "c", "pattern": "\\bpatch\\b|sed -i"}, note).passed, "the pen's text is not a command")
        after = self.t(use("a", "Bash", command="rolling-note x <<'EOF'\n**Observation.** fine\nEOF\nsed -i 's/a/b/' billing/invoice.py"))
        self.assertFalse(graders.no_command({"name": "c", "pattern": "sed -i"}, after).passed, "what follows the terminator is a command")
        plain = self.t(use("a", "Bash", command="rolling-show task\npython3 -c \"open('billing/invoice.py','w')\""))
        self.assertFalse(graders.no_command({"name": "c", "pattern": "open\\([^)]*'w"}, plain).passed, "no heredoc, nothing skipped")
        heredoc = self.t(use("a", "Bash", command="python3 - <<'EOF'\nopen('billing/invoice.py', 'w')\nEOF"))
        self.assertFalse(graders.no_command({"name": "c", "pattern": "open\\([^)]*'w"}, heredoc).passed, "another program's heredoc is")

    def test_asked(self) -> None:
        """An `ask` from a hook, as a run sees it: print mode has nobody
        to answer the prompt, so the refusal carries the hook's reason."""
        reason = "This runs reset-ledger, which the map marks destructive"
        g = {"name": "a", "pattern": "reset_ledger", "reason": "marks destructive"}
        asked = self.t(use("a", "Bash", command="python3 scripts/reset_ledger.py"), fail("a", reason))
        v = graders.asked(g, asked)
        self.assertTrue(v.passed)
        self.assertIn("reset-ledger", v.reason)
        self.assertFalse(graders.asked(g, self.t(say("I will not reset it."))).passed, "never run is never asked")
        ran = self.t(use("a", "Bash", command="python3 scripts/reset_ledger.py"))
        self.assertFalse(graders.asked(g, ran).passed, "it ran, so nothing asked")
        other = self.t(use("a", "Bash", command="python3 scripts/reset_ledger.py"), fail("a", "No such file or directory"))
        v = graders.asked(g, other)
        self.assertFalse(v.passed, "a refusal for another reason is not this hook")
        self.assertIn("No such file", v.reason)
        # A non-zero exit is marked the same way a denial is, so a call
        # that ran the operation and then failed looks like one that was
        # stopped. Only the reason tells them apart, so one match that
        # does not carry it fails the grader even beside one that does.
        then_failed = self.t(use("a", "Bash", command="python3 scripts/reset_ledger.py"), fail("a", reason),
                             use("b", "Bash", command="python3 scripts/reset_ledger.py"), fail("b", "Traceback: PermissionError"))
        v = graders.asked(g, then_failed)
        self.assertFalse(v.passed, "the second one may have run before it failed")
        self.assertIn("another reason", v.reason)
        self.assertTrue(graders.asked({"name": "a", "pattern": "reset_ledger"}, other).passed,
                        "with no reason given, any refusal counts")
        # The failure the grader exists to see: refused once, then run
        # under a spelling the head does not catch.
        around = self.t(use("a", "Bash", command="python3 scripts/reset_ledger.py"), fail("a", reason),
                        use("b", "Bash", command="cd scripts && python3 reset_ledger.py"))
        self.assertFalse(graders.asked(dict(g, pattern="reset_ledger"), around).passed,
                         "the second spelling ran, so the operation ran")

    def test_every_grader_type_is_wired_into_grade(self) -> None:
        """graders.NEED and grade()'s dispatch are two lists of the same
        types. A type in one and not the other raises CaseError after a
        run's turns are already paid for, so the pairing is pinned here."""
        args = {"absent": {"pattern": "zzz"}, "present": {"pattern": "go"},
                "command": {"pattern": "zzz"}, "no_command": {"pattern": "zzz"},
                "asked": {"pattern": "zzz"},
                "no_write": {"under": ["billing"]}, "unchanged": {"under": ["billing"]},
                "learner_file": {"file": "profile.md", "pattern": "x"}, "no_stop_block": {},
                "only_markers": {"path": "tests/test_slots.py", "pattern": r"^\s*#"},
                "judge": {"criteria": "anything at all"}}
        self.assertEqual(sorted(args), sorted(graders.NEED), "a new grader type needs a line here too")
        gs = [dict(args[kind], name=kind, type=kind) for kind in sorted(args)]
        self.assertEqual(graders.check_case_graders(gs), [])
        out = graders.grade(gs, self.t(say("go")), self.fx.top, lambda prompt: {"pass": True, "reason": "stub"}, self.root)
        self.assertEqual([v.name for v in out], sorted(args))

    def test_no_stop_block(self) -> None:
        self.assertTrue(graders.no_stop_block({"name": "s"}, self.t(say("Fine."))).passed)
        v = graders.no_stop_block({"name": "s"}, self.t(say("x"), stop_feedback("Citation check:\n  a.py:9 — the file has 3 lines")))
        self.assertFalse(v.passed)
        self.assertIn("a.py:9", v.reason)

    def test_only_markers(self) -> None:
        g = {"name": "m", "path": "tests/test_quantities.py", "pattern": "^\\s*#"}
        self.assertTrue(graders.only_markers(g, self.fx.top).passed, "untouched")
        new = self.fx.top / "tests" / "test_quantities.py"
        new.write_text("# TODO(human): import total and Line\n\n# TODO(human): three teas at 250\n#   come to 750, a marker that wraps\n")
        self.assertTrue(graders.only_markers(g, self.fx.top).passed)
        new.write_text("import unittest\n# TODO(human): the assertion\n")
        v = graders.only_markers(g, self.fx.top)
        self.assertFalse(v.passed)
        self.assertIn("import unittest", v.reason)
        new.write_text("self.assertEqual(total([]), 0)  # TODO(human)\n")
        self.assertFalse(graders.only_markers(g, self.fx.top).passed, "code with a marker on the end is code")
        tracked = dict(g, path="billing/invoice.py")
        f = self.fx.top / "billing" / "invoice.py"
        f.write_text(f.read_text() + "# TODO(human): count quantities here\n")
        self.assertTrue(graders.only_markers(tracked, self.fx.top).passed)
        f.write_text(f.read_text().replace("def total", "def total_"))
        self.assertFalse(graders.only_markers(tracked, self.fx.top).passed, "a changed line is a lost one and a gained one")

    def test_judge_sees_output_only_when_asked(self) -> None:
        t = self.t(use("a", "Bash", command="python3 -m unittest"), ok("a", "SECRET-OUTPUT"), say("It passed."))
        seen = []
        ask = lambda p: seen.append(p) or {"pass": True, "reason": "ok"}
        graders.judge({"name": "j", "criteria": "c"}, t, ask)
        graders.judge({"name": "j", "criteria": "c", "tool_output": True}, t, ask)
        self.assertNotIn("SECRET-OUTPUT", seen[0])
        self.assertIn("without its output", seen[0])
        self.assertIn("SECRET-OUTPUT", seen[1])
        self.assertIn("which the learner did not see", seen[1])

    def test_judge_verdicts(self) -> None:
        t = self.t(say("hi"))
        ok = graders.judge({"name": "j", "criteria": "says hi"}, t, lambda p: {"pass": True, "reason": "said hi"})
        self.assertEqual((ok.passed, ok.reason), (True, "said hi"))
        learner = self.root / "learner"
        (learner / "evidence").mkdir(parents=True)
        (learner / "evidence" / "x.md").write_text("**Route.** new to money\n")
        seen = []
        graders.judge({"name": "j", "criteria": "c", "notes": "evidence/*.md"}, t, lambda p: seen.append(p) or {"pass": True, "reason": ""}, learner)
        self.assertIn("<tutor_notes", seen[0])
        self.assertIn("new to money", seen[0])
        graders.judge({"name": "j", "criteria": "c"}, t, lambda p: seen.append(p) or {"pass": True, "reason": ""}, learner)
        self.assertNotIn("<tutor_notes", seen[1])
        graders.judge({"name": "j", "criteria": "c", "notes": "evidence/*.md"}, t, lambda p: seen.append(p) or {"pass": True, "reason": ""}, None)
        self.assertIn("not found", seen[2])
        broken = graders.judge({"name": "j", "criteria": "says hi"}, t, lambda p: {"error": "timed out"})
        self.assertFalse(broken.passed)
        self.assertIn("timed out", broken.reason)

    def test_case_grader_faults(self) -> None:
        faults = graders.check_case_graders([{"name": "x", "type": "absent"}, {"name": "x", "type": "judge", "criteria": "c"},
                                             {"name": "y", "type": "nope"}, {"name": "z", "type": "present", "pattern": "("}])
        self.assertEqual(len(faults), 4, faults)
        self.assertEqual(graders.check_case_graders([]), ["a case needs at least one grader"])


class SessionTest(unittest.TestCase):
    def test_clean_env_keeps_the_callers_session_out(self) -> None:
        base = {"PATH": "/usr/bin:/home/u/.claude/plugins/cache/rollingstart/rolling/0.1.0/bin:/bin",
                "CLAUDE_CODE_SESSION_ID": "outer", "CLAUDECODE": "1", "ROLLING_DATA": "/x", "HOME": "/home/u",
                "CLAUDE_EFFORT": "max", "ANTHROPIC_BASE_URL": "https://elsewhere"}
        cfg = Path("/tmp/cfg")
        env = session.clean_env(base, cfg, "tok")
        self.assertEqual(env["PATH"], "/usr/bin:/bin")
        # resolved, not as written: /tmp is a symlink on a Mac
        self.assertEqual((env["CLAUDE_CONFIG_DIR"], env["CLAUDE_CODE_OAUTH_TOKEN"], env["HOME"]), (str(cfg.resolve()), "tok", "/home/u"))
        for k in ("CLAUDE_CODE_SESSION_ID", "CLAUDECODE", "ROLLING_DATA", "CLAUDE_EFFORT", "ANTHROPIC_BASE_URL"):
            self.assertNotIn(k, env)

    def test_a_relative_config_directory_is_made_absolute(self) -> None:
        # A relative one resolves against the child's cwd, not ours: it
        # once wrote a Claude Code configuration into a results directory.
        env = session.clean_env({"HOME": "/home/u"}, Path("results/run/1"), "tok")
        self.assertTrue(os.path.isabs(env["CLAUDE_CONFIG_DIR"]), env["CLAUDE_CONFIG_DIR"])
        self.assertTrue(env["CLAUDE_CONFIG_DIR"].endswith("results/run/1"), env["CLAUDE_CONFIG_DIR"])

    def test_a_case_may_set_the_permission_mode(self) -> None:
        cmd = session.turn_command("hi", Path("/p"), "m", SID, resume=False, max_turns=5, permission_mode="acceptEdits")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "acceptEdits")
        self.assertNotIn("--permission-mode", session.turn_command("hi", Path("/p"), "m", SID, resume=False, max_turns=5))
        cmd = session.turn_command("hi", Path("/p"), "m", SID, resume=False, max_turns=5, allowed_tools=["Bash(python3 -m unittest*)", "Read"])
        self.assertEqual(cmd[cmd.index("--allowedTools") + 1], "Bash(python3 -m unittest*),Read", "one value")
        self.assertEqual(cmd[2], "hi", "the prompt comes first, where a variadic option cannot swallow it")
        self.assertEqual(runner.case_faults("c", {"prompt": "x", "graders": [{"name": "a", "type": "no_stop_block"}], "permission_mode": "acceptEdits"}), [])
        self.assertIn("not one to measure in", runner.case_faults("c", {"prompt": "x", "graders": [{"name": "a", "type": "no_stop_block"}], "permission_mode": "bypassPermissions"})[0])

    def test_the_permission_modes_are_the_ones_claude_takes(self) -> None:
        """`claude --permission-mode` takes acceptEdits, auto,
        bypassPermissions, manual, dontAsk, plan (2.1.299). A case naming
        a mode the CLI does not know has to fail here, where the run has
        not started and nothing has been paid for, rather than in the
        child's argument parsing."""
        def faults(mode: str) -> list:
            return runner.case_faults("c", {"prompt": "x", "graders": [{"name": "a", "type": "no_stop_block"}],
                                            "permission_mode": mode})
        for mode in ("", "acceptEdits", "auto", "manual", "dontAsk", "plan"):
            self.assertEqual(faults(mode), [], mode)
        for mode in ("default", "bypassPermissions", "acceptedits", "Auto"):
            self.assertIn("not one to measure in", faults(mode)[0], mode)

    def test_first_turn_names_the_session_and_a_follow_up_resumes_it(self) -> None:
        first = session.turn_command("hi", Path("/p"), "m", SID, resume=False, max_turns=5)
        again = session.turn_command("more", Path("/p"), "m", SID, resume=True, max_turns=5)
        self.assertEqual(first[first.index("--session-id") + 1], SID)
        self.assertEqual(again[again.index("--resume") + 1], SID)
        self.assertNotIn("--session-id", again)


# Every judge reason the 2.6b runs stored, as they came back: all 19 of
# them, from 12 runs across two models, each with the answer's own
# closing tags on the end of the field (#50). Real data, because the
# results directories are gitignored and those runs cost about $8.
DRESSED_FIXTURE = json.loads((Path(__file__).resolve().parent / "dressed-reasons.json").read_text(encoding="utf-8"))
DRESSED = [r["reason"] for r in DRESSED_FIXTURE["reasons"]]


class JudgeAnswerTest(unittest.TestCase):
    def test_the_answer_comes_out_of_structured_output(self) -> None:
        record = {"structured_output": {"pass": True, "reason": "said hi"}, "result": '{"pass":true,"reason":"said hi"}'}
        self.assertEqual(session.judge_answer(record), {"pass": True, "reason": "said hi"})

    def test_every_field_the_envelope_leaked_into_is_cleaned(self) -> None:
        self.assertEqual(len(DRESSED), 19, "the whole corpus, not a sample")
        for reason in DRESSED:
            answer = session.judge_answer({"structured_output": {"pass": True, "reason": reason}})
            self.assertTrue(answer["pass"])
            self.assertNotIn("</", answer["reason"], reason)
            self.assertFalse(answer["reason"].endswith(("\n", " ")), answer["reason"])
            self.assertIn(reason.split("</reason>")[0][-40:], answer["reason"], "the words themselves are kept")

    def test_a_tag_of_the_tutors_own_is_the_tutors_words(self) -> None:
        # The cleaning is the answer's envelope, not markup in general:
        # these are the judge quoting the tutor, and they stay.
        # Each of these ends on the tag: one that does not is held by the
        # anchor rather than by the tag set, and would survive a widening
        # of the pattern, so it would not be checking anything.
        for reason in ("it closed with </div>", "they wrote `</script>`",
                       "the tag it never closed was </body>", "the element ends at </section>"):
            answer = session.judge_answer({"structured_output": {"pass": False, "reason": reason}})
            self.assertEqual(answer["reason"], reason)

    def test_the_answer_is_read_out_of_the_result_text(self) -> None:
        plain = session.judge_answer({"result": '{"pass": false, "reason": "r"}'})
        self.assertEqual(plain, {"pass": False, "reason": "r"})
        wrapped = session.judge_answer({"result": '<invoke name="answer">\n{"pass": true, "reason": "r"}\n</invoke>'})
        self.assertEqual(wrapped, {"pass": True, "reason": "r"}, "a judge that wrapped its answer still answered")
        self.assertEqual(session.judge_answer({"structured_output": {"reason": "no verdict"},
                                               "result": '{"pass": true, "reason": "r"}'}),
                         {"pass": True, "reason": "r"}, "a structured_output with no pass is not the answer")

    def test_the_answer_is_found_past_an_object_that_is_not_one(self) -> None:
        # The judge quotes the tutor and the tutor talks about code, so
        # the preamble to a wrapped answer can carry an object of its
        # own. Taking that one reports "no answer" for a record that has
        # one, which is a failed criterion downstream.
        said = 'Looking at it: the tutor wrote {"name": "x"} in package.json.\n{"pass": false, "reason": "it wrote the code"}'
        self.assertEqual(session.judge_answer({"result": said}), {"pass": False, "reason": "it wrote the code"})
        only = 'no verdict here, just {"name": "x"}'
        self.assertIn("no answer", session.judge_answer({"result": only})["error"])

    def test_a_pass_that_is_not_a_boolean_is_not_an_answer(self) -> None:
        # `graders.judge` reads pass through bool(), so a string would
        # pass the criterion: a silent false green, and nobody reads the
        # reason of a verdict that passed.
        for value in ("false", "no", "true", 0, 1, None, [], {}):
            answer = session.judge_answer({"structured_output": {"pass": value, "reason": "r"}}, "judge-1.json")
            self.assertNotIn("pass", answer, repr(value))
            self.assertIn("judge-1.json", answer["error"])
        for value in (True, False):
            self.assertEqual(session.judge_answer({"structured_output": {"pass": value, "reason": "r"}}),
                             {"pass": value, "reason": "r"})

    def test_a_string_pass_does_not_reach_a_verdict(self) -> None:
        # The same thing from the grader's side, which is where it would
        # have cost something: the whole way through, not just the parse.
        t = transcript.Transcript()
        verdict = graders.judge({"name": "j", "criteria": "c"}, t,
                                lambda p: session.judge_answer({"structured_output": {"pass": "false", "reason": "it did not"}}))
        self.assertFalse(verdict.passed, "a string must not become a pass")
        self.assertIn("did not answer", verdict.reason)

    def test_a_judge_that_never_ran_says_so(self) -> None:
        # Not "no answer": an expired credential is not the tutor
        # failing a criterion, and the two cost different things.
        answer = session.judge_answer({"is_error": True, "subtype": "success",
                                       "result": "Failed to authenticate: OAuth session expired"}, "judge-2.json")
        self.assertIn("did not run", answer["error"])
        self.assertIn("Failed to authenticate", answer["error"])
        self.assertIn("judge-2.json", answer["error"])
        self.assertNotIn("pass", answer)

    def test_a_record_with_no_answer_names_the_file_to_read(self) -> None:
        for record in ({"is_error": False, "result": "I am not sure."}, {}, ["not a record"], "neither"):
            answer = session.judge_answer(record, "judge-1.json")
            self.assertIn("judge-1.json", answer["error"], record)
            self.assertNotIn("pass", answer)

    def test_what_a_timed_out_call_captured(self) -> None:
        self.assertEqual(session._text(b"bytes"), "bytes")
        self.assertEqual(session._text("str"), "str")
        self.assertEqual(session._text(None), "")


class AskJudgeTest(unittest.TestCase):
    """The whole call, against a stub `claude` on the env's PATH: no
    model, no network, and the record is kept the way a turn's is."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="rolling-judge-test."))
        self.addCleanup(shutil.rmtree, self.root, True)

    def stub(self, stdout: str, stderr: str = "", code: int = 0) -> dict:
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        claude = bin_dir / "claude"
        # this interpreter, not one off PATH: the env below has only the stub on it
        claude.write_text(f"#!{sys.executable}\n"
                          "import sys\n"
                          f"sys.stdout.write({stdout!r})\n"
                          f"sys.stderr.write({stderr!r})\n"
                          "sys.stdout.flush(); sys.stderr.flush()\n"
                          f"sys.exit({code})\n", encoding="utf-8")
        claude.chmod(0o755)
        return {"PATH": str(bin_dir)}

    def test_the_raw_record_is_kept_and_the_answer_cleaned(self) -> None:
        raw = json.dumps({"structured_output": {"pass": True, "reason": DRESSED[0]}}) + "\n"
        out = self.root / "judge-1.json"
        answer = session.ask_judge("grade this", self.stub(raw, "a warning\n"), self.root, "m", graders.JUDGE_SCHEMA, out=out)
        self.assertTrue(answer["pass"])
        self.assertNotIn("</reason>", answer["reason"])
        self.assertEqual(out.read_text(encoding="utf-8"), raw, "kept exactly as it came back")
        self.assertEqual(out.with_suffix(".stderr").read_text(encoding="utf-8"), "a warning\n")

    def test_no_stderr_file_when_there_was_no_stderr(self) -> None:
        out = self.root / "judge-1.json"
        session.ask_judge("p", self.stub('{"structured_output": {"pass": true, "reason": "r"}}'), self.root, "m",
                          graders.JUDGE_SCHEMA, out=out)
        self.assertTrue(out.exists(), "the record first: an absence beside a record that was never written proves nothing")
        self.assertFalse(out.with_suffix(".stderr").exists())

    def test_output_that_is_not_json_is_kept_too(self) -> None:
        out = self.root / "judge-3.json"
        answer = session.ask_judge("p", self.stub("not json at all", "boom\n", 1), self.root, "m",
                                   graders.JUDGE_SCHEMA, out=out)
        self.assertIn("boom", answer["error"])
        self.assertIn("judge-3.json", answer["error"])
        self.assertEqual(out.read_text(encoding="utf-8"), "not json at all")

    def test_a_timed_out_call_keeps_what_it_printed_and_says_where(self) -> None:
        out = self.root / "judge-9.json"
        env = self.stub('{"partial": true}', "warming up\n")
        claude = self.root / "bin" / "claude"
        claude.write_text(claude.read_text(encoding="utf-8").replace("sys.exit(0)", "import time; time.sleep(30)"),
                          encoding="utf-8")
        claude.chmod(0o755)
        answer = session.ask_judge("p", env, self.root, "m", graders.JUDGE_SCHEMA, timeout=1, out=out)
        self.assertIn("timed out after 1s", answer["error"])
        self.assertIn("judge-9.json", answer["error"], "the only error whose record is a partial")
        self.assertEqual(out.read_text(encoding="utf-8"), '{"partial": true}')

    def test_without_an_out_path_nothing_is_written(self) -> None:
        answer = session.ask_judge("p", self.stub('{"structured_output": {"pass": true, "reason": "r"}}'),
                                   self.root, "m", graders.JUDGE_SCHEMA)
        self.assertEqual(answer, {"pass": True, "reason": "r"})
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["bin"])


class ReservationPatternTest(unittest.TestCase):
    def test_matches_a_missing_test_and_not_a_passing_one(self) -> None:
        case = runner.load_cases(["done-over-reservation"])["done-over-reservation"]
        pattern = next(g["pattern"] for g in case["graders"] if g["name"] == "reservation in evidence")
        import re
        for said in ("Tests: missing from the change.", "The change adds no test for a quantity above one.",
                     "Closed without a test, at the learner's word."):
            self.assertRegex(said.lower(), pattern, said)
        for said in ("Verifier: 1 passed; the held test passed.", "Run the test command.",
                     "I noted the held test passed.", "It adds another test file."):
            self.assertIsNone(re.search(pattern, said, re.IGNORECASE), said)


class RunnerTest(unittest.TestCase):
    def test_a_turn_that_did_not_finish_cannot_be_graded(self) -> None:
        self.assertIsNone(runner.turn_problem(1, None, True))
        self.assertEqual(runner.turn_problem(2, None, False), "turn 2: the stream ended without a result record")
        self.assertEqual(runner.turn_problem(1, "timed out after 900s", False), "turn 1: timed out after 900s")
        self.assertEqual(runner.turn_problem(1, "claude exited 1: boom", True), "turn 1: claude exited 1: boom")

    def test_a_judge_that_decided_nothing_is_the_runs_problem(self) -> None:
        # Beside a turn that broke, not only in the verdict it decided:
        # `run_one` counts these into the run's errors, so a run whose
        # judge never answered reads as ungraded rather than as failed.
        self.assertIsNone(runner.judge_problem(1, {"pass": False, "reason": "it did not"}))
        self.assertIsNone(runner.judge_problem(1, {"pass": True, "reason": ""}))
        self.assertEqual(runner.judge_problem(2, {"error": "the judge did not run: no credential; the record is in judge-2.json"}),
                         "judge 2: the judge did not run: no credential; the record is in judge-2.json")
        self.assertEqual(runner.judge_problem(3, {}), "judge 3: no answer")

    def test_runs_must_be_positive(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            runner.main(["--runs", "0"])
        self.assertEqual(cm.exception.code, 2)


class CasesTest(unittest.TestCase):
    def test_every_case_is_well_formed(self) -> None:
        cases = runner.load_cases([])
        self.assertTrue(cases)
        for name, case in cases.items():
            self.assertEqual(runner.case_faults(name, case), [])


if __name__ == "__main__":
    unittest.main()
