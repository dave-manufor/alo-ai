import { useEffect, useState } from 'react';
import { ApiError, type ApiClient } from '../api/client';
import { dataMode, liveApi } from '../api';

// Where a session the guardian started has got to (schemas/session_start.schema.json, $defs/status;
// Account GET /v1/sessions/{session_id}). The session screen cannot know when the report is
// ready: the grading happens after the child has left. So the reports screen asks, every few
// seconds, until the report exists or the check is known to have stopped early.

export type SessionStatusName = 'PENDING' | 'STARTED' | 'COMPLETE' | 'INCOMPLETE';

export interface SessionStatus {
  schema_version: 2;
  session_id: string;
  status: SessionStatusName;
  report_ready: boolean;
  plan_ready: boolean;
}

export async function fetchSessionStatus(api: ApiClient, sessionId: string): Promise<SessionStatus | null> {
  try {
    return await api.get<SessionStatus>(`/v1/sessions/${encodeURIComponent(sessionId)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** What the reports screen should say about the check the guardian has just finished. */
export type PendingReport = 'none' | 'waiting' | 'ready' | 'unfinished' | 'unknown';

export const POLL_MS = 5000;
// Grading takes a minute or two; past this the screen stops asking and says to look again later.
export const POLL_LIMIT_MS = 10 * 60 * 1000;

/** Follows one session until its report exists. `none` when there is no session to follow. */
export function usePendingReport(sessionId: string | null, pollMs = POLL_MS): PendingReport {
  const [state, setState] = useState<PendingReport>('waiting');
  useEffect(() => {
    if (dataMode !== 'live' || !sessionId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const startedAt = Date.now();
    setState('waiting');
    const look = () => {
      fetchSessionStatus(liveApi(), sessionId)
        .then((status) => {
          if (cancelled) return;
          if (status?.report_ready) return setState('ready');
          if (status?.status === 'INCOMPLETE') return setState('unfinished');
          if (Date.now() - startedAt > POLL_LIMIT_MS) return setState('unknown');
          timer = setTimeout(look, pollMs);
        })
        .catch(() => {
          // A dropped request is not the end of the wait: try again until the limit.
          if (cancelled) return;
          if (Date.now() - startedAt > POLL_LIMIT_MS) return setState('unknown');
          timer = setTimeout(look, pollMs);
        });
    };
    look();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [sessionId, pollMs]);
  if (dataMode !== 'live' || !sessionId) return 'none';
  return state;
}
