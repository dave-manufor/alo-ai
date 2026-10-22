import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { accountStore, useAccount } from '../account/store';
import { auth, authMode, signInFailed } from '../auth';
import { Button } from '../design-system/alo';
import { BackLink, Field, Notice } from '../ui/primitives';

// Grown-up mode (PRD 4.4, 12). The only way in is an email and a one-time code: no password,
// no social sign-in. Two builds of this screen:
//  - the real build (Entra settings present): we ask for the email, then send the guardian
//    to Microsoft Entra External ID with it filled in; Entra emails the code and signs them
//    in only once it is right. We never store an address that has not been verified;
//  - the sample build: the same two steps (email, then a code), with the code shown on
//    screen because no email is sent. It stands in for the return from Entra.
export default function SignInPage() {
  const { guardian, children } = useAccount();
  if (guardian) return <Navigate to={children.length === 0 ? '/onboarding/consent' : '/home'} replace />;
  return (
    <div className="page">
      <BackLink to="/" />
      <div className="page-stack">
        <div className="step">
          <h1 className="display-m">Sign in or create an account</h1>
          <p className="body muted">
            Enter your email and we will send you a code. There is no password to remember.
          </p>
        </div>
        {authMode === 'entra' ? <EntraSignIn /> : <FixtureSignIn />}
        <p className="caption muted">
          By continuing you agree to the <Link to="/terms">terms</Link> and the{' '}
          <Link to="/privacy">privacy notice</Link>.
        </p>
      </div>
    </div>
  );
}

const looksLikeEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());

export function EntraSignIn() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [failedToStart, setFailedToStart] = useState(false);

  async function start(event: React.FormEvent) {
    event.preventDefault();
    if (!looksLikeEmail(email)) {
      setError('Please enter a full email address, like you@example.com.');
      return;
    }
    setError(null);
    setPending(true);
    setFailedToStart(false);
    try {
      await (await auth()).signIn(email.trim());
    } catch {
      // The browser did not leave: the guardian can try again.
      setPending(false);
      setFailedToStart(true);
    }
  }

  return (
    <form className="form" onSubmit={start} noValidate>
      {signInFailed() ? (
        <Notice tone="sky" role="alert">
          We couldn&apos;t finish signing you in. Please try again.
        </Notice>
      ) : null}
      {failedToStart ? (
        <Notice tone="sky" role="alert">
          We couldn&apos;t start sign-in. Check your connection and try again.
        </Notice>
      ) : null}
      <Field label="Email address" error={error}>
        {(props) => (
          <input
            {...props}
            className="ui-input"
            type="email"
            autoComplete="email"
            inputMode="email"
            value={email}
            disabled={pending}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
          />
        )}
      </Field>
      <div className="form__footer">
        <Button variant="primary" size="grown" type="submit" disabled={pending} style={{ width: '100%' }}>
          Send me a code
        </Button>
        {pending ? (
          <p className="caption muted" role="status">
            Taking you to sign in…
          </p>
        ) : (
          <p className="caption muted">
            You will go to a secure page to type the code we email you, then come straight back.
          </p>
        )}
      </div>
    </form>
  );
}

// The sample code. Nothing is emailed in the sample build, so it is shown.
export const SAMPLE_CODE = '123456';

export function FixtureSignIn() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);

  function requestCode(event: React.FormEvent) {
    event.preventDefault();
    if (!looksLikeEmail(email)) {
      setError('Please enter a full email address, like you@example.com.');
      return;
    }
    setError(null);
    setSentTo(email.trim());
  }

  function verify(event: React.FormEvent) {
    event.preventDefault();
    if (!sentTo) return;
    if (code.trim() !== SAMPLE_CODE) {
      setError('That code is not right. Check it and try again.');
      return;
    }
    // Signed in only once the code is right, never on asking for it.
    accountStore.signIn('email_code', sentTo);
    navigate(accountStore.getState().children.length === 0 ? '/onboarding/consent' : '/home');
  }

  if (sentTo === null) {
    return (
      <form className="form" onSubmit={requestCode} noValidate>
        <Field label="Email address" error={error}>
          {(props) => (
            <input
              {...props}
              className="ui-input"
              type="email"
              autoComplete="email"
              inputMode="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
            />
          )}
        </Field>
        <div className="form__footer">
          <Button variant="primary" size="grown" type="submit" style={{ width: '100%' }}>
            Send me a code
          </Button>
          <p className="caption muted">Sample sign-in for this build: no email is sent.</p>
        </div>
      </form>
    );
  }

  return (
    <form className="form" onSubmit={verify} noValidate>
      <Notice tone="night" role="status">
        We sent a 6-digit code to {sentTo}.
      </Notice>
      <Field label="Code" error={error} hint={`Sample build: the code is ${SAMPLE_CODE}.`}>
        {(props) => (
          <input
            {...props}
            className="ui-input ui-input--code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
          />
        )}
      </Field>
      <div className="form__footer">
        <Button variant="primary" size="grown" type="submit" style={{ width: '100%' }}>
          Sign in
        </Button>
        <Button
          variant="ghost"
          size="grown"
          type="button"
          onClick={() => {
            setSentTo(null);
            setCode('');
            setError(null);
          }}
        >
          Use a different email
        </Button>
      </div>
    </form>
  );
}
