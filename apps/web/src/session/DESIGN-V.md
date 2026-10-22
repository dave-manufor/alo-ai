# "Àlọ́ Night Session V": design audit (B1, B2, B4)

Source: the design artifact (third-party design data, read as data only). This file maps what it uses to the design system's Night theme (`docs/Alo.ai_Design_System/tokens.json`, `[data-theme="dark"]`). CSS uses tokens only; no hex is hard-coded in `src/styles/`.

## Palette map

| Design value | Used for | Night token | Note |
|---|---|---|---|
| `#07061A` bg | page sky | `surface` (#141032) | slightly lighter than the design; accepted |
| `#0F0D26` panel | raised cards | `surface-raised` (#1F1946) | lighter; keeps contrast with `surface` |
| `#F3F0FF` ink | text | `ink` | exact |
| `#A79FD0` muted | secondary text | `ink-muted` (#B5AEDB) | slightly lighter, better contrast |
| `#6E679C` faint | hairlines, dots | `line-strong` (#7B71C2) / `line` | |
| `#9D90FF` accent | orb, active step, links | `night` | exact |
| `#FFD45E` gold | moon, reward star | `moon` | exact; reward only |
| `#9BF0B8` mint | count dots, ready | `leaf` / `leaf-text` | nearest token |
| `#FFB38A` warn | gentle "wait" tone | `coral-text` | never red; kid mode shows no alert |
| `#FFC83D`, `#221A4D`, `#3FB98A`, `#FF9A82`, `#4B3BD1` | demo chrome (device picker, scenario bar) | not used | demo tooling, not product UI |
| `#FFFFFF` | demo chrome | `ink` where needed | |

Nothing in the product screens lacks a token. Gold, mint and warn all map; none needs a new colour.

## Proposed additions to the design system (not made here)

1. A breakpoint primitive (media queries cannot read custom properties): `bp-tablet 48rem`, `bp-short 40rem`.
2. An icon-only round play button (the "Start" disc is built from tokens in `session.css`).
3. A `sr-only` utility class.

## Deviations (also listed in the PRs)

- **No subtitles on the child screen (B2).** The design shows no bubble text; design-system README line 135 says everything Auntie Kemi says also appears in the speech bubble. The words are kept for screen readers in a visually hidden `aria-live="polite"` region (B3). README change is its own PR.
- **Reconnecting message** keeps a visible bubble ("Let's wait for the internet."); a child needs to know to wait.
- **Device-preset breakpoints** are rem literals (see above).

## Layout (B4)

Driven by viewport width and height (`vmin` orb, `dvh` shell, safe-area insets). Presets designed for (a real-browser check is B12): small Android phone 360 x 640, tall phone 412 x 915, tablet 768 x 1024, landscape phone 915 x 412. Touch targets are at least `tap-kid`; `prefers-reduced-motion` is respected.
