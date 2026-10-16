# tests: pytest (each owner tests what they build)

Read PRD 13.4-13.6. Unit, contract and Compose integration tests run in CI with recorded AI responses (`AI_MODE=fixtures`); pull requests must cost nothing.

- **W1:** web components, account/payments (forged and duplicate webhooks), Firestore rules, preview no-network test, Compose smoke test.
- **W2:** session state machine at 100% line coverage, gate and spaCy boundary rule, clip-store key tests.
- **W3:** `aloai_scoring`, `aloai_authz`, `aloai_guardrails` at 100%; miscue labels, golden recordings (WCPM +/-5, accuracy +/-3), grader reconciliation, contract tests.
- Coverage: 100% for scoring, authz, guardrails, state machine; at least 80% elsewhere. Never delete or loosen a test to get green; fix the code or raise it with the owner.
- Tests use fictional fixtures only; no real child audio. Use the `testing-strategy` skill when planning new test suites.
