import { Link } from 'react-router-dom';
import { Button } from '../design-system/alo';

// Grown-up mode. The landing page for parents (PRD 4.4); sign-in, consent
// and child profiles arrive in follow-up branches.
export default function LandingPage() {
  return (
    <main className="app-main">
      <section className="stack">
        <h1 className="display-m">Stories that listen back.</h1>
        <p className="body">
          Alo.ai chats with your child, writes a story about what they love,
          and listens as they read it aloud. You get a plain report and one
          thing to try each week.
        </p>
        <div className="row">
          <Link to="/session" aria-label="Try the reading check">
            <Button variant="primary" size="grown">
              Start a reading check
            </Button>
          </Link>
          <Link to="/schools/preview" aria-label="See the schools preview">
            <Button variant="secondary" size="grown">
              For schools (preview)
            </Button>
          </Link>
        </div>
      </section>

      <section className="card" aria-labelledby="how-it-works">
        <h2 id="how-it-works" className="title">
          How it works
        </h2>
        <p className="body">
          Your child chats about their interests, reads a short story aloud,
          tells it back and answers a few questions. It takes about three
          minutes, on an ordinary phone.
        </p>
        <p className="body muted">
          Alo.ai is a screening tool. It helps you see what to practise next;
          it is not a test with pass or fail.
        </p>
      </section>
    </main>
  );
}
