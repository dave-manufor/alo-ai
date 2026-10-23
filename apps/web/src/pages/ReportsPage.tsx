import { Link, useSearchParams } from 'react-router-dom';
import { ProfilePill } from '../design-system/alo';
import NavButton from '../design-system/NavButton';
import { formatReportDate } from '../report/reportFixture';
import { useReports } from '../report/useReports';
import { usePendingReport, type PendingReport } from '../session/status';
import { useActiveChild } from '../shell/activeChildContext';
import { Avatar, Card, Notice } from '../ui/primitives';

// Reports (a tab): every reading check, newest first, one card each. Every number lives on
// the report itself; this list shows only who, when, the story and the reader profile.
const PENDING_TEXT: Record<Exclude<PendingReport, 'none' | 'ready'>, string> = {
  waiting: 'The report is being made. This usually takes a minute or two, and it will appear here on its own.',
  unfinished:
    'That reading check stopped before the end, so there is no report for it. You can start another one when you are ready.',
  unknown: 'The report is taking longer than usual. Please look again in a little while.',
};

export default function ReportsPage() {
  // /reports?pending=<session id> is where a finished reading check sends the grown-up.
  const [params] = useSearchParams();
  const pending = usePendingReport(params.get('pending'));
  const view = useReports(pending === 'ready' ? 'ready' : '');
  const { child } = useActiveChild();

  return (
    <div className="page page--mid">
      <div className="step">
        <h1 className="display-m">Reading reports</h1>
        <p className="body muted">
          A plain look at each reading check: a strength first, then one thing to work on and one thing to do.
        </p>
      </div>

      {pending !== 'none' && pending !== 'ready' ? (
        <Notice tone={pending === 'waiting' ? 'plain' : 'sky'} role="status">
          {PENDING_TEXT[pending]}
        </Notice>
      ) : null}

      {view.status !== 'ready' ? (
        <Notice tone={view.status === 'error' ? 'sky' : 'plain'} role={view.status === 'error' ? 'alert' : 'status'}>
          {view.status === 'loading' ? 'Getting the reports…' : view.message}
        </Notice>
      ) : view.reports.length === 0 ? (
        <Card>
          <h2 className="title">No reading checks yet</h2>
          <p className="body">After the first check, the report appears here.</p>
          {child ? (
            <NavButton variant="primary" size="grown" icon="book" to={`/ready/${child.child_id}`}>
              Start a reading check
            </NavButton>
          ) : null}
        </Card>
      ) : (
        <ul className="report-list">
          {view.reports.map((report) => {
            const name = view.children[report.child_id]?.first_name ?? 'Your child';
            return (
              <li key={report.session_id}>
                <Card>
                  <div className="child-card__head">
                    <Avatar name={name} />
                    <div className="child-card__name">
                      <h2 className="title">{name}</h2>
                      <span className="caption muted">
                        {formatReportDate(report.timestamp_iso)} · {report.passage.title}
                      </span>
                    </div>
                  </div>
                  <ProfilePill profile={report.profile.code} provisional={report.profile.provisional} />
                  <Link to={`/reports/${report.session_id}`} className="body card-title ui-tap ui-tap--flush">
                    See the full report
                  </Link>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
