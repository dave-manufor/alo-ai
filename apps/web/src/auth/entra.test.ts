import type { AccountInfo, Configuration } from '@azure/msal-browser';
import { describe, expect, it, vi } from 'vitest';
import { createEntraClient, entraConfigFromEnv, userFrom, type EntraConfig } from './entra';

// A fake MSAL application: nothing here reaches Entra.
function account(overrides: Partial<AccountInfo> = {}): AccountInfo {
  return {
    homeAccountId: 'home-1',
    localAccountId: 'oid-1',
    environment: 'aloai.ciamlogin.com',
    tenantId: 'tenant',
    username: 'guardian@example.com',
    idTokenClaims: { email: 'guardian@example.com', idp: 'https://aloai.ciamlogin.com/tenant/v2.0' },
    ...overrides,
  } as AccountInfo;
}

function fakeApp(state: { accounts?: AccountInfo[]; returned?: { account: AccountInfo } | null } = {}) {
  let active: AccountInfo | null = null;
  return {
    handleRedirectPromise: vi.fn(async () => state.returned ?? null),
    getActiveAccount: vi.fn(() => active),
    getAllAccounts: vi.fn(() => state.accounts ?? []),
    setActiveAccount: vi.fn((next: AccountInfo | null) => {
      active = next;
    }),
    loginRedirect: vi.fn<(request: unknown) => Promise<void>>(async () => undefined),
    logoutRedirect: vi.fn<(request?: unknown) => Promise<void>>(async () => undefined),
    acquireTokenSilent: vi.fn<(request: unknown) => Promise<{ accessToken: string }>>(async () => ({
      accessToken: 'api-token',
    })),
    acquireTokenRedirect: vi.fn<(request: unknown) => Promise<void>>(async () => undefined),
  };
}

const config: EntraConfig = {
  clientId: 'client-1',
  authority: 'https://aloai.ciamlogin.com/',
  redirectUri: 'https://alo.example/signin',
  apiScope: 'api://client-1/access_as_user',
};

async function client(app = fakeApp(), cfg = config) {
  let seen: Configuration | undefined;
  const made = await createEntraClient(cfg, async (msal) => {
    seen = msal;
    return app as never;
  });
  return { made, app, msal: seen! };
}

describe('Entra settings from the build environment', () => {
  it('needs both a client id and an authority', () => {
    expect(entraConfigFromEnv({}, 'https://alo.example')).toBeNull();
    expect(entraConfigFromEnv({ VITE_ENTRA_CLIENT_ID: 'c' }, 'https://alo.example')).toBeNull();
    expect(
      entraConfigFromEnv({ VITE_ENTRA_AUTHORITY: 'https://aloai.ciamlogin.com' }, 'https://alo.example'),
    ).toBeNull();
    expect(
      entraConfigFromEnv({ VITE_ENTRA_CLIENT_ID: '  ', VITE_ENTRA_AUTHORITY: 'x' }, 'https://alo.example'),
    ).toBeNull();
  });

  it('returns to the sign-in page of the same origin and ends the authority with a slash', () => {
    expect(
      entraConfigFromEnv(
        { VITE_ENTRA_CLIENT_ID: 'c', VITE_ENTRA_AUTHORITY: 'https://aloai.ciamlogin.com' },
        'https://alo.example',
      ),
    ).toEqual({
      clientId: 'c',
      authority: 'https://aloai.ciamlogin.com/',
      redirectUri: 'https://alo.example/signin',
      apiScope: undefined,
    });
  });

  it('takes the API scope when there is one', () => {
    const found = entraConfigFromEnv(
      {
        VITE_ENTRA_CLIENT_ID: 'c',
        VITE_ENTRA_AUTHORITY: 'https://aloai.ciamlogin.com/',
        VITE_ENTRA_API_SCOPE: ' api://c/access_as_user ',
      },
      'https://alo.example',
    );
    expect(found?.apiScope).toBe('api://c/access_as_user');
  });
});

describe('the Entra client', () => {
  it('is a public client for the tenant, with its session in this tab only', async () => {
    const { msal } = await client();
    expect(msal.auth).toMatchObject({
      clientId: 'client-1',
      authority: 'https://aloai.ciamlogin.com/',
      knownAuthorities: ['aloai.ciamlogin.com'],
      redirectUri: 'https://alo.example/signin',
      postLogoutRedirectUri: 'https://alo.example',
    });
    expect(msal.cache?.cacheLocation).toBe('sessionStorage');
  });

  it('completes the sign-in the browser has just come back from', async () => {
    const returned = account();
    const { made, app } = await client(fakeApp({ returned: { account: returned } }));
    expect(await made.restore()).toEqual({
      id: 'oid-1',
      email: 'guardian@example.com',
      method: 'email_code',
    });
    expect(app.setActiveAccount).toHaveBeenCalledWith(returned);
  });

  it('restores the sign-in this tab already has', async () => {
    const { made } = await client(fakeApp({ accounts: [account({ localAccountId: 'oid-2' })] }));
    expect((await made.restore())?.id).toBe('oid-2');
  });

  it('is signed out when there is no sign-in', async () => {
    const { made, app } = await client();
    expect(await made.restore()).toBeNull();
    expect(app.setActiveAccount).not.toHaveBeenCalled();
  });

  it('sends the guardian to Entra for an emailed code, with their email filled in', async () => {
    const { made, app } = await client();
    await made.signIn('  guardian@example.com ');
    const request = app.loginRedirect.mock.calls[0][0] as {
      scopes: string[];
      loginHint?: string;
      extraQueryParameters?: unknown;
    };
    expect(request.loginHint).toBe('guardian@example.com');
    // No social provider is requested: the email code is the only way in.
    expect(request.extraQueryParameters).toBeUndefined();
    expect(request.scopes).toEqual(['openid', 'profile', 'email', 'api://client-1/access_as_user']);
  });

  it('clears a stuck "sign-in in progress" marker and tries once more', async () => {
    window.sessionStorage.setItem('msal.client-1.interaction.status', 'interaction_in_progress');
    const { made, app } = await client();
    app.loginRedirect.mockRejectedValueOnce(
      Object.assign(new Error('x'), { errorCode: 'interaction_in_progress' }),
    );
    await made.signIn('guardian@example.com');
    expect(app.loginRedirect).toHaveBeenCalledTimes(2);
    expect(window.sessionStorage.getItem('msal.client-1.interaction.status')).toBeNull();
  });

  it('logs only the error code when sign-in cannot start, and passes the error on', async () => {
    const { made, app } = await client();
    const failure = Object.assign(new Error('a@b.example failed'), { errorCode: 'endpoints_resolution_error' });
    app.loginRedirect.mockRejectedValueOnce(failure);
    const logged = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    await expect(made.signIn('guardian@example.com')).rejects.toBe(failure);
    expect(logged).toHaveBeenCalledWith('sign-in could not start:', 'endpoints_resolution_error');
    expect(JSON.stringify(logged.mock.calls)).not.toContain('a@b.example');
    logged.mockRestore();
  });

  it('asks only for the sign-in scopes when there is no API yet', async () => {
    const { made, app } = await client(fakeApp(), { ...config, apiScope: undefined });
    await made.signIn('guardian@example.com');
    expect((app.loginRedirect.mock.calls[0][0] as { scopes: string[] }).scopes).toEqual([
      'openid',
      'profile',
      'email',
    ]);
  });

  it('signs out of the account that is signed in, or of none', async () => {
    const signedIn = account();
    const { made, app } = await client(fakeApp({ accounts: [signedIn] }));
    await made.signOut();
    expect(app.logoutRedirect).toHaveBeenCalledWith({ account: signedIn });
    const { made: nobody, app: nobodyApp } = await client();
    await nobody.signOut();
    expect(nobodyApp.logoutRedirect).toHaveBeenCalledWith(undefined);
  });
});

describe('the token for the Account API', () => {
  it('is none while there is no API scope, or nobody signed in', async () => {
    const { made } = await client(fakeApp({ accounts: [account()] }), { ...config, apiScope: undefined });
    expect(await made.getAccessToken()).toBeNull();
    const { made: signedOut } = await client();
    expect(await signedOut.getAccessToken()).toBeNull();
  });

  it('comes silently from the sign-in', async () => {
    const signedIn = account();
    const { made, app } = await client(fakeApp({ accounts: [signedIn] }));
    expect(await made.getAccessToken()).toBe('api-token');
    expect(app.acquireTokenSilent).toHaveBeenCalledWith({
      scopes: ['api://client-1/access_as_user'],
      account: signedIn,
    });
  });

  it('goes back through sign-in when the session needs the guardian again', async () => {
    const app = fakeApp({ accounts: [account()] });
    app.acquireTokenSilent.mockRejectedValueOnce(
      Object.assign(new Error('login required'), { name: 'InteractionRequiredAuthError' }),
    );
    const { made } = await client(app);
    expect(await made.getAccessToken()).toBeNull();
    expect(app.acquireTokenRedirect).toHaveBeenCalledOnce();
  });

  it('lets any other failure through', async () => {
    const app = fakeApp({ accounts: [account()] });
    app.acquireTokenSilent.mockRejectedValueOnce(new Error('network down'));
    const { made } = await client(app);
    await expect(made.getAccessToken()).rejects.toThrow('network down');
    expect(app.acquireTokenRedirect).not.toHaveBeenCalled();
  });
});

describe('who the sign-in says the guardian is', () => {
  it('knows a Google sign-in', () => {
    expect(userFrom(account({ idTokenClaims: { email: 'g@example.com', idp: 'google.com' } })).method).toBe(
      'google',
    );
  });

  it('knows an emailed code, which has the tenant as its identity provider', () => {
    expect(userFrom(account()).method).toBe('email_code');
    expect(userFrom(account({ idTokenClaims: undefined })).method).toBe('email_code');
  });

  it('uses the verified email claim, else the username, and never the email as the id', () => {
    expect(userFrom(account({ idTokenClaims: { email: 'claim@example.com' } })).email).toBe('claim@example.com');
    expect(userFrom(account({ idTokenClaims: undefined })).email).toBe('guardian@example.com');
    const user = userFrom(account({ localAccountId: '', homeAccountId: 'home-9' }));
    expect(user.id).toBe('home-9');
    expect(user.id).not.toContain('@');
  });
});
