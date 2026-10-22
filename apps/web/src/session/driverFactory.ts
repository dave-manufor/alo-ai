import { dataMode, liveApi } from '../api';
import type { SessionDriver } from './driver';
import { createFixtureDriver } from './fixtureDriver';
import { createLiveDriver, type SessionJoin } from './liveDriver';

// Which driver carries the session is decided by the build alone (D6):
// the live build joins a LiveKit room through the Account API; every
// other build replays the fixture session with no network. The browser
// never chooses, and never sends a voice_mode or session_profile (those
// are server settings).
export function createSessionDriver(childId: string): SessionDriver {
  if (dataMode !== 'live') return createFixtureDriver();
  return createLiveDriver({
    startSession: () => liveApi().post<SessionJoin>('/v1/sessions', { child_id: childId }),
  });
}
