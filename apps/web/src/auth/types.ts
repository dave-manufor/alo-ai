// How a guardian proved who they are. The Account service (PRD 4.4, 12) records the
// method with each consent: Google, a one-time code emailed to them (Entra External ID's
// email sign-in), or, in the fixture build only, the old sample email link.
export type SignInMethod = 'google' | 'email_code' | 'email_link';

/** A verified guardian identity: the id is stable and never an email address. */
export interface AuthUser {
  id: string;
  email: string;
  method: SignInMethod;
}

export interface AuthClient {
  /** Completes a sign-in the browser has just come back from, or restores one from
   *  this tab's session. Resolves to null when nobody is signed in. */
  restore(): Promise<AuthUser | null>;
  /** Sends the guardian to sign in. Resolves only if the browser did not leave. */
  signIn(method: 'google' | 'email'): Promise<void>;
  signOut(): Promise<void>;
  /** A bearer token for the Account API, or null when no API scope is configured. */
  getAccessToken(): Promise<string | null>;
}
