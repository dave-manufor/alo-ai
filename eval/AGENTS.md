# eval: agent evaluation sets (shared; split by set)

Evaluation sets, the red-team set and the golden-recordings index. Read PRD 13.4 and 13.5, and use `alo-prompt-eval`. A set passes only if every metric meets its threshold. Sets run before the demo and whenever a prompt or model changes.

| Set | Owner | Reviewer | Threshold (PRD 13.4) |
|---|---|---|---|
| Story Writer + Critic: 10 generation requests plus 10 seeded flawed stories | W2 | W3 | gate pass at least 8 of 10; Critic catch at least 9 of 10 |
| Grading: mini-study answers and retells, hand-scored | W3 | W2 | weighted kappa target at least 0.60, reported as early trial readings |
| Reading Coach: 10 reports incl. provisional, LC_MISSED, missing fields | W3 | W2 | tool sequence at least 9 of 10; library-only activities 10 of 10; validator first try at least 9 of 10 |
| Red-team: 20 cases | W3 | W2 | 20 of 20 |
| Session conductor: 6-scenario checklist | W2 | W3 | all 6, run by hand at rehearsals |

- Live-model runs spend from the shared $400 budget; run each set once per change, not in a loop. CI uses recorded responses (`AI_MODE=fixtures`).
- No real child's audio, name or transcript in any set. The golden-recordings index lists files and hand counts only; the audio itself stays out of Git.
- Report real results with the numbers; never claim a threshold was met without the run.
