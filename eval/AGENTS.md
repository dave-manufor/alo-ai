# eval: agent evaluation sets (shared; split by set)

Evaluation sets, the red-team set and the golden-recordings index. Read PRD 13.4 and 13.5, and use `alo-prompt-eval`. A set passes only if every metric meets its threshold. Sets run before the demo and whenever a prompt or model changes.

| Set | Owner | Reviewer | Threshold (PRD 13.4) |
|---|---|---|---|
| Story Writer + Critic: 10 generation requests plus 10 seeded flawed stories | W2 | W3 | gate pass at least 8 of 10; Critic catch at least 9 of 10 |
| Grading: mini-study answers and retells, hand-scored | W3 | W2 | weighted kappa target at least 0.60, reported as early trial readings |
| Reading Coach: 10 reports incl. provisional, LC_MISSED, missing fields | W3 | W2 | tool sequence at least 9 of 10; library-only activities 10 of 10; validator first try at least 9 of 10 |
| Red-team: 20 cases | W3 | W2 | 20 of 20 |
| Session conductor: 6-scenario checklist | W2 | W3 | all 6, run by hand at rehearsals |

- Live-model runs use the models Core runs on `CLOUD` (`eval/models.py`) and spend from that cloud's budget ($400 on GCP, the $150 Azure credit, or the outside provider's key on Azure with `LLM_BASE_URL`); run each set once per change, not in a loop. Recordings are kept per cloud in `eval/recorded/{cloud}/`. CI uses recorded responses (`AI_MODE=fixtures`).
- The sets are fictional, so they may run on a route that real children's data may not use yet (the Gemini key, #150): a set's result is still required before that route sees a real child (hard rule 6).
- No real child's audio, name or transcript in any set. The golden-recordings index lists files and hand counts only; the audio itself stays out of Git.
- Report real results with the numbers; never claim a threshold was met without the run.
