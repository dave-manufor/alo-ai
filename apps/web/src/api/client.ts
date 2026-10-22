// The one place that knows the API's base URL, the bearer token and the
// error shape (D1). The Account API answers errors as
// {"error": {"code", "message", "retryable"}}. Screens never show the
// server's message or a status code; they show `ApiError.plain`, which
// is written for a grown-up and never blames them or the child.

export interface ApiErrorBody {
  code: string;
  message: string;
  retryable: boolean;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly retryable: boolean,
    /** What a grown-up sees. */
    readonly plain: string,
  ) {
    super(`${status} ${code}`);
    this.name = 'ApiError';
  }
}

const PLAIN: Record<string, string> = {
  CONSENT_REQUIRED: 'Please tick the box to say you are the parent or guardian.',
  NOT_FOUND: 'We could not find that. Please go back and try again.',
  UNAUTHENTICATED: 'Please sign in again.',
  FORBIDDEN: 'This is not available for your account.',
};

export function plainMessage(status: number, code: string): string {
  if (PLAIN[code]) return PLAIN[code];
  if (status === 401) return PLAIN.UNAUTHENTICATED;
  if (status === 403) return PLAIN.FORBIDDEN;
  if (status === 404) return PLAIN.NOT_FOUND;
  if (status >= 500 || status === 429) {
    return 'Something went wrong on our side. Please try again in a moment.';
  }
  return 'We could not do that. Please check and try again.';
}

export interface ApiClientOptions {
  baseUrl: string;
  /** The guardian's bearer token, or null when none is available. */
  getToken: () => Promise<string | null>;
  fetchImpl?: typeof fetch;
}

export interface ApiClient {
  get<T>(path: string): Promise<T>;
  post<T>(path: string, body: unknown): Promise<T>;
}

export function createApiClient(options: ApiClientOptions): ApiClient {
  const doFetch = options.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));

  async function request<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
    const token = await options.getToken();
    if (!token) throw new ApiError(401, 'UNAUTHENTICATED', false, PLAIN.UNAUTHENTICATED);
    let response: Response;
    try {
      response = await doFetch(`${options.baseUrl}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(
        0,
        'NETWORK',
        true,
        'We could not reach Alo.ai. Please check the internet and try again.',
      );
    }
    if (!response.ok) {
      let code = 'UNKNOWN';
      let retryable = response.status >= 500;
      try {
        const parsed = (await response.json()) as { error?: Partial<ApiErrorBody> };
        if (parsed.error?.code) code = parsed.error.code;
        if (typeof parsed.error?.retryable === 'boolean') retryable = parsed.error.retryable;
      } catch {
        // A non-JSON error body: keep the defaults.
      }
      throw new ApiError(response.status, code, retryable, plainMessage(response.status, code));
    }
    return (await response.json()) as T;
  }

  return {
    get: (path) => request('GET', path),
    post: (path, body) => request('POST', path, body),
  };
}
