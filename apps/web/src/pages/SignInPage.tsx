import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { accountStore, useAccount } from '../account/store';
import { Button } from '../design-system/alo';

// Grown-up mode: sign in with Google or an email link (PRD 4.4, 12).
// In this fixture-backed phase both buttons sign in a sample guardian;
// Firebase Authentication replaces them without changing the flow.
export default function SignInPage() {
  const navigate = useNavigate();
  const { guardian } = useAccount();
  const [email, setEmail] = useState('');
  const [emailSent, setEmailSent] = useState(false);

  function afterSignIn() {
    navigate(accountStore.getState().consent ? '/children' : '/consent');
  }

  function signInWithEmail(event: React.FormEvent) {
    event.preventDefault();
    if (!email.includes('@')) return;
    accountStore.signIn('email_link', email);
    setEmailSent(true);
    afterSignIn();
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
            afterSignIn();
          }}
        >
          Continue with Google
        </Button>
        <form className="stack" onSubmit={signInWithEmail}>
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
          {emailSent ? (
            <p className="body" role="status">
              Your sign-in link is on its way to {email}.
            </p>
          ) : null}
        </form>
        <p className="body muted">
          Sample sign-in for this build. Your real sign-in will check your
          email before anything is saved.
        </p>
      </section>
    </main>
  );
}
