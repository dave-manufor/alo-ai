import { Link } from 'react-router-dom';
import { accountStore, useAccount } from '../account/store';
import NavButton from '../design-system/NavButton';
import { PLAN_PRICE, PLAN_PRICE_PERIOD } from '../plan/price';
import { formatLongDay, nextCheckIso } from '../report/childReports';
import { sampleBooks, samplePlan } from '../report/reportFixture';
import { useLatestReport } from '../report/useReports';
import { useActiveChild } from '../shell/activeChildContext';
import { Card, ListRow, Notice, SectionLabel } from '../ui/primitives';

// The weekly plan (a tab; wireframe 20). With a subscription: activities for home, books at
// the child's level, and when the next check is. Without one: the free tip from the report
// and the way to get the plan. The plan comes from the child's latest report.
export default function PlanPage() {
  const { guardian } = useAccount();
  const { child } = useActiveChild();
  const { status, report } = useLatestReport(child?.child_id);
  const entitled = guardian !== null && accountStore.hasActiveSubscription();

  if (!child) return null;

  if (status !== 'ready') {
    return (
      <div className="page page--mid">
        <h1 className="display-m">{child.first_name}&apos;s plan</h1>
        <Notice tone="plain" role="status">
          {status === 'loading' ? 'Getting the plan…' : 'We could not load the plan. Please try again.'}
        </Notice>
      </div>
    );
  }

  if (!report || report.profile.code === 'INSUFFICIENT_EVIDENCE') {
    return (
      <div className="page page--mid">
        <h1 className="display-m">{child.first_name}&apos;s plan</h1>
        <Card>
          <h2 className="title">The plan starts after a check</h2>
          <p className="body">
            Once {child.first_name} has done a reading check, the plan and books are made from what the check showed.
          </p>
          <NavButton variant="primary" size="grown" icon="book" to={`/ready/${child.child_id}`}>
            Start a reading check
          </NavButton>
        </Card>
      </div>
    );
  }

  const books = report.recommendations.book_ids.flatMap((id) => (sampleBooks[id] ? [sampleBooks[id]] : []));

  return (
    <div className="page page--mid">
      <div className="step">
        <h1 className="display-m">{child.first_name}&apos;s plan</h1>
        <p className="caption muted">
          For the next two weeks · from the {formatLongDay(report.timestamp_iso)} check
        </p>
      </div>

      {entitled ? (
        <>
          <section className="step" aria-labelledby="try-heading">
            <SectionLabel id="try-heading">Try at home</SectionLabel>
            <ul className="activity-list">
              {samplePlan.map((activity) => (
                <li key={activity.activity_id}>
                  <Card>
                    <span className="body card-title">{activity.title}</span>
                    <span className="body muted">{activity.text}</span>
                  </Card>
                </li>
              ))}
            </ul>
          </section>

          {books.length > 0 ? (
            <section className="step" aria-labelledby="books-heading">
              <SectionLabel id="books-heading">Books for {child.first_name}</SectionLabel>
              <Card>
                <div className="ui-list">
                  {books.map((book) => (
                    <ListRow
                      key={book.book_id}
                      icon="book"
                      title={book.title}
                      subtitle={
                        <>
                          {book.author} · Level {book.arl}
                          <br />
                          {book.licence}. {book.attribution}
                        </>
                      }
                    />
                  ))}
                </div>
              </Card>
              <p className="caption muted">
                Open-licence African storybooks, chosen from the Alo.ai catalogue for {child.first_name}&apos;s level and
                interests.
              </p>
            </section>
          ) : null}

          <Card tone="leaf">
            <SectionLabel>Next check</SectionLabel>
            <p className="body card-title">
              {formatLongDay(nextCheckIso(report))}, with a new story at {child.first_name}&apos;s level.
            </p>
          </Card>
        </>
      ) : (
        <>
          <Card>
            <SectionLabel>Try this week</SectionLabel>
            <p className="body">{report.parent_reporting?.home_practice}</p>
            <p className="caption muted">One thing to try is free with every check.</p>
          </Card>
          <Card tone="night">
            <p className="title">Get {child.first_name}&apos;s weekly plan</p>
            <p className="body">
              A short activity for home after every check, plus books at {child.first_name}&apos;s level.
            </p>
            <NavButton variant="primary" size="grown" to="/upgrade" style={{ width: '100%' }}>
              See the plan · {PLAN_PRICE} {PLAN_PRICE_PERIOD}
            </NavButton>
          </Card>
          <Link to={`/reports/${report.session_id}`} className="body card-title">
            Back to the report
          </Link>
        </>
      )}
    </div>
  );
}
