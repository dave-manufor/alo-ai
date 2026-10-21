import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { accountStore } from './account/store';
import App from './App';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe('App routing', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
  });

  it('shows the grown-up landing page with the tagline', () => {
    renderAt('/');
    expect(
      screen.getByRole('heading', { name: 'Stories that listen back.' }),
    ).toBeInTheDocument();
    // Accessible names match the visible text (WCAG 2.5.3): NavButton
    // renders one button per action, never a button inside a link.
    expect(screen.getByRole('button', { name: 'Start a reading check' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'For schools (preview)' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'See reports' })).not.toBeInTheDocument();
  });

  it('labels the schools preview and makes no network calls', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderAt('/schools/preview');
    expect(
      screen.getByText('Preview with sample data. Coming soon for schools.'),
    ).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it('gates reports behind sign-in (PRD 12)', () => {
    renderAt('/reports');
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Reading reports' })).not.toBeInTheDocument();
  });

  it('gates the session per child: no consent record, no session', () => {
    renderAt('/session/child_nope');
    expect(screen.getByRole('heading', { name: 'Sign in first' })).toBeInTheDocument();
  });

  it('shows reports to a signed-in guardian', () => {
    accountStore.signIn('google');
    renderAt('/reports');
    expect(screen.getByRole('heading', { name: 'Reading reports' })).toBeInTheDocument();
  });

  it('shows a friendly page for unknown routes', () => {
    renderAt('/no-such-page');
    expect(
      screen.getByRole('heading', { name: 'We could not find that page' }),
    ).toBeInTheDocument();
  });
});
