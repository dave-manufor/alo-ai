---
name: alo-ui-change
description: Build or change any user interface in the Alo.ai web app (screens, components, styles, report, session screen, teacher preview) while following the design system as closely as possible. Use before writing UI code.
---

# Alo.ai UI change

**Directive:** follow the project design system as closely as possible. Deviate only when following it is impossible.

## Steps
1. **Find the system.** Look in `web/src/design-system/` and `docs/DESIGN_SYSTEM.md` (tokens: colour, type, spacing, radius, motion; components; patterns). If neither exists yet, stop and ask the user before inventing visual patterns - W1 (Anthony) establishes the system. If you must proceed, put every value in one tokens file so it can be swapped and flag it in the PR.
2. **Reuse first.** For each element you need, use an existing token/component/pattern. No hard-coded colours, spacing or font values. No one-off components when a system one exists. Extend a system component rather than forking it.
3. **If something is missing or doesn't fit:** make the smallest possible deviation, and record it. "Impossible" means the system lacks the piece or conflicts with an accessibility/technical requirement - not that another look is preferred.
4. **Record deviations** in the PR under "Design system deviations": what, why following the system was impossible, and the proposed addition to the system. Tick the UI checkbox in the PR template.
5. **Check the product rules:** children never see a score, timer, leaderboard, ad or red mark; screening language only; teacher view is a labelled preview using sample data with no data-client imports or network calls.
6. **Accessibility and device:** ordinary Android phones on mobile data. Verify touch target size, contrast, keyboard/screen-reader behaviour, small payloads. Use the `accessibility-review` skill.
7. **Review:** `design-critique` for feedback, `design-handoff` for specs, `design-system` to document or extend the system, `ux-copy` for wording (parents and children).
8. Screenshots in PRs use sample data only.
