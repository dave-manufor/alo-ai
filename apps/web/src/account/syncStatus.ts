import { useSyncExternalStore } from 'react';
import { syncAccount } from './actions';

// Whether the last load of the guardian's children failed (live build). Without it an empty
// list after a dropped connection looks like a new guardian and sends them to add a child again.

let failed = false;
const listeners = new Set<() => void>();

function set(next: boolean) {
  if (failed === next) return;
  failed = next;
  listeners.forEach((listener) => listener());
}

/** Load the guardian's children and consents; remember whether that worked. Never throws. */
export async function loadAccountSafely(): Promise<void> {
  try {
    await syncAccount();
    set(false);
  } catch {
    set(true);
  }
}

export const retrySync = loadAccountSafely;

export function useSyncFailed(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => failed,
  );
}
