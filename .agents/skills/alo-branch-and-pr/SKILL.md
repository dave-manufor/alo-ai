---
name: alo-branch-and-pr
description: Create a correctly named Alo.ai branch, make scoped commits, and open a pull request with the right reviewer. Use whenever starting work, committing, pushing or opening/updating a PR in this repo.
---

# Alo.ai branch, commit and PR

Rules come from `docs/CONTRIBUTING.md` and PRD 14.2. Never commit to `main`.

## 1. Branch
1. `git status` and `git branch --show-current`. If on `main`: `git fetch && git switch -c <branch> origin/main`.
2. Name: `type/scope-short-description`, lowercase, hyphens. Types: `feat fix docs refactor test chore`. Scopes: W1 `web account payments infra ci dev`; W2 `session generator voice clips books`; W3 `scorer grader scoring coach eval`; shared `schemas docs repo`. One branch per feature, fix or doc update. No `test2`, `final`, `<name>-branch`.
3. Check which area you are touching vs the person's workstream (`git config user.name`). If it is someone else's area, tell the user to tag that owner.

## 2. Commit
- Small, one purpose each: `type(scope): what it does`.
- Before committing run the `alo-child-safety-check` skill. Run the area's tests and linters first and report real results.
- Stage files by name; never `git add -A` blindly (risk of `.env`, audio, weights).

## 3. PR
1. `git fetch && git rebase origin/main`, then push with `-u`.
2. Write the body to a temporary file from `.github/pull_request_template.md` (what / why / how tested / checklist). Do not use heredocs inside command flags.
3. `gh pr create --base main --title "type(scope): what" --body-file <file> --reviewer <reviewer>`.
4. **Reviewer ring:** W1 (Anthony) PRs -> W2 (`dave-manufor`) or W3 (`SmartWebCodder`); W2 (David) PRs -> W3 (`SmartWebCodder`); W3 (Nelson) PRs -> W2 (`dave-manufor`). If the reviewer is busy for more than a couple of hours, the remaining person reviews.
5. Contract, scoring, prompt/model and UI-deviation items in the template must be filled in or ticked honestly. Tag consumers by name.
6. Nobody merges their own PR. The reviewer squash-merges after CI is green; delete the branch.

## Freeze
After end of day 5 only `fix/` branches merge, approved by both other people.
