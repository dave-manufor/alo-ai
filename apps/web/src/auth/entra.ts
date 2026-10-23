import type { AccountInfo, Configuration, IPublicClientApplication } from '@azure/msal-browser';
import { clearReturnTo, saveReturnTo } from './returnTo';
import type { AuthClient, AuthUser } from './types';

// Sign-in with Microsoft Entra External ID (the customer tenant, `*.ciamlogin.com`): a
// one-time code emailed to the guardian, or Google. Both are set up in the tenant's user
// flow, not here (apps/web/README.md). The browser holds no secret: this is a public client
// with PKCE, and the session lives in this tab only (sessionStorage), so a shared family
// phone does not keep a guardian signed in.

export interface EntraConfig {
  clientId: string;
  /** e.g. https://aloai.ciamlogin.com/ */
  authority: string;
  redirectUri: string;
  /** The Account API's scope, e.g. api://<client id>/access_as_user. Optional until it exists. */
  apiScope?: string;
}

export type MsalFactory = (config: Configuration) => Promise<IPublicClientApplication>;

const SIGN_IN_SCOPES = ['openid', 'profile', 'email'];

export function entraConfigFromEnv(
  env: Record<string, string | undefined>,
  origin: string,
): EntraConfig | null {
  const clientId = env.VITE_ENTRA_CLIENT_ID?.trim();
  const authority = env.VITE_ENTRA_AUTHORITY?.trim();
  if (!clientId || !authority) return null;
  return {
    clientId,
    authority: authority.endsWith('/') ? authority : `${authority}/`,
    // The sign-in page finishes the redirect, so the guardian lands where they started.
    redirectUri: `${origin}/signin`,
    apiScope: env.VITE_ENTRA_API_SCOPE?.trim() || undefined,
  };
}

const defaultFactory: MsalFactory = async (config) => {
  // Loaded only when Entra is the chosen mode, so the fixture build does not carry it.
  const { createStandardPublicClientApplication } = await import('@azure/msal-browser');
  return createStandardPublicClientApplication(config);
};

export function userFrom(account: AccountInfo): AuthUser {
  const claims = (account.idTokenClaims ?? {}) as Record<string, unknown>;
  const idp = String(claims.idp ?? '');
  const email = String(claims.email ?? account.username ?? '').trim();
  return {
    id: account.localAccountId || account.homeAccountId,
    email,
    method: /google/i.test(idp) ? 'google' : 'email_code',
  };
}

export async function createEntraClient(
  config: EntraConfig,
  factory: MsalFactory = defaultFactory,
): Promise<AuthClient> {
  const app = await factory({
    auth: {
      clientId: config.clientId,
      authority: config.authority,
      knownAuthorities: [new URL(config.authority).host],
      redirectUri: config.redirectUri,
      postLogoutRedirectUri: new URL(config.redirectUri).origin,
    },
    cache: { cacheLocation: 'sessionStorage' },
  });

  const scopes = config.apiScope ? [...SIGN_IN_SCOPES, config.apiScope] : SIGN_IN_SCOPES;

  function activeAccount(): AccountInfo | null {
    return app.getActiveAccount() ?? app.getAllAccounts()[0] ?? null;
  }

  return {
    async restore() {
      const returned = await app.handleRedirectPromise();
      const account = returned?.account ?? activeAccount();
      if (!account) return null;
      app.setActiveAccount(account);
      return userFrom(account);
    },

    async signIn(email) {
      // The one-time code is Entra's default; the email the guardian typed is passed on so its
      // page opens with the address filled in and sends the code straight away.
      const loginHint = email.trim();
      await app.loginRedirect({ scopes, ...(loginHint ? { loginHint } : {}) });
    },

    async signOut() {
      const account = activeAccount();
      clearReturnTo();
      await app.logoutRedirect(account ? { account } : undefined);
    },

    async getAccessToken() {
      if (!config.apiScope) return null;
      const account = activeAccount();
      if (!account) return null;
      try {
        return (await app.acquireTokenSilent({ scopes: [config.apiScope], account })).accessToken;
      } catch (error) {
        // The session needs the guardian again (expired, or consent changed): go back through
        // sign-in. This leaves the page, so there is no token to return.
        if ((error as { name?: string }).name === 'InteractionRequiredAuthError') {
          saveReturnTo(window.location.pathname + window.location.search);
          await app.acquireTokenRedirect({ scopes: [config.apiScope], account });
          return null;
        }
        throw error;
      }
    },
  };
}
