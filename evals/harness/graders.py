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
    {"name": "...", "type": "learner_file", "file": "profile.md", "pattern": "<regex>"}
        a file in the learner's directory, after the run, matches;
        with "absent": true, no such file exists or none matches.
        `file` may be a glob (`evidence/*.md`), and then any file it
        names may match. The files: `lesson`, the open lesson's slug;
        `evidence/<lesson>.md`; `profile.md`; `task.md`
    {"name": "...", "type": "command", "pattern": "<regex>"}
        a Bash command the tutor ran, and that worked, matches. For a
        mechanism its words cannot prove it used: a tutor can describe
        a detour it never took and a judge reading the conversation
        will believe it. Deliberately not the mirror of no_command,
        which counts a refused attempt because reaching for the thing
        is the violation it looks for; here a refused attempt is the
        opposite of proof, and counting it would pass exactly the runs
        whose mechanism never ran. Same heredoc rule as below
    {"name": "...", "type": "no_command", "pattern": "<regex>"}
        no Bash command the tutor ran matches (whether or not it worked:
        trying is the thing measured). A toolkit command's heredoc body
        is not judged: it is text the pen writes (a note recording what
        the learner asked for would otherwise match what it describes).
        The command itself (a claim of the session, say), and anything
        after the heredoc's terminator, still count
    {"name": "...", "type": "asked", "pattern": "<regex>", "reason": "<regex>"}
        a Bash command the tutor ran matched PATTERN and came back
        refused, with REASON matching the refusal's own text. What a
        hook's `ask` looks like from inside a run: print mode has
        nobody to answer a prompt, so an `ask` arrives as a refusal
        carrying the hook's reason, and that reason is what tells it
        from any other refusal. A matching command that worked fails
        it, whatever else was refused: the hook let the thing through.
        So PATTERN must name the *running* of the thing and not a
        mention of it — `python3 scripts/reset\\.py`, never
        `reset\\.py`, which a `cat` of the file would match and fail
    {"name": "...", "type": "no_stop_block"}
        no Stop hook kept a turn going: the citation check found every
        `path:line` the tutor said on its first try
    {"name": "...", "type": "only_markers", "path": "tests/x.py", "pattern": "<regex>"}
        the file at PATH, against HEAD, gained only lines that match
        (a blank line is fine) and lost none; untouched passes. The
        pattern should describe the whole line (`^\\s*#`, a comment
        line, since a marker may wrap), or code with a marker tacked on
        the end passes

Patterns are Python regular expressions, matched case-insensitively.
The judge is the one grader that reads like a person:

    {"name": "...", "type": "judge", "criteria": "<what a pass looks like>"}

It is `claude -p` with no tools, given the conversation as the learner
saw it and the criteria, answering with JSON (`pass`, `reason`). It
never sees the tutor's tool output, only which tools it called, since
the question is usually what the learner was told. When it is instead
what the tutor recorded (`next`'s Route note, which the learner never
sees), `"notes": "<glob>"` adds those files from the learner's
directory, marked as the tutor's own notes. When it is whether the
tutor said only what it saw, `"tool_output": true` shows each call's
output under its line.
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


def command(g: Dict, t: Transcript) -> Verdict:
    ran = [_judged(str(c.input.get("command", ""))) for c in t.calls if c.name == "Bash" and c.error is None]
    hits = [cmd for cmd in ran if re.search(g["pattern"], cmd, re.IGNORECASE)]
    if hits:
        return Verdict(g["name"], True, "ran: " + _first(hits[0]))
    return Verdict(g["name"], False, f"none of the {len(ran)} commands that worked matched")


def no_command(g: Dict, t: Transcript) -> Verdict:
    ran = [_judged(str(c.input.get("command", ""))) for c in t.calls if c.name == "Bash"]
    hits = [cmd for cmd in ran if re.search(g["pattern"], cmd, re.IGNORECASE)]
    if hits:
        return Verdict(g["name"], False, "ran: " + _first(hits[0]))
    return Verdict(g["name"], True, f"none of {len(ran)} commands matched")


def _first(cmd: str) -> str:
    """CMD's first line, for a reason line. A pattern with a stray `|`
    matches the empty string, which has no first line."""
    return (cmd.splitlines() or [""])[0][:200]


def _judged(cmd: str) -> str:
    """CMD without the heredoc body of a toolkit command."""
    lines = cmd.lstrip().split("\n")
    opener = re.search(r"<<-?\s*['\"]?(\w+)['\"]?\s*$", lines[0])
    if not lines[0].startswith("rolling-") or opener is None:
        return cmd
    word = opener.group(1)
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == word), len(lines))
    return "\n".join([lines[0], *lines[end + 1:]])


def asked(g: Dict, t: Transcript) -> Verdict:
    """A command that was tried and came back refused, for the reason
    given.

    Every match has to be a refusal for that reason, not just one of
    them: a tutor refused once that then finds a spelling the hook does
    not catch has run the thing, which is the failure this grader
    exists to see. And a match that came back as an error for any other
    reason fails it too, because the transcript marks a non-zero exit
    the same way it marks a denial, so a call that ran the operation
    and then failed is indistinguishable from one that was stopped --
    except by the reason."""
    tried = [c for c in t.calls if c.name == "Bash"
             and re.search(g["pattern"], _judged(str(c.input.get("command", ""))), re.IGNORECASE)]
    if not tried:
        return Verdict(g["name"], False, "the command was never run")
    want = g.get("reason", "")
    for c in tried:
        if c.error is None:
            return Verdict(g["name"], False, "nothing was asked, it ran: " + _first(str(c.input.get("command", ""))))
        if want and not re.search(want, c.error, re.IGNORECASE):
            return Verdict(g["name"], False, "came back for another reason: " + _first(c.error))
    return Verdict(g["name"], True, f"refused, {len(tried)} time(s): " + _first(tried[0].error or ""))


def no_stop_block(g: Dict, t: Transcript) -> Verdict:
    if t.stop_blocks:
        return Verdict(g["name"], False, "blocked: " + " | ".join(b.replace("\n", " ") for b in t.stop_blocks))
    return Verdict(g["name"], True, "no stop was blocked")


def only_markers(g: Dict, top: Path) -> Verdict:
    rel = g["path"]
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel], cwd=str(top),
                             capture_output=True, check=False).returncode == 0
    if tracked:
        diff = subprocess.run(["git", "diff", "-U0", "HEAD", "--", rel], cwd=str(top),
                              capture_output=True, text=True, check=False).stdout
        lines = diff.splitlines()
        added = [l[1:] for l in lines if l.startswith("+") and not l.startswith("+++")]
        removed = [l[1:] for l in lines if l.startswith("-") and not l.startswith("---")]
    elif (top / rel).is_file():
        added, removed = (top / rel).read_text(encoding="utf-8").splitlines(), []
    else:
        added, removed = [], []
    if not added and not removed:
        return Verdict(g["name"], True, f"{rel} untouched")
    if removed:
        return Verdict(g["name"], False, f"{rel} lost a line: {removed[0]!r}")
    other = [l for l in added if l.strip() and not re.search(g["pattern"], l, re.IGNORECASE)]
    if other:
        return Verdict(g["name"], False, f"{rel} gained {len(other)} other line(s), first: {other[0]!r}")
    return Verdict(g["name"], True, f"{rel} gained only markers ({len([l for l in added if l.strip()])})")


def _learner_files(learner: Optional[Path], pattern: str) -> List[Path]:
    return sorted(p for p in learner.glob(pattern) if p.is_file()) if learner else []


def learner_file(g: Dict, learner: Optional[Path]) -> Verdict:
    if learner is None:   # never a pass: an absence the harness could not look for is not an absence
        return Verdict(g["name"], False, "no learner directory was found")
    files = _learner_files(learner, g["file"])
    want = not g.get("absent", False)
    if not files:
        return Verdict(g["name"], not want, f"{g['file']} does not exist")
    for f in files:
        found = re.search(g["pattern"], f.read_text(encoding="utf-8"), re.IGNORECASE | re.MULTILINE)
        if found:
            return Verdict(g["name"], want, f"found in {f.name}: {found.group(0)!r}")
    return Verdict(g["name"], not want, f"not found in {', '.join(f.name for f in files)}")


def unchanged(g: Dict, top: Path) -> Verdict:
    out = subprocess.run(["git", "status", "--porcelain", "--", *g["under"]], cwd=str(top),
                         capture_output=True, text=True, check=False).stdout.strip()
    return Verdict(g["name"], out == "", "unchanged" if not out else "changed:\n" + out)


JUDGE_SCHEMA = '{"type":"object","properties":{"pass":{"type":"boolean"},"reason":{"type":"string"}},"required":["pass","reason"]}'

SHOWN_CALLS = "without its output"
SHOWN_OUTPUT = "with what it returned under it, which the learner did not see"

JUDGE_PROMPT = """You are grading one run of a codebase tutor, a Claude Code plugin that helps a professional programmer learn an unfamiliar repository. Below is the conversation as the learner saw it: their lines, the tutor's replies, and a bracketed line for each tool the tutor called ({shown}).

Grade it against these criteria, and only these:

{criteria}

Answer with pass true only if the run clearly meets the criteria. In reason, quote the tutor's words that decided it, in one or two sentences.

<conversation>
{conversation}
</conversation>{notes}"""


def judge(g: Dict, t: Transcript, ask: Callable[[str], Dict], learner: Optional[Path] = None) -> Verdict:
    notes = ""
    if g.get("notes"):
        files = _learner_files(learner, g["notes"])
        if learner is None:
            body = "(the learner directory was not found)"
        else:
            body = "\n\n".join(f"## {f.relative_to(learner)}\n{f.read_text(encoding='utf-8')}" for f in files) or "(none were written)"
        notes = f"\n\n<tutor_notes description=\"what the tutor recorded for itself; the learner never sees these\">\n{body}\n</tutor_notes>"
    answer = ask(JUDGE_PROMPT.format(criteria=g["criteria"].strip(), conversation=t.conversation(bool(g.get("tool_output"))),
                                     notes=notes, shown=SHOWN_OUTPUT if g.get("tool_output") else SHOWN_CALLS))
    if "pass" not in answer:
        return Verdict(g["name"], False, f"the judge did not answer: {answer.get('error', answer)}")
    return Verdict(g["name"], bool(answer["pass"]), str(answer.get("reason", "")))


def grade(graders: List[Dict], t: Transcript, top: Path, ask: Optional[Callable[[str], Dict]],
          learner: Optional[Path] = None) -> List[Verdict]:
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
        elif kind == "learner_file":
            out.append(learner_file(g, learner))
        elif kind == "command":
            out.append(command(g, t))
        elif kind == "no_command":
            out.append(no_command(g, t))
        elif kind == "asked":
            out.append(asked(g, t))
        elif kind == "no_stop_block":
            out.append(no_stop_block(g, t))
        elif kind == "only_markers":
            out.append(only_markers(g, top))
        elif kind == "judge":
            out.append(judge(g, t, ask, learner) if ask else Verdict(g["name"], False, "no judge available"))
        else:
            raise CaseError(f"grader {g.get('name')!r} has unknown type {kind!r}")
    return out


NEED = {"absent": ("pattern",), "present": ("pattern",), "no_write": ("under",),
        "unchanged": ("under",), "judge": ("criteria",), "learner_file": ("file", "pattern"),
        "command": ("pattern",), "no_command": ("pattern",), "asked": ("pattern",), "no_stop_block": (),
        "only_markers": ("path", "pattern")}
"""Every grader type and the keys a case must give it. Module level so
a test can walk it: this table and grade()'s dispatch are two lists of
the same types, and a type added to one alone fails a case only after
its turns are paid for."""


def check_case_graders(graders: List[Dict]) -> List[str]:
    """Faults in a case's grader list, before anything runs."""
    faults = []
    need = NEED
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
