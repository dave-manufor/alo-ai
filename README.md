# Alo.ai

Voice-first reading and comprehension screener for Nigerian primary school children. A child chats, reads a generated story aloud, retells it and answers questions; the system returns a screening report, a parent plan and book recommendations. Built for the Paystack AI Builder Challenge (with Google for Developers). Named after àlọ́, the Yoruba folktale.

## Team

| | Person | Area |
|---|---|---|
| W1 | Anthony | Web app, accounts and payments, Terraform, CI, Docker Compose |
| W2 | David ([@dave-manufor](https://github.com/dave-manufor)) | Live session, voice and clips, Passage Generator, books |
| W3 | Nelson ([@SmartWebCodder](https://github.com/SmartWebCodder)) | Scorer, Grader, scoring code, Reading Coach, evals |

## Start here

1. Read [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md): branches, commits, PRs, review ring.
2. Read [`docs/LOCAL_DEV.md`](docs/LOCAL_DEV.md) and run your part: `make up-web` (W1), `make up-session` (W2), `make up-after` (W3).
3. Copy `.env.example` to `.env` (never commit it).
4. The spec is [`docs/Alo.ai_PRD_v1.8.0.md`](docs/Alo.ai_PRD_v1.8.0.md).

## Working with AI tools

One rule file, [`AGENTS.md`](AGENTS.md), is read by Claude Code (via `CLAUDE.md`), Codex, Cursor and Antigravity (via `GEMINI.md` and `.agent/`). Team skills live in `.agents/skills/`. Each area folder has its own `AGENTS.md`. To change a team rule, edit `AGENTS.md` in a PR; do not fork rules into tool-specific files.

## Licence

See [`LICENSE`](LICENSE).
