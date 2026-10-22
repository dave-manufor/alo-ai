import { useEffect, useState } from 'react';
import { ApiError, type ApiClient } from '../api/client';
import { dataMode, liveApi } from '../api';
import { nextCheckIso } from './childReports';
import { sampleBooks, samplePlan, type ReadingReport } from './reportFixture';

// The weekly plan (PRD 8, 10.4). Live build: the Account API's
// GET /v1/plans/{session_id} (schemas/guardian_plan.schema.json), 404 until the Coach has made
// the plan. Fixture build: a sample plan built from the sample report, no network.
// The browser shows what it is given and makes no number.

export interface PlanBook {
  book_id: string;
  title: string;
  author: string;
  licence: string;
  attribution: string;
  arl: number;
}

export interface GuardianPlan {
  schema_version: 1;
  plan_id: string;
  session_id: string;
  child_id: string;
  activities: { activity_id: string; title: string; text: string }[];
  books: PlanBook[];
  next_session_at: string;
}

export async function fetchPlan(api: ApiClient, sessionId: string): Promise<GuardianPlan | null> {
  try {
    return await api.get<GuardianPlan>(`/v1/plans/${encodeURIComponent(sessionId)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function samplePlanFor(report: ReadingReport): GuardianPlan {
  return {
    schema_version: 1,
    plan_id: `plan_${report.session_id}`,
    session_id: report.session_id,
    child_id: report.child_id,
    activities: samplePlan,
    books: report.recommendations.book_ids.flatMap((id) => (sampleBooks[id] ? [sampleBooks[id]] : [])),
    next_session_at: nextCheckIso(report),
  };
}

export type PlanState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  /** `plan` is null when there is no plan yet (live: the Coach has not made one). */
  | { status: 'ready'; plan: GuardianPlan | null };

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.plain : 'We could not load the plan. Please try again.';
}

/** The plan for a report, when `wanted` (the guardian may see it). */
export function usePlan(report: ReadingReport | null | undefined, wanted: boolean): PlanState {
  const sessionId = report?.session_id;
  const [state, setState] = useState<PlanState>({ status: 'loading' });
  useEffect(() => {
    if (dataMode !== 'live' || !wanted || !sessionId) return;
    let cancelled = false;
    setState({ status: 'loading' });
    fetchPlan(liveApi(), sessionId)
      .then((plan) => {
        if (!cancelled) setState({ status: 'ready', plan });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: 'error', message: messageOf(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, wanted]);
  if (!wanted || !report) return { status: 'ready', plan: null };
  if (dataMode !== 'live') return { status: 'ready', plan: samplePlanFor(report) };
  return state;
}
