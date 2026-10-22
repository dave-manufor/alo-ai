import { useEffect, useState } from 'react';
import { useAccount } from '../account/store';
import { ApiError, type ApiClient } from '../api/client';
import { dataMode, liveApi } from '../api';
import { sampleChildren, sampleReports, type ReadingReport, type ReportChild } from './reportFixture';

// Reports for the grown-up screens (D5). Fixture build: the sample
// reports, no network. Live build: the Account API's reports endpoint.
//
// CONTRACT ASSUMPTION: C5 (the reports API, #71) is not built yet. These
// paths follow the plan: GET /v1/reports (the signed-in guardian's
// reports, newest first) -> {"reports": [ReadingReport]} and
// GET /v1/reports/{session_id} -> ReadingReport (schemas/
// reading_report.schema.json). Each read is audit-logged server side.
// Change the two paths here if C5 lands differently; nothing else moves.

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

function useChildNames(): Record<string, ReportChild> {
  const { children } = useAccount();
  if (dataMode !== 'live') return sampleChildren;
  return Object.fromEntries(
    children.map((child) => [child.child_id, { child_id: child.child_id, first_name: child.first_name }]),
  );
}

export function useReports(): ReportsState {
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
    return { status: 'ready', reports: sampleReports, children: sampleChildren };
  }
  return state.status === 'ready' ? { ...state, children: names } : state;
}

export type ReportState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; report: ReadingReport | null; children: Record<string, ReportChild> };

export function useReport(sessionId: string | undefined): ReportState {
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
      report: sampleReports.find((item) => item.session_id === sessionId) ?? null,
      children: sampleChildren,
    };
  }
  return state.status === 'ready' ? { ...state, children: names } : state;
}
