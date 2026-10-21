import type { ReactNode } from 'react';
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAccount } from './account/store';
import CheckoutPlaceholderPage from './pages/CheckoutPlaceholderPage';
import ChildrenPage from './pages/ChildrenPage';
import ConsentPage from './pages/ConsentPage';
import LandingPage from './pages/LandingPage';
import NotFoundPage from './pages/NotFoundPage';
import ReportDetailPage from './pages/ReportDetailPage';
import ReportsPage from './pages/ReportsPage';
import SchoolChildPage from './pages/SchoolChildPage';
import SchoolsPreviewPage from './pages/SchoolsPreviewPage';
import SessionPage from './pages/SessionPage';
import SignInPage from './pages/SignInPage';

// Grown-up data stays behind sign-in (PRD 12: guardians see only their
// own children; every report read will be audited by the Account
// service). The kid session is gated per child in SessionPage itself.
function RequireGuardian({ children }: { children: ReactNode }) {
  const { guardian } = useAccount();
  return guardian ? <>{children}</> : <Navigate to="/signin" replace />;
}

// Routing. Kid-mode and grown-up-mode screens are separate routes and
// are never mixed on one screen (design system README).
export default function App() {
  // The kid session is a full-bleed Night screen (the "Àlọ́ Night
  // Session" demo): no grown-up chrome inside it.
  const { pathname } = useLocation();
  const inSession = pathname.startsWith('/session/');
  return (
    <div className="app-shell">
      {inSession ? null : (
        <header className="app-header">
          <Link to="/">
            <img
              className="app-wordmark"
              src="/design-system/assets/Logos/wordmark-on-light.svg"
              alt="alo.ai"
            />
          </Link>
        </header>
      )}
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/signin" element={<SignInPage />} />
        <Route path="/consent" element={<ConsentPage />} />
        <Route path="/children" element={<ChildrenPage />} />
        <Route path="/session/:childId" element={<SessionPage />} />
        <Route
          path="/reports"
          element={
            <RequireGuardian>
              <ReportsPage />
            </RequireGuardian>
          }
        />
        <Route
          path="/reports/:sessionId"
          element={
            <RequireGuardian>
              <ReportDetailPage />
            </RequireGuardian>
          }
        />
        <Route
          path="/plan/checkout"
          element={
            <RequireGuardian>
              <CheckoutPlaceholderPage />
            </RequireGuardian>
          }
        />
        <Route path="/schools/preview" element={<SchoolsPreviewPage />} />
        <Route path="/schools/preview/children/:childId" element={<SchoolChildPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </div>
  );
}
