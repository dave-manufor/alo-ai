---
name: alo-prompt-eval
description: Rerun the right evaluation set after changing a prompt, model, rubric or agent tool, and format the result for the PR. Use whenever a Gemini prompt, model version, rubric, Critic check or Coach instruction changes.
---

# Alo.ai prompt / model change and evaluation

A changed prompt or model must be re-evaluated and the result pasted in the PR (CONTRIBUTING; PRD 13.4).

## Pick the set (PRD 13.4)
| Changed | Evaluation set | Tooling | Threshold |
|---|---|---|---|
| Story Writer / Critic / gate | 10 generation requests (ARL 2-9, several tags) + 10 seeded flawed stories | Vertex AI Gen AI evaluation + rubric | gate pass >= 8/10; Critic catch >= 9/10 |
| Grading prompts / model | Mini-study answers and retells, hand-scored | pytest | weighted kappa target >= 0.60 (report as early trial readings) |
| Reading Coach | 10 reports incl. provisional, LC_MISSED, missing fields | ADK evaluation | tool sequence >= 9/10; activities only from library 10/10; summary passes validator first try >= 9/10 |
| Session conductor | 6-scenario manual checklist | manual at rehearsal | all 6 |
| Any agent | Red-team set, 20 cases | ADK evaluation + pytest | 20/20 |

## Steps
1. Make the change; keep model versions pinned.
2. Refresh `fixtures/ai/` recorded responses if the output shape changed so CI stays deterministic and free.
3. Run the set. Use `AI_MODE=live` only for this; it spends the shared $400 budget, so run each set once, not in a loop.
4. Always run the red-team set if any agent prompt or tool changed.
5. Paste in the PR: set name, commit, model/version, metric values vs thresholds, failures. Do not claim a pass you did not see; if below threshold, say so.
6. Numbers in agent output must still come only from tools (the guardrail check).
