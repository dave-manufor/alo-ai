---
name: alo-ui-change
description: Build or change any user interface in the Alo.ai web app (screens, components, styles, report, session screen, teacher preview) while following the design system as closely as possible. Use before writing UI code.
---

# Alo.ai UI change

**Directive:** follow the project design system as closely as possible. Deviate only when following it is impossible.

## Steps
1. **Read the system.** It is in `docs/Alo.ai_Design_System/`. Read `README.md` (the two modes, voice and tone, colour meaning, type, motion, accessibility), then the pieces you need: `tokens.json`, `components/<Name>/README.md` and `preview.html`, `components/index.d.ts` for props, and `assets/` for logos, Jàpá poses and icons. Decide first whether the screen is **kid mode or grown-up mode**; never mix them.
2. **Reuse first.** For each element you need, use an existing token or component (`Button`, `MicButton`, `SpeechBubble`, `ReadingPanel`, `Japa`, `MoonProgress`, `ParentReportCard`, `ProfilePill`, `RewardBadge`, `LanternStreak`, ...). No hard-coded colours, spacing, radius or font values. No one-off components when a system one exists. Use assets as supplied; no emoji. If the web app doesn't yet have the bundle/tokens wired in, tell the user and ask W1 (Anthony) how it is consumed rather than copying values by hand.
3. **If something is missing or doesn't fit:** make the smallest possible deviation, and record it. "Impossible" means the system lacks the piece or conflicts with an accessibility/technical requirement - not that another look is preferred.
4. **Record deviations** in the PR under "Design system deviations": what, why following the system was impossible, and the proposed addition to the system. Tick the UI checkbox in the PR template.
5. **Check the product rules:** children never see a score, timer, percentage, leaderboard, ad or red mark, and kid copy follows the README (short sentences, praise effort, never "wrong"/"no"/"incorrect"/"fail"); `moon` means reward only; story text is Andika; screening language only; teacher view is a labelled preview using sample data with no data-client imports or network calls.
6. **Accessibility and device:** ordinary Android phones on mobile data. Verify touch target size, contrast, keyboard/screen-reader behaviour, small payloads. Use the `accessibility-review` skill.
7. **Review:** `design-critique` for feedback, `design-handoff` for specs, `design-system` to document or extend the system, `ux-copy` for wording (parents and children).
8. Screenshots in PRs use sample data only.
