import { auth } from '../auth';
import { createApiClient, type ApiClient } from './client';
import { apiBaseUrl, dataMode } from './mode';

export { ApiError } from './client';
export type { ApiClient } from './client';
export { dataMode } from './mode';

let client: ApiClient | null = null;

/** The live API client; only exists in a live build. The token comes from src/auth. */
export function liveApi(): ApiClient {
  if (dataMode !== 'live') throw new Error('The API is not configured in this build.');
  client ??= createApiClient({
    baseUrl: apiBaseUrl,
    getToken: async () => (await auth()).getAccessToken(),
  });
  return client;
}
