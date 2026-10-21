import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { registerSW } from 'virtual:pwa-register';
import { accountStore } from './account/store';
import App from './App';
import { restoreSignIn } from './auth';
import './styles/app.css';
import './styles/preview.css';
import './styles/session.css';

registerSW({ immediate: true });

// Finish a sign-in the browser has just come back from, or restore this tab's, before the
// first screen: a guardian who reloads a report must not be sent to sign in again first.
// It never throws, so the app always opens (signed out if the return failed).
restoreSignIn()
  .then((user) => {
    if (user) accountStore.signInVerified(user);
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
