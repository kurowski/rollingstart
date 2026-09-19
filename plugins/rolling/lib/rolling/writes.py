"""The tutor's pen: how the model's text reaches the learner's directory.

The plugin's data directory is under ~/.claude, a path Claude Code
protects: the Edit and Write tools prompt there on every call, in every
mode short of bypassing permissions, and no allow rule pre-approves it.
A `bin/` script a skill grants runs without a prompt, so the tutor
writes its files by piping them into one. The model still authors
every byte; the script is the pen, and it will only write the tutor's
own files, named by role, never by path, so the grant lets it write
nothing else.

Writing and checking are one step: `task.md` is validated before it
lands, and a malformed one is refused with its faults, so nothing
downstream ever reads one. The tutor's session id is not the pen's to
take from the text: whatever the text says is rewritten, and the stamp
comes from the open task or the `session` file the skill's inline
claim wrote moments before. That id is what the write guard keys on.
It is not beyond the model's reach altogether (a shell can rewrite
any file here, and `rolling-claim-session` takes its id on the command
line); the plan names that exposure, and this module just declines to
be the easy route.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from . import frontmatter as fm, rules, session, validate
from .model import Learner, LoadError, Map, Task
from .repo import GitError, Repo, literal

FILES = ("task", "profile", "reference", "patch")
KINDS = ("Route", "Observation", "Intervention", "Feedback")
RUN_FIELDS = ("branch", "base", "return-to", "started", "tutor-session")   # the lines that belong to one run


class Refused(Exception):
    """Nothing was written; the message says why, in words."""


def read_stdin() -> str:
    """The text a heredoc delivers. A terminal is refused rather than
    waited on: the pen is for skills, and a skill always pipes."""
    if sys.stdin.isatty():
        raise Refused("the text arrives on standard input, as a heredoc; nothing was piped")
    return sys.stdin.read()


def write(learner: Learner, what: str, text: str, top: Path, map_dir: Path) -> List[str]:
    """Write TEXT as the learner's task, profile, or reference, checked
    first where there is a checker. Returns the lines to print."""
    if what not in FILES:
        raise Refused(f"rolling-write takes one of {', '.join(FILES)}, not '{what}'")
    if not text.strip():
        raise Refused(f"nothing to write: the {what} arrives on standard input, as a heredoc")
    if not text.endswith("\n"):
        text += "\n"
    if what == "task":
        text = _stamped(learner, text)
    dest = {"task": learner.task_file, "profile": learner.profile, "reference": learner.reference, "patch": learner.patch}[what]
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.new")
    try:
        learner.dir.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8", errors="surrogateescape")
    except OSError as e:
        raise Refused(f"the learner directory cannot be written: {e}")
    try:
        notes = _check(what, tmp, dest, learner, top, map_dir)
        os.replace(tmp, dest)
    except (Refused, OSError) as e:
        # The refusal's reason is the message whatever the cleanup does;
        # a temp file that cannot be removed is said, not left in silence.
        try:
            tmp.unlink()
        except OSError as e2:
            raise Refused(f"{e}; and the temporary copy {tmp.name} could not be removed ({e2})")
        raise Refused(str(e) if isinstance(e, Refused) else f"the learner directory cannot be written: {e}")
    return notes + [f"wrote {dest.name}"]


def patch_from_tree(learner: Learner, repo: Repo, paths: List[str]) -> List[str]:
    """The reference patch taken from the tree instead of a heredoc: the
    diff of PATHS against HEAD becomes reference.patch, and the paths
    are put back as HEAD has them, so the solution the tutor tried out
    in the tree before the task existed leaves no trace there. A
    heredoc carrying code trips the Bash tool's obfuscation check
    (braces beside quotes), and the tree is where the solution already
    was for the checks to run.

    Each path names one file, literally: no glob, no pathspec magic,
    since git would expand either into files the tutor never named. A
    file new to the repository is taken too (git's intent-to-add makes
    it diff) and removed from the tree afterwards; its content is in
    the patch. A directory the new file was in stays, even empty: git
    tracks no directory and shows none, and whether the tutor made it
    or the learner's own tooling did (a logs/ an app writes to) cannot
    be told afterwards. Everything refusable is checked before anything
    is written; a restore that fails afterwards says what is still
    changed."""
    if not paths:
        raise Refused("rolling-write patch --from-tree needs the paths the solution touched, one by one, after it")
    if learner.has_task():
        # The restore below puts the named paths back as HEAD has them.
        # With a task open those paths may hold the learner's work, and
        # the guard that keeps the tutor's editing tools out of the scope
        # cannot see a granted script; so the reference is taken from the
        # tree only before the task exists, which is when a seam task's
        # solution is tried there anyway.
        t = learner.task()
        raise Refused(f"a task is open ({t.lesson if t else '?'}); the reference is taken from the tree before the task begins (rolling-write patch --from-tree, then rolling-begin-task --here), never while the learner's work may be in it")
    seen: List[str] = []
    for p in paths:
        if not rules.is_literal_path(p):
            raise Refused(f"{p} is not a plain repository-relative path naming one file (no leading ./ or /, no .., no //, no glob, no pathspec magic)")
        if p in seen:
            raise Refused(f"{p} is listed twice")
        seen.append(p)
        fp = repo.top / p
        if fp.is_symlink() or fp.is_dir():
            raise Refused(f"{p} is a directory or a link; name the files, one by one")
    # Known to HEAD by exact name (no listing to match by eye: git quotes
    # some names in a listing, and a quoted name matches nothing).
    known = [p for p in paths if repo.in_tree("HEAD", p)]
    new = [p for p in paths if p not in known]
    for p in new:
        if not (repo.top / p).is_file():
            what = "a directory at HEAD; name the files, one by one" if repo.ok("cat-file", "-e", f"HEAD:{p}") else "neither in HEAD nor in the tree"
            raise Refused(f"{p} is {what}")
    try:
        # Intent to add makes a new file diff. It is dropped again as soon
        # as the diff is taken, whatever happened, and only for the files
        # the tutor had not already staged: `add -N` stages what it can
        # before failing, and a refusal must leave the index as it was.
        staged = repo.staged_names(new) if new else []
        unstaged = [p for p in new if p not in staged]
        try:
            if new:
                repo.run("add", "-N", "--", *literal(new))
            diff = repo.run_bytes("diff", "--binary", "HEAD", "--", *literal(paths))
            stat = [l for l in repo.run("diff", "--stat", "HEAD", "--", *literal(paths)).split("\n") if l]
        finally:
            if unstaged:
                repo.run("rm", "-q", "-f", "--cached", "--ignore-unmatch", "--", *literal(unstaged), check=False)
        if not diff.strip():
            raise Refused("nothing to take: those paths are as HEAD has them")
        learner.dir.mkdir(parents=True, exist_ok=True)
        tmp = learner.patch.with_name(f".{learner.patch.name}.{os.getpid()}.new")
        tmp.write_bytes(diff)
        os.replace(tmp, learner.patch)
    except GitError as e:
        raise Refused(f"git failed: {e}")
    except OSError as e:
        raise Refused(f"the learner directory cannot be written: {e}")
    try:
        # Every new file is leaving the tree now, so its index entry goes
        # with it, the tutor's own staging included; the finally above
        # kept that entry only because a refusal must change nothing.
        if new:
            repo.run("rm", "-q", "-f", "--cached", "--ignore-unmatch", "--", *literal(new), check=False)
        for p in new:
            (repo.top / p).unlink()
        if known:
            repo.checkout_paths("HEAD", known)
    except (GitError, OSError) as e:
        left = [p for p in repo.status_paths() if p in paths]
        raise Refused(f"{learner.patch.name} is written, but restoring the tree failed ({e}); still changed: " + (", ".join(left) or "nothing"))
    return [f"wrote {learner.patch.name} from the tree:"] + ["  " + l for l in stat] + ["restored " + ", ".join(paths) + " to HEAD" + (" (new files removed; their content is in the patch)" if new else "")]


def _stamped(learner: Learner, text: str) -> str:
    """The task with the tutor's session id as its tutor-session line,
    whatever the text said: the open task's current line if a task is
    open (claim keeps that one fresh), else the session file."""
    block = fm.block(text)
    if block is None:
        return text   # the validator will say so
    sid = _recorded_session(learner)
    if sid is None:
        raise Refused("the tutor's session is not recorded; a skill's inline rolling-claim-session records it before anything is written")
    return session.stamped(text, sid)   # replaces every tutor-session line the text carried


def _recorded_session(learner: Learner) -> Optional[str]:
    open_task = learner.task()
    candidate = open_task.tutor_session if open_task and open_task.tutor_session else _session_file(learner)
    return candidate if candidate and session.is_session_id(candidate) else None


def _session_file(learner: Learner) -> str:
    try:
        return learner.session.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _check(what: str, tmp: Path, dest: Path, learner: Learner, top: Path, map_dir: Path) -> List[str]:
    if what in ("reference", "patch"):
        return []
    if what == "task":
        results = validate.validate_task(tmp, top, map_dir, learner.held)
    else:
        results = validate.validate_profile(tmp, _regions(map_dir))
    rendered = [str(f).replace(str(tmp), str(dest)) for f in results]
    faults = [r for r, f in zip(rendered, results) if not f.warning]
    if faults:
        raise Refused("\n".join(faults) + f"\n{len(faults)} fault(s); {dest.name} not written")
    return rendered


def _regions(map_dir: Path) -> Optional[List[str]]:
    try:
        return Map.load(map_dir).regions
    except LoadError:
        return None


def note(learner: Learner, lesson: str, text: str) -> str:
    """Append an evidence entry for LESSON: a date line, then TEXT, which
    must open with its kind in bold, the way docs/profile.md shows."""
    if not rules.is_slug(lesson):
        raise Refused(f"'{lesson}' is not a lesson slug")
    body = text.strip()
    if not body:
        raise Refused("nothing to note: the entry arrives on standard input, as a heredoc")
    kind = next((k for k in KINDS if body.startswith(f"**{k}.**")), None)
    if kind is None:
        raise Refused("an evidence entry opens with its kind in bold: " + ", ".join(f"**{k}.**" for k in KINDS))
    dest = learner.evidence / f"{lesson}.md"
    if dest.is_symlink():
        raise Refused(f"evidence/{lesson}.md is a symbolic link; nothing written")
    entry = f"## {time.strftime('%Y-%m-%d')}\n\n{body}\n"
    try:
        learner.evidence.mkdir(parents=True, exist_ok=True)
        existing = dest.read_text(encoding="utf-8", errors="surrogateescape") if dest.is_file() else ""
        # A rewrite through a temporary file and a rename, never an append
        # through whatever the name has become: that is what keeps this
        # module's one promise, nothing in the learner's tree.
        tmp = dest.with_name(f".{dest.name}.{os.getpid()}.new")
        tmp.write_text(_joined(existing, entry), encoding="utf-8", errors="surrogateescape")
        os.replace(tmp, dest)
    except OSError as e:
        raise Refused(f"the learner directory cannot be written: {e}")
    return f"noted in evidence/{lesson}.md ({kind})"


def _joined(existing: str, entry: str) -> str:
    """One blank line between entries, whatever the file ended with."""
    if not existing:
        return entry
    return existing.rstrip("\n") + "\n\n" + entry


def keep_task(learner: Learner) -> str:
    """Copy the open task, minus the lines that belong to this run, to
    tasks/<lesson>/<stamp>.md, so a later session can serve it again."""
    if not learner.has_task():
        raise Refused("no open task to keep")
    task = Task.load(learner.task_file)
    if not rules.is_slug(task.lesson):
        raise Refused(f"the open task's lesson '{task.lesson}' is not a slug; nothing kept")
    text = learner.task_file.read_text(encoding="utf-8", errors="surrogateescape")
    head, fence, body = text.partition("\n---")
    kept = [l for l in head.split("\n") if l.split(":", 1)[0].strip() not in RUN_FIELDS]
    stamp = time.strftime('%Y%m%d-%H%M%S')
    dest = learner.tasks / task.lesson / f"{stamp}.md"
    n = 1
    while dest.exists():   # two keeps in one second, as the branch names handle it
        n += 1
        dest = dest.with_name(f"{stamp}-{n}.md")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(kept) + fence + body, encoding="utf-8", errors="surrogateescape")
    except OSError as e:
        raise Refused(f"the learner directory cannot be written: {e}")
    return f"kept as tasks/{task.lesson}/{dest.name}"
