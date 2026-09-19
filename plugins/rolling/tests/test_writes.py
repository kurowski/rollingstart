"""The tutor's pen: rolling-write, rolling-note, rolling-keep-task, driven
the way a skill drives them, text on standard input."""

from __future__ import annotations

import time
import unittest

from support import WorldTest, is_root

TASK = """---
lesson: greet-politely
mode: write
branch: b
base: {base}
return-to: main {base}
started: 2026-09-16
scope: src/greet.sh
verify: check
---

## Brief

Fix the shout.

## Source

The fix.
"""

PROFILE = """# Profile

## Background
Fluent in sh.

## Destination
{region}: working

## Why
Because.

## Satisfied
"""


class WriteTest(WorldTest):
    def test_task_is_checked_stamped_and_written(self):
        w = self.w
        self.assertRuns("claim-session", "tutor-9")
        out = self.assertRuns("write", "task", stdin=TASK.format(base=w.fix))
        self.assertIn("wrote task.md", out)
        text = w.learner.task_file.read_text()
        self.assertIn("tutor-session: tutor-9", text, "stamped from the session file the inline claim wrote")
        self.assertEqual(w.learner.task().scope, ["src/greet.sh"])
        self.assertFalse((w.learner.dir / ".task.md.new").exists())

    def test_the_session_line_is_never_the_models(self):
        """The guard keys on tutor-session; a line the model typed is
        dropped and the recorded id stamped, and with none recorded the
        write is refused in words."""
        w = self.w
        text = TASK.format(base=w.fix).replace("started:", "tutor-session: not-this-session\nstarted:")
        out = self.assertRuns("write", "task", stdin=text, status=1)
        self.assertIn("session is not recorded", out)
        self.assertFalse(w.learner.has_task())
        w.learner.dir.mkdir(parents=True, exist_ok=True)
        w.learner.session.write_text("$(touch pwn)\n")
        self.assertIn("session is not recorded", self.assertRuns("write", "task", stdin=text, status=1))
        self.assertRuns("claim-session", "tutor-9")
        self.assertRuns("write", "task", stdin=text)
        self.assertEqual(w.learner.task().tutor_session, "tutor-9")
        self.assertEqual(w.learner.task_file.read_text().count("tutor-session:"), 1)
        # While a task is open its own line is the fresh one, whatever session says
        w.learner.session.write_text("stale-1\n")
        self.assertRuns("write", "task", stdin=text)
        self.assertEqual(w.learner.task().tutor_session, "tutor-9")

    def test_a_malformed_task_is_refused_and_nothing_lands(self):
        w = self.w
        self.assertRuns("claim-session", "tutor-9")
        bad = TASK.format(base=w.fix).replace("verify: check", "verify: nonesuch")
        out = self.assertRuns("write", "task", stdin=bad, status=1)
        self.assertIn("nonesuch", out)
        self.assertIn("task.md not written", out)
        self.assertIn(str(w.learner.task_file), out, "faults name the destination, not the temporary file")
        self.assertFalse(w.learner.has_task())
        self.assertFalse((w.learner.dir / ".task.md.new").exists())
        w.task(lesson="greet-politely", mode="write", scope="src", verify="check")
        self.assertRuns("write", "task", stdin=bad, status=1)
        self.assertEqual(w.learner.task().scope, ["src"], "a refused rewrite leaves the open task as it was")

    def test_profile_reference_and_refusals(self):
        w = self.w
        out = self.assertRuns("write", "profile", stdin=PROFILE.format(region="greeting"))
        self.assertIn("wrote profile.md", out)
        out = self.assertRuns("write", "profile", stdin=PROFILE.format(region="nowhere"))
        self.assertIn("wrote profile.md", out)
        self.assertIn("nowhere", out, "an unknown region is a warning, printed")
        self.assertRuns("write", "profile", stdin="# Profile\n\n## Background\nx\n", status=1)
        self.assertRuns("write", "reference", stdin="af3d9273: ten lines in participants.ts\n")
        self.assertEqual(w.learner.reference.read_text(), "af3d9273: ten lines in participants.ts\n")
        self.assertIn("one of task, profile, reference", self.assertRuns("write", "evidence", stdin="x", status=1))
        self.assertIn("one of task, profile, reference", self.assertRuns("write", "../x", stdin="x", status=1))
        self.assertIn("nothing to write", self.assertRuns("write", "reference", stdin="", status=1))

    @unittest.skipIf(is_root(), "root writes anywhere")
    def test_an_unwritable_directory_is_refused_in_words(self):
        w = self.w
        w.learner.dir.mkdir(parents=True, exist_ok=True)
        w.learner.dir.chmod(0o500)
        try:
            self.assertIn("cannot be written", self.assertRuns("write", "reference", stdin="x", status=1))
        finally:
            w.learner.dir.chmod(0o700)


class NoteTest(WorldTest):
    def test_entries_append_under_a_date(self):
        w = self.w
        today = time.strftime("%Y-%m-%d")
        out = self.assertRuns("note", "greet-politely", stdin="**Route.** polls at working; nothing else reachable.\n")
        self.assertIn("noted in evidence/greet-politely.md (Route)", out)
        self.assertRuns("note", "greet-politely", stdin="**Observation.** ran the same failing test three times.")
        text = (w.learner.evidence / "greet-politely.md").read_text()
        self.assertEqual(text, f"## {today}\n\n**Route.** polls at working; nothing else reachable.\n\n## {today}\n\n**Observation.** ran the same failing test three times.\n")
        (w.learner.evidence / "greet-politely.md").write_text(text + "\n\n\n")
        self.assertRuns("note", "greet-politely", stdin="**Feedback.** x")
        self.assertIn("three times.\n\n## ", (w.learner.evidence / "greet-politely.md").read_text(), "one blank line, whatever the file ended with")

    def test_a_link_in_the_evidence_dir_is_refused(self):
        w = self.w
        w.learner.evidence.mkdir(parents=True)
        (w.learner.evidence / "greet-politely.md").symlink_to(w.top / "README.md")
        self.assertIn("symbolic link", self.assertRuns("note", "greet-politely", stdin="**Route.** y", status=1))
        self.assertFalse((w.top / "README.md").exists())

    def test_kind_and_slug_are_required(self):
        self.assertIn("opens with its kind", self.assertRuns("note", "greet-politely", stdin="chose it because\n", status=1))
        self.assertIn("not a lesson slug", self.assertRuns("note", "../x", stdin="**Route.** y", status=1))
        self.assertIn("nothing to note", self.assertRuns("note", "greet-politely", stdin="  \n", status=1))
        self.assertFalse(self.w.learner.evidence.exists())


class KeepTaskTest(WorldTest):
    def test_kept_copy_drops_the_run_lines(self):
        w = self.w
        w.held_task("b", w.fix)
        out = self.assertRuns("keep-task")
        self.assertIn("kept as tasks/greet-politely/", out)
        kept = next((w.learner.tasks / "greet-politely").iterdir()).read_text()
        keys = [l.split(":", 1)[0] for l in kept.split("\n---")[0].split("\n")]
        for key in ("branch", "base", "return-to", "started", "tutor-session"):
            self.assertNotIn(key, keys)
        self.assertIn("expect-fail-on-base", keys)
        self.assertIn("fix: " + w.fix, kept)
        self.assertIn("held-verify: test tests/greet.test.sh", kept)
        self.assertIn("## Brief", kept)
        self.assertRuns("close-task")
        self.assertIn("no open task", self.assertRuns("keep-task", status=1))
        w.task(lesson="../../escaped", mode="write", scope="src", verify="check")
        self.assertIn("not a slug", self.assertRuns("keep-task", status=1))
        self.assertFalse((w.root / "escaped").exists())


if __name__ == "__main__":
    unittest.main()
