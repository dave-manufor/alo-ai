import { authMode } from '../auth';
import { isLocal } from '../config/env';

// Fixture or live is decided by the build's settings alone (D6): the
// browser, the URL and the user never choose. Live needs real sign-in
// (Entra) AND an API address baked in at build time (VITE_ALO_API_URL).
// Everything else, including a build that forgot either setting, is the
// fixture build, which makes no network calls for account data. The
// teacher preview never imports this: it has no data client at all.
export function resolveDataMode(
  env: Record<string, unknown>,
  auth: 'entra' | 'fixture',
  local: boolean,
): { mode: 'live' | 'fixture'; baseUrl: string } {
  const raw = env.VITE_ALO_API_URL;
  const baseUrl = (typeof raw === 'string' ? raw : '').trim().replace(/\/+$/, '');
  const live = !local && auth === 'entra' && baseUrl !== '';
  return { mode: live ? 'live' : 'fixture', baseUrl: live ? baseUrl : '' };
}

const resolved = resolveDataMode(import.meta.env, authMode, isLocal);

export const dataMode: 'live' | 'fixture' = resolved.mode;
export const apiBaseUrl: string = resolved.baseUrl;
