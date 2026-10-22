import { Link, Navigate } from 'react-router-dom';
import { useAccount } from '../account/store';
import NavButton from '../design-system/NavButton';
import { formatLongDay, nextCheckIso } from '../report/childReports';
import { useLatestReport } from '../report/useReports';
import { useActiveChild } from '../shell/activeChildContext';
import { Avatar, Card, SectionLabel } from '../ui/primitives';

function greeting(now = new Date()): string {
  const hour = now.getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

const DEFAULT_TIP = 'While you read together, stop every few sentences and ask “Why do you think that happened?”';

// Home (wireframe 4): the child, when they last read, and the one next thing to do. With
// more than one child, the switcher in the top bar picks who this is about.
export default function HomePage() {
  const { children } = useAccount();
  const { child } = useActiveChild();
  const { report } = useLatestReport(child?.child_id);
  if (!child) return <Navigate to={children.length === 0 ? '/onboarding/consent' : '/'} replace />;

  const tip = report?.parent_reporting?.home_practice ?? DEFAULT_TIP;

  return (
    <div className="page page--wide">
      <h1 className="title home-greeting">{greeting()}</h1>
      <div className="page-grid">
        <div className="page-stack">
          <Card>
            <div className="child-card__head">
              <Avatar name={child.first_name} />
              <div className="child-card__name">
                <h2 className="title">{child.first_name}</h2>
                <span className="caption muted">Primary {child.primary_class}</span>
              </div>
            </div>
            <div className="ui-stat-row">
              <div className="ui-stat">
                <span className="label muted">Last check</span>
                <span className="body card-title">{report ? formatLongDay(report.timestamp_iso) : 'None yet'}</span>
              </div>
              <div className="ui-stat">
                <span className="label muted">Next check</span>
                <span className="body card-title">{report ? formatLongDay(nextCheckIso(report)) : 'Any time'}</span>
              </div>
            </div>
            <NavButton variant="primary" size="grown" icon="book" to={`/ready/${child.child_id}`} style={{ width: '100%' }}>
              Start a reading check
            </NavButton>
            {report ? (
              <Link to={`/reports/${report.session_id}`} className="body card-title">
                See the last report
              </Link>
            ) : null}
          </Card>
        </div>
        <div className="page-stack">
          <Card>
            <SectionLabel>Try this week</SectionLabel>
            <p className="body">{tip}</p>
            <Link to="/plan" className="body card-title">
              Open {child.first_name}&apos;s plan
            </Link>
          </Card>
          <NavButton variant="ghost" size="grown" to="/children/new" style={{ alignSelf: 'flex-start' }}>
            Add another child
          </NavButton>
        </div>
      </div>
    </div>
  );
}
