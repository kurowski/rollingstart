"""Git, behind a small wrapper.

Every call is an argument list handed to subprocess with no shell, so
nothing here can be re-parsed. The policy (what a task may do to the
tree, what is refused) lives in the commands; this is the plumbing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional


class GitError(RuntimeError):
    pass


class Repo:
    def __init__(self, top: Path):
        self.top = top

    # ---- plumbing

    def run_bytes(self, *args: str, check: bool = True) -> bytes:
        """git ARGS in the repository; raw stdout. Raises GitError on a
        non-zero exit when check is set."""
        res = subprocess.run(
            ["git", "-c", "color.ui=false", "-c", "core.quotePath=false", *args],
            cwd=str(self.top),
            capture_output=True,
            check=False,
        )
        if check and res.returncode != 0:
            raise GitError(res.stderr.decode("utf-8", "replace").strip() or f"git {' '.join(args)} failed")
        return res.stdout

    def run(self, *args: str, check: bool = True) -> str:
        """run_bytes as text, without a final newline."""
        out = self.run_bytes(*args, check=check).decode("utf-8", "surrogateescape")
        return out[:-1] if out.endswith("\n") else out

    def ok(self, *args: str) -> bool:
        return subprocess.run(
            ["git", *args], cwd=str(self.top), capture_output=True, check=False
        ).returncode == 0

    # ---- reads

    def head(self) -> Optional[str]:
        return self.run("rev-parse", "HEAD") if self.ok("rev-parse", "--verify", "-q", "HEAD") else None

    def branch(self) -> Optional[str]:
        """The current branch, or None when detached."""
        res = subprocess.run(
            ["git", "symbolic-ref", "-q", "--short", "HEAD"],
            cwd=str(self.top), capture_output=True, text=True, check=False,
        )
        return res.stdout.strip() if res.returncode == 0 else None

    def rev_parse(self, ref: str) -> str:
        return self.run("rev-parse", ref)

    def is_commit(self, ref: str) -> bool:
        return self.ok("cat-file", "-e", f"{ref}^{{commit}}")

    def has_parent(self, sha: str) -> bool:
        return self.ok("rev-parse", "-q", "--verify", f"{sha}^")

    def is_merge(self, sha: str) -> bool:
        return self.ok("rev-parse", "-q", "--verify", f"{sha}^2")

    def touched(self, sha: str, path: str) -> bool:
        """Did commit SHA change PATH (against its first parent)?"""
        return self.run("diff", "--name-only", f"{sha}^", sha, "--", *literal([path])) != ""

    def changed_paths(self, a: str, b: str) -> List[str]:
        """The paths that differ between A and B, by their real names."""
        out = self.run_bytes("diff", "--name-only", "-z", a, b, "--").decode("utf-8", "surrogateescape")
        return [p for p in out.split("\0") if p]

    def in_tree(self, sha: str, path: str) -> bool:
        """Is PATH a file (a blob) at SHA: exact, by name, no pathspec at
        all. A directory at SHA is not a file, whatever the worktree has."""
        return self.run("cat-file", "-t", f"{sha}:{path}", check=False).strip() == "blob"

    def mode_at(self, sha: str, path: str) -> str:
        """The tree mode of PATH at SHA ('100644', '120000', '040000'…), or ''."""
        out = self.run("ls-tree", sha, "--", *literal([path]), check=False)
        return out.split()[0] if out else ""

    def staged_names(self, paths: List[str]) -> List[str]:
        """Which of PATHS the index holds, by their real names. No paths,
        no answer: an empty pathspec would list the whole index."""
        if not paths:
            return []
        out = self.run_bytes("ls-files", "-z", "--cached", "--", *literal(paths)).decode("utf-8", "surrogateescape")
        return [p for p in out.split("\0") if p]

    def show(self, sha: str, path: str) -> bytes:
        return self.run_bytes("show", f"{sha}:{path}")

    def status(self) -> List[str]:
        """Porcelain status lines, untracked files listed one by one."""
        out = self.run("status", "--porcelain", "-uall")
        return [line for line in out.split("\n") if line]

    def status_paths(self) -> List[str]:
        """The paths status reports, by their real names (NUL-separated,
        so a name git would otherwise quote comes back as itself)."""
        out = self.run_bytes("status", "--porcelain", "-uall", "-z").decode("utf-8", "surrogateescape")
        entries = out.split("\0")
        found: List[str] = []
        i = 0
        while i < len(entries):
            e = entries[i]
            if len(e) > 3:
                found.append(e[3:])
                if e[0] in "RC":   # a rename or copy: the next field is the original name
                    i += 1
            i += 1
        return found

    def status_short(self) -> List[str]:
        """Porcelain status as a person would see it (untracked directories collapsed)."""
        out = self.run("status", "--porcelain")
        return [line for line in out.split("\n") if line]

    def untracked(self) -> List[str]:
        """Untracked files by their real names (NUL-separated, so a name
        git would otherwise quote comes back as itself)."""
        out = self.run_bytes("ls-files", "-z", "--others", "--exclude-standard").decode("utf-8", "surrogateescape")
        return [name for name in out.split("\0") if name]

    def branch_exists(self, name: str) -> bool:
        return self.ok("show-ref", "--verify", "-q", f"refs/heads/{name}")

    def valid_branch_name(self, name: str) -> bool:
        return self.ok("check-ref-format", f"refs/heads/{name}")

    def subject(self, sha: str) -> str:
        return self.run("log", "-1", "--format=%s", sha, check=False)

    def short(self, sha: str) -> str:
        return self.run("rev-parse", "--short", sha)

    def staged_nonempty(self) -> bool:
        return not self.ok("diff", "--cached", "--quiet")

    def diff_stat(self, base: str) -> str:
        return self.run("--no-pager", "diff", "--stat", base, "--", ".")

    def diff(self, base: str) -> str:
        return self.run("--no-pager", "diff", base, "--", ".")

    def diff_new_file(self, path: str) -> str:
        res = subprocess.run(
            ["git", "-c", "color.ui=false", "-c", "core.quotePath=false", "--no-pager",
             "diff", "--no-index", "--no-prefix", "--", "/dev/null", path],
            cwd=str(self.top), capture_output=True, check=False,
        )
        return res.stdout.decode("utf-8", "replace")

    # ---- writes

    def switch_new(self, branch: str, start: Optional[str] = None) -> None:
        args = ["switch", "-q", "-c", branch]
        if start:
            args.append(start)
        self.run(*args)

    def switch(self, ref: str) -> None:
        self.run("switch", "-q", ref)

    def switch_detach(self, sha: str) -> None:
        self.run("switch", "-q", "--detach", sha)

    def checkout_paths(self, sha: str, paths: List[str]) -> None:
        self.run("checkout", "-q", sha, "--", *literal(paths))

    def add(self, paths: Optional[List[str]] = None) -> None:
        if paths is None:
            self.run("add", "-A")
        else:
            self.run("add", "--", *literal(paths))

    def commit(self, message: str, allow_empty: bool = False) -> None:
        args = ["commit", "-q", "-m", message]
        if allow_empty:
            args.append("--allow-empty")
        self.run(*args)


def literal(paths: List[str]) -> List[str]:
    """Paths as git pathspecs that mean exactly those names: a `*`, `?`,
    or `[` in a filename (a Next.js route is `[urlId].tsx`) is a
    character, not a pattern, and a leading `:` cannot start magic."""
    return [f":(literal){p}" for p in paths]
