# libs: shared libraries (W3, reviewed by W2)

`aloai_scoring` (every formula in PRD 6), `aloai_authz` (agent authorization, 12.1), `aloai_guardrails` (output checks on agent text, 3.1). Read PRD 6, 12.1, 13.3 and the root `AGENTS.md` first.

- `aloai_scoring` is the **only source of numbers**. Pure functions, no network, no LLM. Any change to a formula, [CAL] constant, allowlist or profile rule needs W3 approval, a new `scoring_module` version, a validation rerun and a PRD changelog line. Use `alo-scoring-change`.
- 100% line coverage for all three libraries (130 tests are described in the PRD, to be added to `tests/`). Never lower a threshold or delete a test to pass.
- `aloai_authz`: allowlist per agent plus run context built server-side from the verified token. The model never supplies the context. `FORBIDDEN_TOOLS` (write score/report/level/profile, change consent, delete child, charge/refund, change subscription, free-form SQL) stay refused for every agent.
- `aloai_guardrails`: every number in agent text must match a tool result; banned words (diagnosis, dyslexia, behind, failing, hyperlexic, word caller) rejected; length limits.
- Other services import these; keep public signatures stable and tell consumers on the PR.
