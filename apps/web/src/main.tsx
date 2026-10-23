import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { registerSW } from 'virtual:pwa-register';
import { accountStore } from './account/store';
import { loadAccountSafely } from './account/syncStatus';
import App from './App';
import { restoreSignIn } from './auth';
import './styles/app.css';
import './styles/shell.css';
import './styles/ui.css';
import './styles/screens.css';
import './styles/preview.css';

registerSW({ immediate: true });

// Finish a sign-in the browser has just come back from, or restore this tab's, before the
// first screen: a guardian who reloads a report must not be sent to sign in again first.
// It never throws, so the app always opens (signed out if the return failed).
restoreSignIn()
  .then(async (user) => {
    if (!user) return;
    accountStore.signInVerified(user);
    // Live build: load this guardian's children and consents from the Account API. A failure
    // must not block the app: the screens say the list could not be loaded and offer a retry.
    await loadAccountSafely();
  })
  .finally(() => {
    createRoot(document.getElementById('root')!).render(
      <StrictMode>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </StrictMode>,
    );
  });
