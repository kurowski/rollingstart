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

from . import frontmatter as fm


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
    keys: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Lesson":
        f = fm.read(path)
        if f is None:
            raise LoadError(path, "no frontmatter block")
        return cls(
            slug=path.name[:-3], path=path, title=f.scalar("title"), region=f.scalar("region"),
            depth=f.scalar("depth"), mode=f.scalar("mode"), requires=f.list("requires"),
            assumes=f.list("assumes"), test=f.scalar("test"), keys=list(f.keys),
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
            scope=f.all("scope"), scaffold=f.all("scaffold"), setup=f.all("setup"), verify=f.all("verify"),
            held=f.all("held"), held_verify=f.all("held-verify"), expect_fail_on_base=f.all("expect-fail-on-base"),
            keys=list(f.keys),
        )

    def return_ref_and_sha(self) -> Tuple[str, str]:
        """('main', sha), or (sha, '') when the learner was detached."""
        words = self.return_to.split()
        if len(words) == 2:
            return words[0], words[1]
        return (words[0] if words else ""), ""


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
    def task_file(self) -> Path:
        return self.dir / "task.md"

    @property
    def reference(self) -> Path:
        return self.dir / "reference.md"

    @property
    def held(self) -> Path:
        return self.dir / "held"

    @property
    def aside(self) -> Path:
        return self.dir / "held-aside"

    @property
    def pending(self) -> Path:
        return self.dir / "held-aside.pending"

    def has_task(self) -> bool:
        return self.task_file.is_file()

    def task(self) -> Optional[Task]:
        try:
            return Task.load(self.task_file)
        except LoadError:
            return None
