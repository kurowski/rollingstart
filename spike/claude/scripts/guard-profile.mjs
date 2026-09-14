#!/usr/bin/env node
// PreToolUse hook for the learner's coding session in a `direct` lesson:
// keep the agent out of .rolling/profile/, where the reference solution
// and the task's record live. Ripgrep already skips the profile because
// it is gitignored, so this covers the direct routes: a Read, Edit, or
// Write with that path, or a Bash command that names it. Everything else
// is allowed. Exits 0 always; a deny is expressed in the JSON output.
import { readFileSync } from "node:fs";
let ev;
try { ev = JSON.parse(readFileSync(0, "utf8")) ?? {}; } catch { process.exit(0); }
if (typeof ev !== "object" || Array.isArray(ev)) process.exit(0);
const i = ev.tool_input || {};
const probe = [i.file_path, i.path, i.command, i.pattern, i.notebook_path].filter(Boolean).join(" ");
if (/\.rolling\/profile\b/.test(probe)) {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ".rolling/profile is the tutor's; the coding session does not read or write it.",
    },
  }));
}
process.exit(0);
