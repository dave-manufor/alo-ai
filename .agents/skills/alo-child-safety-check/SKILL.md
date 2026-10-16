---
name: alo-child-safety-check
description: Pre-commit scan for secrets, real child data, large/audio files and banned (diagnostic) wording in Alo.ai changes. Use before every commit or PR, and whenever adding fixtures, seeds, copy or prompts.
---

# Alo.ai child-safety and secrets check

Run on the staged/changed files before committing (PRD 12, 3.1, CONTRIBUTING).

## 1. Files that must never be committed
- `git status --short` and `git diff --cached --name-only`: look for `.env*` (except `.env.example`), `*.pem`, `*.key`, `adc.json`, `application_default_credentials.json`, audio (`wav mp3 webm opus m4a ogg flac`), model weights (`pt pth onnx safetensors ckpt`), tfstate.
- Anything over ~1 MB. Mini-study recordings never go in Git.

## 2. Secrets
- Grep the diff for: `sk_live`, `sk_test_` with real values, `PAYSTACK_SECRET`, `-----BEGIN`, `AIza`, `api_key=`, `secret=`, bearer tokens. `.env.example` placeholders are fine.
- If a secret was committed: tell the team and rotate it immediately; deleting the commit is not enough.

## 3. Child data
- Fixtures, seeds, tests and docs must be fictional. Look for real-looking child names, school names, phone numbers, emails, transcripts or audio of real children.
- Chidi and other seeded names are fictional sample data only.

## 4. Banned wording in parent-, child- or teacher-facing text and agent prompts' outputs
- Search changed copy, templates and prompts for: `diagnos`, `dyslex`, `disorder`, `behind`, `failing`, `slow learner`, `hyperlexic`, `word caller` (the PRD list plus the design system README's list). Reports say "screening", never "diagnosis".
- In child-facing copy also search for `wrong`, `incorrect`, `fail` and a bare "no"; children are never told these, and never see scores, timers, percentages or red marks (design system README, "Voice and tone").
- Banned words may appear inside the guardrail's own blocklist and its tests; that is fine.

## 5. Report
List what you checked, what you found and what you could not check. Fix or flag findings before committing.
