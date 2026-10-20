import { Link, useParams } from 'react-router-dom';
import { Button, ParentReportCard, ProfilePill } from '../design-system/alo';
import {
  formatReportDate,
  sampleBooks,
  samplePlan,
  sampleReports,
} from '../report/reportFixture';

// Grown-up mode: one ReadingReport (PRD 10.4). The summary leads with a
// strength, then one thing to work on, then one thing to do (design
// system voice rules). A level is only called confirmed after two checks
// agree; a short check is called a first look.
export default function ReportDetailPage() {
  const { sessionId } = useParams();
  const report = sampleReports.find((item) => item.session_id === sessionId);

  if (!report) {
    return (
      <main className="app-main">
        <section className="stack">
          <h1 className="title">We could not find that report</h1>
          <p className="body">It may still be on its way. Reports appear here when they are ready.</p>
          <Link to="/reports">
            <Button variant="secondary" size="grown">
              Back to reports
            </Button>
          </Link>
        </section>
      </main>
    );
  }

  const stats = [
    { label: 'Words read correctly', value: `${report.fluency.accuracy_pct}%` },
    { label: 'Words a minute', value: report.fluency.wcpm },
    { label: 'Understanding the story', value: `${report.comprehension.reading_comprehension}%` },
  ];
  if (report.comprehension.listening_module_run && report.comprehension.listening_comprehension !== null) {
    stats.push({
      label: 'Understanding when listening',
      value: `${report.comprehension.listening_comprehension}%`,
    });
  }

  return (
    <main className="app-main">
      <section className="stack">
        <h1 className="title">{report.child_display_name}&apos;s report</h1>
        <ProfilePill profile={report.profile.code} provisional={report.profile.provisional} />
        <p className="body muted">
          {formatReportDate(report.timestamp_iso)} · Story: {report.passage.title}
        </p>
        {report.flags.includes('SHORT_READING') ? (
          <p className="body">
            This was a short check, so think of it as a first look. The
            reading level is a guide until two checks agree.
          </p>
        ) : null}
      </section>

      <ParentReportCard
        title="How the reading went"
        date={formatReportDate(report.timestamp_iso)}
        summary={report.profile.primary_need}
        stats={stats}
        workingOn={report.profile.instructional_focus}
        tip={samplePlan[0].text}
      />

      <section className="card" aria-labelledby="level-heading">
        <h2 id="level-heading" className="title">
          Reading level guide
        </h2>
        <p className="body">
          About ARL {report.level.reported_arl} ({report.level.approx_primary_class}).
          {report.level.confirmed
            ? ' Two checks agree on this level.'
            : ' One more check will confirm this level.'}
        </p>
      </section>

      <section className="card" aria-labelledby="books-heading">
        <h2 id="books-heading" className="title">
          Books to try next
        </h2>
        <ul className="body">
          {sampleBooks.map((book) => (
            <li key={book.book_id}>
              {book.title} <span className="muted">({book.band})</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card" aria-labelledby="plan-heading">
        <h2 id="plan-heading" className="title">
          The weekly reading plan
        </h2>
        <p className="body">
          A two-week plan with short activities like these, made for{' '}
          {report.child_display_name} from this check:
        </p>
        <ul className="body">
          {samplePlan.map((activity) => (
            <li key={activity.activity_id}>
              <strong>{activity.title}.</strong> {activity.text}
            </li>
          ))}
        </ul>
        <Link to="/plan/checkout">
          <Button variant="primary" size="grown">
            Get the weekly plan
          </Button>
        </Link>
      </section>

      <Link to="/reports">
        <Button variant="secondary" size="grown">
          Back to reports
        </Button>
      </Link>
    </main>
  );
}
