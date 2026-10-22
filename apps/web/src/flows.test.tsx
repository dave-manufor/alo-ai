import { fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { accountStore } from './account/store';
import { SAMPLE_CODE } from './pages/SignInPage';
import { consentDraft } from './onboarding/draft';
import { renderApp, signInWithChild } from './test/helpers';

// The parent journey, screen to screen, in the sample build (wireframes 1-5 and 19-22).
describe('the parent journey', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
    consentDraft.clear();
  });

  it('goes from the first screen to a child’s Home and the start of a check', () => {
    renderApp('/');
    fireEvent.click(screen.getByRole('link', { name: /Parent or guardian/ }));

    // Sign in with an email and a code; nobody is signed in until the code is right.
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'parent@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send me a code' }));
    expect(accountStore.getState().guardian).toBeNull();
    fireEvent.change(screen.getByLabelText('Code'), { target: { value: '000000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByRole('alert')).toHaveTextContent('not right');
    fireEvent.change(screen.getByLabelText('Code'), { target: { value: SAMPLE_CODE } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(accountStore.getState().guardian?.email).toBe('parent@example.com');
    expect(accountStore.getState().guardian?.sign_in_method).toBe('email_code');

    // Consent comes first; Continue waits for the parent-or-guardian tick.
    expect(screen.getByRole('heading', { name: 'Before your child reads' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/I am the parent or guardian of this child/));
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));

    // Add the child. The attestation names them, and the consent is written with them.
    expect(screen.getByRole('heading', { name: 'Add your child' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'Chidi' } });
    expect(screen.getByText(/parent or guardian of Chidi, aged \d+/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'P3' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save child' }));

    // Home, then the Get ready step.
    return screen.findByRole('heading', { name: 'Chidi' }).then(() => {
      expect(accountStore.getState().children).toHaveLength(1);
      expect(accountStore.canStartSession(accountStore.getState().children[0].child_id)).toBe(true);
      fireEvent.click(screen.getByRole('button', { name: 'Start a reading check' }));
      expect(screen.getByRole('heading', { name: 'Get ready' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Hand the phone to Chidi' })).toBeEnabled();
    });
  });

  it('does not let onboarding skip the consent tick', () => {
    accountStore.signIn('email_code', 'parent@example.com');
    renderApp('/onboarding/child');
    expect(screen.getByRole('heading', { name: 'Before your child reads' })).toBeInTheDocument();
  });

  it('navigates between the four places with the tab bar', () => {
    signInWithChild('Chidi');
    renderApp('/home');
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page');
    fireEvent.click(within(nav).getByRole('link', { name: 'Reports' }));
    expect(screen.getByRole('heading', { name: 'Reading reports' })).toBeInTheDocument();
    fireEvent.click(within(nav).getByRole('link', { name: 'Plan' }));
    expect(screen.getByRole('heading', { name: "Chidi's plan" })).toBeInTheDocument();
    fireEvent.click(within(nav).getByRole('link', { name: 'Account' }));
    expect(screen.getByRole('heading', { name: 'Account' })).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: 'Account' })).toHaveAttribute('aria-current', 'page');
  });

  it('opens the report from Home, then the upgrade, and sees the plan once it is on', () => {
    signInWithChild('Chidi');
    renderApp('/home');
    fireEvent.click(screen.getByRole('link', { name: 'See the last report' }));
    expect(screen.getByRole('heading', { name: "Chidi's report" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /See the plan/ }));
    expect(screen.getByRole('heading', { name: "Get Chidi's weekly plan" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sample build: switch the plan on' }));
    expect(screen.getByRole('heading', { name: "Chidi's plan" })).toBeInTheDocument();
    expect(screen.getByText('Try at home')).toBeInTheDocument();
  });

  it('lets the parent turn recordings on and off from the account', () => {
    signInWithChild('Chidi');
    renderApp('/account');
    const toggle = screen.getByRole('switch', { name: /Use recordings to improve Alo.ai/ });
    expect(toggle).not.toBeChecked();
    fireEvent.click(toggle);
    expect(screen.getByRole('switch', { name: /Use recordings/ })).toBeChecked();
    const child = accountStore.getState().children[0];
    expect(accountStore.consentFor(child.child_id)?.training_opt_in).toBe(true);
  });

  it('asks before deleting a child’s data, and returns to onboarding after', () => {
    signInWithChild('Chidi');
    renderApp('/account');
    fireEvent.click(screen.getByRole('button', { name: "Delete Chidi's data" }));
    expect(accountStore.getState().children).toHaveLength(1); // not yet
    fireEvent.click(screen.getByRole('button', { name: 'Keep it' }));
    expect(accountStore.getState().children).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: "Delete Chidi's data" }));
    fireEvent.click(screen.getByRole('button', { name: "Yes, delete Chidi's data" }));
    expect(accountStore.getState().children).toHaveLength(0);
    expect(screen.getByRole('heading', { name: 'Before your child reads' })).toBeInTheDocument();
  });

  it('edits a child from the account', () => {
    signInWithChild('Chidi');
    renderApp('/account');
    fireEvent.click(screen.getByRole('link', { name: 'Edit Chidi' }));
    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'Chidiebere' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(screen.getByText('Chidiebere')).toBeInTheDocument();
  });

  it('asks a second child’s consent again, because consent is per child', () => {
    signInWithChild('Chidi');
    renderApp('/children/new');
    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'Ngozi' } });
    expect(screen.getByRole('button', { name: 'Save child' })).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/I am the parent or guardian of this child/));
    expect(screen.getByRole('button', { name: 'Save child' })).toBeEnabled();
  });

  it('signs out from the account and returns to the first screen', () => {
    signInWithChild('Chidi');
    renderApp('/account');
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(accountStore.getState().guardian).toBeNull();
    return screen.findByRole('heading', { name: 'Stories that listen back' });
  });

  it('uses a child switcher once there are two children', () => {
    signInWithChild('Chidi');
    accountStore.addChildWithConsent({
      firstName: 'Ngozi',
      primaryClass: 2,
      birthYear: 2019,
      attested: true,
      trainingOptIn: false,
    });
    renderApp('/home');
    fireEvent.change(screen.getByRole('combobox', { name: 'Child' }), {
      target: { value: accountStore.getState().children[1].child_id },
    });
    expect(screen.getByRole('heading', { name: 'Ngozi' })).toBeInTheDocument();
  });
});
