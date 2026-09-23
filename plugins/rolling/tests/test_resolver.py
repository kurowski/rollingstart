"""The resolver: the tree's map wins, else the installed map plugin
declared for this repository, else none with the registrations listed.
Registrations are built under the scratch world's data root, the
parent of ROLLING_DATA, the way Claude Code lays out every plugin's
data directory beside rolling's."""

from __future__ import annotations

import json
import os
import shutil
import unittest
from pathlib import Path

from support import MAP, SETUP_LESSON, WorldTest

from rolling import mapsource

REMOTE = "https://github.com/someone/scratch-target.git"


class NormalizeTest(unittest.TestCase):
    def test_every_spelling_of_one_remote(self):
        want = "github.com/someone/scratch-target"
        for url in [
            "https://github.com/someone/scratch-target.git",
            "https://github.com/someone/scratch-target",
            "https://github.com/someone/scratch-target/",
            "https://pat:token@GitHub.com/someone/scratch-target.git",
            "git@github.com:someone/scratch-target.git",
            "ssh://git@github.com/someone/scratch-target.git",
            "git://github.com/someone/scratch-target.git",
            "  git@github.com:someone/scratch-target  ",
        ]:
            self.assertEqual(mapsource.normalize_remote(url), want, url)

    def test_paths_and_nothing_are_nothing(self):
        for url in ["", "/home/pat/scheduling", "../scheduling", "C:\\repos\\scheduling"]:
            self.assertEqual(mapsource.normalize_remote(url), "", repr(url))

    def test_case_is_not_significant_anywhere(self):
        # GitHub and its kind are case-insensitive; a clone URL typed with
        # capitals must match a declaration written without, and the reverse.
        n = mapsource.normalize_remote("https://GitHub.com/Example/Scheduling.git")
        self.assertEqual(n, "github.com/example/scheduling")
        self.assertTrue(mapsource.matches("github.com/example/scheduling", n))
        self.assertTrue(mapsource.matches("*/Scheduling", n))
        self.assertTrue(mapsource.matches("GitHub.com/Example/*", n))

    def test_file_urls_are_local_paths(self):
        self.assertEqual(mapsource.normalize_remote("file:///home/pat/scheduling"), "")
        self.assertEqual(mapsource.normalize_remote("file://localhost/home/pat/scheduling"), "localhost/home/pat/scheduling")

    def test_patterns(self):
        n = "github.com/example/scheduling"
        self.assertTrue(mapsource.matches("*/scheduling", n))
        self.assertTrue(mapsource.matches("github.com/example/scheduling", n))
        self.assertFalse(mapsource.matches("*/scheduling-spike", n))
        self.assertFalse(mapsource.matches("", n))
        self.assertFalse(mapsource.matches("*/scheduling", ""))


class ResolverTest(WorldTest):
    """Each test starts with the scratch world's tree map in place."""

    def register(self, id_: str, name: str, repo: str, commit: str = "", version: str = "0.1.0",
                 root: Path = None, map_text: str = MAP) -> Path:
        """A map plugin as its hook registers it: <data root>/<id>/root
        naming a plugin directory with a manifest and a map."""
        root = root or (self.w.root / f"plugin-{id_}")
        (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        manifest = {"name": name, "version": version,
                    "metadata": {"rolling": {"repo": repo, "commit": commit}}}
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
        if map_text is not None:
            (root / "map.md").write_text(map_text, encoding="utf-8")
            (root / "lessons").mkdir(exist_ok=True)
            (root / "lessons" / "setup.md").write_text(SETUP_LESSON, encoding="utf-8")
        reg = self.w.data.parent / id_
        reg.mkdir(parents=True, exist_ok=True)
        (reg / "root").write_text(str(root) + "\n", encoding="utf-8")
        return root

    def drop_tree_map(self) -> None:
        self.w.git("rm", "-r", "-q", ".rolling")
        self.w.git("commit", "-q", "-m", "no map in the tree")
        self.assertFalse((self.w.top / ".rolling").exists())

    def resolve(self) -> mapsource.Resolved:
        return mapsource.resolve(self.w.top, self.w.data)

    def test_the_tree_wins_whatever_is_installed(self):
        self.w.git("remote", "add", "origin", REMOTE)
        self.register("scratchmap-scratchmarket", "scratchmap", "*/scratch-target")
        r = self.resolve()
        self.assertEqual(r.source, "tree")
        self.assertEqual(r.dir, self.w.top / ".rolling")
        self.assertEqual(r.notes, [])
        self.assertTrue(self.assertRuns("show", "map").startswith("(map: in tree)\n"))
        self.assertIn("MAP: ok", self.assertRuns("show", "map-check"))
        self.assertIn("in tree", self.assertRuns("show", "map-check"))

    def test_a_plugin_alone_is_the_map(self):
        self.w.git("remote", "add", "origin", REMOTE)
        root = self.register("scratchmap-scratchmarket", "scratchmap", "*/scratch-target", commit=self.w.pre, version="0.2.0")
        self.drop_tree_map()
        r = self.resolve()
        self.assertEqual((r.source, r.dir), ("plugin", root))
        self.assertEqual(r.plugin.label, "scratchmap@scratchmarket 0.2.0")
        self.assertEqual(r.notes, [], "the declared commit is in history and behind HEAD")
        out = self.assertRuns("show", "map")
        self.assertTrue(out.startswith("(map: plugin scratchmap@scratchmarket 0.2.0)\n"), out)
        self.assertIn("name: Scratch", out)
        self.assertIn("MAP: ok", self.assertRuns("show", "map-check"))
        self.assertIn("### setup", self.assertRuns("show", "lessons"), "every command reads the plugin's map")
        self.assertIn("map ok", self.assertRuns("check-map"))

    def test_the_label_when_the_marketplace_cannot_be_told(self):
        self.w.git("remote", "add", "origin", REMOTE)
        self.register("oddly-named", "scratchmap", "*/scratch-target")
        self.drop_tree_map()
        self.assertEqual(self.resolve().plugin.label, "scratchmap 0.1.0")

    def test_two_matches_are_refused_naming_both(self):
        self.w.git("remote", "add", "origin", REMOTE)
        self.register("one-market", "one", "*/scratch-target")
        self.register("two-market", "two", "github.com/someone/*")
        self.drop_tree_map()
        r = self.resolve()
        self.assertEqual((r.source, r.dir), ("none", None))
        self.assertEqual(r.notes, [])
        self.assertIn("one@market 0.1.0", r.summary)
        self.assertIn("two@market 0.1.0", r.summary)
        out = self.assertRuns("show", "map-check")
        self.assertIn("MAP: none; two map plugins claim this repository", out)
        self.assertNotIn("no installed map plugin", out, "the verdict says the same thing as the reason")
        self.assertIn("two map plugins claim", self.assertRuns("show", "map"))
        rc, out = self.w.run("check-map")
        self.assertEqual(rc, 1)
        self.assertIn("two map plugins claim", out)

    def test_no_match_lists_what_is_installed_and_why(self):
        self.w.git("remote", "add", "origin", REMOTE)
        self.register("other-market", "other", "*/other-repo")
        gone = self.register("gone-market", "gone", "*/scratch-target", root=self.w.root / "plugin-gone")
        shutil.rmtree(gone)
        self.register("bare-market", "bare", "*/scratch-target", map_text=None)
        undeclared_root = self.w.root / "plugin-undeclared"
        (undeclared_root / ".claude-plugin").mkdir(parents=True)
        (undeclared_root / ".claude-plugin" / "plugin.json").write_text('{"name": "undeclared"}', encoding="utf-8")
        (self.w.data.parent / "undeclared-market").mkdir()
        (self.w.data.parent / "undeclared-market" / "root").write_text(str(undeclared_root) + "\n", encoding="utf-8")
        self.drop_tree_map()
        r = self.resolve()
        self.assertEqual((r.source, r.dir), ("none", None))
        text = "\n".join(r.notes)
        self.assertIn("github.com/someone/scratch-target", text)
        self.assertIn("other@market 0.1.0: for */other-repo", text)
        self.assertIn("gone-market: its root is gone", text, "no manifest to name it by, so the id")
        self.assertIn("bare@market 0.1.0: no map.md", text)
        self.assertIn("declares no repository", text)
        out = self.assertRuns("show", "map")
        self.assertTrue(out.startswith("(map: none\n"), out)
        self.assertIn("(no map:", out)

    def test_no_remote_cannot_match(self):
        self.register("scratchmap-scratchmarket", "scratchmap", "*/scratch-target")
        self.drop_tree_map()
        r = self.resolve()
        self.assertEqual(r.source, "none")
        self.assertIn("no origin remote", r.notes[0])

    def test_a_local_remote_cannot_match(self):
        self.w.git("remote", "add", "origin", "/somewhere/on/disk")
        self.register("scratchmap-scratchmarket", "scratchmap", "*")
        self.drop_tree_map()
        r = self.resolve()
        self.assertEqual(r.source, "none")
        self.assertIn("local path", r.notes[0])

    def test_a_declared_commit_that_is_not_a_sha_is_a_note(self):
        self.w.git("remote", "add", "origin", REMOTE)
        self.register("scratchmap-scratchmarket", "scratchmap", "*/scratch-target", commit="--not-a-sha")
        self.drop_tree_map()
        r = self.resolve()
        self.assertEqual(r.source, "plugin")
        self.assertIn("not a sha", r.notes[0])

    def test_a_task_branch_does_not_revive_a_map_history_carried(self):
        # The project used to commit its map (the fix's parent has one) and
        # now ships it as a plugin (HEAD has none). Cutting the task branch
        # from the parent must not put the old map back in the tree, where
        # it would win over the plugin's for the rest of the task.
        self.w.git("remote", "add", "origin", REMOTE)
        root = self.register("scratchmap-scratchmarket", "scratchmap", "*/scratch-target")
        self.drop_tree_map()
        self.assertIn("plugin scratchmap", self.assertRuns("show", "map-check"))
        self.assertRuns("claim-session", "s1")
        rc, out = self.w.run("begin-task", "greet-politely", "--fix", self.w.fix, "--held", "tests/greet.test.sh")
        self.assertEqual(rc, 0, out)
        self.assertFalse((self.w.top / ".rolling").exists(), "the parent's map is not in the task branch's tree")
        self.assertEqual(self.resolve().dir, root)
        self.assertIn("plugin scratchmap", self.assertRuns("show", "map-check"))
        self.assertClean()

    def test_no_data_directory_sees_no_plugins(self):
        self.drop_tree_map()
        r = mapsource.resolve(self.w.top, None)
        self.assertEqual(r.source, "none")
        self.assertIn("ROLLING_DATA", r.notes[0])
        rc, out = self.w.run("show", "map", env={"ROLLING_DATA": None})
        self.assertEqual(rc, 0)
        self.assertIn("ROLLING_DATA", out)

    def test_nothing_installed(self):
        self.drop_tree_map()
        r = self.resolve()
        self.assertEqual(r.source, "none")
        self.assertIn("registers at the next session start", r.notes[0], "installed this session is the common case")
        self.assertIn("does not exist in the tree", r.summary)
        self.assertIn("MAP: none; " + r.summary, self.assertRuns("show", "map-check"))
        self.w.task(lesson="setup", mode="write", scope="src")   # the verifier looks for a task before a map
        self.assertIn("no map: " + r.summary, self.assertRuns("verify"), "the verifier says the same, not the tree's path")

    def test_a_declared_commit_the_checkout_lacks_is_a_note(self):
        self.w.git("remote", "add", "origin", REMOTE)
        self.register("scratchmap-scratchmarket", "scratchmap", "*/scratch-target", commit="0123456789abcdef0123456789abcdef01234567")
        self.drop_tree_map()
        r = self.resolve()
        self.assertEqual(r.source, "plugin", "a stale pin is a note, never a refusal")
        self.assertEqual(len(r.notes), 1)
        self.assertIn("does not have", r.notes[0])
        out = self.assertRuns("show", "map-check")
        self.assertIn("MAP: ok", out)
        self.assertIn("does not have", out)

    def test_a_declared_commit_ahead_of_head_is_a_note(self):
        self.w.git("remote", "add", "origin", REMOTE)
        self.register("scratchmap-scratchmarket", "scratchmap", "*/scratch-target", commit=self.w.fix)
        self.drop_tree_map()
        ahead = self.w.git("rev-parse", "HEAD")
        self.w.git("switch", "-q", "--detach", self.w.pre)   # behind the map's pin, before the tree map was removed
        try:
            r = self.resolve()
            self.assertEqual(r.source, "tree", "at pre the tree map is back, and it wins")
            self.w.git("rm", "-r", "-q", "--cached", ".rolling")
            shutil.rmtree(self.w.top / ".rolling")
            r = self.resolve()
            self.assertEqual(r.source, "plugin")
            self.assertEqual(len(r.notes), 1)
            self.assertIn("not an ancestor of HEAD", r.notes[0])
        finally:
            self.w.git("reset", "-q", "--hard")
            self.w.git("switch", "-q", "--detach", ahead)

    def test_registrations_ignore_directories_without_a_root_file(self):
        (self.w.data.parent / "not-a-plugin").mkdir()
        self.w.data.mkdir(parents=True, exist_ok=True)   # rolling's own data directory has no root file
        self.assertEqual(mapsource.registrations(self.w.data), [])


if __name__ == "__main__":
    unittest.main()
