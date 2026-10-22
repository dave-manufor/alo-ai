# Paper

A light card that carries its own light token scope (`data-theme="light"`), so it stays light when it sits inside the Night session. Story pages and the hand-back report card use it.

- **Where it is allowed:** only inside a kid-mode Night screen, for story text (Andika, `reading-*`) and for the hand-back card after the grown-up hold gate. The card is a surface for reading, not a second theme for the screen: the rest of the screen stays Night.
- A hand-back report card is grown-up mode. Show it only after the hold gate and with no Jàpá, kid button or moon on that card.
- Text is `ink` on `surface-raised`; both come from the scoped light tokens, so contrast is the Day theme's (4.5:1).
- Never put `moon`, `coral`, `leaf` or `sky` text on it without the `*-text` token, and keep `on-bright` on fills.
- Plain `data-theme="light"` on any element does the same job without the card styling.
- Pass `as` to change the tag (default `div`).
