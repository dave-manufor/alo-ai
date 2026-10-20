import { Link, Route, Routes } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import NotFoundPage from './pages/NotFoundPage';
import SchoolChildPage from './pages/SchoolChildPage';
import SchoolsPreviewPage from './pages/SchoolsPreviewPage';
import SessionPlaceholderPage from './pages/SessionPlaceholderPage';

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
        <Route path="/session" element={<SessionPlaceholderPage />} />
        <Route path="/schools/preview" element={<SchoolsPreviewPage />} />
        <Route path="/schools/preview/children/:childId" element={<SchoolChildPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </div>
  );
}
