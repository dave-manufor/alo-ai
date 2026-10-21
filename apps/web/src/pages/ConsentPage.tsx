import { accountStore, useAccount } from '../account/store';
import NavButton from '../design-system/NavButton';

// Grown-up mode: what consent means, and the per-child records on file
// (PRD 12). Consent itself is given per child when the child is added —
// the attestation names that child and their age — so this page explains
// it and shows the records; it never collects a blanket consent.
export default function ConsentPage() {
  const { guardian, children, consentsByChildId } = useAccount();

  if (!guardian) {
    return (
      <main className="app-main">
        <section className="card">
          <h1 className="title">Sign in first</h1>
          <p className="body">We need to know who is giving consent.</p>
          <NavButton variant="primary" size="grown" to="/signin">
            Go to sign in
          </NavButton>
        </section>
      </main>
    );
  }

  return (
    <main className="app-main">
      <section className="card">
        <h1 className="title">Consent, in plain words</h1>
        <p className="body">
          For each child you add, we ask you to agree that Alo.ai can record
          them reading aloud, use the recording to make their reading
          report, and keep the audio for up to 90 days. Alo.ai is a
          screening tool that helps you practise reading.
        </p>
        <p className="body">
          Letting recordings help Alo.ai learn is a separate choice for each
          child, and it is off unless you turn it on.
        </p>
        <p className="body muted">
          No reading check can start for a child until their consent is
          saved here.
        </p>
      </section>

      <section className="stack" aria-label="Consent records">
        <h2 className="title">Your consent records</h2>
        {children.length === 0 ? (
          <p className="body">No children added yet, so no consent records yet.</p>
        ) : (
          children.map((child) => {
            const consent = consentsByChildId[child.child_id];
            return (
              <article key={child.child_id} className="card">
                <h3 className="title">{child.first_name}</h3>
                {consent && accountStore.consentFor(child.child_id) ? (
                  <p className="body muted">
                    Consent saved {new Date(consent.timestamp).toLocaleDateString('en-GB')} ·
                    agreed as {consent.verified_email} · recordings to help
                    Alo.ai learn: {consent.training_opt_in ? 'yes' : 'no'}
                  </p>
                ) : (
                  <p className="body">No consent on file for this child yet.</p>
                )}
              </article>
            );
          })
        )}
        <NavButton variant="secondary" size="grown" to="/children">
          Back to your children
        </NavButton>
      </section>
    </main>
  );
}
