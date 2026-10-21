import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import ChildrenPage from '../pages/ChildrenPage';
import ConsentPage from '../pages/ConsentPage';
import SignInPage from '../pages/SignInPage';
import { CONSENT_VERSION, accountStore } from './store';

describe('fixture account store (PRD 12 per-child consent)', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
  });

  it('records per-child consent naming the child, and gates the session on it', () => {
    accountStore.signIn('google');
    expect(() =>
      accountStore.addChildWithConsent({
        firstName: 'Adaeze',
        primaryClass: 3,
        birthYear: 2017,
        attested: false,
        trainingOptIn: false,
      }),
    ).toThrow(/consent/i);

    const { child, consent } = accountStore.addChildWithConsent({
      firstName: 'Adaeze',
      primaryClass: 3,
      birthYear: 2017,
      attested: true,
      trainingOptIn: false,
    });
    expect(consent.text_version).toBe(CONSENT_VERSION);
    expect(consent.guardian_id).toBe('guardian_sample_001');
    expect(consent.child_id).toBe(child.child_id);
    expect(consent.verified_email).toBe('guardian@example.com');
    expect(consent.training_opt_in).toBe(false);
    expect(consent.attestation).toMatch(/parent or guardian of Adaeze, aged \d+/);
    expect(accountStore.canStartSession(child.child_id)).toBe(true);
    expect(accountStore.canStartSession('nobody')).toBe(false);
  });

  it('walks sign-in to children and adds a child with its consent in the UI', () => {
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
    expect(screen.getByRole('heading', { name: 'Your children' })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('First name'), {
      target: { value: 'Adaeze' },
    });
    fireEvent.click(screen.getByLabelText(/parent or guardian of Adaeze, aged/));
    fireEvent.click(screen.getByRole('button', { name: 'Add child' }));
    expect(screen.getByRole('heading', { name: 'Adaeze' })).toBeInTheDocument();
    expect(screen.getByText(/Consent on file/)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Start a reading check' }),
    ).toBeInTheDocument();
  });

  it('does not sign in on an email link until the link is clicked', () => {
    render(
      <MemoryRouter initialEntries={['/signin']}>
        <Routes>
          <Route path="/signin" element={<SignInPage />} />
          <Route path="/children" element={<ChildrenPage />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText(/Email address/), {
      target: { value: 'parent@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Email me a sign-in link' }));
    expect(screen.getByText(/Check your email/)).toBeInTheDocument();
    expect(accountStore.getState().guardian).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'I clicked the link' }));
    expect(accountStore.getState().guardian?.email).toBe('parent@example.com');
    expect(screen.getByRole('heading', { name: 'Your children' })).toBeInTheDocument();
  });

  it('lists per-child consent records on the consent page', () => {
    accountStore.signIn('google');
    accountStore.addChildWithConsent({
      firstName: 'Adaeze',
      primaryClass: 3,
      birthYear: 2017,
      attested: true,
      trainingOptIn: true,
    });
    render(
      <MemoryRouter>
        <ConsentPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Consent, in plain words/)).toBeInTheDocument();
    expect(screen.getByText(/recordings to help Alo.ai learn: yes/)).toBeInTheDocument();
  });
});
