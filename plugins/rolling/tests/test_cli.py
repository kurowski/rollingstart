"""The inline commands' contract: always exit 0, absence in words; and
the small action commands (export, the checks' exit codes)."""

from __future__ import annotations

import os
import unittest

from support import WorldTest, is_root

from rolling.model import Task


class ShowTest(WorldTest):
    def test_map_check_reports_at_exit_zero(self):
        w = self.w
        self.assertIn("MAP: ok", self.assertRuns("show", "map-check"))
        w.write(".rolling/map.md", w.read(".rolling/map.md").replace("mode: write", "mode: sideways"))
        out = self.assertRuns("show", "map-check")
        self.assertIn("mode", out)
        self.assertIn("MAP: 1 fault(s)", out)
        self.assertRuns("check-map", status=1)
        w.restore_map()

    def test_every_subcommand(self):
        w = self.w
        self.assertIn("name: Scratch", self.assertRuns("show", "map"))
        lessons = self.assertRuns("show", "lessons")
        self.assertIn("### greet-politely", lessons)
        self.assertIn("requires: [setup]", lessons)
        self.assertNotIn("## Rubric", lessons, "the index omits bodies")
        self.assertIn("## Rubric", self.assertRuns("show", "lesson", "setup"))
        self.assertIn("no lesson 'nope'", self.assertRuns("show", "lesson", "nope"))
        self.assertIn("not a lesson slug", self.assertRuns("show", "lesson", "Bad Slug"))
        self.assertIn("no open task", self.assertRuns("show", "lesson"))
        w.task(lesson="setup", mode="write", scope="src")
        self.assertIn("title: Setup", self.assertRuns("show", "lesson"))
        self.assertIn("lesson: setup", self.assertRuns("show", "task"))
        self.assertIn("no profile", self.assertRuns("show", "profile"))
        w.learner.profile.write_text("# Profile\n")
        self.assertIn("# Profile", self.assertRuns("show", "profile"))
        corpus = self.assertRuns("show", "corpus")
        self.assertIn("## Corpus", corpus)
        self.assertNotIn("## Regions", corpus)
        self.assertIn("(clean)", self.assertRuns("show", "tree"))
        w.write("src/new.sh", "x")
        tree = self.assertRuns("show", "tree")
        self.assertIn("?? src/new.sh", tree)
        self.assertIn("on main", tree)
        self.assertEqual(self.assertRuns("show", "state-dir").strip(), str(w.learner.dir))
        self.assertIn("usage:", self.assertRuns("show"))

    def test_absence_is_words_not_status(self):
        rc, out = self.w.run("show", "profile", env={"ROLLING_DATA": ""})
        self.assertEqual(rc, 0)
        self.assertIn("ROLLING_DATA is not set", out)
        rc, out = self.w.run("show", "map", env={"ROLLING_DATA": ""})
        self.assertEqual(rc, 0)
        self.assertIn("name: Scratch", out, "the map does not need the data directory")
        rc, out = self.w.run("show", "tree", env={"ROLLING_DATA": ""})
        self.assertEqual((rc, "(clean)" in out), (0, True))


class SessionTest(WorldTest):
    def test_claim_without_and_with_a_task(self):
        w = self.w
        self.assertIn("no task open", self.assertRuns("claim-session", "abc-123"))
        self.assertEqual(w.learner.session.read_text(), "abc-123\n")
        w.task(lesson="setup", mode="write", scope="src")
        self.assertIn("recorded in the open task", self.assertRuns("claim-session", "def-456"))
        text = w.learner.task_file.read_text()
        self.assertIn("tutor-session: def-456", text)
        self.assertIn("lesson: setup", text)
        self.assertIn("## Brief", text)
        self.assertRuns("claim-session", "ghi-789")
        text = w.learner.task_file.read_text()
        self.assertEqual(text.count("tutor-session:"), 1)
        self.assertIn("tutor-session: ghi-789", text)
        self.assertIn("not recorded", self.assertRuns("claim-session", "x; rm"))
        self.assertIn("not recorded", self.assertRuns("claim-session", ""))

    def test_claim_on_a_crlf_task(self):
        w = self.w
        w.task(lesson="setup", mode="write", scope="src")
        w.learner.task_file.write_bytes(w.learner.task_file.read_text().replace("\n", "\r\n").encode())
        self.assertRuns("claim-session", "crlf-1")
        self.assertEqual(Task.load(w.learner.task_file).tutor_session, "crlf-1")

    def test_session_start_exports_once(self):
        w = self.w
        envf = w.root / "env.sh"
        envf.write_text("")
        rc, _ = w.run("session-start", "/some/data dir", env={"CLAUDE_ENV_FILE": str(envf)}, stdin="{}")
        self.assertEqual(rc, 0)
        self.assertEqual(envf.read_text(), "export ROLLING_DATA='/some/data dir'\n")
        w.run("session-start", "/some/data dir", env={"CLAUDE_ENV_FILE": str(envf)})
        self.assertEqual(envf.read_text().count("ROLLING_DATA"), 1, "written once")
        self.assertEqual(w.run("session-start", "/x", env={"CLAUDE_ENV_FILE": ""})[0], 0)
        self.assertEqual(w.run("session-start", "", env={"CLAUDE_ENV_FILE": str(envf)})[0], 0)


class DiffTest(WorldTest):
    def test_fails_safe_in_words(self):
        w = self.w
        self.assertIn("no open task", self.assertRuns("diff"))
        w.task(lesson="setup", mode="write", base="main", scope="src", verify="check")
        self.assertIn("not a commit sha", self.assertRuns("diff"))
        w.task(lesson="setup", mode="write", base="0123456789abcdef0123456789abcdef01234567", scope="src", verify="check")
        self.assertIn("not a commit in this repository", self.assertRuns("diff"))

    def test_untracked_names_git_would_quote(self):
        w = self.w
        w.task(lesson="setup", mode="write", base=w.fix, scope="src", verify="check")
        w.write("src/ta\tb.sh", "tabbed\n")
        out = self.assertRuns("diff")
        self.assertIn("  src/ta\tb.sh", out)
        self.assertIn("+tabbed", out)

    def test_capped(self):
        w = self.w
        w.task(lesson="setup", mode="write", base=w.fix, scope="src", verify="check")
        w.write("src/big.txt", "\n".join(str(i) for i in range(500)))
        rc, out = w.run("diff", env={"ROLLING_DIFF_MAX_LINES": "50"})
        self.assertIn("DIFF: truncated at 50 of", out)


class ContractTest(WorldTest):
    """An inline command exits 0 whatever goes wrong; an action exits 1
    with a reason; neither ever prints a traceback."""

    def test_a_bad_environment_variable(self):
        w = self.w
        w.task(lesson="setup", mode="write", base=w.fix, scope="src", verify="check")
        for value in ("abc", "-5", ""):
            rc, out = w.run("diff", env={"ROLLING_DIFF_MAX_LINES": value})
            self.assertEqual(rc, 0, out)
            self.assertNotIn("Traceback", out)
            self.assertIn("## Diff", out)

    def test_a_broken_repository(self):
        w = self.w
        (w.top / ".git/index").write_bytes(b"garbage")
        for name in ("show tree", "diff", "verify", "report"):
            rc, out = w.run(*name.split())
            self.assertEqual(rc, 0, out)
            self.assertNotIn("Traceback", out)
        rc, out = w.run("begin-task", "setup", "--fix", w.fix, "--shown", "tests/greet.test.sh")
        self.assertEqual(rc, 1)
        self.assertNotIn("Traceback", out)

    def test_an_unreadable_lessons_directory(self):
        if is_root():
            self.skipTest("root can read anything")
        os.chmod(self.w.top / ".rolling/lessons", 0)
        try:
            rc, out = self.w.run("show", "lessons")
            self.assertEqual(rc, 0)
            self.assertNotIn("Traceback", out)
            rc, out = self.w.run("check-map")
            self.assertEqual(rc, 1)
            self.assertIn("cannot be read", out)
        finally:
            os.chmod(self.w.top / ".rolling/lessons", 0o755)

    def test_an_unreadable_task_is_not_an_absent_one(self):
        w = self.w
        w.task(lesson="setup", mode="write", scope="src")
        w.learner.task_file.write_text("no fence\n")
        self.assertIn("no frontmatter block", self.assertRuns("verify"))
        self.assertNotIn("no open task", self.assertRuns("verify"))

    def test_report_keeps_both_halves(self):
        w = self.w
        w.task(lesson="setup", mode="write", base=w.fix, scope="src", verify="check")
        (w.top / ".git/index").write_bytes(b"garbage")
        out = self.assertRuns("report")
        self.assertIn("DIFF: not captured (git failed:", out)
        self.assertIn("## Verifier", out)
        self.assertIn("VERIFIER:", out)

    def test_a_stale_held_file_does_not_strand_a_branch(self):
        w = self.w
        w.learner.dir.mkdir(parents=True, exist_ok=True)
        w.learner.held.write_text("not a directory")
        w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        self.assertTrue((w.learner.held / "tests/greet.test.sh").is_file())

    def test_no_abbreviated_flags(self):
        out = self.assertRuns("verify", "--on")
        self.assertIn("PROOF: not ok (bad arguments)", out)

    def test_a_flag_typo_is_not_silently_the_other_mode(self):
        out = self.assertRuns("verify", "--onbase")
        self.assertIn("rolling-verify:", out)
        self.assertIn("PROOF: not ok (bad arguments)", out)

    def test_begin_refuses_before_writing_when_the_data_dir_is_unwritable(self):
        if is_root():
            self.skipTest("root can write anywhere")
        w = self.w
        w.data.mkdir(parents=True, exist_ok=True)
        os.chmod(w.data, 0o500)
        try:
            rc, out = w.run("begin-task", "greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
            self.assertEqual(rc, 1)
            self.assertIn("learner directory", out)
            self.assertNotIn("Traceback", out)
            self.assertOnBranch("main")
        finally:
            os.chmod(w.data, 0o755)


class ExportAndChecksTest(WorldTest):
    def test_export(self):
        w = self.w
        w.learner.dir.mkdir(parents=True)
        w.learner.profile.write_text("# Profile\n")
        out = self.assertRuns("export", str(w.root / "out"))
        self.assertTrue((w.root / "out/profile.md").is_file())
        self.assertIn("profile.md", out)
        self.assertIn("refusing to overwrite", self.assertRuns("export", str(w.root / "out"), status=1))
        self.assertRuns("export", status=2)

    def test_check_exit_codes(self):
        w = self.w
        self.assertIn("map ok", self.assertRuns("check-map"))
        self.assertIn("2 lessons, 2 regions, 1 courses", self.assertRuns("check-map", str(w.top / ".rolling")))
        self.assertRuns("check-profile", status=1)
        self.assertRuns("check-task", status=1)
        w.task(lesson="setup", mode="write", branch="b", base=w.fix, return_to=f"main {w.pre}", started="2026-09-15", tutor_session="s1", scope="src", verify="check")
        self.assertIn("task ok", self.assertRuns("check-task"))


if __name__ == "__main__":
    unittest.main()
