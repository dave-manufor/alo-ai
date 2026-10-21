import { useSyncExternalStore } from 'react';
import { authMode, type AuthUser, type SignInMethod } from '../auth';

// Fixture-backed account store for the MVP UI phase. Shapes mirror what
// the Account and Payments service will own (PRD 4.4, 12; SDD 12):
//   guardians/{guardian_id}, children/{child_id}, consents/{consent_id}
// Consent is PER CHILD: the guardian attests "I am the parent or guardian
// of [child], aged [n]" when adding that child, and the record carries
// guardian_id and child_id so the Session Agent (mic gate) and the
// Reading Coach can both look it up by child. A session can only start
// for a child with a consent record from this guardian.
//
// TODO(live): child first names and birth years must NOT stay in
// localStorage on a shared family phone. Live: profiles live in the Account service's
// database behind its authorisation (guardians see only their own children); only the
// sign-in session persists in the browser (Entra, in this tab only: src/auth).

export const CONSENT_VERSION = 'consent_v1_2026-10';
export const CONSENT_TEXT =
  'I agree that Alo.ai can record my child reading aloud, use the recording to make their reading report, and keep the audio for up to 90 days. Alo.ai is a screening tool that helps us practise reading.';

export interface Guardian {
  guardian_id: string;
  email: string;
  sign_in_method: SignInMethod;
}

export interface ConsentRecord {
  consent_id: string;
  guardian_id: string;
  child_id: string;
  text_version: string;
  /** The exact attestation the guardian agreed to, naming the child. */
  attestation: string;
  sign_in_method: Guardian['sign_in_method'];
  verified_email: string;
  timestamp: string;
  training_opt_in: boolean;
}

export interface ChildProfile {
  child_id: string;
  first_name: string;
  primary_class: number; // 1..6
  birth_year: number;
  class_confirmed_year: number;
}

export interface Subscription {
  guardian_id: string;
  active: boolean;
}

export interface AccountState {
  guardian: Guardian | null;
  children: ChildProfile[];
  /** consents/{consent_id} by child_id — one record per child. */
  consentsByChildId: Record<string, ConsentRecord>;
  subscription: Subscription | null;
}

const STORAGE_KEY = 'alo.fixture.account.v2';
const emptyState: AccountState = {
  guardian: null,
  children: [],
  consentsByChildId: {},
  subscription: null,
};

// The sample build keeps its fixtures in localStorage. With real sign-in (Entra) nothing is
// written to the browser: a guardian's children and consents must not stay on a shared family
// phone, and there is no Account service to hold them yet, so in that mode they last only as
// long as the tab. Anything an earlier sample build left on this origin is removed.
let persist = authMode === 'fixture';

function forgetStored() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage can be unavailable; there is then nothing to remove.
  }
}

function load(): AccountState {
  if (!persist) {
    forgetStored();
    return emptyState;
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...emptyState, ...(JSON.parse(raw) as AccountState) } : emptyState;
  } catch {
    return emptyState;
  }
}

let state: AccountState = load();
const listeners = new Set<() => void>();

function setState(next: AccountState) {
  state = next;
  if (persist) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Storage can be unavailable (private mode); in-memory state still works.
    }
  }
  listeners.forEach((listener) => listener());
}

export function attestationFor(firstName: string, age: number): string {
  return `I am the parent or guardian of ${firstName}, aged ${age}. ${CONSENT_TEXT}`;
}

export function ageFromBirthYear(birthYear: number, now = new Date()): number {
  return now.getFullYear() - birthYear;
}

let idCounter = 0;
function nextId(prefix: string): string {
  idCounter += 1;
  return `${prefix}_sample_${Date.now()}_${idCounter}`;
}

export const accountStore = {
  getState: () => state,
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  /** Completes sign-in (Google, or returning via the email link). */
  signIn(method: Guardian['sign_in_method'], email = 'guardian@example.com') {
    setState({
      ...state,
      guardian: { guardian_id: 'guardian_sample_001', email, sign_in_method: method },
    });
  },
  /** Sets the guardian from an identity the sign-in provider has verified. The id is the
   *  provider's stable one, never the email address. */
  signInVerified(user: AuthUser) {
    setState({
      ...state,
      guardian: { guardian_id: user.id, email: user.email, sign_in_method: user.method },
    });
  },
  signOut() {
    setState(emptyState);
  },
  /** For tests: whether the account is kept in the browser (the sample build) or not. */
  setPersistence(keep: boolean) {
    persist = keep;
    if (!keep) forgetStored();
  },
  /**
   * Adds a child AND records that child's consent in one step, the way the
   * live Add-a-child screen will. Without the attestation, nothing is saved.
   */
  addChildWithConsent(input: {
    firstName: string;
    primaryClass: number;
    birthYear: number;
    attested: boolean;
    trainingOptIn: boolean;
  }): { child: ChildProfile; consent: ConsentRecord } {
    if (!state.guardian) throw new Error('Sign in before adding a child.');
    if (!input.attested) throw new Error('Consent is needed before adding a child.');
    const child: ChildProfile = {
      child_id: nextId('child'),
      first_name: input.firstName.trim(),
      primary_class: input.primaryClass,
      birth_year: input.birthYear,
      class_confirmed_year: new Date().getFullYear(),
    };
    const consent: ConsentRecord = {
      consent_id: nextId('consent'),
      guardian_id: state.guardian.guardian_id,
      child_id: child.child_id,
      text_version: CONSENT_VERSION,
      attestation: attestationFor(child.first_name, ageFromBirthYear(child.birth_year)),
      sign_in_method: state.guardian.sign_in_method,
      verified_email: state.guardian.email,
      timestamp: new Date().toISOString(),
      training_opt_in: input.trainingOptIn,
    };
    setState({
      ...state,
      children: [...state.children, child],
      consentsByChildId: { ...state.consentsByChildId, [child.child_id]: consent },
    });
    return { child, consent };
  },
  consentFor(childId: string): ConsentRecord | null {
    const consent = state.consentsByChildId[childId];
    if (!consent || !state.guardian) return null;
    return consent.guardian_id === state.guardian.guardian_id ? consent : null;
  },
  /** The mic gate (PRD 12): signed in + this child's consent on file. */
  canStartSession(childId: string): boolean {
    return this.consentFor(childId) !== null;
  },
  hasActiveSubscription(): boolean {
    return Boolean(
      state.guardian &&
        state.subscription?.active &&
        state.subscription.guardian_id === state.guardian.guardian_id,
    );
  },
  resetForTests() {
    idCounter = 0;
    setState(emptyState);
  },
};

export function useAccount(): AccountState {
  return useSyncExternalStore(accountStore.subscribe, accountStore.getState);
}
