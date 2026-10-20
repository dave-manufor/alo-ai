import { Link } from 'react-router-dom';
import { Button } from '../design-system/alo';

// Teacher view PREVIEW (PRD 4.7): front-end only, fictional sample data,
// no sign-in, and no network calls to Firestore, the agents or any other
// data service. The full preview (class table, groups, child page,
// scripted assistant) arrives in its own branch; this scaffold page keeps
// the route and the mandatory banner in place from day one.
export default function SchoolsPreviewPage() {
  return (
    <main className="app-main">
      <p className="preview-banner body" role="note">
        Preview with sample data. Coming soon for schools.
      </p>

      <section className="stack">
        <h1 className="title">Alo.ai for schools</h1>
        <p className="body">
          Soon, teachers will see every child&apos;s reading check in one
          place: who has been checked, what to practise next, and groups for
          the week. This preview will use a fictional sample class, so you
          can look around without any real child&apos;s information.
        </p>
        <Link to="/" aria-label="Back to the home page">
          <Button variant="secondary" size="grown">
            Back to home
          </Button>
        </Link>
      </section>
    </main>
  );
}
