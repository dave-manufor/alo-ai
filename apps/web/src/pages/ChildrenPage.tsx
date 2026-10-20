import { useState } from 'react';
import { Link } from 'react-router-dom';
import { accountStore, useAccount } from '../account/store';
import { Button } from '../design-system/alo';

// Grown-up mode: child profiles (PRD 4.4). A child has a first name,
// primary class and birth year. Each September the app will ask the
// guardian to confirm the new class; the note shows when class was last
// confirmed. Starting a check needs consent on file (PRD 12).
export default function ChildrenPage() {
  const { guardian, consent, children } = useAccount();
  const [firstName, setFirstName] = useState('');
  const [primaryClass, setPrimaryClass] = useState(3);
  const [birthYear, setBirthYear] = useState(2017);
  const [error, setError] = useState<string | null>(null);

  if (!guardian) {
    return (
      <main className="app-main">
        <section className="card">
          <h1 className="title">Sign in first</h1>
          <p className="body">Your children&apos;s profiles are tied to your sign-in.</p>
          <Link to="/signin">
            <Button variant="primary" size="grown">
              Go to sign in
            </Button>
          </Link>
        </section>
      </main>
    );
  }

  if (!consent) {
    return (
      <main className="app-main">
        <section className="card">
          <h1 className="title">One step before profiles</h1>
          <p className="body">
            We need your consent before you add a child or start a reading
            check.
          </p>
          <Link to="/consent">
            <Button variant="primary" size="grown">
              Give consent
            </Button>
          </Link>
        </section>
      </main>
    );
  }

  function addChild(event: React.FormEvent) {
    event.preventDefault();
    if (!firstName.trim()) {
      setError('Please add your child’s first name.');
      return;
    }
    try {
      accountStore.addChild({ firstName, primaryClass, birthYear });
      setFirstName('');
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'We could not add that child.');
    }
  }

  return (
    <main className="app-main">
      <section className="stack">
        <h1 className="title">Your children</h1>
        <p className="body muted">Signed in as {guardian.email}.</p>
      </section>

      {children.map((child) => (
        <article key={child.id} className="card">
          <h2 className="title">{child.firstName}</h2>
          <p className="body muted">
            Primary {child.primaryClass} · Born {child.birthYear} · Class
            confirmed {child.classConfirmedYear}
          </p>
          <div className="row">
            <Link to="/session">
              <Button variant="primary" size="grown">
                Start a reading check
              </Button>
            </Link>
            <Link to="/reports">
              <Button variant="secondary" size="grown">
                See reports
              </Button>
            </Link>
          </div>
        </article>
      ))}

      <form className="card" onSubmit={addChild}>
        <h2 className="title">Add a child</h2>
        <label className="stack">
          <span className="label">First name</span>
          <input
            className="preview-input"
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            placeholder="First name"
          />
        </label>
        <label className="stack">
          <span className="label">Primary class</span>
          <select
            className="preview-input"
            value={primaryClass}
            onChange={(event) => setPrimaryClass(Number(event.target.value))}
          >
            {[1, 2, 3, 4, 5, 6].map((year) => (
              <option key={year} value={year}>
                Primary {year}
              </option>
            ))}
          </select>
        </label>
        <label className="stack">
          <span className="label">Birth year</span>
          <input
            className="preview-input"
            type="number"
            min={2012}
            max={2022}
            value={birthYear}
            onChange={(event) => setBirthYear(Number(event.target.value))}
          />
        </label>
        {error ? (
          <p className="body" role="alert">
            {error}
          </p>
        ) : null}
        <Button variant="primary" size="grown" type="submit">
          Add child
        </Button>
      </form>
    </main>
  );
}
