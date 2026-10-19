# Contributing to Alo.ai

How the three of us use Git during the hackathon. Keep it simple, keep `main` working.

## Who owns what

| Owner | Area | Branch scopes | Reviewed and merged by |
|---|---|---|---|
| W1: Anthony (@dhtml) | Web app, the Account and Payments service, Terraform, CI, the Docker Compose setup | `web`, `account`, `payments`, `infra`, `ci`, `dev` | W2 or W3 |
| W2: David (@dave-manufor) | Live session: Session Agent, voice and the clip store, Passage Generator, book catalogue | `session`, `generator`, `voice`, `clips`, `books` | W3 |
| W3: Nelson (@SmartWebCodder) | After the session: Reading Scorer, Grader, `aloai_scoring.py`, Reading Coach, evals | `scorer`, `grader`, `scoring`, `coach`, `eval` | W2 |

Shared scopes: `schemas`, `docs`, `repo`. If your reviewer is busy for more than a couple of hours, ask the third person.

AI tools: every agent reads `AGENTS.md` at the repo root (Claude Code through `CLAUDE.md`, Antigravity through `GEMINI.md`). Team skills are in `.agents/skills/`. Change a team rule there, in a pull request.

## Branches

- Never commit to `main`. Every change goes through a pull request.
- **One branch per feature, fix or doc update.** Don't bundle them.
- Name it `type/scope-short-description`, all lowercase, words joined by hyphens:

  ```
  feat/session-told-word-prompt
  fix/payments-webhook-signature
  docs/prd-team-split
  ```

  Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`. No `dave-branch`, `test2` or `final`.
- Keep branches short: merge within a day if you can. Rebase on `main` every morning (`git fetch && git rebase origin/main`).

## Commits

- Small commits that each do one thing.
- Message format: `type(scope): what it does`, for example `fix(grader): use the mean when retell passes agree`.
- Never commit secrets, `.env` files, real children's audio, transcripts or names, or large files (audio, model weights).

## Pull requests

- Open one as soon as there's something to show, and keep it small.
- Description: what changed, why, and how you tested it. Add a screenshot for UI changes, using sample data only.
- **Nobody merges their own pull request.** The reviewer in the table approves and merges, once CI is green.
- Use **squash and merge**, then delete the branch.

## A few project rules

- **Contracts:** if you change a schema, an endpoint or an event another person uses, tag them on the pull request before it merges, and update its schema in `schemas/` and its fixture in `fixtures/contracts/` in the same pull request (PRD 14.2 lists the contracts).
- **Scoring:** changes to `aloai_scoring.py` or a [CAL] constant need W3's approval and a line in the PRD changelog.
- **Prompts:** if you change a prompt or a model, rerun its evaluation and paste the result in the pull request.
- **Design system:** UI follows the design system as closely as possible. Deviate only when following it is impossible, and explain the deviation in the pull request.
- **Secrets:** they live in Secret Manager only. If one gets committed, tell the team and rotate it straight away.
- **Feature freeze (end of day 5):** only `fix/` branches merge after this, approved by both other people.
- **Server settings** (`voice_mode`, `session_profile`, `demo_warm` in `infra/terraform.tfvars`) change only through a `chore/infra-…` pull request like any other change.

## Setup on `main`

Turn these on in the repository settings on day 1:

- A pull request and 1 approval are required to merge.
- CI must pass.
- Force pushes are blocked.
- Nobody can bypass these rules, including admins.
