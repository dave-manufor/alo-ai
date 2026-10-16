---
name: alo-scoring-change
description: Change scoring formulas, a [CAL] constant, an allowlist or a profile rule in aloai_scoring.py (or anything that decides a score, level or profile). Use before editing libs/aloai/aloai_scoring.py or scoring logic anywhere.
---

# Alo.ai scoring change

Code scores; LLMs and agents never do (PRD 3.1, 13.3). Only `aloai_scoring.py` produces numbers. W3 (Nelson) owns it.

## Gate (all required)
1. **W3 approval** - if you are not W3, stop and tell the user to get Nelson's explicit approval on the PR before merging.
2. **New `scoring_module` version** - bump it; every report stores the version that produced it.
3. **Validation rerun** - rerun the validation set / golden recordings (WCPM within +/-5 words, accuracy within +/-3 points) and paste results in the PR. Report failures as they are.
4. **PRD changelog line** - add it to `docs/Alo.ai_PRD_v1.8.0.md` section 0.
5. **Tests** - 100% line coverage for `aloai_scoring.py`. Add tests for each changed branch; exhaustive tests for the diagnosis decision tree (every input maps to exactly one outcome).

## Rules while editing
- Pure functions; no network, no LLM calls, no randomness.
- [CAL] constants are provisional; mark them and note they are to be recalibrated on pilot data (PRD 13.2).
- Do not feed prosody into comprehension, level or profile (display-only).
- Keep screening language in any generated text. Never produce a diagnosis.
- If the change alters a field in `ReadingReport` or the grader output, also run `alo-contract-change`.
