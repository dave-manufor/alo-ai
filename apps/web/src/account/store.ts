import { useSyncExternalStore } from 'react';

// Fixture-backed account store for the MVP UI phase. It mirrors the shape
// the Account and Payments service will own (PRD 4.4, 12): a verified
// guardian, a consent record, and the guardian's children. The microphone
// and a session can never start for a child without a consent record, so
// `addChild` refuses until consent exists. Nothing here calls a network;
// Firebase Auth and the Account service replace this store later.

export const CONSENT_VERSION = 'consent_v1_2026-10';
export const CONSENT_TEXT =
  'I am the parent or guardian of the child I am adding. I agree that Alo.ai can record my child reading aloud, use the recording to make their reading report, and keep the audio for up to 90 days. Alo.ai is a screening tool that helps us practise reading.';

export interface Guardian {
  id: string;
  email: string;
  signInMethod: 'google' | 'email_link';
}

export interface ConsentRecord {
  childScope: 'added_children';
  textVersion: string;
  attestedAtIso: string;
  signInMethod: Guardian['signInMethod'];
  verifiedEmail: string;
  trainingOptIn: boolean;
}

export interface ChildProfile {
  id: string;
  firstName: string;
  primaryClass: number; // 1..6
  birthYear: number;
  classConfirmedYear: number;
}

export interface AccountState {
  guardian: Guardian | null;
  consent: ConsentRecord | null;
  children: ChildProfile[];
}

const STORAGE_KEY = 'alo.fixture.account.v1';
const emptyState: AccountState = { guardian: null, consent: null, children: [] };

function load(): AccountState {
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
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage can be unavailable (private mode); the in-memory state works.
  }
  listeners.forEach((listener) => listener());
}

export const accountStore = {
  getState: () => state,
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  /** Sample sign-in standing in for Firebase Auth (Google / email link). */
  signIn(method: Guardian['signInMethod'], email = 'guardian@example.com') {
    setState({
      ...state,
      guardian: { id: 'guardian_sample_001', email, signInMethod: method },
    });
  },
  signOut() {
    setState(emptyState);
  },
  recordConsent(trainingOptIn: boolean) {
    if (!state.guardian) throw new Error('Sign in before giving consent.');
    const consent: ConsentRecord = {
      childScope: 'added_children',
      textVersion: CONSENT_VERSION,
      attestedAtIso: new Date().toISOString(),
      signInMethod: state.guardian.signInMethod,
      verifiedEmail: state.guardian.email,
      trainingOptIn,
    };
    setState({ ...state, consent });
    return consent;
  },
  addChild(input: { firstName: string; primaryClass: number; birthYear: number }) {
    if (!state.consent) {
      throw new Error('Consent is needed before adding a child.');
    }
    const child: ChildProfile = {
      id: `child_sample_${Date.now()}`,
      firstName: input.firstName.trim(),
      primaryClass: input.primaryClass,
      birthYear: input.birthYear,
      classConfirmedYear: new Date().getFullYear(),
    };
    setState({ ...state, children: [...state.children, child] });
    return child;
  },
  /** Whether a session may start: signed in, consent on file, child exists. */
  canStartSession(childId: string) {
    return Boolean(
      state.guardian && state.consent && state.children.some((c) => c.id === childId),
    );
  },
  resetForTests() {
    setState(emptyState);
  },
};

export function useAccount(): AccountState {
  return useSyncExternalStore(accountStore.subscribe, accountStore.getState);
}
