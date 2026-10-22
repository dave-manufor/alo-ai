import { describe, expect, it, vi } from 'vitest';
import { createChild, loadAccount } from '../account/remote';
import { fetchReport, fetchReports } from '../report/useReports';
import { ApiError, createApiClient } from './client';
import { resolveDataMode } from './mode';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function clientWith(fetchImpl: typeof fetch, token: string | null = 'tok') {
  return createApiClient({
    baseUrl: 'https://api.example.test',
    getToken: async () => token,
    fetchImpl,
  });
}

describe('API client (D1)', () => {
  it('attaches the bearer token and sends JSON', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { ok: true }));
    await clientWith(fetchImpl as unknown as typeof fetch).post('/v1/x', { a: 1 });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://api.example.test/v1/x');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
    expect(init.body).toBe('{"a":1}');
  });

  it('can PATCH, with the same token and JSON body', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { ok: true }));
    await clientWith(fetchImpl as unknown as typeof fetch).patch('/v1/children/c1', { first_name: 'Ada' });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://api.example.test/v1/children/c1');
    expect(init.method).toBe('PATCH');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
    expect(init.body).toBe('{"first_name":"Ada"}');
  });

  it('does not call the network without a token', async () => {
    const fetchImpl = vi.fn();
    await expect(clientWith(fetchImpl as unknown as typeof fetch, null).get('/v1/me')).rejects.toMatchObject({
      status: 401,
      plain: 'Please sign in again.',
    });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it('maps the error envelope to a plain message, never the server text', async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(400, {
        error: { code: 'CONSENT_REQUIRED', message: 'raw server text', retryable: false },
      }),
    );
    const error = await clientWith(fetchImpl as unknown as typeof fetch)
      .post('/v1/children', {})
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).plain).toBe('Please tick the box to say you are the parent or guardian.');
    expect((error as ApiError).plain).not.toMatch(/raw server text/);
    expect((error as ApiError).retryable).toBe(false);
  });

  it('treats a 500 with no JSON body as retryable', async () => {
    const fetchImpl = vi.fn(async () => new Response('boom', { status: 503 }));
    const error = (await clientWith(fetchImpl as unknown as typeof fetch)
      .get('/v1/me')
      .catch((e: unknown) => e)) as ApiError;
    expect(error.retryable).toBe(true);
    expect(error.plain).toMatch(/try again in a moment/);
  });

  it('turns a dropped network into a retryable plain error', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });
    const error = (await clientWith(fetchImpl as unknown as typeof fetch)
      .get('/v1/me')
      .catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe('NETWORK');
    expect(error.retryable).toBe(true);
  });
});

describe('children and consent through the API (D2)', () => {
  const child = {
    child_id: 'child_1',
    first_name: 'Ada',
    primary_class: 3,
    birth_year: 2017,
    class_confirmed_year: 2026,
  };
  const consent = { consent_id: 'consent_1', child_id: 'child_1', guardian_id: 'g' };

  it('loads children and their consent; a child with none has none', async () => {
    const fetchImpl = vi.fn(async (url: string) => {
      if (url.endsWith('/v1/children')) {
        return jsonResponse(200, {
          children: [child, { ...child, child_id: 'child_2', first_name: 'Bayo' }],
        });
      }
      if (url.endsWith('/child_1/consent')) return jsonResponse(200, consent);
      return jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'x', retryable: false } });
    });
    const loaded = await loadAccount(clientWith(fetchImpl as unknown as typeof fetch));
    expect(loaded.children.map((c) => c.first_name)).toEqual(['Ada', 'Bayo']);
    expect(loaded.consents).toHaveLength(1);
  });

  it('sends only the tick, never an attestation text', async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(201, { child_id: 'child_1', child, consent }),
    );
    const saved = await createChild(clientWith(fetchImpl as unknown as typeof fetch), {
      firstName: ' Ada ',
      primaryClass: 3,
      birthYear: 2017,
      attested: true,
      trainingOptIn: false,
    });
    const init = (fetchImpl.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(JSON.parse(init.body as string)).toEqual({
      first_name: 'Ada',
      primary_class: 3,
      birth_year: 2017,
      attested: true,
      training_opt_in: false,
    });
    expect(saved.child.child_id).toBe('child_1');
  });
});

describe('reports through the API (D5, against the planned C5 contract)', () => {
  it('reads the list and one report; a missing report is null', async () => {
    const fetchImpl = vi.fn(async (url: string) => {
      if (url.endsWith('/v1/reports')) return jsonResponse(200, { reports: [{ session_id: 's1' }] });
      if (url.endsWith('/v1/reports/s1')) return jsonResponse(200, { session_id: 's1' });
      return jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'x', retryable: false } });
    });
    const api = clientWith(fetchImpl as unknown as typeof fetch);
    expect(await fetchReports(api)).toHaveLength(1);
    expect(await fetchReport(api, 's1')).toMatchObject({ session_id: 's1' });
    expect(await fetchReport(api, 'nope')).toBeNull();
  });
});

describe('fixture or live is chosen by build settings only (D6)', () => {
  const url = { VITE_ALO_API_URL: 'https://api.example.test/' };
  it('is live only with Entra, an API address and a non-local build', () => {
    expect(resolveDataMode(url, 'entra', false)).toEqual({
      mode: 'live',
      baseUrl: 'https://api.example.test',
    });
  });
  it('is fixture when any setting is missing', () => {
    expect(resolveDataMode({}, 'entra', false).mode).toBe('fixture');
    expect(resolveDataMode(url, 'fixture', false).mode).toBe('fixture');
    expect(resolveDataMode(url, 'entra', true).mode).toBe('fixture');
  });
  it('the test build itself is the fixture build and makes no API calls', async () => {
    const { dataMode } = await import('./mode');
    expect(dataMode).toBe('fixture');
  });
});
