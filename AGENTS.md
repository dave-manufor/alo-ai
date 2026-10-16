# Alo.ai: instructions for AI coding agents

This file is the single source of truth for every AI tool used on this repo (Claude Code, Codex, Cursor, Antigravity). `CLAUDE.md` and `GEMINI.md` import it. Area folders have their own `AGENTS.md` with local rules. Read this file fully before changing anything.

## What this is

Alo.ai is a voice-first reading and comprehension screener for Nigerian primary school children (P1-P6), built in a 6-day hackathon for the Paystack AI Builder Challenge. A child chats about their interests, reads a generated story aloud, retells it and answers questions. The system produces a screening report, a parent plan and book recommendations. **It screens; it never diagnoses.**

Docs (read the section for your area, not the whole PRD):

| Doc | Use it for |
|---|---|
| `docs/Alo.ai_PRD_v1.8.0.md` | The spec. 3 architecture and agents, 4 session protocol, 5 speech, 6 scoring, 7 grader, 9 books, 10 data contracts, 12 privacy and authz, 13 testing and evals, 14 team and plan, 15 Terraform |
| `docs/CONTRIBUTING.md` | Git rules, ownership, review ring |
| `docs/LOCAL_DEV.md` | Docker Compose stack, toggles, make targets |
| `docs/Software_Design_Document.md` | How each part is built (markdown copy of `docs/Software Design Document.pdf`; diagrams in `docs/sdd-images/`) |
| `docs/Alo.ai_Design_System/` | The UI design system: `README.md` (brand, voice, rules), `tokens.json`, `components/`, `assets/` (see "Design system") |

## Team and ownership

| | Person | GitHub | Owns | Reviewed by |
|---|---|---|---|---|
| W1 | Anthony | TODO | Web app/PWA, Account and Payments service, Terraform, CI, Docker Compose, Firestore rules | W2 or W3 |
| W2 | David | @dave-manufor | Session Agent, voice and clip store, Passage Generator, book catalogue | W3 |
| W3 | Nelson | @SmartWebCodder | Reading Scorer, Grader, `aloai_scoring.py`, Reading Coach, authz, guardrails, evals | W2 |

Review ring: **W1's PRs are reviewed by W2 or W3; W2 reviews W3; W3 reviews W2.** If a reviewer is busy for more than a couple of hours, the remaining person reviews. Each owner's reviewer is also their backup. Nobody merges their own PR.

**Identify the human first.** Work out who you are working with from `git config user.name` / `user.email`, or ask. If a task touches another person's area, say so before editing and tell the user to tag that owner on the PR. Shared areas (`schemas/`, `fixtures/contracts/`, `docs/`, agent files) need all three people informed.

## Repo layout

```
services/
  session_agent/  W2        account/  W1 (accounts and payments)
  scorer/         W3        core/     generator/ books/ (W2), grader/ coach/ (W3)
web/              W1        libs/     aloai_scoring, aloai_authz, aloai_guardrails (W3)
schemas/          one JSON Schema per contract (PRD 14.2)
fixtures/         seed/, contracts/, ai/, recordings/
dev/              emulators/, init.py, replay.py, webhook.py, smoke.py (W1)
infra/            Terraform + pubsub.json (W1)     ops/  things configured outside Terraform
tests/            pytest
```

Some of these folders are empty skeletons. Check what exists before assuming code is there. `aloai_scoring.py`, `aloai_authz.py`, `aloai_guardrails.py` and their 130 tests are described in the PRD and are to be added by W3.

## Running things

See `docs/LOCAL_DEV.md`. `make up-web` (W1), `make up-session` (W2), `make up-after` (W3), `make up-all`, `make smoke`, `make replay SESSION=chidi`, `make reset`. Default to `AI_MODE=fixtures` (free, deterministic). Use `AI_MODE=live` only when the task needs real Vertex AI, because it spends from the shared $400 budget. Never put real keys in files; use `.env` (git-ignored) copied from `.env.example`.

## Hard rules

Breaking one of these is a bug, even if the code works. Section numbers refer to the PRD.

1. **Agents plan, code scores (3.1).** No LLM output may create, change or estimate a score, level or profile. Only `aloai_scoring.py` produces numbers. Every number in agent text must match a tool result.
2. **No child data or secrets in Git (12).** Never commit `.env`, keys, real children's audio, names, transcripts or large files (audio, weights). Fixtures and seeds use fictional data only. Secrets live in Secret Manager; if one is committed, tell the team and rotate it immediately.
3. **Screening language only (3.1, 12).** Never write "diagnosis", "dyslexia", "disorder", "behind", "failing", "slow learner", "hyperlexic" or "word caller" in parent- or child-facing text. Children never see a score, timer, percentage or red mark, and are never told "wrong", "no", "incorrect" or "fail" (the design system README has the full voice rules).
4. **Contracts (14.2).** A schema, endpoint or event used by another person changes only with: the schema in `schemas/` updated, its fixture in `fixtures/contracts/` updated, `schema_version` bumped, and the consumer tagged on the PR. Use the `alo-contract-change` skill.
5. **Scoring (13.3).** Any change to `aloai_scoring.py`, a [CAL] constant, allowlist or profile rule needs W3's approval, a new `scoring_module` version, a validation rerun and a line in the PRD changelog.
6. **Prompts and models (13.4).** Changing a prompt or model means rerunning its evaluation set and pasting the result in the PR. Use `alo-prompt-eval`.
7. **Infrastructure (15.1).** Nothing in Google Cloud is created or changed by hand. Terraform only, in `infra/`. Server settings (`voice_mode`, `session_profile`, `demo_warm`) change only via a `chore/infra-...` PR to `terraform.tfvars`. Secret values stay out of Terraform state.
8. **Local shortcuts stay local.** Keep the guard that refuses `ALO_ENV=local` when `K_SERVICE` is set. "That word is X." is always a pre-made clip, never Gemini Live (4.2). The browser never chooses `VOICE_MODE` or `SESSION_PROFILE`.
9. **Least privilege (12, 12.1).** EU region for everything. One service account per service. Only the Account and Payments service holds the Paystack secret and email key. Agents never hold secrets and have no tool that writes scores, consent or payments. Every agent tool call goes through `authorize()`.
10. **Tests (13.5).** 100% line coverage for `aloai_scoring.py`, `aloai_authz.py`, `aloai_guardrails.py` and the session state machine; at least 80% elsewhere. Each owner writes tests for what they build. Never weaken or delete a test to make CI pass.
11. **Design system.** See the next section.
12. **Scope.** Do what was asked, in the owner's area. Respect the cut list and the "never cut" list in 14.2. After feature freeze (end of day 5) only `fix/` branches merge, approved by both other people.

## Design system

All UI work (the web app, PWA, report screens, and the teacher view preview) must **follow the project design system as closely as possible**. It lives in `docs/Alo.ai_Design_System/`:

| Path | What it is |
|---|---|
| `README.md` | Brand, the two modes (kid and grown-up), voice and tone, colour, type, shape, motion, the game layer, accessibility. **Read it before any UI or copy work.** |
| `tokens.json` | Colour (Day/Night themes), type, spacing, radius, tap sizes, motion |
| `components/` | React components (`Button`, `MicButton`, `SpeechBubble`, `ReadingPanel`, `Japa`, `MoonProgress`, `ParentReportCard`, `ProfilePill`, `RewardBadge`, `LanternStreak`, ...). Each has a `README.md` and `preview.html`; `index.d.ts` has the prop types; `bundle.js` and `bundle.css` are the built output |
| `assets/` | Logos, the Jàpá mascot poses, icons, the adire pattern |

- Use its tokens and components. Do not hard-code colour, spacing, radius or font values, and do not write a one-off component when a system component exists. Use the assets as supplied (never recolour or restyle the logo or Jàpá, and no emoji).
- Respect the rules in its README, for example: never mix kid and grown-up mode on one screen; kid mode never shows red or a score; `moon` means reward only; story text is always Andika; text on `moon`, `coral`, `leaf` and `sky` is `on-bright`; respect `prefers-reduced-motion`.
- Deviate **only when following the system is impossible** (it lacks the piece, or it conflicts with an accessibility or technical requirement). When you deviate, say why in the PR under "Design system deviations", keep the deviation as small as possible, and propose the missing piece as an addition to the system.
- Treat `docs/Alo.ai_Design_System/` as the source of truth: don't fork or edit its files to suit one screen. A change to the system itself is its own PR with a reason, and W1 (who builds the web app) decides how the app imports the bundle, tokens and assets.
- Before building UI, use the `alo-ui-change` skill. For review use `design-critique`, `accessibility-review` and `design-handoff`; to extend the system use `design-system`.
- Accessibility is part of this: the app is used by children on ordinary Android phones. Check touch targets, contrast and screen-reader behaviour.

## Git workflow

- **Never commit to `main`.** Every change is a PR. A Claude Code hook blocks commits on `main`; other tools must follow the rule too.
- One branch per feature, fix or doc update, named `type/scope-short-description`, lowercase and hyphenated, e.g. `feat/session-told-word-prompt`. Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`. Scopes: W1 `web account payments infra ci dev`; W2 `session generator voice clips books`; W3 `scorer grader scoring coach eval`; shared `schemas docs repo`.
- Commits are small and do one thing: `type(scope): what it does`, e.g. `fix(grader): use the mean when retell passes agree`.
- Rebase on `main` each morning: `git fetch && git rebase origin/main`. Merge within a day where you can.
- PR description: what changed, why, how tested. Use `.github/pull_request_template.md`. Pass bodies to `gh` with `--body-file`, not heredocs inside flags.
- Squash and merge once CI is green and the reviewer in the ring approves; then delete the branch. Use the `alo-branch-and-pr` skill.
- Never force-push to a shared branch, skip hooks, or bypass checks.

## Skills

Skills live once in `.agents/skills/` and are exposed to each tool through `.claude/skills`, `.agent/skills` and `.cursor/skills` (symlinks). Codex reads `.agents/skills` directly. Use a skill when its description matches the task.

**Alo.ai workflow skills** (these encode the rules above): `alo-branch-and-pr`, `alo-contract-change`, `alo-scoring-change`, `alo-prompt-eval`, `alo-infra-change`, `alo-ui-change`, `alo-child-safety-check`.

**Engineering:** `review-checklist` (structured code review), `debug`, `testing-strategy`, `architecture` (ADRs), `system-design`, `documentation`, `deploy-checklist`, `incident-response`, `tech-debt`, `standup`.

**Design and UX (mainly W1):** `design-system`, `design-critique`, `design-handoff`, `accessibility-review`, `ux-copy`.

**Product, compliance, evidence:** `write-spec`, `sprint-planning`, `stakeholder-update`, `compliance-check` (NDPA 2023 and children's voice data), `statistical-analysis` and `validate-data` (W3: mini-study readings).

**Docs and demo:** `doc-coauthoring` (PRD/SDD revisions), `pptx` (demo slides), `skill-creator` (add team skills here).

Claude Code also has built-in `/code-review`, `/security-review` and `/simplify`. Other tools: run the same checks by hand or via `review-checklist`.

## How to work

- Read the relevant PRD section and the area's `AGENTS.md` before editing. Search for existing code before writing new code.
- Prefer small, reviewable diffs. Say what you verified and what you could not (tests not run, cloud not reachable).
- Report test failures honestly with the output; do not claim a green result you did not see.
- When the PRD and the code disagree, stop and ask which is right; do not silently pick one. Changes to the spec go in the PRD changelog.
- Do not edit files under `.agents/skills/` vendored from Anthropic (anything not prefixed `alo-`) except to fix broken links; add team behaviour as a new `alo-*` skill instead.
