import { useSyncExternalStore } from 'react';

// What the guardian chose on the Consent step, held in memory until the child is saved on the
// next one. Consent is still written per child, naming the child, when the child is added
// (accountStore.addChildWithConsent); this only carries the two ticks between the screens.
// Nothing here is stored in the browser.
export interface ConsentDraft {
  attested: boolean;
  trainingOptIn: boolean;
}

const empty: ConsentDraft = { attested: false, trainingOptIn: false };
let draft: ConsentDraft = empty;
const listeners = new Set<() => void>();

export const consentDraft = {
  get: () => draft,
  set(next: ConsentDraft) {
    draft = next;
    listeners.forEach((listener) => listener());
  },
  clear() {
    consentDraft.set(empty);
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useConsentDraft(): ConsentDraft {
  return useSyncExternalStore(consentDraft.subscribe, consentDraft.get);
}
