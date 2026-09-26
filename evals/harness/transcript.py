"""Reading what a session did, from `claude -p --output-format stream-json`.

Each line of the stream is one JSON record. The harness keeps them all
(they are the run's evidence) and reads five things out of them: the
tutor's text, in order; the tool calls it made, with their inputs; what
each call returned, marked when it came back as an error, which every
permission denial and every hook's refusal does, and what each skill
loaded into the tutor's context with its inline commands' output (a
user record marked isSynthetic); each time a Stop hook
kept the turn going (the citation check, whose reason reaches the model
as a user message beginning "Stop hook feedback:"); and the final
`result` record, with the session id, the turn count, and the cost. A turn is one `claude -p`
invocation; a case with a follow-up has two streams, read as one.
A subagent's records (those with a `parent_tool_use_id`) are skipped:
the learner never sees a subagent's text, only what the tutor says.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

STOP_FEEDBACK = "Stop hook feedback:"
OUTPUT_LIMIT = 4000   # characters of a call's output shown to a judge
CONTEXT_LIMIT = 30000   # of a loaded skill, whose inline output comes last


@dataclass
class ToolCall:
    id: str
    name: str
    input: Dict
    error: Optional[str] = None      # the result's text, when it came back as an error
    output: str = ""                 # the result's text, error or not

    def path(self) -> str:
        """The file a file tool was aimed at, or the empty string."""
        return str(self.input.get("file_path") or self.input.get("notebook_path") or "")


@dataclass
class Transcript:
    prompts: List[str] = field(default_factory=list)   # the learner's lines, one per turn
    texts: List[str] = field(default_factory=list)     # the tutor's text blocks, in order
    calls: List[ToolCall] = field(default_factory=list)
    results: List[Dict] = field(default_factory=list)  # one `result` record per turn
    stop_blocks: List[str] = field(default_factory=list)  # each Stop hook's reason for keeping the turn going
    events: List[Tuple[str, object]] = field(default_factory=list)  # prompts, texts, calls, and stop blocks, in order
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

    def conversation(self, outputs: bool = False) -> str:
        """The run as the learner saw it, for a judge: their lines and the
        tutor's text, with each tool call as one bracketed line so a
        reader knows what the tutor looked at without its output; with
        OUTPUTS, what each call returned too, for a judge whose question
        is whether the tutor said only what it saw."""
        return render(self, outputs)


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
                if block.get("type") == "tool_result":
                    call = by_id.get(block.get("tool_use_id", ""))
                    if call is not None:
                        call.output = _result_text(block.get("content"))
                        if block.get("is_error"):
                            call.error = call.output
                elif block.get("type") == "text" and str(block.get("text", "")).startswith(STOP_FEEDBACK):
                    reason = block["text"][len(STOP_FEEDBACK):].strip()
                    t.stop_blocks.append(reason)
                    t.events.append(("stop", reason))
                elif block.get("type") == "text" and rec.get("isSynthetic"):
                    # A skill loaded: its body, with what its inline
                    # commands printed (the report at done, the lesson,
                    # the task). The tutor read it; the learner did not.
                    t.events.append(("context", str(block.get("text", ""))))
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


def render(t: Transcript, outputs: bool = False) -> str:
    parts = []
    for kind, item in t.events:
        if kind == "prompt":
            parts.append(f"LEARNER: {item}")
        elif kind == "text":
            parts.append(f"TUTOR: {item}")
        elif kind == "stop":
            parts.append(f"[stop hook, shown to the learner: {item}]")
        elif kind == "context":
            if outputs:
                half = CONTEXT_LIMIT // 2   # the middle goes: the inline output is at the end
                body = item if len(item) <= CONTEXT_LIMIT else item[:half] + "\n…(cut)…\n" + item[-half:]  # type: ignore[index,operator]
                parts.append("[a skill loaded into the tutor's context, with its commands' output]\n<context>\n" + body + "\n</context>")
        else:
            line = _call_line(item)  # type: ignore[arg-type]
            if outputs:
                out = item.output if len(item.output) <= OUTPUT_LIMIT else item.output[:OUTPUT_LIMIT] + "\n…(cut)"  # type: ignore[union-attr]
                line += "\n<output>\n" + out + "\n</output>"
            parts.append(line)
    return "\n\n".join(parts)
