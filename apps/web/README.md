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

Only an explicit `VITE_ALO_ENV=local` talks to the local emulators once
the Compose stack (`make up-web`, in `docs/LOCAL_DEV.md`) exists; the
default is non-local, so a production build can never mistake itself for
a local one (AGENTS rule 8). The browser never chooses `VOICE_MODE` or
`SESSION_PROFILE`; those are server settings.

## Design system

Followed as closely as possible, through exactly one consumption layer —
see `src/design-system/README.md` for W1's decision (verbatim bundle +
generated `tokens.css` + synced assets; no hard-coded token values).
Navigation uses `src/design-system/NavButton.tsx` (the system `Button`
with `navigate()`), never a `<button>` inside an `<a>`.

## Routes (fixture-backed MVP)

| Route | Mode | What it does | Live replacement |
|---|---|---|---|
| `/` | Grown-up | Landing. No report links: grown-up data sits behind sign-in (PRD 12) | — |
| `/signin` | Grown-up | Google sign-in, or an email link that only signs in when clicked | Firebase Authentication |
| `/consent` | Grown-up | What consent means + the per-child records on file | Account service `consents/` |
| `/children` | Grown-up | Child profiles. Adding a child records **that child's** consent (attestation names the child and age; `consents/{consent_id}` shape with `guardian_id` + `child_id`) | Account service `children/` + `consents/` |
| `/session/:childId` | Kid | Gated on that child's consent record. Follows **session protocol v2** (PR #24): the agent's `step` drives the screen, clip `text` fills the bubble, `show_passage` carries the story and ARL, clips fully download before play and `played` means playback finished | LiveKit room + `POST /v1/sessions` driver emitting v2 |
| `/reports`, `/reports/:sessionId` | Grown-up | Signed-in only. Report joined with its child: Coach summary + home practice free, weekly-plan activities only with an active subscription, null-safe for checks with no evidence | `reports/{session_id}` + `children/{child_id}` |
| `/plan/checkout` | Grown-up | Signed-in only. Weekly-plan checkout placeholder | Paystack inline checkout, initialized by the Account service (PRD 11.1) |
| `/schools/preview`, `/schools/preview/children/:childId` | Grown-up | Teacher view preview: sample P3B class of 23, sortable table, groups, child pages, scripted assistant. No network calls (tested) | Real teacher view comes after the hackathon (PRD 4.7) |

Fixture stores live beside their screens (`src/account/store.ts`,
`src/report/reportFixture.ts`, `src/preview/teacherFixture.ts`,
`src/session/`) and are the only places sample data enters the app.
