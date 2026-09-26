"""The tutor's reply, checked before the learner can answer it.

A Stop hook. When the tutor's session finishes a turn, every
`path:line` the turn's text cites is checked against the working tree
(citations.py); if any points nowhere, the hook blocks the stop with
the flags as its reason, and Claude Code has the tutor continue in the
same turn: a line or two giving each one's right location or
withdrawing the point. The learner reads the correction under the
mistake, before they have typed anything, rather than after acting on
it. Nothing is flagged in nearly every turn, and then the hook is
silent and costs a few milliseconds. The learner may see the reason
too: Claude Code shows it under "Ran 1 stop hook" as "Stop hook error:
<reason>", in an interactive session, which is fine; the tutor catching
its own mistake is nothing to hide.

A citation of the open task's held test is not judged: the held test
is in the tree only while the verifier runs it, and the tutor rightly
quotes where it failed. The turn's text is read from two places,
because neither holds all of it (confirmed 2026-09-26, Claude Code
2.1.283, print and interactive mode): the event's
`last_assistant_message` is only the final text block, and the
transcript at `transcript_path` has every block before it but not yet
the final one. So: the assistant text in the transcript since the last
prompt (a user entry that is neither a tool result nor a skill's
injected body), then the final message if the transcript did not
already end with it. A turn that moves the tree (begins or ends a
task, or takes a seam's reference out of it) is checked only from its
last such call on: what was said before was true of another tree.

Silent, always, when: the stop is the one after a correction
(`stop_hook_active`, so a correction is never itself blocked and the
turn always ends); the session is not the tutor's (the id the skills'
inline claim wrote to the learner's `session` file, or the open task's
`tutor-session`), so a coding session in the same repository is never
checked; the working directory is not in a repository with a learner
directory; or anything at all goes wrong. A hook that holds a turn open
on its own failure would be worse than none.

Claude Code hands the handler the event as JSON on stdin (session_id,
cwd, transcript_path, last_assistant_message, stop_hook_active) and the
plugin's data directory as an argument, substituted from
${CLAUDE_PLUGIN_DATA} in hooks.json. A block is the documented JSON on
stdout; letting the turn end is silence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import citations, paths
from .model import Learner
from .repo import Repo

TREE_MOVERS = ("rolling-begin-task", "rolling-end-task", "rolling-write patch --from-tree")


def turn_text(ev: Dict) -> str:
    """Everything the tutor said in this turn, as the learner read it."""
    parts: List[str] = []
    try:
        parts = _transcript_texts(Path(str(ev.get("transcript_path") or "")))
    except (OSError, ValueError):
        pass
    last = ev.get("last_assistant_message")
    if isinstance(last, str) and last.strip() and (not parts or parts[-1].strip() != last.strip()):
        parts.append(last)
    return "\n\n".join(parts)


def _transcript_texts(path: Path) -> List[str]:
    entries = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue   # a blank line, or one torn by a concurrent write
            if isinstance(e, dict):
                entries.append(e)
    start = max((i for i, e in enumerate(entries) if _is_prompt(e)), default=0)
    texts: List[str] = []
    for e in entries[start:]:
        if e.get("type") != "assistant":
            continue
        content = (e.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                texts.append(block["text"])
            elif block.get("type") == "tool_use" and _moves_the_tree(block):
                texts = []   # what was said before was true of another tree
    return texts


def _moves_the_tree(block: Dict) -> bool:
    """A toolkit call that changes what the working tree is: beginning or
    ending a task switches branch, and taking a seam's reference from
    the tree removes it."""
    cmd = str((block.get("input") or {}).get("command") or "").strip()
    return block.get("name") == "Bash" and cmd.startswith(TREE_MOVERS)


def _is_prompt(e: Dict) -> bool:
    """A line the learner typed. A skill's body, injected when a skill is
    typed or handed off to mid-turn, is marked meta and is not one."""
    if e.get("type") != "user" or e.get("isMeta"):
        return False
    content = (e.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    return isinstance(content, list) and not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)


def tutor_top(ev: Dict, data: Path) -> Optional[Path]:
    """The repository top, when this session is the tutor's there."""
    sid = str(ev.get("session_id") or "")
    top = paths.toplevel(Path(str(ev.get("cwd") or ".")))
    if not sid or top is None:
        return None
    learner = Learner(paths.learner_dir_in(data, top))
    try:
        claimed = learner.session.read_text(encoding="utf-8").strip()
    except OSError:
        claimed = ""
    task = learner.task()
    if sid == claimed or (task is not None and task.tutor_session == sid):
        return top
    return None


def decide(ev: Dict, data_dir: str) -> Optional[str]:
    """The reason to keep the turn going, or None to let it end."""
    if ev.get("stop_hook_active") or not data_dir:
        return None
    top = tutor_top(ev, Path(data_dir))
    if top is None:
        return None
    task = Learner(paths.learner_dir_in(Path(data_dir), top)).task()
    flags = citations.check(turn_text(ev), Repo(top), away=task.held if task else ())
    if not flags:
        return None
    # The learner sees this too, under Claude Code's "Stop hook error"
    # label, so it is short and reads as what it is.
    return (
        "Citation check:\n" + "\n".join(f"  {f}" for f in flags) + "\n"
        "Give the right location for each, or withdraw the point, in a line or two."
    )


def main(argv: List[str]) -> int:
    """Read the event, decide, print a block if any. Never fails: any
    surprise lets the turn end."""
    try:
        ev = json.loads(sys.stdin.read())
        if not isinstance(ev, dict):
            return 0
        reason = decide(ev, argv[0] if argv else "")
        if reason:
            sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    except Exception:  # noqa: BLE001  a hook must not hold a turn open on its own failure
        pass
    return 0
