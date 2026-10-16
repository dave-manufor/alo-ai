@AGENTS.md

## Claude Code specifics

- Skills are loaded from `.claude/skills/` (a symlink to `.agents/skills/`). Invoke the `alo-*` skills for branch/PR, contract, scoring, prompt-eval, infra, UI and child-safety work.
- `.claude/settings.json` blocks reading `.env*`, force-pushes and pushes to `main`, and a PreToolUse hook (`.claude/hooks/block-main-commit.sh`) refuses `git commit` while on `main`. Create a branch first.
- Nested `CLAUDE.md` files in each area import that area's `AGENTS.md`.
- Personal overrides go in `CLAUDE.local.md` or `.claude/settings.local.json` (both git-ignored). Do not put personal preferences in this file.
