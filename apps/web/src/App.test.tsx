import { fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { accountStore } from './account/store';
import { renderApp, signInWithChild } from './test/helpers';

describe('App routing', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
  });

  it('opens on the choice between parent and school', () => {
    renderApp('/');
    expect(screen.getByRole('heading', { name: 'Stories that listen back' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Parent or guardian/ })).toHaveAttribute('href', '/signin');
    expect(screen.getByRole('link', { name: /School or teacher/ })).toHaveAttribute('href', '/schools');
  });

  it('shows the school preview without signing in', () => {
    renderApp('/');
    fireEvent.click(screen.getByRole('link', { name: /School or teacher/ }));
    expect(screen.getByRole('heading', { name: 'P3B reading checks' })).toBeInTheDocument();
    expect(accountStore.getState().guardian).toBeNull();
  });

  it('gates grown-up screens behind sign-in (PRD 12)', () => {
    renderApp('/reports');
    expect(screen.getByLabelText('Email address')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Reading reports' })).not.toBeInTheDocument();
  });

  it('gates the session per child: no consent record, no session', () => {
    renderApp('/session/child_nope');
    // Not signed in: the gate sends the visitor back, and no session screen is shown.
    expect(screen.queryByRole('button', { name: /start/i })).not.toBeInTheDocument();
  });

  it('shows reports to a signed-in guardian with a child', () => {
    signInWithChild();
    renderApp('/reports');
    expect(screen.getByRole('heading', { name: 'Reading reports' })).toBeInTheDocument();
  });

  it('sends a signed-in guardian with no child through onboarding first', () => {
    accountStore.signIn('email_code', 'parent@example.com');
    renderApp('/home');
    expect(screen.getByRole('heading', { name: 'Before your child reads' })).toBeInTheDocument();
  });

  it('sends a signed-in guardian on from the start page to Home', () => {
    signInWithChild('Chidi');
    renderApp('/');
    expect(screen.getByRole('heading', { name: /Good (morning|afternoon|evening)/ })).toBeInTheDocument();
  });

  it('keeps the old addresses working', () => {
    signInWithChild('Chidi');
    renderApp('/children');
    expect(screen.getByRole('heading', { name: 'Chidi' })).toBeInTheDocument();
  });

  it('shows a friendly page for unknown routes', () => {
    renderApp('/no-such-page');
    expect(screen.getByRole('heading', { name: 'We could not find that page' })).toBeInTheDocument();
  });
});
