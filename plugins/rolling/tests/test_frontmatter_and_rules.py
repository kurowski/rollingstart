"""The parser for the flat subset, and the rules the specs state."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from support import PLUGIN  # noqa: F401  (puts lib on the path)

from rolling import frontmatter as fm, rules, paths

SAMPLE = """---
name: Thing
mode: write
requires: [a, b ,c]
assumes:
  - x
  - y
empty: []
commands:
  check: sh check.sh
  test: sh run-test.sh   # a comment
scope: one
scope: two
---

## Body

name: not-a-field
"""


class FrontmatterTest(unittest.TestCase):
    def test_parses_every_shape(self):
        f = fm.parse(SAMPLE)
        self.assertEqual(f.scalar("name"), "Thing")
        self.assertEqual(f.scalar("nothing"), "")
        self.assertEqual(f.all("scope"), ["one", "two"])
        self.assertEqual(f.list("requires"), ["a", "b", "c"])
        self.assertEqual(f.list("assumes"), ["x", "y"])
        self.assertEqual(f.list("empty"), [])
        self.assertEqual(f.keys, ["name", "mode", "requires", "assumes", "empty", "commands", "scope", "scope"])
        self.assertEqual(f.map_get("commands", "check"), "sh check.sh")
        self.assertEqual(f.map_get("commands", "test"), "sh run-test.sh   # a comment", "values are verbatim")
        self.assertEqual(f.map_get("commands", "nope"), "")

    def test_body_is_never_read(self):
        f = fm.parse(SAMPLE)
        self.assertEqual(f.all("name"), ["Thing"])

    def test_needs_a_fence_on_line_one(self):
        self.assertIsNone(fm.parse("no frontmatter\n---\nx: 1\n---\n"))
        self.assertIsNone(fm.parse("---\nx: 1\n"))

    def test_crlf_reads_as_lf(self):
        f = fm.parse(SAMPLE.replace("\n", "\r\n"))
        self.assertEqual(f.scalar("name"), "Thing")
        self.assertEqual(f.map_get("commands", "check"), "sh check.sh")

    def test_keys_are_literal(self):
        f = fm.parse("---\na.b: 1\nscope-x: y\nscope: z\n---\n")
        self.assertEqual(f.scalar("a.b"), "1")
        self.assertEqual(f.all("scope"), ["z"])
        self.assertIn("a.b", f.keys)

    def test_tab_in_a_command_survives(self):
        f = fm.parse("---\ncommands:\n  c: sh a\tsh b\n---\n")
        self.assertEqual(f.map_get("commands", "c"), "sh a\tsh b")

    def test_regions_and_courses(self):
        text = "# T\n\n## Regions\n\n- **billing** — x\n- **platform** — y\n- not a region\n\n## Suggested courses\n\n### Generalist\n\n### Billing engineer\n\n## Corpus\n"
        self.assertEqual(fm.map_regions(text), ["billing", "platform"])
        self.assertEqual(fm.map_courses(text), ["Generalist", "Billing engineer"])
        self.assertEqual(fm.map_courses(text.replace("courses", "course")), ["Generalist", "Billing engineer"])


class RulesTest(unittest.TestCase):
    def test_slugs(self):
        self.assertTrue(rules.is_slug("poll-data-model"))
        for bad in ("Poll-Model", "a--b", "-a", "a-", "", "a_b"):
            self.assertFalse(rules.is_slug(bad), bad)

    def test_shas_and_dates(self):
        self.assertTrue(rules.is_sha("abcdef1"))
        self.assertFalse(rules.is_sha("abcde"))
        self.assertTrue(rules.is_date("2026-09-15"))
        self.assertFalse(rules.is_date("15/09/2026"))

    def test_arguments_are_words(self):
        self.assertTrue(rules.args_are_words("src/x.test.sh --flag"))
        self.assertTrue(rules.args_are_words(""))
        for bad in ("a; rm -rf /", "*.sh", "it's", "a\tb", "$(x)", "a|b", "a  b", " a", "a "):
            self.assertFalse(rules.args_are_words(bad), bad)

    def test_plain_relative_paths(self):
        for ok in ("a/b.c", ".github/workflows/ci.yml", "a/..b", "...", "src/**", "packages/*/src", "-dash/x"):
            self.assertTrue(rules.is_plain_relpath(ok), ok)
        for bad in ("/etc/passwd", "a/../b", "../x", "./a", "a/./b", "a//b", "a/.", ".", "..", ""):
            self.assertFalse(rules.is_plain_relpath(bad), bad)

    def test_commands_that_take_arguments(self):
        for ok in ("sh check.sh", "make -C sub", "cmd 2>&1", "sh -c 'exit 3'"):
            self.assertTrue(rules.command_takes_args(ok), ok)
        for bad in ("echo x;", "echo x; ", "echo x &", "echo x |", "echo x ||", "echo x && ", "sh args.sh >", "cmd <", "cmd\\", "sh args.sh;#x", "sh x # note", "", "   ", "cmd\t;"):
            self.assertFalse(rules.command_takes_args(bad), repr(bad))

    def test_symlink_components(self):
        with tempfile.TemporaryDirectory() as d:
            top = Path(d)
            (top / "aa" / "sub").mkdir(parents=True)
            os.symlink("aa", top / "ab")
            (top / "aa" / "f").write_text("x")
            os.symlink("f", top / "aa" / "link")
            self.assertFalse(rules.has_symlink_component(top, "aa/sub/x"))
            self.assertTrue(rules.has_symlink_component(top, "ab/f"))
            self.assertTrue(rules.has_symlink_component(top, "aa/link"))
            self.assertFalse(rules.has_symlink_component(top, "a*/f"), "a glob is a literal name, not a pattern")

    def test_encode(self):
        self.assertEqual(paths.encode("/home/pat/repo"), "-home-pat-repo")
        self.assertEqual(paths.encode("/home/pat/café"), "-home-pat-caf--")


if __name__ == "__main__":
    unittest.main()
