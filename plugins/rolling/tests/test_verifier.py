"""The verifier and the held test: the structured report, the proof,
argument safety, and everything six review rounds found about applying
and reverting the held test: the learner's own file always comes back,
a kill leaves a record the next script finishes, a failed restore is
never claimed as clean, symbolic links are refused, aliases are refused.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
import unittest
from pathlib import Path

from support import BIN, GREET_TEST, WorldTest, is_root

from rolling import heldtest
from rolling.model import Map, Task
from rolling.verifier import Kind, Outcome, Verifier


class VerifierTest(WorldTest):
    def setUp(self):
        super().setUp()
        self.branch, self.base = self.w.begin("greet-politely", "--fix", self.w.fix, "--held", "tests/greet.test.sh")

    def verify(self, on_base=False, on_reference=False):
        w = self.w
        return Verifier(w.top, w.learner, Map.load(w.top / ".rolling"), Task.load(w.learner.task_file), on_base=on_base, on_reference=on_reference).run()

    def test_proof_with_the_reference_applied(self):
        """The forward half: the fix's change goes in as a patch, every
        line passes, the held test included, and both come back out."""
        w = self.w
        w.held_task(self.branch, self.base)
        rep = self.verify(on_reference=True)
        self.assertEqual([r.outcome for r in rep.lines], [Outcome.PASS, Outcome.PASS])
        self.assertTrue(rep.proof_ok, rep.render())
        self.assertEqual(rep.notes, ["REFERENCE reversed"])
        self.assertIn("HELLO", w.read("src/greet.sh"), "the fix is back out")
        self.assertFalse((w.top / "tests/greet.test.sh").exists(), "the held test is back out")
        self.assertFalse((w.learner.dir / ".reference.applied.patch").exists())
        self.assertClean()
        out = self.assertRuns("verify", "--on-reference")
        self.assertIn("PROOF: ok (with the reference applied", out)
        self.assertIn("PROOF: not ok (bad arguments)", self.assertRuns("verify", "--on-base", "--on-reference"))

    def test_reference_that_fails_is_still_reversed(self):
        w = self.w
        w.held_task(self.branch, self.base, verify=["check", "fails"])
        rep = self.verify(on_reference=True)
        self.assertFalse(rep.proof_ok)
        self.assertIn("REFERENCE reversed", rep.notes)
        self.assertIn("PROOF: not ok (see FAIL", "\n".join(rep.render()))
        self.assertClean()

    def test_reference_needs_a_clean_tree_and_something_to_apply(self):
        w = self.w
        w.held_task(self.branch, self.base)
        w.write("src/greet.sh", w.read("src/greet.sh") + "# learner\n")
        rep = self.verify(on_reference=True)
        self.assertIn("not clean", rep.not_run)
        self.assertEqual(self.assertRuns("verify", "--on-reference").strip().split("\n")[-1], "PROOF: not ok (the verifier did not run)")
        w.git("checkout", "--", "src/greet.sh")
        w.held_task(self.branch, self.base, fix="")
        rep = self.verify(on_reference=True)
        self.assertIn("no fix: line and no reference patch", rep.not_run)
        self.assertRuns("write", "patch", stdin="not a patch\n")
        rep = self.verify(on_reference=True)
        self.assertIn("does not apply", rep.not_run)
        self.assertFalse((w.learner.dir / ".reference.applied.patch").exists())
        self.assertClean()

    def test_a_check_that_dirties_the_tree_fails_the_proof(self):
        w = self.w
        w.add_command("junk", "sh -c 'echo x > junk.txt'")
        w.git("commit", "-q", "-am", "a command that litters")
        w.held_task(self.branch, w.git("rev-parse", "HEAD"), verify=["check", "junk"])
        out = self.assertRuns("verify", "--on-reference")
        self.assertIn("REFERENCE reversed, but the tree is not clean afterwards", out)
        self.assertIn("?? junk.txt", out)
        self.assertIn("PROOF: not ok", out)

    def test_a_root_commit_fix_is_refused_in_words(self):
        w = self.w
        w.held_task(self.branch, self.base, fix=w.pre)
        out = self.assertRuns("verify", "--on-reference")
        self.assertIn("root commit", out)
        self.assertTrue(out.strip().endswith("PROOF: not ok (the verifier did not run)"))
        self.assertClean()

    def test_a_killed_proof_is_repaired_by_the_next_command(self):
        """SIGKILL leaves the applied copy and the reference in the tree;
        every tree-touching command reverses it first, or refuses."""
        w = self.w
        w.held_task(self.branch, self.base)
        patch = w.git("diff", "--binary", "HEAD", w.fix, "--", "src/greet.sh") + "\n"

        def killed_mid_proof():   # what SIGKILL leaves: the copy, the commit it went in on, the tree patched
            w.learner.applied_patch.write_text(patch)
            w.learner.applied_at.write_text(w.git("rev-parse", "HEAD") + "\n")
            w.git("apply", str(w.learner.applied_patch))
        killed_mid_proof()
        self.assertIn("Hello", w.read("src/greet.sh"), "the reference is in the tree, as after a kill")
        out = self.assertRuns("diff")
        self.assertIn("REFERENCE repaired", out)
        self.assertNotIn("Hello", out.split("## Diff")[1], "the diff shows nothing of the reference")
        self.assertFalse(w.learner.applied_patch.exists())
        self.assertFalse(w.learner.applied_at.exists())
        self.assertClean()
        # And when it no longer reverses cleanly: refuse, naming the file.
        killed_mid_proof()
        w.write("src/greet.sh", w.read("src/greet.sh") + "# the learner typed here\n")
        out = self.assertRuns("diff")
        self.assertIn("REFERENCE STILL APPLIED", out)
        self.assertIn("DIFF: not captured", out)
        self.assertIn("not starting a task", self.assertRuns("begin-task", "setup", "--fix", w.fix, status=1))
        self.assertIn("PROOF: not ok", self.assertRuns("verify", "--on-base"))
        self.assertTrue(w.learner.applied_patch.exists(), "the record is kept until a human finishes it")
        # And never on another commit: the record names where it went in.
        w.git("checkout", "-q", "--", "src/greet.sh")
        w.git("apply", str(w.learner.applied_patch))
        w.git("stash", "-q")
        w.git("switch", "-q", "main")
        out = self.assertRuns("diff")
        self.assertIn("REFERENCE STILL APPLIED", out)
        self.assertIn("HEAD is now", out)
        self.assertClean()
        self.assertEqual(w.git("rev-parse", "HEAD"), w.fix, "main's committed fix was not reverted")
        w.git("switch", "-q", self.branch)
        w.git("stash", "pop", "-q")
        self.assertIn("REFERENCE repaired", self.assertRuns("diff"))
        self.assertClean()
        # A record with no commit noted refuses too, saying so.
        killed_mid_proof()
        w.learner.applied_at.unlink()
        out = self.assertRuns("diff")
        self.assertIn("did not record", out)
        w.git("checkout", "-q", "--", "src/greet.sh")
        # A record that outlived its reverse is cleared, not refused.
        self.assertIn("record cleared", self.assertRuns("diff"))
        self.assertFalse(w.learner.applied_patch.exists())
        self.assertIn("## Diff", self.assertRuns("diff"))

    def test_a_mode_only_reference_is_still_repaired(self):
        """A mode change applies forward and reverses in either state, so
        the stale-record shortcut must not mistake it for already out."""
        w = self.w
        w.held_task(self.branch, self.base)
        patch = "diff --git a/src/greet.sh b/src/greet.sh\nold mode 100644\nnew mode 100755\n"
        w.learner.applied_patch.write_text(patch)
        w.learner.applied_at.write_text(w.git("rev-parse", "HEAD") + "\n")
        w.git("apply", str(w.learner.applied_patch))
        self.assertTrue(os.access(w.top / "src/greet.sh", os.X_OK), "applied to the worktree")
        out = self.assertRuns("diff")
        self.assertIn("REFERENCE repaired", out)
        self.assertNotIn("record cleared", out)
        self.assertFalse(os.access(w.top / "src/greet.sh", os.X_OK), "reversed")
        self.assertClean()

    @unittest.skipIf(is_root(), "root writes anywhere")
    def test_a_record_that_cannot_be_removed_is_said_so(self):
        w = self.w
        w.held_task(self.branch, self.base)
        patch = w.git("diff", "--binary", "HEAD", w.fix, "--", "src/greet.sh") + "\n"
        w.learner.applied_patch.write_text(patch)
        w.learner.applied_at.write_text(w.git("rev-parse", "HEAD") + "\n")
        w.git("apply", str(w.learner.applied_patch))
        w.learner.dir.chmod(0o555)
        try:
            out = self.assertRuns("diff")
        finally:
            w.learner.dir.chmod(0o700)
        self.assertIn("REFERENCE repaired, but its record could not be removed", out)
        self.assertIn("HELLO", w.read("src/greet.sh"), "reversed all the same")
        self.assertIn("DIFF: not captured", out)
        self.assertIn("record cleared", self.assertRuns("diff"), "writable again: the stale record goes")

    def test_a_seam_task_proves_with_a_written_patch(self):
        """No fix: the tutor's own solution, as a patch it wrote with the pen."""
        w = self.w
        w.git("switch", "-q", "main")
        w.git("branch", "-q", "-D", self.branch)
        w.git("switch", "-q", "--detach", w.pre)
        w.write("tests/greet.test.sh", GREET_TEST)
        branch, base = w.begin("greet-politely", "--here", "tests/greet.test.sh")
        w.task(lesson="greet-politely", mode="write", branch=branch, base=base, return_to=w.pre, started="2026-09-16",
               tutor_session="s1", scope="src", verify=["check", "test tests/greet.test.sh"], expect_fail_on_base=["verify test tests/greet.test.sh"])
        self.assertIn("PROOF: ok", self.assertRuns("verify", "--on-base"))
        self.assertIn("no fix: line and no reference patch", self.assertRuns("verify", "--on-reference"))
        self.assertRuns("write", "patch", stdin=w.git("diff", w.pre, w.fix, "--", "src/greet.sh") + "\n")
        out = self.assertRuns("verify", "--on-reference")
        self.assertIn("PROOF: ok (with the reference applied", out)
        self.assertIn("HELLO", w.read("src/greet.sh"))
        self.assertClean()
        self.assertIn("removed reference.patch", self.assertRuns("close-task"))

    def test_proof_on_the_starting_state(self):
        self.w.held_task(self.branch, self.base)
        rep = self.verify(on_base=True)
        self.assertEqual([r.outcome for r in rep.lines], [Outcome.PASS, Outcome.EXPECTED_FAIL])
        self.assertTrue(rep.proof_ok)
        self.assertEqual(rep.revert.status, "reverted")
        self.assertFalse((self.w.top / "tests/greet.test.sh").exists(), "the held test is reverted")
        self.assertClean()
        text = "\n".join(rep.render())
        self.assertIn("PASS     check   (sh check.sh)", text)
        self.assertIn("HELD EXPECTED-FAIL(1) test tests/greet.test.sh", text)
        self.assertIn("expected failures: 1", text)
        self.assertTrue(text.endswith("PROOF: ok (on the starting state, every expected failure failed, everything else passed, every line ran, and the held test was reverted)"))

    def test_held_fails_before_the_work_and_passes_after(self):
        w = self.w
        w.held_task(self.branch, self.base)
        rep = self.verify()
        self.assertEqual(rep.count(Kind.HELD, Outcome.FAIL), 1)
        self.assertIn("expected 'Hello pat', got 'HELLO pat'", rep.lines[1].output)
        self.assertEqual(rep.summary(), "VERIFIER: 1 passed, 0 failed, 0 unknown or rejected; held: 0 passed, 1 failed, reverted")
        # The learner's work, by a different route, with their own test at the held path.
        w.write("src/greet.sh", w.read("src/greet.sh").replace("HELLO", "Hello"))
        w.write("tests/greet.test.sh", "#!/bin/sh\necho 'my own test'\n")
        rep = self.verify()
        self.assertEqual(rep.count(Kind.HELD, Outcome.PASS), 1)
        self.assertEqual(w.sh("tests/greet.test.sh"), "my own test", "the learner's own file is restored")
        self.assertFalse(w.learner.pending.exists())

    def test_report_puts_the_diff_before_the_verifier(self):
        w = self.w
        w.held_task(self.branch, self.base)
        w.write("src/greet.sh", w.read("src/greet.sh").replace("HELLO", "Hello"))
        w.write("tests/notes.txt", "note\n")
        out = self.assertRuns("report")
        self.assertLess(out.index("## The change"), out.index("## Verifier"))
        self.assertIn("-printf 'HELLO %s\\n' \"$1\"", out)
        self.assertIn("tests/notes.txt", out)
        self.assertNotIn("expected 'Hello pat'", out, "the held test is not in the diff")
        self.assertIn("HELD PASS     test tests/greet.test.sh", out)

    def test_arguments_are_words_never_shell(self):
        w = self.w
        w.task(lesson="setup", mode="write", branch=self.branch, base=self.base, return_to=f"main {w.fix}", started="2026-09-15",
               tutor_session="s1", scope="src", verify=["args one two", "args a;b", "args *.sh", "nope x", "fails"])
        rep = self.verify()
        self.assertEqual([r.outcome for r in rep.lines], [Outcome.PASS, Outcome.REJECTED, Outcome.REJECTED, Outcome.UNKNOWN, Outcome.FAIL])
        self.assertEqual(rep.lines[4].rc, 3)
        self.assertEqual(rep.summary(), "VERIFIER: 1 passed, 1 failed, 3 unknown or rejected")

    def test_a_command_that_cannot_take_arguments_never_runs(self):
        w = self.w
        w.add_command("redir", "sh args.sh >")
        w.add_command("hash", "sh args.sh;#x")
        w.write("src/victim.txt", "PRECIOUS\n")
        w.task(lesson="setup", mode="write", branch=self.branch, base=self.base, return_to=f"main {w.fix}", started="2026-09-15",
               tutor_session="s1", scope="src", verify=["redir src/victim.txt", "hash one two"])
        rep = self.verify()
        self.assertEqual([r.outcome for r in rep.lines], [Outcome.REJECTED, Outcome.REJECTED])
        self.assertEqual(w.read("src/victim.txt"), "PRECIOUS\n")

    def test_proof_is_not_ok_for_lines_that_never_ran(self):
        w = self.w
        w.held_task(self.branch, self.base, verify=["check", "nope"])
        self.assertFalse(self.verify(on_base=True).proof_ok)
        w.held_task(self.branch, self.base, held=["../escape.sh"])
        rep = self.verify(on_base=True)
        self.assertFalse(rep.proof_ok)
        self.assertEqual(rep.proof_gaps, ["held-verify test tests/greet.test.sh"])
        self.assertIn("HELD REJECTED ../escape.sh", "\n".join(rep.notes))
        self.assertIn("PROOF GAP: expected to fail but never ran: held-verify test tests/greet.test.sh", rep.render())

    def test_not_run_still_ends_with_a_proof_line(self):
        self.w.learner.task_file.unlink() if self.w.learner.task_file.exists() else None
        out = self.assertRuns("verify", "--on-base")
        self.assertEqual(out.strip().split("\n"), ["VERIFIER: not run (no open task)", "PROOF: not ok (the verifier did not run)"])

    def test_missing_held_copy(self):
        w = self.w
        w.held_task(self.branch, self.base, held=["tests/absent.test.sh"], held_verify=["test tests/absent.test.sh"], expect_fail_on_base=[])
        rep = self.verify()
        self.assertIn("HELD MISSING tests/absent.test.sh   (no copy under held/)", rep.notes)
        self.assertFalse((w.top / "tests/absent.test.sh").exists())


class HeldTestRecoveryTest(WorldTest):
    """What a kill, a failed restore, or a bad path leaves behind, and
    that the next script puts it right."""

    def setUp(self):
        super().setUp()
        self.branch, self.base = self.w.begin("greet-politely", "--fix", self.w.fix, "--held", "tests/greet.test.sh")
        self.w.held_task(self.branch, self.base)

    def leave_killed_state(self, content="learner test 2"):
        """The tree as SIGKILL leaves it mid-run: the learner's file set
        aside, the held copy applied, the record present."""
        w = self.w
        w.write("tests/greet.test.sh", f"#!/bin/sh\necho '{content}'\n")
        (w.learner.aside / "tests").mkdir(parents=True, exist_ok=True)
        os.replace(w.top / "tests/greet.test.sh", w.learner.aside / "tests/greet.test.sh")
        (w.top / "tests/greet.test.sh").write_bytes((w.learner.held / "tests/greet.test.sh").read_bytes())
        w.learner.pending.write_text("aside tests/greet.test.sh\napplied tests/greet.test.sh\n")

    def test_every_script_repairs_first(self):
        w = self.w
        for name in ("diff", "verify", "report"):
            self.leave_killed_state()
            self.assertIn("Hello pat", w.read("tests/greet.test.sh"), "the held test is in the tree before recovery")
            out = self.assertRuns(name)
            self.assertIn("HELD reverted: restored your file at tests/greet.test.sh", out)
            self.assertEqual(w.sh("tests/greet.test.sh"), "learner test 2")
            self.assertFalse(w.learner.pending.exists())
            self.assertFalse(w.learner.aside.exists())
        self.leave_killed_state()
        out = self.assertRuns("end-task")
        self.assertIn("HELD reverted", out)
        self.assertEqual(w.git("log", self.branch, "--format=%H", "-S", "Hello pat", "--", "tests/greet.test.sh"), "", "the held test is in no commit")
        self.assertIn("learner test 2", w.git("show", f"{self.branch}:tests/greet.test.sh"))
        # close-task repairs too, and begin-task refuses only after repairing.
        w.git("switch", "-q", self.branch)
        self.leave_killed_state()
        self.assertIn("HELD reverted", self.assertRuns("close-task"))
        self.assertEqual(w.sh("tests/greet.test.sh"), "learner test 2")

    def test_the_record_is_ordered_removals_then_restores(self):
        w = self.w
        self.leave_killed_state("mine")
        w.learner.pending.write_text("applied tests/greet.test.sh\naside tests/greet.test.sh\n")
        res = heldtest.revert(w.learner, w.top)
        self.assertTrue(res.ok)
        self.assertEqual(w.sh("tests/greet.test.sh"), "mine")

    def test_real_sigkill_mid_held_line(self):
        w = self.w
        started = w.root / "slow-started"
        w.add_command("slow", f"touch {started} && sleep 5")
        w.held_task(self.branch, self.base, held_verify=["slow", "test tests/greet.test.sh"], expect_fail_on_base=[])
        w.write("tests/greet.test.sh", "#!/bin/sh\necho mine\n")
        proc = subprocess.Popen([str(BIN / "rolling-verify")], cwd=str(w.top), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=dict(os.environ))
        for _ in range(200):
            if started.exists():
                break
            time.sleep(0.05)
        proc.kill()
        proc.communicate()
        self.assertIn("Hello pat", w.read("tests/greet.test.sh"), "SIGKILL left the held test in the tree")
        out = self.assertRuns("diff")
        self.assertIn("HELD reverted: restored your file", out)
        self.assertEqual(w.sh("tests/greet.test.sh"), "mine")

    def test_sigterm_reverts_and_stops(self):
        w = self.w
        started = w.root / "slow-started"
        w.add_command("slow", f"touch {started} && sleep 5")
        w.held_task(self.branch, self.base, held_verify=["slow", "test tests/greet.test.sh"], expect_fail_on_base=[])
        w.write("tests/greet.test.sh", "#!/bin/sh\necho mine\n")
        proc = subprocess.Popen([str(BIN / "rolling-verify")], cwd=str(w.top), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=dict(os.environ))
        for _ in range(200):
            if started.exists():
                break
            time.sleep(0.05)
        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=30)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("HELD interrupted; reverting", out)
        self.assertIn("VERIFIER: interrupted", out)
        self.assertNotIn("HELD PASS", out, "no later held line ran against the reverted tree")
        self.assertEqual(w.sh("tests/greet.test.sh"), "mine")
        self.assertFalse(w.learner.pending.exists())

    def test_sigterm_during_a_verify_line(self):
        w = self.w
        started = w.root / "slow-started"
        w.add_command("slow", f"touch {started} && sleep 5")
        w.task(lesson="greet-politely", mode="write", branch=self.branch, base=self.base, return_to=f"main {w.fix}", started="2026-09-15",
               tutor_session="s1", scope="src", verify=["check", "slow"])
        proc = subprocess.Popen([str(BIN / "rolling-verify"), "--on-base"], cwd=str(w.top), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=dict(os.environ))
        for _ in range(200):
            if started.exists():
                break
            time.sleep(0.05)
        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=30)
        self.assertIn("VERIFIER: interrupted", out)
        self.assertIn("PROOF: not ok (interrupted)", out)
        self.assertNotIn("HELD", out)

    @unittest.skipIf(is_root(), "root cannot be locked out of a directory")
    def test_a_failed_restore_keeps_the_learners_file_and_fails_the_proof(self):
        w = self.w
        w.add_command("lockdir", "chmod a-w tests")
        w.held_task(self.branch, self.base, held_verify=["lockdir", "test tests/greet.test.sh"])
        w.write("tests/greet.test.sh", "#!/bin/sh\necho precious\n")
        out = self.assertRuns("verify", "--on-base")
        os.chmod(w.top / "tests", 0o755)
        self.assertIn("HELD REVERT FAILED", out)
        self.assertIn("REVERT FAILED (record kept)", out)
        self.assertIn("PROOF: not ok", out)
        self.assertEqual((w.learner.aside / "tests/greet.test.sh").read_text(), "#!/bin/sh\necho precious\n")
        self.assertTrue(w.learner.pending.exists())
        out = self.assertRuns("diff")
        self.assertIn("HELD reverted: restored your file", out)
        self.assertEqual(w.sh("tests/greet.test.sh"), "precious")
        self.assertFalse(w.learner.pending.exists())

    def test_a_vanished_aside_copy_is_incomplete_not_clean(self):
        w = self.w
        w.add_command("vanish", f"rm -rf {w.learner.aside}")
        w.held_task(self.branch, self.base, held_verify=["vanish", "test tests/greet.test.sh"])
        w.write("tests/greet.test.sh", "#!/bin/sh\necho mine\n")
        out = self.assertRuns("verify", "--on-base")
        self.assertIn("HELD REVERT INCOMPLETE", out)
        self.assertIn("REVERT INCOMPLETE", out)
        self.assertNotIn(", reverted", out)
        self.assertIn("PROOF: not ok", out)
        self.assertFalse(w.learner.pending.exists(), "nothing to retry, so the record is cleared")

    def test_symbolic_links_are_refused(self):
        w = self.w
        w.write("tests/real.sh", "#!/bin/sh\necho real\n")
        os.symlink("real.sh", w.top / "tests/greet.test.sh")
        out = self.assertRuns("verify")
        self.assertIn("HELD REJECTED tests/greet.test.sh   (a symbolic link is in the way", out)
        self.assertEqual(os.readlink(w.top / "tests/greet.test.sh"), "real.sh")
        self.assertFalse(w.learner.pending.exists())
        (w.top / "tests/greet.test.sh").unlink()
        elsewhere = w.root / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "t.sh").write_text("outside\n")
        os.symlink("../elsewhere", w.top / "linked")
        (w.learner.held / "linked").mkdir()
        (w.learner.held / "linked/t.sh").write_bytes((w.learner.held / "tests/greet.test.sh").read_bytes())
        w.held_task(self.branch, self.base, held=["linked/t.sh"], held_verify=["test linked/t.sh"], expect_fail_on_base=[])
        out = self.assertRuns("verify")
        self.assertIn("HELD REJECTED linked/t.sh   (a symbolic link is in the way", out)
        self.assertEqual((elsewhere / "t.sh").read_text(), "outside\n", "nothing written through the link")

    def test_two_paths_that_are_one_file(self):
        w = self.w
        w.write("tests/greet.test.sh", "#!/bin/sh\necho mine\n")
        os.link(w.top / "tests/greet.test.sh", w.top / "tests/hard.test.sh")
        (w.learner.held / "tests/hard.test.sh").write_bytes((w.learner.held / "tests/greet.test.sh").read_bytes())
        w.held_task(self.branch, self.base, held=["tests/greet.test.sh", "tests/hard.test.sh"], expect_fail_on_base=[])
        self.assertRuns("verify")
        self.assertEqual(w.sh("tests/greet.test.sh"), "mine")
        self.assertEqual(w.sh("tests/hard.test.sh"), "mine")
        self.assertFalse(w.learner.pending.exists())
        if (w.top / "Tests").exists():  # a case-folding filesystem; only the macOS CI leg runs this branch
            w.held_task(self.branch, self.base, held=["tests/greet.test.sh", "Tests/greet.test.sh"], expect_fail_on_base=[])
            self.assertIn("the same file as another held path", self.assertRuns("verify"))
            self.assertEqual(w.sh("tests/greet.test.sh"), "mine")

    def test_created_directories_are_removed_deepest_first(self):
        w = self.w
        for rel in ("newtop/shallow.sh", "newtop/sub/deep.sh", "deep/a/b/t.sh"):
            (w.learner.held / rel).parent.mkdir(parents=True, exist_ok=True)
            (w.learner.held / rel).write_bytes((w.learner.held / "tests/greet.test.sh").read_bytes())
        w.held_task(self.branch, self.base, held=["newtop/shallow.sh", "newtop/sub/deep.sh", "deep/a/b/t.sh"], held_verify=["test newtop/shallow.sh"], expect_fail_on_base=[])
        out = self.assertRuns("verify")
        self.assertIn("HELD FAIL(1) test newtop/shallow.sh", out)
        self.assertFalse((w.top / "newtop").exists())
        self.assertFalse((w.top / "deep").exists())

    def test_a_record_with_no_aside_copy_says_so_and_clears(self):
        w = self.w
        w.learner.pending.write_text("aside tests/gone.sh\n")
        out = self.assertRuns("diff")
        self.assertIn("HELD REVERT INCOMPLETE: no set-aside copy of tests/gone.sh", out)
        self.assertFalse(w.learner.pending.exists())

    def test_the_composed_loop(self):
        """begin (held) → edit → report → end: the held test in no diff and
        no commit, the tree as the learner left it, the learner back."""
        w = self.w
        w.write("src/greet.sh", w.read("src/greet.sh").replace("HELLO", "Hello"))
        w.write("tests/greet.test.sh", "#!/bin/sh\necho 'learner test'\n")
        out = self.assertRuns("report")
        self.assertNotIn("Hello pat", out)
        self.assertIn("HELD PASS", out)
        self.assertRuns("end-task")
        self.assertOnBranch("main")
        self.assertEqual(w.git("log", self.branch, "--format=%H", "-S", "Hello pat", "--", "tests/greet.test.sh"), "")
        self.assertIn("learner test", w.git("show", f"{self.branch}:tests/greet.test.sh"))
        self.assertClean()


if __name__ == "__main__":
    unittest.main()
