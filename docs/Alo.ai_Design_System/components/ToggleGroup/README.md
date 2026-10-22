# ToggleGroup

One choice from a few short options, as buttons with `aria-pressed` (for example the class, P1 to P6). Grown-up mode. Pass `id`, `label`, `options` (`{ value, label }`), `value` and `onChange`.

- The options sit in one row, equal width, each `tap-grown` tall. The selected one is filled `night` with `on-night` text, so selection also shows as a fill, not colour alone.
- The group is labelled by its eyebrow label (`role="group"`).
- Keep it to about six options; use Field with `options` for longer lists.
