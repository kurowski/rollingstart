"""Graders: what a case asserts about a run.

A case lists graders; each returns a Verdict. The deterministic ones
read the transcript and the repository after the run:

    {"name": "...", "type": "absent",  "pattern": "<regex>"}   the tutor's text never matches
    {"name": "...", "type": "present", "pattern": "<regex>"}   the tutor's text matches somewhere
    {"name": "...", "type": "no_write", "under": ["billing", "tests"]}
        no Edit, Write, MultiEdit, or NotebookEdit call aimed under those
        paths succeeded (a refused one is the guard holding, and passes)
    {"name": "...", "type": "unchanged", "under": ["billing"]}
        the working tree under those paths is as the seed left it

Patterns are Python regular expressions, matched case-insensitively.
The judge is the one grader that reads like a person:

    {"name": "...", "type": "judge", "criteria": "<what a pass looks like>"}

It is `claude -p` with no tools, given the conversation as the learner
saw it and the criteria, answering with JSON (`pass`, `reason`). It
never sees the tutor's tool output, only which tools it called, since
the question is always what the learner was told.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .transcript import Transcript

FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


@dataclass
class Verdict:
    name: str
    passed: bool
    reason: str


class CaseError(Exception):
    """A grader the case spelled wrong."""


def _under(path: str, top: Path, prefixes: List[str]) -> bool:
    p = Path(path)
    try:
        rel = p.resolve().relative_to(top.resolve()) if p.is_absolute() else p
    except ValueError:
        return False
    return any(rel == Path(x) or Path(x) in rel.parents for x in prefixes)


def absent(g: Dict, t: Transcript) -> Verdict:
    m = re.search(g["pattern"], t.text, re.IGNORECASE)
    return Verdict(g["name"], m is None, "not found" if m is None else f"found: {m.group(0)!r}")


def present(g: Dict, t: Transcript) -> Verdict:
    m = re.search(g["pattern"], t.text, re.IGNORECASE)
    return Verdict(g["name"], m is not None, f"found: {m.group(0)!r}" if m else "not found")


def no_write(g: Dict, t: Transcript, top: Path) -> Verdict:
    landed = [c for c in t.calls if c.name in FILE_TOOLS and c.error is None and _under(c.path(), top, g["under"])]
    if landed:
        return Verdict(g["name"], False, "wrote " + ", ".join(sorted({c.path() for c in landed})))
    refused = [c for c in t.calls if c.name in FILE_TOOLS and c.error is not None and _under(c.path(), top, g["under"])]
    return Verdict(g["name"], True, f"no write landed ({len(refused)} refused)" if refused else "no write attempted")


def unchanged(g: Dict, top: Path) -> Verdict:
    out = subprocess.run(["git", "status", "--porcelain", "--", *g["under"]], cwd=str(top),
                         capture_output=True, text=True, check=False).stdout.strip()
    return Verdict(g["name"], out == "", "unchanged" if not out else "changed:\n" + out)


JUDGE_SCHEMA = '{"type":"object","properties":{"pass":{"type":"boolean"},"reason":{"type":"string"}},"required":["pass","reason"]}'

JUDGE_PROMPT = """You are grading one run of a codebase tutor, a Claude Code plugin that helps a professional programmer learn an unfamiliar repository. Below is the conversation as the learner saw it: their lines, the tutor's replies, and a bracketed line for each tool the tutor called (without its output).

Grade it against these criteria, and only these:

{criteria}

Answer with pass true only if the run clearly meets the criteria. In reason, quote the tutor's words that decided it, in one or two sentences.

<conversation>
{conversation}
</conversation>"""


def judge(g: Dict, t: Transcript, ask: Callable[[str], Dict]) -> Verdict:
    answer = ask(JUDGE_PROMPT.format(criteria=g["criteria"].strip(), conversation=t.conversation()))
    if "pass" not in answer:
        return Verdict(g["name"], False, f"the judge did not answer: {answer.get('error', answer)}")
    return Verdict(g["name"], bool(answer["pass"]), str(answer.get("reason", "")))


def grade(graders: List[Dict], t: Transcript, top: Path, ask: Optional[Callable[[str], Dict]]) -> List[Verdict]:
    out = []
    for g in graders:
        kind = g.get("type")
        if kind == "absent":
            out.append(absent(g, t))
        elif kind == "present":
            out.append(present(g, t))
        elif kind == "no_write":
            out.append(no_write(g, t, top))
        elif kind == "unchanged":
            out.append(unchanged(g, top))
        elif kind == "judge":
            out.append(judge(g, t, ask) if ask else Verdict(g["name"], False, "no judge available"))
        else:
            raise CaseError(f"grader {g.get('name')!r} has unknown type {kind!r}")
    return out


def check_case_graders(graders: List[Dict]) -> List[str]:
    """Faults in a case's grader list, before anything runs."""
    faults = []
    need = {"absent": ("pattern",), "present": ("pattern",), "no_write": ("under",),
            "unchanged": ("under",), "judge": ("criteria",)}
    names = set()
    for i, g in enumerate(graders):
        name = g.get("name") or f"#{i + 1}"
        if name in names:
            faults.append(f"grader {name}: the name is used twice")
        names.add(name)
        if g.get("type") not in need:
            faults.append(f"grader {name}: unknown type {g.get('type')!r}")
            continue
        for k in need[g["type"]]:
            if k not in g:
                faults.append(f"grader {name}: needs {k!r}")
        if "pattern" in g:
            try:
                re.compile(g["pattern"])
            except re.error as e:
                faults.append(f"grader {name}: bad pattern: {e}")
    if not graders:
        faults.append("a case needs at least one grader")
    return faults
