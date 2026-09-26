"""The eval runner: cases in, verdicts out.

    evals/run [--model M]... [--runs N] [--case GLOB]... [--judge-model M]
              [--token-file PATH] [--keep]

A case is a directory under `evals/cases/` holding `case.json`:

    {"description": "what the case is about, in a sentence",
     "seed": {...},                       # see harness/seed.py
     "prompt": "the learner's line",
     "then": ["a follow-up line", ...],   # optional; each resumes the session
     "max_turns": 20,                     # optional, per learner line
     "graders": [...]}                    # see harness/graders.py

For each model, case, and run: a temporary directory with the fixture
(harness/fixture.py) and a throwaway configuration, the seed applied
through the toolkit, then one `claude -p` per learner line
(harness/session.py), then the graders. A run passes when every grader
does; a case passes on a model when every run does.

What a run leaves behind, under `evals/results/<stamp>/` (kept out of
the tree by .gitignore): `summary.md`, a table of cases by model with
each failing verdict's reason, and `summary.json`; and per run,
`<model>/<case>/<n>/` with each turn's stream (`turn-1.jsonl`, ...),
the conversation as the judge read it, `verdicts.json`, and
`learner/`, a copy of the learner's directory as the run left it. The
temporary directory is removed unless --keep, and the maintainer's own
configuration is never touched.

Exits 0 when every case passed on every model, 1 when one did not, and
2 when the run could not start (no token, a case with faults).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from . import fixture, graders, seed, session, transcript

EVALS = Path(__file__).resolve().parent.parent
REPO = EVALS.parent
PLUGIN = REPO / "plugins" / "rolling"
CASES = EVALS / "cases"
RESULTS = EVALS / "results"
DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_JUDGE = "claude-sonnet-5"
DEFAULT_TOKEN = Path.home() / ".config" / "rolling-evals" / "token"
TURN_TIMEOUT = 900


def load_cases(patterns: List[str]) -> Dict[str, Dict]:
    cases = {}
    for d in sorted(p for p in CASES.iterdir() if (p / "case.json").is_file()) if CASES.is_dir() else []:
        if patterns and not any(fnmatch.fnmatch(d.name, pat) for pat in patterns):
            continue
        cases[d.name] = json.loads((d / "case.json").read_text(encoding="utf-8"))
    return cases


def case_faults(name: str, case: Dict) -> List[str]:
    faults = [f"{name}: {f}" for f in graders.check_case_graders(case.get("graders", []))]
    if not str(case.get("prompt", "")).strip():
        faults.append(f"{name}: no prompt")
    if not isinstance(case.get("seed", {}), dict):
        faults.append(f"{name}: seed is not an object")
    return faults


def turn_problem(n: int, problem: Optional[str], got_result: bool) -> Optional[str]:
    """Why turn n cannot be graded, or None. A turn that timed out,
    exited non-zero, or ended without a `result` record never finished,
    and a grader that asserts an absence would pass it vacuously."""
    if problem:
        return f"turn {n}: {problem}"
    if not got_result:
        return f"turn {n}: the stream ended without a result record"
    return None


def run_one(case: Dict, model: str, judge_model: str, token: str, out: Path, keep: bool) -> Dict:
    root = Path(tempfile.mkdtemp(prefix="rolling-eval."))
    world = session.World(root=root, config=root / "config")
    world.config.mkdir()
    try:
        fx = fixture.build(root / "repo")
        sid = str(uuid.uuid4())
        seeded = seed.apply(case.get("seed", {}), fx, PLUGIN / "bin", world.data, sid)
        env = session.clean_env(dict(os.environ), world.config, token)
        t = transcript.Transcript()
        broken: List[str] = []
        lines = [case["prompt"], *case.get("then", [])]
        for i, line in enumerate(lines, 1):
            cmd = session.turn_command(line, PLUGIN, model, sid, resume=i > 1, max_turns=int(case.get("max_turns", 20)))
            stream, problem = session.run_turn(fx.top, env, cmd, out / f"turn-{i}.jsonl", TURN_TIMEOUT)
            before = len(t.results)
            transcript.read(stream, prompt=line, into=t)
            why = turn_problem(i, problem, len(t.results) > before)
            if why:
                broken.append(why)
                break

        def ask(prompt: str) -> Dict:
            return session.ask_judge(prompt, env, root, judge_model, graders.JUDGE_SCHEMA)

        learners = sorted((world.data / "repos").glob("*"))
        learner = learners[0] if len(learners) == 1 else None
        if learner is not None:
            shutil.copytree(str(learner), str(out / "learner"))
        verdicts = graders.grade(case["graders"], t, fx.top, ask, learner)
        (out / "conversation.md").write_text(t.conversation() + "\n", encoding="utf-8")
        errors = broken + t.errors()
        result = {"passed": all(v.passed for v in verdicts) and not errors,
                  "verdicts": [asdict(v) for v in verdicts], "errors": errors, "seeded": seeded,
                  "turns": t.turns, "cost_usd": round(t.cost_usd, 4), "session_id": sid}
    except (seed.SeedError, session.SessionError) as e:
        result = {"passed": False, "verdicts": [], "errors": [str(e)], "seeded": [], "turns": 0, "cost_usd": 0}
    except Exception as e:  # one broken run must not lose the summary of a paid matrix
        result = {"passed": False, "verdicts": [], "errors": [f"{type(e).__name__}: {e}"], "seeded": [], "turns": 0, "cost_usd": 0}
    finally:
        if keep:
            result_root = str(root)
        else:
            shutil.rmtree(root, ignore_errors=True)
            result_root = ""
    result["kept"] = result_root
    (out / "verdicts.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def summarize(results: Dict[str, Dict[str, List[Dict]]], models: List[str]) -> str:
    lines = ["# Eval run", "", "| Case | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    failures = []
    for name in sorted({c for m in results.values() for c in m}):
        cells = []
        for m in models:
            runs = results.get(m, {}).get(name, [])
            passed = sum(1 for r in runs if r["passed"])
            cells.append(f"{passed}/{len(runs)}")
            for n, r in enumerate(runs, 1):
                if not r["passed"]:
                    why = [f"{v['name']}: {v['reason']}" for v in r["verdicts"] if not v["passed"]] + r["errors"]
                    failures.append(f"- **{name}**, {m}, run {n}: " + "; ".join(why))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    cost = sum(r["cost_usd"] for m in results.values() for runs in m.values() for r in runs)
    lines += ["", f"Cost of the tutor's sessions: ${cost:.2f} (the judge's is not counted)."]
    if failures:
        lines += ["", "## Failures", "", *failures]
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="evals/run", description="Run the tutor's eval cases.")
    ap.add_argument("--model", action="append", help=f"a model to run the tutor on (repeatable; default {DEFAULT_MODEL})")
    ap.add_argument("--runs", type=int, default=3, help="runs per case per model (default 3)")
    ap.add_argument("--case", action="append", default=[], help="run only cases whose name matches this glob (repeatable)")
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE, help=f"the judge's model (default {DEFAULT_JUDGE})")
    ap.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN, help=f"the credential for the throwaway config (default {DEFAULT_TOKEN})")
    ap.add_argument("--keep", action="store_true", help="keep each run's temporary directory")
    ns = ap.parse_args(argv)
    if ns.runs < 1:
        ap.error("--runs must be at least 1")
    models = ns.model or [DEFAULT_MODEL]

    cases = load_cases(ns.case)
    if not cases:
        print("no cases match", file=sys.stderr)
        return 2
    faults = [f for name, c in cases.items() for f in case_faults(name, c)]
    if faults:
        print("\n".join(faults), file=sys.stderr)
        return 2
    try:
        token = session.read_token(ns.token_file)
    except session.SessionError as e:
        print(e, file=sys.stderr)
        return 2

    stamp = time.strftime("%Y%m%d-%H%M%S")
    top = RESULTS / stamp
    results: Dict[str, Dict[str, List[Dict]]] = {}
    for m in models:
        for name, case in cases.items():
            for n in range(1, ns.runs + 1):
                out = top / m / name / str(n)
                out.mkdir(parents=True)
                print(f"{m} {name} run {n} ...", end=" ", flush=True)
                r = run_one(case, m, ns.judge_model, token, out, ns.keep)
                print("pass" if r["passed"] else "FAIL", flush=True)
                results.setdefault(m, {}).setdefault(name, []).append(r)
    summary = summarize(results, models)
    (top / "summary.md").write_text(summary, encoding="utf-8")
    (top / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(summary)
    print(f"results: {top}")
    return 0 if all(r["passed"] for m in results.values() for runs in m.values() for r in runs) else 1
