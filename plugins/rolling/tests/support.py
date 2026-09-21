"""The scratch world every test builds: a git repository with a small
map and a fix in its history, under a temporary directory, with
ROLLING_DATA pointed at a sibling directory. Nothing touches a real
checkout or a real data directory.

The fixture's "code" is a shell script with a bug and a test runner the
map declares; the fix commit lowers the shouting and adds the test that
proves it, so a task can be built from it with the test held or shown.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Tuple

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
BIN = PLUGIN / "bin"
sys.path.insert(0, str(PLUGIN / "lib"))

from rolling import paths  # noqa: E402
from rolling.model import Learner  # noqa: E402
from rolling.repo import Repo  # noqa: E402

MAP = """---
name: Scratch
mode: write
commands:
  check: sh check.sh
  test: sh run-test.sh
  args: sh args.sh
  fails: sh -c 'exit 3'
operations:
  seed: sh -c 'echo seeded'
  reset: sh -c 'echo reset'
destructive:
  - reset
---

# Scratch

A scratch repository for the toolkit's tests.

## Regions

- **greeting** — the greeting script in `src/`.
- **platform** — the test runner and the checks.

## Suggested courses

### Generalist

1. platform, orientation: setup
2. greeting, working: greet-politely

## Corpus

- `src/greet.sh` is the whole product.

## Mistakes agents make here

- Shouting.
"""

SETUP_LESSON = """---
title: Setup
region: platform
depth: orientation
requires: []
assumes: [sh]
test: shown
---

Get the checks green.

## Rubric

- `check` passes.
"""

GREET_LESSON = """---
title: Greet politely
region: greeting
depth: working
requires: [setup]
assumes: [sh]
---

Make the greeting polite.

## Rubric

- The greeting is not shouted.
- A test proves it.
"""

GREET_BUGGY = "#!/bin/sh\n# greet NAME: prints a greeting. Bug: shouts.\nprintf 'HELLO %s\\n' \"$1\"\n"
GREET_FIXED = "#!/bin/sh\n# greet NAME: prints a greeting.\nprintf 'Hello %s\\n' \"$1\"\n"
GREET_TEST = "#!/bin/sh\nout=$(sh src/greet.sh pat)\n[ \"$out\" = \"Hello pat\" ] || { echo \"expected 'Hello pat', got '$out'\"; exit 1; }\necho \"greet: ok\"\n"


class ScratchWorld:
    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="rolling-test."))
        self.data = self.root / "data"
        self.repo_dir = self.root / "repo"
        self.repo_dir.mkdir()
        os.environ["ROLLING_DATA"] = str(self.data)
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test")
        self._git("config", "commit.gpgsign", "false")
        # git reports the physical path (macOS keeps temp dirs under a symlink)
        self.top = Path(self._git("rev-parse", "--show-toplevel").strip())
        self.repo = Repo(self.top)
        self._populate()
        self.learner = Learner(paths.learner_dir(self.top))

    def _populate(self) -> None:
        w = self.write
        w("src/greet.sh", GREET_BUGGY)
        w("run-test.sh", "#!/bin/sh\n[ -n \"$1\" ] || { echo 'usage: run-test.sh <file>'; exit 2; }\nsh \"$1\"\n")
        w("check.sh", "#!/bin/sh\nfor f in src/*; do head -n 1 \"$f\" | grep -q '^#!' || { echo \"$f: no shebang\"; exit 1; }; done\necho ok\n")
        w("args.sh", "#!/bin/sh\nfor a in \"$@\"; do printf '[%s]\\n' \"$a\"; done\n")
        w(".rolling/map.md", MAP)
        w(".rolling/lessons/setup.md", SETUP_LESSON)
        w(".rolling/lessons/greet-politely.md", GREET_LESSON)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "initial")
        self.pre = self._git("rev-parse", "HEAD").strip()
        w("src/greet.sh", GREET_FIXED)
        w("tests/greet.test.sh", GREET_TEST)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "fix: greet politely")
        self.fix = self._git("rev-parse", "HEAD").strip()

    # ---- helpers

    def _git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=str(self.repo_dir), capture_output=True, text=True, check=True).stdout

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=str(self.top), capture_output=True, text=True, check=False).stdout.strip()

    def write(self, rel: str, text: str) -> Path:
        p = self.top / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def read(self, rel: str) -> str:
        return (self.top / rel).read_text(encoding="utf-8")

    def sh(self, rel: str) -> str:
        return subprocess.run(["sh", rel], cwd=str(self.top), capture_output=True, text=True, check=False).stdout.strip()

    def run(self, name: str, *args: str, env: Optional[dict] = None, stdin: str = "") -> Tuple[int, str]:
        """Run bin/rolling-NAME as a session would: a subprocess, cwd the
        repository. Returns (exit status, combined output)."""
        e = dict(os.environ)
        for k, v in (env or {}).items():   # None removes a variable
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        res = subprocess.run([str(BIN / f"rolling-{name}"), *args], cwd=str(self.top), capture_output=True, text=True, input=stdin, env=e, check=False)
        return res.returncode, (res.stdout + res.stderr)

    def add_command(self, key: str, cmd: str) -> None:
        text = self.read(".rolling/map.md").replace("  args: sh args.sh\n", f"  args: sh args.sh\n  {key}: {cmd}\n", 1)
        self.write(".rolling/map.md", text)

    def restore_map(self) -> None:
        self.git("checkout", "--", ".rolling/map.md")

    def task(self, **fields) -> Path:
        """A task.md in the learner's directory. Repeated fields are lists;
        keys use underscores for hyphens. Body defaults to a brief and a source."""
        lines = []
        for k, v in fields.items():
            if k == "body":
                continue
            key = k.replace("_", "-")
            for item in (v if isinstance(v, (list, tuple)) else [v]):
                lines.append(f"{key}: {item}")
        body = fields.get("body", "## Brief\n\nDo the thing.\n\n## Source\n\nThe fix.\n")
        self.learner.dir.mkdir(parents=True, exist_ok=True)
        self.learner.task_file.write_text("---\n" + "\n".join(lines) + "\n---\n\n" + body, encoding="utf-8")
        return self.learner.task_file

    def held_task(self, branch: str, base: str, **extra) -> Path:
        """A task on the fix with its test held."""
        fields = dict(lesson="greet-politely", mode="write", branch=branch, base=base, return_to=f"main {self.fix}",
                      started="2026-09-15", tutor_session="s1", fix=self.fix, scope=["src", "tests"], verify=["check"],
                      held=["tests/greet.test.sh"], held_verify=["test tests/greet.test.sh"],
                      expect_fail_on_base=["held-verify test tests/greet.test.sh"])
        fields.update(extra)
        return self.task(**fields)

    def begin(self, *args: str) -> Tuple[str, str]:
        """rolling-begin-task, asserting success; returns (branch, base)."""
        rc, out = self.run("begin-task", *args)
        if rc != 0:
            raise AssertionError(f"begin-task failed:\n{out}")
        fields = dict(l.split(": ", 1) for l in out.split("\n") if ": " in l)
        return fields["branch"], fields["base"]

    def cleanup(self) -> None:
        subprocess.run(["chmod", "-R", "u+rwX", str(self.root)], capture_output=True, check=False)
        os.environ.pop("ROLLING_DATA", None)
        try:
            shutil.rmtree(self.root)
        except OSError as e:
            sys.stderr.write(f"scratch world left behind at {self.root}: {e}\n")


class WorldTest(unittest.TestCase):
    """A test case with a fresh scratch world per test."""

    def setUp(self) -> None:
        self.w = ScratchWorld()
        self.addCleanup(self.w.cleanup)

    def assertRuns(self, name: str, *args: str, status: int = 0, stdin: str = "") -> str:
        rc, out = self.w.run(name, *args, stdin=stdin)
        self.assertEqual(rc, status, f"rolling-{name} {' '.join(args)} exited {rc}:\n{out}")
        return out

    def assertClean(self) -> None:
        self.assertEqual(self.w.git("status", "--porcelain"), "")

    def assertOnBranch(self, name: str) -> None:
        self.assertEqual(self.w.git("symbolic-ref", "--short", "HEAD"), name)


def is_root() -> bool:
    return os.geteuid() == 0
