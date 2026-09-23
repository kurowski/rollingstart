"""Where the map is: the tree's .rolling/, else the installed map plugin
declared for this repository, else nowhere.

The contract, as docs/map.md § "Where the map lives" states it:

- The tree wins. `.rolling/` at the top level, when it exists, is the
  map, whatever is installed.
- Else the map plugins register themselves: each one's SessionStart
  hook writes its root into its own data directory, and every plugin's
  data directory is a sibling of rolling's under one root
  (~/.claude/plugins/data/<plugin id>/). Each `root` file is read for
  the manifest at <root>/.claude-plugin/plugin.json and its
  `metadata.rolling` declaration ({"repo": <pattern>, "commit": <sha>});
  the one whose `repo` matches this repository's origin URL, normalised
  to host/owner/name, is the map. A registration whose root is gone, or
  has no manifest, no declaration, or no map.md, is skipped and said.
  Two matches is a refusal naming both, since choosing would be
  guessing. No remote means no plugin can match.
- Else no map, with the registrations listed so a learner in the wrong
  clone can tell.

Everything returned is structured (a Resolved with the directory, the
source, the registration, and notes in words); rendering is the
caller's. Nothing here raises for a bad registration or a bad
repository: a resolver that fails on someone else's file would take
every command down with it.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from . import paths

ROOT_FILE = "root"          # what a map plugin's hook writes into its data directory
MANIFEST = ".claude-plugin/plugin.json"


@dataclass
class Registration:
    """One map plugin as its data directory registers it."""
    id: str                 # the data directory's name: <plugin>-<marketplace>, encoded
    root: Path              # where the plugin's copy is, as the hook wrote it
    name: str = ""
    version: str = ""
    repo: str = ""          # the declared pattern
    commit: str = ""        # the declared sha
    problem: str = ""       # why it cannot be the map, when it cannot

    @property
    def label(self) -> str:
        """`scheduling@examples 0.4.0`: the marketplace is what the data
        directory's name carries after the plugin's own, when it does."""
        prefix = paths.encode(self.name) + "-" if self.name else ""
        market = self.id[len(prefix):] if prefix and self.id.startswith(prefix) and len(self.id) > len(prefix) else ""
        who = f"{self.name}@{market}" if market else (self.name or self.id)
        return f"{who} {self.version}".rstrip()


@dataclass
class Resolved:
    dir: Optional[Path]                 # the map directory, or None
    source: str                         # "tree", "plugin", or "none"
    plugin: Optional[Registration] = None
    notes: List[str] = field(default_factory=list)
    summary: str = ""                   # for "none": why, in one line, worded here so every command says the same

    def describe(self) -> str:
        if self.source == "tree":
            return "in tree"
        if self.source == "plugin" and self.plugin:
            return f"plugin {self.plugin.label}"
        return "none"


# ------------------------------------------------------------- remotes

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


def normalize_remote(url: str) -> str:
    """A remote URL as host/owner/name, lower-cased throughout (GitHub
    and its kind are case-insensitive): scheme, credentials, a trailing
    slash, and .git stripped, scp-style user@host:path read as
    host/path. '' for nothing usable: a local path, or a file:// URL
    with no host (file:///...), since there is nothing to declare
    against."""
    u = url.strip()
    if not u:
        return ""
    if _SCHEME.match(u):
        u = _SCHEME.sub("", u, count=1)
        host, sep, rest = u.partition("/")
        host = host.rpartition("@")[2]
        if not host:
            return ""
        u = host + (sep + rest if sep else "")
    elif ":" in u and "/" not in u.split(":", 1)[0] and not re.match(r"^[A-Za-z]:[\\/]", u):
        # scp-style user@host:path; a Windows drive (C:\...) is a path
        hostpart, _, rest = u.partition(":")
        host = hostpart.rpartition("@")[2]
        u = host + "/" + rest.lstrip("/")
    else:
        return ""      # a local path: no host, nothing to declare against
    u = u.lower().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u.rstrip("/")


def remote_url(top: Path) -> str:
    """The origin remote's URL as git has it, or ''."""
    try:
        out = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(top), capture_output=True, text=True, check=False,
        )
    except OSError:
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def matches(pattern: str, normalized: str) -> bool:
    return bool(pattern) and bool(normalized) and fnmatch.fnmatchcase(normalized, pattern.strip().lower())


# ------------------------------------------------------ registrations

def data_root(data: Optional[Path]) -> Optional[Path]:
    """The directory every plugin's data directory sits under: the
    parent of rolling's own."""
    return data.parent if data else None


def registrations(data: Optional[Path]) -> List[Registration]:
    """Every map plugin registered under the data root, problems
    included, sorted by id. Rolling's own directory has no root file
    and is skipped like any other directory without one."""
    root = data_root(data)
    if root is None:
        return []
    try:
        entries = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return []
    found: List[Registration] = []
    for entry in entries:
        marker = entry / ROOT_FILE
        if not marker.is_file():
            continue
        found.append(_read(entry.name, marker))
    return found


def _read(id_: str, marker: Path) -> Registration:
    try:
        line = marker.read_text(encoding="utf-8", errors="surrogateescape").strip().split("\n")[0].strip()
    except OSError:
        return Registration(id_, marker, problem="its root file cannot be read")
    reg = Registration(id_, Path(line) if line else marker)
    if not line or not reg.root.is_dir():
        reg.problem = f"its root is gone ({line or 'empty'}); uninstalled, or not started this session"
        return reg
    try:
        manifest = json.loads((reg.root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        reg.problem = f"no readable manifest at {reg.root / MANIFEST}"
        return reg
    if not isinstance(manifest, dict):
        reg.problem = "its manifest is not a JSON object"
        return reg
    reg.name = str(manifest.get("name") or "")
    reg.version = str(manifest.get("version") or "")
    decl = (manifest.get("metadata") or {}).get("rolling") if isinstance(manifest.get("metadata"), dict) else None
    if not isinstance(decl, dict) or not str(decl.get("repo") or "").strip():
        reg.problem = "its manifest declares no repository (metadata.rolling.repo)"
        return reg
    reg.repo = str(decl.get("repo") or "").strip()
    reg.commit = str(decl.get("commit") or "").strip()
    if not (reg.root / "map.md").is_file():
        reg.problem = f"no map.md at its root {reg.root}"
    return reg


# ------------------------------------------------------------ resolve

def resolve(top: Path, data: Optional[Path]) -> Resolved:
    tree = paths.map_dir(top)
    if tree.is_dir():
        return Resolved(tree, "tree")
    regs = registrations(data)
    url = remote_url(top)
    normalized = normalize_remote(url)
    usable = [r for r in regs if not r.problem]
    hits = [r for r in usable if matches(r.repo, normalized)]
    notes: List[str] = []
    if len(hits) == 1:
        reg = hits[0]
        notes += _commit_notes(top, reg)
        return Resolved(reg.root, "plugin", reg, notes)
    if len(hits) > 1:
        summary = ("two map plugins claim this repository (" + ", ".join(r.label for r in hits)
                   + "); uninstall all but one, or commit one of them as .rolling/")
        return Resolved(None, "none", None, [], summary)
    summary = f"{tree} does not exist in the tree, and no installed map plugin is declared for this repository"
    if data is None:
        notes.append("installed map plugins cannot be seen: ROLLING_DATA is not set")
    elif not regs:
        notes.append("no map plugin has registered under " + str(data_root(data))
                     + "; one installed during this session registers at the next session start")
    else:
        where = normalized or ("no origin remote" if not url else f"origin is a local path or file URL: {url}")
        notes.append(f"the repository is {where}; installed:")
        for r in regs:
            notes.append(f"  {r.label}: " + (r.problem if r.problem else f"for {r.repo}"))
    return Resolved(None, "none", None, notes, summary)


def _commit_notes(top: Path, reg: Registration) -> List[str]:
    """One note when the plugin's declared commit is not in this
    checkout's history, or is but is not behind HEAD."""
    if not reg.commit:
        return []
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", reg.commit):
        return [f"the map declares a commit that is not a sha ({reg.commit[:40]!r}); the author fixes the manifest"]
    if not _git_ok(top, "cat-file", "-e", f"{reg.commit}^{{commit}}"):
        return [f"the map was written against {reg.commit[:12]}, which this checkout does not have; "
                "fetch, or expect pointers to code you cannot see"]
    if not _git_ok(top, "merge-base", "--is-ancestor", reg.commit, "HEAD"):
        return [f"the map was written against {reg.commit[:12]}, which is not an ancestor of HEAD; "
                "the checkout is behind the map, so some pointers describe code it does not have yet"]
    return []


def _git_ok(top: Path, *args: str) -> bool:
    try:
        return subprocess.run(["git", *args], cwd=str(top), capture_output=True, check=False).returncode == 0
    except OSError:
        return False
