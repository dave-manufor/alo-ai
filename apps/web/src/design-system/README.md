# How the web app consumes the design system (W1 decision)

`docs/Alo.ai_Design_System/` is the source of truth. It is never edited,
copied by hand, or forked to suit one screen. This folder is the **one place**
the app consumes it, in three steps:

1. **Sync (build time).** `scripts/sync-design-system.mjs` (run automatically
   by `npm run dev`, `build` and `test`) copies, verbatim:
   - `components/bundle.js`, `bundle.css`, `index.d.ts` → `vendor/`
   - `assets/` (logos, Jàpá poses, icons, adire pattern) → `public/design-system/assets/`
   - and generates `vendor/tokens.css` from `tokens.json`: every colour
     (Day on `:root`, Night on `[data-theme="dark"]`), spacing, radius,
     press-edge, size and font token becomes the CSS variable of the same
     name (`--surface`, `--space-5`, `--font-reading`, …), plus one utility
     class per type style (`.display-l`, `.kid-body`, `.reading-p3`,
     `.title`, `.body`, `.label`, `.caption`, …).

   Everything under `vendor/` and `public/design-system/` is generated and
   git-ignored, so the app can never drift from the shipped system.

2. **Components.** The bundle is a classic script: it reads the app's React
   from `window.React` (set in `react-global.ts`, imported first) and
   publishes `window.Alo`. `alo.tsx` re-exports those components typed with
   the bundle's own `index.d.ts` props. Import components only from
   `src/design-system/alo`:

   ```tsx
   import { Button, Japa, ReadingPanel } from '../design-system/alo';
   ```

3. **Assets** are referenced by URL, as supplied, never recoloured:
   `/design-system/assets/Logos/wordmark-on-light.svg`,
   `/design-system/assets/Mascot/japa-happy.svg`, etc.

## Rules this enforces

- No hard-coded colour, spacing, radius or font values in app code: use the
  `--…` variables and type classes from `tokens.css`. (The PWA manifest in
  `vite.config.ts` is the one exception — a manifest cannot read CSS
  variables, so the Day `surface`/`night` hex values are noted there.)
- Kid mode and grown-up mode are never mixed on one screen; kid mode shows
  no score, timer, percentage or red. Story text uses `.reading-*` (Andika).
- If the system lacks a piece, keep the deviation minimal and record it in
  the PR under "Design system deviations" (see `alo-ui-change`).
