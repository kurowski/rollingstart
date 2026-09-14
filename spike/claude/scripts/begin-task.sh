#!/bin/sh
# Put the repository into a task's starting state on a throwaway branch,
# committed, so the learner begins from a clean working tree and nothing
# about the answer is sitting in `git diff` or an editor gutter.
#
#   begin-task.sh <lesson> --fix <sha> <keep-path>...
#       The task is a real fix, reverted. Branch from the fix's parent and
#       bring only the listed paths (its tests) forward from the fix, so
#       the code is as it was before the fix and the test that proves the
#       fix is present and failing. The fix commit itself is not in the
#       branch's history.
#
#   begin-task.sh <lesson> --here
#       The task starts from the current commit plus whatever the tutor has
#       already added to the working tree (a new test, say). Branch here
#       and commit those changes, excluding .rolling/ and .claude/.
#
# Prints the lines task.md needs: branch, base, return-to. Refuses to run
# on a dirty tree in --fix mode, since a branch switch would carry the
# changes along. Exits non-zero on refusal: this is run by the tutor from
# a skill's instructions, not as an inline command, so a real status is
# right here.
set -eu
root=$(git rev-parse --show-toplevel)
cd "$root"
lesson=${1:?usage: begin-task.sh <lesson> --fix <sha> <keep-path>... | --here}
mode=${2:?usage: begin-task.sh <lesson> --fix <sha> <keep-path>... | --here}
shift 2
lesson=$(printf '%s' "$lesson" | tr -cs 'A-Za-z0-9._-' '-')

excl='. :(exclude).rolling :(exclude).claude'
# shellcheck disable=SC2086
dirty=$(git status --porcelain -- $excl)
return_to=$(git symbolic-ref -q --short HEAD || git rev-parse HEAD)
branch="rolling/$lesson-$(date +%Y%m%d-%H%M)"
git check-ref-format "refs/heads/$branch" || { echo "'$lesson' does not make a valid branch name"; exit 1; }
git show-ref --verify -q "refs/heads/$branch" && { echo "branch $branch already exists"; exit 1; }

case "$mode" in
  --fix)
    fix=${1:?--fix needs the fix commit sha}; shift
    [ $# -ge 1 ] || { echo "--fix needs at least one path to keep from the fix (its test)"; exit 1; }
    [ -z "$dirty" ] || { printf 'working tree is not clean; commit, stash, or discard first:\n%s\n' "$dirty"; exit 1; }
    git cat-file -e "$fix^{commit}" || { echo "$fix is not a commit"; exit 1; }
    fix=$(git rev-parse "$fix")
    git rev-parse -q --verify "$fix^" >/dev/null || { echo "$fix is a root commit; pick another fix"; exit 1; }
    git rev-parse -q --verify "$fix^2" >/dev/null 2>&1 && { echo "$fix is a merge commit; pick another fix"; exit 1; }
    # Every keep-path must be one the fix touched, or the checkout below
    # would fail after the branch switch and strand the tree mid-way.
    for p in "$@"; do
      git diff --name-only "$fix^" "$fix" -- "$p" | grep -q . || { echo "$p is not changed by $fix; keep-paths must be its test files"; exit 1; }
    done
    git switch -q -c "$branch" "$fix^"
    git checkout -q "$fix" -- "$@"
    git commit -q -m "rolling: starting state for $lesson

The code as it was before $(git log -1 --format=%h "$fix"), with that
commit's test brought forward so it is present and failing. A Rolling
Start task; the branch is throwaway."
    ;;
  --here)
    git switch -q -c "$branch"
    # shellcheck disable=SC2086
    git add -A -- $excl
    if git diff --cached --quiet; then
      echo "note: nothing to commit; the starting state is the current commit"
    else
      git commit -q -m "rolling: starting state for $lesson

The current commit plus the files the task adds. A Rolling Start task;
the branch is throwaway."
    fi
    ;;
  *) echo "unknown mode $mode"; exit 1 ;;
esac

rm -f "$root/.rolling/profile/session.log"   # a task that actually started starts a new record
echo "branch: $branch"
echo "base: $(git rev-parse HEAD)"
echo "return-to: $return_to"
