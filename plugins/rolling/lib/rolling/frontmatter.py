"""The flat frontmatter subset docs/map.md defines, read without a YAML
parser.

A block is the lines between a `---` on line 1 and the next line that
is exactly `---` (a trailing CR is ignored, so CRLF files read as LF).
A field is `key: value` at column 1. A map is a key on its own line
followed by two-space-indented `sub: value` lines. A list is `[a, b]`
on the key's line or `  - item` lines beneath it. A key may repeat
(scope:, verify:), and every value of a repeated key is kept in order.
Values are kept verbatim: a `#` in a command is a fault the validator
reports, never a comment to strip, because the toolkit appends a
task's arguments after the command and a comment would swallow them.

The result is the block's fields in order, each one typed by what it
was: a scalar, a list, or a map. The accessors read that one list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

_KEY_LINE = re.compile(r"^([^ \t#][^:]*):(.*)$")
_SUB_LINE = re.compile(r"^  ([A-Za-z0-9_-]+):[ \t]*(.*?)[ \t]*$")
_ITEM_LINE = re.compile(r"^  - (.*?)[ \t]*$")


class Shape(Enum):
    SCALAR = "scalar"
    LIST = "list"
    MAP = "map"


@dataclass
class Field:
    key: str
    shape: Shape
    value: str = ""                                          # SCALAR
    items: List[str] = field(default_factory=list)           # LIST
    entries: List[Tuple[str, str]] = field(default_factory=list)  # MAP


@dataclass
class Frontmatter:
    fields: List[Field] = field(default_factory=list)

    @property
    def keys(self) -> List[str]:
        """Every top-level key, in order, repeats included."""
        return [f.key for f in self.fields]

    def scalar(self, key: str) -> str:
        """The first scalar value of KEY, or ''."""
        for f in self.fields:
            if f.key == key and f.shape is Shape.SCALAR:
                return f.value
        return ""

    def all(self, key: str) -> List[str]:
        """Every scalar value of a repeated KEY, in order."""
        return [f.value for f in self.fields if f.key == key and f.shape is Shape.SCALAR]

    def list(self, key: str) -> List[str]:
        return [item for f in self.fields if f.key == key and f.shape is Shape.LIST for item in f.items]

    def map(self, key: str) -> List[Tuple[str, str]]:
        return [e for f in self.fields if f.key == key and f.shape is Shape.MAP for e in f.entries]

    def map_get(self, key: str, sub: str) -> str:
        for k, v in self.map(key):
            if k == sub:
                return v
        return ""


def block(text: str) -> Optional[List[str]]:
    """The frontmatter lines without the fences, or None without a block."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        return None
    out = []
    for line in lines[1:]:
        line = line.rstrip("\r")
        if line == "---":
            return out
        out.append(line)
    return None


def has_block(text: str) -> bool:
    return block(text) is not None


def parse(text: str) -> Optional[Frontmatter]:
    """The frontmatter of TEXT, or None when it has no block."""
    lines = block(text)
    if lines is None:
        return None
    fm = Frontmatter()
    i = 0
    while i < len(lines):
        m = _KEY_LINE.match(lines[i])
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest == "":
            f, i = _indented(key, lines, i + 1)
        elif rest.startswith("["):
            f, i = Field(key, Shape.LIST, items=_flow_items(rest)), i + 1
        else:
            f, i = Field(key, Shape.SCALAR, value=rest), i + 1
        fm.fields.append(f)
    return fm


def _indented(key: str, lines: List[str], i: int) -> Tuple[Field, int]:
    """A map or a block list: the indented lines from I on. A key with
    nothing beneath it is an empty list."""
    items: List[str] = []
    entries: List[Tuple[str, str]] = []
    while i < len(lines):
        line = lines[i]
        im, sm = _ITEM_LINE.match(line), _SUB_LINE.match(line)
        if im:
            items.append(im.group(1))
        elif sm:
            entries.append((sm.group(1), sm.group(2)))
        elif line.startswith("  ") or line.strip() == "":
            pass   # not part of the subset; ignored
        else:
            break
        i += 1
    if entries and not items:
        return Field(key, Shape.MAP, entries=entries), i
    return Field(key, Shape.LIST, items=items), i


def _flow_items(rest: str) -> List[str]:
    inner = rest[1:-1] if rest.endswith("]") else rest[1:]
    return [p.strip() for p in inner.split(",") if p.strip()]


def read(path: Path) -> Optional[Frontmatter]:
    """parse() of the file at PATH; None if unreadable or without a block."""
    try:
        return parse(path.read_text(encoding="utf-8", errors="surrogateescape"))
    except OSError:
        return None


def body_has_h2(path: Path, heading: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return False
    return re.search(r"^## " + re.escape(heading) + r"[ \t]*\r?$", text, re.M) is not None


def map_regions(map_text: str) -> List[str]:
    """The bold slugs opening the bullets under `## Regions`."""
    return [m.group(1) for line in _section(map_text, r"Regions") for m in [re.match(r"^- \*\*([a-z0-9-]+)\*\*", line)] if m]


def map_courses(map_text: str) -> List[str]:
    """The `###` headings under the suggested course(s) heading."""
    return [line[4:].strip() for line in _section(map_text, r"Suggested courses?") if line.startswith("### ")]


def _section(text: str, heading_pattern: str) -> List[str]:
    """The lines under the level-2 heading matching the pattern, up to
    the next level-2 heading."""
    out: List[str] = []
    inside = False
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if re.match(r"^## " + heading_pattern + r"[ \t]*$", line):
            inside = True
            continue
        if line.startswith("## "):
            inside = False
        if inside:
            out.append(line)
    return out
