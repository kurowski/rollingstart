"""The ask hook: a command that runs an operation the map marks
destructive is answered `ask`, naming the operation; a near miss, a
map that marks nothing, and no map at all are silence.

The head rule and the command splitting are driven with strings; the
decision through a real map, in the tree and as a registered map
plugin, so the resolver is the thing being read; and the handler
through its executable, as a hook is run.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from shlex import quote as shlex_quote

from support import MAP, SETUP_LESSON, WorldTest

from rolling import ask

REMOTE = "https://github.com/someone/scratch-target.git"

SCRATCH_OPS = """operations:
  seed: sh -c 'echo seeded'
  reset: sh -c 'echo reset'
destructive:
  - reset
"""

# A realistic pair: a head of two words, and a sibling that is not
# destructive, so silence can be told from "nothing is marked".
REAL_OPS = """operations:
  reset-db: pnpm db:reset --force
  seed-db: pnpm db:seed
destructive:
  - reset-db
"""

NOTHING_MARKED = """operations:
  reset-db: pnpm db:reset --force
  seed-db: pnpm db:seed
"""


def op(key: str, command: str) -> ask.Operation:
    return ask.Operation(key, command, ask.head(command))


RESET = op("reset-db", "pnpm db:reset --force")


class HeadTest(unittest.TestCase):
    def test_the_words_before_the_first_flag(self):
        self.assertEqual(ask.head("pnpm db:reset --force"), ["pnpm", "db:reset"])
        self.assertEqual(ask.head("pnpm db:reset"), ["pnpm", "db:reset"])
        self.assertEqual(ask.head("python3 scripts/reset_ledger.py"), ["python3", "scripts/reset_ledger.py"])
        self.assertEqual(ask.head("pnpm --filter @x/web db:reset"), ["pnpm"],
                         "a flag early makes a short head: safe, and noisy")

    def test_not_a_leading_cd(self):
        # `cd x && <operation>` is what a monorepo's author writes. A
        # head of `cd apps/web` asks on every bare cd and is silent on
        # the reset: wrong in both directions at once.
        self.assertEqual(ask.head("cd apps/web && pnpm db:reset --force"), ["pnpm", "db:reset"])
        self.assertEqual(ask.head("(cd packages/database && pnpm prisma migrate reset --force)"),
                         ["pnpm", "prisma", "migrate", "reset"])
        self.assertEqual(ask.head("pushd db; make reset"), ["make", "reset"])
        self.assertEqual(ask.head("cd a && cd b"), [], "nothing but the way there is no head")

    def test_not_the_substitution_that_finds_the_way(self):
        # `git rev-parse` is how the operation finds the top, not what
        # it does. As a head it asked about every rev-parse in the
        # session and said nothing about the reset.
        self.assertEqual(ask.head('cd "$(git rev-parse --show-toplevel)" && pnpm db:reset --force'),
                         ["pnpm", "db:reset"])
        self.assertEqual(ask.head('cd $(dirname "$0") && pnpm db:reset --force'), ["pnpm", "db:reset"])

    def test_not_a_guard(self):
        self.assertEqual(ask.head("[ -f ledger.json ] && python3 scripts/reset.py"),
                         ["python3", "scripts/reset.py"])
        self.assertEqual(ask.head("test -f x && make reset"), ["make", "reset"])

    def test_a_shell_wrapper_is_read_through(self):
        self.assertEqual(ask.head("sh -c 'rm -rf tmp/db'"), ["rm"], "not `sh`, which every session mentions")
        self.assertEqual(ask.head('/bin/bash -c "pnpm db:reset --force"'), ["pnpm", "db:reset"])
        self.assertEqual(ask.head("bash -c 'cd sub && pnpm db:reset --force'"), ["pnpm", "db:reset"])
        self.assertEqual(ask.head("sh reset.sh"), ["sh", "reset.sh"], "a script is not a command string")

    def test_the_first_command_of_a_chain(self):
        # The words of the whole chain are the head of nothing, and the
        # point is to ask before the chain starts.
        self.assertEqual(ask.head("make resetdb && make seed"), ["make", "resetdb"])
        self.assertEqual(ask.head("pnpm db:reset; pnpm db:seed"), ["pnpm", "db:reset"])

    def test_quoting_comes_off_and_assignments_are_stepped_over(self):
        self.assertEqual(ask.head('"pnpm" db:reset'), ["pnpm", "db:reset"])
        self.assertEqual(ask.head("FORCE=1 pnpm db:reset --force"), ["pnpm", "db:reset"])

    def test_nothing_before_a_flag_is_no_head(self):
        for command in ["", "   ", "--force", "-x reset"]:
            self.assertEqual(ask.head(command), [], repr(command))


class CommandsInTest(unittest.TestCase):
    def test_every_operator_that_starts_a_command(self):
        self.assertEqual(ask.commands_in("cd apps/web && pnpm db:reset"), ["cd apps/web", "pnpm db:reset"])
        self.assertEqual(ask.commands_in("a; b | c || d & e"), ["a", "b", "c", "d", "e"])
        self.assertEqual(ask.commands_in("a\nb"), ["a", "b"])
        self.assertEqual(ask.commands_in("(cd x && pnpm db:reset)"), ["cd x", "pnpm db:reset"])

    def test_an_operator_inside_quotes_is_text(self):
        line = "git commit -m 'stop running pnpm db:reset; it drops rows'"
        self.assertEqual(ask.commands_in(line), [line])
        self.assertEqual(ask.commands_in('echo "a; b"'), ['echo "a; b"'])

    def test_a_substitution_opens_a_command_quoted_or_not(self):
        self.assertIn("pnpm db:reset", ask.commands_in('echo "$(pnpm db:reset)"'))
        self.assertIn("pnpm db:reset", ask.commands_in("echo $(pnpm db:reset)"))
        self.assertIn("pnpm db:reset", ask.commands_in("echo `pnpm db:reset`"))

    def test_a_backslash_keeps_the_next_character_literal(self):
        self.assertEqual(ask.commands_in(r"echo a\; pnpm db:reset"), [r"echo a\; pnpm db:reset"])

    def test_a_redirection_ends_the_commands_words(self):
        # A redirection starts no new command, but the shell takes it
        # off the word before it, and without the break
        # `pnpm db:reset>out.log` leaves `db:reset>out.log` as one word
        # and the head's words are no longer next to each other.
        self.assertEqual(ask.commands_in("pnpm db:reset > log"), ["pnpm db:reset", "log"])
        self.assertEqual(ask.commands_in("pnpm db:reset>log"), ["pnpm db:reset", "log"])
        self.assertEqual(ask.commands_in("pnpm db:reset > log 2>&1")[0], "pnpm db:reset")

    def test_a_single_quoted_substitution_is_text_as_the_shell_has_it(self):
        self.assertEqual(ask.commands_in("echo '$(pnpm db:reset)'"), ["echo '$(pnpm db:reset)'"])


class WordsTest(unittest.TestCase):
    def test_assignments_and_a_leading_dot_slash_come_off(self):
        self.assertEqual(ask.words("FORCE=1 pnpm db:reset"), ["pnpm", "db:reset"])
        self.assertEqual(ask.words("python3 ./scripts/reset.py"), ["python3", "scripts/reset.py"])
        self.assertEqual(ask.words("./.rolling/reset-db"), [".rolling/reset-db"])
        self.assertEqual(ask.words("./x"), ["x"])
        self.assertEqual(ask.words("./"), ["./"], "nothing would be left")

    def test_a_command_that_will_not_parse_loses_its_stray_quotes(self):
        self.assertEqual(ask.words("' pnpm db:reset"), ["pnpm", "db:reset"])
        self.assertEqual(ask.words('" pnpm db:reset'), ["pnpm", "db:reset"])


class WrappedTest(unittest.TestCase):
    def test_a_shells_dash_c_however_it_is_spelled(self):
        for line, want in [("sh -c 'pnpm db:reset'", "pnpm db:reset"),
                           ("bash -lc 'pnpm db:reset'", "pnpm db:reset"),
                           ("sh -ec 'pnpm db:reset'", "pnpm db:reset"),
                           ("bash -xc 'pnpm db:reset'", "pnpm db:reset"),
                           ("sh -c -x 'pnpm db:reset'", "pnpm db:reset"),
                           ("sh -c -- 'pnpm db:reset'", "pnpm db:reset"),
                           ("bash --norc -c 'pnpm db:reset'", "pnpm db:reset"),
                           ("/bin/bash -c 'pnpm db:reset'", "pnpm db:reset"),
                           ('eval "pnpm db:reset --force"', "pnpm db:reset --force")]:
            self.assertEqual(ask.wrapped(ask.words(line)), want, line)

    def test_a_wrapper_in_front_of_the_shell(self):
        # The command line is one quoted word, so searching the words
        # cannot find the operation in it; the shell has to be found
        # wherever it sits.
        for line in ["timeout 20 sh -c 'pnpm db:reset --force'", "sudo sh -c 'pnpm db:reset'",
                     "env sh -c 'pnpm db:reset'", "nice -n 5 bash -c 'pnpm db:reset'",
                     "sudo -u postgres sh -c 'pnpm db:reset'", "/usr/bin/env sh -c 'pnpm db:reset'",
                     "sh run.sh && sh -c 'pnpm db:reset'"]:
            self.assertEqual(ask.wrapped(ask.words(line))[:13], "pnpm db:reset", line)

    def test_what_is_not_a_wrapper(self):
        for line in ["sh script.sh", "sh -c", "sh", "pnpm db:reset", "eval", "python3 -c 'print(1)'"]:
            self.assertIsNone(ask.wrapped(ask.words(line)), line)

    def test_the_reading_stops_going_deeper(self):
        deep = "pnpm db:reset"
        for _ in range(6):
            deep = "sh -c " + shlex_quote(deep)
        self.assertIsNone(ask.matched(deep, [RESET]), "a wrapper nested past the cap is not read")
        self.assertIsNotNone(ask.matched("sh -c 'sh -c \"pnpm db:reset\"'", [RESET]))


class MatchedTest(unittest.TestCase):
    def hit(self, line: str, note: str = "") -> None:
        self.assertIs(ask.matched(line, [RESET]), RESET, note or line)

    def miss(self, line: str, note: str = "") -> None:
        self.assertIsNone(ask.matched(line, [RESET]), note or line)

    def test_the_four_shapes_the_tutor_types(self):
        self.hit("pnpm db:reset")                       # alone, without the declared flag
        self.hit("pnpm db:reset --force")               # as declared
        self.hit("pnpm db:reset --force --yes")         # with arguments added
        self.hit("cd apps/web && pnpm db:reset --force")  # in a chain, after a cd
        self.hit("cd apps/web; pnpm db:reset")
        self.hit("FORCE=1 pnpm db:reset")
        self.hit("pnpm db:reset > reset.log")
        self.hit("pnpm db:reset --force > reset.log 2>&1")
        self.hit("pnpm db:reset>reset.log", "a redirection glued to the word before it")
        self.hit("pnpm \\\n  db:reset --force", "a line continuation")

    def test_a_near_miss_says_nothing(self):
        self.miss("pnpm db:reset-docs")
        self.miss("pnpm db:resetx --force")
        self.miss("pnpmx db:reset")
        self.miss("pnpm db:seed")
        self.miss("pnpm run db:reset", "a word between is a different command")

    def test_the_head_must_start_a_command(self):
        self.miss("git commit -m 'stop running pnpm db:reset'")
        self.miss("echo 'run pnpm db:reset when you are ready'")
        self.miss("grep -r 'pnpm db:reset' .")

    def test_a_command_after_a_double_quoted_substitution(self):
        # The substitution's closing quote was once read as an opening
        # one, and every break after it taken for text, so an ordinary
        # `cd "$(...)" && <operation>` went unnoticed.
        self.hit('cd "$(git rev-parse --show-toplevel)" && pnpm db:reset --force')
        self.hit('echo "$(date)" ; pnpm db:reset --force')
        self.hit('echo "resetting at $(date)"; pnpm db:reset')
        self.hit('test -n "$(ls)" && pnpm db:reset')
        self.hit('echo "`date`" ; pnpm db:reset')
        self.hit('echo "${X:-$(date)}"; pnpm db:reset')
        self.hit('VAR="$(date)" pnpm db:reset')
        self.miss('echo "a; b" ; ls', "the quote is back on after the substitution closed")

    def test_the_shapes_a_guard_or_a_wrapper_puts_it_in(self):
        self.hit("if [ -f db ]; then pnpm db:reset; fi")
        self.hit("for x in 1 2; do pnpm db:reset; done")
        self.hit("true && ! pnpm db:reset")
        self.hit("env FORCE=1 pnpm db:reset")
        self.hit("sudo pnpm db:reset")
        self.hit("sh -c 'pnpm db:reset'")
        self.hit('eval "pnpm db:reset"')
        self.hit('/bin/bash -c "pnpm db:reset --force"')

    def test_the_way_to_an_operation_is_not_the_operation(self):
        cd = op("reset-db", "cd apps/web && pnpm db:reset --force")
        self.assertIsNone(ask.matched("cd apps/web", [cd]), "a bare cd is not a reset")
        self.assertIsNone(ask.matched("cd apps/web && pnpm build", [cd]))
        self.assertIs(ask.matched("cd apps/web && pnpm db:reset --force", [cd]), cd)
        self.assertIs(ask.matched("pnpm db:reset", [cd]), cd, "already in the directory, same reset")

    def test_inside_a_substitution_counts_unless_the_shell_would_not_run_it(self):
        self.hit("echo $(pnpm db:reset)")
        self.hit('echo "$(pnpm db:reset)"')
        self.hit("echo `pnpm db:reset`")
        self.miss("echo '$(pnpm db:reset)'", "single quotes: the shell prints it, it does not run it")

    def test_the_maps_order_decides_which_operation_is_named(self):
        wipe = op("wipe-all", "pnpm db:wipe")
        line = "pnpm db:reset && pnpm db:wipe"
        self.assertIs(ask.matched(line, [RESET, wipe]), RESET)
        self.assertIs(ask.matched(line, [wipe, RESET]), wipe)

    def test_an_operation_with_no_head_matches_nothing(self):
        self.assertIsNone(ask.matched("pnpm db:reset", [op("odd", "--force")]))


class AgainstTheShellTest(unittest.TestCase):
    """The shell decides what a command line runs; this hook only reads
    it. So the reading is checked against the authority: `pnpm` becomes
    a stub that records being called, each line runs under `sh -c` in a
    throwaway directory, and what happened is compared with what
    `matched` said.

    This is here because the splitting has had two fail-opens, and a
    fail-open is the whole failure this hook exists not to have. Both
    would have been caught by this test on the day they were written.
    """

    RUN = "pnpm db:reset --force"

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="rolling-test.shell."))
        self.addCleanup(shutil.rmtree, str(self.root), True)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        self.work = self.root / "work"
        (self.work / "sub").mkdir(parents=True)
        stub = bin_dir / "pnpm"
        stub.write_text('#!/bin/sh\nif [ "$1" = db:reset ]; then echo ran >> "$MARK"; fi\nexit 0\n',
                        encoding="utf-8")
        stub.chmod(0o755)
        self.mark = self.work / "mark"
        self.env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}", MARK=str(self.mark))

    def shell_ran(self, line: str) -> bool:
        if self.mark.exists():
            self.mark.unlink()
        subprocess.run(["sh", "-c", line], cwd=str(self.work), env=self.env,
                       capture_output=True, timeout=30, check=False)
        return self.mark.exists()

    def test_nothing_the_shell_runs_goes_unasked(self):
        run = self.RUN
        lines = [
            run, "pnpm db:reset", f"{run} --yes",
            f"cd sub && {run}", f"cd sub; {run}", f"(cd sub && {run})", f"{{ {run}; }}",
            f'cd "$(pwd)" && {run}', f'echo "$(date)" ; {run}', f'test -n "$(ls)" && {run}',
            f'D="$(pwd)"; {run}', f'V="$(date)" {run}', f'echo "`date`" ; {run}',
            f'echo "${{X:-$(date)}}"; {run}', f"echo $(date) ; {run}",
            f"FORCE=1 {run}", f"env FORCE=1 {run}", f"nohup {run}", f"command {run}",
            f"if true; then {run}; fi", f"for x in 1; do {run}; done",
            f"true && ! false && {run}", f"false || {run}",
            f"sh -c '{run}'", f"bash -c '{run}'", f"/bin/sh -c '{run}'", f'eval "{run}"',
            f"echo $({run})", f'echo "$({run})"', f"echo `{run}`",
            f"{run} > out.log", f"{run} > out.log 2>&1", f"{run} | cat", f"ls\n{run}",
            # a wrapper's own option, whose argument cannot be told
            # from a command, so the head is looked for anywhere
            f"timeout 20 {run}", f"nice -n 5 {run}", f"/usr/bin/env {run}", f"stdbuf -o0 {run}",
            # a compound inside a wrapper: only the first command of it
            # was read once, and the second is the one that runs
            f"sh -c 'cd sub && {run}'", f"bash -c 'echo hi; {run}'", f'eval "cd sub && {run}"',
            f"bash -lc '{run}'", f"sh -ec '{run}'", f"sh -c -x '{run}'", f"bash --norc -c '{run}'",
            # a heredoc body with an apostrophe leaves the rest of the
            # line unparseable, and the operation after it still counts
            f"cat > f <<EOF\nthe user's notes\nEOF\n{run}",
            # a wrapper in front of the shell: the command line is one
            # quoted word, so the search of the words cannot find it
            f"timeout 20 sh -c '{run}'", f"env sh -c '{run}'", f"nice -n 5 bash -c '{run}'",
            # a redirection glued on, and a line continuation
            f"{run}>out.log", "pnpm \\\n  db:reset --force",
        ]
        missed = [line for line in lines
                  if self.shell_ran(line) and ask.matched(line, [RESET]) is None]
        self.assertEqual(missed, [], "the shell ran the operation and the hook said nothing")

    def test_what_the_shell_does_not_run_is_mostly_quiet(self):
        run = self.RUN
        for line in ["pnpm db:reset-docs", "pnpm run db:reset", f"echo '{run}'",
                     f"echo '$({run})'", "git commit -m 'do not pnpm db:reset'",
                     "cd sub", "cd sub && echo built"]:
            self.assertFalse(self.shell_ran(line), line)
            self.assertIsNone(ask.matched(line, [RESET]), line)

    def test_a_condition_the_hook_cannot_know_is_asked_about_anyway(self):
        # `false && <operation>` never reaches it, and the hook has no
        # way to know that. Asking is the safe side of being wrong.
        for line in [f"false && {self.RUN}", f"while false; do {self.RUN}; done"]:
            self.assertFalse(self.shell_ran(line), line)
            self.assertIsNotNone(ask.matched(line, [RESET]), line)


class ReasonTest(unittest.TestCase):
    def test_it_names_the_operation_and_what_was_declared(self):
        reason = ask.reason_for(RESET)
        self.assertIn("reset-db", reason)
        self.assertIn("pnpm db:reset --force", reason)
        self.assertIn("yours", reason, "the learner reads this in the prompt")

    def test_a_long_declaration_is_cut(self):
        long = op("reset-db", "pnpm db:reset " + "x" * 400)
        reason = ask.reason_for(long)
        self.assertLess(len(reason), 400)
        self.assertIn("...", reason)


class DecideTest(WorldTest):
    """Through a real map, found the way a session finds it."""

    def set_ops(self, text: str) -> None:
        m = self.w.read(".rolling/map.md")
        self.assertIn(SCRATCH_OPS, m)
        self.w.write(".rolling/map.md", m.replace(SCRATCH_OPS, text))

    def drop_tree_map(self) -> None:
        self.w.git("rm", "-r", "-q", ".rolling")
        self.w.git("commit", "-q", "-m", "no map in the tree")

    def event(self, command: str, tool: str = "Bash", cwd: Path = None) -> ask.Event:
        return ask.Event(cwd=cwd or self.w.top, tool=tool, command=command)

    def decide(self, command: str, **kw) -> str:
        return ask.decide(self.event(command, **kw), str(self.w.data))

    def test_it_asks_for_the_maps_destructive_operation(self):
        self.set_ops(REAL_OPS)
        reason = self.decide("cd apps/web && pnpm db:reset")
        self.assertIsNotNone(reason)
        self.assertIn("reset-db", reason)

    def test_silence_for_a_near_miss_and_for_what_is_not_marked(self):
        self.set_ops(REAL_OPS)
        self.assertIsNone(self.decide("pnpm db:reset-docs"))
        self.assertIsNone(self.decide("pnpm db:seed"), "declared, and not destructive")

    def test_silence_when_the_map_marks_nothing(self):
        self.set_ops(NOTHING_MARKED)
        self.assertIsNone(self.decide("pnpm db:reset --force"))

    def test_silence_with_no_map_at_all(self):
        self.set_ops(REAL_OPS)
        self.w.git("add", "-A")
        self.w.git("commit", "-q", "-m", "a destructive operation")
        self.assertIsNotNone(self.decide("pnpm db:reset"), "the map is there first")
        self.drop_tree_map()
        self.assertIsNone(self.decide("pnpm db:reset"))

    def test_the_map_comes_through_the_resolver_so_a_plugins_map_counts(self):
        root = self.w.root / "plugin-map"
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps(
            {"name": "scratchmap", "version": "0.1.0",
             "metadata": {"rolling": {"repo": "*/scratch-target", "ref": ""}}}), encoding="utf-8")
        (root / "map.md").write_text(MAP.replace(SCRATCH_OPS, REAL_OPS), encoding="utf-8")
        (root / "lessons").mkdir()
        (root / "lessons" / "setup.md").write_text(SETUP_LESSON, encoding="utf-8")
        reg = self.w.data.parent / "scratchmap-scratchmarket"
        reg.mkdir(parents=True)
        (reg / "root").write_text(str(root) + "\n", encoding="utf-8")
        self.w.git("remote", "add", "origin", REMOTE)
        self.drop_tree_map()
        reason = self.decide("pnpm db:reset --force")
        self.assertIsNotNone(reason, "no map in the tree, and the registered plugin declares this repository")
        self.assertIn("reset-db", reason)

    def test_silence_outside_a_repository_and_for_another_tool(self):
        self.set_ops(REAL_OPS)
        self.assertIsNone(self.decide("pnpm db:reset", cwd=self.w.root))
        self.assertIsNone(self.decide("pnpm db:reset", tool="Edit"))
        self.assertIsNone(self.decide("   "))

    def test_an_unreadable_map_is_silence_not_a_failure(self):
        self.w.write(".rolling/map.md", "no frontmatter here\n")
        self.assertIsNone(self.decide("pnpm db:reset"))


class RegistrationTest(unittest.TestCase):
    """The handler is no use unless hooks.json runs it. Nothing else in
    the gate would notice the entry going missing."""

    def test_hooks_json_runs_it_on_pretooluse_for_bash(self):
        from support import PLUGIN
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
        mine = [entry for entry in hooks
                if any("rolling-ask" in h.get("command", "") for h in entry.get("hooks", []))]
        self.assertEqual(len(mine), 1, "one entry, beside the allow hook's")
        self.assertEqual(mine[0]["matcher"], "Bash", "Bash only: a Skill call runs no shell")
        command = mine[0]["hooks"][0]["command"]
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/rolling-ask", command)
        self.assertIn("${CLAUDE_PLUGIN_DATA}", command, "the resolver needs the data directory for a map plugin")


class HandlerTest(WorldTest):
    """The executable, driven as hooks.json runs it."""

    def run_hook(self, event, data: str = None) -> str:
        from support import BIN
        args = [str(BIN / "rolling-ask")]
        args.append(str(self.w.data) if data is None else data)
        res = subprocess.run(args, input=event if isinstance(event, str) else json.dumps(event),
                             capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def setUp(self) -> None:
        super().setUp()
        m = self.w.read(".rolling/map.md")
        self.w.write(".rolling/map.md", m.replace(SCRATCH_OPS, REAL_OPS))

    def test_it_asks_in_the_documented_shape(self):
        out = self.run_hook({"session_id": "s", "cwd": str(self.w.top), "tool_name": "Bash",
                             "tool_input": {"command": "pnpm db:reset --force", "description": "reset"}})
        d = json.loads(out)["hookSpecificOutput"]
        self.assertEqual((d["hookEventName"], d["permissionDecision"]), ("PreToolUse", "ask"))
        self.assertIn("reset-db", d["permissionDecisionReason"])

    def test_silence_for_a_near_miss_and_for_anything_malformed(self):
        for event in [{"cwd": str(self.w.top), "tool_name": "Bash", "tool_input": {"command": "pnpm db:reset-docs"}},
                      {"cwd": str(self.w.top), "tool_name": "Bash", "tool_input": {"command": 7}},
                      {"cwd": str(self.w.top), "tool_name": "Bash"},
                      {"tool_name": "Skill", "tool_input": {"skill": "rolling:lesson"}},
                      "garbage", "", "[]", "42"]:
            self.assertEqual(self.run_hook(event), "", repr(event))

    def test_it_works_with_no_data_directory_given(self):
        # The tree's map needs no registrations; a learner whose session
        # start has not run still gets the prompt.
        out = self.run_hook({"cwd": str(self.w.top), "tool_name": "Bash",
                             "tool_input": {"command": "pnpm db:reset"}}, data="")
        self.assertIn("reset-db", json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
