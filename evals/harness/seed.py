"""Seeding: put a learner where a case needs them, through the toolkit.

A case starts mid-course: a learner with a profile, perhaps a lesson
open, perhaps a task begun. Rather than drive a conversation there,
the harness runs the toolkit's own commands, the same ones the tutor's
skills run, with ROLLING_DATA pointed where the session's hook will
point it. So the state a case starts from is state the toolkit wrote
and validated, and a change to the toolkit's formats reaches the seed
without anyone editing it.

A seed is the case's `seed` object:

    {"profile": {"background": "...", "destination": {"billing": "working"},
                 "why": "...", "satisfied": ["local-setup"]},
     "lesson": "invoice-totals",          # open it, with no task
     "task": "invoice-totals",            # or begin its task from the fixture's fix
     "edits": {"billing/invoice.py": "..."}}   # the learner's work so far, in the tree

Each key is optional; `lesson` and `task` are exclusive, since a task's
lesson is the open one. The task is the fixture's one: the fix
reverted, its test held back, verified by `test`.

The tutor's session is claimed first, with the id the harness will
give `claude -p --session-id`, so the case's session is the tutor's
from its first turn, as it would be after the skill that opened the
lesson: the write guard keys on it. `edits` are written last, as the
learner's own uncommitted work, the way a learner's editor leaves it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List

from .fixture import Fixture

STARTED = "2026-09-24"


class SeedError(Exception):
    """A toolkit command refused; the message carries its output."""


def _run(bin_dir: Path, data: Path, fx: Fixture, name: str, *args: str, stdin: str = "") -> str:
    env = dict(os.environ, ROLLING_DATA=str(data))
    res = subprocess.run([str(bin_dir.resolve() / f"rolling-{name}"), *args], cwd=str(fx.top), env=env,
                         input=stdin, capture_output=True, text=True, check=False)
    out = res.stdout + res.stderr
    if res.returncode != 0:
        raise SeedError(f"rolling-{name} {' '.join(args)} exited {res.returncode}:\n{out}")
    return out


def profile_text(p: Dict) -> str:
    dest = "\n".join(f"{region}: {depth}" for region, depth in p.get("destination", {}).items())
    done = "\n".join(f"- {slug} ({STARTED})" for slug in p.get("satisfied", []))
    return (f"# Profile\n\n## Background\n{p.get('background', '').strip()}\n\n"
            f"## Destination\n{dest}\n\n## Why\n{p.get('why', '').strip()}\n\n## Satisfied\n{done}\n")


def task_text(lesson: str, begun: Dict[str, str], fx: Fixture) -> str:
    held_line = f"test {fx.held}"
    return (
        "---\n"
        f"lesson: {lesson}\nmode: write\nbranch: {begun['branch']}\nbase: {begun['base']}\n"
        f"return-to: {begun['return-to']}\nstarted: {STARTED}\nfix: {fx.fix}\n"
        "scope: billing\nscope: tests\nverify: test\n"
        f"held: {fx.held}\nheld-verify: {held_line}\nexpect-fail-on-base: held-verify {held_line}\n"
        "---\n\n"
        "## Brief\n\nAn invoice with a line whose quantity is more than one comes out too low. "
        "The total is in `billing/invoice.py`. Done means the total counts quantities, in integer "
        "cents, with a test that proves it; `python3 -m unittest` runs the tests, and a test is held "
        "back that will run when you say you are done.\n\n"
        f"## Source\n\nThe fix {fx.fix[:8]}, \"billing: total counts quantities\".\n"
    )


REFERENCE = ("# Reference\n\n`total` multiplies each line's `unit_cents` by its `quantity` before "
             "summing: `sum(line.unit_cents * line.quantity for line in lines)`. The fix's test "
             "checks three teas at 250 and one cake at 400 come to 1150.\n")


def _fields(out: str) -> Dict[str, str]:
    return dict(line.split(": ", 1) for line in out.splitlines() if ": " in line)


def apply(seed: Dict, fx: Fixture, bin_dir: Path, data: Path, session_id: str) -> List[str]:
    """Seed the learner for fx under data, as the tutor's session
    session_id. Returns what was done, in words."""
    if "lesson" in seed and "task" in seed:
        raise SeedError("a seed opens a lesson or begins a task, not both")
    _run(bin_dir, data, fx, "claim-session", session_id)
    done = []
    if "profile" in seed:
        _run(bin_dir, data, fx, "write", "profile", stdin=profile_text(seed["profile"]))
        done.append("profile written")
    if "lesson" in seed:
        _run(bin_dir, data, fx, "begin-lesson", seed["lesson"])
        done.append(f"lesson {seed['lesson']} open")
    if "task" in seed:
        lesson = seed["task"]
        begun = _fields(_run(bin_dir, data, fx, "begin-task", lesson, "--fix", fx.fix, "--held", fx.held))
        _run(bin_dir, data, fx, "write", "task", stdin=task_text(lesson, begun, fx))
        _run(bin_dir, data, fx, "write", "reference", stdin=REFERENCE)
        done.append(f"task for {lesson} begun on {begun['branch']}")
    for rel, text in seed.get("edits", {}).items():
        path = fx.top / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        done.append(f"learner edited {rel}")
    return done
