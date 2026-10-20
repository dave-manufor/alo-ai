import { Link } from 'react-router-dom';
import { Button, ParentReportCard, ProfilePill } from '../design-system/alo';
import { formatReportDate, sampleReports } from '../report/reportFixture';

// Grown-up mode: a guardian's reports (PRD 4.4, 10.4). Fixture-backed in
// the MVP phase; each card is written from a ReadingReport document and
// every number shown comes from that report.
export default function ReportsPage() {
  return (
    <main className="app-main">
      <section className="stack">
        <h1 className="title">Reading reports</h1>
        <p className="body muted">
          A plain look at each reading check: a strength first, then one
          thing to work on and one thing to do.
        </p>
      </section>

      {sampleReports.map((report) => (
        <article key={report.session_id} className="stack">
          <ParentReportCard
            title={`${report.child_display_name}'s reading`}
            date={`${formatReportDate(report.timestamp_iso)} · ${report.passage.title}`}
            summary={report.profile.primary_need}
            stats={[
              { label: 'Words read correctly', value: `${report.fluency.accuracy_pct}%` },
              { label: 'Words a minute', value: report.fluency.wcpm },
            ]}
            workingOn={report.profile.instructional_focus}
          />
          <div className="row">
            <ProfilePill profile={report.profile.code} provisional={report.profile.provisional} />
            <Link to={`/reports/${report.session_id}`}>
              <Button variant="primary" size="grown">
                See the full report
              </Button>
            </Link>
          </div>
        </article>
      ))}
    </main>
  );
}
