import { Link, NavLink, Outlet } from 'react-router-dom';
import Icon, { type IconName } from '../ui/Icon';
import { ActiveChildProvider } from './ActiveChild';
import { useActiveChild } from './activeChildContext';

const tabs: { to: string; label: string; icon: IconName }[] = [
  { to: '/home', label: 'Home', icon: 'home' },
  { to: '/reports', label: 'Reports', icon: 'reports' },
  { to: '/plan', label: 'Plan', icon: 'plan' },
  { to: '/account', label: 'Account', icon: 'account' },
];

// The signed-in grown-up app. On a phone the four places are a tab bar fixed to the bottom
// (thumb reach); from tablet width up they move into the top bar and the content sits in a
// centred column. It is one <nav>, restyled by CSS, so a screen reader meets it once.
export default function ParentShell() {
  return (
    <ActiveChildProvider>
      <div className="shell">
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <header className="shell-top">
          <Link to="/home" className="shell-brand">
            <img
              className="app-wordmark"
              src="/design-system/assets/Logos/wordmark-on-light.svg"
              alt="alo.ai"
            />
          </Link>
          <ChildSwitcher />
          <nav className="shell-nav" aria-label="Main">
            {tabs.map((tab) => (
              <NavLink key={tab.to} to={tab.to} className="shell-tab">
                <Icon name={tab.icon} />
                <span>{tab.label}</span>
              </NavLink>
            ))}
          </nav>
        </header>
        <main id="main" className="shell-main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </ActiveChildProvider>
  );
}

// Only with two or more children: who the Home, Plan and report screens are about.
function ChildSwitcher() {
  const { child, children, setChildId } = useActiveChild();
  if (children.length < 2 || !child) return null;
  return (
    <label className="shell-child">
      <span className="alo-sr">Child</span>
      <select
        className="ui-input ui-input--compact"
        value={child.child_id}
        onChange={(event) => setChildId(event.target.value)}
      >
        {children.map((item) => (
          <option key={item.child_id} value={item.child_id}>
            {item.first_name}
          </option>
        ))}
      </select>
    </label>
  );
}
