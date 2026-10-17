"""The task's lifecycle in the repository: begin, end, park, resume,
close, and every refusal, through the executables a skill would run."""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest

from support import WorldTest, is_root

from rolling import excludes  # noqa: E402


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

    def test_the_map_as_of_now_comes_along(self):
        """A fix older than the map: the branch is cut from before the map
        existed, and the task must still have it, as it is now."""
        w = self.w
        w.write(".rolling/lessons/newer.md", "---\ntitle: Newer\nregion: greeting\ndepth: working\n---\n\nx\n\n## Rubric\n\ny\n")
        w.git("rm", "-q", ".rolling/lessons/setup.md")
        w.git("add", "-A")
        w.git("commit", "-q", "-m", "the map moved on")
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        self.assertTrue((w.top / ".rolling/lessons/newer.md").is_file(), "a lesson added after the fix is on the branch")
        self.assertFalse((w.top / ".rolling/lessons/setup.md").exists(), "a lesson removed after the fix is gone")
        self.assertClean()
        self.assertEqual(w.git("rev-parse", "HEAD^"), w.pre)
        self.assertIn("newer.md", w.git("show", "--stat", "--format=", base), "the map is in the starting-state commit, so never in the diff")
        self.assertIn("the map as of the commit the task began from", w.git("log", "-1", "--format=%B"))
        w.held_task(branch, base)
        out = self.assertRuns("diff")
        self.assertIn("## Diff", out)
        self.assertNotIn("newer.md", out)
        self.assertNotIn("setup.md", out)

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
        self.assertIn("no glob, no pathspec magic", self.assertRuns("begin-task", "setup", "--fix", w.fix, "--shown", ":!tests/greet.test.sh", status=1))
        self.assertIn("no glob, no pathspec magic", self.assertRuns("begin-task", "setup", "--here", "tests/*", status=1))
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


class BeginSurvivesTheEnvironmentTest(WorldTest):
    """What the first fresh learner's run found (2026-09-21): a container
    with no git identity, and the repository's own commit hooks, are
    conditions the toolkit's own commits must not depend on; and a
    commit that fails part-way must leave the repository as it was,
    since the tutor cannot be trusted to tidy up a half-made branch."""

    NO_IDENTITY = {
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        "EMAIL": None, "GIT_AUTHOR_NAME": None, "GIT_AUTHOR_EMAIL": None, "GIT_COMMITTER_NAME": None, "GIT_COMMITTER_EMAIL": None,
    }

    def forget_identity(self) -> None:
        w = self.w
        w.git("config", "--unset", "user.email")
        w.git("config", "--unset", "user.name")
        w.git("config", "user.useConfigOnly", "true")   # no guessing from the hostname
        env = {k: v for k, v in {**os.environ, **self.NO_IDENTITY}.items() if v is not None}
        rc = subprocess.run(["git", "var", "GIT_COMMITTER_IDENT"], cwd=str(w.top), capture_output=True, env=env, check=False).returncode
        self.assertNotEqual(rc, 0, "the scratch repository should have no identity for this test")

    def test_begins_and_ends_without_a_git_identity(self):
        w = self.w
        self.forget_identity()
        rc, out = w.run("begin-task", "greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh", env=self.NO_IDENTITY)
        self.assertEqual(rc, 0, out)
        fields = dict(l.split(": ", 1) for l in out.split("\n") if ": " in l)
        self.assertEqual(w.git("log", "-1", "--format=%an <%ae>"), "Rolling Start <rolling@localhost>")
        self.assertClean()
        w.held_task(fields["branch"], fields["base"])
        w.write("src/greet.sh", "#!/bin/sh\nprintf 'Hello %s\\n' \"$1\"\n")
        rc, out = w.run("end-task", env=self.NO_IDENTITY)
        self.assertEqual(rc, 0, out)
        self.assertIn("no git identity", out, "the learner is told their work was committed under the toolkit's name")
        self.assertEqual(w.git("log", "-1", "--format=%an", fields["branch"]), "Rolling Start")
        self.assertOnBranch("main")
        self.assertClean()

    def test_the_learner_identity_is_used_when_there_is_one(self):
        w = self.w
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        self.assertEqual(w.git("log", "-1", "--format=%an"), "Rolling Start", "the starting state is the toolkit's commit")
        w.held_task(branch, base)
        w.write("src/greet.sh", "#!/bin/sh\nprintf 'Hello %s\\n' \"$1\"\n")
        out = self.assertRuns("end-task")
        self.assertNotIn("no git identity", out)
        self.assertEqual(w.git("log", "-1", "--format=%an <%ae>", branch), "Test <test@example.com>", "the learner's work is theirs")

    def test_the_repositorys_commit_hooks_do_not_run(self):
        w = self.w
        hooks = w.root / "hooks"   # outside the tree (a tool's hooksPath is usually inside it, but the tree must stay clean here)
        hooks.mkdir()
        for name in ("pre-commit", "prepare-commit-msg", "commit-msg", "post-commit",   # --no-verify skips only two of these
                     "post-checkout", "reference-transaction", "post-index-change"):   # and these fire on switch, add, and every ref update
            (hooks / name).write_text("#!/bin/sh\necho HOOK RAN >&2\nexit 1\n")
            (hooks / name).chmod(0o755)
        w.git("config", "core.hooksPath", str(hooks))
        w.git("config", "commit.gpgsign", "true")
        w.git("config", "gpg.program", "/bin/false")
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        w.held_task(branch, base)
        w.write("src/greet.sh", "#!/bin/sh\nprintf 'Hello %s\\n' \"$1\"\n")
        out = self.assertRuns("end-task")
        self.assertNotIn("HOOK RAN", out)
        self.assertOnBranch("main")
        self.assertRuns("close-task")
        self.assertClean()

    def test_a_refused_ref_update_still_puts_the_tree_back(self):
        """git switch -c rewrites the tree before it moves HEAD; a ref
        update that is refused leaves the learner's branch with the
        starting state in its tree. The undo must not wait for HEAD to
        have moved."""
        from rolling.repo import GitError, Repo
        from rolling.tasks import Refused, Tasks
        w = self.w
        w.write(".rolling/lessons/newer.md", "---\ntitle: Newer\nregion: greeting\ndepth: working\n---\n\nx\n\n## Rubric\n\ny\n")
        w.git("add", "-A")
        w.git("commit", "-q", "-m", "the map moved on")

        class RefusedRef(Repo):
            def switch_new(self, branch, start=None):
                # What a refused ref update leaves: the tree and index at the start point, HEAD unmoved.
                self.run("read-tree", "-m", "-u", start)
                raise GitError("cannot lock ref")

        with self.assertRaises(Refused) as cm:
            Tasks(RefusedRef(w.top), w.learner).begin_from_fix("greet-politely", w.fix, ["tests/greet.test.sh"], [])
        self.assertIn("as it was", str(cm.exception))
        self.assertOnBranch("main")
        self.assertClean()
        self.assertTrue((w.top / ".rolling/lessons/newer.md").is_file(), "the map is back in the tree")

    def test_a_held_copy_that_cannot_be_written_undoes_the_begin(self):
        from rolling.repo import Repo
        from rolling.tasks import Refused, Tasks
        w = self.w

        class FullDisk(Repo):
            def show(self, sha, path):
                raise OSError(28, "No space left on device")

        with self.assertRaises(Refused) as cm:
            Tasks(FullDisk(w.top), w.learner).begin_from_fix("greet-politely", w.fix, ["tests/greet.test.sh"], [])
        self.assertIn("nothing was begun", str(cm.exception))
        self.assertOnBranch("main")
        self.assertClean()
        self.assertEqual(w.git("branch", "--list", "rolling/*"), "")
        self.assertFalse(w.learner.held.exists())

    def test_an_undo_that_cannot_finish_says_so_instead_of_claiming_success(self):
        from rolling.repo import GitError, Repo
        from rolling.tasks import Refused, Tasks
        w = self.w

        class Stuck(Repo):
            def commit(self, message, allow_empty=False, as_tool=False):
                raise GitError("commit failed on purpose")

            def switch_discarding(self, ref, detach=False):
                raise GitError("switch refused on purpose")

        with self.assertRaises(Refused) as cm:
            Tasks(Stuck(w.top), w.learner).begin_from_fix("greet-politely", w.fix, ["tests/greet.test.sh"], [])
        msg = str(cm.exception)
        self.assertNotIn("nothing was begun", msg)
        self.assertIn("could not be put back", msg)
        self.assertIn("could not put the tree back: switch refused on purpose", msg)
        self.assertIn("never yours", msg)
        branch = w.git("symbolic-ref", "--short", "HEAD")
        self.assertTrue(branch.startswith("rolling/greet-politely-"), "and it is honest: the repository is still on the half-made branch")

    def test_refuses_to_begin_on_a_task_branch(self):
        w = self.w
        w.git("switch", "-q", "-c", "rolling/greet-politely-20260921-020224")
        out = self.assertRuns("begin-task", "setup", "--fix", w.fix, "--shown", "tests/greet.test.sh", status=1)
        self.assertIn("task branch from an earlier run", out)
        self.assertOnBranch("rolling/greet-politely-20260921-020224")
        self.assertClean()
        w.write("tests/seam.test.sh", "seam\n")
        out = self.assertRuns("begin-task", "setup", "--here", "tests/seam.test.sh", status=1)
        self.assertIn("task branch from an earlier run", out)
        self.assertEqual(w.git("status", "--porcelain"), "?? tests/seam.test.sh")

    def test_a_branch_named_like_the_map_branch_is_not_a_task_branch(self):
        w = self.w
        w.git("switch", "-q", "-c", "rolling/map")
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        self.assertEqual(w.git("rev-parse", "HEAD^"), w.pre)
        w.held_task(branch, base, return_to=f"rolling/map {w.fix}")
        self.assertRuns("end-task")
        self.assertOnBranch("rolling/map")

    def test_a_committer_in_the_environment_is_not_an_identity(self):
        """GIT_COMMITTER_* alone satisfies git's committer and not its
        author, and a commit needs both; the fallback must see that."""
        w = self.w
        self.forget_identity()
        env = dict(self.NO_IDENTITY, GIT_COMMITTER_NAME="Someone", GIT_COMMITTER_EMAIL="someone@example.com")
        rc, out = w.run("begin-task", "greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh", env=env)
        self.assertEqual(rc, 0, out)
        fields = dict(l.split(": ", 1) for l in out.split("\n") if ": " in l)
        w.held_task(fields["branch"], fields["base"])
        w.write("src/greet.sh", "#!/bin/sh\nprintf 'Hello %s\\n' \"$1\"\n")
        rc, out = w.run("end-task", env=env)
        self.assertEqual(rc, 0, out)
        self.assertIn("no git identity", out)
        self.assertOnBranch("main")

    def test_a_failed_end_commit_keeps_the_work_unstaged_on_the_branch(self):
        from rolling.tasks import Refused
        w = self.w
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        task = w.held_task(branch, base)
        w.write("src/greet.sh", "#!/bin/sh\nprintf 'Hello %s\\n' \"$1\"\n")
        from rolling.model import Task
        with self.assertRaises(Refused) as cm:
            self._failing_tasks().end(Task.load(task))
        self.assertIn("nothing was left", str(cm.exception))
        self.assertOnBranch(branch)
        self.assertEqual(w.git("diff", "--name-only"), "src/greet.sh", "their work is in the tree")
        self.assertEqual(w.git("diff", "--cached", "--name-only"), "", "and unstaged, as they left it")
        # Staged as they had it, too: a deliberately staged hunk survives.
        w.git("add", "src/greet.sh")
        w.write("src/greet.sh", w.read("src/greet.sh") + "# a later edit\n")
        with self.assertRaises(Refused):
            self._failing_tasks().end(Task.load(task))
        self.assertEqual(w.git("diff", "--cached", "--name-only"), "src/greet.sh", "the staged version is still staged")
        self.assertIn("a later edit", w.read("src/greet.sh"))
        self.assertIn("a later edit", w.git("diff"), "and the unstaged edit is still unstaged")
        self.assertRuns("end-task")   # and a second try, with a working git, leaves normally
        self.assertOnBranch("main")

    def _failing_tasks(self):
        """A Tasks whose commit fails, the way a full disk or a refused
        object write would; identity and hooks are already out of the
        picture, so this is the failure that is left."""
        from rolling.repo import GitError, Repo
        from rolling.tasks import Tasks

        class Broken(Repo):
            def commit(self, message, allow_empty=False, as_tool=False):
                raise GitError("commit failed on purpose")

        return Tasks(Broken(self.w.top), self.w.learner)

    def test_a_failed_starting_state_commit_puts_everything_back(self):
        from rolling.tasks import Refused
        w = self.w
        # A fix older than the map, so the map is carried (the case the
        # first run hit), and a shown test the branch point lacks.
        w.write(".rolling/lessons/newer.md", "---\ntitle: Newer\nregion: greeting\ndepth: working\n---\n\nx\n\n## Rubric\n\ny\n")
        w.git("add", "-A")
        w.git("commit", "-q", "-m", "the map moved on")
        origin = w.git("rev-parse", "HEAD")
        with self.assertRaises(Refused) as cm:
            self._failing_tasks().begin_from_fix("greet-politely", w.fix, ["tests/greet.test.sh"], [])
        self.assertIn("nothing was begun", str(cm.exception))
        self.assertIn("commit failed on purpose", str(cm.exception))
        self.assertOnBranch("main")
        self.assertEqual(w.git("rev-parse", "HEAD"), origin)
        self.assertClean()
        self.assertEqual(w.git("branch", "--list", "rolling/*"), "", "the half-made branch is gone")
        self.assertTrue((w.top / ".rolling/lessons/newer.md").is_file())
        self.assertFalse(any(w.learner.held.rglob("*")) if w.learner.held.is_dir() else False, "nothing held for a task that never began")
        # And the repository can begin a task right afterwards.
        w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")

    def test_a_failed_commit_with_a_shown_test_leaves_none_of_it_behind(self):
        from rolling.tasks import Refused
        w = self.w
        with self.assertRaises(Refused):
            self._failing_tasks().begin_from_fix("setup", w.fix, [], ["tests/greet.test.sh"])
        self.assertOnBranch("main")
        self.assertClean()
        self.assertIn("HELLO", w.git("show", f"{w.pre}:src/greet.sh"))
        self.assertNotIn("HELLO", w.read("src/greet.sh"), "the tree is main's again, not the pre-fix code the branch point had")

    def test_a_failed_here_commit_leaves_the_tutors_file_in_the_tree(self):
        from rolling.tasks import Refused
        w = self.w
        w.write("tests/seam.test.sh", "seam\n")
        with self.assertRaises(Refused) as cm:
            self._failing_tasks().begin_here("setup", ["tests/seam.test.sh"])
        self.assertIn("nothing was begun", str(cm.exception))
        self.assertOnBranch("main")
        self.assertEqual(w.git("status", "--porcelain"), "?? tests/seam.test.sh", "the file the tutor prepared is still there, untracked as it was")
        self.assertEqual(w.git("branch", "--list", "rolling/*"), "")

    def test_a_failed_begin_from_a_detached_head_returns_there(self):
        from rolling.tasks import Refused
        w = self.w
        w.git("switch", "-q", "--detach", w.fix)
        with self.assertRaises(Refused):
            self._failing_tasks().begin_from_fix("greet-politely", w.fix, ["tests/greet.test.sh"], [])
        self.assertEqual(w.git("symbolic-ref", "-q", "--short", "HEAD"), "")
        self.assertEqual(w.git("rev-parse", "HEAD"), w.fix)
        self.assertClean()


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
        self.assertIn("closed;", out)
        self.assertFalse(w.learner.task_file.exists())
        self.assertFalse(w.learner.reference.exists())
        self.assertFalse(w.learner.held.exists())
        self.assertTrue(w.learner.profile.exists())
        self.assertTrue((w.learner.dir / "evidence/setup.md").exists())


class ParkAndResumeTest(WorldTest):
    """A task set aside for a detour and picked up again. The learner's
    work stays on the branch; the task's files wait in parked/."""

    def park_a_task(self, lesson="greet-politely"):
        """A begun task with the learner's work in the tree, parked."""
        w = self.w
        branch, base = w.begin(lesson, "--fix", w.fix, "--held", "tests/greet.test.sh")
        w.held_task(branch, base, lesson=lesson)
        w.write("src/greet.sh", w.read("src/greet.sh") + "# the learner was here\n")
        return branch, base

    def test_park_keeps_the_work_and_resume_brings_it_back(self):
        w = self.w
        branch, base = self.park_a_task()
        out = self.assertRuns("park-task")
        self.assertIn("committed the learner's uncommitted work", out)
        self.assertIn("parked", out)
        self.assertOnBranch("main")
        self.assertClean()
        self.assertIn("the learner was here", w.git("show", f"{branch}:src/greet.sh"))
        self.assertFalse(w.learner.has_task(), "task.md moved out of the way")
        self.assertFalse(w.learner.held.exists(), "held/ went with it")
        self.assertTrue(w.learner.has_parked())
        self.assertIn("tests/greet.test.sh", [str(p.relative_to(w.learner.parked / "held")) for p in (w.learner.parked / "held").rglob("*") if p.is_file()])
        self.assertIn("parked", self.assertRuns("show", "task"))

        self.assertRuns("claim-session", "s2")
        out = self.assertRuns("resume-task")
        self.assertIn(branch, out)
        self.assertOnBranch(branch)
        self.assertTrue(w.learner.has_task())
        self.assertFalse(w.learner.has_parked(), "parked/ is empty again")
        self.assertTrue((w.learner.held / "tests/greet.test.sh").is_file())
        t = w.learner.task()
        self.assertEqual(t.return_to.split()[0], "main", "return-to is where they were when they resumed")
        self.assertEqual(t.tutor_session, "s2", "the resumed task carries this session, or the guard would not fire")
        self.assertIn("the learner was here", w.read("src/greet.sh"))

    def test_the_held_test_never_reaches_the_tree(self):
        """Never in the tree and never on the branch while the task is
        open; on the learner's own branch the file there is the
        repository's own, which it always was."""
        w = self.w
        held = "tests/greet.test.sh"
        branch, _ = self.park_a_task()
        self.assertFalse((w.top / held).exists(), "absent on the task branch before the park")
        self.assertRuns("park-task")
        self.assertTrue((w.learner.parked / "held" / held).is_file(), "the held copy waits in parked/")
        self.assertTrue((w.top / held).is_file(), "main's own copy, untouched")
        self.assertRuns("claim-session", "s2")
        self.assertRuns("resume-task")
        self.assertFalse((w.top / held).exists(), "absent again, back on the task branch")
        self.assertTrue((w.learner.held / held).is_file(), "the held copy is back in the learner's directory")
        self.assertEqual(w.git("ls-tree", "-r", "--name-only", branch, "--", held), "", "and never committed to the branch")

    def test_resume_after_another_task_in_between(self):
        w = self.w
        branch, _ = self.park_a_task()
        self.assertRuns("park-task")
        # the detour's own task: begun, ended, and closed on the learner's branch
        step_branch, step_base = w.begin("setup", "--fix", w.fix, "--shown", "tests/greet.test.sh")
        w.task(lesson="setup", mode="write", branch=step_branch, base=step_base, return_to=f"main {w.fix}", scope="src")
        self.assertRuns("end-task")
        self.assertRuns("close-task")
        self.assertRuns("claim-session", "s2")
        out = self.assertRuns("resume-task")
        self.assertIn(branch, out)
        self.assertOnBranch(branch)
        self.assertEqual(w.learner.task().lesson, "greet-politely")

    def test_a_second_park_is_refused_while_one_is_resumable(self):
        w = self.w
        first, _ = self.park_a_task()
        self.assertRuns("park-task")
        second, base = w.begin("setup", "--fix", w.fix)
        w.task(lesson="setup", mode="write", branch=second, base=base, return_to=f"main {w.fix}", scope="src")
        out = self.assertRuns("park-task", status=1)
        self.assertIn("already parked", out)
        self.assertIn(first, out)
        self.assertTrue(w.learner.has_task(), "the refusal left the open task alone")
        self.assertOnBranch(second)

    def test_a_parked_branch_deleted_by_hand_does_not_strand_the_learner(self):
        w = self.w
        branch, _ = self.park_a_task()
        self.assertRuns("park-task")
        w.git("branch", "-D", branch)
        self.assertRuns("claim-session", "s2")
        out = self.assertRuns("resume-task")
        self.assertIn("gone", out)
        self.assertIn(branch, out)
        self.assertFalse(w.learner.has_parked(), "the dead pointer is cleared")
        self.assertFalse(w.learner.has_task(), "and nothing is opened")
        self.assertOnBranch("main")

    def test_park_replaces_a_parked_task_whose_branch_is_gone(self):
        w = self.w
        first, _ = self.park_a_task()
        self.assertRuns("park-task")
        w.git("branch", "-D", first)
        second, base = w.begin("setup", "--fix", w.fix)
        w.task(lesson="setup", mode="write", branch=second, base=base, return_to=f"main {w.fix}", scope="src")
        out = self.assertRuns("park-task")
        self.assertIn(first, out)
        self.assertIn("gone", out)
        self.assertEqual(w.learner.parked_task().lesson, "setup")

    def test_resume_refuses_while_a_task_is_open(self):
        w = self.w
        self.park_a_task()
        self.assertRuns("park-task")
        branch, base = w.begin("setup", "--fix", w.fix)
        w.task(lesson="setup", mode="write", branch=branch, base=base, return_to=f"main {w.fix}", scope="src")
        self.assertRuns("claim-session", "s2")
        out = self.assertRuns("resume-task", status=1)
        self.assertIn("a task is open", out)
        self.assertTrue(w.learner.has_parked())

    def test_resume_refuses_a_dirty_tree(self):
        w = self.w
        self.park_a_task()
        self.assertRuns("park-task")
        w.write("src/greet.sh", w.read("src/greet.sh") + "# their own work, uncommitted\n")
        self.assertRuns("claim-session", "s2")
        out = self.assertRuns("resume-task", status=1)
        self.assertIn("not clean", out)
        self.assertOnBranch("main")
        self.assertTrue(w.learner.has_parked())

    def test_resume_refuses_without_a_recorded_session(self):
        w = self.w
        self.park_a_task()
        self.assertRuns("park-task")
        self.assertFalse(w.learner.session.exists())
        out = self.assertRuns("resume-task", status=1)
        self.assertIn("session", out)
        self.assertTrue(w.learner.has_parked(), "nothing moved")
        self.assertOnBranch("main")

    def test_resume_stamps_the_running_session_not_an_older_one(self):
        """What 2.6a's review turned up: the session file is where a
        resume learns which session is running, and the claim used to
        leave it naming an older one whenever a task was open when it
        ran. A resumed task stamped with a dead session is a task the
        write guard does not fire for."""
        w = self.w
        self.assertRuns("claim-session", "sess-a")   # an earlier session, nothing open
        branch, base = w.begin("greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        w.held_task(branch, base)
        self.assertRuns("claim-session", "sess-b")   # this session, with the task already open
        self.assertRuns("park-task")
        out = self.assertRuns("resume-task")         # and no claim in between
        self.assertIn("tutor-session: sess-b", out)
        self.assertEqual(w.learner.task().tutor_session, "sess-b")

    @unittest.skipIf(is_root(), "root ignores the directory mode this leans on")
    def test_a_restore_that_stopped_part_way_is_finished_by_running_again(self):
        """A real interruption, provoked rather than built by hand: the
        restore cannot move a held/ it is not allowed to remove. The
        second run finishes it, and sends the learner back to where they
        were when they first asked — which the first run wrote into the
        parked copy before it switched, since by then HEAD is the task's
        own branch and there is nothing left to recompute from."""
        w = self.w
        branch, _ = self.park_a_task()
        self.assertRuns("park-task")
        w.git("switch", "-c", "side")   # where the learner is by the time they resume
        self.assertRuns("claim-session", "s2")
        w.learner.held.mkdir()
        (w.learner.held / "in-the-way").write_text("not the toolkit's", encoding="utf-8")
        os.chmod(str(w.learner.held), 0o500)
        try:
            out = self.assertRuns("resume-task", status=1)
        finally:
            os.chmod(str(w.learner.held), 0o700)
        self.assertIn("could not be put back", out)
        shutil.rmtree(str(w.learner.held))   # whatever was in the way, gone
        out = self.assertRuns("resume-task")
        self.assertIn(branch, out)
        self.assertOnBranch(branch)
        self.assertTrue(w.learner.has_task())
        self.assertFalse(w.learner.has_parked())
        self.assertTrue((w.learner.held / "tests/greet.test.sh").is_file(), "the proof can run")
        t = w.learner.task()
        self.assertEqual(t.return_to.split()[0], "side",
                         "where they were when they first asked, not where the task began")
        self.assertEqual(t.tutor_session, "s2")

    @unittest.skipIf(is_root(), "root ignores the directory mode this leans on")
    def test_a_resume_that_cannot_finish_leaves_the_task_parked(self):
        """The invariant the order of the moves holds, as against the
        recovery above: task.md is the marker, so a restore that fails
        part-way leaves a parked task, never an open one whose held test
        is still in parked/ — which would be a task whose proof can
        never run, with nothing left to say a task was parked at all."""
        w = self.w
        self.park_a_task()
        self.assertRuns("park-task")
        self.assertRuns("claim-session", "s2")
        # something the restore cannot move aside: a held/ it cannot remove
        w.learner.held.mkdir()
        (w.learner.held / "in-the-way").write_text("not the toolkit's", encoding="utf-8")
        os.chmod(str(w.learner.held), 0o500)
        try:
            out = self.assertRuns("resume-task", status=1)
        finally:
            os.chmod(str(w.learner.held), 0o700)
        self.assertIn("still parked", out)
        self.assertTrue(w.learner.has_parked(), "the task is still parked")
        self.assertFalse(w.learner.has_task(), "and never open without its held test")

    def test_show_task_says_when_a_parked_branch_is_gone(self):
        w = self.w
        branch, _ = self.park_a_task()
        self.assertRuns("park-task")
        out = self.assertRuns("show", "task")
        self.assertIn("is parked", out)
        self.assertIn(branch, out)
        w.git("branch", "-D", branch)
        out = self.assertRuns("show", "task")
        self.assertIn("gone", out)
        self.assertIn("cannot be resumed", out)

    def test_park_refuses_when_nothing_is_open(self):
        self.assertIn("no open task", self.assertRuns("park-task", status=1))

    def test_resume_refuses_when_nothing_is_parked(self):
        self.assertIn("nothing is parked", self.assertRuns("resume-task", status=1))

if __name__ == "__main__":
    unittest.main()


class CarriedIgnoreRulesTest(WorldTest):
    """#33: a repository that started ignoring its test output last month
    has starting states that do not, so the directory a learner's own run
    left turns from invisible into untracked the moment a task begins —
    dirt to the clean-tree check, and swept into end's commit. Begin
    carries the ignore rules of the branch the task returns to."""

    def setUp(self):
        super().setUp()
        w = self.w
        w.write(".gitignore", "test-results/\n")
        w.write("nested/.gitignore", "junk\n")
        w.git("add", "-A")
        w.git("commit", "-q", "-m", "ignore what a test run leaves")
        # What a learner's own test run leaves behind, invisible on their
        # branch and not ignored by the starting state at all.
        w.write("test-results/last.txt", "99 passed\n")
        w.write("nested/junk", "scratch\n")
        self.assertClean()

    def exclude_text(self) -> str:
        f = excludes.exclude_file(self.w.repo)
        return f.read_text(encoding="utf-8") if f.is_file() else ""

    def begin_one(self):
        return self.w.begin("greet-politely", "--fix", self.w.fix, "--held", "tests/greet.test.sh")

    def test_what_the_learners_branch_ignores_is_not_dirt_on_the_task_branch(self):
        w = self.w
        branch, _ = self.begin_one()
        self.assertOnBranch(branch)
        self.assertEqual(w.git("ls-files", "--", ".gitignore"), "", "the starting state has no ignore file of its own")
        self.assertTrue((w.top / "test-results" / "last.txt").is_file(), "their generated files are still there")
        self.assertClean()
        self.assertIn("test-results/", self.exclude_text())
        self.assertIn("/nested/**/junk", self.exclude_text(), "a nested pattern means what it means where it lives")

    def test_end_does_not_commit_what_their_branch_ignores(self):
        w = self.w
        branch, base = self.begin_one()
        w.held_task(branch, base)
        w.write("src/greet.sh", w.read("src/greet.sh") + "# the learner was here\n")
        self.assertRuns("end-task")
        committed = w.git("show", "--name-only", "--format=", branch).split()
        self.assertIn("src/greet.sh", committed)
        self.assertNotIn("test-results/last.txt", committed)
        self.assertNotIn("nested/junk", committed)
        self.assertTrue((w.top / "test-results" / "last.txt").is_file(), "and they still have them")

    def test_end_takes_the_block_out_again(self):
        w = self.w
        f = excludes.exclude_file(w.repo)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# the learner's own\nmy-scratch/\n", encoding="utf-8")
        branch, base = self.begin_one()
        w.held_task(branch, base)
        self.assertRuns("end-task")
        self.assertEqual(self.exclude_text(), "# the learner's own\nmy-scratch/\n", "theirs is left exactly as it was")

    def test_a_second_begin_replaces_the_block_rather_than_stacking_one(self):
        w = self.w
        branch, base = self.begin_one()
        w.held_task(branch, base)
        self.assertRuns("end-task")
        self.assertRuns("close-task")
        self.begin_one()
        self.assertEqual(self.exclude_text().count(excludes.START), 1)

    def test_close_takes_out_a_block_end_never_removed(self):
        """Off the task's branch end refuses and close goes alone (2.8),
        so close is the other place the rules must not outlive the task."""
        w = self.w
        branch, base = self.begin_one()
        w.held_task(branch, base)
        w.git("switch", "-q", "main")
        self.assertIn(excludes.START, self.exclude_text())
        self.assertRuns("close-task")
        self.assertNotIn(excludes.START, self.exclude_text())

    def test_a_seam_task_carries_them_too(self):
        """--here is the other way in, and it returns to the same branch
        the learner came from."""
        w = self.w
        w.write("tests/seam.test.sh", "echo seam\n")
        branch, base = w.begin("greet-politely", "--here", "tests/seam.test.sh")
        self.assertOnBranch(branch)
        self.assertIn("test-results/", self.exclude_text())
        self.assertTrue((w.top / "test-results" / "last.txt").is_file())
        self.assertClean()

    def test_begin_says_so_when_it_cannot_carry_them(self):
        """Never fatal: the task is begun either way, and the note is how
        the tutor learns the dirt it will see is not the learner's."""
        if is_root():
            self.skipTest("root writes anything")
        w = self.w
        f = excludes.exclude_file(w.repo)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# theirs\n", encoding="utf-8")
        # The directory, not the file: the block is written through a
        # temporary file and a rename, so the file's own mode is beside
        # the point and only the directory can stop it.
        f.parent.chmod(0o500)
        self.addCleanup(f.parent.chmod, 0o755)
        out = self.assertRuns("begin-task", "greet-politely", "--fix", w.fix, "--held", "tests/greet.test.sh")
        self.assertIn("could not be carried", out)
        self.assertIn("branch: rolling/greet-politely-", out, "and the task is begun")

    def test_close_says_so_when_it_cannot_take_them_out(self):
        """Close is the path a block most plausibly outlives its task:
        off the task's branch, end refuses and close goes alone (2.8)."""
        if is_root():
            self.skipTest("root writes anything")
        w = self.w
        branch, base = self.begin_one()
        w.held_task(branch, base)
        f = excludes.exclude_file(w.repo)
        f.parent.chmod(0o500)
        self.addCleanup(f.parent.chmod, 0o755)
        out = self.assertRuns("close-task")
        self.assertIn("could not be taken out", out)

    def test_whatever_the_block_raises_becomes_a_note(self):
        """The promise is that carrying the rules never takes a task
        down, and the codecs now make UnicodeError unreachable, so the
        guard is tested against that promise rather than against a path
        that can still reach it. The cost of getting this wrong was the
        high finding of the review: a successful begin reported as a
        failure, past the undo."""
        from rolling import excludes as ex
        from rolling.tasks import Tasks

        tasks = Tasks(self.w.repo, self.w.learner)

        def boom(*args):
            raise UnicodeEncodeError("utf-8", "\udce9", 0, 1, "on purpose")

        for name, call in (("write", lambda: tasks._carry_excludes("main 0123456")),
                           ("remove", lambda: tasks._drop_excludes())):
            real = getattr(ex, name)
            setattr(ex, name, boom)
            try:
                said = call()
            finally:
                setattr(ex, name, real)
            self.assertIn("exclude file", " ".join([said] if isinstance(said, str) else said))

    def test_a_begin_that_fails_part_way_leaves_no_block(self):
        from rolling.repo import GitError, Repo
        from rolling.tasks import Refused, Tasks

        class Broken(Repo):
            def commit(self, message, allow_empty=False, as_tool=False):
                raise GitError("commit failed on purpose")

        with self.assertRaises(Refused):
            Tasks(Broken(self.w.top), self.w.learner).begin_from_fix("greet-politely", self.w.fix, [], [])
        self.assertOnBranch("main")
        self.assertNotIn(excludes.START, self.exclude_text())

    def test_a_resume_carries_the_rules_of_the_branch_it_returns_to(self):
        """A park and a resume from somewhere else rewrite return-to, so
        the rules carried have to be that branch's and not the old one's."""
        w = self.w
        branch, base = self.begin_one()
        w.held_task(branch, base)
        self.assertRuns("park-task")
        self.assertNotIn(excludes.START, self.exclude_text(), "parking puts them back on their own branch")
        # A branch of their own with different rules, resumed from there.
        w.git("switch", "-q", "-c", "elsewhere")
        w.write(".gitignore", "elsewhere-only/\n")
        w.git("add", "-A")
        w.git("commit", "-q", "-m", "ignore something else here")
        self.assertRuns("claim-session", "s2")
        self.assertRuns("resume-task")
        text = self.exclude_text()
        self.assertIn("elsewhere-only/", text)
        self.assertNotIn("test-results/", text)
        self.assertIn("elsewhere", w.learner.task().return_to)
