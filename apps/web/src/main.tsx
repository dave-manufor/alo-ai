import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { registerSW } from 'virtual:pwa-register';
import { syncAccount } from './account/actions';
import { accountStore } from './account/store';
import App from './App';
import { restoreSignIn } from './auth';
import './styles/app.css';
import './styles/preview.css';

registerSW({ immediate: true });

// Finish a sign-in the browser has just come back from, or restore this tab's, before the
// first screen: a guardian who reloads a report must not be sent to sign in again first.
// It never throws, so the app always opens (signed out if the return failed).
restoreSignIn()
  .then(async (user) => {
    if (!user) return;
    accountStore.signInVerified(user);
    // Live build: load this guardian's children and consents from the Account API. A
    // failure leaves the list empty (the guardian can reload); it must not block the app.
    try {
      await syncAccount();
    } catch {
      // Intentionally ignored: the screens fall back to an empty list.
    }
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
