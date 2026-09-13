#!/usr/bin/env node
// Hook handler for the learner's coding session in a `direct` lesson.
// Claude Code runs it on UserPromptSubmit, PostToolUse, and Stop, with the
// event as JSON on stdin (fields per docs: hook_event_name, session_id,
// transcript_path, user_prompt, tool_name, tool_input). It appends one
// compact line per event to .rolling/profile/session.log, which is the
// tutor's record of how the learner directed the agent: every prompt and
// every file edited or command run, in order. On Stop it also appends the
// agent's last reply, read from the transcript on a best-effort basis
// (that file's format is internal, so a failure there is silent).
//
// Never blocks or alters the session: always exits 0 with no output.
import { readFileSync, appendFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";

const out = join(process.cwd(), ".rolling", "profile", "session.log");
const cut = (s, n = 800) => { s = String(s).replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n) + ` […${s.length - n} more]` : s; };
const stamp = () => new Date().toISOString().slice(11, 19);

let ev;
try { ev = JSON.parse(readFileSync(0, "utf8")); } catch { process.exit(0); }
let line = null;
switch (ev.hook_event_name) {
  case "SessionStart":
    line = `SESSION ${ev.session_id || "?"} started`; break;
  case "UserPromptSubmit":
    line = `LEARNER: ${cut(ev.user_prompt ?? ev.prompt ?? "")}`; break;
  case "PostToolUse": {
    const i = ev.tool_input || {};
    const what = i.file_path || i.command || i.pattern || i.notebook_path || i.description || i.prompt || "";
    line = `  ${ev.tool_name || "tool"}${what ? ": " + cut(what, 300) : ""}`; break;
  }
  case "Stop": {
    let last = "";
    try {
      const lines = readFileSync(ev.transcript_path, "utf8").split("\n").filter(Boolean);
      for (let k = lines.length - 1; k >= 0 && !last; k--) {
        const r = JSON.parse(lines[k]);
        if (r.type !== "assistant") continue;
        const c = r.message?.content;
        const text = Array.isArray(c) ? c.filter((b) => b.type === "text").map((b) => b.text).join(" ") : (typeof c === "string" ? c : "");
        if (text.trim()) last = text;
      }
    } catch { /* internal format; fine */ }
    line = `AGENT: ${last ? cut(last) : "(reply not captured)"}`; break;
  }
  default: process.exit(0);
}
try {
  mkdirSync(dirname(out), { recursive: true });
  if (!existsSync(out)) appendFileSync(out, `# coding session log (direct lesson); one line per prompt, tool call, and reply\n`);
  appendFileSync(out, `[${stamp()}] ${line}\n`);
} catch { /* never block the session */ }
process.exit(0);
