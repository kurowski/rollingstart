"""Reading what a session did, from `claude -p --output-format stream-json`.

Each line of the stream is one JSON record. The harness keeps them all
(they are the run's evidence) and reads four things out of them: the
tutor's text, in order; the tool calls it made, with their inputs; the
tool results that came back as errors, which include every permission
denial and every hook's refusal; and the final `result` record, with
the session id, the turn count, and the cost. A turn is one `claude -p`
invocation; a case with a follow-up has two streams, read as one.
A subagent's records (those with a `parent_tool_use_id`) are skipped:
the learner never sees a subagent's text, only what the tutor says.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class ToolCall:
    id: str
    name: str
    input: Dict
    error: Optional[str] = None      # the result's text, when it came back as an error

    def path(self) -> str:
        """The file a file tool was aimed at, or the empty string."""
        return str(self.input.get("file_path") or self.input.get("notebook_path") or "")


@dataclass
class Transcript:
    prompts: List[str] = field(default_factory=list)   # the learner's lines, one per turn
    texts: List[str] = field(default_factory=list)     # the tutor's text blocks, in order
    calls: List[ToolCall] = field(default_factory=list)
    results: List[Dict] = field(default_factory=list)  # one `result` record per turn
    events: List[Tuple[str, object]] = field(default_factory=list)  # prompts, texts, and calls, in order
    unreadable: int = 0                                # lines that were not JSON

    @property
    def text(self) -> str:
        return "\n\n".join(self.texts)

    @property
    def cost_usd(self) -> float:
        return sum(float(r.get("total_cost_usd") or 0) for r in self.results)

    @property
    def turns(self) -> int:
        return sum(int(r.get("num_turns") or 0) for r in self.results)

    def errors(self) -> List[str]:
        """Why a turn ended badly, if one did: `is_error`, or a subtype
        other than success (max turns, say)."""
        out = []
        for r in self.results:
            if r.get("is_error") or (r.get("subtype") and r.get("subtype") != "success"):
                out.append(str(r.get("subtype") or r.get("result") or "error"))
        return out

    def conversation(self) -> str:
        """The run as the learner saw it, for a judge: their lines and the
        tutor's text, with each tool call as one bracketed line so a
        reader knows what the tutor looked at without its output."""
        return render(self)


def _content(record: Dict) -> List[Dict]:
    msg = record.get("message") or {}
    content = msg.get("content")
    return content if isinstance(content, list) else []


def read(lines: Iterable[str], prompt: str = "", into: Optional[Transcript] = None) -> Transcript:
    """Add one turn's stream to a transcript (a new one if none is given)."""
    t = into or Transcript()
    t.prompts.append(prompt)
    by_id: Dict[str, ToolCall] = {c.id: c for c in t.calls}
    t.events.append(("prompt", prompt))
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            t.unreadable += 1
            continue
        kind = rec.get("type")
        if rec.get("parent_tool_use_id"):
            continue
        if kind == "assistant":
            for block in _content(rec):
                if block.get("type") == "text" and block.get("text", "").strip():
                    t.texts.append(block["text"])
                    t.events.append(("text", block["text"]))
                elif block.get("type") == "tool_use":
                    call = ToolCall(id=block.get("id", ""), name=block.get("name", ""), input=block.get("input") or {})
                    t.calls.append(call)
                    by_id[call.id] = call
                    t.events.append(("call", call))
        elif kind == "user":
            for block in _content(rec):
                if block.get("type") == "tool_result" and block.get("is_error"):
                    call = by_id.get(block.get("tool_use_id", ""))
                    if call is not None:
                        call.error = _result_text(block.get("content"))
        elif kind == "result":
            t.results.append(rec)
    return t


def _result_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(c.get("text", "")) for c in content if isinstance(c, dict))
    return ""


def _call_line(c: ToolCall) -> str:
    if c.name == "Bash":
        what = str(c.input.get("command", "")).splitlines()[0] if c.input.get("command") else ""
    elif c.name == "Skill":
        what = str(c.input.get("skill", ""))
    else:
        what = c.path() or str(c.input.get("pattern", ""))
    return f"[tool: {c.name} {what}{' (error)' if c.error else ''}]"


def render(t: Transcript) -> str:
    parts = []
    for kind, item in t.events:
        if kind == "prompt":
            parts.append(f"LEARNER: {item}")
        elif kind == "text":
            parts.append(f"TUTOR: {item}")
        else:
            parts.append(_call_line(item))  # type: ignore[arg-type]
    return "\n\n".join(parts)
