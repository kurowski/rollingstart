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
seed has already claimed as the tutor's; a follow-up resumes it. The
judge is one too, tool-less and answering against a schema, and its
raw record is kept beside the turns: an answer the harness cannot read
has to be readable by a person, or a glitch in the judge and a tutor
misbehaving look the same afterwards.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

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
    # Absolute: a relative path here resolves against the child's cwd,
    # which once wrote a configuration into a results directory.
    env["CLAUDE_CONFIG_DIR"] = str(Path(config).resolve())
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


def turn_command(prompt: str, plugin: Path, model: str, session_id: str, resume: bool, max_turns: int,
                 permission_mode: str = "", allowed_tools: Sequence[str] = ()) -> List[str]:
    cmd = ["claude", "-p", prompt, "--plugin-dir", str(plugin), "--model", model,
           "--output-format", "stream-json", "--verbose", "--max-turns", str(max_turns)]
    if permission_mode:
        cmd += ["--permission-mode", permission_mode]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    cmd += ["--resume", session_id] if resume else ["--session-id", session_id]
    return cmd


def run_turn(cwd: Path, env: Dict[str, str], cmd: List[str], out: Path, timeout: int) -> Tuple[List[str], Optional[str]]:
    """Run one turn, writing its stream to out. Returns the stream's
    lines and, when the turn went wrong (a timeout, a non-zero exit),
    what went wrong, in words; None when it exited cleanly."""
    problem: Optional[str] = None
    try:
        res = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, timeout=timeout, check=False,
                             stdin=subprocess.DEVNULL)
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


# The closing tags of the answer's own envelope, and nothing else. A
# judge that writes its answer in tool-call syntax leaves the field's
# closing tag on the end of the field (2026-10-13, #50: every reason in
# two runs ended `</reason>\n</invoke>\n`), and the value is otherwise
# the answer. Narrow on purpose: a reason quoting a tag of the tutor's
# own — `</div>`, say — is the tutor's words and stays.
_ENVELOPE = re.compile(
    r"(?:\s*</(?:[A-Za-z][\w.-]*:)?(?:pass|reason|invoke|parameter|function_calls)\s*>)+\s*\Z",
    re.IGNORECASE,
)


def _undressed(value: object) -> object:
    return _ENVELOPE.sub("", value) if isinstance(value, str) else value


def _from_text(said: object) -> Optional[Dict]:
    """The answer out of the result text: the whole of it when that is
    JSON, else the first JSON object in it that looks like an answer,
    which is what a judge that wrapped its answer in prose or markup
    leaves behind.

    The first object in the text is not necessarily the answer. A
    reason quotes the tutor, and the tutor talks about code, so the
    preamble to a wrapped answer can hold an object of its own
    (`the tutor wrote {"name": "x"} in package.json`). Taking that one
    would report "no answer" for a record that has one, and a missing
    answer becomes a failed criterion downstream — the false FAIL this
    is here to prevent. So an object carrying a verdict wins, and the
    first object is only the fallback.
    """
    if not isinstance(said, str):
        return None
    decoder = json.JSONDecoder()
    fallback = None
    for i, ch in enumerate(said):
        if ch == "{":
            try:
                found, _ = decoder.raw_decode(said, i)
            except ValueError:
                continue
            if isinstance(found, dict):
                if isinstance(found.get("pass"), bool):
                    return found
                if fallback is None:
                    fallback = found
    return fallback


def _answered(answer: object) -> bool:
    """Whether this is a verdict and not merely an object.

    A boolean, not just a `pass` key: `graders.judge` reads it through
    `bool()`, so `"pass": "false"` would pass the criterion — a silent
    false green, the one failure this suite cannot afford, and nobody
    reads the reason of a verdict that passed. The schema would have
    caught it, but an answer salvaged from the result text never went
    through the schema, so the check has to be here.
    """
    return isinstance(answer, dict) and isinstance(answer.get("pass"), bool)


def judge_answer(record: object, where: str = "") -> Dict:
    """The judge's answer, out of the record `claude -p` returned.

    `structured_output` is the answer when the call went well, and the
    same JSON is in `result`. When it did not, the harness has to say
    which of two things happened, because they cost different things:
    a judge that answered oddly is a formatting problem, and a judge
    that never ran (an expired credential, a timeout) is not an answer
    at all. Neither is the tutor failing a criterion, which is what a
    missing `pass` turns into downstream.

    So an answer is taken wherever one can be found, and only a record
    with none in it is an error — reported in the record's own words,
    naming the file to read rather than truncating the record into the
    verdict.
    """
    hint = f"; the record is in {where}" if where else ""
    if not isinstance(record, dict):
        return {"error": f"not a result record: {str(record)[:200]}{hint}"}
    answer = record.get("structured_output")
    if not _answered(answer):
        answer = _from_text(record.get("result")) or answer
    if _answered(answer):
        return {k: _undressed(v) for k, v in answer.items()}
    said = record.get("result")
    if record.get("is_error") and isinstance(said, str) and said.strip():
        return {"error": f"the judge did not run: {said.strip()[:300]}{hint}"}
    return {"error": f"no answer in the judge's record{hint}"}


def _keep(out: Optional[Path], stdout: str, stderr: str) -> None:
    """The record as it came back, beside the turn streams."""
    if out is None:
        return
    out.write_text(stdout, encoding="utf-8")
    if stderr.strip():
        out.with_suffix(".stderr").write_text(stderr, encoding="utf-8")


def ask_judge(prompt: str, env: Dict[str, str], cwd: Path, model: str, schema: str, timeout: int = 300,
              out: Optional[Path] = None) -> Dict:
    """One tool-less `claude -p` answering with JSON against schema.
    The raw record is kept at out, the way a turn's stream is."""
    cmd = ["claude", "-p", prompt, "--model", model, "--tools", "", "--output-format", "json",
           "--json-schema", schema, "--no-session-persistence"]
    where = out.name if out is not None else ""
    hint = f"; the record is in {where}" if where else ""
    # No stdin: the CLI waits seconds for input that is never coming.
    try:
        res = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        # What it had printed by then is kept, so say so: this is the
        # one error whose record is a partial rather than a whole.
        _keep(out, _text(e.stdout), _text(e.stderr))
        return {"error": f"the judge timed out after {timeout}s" + hint}
    _keep(out, res.stdout, res.stderr)
    try:
        record = json.loads(res.stdout)
    except ValueError:
        said = (res.stderr or res.stdout).strip()[:500]
        return {"error": (said or "the judge printed nothing") + hint}
    return judge_answer(record, where)


def _text(raw: object) -> str:
    """What a timed-out subprocess captured, which is bytes or str or
    nothing depending on how far it got."""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return raw if isinstance(raw, str) else ""
