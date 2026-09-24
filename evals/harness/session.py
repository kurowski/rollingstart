"""Running the tutor: `claude -p` with the plugin, in a world of its own.

Every run gets a temporary directory holding the fixture repository
and a throwaway Claude Code configuration directory. Pointing
CLAUDE_CONFIG_DIR at the throwaway keeps the maintainer's own
settings, hooks, and installed plugins (an installed `rolling` among
them) out of the session, and puts the plugin's data directory inside
it, at `<config>/plugins/data/rolling-inline`, which is where the seed
writes the learner. The plugin under test is loaded with
`--plugin-dir`.

The environment is the caller's, minus what would leak the caller's
own session into the child (every `CLAUDE*` and `ANTHROPIC_*`
variable, since a maintainer's effort level or endpoint reaching the
tutor under test changes what is measured, and any installed plugin's
`bin/` on PATH), plus the credential. A throwaway
configuration is not logged in, so the credential comes from a token
file (`claude setup-token` makes one), read at run time and passed as
CLAUDE_CODE_OAUTH_TOKEN; it is never written anywhere.

A turn is one `claude -p`. The first names its session id, which the
seed has already claimed as the tutor's; a follow-up resumes it.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PLUGIN_DATA_NAME = "rolling-inline"   # what Claude Code calls a --plugin-dir plugin's data directory


class SessionError(Exception):
    """The run could not start: no claude, no credential."""


@dataclass
class World:
    root: Path        # the run's temporary directory
    config: Path      # its CLAUDE_CONFIG_DIR

    @property
    def data(self) -> Path:
        """Where the session's hook will point ROLLING_DATA."""
        return self.config / "plugins" / "data" / PLUGIN_DATA_NAME


def clean_env(base: Dict[str, str], config: Path, token: str) -> Dict[str, str]:
    env = {k: v for k, v in base.items()
           if not (k.startswith("CLAUDE") or k.startswith("ANTHROPIC_") or k == "ROLLING_DATA")}
    parts = [p for p in env.get("PATH", "").split(os.pathsep) if p and "/plugins/cache/" not in p]
    env["PATH"] = os.pathsep.join(parts)
    env["CLAUDE_CONFIG_DIR"] = str(config)
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    return env


def read_token(path: Path) -> str:
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise SessionError(f"no token at {path} ({e.strerror}): run `claude setup-token` and save what it prints there, mode 600")
    if not token:
        raise SessionError(f"{path} is empty")
    return token


def turn_command(prompt: str, plugin: Path, model: str, session_id: str, resume: bool, max_turns: int) -> List[str]:
    cmd = ["claude", "-p", prompt, "--plugin-dir", str(plugin), "--model", model,
           "--output-format", "stream-json", "--verbose", "--max-turns", str(max_turns)]
    cmd += ["--resume", session_id] if resume else ["--session-id", session_id]
    return cmd


def run_turn(cwd: Path, env: Dict[str, str], cmd: List[str], out: Path, timeout: int) -> Tuple[List[str], Optional[str]]:
    """Run one turn, writing its stream to out. Returns the stream's
    lines and, when the turn went wrong (a timeout, a non-zero exit),
    what went wrong, in words; None when it exited cleanly."""
    problem: Optional[str] = None
    try:
        res = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, timeout=timeout, check=False)
        stdout, stderr = res.stdout, res.stderr
        if res.returncode != 0:
            problem = f"claude exited {res.returncode}"
    except subprocess.TimeoutExpired as e:
        stdout, stderr = e.stdout or b"", e.stderr or b""
        problem = f"timed out after {timeout}s"
    except FileNotFoundError:
        raise SessionError("no `claude` on PATH")
    text = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")
    out.write_text(text, encoding="utf-8")
    if err.strip():
        out.with_suffix(".stderr").write_text(err, encoding="utf-8")
        if problem:
            problem += ": " + err.strip().splitlines()[-1][:300]
    return text.splitlines(), problem


def ask_judge(prompt: str, env: Dict[str, str], cwd: Path, model: str, schema: str, timeout: int = 300) -> Dict:
    """One tool-less `claude -p` answering with JSON against schema."""
    cmd = ["claude", "-p", prompt, "--model", model, "--tools", "", "--output-format", "json",
           "--json-schema", schema, "--no-session-persistence"]
    try:
        res = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"error": f"the judge timed out after {timeout}s"}
    try:
        record = json.loads(res.stdout)
    except ValueError:
        return {"error": (res.stderr or res.stdout).strip()[:500]}
    if not isinstance(record, dict):
        return {"error": f"not a result record: {str(record)[:500]}"}
    answer: Optional[object] = record.get("structured_output")
    if answer is None and isinstance(record.get("result"), str):
        try:
            answer = json.loads(record["result"])
        except ValueError:
            answer = None
    return answer if isinstance(answer, dict) else {"error": f"no structured answer: {str(record)[:500]}"}
