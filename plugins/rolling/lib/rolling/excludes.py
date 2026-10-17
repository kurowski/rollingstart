"""The exclude block: the ignore rules of the branch a task returns to,
carried into `.git/info/exclude` while the task is open.

Why, and the block's lifecycle, are in tasks.py's header. What is here
is the translation and the file.

A pattern means what it means where its `.gitignore` lives, and
`info/exclude` is read from the top of the repository, so a nested
pattern is rewritten on the way in: `node_modules` in
`apps/web/.gitignore` matches at any depth below `apps/web`, which from
the top is `/apps/web/**/node_modules`, while `/test-results` there is
anchored, which from the top is `/apps/web/test-results`. A root
pattern already means what it says. The ignore files are read out of
git at the ref rather than off disk, because the branch the task
returns to is not the branch checked out while the task is open.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import List, Optional

from .repo import GitError, Repo

START = "# rolling-start: the ignore rules of the branch this task returns to"
END = "# rolling-start: end of the carried ignore rules"
IGNORE_FILE = ".gitignore"


def exclude_file(repo: Repo) -> Path:
    """Where the block goes. The common dir, not the per-worktree one:
    info/exclude is shared, and a plain clone has only the one."""
    try:
        out = repo.run("rev-parse", "--git-common-dir").strip()
    except GitError:
        out = ".git"
    p = Path(out or ".git")
    return (p if p.is_absolute() else repo.top / p) / "info" / "exclude"


def translate(directory: str, pattern: str) -> Optional[str]:
    """PATTERN, as written in DIRECTORY's .gitignore, meaning the same
    from the top of the repository. None for a line that is not a
    pattern: a blank or a comment."""
    line = pattern.rstrip("\r")
    # git reads a comment at column zero only, so "  #x" is a pattern
    # for a file whose name starts with two spaces.
    if not line.strip() or line.startswith("#"):
        return None
    if not directory:
        return line
    bang = ""
    if line.startswith("!"):
        bang, line = "!", line[1:]
    # A slash anywhere but the end anchors a pattern to its own
    # directory; without one it matches at any depth below it. The
    # trailing slash that means "a directory only" stays either way.
    anchored = "/" in line.rstrip("/")
    body = line.lstrip("/") if anchored else line
    return bang + "/" + _literal(directory) + ("/" if anchored else "/**/") + body


def _literal(directory: str) -> str:
    """The directory as itself. A name carrying a glob character would
    otherwise widen what the pattern hides — `app[1]/.gitignore` saying
    `node_modules` would hide `app1/node_modules` as well — and hiding
    more than the learner's branch does is the direction that hides real
    dirt."""
    return re.sub(r"([*?\[\]\\])", r"\\\1", directory)


def patterns(repo: Repo, ref: str) -> List[str]:
    """Every pattern REF ignores, translated, with a comment naming the
    file each group came from. An unreadable ignore file is skipped
    rather than fatal: a block missing one file's rules shows the dirt
    that file would have hidden, which is the behaviour without any
    block at all."""
    if not ref or ref.startswith("-"):
        return []   # a ref out of a task.md the model wrote; never an option
    try:
        listed = repo.run("ls-tree", "-r", "--name-only", ref, "--").split("\n")
    except GitError:
        return []
    out: List[str] = []
    # Shallowest first, so a deeper file's negation lands after the rule
    # it overrides, as git reads them. Sorting by name alone inverts that
    # wherever a directory sorts before its own parent's file.
    files = sorted((p for p in listed if p == IGNORE_FILE or p.endswith("/" + IGNORE_FILE)),
                   key=lambda p: (p.count("/"), p))
    for path in files:
        directory = path[: -len(IGNORE_FILE)].rstrip("/")
        try:
            body = repo.show(ref, path).decode("utf-8", "replace")
        except (GitError, OSError):
            continue
        kept = [t for t in (translate(directory, l) for l in body.splitlines()) if t]
        if kept:
            out.append("# from " + path)
            out += kept
    return out


def _read(path: Path) -> str:
    """The file as it is, or "" when there is none. Anything else — it
    cannot be read, it is a directory — is the caller's to report: a
    read that failed is not an empty file, and treating it as one would
    make remove a silent no-op and let write replace the learner's own
    lines. Decoded as the toolkit decodes paths, since this is a file we
    rewrite and do not own."""
    try:
        return path.read_text(encoding="utf-8", errors="surrogateescape")
    except FileNotFoundError:
        return ""


def _without_block(text: str) -> str:
    """TEXT with the block gone, and whether one was there. A start
    marker with no end takes the rest of the file: that is a run killed
    mid-write, and what follows it is ours."""
    lines = text.split("\n")
    try:
        first = lines.index(START)
    except ValueError:
        return text
    rest = lines[first + 1:]
    try:
        last = first + 1 + rest.index(END) + 1
    except ValueError:
        last = len(lines)
    return "\n".join(lines[:first] + lines[last:])


def write(repo: Repo, ref: str) -> None:
    """The block for REF, replacing any block already there. A ref with
    no ignore files writes none, and clears one that is there. Raises
    OSError if the file cannot be read or written, which the caller
    reports: the task still works, with the dirt the rules would have
    hidden."""
    pats = patterns(repo, ref)
    path = exclude_file(repo)
    before = _read(path)
    text = _without_block(before)
    if pats:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n".join([START, "# " + ref + ", for the task that is open; rolling-end-task removes this", *pats, END]) + "\n"
    if text != before:
        _replace_text(path, text)


def remove(repo: Repo) -> bool:
    """The block out again. Returns whether one was there. Raises OSError
    if the file cannot be written."""
    path = exclude_file(repo)
    before = _read(path)
    text = _without_block(before)
    if text == before:
        return False
    _replace_text(path, text)
    return True


def _replace_text(path: Path, text: str) -> None:
    """Through a temporary file and a rename, as the toolkit writes the
    learner's own files: this one holds their excludes too, and a kill
    inside a truncating write would lose them."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".rolling.tmp")
    tmp.write_text(text, encoding="utf-8", errors="surrogateescape")
    if path.is_file():
        shutil.copymode(path, tmp)
    os.replace(tmp, path)
