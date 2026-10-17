"""The exclude block: the ignore rules of the branch a task returns to,
carried into .git/info/exclude for the task's lifetime. The translation
of a nested pattern is pure, so it is tested on its own; the block's
lifecycle is tested against the scratch world's real repository."""

from __future__ import annotations

import unittest

from support import WorldTest, is_root

from rolling import excludes
from rolling.repo import Repo


class TranslateTest(unittest.TestCase):
    """A pattern in a nested .gitignore means what it means where it
    lives; info/exclude is read from the top, so the nesting has to be
    written into the pattern."""

    def test_a_root_pattern_is_carried_verbatim(self):
        for pat in ("node_modules", "/out", "*.pem", "dist/", "!keep.txt", "a/b/c"):
            self.assertEqual(excludes.translate("", pat), pat)

    def test_a_nested_pattern_without_a_slash_matches_at_any_depth_below_it(self):
        self.assertEqual(excludes.translate("apps/web", "node_modules"), "/apps/web/**/node_modules")
        self.assertEqual(excludes.translate("packages/database", "generated"), "/packages/database/**/generated")

    def test_a_nested_pattern_with_a_slash_is_anchored_to_its_directory(self):
        self.assertEqual(excludes.translate("apps/web", "/test-results"), "/apps/web/test-results")
        self.assertEqual(excludes.translate("apps/web", "build/out"), "/apps/web/build/out")

    def test_a_trailing_slash_still_means_a_directory(self):
        self.assertEqual(excludes.translate("apps/web", "dist/"), "/apps/web/**/dist/")
        self.assertEqual(excludes.translate("apps/web", "/dist/"), "/apps/web/dist/")

    def test_a_glob_in_the_directory_name_is_taken_literally(self):
        """Hiding more than the learner's branch hides would hide real
        dirt, so the directory is escaped on the way into the pattern."""
        self.assertEqual(excludes.translate("app[1]", "node_modules"), "/app\\[1\\]/**/node_modules")
        self.assertEqual(excludes.translate("a*b", "junk"), "/a\\*b/**/junk")
        self.assertEqual(excludes.translate("a?b", "junk"), "/a\\?b/**/junk")

    def test_a_comment_is_a_comment_at_column_zero_only(self):
        """git's own rule: '  #x' names a file whose name starts with
        two spaces."""
        self.assertIsNone(excludes.translate("apps/web", "# a comment"))
        self.assertEqual(excludes.translate("apps/web", "  #x"), "/apps/web/**/  #x")

    def test_a_negation_keeps_its_bang(self):
        self.assertEqual(excludes.translate("apps/web", "!keep.log"), "!/apps/web/**/keep.log")
        self.assertEqual(excludes.translate("apps/web", "!/keep.log"), "!/apps/web/keep.log")

    def test_blanks_and_comments_are_not_patterns(self):
        for line in ("", "   ", "# a comment", "#"):
            self.assertIsNone(excludes.translate("apps/web", line))


class BlockTest(WorldTest):
    def setUp(self):
        super().setUp()
        w = self.w
        # An ignore rule the learner's branch has and the starting state
        # does not: the shape of #33.
        w.write(".gitignore", "test-results/\n")
        w.write("apps/web/.gitignore", "node_modules\n/scratch\n")
        w.write("apps/web/keep.txt", "kept\n")
        w.git("add", "-A")
        w.git("commit", "-q", "-m", "ignore what the test run leaves")
        self.main = w.git("rev-parse", "HEAD")

    def exclude_text(self) -> str:
        p = excludes.exclude_file(Repo(self.w.top))
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    def test_the_block_carries_every_ignore_file_of_the_ref(self):
        excludes.write(Repo(self.w.top), "main")
        text = self.exclude_text()
        self.assertIn(excludes.START, text)
        self.assertIn(excludes.END, text)
        self.assertIn("test-results/", text)
        self.assertIn("/apps/web/**/node_modules", text)
        self.assertIn("/apps/web/scratch", text)

    def test_writing_twice_replaces_the_block_rather_than_adding_one(self):
        repo = Repo(self.w.top)
        excludes.write(repo, "main")
        excludes.write(repo, "main")
        self.assertEqual(self.exclude_text().count(excludes.START), 1)

    def test_removing_keeps_what_was_there_before(self):
        p = excludes.exclude_file(Repo(self.w.top))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# the learner's own\nmy-scratch/\n", encoding="utf-8")
        repo = Repo(self.w.top)
        excludes.write(repo, "main")
        excludes.remove(repo)
        self.assertEqual(p.read_text(encoding="utf-8"), "# the learner's own\nmy-scratch/\n")
        self.assertNotIn(excludes.START, p.read_text(encoding="utf-8"))

    def test_removing_when_there_is_no_block_changes_nothing(self):
        repo = Repo(self.w.top)
        self.assertFalse(excludes.remove(repo))
        excludes.write(repo, "main")
        self.assertTrue(excludes.remove(repo))

    def test_a_deeper_file_has_the_last_word_as_git_reads_it(self):
        """A negation in a nested file must land after the rule it
        overrides. Sorting by name alone inverts that wherever a
        directory sorts before its own parent's ignore file."""
        w = self.w
        w.write("apps/.gitignore", "dist\n")
        w.write("apps/-x/.gitignore", "!dist\n")
        w.write("apps/-x/keep.txt", "kept\n")
        w.git("add", "-A")
        w.git("commit", "-q", "-m", "a nested negation")
        pats = [p for p in excludes.patterns(Repo(w.top), "main") if not p.startswith("#")]
        self.assertLess(pats.index("/apps/**/dist"), pats.index("!/apps/-x/**/dist"))

    def test_an_unreadable_file_is_not_an_empty_one(self):
        """A read that failed is the caller's to report: treating it as
        empty would make remove a silent no-op and let write replace the
        learner's own lines."""
        if is_root():
            self.skipTest("root reads anything")
        repo = Repo(self.w.top)
        excludes.write(repo, "main")
        f = excludes.exclude_file(repo)
        f.chmod(0o000)
        self.addCleanup(f.chmod, 0o644)
        with self.assertRaises(OSError):
            excludes.remove(repo)
        with self.assertRaises(OSError):
            excludes.write(repo, "main")

    def test_a_ref_with_no_ignore_files_writes_no_block(self):
        repo = Repo(self.w.top)
        excludes.write(repo, self.w.pre)   # the initial commit, before any .gitignore
        self.assertNotIn(excludes.START, self.exclude_text())
        excludes.write(repo, "main")
        self.assertIn(excludes.START, self.exclude_text())
        excludes.write(repo, self.w.pre)
        self.assertNotIn(excludes.START, self.exclude_text(), "and it clears a block that was there")


if __name__ == "__main__":
    unittest.main()
