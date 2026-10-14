"""Ask before a destructive operation: the second layer of the rule
that nothing drops the learner's work without their word.

A PreToolUse hook on Bash. The author marks operations `destructive`
in the map (docs/map.md); when a Bash command in the session runs one,
this handler answers `ask`, naming the operation, and the learner
decides that run. Everything else is silence, and so is any surprise:
a hook that blocks the session on its own failure would be worse than
no hook, and the answer to any doubt here is to say nothing and let
the session's own permissions decide.

Every session, every mode, task or no task, tutor or not. What the
rule protects is the learner's work, and a `pnpm db:reset` costs them
the same whoever typed it; `direct` mode's coding session (P5) leans
on this hook for exactly that reason. So nothing here reads the open
task or the session id, the two things the write guard turns on.

What counts as running one. An operation is a command line the author
declared verbatim (`reset-db: pnpm db:reset --force`), and its **head**
is the words that name it: the first command in the declaration that
is the operation rather than the way to it, up to the first word
beginning with `-`. `head()` has the reasons for each of those.

A command runs the operation when the head's words appear in it whole,
in order, and next to each other, with the shell's quoting taken off
and a leading `./` off each word. Anywhere in the command, not only at
its start -- `matched()` has that argument, and it is the one decision
here worth disagreeing with. The line is first cut into the commands
in it (`_split`), and a wrapper's argument is read as the line it is
(`wrapped`), so `bash -lc 'cd sub && pnpm db:reset'` is seen.

It holds against accident, not evasion. The operation run plainly,
run after a `cd`, run inside a `sh -c` or an `eval`, run behind a
`sudo` or a `timeout`, is caught; a line that spells it some other way
-- handed to `trap`, piped to a shell, put through a variable, run by
an `awk` -- is not, and nothing read off a command line could catch
the last of those. docs/map.md states that guarantee for authors and
asks them to keep an operation's blast radius small; docs/plan.md
section 10 has the reasoning.

Where it says nothing, and the author declares around it:

- an equivalent spelling of the same operation (`pnpm run db:reset`
  beside `pnpm db:reset`), or another spelling of a path
  (`cd .rolling && ./reset-db`), is a different set of words. Knowing
  a runner's conventions belongs in a map and not here, so docs/map.md
  tells authors to declare the other spelling as an operation of its
  own;
- the head's words must be adjacent, so `python3 -u scripts/reset.py`
  is not `python3 scripts/reset.py`.

Where it asks for nothing, which is the safe way to be wrong:

- a head of one common word asks about every use of that word;
- a quoted heredoc body is text the pen writes and never a command,
  but it reads like one: a note of the tutor's that says "run `pnpm
  db:reset` first" asks. Skipping bodies would fail open on
  `sh <<EOF`, so it is left;
- a `#` is not a comment to the splitting, so `pnpm build # after pnpm
  db:reset` asks.

None of those is a fault the toolkit reports. An author's declaration
is a hint, and a script that enforces a hint is code we do not want,
so docs/map.md says what the shapes cost instead.

Where the map comes from: the resolver, for the repository the session
is in, which is the tree's `.rolling/` or the installed map plugin
declared for it. No repository, no map, or a map that marks nothing
destructive, is silence. The session's cwd follows every `cd` the
tutor runs, and that is the right repository here rather than the
wrong one it would be for the write guard: the command runs in that
cwd too. Resolving costs a `git rev-parse` and, when the map is a
plugin, a few more git calls, on every Bash call of the session; that
is milliseconds against a command the learner is waiting on, and the
alternative is a second place that knows where a map lives.

Claude Code hands the handler the event as JSON on stdin (cwd,
tool_name, tool_input with `command`) and the plugin's data directory
as an argument, substituted from ${CLAUDE_PLUGIN_DATA} in hooks.json.
A decision is the documented JSON on stdout; saying nothing is silence.

An `ask` is honoured in `manual`, `auto`, and `dontAsk` alike, with
its reason reaching the model verbatim, and in print mode, where
nobody can answer, it becomes a refusal: the fail-safe end of the same
rule. An `ask` from one hook stands over an `allow` from another on
the same call, which is the order this handler and `rolling-allow`
depend on. (Probed in 2.7; the p2 plan records what was run.)
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple

from . import mapsource, paths
from .model import LoadError, Map

# Outside quotes, each of these ends the command's words: the ones that
# start another, and a redirection, which does not but which the shell
# takes off the word all the same -- without `<` and `>` here,
# `pnpm db:reset>out.log` leaves `db:reset>out.log` as one word and the
# operation's words are no longer next to each other.
_BREAKS = ";&|\n(){}<>"
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SHELLS = frozenset(("sh", "bash", "zsh", "dash", "ksh"))
_DASH_C = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")   # -c, and -lc, -ec, -xc bundled
# The way to an operation rather than the operation: a declaration
# often opens with one, and its words are not the head.
_PREAMBLE = frozenset(("cd", "pushd", "[", "test", "true", "false"))
_UNWRAP = 3                               # how far into `sh -c` inside `sh -c` to read
COMMAND_SHOWN = 160   # of the declared command, in the reason the learner reads


@dataclass
class Event:
    cwd: Path
    tool: str
    command: str


@dataclass
class Operation:
    """One destructive operation of the map's, with its head."""
    key: str
    command: str
    head: List[str] = field(default_factory=list)


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
    command = ti.get("command")
    return Event(
        cwd=Path(str(ev.get("cwd") or os.getcwd())),
        tool=str(ev.get("tool_name") or ""),
        command=command if isinstance(command, str) else "",
    )


# ------------------------------------------------------ the command line

def _split(line: str) -> List[Tuple[int, str]]:
    """The commands in LINE with how deep inside a substitution each
    one is: it split at everything that starts a new
    one, with the shell's quoting respected so an operator inside
    quotes is text and not a break.

    A single-quoted run is literal, backslash included. Inside double
    quotes the shell still substitutes, so a backtick or a `$(` opens a
    command there as it does outside; `;` and `|` there do not.

    A substitution is a command being parsed afresh, so the quote it
    was found inside stops applying until it closes -- and starts again
    after. Both halves matter, and the second one caught a fail-open
    that the first one caused: without the saving and restoring,
    `cd "$(git rev-parse --show-toplevel)" && pnpm db:reset` ends with
    the closing `"` read as an opening one, every break after it taken
    for text, and the reset unnoticed."""
    out: List[Tuple[int, str]] = []
    subs: List[Tuple[str, str]] = []    # (what closes it, the quote it was found inside)
    start = 0
    quote = ""
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if quote == "'":
            quote = "" if c == "'" else quote
            i += 1
            continue
        if c == "\\":
            i += 2                      # whatever follows is literal
            continue
        if c == "`" and subs and subs[-1][0] == "`":
            out.append((len(subs), line[start:i]))
            _, quote = subs.pop()       # back inside whatever quoted it
            i += 1
            start = i
            continue
        if c == "`" or (c == "$" and line[i + 1:i + 2] == "("):
            out.append((len(subs), line[start:i]))   # a substitution opens a command, quoted or not
            subs.append((")" if c == "$" else "`", quote))
            quote = ""
            i += 2 if c == "$" else 1
            start = i
            continue
        if c == ")" and subs and subs[-1][0] == ")":
            out.append((len(subs), line[start:i]))
            _, quote = subs.pop()
            i += 1
            start = i
            continue
        if quote:
            quote = "" if c == quote else quote
            i += 1
            continue
        if c in "'\"":
            quote = c
            i += 1
            continue
        if c in _BREAKS:
            out.append((len(subs), line[start:i]))
            i += 1
            start = i
            continue
        i += 1
    out.append((len(subs), line[start:]))
    return [(d, s) for d, s in ((d, seg.strip()) for d, seg in out) if s]


def commands_in(line: str) -> List[str]:
    """Every command in LINE, a substitution's own included: what might
    run."""
    return [s for _, s in _split(line)]


def own_commands(line: str) -> List[str]:
    """Only the commands LINE itself runs, not the ones inside a
    substitution it uses. An operation declared `cd "$(git rev-parse
    --show-toplevel)" && pnpm db:reset --force` has `git rev-parse` in
    it, which is how it finds the directory and not what it does; a
    head taken from that would ask on every `git rev-parse` in the
    session and say nothing about the reset."""
    return [s for d, s in _split(line) if d == 0]


def words(command: str) -> List[str]:
    """A command's words as the shell would hand them over: the quoting
    off, leading `VAR=value` assignments dropped since `FORCE=1 pnpm
    db:reset` is the same run, and a leading `./` off each word, since
    `./scripts/reset.py` and `scripts/reset.py` are one file.

    A command that will not parse (an unbalanced quote, most often one
    cut in half by the splitting above) falls back to a plain split
    with the stray quote characters taken off its words. That is a
    worse reading, so it is a reading that asks more rather than less:
    a heredoc body with an apostrophe in it leaves the rest of the line
    unparseable, and the operation after it still has to be found."""
    try:
        # a line continuation leaves shlex a word of just the newline
        parts = [w for w in shlex.split(command) if w.strip()]
    except ValueError:
        parts = [w for w in (p.strip("'\"") for p in command.split()) if w]
    while parts and _ASSIGNMENT.match(parts[0]):
        parts.pop(0)
    return [w[2:] if w.startswith("./") and len(w) > 2 else w for w in parts]


def wrapped(parts: List[str]) -> Optional[str]:
    """The command line a wrapper was handed, when these words hand one
    over: a shell's `-c` (bundled as `-lc` or `-ec` too), or an `eval`.
    None when they do not.

    The shell is looked for at any word, not only the first, because
    `timeout 20 sh -c '<line>'` and `sudo sh -c '<line>'` put a word in
    front of it -- and the line is one quoted word, so searching the
    words cannot find the operation inside it the way it can inside
    `timeout 20 pnpm db:reset`. The command is the first word after the
    flag that is not itself a flag, because `sh -c -x '<line>'` puts
    the shell's own `-x` in between."""
    for i, first in enumerate(parts):
        if first == "eval" and len(parts) > i + 1:
            return " ".join(parts[i + 1:])
        if first in _SHELLS or PurePosixPath(first).name in _SHELLS:
            for j, word in enumerate(parts[i + 1:], i + 1):
                if _DASH_C.match(word):
                    return next((w for w in parts[j + 1:] if not w.startswith("-")), None)
                if not word.startswith("-"):
                    break            # a script to run; a later word may still be a shell
    return None


def word_lists(line: str, depth: int = 0) -> List[List[str]]:
    """The words of every command LINE runs, a substitution's own
    included, and inside a wrapper the words of every command in what
    it was handed -- every command, because `sh -c 'cd sub && pnpm
    db:reset'` runs the second one and only reading the first would
    miss it."""
    out: List[List[str]] = []
    for part in commands_in(line):
        parts = words(part)
        if not parts:
            continue
        out.append(parts)
        if depth < _UNWRAP:
            inner = wrapped(parts)
            if inner:
                out.extend(word_lists(inner, depth + 1))
    return out


def head(command: str, depth: int = 0) -> List[str]:
    """An operation's head: the words of the first command in it that
    is the operation rather than the way to it, up to the first word
    beginning with `-`.

    The first command, because an operation may be a chain
    (`make resetdb && make seed`) and the words of the whole chain are
    the head of nothing: the point is to ask before it starts. Not a
    `cd` or a guard, because `cd apps/web && pnpm db:reset --force` and
    `[ -f db ] && make reset` are how an author writes one that has to
    find its way or check first. Only the line's own commands, so a
    `cd "$(git rev-parse --show-toplevel)"` does not make the head
    `git rev-parse`. And through a wrapper, since the head of
    `sh -c 'rm -rf tmp/db'` is `rm` and not `sh`, which would ask
    about every `sh` the session mentions.

    Empty when there is nothing before the first flag, and an
    operation with no head is passed over, since no words would match
    every command."""
    for part in own_commands(command):
        parts = words(part)
        if not parts:
            continue
        if depth < _UNWRAP:
            inner = wrapped(parts)
            if inner:
                deeper = head(inner, depth + 1)
                if deeper:
                    return deeper
        out: List[str] = []
        for word in parts:
            if word.startswith("-"):
                break
            out.append(word)
        if out and out[0] not in _PREAMBLE:
            return out
    return []


# --------------------------------------------------------------- the map

def destructive(m: Map) -> List[Operation]:
    """The map's destructive operations, each with its head, in the
    order the map lists them. A key naming no operation, or an
    operation with no head, is left out: the first is a fault the
    validator reports to the author, and neither is this hook's to
    complain about."""
    out: List[Operation] = []
    for key in m.destructive:
        command = m.operations.get(key, "")
        words_ = head(command) if isinstance(command, str) and command.strip() else []
        if words_:
            out.append(Operation(key, command.strip(), words_))
    return out


def map_for(cwd: Path, data_dir: str) -> Optional[Map]:
    """The map for the repository the session is in, through the
    resolver, or None when there is no repository, no map, or no
    readable map."""
    top = paths.toplevel(cwd)
    if top is None:
        return None
    resolved = mapsource.resolve(top, Path(data_dir) if data_dir else None)
    if resolved.dir is None:
        return None
    try:
        return Map.load(resolved.dir)
    except LoadError:
        return None


# -------------------------------------------------------------- deciding

def matched(line: str, ops: List[Operation]) -> Optional[Operation]:
    """The destructive operation this command line runs, or None; the
    first in the map's order when a line runs more than one, since one
    prompt is one decision and the learner is reading it.

    A head counts wherever it sits in a command's words, not only at
    the start. Reading only the start means modelling every way a
    command can be reached -- a keyword out of an `if`, a `sudo`, a
    `timeout 20`, a `nice -n 5`, whose own option's argument cannot be
    told from a command -- and each one missed is a destructive
    operation running unasked. Anywhere costs the other kind of
    mistake: `grep -rn pnpm db:reset .`, with the words unquoted, asks
    once for nothing. That is the right side to be wrong on, and the
    common mentions stay quiet by themselves, because a quoted one is
    a single word and never a run of them."""
    lists = word_lists(line)
    for op in ops:
        if not op.head:        # no words match every command; never built, never trusted
            continue
        if any(_runs(ws, op.head) for ws in lists):
            return op
    return None


def _runs(ws: List[str], head_: List[str]) -> bool:
    """Do HEAD_'s words appear in WS whole, in order, and next to each
    other?"""
    return any(ws[i:i + len(head_)] == head_ for i in range(len(ws) - len(head_) + 1))


def reason_for(op: Operation) -> str:
    """Why to ask, as both the learner and the tutor read it: the
    learner in the prompt, the tutor in the refusal that an `ask` with
    nobody to answer becomes."""
    shown = op.command if len(op.command) <= COMMAND_SHOWN else op.command[:COMMAND_SHOWN] + "..."
    return (f"This runs {op.key}, which the map marks destructive: {shown}. "
            "It drops or overwrites something of yours, so it is yours to say yes to, "
            "this run and every run.")


def decide(ev: Event, data_dir: str) -> Optional[str]:
    """The reason to ask, or None to say nothing."""
    if ev.tool != "Bash" or not ev.command.strip():
        return None
    m = map_for(ev.cwd, data_dir)
    if m is None:
        return None
    ops = destructive(m)
    if not ops:
        return None
    op = matched(ev.command, ops)
    return reason_for(op) if op is not None else None


def main(argv: List[str]) -> int:
    """Read the event, decide, print an ask if any. Never fails: any
    surprise is silence."""
    try:
        ev = parse_event(sys.stdin.read())
        if ev is None:
            return 0
        reason = decide(ev, argv[0] if argv else "")
        if reason:
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            }))
    except Exception:  # noqa: BLE001  a hook must not block the session on its own failure
        pass
    return 0
