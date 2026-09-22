"""The commands the bin/rolling-* executables run.

Two exit conventions. A command a skill runs inline (show,
claim-session, session-start, diff, verify, report) always exits 0 and
reports in words, because a non-zero inline exit aborts the skill. A
command a skill runs as an action (begin-task, end-task, the checks,
close-task, export, write, note, keep-task) exits non-zero on refusal
and says what it refused.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import diff as diffmod, frontmatter as fm, heldtest, paths, reference, rules, session, validate, writes
from .model import Learner, LoadError, Map, Task
from .repo import GitError, Repo
from .tasks import Refused, Tasks
from .verifier import Report, Verifier


def say(*lines: str) -> None:
    sys.stdout.write("".join(l + "\n" for l in lines))
    sys.stdout.flush()


@dataclass
class Where:
    """Where a command runs: the repository, its map, the learner's
    directory (None when ROLLING_DATA is unset)."""
    top: Path
    learner: Optional[Learner]

    @property
    def repo(self) -> Repo:
        return Repo(self.top)

    @property
    def map_dir(self) -> Path:
        return paths.map_dir(self.top)

    def load_map(self) -> Optional[Map]:
        try:
            return Map.load(self.map_dir)
        except LoadError:
            return None


def locate() -> Optional[Where]:
    top = paths.toplevel()
    if top is None:
        return None
    ld = paths.learner_dir(top)
    return Where(top, Learner(ld) if ld else None)


def repair_first(w: Where) -> bool:
    """Finish what a killed run left behind, printing what was done: a
    held-test revert, and a reference a proof left applied. False when
    a step failed and the record was kept, so the caller refuses."""
    if w.learner is None:
        return True
    res = heldtest.revert(w.learner, w.top)
    say(*res.lines)
    lines, ok = reference.repair(w.repo, w.learner)
    say(*lines)
    return res.ok and ok


# ----------------------------------------------------------- inline


def cmd_show(args: List[str]) -> int:
    usage = "usage: rolling-show map|map-check|lessons|lesson [slug]|profile|task|reference|evidence [slug]|corpus|tree|state-dir"
    what = args[0] if args else ""
    w = locate()
    if w is None:
        say("(not inside a git repository)")
        return 0
    m = w.load_map()
    if what == "map":
        say(_file_or(w.map_dir / "map.md", f"(no map: {w.map_dir / 'map.md'} does not exist)"))
    elif what == "map-check":
        # The check a skill reads inline: the same faults rolling-check-map
        # exits 1 on, reported in words at exit 0, since a non-zero inline
        # exit aborts the skill before the tutor could say a word about them.
        faults = validate.validate_map(w.map_dir)
        if faults:
            say(*map(str, faults), f"MAP: {len(faults)} fault(s) in {w.map_dir}; the author fixes the map before a task can be built")
        else:
            say(f"MAP: ok ({w.map_dir})")
    elif what == "lessons":
        files = m.lesson_files() if m else []
        for f in files:
            say(f"### {f.name[:-3]}", *(fm.block(_read(f) or "") or []), "")
        if not files:
            say(f"(no lessons under {w.map_dir / 'lessons'}/)")
    elif what == "lesson":
        slug = args[1] if len(args) > 1 else ""
        if not slug:
            slug = w.learner.open_lesson() if w.learner else ""
            if not slug:
                say("(no open lesson: rolling-begin-lesson opens one; or name one: rolling-show lesson <slug>)")
                return 0
        if not rules.is_slug(slug):
            say(f"('{slug}' is not a lesson slug)")
        else:
            f = w.map_dir / "lessons" / f"{slug}.md"
            # The slug on the first line: the file does not carry it, and the
            # skills need it for the commands that take a lesson.
            say(f"### {slug}", _file_or(f, f"(no lesson '{slug}': {f} does not exist)"))
    elif what == "profile":
        say(_file_or(w.learner.profile, "(no profile: this is a new learner, or /rolling:start has not run)") if w.learner else f"({paths.NO_DATA_MSG})")
    elif what == "task":
        say(_file_or(w.learner.task_file, "(no open task)") if w.learner else f"({paths.NO_DATA_MSG})")
    elif what == "reference":
        # The held answer, for the tutor to relay when the learner asks for
        # it: the notes, then the diff itself (the fix's own change, or a
        # seam task's patch), so the lesson skill needs no git grant and no
        # read of the state directory.
        if w.learner is None:
            say(f"({paths.NO_DATA_MSG})")
        else:
            say(_file_or(w.learner.reference, "(no reference notes)"), "")
            try:
                t = Task.load(w.learner.task_file)
                say(reference.patch_for(w.repo, w.learner, t).decode("utf-8", "replace").rstrip("\n"))
            except LoadError as e:
                say(f"(no diff: {'no open task' if not w.learner.has_task() else e.reason})")
            except reference.NoReference as e:
                say(f"(no diff: {e})")
    elif what == "evidence":
        # What the tutor has noted about this lesson so far (the route, its
        # observations, what it showed the learner on request), so done
        # reads the change knowing it.
        slug = args[1] if len(args) > 1 else ""
        if w.learner is None:
            say(f"({paths.NO_DATA_MSG})")
        else:
            if not slug:
                slug = w.learner.open_lesson()
            if not slug:
                say("(no open lesson, so no lesson to show evidence for; name one: rolling-show evidence <slug>)")
            elif not rules.is_slug(slug):
                say(f"('{slug}' is not a lesson slug)")
            else:
                say(_file_or(w.learner.dir / "evidence" / f"{slug}.md", f"(no evidence yet for {slug})"))
    elif what == "corpus":
        say((m.body_from("Corpus") or "(the map has no ## Corpus section)") if m else "(no map)")
    elif what == "tree":
        repo = w.repo
        status = repo.status_short()
        if status:
            say(*status[:20])
            if len(status) > 20:
                say(f"(... and {len(status) - 20} more)")
        else:
            say("(clean)")
        head = repo.head()
        say(f"HEAD {head} on {repo.branch() or '(detached)'}" if head else "HEAD (no commits yet)")
    elif what == "state-dir":
        say(str(w.learner.dir) if w.learner else f"({paths.NO_DATA_MSG})")
    else:
        say(usage)
    return 0


def _read(p: Path) -> Optional[str]:
    try:
        return p.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return None


def _file_or(p: Path, absent: str) -> str:
    if not p.is_file():
        return absent
    text = _read(p)
    return f"({p.name} exists but cannot be read)" if text is None else text.rstrip("\n")


def cmd_claim_session(args: List[str]) -> int:
    sid = args[0] if args else ""
    w = locate()
    if w is None:
        say("SESSION: not recorded (not inside a git repository)")
    elif w.learner is None:
        say(f"SESSION: not recorded ({paths.NO_DATA_MSG})")
    else:
        say(session.claim(w.learner, sid))
    return 0


def cmd_session_start(args: List[str]) -> int:
    try:
        sys.stdin.read()   # the hook's event JSON; not needed
    except Exception:
        pass
    session.export_data_dir(args[0] if args else "", os.environ.get("CLAUDE_ENV_FILE"))
    return 0


def cmd_diff(args: List[str]) -> int:
    w = locate()
    if w is None:
        say("DIFF: not captured (not inside a git repository)")
        return 0
    if w.learner is None:
        say(f"DIFF: not captured ({paths.NO_DATA_MSG})")
        return 0
    if not repair_first(w):
        say("DIFF: not captured (a previous run could not be finished; see above)")
        return 0
    try:
        t = Task.load(w.learner.task_file)
    except LoadError as e:
        say(f"DIFF: not captured ({'no open task' if not w.learner.has_task() else e.reason})")
        return 0
    try:
        say(*diffmod.capture(w.repo, t).render(_diff_cap()))
    except diffmod.NotCaptured as e:
        say(f"DIFF: not captured ({e})")
    return 0


def _diff_cap() -> int:
    """ROLLING_DIFF_MAX_LINES, or the default when it is not a positive number."""
    try:
        cap = int(os.environ.get("ROLLING_DIFF_MAX_LINES", ""))
    except ValueError:
        return 3000
    return cap if cap > 0 else 3000


def _verify(w: Optional[Where], on_base: bool = False, on_reference: bool = False) -> Report:
    rep = Report(on_base=on_base, on_reference=on_reference)
    if w is None:
        rep.not_run = "not inside a git repository"
        return rep
    if w.learner is None:
        rep.not_run = paths.NO_DATA_MSG
        return rep
    if not repair_first(w):
        rep.not_run = "a previous run could not be finished; see above"
        return rep
    try:
        t = Task.load(w.learner.task_file)
    except LoadError as e:
        rep.not_run = "no open task" if not w.learner.has_task() else e.reason
        return rep
    m = w.load_map()
    if m is None:
        rep.not_run = f"no map: {w.map_dir / 'map.md'}"
        return rep
    return Verifier(w.top, w.learner, m, t, on_base=on_base, on_reference=on_reference).run()


def cmd_verify(args: List[str]) -> int:
    parser = _parser("rolling-verify")
    parser.add_argument("--on-base", action="store_true", help="the both-ways proof's first half: expected failures fail on the starting state")
    parser.add_argument("--on-reference", action="store_true", help="the second half: with the reference applied, everything passes")
    try:
        ns = parser.parse_args(args)
    except _Usage as e:
        say(str(e), "PROOF: not ok (bad arguments)")
        return 0
    if ns.on_base and ns.on_reference:
        say("one half at a time: --on-base or --on-reference", "PROOF: not ok (bad arguments)")
        return 0
    say(*_verify(locate(), on_base=ns.on_base, on_reference=ns.on_reference).render())
    return 0


class _Usage(Exception):
    pass


def _parser(prog: str) -> argparse.ArgumentParser:
    """An argparse parser that raises instead of exiting, so the caller
    keeps the command's exit convention."""
    class P(argparse.ArgumentParser):
        def error(self, message: str) -> None:  # type: ignore[override]
            raise _Usage(f"{prog}: {message}\n{self.format_usage().rstrip()}")
    return P(prog=prog, add_help=False, allow_abbrev=False)


def cmd_report(args: List[str]) -> int:
    """The done skill's one inline command: the diff, then the verifier,
    in that order, each ending in its own words whatever happens to the
    other, since a skill's inline commands start together and the tutor
    reads both halves."""
    say("## The change (working tree against the task's base)", "")
    _half("DIFF: not captured", cmd_diff)
    say("", "## Verifier", "")
    _half("VERIFIER: not run", cmd_verify)
    return 0


def _half(prefix: str, fn: Callable[[List[str]], int]) -> None:
    try:
        fn([])
    except GitError as e:
        say(f"{prefix} (git failed: {e})")
    except Exception as e:  # noqa: BLE001  the other half must still run
        say(f"{prefix} ({type(e).__name__}: {e})")


# ---------------------------------------------------------- actions


def _need(w: Optional[Where]) -> Where:
    if w is None:
        raise Refused("not inside a git repository")
    if w.learner is None:
        raise Refused(paths.NO_DATA_MSG)
    return w


def cmd_begin_task(args: List[str]) -> int:
    """rolling-begin-task <lesson> --fix <sha> [--held <path>]... [--shown <path>]...
       rolling-begin-task <lesson> --here <path>...
    Everything after --here is a path, so a path may begin with a dash;
    a --held or --shown path that does is written --held=<path>."""
    parser = _parser("rolling-begin-task")
    parser.add_argument("lesson")
    parser.add_argument("--fix", metavar="SHA", help="the fix to revert: branch from its parent")
    parser.add_argument("--held", metavar="PATH", action="append", default=[], help="a test of the fix to hold back")
    parser.add_argument("--shown", metavar="PATH", action="append", default=[], help="a test of the fix to bring forward")
    here_paths: Optional[List[str]] = None
    if "--here" in args:
        i = args.index("--here")
        args, here_paths = args[:i], args[i + 1:]
    try:
        ns = parser.parse_args(args)
    except _Usage as e:
        say(str(e))
        return 2
    if (ns.fix is None) == (here_paths is None):
        say("one of --fix <sha> or --here <path>... is required")
        return 2
    if here_paths == []:
        say("--here needs the paths the task adds, one by one, after it")
        return 2
    if here_paths is not None and (ns.held or ns.shown):
        say("--held and --shown go with --fix, not --here")
        return 2
    w = _need(locate())
    if not repair_first(w):
        say("a previous run could not be finished (see above); not starting a task")
        return 1
    tasks = Tasks(w.repo, w.learner)
    begun = tasks.begin_here(ns.lesson, here_paths) if here_paths is not None else tasks.begin_from_fix(ns.lesson, ns.fix, ns.held, ns.shown)
    say(*begun.lines())
    return 0


def cmd_begin_lesson(args: List[str]) -> int:
    """rolling-begin-lesson <slug>: record the lesson next chose as the
    open one, before any exercise exists. Refuses while a task is open
    (its lesson is the open one), and for a slug the map lacks."""
    slug = args[0] if args else ""
    w = _need(locate())
    if not rules.is_slug(slug):
        raise Refused(f"'{slug}' is not a lesson slug (lowercase kebab-case)")
    if w.learner.has_task():
        t = w.learner.task()
        raise Refused(f"a task is open ({t.lesson if t else '?'}); its lesson is the open one until rolling-close-task")
    if not (w.map_dir / "lessons" / f"{slug}.md").is_file():
        raise Refused(f"no lesson '{slug}' in the map")
    marker = w.learner.lesson_file
    if marker.is_symlink():
        raise Refused(f"{marker} is a symbolic link; the open-lesson marker is a plain file the toolkit writes, so remove the link first")
    if marker.exists() and not marker.is_file():
        raise Refused(f"{marker} is not a plain file; remove it (rolling-close-task does) and open the lesson again")
    try:
        w.learner.dir.mkdir(parents=True, exist_ok=True)
        marker.write_text(slug + "\n", encoding="utf-8")
    except OSError as e:
        raise Refused(f"the learner directory cannot be written: {e}")
    # A reference a task never got built around (the proof failed and the
    # tutor stopped) would otherwise show as this lesson's answer.
    for f in (w.learner.reference, w.learner.patch):
        if f.is_file():
            f.unlink()
            say(f"removed a leftover {f.name} from an exercise that was never served")
    say(f"LESSON: {slug} is open (no exercise built yet)")
    return 0


def cmd_end_task(args: List[str]) -> int:
    w = _need(locate())
    if not repair_first(w):
        raise Refused("a previous run could not be finished (see above); leaving nothing")
    try:
        t = Task.load(w.learner.task_file)
    except LoadError as e:
        raise Refused("no open task" if not w.learner.has_task() else f"task.md: {e.reason}")
    say(*Tasks(w.repo, w.learner).end(t))
    return 0


def cmd_close_task(args: List[str]) -> int:
    w = locate()
    if w is None:
        say("not inside a git repository; nothing closed")
        return 0
    if w.learner is None:
        say(f"{paths.NO_DATA_MSG}; nothing closed")
        return 0
    if not w.learner.dir.is_dir():
        say("no learner directory; nothing closed")
        return 0
    if not repair_first(w):
        say("note: a previous run could not be finished (see above; the reference may still be in the tree); task files removed anyway, the record kept")
    say(*Tasks(w.repo, w.learner).close())
    return 0


def cmd_write(args: List[str]) -> int:
    """rolling-write task|profile|reference|patch < the file. The tutor's pen:
    the model's text, checked, into the learner's directory. Or
    rolling-write patch --from-tree <path>..., the diff of those paths
    against HEAD, which are then restored."""
    w = _need(locate())
    try:
        if args[:2] == ["patch", "--from-tree"]:
            # Everything after --from-tree is a path, so a path may begin with a dash.
            if not repair_first(w):
                raise Refused("a previous run could not be finished (see above); not touching the tree")
            say(*writes.patch_from_tree(w.learner, w.repo, args[2:]))
        elif any(a.startswith("--from-tree") for a in args):
            raise Refused("that is spelled: rolling-write patch --from-tree <path>...")
        else:
            say(*writes.write(w.learner, args[0] if args else "", writes.read_stdin(), w.top, w.map_dir))
    except writes.Refused as e:
        raise Refused(str(e))
    return 0


def cmd_note(args: List[str]) -> int:
    """rolling-note <lesson> < the entry. Appends to evidence/<lesson>.md
    under today's date."""
    w = _need(locate())
    try:
        say(writes.note(w.learner, args[0] if args else "", writes.read_stdin()))
    except writes.Refused as e:
        raise Refused(str(e))
    return 0


def cmd_keep_task(args: List[str]) -> int:
    w = _need(locate())
    try:
        say(writes.keep_task(w.learner))
    except (writes.Refused, LoadError) as e:
        raise Refused(str(e))
    return 0


def cmd_export(args: List[str]) -> int:
    if not args:
        say("usage: rolling-export <destination-directory>")
        return 2
    dest = Path(args[0])
    w = _need(locate())
    if not w.learner.dir.is_dir():
        raise Refused(f"nothing to export: no learner directory for {w.top}")
    if dest.exists() or dest.is_symlink():
        raise Refused(f"refusing to overwrite {dest}; choose a path that does not exist")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(w.learner.dir, dest, symlinks=True)
    except OSError as e:
        raise Refused(f"copy failed: {e}")
    say(f"exported {w.learner.dir}", f"      to {dest}")
    say(*(f"  {f.relative_to(dest)}" for f in sorted(p for p in dest.rglob("*") if p.is_file())))
    return 0


def cmd_check_map(args: List[str]) -> int:
    if args:
        mdir = Path(args[0].rstrip("/") or "/")
    else:
        w = locate()
        if w is None:
            say("not inside a git repository and no directory given")
            return 2
        mdir = w.map_dir
    faults = validate.validate_map(mdir)
    if faults:
        say(*map(str, faults), f"{len(faults)} fault(s) in {mdir}")
        return 1
    m = Map.load(mdir)
    say(f"map ok: {mdir} ({len(m.lesson_files())} lessons, {len(m.regions)} regions, {len(m.courses)} courses)")
    return 0


def cmd_check_profile(args: List[str]) -> int:
    w = _need(locate())
    m = w.load_map()
    results = validate.validate_profile(w.learner.profile, m.regions if m else None)
    say(*map(str, results))
    faults = [f for f in results if not f.warning]
    if faults:
        say(f"{len(faults)} fault(s) in {w.learner.profile}")
        return 1
    say(f"profile ok: {w.learner.profile}")
    return 0


def cmd_check_task(args: List[str]) -> int:
    w = _need(locate())
    t = w.learner.task_file
    faults = validate.validate_task(t, w.top, w.map_dir, w.learner.held)
    if faults:
        say(*map(str, faults))
        if t.is_file() and w.learner.task() is not None:
            say(f"{len(faults)} fault(s) in {t}")
        return 1
    say(f"task ok: {t}")
    return 0


# -------------------------------------------------------------- main


INLINE: Dict[str, Callable[[List[str]], int]] = {
    "show": cmd_show, "claim-session": cmd_claim_session, "session-start": cmd_session_start,
    "diff": cmd_diff, "verify": cmd_verify, "report": cmd_report,
}
ACTIONS: Dict[str, Callable[[List[str]], int]] = {
    "begin-task": cmd_begin_task, "begin-lesson": cmd_begin_lesson, "end-task": cmd_end_task, "close-task": cmd_close_task,
    "export": cmd_export, "check-map": cmd_check_map, "check-profile": cmd_check_profile, "check-task": cmd_check_task,
    "write": cmd_write, "note": cmd_note, "keep-task": cmd_keep_task,
}


def main(name: str, argv: List[str]) -> int:
    """Dispatch, holding the two exit conventions whatever happens: an
    inline command reports any failure in one line and exits 0, since a
    non-zero exit would abort the skill; an action exits 1 with the
    reason. A traceback is never the report."""
    inline = name in INLINE
    fn = INLINE.get(name) or ACTIONS.get(name)
    if fn is None:
        say(f"rolling: no such command '{name}'")
        return 2
    try:
        return fn(argv)
    except Refused as e:
        say(str(e))
        return 1
    except GitError as e:
        say(f"rolling-{name}: git failed: {e}")
        return 0 if inline else 1
    except Exception as e:  # noqa: BLE001  the report must end in words, not a traceback
        say(f"rolling-{name}: failed: {type(e).__name__}: {e}")
        return 0 if inline else 1
