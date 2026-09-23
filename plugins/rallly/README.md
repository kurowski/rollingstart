# rallly

The Rolling Start map for [Rallly](https://github.com/lukevella/rallly),
as a map plugin: the landscape of the codebase, three suggested
courses through it, and eleven lessons, in the format
[`docs/map.md`](https://github.com/kurowski/rollingstart/blob/main/docs/map.md)
defines. Install it beside the
`rolling` plugin in any Rallly clone and the tutor teaches from it;
nothing is added to the clone's tree. The map's own claims (every
path, line, sha, and pull request number) were checked against the
checkout the manifest's `metadata.rolling.ref` names, and the version
follows the convention the format sets: the Rallly release the map
was last validated against.

This is the demo, and the external-author route: Rallly is not ours to
commit a map to, so the map lives here. A project that would rather
carry its map commits the same directory as `.rolling/` in its tree,
and the tutor prefers that copy whenever it exists.

## Installing

In a Rallly clone, in Claude Code:

```
/plugin marketplace add kurowski/rollingstart
/plugin install rolling@rollingstart
/plugin install rallly@rollingstart
```

Then `/rolling:start`. The map plugin registers itself when a session
starts, so a plugin installed during a session is found at the next
one.

Two things the tutor needs from the environment, neither of which it
will set up itself. A git identity (`user.name` and `user.email`), so
that the checkpoint the tutor commits on a lesson's throwaway branch
is yours; without one the toolkit commits it under its own name and
says so. And standing permission for the toolkit's own commands, in
your user settings or the clone's `.claude/settings.local.json`, so
that a lesson which needs your reply mid-way is not stranded when the
next turn's command is a fresh permission decision:

```json
{
  "permissions": {
    "allow": [
      "Bash(rolling-show *)", "Bash(rolling-claim-session *)", "Bash(rolling-write *)",
      "Bash(rolling-note *)", "Bash(rolling-begin-lesson *)", "Bash(rolling-begin-task *)",
      "Bash(rolling-verify)", "Bash(rolling-verify *)", "Bash(rolling-report)",
      "Bash(rolling-keep-task)", "Bash(rolling-end-task)", "Bash(rolling-close-task)",
      "Bash(rolling-export *)", "Skill(rolling:lesson)", "Skill(rolling:task)"
    ]
  }
}
```

These are the toolkit's own commands, none of which touches the tree
except through a lesson's branch; no Rallly command is among them, so
a database reset still asks.

## What the lessons expect to find running

The map's `## Environment` section says it in full. In short: Rallly's
services (`docker-compose.dev.yml`: postgres, redis, an S3 stand-in, a
mail catcher) are a precondition, brought up by you before a lesson,
never by the tutor; the toolchain (Node 24, the pnpm `packageManager`
pins) is installed per `CONTRIBUTING.md`; and unit tests, the type
check, lint, and the structure check, which every exercise's verifier
is made of, need no service at all. The database operations and the
integration tests do, and the map says which.

## Updating the map

The map changes when Rallly does. A new plugin version is a new
release of this map; `/plugin update rallly@rollingstart` brings it,
and not before, so a lesson in progress keeps the map it started with.
When the tutor says the map was checked against a release your clone
does not have, fetch, tags included.
