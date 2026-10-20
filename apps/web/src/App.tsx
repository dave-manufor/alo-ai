import { Link, Route, Routes } from 'react-router-dom';
import CheckoutPlaceholderPage from './pages/CheckoutPlaceholderPage';
import ChildrenPage from './pages/ChildrenPage';
import ConsentPage from './pages/ConsentPage';
import LandingPage from './pages/LandingPage';
import NotFoundPage from './pages/NotFoundPage';
import SchoolChildPage from './pages/SchoolChildPage';
import SchoolsPreviewPage from './pages/SchoolsPreviewPage';
import ReportDetailPage from './pages/ReportDetailPage';
import ReportsPage from './pages/ReportsPage';
import SessionPlaceholderPage from './pages/SessionPlaceholderPage';
import SignInPage from './pages/SignInPage';

// Routing skeleton. Kid-mode and grown-up-mode screens are separate routes
// and are never mixed on one screen (design system README).
export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" aria-label="Alo.ai home">
          <img
            className="app-wordmark"
            src="/design-system/assets/Logos/wordmark-on-light.svg"
            alt="alo.ai"
          />
        </Link>
      </header>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/signin" element={<SignInPage />} />
        <Route path="/consent" element={<ConsentPage />} />
        <Route path="/children" element={<ChildrenPage />} />
        <Route path="/session" element={<SessionPlaceholderPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
        <Route path="/plan/checkout" element={<CheckoutPlaceholderPage />} />
        <Route path="/schools/preview" element={<SchoolsPreviewPage />} />
        <Route path="/schools/preview/children/:childId" element={<SchoolChildPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </div>
  );
}
