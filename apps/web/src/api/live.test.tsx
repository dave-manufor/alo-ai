import { render, renderHook, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { addChild, syncAccount } from '../account/actions';
import { accountStore } from '../account/store';
import ReportDetailPage from '../pages/ReportDetailPage';
import ReportsPage from '../pages/ReportsPage';
import { createSessionDriver } from '../session/driverFactory';
import { planUnlocked } from '../plan/access';
import { usePlan } from '../report/plan';
import { sampleReports } from '../report/reportFixture';
import { ApiError } from './client';

// A live build, with the API faked: nothing here touches the network.
const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('./client')>('./client');
  return { dataMode: 'live', liveApi: () => api, ApiError: actual.ApiError };
});

const child = {
  child_id: 'child_1',
  first_name: 'Ada',
  primary_class: 3,
  birth_year: 2017,
  class_confirmed_year: 2026,
};
const consent = {
  consent_id: 'c1',
  guardian_id: 'g1',
  child_id: 'child_1',
  text_version: 'v',
  attestation: 'a',
  sign_in_method: 'google',
  verified_email: 'e@example.com',
  timestamp: '2026-10-01T00:00:00Z',
  training_opt_in: false,
};

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  accountStore.resetForTests();
  accountStore.signInVerified({ id: 'g1', email: 'e@example.com', method: 'google' });
});

describe('live build: account', () => {
  it('syncs children and consents from the API into the store', async () => {
    api.get.mockImplementation(async (path: string) =>
      path === '/v1/children' ? { children: [child] } : consent,
    );
    await syncAccount();
    expect(accountStore.getState().children[0].first_name).toBe('Ada');
    expect(accountStore.canStartSession('child_1')).toBe(true);
  });

  it('adds a child through the API, and refuses without the tick before any call', async () => {
    api.post.mockResolvedValue({ child_id: 'child_1', child, consent });
    const input = { firstName: 'Ada', primaryClass: 3, birthYear: 2017, attested: true, trainingOptIn: false };
    await addChild(input);
    expect(api.post).toHaveBeenCalledWith('/v1/children', expect.objectContaining({ attested: true }));
    expect(accountStore.getState().children).toHaveLength(1);

    api.post.mockClear();
    await expect(addChild({ ...input, attested: false })).rejects.toThrow(/Consent is needed/);
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe('live build: reports', () => {
  function renderAt(path: string) {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it('shows loading, then the reports the API returned', async () => {
    api.get.mockResolvedValue({ reports: [sampleReports[0]] });
    renderAt('/reports');
    expect(screen.getByText('Getting the reports…')).toBeInTheDocument();
    expect(await screen.findByText('See the full report')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/v1/reports');
  });

  it('shows a plain message when the reports cannot be loaded', async () => {
    api.get.mockRejectedValue(new ApiError(503, 'X', true, 'Something went wrong on our side. Please try again in a moment.'));
    renderAt('/reports');
    expect(await screen.findByText(/Something went wrong on our side/)).toBeInTheDocument();
    api.get.mockRejectedValue(new Error('boom'));
    renderAt('/reports');
    expect(await screen.findByText(/We could not load the reports/)).toBeInTheDocument();
  });

  it('shows one report, and "could not find" for a 404', async () => {
    api.get.mockResolvedValue(sampleReports[0]);
    renderAt(`/reports/${sampleReports[0].session_id}`);
    expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith(`/v1/reports/${sampleReports[0].session_id}`);

    api.get.mockRejectedValue(new ApiError(404, 'NOT_FOUND', false, 'x'));
    renderAt('/reports/nope');
    expect(await screen.findByText('We could not find that report')).toBeInTheDocument();
  });
});

describe('live build: plan', () => {
  const plan = {
    schema_version: 1 as const,
    plan_id: 'plan_x',
    session_id: sampleReports[0].session_id,
    child_id: sampleReports[0].child_id,
    activities: [{ activity_id: 'a', title: 'Sound hunt', text: 'Find three things.' }],
    books: [],
    next_session_at: '2026-10-29T09:00:00Z',
  };

  it('asks the API for the plan of this report and returns it', async () => {
    api.get.mockResolvedValue(plan);
    const { result } = renderHook(() => usePlan(sampleReports[0], true));
    expect(result.current.status).toBe('loading');
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current).toEqual({ status: 'ready', plan });
    expect(api.get).toHaveBeenCalledWith(`/v1/plans/${sampleReports[0].session_id}`);
  });

  it('is "no plan yet" for a 404, and a plain error otherwise', async () => {
    api.get.mockRejectedValue(new ApiError(404, 'NOT_FOUND', false, 'x'));
    const missing = renderHook(() => usePlan(sampleReports[0], true));
    await waitFor(() => expect(missing.result.current.status).toBe('ready'));
    expect(missing.result.current).toEqual({ status: 'ready', plan: null });

    api.get.mockRejectedValue(new ApiError(503, 'X', true, 'Something went wrong on our side.'));
    const down = renderHook(() => usePlan(sampleReports[0], true));
    await waitFor(() => expect(down.result.current.status).toBe('error'));
    expect(down.result.current).toEqual({ status: 'error', message: 'Something went wrong on our side.' });

    api.get.mockRejectedValue(new Error('boom'));
    const odd = renderHook(() => usePlan(sampleReports[0], true));
    await waitFor(() => expect(odd.result.current.status).toBe('error'));
  });

  it('makes no call when the plan is not wanted or there is no report', () => {
    expect(renderHook(() => usePlan(sampleReports[0], false)).result.current).toEqual({ status: 'ready', plan: null });
    expect(renderHook(() => usePlan(null, true)).result.current).toEqual({ status: 'ready', plan: null });
    expect(api.get).not.toHaveBeenCalled();
  });

  it('is open to every signed-in guardian, with no subscription (study: payments are later work)', () => {
    expect(accountStore.hasActiveSubscription()).toBe(false);
    expect(planUnlocked(true)).toBe(true);
    expect(planUnlocked(false)).toBe(false);
  });
});

describe('live build: session driver', () => {
  it('asks the API for a session for this child only', async () => {
    api.post.mockRejectedValue(new Error('offline'));
    const driver = createSessionDriver('child_1');
    const failures: string[] = [];
    driver.onFailed?.((plain) => failures.push(plain));
    driver.start(() => undefined);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(api.post).toHaveBeenCalledWith('/v1/sessions', { child_id: 'child_1' });
    expect(failures).toHaveLength(1);
    driver.stop();
  });
});
