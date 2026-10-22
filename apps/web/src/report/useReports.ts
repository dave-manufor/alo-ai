import { useEffect, useState } from 'react';
import { useAccount } from '../account/store';
import { ApiError, type ApiClient } from '../api/client';
import { dataMode, liveApi } from '../api';
import { reportsFor } from './childReports';
import type { ReadingReport, ReportChild } from './reportFixture';

// Reports for the grown-up screens (D5). Fixture build: the sample
// reports, no network. Live build: the Account API's reports endpoint.
//
// CONTRACT (C5, services/account/reports.py): GET /v1/reports (the
// signed-in guardian's reports, newest first) -> {"reports": [ReadingReport]}
// and GET /v1/reports/{session_id} -> ReadingReport (schemas/
// reading_report.schema.json), 404 for a report that is missing or not this
// guardian's. Each read is audit-logged server side. Only these two paths
// change if the API does; nothing else moves.

export async function fetchReports(api: ApiClient): Promise<ReadingReport[]> {
  const { reports } = await api.get<{ reports: ReadingReport[] }>('/v1/reports');
  return reports;
}

export async function fetchReport(api: ApiClient, sessionId: string): Promise<ReadingReport | null> {
  try {
    return await api.get<ReadingReport>(`/v1/reports/${encodeURIComponent(sessionId)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export type ReportsState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; reports: ReadingReport[]; children: Record<string, ReportChild> };

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.plain : 'We could not load the reports. Please try again.';
}

// The names come from the guardian's own children in both builds: a report carries a
// child_id, never a name (PRD 12).
function useChildNames(): Record<string, ReportChild> {
  const { children } = useAccount();
  return Object.fromEntries(
    children.map((child) => [child.child_id, { child_id: child.child_id, first_name: child.first_name }]),
  );
}

export function useReports(): ReportsState {
  const { children } = useAccount();
  const names = useChildNames();
  const [state, setState] = useState<ReportsState>({ status: 'loading' });
  useEffect(() => {
    if (dataMode !== 'live') return;
    let cancelled = false;
    fetchReports(liveApi())
      .then((reports) => {
        if (!cancelled) setState({ status: 'ready', reports, children: names });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: 'error', message: messageOf(error) });
      });
    return () => {
      cancelled = true;
    };
    // names is derived from the account store; reload only on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (dataMode !== 'live') {
    // Fixture build: one sample check per child the guardian has added (childReports.ts).
    return { status: 'ready', reports: reportsFor(children), children: names };
  }
  return state.status === 'ready' ? { ...state, children: names } : state;
}

/** The newest report for one child, once the reports have loaded. `report` is null before the
 *  child's first check. */
export function useLatestReport(childId: string | undefined): {
  status: 'loading' | 'error' | 'ready';
  report: ReadingReport | null;
} {
  const view = useReports();
  if (view.status !== 'ready') return { status: view.status, report: null };
  const mine = view.reports
    .filter((report) => report.child_id === childId)
    .sort((a, b) => b.timestamp_iso.localeCompare(a.timestamp_iso));
  return { status: 'ready', report: mine[0] ?? null };
}

export type ReportState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; report: ReadingReport | null; children: Record<string, ReportChild> };

export function useReport(sessionId: string | undefined): ReportState {
  const { children } = useAccount();
  const names = useChildNames();
  const [state, setState] = useState<ReportState>({ status: 'loading' });
  useEffect(() => {
    if (dataMode !== 'live' || !sessionId) return;
    let cancelled = false;
    fetchReport(liveApi(), sessionId)
      .then((report) => {
        if (!cancelled) setState({ status: 'ready', report, children: names });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: 'error', message: messageOf(error) });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);
  if (dataMode !== 'live') {
    return {
      status: 'ready',
      report: reportsFor(children).find((item) => item.session_id === sessionId) ?? null,
      children: names,
    };
  }
  return state.status === 'ready' ? { ...state, children: names } : state;
}
