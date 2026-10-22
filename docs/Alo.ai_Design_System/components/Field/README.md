# Field

A label with a text input, or with a select when you pass `options`. Grown-up mode. `id` and `label` are required; the label is tied to the control by `htmlFor`. Other props (`value`, `onChange`, `required`, `autoComplete`, ...) go to the control.

- The control is `tap-grown` tall with a 2px `line-strong` border (3:1) and `radius-s`.
- `hint` adds a line below, linked with `aria-describedby`.
- Errors are shown as text under the field using the `alert` token, never by colour alone; this piece does not draw them.
- Keyboard focus is the system's 3px `focus-ring`.
