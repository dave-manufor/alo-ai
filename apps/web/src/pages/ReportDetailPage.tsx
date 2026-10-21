import { useParams } from 'react-router-dom';
import { useAccount } from '../account/store';
import { ParentReportCard, ProfilePill } from '../design-system/alo';
import NavButton from '../design-system/NavButton';
import {
  formatReportDate,
  levelLabel,
  sampleBooks,
  sampleChildren,
  samplePlan,
  sampleReports,
} from '../report/reportFixture';

// Grown-up mode, signed-in guardians only (gated in App). One
// ReadingReport joined with its child (PRD 10.4, 12). Free at this stage:
// the Coach's spoken summary text and one home practice. The weekly plan
// itself is what a subscription unlocks (PRD 11.1), so its activities
// only appear with an active entitlement.
export default function ReportDetailPage() {
  const { sessionId } = useParams();
  const { guardian } = useAccount();
  const report = sampleReports.find((item) => item.session_id === sessionId);

  if (!report) {
    return (
      <main className="app-main">
        <section className="stack">
          <h1 className="title">We could not find that report</h1>
          <p className="body">It may still be on its way. Reports appear here when they are ready.</p>
          <NavButton variant="secondary" size="grown" to="/reports">
            Back to reports
          </NavButton>
        </section>
      </main>
    );
  }

  const child = sampleChildren[report.child_id];
  const name = child?.first_name ?? 'Your child';
  const noEvidence = report.profile.code === 'INSUFFICIENT_EVIDENCE';
  const entitled =
    guardian !== null &&
    // subscriptions/{guardian_id} — sample data has no active subscription
    // in the fixture phase, so the plan stays described, not shown.
    (report as { entitled?: boolean }).entitled === true;
  const level = levelLabel(report);

  const stats: { label: string; value: string | number }[] = [];
  if (!noEvidence) {
    if (report.fluency.accuracy_pct !== null) {
      stats.push({ label: 'Words read correctly', value: `${report.fluency.accuracy_pct}%` });
    }
    if (report.fluency.wcpm !== null) {
      stats.push({ label: 'Words a minute', value: report.fluency.wcpm });
    }
    if (report.comprehension.reading_comprehension !== null) {
      // A comprehension score out of 100, not a share of the story.
      stats.push({
        label: 'Understanding the story',
        value: `${report.comprehension.reading_comprehension} out of 100`,
      });
    }
    if (report.comprehension.listening_comprehension !== null) {
      stats.push({
        label: 'Understanding when listening',
        value: `${report.comprehension.listening_comprehension} out of 100`,
      });
    }
  }

  return (
    <main className="app-main">
      <section className="stack">
        <h1 className="title">{name}&apos;s report</h1>
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

      {noEvidence ? (
        <section className="card">
          <h2 className="title">Let&apos;s try another check</h2>
          <p className="body">
            We could not hear enough reading this time to learn anything
            useful. Try again when it is quiet, with the phone close, and
            we will listen properly.
          </p>
        </section>
      ) : (
        <ParentReportCard
          title="How the reading went"
          date={formatReportDate(report.timestamp_iso)}
          summary={
            report.parent_reporting
              ? report.parent_reporting.summary_script
              : 'Your summary is on its way. It will appear here as soon as it is ready.'
          }
          stats={stats}
          workingOn={report.profile.instructional_focus}
          tip={report.parent_reporting?.home_practice}
        />
      )}

      {level !== null ? (
        <section className="card" aria-labelledby="level-heading">
          <h2 id="level-heading" className="title">
            Reading level guide
          </h2>
          <p className="body">
            {level}
            {report.level.approx_primary_class
              ? ` (${report.level.approx_primary_class}).`
              : '.'}{' '}
            {report.level.confirmed
              ? 'Two checks agree on this level.'
              : 'One more check will confirm this level.'}
          </p>
        </section>
      ) : null}

      {report.recommendations.book_ids.length > 0 ? (
        <section className="card" aria-labelledby="books-heading">
          <h2 id="books-heading" className="title">
            Books to try next
          </h2>
          <ul className="body">
            {report.recommendations.book_ids.map((bookId) => {
              const book = sampleBooks[bookId];
              if (!book) return null;
              return (
                <li key={bookId}>
                  {book.title} <span className="muted">by {book.author} (ARL {book.arl})</span>
                  <br />
                  <span className="muted caption">
                    {book.licence}. {book.attribution}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {!noEvidence ? (
        <section className="card" aria-labelledby="plan-heading">
          <h2 id="plan-heading" className="title">
            The weekly reading plan
          </h2>
          {entitled ? (
            <ul className="body">
              {samplePlan.map((activity) => (
                <li key={activity.activity_id}>
                  <strong>{activity.title}.</strong> {activity.text}
                </li>
              ))}
            </ul>
          ) : (
            <>
              <p className="body">
                A two-week plan with a short activity each day, made for{' '}
                {name} from this check, plus new stories every week. The
                summary above and one thing to try at home are free with
                every check.
              </p>
              <NavButton variant="primary" size="grown" to="/plan/checkout">
                Get the weekly plan
              </NavButton>
            </>
          )}
        </section>
      ) : null}

      <NavButton variant="secondary" size="grown" to="/reports">
        Back to reports
      </NavButton>
    </main>
  );
}
