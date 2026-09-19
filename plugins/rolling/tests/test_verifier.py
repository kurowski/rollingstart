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

from rolling import heldtest, reference
from rolling.model import Map, Task
from rolling.verifier import Kind, LineResult, Outcome, Report, Verifier


class VerifierTest(WorldTest):
    def setUp(self):
        super().setUp()
        self.branch, self.base = self.w.begin("greet-politely", "--fix", self.w.fix, "--held", "tests/greet.test.sh")

    def verify(self, on_base=False, on_reference=False):
        w = self.w
        return Verifier(w.top, w.learner, Map.load(w.top / ".rolling"), Task.load(w.learner.task_file), on_base=on_base, on_reference=on_reference).run()

    def test_a_fix_touching_odd_names_is_whole_in_the_reference(self):
        """git quotes some names in a listing; the reference is built from
        real names, so a quoted file is in the patch, and a held file the
        fix also touched, whose name a bracketed sibling would match as a
        glob, stays out of it."""
        w = self.w
        w.git("switch", "-q", "main")
        w.git("branch", "-q", "-D", self.branch)
        w.write('src/a"b.sh', "#!/bin/sh\necho one\n")
        w.write("app/[id].tsx", "export {}\n")
        w.write("app/i.tsx", "export {}\n")
        w.git("add", "-A")
        w.git("commit", "-q", "-m", "odd names")
        w.write('src/a"b.sh', "#!/bin/sh\necho two\n")
        w.write("app/[id].tsx", "export {}; // two\n")
        w.write("app/i.tsx", "export {}; // HELD_ANSWER\n")
        w.git("add", "-A")
        w.git("commit", "-q", "-m", "fix touching odd names")
        odd_fix = w.git("rev-parse", "HEAD")
        branch, base = w.begin("greet-politely", "--fix", odd_fix, "--held", "app/i.tsx")
        w.task(lesson="greet-politely", mode="write", branch=branch, base=base, return_to=f"main {odd_fix}", started="2026-09-16",
               tutor_session="s1", scope="src", fix=odd_fix, verify=["check"], held="app/i.tsx")
        text = reference.patch_for(w.repo, w.learner, Task.load(w.learner.task_file)).decode()
        self.assertIn('a/src/a\\"b.sh', text, "the quoted name is in the patch")
        self.assertIn("app/[id].tsx", text)
        self.assertNotIn("HELD_ANSWER", text, "the held file the bracket would match as a glob is not in the reference")
        self.assertIn("PROOF: ok", self.assertRuns("verify", "--on-reference"))
        self.assertClean()

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

    def test_a_mode_entry_that_landed_alone_keeps_the_record(self):
        """A patch with a mode change and a content hunk, of which only
        the mode landed: it re-applies forward (a mode entry does, whatever
        the mode is) and does not reverse, which used to read as "not in
        the tree"; the dirty named path keeps the record instead."""
        w = self.w
        w.held_task(self.branch, self.base)
        patch = ("diff --git a/check.sh b/check.sh\nold mode 100644\nnew mode 100755\n"
                 + w.git("diff", "--binary", "HEAD", w.fix, "--", "src/greet.sh") + "\n")
        w.learner.applied_patch.write_text(patch)
        w.learner.applied_at.write_text(w.git("rev-parse", "HEAD") + "\n")
        (w.top / "check.sh").chmod(0o755)   # the mode landed, the content did not
        self.assertEqual(w.git("status", "--porcelain").split(), ["M", "check.sh"])
        out = self.assertRuns("diff")
        self.assertIn("REFERENCE record kept", out)
        self.assertIn("check.sh changed since it went in", out)
        self.assertIn("DIFF: not captured", out)
        self.assertNotIn("record cleared", out)
        self.assertTrue(w.learner.applied_patch.exists(), "the record stays while a named path is dirty")
        (w.top / "check.sh").chmod(0o644)
        self.assertIn("record cleared", self.assertRuns("diff"))
        self.assertClean()

    def test_patch_paths_name_a_rename_by_its_new_name(self):
        """`git apply --numstat -z` lists one record per entry, a rename
        under its new name; not `git diff --numstat -z`'s two-name form."""
        w = self.w
        w.git("mv", "src/greet.sh", "src/hello.sh")
        w.write("src/hello.sh", w.read("src/hello.sh") + "# moved\n")
        w.write("src/new.sh", "#!/bin/sh\n")
        w.git("add", "-A")
        patch = w.git("diff", "--cached", "-M", "--binary") + "\n"
        w.git("reset", "-q", "--hard")
        w.learner.dir.mkdir(parents=True, exist_ok=True)
        w.learner.applied_patch.write_text(patch)
        self.assertIn("rename from src/greet.sh", patch)
        self.assertEqual(reference._patch_paths(w.repo, w.learner.applied_patch), ["src/hello.sh", "src/new.sh"])
        w.learner.applied_patch.write_text("not a patch\n")
        self.assertEqual(reference._patch_paths(w.repo, w.learner.applied_patch), [])
        w.learner.applied_patch.unlink()

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
    def test_a_refused_from_tree_leaves_no_intent_to_add(self):
        w = self.w
        w.write("src/helper.sh", "#!/bin/sh\n")
        w.learner.dir.chmod(0o555)
        try:
            self.assertIn("cannot be written", self.assertRuns("write", "patch", "--from-tree", "src/helper.sh", status=1))
        finally:
            w.learner.dir.chmod(0o700)
        self.assertEqual(w.git("status", "--porcelain").split(), ["??", "src/helper.sh"], "untracked, as before")
        (w.top / "src/helper.sh").unlink()

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

    def test_a_seam_task_proves_with_a_patch_taken_from_the_tree(self):
        """The tutor tried its solution in the tree; the pen takes the diff
        as the patch and restores the tree, and the proof then runs."""
        w = self.w
        w.git("switch", "-q", "main")
        w.git("branch", "-q", "-D", self.branch)
        w.git("switch", "-q", "--detach", w.pre)
        self.assertIn("nothing to take", self.assertRuns("write", "patch", "--from-tree", "src/greet.sh", status=1))
        self.assertIn("needs the paths", self.assertRuns("write", "patch", "--from-tree", status=1))
        self.assertIn("not a plain repository-relative path", self.assertRuns("write", "patch", "--from-tree", "../x", status=1))
        for magic in (":!src/greet.sh", "src/*", "src/gree?.sh", ":(top)src/greet.sh"):
            self.assertIn("no glob, no pathspec magic", self.assertRuns("write", "patch", "--from-tree", magic, status=1), magic)
        self.assertIn("name the files", self.assertRuns("write", "patch", "--from-tree", "src", status=1))
        self.assertIn("neither in HEAD nor in the tree", self.assertRuns("write", "patch", "--from-tree", "src/absent.sh", status=1))
        self.assertIn("spelled:", self.assertRuns("write", "patch", "--from-tree=src/greet.sh", status=1))
        self.assertIn("listed twice", self.assertRuns("write", "patch", "--from-tree", "src/greet.sh", "src/greet.sh", status=1))
        self.assertFalse(w.learner.patch.exists(), "nothing written by any refusal")
        # Names git quotes in a listing, and names with a bracket, are files like any other.
        w.write('src/a"b.sh', "#!/bin/sh\necho quoted\n")
        w.write("app/[urlId].tsx", "export {}\n")
        w.git("add", "-A")
        w.git("commit", "-q", "-m", "odd names")
        w.write('src/a"b.sh', "#!/bin/sh\necho changed\n")
        w.write("app/[urlId].tsx", "export {}; // changed\n")
        out = self.assertRuns("write", "patch", "--from-tree", 'src/a"b.sh', "app/[urlId].tsx")
        self.assertIn("2 files changed", out)
        self.assertTrue((w.top / 'src/a"b.sh').is_file(), "a tracked file with a quoted name is restored, never deleted")
        self.assertTrue((w.top / "app/[urlId].tsx").is_file())
        self.assertClean()
        w.git("reset", "-q", "--hard", "HEAD^")
        # The test that specifies the seam, then the solution: a change to a tracked file and a new file; the learner's own unnamed change stays.
        w.write("tests/greet.test.sh", GREET_TEST)
        w.write("src/greet.sh", w.read("src/greet.sh").replace("HELLO", "Hello"))
        w.write("src/helper.sh", "#!/bin/sh\n# a new module\n")
        w.write("check.sh", w.read("check.sh") + "# the learner's own change, unnamed\n")
        out = self.assertRuns("write", "patch", "--from-tree", "src/greet.sh", "src/helper.sh")
        self.assertIn("wrote reference.patch from the tree", out)
        self.assertIn("2 files changed", out)
        self.assertIn("new files removed", out)
        self.assertIn("HELLO", w.read("src/greet.sh"), "the solution is out of the tree")
        self.assertFalse((w.top / "src/helper.sh").exists())
        self.assertIn("new file mode", w.learner.patch.read_text())
        self.assertNotIn("src/helper.sh", w.git("ls-files", "--stage"), "no intent-to-add entry lingers")
        self.assertEqual(w.git("status", "--porcelain", "-uall").split(), ["M", "check.sh", "??", "tests/greet.test.sh"], "the unnamed change and the test are left alone")
        w.git("checkout", "--", "check.sh")
        # Then the task begins, from the test alone, and the proof runs on its branch.
        branch, base = w.begin("greet-politely", "--here", "tests/greet.test.sh")
        w.task(lesson="greet-politely", mode="write", branch=branch, base=base, return_to=w.pre, started="2026-09-16",
               tutor_session="s1", scope="src", verify=["check", "test tests/greet.test.sh"], expect_fail_on_base=["verify test tests/greet.test.sh"])
        self.assertIn("PROOF: ok (with the reference applied", self.assertRuns("verify", "--on-reference"))
        self.assertFalse((w.top / "src/helper.sh").exists(), "the new file went in and came out with the patch")
        self.assertClean()
        # With the task open the pen refuses to take from the tree: those paths may hold the learner's work.
        w.write("src/greet.sh", w.read("src/greet.sh") + "# the learner's work\n")
        out = self.assertRuns("write", "patch", "--from-tree", "src/greet.sh", status=1)
        self.assertIn("a task is open (greet-politely)", out)
        self.assertIn("the learner's work", w.read("src/greet.sh"), "nothing restored")
        self.assertIn("new file mode", w.learner.patch.read_text(), "the reference patch is as it was")
        w.git("checkout", "--", "src/greet.sh")
        w.learner.task_file.unlink()
        # A new file in a new directory: the file goes, the directory stays (it may be the learner's); an ignored sibling refuses and leaves both untracked.
        w.write("lib/deep/new.sh", "#!/bin/sh\n")
        w.write(".gitignore", "*.log\n")
        w.git("add", ".gitignore")
        w.git("commit", "-q", "-m", "ignore logs")
        w.write("lib/out.log", "x\n")
        self.assertRuns("write", "patch", "--from-tree", "lib/deep/new.sh", "lib/out.log", status=1)
        self.assertNotIn("lib/", w.git("ls-files", "--stage"), "a failed intent-to-add leaves nothing in the index")
        self.assertIn("?? lib/deep/new.sh", w.git("status", "--porcelain", "-uall"))
        (w.top / "lib/out.log").unlink()
        if not is_root():   # root writes anywhere, so the refusal cannot be provoked
            w.git("add", "lib/deep/new.sh")
            w.learner.dir.chmod(0o555)
            try:
                self.assertRuns("write", "patch", "--from-tree", "lib/deep/new.sh", status=1)
            finally:
                w.learner.dir.chmod(0o700)
            self.assertEqual(w.git("diff", "--cached", "--name-only"), "lib/deep/new.sh", "a file the tutor had staged stays staged after a refusal")
            w.git("reset", "-q", "--", "lib/deep/new.sh")
        self.assertRuns("write", "patch", "--from-tree", "lib/deep/new.sh")
        self.assertFalse((w.top / "lib/deep/new.sh").exists())
        self.assertTrue((w.top / "lib/deep").is_dir(), "the directory stays: git shows no empty directory, and it may be the learner's own")
        self.assertClean()
        w.git("reset", "-q", "--hard", "HEAD^")

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

    def test_the_on_base_proof_needs_an_expected_failure(self):
        """A task with no expect-fail-on-base line proves nothing: its
        checks pass before the work is done. The script says so; the
        skill's prose is not the only thing holding it."""
        w = self.w
        w.held_task(self.branch, self.base, expect_fail_on_base=[])
        rep = self.verify(on_base=True)
        self.assertFalse(rep.proof_ok)
        self.assertTrue(rep.nothing_expected)
        text = "\n".join(rep.render())
        self.assertIn("PROOF GAP: no expect-fail-on-base line", text)
        self.assertTrue(text.endswith("do not serve this task)"))
        self.assertClean()
        self.assertFalse(self.verify(on_reference=True).nothing_expected, "the forward half asks nothing of it")

    @unittest.skipIf(is_root(), "root writes anywhere")
    def test_a_write_that_fails_part_way_through_apply_keeps_the_record(self):
        """`git apply --check` passes and then a write fails (a read-only
        directory inside the scope): part of the reference may be in the
        tree, so the record stays and every command refuses, loudly,
        rather than the tutor's answer reading as the learner's work."""
        w = self.w
        w.git("switch", "-q", "main")
        w.git("branch", "-q", "-D", self.branch)
        w.git("switch", "-q", "--detach", w.pre)
        # A solution in two files, the second in a directory that will refuse the write.
        w.write("src/greet.sh", w.read("src/greet.sh").replace("HELLO", "Hello"))
        w.write("zro/c.txt", "c\n")
        self.assertRuns("write", "patch", "--from-tree", "src/greet.sh", "zro/c.txt")
        self.assertTrue((w.top / "zro").is_dir())
        w.write("tests/greet.test.sh", GREET_TEST)
        branch, base = w.begin("greet-politely", "--here", "tests/greet.test.sh")
        w.task(lesson="greet-politely", mode="write", branch=branch, base=base, return_to=w.pre, started="2026-09-16",
               tutor_session="s1", scope="src", verify=["check"], expect_fail_on_base=["verify check"])
        (w.top / "zro").chmod(0o555)
        try:
            out = self.assertRuns("verify", "--on-reference")
        finally:
            (w.top / "zro").chmod(0o755)
        self.assertIn("could not be written into the tree", out)
        self.assertIn("PROOF: not ok", out)
        if w.git("status", "--porcelain"):   # git wrote the first file before failing on the second
            self.assertTrue(w.learner.applied_patch.exists(), "the record is kept while the tree holds part of the reference")
            self.assertIn("part of it is: src/greet.sh", out)
            self.assertIn("record is kept", out)
            self.assertIn("REFERENCE STILL APPLIED", self.assertRuns("diff"))
        else:   # nothing landed: the record is gone and the message says so
            self.assertFalse(w.learner.applied_patch.exists())
            self.assertIn("nothing of it is there", out)
        # Never does the reference sit in the tree with no record of it.
        self.assertFalse(w.git("status", "--porcelain") and not w.learner.applied_patch.exists(), "a dirty tree with no record would read as the learner's work")

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


class ReportTest(unittest.TestCase):
    def test_a_report_that_stops_mid_run_still_shows_what_ran(self):
        rep = Report(on_base=False, on_reference=True)
        rep.lines.append(LineResult(Kind.VERIFY, "check", Outcome.PASS, command="sh check.sh"))
        rep.notes.append("a note from the run")
        rep.not_run = "git failed after the first line"
        text = rep.render()
        self.assertEqual(text[-2:], ["VERIFIER: not run (git failed after the first line)", "PROOF: not ok (the verifier did not run)"])
        self.assertIn("PASS     check   (sh check.sh)", text)
        self.assertIn("a note from the run", text)


if __name__ == "__main__":
    unittest.main()
