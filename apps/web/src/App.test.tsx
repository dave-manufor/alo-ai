import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import App from './App';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe('App routing skeleton', () => {
  it('shows the grown-up landing page with the tagline', () => {
    renderAt('/');
    expect(
      screen.getByRole('heading', { name: 'Stories that listen back.' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Try the reading check' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See the schools preview' })).toBeInTheDocument();
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

  it('opens the kid session with the call and response and no score or timer', () => {
    const { container } = renderAt('/session');
    expect(screen.getByText('Àlọ́ o!')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ààlọ̀!' })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\d+\s?%|score|timer/i);
  });

  it('shows a friendly page for unknown routes', () => {
    renderAt('/no-such-page');
    expect(
      screen.getByRole('heading', { name: 'We could not find that page' }),
    ).toBeInTheDocument();
  });
});
