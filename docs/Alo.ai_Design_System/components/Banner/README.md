# Banner

A calm status line with an icon, for grown-up screens ("Your connection is good enough for a check."). `tone`: `good` (`leaf-soft`, check circle), `info` (`sky-soft`) or `notice` (`night-soft`). Text is `ink`; the icon uses the matching `*-text` token. Announced politely with `role="status"`.

- Never red and never `moon`. A system error uses `alert` text in the page, not a banner tone.
- Always carries words as well as the icon.
- Grown-up mode only: kid screens use Jàpá and a SpeechBubble instead.
