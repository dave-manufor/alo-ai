import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { accountStore, useAccount } from '../account/store';
import { auth, authMode, signInFailed } from '../auth';
import { Button } from '../design-system/alo';
import NavButton from '../design-system/NavButton';

// Grown-up mode (PRD 4.4, 12). Two builds of this screen:
//  - the sample build (no Entra settings): the fixture sign-in the MVP screens run on;
//  - the real build: Microsoft Entra External ID. "Continue with Google" and "Continue with
//    email" both go to Entra's hosted page, which verifies the guardian (Google's account, or
//    a one-time code emailed to them) before anyone is signed in. We never store an address
//    that has not been verified.
export default function SignInPage() {
  return authMode === 'entra' ? <EntraSignIn /> : <FixtureSignIn />;
}

export function EntraSignIn() {
  const { guardian } = useAccount();
  const [pending, setPending] = useState(false);
  const [failedToStart, setFailedToStart] = useState(false);

  async function start(method: 'google' | 'email') {
    setPending(true);
    setFailedToStart(false);
    try {
      await (await auth()).signIn(method);
    } catch {
      // The browser did not leave: the guardian can try again.
      setPending(false);
      setFailedToStart(true);
    }
  }

  async function leave() {
    accountStore.signOut();
    try {
      await (await auth()).signOut();
    } catch {
      // Already signed out on this phone; nothing more to end.
    }
  }

  return (
    <main className="app-main">
      <section className="card">
        <h1 className="title">Welcome to Alo.ai</h1>
        <p className="body">
          Sign in so we can keep your child&apos;s reports safe and only show them to you.
        </p>
        {guardian ? (
          <>
            <p className="body" role="status">
              Signed in as {guardian.email}.
            </p>
            <NavButton variant="primary" size="grown" to="/children">
              Go to your children
            </NavButton>
            <Button variant="secondary" size="grown" onClick={leave}>
              Sign out
            </Button>
          </>
        ) : (
          <>
            {signInFailed() ? (
              <p className="body" role="alert">
                We couldn&apos;t finish signing you in. Please try again.
              </p>
            ) : null}
            {failedToStart ? (
              <p className="body" role="alert">
                We couldn&apos;t start sign-in. Check your connection and try again.
              </p>
            ) : null}
            {pending ? (
              <p className="body" role="status">
                Taking you to sign in…
              </p>
            ) : null}
            <Button variant="primary" size="grown" disabled={pending} onClick={() => start('google')}>
              Continue with Google
            </Button>
            <Button variant="secondary" size="grown" disabled={pending} onClick={() => start('email')}>
              Continue with email
            </Button>
            <p className="body muted">
              With email, we send you a code to type in. There is no password to remember.
            </p>
          </>
        )}
      </section>
    </main>
  );
}

// The sample sign-in. The email-link flow models a real one honestly: asking for a link does
// NOT sign anyone in. The guardian is signed in only when they come back through the link
// (here, the "I clicked the link" step stands in for that return), so an unverified typed
// address is never stored as a verified email.
export function FixtureSignIn() {
  const navigate = useNavigate();
  const { guardian } = useAccount();
  const [email, setEmail] = useState('');
  const [linkSentTo, setLinkSentTo] = useState<string | null>(null);

  function requestLink(event: React.FormEvent) {
    event.preventDefault();
    if (!email.includes('@')) return;
    setLinkSentTo(email);
  }

  function completeEmailSignIn() {
    if (!linkSentTo) return;
    accountStore.signIn('email_link', linkSentTo);
    navigate('/children');
  }

  return (
    <main className="app-main">
      <section className="card">
        <h1 className="title">Welcome to Alo.ai</h1>
        <p className="body">
          Sign in so we can keep your child&apos;s reports safe and only
          show them to you.
        </p>
        {guardian ? (
          <p className="body" role="status">
            Signed in as {guardian.email}.
          </p>
        ) : null}
        <Button
          variant="primary"
          size="grown"
          onClick={() => {
            accountStore.signIn('google');
            navigate('/children');
          }}
        >
          Continue with Google
        </Button>

        {linkSentTo === null ? (
          <form className="stack" onSubmit={requestLink}>
            <label className="stack">
              <span className="label">Email address</span>
              <input
                className="preview-input"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </label>
            <Button variant="secondary" size="grown" type="submit">
              Email me a sign-in link
            </Button>
          </form>
        ) : (
          <div className="stack" role="status">
            <p className="body">
              Check your email: we sent a sign-in link to {linkSentTo}. Open
              it on this phone to finish signing in.
            </p>
            <Button variant="primary" size="grown" onClick={completeEmailSignIn}>
              I clicked the link
            </Button>
          </div>
        )}
        <p className="body muted">
          Sample sign-in for this build. Your real sign-in checks your email
          before anything is saved.
        </p>
      </section>
    </main>
  );
}
