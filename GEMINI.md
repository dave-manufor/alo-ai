@AGENTS.md

## Antigravity / Gemini specifics

- The full rules are in `AGENTS.md` above; follow them exactly. Antigravity also loads `.agent/rules/alo-core.md` (always on).
- Skills are available from `.agent/skills/` (a symlink to `.agents/skills/`). Workflows in `.agent/workflows/` are shortcuts that run the matching `alo-*` skill.
- Never commit to `main`; create a `type/scope-description` branch first.
