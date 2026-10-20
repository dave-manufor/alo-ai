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

## Routes (scaffold)

| Route | Mode | Status |
|---|---|---|
| `/` | Grown-up | Landing placeholder |
| `/session` | Kid | Session-screen scaffold with sample story; LiveKit + W2's session protocol arrive in `feat/web-session-screen` |
| `/schools/preview` | Grown-up | Teacher view preview shell with the mandatory sample-data banner (PRD 4.7); full preview in its own branch |

Sign-in, consent, child profiles, the real report screen and Paystack
checkout are follow-up branches (`feat/web-auth-consent`,
`feat/web-report-screen`, `feat/payments-paystack-checkout`, …).
