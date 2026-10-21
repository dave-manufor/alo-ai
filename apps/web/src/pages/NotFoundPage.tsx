import NavButton from '../design-system/NavButton';

export default function NotFoundPage() {
  return (
    <main className="app-main">
      <section className="stack">
        <h1 className="title">We could not find that page</h1>
        <p className="body">The page may have moved. Let us take you home.</p>
        <NavButton variant="primary" size="grown" to="/">
          Back to home
        </NavButton>
      </section>
    </main>
  );
}
