#!/usr/bin/env bash
# rolling-show: every subcommand, present and absent, always exit 0.
. "$(dirname "$0")/lib.sh"
scratch_world

out=$(rolling-show map); assert_status "map" 0 $?
assert_contains "map prints the map" "name: Scratch" "$out"
out=$(rolling-show lessons)
assert_contains "lessons is an index" "### greet-politely" "$out"
assert_contains "lessons carries frontmatter" "requires: [setup]" "$out"
assert_not_contains "lessons omits bodies" "## Rubric" "$out"
out=$(rolling-show lesson setup)
assert_contains "lesson <slug> is whole" "## Rubric" "$out"
assert_contains "lesson missing" "no lesson 'nope'" "$(rolling-show lesson nope)"
assert_contains "lesson bad slug" "not a lesson slug" "$(rolling-show lesson 'Bad Slug')"
assert_contains "lesson with no task" "no open task" "$(rolling-show lesson)"
write_task "lesson: setup
mode: write
scope: src"
assert_contains "lesson resolves the open task's" "title: Setup" "$(rolling-show lesson)"
assert_contains "task" "lesson: setup" "$(rolling-show task)"
assert_contains "profile absent" "no profile" "$(rolling-show profile)"
mkdir -p "$LEARNER" && printf '# Profile\n' > "$LEARNER/profile.md"
assert_contains "profile present" "# Profile" "$(rolling-show profile)"
assert_contains "corpus" "## Corpus" "$(rolling-show corpus)"
assert_not_contains "corpus starts at the heading" "## Regions" "$(rolling-show corpus)"
assert_contains "tree clean" "(clean)" "$(rolling-show tree)"
echo x > src/new.sh
assert_contains "tree dirty" "?? src/new.sh" "$(rolling-show tree)"
assert_contains "tree names the branch" "on main" "$(rolling-show tree)"
assert_eq "state-dir" "$LEARNER" "$(rolling-show state-dir)"
assert_contains "usage" "usage:" "$(rolling-show)"
out=$(ROLLING_DATA='' rolling-show profile); assert_status "unset data is not an error" 0 $?
assert_contains "unset data says so" "ROLLING_DATA is not set" "$out"
cd "$WORLD" || exit 1
assert_contains "outside a repo" "not inside a git repository" "$(rolling-show map)"
finish
