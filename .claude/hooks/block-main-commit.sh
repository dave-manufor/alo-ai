#!/usr/bin/env bash
# PreToolUse hook (Bash): refuse `git commit` / `git push` while on main.
# CONTRIBUTING.md: never commit to main; every change goes through a pull request.
input="$(cat)"

case "$input" in
  *"git commit"*|*"git push"*) ;;
  *) exit 0 ;;
esac

# Use the directory the command runs in, so a worktree is judged by its own branch.
# Fall back to the project dir if that is not a git checkout.
branch="$(git branch --show-current 2>/dev/null)"
if [ -z "$branch" ]; then
  branch="$(git -C "${CLAUDE_PROJECT_DIR:-.}" branch --show-current 2>/dev/null)"
fi
if [ "$branch" = "main" ]; then
  echo "Blocked: you are on main. Create a branch first (type/scope-short-description), e.g. git checkout -b feat/session-told-word-prompt. See docs/CONTRIBUTING.md." >&2
  exit 2
fi
exit 0
