import { Link, Outlet } from 'react-router-dom';
import { previewBannerText } from '../preview/teacherFixture';
import { Notice } from '../ui/primitives';

// The teacher view PREVIEW (PRD 4.7). Sample data only, so the banner is on every screen
// of it, and nothing here signs anyone in or reaches a service.
export default function SchoolShell() {
  return (
    <div className="shell shell--school">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="shell-top shell-top--plain">
        <div className="shell-brand-group">
          <Link to="/" className="shell-brand">
            <img className="app-wordmark" src="/design-system/assets/Logos/wordmark-on-light.svg" alt="alo.ai" />
          </Link>
          <span className="label muted shell-label">Class view</span>
        </div>
        <Link to="/signin" className="shell-link">
          Parent sign in
        </Link>
      </header>
      <main id="main" className="shell-main" tabIndex={-1}>
        <div className="page page--wide">
          <Notice tone="sky" role="note">
            {previewBannerText}
          </Notice>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
