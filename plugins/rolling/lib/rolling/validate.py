"""Shape, never content: the lists at the end of docs/map.md and
docs/profile.md, as functions that return every fault they find, so a
file is fixed in one pass. A Fault names the file and says what is
wrong; a Warning is the one case the spec calls a warning (a
destination region the map does not have).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import frontmatter as fm, rules
from .frontmatter import Shape
from .model import Lesson, LoadError, Map, Task


@dataclass(frozen=True)
class Fault:
    where: str
    what: str
    warning: bool = False

    def __str__(self) -> str:
        return f"{self.where}: {'warning: ' if self.warning else ''}{self.what}"


MAP_FIELDS = ("name", "mode", "commands", "operations", "destructive")
LESSON_FIELDS = ("title", "region", "depth", "mode", "requires", "assumes", "test")
AUTHOR_TASK_FIELDS = ("mode", "scope", "scaffold", "setup", "verify", "held", "held-verify", "expect-fail-on-base", "fix")
TASK_FIELDS = ("lesson", "branch", "base", "return-to", "started", "tutor-session", "task") + AUTHOR_TASK_FIELDS

SHAPES = {
    # what shape each field must have where it appears; a scalar where a
    # list is wanted would otherwise read as an empty list and pass
    "map": {"commands": Shape.MAP, "operations": Shape.MAP, "destructive": Shape.LIST},
    "lesson": {"requires": Shape.LIST, "assumes": Shape.LIST},
}


def _shape_faults(where: str, path: Path, kind: str) -> List[Fault]:
    f = fm.read(path)
    if f is None:
        return []
    faults = []
    for fld in f.fields:
        want = SHAPES[kind].get(fld.key)
        if want is None:
            if fld.shape is not Shape.SCALAR:
                faults.append(Fault(where, f"{fld.key} is a {fld.shape.value}, but it takes one value"))
        elif fld.shape is not want:
            faults.append(Fault(where, f"{fld.key} is a {fld.shape.value}, but it must be a {want.value} ({'[a, b]' if want is Shape.LIST else 'indented key: value lines'})"))
    return faults




# ---------------------------------------------------------------- map


def validate_map(mdir: Path) -> List[Fault]:
    faults: List[Fault] = []
    mpath = mdir / "map.md"
    m: Optional[Map] = None
    try:
        m = Map.load(mdir)
    except LoadError as e:
        hint = " (a --- line first, another closing it)" if "frontmatter" in e.reason else ""
        faults.append(Fault(str(mpath), e.reason + hint))
    if m is not None:
        faults += _shape_faults(str(mpath), mpath, "map")
        faults += _map_frontmatter_faults(m)
        faults += _map_body_faults(m)

    lessons_dir = mdir / "lessons"
    lessons: Dict[str, Lesson] = {}
    if not lessons_dir.is_dir():
        faults.append(Fault(str(lessons_dir), "does not exist"))
    else:
        faults += _collect_lessons(lessons_dir, lessons)
    regions = m.regions if m else []
    for lesson in lessons.values():
        faults += _lesson_faults(lesson, regions, lessons)
    cycle = _cycle_in({s: [q for q in l.requires if q in lessons and q != s] for s, l in lessons.items()})
    if cycle:
        faults.append(Fault(str(lessons_dir), f"requires has a cycle through {cycle}"))
    for lesson in lessons.values():
        faults += _author_task_faults(lesson, m)
    return faults


def _map_frontmatter_faults(m: Map) -> List[Fault]:
    where = str(m.path)
    faults = [Fault(where, f"unknown field '{k}'") for k in m.keys if k not in MAP_FIELDS]
    if not m.name:
        faults.append(Fault(where, "name is missing"))
    if not m.mode:
        faults.append(Fault(where, "mode is missing (write or direct)"))
    elif m.mode not in rules.MODES:
        faults.append(Fault(where, f"mode '{m.mode}' is not write or direct"))
    if not m.commands:
        faults.append(Fault(where, "commands is missing or empty"))
    for key, cmd in m.commands.items():
        if not rules.is_key(key):
            faults.append(Fault(where, f"commands key '{key}' is not [a-z0-9-]+"))
        if not cmd:
            faults.append(Fault(where, f"commands.{key} has no command"))
        elif not rules.command_takes_args(cmd):
            faults.append(Fault(where, f"commands.{key} ends in an operator (; & | > < \\) or contains '#', so arguments could not be appended safely"))
    for key, cmd in m.operations.items():
        if not rules.is_key(key):
            faults.append(Fault(where, f"operations key '{key}' is not [a-z0-9-]+"))
        if not cmd:
            faults.append(Fault(where, f"operations.{key} has no command"))
    for d in m.destructive:
        if d not in m.operations:
            faults.append(Fault(where, f"destructive names '{d}', which is not an operation"))
    return faults


def _map_body_faults(m: Map) -> List[Fault]:
    where = str(m.path)
    faults: List[Fault] = []
    if not fm.body_has_h2(m.path, "Regions"):
        faults.append(Fault(where, "no ## Regions heading"))
    elif not m.regions:
        faults.append(Fault(where, "## Regions has no bullet opening with a bold slug (- **slug** ...)"))
    if not re.search(r"^## Suggested courses?[ \t]*\r?$", m.text, re.M):
        faults.append(Fault(where, "no ## Suggested courses heading"))
    elif not m.courses:
        faults.append(Fault(where, "## Suggested courses has no ### course heading under it"))
    return faults


def _collect_lessons(lessons_dir: Path, into: Dict[str, Lesson]) -> List[Fault]:
    faults: List[Fault] = []
    try:
        entries = sorted(lessons_dir.iterdir())
    except OSError:
        return [Fault(str(lessons_dir), "cannot be read")]
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_symlink():
            faults.append(Fault(str(entry), "a symbolic link; lessons/ holds regular files and task directories only"))
            continue
        if entry.is_dir():
            if not (lessons_dir / f"{entry.name}.md").is_file():
                faults.append(Fault(f"{entry}/", f"a directory in lessons/ must match a lesson file beside it ({entry.name}.md)"))
            continue
        if not entry.name.endswith(".md"):
            faults.append(Fault(str(entry), "not a lesson file (every file in lessons/ ends in .md)"))
            continue
        slug = entry.name[:-3]
        if not rules.is_slug(slug):
            faults.append(Fault(str(entry), f"'{slug}' is not a slug (lowercase kebab-case)"))
            continue
        try:
            into[slug] = Lesson.load(entry)
        except LoadError:
            faults.append(Fault(str(entry), "no frontmatter block"))
    return faults


def _lesson_faults(lesson: Lesson, regions: Sequence[str], lessons: Dict[str, Lesson]) -> List[Fault]:
    where = str(lesson.path)
    faults = [Fault(where, f"unknown field '{k}'") for k in lesson.keys if k not in LESSON_FIELDS]
    faults += _shape_faults(where, lesson.path, "lesson")
    if not lesson.title:
        faults.append(Fault(where, "title is missing"))
    if not lesson.region:
        faults.append(Fault(where, "region is missing"))
    elif regions and lesson.region not in regions:
        faults.append(Fault(where, f"region '{lesson.region}' is not in the map's ## Regions"))
    if not lesson.depth:
        faults.append(Fault(where, "depth is missing"))
    elif lesson.depth not in rules.DEPTHS:
        faults.append(Fault(where, f"depth '{lesson.depth}' is not orientation, working, or deep"))
    if lesson.mode and lesson.mode not in rules.MODES:
        faults.append(Fault(where, f"mode '{lesson.mode}' is not write or direct"))
    if lesson.test and lesson.test not in rules.TESTS:
        faults.append(Fault(where, f"test '{lesson.test}' is not held or shown"))
    seen = set()
    for q in lesson.requires:
        if q == lesson.slug:
            faults.append(Fault(where, "requires itself"))
        elif q not in lessons:
            faults.append(Fault(where, f"requires '{q}', which is not a lesson"))
        if q in seen:
            faults.append(Fault(where, f"requires '{q}' twice"))
        seen.add(q)
    if not fm.body_has_h2(lesson.path, "Rubric"):
        faults.append(Fault(where, "no ## Rubric heading"))
    return faults


def _cycle_in(edges: Dict[str, List[str]]) -> str:
    """The edge closing a cycle, as 'a -> b', or ''. Depth first, three
    states, reported once."""
    state: Dict[str, int] = {}
    found = ""

    def visit(n: str) -> None:
        nonlocal found
        state[n] = 1
        for m in edges.get(n, []):
            if found:
                return
            if state.get(m) == 1:
                found = f"{n} -> {m}"
                return
            if not state.get(m):
                visit(m)
        state[n] = 2

    for n in sorted(edges):
        if not state.get(n) and not found:
            visit(n)
    return found


def _author_task_faults(lesson: Lesson, m: Optional[Map]) -> List[Fault]:
    faults: List[Fault] = []
    tdir = lesson.task_dir
    if not tdir.is_dir():
        return faults
    for entry in sorted(tdir.iterdir()):
        if entry.name.startswith("."):
            continue
        where = str(entry)
        if entry.is_dir():
            faults.append(Fault(where, "a task directory holds task files, not directories"))
            continue
        if not entry.name.endswith(".md"):
            faults.append(Fault(where, "not a task file (ends in .md)"))
            continue
        if not rules.is_slug(entry.name[:-3]):
            faults.append(Fault(where, f"'{entry.name[:-3]}' is not a slug"))
        try:
            t = Task.load(entry)
        except LoadError:
            faults.append(Fault(where, "no frontmatter block"))
            continue
        faults += [Fault(where, f"unknown field '{k}'") for k in t.keys if k not in AUTHOR_TASK_FIELDS]
        faults += _task_command_faults(where, t, m)
        if not (fm.body_has_h2(entry, "Brief") or fm.body_has_h2(entry, "Situation")):
            faults.append(Fault(where, "no ## Brief or ## Situation heading"))
        if not fm.body_has_h2(entry, "Source"):
            faults.append(Fault(where, "no ## Source heading"))
    return faults


def _task_command_faults(where: str, t: Task, m: Optional[Map]) -> List[Fault]:
    """What a task's frontmatter gets whether it is the author's or the
    tutor's: mode, commands, arguments, operations, fix."""
    faults: List[Fault] = []
    if t.mode and t.mode not in rules.MODES:
        faults.append(Fault(where, f"mode '{t.mode}' is not write or direct"))
    for kind, lines in (("verify", t.verify), ("held-verify", t.held_verify)):
        for line in lines:
            key, _, args = line.partition(" ")
            if m is not None:
                cmd = m.commands.get(key, "")
                if not cmd:
                    faults.append(Fault(where, f"{kind} names '{key}', which is not a command in the map"))
                elif not rules.command_takes_args(cmd):
                    faults.append(Fault(where, f"{kind} names '{key}', whose command in the map ends in an operator or contains '#'"))
            if not rules.args_are_words(args):
                faults.append(Fault(where, f"{kind} line '{line}' carries a shell metacharacter, quote, or glob"))
    for op in t.setup:
        if m is not None and op not in m.operations:
            faults.append(Fault(where, f"setup names '{op}', which is not an operation in the map"))
    if t.fix and not rules.is_sha(t.fix):
        faults.append(Fault(where, f"fix '{t.fix}' is not 7 to 40 hex characters"))
    return faults


# ------------------------------------------------------------ profile


def validate_profile(path: Path, regions: Optional[Sequence[str]]) -> List[Fault]:
    """REGIONS is the map's list when a map is at hand; an unknown
    region is then a warning, not a fault. Without a map it is not
    checked."""
    where = str(path)
    if not path.is_file():
        return [Fault(where, "does not exist (no profile; /rolling:start has not run)")]
    lines = [l.rstrip("\r") for l in path.read_text(encoding="utf-8", errors="surrogateescape").split("\n")]
    faults: List[Fault] = []
    if not any(re.match(r"^# Profile[ \t]*$", l) for l in lines):
        faults.append(Fault(where, "no '# Profile' title"))
    headings = [l[3:].rstrip() for l in lines if l.startswith("## ")]
    wanted = ["Background", "Destination", "Why", "Satisfied"]
    if [h for h in headings if h in wanted] != wanted:
        faults.append(Fault(where, f"the headings ## Background, ## Destination, ## Why, ## Satisfied must be present, in that order (found: {'|'.join(headings)})"))
    seen = set()
    for line in _section(lines, "Destination"):
        m = re.match(r"^([a-z0-9]+(?:-[a-z0-9]+)*):[ \t]*(orientation|working|deep)[ \t]*$", line)
        if not m:
            faults.append(Fault(where, f"destination line is not '<region>: <orientation|working|deep>': {line}"))
            continue
        region = m.group(1)
        if region in seen:
            faults.append(Fault(where, f"destination lists '{region}' twice"))
        seen.add(region)
        if regions and region not in regions:
            faults.append(Fault(where, f"destination region '{region}' is not in the map's ## Regions", warning=True))
    for line in _section(lines, "Satisfied"):
        if not re.match(r"^- [a-z0-9]+(-[a-z0-9]+)* \([0-9]{4}-[0-9]{2}-[0-9]{2}\)[ \t]*$", line):
            faults.append(Fault(where, f"satisfied line is not '- <slug> (<YYYY-MM-DD>)': {line}"))
    return faults


def _section(lines: List[str], name: str) -> List[str]:
    out: List[str] = []
    inside = False
    for line in lines:
        if line.rstrip() == f"## {name}":
            inside = True
            continue
        if line.startswith("## "):
            inside = False
        if inside and line.strip():
            out.append(line)
    return out


# --------------------------------------------------------------- task


def validate_task(task_path: Path, top: Path, mdir: Path, held_dir: Path) -> List[Fault]:
    where = str(task_path)
    try:
        t = Task.load(task_path)
    except LoadError as e:
        return [Fault(where, e.reason + (" (no open task)" if not task_path.is_file() else ""))]
    m: Optional[Map]
    try:
        m = Map.load(mdir)
    except LoadError:
        m = None
    faults = [Fault(where, f"unknown field '{k}'") for k in t.keys if k not in TASK_FIELDS]
    for name, value in (("lesson", t.lesson), ("mode", t.mode), ("branch", t.branch), ("base", t.base),
                        ("return-to", t.return_to), ("started", t.started), ("tutor-session", t.tutor_session)):
        if not value:
            faults.append(Fault(where, f"{name} is missing"))
    if t.lesson:
        if not rules.is_slug(t.lesson):
            faults.append(Fault(where, f"lesson '{t.lesson}' is not a slug"))
        if not (mdir / "lessons" / f"{t.lesson}.md").is_file():
            faults.append(Fault(where, f"lesson '{t.lesson}' is not in the map"))
    if t.base and not rules.is_sha(t.base):
        faults.append(Fault(where, f"base '{t.base}' is not 7 to 40 hex characters"))
    faults += _return_to_faults(where, t.return_to, top)
    if t.started and not rules.is_date(t.started):
        faults.append(Fault(where, f"started '{t.started}' is not YYYY-MM-DD"))
    if t.task:
        if not rules.is_slug(t.task):
            faults.append(Fault(where, f"task '{t.task}' is not a slug"))
        elif t.lesson and not (mdir / "lessons" / t.lesson / f"{t.task}.md").is_file():
            faults.append(Fault(where, f"task '{t.task}' is not a task of lesson '{t.lesson}' ({mdir / 'lessons' / t.lesson / (t.task + '.md')} does not exist)"))
    if not t.scope:
        faults.append(Fault(where, "at least one scope: line is required"))
    for s in t.scope:
        if not rules.is_plain_relpath(s):
            faults.append(Fault(where, f"scope '{s}' is not repository-relative"))
    for s in t.scaffold:
        if not rules.is_plain_relpath(s):
            faults.append(Fault(where, f"scaffold '{s}' is not repository-relative"))
        elif not any(rules.inside_scope(s, rules.normalize_scope(sc)) for sc in t.scope if rules.normalize_scope(sc)):
            faults.append(Fault(where, f"scaffold '{s}' is not inside any scope"))
    if not t.verify:
        faults.append(Fault(where, "at least one verify: line is required"))
    faults += _task_command_faults(where, t, m)
    for e in t.expect_fail_on_base:
        kind, _, rest = e.partition(" ")
        if kind == "verify" and rest not in t.verify:
            faults.append(Fault(where, f"expect-fail-on-base '{e}' does not repeat a verify: line verbatim"))
        elif kind == "held-verify" and rest not in t.held_verify:
            faults.append(Fault(where, f"expect-fail-on-base '{e}' does not repeat a held-verify: line verbatim"))
        elif kind not in ("verify", "held-verify"):
            faults.append(Fault(where, f"expect-fail-on-base '{e}' must start with verify or held-verify"))
    seen = set()
    for h in t.held:
        if not rules.is_plain_relpath(h):
            faults.append(Fault(where, f"held '{h}' is not a plain repository-relative path"))
            continue
        if h in seen:
            faults.append(Fault(where, f"held '{h}' is listed twice"))
        seen.add(h)
        if not (held_dir / h).is_file():
            faults.append(Fault(where, f"held '{h}' has no file under held/"))
    if t.mode == "write" and not fm.body_has_h2(task_path, "Brief"):
        faults.append(Fault(where, "a write task needs a ## Brief heading"))
    if t.mode == "direct" and not fm.body_has_h2(task_path, "Situation"):
        faults.append(Fault(where, "a direct task needs a ## Situation heading"))
    if not fm.body_has_h2(task_path, "Source"):
        faults.append(Fault(where, "no ## Source heading"))
    return faults


def _return_to_faults(where: str, rt: str, top: Path) -> List[Fault]:
    if not rt:
        return []
    words = rt.split()
    if len(words) == 1:
        return [] if rules.is_sha(words[0]) else [Fault(where, f"return-to '{rt}' is neither '<ref> <sha>' nor a sha")]
    if len(words) > 2:
        return [Fault(where, f"return-to has {len(words)} words; expected '<ref> <sha>' or a sha")]
    faults: List[Fault] = []
    if not rules.is_sha(words[1]):
        faults.append(Fault(where, f"return-to's second word '{words[1]}' is not a sha"))
    ok = subprocess.run(["git", "check-ref-format", f"refs/heads/{words[0]}"], cwd=str(top), capture_output=True, check=False).returncode == 0
    if not ok:
        faults.append(Fault(where, f"return-to's first word '{words[0]}' is not a ref name"))
    return faults

