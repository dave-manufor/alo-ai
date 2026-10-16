---
trigger: always_on
description: Alo.ai core rules for Antigravity. Always on.
---

Read and follow `AGENTS.md` at the repo root; it is the source of truth. The area folder's `AGENTS.md` adds local rules.

Non-negotiable:
- Agents plan, code scores: only `aloai_scoring.py` produces numbers.
- Never commit secrets, `.env`, real children's audio, names or transcripts, or large files.
- Screening language only (never: diagnosis, dyslexia, behind, failing, hyperlexic, word caller).
- Contract change = schema + fixture + `schema_version` + tag the consumer, in one PR.
- Scoring/[CAL] change needs W3 approval, version bump, validation rerun, PRD changelog line.
- Prompt/model change: rerun its eval set and paste the result in the PR.
- Infra only through Terraform; server settings only via `chore/infra-...` PR.
- UI follows the design system as closely as possible; deviate only when impossible and explain in the PR.
- Never commit to `main`; branch `type/scope-description`; commit `type(scope): what`; nobody merges their own PR.
- Review ring: W1 reviewed by W2 or W3, W2 by W3, W3 by W2.
- Skills: `.agent/skills/` (symlink to `.agents/skills/`); use the `alo-*` skills for these workflows.
