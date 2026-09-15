#!/usr/bin/env bash
# The shared library: frontmatter parsing and the small checks.
. "$(dirname "$0")/lib.sh"
scratch_world

f="$WORLD/fm.md"
cat > "$f" <<'EOF'
---
name: Thing
mode: write
requires: [a, b ,c]
assumes:
  - x
  - y
empty: []
commands:
  check: sh check.sh
  test: sh run-test.sh   # a comment
scope: one
scope: two
---

## Body

name: not-a-field
EOF

assert_eq "fm_has" 0 "$(fm_has "$f"; echo $?)"
assert_eq "fm_scalar" "Thing" "$(fm_scalar "$f" name)"
assert_eq "fm_scalar ignores the body" "" "$(fm_scalar "$f" nothing)"
assert_eq "fm_values repeated key" "one two" "$(fm_values "$f" scope | tr '\n' ' ' | sed 's/ $//')"
assert_eq "fm_list flow" "a b c" "$(fm_list "$f" requires | tr '\n' ' ' | sed 's/ $//')"
assert_eq "fm_list block" "x y" "$(fm_list "$f" assumes | tr '\n' ' ' | sed 's/ $//')"
assert_eq "fm_list empty" "" "$(fm_list "$f" empty)"
assert_eq "fm_keys" "name mode requires assumes empty commands scope scope" "$(fm_keys "$f" | tr '\n' ' ' | sed 's/ $//')"
assert_eq "fm_map_get" "sh check.sh" "$(fm_map_get "$f" commands check)"
assert_eq "fm_map_get is verbatim, comment included" "sh run-test.sh   # a comment" "$(fm_map_get "$f" commands test)"
assert_eq "fm_map_get missing" "" "$(fm_map_get "$f" commands nope)"
printf 'no frontmatter\n---\nx: 1\n---\n' > "$WORLD/nofm.md"
assert_eq "fm_has needs --- on line 1" 1 "$(fm_has "$WORLD/nofm.md"; echo $?)"

assert_eq "map_regions" "greeting platform" "$(map_regions "$REPO/.rolling/map.md" | tr '\n' ' ' | sed 's/ $//')"
assert_eq "map_courses" "Generalist" "$(map_courses "$REPO/.rolling/map.md")"
assert_eq "body_has_h2" 0 "$(body_has_h2 "$REPO/.rolling/lessons/setup.md" Rubric; echo $?)"

assert_eq "slug ok" 0 "$(slug_ok poll-data-model; echo $?)"
assert_eq "slug rejects caps" 1 "$(slug_ok Poll-Model; echo $?)"
assert_eq "slug rejects double hyphen" 1 "$(slug_ok a--b; echo $?)"
assert_eq "hex ok" 0 "$(hex_ok abcdef1; echo $?)"
assert_eq "hex too short" 1 "$(hex_ok abcde; echo $?)"
assert_eq "args safe" 0 "$(args_safe "src/x.test.sh --flag"; echo $?)"
assert_eq "args reject semicolon" 1 "$(args_safe "a; rm -rf /"; echo $?)"
assert_eq "args reject glob" 1 "$(args_safe "*.sh"; echo $?)"
assert_eq "args reject quote" 1 "$(args_safe "it's"; echo $?)"
assert_eq "relpath ok" 0 "$(relpath_ok "a/b.c"; echo $?)"
assert_eq "relpath rejects absolute" 1 "$(relpath_ok "/etc/passwd"; echo $?)"
assert_eq "relpath rejects dotdot" 1 "$(relpath_ok "a/../b"; echo $?)"
assert_eq "encode" "-home-pat-rallly" "$(rolling_encode /home/pat/rallly)"
assert_eq "learner dir under ROLLING_DATA" "$ROLLING_DATA/repos/$(rolling_encode "$REPO")" "$LEARNER"
assert_eq "learner dir needs ROLLING_DATA" 1 "$(ROLLING_DATA='' rolling_learner_dir "$REPO"; echo $?)"
finish
