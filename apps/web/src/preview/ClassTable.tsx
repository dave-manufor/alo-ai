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
              <td>
                <Link to={`/schools/preview/children/${child.id}`}>{child.name}</Link>
                {child.dueForCheck ? <span className="due-pill">Due a check</span> : null}
              </td>
              <td>{child.lastCheck}</td>
              <td>{child.readingLevel}</td>
              <td>
                <ProfilePill profile={child.profile} provisional={child.provisional} />
              </td>
              <td>{child.accuracyPct === null ? '—' : `${child.accuracyPct}%`}</td>
              <td>{child.wcpm === null ? '—' : child.wcpm}</td>
              <td>{flags(child).join(', ') || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
