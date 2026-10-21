import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { accountStore, useAccount } from '../account/store';
import { Button } from '../design-system/alo';

// Grown-up mode: sign in with Google or an email link (PRD 4.4, 12).
// The email-link flow models Firebase honestly: asking for a link does
// NOT sign anyone in. The guardian is signed in only when they come back
// through the link — here, the "I clicked the link" step stands in for
// that return — so an unverified typed address is never stored as a
// verified email.
export default function SignInPage() {
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
