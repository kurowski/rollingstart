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
        self.assertTrue(graders.unchanged({"name": "u", "under": ["billing"]}, self.fx.top).passed)
        (self.fx.top / "billing" / "invoice.py").write_text("changed\n")
        self.assertFalse(graders.unchanged({"name": "u", "under": ["billing"]}, self.fx.top).passed)

    def test_judge_verdicts(self) -> None:
        t = self.t(say("hi"))
        ok = graders.judge({"name": "j", "criteria": "says hi"}, t, lambda p: {"pass": True, "reason": "said hi"})
        self.assertEqual((ok.passed, ok.reason), (True, "said hi"))
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
        env = session.clean_env(base, Path("/tmp/cfg"), "tok")
        self.assertEqual(env["PATH"], "/usr/bin:/bin")
        self.assertEqual((env["CLAUDE_CONFIG_DIR"], env["CLAUDE_CODE_OAUTH_TOKEN"], env["HOME"]), ("/tmp/cfg", "tok", "/home/u"))
        for k in ("CLAUDE_CODE_SESSION_ID", "CLAUDECODE", "ROLLING_DATA", "CLAUDE_EFFORT", "ANTHROPIC_BASE_URL"):
            self.assertNotIn(k, env)

    def test_first_turn_names_the_session_and_a_follow_up_resumes_it(self) -> None:
        first = session.turn_command("hi", Path("/p"), "m", SID, resume=False, max_turns=5)
        again = session.turn_command("more", Path("/p"), "m", SID, resume=True, max_turns=5)
        self.assertEqual(first[first.index("--session-id") + 1], SID)
        self.assertEqual(again[again.index("--resume") + 1], SID)
        self.assertNotIn("--session-id", again)


class RunnerTest(unittest.TestCase):
    def test_a_turn_that_did_not_finish_cannot_be_graded(self) -> None:
        self.assertIsNone(runner.turn_problem(1, None, True))
        self.assertEqual(runner.turn_problem(2, None, False), "turn 2: the stream ended without a result record")
        self.assertEqual(runner.turn_problem(1, "timed out after 900s", False), "turn 1: timed out after 900s")
        self.assertEqual(runner.turn_problem(1, "claude exited 1: boom", True), "turn 1: claude exited 1: boom")

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
