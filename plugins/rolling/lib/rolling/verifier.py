"""The verifier: the task's verify: lines run against the tree as the
learner left it, then the held test applied and its held-verify: lines
run, then the revert. The result is a Report, a structured record of
what ran and how it went, with a render() for the text the skill reads.

A verify line names a command key in the map plus arguments as words.
The command line is run by a shell with the words appended as separate
arguments, never re-parsed: subprocess gets a list. A command that
cannot take arguments, or a line whose arguments are not words, is
rejected, not run.

The both-ways proof reads the same report differently. --on-base: the
lines named by expect-fail-on-base must fail, everything else must
pass, every line must actually have run, and the revert must have
succeeded. --on-reference: with the reference applied around the whole
run (reference.py), every line must pass, the held test included, and
the reference must have come back out leaving the tree clean. Anything
less is PROOF: not ok.
"""

from __future__ import annotations

import signal
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from . import heldtest, reference, rules
from .model import Learner, Map, Task
from .repo import GitError, Repo


class Kind(Enum):
    VERIFY = "verify"
    HELD = "held-verify"


class Outcome(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"              # no such command in the map
    REJECTED = "REJECTED"            # the command or the arguments are unsafe
    EXPECTED_FAIL = "EXPECTED-FAIL"  # on base: failed, as it should
    UNEXPECTED_PASS = "UNEXPECTED-PASS"


@dataclass
class LineResult:
    kind: Kind
    line: str
    outcome: Outcome
    command: str = ""
    rc: int = 0
    output: str = ""
    reason: str = ""

    @property
    def ran(self) -> bool:
        return self.outcome not in (Outcome.UNKNOWN, Outcome.REJECTED)

    @property
    def expect_key(self) -> str:
        """How expect-fail-on-base names this line."""
        return f"{self.kind.value} {self.line}"


@dataclass
class Report:
    on_base: bool
    lines: List[LineResult] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)       # HELD ... lines, in order
    revert: Optional[heldtest.RevertResult] = None
    had_held: bool = False
    held_not_run: bool = False                           # the held block was declared but could not run
    nothing_expected: bool = False                       # on base, no expect-fail-on-base line at all
    interrupted: bool = False
    proof_gaps: List[str] = field(default_factory=list)  # expect-fail entries that never ran
    not_run: str = ""                                    # why nothing ran at all
    on_reference: bool = False
    reference_out: bool = True                           # reversed, and the tree clean afterwards

    def count(self, kind: Kind, outcome: Outcome) -> int:
        return sum(1 for r in self.lines if r.kind is kind and r.outcome is outcome)

    @property
    def proof_ok(self) -> bool:
        if self.not_run or self.interrupted or self.proof_gaps or self.nothing_expected:
            return False
        if any(not r.ran or r.outcome in (Outcome.FAIL, Outcome.UNEXPECTED_PASS) for r in self.lines):
            return False
        if self.held_not_run:
            return False
        if self.revert is not None and (not self.revert.ok or self.revert.incomplete):
            return False
        if not self.reference_out:
            return False
        return True

    @property
    def proving(self) -> bool:
        return self.on_base or self.on_reference

    def summary(self) -> str:
        s = (f"VERIFIER: {self.count(Kind.VERIFY, Outcome.PASS)} passed, "
             f"{self.count(Kind.VERIFY, Outcome.FAIL)} failed, "
             f"{sum(1 for r in self.lines if not r.ran)} unknown or rejected")
        if self.on_base:
            s += f", expected failures: {sum(1 for r in self.lines if r.outcome is Outcome.EXPECTED_FAIL)}"
        if self.had_held:
            s += f"; held: {self.count(Kind.HELD, Outcome.PASS)} passed, {self.count(Kind.HELD, Outcome.FAIL)} failed"
            if self.revert and self.revert.status:
                s += f", {self.revert.status}"
        return s

    def render(self) -> List[str]:
        if self.not_run:
            out = []
            for r in self.lines:   # what ran before the failure, when anything did
                out += _render_line(r)
            out += self.notes
            out.append(f"VERIFIER: not run ({self.not_run})")
            if self.proving:
                out.append("PROOF: not ok (the verifier did not run)")
            return out
        out: List[str] = []
        for r in self.lines:
            out += _render_line(r)
        out += self.notes
        if self.interrupted:
            out.append("VERIFIER: interrupted before the report was complete; run it again")
            if self.proving:
                out.append("PROOF: not ok (interrupted)")
            return out
        out += [f"PROOF GAP: expected to fail but never ran: {e}" for e in self.proof_gaps]
        if self.nothing_expected:
            out.append("PROOF GAP: no expect-fail-on-base line; a task whose checks pass before the work is done teaches nothing")
        out.append(self.summary())
        if self.on_base:
            out.append("PROOF: ok (on the starting state, every expected failure failed, everything else passed, every line ran, and the held test was reverted)"
                       if self.proof_ok else
                       "PROOF: not ok (see UNEXPECTED-PASS, FAIL, UNKNOWN, REJECTED, HELD not run, REVERT FAILED, or PROOF GAP above; do not serve this task)")
        if self.on_reference:
            held = " and the held test" if self.had_held else ""
            out.append(f"PROOF: ok (with the reference applied, every line passed, and the reference{held} came back out leaving the tree clean)"
                       if self.proof_ok else
                       "PROOF: not ok (see FAIL, UNKNOWN, REJECTED, HELD not run, REVERT FAILED, or REFERENCE above; do not serve this task)")
        return out


def _render_line(r: LineResult) -> List[str]:
    tag = "HELD " if r.kind is Kind.HELD else ""
    o = r.outcome
    if o is Outcome.UNKNOWN or o is Outcome.REJECTED:
        return [f"{tag}{o.value:<8} {r.line}   ({r.reason})"]
    if o is Outcome.PASS:
        return [f"{tag}PASS     {r.line}   ({r.command})"]
    if o is Outcome.EXPECTED_FAIL:
        return [f"{tag}EXPECTED-FAIL({r.rc}) {r.line}   ({r.command})"]
    if o is Outcome.UNEXPECTED_PASS:
        return [f"{tag}UNEXPECTED-PASS {r.line}   ({r.command})  <- must fail on the starting state"]
    tail = r.output.rstrip("\n").split("\n")[-40:] if r.output.strip() else []
    return [f"{tag}FAIL({r.rc}) {r.line}   ({r.command})"] + (["    | " + l for l in tail] or ["    | (no output)"])


class Interrupted(Exception):
    pass


@contextmanager
def interruptible() -> Iterator[None]:
    """SIGINT and SIGTERM raise Interrupted inside the block, so the
    held test is reverted on the way out instead of the loop carrying
    on against a reverted tree."""
    def raise_it(signum, frame):
        raise Interrupted()
    old = {s: signal.signal(s, raise_it) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield
    finally:
        for s, h in old.items():
            signal.signal(s, h)


def run_declared(top: Path, command: str, words: List[str]) -> Tuple[int, str]:
    with subprocess.Popen(
        ["sh", "-c", command + ' "$@"', "verifier", *words],
        cwd=str(top), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    ) as proc:
        try:
            out, _ = proc.communicate()
        except BaseException:
            proc.kill()
            raise
    return proc.returncode, out.decode("utf-8", "replace")


class Verifier:
    def __init__(self, top: Path, learner: Learner, the_map: Map, task: Task, on_base: bool = False, on_reference: bool = False):
        self.top = top
        self.learner = learner
        self.map = the_map
        self.task = task
        self.on_base = on_base
        self.on_reference = on_reference
        self.report = Report(on_base=on_base, on_reference=on_reference)
        self._held: Optional[heldtest.HeldTest] = None

    def run(self) -> Report:
        rep = self.report
        t = self.task
        if not t.verify and not t.held_verify:
            rep.not_run = "the open task declares no verify: or held-verify: lines"
            return rep
        if self.on_reference:
            return self._run_on_reference()
        try:
            with interruptible():
                self._run_lines()
        except Interrupted:
            self._interrupted()
            return rep
        self._note_proof_gaps()
        return rep

    def _run_on_reference(self) -> Report:
        """The forward half: the reference in the tree around the whole
        run, taken out again whatever happens inside."""
        rep = self.report
        repo = Repo(self.top)
        if self.task.fix and self.learner.patch.is_file():
            rep.notes.append("note: reference.patch is ignored; the task names a fix, and the fix is the reference")
        ran: Optional[reference.Applied] = None
        try:
            patch = reference.patch_for(repo, self.learner, self.task)
            with interruptible():
                with reference.applied(repo, self.learner, patch) as ran:
                    try:
                        self._run_lines()
                    except Interrupted:
                        self._interrupted()
        except (reference.NoReference, reference.CannotApply, GitError, OSError) as e:
            rep.not_run = str(e)
            if ran is not None:   # the block was entered, so the reverse ran on the way out; keep its outcome
                rep.not_run += "; " + "; ".join(ran.notes)
            return rep
        rep.notes += ran.notes
        rep.reference_out = ran.clean_exit
        return rep

    def _run_lines(self) -> None:
        rep = self.report
        for line in self.task.verify:
            rep.lines.append(self._run_line(Kind.VERIFY, line))
        self._run_held()

    def _note_proof_gaps(self) -> None:
        rep, t = self.report, self.task
        if self.on_base:
            seen = {r.expect_key for r in rep.lines if r.outcome in (Outcome.EXPECTED_FAIL, Outcome.UNEXPECTED_PASS)}
            rep.proof_gaps = [e for e in t.expect_fail_on_base if e not in seen]
            rep.nothing_expected = not t.expect_fail_on_base

    def _interrupted(self) -> None:
        rep = self.report
        rep.interrupted = True
        ht = self._held
        if ht is not None and ht.result is not None and ht.result.had_record:
            # The with-block already reverted, aloud; say why first.
            rep.notes.append("HELD interrupted; reverting")
            rep.notes += ht.result.lines
            rep.revert = ht.result
        else:
            res = heldtest.revert(self.learner, self.top, quiet=False)
            rep.notes += res.lines
            rep.revert = res

    def _run_held(self) -> None:
        rep, t = self.report, self.task
        if not t.held_verify:
            return
        rep.had_held = True
        if not t.held:
            rep.notes.append("HELD not run (held-verify: lines but no held: paths)")
            rep.held_not_run = True
            return
        ht = heldtest.HeldTest(self.learner, self.top)
        self._held = ht
        try:
            with ht.applied(t.held):
                for line in t.held_verify:
                    rep.lines.append(self._run_line(Kind.HELD, line))
        except heldtest.CannotApply as r:
            rep.notes += r.lines
            rep.notes.append("HELD not run (a held path could not be applied; see above)")
            rep.held_not_run = True
        rep.revert = ht.result
        rep.notes += ht.result.lines if ht.result else []

    def _run_line(self, kind: Kind, line: str) -> LineResult:
        key, _, args = line.partition(" ")
        command = self.map.commands.get(key, "")
        if not command:
            return LineResult(kind, line, Outcome.UNKNOWN, reason=f"no command '{key}' in the map")
        if not rules.command_takes_args(command):
            return LineResult(kind, line, Outcome.REJECTED, reason=f"the map's command for '{key}' ends in an operator or contains '#', so arguments cannot be appended safely")
        if not rules.args_are_words(args):
            return LineResult(kind, line, Outcome.REJECTED, reason="arguments may not contain shell metacharacters, quotes, globs, or control characters")
        rc, out = run_declared(self.top, command, rules.words(args))
        result = LineResult(kind, line, Outcome.PASS if rc == 0 else Outcome.FAIL, command=command, rc=rc, output=out)
        if self.on_base and result.expect_key in self.task.expect_fail_on_base:
            result.outcome = Outcome.EXPECTED_FAIL if rc != 0 else Outcome.UNEXPECTED_PASS
        return result
