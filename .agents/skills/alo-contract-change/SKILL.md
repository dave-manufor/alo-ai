---
name: alo-contract-change
description: Change a hand-off contract between workstreams (an API endpoint, event, Firestore document or schema). Use when editing anything in schemas/, fixtures/contracts/, or code that produces or consumes a PRD 14.2 contract.
---

# Alo.ai contract change

Contracts are the only way work crosses between W1, W2 and W3 (PRD 14.2, 13.5). The producer owns each one.

| Contract | Producer | Consumer |
|---|---|---|
| `POST /v1/sessions` | W1 | W2 |
| Session protocol (`play`, `show_passage`, `hide_passage`, `reconnecting`, clip list) | W2 | W1 |
| `POST /v1/grade:quick` | W3 | W2 |
| Events `phase1.recorded`, `session.done` | W2 | W3 |
| Passage artifact (PRD 10.1) | W2 | W3 |
| `books/{book_id}` with embedding | W2 | W3 |
| `ReadingReport` in `reports/{session_id}` (PRD 10.4) | W3 | W1 |
| `queue_story` | W2 | W3 |
| `/internal/notify` | W1 | W3 |
| Entitlement `subscriptions/{guardian_id}` | W1 | W2 |

## Steps
1. Identify the contract and its producer/consumer from the table. Read the PRD section that defines it.
2. Update the schema in `schemas/`; bump `schema_version` (breaking changes: new major).
3. Update the matching fixture in `fixtures/contracts/` in the **same PR**. Fictional data only.
4. Update producer code and any consumer code that must change; if the consumer is another person's area, leave a clear note rather than editing it silently.
5. Run contract tests (fixtures validate against schemas; producer output validates against the schema) and `make smoke` if the stack is up. Report real results.
6. In the PR, tag the consumer by name (see `alo-branch-and-pr` for handles) and tick the contract box in the template.
7. If the PRD text is now wrong, update it and add a changelog line.

Never edit a fixture just to make a failing producer test pass.
