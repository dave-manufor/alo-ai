import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { accountStore } from '../account/store';
import { auth, signInFailed } from '../auth';
import SignInPage, { EntraSignIn } from './SignInPage';

// The real build's sign-in (Entra External ID, email and a one-time code). The auth module is
// replaced: nothing here reaches Entra.
vi.mock('../auth', () => ({
  authMode: 'entra',
  auth: vi.fn(),
  signInFailed: vi.fn(() => false),
}));

const client = { signIn: vi.fn(), signOut: vi.fn(), restore: vi.fn(), getAccessToken: vi.fn() };

function show() {
  return render(
    <MemoryRouter initialEntries={['/signin']}>
      <Routes>
        <Route path="/signin" element={<EntraSignIn />} />
      </Routes>
    </MemoryRouter>,
  );
}

function typeEmail(value: string) {
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value } });
}

describe('sign-in with Entra External ID (PRD 4.4, 12)', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
    client.signIn.mockReset().mockResolvedValue(undefined);
    client.signOut.mockReset().mockResolvedValue(undefined);
    vi.mocked(auth).mockResolvedValue(client);
    vi.mocked(signInFailed).mockReturnValue(false);
  });

  it('asks for an email and offers a code, with no Google and no password', () => {
    show();
    expect(screen.getByLabelText('Email address')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send me a code' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: /google/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/sample sign-in/i)).not.toBeInTheDocument();
  });

  it('takes the guardian to Entra with their email and holds the form meanwhile', async () => {
    client.signIn.mockReturnValue(new Promise(() => undefined)); // the browser is leaving
    show();
    typeEmail('guardian@example.com');
    fireEvent.click(screen.getByRole('button', { name: 'Send me a code' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Taking you to sign in');
    expect(client.signIn).toHaveBeenCalledWith('guardian@example.com');
    expect(screen.getByRole('button', { name: 'Send me a code' })).toBeDisabled();
  });

  it('does not go to Entra for something that is not an email address', () => {
    show();
    typeEmail('guardian');
    fireEvent.click(screen.getByRole('button', { name: 'Send me a code' }));
    expect(screen.getByRole('alert')).toHaveTextContent('full email address');
    expect(client.signIn).not.toHaveBeenCalled();
  });

  it('does not sign anyone in itself: only the verified return does', async () => {
    show();
    typeEmail('guardian@example.com');
    fireEvent.click(screen.getByRole('button', { name: 'Send me a code' }));
    await waitFor(() => expect(client.signIn).toHaveBeenCalled());
    expect(accountStore.getState().guardian).toBeNull();
  });

  it('says so, and lets the guardian try again, when sign-in cannot start', async () => {
    client.signIn.mockRejectedValue(new Error('offline'));
    show();
    typeEmail('guardian@example.com');
    fireEvent.click(screen.getByRole('button', { name: 'Send me a code' }));
    expect(await screen.findByRole('alert')).toHaveTextContent("We couldn't start sign-in");
    expect(screen.getByRole('button', { name: 'Send me a code' })).toBeEnabled();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('says so when the return from sign-in did not complete', () => {
    vi.mocked(signInFailed).mockReturnValue(true);
    show();
    expect(screen.getByRole('alert')).toHaveTextContent("We couldn't finish signing you in");
  });

  it('sends a guardian who has just come back signed in on to onboarding, or to Home', () => {
    accountStore.signInVerified({ id: 'oid-1', email: 'guardian@example.com', method: 'email_code' });
    render(
      <MemoryRouter initialEntries={['/signin']}>
        <Routes>
          <Route path="/signin" element={<SignInPage />} />
          <Route path="/onboarding/consent" element={<h1>Before your child reads</h1>} />
          <Route path="/home" element={<h1>Home</h1>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Before your child reads' })).toBeInTheDocument();
  });
});

describe('the account in the real build (PRD 12: nothing of a child stays on a shared phone)', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
  });

  it('is kept in this tab, never in the browser', () => {
    accountStore.signInVerified({ id: 'oid-1', email: 'guardian@example.com', method: 'email_code' });
    accountStore.addChildWithConsent({
      firstName: 'Adaeze',
      primaryClass: 3,
      birthYear: 2017,
      attested: true,
      trainingOptIn: false,
    });
    expect(localStorage.length).toBe(0);
    expect(accountStore.getState().children).toHaveLength(1);
  });

  it('records the verified identity as the guardian, with its stable id and method', () => {
    const { consent } = (() => {
      accountStore.signInVerified({ id: 'oid-7', email: 'guardian@example.com', method: 'email_code' });
      return accountStore.addChildWithConsent({
        firstName: 'Adaeze',
        primaryClass: 3,
        birthYear: 2017,
        attested: true,
        trainingOptIn: false,
      });
    })();
    expect(consent.guardian_id).toBe('oid-7');
    expect(consent.sign_in_method).toBe('email_code');
    expect(consent.verified_email).toBe('guardian@example.com');
  });

  it('removes what an earlier sample build left on this origin', () => {
    localStorage.setItem('alo.fixture.account.v2', '{"children":[{"first_name":"Sample"}]}');
    accountStore.setPersistence(false);
    expect(localStorage.getItem('alo.fixture.account.v2')).toBeNull();
  });
});
