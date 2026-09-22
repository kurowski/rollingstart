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
        self.assertIn("no open lesson", self.assertRuns("show", "lesson"))
        w.task(lesson="setup", mode="write", scope="src")
        shown = self.assertRuns("show", "lesson")
        self.assertIn("title: Setup", shown)
        self.assertTrue(shown.startswith("### setup\n"), "the slug leads, since the file does not carry it")
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

    def test_a_lesson_opens_before_any_exercise_and_closes_with_it(self):
        """next opens a lesson for the walkthrough; the exercise, if the
        learner takes the offer, is built later; close removes both."""
        w = self.w
        self.assertIn("not a lesson slug", self.assertRuns("begin-lesson", "Bad Slug", status=1))
        self.assertIn("no lesson 'nope'", self.assertRuns("begin-lesson", "nope", status=1))
        self.assertIn("no open lesson", self.assertRuns("show", "lesson"))
        self.assertIn("LESSON: setup is open", self.assertRuns("begin-lesson", "setup"))
        self.assertTrue(self.assertRuns("show", "lesson").startswith("### setup\n"))
        self.assertIn("(no open task)", self.assertRuns("show", "task"))
        self.assertIn("LESSON: greet-politely is open", self.assertRuns("begin-lesson", "greet-politely"), "reopening with another lesson, no task yet, is fine")
        # Closing after the walkthrough alone: the marker goes, nothing else was there.
        out = self.assertRuns("close-task")
        self.assertIn("removed lesson", out)
        self.assertIn("closed;", out)
        self.assertIn("no open lesson", self.assertRuns("show", "lesson"))
        # Notes follow the open lesson too, before any task exists.
        self.assertRuns("begin-lesson", "greet-politely")
        self.assertRuns("note", "greet-politely", stdin="**Route.** Chosen for the walkthrough.\n")
        self.assertIn("Chosen for the walkthrough", self.assertRuns("show", "evidence"))
        # A task for another lesson is refused while this one is open; the same lesson is fine, and marks it.
        self.assertIn("the open lesson is greet-politely, not setup", self.assertRuns("begin-task", "setup", "--fix", w.fix, "--shown", "tests/greet.test.sh", status=1))
        self.assertOnBranch("main")
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        self.assertEqual(w.learner.lesson_file.read_text().strip(), "greet-politely")
        w.held_task(branch, base)
        self.assertIn("a task is open (greet-politely)", self.assertRuns("begin-lesson", "setup", status=1))
        self.assertRuns("end-task")
        self.assertRuns("close-task")
        self.assertFalse(w.learner.lesson_file.exists())

    def test_a_marker_the_toolkit_did_not_write_is_handled(self):
        w = self.w
        w.learner.dir.mkdir(parents=True, exist_ok=True)
        w.learner.lesson_file.write_bytes(b"\xff\xfe not text")
        self.assertIn("no open lesson", self.assertRuns("show", "lesson"), "garbage reads as no lesson, in words")
        w.learner.lesson_file.unlink()
        w.learner.lesson_file.mkdir()
        self.assertIn("not a plain file", self.assertRuns("begin-lesson", "setup", status=1))
        self.assertIn("it was a directory", self.assertRuns("close-task"))
        self.assertFalse(w.learner.lesson_file.exists())
        outside = w.root / "elsewhere"
        outside.write_text("keep me\n")
        os.symlink(outside, w.learner.lesson_file)
        self.assertIn("symbolic link", self.assertRuns("begin-lesson", "setup", status=1))
        self.assertEqual(outside.read_text(), "keep me\n", "nothing was written through the link")
        self.assertIn("removed lesson", self.assertRuns("close-task"))
        self.assertTrue(outside.is_file(), "the link went, not its target")
        os.symlink(outside, w.learner.lesson_file)
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        self.assertEqual(outside.read_text(), "keep me\n", "begin-task does not write through the link either")
        w.held_task(branch, base)
        self.assertRuns("end-task")
        self.assertRuns("close-task")

    def test_opening_a_lesson_clears_a_reference_no_exercise_was_served_with(self):
        w = self.w
        self.assertRuns("begin-lesson", "setup")
        w.learner.reference.write_text("the answer to an exercise that never got built\n")
        out = self.assertRuns("begin-lesson", "greet-politely")
        self.assertIn("leftover reference.md", out)
        self.assertFalse(w.learner.reference.exists())
        self.assertIn("(no reference notes)", self.assertRuns("show", "reference"))

    def test_evidence_shows_the_lessons_notes(self):
        w = self.w
        self.assertIn("no open lesson", self.assertRuns("show", "evidence"))
        self.assertIn("no evidence yet for setup", self.assertRuns("show", "evidence", "setup"))
        self.assertRuns("note", "setup", stdin="**Observation.** Showed the reference on request.\n")
        self.assertIn("Showed the reference on request", self.assertRuns("show", "evidence", "setup"))
        w.task(lesson="setup", mode="write", scope="src")
        self.assertIn("Showed the reference on request", self.assertRuns("show", "evidence"), "the open task's lesson by default")
        self.assertIn("not a lesson slug", self.assertRuns("show", "evidence", "Bad Slug"))

    def test_reference_shows_the_notes_and_the_diff(self):
        """What the tutor relays when the learner asks to see the answer:
        for a fix, the fix's own change; for a seam, the patch."""
        w = self.w
        out = self.assertRuns("show", "reference")
        self.assertIn("(no reference notes)", out)
        self.assertIn("no open task", out)
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        w.held_task(branch, base)
        w.learner.reference.write_text("The fix lowers the shouting.\n")
        out = self.assertRuns("show", "reference")
        self.assertIn("The fix lowers the shouting.", out)
        self.assertIn("-printf 'HELLO", out)
        self.assertIn("+printf 'Hello", out)
        self.assertNotIn("greet.test.sh", out, "the held test is not part of the answer")
        self.assertRuns("end-task")
        self.assertRuns("close-task")
        w.write("tests/seam.test.sh", "seam\n")
        branch, base = w.begin("setup", "--here", "tests/seam.test.sh")
        w.task(lesson="setup", mode="write", branch=branch, base=base, return_to=f"main {w.fix}",
               started="2026-09-21", tutor_session="s1", scope="src", verify="check")
        w.learner.patch.write_text("diff --git a/src/greet.sh b/src/greet.sh\n--- a/src/greet.sh\n+++ b/src/greet.sh\n@@ -1 +1 @@\n-x\n+y\n")
        out = self.assertRuns("show", "reference")
        self.assertIn("+++ b/src/greet.sh", out)
        self.assertRuns("end-task")
        self.assertRuns("close-task")

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
