import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CONSENT_TEXT, accountStore, useAccount } from '../account/store';
import { Button } from '../design-system/alo';

// Grown-up mode: verified guardian consent (PRD 12). The consent record
// (text, version, timestamp, sign-in method, verified email) must exist
// before a child can be added or the microphone can open.
export default function ConsentPage() {
  const navigate = useNavigate();
  const { guardian, consent } = useAccount();
  const [agreed, setAgreed] = useState(false);
  const [trainingOptIn, setTrainingOptIn] = useState(false);

  if (!guardian) {
    return (
      <main className="app-main">
        <section className="card">
          <h1 className="title">Sign in first</h1>
          <p className="body">We need to know who is giving consent.</p>
          <Link to="/signin">
            <Button variant="primary" size="grown">
              Go to sign in
            </Button>
          </Link>
        </section>
      </main>
    );
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!agreed) return;
    accountStore.recordConsent(trainingOptIn);
    navigate('/children');
  }

  return (
    <main className="app-main">
      <form className="card" onSubmit={submit}>
        <h1 className="title">Before we start</h1>
        <p className="body">{CONSENT_TEXT}</p>
        <p className="body muted">
          Using recordings to help Alo.ai learn is separate, and only if
          you say yes here. It is off unless you turn it on.
        </p>
        <label className="row">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(event) => setAgreed(event.target.checked)}
          />
          <span className="body">I am the parent or guardian, and I agree.</span>
        </label>
        <label className="row">
          <input
            type="checkbox"
            checked={trainingOptIn}
            onChange={(event) => setTrainingOptIn(event.target.checked)}
          />
          <span className="body">You may use recordings to help Alo.ai learn (optional).</span>
        </label>
        {consent ? (
          <p className="body" role="status">
            Consent saved for {consent.verifiedEmail}.
          </p>
        ) : null}
        <Button variant="primary" size="grown" type="submit" disabled={!agreed}>
          Save and continue
        </Button>
      </form>
    </main>
  );
}
