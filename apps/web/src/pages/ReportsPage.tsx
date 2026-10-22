import { ParentReportCard, ProfilePill } from '../design-system/alo';
import NavButton from '../design-system/NavButton';
import { formatReportDate } from '../report/reportFixture';
import { useReports } from '../report/useReports';

// Grown-up mode, signed-in guardians only (gated in App). Every number
// comes from the ReadingReport document; a report with no evidence shows
// no numbers at all.
export default function ReportsPage() {
  const view = useReports();
  if (view.status !== 'ready') {
    return (
      <main className="app-main">
        <section className="stack">
          <h1 className="title">Reading reports</h1>
          <p className="body muted" role="status">
            {view.status === 'loading' ? 'Getting the reports…' : view.message}
          </p>
        </section>
      </main>
    );
  }
  const sampleReports = view.reports;
  const sampleChildren = view.children;
  return (
    <main className="app-main">
      <section className="stack">
        <h1 className="title">Reading reports</h1>
        <p className="body muted">
          A plain look at each reading check: a strength first, then one
          thing to work on and one thing to do.
        </p>
      </section>

      {sampleReports.map((report) => {
        const child = sampleChildren[report.child_id];
        const name = child?.first_name ?? 'Your child';
        const noEvidence = report.profile.code === 'INSUFFICIENT_EVIDENCE';
        return (
          <article key={report.session_id} className="stack">
            <ParentReportCard
              title={`${name}'s reading`}
              date={`${formatReportDate(report.timestamp_iso)} · ${report.passage.title}`}
              summary={
                report.parent_reporting?.summary_script ?? report.profile.primary_need
              }
              stats={
                noEvidence || report.fluency.accuracy_pct === null || report.fluency.wcpm === null
                  ? []
                  : [
                      { label: 'Words read correctly', value: `${report.fluency.accuracy_pct}%` },
                      { label: 'Words a minute', value: report.fluency.wcpm },
                    ]
              }
              workingOn={noEvidence ? undefined : report.profile.instructional_focus}
            />
            <div className="row">
              <ProfilePill profile={report.profile.code} provisional={report.profile.provisional} />
              <NavButton variant="primary" size="grown" to={`/reports/${report.session_id}`}>
                See the full report
              </NavButton>
            </div>
          </article>
        );
      })}
    </main>
  );
}
