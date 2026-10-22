# apps/web: Web app / PWA (W1, reviewed by W2 or W3)

A Parent/School first screen, sign-in (an emailed code, through Entra External ID), consent, child profiles, the session screen (mic, clip cache, reconnect), report screen, Paystack checkout and the teacher view **preview**. Read PRD 4.1, 4.4, 4.7, 14.1 and the root `AGENTS.md` first.

## Design system (mandatory)

Follow the project design system **as closely as possible** in every UI change:

- The system is in `docs/Alo.ai_Design_System/`: read its `README.md` first, then use `tokens.json`, the `components/` (each has a README, `preview.html` and types in `index.d.ts`) and `assets/`. See the root `AGENTS.md` for the full directive.
- Use its tokens and components. No hard-coded colour/spacing/font values; no one-off component when a system component exists. Use logos, Jàpá and icons from `assets/` as supplied.
- Kid mode and grown-up mode are never mixed on one screen. Kid mode never shows red, a score, a timer or a percentage. Story text is always Andika. `moon` is for rewards only.
- Deviate **only when following it is impossible**. Then keep the deviation minimal, explain it in the PR under "Design system deviations", and propose the missing piece as an addition to the system.
- W1 decides how the app consumes the bundle, tokens and assets (import or copy into `apps/web/`), and does it once in one place. Don't edit the files in `docs/Alo.ai_Design_System/` to suit one screen; changes to the system are their own PR.
- Run `alo-ui-change` before building UI; review with `design-critique` and `accessibility-review`.

## Other rules

- Children never see a score, timer, leaderboard, ad or red mark. Screening language only.
- Built for ordinary Android phones on mobile data: small payloads, touch targets, contrast, screen-reader support.
- The browser never chooses `VOICE_MODE` or `SESSION_PROFILE`. The session screen follows W2's session protocol (`play`, `show_passage`, `hide_passage`, `reconnecting`); all clips download before reading starts.
- **Teacher view is a preview**: fictional sample data only, a banner on every screen, no data client imports and no network calls (unit test enforces it). Never presented as live.
- Screenshots and fixtures use sample data only. Local mode (`VITE_ALO_ENV=local`) talks to the emulators.
- **Consumes:** `ReadingReport` (W3), session protocol (W2). **Produces:** nothing others depend on except via the Account service. Contract changes: `alo-contract-change`.
