"""The things the specs describe, as objects: the map and its lessons
(docs/map.md), the learner's directory and the open task (docs/profile.md).

Loading is lenient and typed: a missing field is an empty value, so a
consumer can read a half-written file and the validator (validate.py)
can say what is wrong with it. A consumer that needs the file to be
right runs the validator first; that is what the skills do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import frontmatter as fm, rules


class LoadError(Exception):
    """A file that a consumer needs is missing, unreadable, or has no
    frontmatter. `path` and `reason` are separate so a caller can report
    them without parsing the message."""

    def __init__(self, path: Path, reason: str):
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


# ---------------------------------------------------------------- map


@dataclass
class Lesson:
    slug: str
    path: Path
    title: str = ""
    region: str = ""
    depth: str = ""
    mode: str = ""              # '' means the map's default
    requires: List[str] = field(default_factory=list)
    assumes: List[str] = field(default_factory=list)
    test: str = ""              # '' means held
    exercise: str = ""          # '' means one is offered; 'none' means the walkthrough is the lesson
    keys: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Lesson":
        f = fm.read(path)
        if f is None:
            raise LoadError(path, "no frontmatter block")
        return cls(
            slug=path.name[:-3], path=path, title=f.scalar("title"), region=f.scalar("region"),
            depth=f.scalar("depth"), mode=f.scalar("mode"), requires=f.list("requires"),
            assumes=f.list("assumes"), test=f.scalar("test"), exercise=f.scalar("exercise"), keys=list(f.keys),
        )

    @property
    def task_dir(self) -> Path:
        return self.path.with_name(self.slug)


@dataclass
class Map:
    dir: Path
    name: str = ""
    mode: str = ""
    commands: Dict[str, str] = field(default_factory=dict)
    operations: Dict[str, str] = field(default_factory=dict)
    destructive: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=list)
    courses: List[str] = field(default_factory=list)
    keys: List[str] = field(default_factory=list)
    text: str = ""

    @property
    def path(self) -> Path:
        return self.dir / "map.md"

    @property
    def lessons_dir(self) -> Path:
        return self.dir / "lessons"

    @classmethod
    def load(cls, mdir: Path) -> "Map":
        path = mdir / "map.md"
        try:
            text = path.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError:
            raise LoadError(path, "does not exist") from None
        f = fm.parse(text)
        if f is None:
            raise LoadError(path, "no frontmatter block")
        return cls(
            dir=mdir, name=f.scalar("name"), mode=f.scalar("mode"),
            commands=dict(f.map("commands")), operations=dict(f.map("operations")),
            destructive=f.list("destructive"), regions=fm.map_regions(text),
            courses=fm.map_courses(text), keys=list(f.keys), text=text,
        )

    def lesson_files(self) -> List[Path]:
        try:
            entries = list(self.lessons_dir.iterdir())
        except OSError:
            return []
        return sorted(p for p in entries if p.is_file() and not p.is_symlink() and p.name.endswith(".md") and not p.name.startswith("."))

    def lesson(self, slug: str) -> Optional[Lesson]:
        p = self.lessons_dir / f"{slug}.md"
        return Lesson.load(p) if p.is_file() else None

    def body_from(self, heading: str) -> str:
        """The map's text from `## HEADING` to the end, or ''."""
        lines = self.text.split("\n")
        for i, line in enumerate(lines):
            if line.rstrip("\r").rstrip() == f"## {heading}":
                return "\n".join(lines[i:]).rstrip("\n")
        return ""


# ---------------------------------------------------------- the task


@dataclass
class Task:
    path: Path
    lesson: str = ""
    mode: str = ""
    branch: str = ""
    base: str = ""
    return_to: str = ""
    started: str = ""
    tutor_session: str = ""
    task: str = ""
    fix: str = ""
    scope: List[str] = field(default_factory=list)
    scaffold: List[str] = field(default_factory=list)
    setup: List[str] = field(default_factory=list)
    reference_setup: List[str] = field(default_factory=list)
    verify: List[str] = field(default_factory=list)
    held: List[str] = field(default_factory=list)
    held_verify: List[str] = field(default_factory=list)
    expect_fail_on_base: List[str] = field(default_factory=list)
    keys: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Task":
        if not path.is_file():
            raise LoadError(path, "does not exist")
        try:
            text = path.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError as e:
            raise LoadError(path, f"cannot be read ({e.strerror})") from None
        f = fm.parse(text)
        if f is None:
            raise LoadError(path, "no frontmatter block")
        return cls(
            path=path, lesson=f.scalar("lesson"), mode=f.scalar("mode"), branch=f.scalar("branch"),
            base=f.scalar("base"), return_to=f.scalar("return-to"), started=f.scalar("started"),
            tutor_session=f.scalar("tutor-session"), task=f.scalar("task"), fix=f.scalar("fix"),
            scope=f.all("scope"), scaffold=f.all("scaffold"), setup=f.all("setup"),
            reference_setup=f.all("reference-setup"), verify=f.all("verify"),
            held=f.all("held"), held_verify=f.all("held-verify"), expect_fail_on_base=f.all("expect-fail-on-base"),
            keys=list(f.keys),
        )

    def return_ref_and_sha(self) -> Tuple[str, str]:
        """('main', sha), or (sha, '') when the learner was detached."""
        words = self.return_to.split()
        if len(words) == 2:
            return words[0], words[1]
        return (words[0] if words else ""), ""


# -------------------------------------------------------- the detour


@dataclass
class Detour:
    """A detour's plan (docs/profile.md § `detours/`): the gap in the
    learner's words, the lesson it returns to, and its one to three
    steps in order. Loaded leniently like everything here; the pen
    validates before it lands."""
    path: Path
    gap: str = ""
    returns_to: str = ""
    steps: List[str] = field(default_factory=list)
    keys: List[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.path.name[:-3] if self.path.name.endswith(".md") else self.path.name

    @classmethod
    def load(cls, path: Path) -> "Detour":
        if not path.is_file():
            raise LoadError(path, "does not exist")
        try:
            text = path.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError as e:
            raise LoadError(path, f"cannot be read ({e.strerror})") from None
        f = fm.parse(text)
        if f is None:
            raise LoadError(path, "no frontmatter block")
        return cls(path=path, gap=f.scalar("gap"), returns_to=f.scalar("returns-to"),
                   steps=f.list("steps"), keys=list(f.keys))

    def step_after(self, step: str) -> Optional[str]:
        """The step following STEP, or None when it is the last one or
        not one of ours. Position is read from the slug, which is why
        the pen refuses the same slug twice."""
        try:
            i = self.steps.index(step)
        except ValueError:
            return None
        return self.steps[i + 1] if i + 1 < len(self.steps) else None

    def has_step(self, step: str) -> bool:
        return step in self.steps


# -------------------------------------------------- the learner's dir


@dataclass
class Learner:
    """The learner's directory for one repository, and the files in it."""
    dir: Path

    @property
    def profile(self) -> Path:
        return self.dir / "profile.md"

    @property
    def session(self) -> Path:
        return self.dir / "session"

    @property
    def lesson_file(self) -> Path:
        """The open lesson's slug, one line: written when next chooses it,
        before any exercise exists, and removed with the task."""
        return self.dir / "lesson"

    @property
    def task_file(self) -> Path:
        return self.dir / "task.md"

    @property
    def reference(self) -> Path:
        return self.dir / "reference.md"

    @property
    def patch(self) -> Path:
        return self.dir / "reference.patch"

    @property
    def applied_patch(self) -> Path:
        """The copy of the reference a proof applied, present only while
        it is in the tree (or after a kill, until repaired)."""
        return self.dir / ".reference.applied.patch"

    @property
    def applied_at(self) -> Path:
        """The commit that copy was applied on, beside it."""
        return self.dir / ".reference.applied.at"

    @property
    def held(self) -> Path:
        return self.dir / "held"

    @property
    def aside(self) -> Path:
        return self.dir / "held-aside"

    @property
    def pending(self) -> Path:
        return self.dir / "held-aside.pending"

    @property
    def parked(self) -> Path:
        """The task set aside while a detour runs, holding the files it
        was made of; parked/task.md is what says one is parked."""
        return self.dir / "parked"

    @property
    def detours(self) -> Path:
        """The detours the tutor has written: `<slug>.md` is a plan, and
        `<slug>/` holds the steps written for it."""
        return self.dir / "detours"

    @property
    def open_detour_file(self) -> Path:
        """The open detour's slug, one line, while one is open; the open
        step's own slug is in the `lesson` marker, as any lesson's is."""
        return self.dir / "open-detour"

    @property
    def evidence(self) -> Path:
        return self.dir / "evidence"

    @property
    def tasks(self) -> Path:
        return self.dir / "tasks"

    def has_task(self) -> bool:
        return self.task_file.is_file()

    def open_lesson(self) -> str:
        """The open lesson's slug: the task's when one is open, else the
        marker's, else ''."""
        t = self.task()
        if t is not None and t.lesson:
            return t.lesson
        try:
            slug = self.lesson_file.read_text(encoding="utf-8", errors="surrogateescape").strip()
        except (OSError, ValueError):
            return ""
        return slug if rules.is_slug(slug) else ""

    def task(self) -> Optional[Task]:
        try:
            return Task.load(self.task_file)
        except LoadError:
            return None

    def open_detour(self) -> str:
        """The open detour's slug, or '' when none is open or the marker
        holds something that is not a slug."""
        try:
            slug = self.open_detour_file.read_text(encoding="utf-8", errors="surrogateescape").strip()
        except (OSError, ValueError):
            return ""
        return slug if rules.is_slug(slug) else ""

    def detour_plan(self, slug: str) -> Optional[Detour]:
        if not rules.is_slug(slug):
            return None
        try:
            return Detour.load(self.detours / f"{slug}.md")
        except LoadError:
            return None

    def detour(self) -> Optional[Detour]:
        """The open detour's plan, or None."""
        slug = self.open_detour()
        return self.detour_plan(slug) if slug else None

    def step_dir(self, detour: str) -> Path:
        """Where a detour's own steps live. The caller has checked the
        slug: every path into here comes through `rules.is_slug` at the
        command's edge, or through `steps` in a plan the validator has
        already faulted a non-slug in."""
        return self.detours / detour

    def step_file(self, detour: str, step: str) -> Path:
        """One step's lesson file; the slug caveat on step_dir applies."""
        return self.detours / detour / f"{step}.md"

    def open_step_dir(self) -> Optional[Path]:
        """Where the open detour's own steps live, or None when no detour
        is open. The task validator takes it: a task's lesson may be a
        step the tutor wrote, which is no lesson of the map's."""
        slug = self.open_detour()
        return self.step_dir(slug) if slug else None

    def has_parked(self) -> bool:
        return (self.parked / "task.md").is_file()

    def parked_task(self) -> Optional[Task]:
        try:
            return Task.load(self.parked / "task.md")
        except LoadError:
            return None
