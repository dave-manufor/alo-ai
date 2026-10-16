# schemas: JSON Schemas for every contract (shared)

One JSON Schema per hand-off in the PRD 14.2 contracts table (and the section 10 artifacts). Producer owns each contract.

- A change needs: schema updated, `schema_version` bumped, matching fixture in `fixtures/contracts/` updated in the **same PR**, consumer tagged on the PR. Use `alo-contract-change`.
- CI validates every fixture against its schema and each producer's real output against the same schema. Do not edit a fixture to hide a producer bug.
- Keep schemas strict (`additionalProperties: false` unless the PRD says otherwise). No real child data in examples.
