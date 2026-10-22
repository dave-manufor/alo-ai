import { useParams } from 'react-router-dom';
import { useAccount } from '../account/store';
import { dataMode } from '../api';
import { Button, ParentReportCard, ProfilePill } from '../design-system/alo';
import NavButton from '../design-system/NavButton';
import { planUnlocked } from '../plan/access';
import { PLAN_PRICE, PLAN_PRICE_PERIOD } from '../plan/price';
import { formatLongDay, nextCheckIso } from '../report/childReports';
import { formatReportDate, levelLabel } from '../report/reportFixture';
import { useReport } from '../report/useReports';
import { BackLink, Card, Notice, SectionLabel } from '../ui/primitives';

// One ReadingReport joined with its child (PRD 10.4, 12). Free: the spoken-summary text, the
// reading profile and one thing to try at home. The weekly plan and the books are what a
// subscription unlocks (PRD 11.1), on their own screen. Every number comes from the report;
// a report with no evidence shows none, and "null%" is never printed.
export default function ReportDetailPage() {
  const { sessionId } = useParams();
  const { guardian } = useAccount();
  const view = useReport(sessionId);

  if (view.status !== 'ready') {
    return (
      <div className="page">
        <BackLink to="/reports" />
        <Notice tone={view.status === 'error' ? 'sky' : 'plain'} role={view.status === 'error' ? 'alert' : 'status'}>
          {view.status === 'loading' ? 'Getting the report…' : view.message}
        </Notice>
      </div>
    );
  }
  const report = view.report;
  if (!report) {
    return (
      <div className="page">
        <BackLink to="/reports" />
        <Card>
          <h1 className="title">We could not find that report</h1>
          <p className="body">It may still be on its way. Reports appear here when they are ready.</p>
          <NavButton variant="secondary" size="grown" to="/reports">
            Back to reports
          </NavButton>
        </Card>
      </div>
    );
  }

  const name = view.children[report.child_id]?.first_name ?? 'Your child';
  const noEvidence = report.profile.code === 'INSUFFICIENT_EVIDENCE';
  // Entitlement belongs to the guardian (subscriptions/{guardian_id}), not the report.
  const entitled = planUnlocked(guardian !== null);
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
    <div className="page page--wide">
      <BackLink to="/reports" />
      <div className="step">
        <h1 className="display-m">{name}&apos;s report</h1>
        <p className="body muted">
          {formatReportDate(report.timestamp_iso)} · Story: {report.passage.title}
        </p>
        <div>
          <ProfilePill profile={report.profile.code} provisional={report.profile.provisional} />
        </div>
      </div>

      {report.flags.includes('SHORT_READING') ? (
        <Notice tone="sky" role="note">
          This was a short check, so think of it as a first look. The reading level is a guide until two
          checks agree.
        </Notice>
      ) : null}

      <div className="page-grid">
        <div className="page-stack">
          {noEvidence ? (
            <Card>
              <h2 className="title">Let&apos;s try another check</h2>
              <p className="body">
                We could not hear enough reading this time to learn anything useful. Try again when it is quiet,
                with the phone close, and we will listen properly.
              </p>
              <NavButton variant="primary" size="grown" icon="book" to={`/ready/${report.child_id}`}>
                Start another check
              </NavButton>
            </Card>
          ) : (
            <>
              <div className="report-actions">
                <Button variant="secondary" size="grown" icon="ear" disabled style={{ width: '100%' }}>
                  Hear Kemi&apos;s summary
                </Button>
                <p className="caption muted">The spoken summary is coming soon. The same words are below.</p>
              </div>
              <ParentReportCard
                title={`${name}'s reading`}
                date={`Reading check · ${formatReportDate(report.timestamp_iso)}`}
                summary={
                  report.parent_reporting
                    ? report.parent_reporting.summary_script
                    : 'Your summary is on its way. It will appear here as soon as it is ready.'
                }
                stats={stats}
                workingOn={report.profile.instructional_focus}
                tip={report.parent_reporting?.home_practice}
              />
            </>
          )}
        </div>

        <div className="page-stack">
          {!noEvidence ? (
            <Card>
              <SectionLabel>What the check showed</SectionLabel>
              <p className="title">{report.profile.primary_need}</p>
              {level !== null ? (
                <p className="body">
                  Reading level guide: {level}.
                  {report.level.approx_primary_class ? ` ${report.level.approx_primary_class}.` : ''}{' '}
                  {report.level.confirmed
                    ? 'Two checks agree on this level.'
                    : 'One more check will confirm this level.'}
                </p>
              ) : null}
              <p className="caption muted">This is a screening to guide practice. A level is confirmed after two checks agree.</p>
            </Card>
          ) : null}

          {!noEvidence ? (
            <Card tone="night">
              {entitled ? (
                <>
                  <p className="title">{name}&apos;s weekly plan</p>
                  <p className="body">Activities for home and books matched to {name}.</p>
                  <NavButton variant="primary" size="grown" to="/plan" style={{ width: '100%' }}>
                    Open the plan
                  </NavButton>
                </>
              ) : (
                <>
                  <p className="title">Get {name}&apos;s weekly plan</p>
                  <p className="body">Activities for home and books at {name}&apos;s level, matched to what they like.</p>
                  <NavButton variant="primary" size="grown" to="/upgrade" style={{ width: '100%' }}>
                    See the plan · {PLAN_PRICE} {PLAN_PRICE_PERIOD}
                  </NavButton>
                </>
              )}
            </Card>
          ) : null}

          <p className="caption muted">Next check: {formatLongDay(nextCheckIso(report))}, with a new story.</p>
          {dataMode !== 'live' ? (
            <p className="caption muted">This is a sample report for the preview build.</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
