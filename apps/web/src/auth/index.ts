import { isLocal } from '../config/env';
import { createEntraClient, entraConfigFromEnv } from './entra';
import type { AuthClient, AuthUser } from './types';

export type { AuthClient, AuthUser, SignInMethod } from './types';

// Which sign-in this build uses. `entra` when the Entra settings are present and this is not
// a local run; otherwise `fixture`, the sample sign-in the MVP screens run on. The mode is
// fixed by the build's environment variables, never chosen by the browser at run time.
const config = isLocal ? null : entraConfigFromEnv(import.meta.env, window.location.origin);

export const authMode: 'entra' | 'fixture' = config ? 'entra' : 'fixture';

let client: Promise<AuthClient> | null = null;

/** The Entra client, made once. Only in `entra` mode. */
export function auth(): Promise<AuthClient> {
  if (!config) return Promise.reject(new Error('Entra sign-in is not configured in this build.'));
  client ??= createEntraClient(config);
  return client;
}

let returnFailed = false;

/** True when the browser came back from sign-in and it did not complete. The app renders
 *  only after restoreSignIn has finished, so the sign-in page can read this once. */
export const signInFailed = () => returnFailed;

/** Called once at start-up: completes a sign-in the browser just came back from. Never
 *  throws, so the app always opens; a failure leaves the guardian signed out and is
 *  reported by signInFailed(). */
export async function restoreSignIn(): Promise<AuthUser | null> {
  if (authMode !== 'entra') return null;
  try {
    returnFailed = false;
    return await (await auth()).restore();
  } catch {
    returnFailed = true;
    return null;
  }
}
