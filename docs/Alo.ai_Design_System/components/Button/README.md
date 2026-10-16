# Button

A chunky button that sits on its own darker edge and drops onto it when tapped. Pass `variant`, `size`, an optional `icon` and the label as children.

- **Kid mode** (`size="kid"`, the default): at least `tap-kid` tall, `kid-button` type, a press edge. One `primary` per screen.
- **Grown-up mode** (`size="grown"`): `tap-grown` tall, flat, `radius-m`.
- `primary` (`night`) is the main action. `reward` (`moon`) appears only after a reward ("Collect stars", "Next story"). `call` (`coral`) is for the "Àlọ́ o!" moment and secondary game actions. `done` (`leaf`) confirms a finished step. `secondary` and `ghost` are quiet.
- Every kid button has an icon and a word, so children who can't read the label still know what it does.
- Labels start with a verb and stay short: "Start reading", "Say it again".
- Don't use `reward` for anything but rewards, and never put white text on `moon`, `coral` or `leaf`.
