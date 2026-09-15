"""The task's lifecycle in the repository: begin, end, close, and every
refusal, through the executables a skill would run."""

from __future__ import annotations

import os
import subprocess
import unittest

from support import WorldTest


class BeginFromFixTest(WorldTest):
    def test_held_test_stays_out_of_the_tree(self):
        w = self.w
        out = self.assertRuns("begin-task", "greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        fields = dict(l.split(": ", 1) for l in out.split("\n") if ": " in l)
        self.assertTrue(fields["branch"].startswith("rolling/greet-politely-"))
        self.assertOnBranch(fields["branch"])
        self.assertEqual(fields["base"], w.git("rev-parse", "HEAD"))
        self.assertEqual(fields["return-to"], f"main {w.fix}")
        self.assertEqual(fields["held"], "tests/greet.test.sh")
        self.assertFalse((w.top / "tests/greet.test.sh").exists())
        self.assertTrue((w.learner.held / "tests/greet.test.sh").is_file())
        self.assertIn("HELLO", w.read("src/greet.sh"), "the code is as it was before the fix")
        self.assertClean()
        self.assertNotIn(w.fix, w.git("log", "--format=%H"), "the fix is not in the branch's history")
        self.assertEqual(w.git("rev-parse", "HEAD^"), w.pre)

    def test_shown_test_is_present_and_failing(self):
        w = self.w
        out = self.assertRuns("begin-task", "setup", "--fix", w.fix, "--shown", "tests/greet.test.sh")
        self.assertTrue((w.top / "tests/greet.test.sh").is_file())
        self.assertClean()
        self.assertNotIn("held:", out)
        self.assertNotEqual(subprocess.run(["sh", "run-test.sh", "tests/greet.test.sh"], cwd=str(w.top), capture_output=True, check=False).returncode, 0)

    def test_refusals_leave_head_where_it_was(self):
        w = self.w
        w.write("src/greet.sh", w.read("src/greet.sh") + "dirty\n")
        self.assertIn("not clean", self.assertRuns("begin-task", "setup", "--fix", w.fix, "--held", "tests/greet.test.sh", status=1))
        w.git("checkout", "--", "src/greet.sh")
        self.assertIn("root commit", self.assertRuns("begin-task", "setup", "--fix", w.pre, "--held", "tests/greet.test.sh", status=1))
        self.assertIn("not changed by", self.assertRuns("begin-task", "setup", "--fix", w.fix, "--held", "src/nope.sh", status=1))
        self.assertRuns("begin-task", "Bad Slug", "--fix", w.fix, status=1)
        self.assertRuns("begin-task", "setup", "--fix", w.fix, "--held", "/etc/passwd", status=1)
        self.assertRuns("begin-task", "setup", "--fix", w.fix, "--held", "../x", status=1)
        self.assertIn("is listed twice", self.assertRuns("begin-task", "setup", "--fix", w.fix, "--held", "tests/greet.test.sh", "--shown", "tests/greet.test.sh", status=1))
        self.assertIn("is not a regular file at", self.assertRuns("begin-task", "setup", "--fix", w.fix, "--held", "tests", status=1))
        w.git("checkout", "-q", "-b", "side")
        w.git("commit", "-q", "--allow-empty", "-m", "side")
        w.git("switch", "-q", "main")
        w.git("merge", "-q", "--no-ff", "-m", "merge", "side")
        merge = w.git("rev-parse", "HEAD")
        self.assertIn("merge commit", self.assertRuns("begin-task", "setup", "--fix", merge, "--held", "tests/greet.test.sh", status=1))
        self.assertOnBranch("main")
        self.assertRuns("begin-task", "setup", "--wat", status=2)
        self.assertIn("go with --fix", self.assertRuns("begin-task", "setup", "--held", "y", "--here", "x", status=2))
        self.assertIn("one of --fix", self.assertRuns("begin-task", "setup", status=2))

    def test_symlink_in_the_fix_is_refused(self):
        w = self.w
        os.symlink("../src/greet.sh", w.top / "tests/link.test.sh")
        w.git("add", "tests/link.test.sh")
        w.git("commit", "-q", "-m", "link")
        linkfix = w.git("rev-parse", "HEAD")
        self.assertIn("is not a regular file at", self.assertRuns("begin-task", "greet-politely", "--fix", linkfix, "--held", "tests/link.test.sh", status=1))

    def test_open_task_is_refused_and_stale_held_is_cleared(self):
        w = self.w
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        w.held_task(branch, base)
        out = self.assertRuns("begin-task", "setup", "--fix", w.fix, "--shown", "tests/greet.test.sh", status=1)
        self.assertIn("a task is already open (greet-politely)", out)
        self.assertOnBranch(branch)
        self.assertRuns("end-task")
        self.assertRuns("close-task")
        self.assertFalse(w.learner.held.exists())
        (w.learner.held / "tests").mkdir(parents=True)
        (w.learner.held / "tests/stale.sh").write_text("stale")
        w.begin("setup", "--fix", w.fix, "--shown", "tests/greet.test.sh")
        self.assertFalse((w.learner.held / "tests/stale.sh").exists())

    def test_needs_the_data_directory_for_a_held_test(self):
        rc, out = self.w.run("begin-task", "setup", "--fix", self.w.fix, "--held", "tests/greet.test.sh", env={"ROLLING_DATA": ""})
        self.assertEqual(rc, 1)
        self.assertIn("ROLLING_DATA is not set", out)
        self.assertOnBranch("main")

    def test_dash_leading_paths(self):
        w = self.w
        w.write("-dashdir/t.sh", "y\n")
        w.git("add", "--", "-dashdir")
        w.git("commit", "-q", "-m", "dash")
        dashfix = w.git("rev-parse", "HEAD")
        branch, base = w.begin("greet-politely", "--fix", dashfix, "--held=-dashdir/t.sh")
        self.assertTrue((w.learner.held / "-dashdir/t.sh").is_file())


class BeginHereTest(WorldTest):
    def test_commits_only_the_named_files(self):
        w = self.w
        w.write("tests/seam.test.sh", "echo seam\n")
        out = self.assertRuns("begin-task", "setup", "--here", "tests/seam.test.sh")
        self.assertIn(f"return-to: main {w.fix}", out)
        self.assertClean()
        self.assertIn("tests/seam.test.sh", w.git("show", "--stat", "--format=", "HEAD"))

    def test_refuses_the_learners_own_changes(self):
        w = self.w
        w.write("src/greet.sh", w.read("src/greet.sh") + "# learner's own edit\n")
        w.write("tests/seam.test.sh", "seam\n")
        out = self.assertRuns("begin-task", "setup", "--here", "tests/seam.test.sh", status=1)
        self.assertIn("src/greet.sh", out)
        self.assertOnBranch("main")
        self.assertIn("learner's own edit", w.read("src/greet.sh"))

    def test_files_only(self):
        w = self.w
        w.write("newdir/t.sh", "t\n")
        w.write("newdir/learner-notes.txt", "notes\n")
        self.assertIn("never a directory", self.assertRuns("begin-task", "setup", "--here", "newdir", status=1))
        self.assertIn("newdir/learner-notes.txt", self.assertRuns("begin-task", "setup", "--here", "newdir/t.sh", status=1))
        self.assertRuns("begin-task", "setup", "--here", status=2)

    def test_non_ascii_name(self):
        w = self.w
        w.write("src/café.sh", "x\n")
        self.assertRuns("begin-task", "setup", "--here", "src/café.sh")
        self.assertIn("café", w.git("show", "--stat", "--format=", "HEAD"))


class EndAndCloseTest(WorldTest):
    def test_end_commits_and_returns(self):
        w = self.w
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        w.held_task(branch, base)
        w.write("src/greet.sh", w.read("src/greet.sh") + "edit\n")
        w.write("src/other.sh", "new\n")
        out = self.assertRuns("end-task")
        self.assertIn("committed the learner's uncommitted work", out)
        self.assertIn("back on main", out)
        self.assertOnBranch("main")
        self.assertEqual(w.git("rev-parse", "HEAD"), w.fix, "main is untouched")
        self.assertIn("src/other.sh", w.git("show", "--stat", "--format=", branch))
        self.assertClean()
        self.assertIn(f"not on {branch}", self.assertRuns("end-task", status=1))

    def test_end_falls_back_to_the_sha(self):
        w = self.w
        branch, base = w.begin("setup", "--fix", w.fix, "--shown", "tests/greet.test.sh")
        w.task(lesson="setup", mode="write", branch=branch, base=base, return_to=f"gone-branch {w.pre}", scope="src")
        out = self.assertRuns("end-task")
        self.assertIn("detached", out)
        self.assertEqual(w.git("rev-parse", "HEAD"), w.pre)

    def test_close_removes_only_the_tasks_files(self):
        w = self.w
        w.task(lesson="setup", mode="write", scope="src")
        w.learner.reference.write_text("r")
        (w.learner.held / "tests").mkdir(parents=True)
        (w.learner.dir / "evidence").mkdir()
        (w.learner.dir / "evidence/setup.md").write_text("e")
        w.learner.profile.write_text("# Profile\n")
        out = self.assertRuns("close-task")
        self.assertIn("task closed", out)
        self.assertFalse(w.learner.task_file.exists())
        self.assertFalse(w.learner.reference.exists())
        self.assertFalse(w.learner.held.exists())
        self.assertTrue(w.learner.profile.exists())
        self.assertTrue((w.learner.dir / "evidence/setup.md").exists())


if __name__ == "__main__":
    unittest.main()
