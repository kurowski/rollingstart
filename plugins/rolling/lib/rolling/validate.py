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
from .model import Detour, Lesson, LoadError, Map, Task


@dataclass(frozen=True)
class Fault:
    where: str
    what: str
    warning: bool = False

    def __str__(self) -> str:
        return f"{self.where}: {'warning: ' if self.warning else ''}{self.what}"


MAP_FIELDS = ("name", "mode", "commands", "operations", "destructive")
LESSON_FIELDS = ("title", "region", "depth", "mode", "requires", "assumes", "test", "exercise")
AUTHOR_TASK_FIELDS = ("mode", "scope", "scaffold", "setup", "verify", "held", "held-verify", "expect-fail-on-base", "fix")
TASK_FIELDS = ("lesson", "branch", "base", "return-to", "started", "tutor-session", "task") + AUTHOR_TASK_FIELDS
DETOUR_FIELDS = ("gap", "returns-to", "steps")
# A step is a lesson, minus the two fields that only make sense inside a
# map: `requires` names map lessons by slug, and a step is never served
# by `next`, which is what reads it; `exercise: none` would make a step
# a walkthrough, and a gap worth a detour is worth doing something about.
STEP_FIELDS = ("title", "region", "depth", "mode", "assumes", "test")
MAX_STEPS = 3

SHAPES = {
    # what shape each field must have where it appears; a scalar where a
    # list is wanted would otherwise read as an empty list and pass
    "map": {"commands": Shape.MAP, "operations": Shape.MAP, "destructive": Shape.LIST},
    "lesson": {"requires": Shape.LIST, "assumes": Shape.LIST},
    "step": {"assumes": Shape.LIST},
    "detour": {"steps": Shape.LIST},
}


KNOWN = {"map": MAP_FIELDS, "lesson": LESSON_FIELDS, "step": STEP_FIELDS, "detour": DETOUR_FIELDS}


def _shape_faults(where: str, path: Path, kind: str) -> List[Fault]:
    """What shape each field was written in, against what it takes. A
    key that is not a field here is skipped: it is already reported as
    unknown, and saying a misspelled `requries: [a]` "takes one value"
    would be advice towards a field that does not exist."""
    f = fm.read(path)
    if f is None:
        return []
    faults = []
    for fld in f.fields:
        if fld.key not in KNOWN[kind]:
            continue
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
    if lesson.exercise and lesson.exercise != "none":
        faults.append(Fault(where, f"exercise '{lesson.exercise}' is not 'none' (leave it out to offer one)"))
    if lesson.exercise == "none" and (lesson.path.parent / lesson.slug).is_dir():
        faults.append(Fault(where, "exercise: none, but the lesson has a task directory beside it; its tasks would never be served"))
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
    if t.held_verify and not t.held:
        # Seen in the exit run: a shown test's line written as held-verify,
        # which then never runs (nothing is held) and the proof reports no
        # expected failure. The line for a test in the tree is verify.
        faults.append(Fault(where, "held-verify lines need a held: path; a test that is in the tree (shown) goes on a verify: line"))
    for op in t.setup:
        if m is not None and op not in m.operations:
            faults.append(Fault(where, f"setup names '{op}', which is not an operation in the map"))
    if t.fix and not rules.is_sha(t.fix):
        faults.append(Fault(where, f"fix '{t.fix}' is not 7 to 40 hex characters"))
    return faults


# ------------------------------------------------------------ profile


# ------------------------------------------------------------ detour


def validate_detour(path: Path, mdir: Path) -> List[Fault]:
    """A detour's plan. The steps are checked for shape only — a slug,
    at most three, none twice — and not for existing: a step the tutor
    writes is written after the plan that names it, since `rolling-write
    step` takes the detour's slug. Whether every step can be served is
    `rolling-begin-detour`'s check, which is when it has to be true."""
    where = str(path)
    try:
        d = Detour.load(path)
    except LoadError as e:
        return [Fault(where, e.reason + (" (no such detour)" if not path.is_file() else ""))]
    faults = [Fault(where, f"unknown field '{k}'") for k in d.keys if k not in DETOUR_FIELDS]
    faults += _shape_faults(where, path, "detour")
    if not d.gap:
        faults.append(Fault(where, "gap is missing: what the learner is missing, in their words"))
    if not d.returns_to:
        faults.append(Fault(where, "returns-to is missing: the lesson the detour was taken from"))
    elif not rules.is_slug(d.returns_to):
        faults.append(Fault(where, f"returns-to '{d.returns_to}' is not a slug"))
    elif not (mdir / "lessons" / f"{d.returns_to}.md").is_file():
        faults.append(Fault(where, f"returns-to '{d.returns_to}' is not a lesson in the map; a detour is taken from the course, and returns to it"))
    if not d.steps:
        faults.append(Fault(where, "steps is missing: one to three, in order"))
    elif len(d.steps) > MAX_STEPS:
        faults.append(Fault(where, f"{len(d.steps)} steps; a detour is at most {MAX_STEPS}. A gap that needs more is bigger than a detour: say so, and suggest a teammate"))
    seen = set()
    for s in d.steps:
        if not rules.is_slug(s):
            faults.append(Fault(where, f"step '{s}' is not a slug (lowercase kebab-case)"))
        elif s in seen:
            faults.append(Fault(where, f"step '{s}' is listed twice; the open step is found by its slug, so two of them leave no way to say which one is open"))
        elif s == d.returns_to:
            faults.append(Fault(where, f"step '{s}' is the lesson the detour returns to; a detour does not step through its own starting point"))
        seen.add(s)
    if not _body_text(path):
        faults.append(Fault(where, "no body: a sentence or two on why these steps, as they were proposed and agreed"))
    return faults


def validate_step(path: Path, top: Path) -> List[Fault]:
    """A step the tutor wrote: a lesson, with pointer paths that are in
    the tree. `region` and `depth` are required as any lesson's are and
    are not checked against the map's regions here, because the step's
    own file does not say which lesson it returns to; the plan does, and
    `rolling-write step` checks them against it."""
    where = str(path)
    try:
        lesson = Lesson.load(path)
    except LoadError as e:
        return [Fault(where, e.reason + (" (no such step)" if not path.is_file() else ""))]
    faults = [Fault(where, _unknown_step_field(k)) for k in lesson.keys if k not in STEP_FIELDS]
    faults += _shape_faults(where, path, "step")
    if not lesson.title:
        faults.append(Fault(where, "title is missing"))
    if not lesson.region:
        faults.append(Fault(where, "region is missing: the region of the lesson the detour returns to"))
    if not lesson.depth:
        faults.append(Fault(where, "depth is missing: the depth of the lesson the detour returns to"))
    elif lesson.depth not in rules.DEPTHS:
        faults.append(Fault(where, f"depth '{lesson.depth}' is not orientation, working, or deep"))
    if lesson.mode and lesson.mode not in rules.MODES:
        faults.append(Fault(where, f"mode '{lesson.mode}' is not write or direct"))
    if lesson.test and lesson.test not in rules.TESTS:
        faults.append(Fault(where, f"test '{lesson.test}' is not held or shown"))
    faults += _pointer_faults(where, path, top)
    if not fm.body_has_h2(path, "Rubric"):
        faults.append(Fault(where, "no ## Rubric heading; a step is served as a lesson, and a lesson says what done looks like"))
    return faults


def _unknown_step_field(key: str) -> str:
    if key == "requires":
        return "requires is for a map lesson: a step's order is the detour's steps: list, and nothing serves a step but the detour"
    if key == "exercise":
        return "exercise is for a map lesson: a step the tutor wrote offers one, since a gap worth a detour is worth doing something about"
    return f"unknown field '{key}'"


_GLOSS = re.compile(r"\s+(?:—|–|--|-)\s+|\s*:\s+")
_WRAPS = ("`", "**", "*")


def _pointer_path(item: str) -> str:
    """The path in a `- <path>` pointer line, which may be dressed.

    The section is in the body, not the frontmatter, because the paths
    are the lesson's own prose as much as a declaration — and prose is
    how they get written: the path formatted as code, and a note on
    why it matters. Every run of the detour eval wrote one that way
    (`` - `billing/invoice.py` — the Line type ``), and the first
    write was refused every time, with a message that read as the file
    being absent. So the dressing comes off here instead: a wrapping
    wrapping of backticks or asterisks in any nesting, a sentence's
    full stop, and a note after a spaced dash or a colon. The note stays in the file, where whoever reads the lesson
    reads it; only the check reads past it.

    A path that itself contains a spaced dash has to go without a note,
    which is a trade for one real case against a pathological one. The
    faults below quote what was tried, so either way the writer can
    see what the check read.
    """
    text = _GLOSS.split(item.strip(), 1)[0].strip().rstrip(".,;")
    changed = True
    while changed:                     # until stable: a bold code span
        changed = False                # wraps one kind inside another
        for wrap in _WRAPS:
            n = len(wrap)
            if text.startswith(wrap) and text.endswith(wrap) and len(text) > 2 * n:
                text = text[n:-n].strip().rstrip(".,;")
                changed = True
    return text


def _pointer_faults(where: str, path: Path, top: Path) -> List[Fault]:
    """Every `- <path>` line under `## Pointers`: a plain
    repository-relative path that is in the tree now. The step is the
    tutor's grounding in this repository, and a pointer that is not
    there grounds nothing."""
    try:
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return [Fault(where, "cannot be read")]
    if not fm.body_has_h2(path, "Pointers"):
        return [Fault(where, "no ## Pointers heading: a step names the paths it is about, as `- <path>` lines, and task builds its exercise from a seam in them")]
    pointers = fm.body_items(text, "Pointers")
    if not pointers:
        return [Fault(where, "## Pointers has no `- <path>` lines")]
    faults: List[Fault] = []
    seen = set()
    for item in pointers:
        ptr = _pointer_path(item)
        if not rules.is_plain_relpath(ptr):
            # the line itself when the parse came back with nothing, so
            # the fault quotes something the writer can recognise
            faults.append(Fault(where, f"pointer '{ptr or item.strip()}' is not a plain repository-relative path"))
            continue
        if ptr in seen:
            faults.append(Fault(where, f"pointer '{ptr}' is listed twice"))
        seen.add(ptr)
        target = top / ptr
        if not (target.is_file() or target.is_dir()):
            faults.append(Fault(where, f"pointer '{ptr}' is not in the tree"))
    return faults


def _body_text(path: Path) -> str:
    """What follows the frontmatter block, stripped."""
    try:
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return ""
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        return text.strip()
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r") == "---":
            return "\n".join(lines[i + 1:]).strip()
    return ""


# ----------------------------------------------------------- profile


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


def validate_task(task_path: Path, top: Path, mdir: Path, held_dir: Path, step_dir: Optional[Path] = None) -> List[Fault]:
    """STEP_DIR is the open detour's own directory, when one is open: a
    task's lesson may be a step the tutor wrote there, which is no
    lesson of the map's and must still validate, or a step could never
    have an exercise."""
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
        elif not (mdir / "lessons" / f"{t.lesson}.md").is_file() and not (step_dir and (step_dir / f"{t.lesson}.md").is_file()):
            faults.append(Fault(where, f"lesson '{t.lesson}' is not in the map" + (" and is no step of the open detour" if step_dir else "")))
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

