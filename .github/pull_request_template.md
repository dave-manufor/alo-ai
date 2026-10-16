## What changed

## Why

## How I tested it
<!-- Commands run, tests added. Screenshots for UI use sample data only. -->

## Checklist
- [ ] One branch, one purpose; branch and commit names follow `type/scope-description` / `type(scope): what`
- [ ] No secrets, `.env`, real child audio, names or transcripts, or large files
- [ ] **Contract change?** Schema in `schemas/` and fixture in `fixtures/contracts/` updated, `schema_version` bumped, consumer tagged: @
- [ ] **Scoring / [CAL] change?** W3 approved, `scoring_module` version bumped, validation rerun, PRD changelog line added
- [ ] **Prompt or model change?** Evaluation rerun, result pasted below
- [ ] **Infra / server setting change?** Done through Terraform only
- [ ] **UI change?** Follows the design system, or the deviation and why following it was impossible are explained below
- [ ] Parent- and child-facing text uses screening language (no "diagnosis", "dyslexia", "behind", "failing", "hyperlexic", "word caller")
- [ ] Tests added or updated; coverage rules met (100% for scoring, authz, guardrails, state machine; 80% elsewhere)

## Evaluation results (if prompt or model changed)

## Design system deviations (if any)
