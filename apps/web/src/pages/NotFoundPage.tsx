import NavButton from '../design-system/NavButton';

export default function NotFoundPage() {
  return (
    <div className="page">
      <h1 className="display-m">We could not find that page</h1>
      <p className="body">The page may have moved. Let us take you home.</p>
      <NavButton variant="primary" size="grown" to="/">
        Back to home
      </NavButton>
    </div>
  );
}
