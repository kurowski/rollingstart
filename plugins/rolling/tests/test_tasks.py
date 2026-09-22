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


if __name__ == "__main__":
    unittest.main()
