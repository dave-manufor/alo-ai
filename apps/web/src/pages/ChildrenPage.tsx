import { useState } from 'react';
import {
  accountStore,
  ageFromBirthYear,
  attestationFor,
  useAccount,
} from '../account/store';
import { Button } from '../design-system/alo';
import NavButton from '../design-system/NavButton';

// Grown-up mode: child profiles (PRD 4.4, 12). Adding a child includes
// that child's consent: the attestation names the child and their age,
// and the record is stored per child. Without it, nothing is saved and
// no reading check can start for that child. Each September the app will
// ask the guardian to confirm the new class.
export default function ChildrenPage() {
  const { guardian, children, consentsByChildId } = useAccount();
  const [firstName, setFirstName] = useState('');
  const [primaryClass, setPrimaryClass] = useState(3);
  const [birthYear, setBirthYear] = useState(2017);
  const [attested, setAttested] = useState(false);
  const [trainingOptIn, setTrainingOptIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!guardian) {
    return (
      <main className="app-main">
        <section className="card">
          <h1 className="title">Sign in first</h1>
          <p className="body">Your children&apos;s profiles are tied to your sign-in.</p>
          <NavButton variant="primary" size="grown" to="/signin">
            Go to sign in
          </NavButton>
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
      accountStore.addChildWithConsent({
        firstName,
        primaryClass,
        birthYear,
        attested,
        trainingOptIn,
      });
      setFirstName('');
      setAttested(false);
      setTrainingOptIn(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'We could not add that child.');
    }
  }

  const trimmedName = firstName.trim();

  return (
    <main className="app-main">
      <section className="stack">
        <h1 className="title">Your children</h1>
        <p className="body muted">Signed in as {guardian.email}.</p>
      </section>

      {children.map((child) => (
        <article key={child.child_id} className="card">
          <h2 className="title">{child.first_name}</h2>
          <p className="body muted">
            Primary {child.primary_class} · Born {child.birth_year} · Class
            confirmed {child.class_confirmed_year}
            {consentsByChildId[child.child_id] ? ' · Consent on file' : ''}
          </p>
          <div className="row">
            <NavButton variant="primary" size="grown" to={`/session/${child.child_id}`}>
              Start a reading check
            </NavButton>
            <NavButton variant="secondary" size="grown" to="/reports">
              See reports
            </NavButton>
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

        <label className="row">
          <input
            type="checkbox"
            checked={attested}
            onChange={(event) => setAttested(event.target.checked)}
          />
          <span className="body">
            {trimmedName
              ? attestationFor(trimmedName, ageFromBirthYear(birthYear))
              : 'I am the parent or guardian of this child. I agree that Alo.ai can record them reading aloud, use the recording to make their reading report, and keep the audio for up to 90 days.'}
          </span>
        </label>
        <label className="row">
          <input
            type="checkbox"
            checked={trainingOptIn}
            onChange={(event) => setTrainingOptIn(event.target.checked)}
          />
          <span className="body">
            You may use recordings to help Alo.ai learn (optional, off unless you say yes).
          </span>
        </label>

        {error ? (
          <p className="body" role="alert">
            {error}
          </p>
        ) : null}
        <Button variant="primary" size="grown" type="submit" disabled={!attested || !trimmedName}>
          Add child
        </Button>
      </form>
    </main>
  );
}
