#!/usr/bin/env node
// Print a compact, readable log of a Claude Code session: what the learner
// said, what the agent said back, and what it did (files edited, commands
// run). For the tutor to read after a `direct` lesson, so feedback is
// about how the learner directed the agent, turn by turn, not about a
// single pasted brief.
//
//   node .claude/scripts/transcript.mjs <session-id | path.jsonl> [--since <ISO time>] [--exclude <id>]
//   node .claude/scripts/transcript.mjs --latest [--since <ISO time>] [--exclude <id>]
//
// Sessions live in ~/.claude/projects/<encoded cwd>/<id>.jsonl. --latest
// picks the most recently modified session for this working directory
// other than --exclude (the tutor passes its own id) and, with --since,
// only sessions touched after the task began. Thinking blocks and tool
// results are omitted; long text is cut. Always exits 0.
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const args = process.argv.slice(2);
const opt = (name) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined; };
const since = opt("--since") ? Date.parse(opt("--since")) : 0;
const exclude = opt("--exclude") || "";
const configDir = process.env.CLAUDE_CONFIG_DIR || join(homedir(), ".claude");
const projectDir = join(configDir, "projects", process.cwd().replace(/[^A-Za-z0-9]/g, "-"));
const CUT = 600;

function resolveFile() {
  const target = args.find((a) => !a.startsWith("--") && a !== opt("--since") && a !== opt("--exclude"));
  if (target && target.endsWith(".jsonl")) return target;
  if (target) return join(projectDir, `${target}.jsonl`);
  if (!existsSync(projectDir)) return null;
  const candidates = readdirSync(projectDir)
    .filter((f) => f.endsWith(".jsonl") && !f.startsWith(exclude))
    .map((f) => ({ f, m: statSync(join(projectDir, f)).mtimeMs }))
    .filter((c) => c.m >= since)
    .sort((a, b) => b.m - a.m);
  return candidates.length ? join(projectDir, candidates[0].f) : null;
}

const file = resolveFile();
if (!file || !existsSync(file)) {
  console.log(`TRANSCRIPT: none found (looked in ${projectDir}${since ? `, modified since ${new Date(since).toISOString()}` : ""})`);
  process.exit(0);
}

const cut = (s) => (s.length > CUT ? s.slice(0, CUT) + ` […${s.length - CUT} more chars]` : s);
const one = (s) => s.replace(/\s+/g, " ").trim();
let turns = 0, tools = 0;
console.log(`TRANSCRIPT: ${file}`);
for (const line of readFileSync(file, "utf8").split("\n")) {
  if (!line.trim()) continue;
  let r; try { r = JSON.parse(line); } catch { continue; }
  if (r.type !== "user" && r.type !== "assistant") continue;
  const m = r.message || {};
  const content = typeof m.content === "string" ? [{ type: "text", text: m.content }] : (m.content || []);
  const when = r.timestamp ? r.timestamp.slice(11, 19) : "        ";
  for (const b of content) {
    if (r.type === "user" && b.type === "text") {
      const t = one(b.text);
      if (!t || t.startsWith("<")) continue; // system-injected reminders, command output wrappers
      turns++; console.log(`\n[${when}] LEARNER: ${cut(t)}`);
    } else if (r.type === "assistant" && b.type === "text") {
      const t = one(b.text); if (t) console.log(`[${when}] AGENT: ${cut(t)}`);
    } else if (r.type === "assistant" && b.type === "tool_use") {
      tools++;
      const i = b.input || {};
      const what = i.file_path || i.command || i.pattern || i.notebook_path || i.description || "";
      console.log(`[${when}]   ${b.name}${what ? ": " + cut(one(String(what))) : ""}`);
    }
  }
}
console.log(`\nTRANSCRIPT: ${turns} learner turns, ${tools} tool calls`);
