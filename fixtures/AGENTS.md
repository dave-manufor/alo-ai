# fixtures: seed data, contract samples, recorded AI responses, recordings (shared)

- `seed/` data loaded by `make seed` (parent, child, consent, subscription, Chidi's finished session). `contracts/` one sample per schema in `schemas/`. `ai/` canned AI responses used by `AI_MODE=fixtures` and CI. `recordings/` audio for `make replay`.
- **Fictional data only.** No real child's name, audio or transcript, ever. Mini-study recordings never go in Git. Audio is git-ignored; see `recordings/README.md`.
- Every `contracts/` sample must validate against its schema (CI checks). Update them in the same PR as the schema.
- `ai/` responses should be refreshed when a prompt or model changes (`alo-prompt-eval`).
