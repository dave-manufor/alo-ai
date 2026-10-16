# MicButton

The big round button a child taps to talk, in three states: `idle` (`night`), `listening` (`sky`, with a pulsing glow) and `thinking` (`moon`, with hopping dots).

- Only one per screen, centred, at `mic` size (112px).
- The consumer controls `state` from the Session Agent's events and passes an optional `label`; defaults are "Tap to talk", "Listening…" and "One moment".
- Pair `listening` with Jàpá's `listening` pose. The pulse stops under `prefers-reduced-motion`.
