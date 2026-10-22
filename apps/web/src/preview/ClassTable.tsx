import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ProfilePill } from '../design-system/alo';
import type { PreviewChild } from './teacherFixture';

type SortKey = 'name' | 'lastCheckIso' | 'accuracyPct' | 'wcpm';

const columns: { key: SortKey; label: string }[] = [
  { key: 'name', label: 'Child' },
  { key: 'lastCheckIso', label: 'Last check' },
  { key: 'accuracyPct', label: 'Accuracy' },
  { key: 'wcpm', label: 'Words a minute' },
];

function flags(child: PreviewChild): string[] {
  const out: string[] = [];
  if (child.provisional) out.push('provisional');
  if (child.assisted) out.push('assisted');
  return out;
}

/** Class table (PRD 4.7): sortable, children due a check are labelled. */
export default function ClassTable({ children }: { children: PreviewChild[] }) {
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [ascending, setAscending] = useState(true);

  const rows = useMemo(() => {
    const empty = (value: string | number | null) => value === null || value === '';
    return [...children].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      // Children with no result yet always sort last, in both directions.
      if (empty(av) || empty(bv)) {
        return empty(av) === empty(bv) ? 0 : empty(av) ? 1 : -1;
      }
      const order = av < bv ? -1 : av > bv ? 1 : 0;
      return ascending ? order : -order;
    });
  }, [children, sortKey, ascending]);

  function sortBy(key: SortKey) {
    if (key === sortKey) {
      setAscending((value) => !value);
    } else {
      setSortKey(key);
      setAscending(true);
    }
  }

  return (
    <div className="table-scroll">
      {/* On a phone the table becomes one card per child (preview.css); the column buttons
          are then hidden, so sorting is offered here instead. */}
      <label className="preview-sort">
        <span className="label muted">Sort by</span>
        <select
          className="ui-input"
          value={`${sortKey}:${ascending ? 'asc' : 'desc'}`}
          onChange={(event) => {
            const [key, direction] = event.target.value.split(':');
            setSortKey(key as SortKey);
            setAscending(direction === 'asc');
          }}
        >
          {columns.flatMap((col) => [
            <option key={`${col.key}:asc`} value={`${col.key}:asc`}>
              {col.label}, low to high
            </option>,
            <option key={`${col.key}:desc`} value={`${col.key}:desc`}>
              {col.label}, high to low
            </option>,
          ])}
        </select>
      </label>
      <table className="preview-table">
        <caption className="caption muted">P3B (sample), {children.length} children</caption>
        <thead>
          <tr>
            {columns.slice(0, 2).map((col) => (
              <th key={col.key} aria-sort={sortKey === col.key ? (ascending ? 'ascending' : 'descending') : undefined}>
                <button className="sort-button" type="button" onClick={() => sortBy(col.key)}>
                  {col.label}
                </button>
              </th>
            ))}
            <th>Reading level</th>
            <th>Profile</th>
            {columns.slice(2).map((col) => (
              <th key={col.key} aria-sort={sortKey === col.key ? (ascending ? 'ascending' : 'descending') : undefined}>
                <button className="sort-button" type="button" onClick={() => sortBy(col.key)}>
                  {col.label}
                </button>
              </th>
            ))}
            <th>Flags</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((child) => (
            <tr key={child.id} className={child.dueForCheck ? 'row-due' : undefined}>
              <td className="cell-name">
                <Link to={`/schools/children/${child.id}`}>{child.name}</Link>
                {child.dueForCheck ? <span className="due-pill">Due a check</span> : null}
              </td>
              <td data-label="Last check">{child.lastCheck}</td>
              <td data-label="Reading level">{child.readingLevel}</td>
              <td className="cell-profile">
                <ProfilePill profile={child.profile} provisional={child.provisional} />
              </td>
              <td data-label="Accuracy">{child.accuracyPct === null ? '—' : `${child.accuracyPct}%`}</td>
              <td data-label="Words a minute">{child.wcpm === null ? '—' : child.wcpm}</td>
              <td data-label="Flags" data-empty={flags(child).length === 0 ? '' : undefined}>
                {flags(child).join(', ') || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
