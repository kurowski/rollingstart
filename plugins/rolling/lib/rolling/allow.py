"""The toolkit allows its own commands: a PreToolUse hook on Bash and
on the Skill tool that answers `allow` for the plugin's own executables
and its two hand-off skills, and says nothing about anything else.

Why a hook. A skill's `allowed-tools` hold only for the turn the skill
ran in; the moment a lesson needs the learner's reply, the next turn's
`rolling-begin-task` is a fresh permission decision, and auto mode
denies rather than asks. The first fix was a block of allow rules the
learner pasted into their settings, the roughest edge of the install.
A plugin cannot ship permission rules, but its hooks run in every
mode, and an `allow` skips the prompt for that one call: the same
mechanism the write guard uses for `deny`.

What is allowed, exactly:

- A Bash call whose command is one invocation of a toolkit executable
  (a name from this plugin's bin/, spelled bare) with plain-word
  arguments: outside quotes no `;`, `|`, `&`, `$`, backtick, `<`, `>`,
  parentheses, braces, or backslash, so nothing can be chained,
  substituted, grouped, or redirected; inside single quotes anything
  is literal, and inside double quotes `$`, backtick, and backslash
  are out, since the shell still expands them there. A Next.js route
  path with its brackets and parentheses travels quoted, which is how
  the tutor already passes one. Two shapes on top of that: the pen's
  heredoc, `rolling-write task <<'EOF'` with the body on the lines
  after, allowed only with a quoted delimiter, since an unquoted
  heredoc body is expanded by the shell and could run anything; and a
  trailing `2>&1`, which the tutor adds by habit and which sends
  nothing anywhere but its own transcript.
- A Skill call for `rolling:lesson` or `rolling:task`, the two skills
  the others hand off to.

Everything else is silence: the session's own permissions decide, so a
map's command, a destructive operation, and any compound command the
tutor types still ask as they always did. A hook that blocks the
session on its own failure would be worse than none, so any surprise is
silence too. The handler never reads the learner's directory; it has no
need of it.

Claude Code hands the handler the event as JSON on stdin (tool_name,
tool_input with `command` for Bash or `skill` for Skill). A decision is
the documented JSON on stdout.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

HANDOFF_SKILLS = ("rolling:lesson", "rolling:task")
PREFIX = "rolling-"
_FORBIDDEN = frozenset(";|&$`<>(){}\\")   # outside quotes
_HEREDOC = re.compile(r"\s<<(-?)\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\2\s*$")
_HOOK_HANDLERS = frozenset(("rolling-allow", "rolling-guard", "rolling-session-start"))
_STDERR_TO_STDOUT = re.compile(r"\s2>&1\s*$")


@dataclass
class Event:
    tool: str
    command: str = ""
    skill: str = ""


def executables(bin_dir: Optional[Path] = None) -> Set[str]:
    """The toolkit's own names: every `rolling-*` executable in this
    plugin's bin/, read at the time of the call so an installed copy
    answers for itself, minus the hook handlers, which exist to be run
    by hooks.json and never by the model (rolling-session-start would
    repoint the learner's directory for the rest of the session)."""
    d = bin_dir or Path(__file__).resolve().parents[2] / "bin"
    try:
        return {p.name for p in d.iterdir()
                if p.name.startswith(PREFIX) and p.name not in _HOOK_HANDLERS and p.is_file() and os.access(p, os.X_OK)}
    except OSError:
        return set()


def parse_event(text: str) -> Optional[Event]:
    try:
        ev = json.loads(text)
    except ValueError:
        return None
    if not isinstance(ev, dict):
        return None
    ti = ev.get("tool_input")
    if not isinstance(ti, dict):
        return None
    tool = str(ev.get("tool_name") or "")
    command = ti.get("command")
    skill = ti.get("skill")
    return Event(
        tool,
        command if isinstance(command, str) else "",
        skill if isinstance(skill, str) else "",
    )


def allowed_command(command: str, names: Set[str]) -> bool:
    """Is COMMAND one plain invocation of a toolkit executable?"""
    text = command.lstrip()
    head, sep, body = text.partition("\n")
    head = head.rstrip("\r")
    m = _HEREDOC.search(head)
    if m:
        # the body is the heredoc's, data to the command's stdin, and the
        # quoted delimiter keeps the shell out of it; but only as far as
        # the terminator line, and anything after that is a second command
        if not heredoc_body(body, m.group(3), bool(m.group(1))):
            return False
        head = head[:m.start()]
    elif sep and body.strip():
        return False          # a second line that is not a heredoc body
    head = _STDERR_TO_STDOUT.sub("", head)
    if not head.strip() or not shell_clean(head):
        return False
    try:
        words = shlex.split(head)
    except ValueError:
        return False
    return bool(words) and words[0] in names


def heredoc_body(body: str, delim: str, dash: bool) -> bool:
    """Is BODY the heredoc's and nothing more: the lines up to the
    terminator, and only blank lines after it? With `<<-` the shell
    strips leading tabs from the terminator too. A body that is never
    terminated is refused: under `bash -c` it would be stdin to the end
    and harmless, but the Bash tool drives a persistent shell, where an
    open heredoc swallows every later command silently, and a prompt is
    the better outcome for a truncated command."""
    lines = [ln.rstrip("\r") for ln in body.split("\n")]
    for i, ln in enumerate(lines):
        if (ln.lstrip("\t") if dash else ln) == delim:
            return not any(rest.strip() for rest in lines[i + 1:])
    return False


def shell_clean(line: str) -> bool:
    """Is LINE free of anything the shell would act on beyond splitting
    words? Outside quotes, no operator, substitution, grouping, or
    backslash; inside single quotes anything is literal; inside double
    quotes `$`, backtick, and backslash still expand, so they are out
    there too. Brackets and parentheses inside quotes are fine, which is
    how a Next.js route path travels. Control characters are out
    everywhere."""
    quote = ""
    for c in line:
        if ord(c) < 32 or ord(c) == 127:
            return False
        if quote:
            if c == quote:
                quote = ""
            elif quote == '"' and c in "$`\\":
                return False
            continue
        if c in ("'", '"'):
            quote = c
        elif c in _FORBIDDEN:
            return False
    return not quote


def decide(ev: Event, names: Set[str]) -> Optional[str]:
    """The reason to allow, or None to say nothing."""
    if ev.tool == "Bash" and ev.command and allowed_command(ev.command, names):
        return "the tutor's own toolkit command"
    if ev.tool == "Skill" and ev.skill in HANDOFF_SKILLS:
        return "the tutor's own hand-off skill"
    return None


def main(argv: List[str]) -> int:
    """Read the event, decide, print an allow if any. Never fails: any
    surprise is silence, and the session's permissions decide."""
    try:
        ev = parse_event(sys.stdin.read())
        if ev is None:
            return 0
        reason = decide(ev, executables())
        if reason:
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": reason,
                }
            }))
    except Exception:  # noqa: BLE001  a hook must not block the session on its own failure
        pass
    return 0
