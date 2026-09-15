# shellcheck shell=bash
# Shared by every script in ../bin. Sourced, never run. Bash 3.2 or later:
# no associative arrays, no mapfile, no case conversion; an empty array is
# expanded as ${arr[@]+"${arr[@]}"} because 3.2 with `set -u` treats a
# bare "${arr[@]}" on an empty array as an unbound variable.
#
# Three things live here: where the map and the learner's directory are,
# how frontmatter is read (the flat subset docs/map.md defines, parsed
# with awk), and the small checks every script repeats (slug shape,
# argument safety).

# ---------------------------------------------------------------- where

# The repository's top level, or nothing (status 1) outside one.
rolling_toplevel() {
  git rev-parse --show-toplevel 2>/dev/null
}

# The map directory for the repository at $1 (a top level).
rolling_map_dir() {
  printf '%s/.rolling' "$1"
}

# A path encoded the way Claude Code encodes its own project directories:
# every byte that is not a letter or a digit becomes '-'.
rolling_encode() {
  printf '%s' "$1" | LC_ALL=C tr -c 'A-Za-z0-9' '-'
}

# The learner's directory for the repository at $1. Needs ROLLING_DATA,
# which the plugin's SessionStart hook exports from CLAUDE_PLUGIN_DATA;
# prints nothing and returns 1 when it is unset, and the caller says so.
rolling_learner_dir() {
  [ -n "${ROLLING_DATA:-}" ] || return 1
  printf '%s/repos/%s' "$ROLLING_DATA" "$(rolling_encode "$1")"
}

# The one message for the unset case, so every script says the same thing.
# shellcheck disable=SC2034  # used by every script that sources this file
rolling_no_data_msg='the learner directory cannot be resolved: ROLLING_DATA is not set (the rolling plugin sets it at session start; a script run outside a session needs it set by hand)'

# ---------------------------------------------------------- frontmatter

# All of these read the block between a `---` on line 1 and the next line
# that is exactly `---`. Keys are matched at column 1; a map's entries are
# the two-space-indented `key: value` lines that follow its key.

# 0 if the file opens with a frontmatter block.
fm_has() {
  awk '{ sub(/\r$/, "") } NR==1 { if ($0 != "---") exit 1; next } /^---$/ { found = 1; exit } END { exit found ? 0 : 1 }' "$1" 2>/dev/null
}

# The block's lines, without the fences.
fm_block() {
  awk '{ sub(/\r$/, "") } NR==1 { next } /^---$/ { exit } { print }' "$1" 2>/dev/null
}

# Every top-level key, in order, one per line.
fm_keys() {
  fm_block "$1" | awk '/^[^ \t#][^:]*:/ { k = $0; sub(/:.*$/, "", k); print k }'
}

# The value of the first top-level `KEY: value` line, trimmed.
fm_scalar() {
  fm_block "$1" | FM_KEY=$2 awk 'BEGIN { k = ENVIRON["FM_KEY"] }
    index($0, k ":") == 1 && substr($0, length(k)+1, 1) == ":" {
      v = substr($0, length(k)+2); sub(/^[ \t]+/, "", v); sub(/[ \t]+$/, "", v); print v; exit }'
}

# Every value of a repeated top-level `KEY: value` line (scope:, verify:).
fm_values() {
  fm_block "$1" | FM_KEY=$2 awk 'BEGIN { k = ENVIRON["FM_KEY"] }
    index($0, k ":") == 1 && substr($0, length(k)+1, 1) == ":" {
      v = substr($0, length(k)+2); sub(/^[ \t]+/, "", v); sub(/[ \t]+$/, "", v); if (v != "") print v }'
}

# The items of a list under KEY, one per line: `KEY: [a, b]` on one line
# or `KEY:` followed by `  - item` lines. An empty list prints nothing.
fm_list() {
  fm_block "$1" | FM_KEY=$2 awk 'BEGIN { k = ENVIRON["FM_KEY"] }
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
    inlist && /^  - / { v = substr($0, 5); print trim(v); next }
    inlist { inlist = 0 }
    index($0, k ":") == 1 && substr($0, length(k)+1, 1) == ":" {
      v = trim(substr($0, length(k)+2))
      if (v == "") { inlist = 1; next }
      if (substr(v, 1, 1) == "[") {
        v = substr(v, 2); sub(/\]$/, "", v)
        n = split(v, parts, ",")
        for (i = 1; i <= n; i++) { p = trim(parts[i]); if (p != "") print p }
      }
      exit
    }'
}

# The entries of a map under KEY as `subkey<TAB>value` lines.
fm_map() {
  fm_block "$1" | FM_KEY=$2 awk 'BEGIN { k = ENVIRON["FM_KEY"] }
    inmap && /^  [A-Za-z0-9_-]+:/ {
      sk = $1; sub(/:$/, "", sk)
      v = $0; sub(/^  [A-Za-z0-9_-]+:[ \t]*/, "", v); sub(/[ \t]+$/, "", v)
      print sk "\t" v; next }
    inmap && /^[^ ]/ { exit }
    index($0, k ":") == 1 && substr($0, length(k)+1, 1) == ":" { inmap = 1 }'
}

# The value for SUBKEY under map KEY, verbatim.
fm_map_get() {
  fm_map "$1" "$2" | FM_SUB=$3 awk '{ i = index($0, "\t"); if (substr($0, 1, i - 1) == ENVIRON["FM_SUB"]) { print substr($0, i + 1); exit } }'
}

# ----------------------------------------------------------------- body

# 0 if the body has a level-2 heading with exactly this text.
body_has_h2() {
  grep -q "^## $2[[:space:]]*$" "$1" 2>/dev/null
}

# The region slugs a map declares: the bold slug opening each bullet
# under `## Regions`.
map_regions() {
  awk '/^## Regions[[:space:]]*$/ { s = 1; next } /^## / { s = 0 } s && /^- \*\*[a-z0-9-]+\*\*/ {
    x = $0; sub(/^- \*\*/, "", x); sub(/\*\*.*$/, "", x); print x }' "$1" 2>/dev/null
}

# The course names a map declares: `###` headings under the suggested
# course(s) heading.
map_courses() {
  awk '/^## Suggested courses?[[:space:]]*$/ { s = 1; next } /^## / { s = 0 } s && /^### / { x = $0; sub(/^### /, "", x); print x }' "$1" 2>/dev/null
}

# ---------------------------------------------------------------- checks

# 0 if $1 is a slug: lowercase kebab-case.
slug_ok() {
  [[ $1 =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]
}

# 0 if $1 is a command or operation key.
key_ok() {
  [[ $1 =~ ^[a-z0-9-]+$ ]]
}

# 0 if $1 is 7 to 40 hex characters.
hex_ok() {
  [[ $1 =~ ^[0-9a-f]{7,40}$ ]]
}

# 0 if $1 carries nothing a shell would interpret: no metacharacter, no
# glob, no quote. Arguments on a verify line are words and nothing else.
args_safe() {
  case $1 in
    *[\$\`\;\&\|\<\>\(\)\{\}\\\"\'\*\?\[]*) return 1 ;;
    *[[:cntrl:]]*) return 1 ;;
  esac
  return 0
}

# 0 if $1, a map command line, may take arguments appended after it: it
# must not end in a control operator, or the appended "$@" would become a
# command of its own and the arguments a command line.
command_takes_args() {
  local c=$1
  c=${c%"${c##*[! 	]}"}   # trim trailing spaces and tabs
  case $c in
    ''|*';'|*'&'|*'|'|*'>'|*'<'|*\\|*'#'*) return 1 ;;
  esac
  return 0
}

# 0 if $1 is a repository-relative path with no `..` segment and no
# leading slash.
relpath_ok() {
  case $1 in
    /*|*/../*|../*|*/..|..|''|./*|*/./*|.|*/.|*//*) return 1 ;;
  esac
  return 0
}

# 0 if no component of $2 (relative to top level $1), the path itself
# included, is a symbolic link. A held test is applied and reverted
# through this path, and a link anywhere in it would let the apply write
# outside the repository or the revert lose a file the link stood for.
no_symlink_in() {
  local top=$1 p=$2 cur="" seg globbing=1
  local IFS=/
  case $- in *f*) globbing=0 ;; esac
  set -f   # split on /, never glob
  # shellcheck disable=SC2086  # splitting on / is the point
  set -- $p
  [ "$globbing" -eq 0 ] || set +f
  for seg in "$@"; do
    [ -n "$seg" ] || continue
    cur="${cur:+$cur/}$seg"
    [ ! -L "$top/$cur" ] || return 1
  done
  return 0
}

# Split $1 on single spaces into the array named $2 (bash 3.2 has no
# `readarray`; `read -a` does the job).
split_words() {
  # shellcheck disable=SC2034  # the caller reads the array by name
  IFS=' ' read -r -a "$2" <<< "$1"
}

# ------------------------------------------------------- held test aside

# While rolling-verify has the held test applied, it keeps a record in the
# learner's directory: held-aside/ holds any learner file it set aside
# (same relative path, copied in full before the original is removed),
# and held-aside.pending lists what it did, one line each, `dir <path>`,
# `aside <path>`, or `applied <path>`, each written before the step it
# names is taken. A kill the trap cannot catch (SIGKILL, the Bash tool's
# timeout) leaves both behind; every script that touches the tree
# finishes the revert first, through held_finish_pending, so the held
# test never lingers and the learner's file is never lost. Order is fixed
# whatever the record says: held copies removed, then set-aside files
# restored, then created directories removed. $1 = learner dir, $2 = top
# level; $3 = "quiet" to say nothing on success (rolling-verify's own
# run, where a revert is the normal ending, not a repair). Failures are
# always printed. Returns 1 if a step failed; the record is kept so the
# next run tries again. A set-aside copy that is missing cannot be
# retried, so it clears the record but sets held_incomplete=1 for the
# caller to report; the learner's file at that path is gone.
# shellcheck disable=SC2034  # read by rolling-verify after the call
held_incomplete=0
held_finish_pending() {
  local learner=$1 top=$2 quiet=${3:-} marker rc=0 kind p
  marker="$learner/held-aside.pending"
  held_incomplete=0
  [ -f "$marker" ] || return 0
  while read -r kind p; do
    [ "$kind" = applied ] && [ -n "$p" ] || continue
    [ -e "$top/$p" ] || [ -L "$top/$p" ] || continue
    if rm -rf "${top:?}/$p" 2>/dev/null; then [ -n "$quiet" ] || echo "HELD reverted: removed the held copy left at $p"
    else echo "HELD REVERT FAILED: could not remove the held copy at $p"; rc=1; fi
  done < "$marker"
  while read -r kind p; do
    [ "$kind" = aside ] && [ -n "$p" ] || continue
    if [ ! -e "$learner/held-aside/$p" ] && [ ! -L "$learner/held-aside/$p" ]; then
      echo "HELD REVERT INCOMPLETE: no set-aside copy of $p was found; if you had a file there before the last run, it is gone"
      # shellcheck disable=SC2034  # read by rolling-verify after the call
      held_incomplete=1; continue
    fi
    if mkdir -p "$(dirname -- "$top/$p")" 2>/dev/null && mv -f "$learner/held-aside/$p" "$top/$p" 2>/dev/null; then [ -n "$quiet" ] || echo "HELD reverted: restored your file at $p"
    else echo "HELD REVERT FAILED: your file is still at $learner/held-aside/$p; put it back at $p by hand"; rc=1; fi
  done < "$marker"
  # Deepest directories first, whatever order they were recorded in.
  awk '$1 == "dir" && NF > 1 { sub(/^dir /, ""); print length, $0 }' "$marker" | sort -rn | while read -r _ p; do
    [ -n "$p" ] && rmdir "$top/$p" 2>/dev/null
  done
  if [ "$rc" -eq 0 ]; then
    rm -f "$marker"; rm -rf "$learner/held-aside"
  fi
  return "$rc"
}
