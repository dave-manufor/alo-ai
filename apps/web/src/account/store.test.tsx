import { beforeEach, describe, expect, it } from 'vitest';
import { CONSENT_VERSION, accountStore } from './store';

const adaeze = {
  firstName: 'Adaeze',
  primaryClass: 3,
  birthYear: 2017,
  attested: true,
  trainingOptIn: false,
};

describe('fixture account store (PRD 12 per-child consent)', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
  });

  it('records per-child consent naming the child, and gates the session on it', () => {
    accountStore.signIn('email_code');
    expect(() => accountStore.addChildWithConsent({ ...adaeze, attested: false })).toThrow(/consent/i);

    const { child, consent } = accountStore.addChildWithConsent(adaeze);
    expect(consent.text_version).toBe(CONSENT_VERSION);
    expect(consent.guardian_id).toBe('guardian_sample_001');
    expect(consent.child_id).toBe(child.child_id);
    expect(consent.verified_email).toBe('guardian@example.com');
    expect(consent.training_opt_in).toBe(false);
    expect(consent.attestation).toMatch(/parent or guardian of Adaeze, aged \d+/);
    expect(accountStore.canStartSession(child.child_id)).toBe(true);
    expect(accountStore.canStartSession('nobody')).toBe(false);
  });

  it('edits a child’s details', () => {
    accountStore.signIn('email_code');
    const { child } = accountStore.addChildWithConsent(adaeze);
    const edited = accountStore.updateChild(child.child_id, { firstName: ' Ada ', primaryClass: 4, birthYear: 2016 });
    expect(edited).toMatchObject({ first_name: 'Ada', primary_class: 4, birth_year: 2016 });
    expect(accountStore.getState().children[0].first_name).toBe('Ada');
    expect(() => accountStore.updateChild('nobody', { firstName: 'X', primaryClass: 1, birthYear: 2019 })).toThrow();
  });

  it('changes the recordings choice without changing anything else on the consent', () => {
    accountStore.signIn('email_code');
    const { child, consent } = accountStore.addChildWithConsent(adaeze);
    accountStore.setTrainingOptIn(child.child_id, true);
    const after = accountStore.consentFor(child.child_id)!;
    expect(after.training_opt_in).toBe(true);
    expect(after.attestation).toBe(consent.attestation);
    expect(after.consent_id).toBe(consent.consent_id);
  });

  it('deletes a child with their consent, so no session can start for them', () => {
    accountStore.signIn('email_code');
    const { child } = accountStore.addChildWithConsent(adaeze);
    accountStore.removeChild(child.child_id);
    expect(accountStore.getState().children).toHaveLength(0);
    expect(accountStore.consentFor(child.child_id)).toBeNull();
    expect(accountStore.canStartSession(child.child_id)).toBe(false);
  });

  it('only holds a plan for the signed-in guardian, and only in the sample build', () => {
    expect(accountStore.hasActiveSubscription()).toBe(false);
    accountStore.activateSampleSubscription(); // nobody signed in: nothing happens
    expect(accountStore.hasActiveSubscription()).toBe(false);
    accountStore.signIn('email_code');
    accountStore.activateSampleSubscription();
    expect(accountStore.hasActiveSubscription()).toBe(true);
    accountStore.signOut();
    expect(accountStore.hasActiveSubscription()).toBe(false);
  });
});
