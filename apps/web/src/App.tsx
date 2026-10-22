import type { ReactNode } from 'react';
import { Navigate, Outlet, Route, Routes, useParams } from 'react-router-dom';
import { useAccount } from './account/store';
import AccountPage from './pages/AccountPage';
import ChildFormPage from './pages/ChildFormPage';
import CheckoutPlaceholderPage from './pages/CheckoutPlaceholderPage';
import ConsentPage from './pages/ConsentPage';
import GetReadyPage from './pages/GetReadyPage';
import HomePage from './pages/HomePage';
import LegalPage from './pages/LegalPage';
import NotFoundPage from './pages/NotFoundPage';
import PlanPage from './pages/PlanPage';
import ReportDetailPage from './pages/ReportDetailPage';
import ReportsPage from './pages/ReportsPage';
import SchoolChildPage from './pages/SchoolChildPage';
import SchoolsPreviewPage from './pages/SchoolsPreviewPage';
import SessionPage from './pages/SessionPage';
import SignInPage from './pages/SignInPage';
import UpgradePage from './pages/UpgradePage';
import WelcomePage from './pages/WelcomePage';
import FocusShell from './shell/FocusShell';
import ParentShell from './shell/ParentShell';
import SchoolShell from './shell/SchoolShell';

// Grown-up data stays behind sign-in (PRD 12: guardians see only their own children; every
// report read is audited by the Account service). The kid session is gated per child in
// SessionPage itself.
function RequireGuardian({ children }: { children: ReactNode }) {
  const { guardian } = useAccount();
  return guardian ? <>{children}</> : <Navigate to="/signin" replace />;
}

// A guardian with no child yet goes through the two onboarding steps first.
function RequireChild({ children }: { children: ReactNode }) {
  const { children: kids } = useAccount();
  return kids.length > 0 ? <>{children}</> : <Navigate to="/onboarding/consent" replace />;
}

// Old paths keep working: the session screen and earlier links still use some of them.
function Redirect({ to }: { to: string }) {
  const params = useParams();
  return <Navigate to={to.replace(/:(\w+)/g, (_, key: string) => params[key] ?? '')} replace />;
}

// Routing. Kid-mode and grown-up-mode screens are separate routes and are never mixed on
// one screen (design system README). Three grown-up layouts: a focused one (sign-in,
// onboarding, getting ready), the app with its tabs, and the school preview.
export default function App() {
  return (
    <Routes>
      <Route element={<FocusShell />}>
        <Route path="/" element={<WelcomePage />} />
        <Route path="/signin" element={<SignInPage />} />
        <Route path="/privacy" element={<LegalPage kind="privacy" />} />
        <Route path="/terms" element={<LegalPage kind="terms" />} />
        <Route
          element={
            <RequireGuardian>
              <Outlet />
            </RequireGuardian>
          }
        >
          <Route path="/onboarding/consent" element={<ConsentPage />} />
          <Route path="/onboarding/child" element={<ChildFormPage mode="onboarding" />} />
          <Route
            path="/ready/:childId"
            element={
              <RequireChild>
                <GetReadyPage />
              </RequireChild>
            }
          />
        </Route>
      </Route>

      <Route
        element={
          <RequireGuardian>
            <RequireChild>
              <ParentShell />
            </RequireChild>
          </RequireGuardian>
        }
      >
        <Route path="/home" element={<HomePage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
        <Route path="/plan" element={<PlanPage />} />
        <Route path="/upgrade" element={<UpgradePage />} />
        <Route path="/plan/checkout" element={<CheckoutPlaceholderPage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/children/new" element={<ChildFormPage mode="new" />} />
        <Route path="/children/:childId/edit" element={<ChildFormPage mode="edit" />} />
      </Route>

      <Route path="/schools" element={<SchoolShell />}>
        <Route index element={<SchoolsPreviewPage />} />
        <Route path="children/:childId" element={<SchoolChildPage />} />
      </Route>

      <Route path="/session/:childId" element={<SessionPage />} />

      <Route path="/children" element={<Redirect to="/home" />} />
      <Route path="/consent" element={<Redirect to="/account" />} />
      <Route path="/schools/preview" element={<Redirect to="/schools" />} />
      <Route path="/schools/preview/children/:childId" element={<Redirect to="/schools/children/:childId" />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
