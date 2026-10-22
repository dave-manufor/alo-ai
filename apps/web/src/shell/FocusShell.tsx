import { Link, Outlet } from 'react-router-dom';

// One task, nothing else: sign-in, getting ready for a check, the privacy and terms text.
// A wordmark and the screen; no tab bar to wander off with.
export default function FocusShell() {
  return (
    <div className="shell shell--focus">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="shell-top shell-top--plain">
        <Link to="/" className="shell-brand">
          <img className="app-wordmark" src="/design-system/assets/Logos/wordmark-on-light.svg" alt="alo.ai" />
        </Link>
      </header>
      <main id="main" className="shell-main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
