import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import ChildrenPage from '../pages/ChildrenPage';
import ConsentPage from '../pages/ConsentPage';
import SignInPage from '../pages/SignInPage';
import { CONSENT_VERSION, accountStore } from './store';

describe('fixture account store (PRD 12 consent gate)', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
  });

  it('refuses to add a child before consent, then allows it after', () => {
    accountStore.signIn('google');
    expect(() =>
      accountStore.addChild({ firstName: 'Adaeze', primaryClass: 3, birthYear: 2017 }),
    ).toThrow(/consent/i);

    const consent = accountStore.recordConsent(false);
    expect(consent.textVersion).toBe(CONSENT_VERSION);
    expect(consent.verifiedEmail).toBe('guardian@example.com');
    expect(consent.trainingOptIn).toBe(false);

    const child = accountStore.addChild({
      firstName: 'Adaeze',
      primaryClass: 3,
      birthYear: 2017,
    });
    expect(accountStore.canStartSession(child.id)).toBe(true);
    expect(accountStore.canStartSession('nobody')).toBe(false);
  });

  it('walks sign-in to consent to children in the UI', () => {
    render(
      <MemoryRouter initialEntries={['/signin']}>
        <Routes>
          <Route path="/signin" element={<SignInPage />} />
          <Route path="/consent" element={<ConsentPage />} />
          <Route path="/children" element={<ChildrenPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(screen.getByRole('heading', { name: 'Before we start' })).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/I am the parent or guardian, and I agree/));
    fireEvent.click(screen.getByRole('button', { name: 'Save and continue' }));
    expect(screen.getByRole('heading', { name: 'Your children' })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('First name'), {
      target: { value: 'Adaeze' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add child' }));
    expect(screen.getByRole('heading', { name: 'Adaeze' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /start a reading check/i })).toBeInTheDocument();
  });

  it('blocks the children page without consent', () => {
    accountStore.signIn('email_link', 'parent@example.com');
    render(
      <MemoryRouter>
        <ChildrenPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole('heading', { name: 'One step before profiles' }),
    ).toBeInTheDocument();
  });
});
