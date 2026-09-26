"""The citation check rolling-note runs on every entry: which `path:line`s
an entry cites, and which of them point nowhere in the working tree."""

from __future__ import annotations

import json
import unittest

from support import WorldTest

from rolling import citations


class FindTest(unittest.TestCase):
    def cited(self, text):
        return [str(c) for c in citations.find(text)]

    def test_the_shapes_feedback_uses(self):
        text = ("- billing/invoice.py:14 — the total; the language's norm. Met.\n"
                "- see `src/greet.sh:3` and the comment at poll.prisma:76.\n"
                "- lines tests/greet.test.sh:2-4, and ./run-test.sh:3\n"
                "- an en dash range, src/greet.sh:1–3, and a column, src/greet.sh:2:5\n"
                "- an extensionless file under a directory, bin/rolling-note:4\n")
        self.assertEqual(self.cited(text), [
            "billing/invoice.py:14", "src/greet.sh:3", "poll.prisma:76", "tests/greet.test.sh:2-4",
            "./run-test.sh:3", "src/greet.sh:1-3", "src/greet.sh:2", "bin/rolling-note:4"])

    def test_things_that_are_not_citations(self):
        text = ("Served on http://localhost:3000 and https://example.com:8443/x.py:9 at 12:30, "
                "release v4.15.2:1 is not a path, nor 1.2.3:4, nor Makefile:3, nor a sha f61c0970:2.")
        self.assertEqual(self.cited(text), ["v4.15.2:1"], "a dotted version with a letter reads as a file name; the check then finds no such file")

    def test_each_citation_once(self):
        self.assertEqual(self.cited("src/greet.sh:3, again src/greet.sh:3"), ["src/greet.sh:3"])


class CheckTest(WorldTest):
    def flags(self, text):
        return citations.check(text, self.w.repo)

    def test_citations_that_land_are_silent(self):
        self.assertEqual(self.flags("src/greet.sh:3, tests/greet.test.sh:1-4, ./run-test.sh:1, src/../check.sh:2"), [])

    def test_a_line_past_the_end(self):
        self.assertEqual(self.flags("src/greet.sh:4"), ["src/greet.sh:4 — the file has 3 lines"])
        self.assertEqual(self.flags("src/greet.sh:2-9"), ["src/greet.sh:2-9 — the file has 3 lines"], "a range is checked at its end")

    def test_a_file_that_is_not_there(self):
        self.assertEqual(self.flags("src/totals.sh:14"), ["src/totals.sh:14 — no such file in the working tree"], "src/ is in the tree")
        self.assertEqual(self.flags("src:1"), [], "no extension and no directory: not a citation")
        self.assertEqual(self.flags("src/:1"), [], "a trailing slash is not a file name")
        self.assertEqual(self.flags("tests/greet.test.sh/x.sh:1"), ["tests/greet.test.sh/x.sh:1 — no such file in the working tree"])

    def test_what_could_not_have_been_a_file_passes(self):
        """A path under a directory the tree lacks, or a bare name no file
        carries, is a host, an image, or an attribute more often than a
        citation; a false flag costs more than a missed one."""
        for said in ("self.total:5", "summary.total:4", "db.example.com:5432", "redis.internal:6379",
                     "localhost/api:8080", "docker.io/library/python:3.9", "billing/invoice.py:14", "invoice.py:14"):
            self.assertEqual(self.flags(said), [], said)

    def test_a_directory(self):
        self.w.write("src/v2.d/x.sh", "x\n")
        self.assertEqual(self.flags("src/v2.d:1"), ["src/v2.d:1 — a directory, not a file"])

    def test_a_path_that_climbs(self):
        """Written from a directory below the top, as a tutor in a package
        might: what follows the climb is searched for, and a climb out of
        the repository finds nothing and is silent."""
        self.w.write("apps/api/src/handler.ts", "x\n" * 20)
        self.assertEqual(self.flags("../api/src/handler.ts:12"), [])
        self.assertEqual(self.flags("../api/src/handler.ts:30"), ["../api/src/handler.ts:30 — the file has 20 lines"])
        self.assertEqual(self.flags("../../src/greet.sh:3"), [])
        self.assertEqual(self.flags("../elsewhere/x.py:1"), [], "nothing of that name here")
        self.assertEqual(self.flags("src/../../x.py:1"), [])
        self.w.write("docs/README.md", "a\nb\nc\n")
        self.w.write("apps/docs/README.md", "x\n" * 100)
        self.assertEqual(self.flags("../docs/README.md:80"), [], "a climb was not written from the top, so the top's docs/ does not hide apps/docs/")
        self.assertEqual(self.flags("docs/README.md:80"), ["docs/README.md:80 — the file has 3 lines"], "written from the top, judged as written")

    def test_line_zero(self):
        self.assertEqual(self.flags("src/greet.sh:0"), ["src/greet.sh:0 — there is no line 0"])
        self.assertEqual(self.flags("greet.sh:0"), ["greet.sh:0 — there is no line 0"])
        self.assertEqual(self.flags("self.count:0, tests.failed:0, db.example.com:0"), [], "a counter at zero is not a file")

    def test_a_bare_name_is_found_anywhere_in_the_repository(self):
        self.assertEqual(self.flags("greet.sh:3"), [], "src/greet.sh has line 3")
        self.assertEqual(self.flags("greet.sh:9"), ["greet.sh:9 — the file has 3 lines"])
        self.w.write("other/greet.sh", "\n" * 12)
        self.assertEqual(self.flags("greet.sh:9"), [], "an untracked greet.sh has line 9")
        self.assertEqual(self.flags("nowhere.py:1"), [], "no file of that name: not taken for a file")

    def test_a_path_that_left_out_its_package_directory(self):
        self.w.write("apps/web/src/lib/poll.ts", "x\n" * 50)
        self.assertEqual(self.flags("src/lib/poll.ts:40"), [], "src/ is in the tree, but apps/web/src/lib/poll.ts is what was meant")
        self.assertEqual(self.flags("web/src/lib/poll.ts:40"), [])
        self.assertEqual(self.flags("src/lib/poll.ts:999"), ["src/lib/poll.ts:999 — the file has 50 lines"])
        self.assertEqual(self.flags("web/src/lib/poll.ts:999"), ["web/src/lib/poll.ts:999 — the file has 50 lines"], "web/ is not in the tree, but the suffix is")
        self.assertEqual(self.flags("pp/web/src/lib/poll.ts:1"), [], "a suffix is whole path segments")

    def test_a_bare_name_at_the_top_does_not_hide_a_longer_one_below(self):
        self.w.write("package.json", "{\n}\n")
        self.w.write("apps/web/package.json", "{\n" + "\n" * 38 + "}\n")
        self.assertEqual(self.flags("package.json:30"), [], "apps/web/package.json has line 30")
        self.assertEqual(self.flags("package.json:90"), ["package.json:90 — no file of that name has that many lines (the longest of 2 has 40)"])

    def test_ignored_files_are_not_found_by_bare_name(self):
        self.w.write(".gitignore", "build/\n")
        self.w.write("build/out.js", "\n" * 50)
        self.assertEqual(self.flags("out.js:10"), [], "an ignored file is not found by name, and a name nothing carries is not flagged")
        self.assertEqual(self.flags("build/out.js:10"), [], "named by its path, it is in the working tree")

    def test_the_working_tree_not_head(self):
        self.w.write("src/greet.sh", "a\nb\nc\nd\ne\n")
        self.assertEqual(self.flags("src/greet.sh:5"), [], "the learner's uncommitted change is what is read")
        (self.w.top / "src/greet.sh").unlink()
        self.assertEqual(self.flags("src/greet.sh:1"), ["src/greet.sh:1 — no such file in the working tree"])
        self.assertEqual(self.flags("greet.sh:1"), ["greet.sh:1 — no such file in the working tree"], "deleted below the top")
        (self.w.top / "check.sh").unlink()
        self.assertEqual(self.flags("check.sh:1"), ["check.sh:1 — no such file in the working tree"], "deleted at the top, the same")

    def test_a_last_line_without_a_newline_counts(self):
        self.w.write("src/tail.sh", "one\ntwo")
        self.assertEqual(self.flags("src/tail.sh:2"), [])
        self.w.write("src/empty.sh", "")
        self.assertEqual(self.flags("src/empty.sh:1"), ["src/empty.sh:1 — the file has 0 lines"])


SID = "8b1f0c2e-1111-4222-8333-944455556666"


class ReplyHookTest(WorldTest):
    """The Stop hook, driven the way Claude Code drives it: the event on
    stdin, the data directory as the argument, a decision (or silence)
    on stdout."""

    def setUp(self):
        super().setUp()
        self.w.learner.dir.mkdir(parents=True, exist_ok=True)
        self.w.learner.session.write_text(SID + "\n", encoding="utf-8")
        self.transcript = self.w.root / "transcript.jsonl"

    def said(self, *blocks, earlier=()):
        """A transcript: an earlier turn, a prompt, then the turn's text
        blocks with a tool call and its result between each; the last
        block is left out, as Claude Code has not flushed it yet."""
        entries = []
        for text in earlier:
            entries += [{"type": "user", "message": {"content": "earlier"}},
                        {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}]
        entries.append({"type": "user", "message": {"content": [{"type": "text", "text": "/rolling:done"}]}})
        for text in blocks[:-1]:
            entries += [{"type": "assistant", "message": {"content": [{"type": "text", "text": text}, {"type": "tool_use", "id": "t", "name": "Bash", "input": {}}]}},
                        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "content": "src/nothing.sh:99"}]}},
                        {"type": "attachment"}]
        self.transcript.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        return {"session_id": SID, "cwd": str(self.w.top), "transcript_path": str(self.transcript),
                "last_assistant_message": blocks[-1], "stop_hook_active": False, "hook_event_name": "Stop"}

    def decide(self, ev, data=None):
        status, out = self.w.run("check-reply", str(self.w.data) if data is None else data, stdin=json.dumps(ev))
        self.assertEqual(status, 0, out)
        return json.loads(out) if out.strip() else None

    def test_a_citation_that_points_nowhere_keeps_the_turn_going(self):
        d = self.decide(self.said("Good change. See src/greet.sh:40 for the greeting."))
        self.assertEqual(d["decision"], "block")
        self.assertIn("src/greet.sh:40 — the file has 3 lines", d["reason"])
        self.assertTrue(d["reason"].startswith("Citation check:\n  src/greet.sh:40"))
        self.assertIn("withdraw the point", d["reason"])

    def test_every_block_of_the_turn_is_read(self):
        d = self.decide(self.said("First, src/greet.sh:40 is where it prints.", "Then, all good at src/greet.sh:3."))
        self.assertIn("src/greet.sh:40", d["reason"], "an early block, before a tool call, is read from the transcript")
        self.assertNotIn("src/nothing.sh", d["reason"], "tool output is not the tutor's words")
        d = self.decide(self.said("All good at src/greet.sh:3.", "But src/greet.sh:41 is wrong."))
        self.assertIn("src/greet.sh:41", d["reason"], "the final block comes from the event")

    def test_a_flushed_final_block_is_not_read_twice(self):
        ev = self.said("Fine at src/greet.sh:3.", "Off at src/greet.sh:50.")
        with self.transcript.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Off at src/greet.sh:50."}]}}) + "\n")
        self.assertEqual(self.decide(ev)["reason"].count("src/greet.sh:50"), 1)

    def test_earlier_turns_are_not_read(self):
        self.assertIsNone(self.decide(self.said("Now src/greet.sh:3.", earlier=["Before, src/greet.sh:77."])))

    def test_silent_when_nothing_points_nowhere(self):
        self.assertIsNone(self.decide(self.said("See src/greet.sh:3, and db.example.com:5432 was down.")))
        self.assertIsNone(self.decide(self.said("No citations at all.")))

    def test_the_turn_after_a_correction_always_ends(self):
        ev = self.said("Still src/greet.sh:40.")
        ev["stop_hook_active"] = True
        self.assertIsNone(self.decide(ev))

    def test_only_the_tutors_session(self):
        ev = self.said("See src/greet.sh:40.")
        ev["session_id"] = "0000-other"
        self.assertIsNone(self.decide(ev), "a coding session in the same repository is never checked")
        self.w.learner.session.unlink()
        ev["session_id"] = SID
        self.assertIsNone(self.decide(ev), "no claim, no tutor")
        self.w.task(lesson="greet-politely", mode="write", scope="src", tutor_session=SID)
        self.assertEqual(self.decide(ev)["decision"], "block", "the open task's stamp is the tutor's too")

    def test_a_held_test_between_its_runs_is_not_judged(self):
        self.w.task(lesson="greet-politely", mode="write", scope="src", tutor_session=SID, held="tests/held/greet.test.sh")
        self.assertIsNone(self.decide(self.said("The held test fails at tests/held/greet.test.sh:12: expected Hello.")))
        self.assertIsNone(self.decide(self.said("It fails at greet.test.sh:12.")), "by bare name too")
        self.assertEqual(self.decide(self.said("It fails at tests/held/greet.test.sh:12, see src/greet.sh:40."))["reason"].count("\n  "), 1, "the rest is still judged")

    def entries(self, *entries, last):
        self.transcript.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        return {"session_id": SID, "cwd": str(self.w.top), "transcript_path": str(self.transcript),
                "last_assistant_message": last, "stop_hook_active": False}

    @staticmethod
    def spoke(text, command=None):
        content = [{"type": "text", "text": text}]
        if command:
            content.append({"type": "tool_use", "id": "t", "name": "Bash", "input": {"command": command}})
        return {"type": "assistant", "message": {"content": content}}

    def test_what_was_said_before_the_tree_moved_is_not_judged(self):
        prompt = {"type": "user", "message": {"content": "yes, build it"}}
        for command in ("rolling-begin-task greet-politely --fix abc123 --held tests/greet.test.sh",
                        "rolling-end-task", "rolling-write patch --from-tree src/new.sh"):
            ev = self.entries(prompt, self.spoke("The fix changed src/new.sh:30.", command), last="Here is your task, in src/greet.sh:3.")
            self.assertIsNone(self.decide(ev), command)
        ev = self.entries(prompt, self.spoke("The fix changed src/new.sh:30.", "rolling-write patch <<'EOF'"), last="Done.")
        self.assertEqual(self.decide(ev)["decision"], "block", "a patch from a heredoc does not touch the tree")
        ev = self.entries(prompt, self.spoke("Before.", "rolling-end-task"), self.spoke("After, src/greet.sh:40.", "rolling-close-task"), last="Closed.")
        self.assertIn("src/greet.sh:40", self.decide(ev)["reason"], "what is said after the move is judged")

    def test_the_turn_starts_at_what_the_learner_typed(self):
        """The shapes real transcripts have: a typed skill is a string
        prompt followed by the skill's body as a meta entry; a skill handed
        off to mid-turn is a tool result then a meta entry."""
        typed = {"type": "user", "message": {"content": "<command-message>rolling:done</command-message>\n<command-name>/rolling:done</command-name>"}}
        body = {"type": "user", "isMeta": True, "message": {"content": [{"type": "text", "text": "Base directory for this skill: ... cite billing/x.py:9"}]}}
        handoff = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "s", "content": "Launching skill: rolling:lesson"}]}}
        ev = self.entries({"type": "user", "message": {"content": "earlier"}}, self.spoke("Earlier, src/greet.sh:77."),
                          typed, body, self.spoke("First, src/greet.sh:40."), handoff, body, last="Then the walkthrough.")
        reason = self.decide(ev)["reason"]
        self.assertIn("src/greet.sh:40", reason, "the hand-off's meta entry is not a new turn")
        self.assertNotIn("src/greet.sh:77", reason, "the typed command is")

    def test_a_torn_line_costs_only_itself(self):
        ev = self.said("First, src/greet.sh:40.", "Then fine.")
        with self.transcript.open("a", encoding="utf-8") as f:
            f.write('{"type": "assist')
        self.assertIn("src/greet.sh:40", self.decide(ev)["reason"])

    def test_anything_odd_lets_the_turn_end(self):
        ev = self.said("See src/greet.sh:40.")
        self.assertIsNone(self.decide(ev, data=""), "no data directory")
        self.assertIsNone(self.decide(dict(ev, cwd=str(self.w.root))), "not in a repository")
        self.assertIsNone(self.decide(dict(ev, cwd=str(self.w.root / "gone"))), "a cwd that is not there")
        self.assertEqual(self.decide(dict(ev, transcript_path=str(self.w.root / "none.jsonl")))["decision"], "block", "no transcript: the final block alone")
        self.transcript.write_text("not json\n")
        self.assertEqual(self.decide(ev)["decision"], "block", "an unreadable transcript: the final block alone")
        status, out = self.w.run("check-reply", str(self.w.data), stdin="[1, 2]")
        self.assertEqual((status, out), (0, ""))
        status, out = self.w.run("check-reply", str(self.w.data), stdin="{")
        self.assertEqual((status, out), (0, ""))


if __name__ == "__main__":
    unittest.main()
