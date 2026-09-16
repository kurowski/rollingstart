"""The write-mode scope guard, driven with hand-built hook events, the
way Claude Code drives it: JSON on stdin, the data directory as the
argument, a denial as JSON on stdout, silence otherwise, exit 0 always."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from unittest import mock

from support import WorldTest

from rolling import guard


class GuardTest(WorldTest):
    def setUp(self):
        super().setUp()
        self.w.task(lesson="greet-politely", mode="write", branch="b", base=self.w.fix, return_to=f"main {self.w.fix}",
                    started="2026-09-15", tutor_session="tutor-1", scope=["src/greet.sh", "tests"],
                    scaffold=["tests/greet.test.sh"], verify="check")

    def event(self, path, session="tutor-1", tool="Edit", cwd=None, **extra):
        ev = {"hook_event_name": "PreToolUse", "session_id": session, "cwd": str(cwd or self.w.top),
              "tool_name": tool, "tool_input": {"file_path": path}}
        ev.update(extra)
        return json.dumps(ev)

    def run_guard(self, stdin, data=None):
        rc, out = self.w.run("guard", str(self.w.data) if data is None else data, stdin=stdin)
        self.assertEqual(rc, 0)
        return json.loads(out)["hookSpecificOutput"] if out.strip() else None

    def test_denies_inside_scope_with_a_reason(self):
        d = self.run_guard(self.event(str(self.w.top / "src/greet.sh")))
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("src/greet.sh is the learner's to write in this lesson (it is under src/greet.sh)", d["permissionDecisionReason"])
        self.assertIn("TODO(human)", d["permissionDecisionReason"])
        self.assertEqual(d["hookEventName"], "PreToolUse")

    def test_directory_scope_and_relative_paths(self):
        self.assertEqual(self.run_guard(self.event("tests/other.test.sh"))["permissionDecision"], "deny")
        self.assertEqual(self.run_guard(self.event("tests/deep/x.sh"))["permissionDecision"], "deny")
        sub = self.w.top / "src"
        self.assertEqual(self.run_guard(self.event("greet.sh", cwd=sub))["permissionDecision"], "deny", "relative to a subdirectory cwd")
        self.assertEqual(self.run_guard(self.event("../src/greet.sh", cwd=sub))["permissionDecision"], "deny")

    def test_allows_scaffold_and_outside(self):
        self.assertIsNone(self.run_guard(self.event("tests/greet.test.sh")), "a scaffold path is allowed")
        self.assertIsNone(self.run_guard(self.event("check.sh")))
        self.assertIsNone(self.run_guard(self.event(str(self.w.root / "elsewhere.txt"))), "outside the repository")
        self.assertIsNone(self.run_guard(self.event("src/greet.sh.bak")), "a scope names a file, not a prefix")

    def test_allows_other_sessions_modes_and_no_task(self):
        self.assertIsNone(self.run_guard(self.event("src/greet.sh", session="coder-2")), "another session is the learner's")
        self.assertIsNone(self.run_guard(self.event("src/greet.sh", session="")))
        self.w.task(lesson="greet-politely", mode="direct", tutor_session="tutor-1", scope="src", verify="check",
                    body="## Situation\n\nx\n\n## Source\n\ny\n")
        self.assertIsNone(self.run_guard(self.event("src/greet.sh")), "a direct task does not guard")
        self.w.learner.task_file.unlink()
        self.assertIsNone(self.run_guard(self.event("src/greet.sh")), "no task")

    def test_every_tool_and_the_notebook_path(self):
        for tool in ("Edit", "Write", "MultiEdit"):
            self.assertEqual(self.run_guard(self.event("src/greet.sh", tool=tool))["permissionDecision"], "deny", tool)
        ev = json.loads(self.event("x", tool="NotebookEdit"))
        ev["tool_input"] = {"notebook_path": str(self.w.top / "tests/nb.ipynb")}
        self.assertEqual(self.run_guard(json.dumps(ev))["permissionDecision"], "deny")

    def test_never_blocks_on_its_own_trouble(self):
        for stdin in ("", "not json", "[]", '{"tool_input": "x"}', '{"tool_input": {}}', '{"tool_input": {"file_path": ""}}'):
            self.assertIsNone(self.run_guard(stdin), repr(stdin))
        self.assertIsNone(self.run_guard(self.event("src/greet.sh"), data=""), "no data directory")
        self.assertIsNone(self.run_guard(self.event("src/greet.sh"), data=str(self.w.root / "nowhere")))
        self.w.learner.task_file.write_text("garbage")
        self.assertIsNone(self.run_guard(self.event("src/greet.sh")), "an unreadable task")
        self.assertIsNone(self.run_guard(self.event("src/greet.sh", cwd=self.w.root)), "not inside a repository")

    def test_glob_scopes(self):
        self.w.task(lesson="greet-politely", mode="write", tutor_session="tutor-1", scope=["src/*.sh", "docs/**"], verify="check")
        self.assertEqual(self.run_guard(self.event("src/greet.sh"))["permissionDecision"], "deny")
        self.assertIsNone(self.run_guard(self.event("src/deep/x.sh")), "a single * stays within a segment")
        self.assertEqual(self.run_guard(self.event("docs/a/b/c.md"))["permissionDecision"], "deny")

    def test_symlinked_checkout_and_links(self):
        w = self.w
        link = w.root / "via-link"
        os.symlink(w.top, link)
        self.assertEqual(self.run_guard(self.event(str(link / "src/greet.sh")))["permissionDecision"], "deny", "the repo reached through a link, absolute path")
        self.assertEqual(self.run_guard(self.event("src/greet.sh", cwd=link))["permissionDecision"], "deny", "the repo reached through a link, as cwd")
        os.symlink("src/greet.sh", w.top / "alias.sh")
        self.assertEqual(self.run_guard(self.event("alias.sh"))["permissionDecision"], "deny", "a link outside the scope pointing in")
        os.symlink("src", w.top / "srclink")
        self.assertEqual(self.run_guard(self.event("srclink/greet.sh"))["permissionDecision"], "deny", "a linked directory pointing in")
        w.task(lesson="greet-politely", mode="write", tutor_session="tutor-1", scope="src", verify="check")
        (w.root / "outside.sh").write_text("o")
        os.symlink(w.root / "outside.sh", w.top / "src/escape.sh")
        self.assertEqual(self.run_guard(self.event("src/escape.sh"))["permissionDecision"], "deny", "a link inside the scope pointing out: the scope names paths")

    def test_a_task_with_no_session_or_odd_scopes(self):
        w = self.w
        w.task(lesson="greet-politely", mode="write", scope="src", verify="check")
        self.assertIsNone(self.run_guard(self.event("src/greet.sh")), "no tutor-session line")
        w.task(lesson="greet-politely", mode="write", tutor_session="tutor-1", scope=["./src/", "/etc", "..", "."], verify="check")
        self.assertEqual(self.run_guard(self.event("src/greet.sh"))["permissionDecision"], "deny", "./src/ normalises to src")
        self.assertIsNone(self.run_guard(self.event("README.md")), "/etc, .., and . guard nothing")

    def test_another_repository_is_not_this_task(self):
        other = self.w.root / "other"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        (other / "src").mkdir()
        self.assertIsNone(self.run_guard(self.event(str(other / "src/greet.sh"), cwd=other)))

    def test_tool_name_matters(self):
        self.assertIsNone(self.run_guard(self.event("src/greet.sh", tool="Read")))
        self.assertIsNone(self.run_guard(self.event("src/greet.sh", tool="")))

    def test_the_repository_comes_from_the_path_not_the_cwd(self):
        w = self.w
        inside = str(w.top / "src/greet.sh")
        self.assertEqual(self.run_guard(self.event(inside, cwd=w.root))["permissionDecision"], "deny", "cwd outside any repository")
        nested = w.top / "vendor/lib"
        nested.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(nested)], check=True)
        self.assertEqual(self.run_guard(self.event(inside, cwd=nested))["permissionDecision"], "deny", "cwd in a nested repository")
        self.assertEqual(self.run_guard(self.event("../../src/greet.sh", cwd=nested))["permissionDecision"], "deny")
        w.task(lesson="greet-politely", mode="write", tutor_session="tutor-1", scope="src", verify="check")
        pocket = w.top / "src/pocket"
        pocket.mkdir()
        subprocess.run(["git", "init", "-q", str(pocket)], check=True)
        self.assertEqual(self.run_guard(self.event("new.sh", cwd=pocket))["permissionDecision"], "deny", "a repository made inside the scope")

    def test_case_folding_is_judged_at_the_top(self):
        w = self.w
        w.task(lesson="greet-politely", mode="write", tutor_session="tutor-1", scope="src", verify="check")
        folding = guard.folds_case(w.top)
        if folding:   # a Mac's default volume: the other case is the same file, and the top can be spelled either way
            self.assertEqual(self.run_guard(self.event("SRC/greet.sh"))["permissionDecision"], "deny")
            odd = w.top.parent / w.top.name.swapcase() / "src/greet.sh"
            self.assertEqual(self.run_guard(self.event(str(odd)))["permissionDecision"], "deny", "the top spelled in another case")
        else:
            self.assertIsNone(self.run_guard(self.event("SRC/greet.sh")), "a case-sensitive filesystem: another path")
            (w.top / ".GIT").mkdir()
            self.assertIsNone(self.run_guard(self.event("SRC/greet.sh")), "a decoy .GIT directory is not the same entry")
        # The folding branches themselves, on any filesystem: the learner
        # directory keyed by git's spelling, the top spelled in another.
        enc = w.learner.dir.name
        swapped = w.learner.dir.parent / enc.swapcase()
        shutil.move(str(w.learner.dir), str(swapped))
        ev = guard.parse_event(self.event("src/greet.sh"))
        with mock.patch.object(guard, "folds_case", return_value=False):
            self.assertIsNone(guard.decide(ev, str(w.data)))
        with mock.patch.object(guard, "folds_case", return_value=True):
            self.assertIsNotNone(guard.decide(ev, str(w.data)))
            self.assertIsNotNone(guard.decide(guard.parse_event(self.event("SRC/Greet.sh")), str(w.data)))
            w.task(lesson="greet-politely", mode="write", tutor_session="tutor-1", scope="tests", scaffold="tests/greet.test.sh", verify="check")
            if swapped.exists() and not swapped.samefile(w.learner.dir):   # case-sensitive: the stale copy would swallow the move
                shutil.rmtree(str(swapped))
                shutil.move(str(w.learner.dir), str(swapped))
            self.assertIsNone(guard.decide(guard.parse_event(self.event("tests/GREET.test.sh")), str(w.data)), "a scaffold folds too")

    def test_a_doubled_leading_slash(self):
        w = self.w
        w.task(lesson="greet-politely", mode="write", tutor_session="tutor-1", scope="src", verify="check")
        (w.root / "outside.sh").write_text("o")
        os.symlink(w.root / "outside.sh", w.top / "src/escape.sh")
        self.assertEqual(self.run_guard(self.event("/" + str(w.top / "src/escape.sh")))["permissionDecision"], "deny")
        self.assertEqual(guard.spellings("//" + str(w.top / "x"), w.top), [w.top / "x"])

    def test_a_scaffold_names_files_exactly(self):
        w = self.w
        w.task(lesson="greet-politely", mode="write", tutor_session="tutor-1", scope="tests", scaffold="tests", verify="check")
        self.assertEqual(self.run_guard(self.event("tests/x.sh"))["permissionDecision"], "deny", "a directory scaffold exempts nothing beneath it")
        w.task(lesson="greet-politely", mode="write", tutor_session="tutor-1", scope="tests", scaffold=["tests/*.sh", "tests/new/**"], verify="check")
        self.assertIsNone(self.run_guard(self.event("tests/x.sh")))
        self.assertIsNone(self.run_guard(self.event("tests/new/a/b.sh")))
        self.assertEqual(self.run_guard(self.event("tests/deep/x.sh"))["permissionDecision"], "deny")

    def test_a_newline_in_the_path(self):
        self.assertIsNone(self.run_guard(self.event("src/greet.sh\nx")), "another file than the one the scope names")
        self.w.task(lesson="greet-politely", mode="write", tutor_session="tutor-1", scope="src", verify="check")
        self.assertEqual(self.run_guard(self.event("src/a\nb.sh"))["permissionDecision"], "deny")

    def test_decide_directly(self):
        ev = guard.parse_event(self.event("src/greet.sh"))
        self.assertIsNotNone(guard.decide(ev, str(self.w.data)))
        self.assertIsNone(guard.decide(ev, ""))
        self.assertEqual(guard.spellings("a/../b", self.w.top), [self.w.top / "b"])
        ps = list(guard.placements(ev, self.w.data))
        self.assertEqual([(p.top, p.rel) for p in ps], [(self.w.top, "src/greet.sh")])


if __name__ == "__main__":
    unittest.main()
