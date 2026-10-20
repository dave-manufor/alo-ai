import { Link } from 'react-router-dom';
import { Button } from '../design-system/alo';

export default function NotFoundPage() {
  return (
    <main className="app-main">
      <section className="stack">
        <h1 className="title">We could not find that page</h1>
        <p className="body">The page may have moved. Let us take you home.</p>
        <Link to="/" aria-label="Back to the home page">
          <Button variant="primary" size="grown">
            Back to home
          </Button>
        </Link>
      </section>
    </main>
  );
}
