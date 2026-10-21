import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { accountStore } from '../account/store';
import { auth, signInFailed } from '../auth';
import { EntraSignIn } from './SignInPage';

// The real build's sign-in screen (Entra External ID). The auth module is replaced: nothing
// here reaches Entra.
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
        <Route path="/children" element={<h1>Your children</h1>} />
      </Routes>
    </MemoryRouter>,
  );
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

  it('offers Google and an emailed code, and says what the email does', () => {
    show();
    expect(screen.getByRole('heading', { name: 'Welcome to Alo.ai' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Continue with email' })).toBeEnabled();
    expect(screen.getByText(/we send you a code to type in/i)).toBeInTheDocument();
    // None of the sample build's controls or its sample-sign-in note.
    expect(screen.queryByPlaceholderText('you@example.com')).not.toBeInTheDocument();
    expect(screen.queryByText(/sample sign-in/i)).not.toBeInTheDocument();
  });

  it.each([
    ['Continue with Google', 'google'],
    ['Continue with email', 'email'],
  ])('%s takes the guardian to Entra and holds the buttons meanwhile', async (name, method) => {
    client.signIn.mockReturnValue(new Promise(() => undefined)); // the browser is leaving
    show();
    fireEvent.click(screen.getByRole('button', { name }));
    expect(await screen.findByRole('status')).toHaveTextContent('Taking you to sign in');
    expect(client.signIn).toHaveBeenCalledWith(method);
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Continue with email' })).toBeDisabled();
  });

  it('does not sign anyone in itself: only the verified return does', async () => {
    show();
    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));
    await waitFor(() => expect(client.signIn).toHaveBeenCalled());
    expect(accountStore.getState().guardian).toBeNull();
  });

  it('says so, and lets the guardian try again, when sign-in cannot start', async () => {
    client.signIn.mockRejectedValue(new Error('offline'));
    show();
    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(await screen.findByRole('alert')).toHaveTextContent("We couldn't start sign-in");
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeEnabled();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('says so when the return from sign-in did not complete', () => {
    vi.mocked(signInFailed).mockReturnValue(true);
    show();
    expect(screen.getByRole('alert')).toHaveTextContent("We couldn't finish signing you in");
  });

  it('shows who is signed in and goes on to the children', () => {
    accountStore.signInVerified({ id: 'oid-1', email: 'guardian@example.com', method: 'email_code' });
    show();
    expect(screen.getByRole('status')).toHaveTextContent('Signed in as guardian@example.com.');
    expect(screen.queryByRole('button', { name: 'Continue with Google' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Go to your children' }));
    expect(screen.getByRole('heading', { name: 'Your children' })).toBeInTheDocument();
  });

  it('signs out of this phone and of Entra', async () => {
    accountStore.signInVerified({ id: 'oid-1', email: 'guardian@example.com', method: 'google' });
    show();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    await waitFor(() => expect(client.signOut).toHaveBeenCalled());
    expect(accountStore.getState().guardian).toBeNull();
  });

  it('is signed out here even if Entra cannot be reached to end the session', async () => {
    client.signOut.mockRejectedValue(new Error('offline'));
    accountStore.signInVerified({ id: 'oid-1', email: 'guardian@example.com', method: 'google' });
    show();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    await waitFor(() => expect(client.signOut).toHaveBeenCalled());
    expect(accountStore.getState().guardian).toBeNull();
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
