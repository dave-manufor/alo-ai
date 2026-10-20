# Alo.ai web app (W1)

The installable PWA: landing, sign-in, consent, child profiles, the kid
session screen, the grown-up report screen, Paystack checkout, and the
teacher view preview. Read `AGENTS.md` in this folder, PRD 4.1/4.4/4.7/14.1
and the design system (`docs/Alo.ai_Design_System/README.md`) before
changing UI.

## Run it

```sh
npm ci
npm run dev        # http://localhost:5173, syncs the design system first
npm test           # Vitest + Testing Library
npm run lint
npm run build      # type-check + production build (PWA) into dist/
```

`VITE_ALO_ENV=local` (the default) talks to the local emulators once the
Compose stack (`make up-web`, in `docs/LOCAL_DEV.md`) exists. The browser
never chooses `VOICE_MODE` or `SESSION_PROFILE`; those are server settings.

## Design system

Followed as closely as possible, through exactly one consumption layer —
see `src/design-system/README.md` for W1's decision (verbatim bundle +
generated `tokens.css` + synced assets; no hard-coded token values).

## Routes (fixture-backed MVP)

The MVP UI is complete against fixtures, ready to swap each fixture for
its live service without changing the screens:

| Route | Mode | What it does | Live replacement |
|---|---|---|---|
| `/` | Grown-up | Landing | — |
| `/signin` | Grown-up | Sample Google / email-link sign-in | Firebase Authentication |
| `/consent` | Grown-up | Consent record (text, version, time, sign-in method, email); gates everything after it | Account service consent records (PRD 12) |
| `/children` | Grown-up | Child profiles (first name, Primary 1–6, birth year) | Account service `children/` |
| `/session` | Kid | Full session flow on W2's protocol: `clip_list` downloads, `show/hide_passage`, told-word `play` with `played`/`missing` acks, retell, questions, reward close | LiveKit room + `POST /v1/sessions` driver |
| `/reports`, `/reports/:sessionId` | Grown-up | Report list and detail from the `ReadingReport` shape (PRD 10.4): strength first, profile, level guide, books, weekly plan | `reports/{session_id}` written by W3's Grader |
| `/plan/checkout` | Grown-up | Weekly-plan checkout placeholder | Paystack inline checkout, initialized by the Account service (PRD 11.1) |
| `/schools/preview`, `/schools/preview/children/:childId` | Grown-up | Full teacher view preview: sample P3B class of 23, sortable table, groups, child pages, scripted assistant. No network calls (tested) | Real teacher view comes after the hackathon (PRD 4.7) |

Fixture stores live beside their screens (`src/account/store.ts`,
`src/report/reportFixture.ts`, `src/preview/teacherFixture.ts`,
`src/session/`) and are the only places sample data enters the app.
