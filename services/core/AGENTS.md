# services/core: Core service (shared; split by subfolder)

One Cloud Run service (and the book-ingestion job image) holding four parts. Subfolder owner decides reviewer.

| Folder | Owner | Reviewer | PRD |
|---|---|---|---|
| `generator/` Passage Generator (Story Writer + Critic, gate, bank fallback, `queue_story`) | W2 | W3 | 4.5 |
| `books/` Book catalogue and ingestion job | W2 | W3 | 9 |
| `grader/` Quick endpoint, two-pass Gemini Pro grading, report assembly, book ranking | W3 | W2 | 7, 10.3-10.4 |
| `coach/` Reading Coach (ADK agent, activity library, validator) | W3 | W2 | 3.1, 8 |

- The four parts share one service account today, but each agent's tool limits still come from `libs/aloai/aloai_authz.py`. Call `authorize()` before every agent tool.
- **LLMs score propositions and items only; code computes everything else** (`aloai_scoring.py`). No agent can write a score, report, level or profile.
- Coach output passes the guardrail validator (numbers match the report, banned words rejected) before sending; on second failure use the template summary and flag `COACH_TEMPLATE_USED`.
- Prompt or model changes: `alo-prompt-eval`. Structured outputs are validated against `schemas/`.
- Child's interest-chat words never reach the generator; only taxonomy tags and a safe detail do.
