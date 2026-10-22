import { useId, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import Icon from './Icon';

// Thin wrappers for patterns the design system does not ship (form controls, list rows,
// notices, a back link). Every value comes from the tokens, through the classes in
// styles/screens.css and styles/forms.css. Recorded as design-system deviations in the PR.

/** A raised card. `tone` picks a soft background from the tokens. */
export function Card({
  tone = 'raised',
  children,
  ...rest
}: {
  tone?: 'raised' | 'night' | 'leaf' | 'sky';
  children: ReactNode;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div {...rest} className={`ui-card ui-card--${tone}${rest.className ? ` ${rest.className}` : ''}`}>
      {children}
    </div>
  );
}

/** The small uppercase label above a group, e.g. "Children". */
export function SectionLabel({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <h2 className="label ui-section-label" id={id}>
      {children}
    </h2>
  );
}

/** "Back" as in the wireframes: a link, 44px tall. */
export function BackLink({ to, children = 'Back' }: { to: string; children?: ReactNode }) {
  return (
    <Link to={to} className="ui-back">
      <Icon name="back" size={20} />
      {children}
    </Link>
  );
}

/** A banner line: the sky one is for information, leaf for good news, night for emphasis. */
export function Notice({
  tone = 'sky',
  role,
  children,
}: {
  tone?: 'sky' | 'leaf' | 'night' | 'plain';
  role?: 'note' | 'status' | 'alert';
  children: ReactNode;
}) {
  return (
    <div className={`ui-notice ui-notice--${tone}`} role={role}>
      {children}
    </div>
  );
}

/** A label, the control and the hint or error under it, wired together for screen readers. */
export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  children: (props: { id: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }) => ReactNode;
}) {
  const id = useId();
  const describedBy = [hint ? `${id}-hint` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ');
  return (
    <div className="ui-field">
      <label htmlFor={id} className="label">
        {label}
      </label>
      {children({
        id,
        'aria-describedby': describedBy || undefined,
        'aria-invalid': error ? true : undefined,
      })}
      {hint ? (
        <span id={`${id}-hint`} className="caption muted">
          {hint}
        </span>
      ) : null}
      {error ? (
        <span id={`${id}-error`} className="caption ui-error" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}

/** One choice from a few (the class P1..P6): pressed buttons in a labelled group. */
export function Segmented<T extends string | number>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  const id = useId();
  return (
    <div className="ui-field">
      <span id={id} className="label">
        {label}
      </span>
      <div role="group" aria-labelledby={id} className="ui-segmented">
        {options.map((option) => (
          <button
            key={String(option.value)}
            type="button"
            aria-pressed={option.value === value}
            className="ui-segment"
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/** A checkbox with its text, big enough to tap, for consent and settings. */
export function CheckRow({
  checked,
  onChange,
  title,
  hint,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  title: ReactNode;
  hint?: ReactNode;
}) {
  const id = useId();
  return (
    <div className="ui-check">
      <input id={id} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <div className="ui-check__text">
        <label htmlFor={id} className="body ui-check__title">
          {title}
        </label>
        {hint ? <span className="caption muted">{hint}</span> : null}
      </div>
    </div>
  );
}

/** An on/off setting, announced as a switch. */
export function Switch({
  checked,
  onChange,
  title,
  hint,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  title: string;
  hint?: string;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="ui-switch">
      <label htmlFor={id} className="ui-switch__text">
        <span className="body ui-check__title">{title}</span>
        {hint ? <span className="caption muted">{hint}</span> : null}
      </label>
      <input
        id={id}
        type="checkbox"
        role="switch"
        className="ui-switch__input"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
    </div>
  );
}

/** A tappable row in a list card: title, a line under it, and a chevron or an end slot. */
export function ListRow({
  to,
  icon,
  title,
  subtitle,
  end,
}: {
  /** Omit for a row that is only information, not a link. */
  to?: string;
  icon?: 'book' | 'child' | 'reports';
  title: ReactNode;
  subtitle?: ReactNode;
  end?: ReactNode;
}) {
  const content = (
    <>
      {icon ? <Icon name={icon} /> : null}
      <span className="ui-row__text">
        <span className="body ui-row__title">{title}</span>
        {subtitle ? <span className="caption muted">{subtitle}</span> : null}
      </span>
      {end ?? null}
    </>
  );
  return to ? (
    <Link to={to} className="ui-row">
      {content}
    </Link>
  ) : (
    <div className="ui-row">{content}</div>
  );
}

/** A coloured circle with the child's first letter. Decorative: the name is next to it. */
export function Avatar({ name }: { name: string }) {
  return (
    <span className="ui-avatar" aria-hidden="true">
      {name.trim().charAt(0).toUpperCase()}
    </span>
  );
}
