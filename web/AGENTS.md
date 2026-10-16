# web: Web app / PWA (W1, reviewed by W2 or W3)

Landing, Google and email-link sign-in, consent, child profiles, the session screen (mic, clip cache, reconnect), report screen, Paystack checkout and the teacher view **preview**. Read PRD 4.1, 4.4, 4.7, 14.1 and the root `AGENTS.md` first.

## Design system (mandatory)

Follow the project design system **as closely as possible** in every UI change:

- Use its tokens (colour, type, spacing, radius, motion), components and patterns. No hard-coded colour/spacing/font values; no one-off component when a system component exists.
- Deviate **only when following it is impossible**. Then keep the deviation minimal, explain it in the PR under "Design system deviations", and propose the missing piece as an addition to the system.
- The system lives in `web/src/design-system/` and is documented in `docs/DESIGN_SYSTEM.md` (W1 creates it first; until it exists, ask before inventing visual patterns and keep tokens in one swappable place).
- Run `alo-ui-change` before building UI; review with `design-critique` and `accessibility-review`.

## Other rules

- Children never see a score, timer, leaderboard, ad or red mark. Screening language only.
- Built for ordinary Android phones on mobile data: small payloads, touch targets, contrast, screen-reader support.
- The browser never chooses `VOICE_MODE` or `SESSION_PROFILE`. The session screen follows W2's session protocol (`play`, `show_passage`, `hide_passage`, `reconnecting`); all clips download before reading starts.
- **Teacher view is a preview**: fictional sample data only, a banner on every screen, no data client imports and no network calls (unit test enforces it). Never presented as live.
- Screenshots and fixtures use sample data only. Local mode (`VITE_ALO_ENV=local`) talks to the emulators.
- **Consumes:** `ReadingReport` (W3), session protocol (W2). **Produces:** nothing others depend on except via the Account service. Contract changes: `alo-contract-change`.
